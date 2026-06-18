"""Tests du sommaire (table des matières) — HTML inline, pas de réseau."""

from __future__ import annotations

from regulatory_index.glossary import build_toc

_SAMPLE_HTML = """
<html><body>
  <p class="oj-ti-section-1">CHAPTER I</p>
  <p class="oj-ti-section-2">GENERAL PROVISIONS</p>
  <div class="eli-subdivision" id="art_1">
    <p class="oj-ti-art">Article 1</p>
    <p class="oj-sti-art">Subject matter</p>
  </div>
  <div class="eli-subdivision" id="art_2">
    <p class="oj-ti-art">Article 2</p>
    <p class="oj-sti-art">Definitions</p>
  </div>
  <p class="oj-ti-section-1">CHAPTER II</p>
  <p class="oj-ti-section-2">AUTHORISATION</p>
  <div class="eli-subdivision" id="art_3">
    <p class="oj-ti-art">Article 3</p>
    <p class="oj-sti-art">Conditions</p>
  </div>
</body></html>
"""


def test_build_toc_structure() -> None:
    toc = build_toc(_SAMPLE_HTML, source_id="TEST", language="EN")
    assert toc.source_id == "TEST"
    assert len(toc.sections) == 2
    assert toc.sections[0].label == "CHAPTER I"
    assert toc.sections[0].title == "GENERAL PROVISIONS"
    assert toc.article_count == 3
    assert [a.article for a in toc.iter_articles()] == ["1", "2", "3"]


def test_build_toc_detects_definitions_article() -> None:
    toc = build_toc(_SAMPLE_HTML, source_id="TEST", language="EN")
    assert toc.definitions_article == "2"
    definitions = [a for a in toc.iter_articles() if a.is_definitions]
    assert len(definitions) == 1
    assert definitions[0].article == "2"
