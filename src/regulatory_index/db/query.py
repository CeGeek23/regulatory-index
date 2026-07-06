"""Requête SQL ad hoc en **lecture seule** sur `regindex`.

Garde-fou anti-écriture côté serveur (`read_only_connection`) : un write
accidentel (INSERT/UPDATE/DELETE/DDL, même après un `COMMIT;` intercalé) lève
`psycopg.errors.ReadOnlySqlTransaction`, jamais une inspection du texte côté
client. Portée et limite du garde-fou : voir `connection.read_only_connection`.
"""

from __future__ import annotations

from pydantic import BaseModel

from .connection import read_only_connection


class QueryResult(BaseModel):
    """Résultat tabulaire d'une requête SELECT (colonnes + lignes)."""

    columns: list[str]
    rows: list[tuple[object, ...]]

    @property
    def row_count(self) -> int:
        return len(self.rows)


def read_only_query(query: str, dsn: str | None = None) -> QueryResult:
    """Exécute `query` dans une transaction `READ ONLY` et renvoie ses lignes.

    Un write y lève `psycopg.errors.ReadOnlySqlTransaction` (propagée telle
    quelle : c'est le serveur qui fait foi).
    """
    with read_only_connection(dsn) as conn, conn.cursor() as cur:
        cur.execute(query.encode("utf-8"))
        columns = [d.name for d in cur.description] if cur.description else []
        rows = [tuple(row) for row in cur.fetchall()] if cur.description else []
    return QueryResult(columns=columns, rows=rows)
