# Journal d'avancement — regulatory-index

Synthèse **lisible** de l'avancement, pour préparer les points et présentations client :
retrouver d'un coup d'œil **ce qui est fait** et **ce qui reste à faire**.

- Mise à jour via la skill `/journal` (en fin de session ou avant une présentation).
- Trace brute et exhaustive, une ligne par commit : voir [`CHANGELOG.md`](CHANGELOG.md)
  (alimentée automatiquement par le hook git `post-commit`).

## Reste à faire (backlog)

_Ce qui n'est pas (encore) fait — à garder à jour pour ne rien oublier en présentation._

- [x] Récupérer le fichier Excel modèle du client (reçu : `modele_relationnel_raglogic_irr_v2.xlsx`, 16 onglets).
- [x] Traduire les onglets en schéma PostgreSQL normalisé (15 tables, schéma `regindex` — branche `claude/irr-schema-v2`).
- [ ] Contrôle de complétude **article par article** (aucun article sauté silencieusement).
- [ ] Agents d'automatisation, un par étape de l'« Ordre d'exécution ».
- [ ] Faire tourner le pipeline sur les textes EN **et** FR.

## Points d'avancement

<!-- Nouvelles entrées en haut. -->

### 2026-07-06 — Schéma IRR v2 (modèle client) + interface `regindex db`

**Fait**
- Le modèle relationnel du client est arrivé (`modele_relationnel_raglogic_irr_v2.xlsx`,
  16 onglets) : `db/schema.sql` réécrit en modèle réconcilié — 15 tables dans le schéma
  PG `regindex`, 29 FKs, CHECKs alignés sur les 10 `statement_type` et les 5 statuts de
  couverture du mode d'emploi, PK lisibles stables (`REG-`/`SU-`/`ST-`/`ACT-`).
  **Fidélité vérifiée colonne par colonne contre le classeur (14/14 tables exactes).**
- Interface Claude Code : paquet `src/regulatory_index/db` + CLI `regindex db
  apply|status|query` + skill `.claude/skills/regindex-db` + cibles `just`.
- Vérification adversariale sur base réelle : ordre d'insertion du mode d'emploi joué
  avec AIFMD (32011L0061), sondes de contraintes toutes refusées, `just check` vert
  (ruff, mypy 69 fichiers, 83 tests).

**Décisions**
- Suppression en `NO ACTION` (pas de cascade) : donnée golden auditable, suppression
  enfants-d'abord — invariant commenté dans le schéma.
- `db query` = **garde-fou** lecture-seule côté serveur
  (`default_transaction_read_only=on` session) — la revue a prouvé le contournement du
  simple `conn.read_only` (`COMMIT; INSERT` écrivait réellement) et l'a corrigé ;
  limite résiduelle documentée : la vraie frontière sera un rôle SQL sans écriture.
- Onglet `15_dictionnaire` (pivot multi-blocs) normalisé en
  `dictionary_entry(dictionary_type)`.
- Convergence Lalande actée dans `docs/schema_relationnel.md` : `source_text_hash` ↔
  `content_hash`, ids stables `SU-*` ↔ contrat d'identité Lalande, RAG dérivé de PG
  (étapes 22-23 du client).

**Reste à faire**
- Provisionner un rôle SQL lecture-seule dédié (la limite documentée de `db query`).
- Étapes suivantes du mode d'emploi (à dévoiler par Cédric) : imports 01→02 (parser
  déterministe), dictionnaires, extraction → `statement`, liaisons, couverture.
- Migrer les données existantes (extractions JSON, glossaires jalon) vers le schéma v2
  (mapping écrit dans `docs/schema_relationnel.md`).

<!-- Dernier commit journalisé : aadbb54 -->

### 2026-07-04 — Initialisation du journal (rattrapage 21/06 → 04/07)

_Entrée de rattrapage : synthèse des 15 derniers commits._

**Fait**

- **Glossaire & extraction niveau 1** : glossaire L1 consolidé multi-actes avec typologie
  acteur / produit / activité, graphe de renvois inter-textes (extraction fidèle), règles
  d'extraction **générales** (acteur substantiel, verbe ancré, clause permissive) +
  déduplication déterministe. Corpus AIFMD L1 reconstruit hors-ligne, complet.
- **Bascule vers une source unique = le dump PostgreSQL** : suppression de toute
  l'acquisition réseau (fetchers EUR-Lex / AMF / Légifrance) au profit d'un pont
  **DB → corpus** (lecteur du dump PostgreSQL → `NormativeUnit`). `obligation_id` désormais
  préfixé par l'acte → généralise le multi-texte (L1 + L2).
- **Outillage & doc** : dossiers `.claude/hooks` et `.claude/skills`, gros nettoyage de code
  mort / config spéculative, corrections doc, et mise en place du **journal d'avancement**
  (hook `post-commit` + skill `/journal`).

**Décisions / notes**

- Choix structurant : abandon de l'acquisition réseau ; le corpus se reconstruit depuis le
  cache HTML + le **dump PostgreSQL** (source unique, reproductible hors-ligne). Aligné avec
  la direction voulue par le client (base Postgres normalisée).
- Extraction pilotée par des **règles générales** (aucun patch par article), testées sur des
  cas abstraits (`tests/test_obligation_builder.py`).

**Reste à faire / en attente**

- **Fichier modèle Excel du client** (14 onglets, `00_mode d'emploi`) à récupérer — bloquant.
- Schéma **PostgreSQL normalisé** des 14 tables (tables + clés) + mapping sur le pipeline.
- **Complétude article par article** ; trou connu : **AIFMD Article 21 (dépositaire)** non
  extrait (trop long pour le modèle local) → à traiter par découpage / modèle plus grand.
- **Agents** d'automatisation, un par étape de l'« Ordre d'exécution ».
- Faire tourner le pipeline sur les textes **EN et FR**.
