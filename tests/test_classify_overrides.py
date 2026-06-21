"""Tests de la logique de classification reproductible (scripts/classify_overrides.py).

Pas de réseau, pas de LM Studio : on teste les fonctions pures (parsing, harmonisation
inter-textes par vote majoritaire, application des décisions tie_breaks)."""

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


def test_harmonize_aligns_majority_and_leaves_ties() -> None:
    docs = {
        # 'issuer' : concept x1 / actor x3 -> majorité stricte = actor partout
        "A": _doc({"a": "concept"}, [("a", "issuer")]),
        "B": _doc({"a": "actor"}, [("a", "issuer")]),
        "C": _doc({"a": "actor"}, [("a", "issuer")]),
        "D": _doc({"a": "actor"}, [("a", "issuer")]),
        # 'tie' : actor x1 / concept x1 -> égalité, laissé tel quel
        "E": _doc({"b": "actor"}, [("b", "tie")]),
        "F": _doc({"b": "concept"}, [("b", "tie")]),
    }
    changes, ties = co._harmonize(docs)

    assert docs["A"].types["a"] == "actor"  # basculé vers la majorité
    assert changes == 1  # seul A a changé
    assert ties == ["tie"]
    # l'égalité n'est pas tranchée
    assert docs["E"].types["b"] == "actor"
    assert docs["F"].types["b"] == "concept"


def test_apply_tie_breaks_forces_type_everywhere() -> None:
    docs = {
        "A": _doc({"a": "actor"}, [("a", "deposit")]),
        "B": _doc({"b": "concept"}, [("b", "deposit")]),
        "C": _doc({"c": "actor"}, [("c", "issuer")]),  # non concerné
    }
    applied = co._apply_tie_breaks(docs, {"deposit": "concept"})

    assert docs["A"].types["a"] == "concept"  # forcé
    assert docs["B"].types["b"] == "concept"  # déjà concept (pas compté)
    assert docs["C"].types["c"] == "actor"  # intact
    assert applied == 1  # seul A a effectivement changé


def test_apply_tie_breaks_empty_is_noop() -> None:
    docs = {"A": _doc({"a": "actor"}, [("a", "issuer")])}
    assert co._apply_tie_breaks(docs, {}) == 0
    assert docs["A"].types["a"] == "actor"
