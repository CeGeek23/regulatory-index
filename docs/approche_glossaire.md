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

- Ils constituent le **socle terminologique** : un terme y est défini une fois, précisément, puis
  réutilisé partout dans le texte. Sa définition fait foi.
- Ils définissent **à la fois des acteurs** (le gestionnaire, le dépositaire, l'autorité
  compétente, l'investisseur…) **et des produits et activités** (l'effet de levier, la
  participation qualifiée, les liens étroits — autant de produits ; la commercialisation —
  une activité…).
- Les capturer comme objets normalisés, c'est se donner le moyen de les **rattacher et relier**
  ensuite — c'est exactement le besoin exprimé : « les identifier comme objets pour mieux les lier ».

## 3. Ce qu'on produit pour chaque texte

Pour chaque acte, deux livrables :

1. **Le sommaire** (table des matières chapitres / sections / articles) — qui sert à **localiser
   l'article de définitions** et à cartographier la structure du texte.
2. **Le glossaire des termes définis**, tiré de cet article, avec pour **chaque terme** :
   - le **libellé EN et FR** (versions officielles, pas une traduction maison) ;
   - sa **base légale précise** (l'article et le point exact, ex. « Art. 4(1)(b) ») ;
   - sa **catégorie** (typologie du client, tirée des articles de définition) : **acteur**, **produit** ou **activité** ;
   - sa **définition reprise mot pour mot** ;
   - les **renvois** vers d'autres textes que la définition importe.

## 4. Une règle claire : extraire fidèlement, enrichir en relecture

Deux étapes nettement séparées, pour qu'il n'y ait jamais d'ambiguïté sur ce qui vient du texte
et ce qui vient de notre analyse :

- **Extraction = automatique et fidèle.** Le terme et sa définition sont **repris à la lettre**
  du texte officiel. Aucune reformulation, aucune interprétation. C'est mécanique et vérifiable.
- **Catégorisation (acteur/produit/activité) = proposée puis relue.** Cette couche d'analyse est
  produite **automatiquement et de façon reproductible**, puis systématiquement **marquée « à
  relire »** : c'est une **proposition** que la relecture métier valide ou corrige. **Rien n'est
  présenté comme acquis** — le statut « à relire » est explicite sur chaque terme.

C'est ce double principe qui rend le résultat **fiable et défendable** devant un régulateur.

## 5. La « liste minimale »

Un même terme — par exemple **« investisseur professionnel »** — est défini dans un texte et
**repris par renvoi** dans plusieurs autres. Plutôt que de le compter dix fois, on le ramène à
**une seule entrée**, en gardant la **trace de tous les textes** où il apparaît.

C'est la **liste minimale** : le vocabulaire de référence, dédoublonné — un terme = une ligne.

## 6. Isoler les acteurs

Le besoin central exprimé : sortir **séparément la liste de tous les acteurs** (gestionnaire,
dépositaire, autorités compétentes, courtier principal, investisseurs, représentant légal,
fonctions de direction…), distincts des produits et activités. C'est fait : le glossaire produit
**deux blocs**, « Acteurs » d'un côté, « Produits / activités » de l'autre.

## 7. Le piège des « textes les plus à jour »

Point sensible identifié et documenté : les définitions **renvoient à d'autres textes**, et beaucoup
de ces renvois pointent vers des directives **aujourd'hui abrogées** (MiFID I, l'ancienne directive
bancaire, la 7ᵉ directive comptable…). Travailler « sur les textes les plus à jour » suppose donc de
**re-pointer chaque renvoi vers le texte en vigueur** (MiFID II, CRR/CRD, directive comptable de
2013, etc.). Cette table de correspondance est établie.

C'est désormais **acté** : le glossaire est construit sur les **versions consolidées** (droit le plus
à jour) chaque fois qu'elles existent. La directive AIFMD elle-même a été **modifiée (AIFMD II,
directive (UE) 2024/927, applicable le 16 avril 2026)** : la version consolidée ajoute des définitions
récentes — *octroi de prêts*, *FIA octroyant des prêts*, *prêt d'actionnaire*, *FIA à effet de
levier* — désormais **intégrées** (AIFMD passe ainsi de 41 à 48 termes définis).

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
récupéré automatiquement depuis la **source officielle de l'UE** (EUR-Lex / Office des
publications). Couvre : fonds (AIFMD L1/L2,
UCITS, ELTIF, MMFR, EuVECA, EuSEF), marchés (MiFID II, MiFIR, MAR, MAD II, Prospectus, CSDR,
Short Selling, Benchmarks, Securitisation, SFTR, EMIR, Transparence, CRA), banque/résolution
(CRR, CRD IV, BRRD, SRMR, DGSD), assurance (Solvabilité II, IDD), paiements (DSP2, monnaie
électronique), durabilité (SFDR, Taxonomie), numérique (MiCA, DORA), financement participatif
(ECSP), retraite (PEPP, IORP II), LCB-FT, comptable, AEMF/ESMA.

