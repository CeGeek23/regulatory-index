"""Écrit un classeur Excel multi-feuilles et formaté à partir d'un MaterializedIndex."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import xlsxwriter

from ..materialize import (
    MaterializedIndex,
    actor_theme_matrix,
    by_actor,
    by_theme,
    relations_summary,
    sources_view,
)

_LEVEL_COLOURS: dict[str, str] = {
    "1": "#D9EAD3",
    "2": "#FCE5CD",
    "3": "#CFE2F3",
    "national": "#F4CCCC",
}


_OBLIGATION_COLUMNS = [
    ("obligation_id", "Obligation ID", 18),
    ("source_id", "Source", 20),
    ("level", "Level", 8),
    ("issuer", "Issuer", 22),
    ("language", "Lang", 6),
    ("article", "Article", 9),
    ("paragraph", "Paragraph", 9),
    ("actor", "Actor", 22),
    ("action", "Action", 15),
    ("object", "Object", 35),
    ("theme", "Theme", 18),
    ("sub_theme", "Sub-theme", 25),
    ("condition", "Condition", 22),
    ("scope", "Scope", 22),
    ("exception", "Exception", 22),
    ("expected_evidence", "Expected evidence", 30),
    ("associated_control", "Associated control", 30),
    ("verbatim_text", "Verbatim", 60),
    ("cited_references", "Cited refs", 35),
    ("source_url", "Source URL", 35),
]

_RELATION_COLUMNS = [
    ("source_obligation_id", "From obligation", 20),
    ("target_obligation_id", "To target", 26),
    ("relation_type", "Relation", 16),
    ("citation_in_text", "Citation", 40),
    ("evidence_text", "Evidence", 60),
]


def _df_rows(df: pl.DataFrame, columns: list[str]) -> list[tuple[Any, ...]]:
    if df.is_empty():
        return []
    return [tuple(row) for row in df.select(columns).iter_rows()]


def write_workbook(materialized: MaterializedIndex, output_path: Path) -> dict[str, int]:
    """Construit le classeur à partir des DataFrames en mémoire. Renvoie le nombre de lignes par feuille."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    obligations_df = materialized.obligations_df.sort(["level", "theme", "obligation_id"])
    relations_df = materialized.relations_df.sort("source_obligation_id")
    sources_df = sources_view(materialized.obligations_df)

    obligations = _df_rows(obligations_df, [c for c, *_ in _OBLIGATION_COLUMNS])
    relations = _df_rows(relations_df, [c for c, *_ in _RELATION_COLUMNS])

    workbook = xlsxwriter.Workbook(str(output_path))
    header_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#0B5394", "font_color": "white", "border": 1}
    )
    wrap_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
    level_fmts: dict[str, Any] = {
        lvl: workbook.add_format({"bg_color": colour, "valign": "top", "text_wrap": True})
        for lvl, colour in _LEVEL_COLOURS.items()
    }

    counts: dict[str, int] = {}

    # 1. Feuille Obligations
    ws = workbook.add_worksheet("Obligations")
    ws.freeze_panes(1, 1)
    ws.autofilter(0, 0, max(1, len(obligations)), len(_OBLIGATION_COLUMNS) - 1)
    for col, (_, label, width) in enumerate(_OBLIGATION_COLUMNS):
        ws.write(0, col, label, header_fmt)
        ws.set_column(col, col, width)
    for row, record in enumerate(obligations, start=1):
        level = str(record[2]) if record[2] is not None else ""
        fmt = level_fmts.get(level, wrap_fmt)
        for col, value in enumerate(record):
            ws.write(row, col, value if value is not None else "", fmt)
    counts["Obligations"] = len(obligations)

    # 2. Feuille Relations
    ws = workbook.add_worksheet("Relations")
    ws.freeze_panes(1, 0)
    if relations:
        ws.autofilter(0, 0, len(relations), len(_RELATION_COLUMNS) - 1)
    for col, (_, label, width) in enumerate(_RELATION_COLUMNS):
        ws.write(0, col, label, header_fmt)
        ws.set_column(col, col, width)
    for row, record in enumerate(relations, start=1):
        for col, value in enumerate(record):
            ws.write(row, col, value if value is not None else "", wrap_fmt)
    counts["Relations"] = len(relations)

    # 3. Feuille Sources
    ws = workbook.add_worksheet("Sources")
    headers = ["Source ID", "Level", "Issuer", "Language", "Title", "URL"]
    widths = [22, 8, 22, 8, 50, 40]
    for col, (label, width) in enumerate(zip(headers, widths, strict=False)):
        ws.write(0, col, label, header_fmt)
        ws.set_column(col, col, width)
    sources = _df_rows(
        sources_df, ["source_id", "level", "issuer", "language", "source_title", "source_url"]
    )
    for row, record in enumerate(sources, start=1):
        for col, value in enumerate(record):
            ws.write(row, col, value if value is not None else "", wrap_fmt)
    counts["Sources"] = len(sources)

    # 4. Synthèse par thème
    _write_summary_sheet(
        workbook,
        "Themes summary",
        by_theme(materialized.obligations_df),
        ["Theme", "Count"],
        [30, 12],
        header_fmt,
    )

    # 5. Matrice Acteur x Thème
    _write_summary_sheet(
        workbook,
        "Actor x Theme",
        actor_theme_matrix(materialized.obligations_df),
        ["Actor", "Theme", "Count"],
        [28, 28, 10],
        header_fmt,
    )

    # 6. Synthèse par acteur
    _write_summary_sheet(
        workbook,
        "Actors summary",
        by_actor(materialized.obligations_df),
        ["Actor", "Count"],
        [30, 12],
        header_fmt,
    )

    # 7. Synthèse des relations
    _write_summary_sheet(
        workbook,
        "Relations summary",
        relations_summary(materialized.relations_df),
        ["Relation type", "Count"],
        [22, 22],
        header_fmt,
    )

    workbook.close()
    return counts


def _write_summary_sheet(
    workbook: xlsxwriter.Workbook,
    name: str,
    df: pl.DataFrame,
    headers: list[str],
    widths: list[int],
    header_fmt: Any,
) -> None:
    ws = workbook.add_worksheet(name)
    for col, (label, width) in enumerate(zip(headers, widths, strict=False)):
        ws.write(0, col, label, header_fmt)
        ws.set_column(col, col, width)
    if df.is_empty():
        return
    for row, record in enumerate(df.iter_rows(), start=1):
        for col, value in enumerate(record):
            ws.write(row, col, value)
