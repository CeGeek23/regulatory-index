"""Visualisation « ancrée » du GLOSSAIRE (brief client), pour TOUS les textes de niveau 1.

Pour chaque texte : le TEXTE RÉEL de son article de définitions, avec chaque terme défini surligné
À SA PLACE et coloré selon ce que notre approche extrait — acteur / investisseur / autorité /
concept (les 4 catégories du projet). Légende + sommaire pour naviguer. Survol = type + base légale
+ libellé FR. Façon « grounded » LangExtract appliquée au glossaire. Aucun LLM (cache uniquement).

Usage : uv run python scripts/build_glossary_viz.py
Sortie : data/exports/presentation/glossaire_ancre.html
"""

from __future__ import annotations

import html
from pathlib import Path

from regulatory_index.glossary import DefinedTerm, harvest_glossary
from regulatory_index.ingestion.eurlex_html_parser import parse_articles

RAW = Path("data/raw")
OVERRIDES = Path("config/glossary/overrides")
OUT = Path("data/exports/presentation/glossaire_ancre.html")

# Les 4 catégories extraites par le projet, leur couleur et leur libellé.
TYPE_COLOUR = {"actor": "#2E75B6", "investor": "#2E8B57", "supervisor": "#7030A0", "concept": "#C55A11"}
TYPE_LABEL = {"actor": "acteur", "investor": "investisseur", "supervisor": "autorité", "concept": "concept"}
ACTOR_TYPES = {"actor", "investor", "supervisor"}

# Périmètre groupé par domaine (ordre d'affichage + sommaire), avec libellés lisibles.
DOMAINS: dict[str, list[str]] = {
    "Fonds / gestion d'actifs": ["AIFMD_L1", "AIFMD_L2", "UCITS", "ELTIF", "MMFR", "EUVECA", "EUSEF", "CBDF_REG"],
    "Marchés": ["MIFID2", "MIFIR", "MAR", "MAD2", "PROSPECTUS", "CSDR", "SHORT_SELLING", "BENCHMARKS",
                "SECURITISATION", "SFTR", "EMIR", "TRANSPARENCY", "CRA"],
    "Banque / résolution": ["CRR", "CRD4", "BRRD", "SRMR", "DGSD"],
    "Assurance": ["SOLVENCY2", "IDD"], "Paiements": ["PSD2", "EMONEY2"],
    "Durabilité": ["SFDR", "TAXONOMY"], "Numérique": ["MICA", "DORA"],
    "Transverse": ["ECSP", "PEPP", "IORP2", "AMLD", "ACCOUNTING", "ESMA_REG", "PRIIPS"],
}
TITLES = {
    "AIFMD_L1": "AIFMD (gestion de FIA)", "AIFMD_L2": "AIFMD niveau 2", "UCITS": "OPCVM/UCITS",
    "ELTIF": "ELTIF", "MMFR": "Fonds monétaires", "EUVECA": "EuVECA", "EUSEF": "EuSEF",
    "CBDF_REG": "Distribution transfrontalière", "MIFID2": "MiFID II", "MIFIR": "MiFIR",
    "MAR": "Abus de marché (MAR)", "MAD2": "Abus de marché pénal", "PROSPECTUS": "Prospectus",
    "CSDR": "Dépositaires centraux", "SHORT_SELLING": "Ventes à découvert", "BENCHMARKS": "Indices de référence",
    "SECURITISATION": "Titrisation", "SFTR": "Financement sur titres", "EMIR": "Dérivés OTC (EMIR)",
    "TRANSPARENCY": "Transparence", "CRA": "Agences de notation", "CRR": "Fonds propres (CRR)",
    "CRD4": "CRD IV", "BRRD": "Résolution bancaire", "SRMR": "Résolution unique", "DGSD": "Garantie des dépôts",
    "SOLVENCY2": "Solvabilité II", "IDD": "Distribution d'assurance", "PSD2": "Services de paiement (DSP2)",
    "EMONEY2": "Monnaie électronique", "SFDR": "Durabilité (SFDR)", "TAXONOMY": "Taxonomie",
    "MICA": "Crypto-actifs (MiCA)", "DORA": "Résilience numérique (DORA)", "ECSP": "Financement participatif",
    "PEPP": "Retraite paneuropéenne", "IORP2": "Retraite professionnelle", "AMLD": "Anti-blanchiment",
    "ACCOUNTING": "Directive comptable", "ESMA_REG": "Règlement AEMF", "PRIIPS": "PRIIPs",
}


