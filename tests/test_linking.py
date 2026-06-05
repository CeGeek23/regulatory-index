from datetime import UTC, datetime

import networkx as nx

from regulatory_index.linking.citation_extractor import (
    parse_article_locator,
    resolve_all,
    resolve_citation,
)
from regulatory_index.linking.graph_builder import build_graph, build_relations
from regulatory_index.schemas.obligation import Obligation
from regulatory_index.schemas.relation import CrossLevelRelationType
from regulatory_index.schemas.source import Issuer, Level, Source


def _obligation(
    oid: str,
    level: Level = 1,
    issuer: Issuer = "EU_Parliament_Council",
    cited: list[str] | None = None,
    title: str = "Directive 2011/61/EU on AIFMs",
    source_id_base: str = "SRC",
    article: str | None = None,
) -> Obligation:
    return Obligation(
        obligation_id=oid,
        actor="AIFM",
        action="establish",
        object="risk management framework",
        source=Source(
            source_id=f"{source_id_base}#{oid}",
            title=title,
            celex="32011L0061",
            level=level,
            issuer=issuer,
            article=article,
            url="https://example.org",
            language="EN",
        ),
        theme="Risk Management",
        verbatim_text="...",
        char_interval=(0, 10),
        cited_references=cited or [],
        extraction_model="gemma3:4b",
        extracted_at=datetime.now(UTC),
    )


def test_resolve_citation_matches_longest_alias() -> None:
    assert resolve_citation("Article 15(3) of Directive 2011/61/EU") == "AIFMD_L1"
    assert resolve_citation("Article 38 of Regulation 231/2013") == "AIFMD_L2"
    assert resolve_citation("DOC-2014-06") == "AMF_DOC_2014_06"
    assert resolve_citation("plain text with no known reference") is None


def test_resolve_all_partitions_resolved_and_unresolved() -> None:
    obligations = [
        _obligation(
            "AIFMD-RISK-0001",
            cited=["Article 15 of Directive 2011/61/EU", "some unknown citation"],
        )
    ]
    resolved, unresolved = resolve_all(obligations)
    assert len(resolved) == 1
    assert resolved[0].target_source_id == "AIFMD_L1"
    assert len(unresolved) == 1


def test_relation_type_for_l3_to_l1_is_clarifies() -> None:
    src = _obligation(
        "AIFMD-RISK-0010",
        level=3,
        issuer="ESMA",
        title="ESMA Guidelines on Reporting Obligations",
        cited=["Directive 2011/61/EU"],
    )
    resolved, _ = resolve_all([src])
    relations = build_relations([src], resolved)
    assert len(relations) == 1
    assert relations[0].relation_type is CrossLevelRelationType.CLARIFIES


def test_relation_type_for_amf_to_eu_is_strengthens() -> None:
    src = _obligation(
        "AIFMD-GOV-0020",
        level="national",
        issuer="AMF",
        title="Position-recommandation AMF DOC-2014-06",
        cited=["Directive 2011/61/EU"],
    )
    resolved, _ = resolve_all([src])
    relations = build_relations([src], resolved)
    assert relations[0].relation_type is CrossLevelRelationType.STRENGTHENS


def test_relation_type_for_l2_to_l1_is_operationalizes() -> None:
    src = _obligation(
        "AIFMD-RISK-0030",
        level=2,
        issuer="EU_Commission",
        title="Commission Delegated Regulation (EU) 231/2013",
        cited=["Directive 2011/61/EU"],
    )
    resolved, _ = resolve_all([src])
    relations = build_relations([src], resolved)
    assert relations[0].relation_type is CrossLevelRelationType.OPERATIONALIZES


def test_relation_type_for_qa_is_interprets() -> None:
    src = _obligation(
        "AIFMD-RPT-0040",
        level=3,
        issuer="ESMA",
        title="ESMA Q&A on AIFMD",
        cited=["Article 38 of Regulation 231/2013"],
    )
    resolved, _ = resolve_all([src])
    relations = build_relations([src], resolved)
    assert relations[0].relation_type is CrossLevelRelationType.INTERPRETS


