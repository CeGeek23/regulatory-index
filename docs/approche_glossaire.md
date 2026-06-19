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

**Périmètre niveau 1 traité — 15 textes**, leur article de définitions moissonné automatiquement
(récupérés via l'API officielle de l'Office des publications de l'UE) :

- **AIFMD** (2011/61, art. 4) et son **niveau 2** (231/2013, art. 1) — vérifiés (41/41 termes pour l'art. 4) ;
- **OPCVM/UCITS** (art. 2), **MiFID II** (art. 4), **MiFIR** (art. 2), **CRR** (art. 4), **CRD IV** (art. 3),
  **directive comptable** (art. 2), **PRIIPs** (art. 4), **SFDR** (art. 2), **ELTIF** (art. 2),
  **fonds monétaires/MMFR** (art. 2), **EMIR** (art. 2), **distribution transfrontalière** (art. 4),
  **Taxonomie** (art. 2).

**Résultat consolidé :** **511 termes définis → 329 termes distincts** (liste minimale dédoublonnée)
→ **84 acteurs isolés**, dont **39 partagés** entre plusieurs textes (ex. « credit institution »
dans 5 textes, « competent authority » dans 5 textes). La dédup relie automatiquement le même
terme entre actes et garde la trace de toutes ses bases légales.

**Méthode validée comme réplicable** : un seul code traite les définitions qu'elles soient en
(a)(b)(c) ou en (1)(2)(3), avec différents styles de guillemets, en EN seul ou EN+FR.

## 11. Ce qui reste à faire

1. **Relire la classification acteur/concept** : pour AIFMD elle est faite à la main ; pour les
   14 autres textes elle est **générée automatiquement et marquée « à relire »** (validation métier).
2. **Basculer sur les versions consolidées** (à jour) plutôt que les textes d'origine.
3. **Réconcilier les renvois abrogés** vers les textes en vigueur, et **traiter les faux-amis L3**
   (doctrine AMF/ACPR), non encore intégrés.
4. **Compléter le bilingue** : le FR n'est récupéré que pour une partie des textes pour l'instant.

---

*En une phrase : on transforme les articles de définition des textes en un **dictionnaire structuré,
bilingue, dédoublonné, avec les acteurs isolés** — fidèle au texte pour l'extraction, relu pour
l'analyse — afin de servir de socle au rattachement des obligations.*
