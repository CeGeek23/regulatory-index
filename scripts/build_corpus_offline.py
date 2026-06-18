"""Construit data/units/corpus.jsonl depuis le HTML déjà en cache (data/raw/), SANS réseau.

Rejoue le manifest (config/sources_manifest.yaml) mais, pour chaque source, lit le plus
gros HTML déjà téléchargé dans data/raw/{source_id}/ au lieu de re-fetcher. Pratique pour
itérer sur les essais d'extraction hors-ligne, et indispensable quand EUR-Lex bloque les
requêtes automatiques (challenge WAF). Le cache doit exister (un `regindex acquire`
réussi au préalable, ou des fichiers HTML déposés à la main dans data/raw/).

Usage : uv run python scripts/build_corpus_offline.py
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

from regulatory_index.ingestion.acquire import load_manifest
from regulatory_index.ingestion.eurlex_html_parser import parse_articles
from regulatory_index.ingestion.unit_loader import NormativeUnit, write_units_jsonl
from regulatory_index.refdata.sources_registry import load_sources_registry

RAW_DIR = Path("data/raw")
OUT = Path("data/units/corpus.jsonl")


def _largest_cached_html(source_id: str, celex: str, language: str) -> Path | None:
    """Le plus gros HTML en cache pour cette source = le vrai document (vs pages d'erreur/WAF)."""
    pattern = str(RAW_DIR / source_id / f"{celex}_{language.upper()}_*.html")
    files = sorted(glob.glob(pattern), key=lambda f: Path(f).stat().st_size, reverse=True)
    return Path(files[0]) if files else None


def main() -> int:
    registry = load_sources_registry()
    units: list[NormativeUnit] = []
    for entry in load_manifest():
        if entry.fetcher != "eurlex" or not entry.celex:
            print(f"  skip {entry.source_id} (fetcher '{entry.fetcher}' non géré hors-ligne)")
            continue
        html_path = _largest_cached_html(entry.source_id, entry.celex, entry.language)
        if html_path is None:
            print(f"  /!\\ {entry.source_id} {entry.language}: aucun HTML en cache — lance `regindex acquire` une fois")
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
