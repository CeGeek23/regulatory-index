"""Build a cross-level relations graph from resolved citations.

Strategy (document-level, no regex):
- For each resolved citation, derive the relation_type from (source_obligation.level,
  source_obligation.issuer, target_source.level, target_source.issuer).
- We currently link an obligation to the *target source* (not a target obligation),
  because the LLM-extracted citation rarely encodes a precise article+paragraph
  pair. Obligation-to-obligation linking is a v2 refinement.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from ..schemas.obligation import Obligation
from ..schemas.relation import CrossLevelRelation, CrossLevelRelationType
from ..schemas.sources_registry import load_sources_registry
from .citation_extractor import ResolvedCitation


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


def build_relations(
    obligations: list[Obligation],
    resolved: list[ResolvedCitation],
) -> list[CrossLevelRelation]:
    by_id: dict[str, Obligation] = {o.obligation_id: o for o in obligations}
    out: list[CrossLevelRelation] = []
    for rc in resolved:
        src = by_id.get(rc.obligation_id)
        if src is None:
            continue
        rel_type = _derive_relation_type(src, rc.target_source_id)
        target_obligation_id = f"{rc.target_source_id}#source"
        char_interval: tuple[int, int] = (0, len(rc.citation_text))
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
