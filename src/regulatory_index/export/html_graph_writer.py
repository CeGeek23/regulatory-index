"""Rend un DiGraph NetworkX dans un fichier HTML interactif autonome (pyvis/vis.js).

Le fichier produit s'ouvre dans tout navigateur moderne — aucune extension VS Code requise.
Les nœuds sont colorés par niveau (1, 2, 3, national) et par type (obligation vs source) ;
les arêtes par relation_type. Le survol affiche le triplet d'obligation complet.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

_LEVEL_NODE_COLOURS: dict[str, str] = {
    "1": "#A8E6A1",
    "2": "#FFD699",
    "3": "#B5D1FF",
    "national": "#F4B0B0",
}

_SOURCE_NODE_COLOUR = "#444444"

_RELATION_EDGE_COLOURS: dict[str, str] = {
    "clarifies": "#1f77b4",
    "strengthens": "#d62728",
    "operationalizes": "#ff7f0e",
    "interprets": "#2ca02c",
    "derogates": "#9467bd",
    "references": "#7f7f7f",
}


def _node_label(node_id: str, data: dict[str, object]) -> str:
    if data.get("kind") == "obligation":
        actor = str(data.get("actor", ""))
        action = str(data.get("action", ""))
        obj = str(data.get("object", ""))
        return f"{node_id}\n{actor} → {action} → {obj[:40]}"
    title = str(data.get("title", node_id))
    return title[:60]


def _node_tooltip(node_id: str, data: dict[str, object]) -> str:
    if data.get("kind") == "obligation":
        parts = [
            f"<b>{node_id}</b>",
            f"<b>Actor:</b> {data.get('actor', '')}",
            f"<b>Action:</b> {data.get('action', '')}",
            f"<b>Object:</b> {data.get('object', '')}",
            f"<b>Theme:</b> {data.get('theme', '')}",
            f"<b>Source:</b> {data.get('source_id', '')} (Level {data.get('level', '')}, {data.get('issuer', '')})",
            f"<b>Language:</b> {data.get('language', '')}",
        ]
        raw_verbatim = str(data.get("verbatim_text", ""))
        verbatim = raw_verbatim[:240]
        if verbatim:
            ellipsis = "…" if len(raw_verbatim) > 240 else ""
            parts.append(f"<i>{verbatim}{ellipsis}</i>")
        return "<br>".join(parts)
    return (
        f"<b>{data.get('title', node_id)}</b><br>"
        f"Level {data.get('level', '')}, {data.get('issuer', '')}"
    )


def write_html_graph(
    graph: nx.DiGraph,
    out_path: Path,
    *,
    title: str = "Regulatory Index — Cross-level relations",
    hide_isolated_sources: bool = True,
) -> Path:
    """Écrit un graphe HTML interactif autonome. Renvoie le chemin écrit."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    g = graph
    if hide_isolated_sources:
        # Supprime les nœuds source sans arête — ils encombrent la vue sans apport.
        to_drop = [
            n
            for n, d in graph.nodes(data=True)
            if d.get("kind") == "source"
            and graph.in_degree(n) == 0
            and graph.out_degree(n) == 0
        ]
        if to_drop:
            g = graph.copy()
            g.remove_nodes_from(to_drop)

    net = Network(
        height="780px",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="remote",
        heading=title,
        bgcolor="#ffffff",
    )
    net.barnes_hut(gravity=-3000, spring_length=180, damping=0.4)

    for node_id, data in g.nodes(data=True):
        kind = data.get("kind", "obligation")
        if kind == "obligation":
            colour = _LEVEL_NODE_COLOURS.get(str(data.get("level", "")), "#cccccc")
            shape = "dot"
            size = 18
        else:
            colour = _SOURCE_NODE_COLOUR
            shape = "box"
            size = 26
        net.add_node(
            node_id,
            label=_node_label(node_id, data),
            title=_node_tooltip(node_id, data),
            color=colour,
            shape=shape,
            size=size,
        )

    for source, target, data in g.edges(data=True):
        rel = str(data.get("relation_type", "references"))
        net.add_edge(
            source,
            target,
            title=f"{rel}: {data.get('citation', '')}",
            label=rel,
            color=_RELATION_EDGE_COLOURS.get(rel, "#999999"),
            arrows="to",
        )

    net.set_options(
        """
        var options = {
          "interaction": {"hover": true, "tooltipDelay": 120, "navigationButtons": true},
          "edges": {"smooth": {"type": "dynamic"}, "font": {"size": 11, "align": "middle", "color": "#222222"}},
          "nodes": {"font": {"size": 12, "face": "monospace", "color": "#222222"}, "borderWidth": 1}
        }
        """
    )

    html = net.generate_html(notebook=False)
    out_path.write_text(html, encoding="utf-8")
    return out_path
