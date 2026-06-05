"""Tests du parseur HTML Légifrance. Les appels réseau ne sont pas sollicités."""

from __future__ import annotations

from regulatory_index.ingestion.legifrance_fetcher import legifrance_url, parse_article


def test_legifrance_url_pattern() -> None:
    url = legifrance_url("LEGIARTI000027780446")
    assert url.endswith("LEGIARTI000027780446")
    assert "legifrance.gouv.fr/codes/article_lc/" in url


_SAMPLE_HTML = """
<html><body>
  <header><nav><a href="/">menu</a></nav></header>
  <div class="article-content">
    <p>Le dépositaire d'un FIA s'assure que les flux de liquidités du FIA sont correctement suivis.</p>
    <p>Il veille à ce que tous les paiements effectués par les investisseurs lors de la souscription aient été reçus.</p>
    <li>Liste : un élément.</li>
  </div>
</body></html>
"""


def test_parse_article_extracts_body_paragraphs() -> None:
    units = parse_article(
        _SAMPLE_HTML,
        source_id="CMF_FR",
        article_id="LEGIARTI000027780446",
        article_number="L. 214-24-8",
        title="Code monétaire et financier (France)",
        level="national",
        issuer="FR_Legislator",
        url="https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027780446",
    )
    assert len(units) == 1
    unit = units[0]
    assert unit.unit_id == "CMF_FR#fr#art_L__214-24-8"
    assert unit.language == "FR"
    assert "dépositaire" in unit.text
    assert "flux de liquidités" in unit.text
    assert "souscription" in unit.text
    assert unit.source_meta["article"] == "L. 214-24-8"
    assert unit.source_meta["legifrance_id"] == "LEGIARTI000027780446"


def test_parse_article_falls_back_to_body_when_no_content_div() -> None:
    html = (
        "<html><body><p>"
        "Le dépositaire d'un FIA s'assure que les flux sont suivis correctement et que les paiements sont reçus."
        "</p></body></html>"
    )
    units = parse_article(
        html,
        source_id="CMF_FR",
        article_id="LEGIARTI",
        article_number="L. 1-1",
        title="t",
        level="national",
        issuer="FR_Legislator",
        url="https://example.org",
    )
    assert len(units) == 1
    assert "dépositaire" in units[0].text
