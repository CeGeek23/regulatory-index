"""Matérialisation : transforme les extractions en index (obligations + relations + vues).

- `builder`  : RawObligation -> Obligation (ids stables, canonicalisation vocab).
- `core`     : agrégation en MaterializedIndex (pandas) + relations cross-level + vues.

API publique stable ré-exportée ici pour que `from ..materialize import materialize` etc.
restent valides quelle que soit l'organisation interne.
"""

from __future__ import annotations

from .builder import build_obligations, collect_vocab_gaps
from .core import (
    MaterializedIndex,
    actor_theme_matrix,
    by_actor,
    by_theme,
    load_unit_extractions_from_dir,
    materialize,
    obligations_to_df,
    relations_summary,
    relations_to_df,
    sources_view,
    units_to_df,
)

__all__ = [
    "MaterializedIndex",
    "actor_theme_matrix",
    "build_obligations",
    "by_actor",
    "by_theme",
    "collect_vocab_gaps",
    "load_unit_extractions_from_dir",
    "materialize",
    "obligations_to_df",
    "relations_summary",
    "relations_to_df",
    "sources_view",
    "units_to_df",
]
