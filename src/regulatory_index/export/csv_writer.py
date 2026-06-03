"""Export obligations and relations to UTF-8 CSV files (Excel-FR friendly by default)."""

from __future__ import annotations

from pathlib import Path

from ..materialize import MaterializedIndex


def write_csv(materialized: MaterializedIndex, out_dir: Path, delimiter: str = ";") -> dict[str, int]:
    """Write obligations.csv and relations.csv. Returns row counts per file."""
    out_dir.mkdir(parents=True, exist_ok=True)

    obligations_path = out_dir / "obligations.csv"
    relations_path = out_dir / "relations.csv"

    materialized.obligations_df.write_csv(obligations_path, separator=delimiter)
    materialized.relations_df.write_csv(relations_path, separator=delimiter)

    return {
        "obligations": materialized.obligations_df.height,
        "relations": materialized.relations_df.height,
    }
