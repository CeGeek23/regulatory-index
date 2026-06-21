"""Bascule le cache du périmètre niveau 1 sur les versions CONSOLIDÉES (les plus à jour/complètes).

Pour chaque texte : résout le dernier CELEX consolidé (métadonnées RDF), télécharge le HTML
EN + FR consolidé (API Cellar), puis retire le HTML de base du cache pour que la suite de la chaîne
(harvest, classification, vocab) tourne sur le consolidé. Best-effort : un texte sans version
consolidée, ou dont le fetch échoue, garde sa version de base.

Usage : uv run python scripts/fetch_consolidated.py
"""

from __future__ import annotations

from pathlib import Path

from build_l1_glossary import L1_PERIMETER

from regulatory_index.ingestion.eurlex_fetcher import fetch_to_disk, latest_consolidated_celex

RAW = Path("data/raw")


def main() -> int:
    switched = kept = failed = 0
    for source_id, base_celex in L1_PERIMETER.items():
        folder = RAW / source_id
        try:
            cons = latest_consolidated_celex(base_celex)
        except Exception as exc:  # réseau / RDF indisponible
            print(f"  {source_id:16} résolution consolidé échouée ({type(exc).__name__}) → base conservée")
            failed += 1
            continue
        if not cons or cons == base_celex:
            print(f"  {source_id:16} pas de version consolidée → base ({base_celex}) conservée")
            kept += 1
            continue
        try:
            fetch_to_disk(cons, "EN", folder)  # EN obligatoire
        except Exception as exc:
            print(f"  {source_id:16} fetch EN consolidé échoué ({type(exc).__name__}) → base conservée")
            failed += 1
            continue
        try:
            fetch_to_disk(cons, "FR", folder)  # FR best-effort
        except Exception:
            print(f"  {source_id:16} (FR consolidé indisponible — EN seul)")
        # Retire la version de base pour que `_largest` prenne le consolidé.
        for old in folder.glob(f"{base_celex}_*.html"):
            old.unlink()
        print(f"  {source_id:16} {base_celex} → {cons}  ✓")
        switched += 1

    print(f"\nBascule : {switched} consolidés, {kept} sans consolidé (base gardée), {failed} échecs réseau.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
