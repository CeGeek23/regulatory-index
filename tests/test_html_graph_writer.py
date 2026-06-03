"""Tests for the pyvis HTML graph writer."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from regulatory_index.export.html_graph_writer import write_html_graph


def _toy_graph() -> nx.DiGraph:
    g: nx.DiGraph = nx.DiGraph()
    g.add_node(
        "AIFMD-RISK-0001",
        kind="obligation",
        actor="AIFM",
        action="establish",
        object="risk management framework",
        theme="Risk Management",
        sub_theme="",
        level="1",
        issuer="EU_Parliament_Council",
        source_id="AIFMD_L1",
        language="EN",
        verbatim_text="AIFMs shall establish a risk management framework.",
    )
    g.add_node(
        "AIFMD-RISK-0002",
        kind="obligation",
        actor="AIFM",
        action="implement",
        object="risk management policy",
        theme="Risk Management",
        sub_theme="",
        level="2",
        issuer="EU_Commission",
        source_id="AIFMD_L2",
        language="EN",
        verbatim_text="AIFMs shall implement a risk management policy.",
    )
    g.add_node(
        "AIFMD_L1#source",
        kind="source",
        title="Directive 2011/61/EU",
        level="1",
        issuer="EU_Parliament_Council",
        language="EN",
        url="https://example.org",
    )
    g.add_node(
        "ISOLATED_SOURCE#source",
        kind="source",
        title="Isolated source — should be hidden",
        level="3",
        issuer="ESMA",
        language="EN",
        url="https://example.org",
    )
    g.add_edge(
        "AIFMD-RISK-0002",
        "AIFMD_L1#source",
        relation_type="operationalizes",
        citation="Article 15 of Directive 2011/61/EU",
    )
    return g


def test_write_html_graph_creates_valid_html(tmp_path: Path) -> None:
    out = tmp_path / "graph.html"
    written = write_html_graph(_toy_graph(), out)
    assert written == out
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # vis.js is loaded
    assert "vis-network" in content
    # Both connected nodes are present
    assert "AIFMD-RISK-0001" in content
    assert "AIFMD-RISK-0002" in content
    # Edge label appears
    assert "operationalizes" in content


def test_isolated_sources_are_hidden_by_default(tmp_path: Path) -> None:
    out = tmp_path / "graph.html"
    write_html_graph(_toy_graph(), out, hide_isolated_sources=True)
    content = out.read_text(encoding="utf-8")
    assert "Isolated source" not in content
    # Connected source remains
    assert "AIFMD_L1#source" in content


def test_isolated_sources_kept_when_disabled(tmp_path: Path) -> None:
    out = tmp_path / "graph.html"
    write_html_graph(_toy_graph(), out, hide_isolated_sources=False)
    content = out.read_text(encoding="utf-8")
    assert "Isolated source" in content