def test_build_graph_produces_nodes_and_edges() -> None:
    obligations = [
        _obligation(
            "AIFMD-RISK-0001",
            level=3,
            issuer="ESMA",
            title="ESMA Guidelines on Reporting Obligations",
            cited=["Directive 2011/61/EU"],
        )
    ]
    resolved, _ = resolve_all(obligations)
    relations = build_relations(obligations, resolved)
    graph, stats = build_graph(obligations, relations)
    assert isinstance(graph, nx.DiGraph)
    assert stats.obligation_nodes == 1
    assert stats.source_nodes >= 5  # plusieurs sources connues dans le registre
    assert stats.edges == 1
    assert stats.edges_by_type.get("clarifies") == 1


def test_parse_article_locator_handles_en_fr_and_parentheses() -> None:
    assert parse_article_locator("Article 15(3) of Directive 2011/61/EU") == "15"
    assert parse_article_locator("Article 38 of Regulation 231/2013") == "38"
    assert parse_article_locator("article 44, paragraphe 2") == "44"
    assert parse_article_locator("Art. 47") == "47"
    assert parse_article_locator("Articles 38 to 40 of Regulation 231/2013") == "38"
    assert parse_article_locator("Directive 2011/61/EU") is None
    assert parse_article_locator("DOC-2014-06") is None


def test_article_level_link_targets_specific_obligation() -> None:
    target = _obligation(
        "AIFMD-RISK-0050",
        level=1,
        issuer="EU_Parliament_Council",
        title="Directive 2011/61/EU on AIFMs",
        source_id_base="AIFMD_L1",
        article="15",
    )
    source = _obligation(
        "AIFMD-RISK-0060",
        level=2,
        issuer="EU_Commission",
        title="Commission Delegated Regulation (EU) 231/2013",
        cited=["Article 15(3) of Directive 2011/61/EU"],
        source_id_base="AIFMD_L2",
        article="38",
    )
    resolved, _ = resolve_all([source, target])
    relations = build_relations([source, target], resolved)
    assert len(relations) == 1
    # Pointe vers l'obligation cible precise a l'article 15, pas vers le noeud document.
    assert relations[0].target_obligation_id == "AIFMD-RISK-0050"
    assert relations[0].relation_type is CrossLevelRelationType.OPERATIONALIZES


def test_no_article_falls_back_to_source_node() -> None:
    target = _obligation(
        "AIFMD-RISK-0050",
        level=1,
        source_id_base="AIFMD_L1",
        article="15",
    )
    source = _obligation(
        "AIFMD-RISK-0060",
        level=2,
        issuer="EU_Commission",
        title="Commission Delegated Regulation (EU) 231/2013",
        cited=["Directive 2011/61/EU"],
        source_id_base="AIFMD_L2",
        article="38",
    )
    resolved, _ = resolve_all([source, target])
    relations = build_relations([source, target], resolved)
    assert len(relations) == 1
    assert relations[0].target_obligation_id == "AIFMD_L1#source"


def test_article_level_link_excludes_self_reference() -> None:
    # Une obligation citant son propre article ne doit pas se lier a elle-meme ; sans
    # autre cible a cet article, elle se rabat sur le noeud document.
    ob = _obligation(
        "AIFMD-RISK-0070",
        level=1,
        issuer="EU_Parliament_Council",
        title="Directive 2011/61/EU on AIFMs",
        cited=["Article 15 of Directive 2011/61/EU"],
        source_id_base="AIFMD_L1",
        article="15",
    )
    resolved, _ = resolve_all([ob])
    relations = build_relations([ob], resolved)
    assert len(relations) == 1
    assert relations[0].target_obligation_id == "AIFMD_L1#source"
