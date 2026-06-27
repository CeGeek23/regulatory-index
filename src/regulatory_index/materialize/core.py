"""Matérialise les extractions persistées en DataFrames pandas en mémoire.

La source de vérité est les fichiers JSON dans `data/extractions/` (un par
NormativeUnit). À l'export, on les charge, on construit les Obligations, on
exécute le lieur de citations, et on transforme le tout en trois DataFrames
pandas consommés directement par les writers (Excel / CSV).

Pas de base persistante, pas de SQL — pandas suffit à notre échelle
(milliers d'obligations) et reste une dépendance unique.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ..ingestion.unit_loader import NormativeUnit
from ..linking.citation_extractor import (
    ResolvedCitation,
    UnresolvedCitation,
    resolve_all,
)
from ..linking.graph_builder import build_relations
from ..schemas.obligation import Obligation
from ..schemas.raw import UnitExtraction
from ..schemas.relation import CrossLevelRelation
from .builder import build_obligations

# ──────────────────────────────────────────────────────────────────────────────
# Colonnes — fixent la présence et l'ordre des colonnes, même DataFrame vide
# ──────────────────────────────────────────────────────────────────────────────

OBLIGATION_COLUMNS: list[str] = [
    "obligation_id", "source_id", "level", "issuer", "language", "celex", "article",
    "paragraph", "point", "actor", "action", "object", "theme", "sub_theme", "condition",
    "scope", "exception", "expected_evidence", "associated_control", "verbatim_text",
    "char_start", "char_end", "cited_references", "extraction_model", "extracted_at",
    "human_validated", "source_url", "source_title",
]

RELATION_COLUMNS: list[str] = [
    "source_obligation_id", "target_obligation_id", "relation_type", "citation_in_text",
    "evidence_text", "char_start", "char_end", "validated",
]

UNIT_COLUMNS: list[str] = [
    "unit_id", "source_id", "language", "hierarchy_path", "text_length", "celex",
    "level", "issuer", "article",
]


# ──────────────────────────────────────────────────────────────────────────────
# Chargeurs / convertisseurs
# ──────────────────────────────────────────────────────────────────────────────


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Remplace les valeurs manquantes (NaN/NA pandas) par None.

    Invariant attendu en aval : les writers testent `is not None` et xlsxwriter REJETTE NaN.
    En pandas, une colonne de chaînes optionnelle mêlant valeurs et manquants devient un dtype
    dont le manquant est `float('nan')` (≠ None) — d'où ce nettoyage à la construction.
    """
    cleaned: pd.DataFrame = df.astype(object).where(df.notna(), None)
    return cleaned


def load_unit_extractions_from_dir(obligations_dir: Path) -> list[UnitExtraction]:
    """Lit chaque `{source_id}/{unit_id}.json` produit par le runner."""
    out: list[UnitExtraction] = []
    for path in sorted(obligations_dir.glob("*/*.json")):
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        out.append(UnitExtraction.model_validate(payload))
    return out


def obligations_to_df(obligations: list[Obligation]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "obligation_id": o.obligation_id,
            "source_id": o.source.source_id.split("#")[0],
            "level": str(o.source.level),
            "issuer": o.source.issuer,
            "language": o.source.language,
            "celex": o.source.celex,
            "article": o.source.article,
            "paragraph": o.source.paragraph,
            "point": o.source.point,
            "actor": o.actor,
            "action": o.action,
            "object": o.object,
            "theme": o.theme,
            "sub_theme": o.sub_theme,
            "condition": o.condition,
            "scope": o.scope,
            "exception": o.exception,
            "expected_evidence": "; ".join(o.expected_evidence),
            "associated_control": o.associated_control,
            "verbatim_text": o.verbatim_text,
            "char_start": o.char_interval[0],
            "char_end": o.char_interval[1],
            "cited_references": "; ".join(o.cited_references),
            "extraction_model": o.extraction_model,
            "extracted_at": o.extracted_at.isoformat(),
            "human_validated": o.human_validated,
            "source_url": o.source.url,
            "source_title": o.source.title,
        }
        for o in obligations
    ]
    return _clean(pd.DataFrame(rows, columns=OBLIGATION_COLUMNS))


