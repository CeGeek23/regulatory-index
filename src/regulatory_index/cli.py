"""Point d'entrée en ligne de commande du pipeline d'index réglementaire."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from .eval.metrics import compute, write_report
from .export.csv_writer import write_csv
from .export.excel_writer import write_workbook
from .export.glossary_writer import write_glossary
from .export.html_graph_writer import write_html_graph
from .extraction.langextract_runner import RunnerConfig, run
from .glossary import build_toc, harvest_glossary
from .ingestion.acquire import MANIFEST_PATH, acquire_all
from .ingestion.eurlex_fetcher import fetch_html, latest_consolidated_celex
from .ingestion.unit_loader import load_units_jsonl
from .linking.graph_builder import build_graph
from .materialize import load_unit_extractions_from_dir, materialize
from .refdata.sources_registry import load_sources_registry
from .refdata.vocab import load_acronyms, load_all_vocabularies
from .schemas.source import Language

app = typer.Typer(no_args_is_help=True, help="Regulatory Index POC for AIFMD.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def vocab() -> None:
    """Affiche un résumé des vocabulaires contrôlés chargés."""
    vocabs = load_all_vocabularies()
    for name, vocabulary in vocabs.items():
        typer.echo(f"{name:<20} {len(vocabulary.entries):>3} entries")
    typer.echo(f"{'acronyms':<20} {len(load_acronyms()):>3} entries")


@app.command()
def acquire(
    manifest: Annotated[Path, typer.Option(exists=True)] = MANIFEST_PATH,
    raw_dir: Annotated[Path, typer.Option()] = Path("data/raw"),
    out: Annotated[Path, typer.Option(help="Output JSONL of NormativeUnits.")] = Path(
        "data/units/corpus.jsonl"
    ),
) -> None:
    """Récupère le corpus déclaré dans sources_manifest.yaml et émet un JSONL d'unités."""
    counts = acquire_all(manifest_path=manifest, raw_dir=raw_dir, units_out=out)
    typer.echo(json.dumps({**counts, "out": str(out)}, indent=2))


@app.command()
def extract(
    units: Annotated[Path, typer.Argument(exists=True, help="JSONL file of normative units.")],
    out_dir: Annotated[Path, typer.Option(help="Where to persist extractions.")] = Path(
        "data/obligations"
    ),
    model_id: Annotated[str, typer.Option()] = "qwen2.5-7b-instruct",
    base_url: Annotated[
        str, typer.Option(help="OpenAI-compatible server (LM Studio).")
    ] = "http://localhost:1234/v1",
    api_key: Annotated[str, typer.Option(help="Factice pour un serveur local.")] = "lm-studio",
    extraction_passes: Annotated[int, typer.Option()] = 1,
    temperature: Annotated[float, typer.Option()] = 0.0,
    request_timeout: Annotated[int, typer.Option(help="Request timeout (s).")] = 600,
    force: Annotated[bool, typer.Option(help="Re-extract even if output JSON exists.")] = False,
) -> None:
    """Exécute LangExtract sur un JSONL d'unités normatives, persiste un JSON par unité."""
    config = RunnerConfig(
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
        extraction_passes=extraction_passes,
        temperature=temperature,
        request_timeout=request_timeout,
    )
    counts = run(load_units_jsonl(units), out_dir=out_dir, config=config, force=force)
    typer.echo(
        json.dumps({"counts": counts, "finished_at": datetime.now(UTC).isoformat()}, indent=2)
    )


@app.command()
def link(
    obligations_dir: Annotated[Path, typer.Option(exists=True)] = Path("data/obligations"),
) -> None:
    """Matérialise obligations + relations depuis les extractions et affiche les comptes.

    Ne persiste rien ; utilisez `export` pour aussi écrire Excel / CSV / graphe HTML / rapport qualité.
    """
    unit_extractions = load_unit_extractions_from_dir(obligations_dir)
    materialized = materialize(unit_extractions)
    typer.echo(
        json.dumps(
            {
                "obligations": len(materialized.obligations),
                "relations": len(materialized.relations),
                "unresolved_citations": len(materialized.unresolved_citations),
            },
            indent=2,
        )
    )


