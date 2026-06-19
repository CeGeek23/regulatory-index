"""Contrôle de complétude des overrides de glossaire.

Pour chaque `config/glossary/overrides/<acte>.yaml`, compare les étiquettes de points
réellement extraites de l'article de définitions de l'acte (depuis le HTML en cache) aux
étiquettes présentes dans l'override, et signale :
  - MANQUE   : terme extrait sans entrée d'override (pas de `type`) ;
  - ORPHELIN : entrée d'override sans terme correspondant.

Le CELEX est déduit du nom du HTML en cache (pas de table en dur). Sort en code 1 si écart.

Usage : uv run python scripts/check_overrides.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

from regulatory_index.glossary import harvest_glossary

OVERRIDES_DIR = Path("config/glossary/overrides")
RAW_DIR = Path("data/raw")


def _largest_en_html(source_id: str) -> Path | None:
    files = sorted(
        (RAW_DIR / source_id).glob("*_EN_*.html"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    return files[0] if files else None


def main() -> int:
    complete = True
    print(f"{'acte':14}{'extraits':>9}{'override':>9}  écarts")
    for override_path in sorted(OVERRIDES_DIR.glob("*.yaml")):
        source_id = override_path.stem
        override = yaml.safe_load(override_path.read_text(encoding="utf-8")) or {}
        override_labels = {str(label) for label in override}

        html_path = _largest_en_html(source_id)
        if html_path is None:
            print(f"{source_id:14}{'?':>9}{len(override_labels):>9}  (pas de HTML en cache — non vérifiable)")
            continue

        celex = html_path.name.split("_", 1)[0]
        terms = harvest_glossary(
            html_path.read_text(encoding="utf-8"), source_id=source_id, celex=celex, level=1
        )
        extracted_labels = {t.label for t in terms if t.term_en.strip()}
        missing = sorted(extracted_labels - override_labels)
        orphan = sorted(override_labels - extracted_labels)

        flag = ""
        if missing:
            flag += f" MANQUE {missing}"
        if orphan:
            flag += f" ORPHELIN {orphan}"
        if flag:
            complete = False
        print(f"{source_id:14}{len(extracted_labels):>9}{len(override_labels):>9}  {flag or 'OK'}")

    print("\n" + ("Tous les overrides sont complets." if complete else "Écarts détectés — voir ci-dessus."))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
