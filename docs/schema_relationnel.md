# Schéma relationnel — **modèle IRR v2** (réconcilié)

> **Modèle réconcilié.** Ce schéma est le modèle relationnel IRR v2 du client,
> issu de `modele_relationnel_raglogic_irr_v2.xlsx` (15 onglets). Le classeur
> n'est qu'une **maquette** : la **source de vérité** est PostgreSQL (schéma
> `regindex`). Neo4j et l'index vectoriel sont des **dérivés** reconstruits
> depuis `regindex` — ils ne portent jamais la donnée golden.

DDL : [`db/schema.sql`](../db/schema.sql) · Application : `just schema-apply`
(= `regindex db apply` ; crée le schéma `regindex` dans la base `lalande`,
**sans toucher** aux tables source du dump dans `public`).

Inspection (lecture seule) : `just db-status` (`regindex db status` — volumétrie
par table + couverture + activité d'extraction) et `just db-query "SELECT …"`
(`regindex db query` — transaction `READ ONLY` : le serveur refuse tout write).
API Python : `regulatory_index.db` (`apply_schema`, `collect_status`,
`read_only_query`). Contrat d'usage détaillé : skill `.claude/skills/regindex-db/`.

## Principes de conception (mode d'emploi client)

- **Aucun statement sans source exacte** : `statement.source_unit_id` est `NOT NULL`
  et référence `source_unit`. L'extraction IA ne produit rien qui ne s'ancre à un
  découpage déterministe du texte.
- **Preuve d'exhaustivité** : chaque `source_unit` a **une** ligne
  `coverage_audit` (unicité encodée par `UNIQUE(source_unit_id)` ; l'existence est
  garantie par le pipeline, pas par une contrainte SQL).
- **Identifiants stables lisibles** en PK `text` pour `regulation`, `source_unit`
  et `statement` (`REG-…`, `SU-…`, `ST-…`) ; les dictionnaires (`actor`/`action`/
  `regulatory_object`) ont aussi une PK `text` lisible (`ACT-…`, `ACTN-…`, `OBJ-…`).
  Les tables de liaison et les faits dérivés (conditions, exceptions, relations,
  contrôles, coverage) portent une PK surrogate `IDENTITY`.
- **Détection de changement** : `source_unit.source_text_hash` (même philosophie
  que le `content_hash` de Lalande).
- **Vocabulaires contraints** (CHECK, valeurs anglaises snake_case) :
  `statement.statement_type`, `statement.validation_status`,
  `coverage_audit.coverage_status`, `dictionary_entry.dictionary_type`.
- **Pas de `ON DELETE CASCADE`** (toutes les FK en `NO ACTION`, intentionnel) :
  supprimer une `regulation` encore référencée échoue — la donnée golden ne se
  détruit jamais en silence. Une suppression est explicite, enfants d'abord
  (coverage → liaisons → statements → source_units → regulation).

## Les 15 tables

| # | Table | Rôle | PK |
|---|---|---|---|
| 01 | `regulation` | textes réglementaires sources | `regulation_id` text (`REG-<celex>`) |
| 02 | `source_unit` | découpage déterministe + `source_text_hash` | `source_unit_id` text (`SU-…`) |
| 03 | `statement` | unité logique extraite/normalisée (cœur) | `statement_id` text (`ST-…`) |
| 04 | `actor` | dictionnaire acteurs | `actor_id` text (`ACT-…`) |
| 05 | `action` | dictionnaire actions | `action_id` text (`ACTN-…`) |
| 06 | `regulatory_object` | dictionnaire objets | `object_id` text (`OBJ-…`) |
| 07 | `statement_actor` | liaison statement ↔ acteur | `statement_actor_id` identity |
| 08 | `statement_action` | liaison statement ↔ action | `statement_action_id` identity |
| 09 | `statement_object` | liaison statement ↔ objet | `statement_object_id` identity |
| 10 | `condition` | conditions d'application/déclenchement | `condition_id` identity |
| 11 | `exception` | exceptions (ou absence documentée) | `exception_id` identity |
| 12 | `statement_relation` | relations entre statements + renvois | `relation_id` identity |
| 13 | `control_mapping` | traduction en contrôles/preuves attendues | `control_mapping_id` identity |
| 14 | `coverage_audit` | preuve d'exhaustivité/qualité | `coverage_id` identity |
| 15 | `dictionary_entry` | référentiel contrôlé initial (seed 04/05/06 + types + thèmes) | `entry_id` identity |

### Diagramme des FKs

```
regulation ──┬──< source_unit ──< statement >── regulation
             │                        │  ▲
             │                        │  └───────────────── (source_unit_id NOT NULL)
             │                        │
             │        ┌───────────────┼───────────────┬───────────────┐
             │        │               │               │               │
             │  statement_actor  statement_action  statement_object  condition
             │        │ >actor        │ >action       │ >regulatory_object
             │        │               │               │
             │   exception       statement_relation   control_mapping
             │        (source_statement_id, target_statement_id? )
             │
             ├──< actor (parent_actor_id self · definition_statement_id > statement)
             ├──< regulatory_object (parent_object_id self · definition_statement_id > statement)
             │
             └──< coverage_audit >── source_unit (UNIQUE) · statement?

dictionary_entry : autonome (seed), UNIQUE(dictionary_type, code)
```

Notes : `statement_relation.target_statement_id` et `coverage_audit.statement_id`
sont **nullable** (renvoi externe non ingéré ; source_unit non couverte). Les
colonnes `theme_id`/`subtheme_id`/`business_process_id`/`risk_category_id` de
`statement` portent des **codes de dictionnaire en réf. souple** (pas de FK : ces
axes n'ont pas de table dédiée au v2).

## Mapping — ancien brouillon → IRR v2

| Ancienne table | → v2 |
|---|---|
| `source` | `regulation` (`source_id`→`regulation_id`, `celex`→`celex_id`, `level`→`legal_level`…) |
| `article` | absorbé dans `source_unit` (article_number + chapter/paragraph/point) |
| `theme` | `dictionary_entry` (`dictionary_type='theme'`) + `statement.theme_id` (réf. souple) |
| `actor` | `actor` (label→`canonical_name`, `actor_type`→`actor_type`) |
| `action` | `action` (label→`canonical_verb`) |
| `controlled_vocabulary` | éclaté : `dictionary_entry` (object/theme…) + colonnes `condition`/`exception`/`statement_relation` |
| `extraction_run` | fondu dans `statement.extraction_model` (+ colonnes de validation) |
| **`obligation`** | **`statement`** (type=`obligation`) + liaisons `statement_actor`/`statement_action`/`statement_object` + `condition` + `exception` + `control_mapping` (`expected_evidence`/`associated_control`) |
| `obligation.actor_id/action_id/object` | `statement_actor`/`statement_action`/`statement_object` (N-N, avec rôle + rang) |
| `obligation_citation` | `statement_relation` (`relation_type='reference'`, `target_reference`) |
| `obligation_relation` | `statement_relation` (`source_statement_id`/`target_statement_id`) |
| `defined_term` | `statement` (type=`definition`) + `actor.definition_statement_id` / `regulatory_object.definition_statement_id` |
| `defined_term_citation` | `statement_relation` (`relation_type='reference'`) |

## Mapping — données existantes → v2

| Source existante | → v2 |
|---|---|
| `data/unites/corpus.jsonl` (`unit_id`, `source_id`, `hierarchy_path`, `text`, `language`, `source_meta`) | `source_unit` (`unit_id`→`source_unit_id`, `hierarchy_path`→`structural_path`, `text`→`source_text_exact` + `source_text_hash`) ; `source_meta`/`source_id` → `regulation` |
| `data/textes_sources/<SOURCE>/…` + `config/sources_registry.yaml` | `regulation` (celex, titre, niveau, url) |
| `data/exports/obligations/obligations.csv` | `statement` (verbatim→`statement_text_exact`) + liaisons `statement_actor`/`_action`/`_object` + `condition`/`exception`/`control_mapping` ; `theme`/`sub_theme`→`theme_id`/`subtheme_id` |
| `obligations.csv: cited_references` | `statement_relation` (`relation_type='reference'`, `target_reference`) |
| `data/exports/obligations/relations.csv` | `statement_relation` (`source/target_obligation_id`→`source/target_statement_id`, `relation_type`, `evidence_text`→`relation_description`) |
| `jalon_cedric/glossaires_par_texte/*` + `data/exports/glossary/*` | `statement` (type=`definition`) + `actor`/`regulatory_object` (`definition_statement_id`, `definition_text`) |
| `config/vocabularies/{actors,actions,objects,themes}.yaml` | seed `dictionary_entry` → `actor`/`action`/`regulatory_object` + `statement.theme_id` |
| `config/glossary/overrides/*.yaml` | enrichissement `actor`/`regulatory_object` (canonicalisation, `parent_*`) |

## Intégration Lalande

- **Détection de changement** : `source_unit.source_text_hash` ↔
  `subdivisions.content_hash` de Lalande. Même contrat — un hash différent
  invalide les statements dérivés et déclenche la re-extraction.
- **Identité stable** : les ids `SU-<CELEX>-ART<n>-P<n>-S<n>` de `regindex`
  correspondent à l'identité `hash(celex | version | langue | chemin)` du
  contrat d'identité Lalande (`docs/architecture/data-identity-contract.md` côté
  Lalande). `regulation.celex_id` fait le pont côté acte.
- **Chemin d'intégration RAG** (étapes 22-23 du mode d'emploi) : depuis
  `regindex` (source de vérité), des **vues dérivées** alimentent les
  **embeddings** (index vectoriel) et le **graphe Neo4j** — reconstruits, jamais
  golden. La donnée réglementaire ne vit qu'une fois, dans PostgreSQL ; RAG et
  graphe en sont des projections régénérables.

## Prochaine étape

- Loader `regindex db-load` : pipeline actuel → tables `regindex` (résolution
  des dictionnaires `actor`/`action`/`regulatory_object`, dédup, FK, calcul
  `source_text_hash`, génération des lignes `coverage_audit`).
