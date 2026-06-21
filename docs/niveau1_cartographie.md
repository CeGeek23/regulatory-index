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
        ▼   ← classement acteur / produit / activité
   acteurs  ·  produits  ·  activités
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
| Une entrée du glossaire | Un **terme défini** (acteur, produit ou activité) |
| Renvoi « voir aussi p. X » | Un **renvoi** vers un autre texte |

---

## 3. Les ~40 textes, regroupés par domaine

Colonnes : **CELEX** (identifiant EUR-Lex), **type** (Directive/Règlement, lu depuis le CELEX),
**art. déf.** (article de définitions détecté automatiquement), **#termes** et **#acteurs**
**bruts** (par texte, *avant* déduplication inter-textes).

### Fonds / gestion d'actifs

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| AIFMD (gestion de FIA) | 32011L0061 | Directive | Art. 4 | 48 | 25 |
| AIFMD niveau 2 (délégué) | 32013R0231 | Règlement | Art. 1 | 7 | 3 |
| OPCVM / UCITS | 32009L0065 | Directive | Art. 2 | 24 | 9 |
| ELTIF (fonds long terme) | 32015R0760 | Règlement | Art. 2 | 23 | 9 |
| Fonds monétaires (MMFR) | 32017R1131 | Règlement | Art. 2 | 24 | 4 |
| EuVECA (capital-risque) | 32013R0345 | Règlement | Art. 3 | 15 | 6 |
| EuSEF (entrepr. sociale) | 32013R0346 | Règlement | Art. 3 | 15 | 6 |
| Distribution transfront. (règl.) | 32019R1156 | Règlement | Art. 3 | 8 | 6 |
| Distribution transfront. (dir.) | 32019L1160 | Directive | — *(modificative)* | 0 | 0 |
| **Sous-total** | | | | **164** | **68** |

