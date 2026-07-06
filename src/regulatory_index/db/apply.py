"""Application du schéma relationnel `regindex` (DDL) depuis `db/schema.sql`.

Le SQL recrée le schéma `regindex` (idempotent, `DROP SCHEMA … CASCADE` limité à
`regindex`) sans toucher aux tables source du dump (dans `public`).
"""

from __future__ import annotations

from pathlib import Path

from .connection import connect

DEFAULT_SCHEMA_SQL = Path("db/schema.sql")


def apply_schema(dsn: str | None = None, *, schema_sql: Path = DEFAULT_SCHEMA_SQL) -> int:
    """Applique le DDL de `schema_sql` et retourne le nombre de tables dans `regindex`.

    psycopg3 exécute des instructions multiples en un appel tant qu'il n'y a pas
    de paramètres — le fichier est joué tel quel.
    """
    sql = schema_sql.read_text(encoding="utf-8")
    with connect(dsn, autocommit=True) as conn:
        conn.execute(sql.encode("utf-8"))
        row = conn.execute(
            b"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'regindex'"
        ).fetchone()
    return int(row[0]) if row else 0
