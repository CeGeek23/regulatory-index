"""Materialise persisted extractions into in-memory Polars DataFrames.

This module replaces the previous DuckDB layer. The source of truth is the
JSON files in `data/obligations/` (one per NormativeUnit). At export time we
load them, build Obligations, run the citation linker, and turn everything
into three Polars DataFrames that the writers (Excel / CSV) consume directly.

No persistent database, no SQL — Polars is sufficient for our scale
(thousands of obligations) and keeps the dependency surface minimal.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from .ingestion.unit_loader import NormativeUnit
from .linking.citation_extractor import (
    ResolvedCitation,
    UnresolvedCitation,
    resolve_all,
)
from .linking.graph_builder import build_relations
from .schemas.obligation import Obligation
from .schemas.obligation_builder import build_obligations
from .schemas.raw import UnitExtraction
from .schemas.relation import CrossLevelRelation

# ──────────────────────────────────────────────────────────────────────────────
# Schemas — keep DataFrames typed even when empty (avoid pivot/select errors)
# ──────────────────────────────────────────────────────────────────────────────

OBLIGATION_SCHEMA: dict[str, pl.DataType] = {
    "obligation_id": pl.Utf8(),
    "source_id": pl.Utf8(),
    "level": pl.Utf8(),
    "issuer": pl.Utf8(),
    "language": pl.Utf8(),
    "celex": pl.Utf8(),
    "article": pl.Utf8(),
    "paragraph": pl.Utf8(),
    "point": pl.Utf8(),
    "actor": pl.Utf8(),
    "action": pl.Utf8(),
    "object": pl.Utf8(),
    "theme": pl.Utf8(),
    "sub_theme": pl.Utf8(),
    "condition": pl.Utf8(),
    "scope": pl.Utf8(),
    "exception": pl.Utf8(),
    "expected_evidence": pl.Utf8(),
    "associated_control": pl.Utf8(),
    "verbatim_text": pl.Utf8(),
    "char_start": pl.Int64(),
    "char_end": pl.Int64(),
    "cited_references": pl.Utf8(),
    "extraction_model": pl.Utf8(),
    "extracted_at": pl.Utf8(),
    "human_validated": pl.Boolean(),
    "source_url": pl.Utf8(),
    "source_title": pl.Utf8(),
}

RELATION_SCHEMA: dict[str, pl.DataType] = {
    "source_obligation_id": pl.Utf8(),
    "target_obligation_id": pl.Utf8(),
    "relation_type": pl.Utf8(),
    "citation_in_text": pl.Utf8(),
    "evidence_text": pl.Utf8(),
    "char_start": pl.Int64(),
    "char_end": pl.Int64(),
    "validated": pl.Boolean(),
}

UNIT_SCHEMA: dict[str, pl.DataType] = {
    "unit_id": pl.Utf8(),
    "source_id": pl.Utf8(),
    "language": pl.Utf8(),
    "hierarchy_path": pl.Utf8(),
    "text_length": pl.Int64(),
    "celex": pl.Utf8(),
    "level": pl.Utf8(),
    "issuer": pl.Utf8(),
    "article": pl.Utf8(),
}


# ──────────────────────────────────────────────────────────────────────────────
# Loaders / converters
# ──────────────────────────────────────────────────────────────────────────────


def load_unit_extractions_from_dir(obligations_dir: Path) -> list[UnitExtraction]:
    """Read every `{source_id}/{unit_id}.json` produced by the runner."""
    out: list[UnitExtraction] = []
    for path in sorted(obligations_dir.glob("*/*.json")):
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        out.append(UnitExtraction.model_validate(payload))
    return out


def obligations_to_df(obligations: list[Obligation]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "obligation_id": o.obligation_id,
            "source_id": o.source.source_id.split("#")[0],
            "level": str(o.source.level),
            "issuer": o.source.issuer,
            "language": o.source.language,
            "celex": o.source.celex,
            "article": o.source.article,
            "paragraph": o.source.paragraph,
            "point": o.source.point,
            "actor": o.actor,
            "action": o.action,
            "object": o.object,
            "theme": o.theme,
            "sub_theme": o.sub_theme,
            "condition": o.condition,
            "scope": o.scope,
            "exception": o.exception,
            "expected_evidence": "; ".join(o.expected_evidence),
            "associated_control": o.associated_control,
            "verbatim_text": o.verbatim_text,
            "char_start": o.char_interval[0],
            "char_end": o.char_interval[1],
            "cited_references": "; ".join(o.cited_references),
            "extraction_model": o.extraction_model,
            "extracted_at": o.extracted_at.isoformat(),
            "human_validated": o.human_validated,
            "source_url": o.source.url,
            "source_title": o.source.title,
        }
        for o in obligations
    ]
    return pl.DataFrame(rows, schema=OBLIGATION_SCHEMA)


def relations_to_df(relations: list[CrossLevelRelation]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "source_obligation_id": r.source_obligation_id,
            "target_obligation_id": r.target_obligation_id,
            "relation_type": r.relation_type.value,
            "citation_in_text": r.citation_in_text,
            "evidence_text": r.evidence_text,
            "char_start": r.char_interval[0],
            "char_end": r.char_interval[1],
            "validated": r.validated,
        }
        for r in relations
    ]
    return pl.DataFrame(rows, schema=RELATION_SCHEMA)


def units_to_df(units: Iterable[NormativeUnit]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for u in units:
        meta = u.source_meta or {}
        rows.append(
            {
                "unit_id": u.unit_id,
                "source_id": u.source_id,
                "language": u.language,
                "hierarchy_path": u.hierarchy_path,
                "text_length": len(u.text),
                "celex": meta.get("celex"),
                "level": str(meta.get("level", "")),
                "issuer": meta.get("issuer"),
                "article": (
                    str(meta.get("article", "")) if meta.get("article") is not None else None
                ),
            }
        )
    return pl.DataFrame(rows, schema=UNIT_SCHEMA)


# ──────────────────────────────────────────────────────────────────────────────
# One-call materialisation
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MaterializedIndex:
    """Fully materialised view of the corpus, in-memory."""

    obligations: list[Obligation]
    relations: list[CrossLevelRelation]
    resolved_citations: list[ResolvedCitation]
    unresolved_citations: list[UnresolvedCitation]
    obligations_df: pl.DataFrame
    relations_df: pl.DataFrame
    units_df: pl.DataFrame


def materialize(unit_extractions: list[UnitExtraction]) -> MaterializedIndex:
    """JSON extractions -> Obligations + Relations + DataFrames, single call."""
    obligations = build_obligations(unit_extractions)
    resolved, unresolved = resolve_all(obligations)
    relations = build_relations(obligations, resolved)
    return MaterializedIndex(
        obligations=obligations,
        relations=relations,
        resolved_citations=resolved,
        unresolved_citations=unresolved,
        obligations_df=obligations_to_df(obligations),
        relations_df=relations_to_df(relations),
        units_df=units_to_df([ue.unit for ue in unit_extractions]),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Aggregations — replace the former SQL views, used by the Excel summary sheets
# ──────────────────────────────────────────────────────────────────────────────


def by_theme(obligations_df: pl.DataFrame) -> pl.DataFrame:
    # Themes are canonicalised at build time, so we group by theme alone:
    # FR/EN variants of one theme collapse to a single row.
    if obligations_df.is_empty():
        return pl.DataFrame(schema={"theme": pl.Utf8(), "n": pl.UInt32()})
    return (
        obligations_df.group_by("theme")
        .len(name="n")
        .sort(["n", "theme"], descending=[True, False])
    )


def by_actor(obligations_df: pl.DataFrame) -> pl.DataFrame:
    if obligations_df.is_empty():
        return pl.DataFrame(schema={"actor": pl.Utf8(), "n": pl.UInt32()})
    return (
        obligations_df.group_by("actor")
        .len(name="n")
        .sort(["n", "actor"], descending=[True, False])
    )


def actor_theme_matrix(obligations_df: pl.DataFrame) -> pl.DataFrame:
    if obligations_df.is_empty():
        return pl.DataFrame(schema={"actor": pl.Utf8(), "theme": pl.Utf8(), "n": pl.UInt32()})
    return obligations_df.group_by(["actor", "theme"]).len(name="n").sort(["actor", "theme"])


def relations_summary(relations_df: pl.DataFrame) -> pl.DataFrame:
    if relations_df.is_empty():
        return pl.DataFrame(schema={"relation_type": pl.Utf8(), "n": pl.UInt32()})
    return relations_df.group_by("relation_type").len(name="n").sort("n", descending=True)


def sources_view(obligations_df: pl.DataFrame) -> pl.DataFrame:
    """Distinct (source_id, level, issuer, language, title, url) used by Excel."""
    if obligations_df.is_empty():
        return pl.DataFrame(
            schema={
                "source_id": pl.Utf8(),
                "level": pl.Utf8(),
                "issuer": pl.Utf8(),
                "language": pl.Utf8(),
                "source_title": pl.Utf8(),
                "source_url": pl.Utf8(),
            }
        )
    return (
        obligations_df.select(
            ["source_id", "level", "issuer", "language", "source_title", "source_url"]
        )
        .unique()
        .sort(["level", "source_id"])
    )