def _largest(source_id: str, lang: str) -> Path | None:
    files = sorted((RAW / source_id).glob(f"*_{lang}_*.html"), key=lambda p: (-p.stat().st_size, p.name))
    return files[0] if files else None


def _definitions_text(source_id: str, html_en: str, terms: list[DefinedTerm]) -> str | None:
    article = terms[0].legal_basis.split("Art. ", 1)[1].split("(", 1)[0].strip()
    units = parse_articles(
        html_en, source_id=source_id, title=source_id, celex=terms[0].celex or "",
        language="EN", level=1, issuer="EU", url="",
    )
    unit = next((u for u in units if u.source_meta.get("article") == article), None)
    return unit.text if unit else None


def _find_unclaimed(text: str, needle: str, owner: list[int | None]) -> int | None:
    start = 0
    while (i := text.find(needle, start)) != -1:
        if all(owner[k] is None for k in range(i, i + len(needle))):
            return i
        start = i + 1
    return None


def _render(text: str, terms: list[DefinedTerm]) -> tuple[str, dict[str, int]]:
    """Texte HTML : chaque terme surligné à sa place, coloré par type. Renvoie (html, comptes/type)."""
    owner: list[int | None] = [None] * len(text)
    ordered = sorted(terms, key=lambda t: -len(t.term_en))  # plus longs d'abord (AIFM avant AIF)
    for idx, t in enumerate(ordered):
        i = _find_unclaimed(text, t.term_en, owner)
        if i is not None:
            for k in range(i, i + len(t.term_en)):
                owner[k] = idx

    counts: dict[str, int] = {}
    for t in terms:
        typ = (t.type or "concept") if (t.type in TYPE_COLOUR) else "concept"
        counts[typ] = counts.get(typ, 0) + 1

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
            typ = (t.type or "concept") if (t.type in TYPE_COLOUR) else "concept"
            cls = "act" if typ in ACTOR_TYPES else "con"
            tip = f"{TYPE_LABEL[typ].upper()} · {t.legal_basis}" + (f" · FR : {t.term_fr}" if t.term_fr else "")
            out.append(
                f'<mark class="{cls}" style="--c:{TYPE_COLOUR[typ]}" title="{html.escape(tip)}">{chunk}</mark>'
            )
        i = j
    return "".join(out), counts


