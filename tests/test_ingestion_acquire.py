"""Tests de l'orchestrateur acquire. Le fetcher est monkeypatché (pas de réseau)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from regulatory_index.ingestion import acquire as acquire_module
from regulatory_index.ingestion.acquire import (
    ManifestEntry,
    acquire_all,
    acquire_one,
    load_manifest,
)

_FAKE_HTML = """<html><body><div class="eli-container">
  <div class="eli-subdivision" id="art_42">
    <p class="oj-ti-art">Article 42</p>
    <p class="oj-sti-art">Some topic</p>
    <p class="oj-normal">The AIFM shall do something.</p>
  </div>
</div></body></html>"""


def _stub_fetch_to_disk(celex: str, language: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{celex}_{language}_stub.html"
    path.write_text(_FAKE_HTML, encoding="utf-8")
    return path


def test_load_manifest_reads_yaml() -> None:
    entries = load_manifest()
    assert len(entries) >= 1
    first = entries[0]
    assert first.source_id
    assert first.fetcher in {"eurlex", "amf", "legifrance"}


def test_acquire_one_eurlex_filters_articles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acquire_module, "eurlex_fetch_to_disk", _stub_fetch_to_disk)
    entry = ManifestEntry(
        source_id="AIFMD_L1",
        fetcher="eurlex",
        celex="32011L0061",
        language="EN",
        filter_articles=("42",),
    )
    units = acquire_one(entry, raw_dir=tmp_path)
    assert len(units) == 1
    assert units[0].source_meta["article"] == "42"
    assert units[0].language == "EN"


def test_acquire_one_unknown_source_id_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acquire_module, "eurlex_fetch_to_disk", _stub_fetch_to_disk)
    entry = ManifestEntry(
        source_id="NOT_IN_REGISTRY",
        fetcher="eurlex",
        celex="X",
        language="EN",
        filter_articles=None,
    )
    with pytest.raises(ValueError, match="not in sources_registry"):
        acquire_one(entry, raw_dir=tmp_path)


def test_acquire_one_unknown_fetcher_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = ManifestEntry(
        source_id="AIFMD_L1",
        fetcher="ftp",  # non supporté
        celex="32011L0061",
        language="EN",
        filter_articles=None,
    )
    with pytest.raises(NotImplementedError):
        acquire_one(entry, raw_dir=tmp_path)


def test_acquire_all_writes_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acquire_module, "eurlex_fetch_to_disk", _stub_fetch_to_disk)
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        "- source_id: AIFMD_L1\n"
        "  fetcher: eurlex\n"
        '  celex: "32011L0061"\n'
        "  language: EN\n"
        "  filter_articles: [\"42\"]\n",
        encoding="utf-8",
    )
    out = tmp_path / "units.jsonl"
    counts: dict[str, Any] = acquire_all(
        manifest_path=manifest_path, raw_dir=tmp_path / "raw", units_out=out
    )
    assert counts["units"] == 1
    assert counts["failed"] == 0
    assert out.exists()
    assert out.read_text(encoding="utf-8").strip()
