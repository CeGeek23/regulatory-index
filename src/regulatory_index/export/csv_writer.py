"""Exporte obligations et relations vers des fichiers CSV UTF-8 (compatibles Excel-FR par défaut)."""

from __future__ import annotations

from pathlib import Path

from ..materialize import MaterializedIndex


def write_csv(materialized: MaterializedIndex, out_dir: Path, delimiter: str = ";") -> dict[str, int]:
    """Écrit obligations.csv et relations.csv. Renvoie le nombre de lignes par fichier."""
    out_dir.mkdir(parents=True, exist_ok=True)

    obligations_path = out_dir / "obligations.csv"
    relations_path = out_dir / "relations.csv"

    materialized.obligations_df.to_csv(obligations_path, sep=delimiter, index=False)
    materialized.relations_df.to_csv(relations_path, sep=delimiter, index=False)

    return {
        "obligations": len(materialized.obligations_df),
        "relations": len(materialized.relations_df),
    }
