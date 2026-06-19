"""Tests du moissonnage des termes définis — texte/HTML inline, pas de réseau."""

from __future__ import annotations

from regulatory_index.glossary import harvest_glossary, parse_points

# Guillemets EUR-Lex via code points (évite l'ambiguïté unicode signalée par ruff).
EN_O, EN_C = chr(0x2018), chr(0x2019)
FR_O, FR_C = chr(0x00AB), chr(0x00BB)


def _en_text() -> str:
    return "\n".join(
        [
            "Article 2 — Definitions",
            "",
            "1. For the purposes of this Regulation:",
            "(a)",
            f"{EN_O}alpha{EN_C} means the first letter;",
            "(b)",
            f"{EN_O}beta{EN_C} means the second letter, as defined in AIFMD;",
            "(c)",
            f"{EN_O}gamma{EN_C} means the third letter;",
            "2. This trailing paragraph must NOT be absorbed into point (c).",
        ]
    )


def test_parse_points_letter_style_and_paragraph_boundary() -> None:
    points = parse_points(_en_text(), language="EN")
    assert [p.label for p in points] == ["a", "b", "c"]
    assert points[0].term == "alpha"
    assert points[1].term == "beta"
    # Régression : le dernier point ne doit pas absorber le paragraphe 2.
    assert "trailing paragraph" not in points[-1].definition
    assert points[-1].definition.endswith("the third letter;")


def test_parse_points_number_style() -> None:
    text = "\n".join(
        [
            "Article 4",
            "1. For the purposes:",
            "(1)",
            f"{EN_O}one{EN_C} means 1;",
            "(2)",
            f"{EN_O}two{EN_C} means 2;",
        ]
    )
    points = parse_points(text, language="EN")
    assert [p.label for p in points] == ["1", "2"]
    assert points[0].term == "one"


def _html(language: str, lang_open: str, lang_close: str, *, terms: list[tuple[str, str, str]]) -> str:
    rows = []
    for label, term, tail in terms:
        marker = f"({label})" if language == "EN" else f"{label})"
        rows.append(f'<p class="oj-normal">{marker}</p>')
        rows.append(f'<p class="oj-normal">{lang_open}{term}{lang_close} {tail}</p>')
    points = "\n".join(rows)
    return f"""
    <html><body>
      <div class="eli-subdivision" id="art_2">
        <p class="oj-ti-art">Article 2</p>
        <p class="oj-sti-art">Definitions</p>
        <p class="oj-normal">1. For the purposes of this Regulation:</p>
        {points}
      </div>
    </body></html>
    """


def test_harvest_glossary_bilingual() -> None:
    html_en = _html("EN", EN_O, EN_C, terms=[("a", "alpha", "means X"), ("b", "beta", "means Y")])
    html_fr = _html("FR", FR_O, FR_C, terms=[("a", "alpha_fr", "signifie X"), ("b", "beta_fr", "signifie Y")])
    terms = harvest_glossary(html_en, html_fr, source_id="TEST", celex="123")
    assert len(terms) == 2
    by_label = {t.label: t for t in terms}
    assert by_label["a"].term_en == "alpha"
    assert by_label["a"].term_fr == "alpha_fr"
    assert by_label["a"].legal_basis == "TEST Art. 2(1)(a)"
    # Sans override : extraction OK, mais type/cites non devinés.
    assert by_label["a"].type is None
    assert by_label["a"].cites == []


def test_parse_points_unlabelled_consolidated() -> None:
    """Versions consolidées : définitions sans étiquette -> étiquettes synthétiques séquentielles."""
    text = "\n".join(
        [
            "Article 2",
            "For the purposes of this Directive the following definitions apply:",
            f"{EN_O}alpha{EN_C} means the first letter;",
            f"{EN_O}beta{EN_C} means the second letter;",
            f"{EN_O}gamma{EN_C} means the third letter;",
        ]
    )
    points = parse_points(text, language="EN")
    assert [p.label for p in points] == ["a", "b", "c"]
    assert [p.term for p in points] == ["alpha", "beta", "gamma"]


def test_harvest_glossary_en_only() -> None:
    """FR optionnel : un acte sans version FR sous la main produit quand même son glossaire."""
    html_en = _html("EN", EN_O, EN_C, terms=[("a", "alpha", "means a body")])
    terms = harvest_glossary(html_en, source_id="TEST")
    assert len(terms) == 1
    assert terms[0].term_en == "alpha"
    assert terms[0].term_fr == ""


def test_harvest_glossary_tolerates_unparsable_fr() -> None:
    """FR illisible (article de définitions absent) : EN seul, jamais d'exception."""
    html_en = _html("EN", EN_O, EN_C, terms=[("a", "alpha", "means X")])
    terms = harvest_glossary(html_en, "<html><body><p>rien d'utile</p></body></html>", source_id="TEST")
    assert len(terms) == 1
    assert terms[0].term_en == "alpha"
    assert terms[0].term_fr == ""


def test_harvest_glossary_applies_overrides() -> None:
    html_en = _html("EN", EN_O, EN_C, terms=[("a", "alpha", "means X")])
    html_fr = _html("FR", FR_O, FR_C, terms=[("a", "alpha_fr", "signifie X")])
    overrides = {"a": {"id": "custom_id", "type": "actor", "cites": ["Directive 2009/65/EC"]}}
    terms = harvest_glossary(html_en, html_fr, source_id="TEST", overrides=overrides)
    assert terms[0].term_id == "custom_id"
    assert terms[0].type == "actor"
    assert terms[0].cites == ["Directive 2009/65/EC"]