def relations_to_df(relations: list[CrossLevelRelation]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "source_obligation_id": r.source_obligation_id,
            "target_obligation_id": r.target_obligation_id,
            "relation_type": r.relation_type.value,
            "citation_in_text": r.citation_in_text,
            "evidence_text": r.evidence_text,
            "char_start": r.char_interval[0],
            "char_end": r.char_interval[1],
            "validated": r.validated,
        }
        for r in relations
    ]
    return _clean(pd.DataFrame(rows, columns=RELATION_COLUMNS))


def units_to_df(units: Iterable[NormativeUnit]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for u in units:
        meta = u.source_meta or {}
        rows.append(
            {
                "unit_id": u.unit_id,
                "source_id": u.source_id,
                "language": u.language,
                "hierarchy_path": u.hierarchy_path,
                "text_length": len(u.text),
                "celex": meta.get("celex"),
                "level": str(meta.get("level", "")),
                "issuer": meta.get("issuer"),
                "article": (
                    str(meta.get("article", "")) if meta.get("article") is not None else None
                ),
            }
        )
    return _clean(pd.DataFrame(rows, columns=UNIT_COLUMNS))


# ──────────────────────────────────────────────────────────────────────────────
# Matérialisation en un appel
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MaterializedIndex:
    """Vue entièrement matérialisée du corpus, en mémoire."""

    obligations: list[Obligation]
    relations: list[CrossLevelRelation]
    resolved_citations: list[ResolvedCitation]
    unresolved_citations: list[UnresolvedCitation]
    obligations_df: pd.DataFrame
    relations_df: pd.DataFrame
    units_df: pd.DataFrame


def materialize(unit_extractions: list[UnitExtraction]) -> MaterializedIndex:
    """Extractions JSON -> Obligations + Relations + DataFrames, en un seul appel."""
    obligations = build_obligations(unit_extractions)
    resolved, unresolved = resolve_all(obligations)
    relations = build_relations(obligations, resolved)
    return MaterializedIndex(
        obligations=obligations,
        relations=relations,
        resolved_citations=resolved,
        unresolved_citations=unresolved,
        obligations_df=obligations_to_df(obligations),
        relations_df=relations_to_df(relations),
        units_df=units_to_df([ue.unit for ue in unit_extractions]),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Agrégations utilisées par les feuilles de synthèse Excel
# ──────────────────────────────────────────────────────────────────────────────


def by_theme(obligations_df: pd.DataFrame) -> pd.DataFrame:
    # Les thèmes sont canonisés à la construction, donc on groupe sur le seul thème :
    # les variantes FR/EN d'un même thème fusionnent en une seule ligne.
    if obligations_df.empty:
        return pd.DataFrame(columns=["theme", "n"])
    counts = obligations_df.groupby("theme", dropna=False).size().reset_index(name="n")
    result: pd.DataFrame = counts.sort_values(
        ["n", "theme"], ascending=[False, True]
    ).reset_index(drop=True)
    return result


def by_actor(obligations_df: pd.DataFrame) -> pd.DataFrame:
    if obligations_df.empty:
        return pd.DataFrame(columns=["actor", "n"])
    counts = obligations_df.groupby("actor", dropna=False).size().reset_index(name="n")
    result: pd.DataFrame = counts.sort_values(
        ["n", "actor"], ascending=[False, True]
    ).reset_index(drop=True)
    return result


def actor_theme_matrix(obligations_df: pd.DataFrame) -> pd.DataFrame:
    if obligations_df.empty:
        return pd.DataFrame(columns=["actor", "theme", "n"])
    counts = obligations_df.groupby(["actor", "theme"], dropna=False).size().reset_index(name="n")
    result: pd.DataFrame = counts.sort_values(["actor", "theme"]).reset_index(drop=True)
    return result


def relations_summary(relations_df: pd.DataFrame) -> pd.DataFrame:
    if relations_df.empty:
        return pd.DataFrame(columns=["relation_type", "n"])
    counts = relations_df.groupby("relation_type", dropna=False).size().reset_index(name="n")
    result: pd.DataFrame = counts.sort_values("n", ascending=False).reset_index(drop=True)
    return result


def sources_view(obligations_df: pd.DataFrame) -> pd.DataFrame:
    """Tuples distincts (source_id, level, issuer, language, title, url) utilisés par Excel."""
    cols = ["source_id", "level", "issuer", "language", "source_title", "source_url"]
    if obligations_df.empty:
        return pd.DataFrame(columns=cols)
    result: pd.DataFrame = (
        obligations_df[cols].drop_duplicates().sort_values(["level", "source_id"]).reset_index(drop=True)
    )
    return result
