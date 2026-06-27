"""Lecteur de corpus depuis la base PostgreSQL du dump (acts / versions / subdivisions).

Émet des `NormativeUnit` (1 par article) pour un périmètre de CELEX, à partir
UNIQUEMENT du contenu des articles et de leurs métadonnées — **pas** du graphe
`act_relations` du dump (les renvois inter-textes sont redérivés du texte par `linking/`).

Modèle de données exploité :
- `acts` (métadonnées) → `versions` (1 par langue/date) → `subdivisions` (arbre du texte).
- Le texte d'un article est reconstruit en recollant ses feuilles (paragraph/point/…)
  via `hierarchy_path` ; on retient la version la plus récente pour la langue demandée.

DSN configurable via la variable d'env `LALANDE_DSN` (déploiement VPS).
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from typing import Literal

import psycopg

from ..refdata.sources_registry import load_sources_registry
from .unit_loader import NormativeUnit

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5433/lalande"

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


def _article_text(
    cur: psycopg.Cursor, version_id: int, art_path: str, art_title: str | None
) -> str:
    """Texte complet d'un article = son titre + ses feuilles recollées dans l'ordre du document."""
    cur.execute(
        "SELECT content FROM subdivisions "
        "WHERE version_id=%s AND hierarchy_path LIKE %s AND content IS NOT NULL AND content<>'' "
        "ORDER BY hierarchy_path",
        (version_id, art_path + "/%"),
    )
    leaves = [str(r[0]) for r in cur.fetchall()]
    head = f"{art_title.strip()}\n" if art_title and art_title.strip() else ""
    return head + "\n".join(leaves)


def iter_units(
    celexes: Sequence[str],
    *,
    language: str = "en",
    dsn: str | None = None,
) -> Iterator[NormativeUnit]:
    """Génère 1 `NormativeUnit` par article, pour chaque CELEX du périmètre.

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
                text = _article_text(tcur, version_id, str(art_path), art_title)
                if not text.strip():
                    continue
                num = (str(number) if number else "").strip()
                label = f"Article {num}" if num else "Article"
                title_clean = art_title.strip() if art_title else ""
                if title_clean.lower().startswith("article"):
                    hpath = title_clean
                elif title_clean:
                    hpath = f"{label} — {title_clean}"
                else:
                    hpath = label
                yield NormativeUnit(
                    unit_id=f"{source_id}#{language}#art_{num}",
                    source_id=source_id,
                    hierarchy_path=hpath,
                    text=text,
                    language=out_lang,
                    source_meta={**meta, "article": num},
                )
