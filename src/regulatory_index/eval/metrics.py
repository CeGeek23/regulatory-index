"""Compute extraction-quality metrics from saved UnitExtraction JSONs.

This is intentionally lightweight: coverage, grounding ratio, theme distribution,
and per-source latency. It is run after a batch and produces a Markdown report
that can be committed alongside the export.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..schemas.obligation import Obligation
from ..schemas.obligation_builder import collect_vocab_gaps
from ..schemas.raw import UnitExtraction


@dataclass(frozen=True)
class QualityReport:
    units_total: int
    obligations_total: int
    grounded_total: int
    failed_units: int
    obligations_per_unit_mean: float
    latency_p50_seconds: float
    latency_p95_seconds: float
    by_theme: dict[str, int] = field(default_factory=dict)
    by_actor: dict[str, int] = field(default_factory=dict)
    by_language: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    vocab_gaps: dict[str, list[tuple[str, int]]] = field(default_factory=dict)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sv = sorted(values)
    k = max(0, min(len(sv) - 1, round(pct * (len(sv) - 1))))
    return sv[k]


def compute(
    unit_extractions: list[UnitExtraction],
    obligations: list[Obligation],
    failed_units: int,
) -> QualityReport:
    grounded = sum(
        1 for ue in unit_extractions for ob in ue.obligations if ob.char_interval[1] > ob.char_interval[0]
    )
    obligations_total = sum(len(ue.obligations) for ue in unit_extractions)
    latencies = [ue.extraction_meta.latency_seconds for ue in unit_extractions]
    by_theme: Counter[str] = Counter(o.theme for o in obligations)
    by_actor: Counter[str] = Counter(o.actor for o in obligations)
    by_language: Counter[str] = Counter(str(o.source.language) for o in obligations)
    by_source: Counter[str] = Counter(o.source.source_id.split("#")[0] for o in obligations)

    n_units = max(len(unit_extractions), 1)
    return QualityReport(
        units_total=len(unit_extractions),
        obligations_total=obligations_total,
        grounded_total=grounded,
        failed_units=failed_units,
        obligations_per_unit_mean=round(obligations_total / n_units, 2),
        latency_p50_seconds=round(_percentile(latencies, 0.5), 1),
        latency_p95_seconds=round(_percentile(latencies, 0.95), 1),
        by_theme=dict(by_theme),
        by_actor=dict(by_actor.most_common(20)),
        by_language=dict(by_language),
        by_source=dict(by_source),
        vocab_gaps=collect_vocab_gaps(unit_extractions),
    )


def render_markdown(report: QualityReport) -> str:
    lines = [
        "# Quality report",
        "",
        f"- Units processed: **{report.units_total}**",
        f"- Failed units: **{report.failed_units}**",
        f"- Obligations extracted: **{report.obligations_total}**",
        f"- Grounded obligations: **{report.grounded_total}/{report.obligations_total}**",
        f"- Mean obligations per unit: **{report.obligations_per_unit_mean}**",
        f"- Latency P50 / P95 (s): **{report.latency_p50_seconds} / {report.latency_p95_seconds}**",
        "",
        "## By theme",
        "",
        "| Theme | Count |",
        "| --- | ---: |",
    ]
    for k, v in sorted(report.by_theme.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## By language", "", "| Lang | Count |", "| --- | ---: |"]
    for k, v in sorted(report.by_language.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## By source", "", "| Source | Count |", "| --- | ---: |"]
    for k, v in sorted(report.by_source.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Top 20 actors", "", "| Actor | Count |", "| --- | ---: |"]
    for k, v in report.by_actor.items():
        lines.append(f"| {k} | {v} |")
    if report.vocab_gaps:
        lines += [
            "",
            "## Vocabulary gaps",
            "",
            "Off-vocabulary values emitted by the model — candidates to add to "
            "`config/vocabularies/`.",
        ]
        for field_name, values in report.vocab_gaps.items():
            lines += ["", f"### {field_name}", "", "| Value | Count |", "| --- | ---: |"]
            lines += [f"| {value} | {count} |" for value, count in values]
    return "\n".join(lines) + "\n"


def write_report(report: QualityReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(report), encoding="utf-8")
    return out_path
