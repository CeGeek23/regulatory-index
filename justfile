# regulatory-index — recettes du projet. Lance `just` (sans argument) pour la liste.
# Prérequis : `just` (brew install just) et `uv`.
#
# PYTHONPATH=src + `uv run --no-sync` : robuste même si l'install editable du .venv a
# dérivé (cf. mémoire projet — `uv run` peut désinstaller le paquet au re-sync).

export PYTHONPATH := "src"
uvr := "uv run --no-sync"
cli := uvr + " python -m regulatory_index.cli"

# Liste les recettes disponibles
default:
    @just --list

# === Environnement ========================================================

# Installe / met à jour l'environnement
sync:
    uv sync

# (Ré)installe le paquet en editable (si `regindex` est introuvable)
install:
    uv pip install -e .

# === Qualité ==============================================================

# Tests
test:
    {{uvr}} python -m pytest -q

# Lint (ruff)
lint:
    {{uvr}} ruff check src/ tests/ scripts/

# Typage strict (mypy)
types:
    {{uvr}} mypy src/ tests/ scripts/

# Tout vérifier : lint + types + tests
check: lint types test

# === Glossaire & sommaire =================================================

# Liste les vocabulaires contrôlés chargés
vocab:
    {{cli}} vocab

# Sommaire d'un acte (table des matières + repérage de l'article de définitions)
sommaire SOURCE="AIFMD_L1":
    {{cli}} sommaire {{SOURCE}}

# Glossaire des termes définis d'un acte (bilingue EN/FR)
glossary SOURCE="AIFMD_L1":
    {{cli}} glossary {{SOURCE}}

# Glossaire CONSOLIDÉ niveau 1 : tous les actes en cache -> liste minimale + acteurs
glossary-l1:
    {{uvr}} python scripts/build_l1_glossary.py

# Classe acteur/concept tous les overrides via LM Studio (reproductible : temp=0, seed=0, cache)
classify-overrides *ACTS:
    {{uvr}} python scripts/classify_overrides.py {{ACTS}}

# Contrôle de complétude des overrides (termes extraits vs entrées de classification)
check-overrides:
    {{uvr}} python scripts/check_overrides.py

# Verse les acteurs du glossaire dans le vocabulaire contrôlé (boucle glossaire -> vocab)
vocab-sync:
    {{uvr}} python scripts/vocab_sync.py

# === Pipeline obligations (LM Studio requis) ==============================

# Reconstruit le corpus depuis la base PostgreSQL du dump (source unique)
# ex. `just corpus-db 32011L0061` (un acte) ou `just corpus-db --lang fr`
corpus-db *ARGS:
    {{uvr}} python scripts/build_corpus_from_db.py {{ARGS}}

# Extrait les obligations (LangExtract via LM Studio)
extract UNITS="data/unites/corpus.jsonl" MODEL="qwen2.5-7b-instruct":
    {{cli}} extract {{UNITS}} --model-id {{MODEL}}

# Matérialise obligations + relations (affiche les compteurs)
link:
    {{cli}} link

# Exporte Excel / CSV / graphe HTML / rapport qualité
export:
    {{cli}} export

# De bout en bout : extract -> materialize -> export
pipeline UNITS="data/unites/corpus.jsonl":
    {{cli}} pipeline {{UNITS}}

# === LM Studio / dev ======================================================

# Charge un modèle dans LM Studio + démarre le serveur OpenAI-compatible
lms-load MODEL="qwen2.5-7b-instruct" CTX="32768":
    lms load {{MODEL}} --context-length {{CTX}} --yes
    lms server start

# Benchmark de modèles (ex. `just benchmark qwen2.5-7b-instruct google/gemma-4-e4b`)
benchmark +MODELS:
    {{uvr}} python scripts/benchmark_models.py {{MODELS}}

# Smoke test de l'extraction réelle (LM Studio requis)
smoke:
    {{uvr}} python scripts/run_smoke_e2e.py

# === Base PostgreSQL / schéma ============================================

# (Ré)applique le schéma relationnel IRR v2 dans le schéma `regindex` de la base
# (ne touche pas aux tables source du dump). Voir docs/schema_relationnel.md.
schema-apply:
    {{uvr}} python scripts/apply_schema.py

# Alimente regindex depuis la base corpus Lalande (regulation + source_units + coverage)
# ex. `just ingest 32011L0061` (un acte) ou `just ingest-all` (tout le registre présent)
ingest CELEX:
    {{cli}} ingest {{CELEX}}

# Ingère tous les CELEX du registre présents dans la base corpus Lalande
ingest-all:
    {{cli}} ingest --all-registry

# État de la base regindex : volumétrie par table + couverture + extraction
db-status:
    {{cli}} db status

# Requête SQL ad hoc en LECTURE SEULE (serveur READ ONLY)
# ex. `just db-query "SELECT * FROM regindex.regulation"`
db-query SQL:
    {{cli}} db query {{quote(SQL)}}

# === Journal / documentation =============================================

# Installe les hooks git locaux (journal auto des commits -> docs/CHANGELOG.md)
install-hooks:
    cp scripts/hooks/post-commit .git/hooks/post-commit
    chmod +x .git/hooks/post-commit
    @echo "Hook post-commit installé -> chaque commit alimente docs/CHANGELOG.md"

# === Divers ===============================================================

# Supprime les fichiers parasites (.DS_Store, __pycache__)
clean:
    find . -name .DS_Store -not -path './.git/*' -delete
    -find . -name __pycache__ -type d -not -path './.git/*' -not -path './.venv/*' -exec rm -rf {} +
