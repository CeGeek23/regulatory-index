# Note méthodologique — Construire un index réglementaire à partir des articles de définition

*Document non technique, à destination d'un expert de la réglementation financière. Il décrit
l'approche et l'état d'avancement, en termes métier — pas d'informatique.*

---

## 1. L'idée directrice

Avant de cartographier « qui doit faire quoi », on construit d'abord le **socle de vocabulaire** :
la liste de **tous les termes définis** par les textes, tirée directement de leurs **articles de
définition**. Chaque terme défini devient un **objet identifié** (avec son sens juridique exact),
ce qui permet ensuite de relier proprement les obligations entre elles et entre niveaux.

En clair : on commence par le dictionnaire, pas par les articles de fond.

## 2. Pourquoi partir des articles de définition

- Ce sont le **socle juridique** : un terme y est défini une fois, précisément, puis réutilisé
  partout dans le texte. Sa définition fait foi.
- Ils définissent **à la fois des acteurs** (le gestionnaire, le dépositaire, l'autorité
  compétente, l'investisseur…) **et des concepts** (effet de levier, participation qualifiée,
  liens étroits, commercialisation…).
- Les capturer comme objets normalisés, c'est se donner le moyen de les **rattacher et relier**
  ensuite — c'est exactement le besoin exprimé : « les identifier comme objets pour mieux les lier ».

## 3. Ce qu'on produit pour chaque texte

Pour chaque acte, deux livrables :

1. **Le sommaire** (table des matières chapitres / sections / articles) — qui sert à **localiser
   l'article de définitions** et à cartographier la structure du texte.
2. **Le glossaire des termes définis**, tiré de cet article, avec pour **chaque terme** :
   - le **libellé EN et FR** (versions officielles, pas une traduction maison) ;
   - sa **base légale précise** (l'article et le point exact, ex. « Art. 4(1)(b) ») ;
   - sa **catégorie** : acteur / concept / fonds / autorité… ;
   - sa **définition reprise mot pour mot** ;
   - les **renvois** vers d'autres textes que la définition importe.

## 4. Une règle claire : extraire fidèlement, enrichir en relecture

Deux étapes nettement séparées, pour qu'il n'y ait jamais d'ambiguïté sur ce qui vient du texte
et ce qui vient de notre analyse :

- **Extraction = automatique et fidèle.** Le terme et sa définition sont **repris à la lettre**
  du texte officiel. Aucune reformulation, aucune interprétation. C'est mécanique et vérifiable.
- **Catégorisation (acteur/concept) et renvois = relus.** Cette couche d'analyse est **validée
  par une relecture métier**. **Rien n'est deviné** : un terme non encore relu reste explicitement
  marqué « à classer » plutôt que mal étiqueté.

C'est ce double principe qui rend le résultat **fiable et défendable** devant un régulateur.

## 5. La « liste minimale »

Un même concept — par exemple **« investisseur professionnel »** — est défini dans un texte et
**repris par renvoi** dans plusieurs autres. Plutôt que de le compter dix fois, on le ramène à
**une seule entrée**, en gardant la **trace de tous les textes** où il apparaît.

C'est la **liste minimale** : le vocabulaire de référence, dédoublonné — un terme = une ligne.

## 6. Isoler les acteurs

Le besoin central exprimé : sortir **séparément la liste de tous les acteurs** (gestionnaire,
dépositaire, autorités compétentes, courtier principal, investisseurs, représentant légal,
fonctions de direction…), distincts des concepts. C'est fait : le glossaire produit **deux blocs**,
« Acteurs » et « Concepts/objets ».

## 7. Le piège des « textes les plus à jour »

Point sensible identifié et documenté : les définitions **renvoient à d'autres textes**, et beaucoup
de ces renvois pointent vers des directives **aujourd'hui abrogées** (MiFID I, l'ancienne directive
bancaire, la 7ᵉ directive comptable…). Travailler « sur les textes les plus à jour » suppose donc de
**re-pointer chaque renvoi vers le texte en vigueur** (MiFID II, CRR/CRD IV, directive comptable de
2013, etc.). Cette table de correspondance est établie.

À noter aussi : la directive AIFMD elle-même a été **modifiée (AIFMD II)** — la version consolidée
ajoute des définitions récentes (octroi de prêts…), à intégrer pour viser le droit applicable.

