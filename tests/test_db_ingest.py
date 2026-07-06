"""Tests des règles pures d'ingestion `regindex` (aucune base requise).

Conformément au principe projet, les cas sont des extraits RÉELS des deux actes
(AIFMD 32011L0061 v4060, DR231 32013R0231 v3336) copiés en fixtures inline : découpe
en phrases déterministe, construction d'id stable, aplatissement points/subpoints,
exclusion des notes de bas de page, et logique de merge idempotente.
"""

from __future__ import annotations

from regulatory_index.db.ingest import (
    Subdivision,
    build_article_units,
    build_source_unit_id,
    inline_label,
    plan_merge,
    source_text_hash,
    split_sentences,
)

# === split_sentences (règle générale, sans regex) ==========================


def test_splits_on_period_then_uppercase() -> None:
    text = "First sentence here. Second sentence here."
    assert split_sentences(text) == ["First sentence here.", "Second sentence here."]


def test_reference_with_digits_is_not_a_false_boundary() -> None:
    # '2011/61/EU.' termine bien une phrase (suivi d'une majuscule) ; la date interne ne coupe pas.
    text = "This supplements Directive 2011/61/EU. The Commission shall act."
    assert split_sentences(text) == [
        "This supplements Directive 2011/61/EU.",
        "The Commission shall act.",
    ]


def test_dates_and_lowercase_do_not_split() -> None:
    # '17.11.2009' (chiffres) et 'p. 1.' (fin) — aucune frontière : 1 seule phrase.
    text = "See OJ L 302, 17.11.2009, p. 1."
    assert split_sentences(text) == [text]


def test_semicolon_never_splits_even_before_uppercase() -> None:
    # ';' est un séparateur de liste juridique, jamais une frontière de phrase.
    assert split_sentences("the first item; The second item") == ["the first item; The second item"]


def test_abbreviation_followed_by_digit_does_not_split() -> None:
    assert split_sentences("Art. 15 shall apply") == ["Art. 15 shall apply"]


# === inline_label / build_source_unit_id ===================================


def test_inline_label_extracts_between_parentheses() -> None:
    assert inline_label("(a) implement a policy") == "a"
    assert inline_label("(10) OJ L 302") == "10"
    assert inline_label("(iii) something") == "iii"
    assert inline_label("no parenthesis") is None


def test_source_unit_id_matches_client_example() -> None:
    assert (
        build_source_unit_id("32011L0061", "15", "1", None, None, "1")
        == "SU-32011L0061-ART15-P1-S01"
    )


def test_source_unit_id_zero_pads_sentence_and_uppercases_labels() -> None:
    assert (
        build_source_unit_id("32013R0231", "1", "1", "a", None, "3")
        == "SU-32013R0231-ART1-P1-PTA-S03"
    )
    assert (
        build_source_unit_id("32011L0061", "15", "1", "a", "i", "1")
        == "SU-32011L0061-ART15-P1-PTA-SPTI-S01"
    )


def test_source_unit_id_keeps_hyphen_distinguishing_69a_and_69_dash_a() -> None:
    # '69a' et '69-a' sont deux articles AIFMD DISTINCTS — le tiret ne doit jamais être retiré.
    a = build_source_unit_id("32011L0061", "69a", "1", None, None, "1")
    b = build_source_unit_id("32011L0061", "69-a", "1", None, None, "1")
    assert a == "SU-32011L0061-ART69A-P1-S01"
    assert b == "SU-32011L0061-ART69-A-P1-S01"
    assert a != b


# === build_article_units (arbre réel AIFMD art. 15) ========================

_AIFMD_ART = "000001/000262/000263/000300"


