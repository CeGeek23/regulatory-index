"""Benchmark de modèles LLM (LM Studio) pour l'extraction d'obligations AIFMD.

Pour chaque modèle passé en argument, sur un sous-ensemble représentatif d'unités du
corpus (EN L1/L2, FR, court/dense), mesure :
- obligations extraites, taux de grounding (verbatim retrouvé dans la source),
- latence par unité, échecs (HTTP/template/timeout),
- taux de canonicalisation : % des champs actor/action/theme qui résolvent dans le
  vocabulaire contrôlé (proxy de cohérence avec l'index ; le reste = découverte/bruit).

Chaque modèle est chargé à contexte 8192 via `lms` avant son tour (comparaison équitable).

Usage:
    uv run python scripts/benchmark_models.py "google/gemma-4-e4b" "<qwen>" "<mistral>"

Sortie: récap console + rapport markdown dans data/exports/model_benchmark.md
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from regulatory_index.extraction.langextract_runner import RunnerConfig, extract_unit
from regulatory_index.ingestion.unit_loader import NormativeUnit, load_units_jsonl
from regulatory_index.schemas.vocab import load_vocabulary

CORPUS = Path("data/units/corpus.jsonl")
REPORT = Path("data/exports/model_benchmark.md")
BENCH_RAW = Path("data/exports/_bench_raw.json")  # cache reprenable (1 entrée par modèle)
CTX = 16384  # contexte chargé pour chaque modèle (le prompt vocab + few-shots + schéma est gros)
SUBSET = [
    "AIFMD_L1#en#art_15",   # EN L1 — gestion des risques (dense)
    "AIFMD_L1#en#art_23",   # EN L1 — transparence (dense, très cité)
    "AIFMD_L2#en#art_40",   # EN L2 — politique de gestion des risques
    "AIFMD_L1#fr#art_15",   # FR    — test bilingue
]
_VOCAB_FIELDS = {"actor": "actors", "action": "actions", "theme": "themes"}


def _canonical_rate(obligations: list[Any]) -> float:
    total = resolved = 0
    for o in obligations:
        for field, vocab in _VOCAB_FIELDS.items():
            value = getattr(o, field)
            if value:
                total += 1
                if load_vocabulary(vocab).resolve(value) is not None:
                    resolved += 1
    return (resolved / total * 100) if total else 0.0


def _lms(*args: str) -> None:
    subprocess.run(["lms", *args], capture_output=True, text=True, check=False)


def _bench_model(model: str, units: list[NormativeUnit]) -> list[dict[str, Any]]:
    _lms("load", model, "--context-length", str(CTX), "--yes")
    rows: list[dict[str, Any]] = []
    for u in units:
        t0 = time.monotonic()
        try:
            ext = extract_unit(u, RunnerConfig(model_id=model))
            grounded = sum(1 for o in ext.obligations if o.char_interval[1] > o.char_interval[0])
            rows.append({
                "unit": u.unit_id, "obl": len(ext.obligations), "grounded": grounded,
                "lat": time.monotonic() - t0, "canon": _canonical_rate(ext.obligations),
                "drops": len(ext.errors), "err": None,
            })
        except Exception as e:
            rows.append({
                "unit": u.unit_id, "obl": 0, "grounded": 0, "lat": time.monotonic() - t0,
                "canon": 0.0, "drops": 0, "err": f"{type(e).__name__}: {str(e)[:120]}",
            })
        r = rows[-1]
        flag = f"ERR {r['err']}" if r["err"] else ""
        print(f"    {r['unit']:22} obl={r['obl']:>2} grounded={r['grounded']:>2} "
              f"canon={r['canon']:5.1f}% {r['lat']:6.1f}s {flag}")
    _lms("unload", model)
    return rows


def _aggregate(model: str, rows: list[dict[str, Any]], n_units: int) -> dict[str, Any]:
    ok = [r for r in rows if r["err"] is None]
    obl = sum(r["obl"] for r in ok)
    grounded = sum(r["grounded"] for r in ok)
    canon_den = sum(r["obl"] for r in ok)
    canon = sum(r["canon"] * r["obl"] for r in ok) / canon_den if canon_den else 0.0
    return {
        "model": model, "units_ok": len(ok), "failed": len(rows) - len(ok),
        "obl": obl, "grounded_pct": (grounded / obl * 100) if obl else 0.0,
        "canon_pct": canon, "mean_lat": sum(r["lat"] for r in rows) / len(rows) if rows else 0.0,
    }


def main() -> int:
    models = sys.argv[1:]
    if not models:
        print("Usage: benchmark_models.py <model_id> [<model_id> ...]", file=sys.stderr)
        return 1
    by_id = {u.unit_id: u for u in load_units_jsonl(CORPUS)}
    units = [by_id[uid] for uid in SUBSET if uid in by_id]
    print(f"Benchmark sur {len(units)} unités : {[u.unit_id for u in units]}\n")

    cache: dict[str, list[dict[str, Any]]] = {}
    if BENCH_RAW.exists():
        cache = json.loads(BENCH_RAW.read_text(encoding="utf-8"))

    for m in models:
        if m in cache:
            print(f"### {m}  (déjà mesuré, repris du cache)")
            continue
        print(f"### {m}")
        cache[m] = _bench_model(m, units)
        BENCH_RAW.parent.mkdir(parents=True, exist_ok=True)
        BENCH_RAW.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print()

    detail = {m: cache[m] for m in models if m in cache}
    summaries = [_aggregate(m, detail[m], len(units)) for m in models if m in detail]

    lines = [
        "# Benchmark modèles — extraction d'obligations (LM Studio)", "",
        f"Sous-ensemble : **{len(units)} unités** ({', '.join(u.unit_id for u in units)}).",
        f"Contexte {CTX} pour tous. `canonical %` = part des champs actor/action/theme résolus "
        "dans le vocab contrôlé (cohérence ; le complément = découverte/bruit).", "",
        "| Modèle | Unités OK | Échecs | Obligations | Grounded % | Canonical % | Latence moy. (s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in summaries:
        lines.append(
            f"| `{s['model']}` | {s['units_ok']}/{len(units)} | {s['failed']} | {s['obl']} | "
            f"{s['grounded_pct']:.0f}% | {s['canon_pct']:.0f}% | {s['mean_lat']:.1f} |"
        )
    lines += ["", "## Détail par unité", ""]
    for m, rows in detail.items():
        lines += [f"### `{m}`", "", "| Unité | Obl. | Grounded | Canon % | Lat. (s) | Erreur |",
                  "| --- | ---: | ---: | ---: | ---: | --- |"]
        for r in rows:
            lines.append(
                f"| {r['unit']} | {r['obl']} | {r['grounded']} | {r['canon']:.0f}% | "
                f"{r['lat']:.1f} | {r['err'] or ''} |"
            )
        lines.append("")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== RÉCAP ===")
    for s in summaries:
        print(f"  {s['model']:42} obl={s['obl']:>3} grounded={s['grounded_pct']:5.1f}% "
              f"canon={s['canon_pct']:5.1f}% lat={s['mean_lat']:5.1f}s failed={s['failed']}")
    print(f"\nRapport: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
