"""Idempotent runner: feed normative units to LangExtract via Ollama and persist outputs.

For each unit:
- If `data/obligations/{source_id}/{unit_id}.json` already exists, skip (idempotent reruns).
- Otherwise, call LangExtract, normalise the result into a UnitExtraction, persist JSON.
- Failures are logged to `data/obligations/_failed.jsonl` (one line per failure) and do NOT
  abort the run: the next unit is processed.

No regex, no fallback chain: one LangExtract call per unit, one disk write per outcome.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import langextract as lx

from ..ingestion.unit_loader import NormativeUnit
from ..schemas.raw import ExtractionMeta, RawObligation, UnitExtraction
from .examples_loader import load_examples
from .schema_builder import build_prompt_description

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunnerConfig:
    model_id: str = "mistral:7b"
    model_url: str = "http://localhost:11434"
    temperature: float = 0.0
    extraction_passes: int = 1
    fence_output: bool = True
    use_schema_constraints: bool = False
    request_timeout: int = 600  # seconds; default LangExtract value (120) too short on CPU


def _safe_path_segment(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(":", "_")


def output_path(out_dir: Path, unit: NormativeUnit) -> Path:
    """Return the JSON output path for a unit."""
    sub = out_dir / _safe_path_segment(unit.source_id)
    base = _safe_path_segment(unit.unit_id)
    return sub / f"{base}.json"


def _langextract_version() -> str | None:
    try:
        return version("langextract")
    except PackageNotFoundError:
        return None


def _to_raw_obligation(extraction: lx.data.Extraction) -> RawObligation:
    attrs: dict[str, Any] = dict(extraction.attributes or {})
    ci = extraction.char_interval
    if ci is None or ci.start_pos is None or ci.end_pos is None:
        raise ValueError("extraction has no usable char_interval (grounding missing)")
    alignment = (
        extraction.alignment_status.value
        if extraction.alignment_status is not None
        else None
    )
    return RawObligation(
        actor=str(attrs.get("actor", "")).strip(),
        action=str(attrs.get("action", "")).strip(),
        object=str(attrs.get("object", "")).strip(),
        theme=str(attrs.get("theme", "")).strip(),
        sub_theme=attrs.get("sub_theme"),
        condition=attrs.get("condition"),
        scope=attrs.get("scope"),
        exception=attrs.get("exception"),
        expected_evidence=list(attrs.get("expected_evidence") or []),
        associated_control=attrs.get("associated_control"),
        cited_references=list(attrs.get("cited_references") or []),
        verbatim_text=(extraction.extraction_text or "").strip(),
        char_interval=(ci.start_pos, ci.end_pos),
        alignment_status=alignment,
    )


def extract_unit(unit: NormativeUnit, config: RunnerConfig) -> UnitExtraction:
    """Run a single LangExtract call on one unit, return a UnitExtraction (may be empty)."""
    prompt = build_prompt_description(unit.language)
    examples = load_examples(unit.language)

    started = time.monotonic()
    result = lx.extract(
        text_or_documents=unit.text,
        prompt_description=prompt,
        examples=list(examples),
        model_id=config.model_id,
        model_url=config.model_url,
        fence_output=config.fence_output,
        use_schema_constraints=config.use_schema_constraints,
        extraction_passes=config.extraction_passes,
        temperature=config.temperature,
        language_model_params={"timeout": config.request_timeout},
    )
    elapsed = time.monotonic() - started

    # lx.extract is wrapped in __init__.py as `(*args: Any, **kwargs: Any)`, so
    # static checkers can't see its real return signature
    # (`AnnotatedDocument | list[AnnotatedDocument]`). We pass a single str so we
    # get the single-doc branch; force the narrowing with cast.
    doc = cast(lx.data.AnnotatedDocument, result)
    extractions: list[lx.data.Extraction] = list(doc.extractions or [])

    obligations: list[RawObligation] = []
    errors: list[str] = []
    for ex in extractions:
        try:
            obligations.append(_to_raw_obligation(ex))
        except (ValueError, KeyError) as e:
            errors.append(f"{type(e).__name__}: {e}")

    meta = ExtractionMeta(
        model_id=config.model_id,
        extraction_passes=config.extraction_passes,
        temperature=config.temperature,
        extracted_at=datetime.now(UTC),
        latency_seconds=round(elapsed, 2),
        langextract_version=_langextract_version(),
    )
    return UnitExtraction(unit=unit, obligations=obligations, extraction_meta=meta, errors=errors)


def _persist(extraction: UnitExtraction, out_dir: Path) -> Path:
    json_path = output_path(out_dir, extraction.unit)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(extraction.to_record_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return json_path


def _log_failure(unit: NormativeUnit, error: BaseException, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    failed_log = out_dir / "_failed.jsonl"
    record = {
        "unit_id": unit.unit_id,
        "source_id": unit.source_id,
        "language": unit.language,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "failed_at": datetime.now(UTC).isoformat(),
    }
    with failed_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(
    units: Iterable[NormativeUnit],
    out_dir: Path,
    config: RunnerConfig | None = None,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Process units sequentially. Returns counters: {processed, skipped, failed}."""
    config = config or RunnerConfig()
    counts = {"processed": 0, "skipped": 0, "failed": 0}

    # Reset the failure log so quality reports reflect only this run's failures.
    # A unit that failed previously then succeeded should not leave a phantom line.
    out_dir.mkdir(parents=True, exist_ok=True)
    failed_log = out_dir / "_failed.jsonl"
    if failed_log.exists():
        failed_log.unlink()

    for unit in units:
        json_path = output_path(out_dir, unit)
        if json_path.exists() and not force:
            log.info("skip (already extracted): %s", unit.unit_id)
            counts["skipped"] += 1
            continue

        try:
            extraction = extract_unit(unit, config)
        except Exception as e:
            log.exception("extraction failed for %s", unit.unit_id)
            _log_failure(unit, e, out_dir)
            counts["failed"] += 1
            continue

        _persist(extraction, out_dir)
        counts["processed"] += 1
        log.info(
            "extracted %s: %d obligation(s) in %.1fs",
            unit.unit_id,
            len(extraction.obligations),
            extraction.extraction_meta.latency_seconds,
        )

    return counts