### Marchés financiers

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| MiFID II (marchés d'instr. fin.) | 32014L0065 | Directive | Art. 4 | 65 | 24 |
| MiFIR | 32014R0600 | Règlement | Art. 2 | 57 | 18 |
| Abus de marché (MAR) | 32014R0596 | Règlement | Art. 3 | 40 | 13 |
| Abus de marché pénal (MAD II) | 32014L0057 | Directive | Art. 2 | 14 | 0 |
| Prospectus | 32017R1129 | Règlement | Art. 2 | 28 | 8 |
| Dépositaires centraux (CSDR) | 32014R0909 | Règlement | Art. 2 | 50 | 18 |
| Ventes à découvert | 32012R0236 | Règlement | Art. 2 | 17 | 5 |
| Indices de référence (Benchmarks) | 32016R1011 | Règlement | Art. 3 | 32 | 11 |
| Titrisation | 32017R2402 | Règlement | Art. 2 | 31 | 6 |
| Financement sur titres (SFTR) | 32015R2365 | Règlement | Art. 3 | 18 | 5 |
| Dérivés OTC (EMIR) | 32012R0648 | Règlement | Art. 2 | 31 | 18 |
| Transparence | 32004L0109 | Directive | Art. 2 | 18 | 8 |
| Agences de notation (CRA) | 32009R1060 | Règlement | Art. 3 | 37 | 22 |
| **Sous-total** | | | | **438** | **156** |

### Banque / résolution

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Exigences de fonds propres (CRR) | 32013R0575 | Règlement | Art. 4 | 179 | 66 |
| CRD IV | 32013L0036 | Directive | Art. 3 | 76 | 51 |
| Résolution bancaire (BRRD) | 32014L0059 | Directive | Art. 2 | 117 | 51 |
| Résolution unique (SRMR) | 32014R0806 | Règlement | Art. 3 | 63 | 26 |
| Garantie des dépôts (DGSD) | 32014L0049 | Directive | Art. 2 | 18 | 7 |
| **Sous-total** | | | | **453** | **201** |

### Assurance

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Solvabilité II | 32009L0138 | Directive | Art. 13 | 50 | 24 |
| Distribution d'assurance (IDD) | 32016L0097 | Directive | Art. 2 | 18 | 9 |
| **Sous-total** | | | | **68** | **33** |

### Paiements

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Services de paiement (DSP2) | 32015L2366 | Directive | Art. 4 | 48 | 13 |
| Monnaie électronique | 32009L0110 | Directive | Art. 2 | 4 | 2 |
| **Sous-total** | | | | **52** | **15** |

### Durabilité

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Informations durabilité (SFDR) | 32019R2088 | Règlement | Art. 2 | 24 | 11 |
| Taxonomie | 32020R0852 | Règlement | Art. 2 | 23 | 1 |
| **Sous-total** | | | | **47** | **12** |

### Numérique / crypto

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Crypto-actifs (MiCA) | 32023R1114 | Règlement | Art. 3 | 51 | 18 |
| Résilience opér. numérique (DORA) | 32022R2554 | Règlement | Art. 3 | 65 | 40 |
| **Sous-total** | | | | **116** | **58** |

### Transverse (financement participatif, retraite, LCB-FT, comptable, AES, PRIIPs)

| Texte | CELEX | Type | Art. déf. | #termes | #acteurs |
|---|---|---|---:|---:|---:|
| Financement participatif (ECSP) | 32020R1503 | Règlement | Art. 2 | 18 | 9 |
| Retraite paneuropéenne (PEPP) | 32019R1238 | Règlement | Art. 2 | 33 | 10 |
| Retraite professionnelle (IORP II) | 32016L2341 | Directive | Art. 6 | 19 | 10 |
| Anti-blanchiment (LCB-FT) | 32015L0849 | Directive | Art. 3 | 20 | 13 |
| Directive comptable | 32013L0034 | Directive | Art. 2 | 20 | 10 |
| Règlement AEMF (ESMA) | 32010R1095 | Règlement | Art. 4 | 3 | 3 |
| PRIIPs (doc. d'info. clé) | 32014R1286 | Règlement | Art. 4 | 8 | 4 |
| **Sous-total** | | | | **121** | **59** |

---

## 4. Le total consolidé

| Indicateur | Valeur | Détail |
|---|---:|---|
| Domaines métier | **8** | fonds, marchés, banque, assurance, paiements, durabilité, numérique, transverse |
| Textes moissonnés | **~40** | 42 entrées dont 1 purement modificative (0 terme) |
| Termes définis **bruts** | **1 459** | somme par texte (un terme compté autant de fois qu'il est défini) |
| Termes **distincts** | **893** | après déduplication inter-textes (liste minimale) |
| **Acteurs isolés** | **303** | partagés entre textes pour beaucoup (ex. *credit institution*, *competent authority*) ; décompte « à relire », à resserrer en validation métier |

> **À lire ainsi** : 1 459 entrées brutes → on dédoublonne (un même *« investisseur professionnel »*
> défini dans 10 textes = 1 ligne, avec la trace de ses 10 bases légales) → **893 termes distincts**,
> dont **303 acteurs**. C'est la « liste minimale » : le glossaire de référence, dédoublonné (il
> alimente ensuite le vocabulaire de référence du projet — cf. compteurs distincts).

**Lecture des volumes** : le poids n'est pas uniforme. La **banque** (CRR 179, BRRD 117) et les
**marchés** (MiFID II 65, MiFIR 57) concentrent les définitions ; à l'inverse certains textes sont
quasi muets (monnaie électronique 4, AEMF 3). DORA isole 40 acteurs — beaucoup, car il nomme une
longue chaîne de prestataires TIC.

---

## 5. Naviguer autrement : par **objet** et par **champ d'application**

Le classement par domaine est la porte d'entrée, mais une fois dedans on circule par deux clés :

- **Par objet** — *de quoi traite le texte.* Ex. : un *fonds d'investissement alternatif* → AIFMD ;
  un *dérivé de gré à gré* → EMIR ; un *crypto-actif* → MiCA.
- **Par champ d'application** — *qui est visé.* Ex. : MiFID II vise les *entreprises
  d'investissement* ; CRR/CRD IV les *établissements de crédit* ; AIFMD les *gestionnaires de FIA*.

C'est exactement à quoi servent les **articles de définition** : ils fixent, pour chaque texte, son
**objet** (les produits et activités) et son **champ** (les acteurs). D'où le choix de partir d'eux.

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
| Classer acteur/produit/activité (reproductible) | `scripts/classify_overrides.py` (LM Studio, temp 0/seed fixe, cache) + harmonisation (déf. de référence) | `config/glossary/overrides/*.yaml` |
| Isoler acteurs / produits / activités | override + `refdata/vocab.py` | acteur · produit · activité · *à classer* |
| Construire la carte ci-dessus | `scripts/build_l1_glossary.py` (`L1_PERIMETER`) | `data/exports/glossary/` |
| Alimenter le vocabulaire (idempotent, dédup normalisée) | `scripts/vocab_sync.py` | `config/vocabularies/*.yaml` |

Le **périmètre** (la liste des ~40 textes et leur CELEX) est défini une seule fois dans
`L1_PERIMETER` ([scripts/build_l1_glossary.py](../scripts/build_l1_glossary.py)). Ajouter un texte =
ajouter une ligne → la chaîne entière se rejoue. C'est ce qui rend la méthode **réplicable sur toute
une base d'actes**.

---

## 7. Limites honnêtes (ce qui n'est pas encore solide)

- **Classification acteur / produit / activité** (typologie du client) : **toute générée de façon
  reproductible** (`scripts/classify_overrides.py` via LM Studio, décodage déterministe + cache) puis
  **harmonisée** entre textes (un terme = un type partout), les égalités étant tranchées par la
  **définition de référence** (règle générale, sans liste). Ce qui reste, c'est la **validation métier**
  (confirmer ces décisions, surtout les définitions par renvoi) — pas la reproductibilité. L'extraction
  du terme et de sa définition est, elle, fidèle au texte.
- **Bilingue** : les **42/42 textes** sont récupérés en EN + FR (une part des acteurs du vocabulaire
  porte déjà un libellé FR officiel distinct ; le reste partage EN/FR ou attend la relecture).
- **Versions consolidées** : la carte est bâtie sur les CELEX **consolidés** (droit le plus à jour),
  résolus automatiquement via les métadonnées RDF ; seuls les textes sans consolidé officiel publié
  restent sur le CELEX d'origine.
- **Renvois abrogés** : certaines définitions renvoient à des textes abrogés (MiFID I, ancienne
  directive bancaire…) — la table de re-pointage existe mais n'est pas appliquée partout.
- **L3/L4 absents** : doctrine AMF/ACPR (et les faux-amis FR↔UE) pas encore intégrés.

*Voir [docs/approche_glossaire.md](approche_glossaire.md) (méthode, non technique) et
[docs/level1_perimeter.md](level1_perimeter.md) (détail du périmètre et des renvois).*
