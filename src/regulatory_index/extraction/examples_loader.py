"""Load few-shot examples from prompts/examples_*.yaml and convert to LangExtract objects."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any, Literal

import langextract as lx
import yaml

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def _build_extraction(passage: str, raw: dict[str, Any]) -> lx.data.Extraction:
    verbatim: str = raw["verbatim"]
    if verbatim not in passage:
        raise ValueError(
            f"verbatim is not a literal substring of the example passage:\n  {verbatim!r}"
        )
    attributes = {k: v for k, v in raw.items() if k != "verbatim"}
    return lx.data.Extraction(
        extraction_class="obligation",
        extraction_text=verbatim,
        attributes=attributes,
    )


@cache
def load_examples(language: Literal["EN", "FR"]) -> tuple[lx.data.ExampleData, ...]:
    """Return immutable few-shot examples for the given language."""
    fname = "examples_en.yaml" if language == "EN" else "examples_fr.yaml"
    path = PROMPTS_DIR / fname
    with path.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f) or []

    examples: list[lx.data.ExampleData] = []
    for item in raw:
        text: str = item["text"]
        extractions = [_build_extraction(text, e) for e in item.get("extractions", [])]
        examples.append(lx.data.ExampleData(text=text, extractions=extractions))
    return tuple(examples)
