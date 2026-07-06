# Regulatory Index — POC AIFMD

POC d'un index réglementaire structuré pour AIFMD (Level 1 + Level 2 + ESMA Level 3 + doctrine AMF). Objectif : produire une table exportable (Excel/CSV) où chaque ligne = une obligation, avec ses dimensions (Acteur, Action, Objet, Condition, Source, Level, Thème, Scope, Exception, Preuve, Contrôle) et son rattachement cross-level (clarifies / strengthens / operationalizes / interprets).

## Stack

- **Package manager** : `uv`
- **Parsing** : `BeautifulSoup` (DOM, pas de regex, pas de PDF) — le HTML EUR-Lex **en cache** est parsé en unités normatives (`ingestion/eurlex_html_parser.py`)
- **Extraction** : [LangExtract](https://github.com/google/langextract) avec source grounding natif
- **LLM backend** : **LM Studio** — serveur local OpenAI-compatible (GPU Metal/MLX) piloté via le provider OpenAI de LangExtract ; modèle au choix (**`qwen2.5-7b-instruct`** par défaut — meilleur rappel au benchmark, à charger en contexte **32k** ; `google/gemma-4-e4b` = alternative plus rapide/robuste ; swap via `--model-id`), **sortie structurée** (JSON schema) activée
- **Matérialisation** : pandas (DataFrames en mémoire, pas de base persistante)
- **Graphe** : NetworkX + HTML interactif (pyvis)
- **Export** : xlsxwriter (Excel multi-onglets), CSV UTF-8, HTML interactif (pyvis), rapport Markdown

Contraintes méthodologiques :

- **Pas de clé API LLM cloud** — tout tourne en local
- **Pas de PDF** — on attaque les sources via HTML / API structurés uniquement
- **Pas de regex** nulle part dans le code (extraction, linking, **et validation des schémas**) — tokenisation `str` / traversée DOM uniquement
- **Pas de chaîne de fallback** — une seule approche propre par étape
- **Vocabulaire contrôlé** injecté dans le prompt LangExtract (description + few-shots gold), puis canonicalisation à la matérialisation : les formes FR/EN d'un même terme (actor / action / object / theme) sont repliées sur un libellé pivot unique ; les valeurs hors-vocab sont conservées et remontées en « vocab gaps »
- **Données réelles uniquement** — pas de fixtures synthétiques

## Setup

```bash
# 1. Installer uv (sans sudo)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Installer LM Studio (runner Metal/MLX) + un modèle, puis lancer le serveur local.
#    macOS : brew install --cask lm-studio  (lancer l'app une fois pour initialiser la CLI `lms`)
#    Modèle : préférer un template gérant le rôle `system` (gemma, qwen, ou les variantes
#    lmstudio-community) — le GGUF stock de Mistral ne gère pas `system` sur LM Studio.
lms get https://huggingface.co/lmstudio-community/Qwen2.5-7B-Instruct-GGUF --yes  # URL HF (le nom court ne résout pas toujours)
lms server start                                        # API OpenAI-compatible sur :1234/v1
lms load qwen2.5-7b-instruct --context-length 32768 --yes   # 32k : qwen produit beaucoup sur les textes denses

# 3. Installer les deps Python
#    uv construit .venv à partir du Python pyenv 3.12.11 (cf. .python-version +
#    [tool.uv] python-preference = "only-system" : uv ne télécharge jamais son
#    propre interpréteur). Prérequis : `pyenv install 3.12.11`.
uv sync
```

## Corpus : la base Lalande est la source unique

**Décision (2026-07-06)** : la **base de documents Lalande** (conteneur `lalande-pg`, port 5433,
DSN via `regulatory_index.ingestion.db_corpus.resolve_dsn` ; tables `public.acts`/`versions`/
`subdivisions`) est désormais la **SOURCE UNIQUE du corpus**. L'ingestion alimente directement les
tables golden `regindex` (`regulation` / `source_unit` / `coverage_audit`) — voir
[docs/schema_relationnel.md](docs/schema_relationnel.md) § « Ingestion 01/02 ».

```bash
# Ingestion déterministe base Lalande -> regindex (regulation + source_units + coverage)
just ingest 32011L0061            # un acte  (ou : uv run regindex ingest 32011L0061)
just ingest-all                   # tous les CELEX du registre présents en base
```

### Dictionnaire d'amorçage : seed versionné + candidats à relire

Le référentiel contrôlé (tables 04/05/06 + `dictionary_entry`) s'amorce depuis un **YAML
versionné** — l'onglet 15 du classeur converti **une fois** en
[`config/dictionary_seed.yaml`](config/dictionary_seed.yaml) (l'Excel n'est **jamais** lu au
runtime). Deux temps séparés (mode d'emploi client) : le **seed minimal est ACTIF**,
l'enrichissement entre en **CANDIDATS INACTIFS à relire**. Détails et mapping :
[docs/schema_relationnel.md](docs/schema_relationnel.md) § « Dictionnaire 04/05/06 + 15 ».

```bash
just dict-seed-plan               # dry-run : plan (lignes/table), sans écrire
just dict-seed                    # upsert le seed minimal ACTIF (idempotent)
just dict-candidates              # injecte vocab + 303 acteurs glossaire en candidats INACTIFS (dédup vs seed)
just dict-status                  # comptes : dictionary_entry par famille + actif/candidat par entité
```

**Ordre du pipeline** : `ingest` (01/02) → `dict seed` (04/05/06 + 15, actif) →
`dict candidates` (enrichissement inactif) → *[loader statements 03+ à venir]*. La promotion
d'un candidat est un **geste humain** (`UPDATE is_active=true` + nettoyage du préfixe de
provenance) ; un re-run de `dict candidates` ne réécrit jamais une entrée déjà relue.

L'ingestion est **idempotente** (re-run = mêmes ids ; upsert qui ne réécrit que le texte modifié,
hash recalculé) et **sans regex / sans fallback** : découpe des articles en `source_unit` par règles
structurelles générales (phrases pour les paragraphes, 1 unité par point/subpoint), ids stables
`SU-<CELEX>-ART<n>[-P<n>][-PT<label>][-SPT<label>]-S<nn>`.

