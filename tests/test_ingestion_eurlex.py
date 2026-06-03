"""Tests for the EUR-Lex HTML parser. Network calls are mocked / not exercised."""

from __future__ import annotations

from regulatory_index.ingestion.eurlex_fetcher import eurlex_url
from regulatory_index.ingestion.eurlex_html_parser import parse_articles


def test_eurlex_url_pattern() -> None:
    assert eurlex_url("32011L0061", "EN").endswith("CELEX:32011L0061")
    assert "/EN/" in eurlex_url("32011L0061", "EN")
    assert "/FR/" in eurlex_url("32011L0061", "fr")


_SAMPLE_HTML = """
<html><body><div class="eli-container">
  <div class="eli-subdivision" id="art_15">
    <p class="oj-ti-art">Article 15</p>
    <p class="oj-sti-art">Risk management</p>
    <div class="eli-subdivision" id="art_15.1">
      <p class="oj-normal">1. AIFMs shall functionally and hierarchically separate the functions of risk management from the operating units.</p>
    </div>
    <div class="eli-subdivision" id="art_15.2">
      <p class="oj-normal">2. AIFMs shall implement adequate risk management systems.</p>
    </div>
  </div>
  <div class="eli-subdivision" id="art_16">
    <p class="oj-ti-art">Article 16</p>
    <p class="oj-sti-art">Liquidity management</p>
    <div class="eli-subdivision" id="art_16.1">
      <p class="oj-normal">1. For each AIF, the AIFM shall employ an appropriate liquidity management system.</p>
    </div>
  </div>
  <div class="eli-subdivision" id="art_17">
    <p class="oj-ti-art">Article 17</p>
    <p class="oj-normal">Not in keep filter — should be excluded.</p>
  </div>
</div></body></html>
"""


def test_parse_articles_extracts_each_top_level_article() -> None:
    units = parse_articles(
        _SAMPLE_HTML,
        source_id="AIFMD_L1",
        celex="32011L0061",
        language="EN",
        title="Directive 2011/61/EU on AIFMs",
        level=1,
        issuer="EU_Parliament_Council",
        url="https://eur-lex.europa.eu/...",
    )
    assert len(units) == 3
    assert {u.source_meta["article"] for u in units} == {"15", "16", "17"}
    art15 = next(u for u in units if u.source_meta["article"] == "15")
    assert "Risk management" in art15.hierarchy_path
    assert "AIFMs shall functionally" in art15.text
    assert "implement adequate risk management" in art15.text
    # The article header is included once.
    assert art15.text.count("Risk management") == 1


def test_parse_articles_with_keep_filter() -> None:
    units = parse_articles(
        _SAMPLE_HTML,
        source_id="AIFMD_L1",
        celex="32011L0061",
        language="EN",
        title="t",
        level=1,
        issuer="EU_Parliament_Council",
        url="https://example.org",
        keep={"15", "16"},
    )
    assert {u.source_meta["article"] for u in units} == {"15", "16"}


def test_parse_articles_unit_id_includes_language() -> None:
    units_en = parse_articles(
        _SAMPLE_HTML,
        source_id="AIFMD_L1",
        celex="32011L0061",
        language="EN",
        title="t",
        level=1,
        issuer="EU_Parliament_Council",
        url="https://example.org",
        keep={"15"},
    )
    units_fr = parse_articles(
        _SAMPLE_HTML,
        source_id="AIFMD_L1",
        celex="32011L0061",
        language="FR",
        title="t",
        level=1,
        issuer="EU_Parliament_Council",
        url="https://example.org",
        keep={"15"},
    )
    assert units_en[0].unit_id == "AIFMD_L1#en#art_15"
    assert units_fr[0].unit_id == "AIFMD_L1#fr#art_15"


def test_parse_articles_skips_subdivisions() -> None:
    """Inner divs like art_15.1 are sub-paragraphs — not top-level articles."""
    units = parse_articles(
        _SAMPLE_HTML,
        source_id="AIFMD_L1",
        celex="32011L0061",
        language="EN",
        title="t",
        level=1,
        issuer="EU_Parliament_Council",
        url="https://example.org",
    )
    article_ids = {u.unit_id for u in units}
    assert not any(".1" in uid or ".2" in uid for uid in article_ids)
