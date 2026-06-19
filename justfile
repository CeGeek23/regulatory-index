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
    {{uvr}} mypy src/ tests/

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

# Glossaire CONSOLIDÉ niveau 1 : tous les actes (auto-fetch Cellar) -> liste minimale + acteurs
glossary-l1:
    {{uvr}} python scripts/build_l1_glossary.py

# Idem, sans réseau (cache data/raw/ uniquement)
glossary-l1-cache:
    {{uvr}} python scripts/build_l1_glossary.py --no-fetch

# Contrôle de complétude des overrides (termes extraits vs entrées de classification)
check-overrides:
    {{uvr}} python scripts/check_overrides.py

# Verse les acteurs du glossaire dans le vocabulaire contrôlé (boucle glossaire -> vocab)
vocab-sync:
    {{uvr}} python scripts/vocab_sync.py

# === Pipeline obligations (LM Studio requis) ==============================

# Acquiert le corpus déclaré dans config/sources_manifest.yaml
acquire:
    {{cli}} acquire

# Reconstruit le corpus depuis le HTML déjà en cache (hors-ligne)
corpus-offline:
    {{uvr}} python scripts/build_corpus_offline.py

# Extrait les obligations (LangExtract via LM Studio)
extract UNITS="data/units/corpus.jsonl" MODEL="qwen2.5-7b-instruct":
    {{cli}} extract {{UNITS}} --model-id {{MODEL}}

# Matérialise obligations + relations (affiche les compteurs)
link:
    {{cli}} link

# Exporte Excel / CSV / graphe HTML / rapport qualité
export:
    {{cli}} export

# De bout en bout : extract -> materialize -> export
pipeline UNITS="data/units/corpus.jsonl":
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

# === Divers ===============================================================

# Supprime les fichiers parasites (.DS_Store, __pycache__)
clean:
    find . -name .DS_Store -not -path './.git/*' -delete
    -find . -name __pycache__ -type d -not -path './.git/*' -not -path './.venv/*' -exec rm -rf {} +