> **Legacy** : le chemin HTML `data/textes_sources/` n'est plus la source du corpus. Il ne sert
> plus que de **repli temporaire pour le glossaire** (`sommaire`/`glossary`), dont le port sur la
> base Lalande est **à venir**.

## Pipeline obligations (LLM, sur l'ancien corpus JSONL — legacy)

L'ancien pipeline d'obligations reste disponible : il (re)construit un `corpus.jsonl` depuis la base
(`db_corpus.py`, 1 unité par article) puis extrait via LangExtract. Conservé pour l'extraction IA
tant que la chaîne `regindex` → statements n'est pas branchée.

```bash
# 1. (Re)construire le corpus en unités normatives depuis la base PostgreSQL du dump
just corpus-db                    # ou : uv run python scripts/build_corpus_from_db.py
# → produit data/unites/corpus.jsonl (1 ligne = 1 article ; source = tables subdivisions/chunks)

# 2. Extraire les obligations (LangExtract + LM Studio local, idempotent)
uv run regindex extract data/unites/corpus.jsonl

# 3. Construire les obligations finales + relations (matérialisation en mémoire + compteurs)
uv run regindex link

# 4. Exporter Excel + CSV + HTML interactif + quality_report.md
uv run regindex export

# Tout-en-un (extract → link → export)
uv run regindex pipeline data/unites/corpus.jsonl
```

Vérification rapide (ou simplement `just check`) :

```bash
just check                       # lint + types + tests (100 tests)
# équivalents directs :
uv run --no-sync ruff check src/ tests/ scripts/
uv run --no-sync mypy src/ tests/ scripts/
uv run --no-sync python -m pytest -q
```

