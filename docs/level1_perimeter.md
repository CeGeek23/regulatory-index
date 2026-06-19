# Périmètre « niveau 1 » — textes, articles de définitions, versions à jour

> Document de cadrage répondant à la demande du client : *« intégralité des textes de
> niveau 1, pour récupérer l'article de définition de chaque texte ; faire une liste de
> tous les termes ; liste minimale »* — sur les **textes les plus à jour**.

## 1. Méthode

Pour chaque texte de niveau 1 :
1. récupérer son **sommaire** (`regindex sommaire` / `glossary.build_toc`) → localise l'article de définitions ;
2. moissonner son **article de définitions** (`regindex glossary` / `glossary.harvest_glossary`) →
   liste de tous les termes (acteurs + concepts), bilingue EN/FR, avec base légale et renvois ;
3. réconcilier les termes communs entre textes (un concept = une entrée — la « liste minimale »).

Statut actuel : **les 15 textes du périmètre sont moissonnés** — **329 termes distincts,
84 acteurs isolés** (sortie : `data/exports/glossary_L1_minimal.csv` + `glossary_L1_actors.csv` ;
détail et limites dans `docs/approche_glossaire.md`). Génération de bout en bout :
`uv run python scripts/build_l1_glossary.py` (auto-fetch via Cellar).

## 2. Le point « textes les plus à jour » ⚠️

Le glossaire ci-joint est construit sur le **texte d'origine 2011/61**. Deux écarts à corriger
pour viser le droit applicable aujourd'hui :

**a) AIFMD a été modifiée par AIFMD II** — Directive (UE) 2024/927 (application **16 avril 2026**).
AIFMD II **ajoute/retouche des définitions** à l'article 4 (notamment autour de l'octroi de
prêts : *loan origination*, *loan-originating AIF*, *shareholder loan*…). → il faut rejouer le
moissonnage sur la **version consolidée** `02011L0061-2024xxxx`, pas sur `32011L0061`.

**b) Les définitions d'AIFMD renvoient à des textes en partie ABROGÉS.** C'est le piège central :
prises « à jour », ces définitions pointent vers des textes remplacés. Table des renvois trouvés
dans l'article 4 (et 6) et leur statut actuel :