## 8. Multilingue et faux-amis

EN et FR **officiels** sont récupérés ensemble (pas de traduction approximative). Pour le **niveau 3**
(doctrine AMF / ACPR), certains termes français sont des **faux-amis** des termes UE : ils doivent
être **identifiés à part** pour ne pas être fusionnés à tort avec leur quasi-homonyme européen.

## 9. En parallèle : le bloc-pilote « obligations » (articles 6, 7, 8)

Au-delà des définitions, on a amorcé l'**extraction des obligations** sur le **chapitre Agrément**
(articles 6, 7, 8) — pour confronter une **version « métier »** (la tienne) et une **version
« machine »**, et caler la maille de lecture.

## 10. Où on en est, concrètement

**Périmètre « tout le niveau 1 services financiers » — ~40 textes**, leur article de définitions
moissonné automatiquement (API Cellar de l'Office des publications). Couvre : fonds (AIFMD L1/L2,
UCITS, ELTIF, MMFR, EuVECA, EuSEF), marchés (MiFID II, MiFIR, MAR, MAD II, Prospectus, CSDR,
Short Selling, Benchmarks, Securitisation, SFTR, EMIR, Transparence, CRA), banque/résolution
(CRR, CRD IV, BRRD, SRMR, DGSD), assurance (Solvabilité II, IDD), paiements (DSP2, monnaie
électronique), durabilité (SFDR, Taxonomie), numérique (MiCA, DORA), financement participatif
(ECSP), retraite (PEPP, IORP II), LCB-FT (LBC-FT), comptable, AEMF/ESMA.

**Résultat consolidé :** **1 271 termes définis → 782 termes distincts** (liste minimale
dédoublonnée) → **214 acteurs isolés**, dont **38 partagés par ≥3 textes** (ex. « credit
institution », « competent authority »). La dédup relie le même terme entre actes et garde la
trace de toutes ses bases légales.

**Statut de la classification acteur/concept** : AIFMD L1/L2 sont **relus à la main** ; les
**~38 autres textes sont classés automatiquement** (extraction fidèle, classification générée et
**marquée « à RELIRE »** dans chaque override). Couverture FR : 52/214 acteurs (les textes ajoutés
en masse n'ont été récupérés qu'en EN).

**Boucle glossaire → vocabulaire (le point clé)** : les termes du glossaire sont désormais **versés
dans le vocabulaire de référence du projet** — **228 acteurs** (`actors.yaml`) et **614 concepts/
objets** (`objects.yaml`). Autrement dit, les objets identifiés dans les définitions **alimentent
maintenant l'extraction d'obligations** (reconnaissance des termes + normalisation), exactement la
finalité « les identifier comme objets pour mieux les lier ». Ces entrées sont versées
automatiquement et **marquées « à relire »**.

**Méthode validée comme réplicable** : un seul code traite les définitions en (a)(b)(c) ou
(1)(2)(3), plusieurs styles de guillemets, format de base ou consolidé, EN seul ou EN+FR.

## 11. Ce qui reste à faire

1. **Relire la classification acteur/concept** : pour AIFMD elle est faite à la main ; pour les
   **~38 autres textes** elle est **générée automatiquement et marquée « à relire »** (validation
   métier). C'est aussi ce qui conditionne la qualité du vocabulaire alimenté (voir §10).
2. **Élaguer le vocabulaire injecté à l'extraction** : 228 acteurs + 614 objets, c'est beaucoup
   pour un petit modèle local (risque de dilution du prompt) — à arbitrer après relecture.
3. **Basculer sur les versions consolidées** (à jour) — la capacité est en place (résolution
   automatique du dernier CELEX consolidé), à généraliser à tout le périmètre.
4. **Réconcilier les renvois abrogés** vers les textes en vigueur, et **traiter les faux-amis L3**
   (doctrine AMF/ACPR), non encore intégrés.
5. **Compléter le bilingue** : le FR n'est récupéré que pour une partie des textes pour l'instant.

---

*En une phrase : on transforme les articles de définition des textes en un **dictionnaire structuré,
bilingue, dédoublonné, avec les acteurs isolés** — fidèle au texte pour l'extraction, relu pour
l'analyse — afin de servir de socle au rattachement des obligations.*
