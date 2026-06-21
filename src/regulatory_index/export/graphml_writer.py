"""Écrit un DiGraph NetworkX au format GraphML pour inspection dans Gephi / yEd."""

from __future__ import annotations

from pathlib import Path

import networkx as nx


def write_graphml(graph: nx.DiGraph, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # GraphML ne supporte pas les attributs None ; on les neutralise sur une COPIE (sans muter l'appelant).
    clean = graph.copy()
    for _, data in clean.nodes(data=True):
        for key, value in list(data.items()):
            if value is None:
                data[key] = ""
    for _, _, data in clean.edges(data=True):
        for key, value in list(data.items()):
            if value is None:
                data[key] = ""
    nx.write_graphml(clean, str(out_path), encoding="utf-8", prettyprint=True)
    return out_path