**Résultat consolidé :** **1 459 termes définis bruts → 893 termes distincts** (liste minimale
dédoublonnée) → **303 acteurs isolés**, dont une part partagée par plusieurs textes (ex. « credit
institution », « competent authority »). La dédup relie le même terme entre actes et garde la
trace de toutes ses bases légales.

**Statut de la classification acteur/produit/activité** : elle est, pour les **41 textes**, **produite
automatiquement et de façon reproductible** : pour chaque terme, le système propose « acteur »,
« produit » ou « activité », et **redonne exactement le même résultat** à chaque exécution. Un même
terme reçoit **le même type dans tout le corpus** (cohérence d'un texte à l'autre). Les **14 termes
vraiment ambigus** — le terme penche des deux côtés selon le texte — sont tranchés **automatiquement**
par leur **définition de référence** (la plus substantielle, pas un simple renvoi) : une règle
générale, sans liste de décisions à tenir. L'extraction du terme et de sa définition reste **fidèle
au texte** ; les classifications restent **marquées « à relire »** (validation métier — le décompte
d'acteurs, encore un peu haut, sera resserré à cette étape, notamment sur les définitions par renvoi).

**Bilingue** : les **42/42 textes** sont désormais récupérés en **EN + FR** (versions officielles),
une part des acteurs du vocabulaire portant déjà un libellé **FR** distinct.

**Le glossaire alimente le vocabulaire de référence (le point clé)** : les **303 acteurs** (et les
produits/activités) tirés des définitions sont **versés dans le vocabulaire de référence du projet**.
Ajoutés au vocabulaire déjà présent, ils le portent à **319 acteurs** et **626 objets** (produits +
activités) au total — ce vocabulaire sert ensuite à **reconnaître et normaliser** ces termes lors de
la lecture des obligations. *(À ne pas confondre : **303** = acteurs distincts issus des définitions ;
**319** = taille du vocabulaire de référence après ajout au fonds existant.)* C'est exactement la finalité
« les identifier comme objets pour mieux les lier ». Cette alimentation est **automatique et
reproductible** ; les entrées sont **marquées « à relire »**.

**Méthode réplicable de bout en bout** : un même traitement gère les définitions numérotées
(1)(2)(3) ou en lettres (a)(b)(c), les différents styles de guillemets, le texte d'origine ou
consolidé, l'anglais seul ou anglais + français. **Toute la chaîne se rejoue à l'identique** sur
n'importe quel acte — c'est ce qui la rend applicable à une base entière.

## 11. Ce qui reste à faire

1. **Valider la classification acteur/produit/activité** (le seul vrai travail manuel restant) : elle
   est produite automatiquement et harmonisée entre textes (en cas d'ambiguïté, on tranche par la
   **définition de référence** du terme — règle générale, sans liste à tenir), et **marquée « à
   relire »**. Reste à confirmer ces propositions en relecture métier — en priorité les définitions
   **par renvoi** (« X au sens de l'article Y… »), sans contenu sémantique propre, plus délicates à classer.
2. **Élaguer le vocabulaire** : 319 acteurs + 626 objets (produits/activités), c'est beaucoup à
   présenter au moteur (risque de dilution). Les doublons purement **typographiques** (pluriel, tiret, trait d'union)
   fusionnent désormais **d'office** à la déduplication (règle générale, aucune liste). Reste à
   arbitrer d'éventuels regroupements de fond — en **gardant séparés les termes juridiquement
   distincts** (un « X » et un « X mère » ne sont pas le même terme).
3. ~~**Basculer sur les versions consolidées**~~ — **fait** : le glossaire est désormais bâti sur les
   versions **consolidées** (droit le plus à jour) partout où l'UE en publie une ; seuls quelques textes
   sans consolidé officiel restent sur le texte d'origine.
4. **Réconcilier les renvois abrogés** vers les textes en vigueur, et **traiter les faux-amis L3**
   (doctrine AMF/ACPR), non encore intégrés.
5. ~~**Compléter le bilingue**~~ — **fait** : les 42/42 textes sont récupérés en EN + FR.

---

*En une phrase : on transforme les articles de définition des textes en un **dictionnaire structuré,
bilingue, dédoublonné, avec les acteurs isolés** — fidèle au texte pour l'extraction, relu pour
l'analyse — afin de servir de socle au rattachement des obligations.*