@app.command()
def export(
    obligations_dir: Annotated[Path, typer.Option(exists=True)] = Path("data/obligations"),
    out_dir: Annotated[Path, typer.Option()] = Path("data/exports"),
    excel_name: Annotated[str, typer.Option()] = "aifmd_index.xlsx",
    csv_delimiter: Annotated[str, typer.Option()] = ";",
) -> None:
    """Matérialise l'index puis exporte Excel + CSV + graphe HTML + rapport qualité."""
    dest = out_dir / "obligations"  # exports d'obligations regroupés
    dest.mkdir(parents=True, exist_ok=True)

    unit_extractions = load_unit_extractions_from_dir(obligations_dir)
    materialized = materialize(unit_extractions)

    excel_counts = write_workbook(materialized, dest / excel_name)
    csv_counts = write_csv(materialized, dest, delimiter=csv_delimiter)
    graph, stats = build_graph(materialized.obligations, materialized.relations)
    html_graph_path = write_html_graph(graph, dest / "aifmd_relations.html")

    failed_log = obligations_dir / "_failed.jsonl"
    failed_count = 0
    if failed_log.exists():
        failed_count = sum(
            1 for line in failed_log.read_text(encoding="utf-8").splitlines() if line.strip()
        )

    report = compute(unit_extractions, materialized.obligations, failed_count)
    write_report(report, dest / "quality_report.md")

    typer.echo(
        json.dumps(
            {
                "excel": excel_counts,
                "csv": csv_counts,
                "graph_html": str(html_graph_path),
                "graph_stats": {
                    "obligation_nodes": stats.obligation_nodes,
                    "source_nodes": stats.source_nodes,
                    "edges": stats.edges,
                    "edges_by_type": stats.edges_by_type,
                },
                "unresolved_citations": len(materialized.unresolved_citations),
                "quality_report": str(dest / "quality_report.md"),
            },
            indent=2,
        )
    )


@app.command()
def pipeline(
    units: Annotated[Path, typer.Argument(exists=True, help="JSONL of normative units.")],
    obligations_dir: Annotated[Path, typer.Option()] = Path("data/obligations"),
    out_dir: Annotated[Path, typer.Option()] = Path("data/exports"),
    model_id: Annotated[str, typer.Option()] = "qwen2.5-7b-instruct",
    force: Annotated[bool, typer.Option(help="Re-extract even if outputs exist.")] = False,
) -> None:
    """Exécution de bout en bout : extract -> materialize -> export."""
    # On ne passe que ce que `pipeline` paramètre ; le reste reprend les
    # valeurs par défaut des appelés (RunnerConfig, noms/délimiteur d'export).
    extract(units=units, out_dir=obligations_dir, model_id=model_id, force=force)
    export(obligations_dir=obligations_dir, out_dir=out_dir)


