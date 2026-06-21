# Présentation — Un index de la réglementation financière de l'UE, à partir des articles de définition

*Fil conducteur pour présenter le projet. Écrit pour un public **métier** (réglementation
financière), **sans informatique**. Il relie, à chaque étape, **ce qui a été fait** à **la logique
de la réglementation**. Détails de portée dans [niveau1_cartographie.md](niveau1_cartographie.md),
méthode dans [approche_glossaire.md](approche_glossaire.md).*

---

## 0. Le problème, en une phrase

La réglementation financière de l'UE, c'est une **quarantaine de textes** (AIFMD, MiFID II, CRR,
EMIR, Solvabilité II…) qui posent des **centaines d'obligations** et qui **se renvoient sans cesse
les uns aux autres**. Pour s'y retrouver — et relier les obligations entre elles — il faut d'abord
un **langage commun** : savoir **qui** est concerné et **de quoi** on parle, terme par terme.

> L'idée du projet : **commencer par le dictionnaire**, pas par les articles de fond.

---

## 1. Comment la réglementation est structurée (le cadre)

Le droit financier de l'UE est **empilé** selon le processus **Lamfalussy** :

| Niveau | Nature | Exemples | Notre périmètre |
|---|---|---|---|
| **L1** | Le socle : directives & règlements | AIFMD, MiFID II, CRR, EMIR | **✅ tout le niveau 1** |
| **L2** | Précise le L1 (actes délégués) | AIFMD délégué (231/2013) | ✅ un acte pilote |
| **L3** | Doctrine, orientations (ESMA, AMF, ACPR) | Guidelines, positions | ⏳ pas encore |
| **L4** | Contrôle & sanction | Procédures d'infraction | — |

**On travaille au niveau 1 — le socle.** C'est là que les termes sont **définis pour la première
fois** ; tout le reste (L2, L3) s'y rattache. Bien traiter le L1, c'est poser les fondations.

---

## 2. Pourquoi partir des **articles de définition**

Chaque texte UE commence par un **article de définitions** (ex. AIFMD **article 4**). C'est le
**socle terminologique** du texte : un terme y est défini **une seule fois, précisément**, puis
réutilisé partout. **Sa définition fait foi.**

Ces articles définissent **deux choses** qu'on sépare volontairement :

- **Les acteurs** — *qui* est régulé ou agit : le gestionnaire, le dépositaire, l'**autorité
  compétente**, l'investisseur, le courtier principal (*prime broker*)…
- **Les concepts** — *de quoi* on parle : l'effet de levier, la participation qualifiée, les liens
  étroits, la commercialisation, un instrument financier…

> **Pourquoi c'est le bon point de départ** : une obligation, c'est toujours « **un acteur** doit
> faire quelque chose **à propos d'un concept** ». Si on a la liste propre des acteurs et des
> concepts, on peut ensuite **rattacher et relier** toutes les obligations — exactement le besoin
> exprimé : *« les identifier comme objets pour mieux les lier »*.

---

## 3. Ce que ça donne : une **bibliothèque** navigable

Au lieu d'une pile de 40 textes, on obtient une bibliothèque organisée :

| Bibliothèque | Notre index |
|---|---|
| Les rayons (Histoire, Sciences…) | Les **8 domaines métier** (fonds, marchés, banque, assurance, paiements, durabilité, numérique, transverse) |
| Un livre | Un **texte** (AIFMD, MiFID II…) |
| Le glossaire en fin de livre | L'**article de définitions** du texte |
| Une entrée du glossaire | Un **terme défini** (un acteur ou un concept) |
| « voir aussi p. X » | Un **renvoi** vers un autre texte |

**En chiffres réels :**

| | |
|---|---:|
| Textes de niveau 1 traités | **~40** |
| Termes définis récupérés (bruts) | **1 271** |
| Termes **distincts** après dédoublonnage (la « liste minimale ») | **782** |
| **Acteurs** isolés des concepts | **207** |
| Langues officielles (anglais + français) | **42/42 textes** |

> Beaucoup d'acteurs sont **partagés** par plusieurs textes (ex. *établissement de crédit*,
> *autorité compétente*). On les ramène à **une seule entrée** en gardant la **trace de tous les
> textes** où ils apparaissent : c'est la « liste minimale ».

---

## 4. La rigueur : pourquoi c'est **défendable devant un régulateur**

