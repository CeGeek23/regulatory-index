"""Test du chargement du manifeste de corpus."""

from __future__ import annotations

from regulatory_index.ingestion.manifest import load_manifest


def test_load_manifest_reads_yaml() -> None:
    entries = load_manifest()
    assert len(entries) >= 1
    first = entries[0]
    assert first.source_id
    assert first.celex
    assert first.language in {"EN", "FR"}
