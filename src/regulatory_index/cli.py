"""Point d'entrée en ligne de commande du pipeline d'index réglementaire."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import psycopg
import typer

from .db import DbStatus, QueryResult, apply_schema, collect_status, read_only_query
from .eval.metrics import compute, write_report
from .export.csv_writer import write_csv
from .export.excel_writer import write_workbook
from .export.glossary_writer import write_glossary
from .export.html_graph_writer import write_html_graph
from .extraction.langextract_runner import RunnerConfig, run
from .glossary import build_toc, harvest_glossary
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
def extract(
    units: Annotated[Path, typer.Argument(exists=True, help="JSONL file of normative units.")],
    out_dir: Annotated[Path, typer.Option(help="Where to persist extractions.")] = Path(
        "data/extractions"
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
    obligations_dir: Annotated[Path, typer.Option(exists=True)] = Path("data/extractions"),
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
    obligations_dir: Annotated[Path, typer.Option(exists=True)] = Path("data/extractions"),
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
    obligations_dir: Annotated[Path, typer.Option()] = Path("data/extractions"),
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

    Permet d'utiliser `sommaire`/`glossary` sur n'importe quel acte présent dans data/textes_sources/,
    qu'il soit déclaré ou non dans sources_registry.yaml.
    """
    candidates = sorted(
        (raw_dir / source_id).glob(f"*_{language.upper()}_*.html"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    return candidates[0] if candidates else None


@app.command()
def sommaire(
    source_id: Annotated[str, typer.Argument(help="Source id présent dans sources_registry.yaml")],
    language: Annotated[str, typer.Option(help="EN ou FR")] = "EN",
    raw_dir: Annotated[Path, typer.Option()] = Path("data/textes_sources"),
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
    raw_dir: Annotated[Path, typer.Option()] = Path("data/textes_sources"),
    out_dir: Annotated[Path, typer.Option()] = Path("data/exports"),
    act_label: Annotated[
        str, typer.Option(help="Préfixe de legal_basis (défaut : avant '_').")
    ] = "",
    definitions_article: Annotated[
        str, typer.Option(help="Forcer le n° d'article (sinon auto).")
    ] = "",
) -> None:
    """Construit le glossaire des termes définis d'un acte (EN+FR) depuis son HTML EUR-Lex.

    Marche pour tout acte présent dans data/textes_sources/ (pas besoin qu'il soit dans le registry) ;
    le CELEX est repris du registry s'il y figure, sinon déduit du nom du HTML en cache.
    """
    entry = load_sources_registry().get(source_id)
    level = entry.level if entry else 1
    title = entry.title if entry else source_id
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


# === Base regindex (schéma golden IRR v2) ==================================

db_app = typer.Typer(no_args_is_help=True, help="Base golden regindex (IRR v2).")
app.add_typer(db_app, name="db")


def _render_table(headers: list[str], rows: list[tuple[object, ...]]) -> str:
    """Table texte alignée (colonnes ajustées au plus large). Vide si aucune ligne."""
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in cells)) if cells else len(headers[i])
        for i in range(len(headers))
    ]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "  ".join("-" * widths[i] for i in range(len(headers)))
    body = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in cells]
    return "\n".join([line, sep, *body])


def _echo_status(status: DbStatus) -> None:
    typer.echo(f"# schéma « {status.schema_name} » — {status.total_rows} lignes au total\n")
    typer.echo("## Volumétrie par table")
    typer.echo(_render_table(["table", "lignes"], [(t.table, t.rows) for t in status.tables]))
    typer.echo("\n## Couverture (coverage_audit)")
    if status.coverage:
        typer.echo(
            _render_table(
                ["statut", "source_units"],
                [(c.coverage_status, c.units) for c in status.coverage],
            )
        )
    else:
        typer.echo("(aucune ligne de couverture)")
    typer.echo("\n## Extraction (par modèle)")
    if status.extraction_runs:
        typer.echo(
            _render_table(
                ["modèle", "statements", "dernier"],
                [
                    (r.extraction_model, r.statements, r.last_created_at)
                    for r in status.extraction_runs
                ],
            )
        )
    else:
        typer.echo("(aucun statement extrait)")


@db_app.command("apply")
def db_apply() -> None:
    """Applique `db/schema.sql` au schéma `regindex` (recrée le schéma, idempotent)."""
    n = apply_schema()
    typer.echo(f"OK — schéma regindex appliqué ({n} tables) depuis db/schema.sql")


@db_app.command("status")
def db_status() -> None:
    """Affiche l'état de `regindex` : volumétrie, couverture, activité d'extraction."""
    _echo_status(collect_status())


@db_app.command("query")
def db_query(
    sql: Annotated[str, typer.Argument(help="Requête SELECT (lecture seule, serveur READ ONLY).")],
) -> None:
    """Exécute une requête en LECTURE SEULE sur `regindex`.

    La transaction est `READ ONLY` côté PostgreSQL : tout write est refusé par le
    serveur (`ReadOnlySqlTransaction`), pas par une inspection de la requête.
    """
    try:
        result: QueryResult = read_only_query(sql)
    except psycopg.errors.ReadOnlySqlTransaction:
        typer.echo(
            "refusé : la connexion est en lecture seule (INSERT/UPDATE/DELETE/DDL)", err=True
        )
        raise typer.Exit(code=1) from None
    if not result.columns:
        typer.echo("(aucune colonne renvoyée)")
        return
    typer.echo(_render_table(result.columns, result.rows))
    typer.echo(f"\n{result.row_count} ligne(s)")


if __name__ == "__main__":
    app()
