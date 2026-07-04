# Journal des commits (automatique)

> Une ligne par commit, ajoutée automatiquement par le hook git `post-commit`.
> Trace brute et exhaustive. Pour la synthèse lisible, voir `JOURNAL.md`.

- **2026-06-21 02:42** · `7dd9b0e` — Trame de prise de parole (~5 min) + prépa Q&A pour la présentation
- **2026-06-21 02:54** · `31a9be9` — Bascule Polars -> pandas (matérialisation + export)
- **2026-06-21 03:37** · `ac95630` — Généralise : supprime prune.yaml ET tie_breaks.yaml (règles générales, zéro liste)
- **2026-06-21 03:42** · `db89588` — Visu LangExtract : extraction ancrée (texte surligné par thème)
- **2026-06-21 03:49** · `58ef008` — Visu ancrée recentrée sur le GLOSSAIRE (brief client), pas les obligations
- **2026-06-21 04:02** · `a7771aa` — Fix bloquant : export Excel plantait sur champs optionnels mixtes (régression pandas)
- **2026-06-21 07:25** · `9db8cfb` — Traque d'erreurs (4 sous-systèmes) : corrige 2 bloquants + 7 importants
- **2026-06-21 07:43** · `4d32fd2` — Unifie la taxonomie des types : actor|investor|supervisor|concept (zéro ad-hoc)
- **2026-06-21 08:31** · `6c8fd00` — Visu glossaire « ancrée » : surligne les termes DANS le texte réel de l'article
- **2026-06-21 08:35** · `7b0e235` — Visu glossaire : les 41 textes, 4 catégories surlignées, légende + sommaire
- **2026-06-21 15:16** · `c9f8d0d` — Outillage .claude : hook ruff auto + commandes /gate, /regen-glossaire, /lms
- **2026-06-21 15:17** · `f9f115f` — Glossaire L1 : corpus consolidé + typologie acteur/produit/activité + 3 textes récupérés
- **2026-06-21 15:20** · `20b4c2b` — .claude : dossiers dédiés hooks/ et skills/
- **2026-06-21 15:46** · `e89eb00` — Glossaire : graphe de renvois inter-textes restauré (extraction auto, fidèle)
- **2026-06-25 08:58** · `d1b4ff2` — Extraction : règles générales (acteur substantiel, verbe ancré, clause permissive) + dédup déterministe
- **2026-06-25 18:31** · `5518d04` — Nettoyage : suppression de code mort / config spéculative (audit + vérif adverse)
- **2026-06-27 04:03** · `bfb6b48` — Nettoyage : suppression de l'export GraphML inutilisé + commentaires/refs superflus
- **2026-06-27 04:33** · `c8f58cc` — Suppression de l'acquisition réseau + arborescence data/ explicite
- **2026-06-27 06:10** · `d48737f` — gitignore : dossier livrable local livraison_cedric/ (artefacts à envoyer, non versionnés)
- **2026-06-27 07:55** · `359beb9` — docs : MAJ après retrait de l'acquisition (L1_PERIMETER → scan du cache, plus d'auto-fetch/RDF)
- **2026-06-27 08:02** · `f04f839` — docs(README) : corrige les avertissements markdownlint (MD031/032/040/060)
- **2026-06-27 09:57** · `003de0e` — Corpus offline : recherche du HTML par langue (indépendant du CELEX) + AIFMD L1 complet
- **2026-06-27 15:02** · `7de3e81` — gitignore : exclut les dumps SQL (lalande_corpus_*.gz) du versionnement
- **2026-06-27 15:40** · `f730f94` — feat(dump): pont DB PostgreSQL → corpus (lecteur du dump → NormativeUnit)
- **2026-06-27 15:42** · `c74f5b9` — feat: préfixe d'obligation_id dérivé de l'acte (généralise le multi-texte L1+L2)
- **2026-07-04 04:06** · `aadbb54` (dump-extraction) — feat(journal): journal d'avancement (hook post-commit + skill /journal) _[6 files changed, 163 insertions(+)]_
- **2026-07-04 04:14** · `c9de574` (dump-extraction) — docs(journal): première entrée d'avancement (rattrapage 21/06→04/07) _[3 files changed, 40 insertions(+), 8 deletions(-)]_
- **2026-07-04 04:41** · `bedbeea` (dump-extraction) — chore: ignore data/_archive/ (snapshots de rollback locaux) _[1 file changed, 1 insertion(+)]_
- **2026-07-04 04:46** · `7e94e02` (dump-extraction) — refactor: DB = source unique du corpus, retrait du cluster hors-ligne _[8 files changed, 23 insertions(+), 169 deletions(-)]_
- **2026-07-04 04:57** · `40df941` (dump-extraction) — feat(db_corpus): découpage au seuil des articles longs (fix Art. 21 & co) _[3 files changed, 109 insertions(+), 23 deletions(-)]_
- **2026-07-04 09:53** · `f9ba1e5` (dump-extraction) — feat(db): schéma relationnel normalisé provisoire (regindex) + mapping _[4 files changed, 103 insertions(+)]_
