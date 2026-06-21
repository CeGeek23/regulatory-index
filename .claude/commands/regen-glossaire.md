---
description: Régénère toutes les sorties du glossaire depuis les overrides (sans fetch ni reclassif)
---

Régénère toutes les sorties du glossaire à partir des overrides actuels, **sans** re-télécharger
ni reclasser (donc rapide et hors-ligne) :

1. `just vocab-sync` — verse les acteurs du glossaire dans le vocabulaire contrôlé.
2. `just glossary-l1-cache` — reconstruit la liste minimale + acteurs (cache `data/raw/` uniquement).
3. `PYTHONPATH=src uv run --no-sync python scripts/build_glossary_viz.py` — régénère la visu HTML ancrée.

Puis rapporte les **compteurs finaux** (termes bruts / distincts / acteurs) et les chemins des fichiers produits.

Ne commit pas : laisse-moi vérifier d'abord.
