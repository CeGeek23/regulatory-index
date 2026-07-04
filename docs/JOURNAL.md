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
<!-- Dernier commit journalisé : (aucun) -->

### 2026-07-04 — Mise en place du journal d'avancement
**Fait**
- Ajout d'un système de journalisation à deux niveaux : `docs/JOURNAL.md` (synthèse
  lisible) + `docs/CHANGELOG.md` (trace auto des commits via hook git `post-commit`).
- Ajout de la skill `/journal` pour tenir ce fichier à jour.

**Décisions / notes**
- Objectif : préparer les points client sans reconstituer a posteriori ce qui a été fait.
- Tout traitement partiel doit apparaître explicitement en « Reste à faire ».

**Reste à faire / en attente**
- Voir le backlog ci-dessus (démarre au retour du fichier modèle du client).
