"""Construit data/unites/corpus.jsonl depuis la base PostgreSQL du dump.

Périmètre par défaut = tous les CELEX déclarés dans sources_registry.yaml.
Override : passer des CELEX en arguments positionnels. Langue via --lang en|fr.

Les articles + leurs métadonnées viennent de la base ; les renvois inter-textes ne sont
PAS lus du dump — ils sont redérivés du texte par le linking du pipeline
(citation_extractor + graph_builder).

Usage :
    uv run python scripts/build_corpus_from_db.py                # tout le périmètre registry, EN
    uv run python scripts/build_corpus_from_db.py 32011L0061     # un acte
    uv run python scripts/build_corpus_from_db.py --lang fr
"""

from __future__ import annotations

import sys
from pathlib import Path

from regulatory_index.ingestion.db_corpus import iter_units, registry_celexes
from regulatory_index.ingestion.unit_loader import NormativeUnit, write_units_jsonl

OUT = Path("data/unites/corpus.jsonl")


def main(argv: list[str]) -> int:
    language = "en"
    celexes: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--lang":
            i += 1
            language = argv[i] if i < len(argv) else language
        elif arg.startswith("--lang="):
            language = arg.split("=", 1)[1]
        else:
            celexes.append(arg)
        i += 1
    if not celexes:
        celexes = registry_celexes()

    units: list[NormativeUnit] = []
    acts: set[str] = set()
    for unit in iter_units(celexes, language=language):
        units.append(unit)
        acts.add(unit.source_id)

    if not units:
        print("Aucune unité produite (base injoignable ? mauvais CELEX/langue ?)", file=sys.stderr)
        return 1
    write_units_jsonl(units, OUT)
    print(f"OK — {len(units)} unités sur {len(acts)} acte(s) ({language}) → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
