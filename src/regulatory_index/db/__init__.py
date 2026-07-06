"""Accès à la base golden `regindex` (IRR v2) depuis le code et la CLI.

Surface publique : DDL (`apply_schema`), état (`collect_status` + modèles),
requête ad hoc en lecture seule (`read_only_query`), et les primitives de
connexion. La source de vérité du schéma reste `db/schema.sql`.
"""

from __future__ import annotations

from .apply import apply_schema
from .connection import connect, read_only_connection, resolve_dsn
from .dictionary import (
    CandidateResult,
    DictionarySeed,
    DictionaryStatus,
    SeedResult,
    dictionary_status,
    inject_candidates,
    load_dictionary_seed,
    seed_dictionary,
    seed_plan,
)
from .ingest import (
    RegulationRow,
    SourceUnitRow,
    UpsertCounts,
    ingest_regulation,
    ingest_source_units,
)
from .query import QueryResult, read_only_query
from .status import (
    CoverageCount,
    DbStatus,
    ExtractionRun,
    TableCount,
    collect_status,
)

__all__ = [
    "CandidateResult",
    "CoverageCount",
    "DbStatus",
    "DictionarySeed",
    "DictionaryStatus",
    "ExtractionRun",
    "QueryResult",
    "RegulationRow",
    "SeedResult",
    "SourceUnitRow",
    "TableCount",
    "UpsertCounts",
    "apply_schema",
    "collect_status",
    "connect",
    "dictionary_status",
    "ingest_regulation",
    "ingest_source_units",
    "inject_candidates",
    "load_dictionary_seed",
    "read_only_connection",
    "read_only_query",
    "resolve_dsn",
    "seed_dictionary",
    "seed_plan",
]
