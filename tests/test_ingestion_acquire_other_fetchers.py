"""Tests for the AMF and Légifrance branches of acquire_one (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_index.ingestion import acquire as acquire_module
from regulatory_index.ingestion.acquire import ManifestEntry, acquire_one

_AMF_HTML = """
<html><body><main>
  <p>La société de gestion établit une fonction permanente de gestion des risques.</p>
  <p>Elle veille à ce que cette indépendance soit effective et démontrable.</p>
</main></body></html>
"""

_LEGIFRANCE_HTML = """
<html><body><div class="article-content">
  <p>Le dépositaire s'assure du suivi adéquat des flux de liquidités du FIA.</p>
</div></body></html>
"""


def _stub_amf_fetch(doc_code: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{doc_code}_stub.html"
    p.write_text(_AMF_HTML, encoding="utf-8")
    return p


def _stub_legifrance_fetch(article_id: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{article_id}_stub.html"
    p.write_text(_LEGIFRANCE_HTML, encoding="utf-8")
    return p


def test_acquire_one_amf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(acquire_module, "amf_fetch_to_disk", _stub_amf_fetch)
    entry = ManifestEntry(
        source_id="AMF_DOC_2014_06",
        fetcher="amf",
        celex=None,
        language="FR",
        filter_articles=None,
        doc_code="DOC-2014-06",
    )
    units = acquire_one(entry, raw_dir=tmp_path)
    assert len(units) == 1
    assert units[0].language == "FR"
    assert "fonction permanente" in units[0].text


def test_acquire_one_amf_requires_doc_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acquire_module, "amf_fetch_to_disk", _stub_amf_fetch)
    entry = ManifestEntry(
        source_id="AMF_DOC_2014_06",
        fetcher="amf",
        celex=None,
        language="FR",
        filter_articles=None,
        doc_code=None,
    )
    with pytest.raises(ValueError, match="amf fetcher requires doc_code"):
        acquire_one(entry, raw_dir=tmp_path)


def test_acquire_one_legifrance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(acquire_module, "legifrance_fetch_to_disk", _stub_legifrance_fetch)
    entry = ManifestEntry(
        source_id="CMF_FR",
        fetcher="legifrance",
        celex=None,
        language="FR",
        filter_articles=None,
        article_id="LEGIARTI000027780446",
        article_number="L. 214-24-8",
    )
    units = acquire_one(entry, raw_dir=tmp_path)
    assert len(units) == 1
    assert units[0].source_meta["article"] == "L. 214-24-8"
    assert units[0].source_meta["legifrance_id"] == "LEGIARTI000027780446"


def test_acquire_one_legifrance_requires_id_and_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acquire_module, "legifrance_fetch_to_disk", _stub_legifrance_fetch)
    entry = ManifestEntry(
        source_id="CMF_FR",
        fetcher="legifrance",
        celex=None,
        language="FR",
        filter_articles=None,
        article_id="LEGIARTI",
        article_number=None,
    )
    with pytest.raises(ValueError, match="legifrance fetcher requires"):
        acquire_one(entry, raw_dir=tmp_path)
