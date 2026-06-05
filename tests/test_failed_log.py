"""Vérifie que _failed.jsonl est réinitialisé au début de chaque appel à run()."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import langextract as lx
import pytest

from regulatory_index.extraction.langextract_runner import RunnerConfig, run
from regulatory_index.ingestion.unit_loader import NormativeUnit


def _ok_extract(*, text_or_documents: str, **_: Any) -> lx.data.AnnotatedDocument:
    return lx.data.AnnotatedDocument(text=text_or_documents, extractions=[])


def test_failed_log_is_reset_each_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed_log = tmp_path / "_failed.jsonl"
    # Injecte une entrée d'échec obsolète issue d'une exécution précédente.
    failed_log.write_text('{"unit_id":"old_phantom","error":"stale"}\n', encoding="utf-8")
    assert failed_log.exists()

    monkeypatch.setattr(lx, "extract", _ok_extract)
    unit = NormativeUnit(
        unit_id="u_new",
        source_id="S",
        hierarchy_path="x",
        text="Some text",
        language="EN",
    )
    counts = run([unit], out_dir=tmp_path, config=RunnerConfig(model_id="mock"))
    assert counts["failed"] == 0
    # L'entrée fantôme obsolète doit avoir disparu.
    assert not failed_log.exists()
