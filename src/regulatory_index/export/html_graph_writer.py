"""Rend un DiGraph NetworkX dans un fichier HTML interactif autonome (pyvis/vis.js).

Le fichier produit s'ouvre dans tout navigateur moderne — aucune extension VS Code requise.
Les nœuds sont colorés par niveau (1, 2, 3, national) et par type (obligation vs source) ;
les arêtes par relation_type. Le survol affiche le triplet d'obligation complet.
Une petite légende fixe explique les couleurs (niveaux + types de relations).
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

_LEVEL_NODE_COLOURS: dict[str, str] = {
    "1": "#1B7837",        # vert soutenu (L1 — Directive)
    "2": "#E66101",        # orange soutenu (L2 — Règlement délégué) : bien distinct du vert
    "3": "#1F6FB2",        # bleu (L3 — ESMA)
    "national": "#C0392B",  # rouge (national)
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


def _legend_html(g: nx.DiGraph) -> str:
    """Petite légende fixe expliquant les couleurs (niveaux de nœuds + types de relations).

    Ne liste que les catégories réellement présentes dans le graphe.
    """
    levels = {str(d.get("level", "")) for _, d in g.nodes(data=True) if d.get("kind") == "obligation"}
    has_source = any(d.get("kind") == "source" for _, d in g.nodes(data=True))
    rels = {str(d.get("relation_type", "references")) for _, _, d in g.edges(data=True)}

    def dot(label: str, colour: str) -> str:
        return (
            f"<div><span style='display:inline-block;width:12px;height:12px;border-radius:50%;"
            f"background:{colour};margin-right:6px;vertical-align:middle'></span>{label}</div>"
        )

    def line(label: str, colour: str) -> str:
        return (
            f"<div><span style='display:inline-block;width:18px;height:3px;background:{colour};"
            f"margin-right:6px;vertical-align:middle'></span>{label}</div>"
        )

    level_label = {"1": "Niveau 1", "2": "Niveau 2", "3": "Niveau 3", "national": "National"}
    node_rows = [
        dot(level_label.get(lv, lv), _LEVEL_NODE_COLOURS.get(lv, "#cccccc"))
        for lv in ("1", "2", "3", "national")
        if lv in levels
    ]
    if has_source:
        node_rows.append(dot("Source (document)", _SOURCE_NODE_COLOUR))
    edge_rows = [
        line(rel, _RELATION_EDGE_COLOURS.get(rel, "#999999"))
        for rel in _RELATION_EDGE_COLOURS
        if rel in rels
    ]

    return (
        "<div style='position:fixed;top:12px;right:12px;z-index:999;background:rgba(255,255,255,.95);"
        "border:1px solid #ccc;border-radius:6px;padding:8px 10px;font:12px sans-serif;color:#222;"
        "box-shadow:0 1px 4px rgba(0,0,0,.15)'>"
        "<div style='font-weight:bold;margin-bottom:4px'>Légende</div>"
        "<div style='font-size:11px;color:#666;margin-bottom:2px'>Nœuds (niveau)</div>"
        + "".join(node_rows)
        + "<div style='font-size:11px;color:#666;margin:5px 0 2px'>Arêtes (relation)</div>"
        + "".join(edge_rows)
        + "</div>"
    )


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
    title: str = "Regulatory Index",
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
    # Ressorts plus longs et plus souples (spring_length/strength) + plus de
    # répulsion (gravity) + anti-chevauchement (overlap) => liens « extensibles »,
    # les nœuds s'écartent et restent lisibles.
    net.barnes_hut(
        gravity=-15000, central_gravity=0.1, spring_length=350,
        spring_strength=0.005, damping=0.5, overlap=1,
    )

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
    # pyvis insère le heading (<h1>) en double ; on ne garde que la 1re occurrence.
    heading = f"<h1>{title}</h1>"
    first = html.find(heading)
    if first != -1:
        cut = first + len(heading)
        html = html[:cut] + html[cut:].replace(heading, "")
    legend = _legend_html(g)
    html = html.replace("</body>", legend + "</body>", 1) if "</body>" in html else html + legend
    out_path.write_text(html, encoding="utf-8")
    return out_path
