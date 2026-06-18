"""Écrit le glossaire des termes définis : base YAML + table CSV + table Markdown lisible.

Générique : ne suppose rien de spécifique à AIFMD. Les acteurs (types actor/investor/
supervisor) sont présentés séparément des concepts, car c'est ce que le client veut isoler.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from ..glossary.models import DefinedTerm

_ACTOR_TYPES = frozenset({"actor", "investor", "supervisor"})

_CSV_FIELDS = ["term_id", "type", "term_en", "term_fr", "legal_basis", "cites", "definition_en", "definition_fr"]


def _yaml_path(out_dir: Path, source_id: str) -> Path:
    return out_dir / f"{source_id}_definitions.yaml"


def write_glossary_yaml(terms: list[DefinedTerm], path: Path, *, header: str = "") -> Path:
    """Base de données du glossaire (1 entrée = 1 terme défini)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [t.model_dump() for t in terms]
    path.write_text(
        header + yaml.safe_dump(rows, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    return path


def write_glossary_csv(terms: list[DefinedTerm], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for t in terms:
            row = t.model_dump()
            row["cites"] = " ; ".join(t.cites)
            writer.writerow({k: row.get(k, "") for k in _CSV_FIELDS})
    return path


def write_glossary_md(terms: list[DefinedTerm], path: Path, *, title: str) -> Path:
    actors = [t for t in terms if (t.type or "") in _ACTOR_TYPES]
    concepts = [t for t in terms if (t.type or "") not in _ACTOR_TYPES]
    lines: list[str] = [
        f"# {title}\n",
        f"{len(terms)} termes définis : {len(actors)} acteurs/investisseurs/superviseurs, "
        f"{len(concepts)} concepts/objets.\n",
    ]
    for heading, group in (("Acteurs", actors), ("Concepts / objets", concepts)):
        lines.append(f"\n## {heading}\n")
        lines.append("| Base légale | Terme (EN) | Terme (FR) | Type | Renvois |")
        lines.append("|---|---|---|---|---|")
        for t in group:
            cites = " ; ".join(t.cites) or "—"
            lines.append(f"| {t.legal_basis} | {t.term_en} | {t.term_fr} | {t.type or '—'} | {cites} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_glossary(
    terms: list[DefinedTerm],
    out_dir: Path,
    *,
    source_id: str,
    title: str,
    yaml_header: str = "",
) -> dict[str, str]:
    """Écrit les trois sorties et renvoie leurs chemins."""
    yaml_p = write_glossary_yaml(terms, _yaml_path(out_dir, source_id), header=yaml_header)
    csv_p = write_glossary_csv(terms, out_dir / f"glossary_{source_id}.csv")
    md_p = write_glossary_md(terms, out_dir / f"glossary_{source_id}.md", title=title)
    return {"yaml": str(yaml_p), "csv": str(csv_p), "md": str(md_p)}
