"""Glossaire CONSOLIDÉ de niveau 1 : article de définitions de CHAQUE acte présent dans
data/textes_sources/, puis liste de tous les termes, liste MINIMALE (dédupliquée), acteurs isolés.

Répond à la demande client :
  - articles de définition de l'intégralité des textes de niveau 1 disponibles ;
  - liste de tous les termes + liste minimale (un concept = une entrée) ;
  - isolation de tous les acteurs.

    uv run python scripts/build_l1_glossary.py   # depuis le cache HTML data/textes_sources/, SANS réseau

L'article de définitions de chaque texte est détecté automatiquement (sous-titre
« Definitions/Définitions », ou à défaut la phrase d'amorce « the following definitions… »).

Règle d'acteur (déterministe, sans heuristique) : le `type` de l'override relu fait foi
(acteur ssi actor/investor/supervisor) ; UNIQUEMENT pour un terme NON typé, on tente une
résolution dans le vocabulaire contrôlé config/vocabularies/actors.yaml ; sinon le terme
est listé « untyped » (candidat à compléter — boucle « vocab gaps »).
"""

from __future__ import annotations

import csv
from pathlib import Path

from regulatory_index.glossary import DefinedTerm, harvest_glossary
from regulatory_index.refdata.vocab import load_vocabulary

RAW = Path("data/textes_sources")
OUT = Path("data/exports/glossary")
ACTOR_TYPES = {
    "acteur"
}  # typologie client : seul « acteur » est un acteur (produit/activité = objets)


def _largest(folder: Path, lang: str) -> Path | None:
    files = sorted(folder.glob(f"*_{lang}_*.html"), key=lambda p: p.stat().st_size, reverse=True)
    return files[0] if files else None


def _celex(path: Path) -> str:
    return path.name.split("_", 1)[0]


def _norm(term: str) -> str:
    return " ".join(term.lower().split())


def main() -> int:
    actors_vocab = load_vocabulary("actors")
    objects_vocab = load_vocabulary("objects")

    def actor_status(t: DefinedTerm) -> str:
        # Le type explicite (override relu) fait foi ; le vocab ne sert qu'aux termes non typés.
        if t.type:
            return "actor" if t.type in ACTOR_TYPES else "concept"
        if (
            actors_vocab.resolve(t.term_en) is not None
            or actors_vocab.resolve(t.term_fr) is not None
        ):
            return "actor"
        if (
            objects_vocab.resolve(t.term_en) is not None
            or objects_vocab.resolve(t.term_fr) is not None
        ):
            return "concept"
        return "untyped"

    all_terms: list[DefinedTerm] = []
    if not RAW.exists():
        print(f"/!\\ {RAW} absent — dépose d'abord le HTML des actes L1.")
        return 1
    for folder in sorted(p for p in RAW.iterdir() if p.is_dir()):
        en = _largest(folder, "EN")
        if en is None:
            print(f"  skip {folder.name}: pas de HTML EN")
            continue
        fr = _largest(folder, "FR")
        try:
            terms = harvest_glossary(
                en.read_text(encoding="utf-8"),
                fr.read_text(encoding="utf-8") if fr else "",
                source_id=folder.name,
                celex=_celex(en),
                level=1,
                act_label=folder.name.split("_")[0],
            )
        except Exception as e:  # acte sans article de définitions détectable, HTML inattendu, etc.
            print(f"  skip {folder.name}: {type(e).__name__}: {e}")
            continue
        print(f"  {folder.name}: {len(terms)} termes définis")
        all_terms.extend(terms)

    if not all_terms:
        print("Aucun terme — vérifie que data/textes_sources/<ID>/ contient du HTML EUR-Lex EN.")
        return 1

    # Liste minimale : un terme distinct (par term_en normalisé) = une entrée, multi-sources.
    minimal: dict[str, dict[str, object]] = {}
    for t in all_terms:
        if not (t.term_en.strip() or t.term_fr.strip()):
            continue  # terme non extrait (acte à mise en page tabulaire, ex. CRR) — ignoré
        key = _norm(t.term_en) or _norm(t.term_fr)
        entry = minimal.setdefault(
            key, {"term_en": t.term_en, "term_fr": t.term_fr, "status": "untyped", "sources": []}
        )
        st = actor_status(t)
        if st == "actor" or (st == "concept" and entry["status"] == "untyped"):
            entry["status"] = st
        if not entry["term_fr"] and t.term_fr:
            entry["term_fr"] = t.term_fr
        sources = entry["sources"]
        assert isinstance(sources, list)
        sources.append(t.legal_basis)

    rows = sorted(
        minimal.values(), key=lambda r: (r["status"] != "actor", str(r["term_en"]).lower())
    )
    actors = [r for r in rows if r["status"] == "actor"]
    untyped = [r for r in rows if r["status"] == "untyped"]

    OUT.mkdir(parents=True, exist_ok=True)
    # CSV liste minimale complète
    with (OUT / "glossary_L1_minimal.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["term_en", "term_fr", "status", "n_sources", "sources"])
        for r in rows:
            srcs = r["sources"]
            assert isinstance(srcs, list)
            w.writerow([r["term_en"], r["term_fr"], r["status"], len(srcs), " ; ".join(srcs)])
    # CSV acteurs seuls
    with (OUT / "glossary_L1_actors.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["term_en", "term_fr", "sources"])
        for r in actors:
            srcs = r["sources"]
            assert isinstance(srcs, list)
            w.writerow([r["term_en"], r["term_fr"], " ; ".join(srcs)])
    # MD résumé
    md = [
        "# Glossaire consolidé niveau 1 (liste minimale)\n",
        f"{len(all_terms)} termes bruts → **{len(rows)} termes distincts** "
        f"({len(actors)} acteurs, {len(untyped)} non typés à trier).\n",
        "\n## Acteurs isolés\n",
        "| Terme (EN) | Terme (FR) | Sources |",
        "|---|---|---|",
    ]
    for r in actors:
        srcs = r["sources"]
        assert isinstance(srcs, list)
        md.append(f"| {r['term_en']} | {r['term_fr']} | {' ; '.join(srcs)} |")
    (OUT / "glossary_L1_minimal.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        f"\nTOTAL : {len(all_terms)} termes bruts | {len(rows)} distincts (liste minimale) | "
        f"{len(actors)} acteurs | {len(untyped)} non typés"
    )
    print(f"→ {OUT}/glossary_L1_minimal.csv  (liste minimale complète)")
    print(f"→ {OUT}/glossary_L1_actors.csv   (acteurs isolés)")
    print(f"→ {OUT}/glossary_L1_minimal.md   (résumé lisible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