> ⚠️ **Quirk d'install connu sur ce `.venv`** : le re-sync implicite de `uv run` **désinstalle**
> le paquet `regulatory_index` (la racine éditable de l'`uv.lock` est « checked » mais retombe
> hors `site-packages`) → `uv run regindex …` lève `ModuleNotFoundError`. **Contournements** :
> utilise le **`justfile`** (toutes les recettes passent par `uv run --no-sync`, robuste), ou
> réinstalle avant un appel CLI direct : `uv sync --reinstall-package regulatory-index`.
> En CI (env neuf), `uv sync` installe correctement la racine — pas de souci.
> Le `VIRTUAL_ENV` de ta session shell est ignoré par uv (warning bénin, il cible `.venv`).

## Sources prises en charge

Les textes sont **EUR-Lex (EU Level 1 / 2)** — p. ex. Directive 2011/61/EU et Règlement délégué 231/2013. Le **corpus golden `regindex`** vient de la **base Lalande** (source unique ; `ingest`, tables `acts`/`versions`/`subdivisions`) ; le **glossaire** part encore du **HTML en cache** dans `data/textes_sources/` (legacy, port Lalande à venir). Le dépôt n'embarque plus d'acquisition réseau (PDF, doctrine AMF et Légifrance hors périmètre).

Le registry (`config/sources_registry.yaml`) définit le périmètre : il référence les métadonnées de chaque source (CELEX, level, issuer, aliases pour la résolution de citations) et sert de liste des CELEX à (re)construire depuis la base.

## Glossaire & sommaire (à partir du contenu d'un acte)

Pipeline **autonome** qui part directement du **HTML d'un acte** (pas d'acquisition réseau — il s'intègre à n'importe quelle base d'actes) et produit son sommaire et son glossaire de termes définis. Conçu pour se **répliquer sur tout un corpus d'actes**.

```bash
# Sommaire (chapitres / sections / articles) + repérage de l'article de définitions
uv run regindex sommaire AIFMD_L1            # → data/exports/sommaire/sommaire_AIFMD_L1_EN.json

# Glossaire des termes définis (bilingue EN/FR, acteurs isolés des produits/activités)
uv run regindex glossary AIFMD_L1            # → data/exports/glossary/{AIFMD_L1_definitions.yaml, glossary_AIFMD_L1.csv/.md}
```

API librairie (le vrai produit — `html` en entrée, données en sortie) :

```python
from regulatory_index.glossary import build_toc, harvest_glossary

toc = build_toc(html_en, source_id="AIFMD_L1", language="EN")
toc.definitions_article          # -> "4"  (détecté via le sous-titre 'Definitions')
terms = harvest_glossary(html_en, html_fr, source_id="AIFMD_L1", celex="32011L0061")
# terms: list[DefinedTerm] — term_en/fr, type (acteur|produit|activite), legal_basis, cites, définitions
```

**Un seul chemin, sans heuristique.** L'**extraction** est automatique et se rejoue sur n'importe quel acte : article de définitions auto-détecté via le sommaire, points `(a)(b)…` comme `(1)(2)…` découpés de façon déterministe (str, sans regex), FR optionnel → `term_en/fr`, `definition_en/fr`, `legal_basis`. Le `type` (acteur/produit/activité) provient d'un fichier par acte (`config/glossary/overrides/{source_id}.yaml`) ; un acte sans override sort avec `type` à `null` — **jamais deviné**. Les `cites` (renvois inter-actes) sont **extraits automatiquement de la définition** (`extract_citations`, déterministe, sans regex : « Directive 2009/65/EC », « Regulation (EU) No 575/2013 »…) — **fidèles au texte**, donc le graphe inter-textes se reconstruit pour tout acte, sans curation manuelle. Un override peut toujours fournir des `cites` relus qui priment.

