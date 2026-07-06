"""Tests du module `regulatory_index.db` avec une connexion psycopg mockée.

La base réelle n'est pas disponible en CI ; comme pour `test_langextract_runner`
(LLM mocké), on vérifie ici la **construction des requêtes/modèles** contre un
faux `psycopg.connect`. Le fake mappe chaque requête (bytes ou `psycopg.sql`) à un
jeu de lignes, ce qui exerce le SQL réellement émis par le module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from psycopg import sql

from regulatory_index.db import connection
from regulatory_index.db.query import read_only_query
from regulatory_index.db.status import DbStatus, collect_status

_NOW = datetime(2026, 7, 6, 10, 0, tzinfo=UTC)


class _FakeCursor:
    def __init__(self, responses: dict[str, list[tuple[Any, ...]]]) -> None:
        self._responses = responses
        self._rows: list[tuple[Any, ...]] = []
        self.description: list[Any] | None = None

    def execute(self, query: bytes | sql.Composable, params: Any = None) -> _FakeCursor:
        key = _query_key(query)
        self._rows = self._responses[key]
        self.description = (
            [_Col(f"c{i}") for i in range(len(self._rows[0]))] if self._rows else None
        )
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class _Col:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeConnection:
    def __init__(self, responses: dict[str, list[tuple[Any, ...]]]) -> None:
        self._responses = responses
        self.read_only: bool | None = None

    def execute(self, query: bytes | sql.Composable, params: Any = None) -> _FakeCursor:
        return _FakeCursor(self._responses).execute(query)

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._responses)

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _query_key(query: bytes | sql.Composable) -> str:
    """Clé stable identifiant une requête, qu'elle soit bytes ou psycopg.sql."""
    text = query.decode("utf-8") if isinstance(query, bytes) else query.as_string(None)
    return " ".join(text.split())


_STATUS_RESPONSES: dict[str, list[tuple[Any, ...]]] = {
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'regindex' AND table_type = 'BASE TABLE' "
    "ORDER BY table_name": [("regulation",), ("source_unit",), ("statement",)],
    'SELECT count(*) FROM "regindex"."regulation"': [(2,)],
    'SELECT count(*) FROM "regindex"."source_unit"': [(40,)],
    'SELECT count(*) FROM "regindex"."statement"': [(17,)],
    "SELECT coverage_status, count(*) FROM regindex.coverage_audit "
    "GROUP BY coverage_status ORDER BY coverage_status": [
        ("covered", 30),
        ("to_review", 10),
    ],
    "SELECT extraction_model, count(*), max(created_at) FROM regindex.statement "
    "GROUP BY extraction_model ORDER BY max(created_at) DESC NULLS LAST": [
        ("qwen2.5-7b-instruct", 17, _NOW),
    ],
}


def _patch_connect(
    monkeypatch: pytest.MonkeyPatch, responses: dict[str, list[tuple[Any, ...]]]
) -> None:
    def fake_connect(*_: Any, **__: Any) -> _FakeConnection:
        return _FakeConnection(responses)

    monkeypatch.setattr(psycopg, "connect", fake_connect)


def test_collect_status_shapes_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connect(monkeypatch, _STATUS_RESPONSES)
    status = collect_status()
    assert isinstance(status, DbStatus)
    assert status.schema_name == "regindex"
    assert {t.table: t.rows for t in status.tables} == {
        "regulation": 2,
        "source_unit": 40,
        "statement": 17,
    }
    assert status.total_rows == 59
    assert {c.coverage_status: c.units for c in status.coverage} == {
        "covered": 30,
        "to_review": 10,
    }
    assert len(status.extraction_runs) == 1
    run = status.extraction_runs[0]
    assert run.extraction_model == "qwen2.5-7b-instruct"
    assert run.statements == 17
    assert run.last_created_at == _NOW


def test_read_only_connection_marks_transaction_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, _FakeConnection] = {}

    def fake_connect(*_: Any, **__: Any) -> _FakeConnection:
        conn = _FakeConnection({})
        captured["conn"] = conn
        return conn

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    with connection.read_only_connection():
        pass
    assert captured["conn"].read_only is True


def test_read_only_query_returns_columns_and_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "SELECT regulation_id, official_title FROM regindex.regulation"
    responses = {_query_key(query.encode("utf-8")): [("REG-1", "AIFMD"), ("REG-2", "MiFID")]}
    _patch_connect(monkeypatch, responses)
    result = read_only_query(query)
    assert result.columns == ["c0", "c1"]
    assert result.rows == [("REG-1", "AIFMD"), ("REG-2", "MiFID")]
    assert result.row_count == 2
