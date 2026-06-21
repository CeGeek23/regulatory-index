"""Tests de la logique de classification reproductible (scripts/classify_overrides.py).

Pas de réseau, pas de LM Studio : on teste les fonctions pures — parsing, et harmonisation
inter-textes (vote majoritaire ; égalités tranchées par la définition substantielle/la plus longue)."""

from __future__ import annotations

import classify_overrides as co


def _doc(types: dict[str, str], labels: list[tuple[str, str]]) -> co._Doc:
    doc = co._Doc()
    doc.types = dict(types)
    doc.labels = list(labels)
    return doc


def test_parse_type_recognises_first_match_and_none() -> None:
    assert co._parse_type("acteur") == "acteur"
    assert co._parse_type("  Produit.") == "produit"
    assert co._parse_type("activité") == "activite"  # accent normalisé
    # premier libellé reconnu l'emporte (les libellés ne se chevauchent pas)
    assert co._parse_type("c'est un acteur, pas un produit") == "acteur"
    assert co._parse_type("n'importe quoi") is None
    assert co._parse_type(None) is None


def test_harmonize_majority_wins() -> None:
    docs = {
        # 'issuer' : produit x1 / acteur x3 -> majorité stricte = acteur partout
        "A": _doc({"a": "produit"}, [("a", "issuer")]),
        "B": _doc({"a": "acteur"}, [("a", "issuer")]),
        "C": _doc({"a": "acteur"}, [("a", "issuer")]),
        "D": _doc({"a": "acteur"}, [("a", "issuer")]),
    }
    longest = {"issuer": (50, "acteur")}
    changes, tie_resolved = co._harmonize(docs, longest)
    assert docs["A"].types["a"] == "acteur"  # basculé vers la majorité
    assert changes == 1  # seul A a changé
    assert tie_resolved == 0


def test_harmonize_tie_resolved_by_substantive_definition() -> None:
    docs = {
        # 'deposit' : acteur x1 / produit x1 -> ÉGALITÉ -> on tranche par la déf. la plus longue
        "A": _doc({"a": "acteur"}, [("a", "deposit")]),
        "B": _doc({"b": "produit"}, [("b", "deposit")]),
    }
    longest = {"deposit": (120, "produit")}  # la vraie définition (longue) dit « produit »
    changes, tie_resolved = co._harmonize(docs, longest)
    assert docs["A"].types["a"] == "produit"  # tranché par la définition substantielle
    assert docs["B"].types["b"] == "produit"
    assert tie_resolved == 1
    assert changes == 1  # seul A a changé
