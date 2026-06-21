"""Tests unitaires du runner LangExtract, avec l'appel LLM mocke.

L'extraction reelle via LM Studio est testee separement dans scripts/run_smoke_e2e.py
et est trop lente / non deterministe pour la CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import langextract as lx
import pytest

from regulatory_index.extraction.langextract_runner import (
    RunnerConfig,
    _as_text,
    output_path,
    run,
)
from regulatory_index.ingestion.unit_loader import NormativeUnit


def test_as_text_skips_none_items() -> None:
    # Régression : le LLM peut renvoyer une liste commençant par None -> ne pas coercer en "None".
    assert _as_text([None, "AIFM"]) == "AIFM"
    assert _as_text([None, None]) == ""
    assert _as_text("establish") == "establish"
    assert _as_text(None) == ""


def _fake_annotated_doc(passage: str, hits: list[dict[str, Any]]) -> lx.data.AnnotatedDocument:
    extractions: list[lx.data.Extraction] = []
    for hit in hits:
        verbatim: str = hit["verbatim"]
        start = passage.index(verbatim)
        end = start + len(verbatim)
        extractions.append(
            lx.data.Extraction(
                extraction_class="obligation",
                extraction_text=verbatim,
                attributes=hit["attrs"],
                char_interval=lx.data.CharInterval(start_pos=start, end_pos=end),
                alignment_status=lx.data.AlignmentStatus.MATCH_EXACT,
            )
        )
    return lx.data.AnnotatedDocument(text=passage, extractions=extractions)


@pytest.fixture
def en_unit() -> NormativeUnit:
    return NormativeUnit(
        unit_id="AIFMD_L1#art_15_test",
        source_id="AIFMD_L1",
        hierarchy_path="Article 15 test",
        text="AIFMs shall establish a risk management function. The function shall review the policy annually.",
        language="EN",
    )


def test_extract_one_unit_persists_json(
    tmp_path: Path, en_unit: NormativeUnit, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_extract(*, text_or_documents: str, **_: Any) -> lx.data.AnnotatedDocument:
        return _fake_annotated_doc(
            text_or_documents,
            [
                {
                    "verbatim": "AIFMs shall establish a risk management function",
                    "attrs": {
                        "actor": "AIFM",
                        "action": "establish",
                        "object": "risk management framework",
                        "theme": "Risk Management",
                    },
                },
                {
                    "verbatim": "The function shall review the policy annually",
                    "attrs": {
                        "actor": "Risk Management Function",
                        "action": "review",
                        "object": "risk policy",
                        "theme": "Risk Management",
                        "condition": "annually",
                    },
                },
            ],
        )

    monkeypatch.setattr(lx, "extract", fake_extract)

    counts = run([en_unit], out_dir=tmp_path, config=RunnerConfig(model_id="mock"))
    assert counts == {"processed": 1, "skipped": 0, "failed": 0}

    json_path = output_path(tmp_path, en_unit)
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["unit"]["unit_id"] == en_unit.unit_id
    assert len(payload["obligations"]) == 2
    assert payload["obligations"][0]["actor"] == "AIFM"
    assert payload["obligations"][0]["char_interval"] == [0, len("AIFMs shall establish a risk management function")]


def test_idempotent_skip_when_json_exists(
    tmp_path: Path, en_unit: NormativeUnit, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_path = output_path(tmp_path, en_unit)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text("{}", encoding="utf-8")  # simule une extraction deja faite

    def boom(**_: Any) -> Any:
        raise AssertionError("lx.extract should not have been called when output exists")

    monkeypatch.setattr(lx, "extract", boom)
    counts = run([en_unit], out_dir=tmp_path)
    assert counts == {"processed": 0, "skipped": 1, "failed": 0}


def test_failure_is_logged_and_does_not_abort(
    tmp_path: Path, en_unit: NormativeUnit, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_extract(*, text_or_documents: str, **_: Any) -> lx.data.AnnotatedDocument:
        # La premiere unite echoue, la seconde reussit.
        if text_or_documents.startswith("AIFMs"):
            raise RuntimeError("backend unreachable")
        return _fake_annotated_doc(
            text_or_documents,
            [
                {
                    "verbatim": "Other obligation text",
                    "attrs": {
                        "actor": "AIFM",
                        "action": "monitor",
                        "object": "x",
                        "theme": "Risk Management",
                    },
                }
            ],
        )

    other_with_match = en_unit.model_copy(
        update={"unit_id": "AIFMD_L1#art_16_test", "text": "Other obligation text here"}
    )
    monkeypatch.setattr(lx, "extract", fake_extract)
    counts = run([en_unit, other_with_match], out_dir=tmp_path)
    assert counts == {"processed": 1, "skipped": 0, "failed": 1}
    assert (tmp_path / "_failed.jsonl").exists()
    line = (tmp_path / "_failed.jsonl").read_text(encoding="utf-8").strip()
    failed_record = json.loads(line)
    assert failed_record["unit_id"] == en_unit.unit_id
    assert failed_record["error_type"] == "RuntimeError"
