"""Visualisation « ancrée » du GLOSSAIRE (brief client) : le TEXTE RÉEL de l'article de définitions,
avec chaque terme défini surligné À SA PLACE dans le texte, coloré ACTEUR vs CONCEPT (les acteurs
ressortent). Survol = type + base légale + libellé FR. Façon « grounded » LangExtract, appliquée au
glossaire (« isoler les acteurs des concepts »). Construit du cache (HTML EUR-Lex + override relu),
aucun LLM. HTML autonome.

Usage : uv run python scripts/build_glossary_viz.py
Sortie : data/exports/presentation/glossaire_ancre.html
"""

from __future__ import annotations

import html
from pathlib import Path

from regulatory_index.glossary import DefinedTerm, harvest_glossary
from regulatory_index.ingestion.eurlex_html_parser import parse_articles

RAW = Path("data/raw")
OUT = Path("data/exports/presentation/glossaire_ancre.html")
ACTS = [("AIFMD_L1", "AIFMD — article 4 (définitions)")]
ACTOR_TYPES = {"actor", "investor", "supervisor"}
ACTOR_COLOUR = "#2E75B6"    # acteur (qui est régulé / agit)
CONCEPT_COLOUR = "#C55A11"  # concept / objet (de quoi on parle)


def _largest(source_id: str, lang: str) -> Path | None:
    files = sorted((RAW / source_id).glob(f"*_{lang}_*.html"), key=lambda p: (-p.stat().st_size, p.name))
    return files[0] if files else None


def _definitions_text(source_id: str, html_en: str, terms: list[DefinedTerm]) -> str | None:
    """Texte réel de l'article de définitions (numéro déduit de la base légale du 1er terme)."""
    article = terms[0].legal_basis.split("Art. ", 1)[1].split("(", 1)[0].strip()
    units = parse_articles(
        html_en, source_id=source_id, title=source_id, celex=terms[0].celex or "",
        language="EN", level=1, issuer="EU", url="",
    )
    unit = next((u for u in units if u.source_meta.get("article") == article), None)
    return unit.text if unit else None


def _find_unclaimed(text: str, needle: str, owner: list[int | None]) -> int | None:
    """1re position de `needle` dont tous les caractères sont encore libres (aucun propriétaire)."""
    start = 0
    while (i := text.find(needle, start)) != -1:
        if all(owner[k] is None for k in range(i, i + len(needle))):
            return i
        start = i + 1
    return None


def _render(text: str, terms: list[DefinedTerm]) -> tuple[str, int, int]:
    """Texte HTML : chaque terme surligné à sa place. Renvoie (html, n_acteurs, n_concepts)."""
    owner: list[int | None] = [None] * len(text)
    # Termes les plus longs d'abord (pour que « AIFM » réserve sa place avant « AIF »).
    ordered = sorted(terms, key=lambda t: -len(t.term_en))
    for idx, t in enumerate(ordered):
        i = _find_unclaimed(text, t.term_en, owner)
        if i is None:
            continue
        for k in range(i, i + len(t.term_en)):
            owner[k] = idx

    n_actor = sum(1 for t in terms if (t.type or "") in ACTOR_TYPES)
    out: list[str] = []
    i = 0
    while i < len(text):
        who = owner[i]
        j = i
        while j < len(text) and owner[j] == who:
            j += 1
        chunk = html.escape(text[i:j])
        if who is None:
            out.append(chunk)
        else:
            t = ordered[who]
            is_actor = (t.type or "") in ACTOR_TYPES
            colour = ACTOR_COLOUR if is_actor else CONCEPT_COLOUR
            cls = "actor" if is_actor else "concept"
            tip = f"{'ACTEUR' if is_actor else 'CONCEPT'} · {t.legal_basis}"
            if t.term_fr:
                tip += f" · FR : {t.term_fr}"
            out.append(
                f'<mark class="{cls}" style="--c:{colour}" title="{html.escape(tip)}">{chunk}</mark>'
            )
        i = j
    return "".join(out), n_actor, len(terms) - n_actor


def main() -> int:
    sections: list[str] = []
    tot_actor = tot_concept = 0
    for source_id, title in ACTS:
        en = _largest(source_id, "EN")
        if en is None:
            continue
        html_en = en.read_text(encoding="utf-8")
        fr = _largest(source_id, "FR")
        terms = [
            t for t in harvest_glossary(
                html_en, fr.read_text(encoding="utf-8") if fr else "",
                source_id=source_id, celex=en.name.split("_")[0], level=1,
                act_label=source_id.split("_")[0],
            ) if t.term_en.strip()
        ]
        if not terms:
            continue
        text = _definitions_text(source_id, html_en, terms)
        if text is None:
            continue
        body, na, nc = _render(text, terms)
        tot_actor += na
        tot_concept += nc
        sections.append(
            f'<section><h2>{html.escape(title)} '
            f'<span class="count">{na} acteurs · {nc} concepts surlignés</span></h2>'
            f'<div class="doc">{body}</div></section>'
        )
    if not sections:
        raise SystemExit(f"Aucun HTML/article de définitions exploitable sous {RAW}.")

    doc = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Glossaire ancré — acteurs vs concepts</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2a37;background:#f7f8fa}}
 header{{background:#0B5394;color:#fff;padding:22px 32px}}
 header h1{{margin:0 0 6px;font-size:22px}} header p{{margin:0;opacity:.92;font-size:14px}}
 .legend{{padding:14px 32px;background:#fff;border-bottom:1px solid #e5e7eb;font-size:14px}}
 .legend b{{margin-right:8px}}
 .legend .s{{padding:1px 8px;border-radius:4px;margin:0 14px 0 4px;font-weight:bold}}
 section{{background:#fff;margin:20px 32px;padding:22px 28px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 h2{{font-size:17px;color:#0B5394;margin:0 0 16px}}
 .count{{font-size:13px;font-weight:normal;color:#6b7280;margin-left:8px}}
 .doc{{font-size:15px;line-height:2.05;white-space:pre-wrap}}
 mark{{background:transparent;cursor:help}}
 mark.actor{{color:var(--c);font-weight:bold;background:color-mix(in srgb,var(--c) 14%,transparent);
            border-radius:3px;padding:0 2px;text-decoration:underline;text-decoration-thickness:2px}}
 mark.concept{{color:var(--c);text-decoration:underline dotted;text-decoration-thickness:1px;text-underline-offset:2px}}
 footer{{padding:18px 32px;color:#6b7280;font-size:13px}}
</style></head><body>
<header><h1>Glossaire ancré dans le texte — les acteurs surlignés à leur place</h1>
<p>Le <b>texte réel de l'article de définitions</b>, avec chaque terme défini surligné <b>là où il
apparaît</b> : <b>acteurs</b> en gras coloré, <b>concepts</b> soulignés en pointillé. Survolez un
terme pour son type, sa base légale et son libellé FR. {tot_actor} acteurs · {tot_concept} concepts.</p></header>
<div class="legend"><b>Légende :</b>
 <span class="s" style="color:{ACTOR_COLOUR};background:{ACTOR_COLOUR}22;text-decoration:underline">acteur</span>
 <span class="s" style="color:{CONCEPT_COLOUR};text-decoration:underline dotted">concept</span></div>
{''.join(sections)}
<footer>Données réelles du projet · texte officiel non reformulé · classification acteur/concept (relue pour AIFMD).</footer>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"→ {OUT}  ({tot_actor} acteurs, {tot_concept} concepts surlignés in situ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