**Classification acteur/produit/activité reproductible.** Le `type` des overrides (typologie stricte du client : acteur / produit / activité, tirée des articles de définition) est **généré de façon reproductible** par `scripts/classify_overrides.py` (`just classify-overrides`) : le modèle local LM Studio est interrogé en décodage déterministe (température 0, graine fixe) avec mise en cache (clé incluant une empreinte du prompt → un changement de typologie invalide le cache d'office), donc relancer régénère les mêmes fichiers **à l'identique** (et hors-ligne via `--model <id>` si le cache est rempli). Un run complet **harmonise** ensuite chaque terme sur **un seul type dans tout le corpus** (vote majoritaire déterministe), et les égalités résiduelles sont **tranchées par la définition de référence** du terme (la plus substantielle, pas un simple renvoi) — **règle générale et déterministe, sans liste de décisions à maintenir**. Ces `type` restent marqués « à RELIRE » ; les `cites` viennent de la relecture. La promotion au vocabulaire contrôlé (`scripts/vocab_sync.py`, `just vocab-sync`) **régénère** sa section de façon **idempotente** (plus d'empilement) ; la déduplication unifie casse, espaces et variantes de tiret/trait d'union, si bien que les doublons typographiques fusionnent **d'office** (sans liste à tenir). Le périmètre est acquis en **EN + FR** (`build_l1_glossary`, 42/42 textes). Toute la chaîne définitions → classification → harmonisation → vocabulaire est ainsi rejouable sans dérive.

Réplication (vérifiée) : `regindex glossary AIFMD_L2` produit le glossaire du Règl. délégué 231/2013 (définitions à l'**article 1**, points **numérotés**) via le même code, son enrichissement venant de `config/glossary/overrides/AIFMD_L2.yaml`. Le périmètre niveau 1 et le piège « renvois vers des textes abrogés » sont documentés dans `docs/level1_perimeter.md`. La **cartographie des ~40 textes par domaine métier** (niveaux Lamfalussy, volumétrie réelle termes/acteurs par texte) est dans `docs/niveau1_cartographie.md`. Pour une **présentation métier** (non technique, qui relie le travail à la logique réglementaire) : `docs/presentation.md`, avec une **trame de prise de parole** (~5 min + prépa Q&A) dans `docs/trame_presentation.md`.

> ℹ️ Le corpus livré est **EUR-Lex** uniquement. Les entrées **ESMA** du registry n'ont pas de texte associé (publié en PDF, hors périmètre) : elles servent uniquement de **cibles de citation** (aliases) pour le linkage cross-level.

## Structure du projet

```text
config/
  vocabularies/        YAML de vocab contrôlé (actors, actions, objects, themes,
                       conditions, acronyms, relation_types) + theme codes
  glossary/            overrides/ (classification acteur/produit/activité par acte : tout
                       généré + harmonisé, reproductible — règle générale, sans liste)
  sources_registry.yaml   Registry des sources (CELEX, level, issuer) + aliases citation ; périmètre du corpus

prompts/               Templates Jinja LangExtract (EN/FR) + few-shots gold annotés

data/
  textes_sources/      les VRAIS TEXTES : HTML EUR-Lex en cache (1 dossier par acte)
  unites/              JSONL d'unités normatives (1 ligne = 1 article)
  extractions/         résultats LangExtract : 1 JSON par unité (idempotent)
                       + _failed.jsonl si échec (réinitialisé à chaque run)
  exports/             sorties classées par type :
    glossary/            *_definitions.yaml, glossary_*.csv/.md, glossary_L1_minimal/actors
    sommaire/            sommaire_*.json (tables des matières)
    obligations/         aifmd_index.xlsx, obligations.csv, relations.csv,
                         aifmd_relations.html, quality_report.md

src/regulatory_index/   (chaque paquet expose son API publique via __init__.py)
  schemas/             modèles de données PURS (Pydantic) : Source, Obligation,
                       CrossLevelRelation, RawObligation / UnitExtraction
  refdata/             chargeurs des données de config : vocab (vocabulaires
                       contrôlés) + sources_registry (registre + alias de citation)
  ingestion/           db_corpus (dump PostgreSQL -> NormativeUnit, source du corpus)
                       + eurlex_html_parser (HTML en cache -> articles, glossaire) + unit_loader
  glossary/            models (DefinedTerm, TableOfContents) + toc (sommaire) +
                       definitions (termes définis) — part du HTML, déterministe, sans regex
  extraction/          schema_builder, examples_loader, langextract_runner
  linking/             citation_extractor (alias substring matching, no regex)
                       + graph_builder (NetworkX DiGraph)
  materialize/         builder (RawObligation -> Obligation) + core (index pandas,
                       relations cross-level, vues) — JSON extractions -> index
  export/              excel_writer (xlsxwriter multi-sheet), glossary_writer,
                       csv_writer, html_graph_writer (pyvis)
  eval/                metrics.py (grounding, latence P50/P95, distributions, vocab gaps → quality_report.md)
  cli.py               Typer CLI : vocab / extract / link / export /
                       pipeline / sommaire / glossary

scripts/               build_l1_glossary, classify_overrides, vocab_sync,
                       check_overrides, build_corpus_from_db, benchmark_models,
                       run_smoke_e2e

tests/                 pytest (schemas, vocab, sources_registry,
                       examples_loader, schema_builder, unit_loader,
                       langextract_runner with mocked LLM, obligation_builder,
                       linking, export, eval_metrics, failed_log,
                       eurlex_html_parser, html_graph_writer)
```

## Architecture du pipeline (5 étapes, sans regex, sans fallback)

1. **Corpus** — les articles + leur texte (tables `subdivisions`/`chunks`) sont lus depuis la **base PostgreSQL du dump** par `db_corpus.py` en un `NormativeUnit` par article (`scripts/build_corpus_from_db.py`). *(Le glossaire, lui, part du HTML en cache via `eurlex_html_parser`.)*
2. **Extraction LangExtract** — 1 appel LM Studio (API OpenAI-compatible) par unité, guidé par un prompt structuré (description + few-shots) avec vocab contrôlé injecté en texte. **Sortie structurée** (`use_schema_constraints=True` → JSON schema) : le **format** est garanti (1 valeur par champ, jamais liste/null) **sans figer le vocab en enum** — la découverte de termes hors-vocab reste possible. Persistance idempotente sur disque (`{source_id}/{unit_id}.json`). Échec d'une unité → log dans `_failed.jsonl` (réinitialisé au début de chaque run), on continue.
3. **Materialization** — `RawObligation` → `Obligation` avec id stable `{SCOPE}-{THEME_CODE}-{NNNN}` (déterministe par sort key). Source résolue depuis `sources_registry.yaml`. Les champs à vocabulaire contrôlé sont canonicalisés (pivot EN par défaut) via `Vocabulary.resolve` ; les termes non résolus alimentent le rapport « vocab gaps ».
4. **Linkage cross-level** — `cited_references` → `target_source_id` par alias matching (substring case-insensitive, alias les plus longs gagnent). Quand la citation nomme un article (`Article 15(3)`…), on rattache l'obligation aux **obligations cibles** extraites de cet article dans le document cité (linkage article-level, parsing par tokenisation, sans regex) ; sinon on retombe sur le nœud document `{source}#source`. Relation typée d'après `(level_src, issuer_src, level_tgt, title_src)` : `clarifies` / `strengthens` / `operationalizes` / `interprets` / `references`.
5. **Materialization + Export** — `materialize.py` charge les JSON, construit Obligations/Relations et trois DataFrames pandas (obligations / relations / units) + agrégations, le tout en mémoire → Excel formaté (7 onglets) + CSV (UTF-8, `;`) + HTML interactif (pyvis, ouvrable dans n'importe quel navigateur) + Markdown quality report.

## Phases

| Sem. | Livrable | État |
| --- | --- | --- |
| S1 | Setup uv + LLM local + schémas Pydantic + vocab v0 | ✅ |
| S2 | Pipeline extraction MVP (LangExtract + LM Studio) | ✅ |
| S3 | Acquisition corpus réel (EUR-Lex L1 + L2, FR/EN) | ✅ |
| S4 | Linkage cross-level (citation_extractor + graph_builder) | ✅ |
| S5 | Matérialisation pandas + export Excel/CSV + HTML + quality report | ✅ |
| S6 | Linkage article-level ✅ · itération expert + vocab + bigger LLM | ⏳ |

## Résultats sur le petit corpus réel

8 unités acquises (AIFMD Directive Art. 15-16 EN+FR, Délégué 231/2013 Art. 38-40, 44, 47 EN) → **58 obligations** extraites (100% grounded), **3 relations cross-level `operationalizes`** captées (L2 → L1).

> ⚠️ Chiffres **illustratifs** d'un ancien run local one-off (petit LLM local, non déterministe) — non committés et non reproductibles à l'identique. `data/` est gitignoré : régénère le rapport via `uv run regindex pipeline data/unites/corpus.jsonl` puis `uv run regindex export` (→ `data/exports/obligations/quality_report.md`).

## Limitations connues

- **Les petits LLM locaux capturent imparfaitement les citations externes** : ils confondent parfois l'en-tête de section avec une citation et ratent des références internes (Article 44 sans préciser le document). Modèle swappable via LM Studio (`--model-id`) ; pour plus de robustesse, un 7B+ comme `qwen2.5-7b-instruct`. NB : Mistral 7B v0.3 **tourne** sur LM Studio mais son format n'a pas de rôle `system` (toutes les variantes GGUF testées — mistralai, lmstudio-community, bartowski — refusent le `system` que LangExtract envoie → HTTP 400) ; il faudrait overrider le template (fusionner system→user) pour l'employer. Préférer un modèle à rôle `system` natif (qwen, gemma).
- **Linkage article-level** : on lie obligation → obligations cibles partageant l'**article** cité. Comme les unités source sont découpées par article, la granularité fine paragraphe/point n'est pas encore disponible côté source ; et les citations multi-articles (`Articles 38 à 40`) ne rattachent que le premier article. Quand aucun article n'est résolu, on retombe sur le nœud document.
- **Vocabulary v0** : 35 actors, 49 actions, 43 objects, 16 themes, 42 conditions. À enrichir avec l'expert AIFMD.
- **Pas de support ESMA** : ESMA publie en PDF, hors scope cette itération.
- **Article 21 (Depositary, 19K chars)** non traité dans le run par défaut : trop long pour un petit modèle local (prévoir chunking ou un modèle/contexte plus grand).

## Différenciateurs vs RegTech existants

Recherche éprouvée (sources : Corlytics, CUBE Global, AscentAI, Apiax, Compliance.ai/Archer, papers ICAIL 2025 / arXiv) :

- **Zéro coût API LLM** : aucun produit commercial recensé ni paper récent ne publie un pipeline 100% local. Différenciateur reproductibilité + souveraineté + coût marginal nul.
- **Distinction native Level 1/2/3 + doctrine AMF** comme dimension structurelle. Les concurrents (Corlytics, CUBE, Ascent) traitent tout au même niveau.
- **Source grounding natif** via LangExtract (`char_interval`, `alignment_status`) : traçabilité paragraphe-source vérifiable.
- **Bilingue EN/FR avec doctrine AMF** : niche sous-servie par les acteurs anglo-saxons.

Référence à creuser : Dal Pont et al., *"Lost in EU Regulation? Don't Worry, AI Found the Obligation"*, ICAIL 2025 ([DOI 10.1145/3769126.3769260](https://dl.acm.org/doi/10.1145/3769126.3769260)) — frame déontique très proche du schéma utilisé ici.
