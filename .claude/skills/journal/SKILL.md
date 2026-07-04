---
name: journal
description: Met à jour le journal d'avancement du projet (docs/JOURNAL.md) — une synthèse datée « Fait / Décisions / Reste à faire » depuis le dernier point, à partir de l'historique git réel. À lancer en fin de session de travail ou avant une présentation client, pour retrouver d'un coup d'œil ce qui est fait et ce qui reste à faire.
---

Objectif : maintenir `docs/JOURNAL.md` à jour pour que Cédric prépare ses points
d'avancement sans avoir à reconstituer ce qu'il a fait.

**Ne rien inventer** : tout se fonde sur l'historique git et l'état réel du dépôt.

## Étapes

1. **Trouver la frontière.** Dans `docs/JOURNAL.md`, lire le marqueur
   `<!-- Dernier commit journalisé : <hash> -->`.
   - S'il contient un hash → `RANGE="<hash>..HEAD"`.
   - Sinon (ou `(aucun)`) → `RANGE="-15"` (les 15 derniers commits).

2. **Récupérer les changements réels :**
   - `git log <RANGE> --date=format:'%Y-%m-%d' --pretty=format:'%h|%cd|%s'`
   - `git diff --stat <hash>..HEAD` (ampleur des changements par fichier),
   - `git status --short` (travail en cours **non commité** = WIP à mentionner).

3. **Synthétiser** — ne pas recopier les messages de commit bruts, les regrouper en
   langage métier. Rédiger une entrée datée à placer **en haut** de la section
   `## Points d'avancement` :

   ```
   ### AAAA-MM-JJ — <titre court>

   **Fait**

   - <réalisations regroupées par thème>

   **Décisions / notes**

   - <choix notables, le cas échéant>

   **Reste à faire / en attente**

   - <ce qui est partiel, sauté, ou à poursuivre — explicite>
   ```

   (Laisser une ligne vide entre chaque intitulé en gras et sa liste — évite les
   avertissements markdownlint MD032.)

   Règle importante (exigence d'exhaustivité du client) : tout traitement **partiel**
   — article sauté, texte non couvert, étape inachevée — va **explicitement** dans
   « Reste à faire », jamais passé sous silence.

4. **Mettre à jour le backlog** en tête (`## Reste à faire (backlog)`) : cocher `[x]`
   ce qui est terminé, ajouter les nouveaux `[ ]`.

5. **Mettre à jour le marqueur** avec le hash courant : `git rev-parse --short HEAD`.

6. Écrire le fichier — en français, concis, prêt pour une présentation — puis confirmer
   en une ligne ce qui a été ajouté.

Astuce : si l'utilisateur précise une période (« depuis lundi », « depuis la v1 »),
adapter le `RANGE` en conséquence (ex. `--since='last monday'` ou `<tag>..HEAD`).
