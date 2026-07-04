"""Applique `db/schema.sql` au schéma `regindex` de la base PostgreSQL.

Le SQL recrée le schéma `regindex` (idempotent) sans toucher aux tables source du dump
(dans `public`). DSN via `LALANDE_DSN`, sinon le conteneur Docker local par défaut.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from regulatory_index.ingestion.db_corpus import resolve_dsn

SCHEMA_SQL = Path("db/schema.sql")


def main() -> int:
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    with psycopg.connect(resolve_dsn(), autocommit=True) as conn:
        conn.execute(sql)  # psycopg3 : multi-statements OK sans paramètres
        row = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'regindex'"
        ).fetchone()
    n = int(row[0]) if row else 0
    print(f"OK — schéma regindex appliqué ({n} tables) depuis {SCHEMA_SQL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
