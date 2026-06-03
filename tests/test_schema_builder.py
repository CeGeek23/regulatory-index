from regulatory_index.extraction.schema_builder import build_prompt_description


def test_en_prompt_contains_vocab_and_acronyms() -> None:
    prompt = build_prompt_description("EN")
    assert "senior compliance officer" in prompt
    assert "AIFM" in prompt
    assert "Depositary" in prompt
    assert "Risk Management" in prompt
    assert "ManCo = Management Company" in prompt
    assert "verbatim" in prompt.lower()


def test_fr_prompt_contains_vocab_and_acronyms() -> None:
    prompt = build_prompt_description("FR")
    assert "responsable conformité" in prompt
    assert "Gestionnaire de FIA" in prompt
    assert "Dépositaire" in prompt
    assert "Gestion des Risques" in prompt
    assert "RCCI" in prompt
    assert "littéral" in prompt.lower()


def test_prompts_are_cached() -> None:
    assert build_prompt_description("EN") is build_prompt_description("EN")
    assert build_prompt_description("EN") != build_prompt_description("FR")
