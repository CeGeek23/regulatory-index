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

## Ingestion 01/02 — base Lalande → `regulation` + `source_unit`

`regindex ingest <CELEX>` (module `regulatory_index.db.ingest`) alimente les tables
01/02 depuis la base corpus Lalande (`public.acts`/`versions`/`subdivisions`). Source
**unique** du corpus. Règles **structurelles générales** — aucun `if celex==…`, aucune
liste par article, aucune regex, aucun fallback :

- **Version retenue** : la plus récente pour la langue (`ORDER BY version_date DESC
  NULLS LAST, version_number DESC`) — choix éprouvé de `db_corpus.py`. L'ordre document
  est `ORDER BY hierarchy_path` (== `sequence_order`, garanti intra-version seulement).
- **`regulation`** (01) : 1 ligne par acte. `official_title`/`short_name`/`eurlex_url`/
  `language` ← `acts` ; `consolidation_date` ← `versions.version_date` ; `legal_level`
  ← registre (`L1`/`L2`/`L3`/`national`), **NULL** si le CELEX est absent du registre
  (il s'ingère quand même) ; `legal_instrument_type` ← `acts.act_type`.
- **`source_unit`** (02) : dérivé de l'arbre des `subdivisions` d'un **article**.
  - *paragraphe* (enfant **direct** d'article) → découpé en **phrases** (`S01`, `S02`…).
  - *point* / *subpoint* → **1 unité** (`sentence_number='1'`) : fragment juridique
    citable non découpé, même s'il contient une frontière de phrase interne.
  - **exclus** : notes de bas de page (paragraphe dont le parent est
    paragraph/point/subpoint), en-têtes chapter/section/article, racine `title` (depth 0),
    `preamble`, **annexes** (différées : pas de coordonnée annexe en base).
  - `paragraph_number` = **ordinal de bloc** du paragraphe enfant direct (ordre document,
    notes exclues) — pas forcément le n° officiel cité (déviation documentée).
  - `point_number`/`subpoint_number` = **label inline** verbatim (contenu entre le `(`
    initial et le premier `)`, extraction str sans regex). Le subpoint hérite du label de
    son point ancêtre (chaîne `parent_id`, robuste à l'aplatissement DR231).
  - `chapter_number`/`section_number`/`title_number` = `number` de l'ancêtre correspondant.
  - `structural_path` = titres **lisibles** des ancêtres (chapter/section/article) +
    `paragraph N` + `point (x)` — **jamais** les jetons `hierarchy_path`.
  - `source_text_exact` = `subdivisions.content` verbatim ; `source_text_hash` = SHA-256 hex.
- **Découpe en phrases** (`split_sentences`, sans regex) : frontière = `.`/`!`/`?` +
  ≥1 blanc + première lettre non-blanche **MAJUSCULE** ; `;`/`:` (séparateurs de listes)
  ne coupent jamais ; dates (`17.11.2009`) et `p. 1.` neutralisées par la forme du texte.
- **Id stable** `SU-<CELEX>-ART<n>[-P<n>][-PT<label>][-SPT<label>]-S<nn>` : 100 %
  coordonnées structurelles (le tiret d'`ART69-A` vs `ART69A` est **préservé** — deux
  articles distincts). **Jamais** dérivé de `subdivisions.id` ni de `hierarchy_path`
  (non stables inter-version).
- **`coverage_audit`** : 1 ligne `status='not_covered'` par `source_unit` (invariant
  d'exhaustivité), posée à l'ingestion.
- **Idempotence** : re-run ⇒ mêmes ids. `source_unit` en upsert `ON CONFLICT
  (source_unit_id) DO UPDATE … WHERE hash différent` (ne réécrit que sur dérive de texte) ;
  `coverage_audit` en `INSERT … WHERE NOT EXISTS` (jamais de doublon ni d'écrasement d'une
  revue humaine).

Volumétrie mesurée (dernière version EN) : AIFMD `32011L0061` → 1 `regulation` +
1463 `source_unit` ; DR231 `32013R0231` → 1 + 1034.

## Prochaine étape

- Loader statements `regindex db-load` : pipeline d'extraction actuel → tables 03+
  (`statement` + liaisons `actor`/`action`/`regulatory_object`, `condition`/`exception`,
  résolution des dictionnaires, FK) et mise à jour de `coverage_audit`
  (`covered`/`partially_covered`). L'ingestion 01/02 (`regindex ingest`) est faite.