| Renvoi dans AIFMD (texte d'origine) | Objet | Statut aujourd'hui |
|---|---|---|
| Directive 2004/39/CE (MiFID I) | instrument financier (n), investisseur professionnel (ag) | **Abrogée** → Directive 2014/65/UE (MiFID II) + Règl. 600/2014 (MiFIR) |
| Directive 2006/48/CE (CRD) | capital initial (s), fonds propres (ad) | **Abrogée** → Directive 2013/36/UE (CRD IV) + Règl. 575/2013 (CRR) |
| Directive 2006/49/CE (adéquation des fonds propres) | fonds propres (renvoi §2) | **Abrogée** → CRD IV (Dir. 2013/36/UE) + CRR (Règl. 575/2013). NB : IFR/IFD (2019) n'ont PAS abrogé 2006/49 (déjà disparue depuis 2014) — pour le capital initial / fonds propres d'AIFMD, les références vivantes sont CRR + CRD IV |
| Directive 83/349/CEE (7e dir. — comptes consolidés) | contrôle (i), entreprise mère (ae), filiale (ak), liens étroits (e) | **Abrogée** → Directive 2013/34/UE (directive comptable) |
| Directive 2004/109/CE (Transparence) | émetteur (t), participation qualifiée (ah) | En vigueur (modifiée par 2013/50/UE) |
| Directive 2002/14/CE (information des travailleurs) | représentants des travailleurs (ai) | En vigueur |
| Directive 2003/41/CE (IORP) | gestion de portefeuille (art. 6(4)(a)) | **Abrogée** → Directive (UE) 2016/2341 (IORP II) |
| Directive 2009/65/CE (OPCVM) | AIF (a), OPCVM (ao) | En vigueur (modifiée) |
| Règlement (UE) n° 1095/2010 (AEMF) | normes techniques (§3-4) | En vigueur |
| Règlement (CE) n° 24/2009 (BCE) | structures de titrisation ad hoc (an) | **Abrogé** → Règl. (UE) n° 1075/2013 (BCE/2013/40), applicable 1er janv. 2015 |

➡️ **Conséquence pour le glossaire** : chaque renvoi doit être re-pointé vers le texte en
vigueur (colonne de droite). C'est exactement le travail de réconciliation « liste minimale ».

## 3. Univers des textes de niveau 1 à confirmer avec le client

Au-delà d'AIFMD, le périmètre « niveau 1 » gestion d'actifs (article de définitions de chacun) :

| Texte | CELEX | Art. définitions | Remarque |
|---|---|---|---|
| AIFMD | 32011L0061 (cons. 2024/927) | **Art. 4** | ✅ moissonné |
| OPCVM (UCITS) | 32009L0065 | Art. 2 | renvoyé par AIFMD (a, ao) |
| MiFID II | 32014L0065 | Art. 4 | remplace MiFID I, renvoyé par AIFMD (n, ag) |
| MiFIR | 32014R0600 | Art. 2 | jumeau règlement de MiFID II |
| CRR | 32013R0575 | Art. 4 | remplace 2006/48 pour fonds propres |
| CRD IV | 32013L0036 | Art. 3 | remplace 2006/48 |
| Directive comptable | 32013L0034 | Art. 2 | remplace 83/349 (contrôle, filiale…) |
| PRIIPs | 32014R1286 | Art. 4 | information investisseurs |
| SFDR | 32019R2088 | Art. 2 | durabilité (faux-amis FR fréquents) |
| ELTIF | 32015R0760 | Art. 2 | fonds long terme |
| Règl. fonds monétaires (MMFR) | 32017R1131 | Art. 2 | |
| EuVECA / EuSEF | 32013R0345 / 32013R0346 | Art. 3 | capital-risque / entrepreneuriat social |
| Taxonomie | 32020R0852 | Art. 2 | durabilité, lié à SFDR (à inclure pour cohérence) |
| EMIR | 32012R0648 | Art. 2 | dérivés / contreparties / compensation (gestion d'actifs) |
| Distribution transfrontalière (Règl.) | 32019R1156 | Art. 4 | commercialisation/pré-commercialisation FIA & OPCVM |
| Distribution transfrontalière (Dir.) | 32019L1160 | — | jumeau directive du Règl. 2019/1156 |

**Statut** : **moissonnés** — AIFMD L1/L2, UCITS, MiFID II, MiFIR, CRR, CRD IV, directive
comptable, PRIIPs, SFDR, ELTIF, MMFR, Taxonomie, EMIR, distribution transfrontalière (règlement
2019/1156). **Non encore traités** : EuVECA / EuSEF (345/346) et la directive distribution
2019/1160 — à ajouter si le client veut les inclure.

## 4. Récupération des textes & ce qui reste

- **Récupération automatique** : le HTML est tiré de l'**API Cellar** de l'Office des publications
  (`eurlex_fetcher`), qui contourne le WAF anti-bot d'EUR-Lex (le rendu `legal-content` renvoie
  HTTP 202). `scripts/build_l1_glossary.py` récupère le périmètre L1 manquant tout seul.
- **Versions consolidées** : `eurlex_fetcher.latest_consolidated_celex` résout le CELEX consolidé
  le plus récent via les métadonnées RDF (ex. AIFMD → `02011L0061-20260416`, incluant AIFMD II).
  Le glossaire actuel est bâti sur les textes **d'origine** ; passer au consolidé = re-fetch +
  **re-classification** (jeux de termes différents).
- **Reste à faire** : relire la classification acteur/concept générée pour les 14 textes
  non-AIFMD ; traiter les faux-amis L3 (AMF/ACPR).