def _largest_cached_html(raw_dir: Path, source_id: str, language: str) -> Path | None:
    """Plus gros HTML en cache pour (source, langue) ; indépendant du CELEX (un dossier = un acte).

    Permet d'utiliser `sommaire`/`glossary` sur n'importe quel acte présent dans data/raw/,
    qu'il soit déclaré ou non dans sources_registry.yaml.
    """
    candidates = sorted(
        (raw_dir / source_id).glob(f"*_{language.upper()}_*.html"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _celex_from_cache(raw_dir: Path, source_id: str) -> str | None:
    """Déduit le CELEX de base depuis le nom du HTML EN en cache (data/raw/<id>/<CELEX>_EN_*.html)."""
    html = _largest_cached_html(raw_dir, source_id, "EN")
    return html.name.split("_", 1)[0] if html is not None else None


@app.command()
def sommaire(
    source_id: Annotated[str, typer.Argument(help="Source id présent dans sources_registry.yaml")],
    language: Annotated[str, typer.Option(help="EN ou FR")] = "EN",
    raw_dir: Annotated[Path, typer.Option()] = Path("data/raw"),
    out_dir: Annotated[Path, typer.Option()] = Path("data/exports"),
) -> None:
    """Extrait le sommaire d'un acte (chapitres/sections/articles) et repère ses définitions."""
    lang: Language = "FR" if language.upper() == "FR" else "EN"
    html_path = _largest_cached_html(raw_dir, source_id, lang)
    if html_path is None:
        raise typer.BadParameter(f"Aucun HTML en cache pour {source_id} {lang} dans {raw_dir}")
    toc = build_toc(html_path.read_text(encoding="utf-8"), source_id=source_id, language=lang)
    dest = out_dir / "sommaire"
    dest.mkdir(parents=True, exist_ok=True)
    json_path = dest / f"sommaire_{source_id}_{lang}.json"
    json_path.write_text(toc.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(
        json.dumps(
            {
                "source_id": source_id,
                "language": lang,
                "sections": len(toc.sections),
                "articles": toc.article_count,
                "definitions_article": toc.definitions_article,
                "out": str(json_path),
            },
            indent=2,
        )
    )


@app.command()
def glossary(
    source_id: Annotated[str, typer.Argument(help="Source id présent dans sources_registry.yaml")],
    raw_dir: Annotated[Path, typer.Option()] = Path("data/raw"),
    out_dir: Annotated[Path, typer.Option()] = Path("data/exports"),
    act_label: Annotated[
        str, typer.Option(help="Préfixe de legal_basis (défaut : avant '_').")
    ] = "",
    definitions_article: Annotated[
        str, typer.Option(help="Forcer le n° d'article (sinon auto).")
    ] = "",
    consolidated: Annotated[
        bool,
        typer.Option(help="Utiliser la dernière version consolidée (à jour) via l'API Cellar."),
    ] = False,
) -> None:
    """Construit le glossaire des termes définis d'un acte (EN+FR) depuis son HTML EUR-Lex.

    Marche pour tout acte présent dans data/raw/ (pas besoin qu'il soit dans le registry) ;
    le CELEX est repris du registry s'il y figure, sinon déduit du nom du HTML en cache.
    """
    entry = load_sources_registry().get(source_id)
    level = entry.level if entry else 1
    title = entry.title if entry else source_id
    if consolidated:
        base_celex = entry.celex if entry else _celex_from_cache(raw_dir, source_id)
        if not base_celex:
            raise typer.BadParameter(
                f"CELEX de base inconnu pour {source_id} (ni registry ni cache)"
            )
        celex = latest_consolidated_celex(base_celex)
        if celex is None:
            raise typer.BadParameter(f"aucune version consolidée trouvée pour {source_id}")
        typer.echo(f"# version consolidée : {celex}", err=True)
        html_en_text, html_fr_text = fetch_html(celex, "EN"), ""
    else:
        html_en = _largest_cached_html(raw_dir, source_id, "EN")
        html_fr = _largest_cached_html(raw_dir, source_id, "FR")
        if html_en is None:
            raise typer.BadParameter(f"HTML EN requis en cache pour {source_id} dans {raw_dir}")
        if html_fr is None:
            typer.echo(f"# note: pas de HTML FR pour {source_id} — glossaire EN seul", err=True)
        celex = entry.celex if entry else html_en.name.split("_", 1)[0]
        html_en_text = html_en.read_text(encoding="utf-8")
        html_fr_text = html_fr.read_text(encoding="utf-8") if html_fr is not None else ""
    terms = harvest_glossary(
        html_en_text,
        html_fr_text,
        source_id=source_id,
        celex=celex,
        level=level,
        act_label=act_label or source_id.split("_")[0],
        definitions_article=definitions_article or None,
    )
    n_actors = sum(1 for t in terms if (t.type or "") == "acteur")
    paths = write_glossary(
        terms,
        out_dir / "glossary",
        source_id=source_id,
        title=f"Glossaire {source_id} — {title}",
        yaml_header=(
            f"# Glossaire des termes définis — {source_id} ({title}).\n"
            "# Généré par `regindex glossary` depuis le HTML EUR-Lex. 1 entrée = 1 terme défini.\n\n"
        ),
    )
    typer.echo(json.dumps({"terms": len(terms), "actors": n_actors, **paths}, indent=2))


if __name__ == "__main__":
    app()