def _aifmd_article_15() -> tuple[Subdivision, list[Subdivision], list[Subdivision]]:
    chapter = Subdivision(
        id=100,
        parent_id=None,
        subdivision_type="chapter",
        number="III",
        title="Chapter III \u2013 Operating CONDITIONS FOR AIFMs",
        content="Chapter III \u2013 Operating CONDITIONS FOR AIFMs",
        hierarchy_path="000001/000262",
    )
    section = Subdivision(
        id=101,
        parent_id=100,
        subdivision_type="section",
        number="1",
        title="Section 1 \u2013 General requirements",
        content="Section 1 \u2013 General requirements",
        hierarchy_path="000001/000262/000263",
    )
    article = Subdivision(
        id=102,
        parent_id=101,
        subdivision_type="article",
        number="15",
        title="Article 15 \u2013 Risk management",
        content="",
        hierarchy_path=_AIFMD_ART,
    )
    descendants = [
        Subdivision(
            id=201,
            parent_id=102,
            subdivision_type="paragraph",
            number=None,
            title=None,
            content="AIFMs shall separate the functions of risk management. That separation "
            "shall be reviewed regularly.",
            hierarchy_path=f"{_AIFMD_ART}/000301",
        ),
        Subdivision(
            id=203,
            parent_id=102,
            subdivision_type="paragraph",
            number=None,
            title=None,
            content="AIFMs shall implement adequate risk-management systems.",
            hierarchy_path=f"{_AIFMD_ART}/000303",
        ),
        Subdivision(  # note de bas de page (paragraphe imbriqué) — DOIT être exclue
            id=204,
            parent_id=203,
            subdivision_type="paragraph",
            number=None,
            title=None,
            content="(10) OJ L 302, 17.11.2009, p. 1.",
            hierarchy_path=f"{_AIFMD_ART}/000303/000304",
        ),
        Subdivision(
            id=206,
            parent_id=102,
            subdivision_type="paragraph",
            number=None,
            title=None,
            content="AIFMs shall at least:",
            hierarchy_path=f"{_AIFMD_ART}/000306",
        ),
        Subdivision(
            id=207,
            parent_id=206,
            subdivision_type="point",
            number=None,
            title=None,
            content="(a) implement a policy. It is kept up to date.",
            hierarchy_path=f"{_AIFMD_ART}/000306/000307",
        ),
        Subdivision(
            id=208,
            parent_id=206,
            subdivision_type="point",
            number=None,
            title=None,
            content="(b) ensure that risks are identified;",
            hierarchy_path=f"{_AIFMD_ART}/000306/000308",
        ),
    ]
    return article, [chapter, section], descendants


def test_build_article_units_paragraphs_points_and_footnote_exclusion() -> None:
    article, ancestors, descendants = _aifmd_article_15()
    rows = build_article_units(
        celex="32011L0061",
        regulation_id="REG-32011L0061",
        article=article,
        ancestors=ancestors,
        descendants=descendants,
    )
    ids = [r.source_unit_id for r in rows]

    # P1 -> 2 phrases ; P2 (000303) -> 1 phrase ; P3 (000306) chapeau -> 1 phrase ; a,b -> 1 unité
    assert ids == [
        "SU-32011L0061-ART15-P1-S01",
        "SU-32011L0061-ART15-P1-S02",
        "SU-32011L0061-ART15-P2-S01",
        "SU-32011L0061-ART15-P3-S01",
        "SU-32011L0061-ART15-P3-PTA-S01",
        "SU-32011L0061-ART15-P3-PTB-S01",
    ]
    # La note de bas de page (000303/000304) n'a produit aucune source_unit.
    assert not any("17.11.2009" in r.source_text_exact for r in rows)


def test_build_article_units_point_is_not_sentence_split() -> None:
    article, ancestors, descendants = _aifmd_article_15()
    rows = build_article_units(
        celex="32011L0061",
        regulation_id="REG-32011L0061",
        article=article,
        ancestors=ancestors,
        descendants=descendants,
    )
    point_a = next(r for r in rows if r.source_unit_id == "SU-32011L0061-ART15-P3-PTA-S01")
    # Le point reste 1 unité juridique citable même s'il contient une frontière de phrase interne.
    assert point_a.source_text_exact == "(a) implement a policy. It is kept up to date."
    assert point_a.sentence_number == "1"


def test_build_article_units_structural_path_and_numbers() -> None:
    article, ancestors, descendants = _aifmd_article_15()
    rows = build_article_units(
        celex="32011L0061",
        regulation_id="REG-32011L0061",
        article=article,
        ancestors=ancestors,
        descendants=descendants,
    )
    point_a = next(r for r in rows if r.source_unit_id == "SU-32011L0061-ART15-P3-PTA-S01")
    assert point_a.chapter_number == "III"
    assert point_a.section_number == "1"
    assert point_a.article_number == "15"
    assert point_a.paragraph_number == "3"
    assert point_a.point_number == "a"
    assert point_a.is_normative is True
    assert point_a.structural_path == (
        "Chapter III \u2013 Operating CONDITIONS FOR AIFMs > Section 1 \u2013 General requirements > "
        "Article 15 \u2013 Risk management > paragraph 3 > point (a)"
    )


