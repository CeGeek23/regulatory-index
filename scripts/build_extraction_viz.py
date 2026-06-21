"""Visualisation « LangExtract » : le texte de l'article avec les obligations surlignées
à leur emplacement EXACT, couleur = thème, infobulle = données extraites (acteur/action/objet…).

Montre que l'extraction est ANCRÉE dans la source : chaque surlignage est le passage réel d'où
provient l'obligation (char_interval). Construit depuis le cache (data/obligations/ + texte de
l'unité) — aucun LLM requis. HTML autonome (stdlib seule), ouvrable/projetable dans un navigateur.

Usage : uv run python scripts/build_extraction_viz.py
Sortie : data/exports/presentation/extraction_grounded.html
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

OBL_DIR = Path("data/obligations")
OUT = Path("data/exports/presentation/extraction_grounded.html")
# Articles vitrine (les plus riches), dans l'ordre d'affichage.
ARTICLES = ["AIFMD_L1#en#art_7", "AIFMD_L1#en#art_23", "AIFMD_L1#en#art_22", "AIFMD_L1#en#art_15"]
PALETTE = ["#4E79A7", "#59A14F", "#E15759", "#F28E2B", "#B07AA1", "#76B7B2",
           "#EDC948", "#FF9DA7", "#9C755F", "#BAB0AC", "#86BCB6", "#D37295"]


def _load(unit_id: str) -> dict[str, Any] | None:
    source_id = unit_id.split("#", 1)[0]
    path = OBL_DIR / source_id / f"{unit_id}.json"
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _theme_colours(records: list[dict[str, Any]]) -> dict[str, str]:
    themes: list[str] = []
    for rec in records:
        for o in rec["obligations"]:
            t = o.get("theme") or "—"
            if t not in themes:
                themes.append(t)
    return {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(sorted(themes))}


def _render_text(text: str, obligations: list[dict[str, Any]], colours: dict[str, str]) -> str:
    """Texte HTML avec chaque obligation surlignée (premier propriétaire gagne en cas de chevauchement)."""
    owner: list[int | None] = [None] * len(text)
    for idx, o in enumerate(obligations):
        ci = o.get("char_interval") or [0, 0]
        start, end = max(0, ci[0]), min(len(text), ci[1])
        for i in range(start, end):
            if owner[i] is None:
                owner[i] = idx

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
            o = obligations[who]
            theme = o.get("theme") or "—"
            tip = " | ".join(
                f"{k}: {o[k]}" for k in ("actor", "action", "object", "theme", "condition", "exception")
                if o.get(k)
            )
            out.append(
                f'<mark class="ob" style="background:{colours.get(theme, "#DDD")}33;'
                f'border-bottom:2px solid {colours.get(theme, "#DDD")}" title="{html.escape(tip)}">{chunk}</mark>'
            )
        i = j
    return "".join(out)


def main() -> int:
    records = [r for uid in ARTICLES if (r := _load(uid)) is not None]
    if not records:
        raise SystemExit(f"Aucune obligation en cache sous {OBL_DIR} — lance d'abord l'extraction.")
    colours = _theme_colours(records)

    legend = "".join(
        f'<span class="chip"><i style="background:{c}"></i>{html.escape(t)}</span>'
        for t, c in colours.items()
    )
    total = sum(len(r["obligations"]) for r in records)
    sections: list[str] = []
    for rec in records:
        unit = rec["unit"]
        text = unit.get("text", "")
        path = unit.get("hierarchy_path", unit.get("unit_id", ""))
        n = len(rec["obligations"])
        sections.append(
            f'<section><h2>{html.escape(path)} '
            f'<span class="count">{n} obligation(s) extraite(s)</span></h2>'
            f'<div class="doc">{_render_text(text, rec["obligations"], colours)}</div></section>'
        )

    doc = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Extraction ancrée — AIFMD</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2a37;background:#f7f8fa}}
 header{{background:#0B5394;color:#fff;padding:22px 32px}}
 header h1{{margin:0 0 6px;font-size:22px}} header p{{margin:0;opacity:.9;font-size:14px}}
 .legend{{padding:14px 32px;background:#fff;border-bottom:1px solid #e5e7eb}}
 .chip{{display:inline-block;margin:3px 12px 3px 0;font-size:13px}}
 .chip i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:middle}}
 section{{background:#fff;margin:20px 32px;padding:20px 26px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 h2{{font-size:17px;color:#0B5394;margin:0 0 14px}}
 .count{{font-size:13px;font-weight:normal;color:#6b7280;margin-left:8px}}
 .doc{{font-size:15px;line-height:2.0;white-space:pre-wrap}}
 mark.ob{{border-radius:3px;padding:1px 0;cursor:help}}
 footer{{padding:18px 32px;color:#6b7280;font-size:13px}}
</style></head><body>
<header><h1>Extraction ancrée dans le texte — AIFMD (pilote agrément &amp; transparence)</h1>
<p>Chaque <b>surlignage</b> est le passage EXACT d'où provient une obligation (couleur = thème).
Survolez un surlignage pour voir les données extraites (acteur · action · objet · thème). {total} obligations.</p></header>
<div class="legend">{legend}</div>
{''.join(sections)}
<footer>Données réelles du projet · ancrage par <code>char_interval</code> · aucun texte reformulé.</footer>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"→ {OUT}  ({total} obligations sur {len(records)} articles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
