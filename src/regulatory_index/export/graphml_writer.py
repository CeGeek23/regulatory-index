"""Écrit un DiGraph NetworkX au format GraphML pour inspection dans Gephi / yEd."""

from __future__ import annotations

from pathlib import Path

import networkx as nx


def write_graphml(graph: nx.DiGraph, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, str(out_path), encoding="utf-8", prettyprint=True)
    return out_path
