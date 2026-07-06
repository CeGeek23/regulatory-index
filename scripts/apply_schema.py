"""Applique `db/schema.sql` au schéma `regindex` (compat justfile `schema-apply`).

Fine enveloppe autour de `regulatory_index.db.apply_schema` — la logique vit dans
le module ; ce script reste pour la cible `just schema-apply`.
"""

from __future__ import annotations

from regulatory_index.db import apply_schema
from regulatory_index.db.apply import DEFAULT_SCHEMA_SQL


def main() -> int:
    n = apply_schema()
    print(f"OK — schéma regindex appliqué ({n} tables) depuis {DEFAULT_SCHEMA_SQL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
