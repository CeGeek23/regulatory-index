"""Dictionnaire d'amorçage (seed) + candidats à relire pour `regindex` 04/05/06 + 15.

Deux chemins nettement séparés (mode d'emploi client, bloc 2/5) :

- **Seed** (`seed_dictionary`) : lit `config/dictionary_seed.yaml` (conversion versionnée
  de l'onglet 15 — l'Excel n'est jamais lu au runtime) et upsert le référentiel MINIMAL
  dans `dictionary_entry` (les 5 familles) + `actor`/`action`/`regulatory_object` (les 3
  entités). Tout est **ACTIF** (`is_active=true`) : c'est le référentiel validé.
- **Candidats** (`inject_candidates`) : injecte l'enrichissement (vocabulaires
  `config/vocabularies/{actors,actions,objects}.yaml` + 303 acteurs du glossaire consolidé)
  en **CANDIDATS INACTIFS** (`is_active=false`), provenance tracée dans `definition_text`/
  `description`, **jamais actif d'office**. Un candidat dont le nom canonique normalisé
  (casse/espaces/tirets, sans regex) égale une entrée du seed est **SKIPPÉ**.

Idempotence :
- seed = upsert `DO UPDATE` des colonnes qu'il possède (autoritaire), sans toucher les
  colonnes d'enrichissement aval (`definition_text`, `definition_statement_id`…).
- candidats = `DO NOTHING` sur conflit d'id → un candidat déjà relu par un humain
  (is_active passé à true, préfixe nettoyé) n'est **jamais** réécrit.

Les thèmes candidats (`themes.yaml`) sont HORS base : au v2 aucune table entité ne les
porte, et le seed en pose déjà 10 dans `dictionary_entry` — ils restent en revue humaine
hors schéma (choix documenté, évite une migration).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, LiteralString

import psycopg
from psycopg import sql
from psycopg.rows import TupleRow
from pydantic import BaseModel
from yaml import safe_load

from ..refdata.vocab import VocabEntry, load_vocabulary
from .connection import connect, read_only_connection
from .ingest import UpsertCounts

__all__ = [
    "Candidate",
    "CandidatePlan",
    "CandidateResult",
    "DictEntryRow",
    "DictionarySeed",
    "DictionaryStatus",
    "SeedResult",
    "candidate_rows",
    "dedup_candidates",
    "dictionary_entry_rows",
    "dictionary_status",
    "inject_candidates",
    "load_dictionary_seed",
    "normalize_name",
    "seed_dictionary",
    "seed_name_index",
    "seed_plan",
]

_ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = _ROOT / "config" / "dictionary_seed.yaml"
GLOSSARY_ACTORS_CSV = _ROOT / "jalon_cedric 2" / "glossaire_L1_consolide" / "glossary_L1_actors.csv"

DictionaryType = Literal["actor", "action", "object", "statement_type", "theme"]
EntityType = Literal["actor", "action", "object"]


# === Modèles du seed (dataclasses concrètes, 1:1 avec l'onglet 15) ==========


@dataclass(frozen=True)
class SeedActor:
    code: str
    canonical_name: str
    actor_type: str
    parent_code: str | None


@dataclass(frozen=True)
class SeedAction:
    code: str
    canonical_verb: str
    action_category: str
    description: str


@dataclass(frozen=True)
class SeedObject:
    code: str
    canonical_name: str
    object_category: str
    parent_code: str | None


@dataclass(frozen=True)
class SeedStatementType:
    code: str
    statement_type: str


@dataclass(frozen=True)
class SeedTheme:
    code: str
    theme_name: str
    default_subtheme: str
    description: str


@dataclass(frozen=True)
class DictionarySeed:
    actors: tuple[SeedActor, ...]
    actions: tuple[SeedAction, ...]
    objects: tuple[SeedObject, ...]
    statement_types: tuple[SeedStatementType, ...]
    themes: tuple[SeedTheme, ...]


@dataclass(frozen=True)
class DictEntryRow:
    """Une ligne `regindex.dictionary_entry` prête à upsert (clé = (type, code))."""

    dictionary_type: DictionaryType
    code: str
    canonical_name: str
    category: str | None
    parent_code: str | None
    description: str | None


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def load_dictionary_seed(path: Path | None = None) -> DictionarySeed:
    """Parse `config/dictionary_seed.yaml` (source de vérité versionnée du seed)."""
    raw: dict[str, Any] = safe_load((path or SEED_PATH).read_text(encoding="utf-8")) or {}
    return DictionarySeed(
        actors=tuple(
            SeedActor(
                code=str(a["code"]),
                canonical_name=str(a["canonical_name"]),
                actor_type=str(a["actor_type"]),
                parent_code=_opt_str(a.get("parent_code")),
            )
            for a in raw.get("actors", [])
        ),
        actions=tuple(
            SeedAction(
                code=str(a["code"]),
                canonical_verb=str(a["canonical_verb"]),
                action_category=str(a["action_category"]),
                description=str(a["description"]),
            )
            for a in raw.get("actions", [])
        ),
        objects=tuple(
            SeedObject(
                code=str(o["code"]),
                canonical_name=str(o["canonical_name"]),
                object_category=str(o["object_category"]),
                parent_code=_opt_str(o.get("parent_code")),
            )
            for o in raw.get("objects", [])
        ),
        statement_types=tuple(
            SeedStatementType(code=str(s["code"]), statement_type=str(s["statement_type"]))
            for s in raw.get("statement_types", [])
        ),
        themes=tuple(
            SeedTheme(
                code=str(t["code"]),
                theme_name=str(t["theme_name"]),
                default_subtheme=str(t["default_subtheme"]),
                description=str(t["description"]),
            )
            for t in raw.get("themes", [])
        ),
    )


# === Mapping seed -> lignes (fonctions pures, testables sans base) ===========


def dictionary_entry_rows(seed: DictionarySeed) -> list[DictEntryRow]:
    """Les 100 lignes `dictionary_entry` : les 5 familles unifiées (aucune FK, ordre libre)."""
    rows: list[DictEntryRow] = []
    rows += [
        DictEntryRow("actor", a.code, a.canonical_name, a.actor_type, a.parent_code, None)
        for a in seed.actors
    ]
    rows += [
        DictEntryRow("action", a.code, a.canonical_verb, a.action_category, None, a.description)
        for a in seed.actions
    ]
    rows += [
        DictEntryRow("object", o.code, o.canonical_name, o.object_category, o.parent_code, None)
        for o in seed.objects
    ]
    rows += [
        DictEntryRow("statement_type", s.code, s.statement_type, None, None, None)
        for s in seed.statement_types
    ]
    rows += [
        DictEntryRow("theme", t.code, t.theme_name, t.default_subtheme, None, t.description)
        for t in seed.themes
    ]
    return rows


def parents_before_children(
    codes: Iterable[tuple[str, str | None]],
) -> list[str]:
    """Ordonne des `(code, parent_code)` parents avant enfants (FK auto-référencée sûre).

    Tri topologique général (pas seulement 1 niveau) : un code sort dès que son parent est
    déjà sorti (ou absent du lot). Déterministe (ordre d'entrée préservé à profondeur égale).
    """
    pending = list(codes)
    emitted: set[str] = set()
    present = {c for c, _ in pending}
    order: list[str] = []
    while pending:
        progressed = False
        rest: list[tuple[str, str | None]] = []
        for code, parent in pending:
            if parent is None or parent not in present or parent in emitted:
                order.append(code)
                emitted.add(code)
                progressed = True
            else:
                rest.append((code, parent))
        pending = rest
        if not progressed:  # cycle (ne peut pas arriver sur le seed) : émettre tel quel
            order.extend(c for c, _ in pending)
            break
    return order


# === Normalisation de déduplication (sans regex, alignée sur vocab_sync._norm) ==

# Variantes Unicode de tiret/trait d'union (U+2010..U+2015, U+2212), rabattues sur '-'.
_DASHES = "".join(chr(c) for c in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212))


def normalize_name(value: str) -> str:
    """Clé de comparaison : casse, espaces et tirets/traits d'union unifiés.

    « Risk-Management  System » == « risk management system ». Purement typographique,
    sans table de correspondance — même contrat que `scripts/vocab_sync._norm`.
    """
    lowered = value.lower()
    for dash in _DASHES:
        lowered = lowered.replace(dash, "-")
    return " ".join(lowered.replace("-", " ").split())


def _slug(text: str) -> str:
    """Slug MAJUSCULE lisible pour une PK candidate (alnum conservés, reste -> '-')."""
    out: list[str] = []
    prev_sep = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_sep = False
        elif not prev_sep:
            out.append("-")
            prev_sep = True
    return "".join(out).strip("-").upper()


# === Candidats (vocabulaires + glossaire) -> injection inactive =============


@dataclass(frozen=True)
class Candidate:
    """Un candidat à relire : code PK candidat, nom canonique, libellé FR, provenance."""

    dictionary_type: EntityType
    code: str
    canonical_name: str
    display: str | None
    provenance: str


_VOCAB_SOURCES: tuple[tuple[str, EntityType, str], ...] = (
    ("actors", "actor", "ACT-VOC"),
    ("actions", "action", "ACTN-VOC"),
    ("objects", "object", "OBJ-VOC"),
)


def _vocab_provenance(source_file: str, entry: VocabEntry) -> str:
    parts = [f"source: {source_file}", f"id={entry.id}", f"canonical_fr: {entry.canonical_fr}"]
    if entry.aliases:
        parts.append("aliases: " + "; ".join(entry.aliases))
    parts += [f"{k}: {v}" for k, v in sorted(entry.extra.items())]
    return "[CANDIDATE — pending human review | " + " | ".join(parts) + "]"


def _vocab_candidates() -> Iterator[Candidate]:
    for name, dtype, prefix in _VOCAB_SOURCES:
        for entry in load_vocabulary(name).entries:
            yield Candidate(
                dictionary_type=dtype,
                code=f"{prefix}-{_slug(entry.id)}",
                canonical_name=entry.canonical_en,
                display=entry.canonical_fr or None,
                provenance=_vocab_provenance(f"config/vocabularies/{name}.yaml", entry),
            )


def _glossary_candidates(path: Path = GLOSSARY_ACTORS_CSV) -> Iterator[Candidate]:
    # Pas de skip silencieux si le CSV manque (données non versionnées) : les 303 acteurs
    # du glossaire font partie du contrat candidats — mieux vaut FileNotFoundError qu'une
    # injection partielle indétectable.
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            term_en = (row.get("term_en") or "").strip()
            if not term_en:
                continue
            term_fr = (row.get("term_fr") or "").strip()
            sources = (row.get("sources") or "").strip()
            provenance = "[CANDIDATE — pending human review | source: glossary_L1_actors.csv"
            if term_fr:
                provenance += f" | term_fr: {term_fr}"
            if sources:
                provenance += f" | sources: {sources}"
            provenance += "]"
            yield Candidate(
                dictionary_type="actor",
                code=f"ACT-GLO-{_slug(term_en)}",
                canonical_name=term_en,
                display=term_fr or None,
                provenance=provenance,
            )


def candidate_rows() -> list[Candidate]:
    """Tous les candidats bruts (vocabulaires puis glossaire), avant déduplication."""
    return [*_vocab_candidates(), *_glossary_candidates()]


def seed_name_index(seed: DictionarySeed) -> dict[EntityType, set[str]]:
    """Noms canoniques du seed normalisés, par type d'entité (cible de dédup des candidats)."""
    return {
        "actor": {normalize_name(a.canonical_name) for a in seed.actors},
        "action": {normalize_name(a.canonical_verb) for a in seed.actions},
        "object": {normalize_name(o.canonical_name) for o in seed.objects},
    }


@dataclass(frozen=True)
class CandidatePlan:
    """Résultat de la déduplication : ce qu'on garde, ce qu'on écarte et pourquoi."""

    kept: list[Candidate]
    skipped_as_seed: list[Candidate]
    skipped_duplicate: list[Candidate]


def dedup_candidates(
    candidates: Iterable[Candidate], seed_index: dict[EntityType, set[str]]
) -> CandidatePlan:
    """Écarte les candidats déjà couverts par le seed, puis les doublons intra-lot (1er gagne).

    Fonction pure. Un candidat est SKIPPÉ si son nom canonique normalisé égale une entrée du
    seed de MÊME type (règle du mode d'emploi), ou si un candidat de même type/nom a déjà été
    gardé dans ce lot (vocab avant glossaire — évite un doublon d'acteur des deux sources).
    """
    kept: list[Candidate] = []
    skipped_as_seed: list[Candidate] = []
    skipped_duplicate: list[Candidate] = []
    seen: dict[EntityType, set[str]] = {"actor": set(), "action": set(), "object": set()}
    for cand in candidates:
        norm = normalize_name(cand.canonical_name)
        if norm in seed_index.get(cand.dictionary_type, set()):
            skipped_as_seed.append(cand)
        elif norm in seen[cand.dictionary_type]:
            skipped_duplicate.append(cand)
        else:
            seen[cand.dictionary_type].add(norm)
            kept.append(cand)
    return CandidatePlan(kept, skipped_as_seed, skipped_duplicate)


# === Plan / résultats ========================================================


@dataclass(frozen=True)
class SeedResult:
    dictionary_entry: UpsertCounts
    actor: UpsertCounts
    action: UpsertCounts
    regulatory_object: UpsertCounts


@dataclass(frozen=True)
class CandidateResult:
    actor_inserted: int
    action_inserted: int
    object_inserted: int
    skipped_as_seed: int
    skipped_duplicate: int


def seed_plan(seed: DictionarySeed) -> dict[str, Any]:
    """Plan (dry-run) : nombre de lignes cibles par table, sans écrire en base."""
    entries = dictionary_entry_rows(seed)
    by_type: dict[str, int] = {}
    for row in entries:
        by_type[row.dictionary_type] = by_type.get(row.dictionary_type, 0) + 1
    return {
        "dictionary_entry": {"total": len(entries), "by_type": by_type},
        "actor": len(seed.actors),
        "action": len(seed.actions),
        "regulatory_object": len(seed.objects),
    }


# === Upsert seed (autoritaire, DO UPDATE sur colonnes possédées) ============


def _plan_counts(
    items: Iterable[tuple[str, tuple[Any, ...]]], existing: dict[str, tuple[Any, ...]]
) -> UpsertCounts:
    """Compte créées/màj/inchangées : clé absente=créée, contenu différent=màj, égal=inchangée."""
    created = updated = unchanged = 0
    for key, content in items:
        previous = existing.get(key)
        if previous is None:
            created += 1
        elif previous != content:
            updated += 1
        else:
            unchanged += 1
    return UpsertCounts(created=created, updated=updated, unchanged=unchanged)


def _upsert_dictionary_entries(
    cur: psycopg.Cursor[TupleRow], rows: list[DictEntryRow]
) -> UpsertCounts:
    cur.execute(
        "SELECT dictionary_type, code, canonical_name, category, parent_code, description "
        "FROM regindex.dictionary_entry"
    )
    existing = {f"{r[0]}\x00{r[1]}": (r[2], r[3], r[4], r[5]) for r in cur.fetchall()}
    counts = _plan_counts(
        (
            (
                f"{r.dictionary_type}\x00{r.code}",
                (r.canonical_name, r.category, r.parent_code, r.description),
            )
            for r in rows
        ),
        existing,
    )
    cur.executemany(
        "INSERT INTO regindex.dictionary_entry "
        "(dictionary_type, code, canonical_name, category, parent_code, description) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (dictionary_type, code) DO UPDATE SET "
        "  canonical_name=EXCLUDED.canonical_name, category=EXCLUDED.category, "
        "  parent_code=EXCLUDED.parent_code, description=EXCLUDED.description",
        [
            (r.dictionary_type, r.code, r.canonical_name, r.category, r.parent_code, r.description)
            for r in rows
        ],
    )
    return counts


def _upsert_actors(cur: psycopg.Cursor[TupleRow], seed: DictionarySeed) -> UpsertCounts:
    codes = [a.code for a in seed.actors]
    cur.execute(
        "SELECT actor_id, canonical_name, actor_type, parent_actor_id "
        "FROM regindex.actor WHERE actor_id = ANY(%s)",
        (codes,),
    )
    existing = {str(r[0]): (r[1], r[2], r[3]) for r in cur.fetchall()}
    counts = _plan_counts(
        ((a.code, (a.canonical_name, a.actor_type, a.parent_code)) for a in seed.actors),
        existing,
    )
    order = parents_before_children((a.code, a.parent_code) for a in seed.actors)
    by_code = {a.code: a for a in seed.actors}
    cur.executemany(
        "INSERT INTO regindex.actor "
        "(actor_id, canonical_name, actor_type, parent_actor_id, is_active) "
        "VALUES (%s,%s,%s,%s,true) "
        "ON CONFLICT (actor_id) DO UPDATE SET "
        "  canonical_name=EXCLUDED.canonical_name, actor_type=EXCLUDED.actor_type, "
        "  parent_actor_id=EXCLUDED.parent_actor_id, is_active=true, updated_at=now()",
        [
            (
                by_code[c].code,
                by_code[c].canonical_name,
                by_code[c].actor_type,
                by_code[c].parent_code,
            )
            for c in order
        ],
    )
    return counts


def _upsert_actions(cur: psycopg.Cursor[TupleRow], seed: DictionarySeed) -> UpsertCounts:
    codes = [a.code for a in seed.actions]
    cur.execute(
        "SELECT action_id, canonical_verb, action_category, description "
        "FROM regindex.action WHERE action_id = ANY(%s)",
        (codes,),
    )
    existing = {str(r[0]): (r[1], r[2], r[3]) for r in cur.fetchall()}
    counts = _plan_counts(
        ((a.code, (a.canonical_verb, a.action_category, a.description)) for a in seed.actions),
        existing,
    )
    cur.executemany(
        "INSERT INTO regindex.action "
        "(action_id, canonical_verb, action_category, description, is_active) "
        "VALUES (%s,%s,%s,%s,true) "
        "ON CONFLICT (action_id) DO UPDATE SET "
        "  canonical_verb=EXCLUDED.canonical_verb, action_category=EXCLUDED.action_category, "
        "  description=EXCLUDED.description, is_active=true, updated_at=now()",
        [(a.code, a.canonical_verb, a.action_category, a.description) for a in seed.actions],
    )
    return counts


def _upsert_objects(cur: psycopg.Cursor[TupleRow], seed: DictionarySeed) -> UpsertCounts:
    codes = [o.code for o in seed.objects]
    cur.execute(
        "SELECT object_id, canonical_name, object_category, parent_object_id "
        "FROM regindex.regulatory_object WHERE object_id = ANY(%s)",
        (codes,),
    )
    existing = {str(r[0]): (r[1], r[2], r[3]) for r in cur.fetchall()}
    counts = _plan_counts(
        ((o.code, (o.canonical_name, o.object_category, o.parent_code)) for o in seed.objects),
        existing,
    )
    order = parents_before_children((o.code, o.parent_code) for o in seed.objects)
    by_code = {o.code: o for o in seed.objects}
    cur.executemany(
        "INSERT INTO regindex.regulatory_object "
        "(object_id, canonical_name, object_category, parent_object_id, is_active) "
        "VALUES (%s,%s,%s,%s,true) "
        "ON CONFLICT (object_id) DO UPDATE SET "
        "  canonical_name=EXCLUDED.canonical_name, object_category=EXCLUDED.object_category, "
        "  parent_object_id=EXCLUDED.parent_object_id, is_active=true, updated_at=now()",
        [
            (
                by_code[c].code,
                by_code[c].canonical_name,
                by_code[c].object_category,
                by_code[c].parent_code,
            )
            for c in order
        ],
    )
    return counts


def seed_dictionary(*, dsn: str | None = None) -> SeedResult:
    """Upsert le seed minimal (ACTIF) : `dictionary_entry` (les 5 familles) + les 3 entités.

    Autoritaire : `DO UPDATE` des colonnes possédées par le seed ; ne touche jamais les
    colonnes d'enrichissement aval (`definition_text`, `definition_statement_id`,
    `source_regulation_id`…). Idempotent : re-run = mêmes ids, comptes en `unchanged`.
    """
    seed = load_dictionary_seed()
    with connect(dsn) as conn, conn.cursor() as cur:
        entry_counts = _upsert_dictionary_entries(cur, dictionary_entry_rows(seed))
        actor_counts = _upsert_actors(cur, seed)
        action_counts = _upsert_actions(cur, seed)
        object_counts = _upsert_objects(cur, seed)
    return SeedResult(
        dictionary_entry=entry_counts,
        actor=actor_counts,
        action=action_counts,
        regulatory_object=object_counts,
    )


# === Injection des candidats (INACTIFS, DO NOTHING = ne clobbe jamais une revue) ==

_INSERT_ACTOR_CANDIDATE = (
    "INSERT INTO regindex.actor "
    "(actor_id, canonical_name, display_name, definition_text, is_active) "
    "VALUES (%s,%s,%s,%s,false) ON CONFLICT (actor_id) DO NOTHING"
)
_INSERT_ACTION_CANDIDATE = (
    "INSERT INTO regindex.action "
    "(action_id, canonical_verb, display_label, description, is_active) "
    "VALUES (%s,%s,%s,%s,false) ON CONFLICT (action_id) DO NOTHING"
)
_INSERT_OBJECT_CANDIDATE = (
    "INSERT INTO regindex.regulatory_object "
    "(object_id, canonical_name, display_name, description, is_active) "
    "VALUES (%s,%s,%s,%s,false) ON CONFLICT (object_id) DO NOTHING"
)


def _insert_candidates(
    cur: psycopg.Cursor[TupleRow], statement: LiteralString, cands: list[Candidate]
) -> int:
    if not cands:
        return 0
    cur.executemany(statement, [(c.code, c.canonical_name, c.display, c.provenance) for c in cands])
    return max(cur.rowcount, 0)


def inject_candidates(*, dsn: str | None = None) -> CandidateResult:
    """Injecte les candidats INACTIFS (vocabulaires + glossaire), dédupliqués contre le seed.

    `DO NOTHING` sur conflit d'id : un candidat déjà présent (a fortiori relu et activé par un
    humain) n'est jamais réécrit. Provenance dans `definition_text`/`description`.
    """
    plan = dedup_candidates(candidate_rows(), seed_name_index(load_dictionary_seed()))
    kept = plan.kept
    with connect(dsn) as conn, conn.cursor() as cur:
        actor_n = _insert_candidates(
            cur, _INSERT_ACTOR_CANDIDATE, [c for c in kept if c.dictionary_type == "actor"]
        )
        action_n = _insert_candidates(
            cur, _INSERT_ACTION_CANDIDATE, [c for c in kept if c.dictionary_type == "action"]
        )
        object_n = _insert_candidates(
            cur, _INSERT_OBJECT_CANDIDATE, [c for c in kept if c.dictionary_type == "object"]
        )
    return CandidateResult(
        actor_inserted=actor_n,
        action_inserted=action_n,
        object_inserted=object_n,
        skipped_as_seed=len(plan.skipped_as_seed),
        skipped_duplicate=len(plan.skipped_duplicate),
    )


# === Status (actif vs candidat) =============================================


class DictionaryEntryStat(BaseModel):
    dictionary_type: str
    entries: int


class DictionaryTableStat(BaseModel):
    table: str
    active: int
    candidate: int


class DictionaryStatus(BaseModel):
    entries: list[DictionaryEntryStat]
    tables: list[DictionaryTableStat]


_ENTITY_TABLES = ("actor", "action", "regulatory_object")


def dictionary_status(dsn: str | None = None) -> DictionaryStatus:
    """État du dictionnaire : `dictionary_entry` par famille + actif/candidat par entité."""
    with read_only_connection(dsn) as conn:
        entry_rows = conn.execute(
            b"SELECT dictionary_type, count(*) FROM regindex.dictionary_entry "
            b"GROUP BY dictionary_type ORDER BY dictionary_type"
        ).fetchall()
        entries = [
            DictionaryEntryStat(dictionary_type=str(r[0]), entries=int(r[1])) for r in entry_rows
        ]
        tables: list[DictionaryTableStat] = []
        for table in _ENTITY_TABLES:
            query = sql.SQL(
                "SELECT count(*) FILTER (WHERE is_active), "
                "count(*) FILTER (WHERE NOT is_active) FROM regindex.{}"
            ).format(sql.Identifier(table))
            row = conn.execute(query).fetchone()
            active = int(row[0]) if row and row[0] is not None else 0
            candidate = int(row[1]) if row and row[1] is not None else 0
            tables.append(DictionaryTableStat(table=table, active=active, candidate=candidate))
    return DictionaryStatus(entries=entries, tables=tables)
