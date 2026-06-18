from datetime import UTC, datetime
from typing import Literal

from regulatory_index.ingestion.unit_loader import NormativeUnit
from regulatory_index.materialize.builder import build_obligations, collect_vocab_gaps
from regulatory_index.schemas.raw import ExtractionMeta, RawObligation, UnitExtraction


def _ue(
    unit_id: str,
    source_id: str,
    obligations: list[RawObligation],
    language: Literal["EN", "FR"] = "EN",
) -> UnitExtraction:
    unit = NormativeUnit(
        unit_id=unit_id,
        source_id=source_id,
        hierarchy_path="x",
        text="t",
        language=language,
        source_meta={"celex": "32011L0061", "level": 1, "issuer": "EU_Parliament_Council"},
    )
    meta = ExtractionMeta(
        model_id="qwen2.5-7b-instruct",
        extraction_passes=1,
        temperature=0.0,
        extracted_at=datetime.now(UTC),
        latency_seconds=1.0,
    )
    return UnitExtraction(unit=unit, obligations=obligations, extraction_meta=meta)


def _raw(theme: str, char_start: int = 0, actor: str = "AIFM") -> RawObligation:
    return RawObligation(
        actor=actor,
        action="establish",
        object="risk management framework",
        theme=theme,
        verbatim_text="AIFMs shall establish risk management framework",
        char_interval=(char_start, char_start + 10),
    )


def test_ids_assigned_per_theme_with_codes() -> None:
    obligations = build_obligations(
        [
            _ue("u1", "AIFMD_L1", [_raw("Risk Management", 0), _raw("Risk Management", 100)]),
            _ue("u2", "AIFMD_L1", [_raw("Governance", 0)]),
        ]
    )
    ids = [o.obligation_id for o in obligations]
    assert any(i.startswith("AIFMD-RISK-") for i in ids)
    assert any(i.startswith("AIFMD-GOV-") for i in ids)
    # Deux obligations de risque -> ids 0001 et 0002
    risk_ids = sorted(i for i in ids if i.startswith("AIFMD-RISK-"))
    assert risk_ids[0].endswith("0001")
    assert risk_ids[1].endswith("0002")


def test_source_populated_from_registry_for_known_source_id() -> None:
    obligations = build_obligations(
        [_ue("u1", "AIFMD_L1", [_raw("Risk Management")])]
    )
    src = obligations[0].source
    assert src.celex == "32011L0061"
    assert src.level == 1
    assert src.issuer == "EU_Parliament_Council"
    assert "eur-lex.europa.eu" in src.url


def test_ids_are_deterministic_across_runs() -> None:
    ues = [_ue("u1", "AIFMD_L1", [_raw("Risk Management", 50), _raw("Risk Management", 10)])]
    a = [o.obligation_id for o in build_obligations(ues)]
    b = [o.obligation_id for o in build_obligations(ues)]
    assert a == b


def test_fr_values_canonicalize_to_english_pivot() -> None:
    # Les formes de surface FR doivent se réduire aux mêmes libellés canoniques que leurs jumeaux EN.
    obligations = build_obligations(
        [
            _ue(
                "u1",
                "AIFMD_L1",
                [_raw("Gestion des Risques", actor="Gestionnaire de FIA")],
                language="FR",
            )
        ]
    )
    obl = obligations[0]
    assert obl.theme == "Risk Management"
    assert obl.actor == "AIFM"
    assert obl.obligation_id.startswith("AIFMD-RISK-")


def test_off_vocab_value_kept_verbatim_and_reported() -> None:
    extractions = [_ue("u1", "AIFMD_L1", [_raw("Quantum Compliance")])]
    obligations = build_obligations(extractions)
    # Le thème inconnu est conservé (pas d'abandon silencieux) et regroupé sous le code MISC.
    assert obligations[0].theme == "Quantum Compliance"
    assert obligations[0].obligation_id.startswith("AIFMD-MISC-")
    gaps = collect_vocab_gaps(extractions)
    assert ("Quantum Compliance", 1) in gaps["theme"]
