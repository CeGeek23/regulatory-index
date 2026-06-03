import langextract as lx

from regulatory_index.extraction.examples_loader import load_examples


def test_en_examples_load() -> None:
    examples = load_examples("EN")
    assert len(examples) >= 5
    first = examples[0]
    assert isinstance(first, lx.data.ExampleData)
    assert len(first.extractions) >= 1
    for ext in first.extractions:
        assert ext.extraction_class == "obligation"
        assert ext.extraction_text and ext.extraction_text in first.text


def test_fr_examples_load() -> None:
    examples = load_examples("FR")
    assert len(examples) >= 5
    for example in examples:
        for ext in example.extractions:
            assert ext.extraction_text and ext.extraction_text in example.text
            attrs = ext.attributes or {}
            assert {"actor", "action", "object", "theme"}.issubset(attrs.keys())


def test_examples_are_cached() -> None:
    assert load_examples("EN") is load_examples("EN")
