# Journal d'avancement — regulatory-index

Synthèse **lisible** de l'avancement, pour préparer les points et présentations client :
retrouver d'un coup d'œil **ce qui est fait** et **ce qui reste à faire**.

- Mise à jour via la skill `/journal` (en fin de session ou avant une présentation).
- Trace brute et exhaustive, une ligne par commit : voir [`CHANGELOG.md`](CHANGELOG.md)
  (alimentée automatiquement par le hook git `post-commit`).

## Reste à faire (backlog)

_Ce qui n'est pas (encore) fait — à garder à jour pour ne rien oublier en présentation._

- [ ] Récupérer le fichier Excel modèle du client (14 onglets, onglet `00_mode d'emploi`).
- [ ] Traduire les 14 onglets en schéma PostgreSQL normalisé (tables + clés).
- [ ] Contrôle de complétude **article par article** (aucun article sauté silencieusement).
- [ ] Agents d'automatisation, un par étape de l'« Ordre d'exécution ».
- [ ] Faire tourner le pipeline sur les textes EN **et** FR.

## Points d'avancement

<!-- Nouvelles entrées en haut. -->
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