Deux étapes **nettement séparées**, pour qu'on sache toujours ce qui vient du **texte** et ce qui
vient de **notre analyse** :

1. **Extraction = fidèle au texte.** Le terme et sa définition sont **repris mot pour mot** du
   texte officiel (EN **et** FR officiels, pas une traduction maison), avec leur **base légale
   exacte** (ex. « Art. 4(1)(b) »). Aucune reformulation. **Vérifiable ligne à ligne.**
2. **Classification (acteur / concept) = analyse, relue.** **Rien n'est deviné** : un terme non
   encore validé est **marqué « à relire »** plutôt que mal étiqueté.

**Les pièges identifiés et documentés** (un expert les attend) :

- **« Textes à jour »** : les définitions **renvoient à des textes parfois abrogés** (MiFID I,
  ancienne directive bancaire, 7ᵉ directive comptable…). La table de correspondance vers les textes
  en vigueur (MiFID II, CRR/CRD, directive comptable 2013…) est **établie**.
- **AIFMD a été modifiée (AIFMD II)** — la version consolidée ajoute des définitions récentes
  (octroi de prêts…), à intégrer pour viser le droit applicable.
- **Faux-amis FR ↔ UE** au niveau 3 (doctrine AMF/ACPR) : à isoler pour ne pas les fusionner à tort.

---

## 5. Le vrai différenciateur : ce n'est pas un travail manuel, c'est une **chaîne réplicable**

C'est le point à marteler. Le travail n'a **pas** été fait « à la main sur AIFMD ». C'est une
**chaîne** qui se rejoue sur **n'importe quel acte** — donc sur **toute une base de textes** :

```
   un texte officiel
        │  on lit sa structure → on localise l'article de définitions
        ▼
   tous les termes définis (acteurs + concepts), bilingues, avec base légale
        │  on dédoublonne entre textes → liste minimale
        ▼
   on alimente le « vocabulaire de référence » du projet
        │  qui sert ensuite à reconnaître et relier les obligations
        ▼
   un index réglementaire vivant
```

**Et tout est reproductible** : relancer la chaîne sur les mêmes textes redonne **exactement le
même résultat**. Ajouter un nouvel acte = **une ligne**, et tout se reconstruit pareil. La
**décision humaine** (valider qu'un terme est un acteur ou un concept) est **consignée une fois pour
toutes** dans un fichier dédié, et **ré-appliquée automatiquement** à chaque reconstruction.

> Concrètement, pour la présentation : *« je ne livre pas un glossaire d'AIFMD, je livre la **chaîne**
> qui produit le glossaire de tout le niveau 1 — et qui le reproduira à l'identique demain, sur la
> base entière. »*

---

## 6. Honnêteté : ce qui est **solide** vs ce qui **attend ta validation**

| | État |
|---|---|
| Extraction des termes + définitions (mot pour mot, bilingue, base légale) | ✅ **solide, vérifiable** |
| Liste minimale + acteurs isolés | ✅ **fait** |
| Caractère **reproductible / réplicable** de toute la chaîne | ✅ **vérifié** |
| Classification **acteur / concept** | ⚠️ **proposée automatiquement, « à relire »** — à confirmer par un expert |
| 14 termes vraiment ambigus (le même terme penche des deux côtés selon le texte) | ⚠️ **décisions proposées, à confirmer** (ex. *issuer* → acteur, *deposit* → concept) |
| Versions **consolidées** (droit le plus à jour) | ⏳ capacité prête — **choix de méthode** à décider |
| Niveau 3 (doctrine AMF/ACPR) et faux-amis | ⏳ pas encore intégré |

> Message clé : **la mécanique est faite et fiable ; ce qui reste est du ressort de l'expert
> métier** (valider les classifications), pas du travail technique en suspens.

---

## 7. En une phrase

> On transforme les **articles de définition** des ~40 textes de niveau 1 en un **dictionnaire
> structuré, bilingue, dédoublonné, avec les acteurs isolés des concepts** — **fidèle au texte**
> pour l'extraction, **relu** pour l'analyse — afin de servir de **socle** au rattachement des
> obligations, et **reproductible** sur toute une base d'actes.

*Pour la structure détaillée et les 40 textes domaine par domaine : [niveau1_cartographie.md](niveau1_cartographie.md).
Pour la méthode pas à pas : [approche_glossaire.md](approche_glossaire.md). Pour le périmètre et les
renvois abrogés : [level1_perimeter.md](level1_perimeter.md).*
