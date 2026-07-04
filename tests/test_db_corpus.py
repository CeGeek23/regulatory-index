"""Tests du découpage des articles longs en unités — fonction pure ``pack_leaves``.

Cas minimaux et abstraits (aucune base requise), conformément au principe projet :
une règle générale se teste sur un cas abstrait, pas sur un article précis.
"""

from __future__ import annotations

from regulatory_index.ingestion.db_corpus import pack_leaves


def test_empty() -> None:
    assert pack_leaves([], 100) == []


def test_single_group_when_within_budget() -> None:
    leaves = ["aaa", "bbb", "ccc"]  # 3 + 1 + 3 + 1 + 3 = 11 <= 100
    assert pack_leaves(leaves, 100) == [["aaa", "bbb", "ccc"]]


def test_splits_when_over_budget() -> None:
    leaves = ["aaaa", "bbbb", "cccc"]  # deux feuilles jointes = 4+1+4 = 9 > 5
    assert pack_leaves(leaves, 5) == [["aaaa"], ["bbbb"], ["cccc"]]


def test_packs_greedily() -> None:
    # "aa"+"\n"+"bb" = 5 <= 6 ; ajouter "cccccc" -> 5+1+6 = 12 > 6 -> nouveau bloc
    assert pack_leaves(["aa", "bb", "cccccc"], 6) == [["aa", "bb"], ["cccccc"]]


def test_oversized_leaf_stands_alone() -> None:
    groups = pack_leaves(["x" * 50, "y", "z"], 10)
    assert groups[0] == ["x" * 50]  # feuille géante seule — jamais coupée en plein milieu
    assert groups[1] == ["y", "z"]  # les petites regroupées


def test_preserves_all_leaves_in_order() -> None:
    leaves = [f"leaf{i}" for i in range(20)]
    groups = pack_leaves(leaves, 13)
    flat = [leaf for g in groups for leaf in g]
    assert flat == leaves  # rien perdu, ordre conservé
    for g in groups:
        assert len("\n".join(g)) <= 13 or len(g) == 1  # budget respecté sauf feuille unique
