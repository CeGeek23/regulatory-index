"""Load normative units (articles/paragraphs) from JSONL files."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class NormativeUnit(BaseModel):
    """One article, paragraph, or guideline section extracted from a regulatory source."""

    unit_id: str = Field(description="Stable id, e.g. 'AIFMD_L1#art_15_para_3'")
    source_id: str = Field(description="Document-level id, e.g. 'AIFMD_L1'")
    hierarchy_path: str = Field(
        description="Human-readable path, e.g. 'Article 15 > Paragraph 3 > Point (b)'"
    )
    text: str
    language: Literal["EN", "FR"]
    source_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="title, celex, level, issuer, url, article, paragraph, point, ...",
    )


def load_units_jsonl(path: Path) -> Iterator[NormativeUnit]:
    """Yield NormativeUnit objects line by line from a JSONL file."""
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data: dict[str, Any] = json.loads(line)
            yield NormativeUnit.model_validate(data)


def write_units_jsonl(units: list[NormativeUnit], path: Path) -> None:
    """Write a list of units to JSONL (utility for fixtures/tests)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(u.model_dump_json() + "\n")