def main() -> int:
    sections: list[str] = []
    toc: list[str] = []
    totals: dict[str, int] = {}
    for domain, source_ids in DOMAINS.items():
        toc_items: list[str] = []
        for sid in source_ids:
            en = _largest(sid, "EN")
            if en is None:
                continue
            html_en = en.read_text(encoding="utf-8")
            fr = _largest(sid, "FR")
            try:
                terms = [
                    t for t in harvest_glossary(
                        html_en, fr.read_text(encoding="utf-8") if fr else "",
                        source_id=sid, celex=en.name.split("_")[0], level=1, act_label=sid.split("_")[0],
                    ) if t.term_en.strip()
                ]
            except ValueError:
                continue  # acte sans article de définitions (ex. directive modificative)
            if not terms:
                continue
            text = _definitions_text(sid, html_en, terms)
            if text is None:
                continue
            body, counts = _render(text, terms)
            for k, v in counts.items():
                totals[k] = totals.get(k, 0) + v
            name = TITLES.get(sid, sid)
            n_actor = sum(counts.get(k, 0) for k in ACTOR_TYPES)
            summary = " · ".join(f"{counts[k]} {TYPE_LABEL[k]}{'s' if counts[k] > 1 else ''}"
                                 for k in ("actor", "investor", "supervisor", "concept") if counts.get(k))
            sections.append(
                f'<section id="{sid}"><h2>{html.escape(name)} '
                f'<span class="count">{summary}</span></h2>'
                f'<div class="doc">{body}</div></section>'
            )
            toc_items.append(f'<a href="#{sid}">{html.escape(name)} <em>({n_actor} act.)</em></a>')
        if toc_items:
            toc.append(f'<div class="dom"><b>{html.escape(domain)}</b>{"".join(toc_items)}</div>')

    if not sections:
        raise SystemExit(f"Aucun article de définitions exploitable sous {RAW}.")

    legend = "".join(
        f'<span class="s" style="--c:{TYPE_COLOUR[k]}">{TYPE_LABEL[k]}</span>'
        for k in ("actor", "investor", "supervisor", "concept")
    )
    tot_line = " · ".join(f"<b>{totals.get(k, 0)}</b> {TYPE_LABEL[k]}s"
                          for k in ("actor", "investor", "supervisor", "concept"))

    doc = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Glossaire ancré — niveau 1</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2a37;background:#f7f8fa}}
 header{{background:#0B5394;color:#fff;padding:20px 32px;position:sticky;top:0;z-index:10}}
 header h1{{margin:0 0 4px;font-size:20px}} header p{{margin:0;opacity:.92;font-size:13.5px}}
 .legend{{padding:12px 32px;background:#fff;border-bottom:1px solid #e5e7eb;font-size:14px}}
 .legend b{{margin-right:6px}}
 .legend .s{{color:var(--c);font-weight:bold;text-decoration:underline;text-decoration-thickness:2px;
            background:color-mix(in srgb,var(--c) 13%,transparent);border-radius:4px;padding:1px 9px;margin:0 6px}}
 nav{{padding:14px 32px;background:#fbfbfd;border-bottom:1px solid #e5e7eb}}
 nav .dom{{margin:6px 0;font-size:13px}}
 nav .dom b{{display:inline-block;min-width:170px;color:#0B5394}}
 nav a{{color:#2E75B6;text-decoration:none;margin:0 10px 0 0;white-space:nowrap}}
 nav a em{{color:#9aa3af;font-style:normal}}
 section{{background:#fff;margin:18px 32px;padding:20px 26px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 h2{{font-size:16px;color:#0B5394;margin:0 0 14px;border-bottom:2px solid #eef2f9;padding-bottom:6px}}
 .count{{font-size:12.5px;font-weight:normal;color:#6b7280;margin-left:8px}}
 .doc{{font-size:14.5px;line-height:2.0;white-space:pre-wrap}}
 mark{{background:transparent;cursor:help}}
 mark.act{{color:var(--c);font-weight:bold;background:color-mix(in srgb,var(--c) 13%,transparent);
          border-radius:3px;padding:0 2px;text-decoration:underline;text-decoration-thickness:2px}}
 mark.con{{color:var(--c);text-decoration:underline dotted;text-decoration-thickness:1px;text-underline-offset:2px}}
 footer{{padding:18px 32px;color:#6b7280;font-size:13px}}
</style></head><body>
<header><h1>Glossaire ancré — tout ce que l'approche extrait, surligné dans le texte</h1>
<p>Pour chaque texte de niveau 1 : son <b>article de définitions réel</b>, avec chaque terme défini
surligné <b>à sa place</b> et coloré par catégorie. Acteurs/investisseurs/autorités en gras coloré,
concepts en pointillé. Survolez un terme pour son type, sa base légale et son libellé FR.</p></header>
<div class="legend"><b>Légende :</b>{legend} &nbsp;—&nbsp; total : {tot_line}</div>
<nav>{''.join(toc)}</nav>
{''.join(sections)}
<footer>Données réelles du projet · texte officiel non reformulé · classification acteur/concept « à relire » (sauf AIFMD, relu).</footer>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"→ {OUT}  ({len(sections)} textes ; total " +
          ", ".join(f"{totals.get(k, 0)} {TYPE_LABEL[k]}s" for k in TYPE_COLOUR) + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
