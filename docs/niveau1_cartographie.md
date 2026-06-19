# Cartographie du « niveau 1 » — comprendre la portée réelle du périmètre

*Document de référence à rouvrir pour se rappeler **ce que couvre le projet**, **comment c'est
organisé**, et **où le code agit**. Tous les chiffres viennent des données réelles du projet
(HTML EUR-Lex en cache dans `data/raw/`, moisson via `scripts/build_l1_glossary.py`).*

---

## 1. Le cadre : les 4 niveaux Lamfalussy

La réglementation financière de l'UE est empilée selon le **processus Lamfalussy**. C'est l'axe
vertical qui dit *quel type de norme* on lit.

| Niveau | Nature | Qui produit | Force juridique | Exemples |
|---|---|---|---|---|
| **L1** | Directives & règlements | Parlement + Conseil | Le socle politique | AIFMD, MiFID II, CRR, EMIR… |
| **L2** | Actes délégués / d'exécution | Commission (sur projet AES) | Précise le L1 (« comment ») | AIFMD délégué (Rgt 231/2013) |
| **L3** | Orientations, Q&A, RTS/ITS | ESMA / EBA / EIOPA, AMF, ACPR | Doctrine, *soft law* | Guidelines ESMA, position AMF |
| **L4** | Contrôle & sanction | Commission, autorités nationales | Mise en application | Procédures d'infraction |

**Le projet travaille au niveau 1** (le socle), plus **un acte L2 pilote** (AIFMD délégué) pour
montrer que la mécanique descend d'un niveau. L3/L4 ne sont pas encore intégrés (cf. §7).

> Le « niveau 1 » n'est donc pas *un texte*, c'est **toute la base législative dure** des services
> financiers de l'UE — une quarantaine de textes.

---

## 2. L'axe qui manquait : organiser par **domaine métier**

Lamfalussy classe *à la verticale* (par force juridique). Mais pour s'y retrouver dans ~40 textes,
il faut aussi un classement *à l'horizontale* : **par domaine métier** (de quoi parle le texte).

C'est la **couche intermédiaire** qui reliait tout sans être explicite jusqu'ici :

```
~40 textes de niveau 1
        │
        ▼   ← classement par DOMAINE MÉTIER  (la couche qu'on rend explicite ici)
   8 domaines (fonds, marchés, banque, assurance, paiements, durabilité, numérique, transverse)
        │
        ▼   ← article de définitions de chaque texte
   termes définis (EN/FR, base légale)
        │
        ▼   ← isolation acteurs / concepts
   acteurs  +  concepts
        │
        ▼   ← rattachement
   obligations (« qui doit faire quoi »)
```

Sans le classement par domaine, on a une pile de textes ; avec lui, on a une **bibliothèque**
navigable.

### L'analogie de la bibliothèque

| Bibliothèque | Index réglementaire |
|---|---|
| La bibliothèque entière | Le niveau 1 (tout le droit dur UE) |
| Les rayons (Histoire, Sciences…) | Les **domaines métier** (fonds, marchés, banque…) |
| Un livre | Un **texte** (AIFMD, MiFID II…) |
| Le glossaire en fin de livre | L'**article de définitions** du texte |
| Une entrée du glossaire | Un **terme défini** (acteur ou concept) |
| Renvoi « voir aussi p. X » | Un **renvoi** vers un autre texte |

---

## 3. Les ~40 textes, regroupés par domaine

Colonnes : **CELEX** (identifiant EUR-Lex), **type** (Directive/Règlement, lu depuis le CELEX),
**art. déf.** (article de définitions détecté automatiquement), **#termes** et **#acteurs**
**bruts** (par texte, *avant* déduplication inter-textes).

### Fonds / gestion d'actifs

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| AIFMD (gestion de FIA) | 32011L0061 | Directive | Art. 4 | 41 | 14 |
| AIFMD niveau 2 (délégué) | 32013R0231 | Règlement | Art. 1 | 5 | 3 |
| OPCVM / UCITS | 32009L0065 | Directive | Art. 2 | 18 | 3 |
| ELTIF (fonds long terme) | 32015R0760 | Règlement | Art. 2 | 19 | 7 |
| Fonds monétaires (MMFR) | 32017R1131 | Règlement | Art. 2 | 23 | 3 |
| EuVECA (capital-risque) | 32013R0345 | Règlement | Art. 3 | 13 | 2 |
| EuSEF (entrepr. sociale) | 32013R0346 | Règlement | Art. 3 | 13 | 2 |
| Distribution transfront. (règl.) | 32019R1156 | Règlement | Art. 3 | 8 | 5 |
| Distribution transfront. (dir.) | 32019L1160 | Directive | — *(modificative)* | 0 | 0 |
| **Sous-total** | | | | **140** | **39** |

