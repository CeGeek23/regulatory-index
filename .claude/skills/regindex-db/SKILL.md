---
name: regindex-db
description: Interagir avec la base golden regindex (modèle IRR v2, schéma PostgreSQL). À utiliser pour TOUTE lecture/inspection de la base (volumétrie, couverture, requête SQL) et pour (ré)appliquer le schéma. Impose le contrat : schéma = db/schema.sql, PG = source de vérité, jamais de DDL/write sauvage.
---

# regindex-db — accès à la base golden IRR v2

Quand une tâche touche la base `regindex` (inspecter, compter, requêter, appliquer le
schéma), passe par le module `regulatory_index.db` et la sous-commande CLI `regindex db`.
Ne jamais ouvrir psycopg à la main ni écrire du SQL de write ad hoc.

## Contrat (à respecter absolument)

- **Le schéma vit dans `db/schema.sql`** — source unique du DDL. On ne modifie le schéma
  qu'en éditant ce fichier puis en le réappliquant (`regindex db apply`). Jamais de
  `CREATE/ALTER/DROP TABLE` tapé à la volée.
- **PostgreSQL (schéma `regindex`) est la source de vérité.** Neo4j et l'index vectoriel en
  sont des dérivés régénérables — ils ne portent jamais la donnée golden.
- **Écriture UNIQUEMENT via les pipelines/CLI dédiés** (à venir : loader `db-load`). Toute
  requête d'exploration se fait en **lecture seule** : `regindex db query` ouvre une
  transaction `READ ONLY` — c'est le serveur qui refuse INSERT/UPDATE/DELETE/DDL
  (`ReadOnlySqlTransaction`), pas une inspection de la requête. Ne contourne pas ce mode.
- **Idempotence** : `regindex db apply` fait `DROP SCHEMA regindex CASCADE` puis recrée —
  ne touche jamais aux tables source du dump (dans `public`). À n'exécuter que quand on veut
  effectivement (re)poser le schéma.

## Commandes

| But | Just | CLI directe |
|---|---|---|
| (Ré)appliquer le schéma | `just schema-apply` | `regindex db apply` |
| État (volumétrie + couverture + extraction) | `just db-status` | `regindex db status` |
| Requête SELECT lecture seule | `just db-query "SELECT …"` | `regindex db query "SELECT …"` |

Quirk d'environnement (mémoire projet) : les cibles `just` exportent `PYTHONPATH=src` et
utilisent `uv run --no-sync`. En appel direct, préfixer de même : `PYTHONPATH=src uv run
--no-sync regindex db status` (sinon `ModuleNotFoundError: regulatory_index`, l'éditable
ayant pu être désinstallé au re-sync).

## API Python (si besoin en code, pas en shell)

`from regulatory_index.db import apply_schema, collect_status, read_only_query` — plus les
modèles Pydantic `DbStatus`, `TableCount`, `CoverageCount`, `ExtractionRun`, `QueryResult`.
`collect_status()` et `read_only_query()` sont en lecture seule ; `apply_schema()` écrit le
DDL. La liste des tables du status est **découverte** dans `information_schema` (jamais codée
en dur) — cohérent avec « généraliser, jamais spécialiser ».

## Où on en est (mode d'emploi client)

Le « mode d'emploi » (onglet `00` du classeur, ordre d'exécution en ~24 étapes) va du
découpage déterministe du texte jusqu'à l'intégration RAG (embeddings + graphe Neo4j en
étapes 22-23). État courant :

- **Fait** : modèle IRR v2 posé — les 15 tables du schéma `regindex` appliquées
  (`db/schema.sql`), FKs + CHECK d'énumération en base. Doc : `docs/schema_relationnel.md`.
- **En cours / prochaine étape** : loader `db-load` (pipeline d'extraction actuel →
  tables `regindex` : résolution des dictionnaires actor/action/object, dédup, FK, calcul
  `source_text_hash`, génération des lignes `coverage_audit`). Tant qu'il n'a pas tourné,
  `db status` renvoie des tables vides — normal.
- **Aval** : contrôle de complétude article par article, puis vues dérivées → RAG/graphe.

Consulter `docs/JOURNAL.md` (Fait / Reste à faire) pour l'avancement détaillé avant un point
client.
