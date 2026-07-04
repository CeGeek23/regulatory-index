"""Lecteur de corpus depuis la base PostgreSQL du dump (acts / versions / subdivisions).

Émet des `NormativeUnit` pour un périmètre de CELEX, à partir UNIQUEMENT du contenu des
articles et de leurs métadonnées — **pas** du graphe `act_relations` du dump (les renvois
inter-textes sont redérivés du texte par `linking/`).

Modèle de données exploité :
- `acts` (métadonnées) → `versions` (1 par langue/date) → `subdivisions` (arbre du texte).
- Le texte d'un article est reconstruit en recollant ses feuilles (paragraph/point/…)
  via `hierarchy_path` ; on retient la version la plus récente pour la langue demandée.
- 1 unité par article, SAUF les articles trop longs (> `MAX_UNIT_CHARS`) : ils sont découpés
  le long de leurs feuilles en plusieurs unités `…#p{k}` pour rester extractibles en entier
  (généralise le cas des articles longs, ex. AIFMD art. 21/37).

DSN via `LALANDE_DSN` ; budget de découpe via `REGINDEX_MAX_UNIT_CHARS`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from typing import Literal

import psycopg

from ..refdata.sources_registry import load_sources_registry
from .unit_loader import NormativeUnit

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5433/lalande"

# Budget de caractères par unité : au-delà, un article est découpé le long de ses feuilles
# (paragraphes/points) en plusieurs unités, pour rester extractible en entier. Env override.
MAX_UNIT_CHARS = int(os.environ.get("REGINDEX_MAX_UNIT_CHARS", "8000"))

_LANG_OUT: dict[str, Literal["EN", "FR"]] = {"en": "EN", "fr": "FR"}


def resolve_dsn(dsn: str | None = None) -> str:
    """DSN explicite, sinon LALANDE_DSN, sinon le conteneur Docker local par défaut."""
    return dsn or os.environ.get("LALANDE_DSN", DEFAULT_DSN)


def registry_celexes() -> list[str]:
    """Tous les CELEX déclarés dans sources_registry.yaml (périmètre par défaut)."""
    return [e.celex for e in load_sources_registry().values() if e.celex]


def _latest_version_id(cur: psycopg.Cursor, act_id: int, language: str) -> int | None:
    cur.execute(
        "SELECT id FROM versions WHERE act_id=%s AND language::text=%s "
        "ORDER BY version_date DESC NULLS LAST, version_number DESC LIMIT 1",
        (act_id, language),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _article_leaves(cur: psycopg.Cursor, version_id: int, art_path: str) -> list[str]:
    """Feuilles (contenu non vide) d'un article, dans l'ordre du document."""
    cur.execute(
        "SELECT content FROM subdivisions "
        "WHERE version_id=%s AND hierarchy_path LIKE %s AND content IS NOT NULL AND content<>'' "
        "ORDER BY hierarchy_path",
        (version_id, art_path + "/%"),
    )
    return [str(r[0]) for r in cur.fetchall()]


def pack_leaves(leaves: list[str], max_chars: int) -> list[list[str]]:
    """Regroupe des feuilles consécutives en blocs dont le texte concaténé (jointure
    par un saut de ligne) reste <= ``max_chars``.

    Une feuille plus longue que ``max_chars`` forme son propre bloc : on ne coupe
    jamais une feuille en plein milieu. L'ordre est préservé, aucune feuille perdue.
    Fonction pure et déterministe (testée hors base).
    """
    groups: list[list[str]] = []
    current: list[str] = []
    length = 0
    for leaf in leaves:
        add = len(leaf) + (1 if current else 0)  # +1 pour le saut de ligne de jointure
        if current and length + add > max_chars:
            groups.append(current)
            current, length, add = [], 0, len(leaf)
        current.append(leaf)
        length += add
    if current:
        groups.append(current)
    return groups


def iter_units(
    celexes: Sequence[str],
    *,
    language: str = "en",
    dsn: str | None = None,
) -> Iterator[NormativeUnit]:
    """Génère les `NormativeUnit` d'un périmètre de CELEX (1 par article, ou plusieurs
    `…#p{k}` si l'article dépasse `MAX_UNIT_CHARS`).

    Les métadonnées (source_id, level, issuer, title, url) viennent de
    `sources_registry.yaml` quand le CELEX y figure, sinon de la table `acts`.
    """
    language = language.lower()
    out_lang = _LANG_OUT.get(language)
    if out_lang is None:
        raise ValueError(f"langue non supportée : {language!r} (attendu 'en' ou 'fr')")

    by_celex = {e.celex: (sid, e) for sid, e in load_sources_registry().items() if e.celex}

    with psycopg.connect(resolve_dsn(dsn)) as conn, conn.cursor() as cur, conn.cursor() as tcur:
        for celex in celexes:
            cur.execute(
                "SELECT id, title, url_eurlex FROM acts WHERE celex=%s AND language::text=%s LIMIT 1",
                (celex, language),
            )
            act = cur.fetchone()
            if act is None:
                continue
            act_id, act_title, act_url = int(act[0]), act[1], act[2]

            version_id = _latest_version_id(cur, act_id, language)
            if version_id is None:
                continue

            reg = by_celex.get(celex)
            source_id = reg[0] if reg else celex
            entry = reg[1] if reg else None
            meta: dict[str, object] = {
                "celex": celex,
                "title": (entry.title if entry else None) or act_title or celex,
                "url": (entry.url if entry else None) or act_url or "",
            }
            if entry is not None:
                meta["level"] = entry.level
                meta["issuer"] = entry.issuer

            cur.execute(
                "SELECT number, title, hierarchy_path FROM subdivisions "
                "WHERE version_id=%s AND subdivision_type::text='article' ORDER BY sequence_order",
                (version_id,),
            )
            for number, art_title, art_path in cur.fetchall():
                leaves = _article_leaves(tcur, version_id, str(art_path))
                head = f"{art_title.strip()}\n" if art_title and art_title.strip() else ""
                num = (str(number) if number else "").strip()
                label = f"Article {num}" if num else "Article"
                title_clean = art_title.strip() if art_title else ""
                if title_clean.lower().startswith("article"):
                    hpath = title_clean
                elif title_clean:
                    hpath = f"{label} — {title_clean}"
                else:
                    hpath = label

                groups = pack_leaves(leaves, MAX_UNIT_CHARS) or [[]]
                multi = len(groups) > 1
                for k, group in enumerate(groups, start=1):
                    body = "\n".join(group)
                    text = (head + body) if k == 1 else body
                    if not text.strip():
                        continue
                    if multi:
                        unit_id = f"{source_id}#{language}#art_{num}#p{k}"
                        unit_path = f"{hpath} — partie {k}/{len(groups)}"
                        unit_meta = {**meta, "article": num, "part": k, "n_parts": len(groups)}
                    else:
                        unit_id = f"{source_id}#{language}#art_{num}"
                        unit_path = hpath
                        unit_meta = {**meta, "article": num}
                    yield NormativeUnit(
                        unit_id=unit_id,
                        source_id=source_id,
                        hierarchy_path=unit_path,
                        text=text,
                        language=out_lang,
                        source_meta=unit_meta,
                    )
