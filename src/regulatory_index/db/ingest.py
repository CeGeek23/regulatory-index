"""Ingestion déterministe de `regindex` depuis la base corpus Lalande (source unique).

Alimente les tables golden `regindex.regulation` / `source_unit` / `coverage_audit`
à partir des tables `public.acts` / `versions` / `subdivisions` du dump Lalande, en
appliquant des règles STRUCTURELLES générales (aucun `if celex==…`, aucune liste par
article, aucune regex) :

- 1 `regulation` par acte (métadonnées `acts` croisées avec le registre des sources).
- Les `source_unit` sont dérivées de l'arbre des `subdivisions` de la version retenue :
  paragraphes (enfants directs d'article) découpés en phrases, points/subpoints en 1 unité.
  Les notes de bas de page, en-têtes, préambule, racine et annexes ne sont pas émis.
- `source_unit_id` = coordonnées structurelles (celex + numéro d'article + ordinaux/labels
  en ordre document) — STABLE entre versions tant que la structure de l'article ne change
  pas. Jamais dérivé de `subdivisions.id` ni de `hierarchy_path` (non stables inter-version).
- Toute `source_unit` reçoit sa ligne `coverage_audit(status='not_covered')` — l'invariant
  d'exhaustivité du modèle.

Idempotent : re-run ⇒ mêmes ids ; upsert `ON CONFLICT` qui ne réécrit que si le texte
source a changé (hash recalculé). Jamais de doublon, jamais de dérive d'id.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg.rows import TupleRow

from ..refdata.sources_registry import RegistryEntry, load_sources_registry
from ..schemas.source import Level
from .connection import connect

__all__ = [
    "RegulationRow",
    "SourceUnitRow",
    "UpsertCounts",
    "ingest_regulation",
    "ingest_source_units",
    "plan_merge",
    "source_text_hash",
]


# === Modèles de données (dataclasses concrètes) =============================


@dataclass(frozen=True)
class Subdivision:
    """Une ligne `public.subdivisions` (arbre du texte d'une version)."""

    id: int
    parent_id: int | None
    subdivision_type: str
    number: str | None
    title: str | None
    content: str
    hierarchy_path: str


@dataclass(frozen=True)
class SourceUnitRow:
    """Une ligne `regindex.source_unit` prête à insérer (coordonnées + texte + hash)."""

    source_unit_id: str
    regulation_id: str
    title_number: str | None
    chapter_number: str | None
    section_number: str | None
    article_number: str | None
    paragraph_number: str | None
    point_number: str | None
    subpoint_number: str | None
    sentence_number: str | None
    source_text_exact: str
    source_text_hash: str
    structural_path: str
    is_normative: bool


@dataclass(frozen=True)
class RegulationRow:
    """Une ligne `regindex.regulation` (métadonnées croisées acts et registre)."""

    regulation_id: str
    celex_id: str
    official_title: str
    short_name: str | None
    legal_level: str | None
    legal_instrument_type: str | None
    jurisdiction: str | None
    language: str | None
    consolidation_date: date | None
    eurlex_url: str | None
    status: str | None


@dataclass(frozen=True)
class UpsertCounts:
    """Résultat d'un upsert : lignes créées / mises à jour / inchangées."""

    created: int
    updated: int
    unchanged: int

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


@dataclass(frozen=True)
class RegulationIngestResult:
    regulation_id: str
    regulation: UpsertCounts


@dataclass(frozen=True)
class SourceUnitIngestResult:
    regulation_id: str
    source_units: UpsertCounts
    coverage_created: int


# === Règles pures (testables sans base) =====================================


def source_text_hash(text: str) -> str:
    """SHA-256 hexadécimal du texte source (même contrat que `subdivisions.content_hash`)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_sentences(text: str) -> list[str]:
    """Découpe `text` en phrases, sans regex (scan caractère par caractère).

    Frontière de phrase = un `.`/`!`/`?` suivi d'au moins un blanc puis d'une lettre
    MAJUSCULE comme premier caractère non-blanc ; la coupe se fait après le run de
    blancs. Les pièges EUR-Lex (dates `17.11.2009`, `p. 1.`, `No 231/2013`) sont
    neutralisés par la forme des textes : un chiffre ou une minuscule après le point
    n'est pas une frontière. `;`/`:` (séparateurs de listes) ne coupent jamais.
    """
    boundaries: list[tuple[int, int]] = []  # (fin de phrase exclusive, début suivant)
    n = len(text)
    i = 0
    while i < n:
        if text[i] in ".!?":
            j = i + 1
            if j < n and text[j].isspace():
                k = j
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k].isupper():
                    boundaries.append((i + 1, k))
                    i = k
                    continue
        i += 1

    sentences: list[str] = []
    start = 0
    for end, nxt in boundaries:
        sentences.append(text[start:end])
        start = nxt
    if start < n:
        sentences.append(text[start:])
    return [s for s in sentences if s.strip()]


def inline_label(content: str) -> str | None:
    """Label inline d'un point/subpoint : contenu entre le `(` initial et le premier `)`.

    Extraction str pure (`lstrip` + recherche du `)`), sans regex. Retourne `None` si le
    contenu ne commence pas par `(…)`.
    """
    s = content.lstrip()
    if not s or s[0] != "(":
        return None
    close = s.find(")")
    if close <= 1:
        return None
    return s[1:close]


def build_source_unit_id(
    celex: str,
    article_number: str,
    paragraph_number: str | None,
    point_number: str | None,
    subpoint_number: str | None,
    sentence_number: str,
) -> str:
    """Construit un id stable `SU-<CELEX>-ART<n>[-P<n>][-PT<label>][-SPT<label>]-S<nn>`.

    `article_number`/labels passés en MAJUSCULES sans normalisation destructive (le tiret
    est conservé : `69a` et `69-a` sont deux articles distincts ⇒ `ART69A` vs `ART69-A`).
    `S<nn>` est l'ordinal de phrase zero-paddé à 2 (`S01`), `1` fixe pour point/subpoint.
    """
    parts = [f"SU-{celex}", f"ART{article_number.upper()}"]
    if paragraph_number is not None:
        parts.append(f"P{paragraph_number}")
    if point_number is not None:
        parts.append(f"PT{point_number.upper()}")
    if subpoint_number is not None:
        parts.append(f"SPT{subpoint_number.upper()}")
    parts.append(f"S{int(sentence_number):02d}")
    return "-".join(parts)


def _nearest_point_label(node: Subdivision, by_id: dict[int, Subdivision]) -> str | None:
    """Label du point ancêtre le plus proche (chaîne `parent_id`, robuste à l'aplatissement)."""
    current = node.parent_id
    while current is not None and current in by_id:
        ancestor = by_id[current]
        if ancestor.subdivision_type == "point":
            return inline_label(ancestor.content)
        current = ancestor.parent_id
    return None


def build_article_units(
    *,
    celex: str,
    regulation_id: str,
    article: Subdivision,
    ancestors: list[Subdivision],
    descendants: list[Subdivision],
) -> list[SourceUnitRow]:
    """Génère les `SourceUnitRow` d'un article, en ordre document.

    `descendants` doit être trié par `hierarchy_path` (== ordre document intra-version).
    `ancestors` = chapitres/sections/Titres (depth>0), du plus haut au plus bas, pour
    `chapter_number`/`section_number`/`title_number` et le `structural_path` lisible.
    """
    article_number = (article.number or "").strip()
    art_segments = article.hierarchy_path.split("/")
    direct_depth = len(art_segments) + 1

    chapter_number = _ancestor_number(ancestors, "chapter")
    section_number = _ancestor_number(ancestors, "section")
    title_number = _ancestor_number(ancestors, "title")

    article_label = (article.title or "").strip() or f"Article {article_number}"
    path_prefix = [a.title.strip() for a in ancestors if a.title and a.title.strip()]
    path_prefix.append(article_label)

    by_id: dict[int, Subdivision] = {article.id: article}
    for d in descendants:
        by_id[d.id] = d

    paragraph_ordinal: dict[str, int] = {}
    para_counter = 0
    for d in descendants:
        if d.subdivision_type == "paragraph" and len(d.hierarchy_path.split("/")) == direct_depth:
            para_counter += 1
            paragraph_ordinal[d.hierarchy_path] = para_counter

    rows: list[SourceUnitRow] = []
    for d in descendants:
        segments = d.hierarchy_path.split("/")
        direct_child_path = "/".join(segments[:direct_depth])
        paragraph_number = _optional_str(paragraph_ordinal.get(direct_child_path))

        if d.subdivision_type == "paragraph":
            if len(segments) != direct_depth:
                continue  # note de bas de page (paragraphe imbriqué) — exclue
            for idx, sentence in enumerate(split_sentences(d.content), start=1):
                rows.append(
                    _make_row(
                        celex=celex,
                        regulation_id=regulation_id,
                        article_number=article_number,
                        chapter_number=chapter_number,
                        section_number=section_number,
                        title_number=title_number,
                        paragraph_number=paragraph_number,
                        point_number=None,
                        subpoint_number=None,
                        sentence_number=str(idx),
                        text=sentence,
                        path_prefix=path_prefix,
                    )
                )
        elif d.subdivision_type == "point":
            rows.append(
                _make_row(
                    celex=celex,
                    regulation_id=regulation_id,
                    article_number=article_number,
                    chapter_number=chapter_number,
                    section_number=section_number,
                    title_number=title_number,
                    paragraph_number=paragraph_number,
                    point_number=inline_label(d.content),
                    subpoint_number=None,
                    sentence_number="1",
                    text=d.content,
                    path_prefix=path_prefix,
                )
            )
        elif d.subdivision_type == "subpoint":
            rows.append(
                _make_row(
                    celex=celex,
                    regulation_id=regulation_id,
                    article_number=article_number,
                    chapter_number=chapter_number,
                    section_number=section_number,
                    title_number=title_number,
                    paragraph_number=paragraph_number,
                    point_number=_nearest_point_label(d, by_id),
                    subpoint_number=inline_label(d.content),
                    sentence_number="1",
                    text=d.content,
                    path_prefix=path_prefix,
                )
            )
    return rows


def _ancestor_number(ancestors: list[Subdivision], kind: str) -> str | None:
    return next((a.number for a in ancestors if a.subdivision_type == kind and a.number), None)


def _optional_str(value: int | None) -> str | None:
    return None if value is None else str(value)


def _make_row(
    *,
    celex: str,
    regulation_id: str,
    article_number: str,
    chapter_number: str | None,
    section_number: str | None,
    title_number: str | None,
    paragraph_number: str | None,
    point_number: str | None,
    subpoint_number: str | None,
    sentence_number: str,
    text: str,
    path_prefix: list[str],
) -> SourceUnitRow:
    structural_path = " > ".join(
        [*path_prefix, *_leaf_path_parts(paragraph_number, point_number, subpoint_number)]
    )
    return SourceUnitRow(
        source_unit_id=build_source_unit_id(
            celex, article_number, paragraph_number, point_number, subpoint_number, sentence_number
        ),
        regulation_id=regulation_id,
        title_number=title_number,
        chapter_number=chapter_number,
        section_number=section_number,
        article_number=article_number,
        paragraph_number=paragraph_number,
        point_number=point_number,
        subpoint_number=subpoint_number,
        sentence_number=sentence_number,
        source_text_exact=text,
        source_text_hash=source_text_hash(text),
        structural_path=structural_path,
        is_normative=True,
    )


def _leaf_path_parts(
    paragraph_number: str | None, point_number: str | None, subpoint_number: str | None
) -> list[str]:
    parts: list[str] = []
    if paragraph_number is not None:
        parts.append(f"paragraph {paragraph_number}")
    if point_number is not None:
        parts.append(f"point ({point_number})")
    if subpoint_number is not None:
        parts.append(f"subpoint ({subpoint_number})")
    return parts


def plan_merge(new_rows: Iterable[SourceUnitRow], existing_hashes: dict[str, str]) -> UpsertCounts:
    """Compte créées / mises à jour / inchangées en comparant les hash aux lignes en base.

    Fonction pure (le cœur idempotent) : un id absent ⇒ créé ; présent avec hash différent
    ⇒ mis à jour ; présent avec même hash ⇒ inchangé.
    """
    created = updated = unchanged = 0
    for row in new_rows:
        previous = existing_hashes.get(row.source_unit_id)
        if previous is None:
            created += 1
        elif previous != row.source_text_hash:
            updated += 1
        else:
            unchanged += 1
    return UpsertCounts(created=created, updated=updated, unchanged=unchanged)


# === Accès base : lecture corpus Lalande + upsert regindex ==================


def _legal_level(level: Level) -> str:
    return f"L{level}" if isinstance(level, int) else str(level)


def _registry_by_celex() -> dict[str, RegistryEntry]:
    return {e.celex: e for e in load_sources_registry().values() if e.celex}


@dataclass(frozen=True)
class _ActVersion:
    act_id: int
    title: str
    act_type: str | None
    language: str
    short_name: str | None
    eurlex_url: str | None
    version_id: int
    version_date: date | None


def _resolve_act_version(
    cur: psycopg.Cursor[TupleRow], celex: str, language: str
) -> _ActVersion | None:
    cur.execute(
        "SELECT id, title, act_type::text, language::text, short_name, url_eurlex "
        "FROM acts WHERE celex=%s AND language::text=%s LIMIT 1",
        (celex, language),
    )
    act = cur.fetchone()
    if act is None:
        return None
    act_id = int(act[0])
    cur.execute(
        "SELECT id, version_date FROM versions WHERE act_id=%s AND language::text=%s "
        "ORDER BY version_date DESC NULLS LAST, version_number DESC LIMIT 1",
        (act_id, language),
    )
    version = cur.fetchone()
    if version is None:
        return None
    return _ActVersion(
        act_id=act_id,
        title=str(act[1]),
        act_type=None if act[2] is None else str(act[2]),
        language=str(act[3]),
        short_name=(str(act[4]) if act[4] else None),
        eurlex_url=(str(act[5]) if act[5] else None),
        version_id=int(version[0]),
        version_date=version[1],
    )


def _regulation_row(celex: str, act: _ActVersion, entry: RegistryEntry | None) -> RegulationRow:
    return RegulationRow(
        regulation_id=f"REG-{celex}",
        celex_id=celex,
        official_title=act.title,
        short_name=act.short_name,
        legal_level=(_legal_level(entry.level) if entry else None),
        legal_instrument_type=(act.act_type.capitalize() if act.act_type else None),
        jurisdiction=None,
        language=act.language,
        consolidation_date=act.version_date,
        eurlex_url=act.eurlex_url,
        status=None,
    )


def ingest_regulation(
    celex: str, *, language: str = "en", dsn: str | None = None
) -> RegulationIngestResult:
    """Upsert la ligne `regindex.regulation` d'un acte (métadonnées acts et registre).

    Un CELEX absent du registre est tout de même ingéré (champs registre à `None`).
    Idempotent : réécrit seulement si une métadonnée a changé.
    """
    entry = _registry_by_celex().get(celex)
    with connect(dsn) as conn, conn.cursor() as cur:
        act = _resolve_act_version(cur, celex, language)
        if act is None:
            raise LookupError(f"acte introuvable dans le corpus Lalande : {celex} ({language})")
        row = _regulation_row(celex, act, entry)
        inserted = cur.execute(
            "INSERT INTO regindex.regulation "
            "(regulation_id, celex_id, official_title, short_name, legal_level, "
            " legal_instrument_type, jurisdiction, language, consolidation_date, eurlex_url, status)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (regulation_id) DO UPDATE SET "
            "  celex_id=EXCLUDED.celex_id, official_title=EXCLUDED.official_title, "
            "  short_name=EXCLUDED.short_name, legal_level=EXCLUDED.legal_level, "
            "  legal_instrument_type=EXCLUDED.legal_instrument_type, "
            "  jurisdiction=EXCLUDED.jurisdiction, language=EXCLUDED.language, "
            "  consolidation_date=EXCLUDED.consolidation_date, eurlex_url=EXCLUDED.eurlex_url, "
            "  status=EXCLUDED.status, updated_at=now() "
            "WHERE regindex.regulation.official_title IS DISTINCT FROM EXCLUDED.official_title "
            "   OR regindex.regulation.short_name IS DISTINCT FROM EXCLUDED.short_name "
            "   OR regindex.regulation.legal_level IS DISTINCT FROM EXCLUDED.legal_level "
            "   OR regindex.regulation.legal_instrument_type "
            "        IS DISTINCT FROM EXCLUDED.legal_instrument_type "
            "   OR regindex.regulation.language IS DISTINCT FROM EXCLUDED.language "
            "   OR regindex.regulation.consolidation_date "
            "        IS DISTINCT FROM EXCLUDED.consolidation_date "
            "   OR regindex.regulation.eurlex_url IS DISTINCT FROM EXCLUDED.eurlex_url "
            "   OR regindex.regulation.status IS DISTINCT FROM EXCLUDED.status "
            "RETURNING (xmax = 0) AS inserted",
            (
                row.regulation_id,
                row.celex_id,
                row.official_title,
                row.short_name,
                row.legal_level,
                row.legal_instrument_type,
                row.jurisdiction,
                row.language,
                row.consolidation_date,
                row.eurlex_url,
                row.status,
            ),
        ).fetchone()
        counts = _single_row_counts(inserted)
    return RegulationIngestResult(regulation_id=row.regulation_id, regulation=counts)


def _single_row_counts(inserted: TupleRow | None) -> UpsertCounts:
    """RETURNING (xmax=0) d'un upsert 1-ligne : None=inchangé, True=créé, False=maj."""
    if inserted is None:
        return UpsertCounts(created=0, updated=0, unchanged=1)
    if bool(inserted[0]):
        return UpsertCounts(created=1, updated=0, unchanged=0)
    return UpsertCounts(created=0, updated=1, unchanged=0)


def _fetch_subdivisions(cur: psycopg.Cursor[TupleRow], version_id: int) -> list[Subdivision]:
    cur.execute(
        "SELECT id, parent_id, subdivision_type::text, number, title, "
        "COALESCE(content, ''), hierarchy_path "
        "FROM subdivisions WHERE version_id=%s ORDER BY hierarchy_path",
        (version_id,),
    )
    return [
        Subdivision(
            id=int(r[0]),
            parent_id=None if r[1] is None else int(r[1]),
            subdivision_type=str(r[2]),
            number=None if r[3] is None else str(r[3]),
            title=None if r[4] is None else str(r[4]),
            content=str(r[5]),
            hierarchy_path=str(r[6]),
        )
        for r in cur.fetchall()
    ]


def _units_for_version(
    celex: str, regulation_id: str, nodes: list[Subdivision]
) -> list[SourceUnitRow]:
    by_path = {n.hierarchy_path: n for n in nodes}
    rows: list[SourceUnitRow] = []
    for article in nodes:
        if article.subdivision_type != "article":
            continue
        segments = article.hierarchy_path.split("/")
        ancestors = [
            by_path[p]
            for p in ("/".join(segments[:k]) for k in range(2, len(segments)))
            if p in by_path and by_path[p].subdivision_type in ("title", "chapter", "section")
        ]
        prefix = article.hierarchy_path + "/"
        descendants = [n for n in nodes if n.hierarchy_path.startswith(prefix)]
        rows.extend(
            build_article_units(
                celex=celex,
                regulation_id=regulation_id,
                article=article,
                ancestors=ancestors,
                descendants=descendants,
            )
        )
    return rows


_UPSERT_SOURCE_UNIT = (
    "INSERT INTO regindex.source_unit "
    "(source_unit_id, regulation_id, title_number, chapter_number, section_number, "
    " article_number, paragraph_number, point_number, subpoint_number, sentence_number, "
    " source_text_exact, source_text_hash, structural_path, is_normative) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON CONFLICT (source_unit_id) DO UPDATE SET "
    "  source_text_exact=EXCLUDED.source_text_exact, source_text_hash=EXCLUDED.source_text_hash "
    "WHERE regindex.source_unit.source_text_hash <> EXCLUDED.source_text_hash"
)

_INSERT_COVERAGE = (
    "INSERT INTO regindex.coverage_audit (regulation_id, source_unit_id, coverage_status) "
    "SELECT su.regulation_id, su.source_unit_id, 'not_covered' "
    "FROM regindex.source_unit su "
    "WHERE su.regulation_id=%s AND NOT EXISTS ("
    "  SELECT 1 FROM regindex.coverage_audit ca WHERE ca.source_unit_id=su.source_unit_id)"
)


def ingest_source_units(
    celex: str, *, language: str = "en", dsn: str | None = None
) -> SourceUnitIngestResult:
    """Génère et upsert les `source_unit` d'un acte + une `coverage_audit` par unité.

    Suppose la `regulation` déjà présente (cf. `ingest_regulation`). Idempotent : mêmes
    ids, upsert qui ne réécrit que si le texte source a changé (hash recalculé), et une
    seule ligne `coverage_audit(not_covered)` par `source_unit` (invariant du modèle).
    """
    regulation_id = f"REG-{celex}"
    with connect(dsn) as conn, conn.cursor() as cur:
        act = _resolve_act_version(cur, celex, language)
        if act is None:
            raise LookupError(f"acte introuvable dans le corpus Lalande : {celex} ({language})")
        rows = _units_for_version(celex, regulation_id, _fetch_subdivisions(cur, act.version_id))

        cur.execute(
            "SELECT source_unit_id, source_text_hash FROM regindex.source_unit "
            "WHERE regulation_id=%s",
            (regulation_id,),
        )
        existing = {str(r[0]): str(r[1]) for r in cur.fetchall()}
        counts = plan_merge(rows, existing)

        cur.executemany(
            _UPSERT_SOURCE_UNIT,
            [
                (
                    r.source_unit_id,
                    r.regulation_id,
                    r.title_number,
                    r.chapter_number,
                    r.section_number,
                    r.article_number,
                    r.paragraph_number,
                    r.point_number,
                    r.subpoint_number,
                    r.sentence_number,
                    r.source_text_exact,
                    r.source_text_hash,
                    r.structural_path,
                    r.is_normative,
                )
                for r in rows
            ],
        )
        cur.execute(_INSERT_COVERAGE, (regulation_id,))
        coverage_created = cur.rowcount
    return SourceUnitIngestResult(
        regulation_id=regulation_id, source_units=counts, coverage_created=coverage_created
    )
