"""Promeut les ACTEURS du glossaire niveau 1 dans le vocabulaire contrôlé `actors.yaml`.

Câble la boucle voulue par le client : « le glossaire identifie les acteurs → on les verse
dans le vocabulaire contrôlé → l'extraction d'obligations les reconnaît » (le vocab alimente
à la fois le prompt LangExtract et la canonicalisation). Sans ce pas, le glossaire restait un
artefact parallèle et le vocab ne grossissait pas.

Pour chaque terme du glossaire typé actor/investor/supervisor :
- s'il résout déjà dans `actors.yaml` (forme exacte, alias, ou singulier) → ignoré (dédup) ;
- sinon → ajouté comme nouvelle entrée (id, canonical_en/fr, legal_basis), dans une section
  clairement marquée « issu du glossaire, À RELIRE ».

Idempotent (au run suivant, les entrées ajoutées résolvent → ignorées). Usage :
    uv run python scripts/vocab_sync.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

from regulatory_index.glossary import harvest_glossary
from regulatory_index.refdata.vocab import load_vocabulary

ACTOR_TYPES = {"actor", "investor", "supervisor"}
RAW = Path("data/raw")
OVERRIDES = Path("config/glossary/overrides")
ACTORS_YAML = Path("config/vocabularies/actors.yaml")
SECTION = "# --- Acteurs issus du glossaire niveau 1 (sync auto via scripts/vocab_sync.py — À RELIRE) ---"


def _slug(text: str) -> str:
    out: list[str] = []
    prev = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev = False
        elif not prev:
            out.append("_")
            prev = True
    return "".join(out).strip("_")


def main() -> int:
    actors = load_vocabulary("actors")

    def known(term: str) -> bool:
        # forme exacte, ou singulier (gère pluriel « AIFMs » -> « AIFM »)
        return actors.resolve(term) is not None or (
            term.endswith("s") and actors.resolve(term[:-1]) is not None
        )

    used_ids = set(actors.ids)
    new: dict[str, dict[str, object]] = {}  # valeurs mixtes (str + aliases: list)
    for source_id in sorted(p.stem for p in OVERRIDES.glob("*.yaml")):
        html = sorted((RAW / source_id).glob("*_EN_*.html"), key=lambda p: p.stat().st_size, reverse=True)
        if not html:
            continue
        for t in harvest_glossary(
            html[0].read_text(encoding="utf-8"), source_id=source_id,
            celex=html[0].name.split("_")[0], level=1,
        ):
            if (t.type or "") not in ACTOR_TYPES or not t.term_en.strip():
                continue
            if known(t.term_en) or (t.term_fr and known(t.term_fr)):
                continue
            key = " ".join(t.term_en.lower().split())
            if key in new:
                continue
            base = _slug(t.term_en) or f"{source_id.lower()}_{t.label}"
            ident, i = base, 2
            while ident in used_ids:
                ident, i = f"{base}_{i}", i + 1
            used_ids.add(ident)
            new[key] = {
                "id": ident,
                "canonical_en": t.term_en,
                "canonical_fr": t.term_fr or t.term_en,
                "aliases": [],
                "legal_basis": t.legal_basis,
            }

    if not new:
        print("Vocab déjà à jour — aucun nouvel acteur à ajouter.")
        return 0

    block = "\n\n" + SECTION + "\n" + yaml.safe_dump(
        list(new.values()), allow_unicode=True, sort_keys=False, width=100
    )
    ACTORS_YAML.write_text(ACTORS_YAML.read_text(encoding="utf-8").rstrip() + "\n" + block, encoding="utf-8")
    print(f"{len(new)} nouveaux acteurs versés dans {ACTORS_YAML}")
    print(f"  vocab actors : {len(actors.entries)} -> {len(actors.entries) + len(new)} entrées")
    print("  exemples :", ", ".join(list(new)[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
