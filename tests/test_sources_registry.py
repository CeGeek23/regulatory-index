from regulatory_index.refdata.sources_registry import (
    load_alias_index,
    load_sources_registry,
)


def test_registry_has_expected_sources() -> None:
    reg = load_sources_registry()
    expected = {
        "AIFMD_L1",
        "AIFMD_L2",
        "ESMA_QA_AIFMD",
        "AMF_DOC_2014_06",
        "AMF_RG_LIVRE_IV",
    }
    assert expected <= set(reg.keys())
    aifmd_l1 = reg["AIFMD_L1"]
    assert aifmd_l1.level == 1
    assert aifmd_l1.celex == "32011L0061"


def test_alias_index_sorted_by_length_desc() -> None:
    pairs = load_alias_index()
    lengths = [len(a) for a, _ in pairs]
    assert lengths == sorted(lengths, reverse=True)
    # L'alias le plus long doit l'emporter sur les plus courts pour une même source.
    assert any("directive 2011/61/eu" in a for a, _ in pairs)
