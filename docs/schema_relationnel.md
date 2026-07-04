# Schéma relationnel normalisé — **provisoire**

> ⚠️ **Provisoire.** Ce schéma est dérivé de **nos données actuelles** (obligations,
> relations, glossaire). C'est un **point de départ concret**, pas la cible finale : il
> devra être **réconcilié avec le modèle du client** (les **14 onglets** de son Excel)
> dès réception. On mappera alors chaque table ci-dessous sur ses onglets, en renommant /
> fusionnant / scindant au besoin.

DDL : [`db/schema.sql`](../db/schema.sql) · Application : `just schema-apply`
(crée le schéma `regindex` dans la base `lalande`, **sans toucher** aux tables source du dump).

## Pourquoi

Le client veut « un modèle relationnel normalisé » (14 tables) plutôt que des fichiers plats
épars. Aujourd'hui, notre pipeline sort une **grande table plate** (`obligations.csv`) + vues.
Ce schéma **normalise** ces données en tables liées par des clés — la structure qu'il attend.

## Les 12 tables

| Table | Rôle | Clés |
|---|---|---|
| `source` | acte réglementaire (AIFMD_L1…) | PK `source_id` |
| `article` | article d'un acte | PK `article_id`, FK `source_id`, `UNIQUE(source_id, number)` |
| `theme` | thème (Governance, Risk…) | PK `theme_code` |
| `actor` | acteur + typologie acteur/produit/activité (du glossaire) | PK `actor_id`, `label_en` unique |
| `action` | verbe d'obligation (vocab contrôlé) | PK `action_id`, `label_en` unique |
| `controlled_vocabulary` | vocab générique (object, condition, relation_type, acronym…) | PK `id`, `UNIQUE(kind, code)` |
| `extraction_run` | traçabilité (modèle, version, date) | PK `run_id` |
| **`obligation`** | **fait central** : acteur · action · objet · condition · verbatim · article | PK `obligation_id`, FK vers `source/article/actor/action/theme/extraction_run` |
| `obligation_citation` | références citées **par** une obligation (multi-valué) | PK `citation_id`, FK `obligation_id`, `target_source_id` |
| `obligation_relation` | renvois **obligation → obligation** (graphe L2→L1) | PK `relation_id`, FK `source/target_obligation_id` |
| `defined_term` | terme défini du glossaire | PK `term_id`, FK `source_id` |
| `defined_term_citation` | renvois portés par une définition (`cites`) | PK `id`, FK `term_id`, `target_source_id` |

Relations principales : `source 1—N article 1—N obligation N—1 {actor, action, theme}` ;
`obligation 1—N obligation_citation` ; `obligation N—N obligation` via `obligation_relation` ;
`source 1—N defined_term 1—N defined_term_citation`.

## Mapping depuis nos données actuelles

| Sortie actuelle (colonne) | → Destination |
|---|---|
| `obligations.csv: obligation_id` | `obligation.obligation_id` |
| `source_id, celex, level, issuer, title, source_url` | `source.*` |
| `article` (+ `paragraph`, `point`) | `article.number` (→ `obligation.article_id`) |
| `actor` | `actor.label_en` + `actor_type` (glossaire) → `obligation.actor_id` |
| `action` | `action.label_en` → `obligation.action_id` |
| `object` | `obligation.object` |
| `theme` / `sub_theme` | `theme.theme_code` / `obligation.sub_theme` |
| `condition, scope, exception, expected_evidence, associated_control` | `obligation.*` |
| `verbatim_text, char_start, char_end, language, human_validated` | `obligation.*` |
| `cited_references` (multi-valué) | `obligation_citation.*` |
| `extraction_model, extracted_at` | `extraction_run.*` |
| `relations.csv: source/target_obligation_id, relation_type, citation_in_text, evidence_text` | `obligation_relation.*` |
| Glossaire (`term_en, term_fr, type, legal_basis, definition_en/fr`) | `defined_term.*` |
| Glossaire `cites` | `defined_term_citation.*` |
| `config/vocabularies/*` (themes, actions, objects, conditions, relation_types, acronyms) | `theme`, `action`, `controlled_vocabulary` |

## Prochaine étape

- Écrire le **loader** `regindex db-load` : pipeline → tables `regindex` (résolution des
  dimensions actor/action/theme, dédup, FK).
- **Réconcilier** avec les 14 onglets du client à réception de son Excel (ce schéma sert de base
  de discussion — renommage/fusion/scission des tables selon son modèle).
