"""Connexions à la base `regindex` (schéma golden IRR v2).

Réutilise `resolve_dsn` de l'ingestion (source unique du DSN) — pas de
duplication. `read_only_connection` pose un garde-fou anti-écriture *côté
serveur* (`default_transaction_read_only=on`), pas une inspection de la requête.
Portée exacte du garde-fou : voir la docstring de `read_only_connection`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import TupleRow

from ..ingestion.db_corpus import resolve_dsn

__all__ = ["connect", "read_only_connection", "resolve_dsn"]


def connect(dsn: str | None = None, *, autocommit: bool = False) -> psycopg.Connection[TupleRow]:
    """Connexion en lecture/écriture (DDL, chargements). DSN via `resolve_dsn`."""
    return psycopg.connect(resolve_dsn(dsn), autocommit=autocommit)


@contextmanager
def read_only_connection(dsn: str | None = None) -> Iterator[psycopg.Connection[TupleRow]]:
    """Garde-fou anti-écriture *côté serveur* (pas une inspection de requête).

    Le défaut de transaction est posé au niveau SESSION
    (`default_transaction_read_only=on`), pas seulement sur la transaction que
    psycopg ouvre : une requête multi-instructions qui contient un `COMMIT;`
    (qui clôt la transaction read-only de psycopg) retombe malgré tout sur une
    nouvelle transaction read-only, et le write y lève `ReadOnlySqlTransaction`.

    PORTÉE (garde-fou, PAS frontière de privilège) : arrête tout write
    accidentel — un `UPDATE`/`INSERT` isolé, ou après un `COMMIT;` intercalé.
    Ce que ça n'arrête PAS : un appelant qui ouvre *explicitement* une
    transaction read-write (`BEGIN READ WRITE` / `SET TRANSACTION READ WRITE`)
    AVEC un rôle qui a le privilège d'écrire — c'est un défaut, pas
    `default_transaction_read_only`, qui n'est qu'un défaut surchargeable. La
    vraie frontière serait un rôle SQL sans droit d'écriture (le DSN courant est
    un superuser) ; hors périmètre de cet outil CLI mono-tenant.
    """
    with psycopg.connect(resolve_dsn(dsn), options="-c default_transaction_read_only=on") as conn:
        conn.read_only = True
        yield conn
