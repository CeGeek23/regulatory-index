"""Tests du parseur HTML AMF. Les appels réseau ne sont pas sollicités."""

from __future__ import annotations

from regulatory_index.ingestion.amf_fetcher import amf_url, parse_doctrine


def test_amf_url_pattern() -> None:
    assert amf_url("DOC-2014-06").endswith("doc-2014-06")
    assert amf_url("DOC-2014-06").startswith("https://www.amf-france.org/")


_SAMPLE_HTML = """
<html><body>
  <header>
    <nav>
      <a href="/">Accueil</a>
      <a href="/menu">Menu</a>
    </nav>
  </header>
  <main>
    <h2>1. Indépendance de la fonction de gestion des risques</h2>
    <p>La société de gestion établit une fonction permanente de gestion des risques, hiérarchiquement et fonctionnellement indépendante des unités opérationnelles.</p>
    <h3>1.1 Indicateurs d'indépendance</h3>
    <p>La société de gestion veille à ce que cette indépendance soit effective et démontrable.</p>
    <li>Short link</li>
  </main>
  <footer>
    <p>© AMF</p>
  </footer>
</body></html>
"""


def test_parse_doctrine_produces_one_unit() -> None:
    units = parse_doctrine(
        _SAMPLE_HTML,
        source_id="AMF_DOC_2014_06",
        doc_code="DOC-2014-06",
        title="Position-recommandation AMF DOC-2014-06 — Guide AIFM",
        level="national",
        issuer="AMF",
        url="https://www.amf-france.org/fr/reglementation/doctrine/doc-2014-06",
    )
    assert len(units) == 1
    unit = units[0]
    assert unit.unit_id == "AMF_DOC_2014_06#fr#full"
    assert unit.language == "FR"
    assert unit.source_id == "AMF_DOC_2014_06"
    # Paragraphes opérationnels inclus, en-tête/pied de page ignorés.
    assert "fonction permanente de gestion des risques" in unit.text
    assert "indépendance soit effective" in unit.text
    # Les courts extraits et liens de navigation doivent être filtrés par la règle >20 caractères.
    assert "Short link" not in unit.text


def test_parse_doctrine_returns_empty_when_no_main_content() -> None:
    """Un body vide doit produire zéro unité plutôt que lever une exception."""
    units = parse_doctrine(
        "<html><head></head><body></body></html>",
        source_id="AMF_DOC_2014_06",
        doc_code="DOC-2014-06",
        title="t",
        level="national",
        issuer="AMF",
        url="https://example.org",
    )
    assert units == []