def test_build_article_units_resolves_subpoint_point_ancestor() -> None:
    # Un subpoint (type subpoint) hérite du label de son point ancêtre via la chaîne parent_id.
    article = Subdivision(
        id=1,
        parent_id=None,
        subdivision_type="article",
        number="30",
        title="Article 30 \u2013 Delegation",
        content="",
        hierarchy_path="000001/000010",
    )
    descendants = [
        Subdivision(
            id=2,
            parent_id=1,
            subdivision_type="paragraph",
            number=None,
            title=None,
            content="The AIFM shall ensure the following:",
            hierarchy_path="000001/000010/000011",
        ),
        Subdivision(
            id=3,
            parent_id=2,
            subdivision_type="point",
            number=None,
            title=None,
            content="(a) the delegation is justified;",
            hierarchy_path="000001/000010/000011/000012",
        ),
        Subdivision(
            id=4,
            parent_id=3,
            subdivision_type="subpoint",
            number=None,
            title=None,
            content="(i) on objective reasons;",
            hierarchy_path="000001/000010/000011/000012/000013",
        ),
    ]
    rows = build_article_units(
        celex="32013R0231",
        regulation_id="REG-32013R0231",
        article=article,
        ancestors=[],
        descendants=descendants,
    )
    subpoint = next(r for r in rows if r.subpoint_number is not None)
    assert subpoint.source_unit_id == "SU-32013R0231-ART30-P1-PTA-SPTI-S01"
    assert subpoint.point_number == "a"
    assert subpoint.subpoint_number == "i"


def test_build_article_units_flattened_definitions_keep_distinct_labels() -> None:
    # DR231 art. 1er : (2) et ses (a)(b)(c) sont des FRÈRES typés point — labels distincts, pas de collision.
    art = "000001/000003/000004"
    article = Subdivision(
        id=1,
        parent_id=None,
        subdivision_type="article",
        number="1",
        title="Article 1 \u2013 Definitions",
        content="",
        hierarchy_path=art,
    )
    para = Subdivision(
        id=2,
        parent_id=1,
        subdivision_type="paragraph",
        number=None,
        title=None,
        content="In addition to the definitions laid down in Article 2:",
        hierarchy_path=f"{art}/000005",
    )
    labels = ["(2) 'relevant person' means ...", "(a) a director;", "(b) an employee;"]
    points = [
        Subdivision(
            id=10 + i,
            parent_id=2,
            subdivision_type="point",
            number=None,
            title=None,
            content=c,
            hierarchy_path=f"{art}/000005/{6 + i:06d}",
        )
        for i, c in enumerate(labels)
    ]
    rows = build_article_units(
        celex="32013R0231",
        regulation_id="REG-32013R0231",
        article=article,
        ancestors=[],
        descendants=[para, *points],
    )
    point_ids = [r.source_unit_id for r in rows if r.point_number is not None]
    assert point_ids == [
        "SU-32013R0231-ART1-P1-PT2-S01",
        "SU-32013R0231-ART1-P1-PTA-S01",
        "SU-32013R0231-ART1-P1-PTB-S01",
    ]
    assert len(point_ids) == len(set(point_ids))  # aucune collision d'id


# === plan_merge (cœur idempotent) ==========================================


def test_plan_merge_first_run_creates_all() -> None:
    article, ancestors, descendants = _aifmd_article_15()
    rows = build_article_units(
        celex="32011L0061",
        regulation_id="REG-32011L0061",
        article=article,
        ancestors=ancestors,
        descendants=descendants,
    )
    counts = plan_merge(rows, existing_hashes={})
    assert counts.created == len(rows)
    assert counts.updated == 0
    assert counts.unchanged == 0


def test_plan_merge_second_run_is_all_unchanged() -> None:
    article, ancestors, descendants = _aifmd_article_15()
    rows = build_article_units(
        celex="32011L0061",
        regulation_id="REG-32011L0061",
        article=article,
        ancestors=ancestors,
        descendants=descendants,
    )
    existing = {r.source_unit_id: r.source_text_hash for r in rows}
    counts = plan_merge(rows, existing)
    assert counts.created == 0
    assert counts.updated == 0
    assert counts.unchanged == len(rows)


def test_plan_merge_detects_text_drift_as_update() -> None:
    article, ancestors, descendants = _aifmd_article_15()
    rows = build_article_units(
        celex="32011L0061",
        regulation_id="REG-32011L0061",
        article=article,
        ancestors=ancestors,
        descendants=descendants,
    )
    existing = {r.source_unit_id: r.source_text_hash for r in rows}
    drifted_id = rows[0].source_unit_id
    existing[drifted_id] = source_text_hash("stale previous text")
    counts = plan_merge(rows, existing)
    assert counts.created == 0
    assert counts.updated == 1
    assert counts.unchanged == len(rows) - 1
