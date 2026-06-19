"""Promeut les termes du glossaire niveau 1 dans le vocabulaire contrôlé.

Câble la boucle voulue par le client : « le glossaire identifie acteurs ET concepts → on les
verse dans le vocabulaire contrôlé → l'extraction d'obligations les reconnaît » (le vocab
alimente le prompt LangExtract et la canonicalisation). Sans ce pas, le glossaire restait un
artefact parallèle.

- termes typés actor/investor/supervisor → `config/vocabularies/actors.yaml`
- autres termes (concepts/objets)        → `config/vocabularies/objects.yaml`

Dédup contre la partie relue à la main (forme exacte, alias, ou singulier). La section « issu du
glossaire, À RELIRE » est RÉGÉNÉRÉE à chaque run (toute section auto antérieure est retirée avant
réécriture) : reproductible et idempotent — relancer produit le même fichier au bit près.

Usage : uv run python scripts/vocab_sync.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

from regulatory_index.glossary import DefinedTerm, harvest_glossary

ACTOR_TYPES = {"actor", "investor", "supervisor"}
RAW = Path("data/raw")
OVERRIDES = Path("config/glossary/overrides")
VOCAB = Path("config/vocabularies")
SECTION = {
    "actors": "# --- Acteurs issus du glossaire niveau 1 (sync auto via scripts/vocab_sync.py — À RELIRE) ---",
    "objects": "# --- Concepts/objets issus du glossaire niveau 1 (sync auto via scripts/vocab_sync.py — À RELIRE) ---",
}


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


def _glossary_terms() -> list[DefinedTerm]:
    """Tous les termes définis du glossaire (chaque acte ayant un override)."""
    terms: list[DefinedTerm] = []
    for source_id in sorted(p.stem for p in OVERRIDES.glob("*.yaml")):
        html = sorted((RAW / source_id).glob("*_EN_*.html"), key=lambda p: p.stat().st_size, reverse=True)
        if not html:
            continue
        terms.extend(
            harvest_glossary(
                html[0].read_text(encoding="utf-8"), source_id=source_id,
                celex=html[0].name.split("_")[0], level=1,
            )
        )
    return terms


def _index(entries: list[dict[str, object]]) -> tuple[set[str], set[str]]:
    """À partir d'entrées de vocab brutes : (surfaces normalisées pour dédup, ids déjà utilisés)."""
    surfaces: set[str] = set()
    ids: set[str] = set()
    for e in entries:
        ident = str(e.get("id") or "")
        if ident:
            ids.add(ident)
        aliases = e.get("aliases")
        keys: list[object] = [e.get("canonical_en"), e.get("canonical_fr"), e.get("id")]
        if isinstance(aliases, list):
            keys.extend(aliases)
        for key in keys:
            if key:
                surfaces.add(str(key).strip().lower())
    return surfaces, ids


def _promote(terms: list[DefinedTerm], vocab_name: str, *, actors_wanted: bool) -> tuple[int, int]:
    """Régénère la section glossaire de `{vocab_name}.yaml`. Renvoie (entrées relues, entrées du glossaire).

    La partie relue à la main = tout ce qui précède le marqueur de section auto ; toute section auto
    antérieure est retirée puis réécrite à neuf → reproductible (relancer donne le même fichier).
    """
    path = VOCAB / f"{vocab_name}.yaml"
    text = path.read_text(encoding="utf-8")
    marker = SECTION[vocab_name]
    idx = text.find(marker)
    base_text = (text[:idx] if idx != -1 else text).rstrip()
    base_entries: list[dict[str, object]] = yaml.safe_load(base_text) or []
    surfaces, used_ids = _index(base_entries)

    def known(term: str) -> bool:
        t = term.strip().lower()
        return t in surfaces or (t.endswith("s") and t[:-1] in surfaces)

    new: dict[str, dict[str, object]] = {}
    for t in terms:
        if not t.term_en.strip():
            continue
        if ((t.type or "") in ACTOR_TYPES) != actors_wanted:
            continue
        if known(t.term_en) or (t.term_fr and known(t.term_fr)):
            continue
        key = " ".join(t.term_en.lower().split())
        if key in new:
            continue
        base = _slug(t.term_en) or _slug(t.term_fr) or "term"
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

    out = base_text + "\n"
    if new:
        out += "\n" + marker + "\n" + yaml.safe_dump(
            list(new.values()), allow_unicode=True, sort_keys=False, width=100
        )
    path.write_text(out, encoding="utf-8")
    return len(base_entries), len(new)


def main() -> int:
    terms = _glossary_terms()
    a_base, a_new = _promote(terms, "actors", actors_wanted=True)
    o_base, o_new = _promote(terms, "objects", actors_wanted=False)
    print(f"actors  : {a_base} relus + {a_new} du glossaire (régénérés) → {a_base + a_new} entrées")
    print(f"objects : {o_base} relus + {o_new} du glossaire (régénérés) → {o_base + o_new} entrées")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
