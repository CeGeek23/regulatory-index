from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regulatory_index.refdata.vocab import (
    load_acronyms,
    load_all_vocabularies,
    load_vocabulary,
)
from regulatory_index.schemas import (
    CrossLevelRelation,
    CrossLevelRelationType,
    Obligation,
    Source,
)


def _dummy_source() -> Source:
    return Source(
        source_id="AIFMD_L1#art_15",
        title="Directive 2011/61/EU",
        celex="32011L0061",
        level=1,
        issuer="EU_Parliament_Council",
        url="https://example.org",
        language="EN",
    )


def test_source_round_trip() -> None:
    src = Source(
        source_id="AIFMD_L1#art_15_para_3",
        title="Directive 2011/61/EU",
        celex="32011L0061",
        level=1,
        issuer="EU_Parliament_Council",
        article="15",
        paragraph="3",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        language="EN",
    )
    restored = Source.model_validate_json(src.model_dump_json())
    assert restored == src


def test_obligation_requires_grounding() -> None:
    # char_interval est requis ; l'omettre via model_validate déclenche
    # la validation Pydantic tout en contournant le vérificateur de types statique.
    payload = {
        "obligation_id": "AIFMD-RISK-0001",
        "actor": "AIFM",
        "action": "establish",
        "object": "risk management framework",
        "source": _dummy_source().model_dump(mode="json"),
        "theme": "Risk Management",
        "verbatim_text": "AIFMs shall establish ...",
        "extraction_model": "qwen2.5-7b-instruct",
        "extracted_at": datetime.now(UTC).isoformat(),
    }
    with pytest.raises(ValidationError):
        Obligation.model_validate(payload)


def test_obligation_id_pattern() -> None:
    with pytest.raises(ValidationError):
        Obligation(
            obligation_id="bad-id",
            actor="AIFM",
            action="establish",
            object="risk management framework",
            source=_dummy_source(),
            theme="Risk Management",
            verbatim_text="...",
            char_interval=(0, 10),
            extraction_model="qwen2.5-7b-instruct",
            extracted_at=datetime.now(UTC),
        )


def test_relation_round_trip() -> None:
    rel = CrossLevelRelation(
        source_obligation_id="AIFMD-RISK-0042",
        target_obligation_id="AIFMD-RISK-0001",
        relation_type=CrossLevelRelationType.CLARIFIES,
        evidence_text="This Guideline clarifies Article 15 of AIFMD.",
        citation_in_text="Article 15 of Directive 2011/61/EU",
        char_interval=(0, 36),
    )
    assert rel.relation_type is CrossLevelRelationType.CLARIFIES


def test_vocabularies_load() -> None:
    vocabs = load_all_vocabularies()
    expected = {"actors", "actions", "objects", "themes", "conditions", "relation_types"}
    assert expected <= vocabs.keys()
    actors = load_vocabulary("actors")
    assert "aifm" in actors.ids
    assert "AIFM" in actors.canonical_values("EN")
    assert "Gestionnaire de FIA" in actors.canonical_values("FR")


def test_acronyms_load() -> None:
    acronyms = load_acronyms()
    shorts = {a.short for a in acronyms}
    assert {"AIFM", "NAV", "ManCo", "RTS", "ESMA", "AMF", "RCCI"} <= shorts
