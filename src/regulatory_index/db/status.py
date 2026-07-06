"""État de la base `regindex` : volumétrie, couverture, activité d'extraction.

Le module ne fait que **collecter des données** (modèles Pydantic) ; leur
affichage vit dans la CLI. Toutes les lectures passent par une transaction
`READ ONLY` (`read_only_connection`).

La liste des tables est **découverte** dans `information_schema` (jamais codée en
dur) : le status reste juste si le schéma gagne ou perd une table.
"""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg import sql
from psycopg.rows import TupleRow
from pydantic import BaseModel

from .connection import read_only_connection

SCHEMA = "regindex"


class TableCount(BaseModel):
    """Nombre de lignes d'une table de `regindex`."""

    table: str
    rows: int


class CoverageCount(BaseModel):
    """Nombre de `source_unit` par statut de couverture (`coverage_audit`)."""

    coverage_status: str
    units: int


class ExtractionRun(BaseModel):
    """Activité d'extraction agrégée par modèle : combien de statements, quand.

    Proxy de « run » tant qu'il n'existe pas de table de runs dédiée : la trace
    d'exécution vit dans `statement.extraction_model` + `statement.created_at`.
    """

    extraction_model: str | None
    statements: int
    last_created_at: datetime | None


class DbStatus(BaseModel):
    """Vue d'ensemble de `regindex` (données ; l'affichage est côté CLI)."""

    schema_name: str = SCHEMA
    tables: list[TableCount]
    coverage: list[CoverageCount]
    extraction_runs: list[ExtractionRun]

    @property
    def total_rows(self) -> int:
        return sum(t.rows for t in self.tables)


def _table_names(conn: psycopg.Connection[TupleRow]) -> list[str]:
    rows = conn.execute(
        b"SELECT table_name FROM information_schema.tables "
        b"WHERE table_schema = 'regindex' AND table_type = 'BASE TABLE' "
        b"ORDER BY table_name"
    ).fetchall()
    return [str(r[0]) for r in rows]


def _row_count(conn: psycopg.Connection[TupleRow], table: str) -> int:
    # Identifiant issu d'information_schema, composé via psycopg.sql (jamais interpolé).
    query = sql.SQL("SELECT count(*) FROM {}.{}").format(
        sql.Identifier(SCHEMA), sql.Identifier(table)
    )
    row = conn.execute(query).fetchone()
    return int(row[0]) if row else 0


def _coverage(conn: psycopg.Connection[TupleRow]) -> list[CoverageCount]:
    rows = conn.execute(
        b"SELECT coverage_status, count(*) FROM regindex.coverage_audit "
        b"GROUP BY coverage_status ORDER BY coverage_status"
    ).fetchall()
    return [CoverageCount(coverage_status=str(r[0]), units=int(r[1])) for r in rows]


def _extraction_runs(conn: psycopg.Connection[TupleRow]) -> list[ExtractionRun]:
    rows = conn.execute(
        b"SELECT extraction_model, count(*), max(created_at) FROM regindex.statement "
        b"GROUP BY extraction_model ORDER BY max(created_at) DESC NULLS LAST"
    ).fetchall()
    return [
        ExtractionRun(
            extraction_model=None if r[0] is None else str(r[0]),
            statements=int(r[1]),
            last_created_at=r[2],
        )
        for r in rows
    ]


def collect_status(dsn: str | None = None) -> DbStatus:
    """Interroge `regindex` (en lecture seule) et renvoie sa vue d'ensemble."""
    with read_only_connection(dsn) as conn:
        tables = [
            TableCount(table=name, rows=_row_count(conn, name)) for name in _table_names(conn)
        ]
        return DbStatus(
            tables=tables,
            coverage=_coverage(conn),
            extraction_runs=_extraction_runs(conn),
        )
