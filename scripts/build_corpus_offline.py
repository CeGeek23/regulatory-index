"""Construit data/unites/corpus.jsonl depuis le HTML en cache (data/textes_sources/), SANS réseau.

Rejoue le manifest (config/sources_manifest.yaml) : pour chaque source, lit le plus gros
HTML présent dans data/textes_sources/{source_id}/ et le parse en unités normatives. Le cache doit
exister (fichiers HTML EUR-Lex déposés dans data/textes_sources/).

Usage : uv run python scripts/build_corpus_offline.py
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

from regulatory_index.ingestion.eurlex_html_parser import parse_articles
from regulatory_index.ingestion.manifest import load_manifest
from regulatory_index.ingestion.unit_loader import NormativeUnit, write_units_jsonl
from regulatory_index.refdata.sources_registry import load_sources_registry

RAW_DIR = Path("data/textes_sources")
OUT = Path("data/unites/corpus.jsonl")


def _largest_cached_html(source_id: str, celex: str, language: str) -> Path | None:
    """Le plus gros HTML en cache pour cette source = le vrai document (vs pages d'erreur/WAF)."""
    pattern = str(RAW_DIR / source_id / f"{celex}_{language.upper()}_*.html")
    files = sorted(glob.glob(pattern), key=lambda f: Path(f).stat().st_size, reverse=True)
    return Path(files[0]) if files else None


def main() -> int:
    registry = load_sources_registry()
    units: list[NormativeUnit] = []
    for entry in load_manifest():
        html_path = _largest_cached_html(entry.source_id, entry.celex, entry.language)
        if html_path is None:
            print(
                f"  /!\\ {entry.source_id} {entry.language}: aucun HTML en cache dans data/textes_sources/{entry.source_id}/"
            )
            continue
        reg = registry[entry.source_id]
        keep = set(entry.filter_articles) if entry.filter_articles else None
        got = parse_articles(
            html_path.read_text(encoding="utf-8"),
            source_id=entry.source_id,
            celex=entry.celex,
            language=entry.language,
            title=reg.title,
            level=reg.level,
            issuer=reg.issuer,
            url=reg.url,
            keep=keep,
        )
        print(f"  {entry.source_id} {entry.language}: {len(got)} unité(s) depuis {html_path.name}")
        units.extend(got)

    if not units:
        print("Aucune unité produite (cache vide ?).", file=sys.stderr)
        return 1
    write_units_jsonl(units, OUT)
    print(f"OK — {len(units)} unités écrites dans {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
