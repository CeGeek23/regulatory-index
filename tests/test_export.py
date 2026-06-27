from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from regulatory_index.export.csv_writer import write_csv
from regulatory_index.export.excel_writer import write_workbook
from regulatory_index.ingestion.unit_loader import NormativeUnit
from regulatory_index.linking.citation_extractor import resolve_all
from regulatory_index.linking.graph_builder import build_relations
from regulatory_index.materialize import (
    MaterializedIndex,
    by_theme,
    obligations_to_df,
    relations_to_df,
    units_to_df,
)
from regulatory_index.schemas.obligation import Obligation
from regulatory_index.schemas.source import Source


def _make_obligation(
    oid: str, theme: str = "Risk Management", language: Literal["EN", "FR"] = "EN"
) -> Obligation:
    return Obligation(
        obligation_id=oid,
        actor="AIFM",
        action="establish",
        object="risk management framework",
        source=Source(
            source_id=f"AIFMD_L1#{oid}",
            title="Directive 2011/61/EU on AIFMs",
            celex="32011L0061",
            level=1,
            issuer="EU_Parliament_Council",
            url="https://eur-lex.europa.eu/",
            language=language,
        ),
        theme=theme,
        verbatim_text="AIFMs shall establish a risk management function.",
        char_interval=(0, 49),
        cited_references=["Directive 2011/61/EU"],
        extraction_model="qwen2.5-7b-instruct",
        extracted_at=datetime.now(UTC),
    )


def _make_unit() -> NormativeUnit:
    return NormativeUnit(
        unit_id="AIFMD_L1#art_15",
        source_id="AIFMD_L1",
        hierarchy_path="Article 15",
        text="text",
        language="EN",
        source_meta={"celex": "32011L0061", "level": 1, "issuer": "EU_Parliament_Council"},
    )


def test_full_export_pipeline(tmp_path: Path) -> None:
    obligations = [
        _make_obligation("AIFMD-RISK-0001"),
        _make_obligation("AIFMD-GOV-0001", "Governance"),
    ]
    resolved, unresolved = resolve_all(obligations)
    relations = build_relations(obligations, resolved)
    units = [_make_unit()]

    materialized = MaterializedIndex(
        obligations=obligations,
        relations=relations,
        resolved_citations=resolved,
        unresolved_citations=unresolved,
        obligations_df=obligations_to_df(obligations),
        relations_df=relations_to_df(relations),
        units_df=units_to_df(units),
    )

    assert len(materialized.obligations_df) == 2
    themes = set(by_theme(materialized.obligations_df)["theme"].tolist())
    assert themes == {"Risk Management", "Governance"}

    excel_path = tmp_path / "out.xlsx"
    counts = write_workbook(materialized, excel_path)
    assert excel_path.exists() and excel_path.stat().st_size > 0
    assert counts["Obligations"] == 2

    csv_counts = write_csv(materialized, tmp_path)
    assert (tmp_path / "obligations.csv").exists()
    assert csv_counts["obligations"] == 2


def test_excel_export_with_mixed_optional_fields(tmp_path: Path) -> None:
    # Régression : un champ optionnel (condition) rempli sur une ligne, None sur l'autre.
    # En pandas la colonne mêle valeur et NaN -> xlsxwriter rejetait le NaN (TypeError).
    o1 = _make_obligation("AIFMD-RISK-0001").model_copy(update={"condition": "annually"})
    o2 = _make_obligation("AIFMD-RISK-0002")  # condition = None
    obligations = [o1, o2]
    materialized = MaterializedIndex(
        obligations=obligations,
        relations=[],
        resolved_citations=[],
        unresolved_citations=[],
        obligations_df=obligations_to_df(obligations),
        relations_df=relations_to_df([]),
        units_df=units_to_df([]),
    )
    out = tmp_path / "mixed.xlsx"
    counts = write_workbook(materialized, out)  # ne doit PAS lever
    assert out.exists() and out.stat().st_size > 0
    assert counts["Obligations"] == 2


def test_by_theme_merges_across_languages() -> None:
    # Meme theme canonique pour des obligations EN et FR -> une seule ligne agregee.
    obligations = [
        _make_obligation("AIFMD-RISK-0001", "Risk Management", language="EN"),
        _make_obligation("AIFMD-RISK-0002", "Risk Management", language="FR"),
    ]
    summary = by_theme(obligations_to_df(obligations))
    assert len(summary) == 1
    row = summary.iloc[0].to_dict()
    assert row["theme"] == "Risk Management"
    assert row["n"] == 2
