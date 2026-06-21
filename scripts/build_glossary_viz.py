"""Visualisation « ancrée » du GLOSSAIRE (le brief client) : l'article de définitions d'un acte,
chaque terme défini surligné et coloré par **acteur vs concept**, infobulle = type + base légale + FR.

C'est la version « grounded » adaptée à la demande : isoler les acteurs des concepts, à partir des
articles de définition. Construit du cache (HTML EUR-Lex + override relu), aucun LLM. HTML autonome.

Usage : uv run python scripts/build_glossary_viz.py
Sortie : data/exports/presentation/glossaire_ancre.html
"""

from __future__ import annotations

import html
from pathlib import Path

from regulatory_index.glossary import harvest_glossary

RAW = Path("data/raw")
OUT = Path("data/exports/presentation/glossaire_ancre.html")
ACTS = [("AIFMD_L1", "AIFMD — article 4 (définitions)")]
ACTOR_TYPES = {"actor", "investor", "supervisor"}
ACTOR_COLOUR = "#2E75B6"   # acteur (qui est régulé / agit)
CONCEPT_COLOUR = "#C55A11"  # concept / objet (de quoi on parle)


def _largest(source_id: str, lang: str) -> Path | None:
    files = sorted((RAW / source_id).glob(f"*_{lang}_*.html"), key=lambda p: p.stat().st_size, reverse=True)
    return files[0] if files else None


def _section(source_id: str, title: str) -> tuple[str, int, int]:
    en = _largest(source_id, "EN")
    if en is None:
        return "", 0, 0
    fr = _largest(source_id, "FR")
    terms = [
        t for t in harvest_glossary(
            en.read_text(encoding="utf-8"),
            fr.read_text(encoding="utf-8") if fr else "",
            source_id=source_id, celex=en.name.split("_")[0], level=1,
            act_label=source_id.split("_")[0],
        ) if t.term_en.strip()
    ]
    n_actor = sum(1 for t in terms if (t.type or "") in ACTOR_TYPES)
    rows: list[str] = []
    for t in terms:
        is_actor = (t.type or "") in ACTOR_TYPES
        colour = ACTOR_COLOUR if is_actor else CONCEPT_COLOUR
        badge = (t.type or "concept")
        tip = f"{'ACTEUR' if is_actor else 'CONCEPT'} · type: {badge} · {t.legal_basis}"
        if t.term_fr:
            tip += f" · FR: {t.term_fr}"
        definition = html.escape((t.definition_en or "").strip())
        rows.append(
            f'<div class="pt"><span class="lbl">({html.escape(t.label)})</span> '
            f'<mark class="term" style="background:{colour}1A;border-bottom:2px solid {colour}" '
            f'title="{html.escape(tip)}"><b style="color:{colour}">‘{html.escape(t.term_en)}’</b>'
            f'<span class="badge" style="background:{colour}">{html.escape(badge)}</span></mark> '
            f'<span class="def">{definition}</span></div>'
        )
    block = (
        f'<section><h2>{html.escape(title)} '
        f'<span class="count">{len(terms)} termes · {n_actor} acteurs · {len(terms) - n_actor} concepts</span></h2>'
        f'{"".join(rows)}</section>'
    )
    return block, len(terms), n_actor


def main() -> int:
    sections: list[str] = []
    total = total_actor = 0
    for source_id, title in ACTS:
        block, n, na = _section(source_id, title)
        if block:
            sections.append(block)
            total += n
            total_actor += na
    if not sections:
        raise SystemExit(f"Aucun HTML en cache sous {RAW} — rien à afficher.")

    doc = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Glossaire ancré — acteurs vs concepts</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2a37;background:#f7f8fa}}
 header{{background:#0B5394;color:#fff;padding:22px 32px}}
 header h1{{margin:0 0 6px;font-size:22px}} header p{{margin:0;opacity:.92;font-size:14px}}
 .legend{{padding:14px 32px;background:#fff;border-bottom:1px solid #e5e7eb;font-size:14px}}
 .legend i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin:0 6px 0 18px;vertical-align:middle}}
 section{{background:#fff;margin:20px 32px;padding:20px 26px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 h2{{font-size:17px;color:#0B5394;margin:0 0 16px}}
 .count{{font-size:13px;font-weight:normal;color:#6b7280;margin-left:8px}}
 .pt{{margin:9px 0;line-height:1.6;font-size:14.5px}}
 .lbl{{color:#9aa3af;font-weight:bold;margin-right:4px}}
 mark.term{{border-radius:4px;padding:1px 4px;cursor:help;white-space:nowrap}}
 .badge{{color:#fff;font-size:10px;font-weight:bold;border-radius:3px;padding:1px 5px;margin-left:6px;vertical-align:middle;text-transform:uppercase}}
 .def{{color:#374151}}
 footer{{padding:18px 32px;color:#6b7280;font-size:13px}}
</style></head><body>
<header><h1>Glossaire ancré dans le texte — acteurs isolés des concepts</h1>
<p>À partir de l'<b>article de définitions</b>, chaque terme défini est surligné et coloré selon qu'il
désigne un <b>acteur</b> (qui est régulé / agit) ou un <b>concept</b> (de quoi on parle). Survolez un
terme pour son type et sa base légale. {total} termes · {total_actor} acteurs.</p></header>
<div class="legend"><b>Légende :</b>
 <i style="background:{ACTOR_COLOUR}"></i> Acteur
 <i style="background:{CONCEPT_COLOUR}"></i> Concept / objet</div>
{''.join(sections)}
<footer>Données réelles du projet · termes &amp; définitions repris mot pour mot · classification acteur/concept (relue pour AIFMD).</footer>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"→ {OUT}  ({total} termes, {total_actor} acteurs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