### Marchés financiers

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| MiFID II (marchés d'instr. fin.) | 32014L0065 | Directive | Art. 4 | 63 | 20 |
| MiFIR | 32014R0600 | Règlement | Art. 2 | 47 | 15 |
| Abus de marché (MAR) | 32014R0596 | Règlement | Art. 3 | 35 | 12 |
| Abus de marché pénal (MAD II) | 32014L0057 | Directive | Art. 2 | 14 | 1 |
| Prospectus | 32017R1129 | Règlement | Art. 2 | 26 | 6 |
| Dépositaires centraux (CSDR) | 32014R0909 | Règlement | Art. 2 | 46 | 12 |
| Ventes à découvert | 32012R0236 | Règlement | Art. 2 | 17 | 5 |
| Indices de référence (Benchmarks) | 32016R1011 | Règlement | Art. 3 | 29 | 10 |
| Titrisation | 32017R2402 | Règlement | Art. 2 | 23 | 7 |
| Financement sur titres (SFTR) | 32015R2365 | Règlement | Art. 3 | 18 | 4 |
| Dérivés OTC (EMIR) | 32012R0648 | Règlement | Art. 2 | 29 | 12 |
| Transparence | 32004L0109 | Directive | Art. 2 | 16 | 5 |
| Agences de notation (CRA) | 32009R1060 | Règlement | Art. 3 | 15 | 6 |
| **Sous-total** | | | | **378** | **115** |

### Banque / résolution

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Exigences de fonds propres (CRR) | 32013R0575 | Règlement | Art. 4 | 128 | 28 |
| CRD IV | 32013L0036 | Directive | Art. 3 | 59 | 23 |
| Résolution bancaire (BRRD) | 32014L0059 | Directive | Art. 2 | 108 | 30 |
| Résolution unique (SRMR) | 32014R0806 | Règlement | Art. 3 | 54 | 11 |
| Garantie des dépôts (DGSD) | 32014L0049 | Directive | Art. 2 | 18 | 4 |
| **Sous-total** | | | | **367** | **96** |

### Assurance

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Solvabilité II | 32009L0138 | Directive | Art. 13 | 39 | 10 |
| Distribution d'assurance (IDD) | 32016L0097 | Directive | Art. 2 | 18 | 6 |
| **Sous-total** | | | | **57** | **16** |

### Paiements

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Services de paiement (DSP2) | 32015L2366 | Directive | Art. 4 | 48 | 10 |
| Monnaie électronique | 32009L0110 | Directive | Art. 2 | 4 | 2 |
| **Sous-total** | | | | **52** | **12** |

### Durabilité

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Informations durabilité (SFDR) | 32019R2088 | Règlement | Art. 2 | 24 | 10 |
| Taxonomie | 32020R0852 | Règlement | Art. 2 | 23 | 2 |
| **Sous-total** | | | | **47** | **12** |

### Numérique / crypto

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Crypto-actifs (MiCA) | 32023R1114 | Règlement | Art. 3 | 51 | 16 |
| Résilience opér. numérique (DORA) | 32022R2554 | Règlement | Art. 3 | 65 | 39 |
| **Sous-total** | | | | **116** | **55** |

### Transverse (financement participatif, retraite, LCB-FT, comptable, AES, PRIIPs)

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Financement participatif (ECSP) | 32020R1503 | Règlement | Art. 2 | 18 | 7 |
| Retraite paneuropéenne (PEPP) | 32019R1238 | Règlement | Art. 2 | 33 | 7 |
| Retraite professionnelle (IORP II) | 32016L2341 | Directive | Art. 6 | 19 | 8 |
| Anti-blanchiment (LCB-FT) | 32015L0849 | Directive | Art. 3 | 17 | 6 |
| Directive comptable | 32013L0034 | Directive | Art. 2 | 16 | 0 |
| Règlement AEMF (ESMA) | 32010R1095 | Règlement | Art. 4 | 3 | 3 |
| PRIIPs (doc. d'info. clé) | 32014R1286 | Règlement | Art. 4 | 8 | 4 |
| **Sous-total** | | | | **114** | **35** |

---

## 4. Le total consolidé

| Indicateur | Valeur | Détail |
|---|---:|---|
| Domaines métier | **8** | fonds, marchés, banque, assurance, paiements, durabilité, numérique, transverse |
| Textes moissonnés | **~40** | 42 entrées dont 1 purement modificative (0 terme) |
| Termes définis **bruts** | **1 271** | somme par texte (un terme compté autant de fois qu'il est défini) |
| Termes **distincts** | **782** | après déduplication inter-textes (liste minimale) |
| **Acteurs isolés** | **214** | dont **38 partagés par ≥3 textes** (ex. *credit institution*, *competent authority*) |

> **À lire ainsi** : 1 271 entrées brutes → on dédoublonne (un même *« investisseur professionnel »*
> défini dans 10 textes = 1 ligne, avec la trace de ses 10 bases légales) → **782 termes distincts**,
> dont **214 acteurs**. C'est la « liste minimale » : le vocabulaire de référence du projet.

**Lecture des volumes** : le poids n'est pas uniforme. La **banque** (CRR 128, BRRD 108) et les
**marchés** (MiFID II 63) concentrent les définitions ; à l'inverse certains textes sont quasi muets
(monnaie électronique 4, AEMF 3). DORA isole 39 acteurs — beaucoup, car il nomme une longue chaîne
de prestataires TIC.

---

## 5. Naviguer autrement : par **objet** et par **champ d'application**

Le classement par domaine est la porte d'entrée, mais une fois dedans on circule par deux clés :

- **Par objet** — *de quoi traite le texte.* Ex. : un *fonds d'investissement alternatif* → AIFMD ;
  un *dérivé de gré à gré* → EMIR ; un *crypto-actif* → MiCA.
- **Par champ d'application** — *qui est visé.* Ex. : MiFID II vise les *entreprises
  d'investissement* ; CRR/CRD IV les *établissements de crédit* ; AIFMD les *gestionnaires de FIA*.

C'est exactement à quoi servent les **articles de définition** : ils fixent, pour chaque texte, son
**objet** (les concepts) et son **champ** (les acteurs). D'où le choix de partir d'eux.

| Question de l'utilisateur | Clé de navigation | Réponse |
|---|---|---|
| « Quel texte régit les FIA ? » | par champ d'application | AIFMD (32011L0061) |
| « Où est défini un *dérivé OTC* ? » | par objet | EMIR, Art. 2 |
| « Qui surveille les indices de référence ? » | par acteur | Benchmarks, Art. 3 |

---

## 6. Où le code agit (rappel pour relier la carte au dépôt)

| Étape de la chaîne (§2) | Code | Sortie |
|---|---|---|
| Récupérer un texte (par CELEX) | `ingestion/eurlex_fetcher.py` (API Cellar) | HTML EN/FR dans `data/raw/<ID>/` |
| Lire la structure (sommaire) | `glossary/toc.py` | sommaire chapitres/articles |
| Moissonner l'article de définitions | `glossary/definitions.py` | termes (EN/FR, base légale) |
| Classer acteur/concept (reproductible) | `scripts/classify_overrides.py` (LM Studio, temp 0/seed fixe, cache) | `config/glossary/overrides/*.yaml` |
| Isoler acteurs / concepts | override + `refdata/vocab.py` | acteur · concept · *à classer* |
| Construire la carte ci-dessus | `scripts/build_l1_glossary.py` (`L1_PERIMETER`) | `data/exports/glossary/` |
| Alimenter le vocabulaire (idempotent) | `scripts/vocab_sync.py` | `config/vocabularies/*.yaml` |

Le **périmètre** (la liste des ~40 textes et leur CELEX) est défini une seule fois dans
`L1_PERIMETER` ([scripts/build_l1_glossary.py](../scripts/build_l1_glossary.py)). Ajouter un texte =
ajouter une ligne → la chaîne entière se rejoue. C'est ce qui rend la méthode **réplicable sur toute
une base d'actes**.

---

## 7. Limites honnêtes (ce qui n'est pas encore solide)

- **Classification acteur/concept** : relue à la main pour AIFMD L1/L2 ; pour les ~38 autres textes
  elle est **générée de façon reproductible** (`scripts/classify_overrides.py` via LM Studio, décodage
  déterministe + cache) et **marquée « à RELIRE »**. Ce qui reste, c'est la **validation métier** —
  pas la reproductibilité. L'extraction du terme et de sa définition est, elle, fidèle au texte.
- **Bilingue partiel** : le FR n'est récupéré que pour une partie des textes (52/214 acteurs ont leur
  libellé FR).
- **Versions de base, pas consolidées** : la carte utilise les CELEX d'origine. Les versions « à
  jour » (consolidées) ont un CELEX daté distinct ; la résolution automatique existe
  (`--consolidated`) mais n'est pas généralisée à tout le périmètre.
- **Renvois abrogés** : certaines définitions renvoient à des textes abrogés (MiFID I, ancienne
  directive bancaire…) — la table de re-pointage existe mais n'est pas appliquée partout.
- **L3/L4 absents** : doctrine AMF/ACPR (et les faux-amis FR↔UE) pas encore intégrés.

*Voir [docs/approche_glossaire.md](approche_glossaire.md) (méthode, non technique) et
[docs/level1_perimeter.md](level1_perimeter.md) (détail du périmètre et des renvois).*
