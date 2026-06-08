from datetime import UTC, datetime

from regulatory_index.eval.metrics import compute, render_markdown
from regulatory_index.ingestion.unit_loader import NormativeUnit
from regulatory_index.schemas.obligation import Obligation
from regulatory_index.schemas.raw import ExtractionMeta, RawObligation, UnitExtraction
from regulatory_index.schemas.source import Source


def _unit_extraction() -> UnitExtraction:
    unit = NormativeUnit(
        unit_id="u1", source_id="AIFMD_L1", hierarchy_path="x", text="t", language="EN"
    )
    raw = RawObligation(
        actor="AIFM",
        action="establish",
        object="risk management framework",
        theme="Risk Management",
        verbatim_text="...",
        char_interval=(0, 5),
    )
    meta = ExtractionMeta(
        model_id="qwen2.5-7b-instruct",
        extraction_passes=1,
        temperature=0.0,
        extracted_at=datetime.now(UTC),
        latency_seconds=12.3,
    )
    return UnitExtraction(unit=unit, obligations=[raw], extraction_meta=meta)


def _obligation() -> Obligation:
    return Obligation(
        obligation_id="AIFMD-RISK-0001",
        actor="AIFM",
        action="establish",
        object="risk management framework",
        source=Source(
            source_id="AIFMD_L1#1",
            title="Directive 2011/61/EU on AIFMs",
            celex="32011L0061",
            level=1,
            issuer="EU_Parliament_Council",
            url="https://example.org",
            language="EN",
        ),
        theme="Risk Management",
        verbatim_text="...",
        char_interval=(0, 5),
        extraction_model="qwen2.5-7b-instruct",
        extracted_at=datetime.now(UTC),
    )


def test_compute_metrics() -> None:
    report = compute([_unit_extraction()], [_obligation()], failed_units=0)
    assert report.units_total == 1
    assert report.obligations_total == 1
    assert report.grounded_total == 1
    assert report.by_theme == {"Risk Management": 1}
    assert report.by_language == {"EN": 1}


def test_render_markdown_contains_key_sections() -> None:
    report = compute([_unit_extraction()], [_obligation()], failed_units=0)
    md = render_markdown(report)
    assert "# Quality report" in md
    assert "## By theme" in md
    assert "Risk Management" in md
