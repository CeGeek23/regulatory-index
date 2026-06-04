"""Build a cross-level relations graph from resolved citations.

Strategy (article-level, no regex):
- For each resolved citation, derive the relation_type from (source_obligation.level,
  source_obligation.issuer, target_source.level, target_source.issuer).
- When the citation names an article (e.g. "Article 15(3)"), link the obligation to
  the target *obligations* extracted from that article in the cited document. Source
  units are one-per-article, so the article is the finest target granularity available.
- When no article is named (or none matches), fall back to the document node
  `{target_source_id}#source`, preserving doc-level coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from ..schemas.obligation import Obligation
from ..schemas.relation import CrossLevelRelation, CrossLevelRelationType
from ..schemas.sources_registry import load_sources_registry
from .citation_extractor import ResolvedCitation, normalize_article


def _derive_relation_type(
    source_obligation: Obligation, target_source_id: str
) -> CrossLevelRelationType:
    registry = load_sources_registry()
    target = registry.get(target_source_id)
    if target is None:
        return CrossLevelRelationType.REFERENCES

    src_level = source_obligation.source.level
    src_issuer = source_obligation.source.issuer
    src_title_lower = source_obligation.source.title.lower()
    tgt_level = target.level
    tgt_issuer = target.issuer

    if src_level == "national" and tgt_issuer in {"EU_Parliament_Council", "EU_Commission", "ESMA"}:
        return CrossLevelRelationType.STRENGTHENS
    if src_level == 3 and tgt_level in (1, 2):
        if src_issuer == "ESMA" and "q&a" in src_title_lower:
            return CrossLevelRelationType.INTERPRETS
        return CrossLevelRelationType.CLARIFIES
    if src_level == 2 and tgt_level == 1:
        return CrossLevelRelationType.OPERATIONALIZES
    return CrossLevelRelationType.REFERENCES


def _build_article_index(obligations: list[Obligation]) -> dict[tuple[str, str], list[str]]:
    """Map (base_source_id, normalized_article) -> [obligation_id].

    Source units are one-per-article, so all obligations extracted from a given
    article share the same key — the finest target granularity we can resolve to.
    """
    index: dict[tuple[str, str], list[str]] = {}
    for ob in obligations:
        if ob.source.article is None:
            continue
        key = (ob.source.source_id.split("#")[0], normalize_article(ob.source.article))
        index.setdefault(key, []).append(ob.obligation_id)
    return index


def _citation_char_interval(verbatim: str, citation: str) -> tuple[int, int]:
    """Offsets of the citation within the source obligation's verbatim text (no regex)."""
    idx = verbatim.lower().find(citation.lower())
    if idx >= 0:
        return (idx, idx + len(citation))
    return (0, len(citation))


def build_relations(
    obligations: list[Obligation],
    resolved: list[ResolvedCitation],
) -> list[CrossLevelRelation]:
    by_id: dict[str, Obligation] = {o.obligation_id: o for o in obligations}
    article_index = _build_article_index(obligations)
    out: list[CrossLevelRelation] = []
    seen: set[tuple[str, str, str]] = set()
    for rc in resolved:
        src = by_id.get(rc.obligation_id)
        if src is None:
            continue
        rel_type = _derive_relation_type(src, rc.target_source_id)
        char_interval = _citation_char_interval(src.verbatim_text, rc.citation_text)

        # Article-level targets: obligations of the cited document at the cited article.
        targets: list[str] = []
        if rc.target_article is not None:
            key = (rc.target_source_id, normalize_article(rc.target_article))
            targets = [t for t in article_index.get(key, []) if t != src.obligation_id]

        # Fall back to the document node when no specific target obligation is known.
        if not targets:
            targets = [f"{rc.target_source_id}#source"]

        for target_obligation_id in targets:
            dedupe_key = (src.obligation_id, target_obligation_id, rel_type.value)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append(
                CrossLevelRelation(
                    source_obligation_id=src.obligation_id,
                    target_obligation_id=target_obligation_id,
                    relation_type=rel_type,
                    evidence_text=src.verbatim_text,
                    citation_in_text=rc.citation_text,
                    char_interval=char_interval,
                )
            )
    return out


@dataclass(frozen=True)
class GraphStats:
    obligation_nodes: int
    source_nodes: int
    edges: int
    edges_by_type: dict[str, int]


def build_graph(
    obligations: list[Obligation], relations: list[CrossLevelRelation]
) -> tuple[nx.DiGraph, GraphStats]:
    """Build a NetworkX DiGraph with obligation + source nodes and typed edges."""
    g: nx.DiGraph = nx.DiGraph()

    for ob in obligations:
        g.add_node(
            ob.obligation_id,
            kind="obligation",
            actor=ob.actor,
            action=ob.action,
            object=ob.object,
            theme=ob.theme,
            sub_theme=ob.sub_theme or "",
            level=str(ob.source.level),
            issuer=ob.source.issuer,
            source_id=ob.source.source_id.split("#")[0],
            language=ob.source.language,
            verbatim_text=ob.verbatim_text,
        )

    registry = load_sources_registry()
    for entry in registry.values():
        g.add_node(
            f"{entry.source_id}#source",
            kind="source",
            title=entry.title,
            level=str(entry.level),
            issuer=entry.issuer,
            language=entry.language,
            url=entry.url,
        )

    edges_by_type: dict[str, int] = {}
    for rel in relations:
        g.add_edge(
            rel.source_obligation_id,
            rel.target_obligation_id,
            relation_type=rel.relation_type.value,
            citation=rel.citation_in_text,
        )
        edges_by_type[rel.relation_type.value] = edges_by_type.get(rel.relation_type.value, 0) + 1

    obligation_nodes = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "obligation")
    source_nodes = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "source")
    stats = GraphStats(
        obligation_nodes=obligation_nodes,
        source_nodes=source_nodes,
        edges=g.number_of_edges(),
        edges_by_type=edges_by_type,
    )
    return g, stats
