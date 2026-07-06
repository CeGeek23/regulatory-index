"""Accès à la base golden `regindex` (IRR v2) depuis le code et la CLI.

Surface publique : DDL (`apply_schema`), état (`collect_status` + modèles),
requête ad hoc en lecture seule (`read_only_query`), et les primitives de
connexion. La source de vérité du schéma reste `db/schema.sql`.
"""

from __future__ import annotations

from .apply import apply_schema
from .connection import connect, read_only_connection, resolve_dsn
from .query import QueryResult, read_only_query
from .status import (
    CoverageCount,
    DbStatus,
    ExtractionRun,
    TableCount,
    collect_status,
)

__all__ = [
    "CoverageCount",
    "DbStatus",
    "ExtractionRun",
    "QueryResult",
    "TableCount",
    "apply_schema",
    "collect_status",
    "connect",
    "read_only_connection",
    "read_only_query",
    "resolve_dsn",
]
