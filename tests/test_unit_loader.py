from pathlib import Path

from regulatory_index.ingestion.unit_loader import (
    NormativeUnit,
    load_units_jsonl,
    write_units_jsonl,
)


def test_round_trip_jsonl(tmp_path: Path) -> None:
    units = [
        NormativeUnit(
            unit_id="AIFMD_L1#art_15",
            source_id="AIFMD_L1",
            hierarchy_path="Article 15",
            text="AIFMs shall...",
            language="EN",
            source_meta={"celex": "32011L0061", "level": 1},
        ),
        NormativeUnit(
            unit_id="AMF_DOC_2014_06#1",
            source_id="AMF_DOC_2014_06",
            hierarchy_path="Section 1",
            text="La société de gestion...",
            language="FR",
            source_meta={"issuer": "AMF"},
        ),
    ]
    path = tmp_path / "units.jsonl"
    write_units_jsonl(units, path)
    loaded = list(load_units_jsonl(path))
    assert loaded == units


def test_skip_blank_lines(tmp_path: Path) -> None:
    content = (
        '{"unit_id":"u1","source_id":"s","hierarchy_path":"h","text":"t","language":"EN"}\n'
        "\n"
        '{"unit_id":"u2","source_id":"s","hierarchy_path":"h","text":"t","language":"FR"}\n'
    )
    path = tmp_path / "units.jsonl"
    path.write_text(content, encoding="utf-8")
    loaded = list(load_units_jsonl(path))
    assert [u.unit_id for u in loaded] == ["u1", "u2"]
