# Regulatory Index — POC AIFMD

POC d'un index réglementaire structuré pour AIFMD (Level 1 + Level 2 + ESMA Level 3 + doctrine AMF). Objectif : produire une table exportable (Excel/CSV) où chaque ligne = une obligation, avec ses dimensions (Acteur, Action, Objet, Condition, Source, Level, Thème, Scope, Exception, Preuve, Contrôle) et son rattachement cross-level (clarifies / strengthens / operationalizes / interprets).

## Stack

- **Package manager** : `uv`
- **Acquisition** : `httpx` + `BeautifulSoup` (DOM, pas de regex, pas de PDF) — fetchers EUR-Lex, AMF, Légifrance
- **Extraction** : [LangExtract](https://github.com/google/langextract) avec source grounding natif
- **LLM backend** : Ollama local (`gemma3:4b` par défaut, swap possible vers `qwen2.5:7b` ou `qwen2.5:14b`)
- **Matérialisation** : Polars (DataFrames en mémoire, pas de base persistante)
- **Graphe** : NetworkX + GraphML + HTML interactif (pyvis)
- **Export** : xlsxwriter (Excel multi-onglets), CSV UTF-8, GraphML, HTML interactif, rapport Markdown

Contraintes méthodologiques :
- **Pas de clé API LLM cloud** — tout tourne en local
- **Pas de PDF** — on attaque les sources via HTML / API structurés uniquement
- **Pas de regex** dans le pipeline (extraction ni linking)
- **Pas de chaîne de fallback** — une seule approche propre par étape
- **Vocabulaire contrôlé** injecté dans le schéma LangExtract, puis canonicalisation à la matérialisation : les formes FR/EN d'un même terme (actor / action / object / theme) sont repliées sur un libellé pivot unique ; les valeurs hors-vocab sont conservées et remontées en « vocab gaps »
- **Données réelles uniquement** — pas de fixtures synthétiques

## Setup

```bash
# 1. Installer uv (sans sudo)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Installer Ollama
curl -fsSL https://ollama.com/install.sh | sh   # ou bin local sans sudo
ollama pull gemma3:4b
ollama serve   # ou laisser le service systemd tourner

# 3. Installer les deps Python
uv sync

# 4. Variables d'env (optionnel)
cp .env.example .env
```

## Pipeline end-to-end

```bash
# 1. Acquérir le corpus officiel depuis EUR-Lex (HTML, no PDF)
uv run regindex acquire
# → télécharge les CELEX listés dans config/sources_manifest.yaml
#   et produit data/units/corpus.jsonl

# 2. Extraire les obligations (LangExtract + Ollama local, idempotent)
uv run regindex extract data/units/corpus.jsonl

# 3. Construire les obligations finales + relations (matérialisation en mémoire + compteurs)
uv run regindex link

# 4. Exporter Excel + CSV + GraphML + HTML interactif + quality_report.md
uv run regindex export

# Tout-en-un (acquire → extract → link → export)
uv run regindex pipeline data/units/corpus.jsonl
```

Vérification rapide :
```bash
uv run regindex vocab            # liste les vocabs chargés (actors, actions, themes...)
uv run pytest                    # 42+ tests passent
uv run ruff check src/ tests/    # All checks passed
uv run mypy src/ tests/          # No issues
```

## Sources prises en charge

| Type | Fetcher | Format | Exemples |
|---|---|---|---|
| **EU Level 1 / 2** | `eurlex` | HTML structuré (ELI/OJ) | Directive 2011/61/EU, Délégué 231/2013 |
| **AMF doctrine** | `amf` | HTML structuré | Positions, recommandations, instructions |
| **Code monétaire et financier** | `legifrance` | HTML structuré | Articles L. 214-* (transposition AIFMD) |
| **ESMA Guidelines / Q&A** | non implémenté | (PDF, hors scope cette itération) | |

Le manifest (`config/sources_manifest.yaml`) liste les documents à acquérir. Le registry (`config/sources_registry.yaml`) référence les métadonnées de chaque source (CELEX, level, issuer, aliases pour la résolution de citations).

## Structure du projet

```
config/
  vocabularies/        YAML de vocab contrôlé (actors, actions, objects, themes,
                       conditions, acronyms, relation_types) + theme codes
  sources_manifest.yaml   Documents officiels à acquérir
  sources_registry.yaml   Registry des sources + aliases pour citation matching

prompts/               Templates Jinja LangExtract (EN/FR) + few-shots gold annotés

data/
  raw/                 HTML officiels téléchargés (par fetcher)
  units/               JSONL d'unités normatives (1 ligne = 1 article)
  obligations/         Extractions JSONL (1 fichier par unit, idempotent)
                       + _failed.jsonl si échec (réinitialisé à chaque run)
  exports/             aifmd_index.xlsx, obligations.csv, relations.csv,
                       aifmd_relations.graphml, aifmd_relations.html,
                       quality_report.md

src/regulatory_index/
  schemas/             Pydantic: Source, Obligation, CrossLevelRelation,
                       RawObligation, NormativeUnit, vocab, sources_registry,
                       obligation_builder
  ingestion/           acquire (orchestrator) + 3 fetchers : eurlex / amf /
                       legifrance + eurlex_html_parser
  extraction/          schema_builder, examples_loader, langextract_runner
  linking/             citation_extractor (alias substring matching, no regex)
                       graph_builder (NetworkX DiGraph)
  materialize.py       JSON extractions -> Obligations/Relations + Polars
                       DataFrames + agrégations (remplace l'ancienne couche DuckDB)
  export/              excel_writer (xlsxwriter multi-sheet),
                       csv_writer, graphml_writer, html_graph_writer (pyvis)
  eval/                metrics.py (coverage, grounding, latency, quality_report.md)
  cli.py               Typer CLI : vocab / acquire / extract / link /
                       export / pipeline

notebooks/             04_corpus_acquisition (exploration corpus, sans LLM)

tests/                 pytest (schemas, vocab, sources_registry,
                       examples_loader, schema_builder, unit_loader,
                       langextract_runner with mocked LLM, obligation_builder,
                       linking, export, eval_metrics,
                       ingestion_eurlex, ingestion_acquire, ingestion_amf,
                       ingestion_legifrance, html_graph_writer)
```

## Architecture du pipeline (5 étapes, sans regex, sans fallback)

1. **Acquisition** — fetcher (`eurlex` / `amf` / `legifrance`) télécharge le HTML officiel ; parser DOM extrait un `NormativeUnit` par article.
2. **Extraction LangExtract** — 1 appel Ollama par unité, schema-guided avec vocab contrôlé en enum, persistance idempotente sur disque (`{source_id}/{unit_id}.json`). Échec d'une unité → log dans `_failed.jsonl` (réinitialisé au début de chaque run), on continue.
3. **Materialization** — `RawObligation` → `Obligation` avec id stable `{SCOPE}-{THEME_CODE}-{NNNN}` (déterministe par sort key). Source résolue depuis `sources_registry.yaml`. Les champs à vocabulaire contrôlé sont canonicalisés (pivot EN par défaut) via `Vocabulary.resolve` ; les termes non résolus alimentent le rapport « vocab gaps ».
4. **Linkage cross-level** — `cited_references` → `target_source_id` par alias matching (substring case-insensitive, alias les plus longs gagnent). Relation typée d'après `(level_src, issuer_src, level_tgt, title_src)` : `clarifies` / `strengthens` / `operationalizes` / `interprets` / `references`.
5. **Materialization + Export** — `materialize.py` charge les JSON, construit Obligations/Relations et trois DataFrames Polars (obligations / relations / units) + agrégations, le tout en mémoire → Excel formaté (7 onglets) + CSV (UTF-8, `;`) + GraphML (Gephi/yEd) + HTML interactif (pyvis, ouvrable dans n'importe quel navigateur) + Markdown quality report.

## Phases

| Sem. | Livrable | État |
|---|---|---|
| S1 | Setup uv + Ollama + schémas Pydantic + vocab v0 | ✅ |
| S2 | Pipeline extraction MVP (LangExtract + Ollama gemma3:4b) | ✅ |
| S3 | Acquisition corpus réel (EUR-Lex L1 + L2, FR/EN) | ✅ |
| S4 | Linkage cross-level (citation_extractor + graph_builder) | ✅ |
| S5 | Matérialisation Polars + export Excel/CSV/GraphML + HTML + quality report | ✅ |
| S6 | Itération expert + polish + bigger LLM | ⏳ |

## Résultats sur le petit corpus réel

8 unités acquises (AIFMD Directive Art. 15-16 EN+FR, Délégué 231/2013 Art. 38-40, 44, 47 EN) → **58 obligations** extraites (100% grounded), **3 relations cross-level `operationalizes`** captées (L2 → L1).

Détails dans `data/exports/quality_report.md`.

## Limitations connues

- **`gemma3:4b` capture mal les citations externes** : il confond parfois l'en-tête de section avec une citation, et rate les références internes (Article 44 sans préciser le document). Recommandation : passer à `qwen2.5:7b` ou `qwen2.5:14b` avec GPU.
- **Linkage doc-level** : pour l'instant, on lie obligation → source (document). Le lien article-level (obligation → obligation cible) demande une résolution supplémentaire — prévue en S6.
- **Vocabulary v0** : 34 actors, 38 actions, 37 objects, 13 themes. À enrichir avec l'expert AIFMD.
- **Pas de support ESMA** : ESMA publie en PDF, hors scope cette itération.
- **Article 21 (Depositary, 19K chars)** non traité dans le run par défaut : trop long pour `gemma3:4b` sur CPU.

## Différenciateurs vs RegTech existants

Recherche éprouvée (sources : Corlytics, CUBE Global, AscentAI, Apiax, Compliance.ai/Archer, papers ICAIL 2025 / arXiv) :

- **Zéro coût API LLM** : aucun produit commercial recensé ni paper récent ne publie un pipeline 100% local. Différenciateur reproductibilité + souveraineté + coût marginal nul.
- **Distinction native Level 1/2/3 + doctrine AMF** comme dimension structurelle. Les concurrents (Corlytics, CUBE, Ascent) traitent tout au même niveau.
- **Source grounding natif** via LangExtract (`char_interval`, `alignment_status`) : traçabilité paragraphe-source vérifiable.
- **Bilingue EN/FR avec doctrine AMF** : niche sous-servie par les acteurs anglo-saxons.

Référence à creuser : Dal Pont et al., *"Lost in EU Regulation? Don't Worry, AI Found the Obligation"*, ICAIL 2025 ([DOI 10.1145/3769126.3769260](https://dl.acm.org/doi/10.1145/3769126.3769260)) — frame déontique très proche du schéma utilisé ici.
