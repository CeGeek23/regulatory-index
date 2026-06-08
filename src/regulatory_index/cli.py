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
from .export.graphml_writer import write_graphml
from .export.html_graph_writer import write_html_graph
from .extraction.langextract_runner import RunnerConfig, run
from .ingestion.acquire import MANIFEST_PATH, acquire_all
from .ingestion.unit_loader import load_units_jsonl
from .linking.graph_builder import build_graph
from .materialize import load_unit_extractions_from_dir, materialize
from .schemas.vocab import load_acronyms, load_all_vocabularies

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
    base_url: Annotated[str, typer.Option(help="OpenAI-compatible server (LM Studio).")] = "http://localhost:1234/v1",
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
    typer.echo(json.dumps({"counts": counts, "finished_at": datetime.now(UTC).isoformat()}, indent=2))


@app.command()
def link(
    obligations_dir: Annotated[Path, typer.Option(exists=True)] = Path("data/obligations"),
) -> None:
    """Matérialise obligations + relations depuis les extractions et affiche les comptes.

    Ne persiste rien ; utilisez `export` pour aussi écrire Excel / CSV / GraphML.
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
    graphml_name: Annotated[str, typer.Option()] = "aifmd_relations.graphml",
    csv_delimiter: Annotated[str, typer.Option()] = ";",
) -> None:
    """Matérialise l'index puis exporte Excel + CSV + GraphML + graphe HTML + rapport qualité."""
    out_dir.mkdir(parents=True, exist_ok=True)

    unit_extractions = load_unit_extractions_from_dir(obligations_dir)
    materialized = materialize(unit_extractions)

    excel_counts = write_workbook(materialized, out_dir / excel_name)
    csv_counts = write_csv(materialized, out_dir, delimiter=csv_delimiter)
    graph, stats = build_graph(materialized.obligations, materialized.relations)
    graphml_path = write_graphml(graph, out_dir / graphml_name)
    html_graph_path = write_html_graph(graph, out_dir / "aifmd_relations.html")

    failed_log = obligations_dir / "_failed.jsonl"
    failed_count = 0
    if failed_log.exists():
        failed_count = sum(
            1 for line in failed_log.read_text(encoding="utf-8").splitlines() if line.strip()
        )

    report = compute(unit_extractions, materialized.obligations, failed_count)
    write_report(report, out_dir / "quality_report.md")

    typer.echo(
        json.dumps(
            {
                "excel": excel_counts,
                "csv": csv_counts,
                "graphml": str(graphml_path),
                "graph_html": str(html_graph_path),
                "graph_stats": {
                    "obligation_nodes": stats.obligation_nodes,
                    "source_nodes": stats.source_nodes,
                    "edges": stats.edges,
                    "edges_by_type": stats.edges_by_type,
                },
                "unresolved_citations": len(materialized.unresolved_citations),
                "quality_report": str(out_dir / "quality_report.md"),
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


if __name__ == "__main__":
    app()
