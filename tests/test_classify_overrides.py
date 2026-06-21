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
    assert co._parse_type("actor") == "actor"
    assert co._parse_type("  Concept.") == "concept"
    assert co._parse_type("réponse : investor") == "investor"
    assert co._parse_type("supervisor\n") == "supervisor"
    # premier libellé reconnu l'emporte (les libellés ne se chevauchent pas)
    assert co._parse_type("not an actor but a concept") == "actor"
    assert co._parse_type("n'importe quoi") is None
    assert co._parse_type(None) is None


def test_harmonize_majority_wins() -> None:
    docs = {
        # 'issuer' : concept x1 / actor x3 -> majorité stricte = actor partout
        "A": _doc({"a": "concept"}, [("a", "issuer")]),
        "B": _doc({"a": "actor"}, [("a", "issuer")]),
        "C": _doc({"a": "actor"}, [("a", "issuer")]),
        "D": _doc({"a": "actor"}, [("a", "issuer")]),
    }
    longest = {"issuer": (50, "actor")}
    changes, tie_resolved = co._harmonize(docs, longest)
    assert docs["A"].types["a"] == "actor"  # basculé vers la majorité
    assert changes == 1  # seul A a changé
    assert tie_resolved == 0


def test_harmonize_tie_resolved_by_substantive_definition() -> None:
    docs = {
        # 'deposit' : actor x1 / concept x1 -> ÉGALITÉ -> on tranche par la déf. la plus longue
        "A": _doc({"a": "actor"}, [("a", "deposit")]),
        "B": _doc({"b": "concept"}, [("b", "deposit")]),
    }
    longest = {"deposit": (120, "concept")}  # la vraie définition (longue) dit « concept »
    changes, tie_resolved = co._harmonize(docs, longest)
    assert docs["A"].types["a"] == "concept"  # tranché par la définition substantielle
    assert docs["B"].types["b"] == "concept"
    assert tie_resolved == 1
    assert changes == 1  # seul A a changé
