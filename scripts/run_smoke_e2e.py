"""Smoke test of the real Ollama-backed extraction path (no mocks).

Unlike tests/test_langextract_runner.py (which mocks `lx.extract`), this script
exercises the genuine extraction against a locally running Ollama. It is deliberately
NOT a pytest test: it needs `ollama serve` up with the model pulled, which is not
available in CI and is non-deterministic.

Run it manually after `ollama pull mistral:7b` and `ollama serve`:

    uv run python scripts/run_smoke_e2e.py
    uv run python scripts/run_smoke_e2e.py --model-id qwen2.5:7b

Exit code 0 if at least one grounded obligation is extracted, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys

from regulatory_index.extraction.langextract_runner import RunnerConfig, extract_unit
from regulatory_index.ingestion.unit_loader import NormativeUnit

_SAMPLE = NormativeUnit(
    unit_id="SMOKE_L1#en#art_15",
    source_id="SMOKE_L1",
    hierarchy_path="Article 15 > Paragraph 1",
    text=(
        "Article 15\n\n"
        "AIFMs shall functionally and hierarchically separate the functions of risk "
        "management from the operating units, including from the functions of portfolio "
        "management. AIFMs shall implement adequate risk management systems in order to "
        "identify, measure, manage and monitor appropriately all risks relevant to each "
        "AIF investment strategy and to which each AIF is or may be exposed."
    ),
    language="EN",
    source_meta={
        "title": "Directive 2011/61/EU on AIFMs",
        "celex": "32011L0061",
        "level": 1,
        "issuer": "EU_Parliament_Council",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "article": "15",
    },
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="mistral:7b")
    parser.add_argument("--model-url", default="http://localhost:11434")
    args = parser.parse_args()

    config = RunnerConfig(model_id=args.model_id, model_url=args.model_url)
    print(f"Running real extraction against Ollama ({config.model_id}) at {config.model_url} ...")
    extraction = extract_unit(_SAMPLE, config)

    grounded = sum(
        1 for ob in extraction.obligations if ob.char_interval[1] > ob.char_interval[0]
    )
    print(f"  obligations: {len(extraction.obligations)}  grounded: {grounded}")
    print(f"  latency: {extraction.extraction_meta.latency_seconds}s")
    for ob in extraction.obligations:
        ci = ob.char_interval
        print(f"   - {ob.actor} | {ob.action} | {ob.object}  [{ci[0]}:{ci[1]}]")
    if extraction.errors:
        print(f"  errors: {extraction.errors}")

    if grounded == 0:
        print("FAIL: no grounded obligation extracted.", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
