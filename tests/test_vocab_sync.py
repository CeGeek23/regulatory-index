"""Tests de la logique d'élagage du vocabulaire (scripts/vocab_sync.py).

Pas de réseau : on teste la normalisation, le chargement de prune.yaml, et la fusion
d'une variante en alias du canonique (merge)."""

from __future__ import annotations

from pathlib import Path

import pytest
import vocab_sync as vs


def test_norm_lowercases_and_collapses_spaces() -> None:
    assert vs._norm("  Money-Market   Instruments ") == "money-market instruments"
    assert vs._norm("Issuer") == "issuer"


def test_load_prune_parses_drop_and_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prune = tmp_path / "prune.yaml"
    prune.write_text(
        "actors:\n  drop: [Foo Bar]\n  merge: {'A  B': 'C D'}\nobjects:\n  drop: []\n  merge: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vs, "PRUNE", prune)

    drop, merge = vs._load_prune("actors")
    assert drop == {"foo bar"}
    assert merge == {"a b": "c d"}  # clés/valeurs normalisées
    assert vs._load_prune("objects") == (set(), {})  # section vide


def test_load_prune_absent_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vs, "PRUNE", tmp_path / "absent.yaml")
    assert vs._load_prune("actors") == (set(), {})


def _entry(en: str, fr: str, aliases: list[str]) -> dict[str, object]:
    return {"id": en.replace(" ", "_"), "canonical_en": en, "canonical_fr": fr, "aliases": aliases, "legal_basis": "x"}


def _aliases(entry: dict[str, object]) -> list[str]:
    al = entry["aliases"]
    assert isinstance(al, list)
    return al


def test_fold_aliases_merges_variant_into_canonical() -> None:
    new = {"money market instruments": _entry("money market instruments", "instruments du marché monétaire", [])}
    vs._fold_aliases(new, [("money market instruments", "money-market instruments", "")])
    assert "money-market instruments" in _aliases(new["money market instruments"])


def test_fold_aliases_skips_absent_canonical() -> None:
    new: dict[str, dict[str, object]] = {}
    vs._fold_aliases(new, [("missing", "variant", "")])  # ne doit pas lever
    assert new == {}


def test_fold_aliases_no_self_or_duplicate() -> None:
    new = {"x": _entry("x", "x", ["y"])}
    vs._fold_aliases(new, [("x", "x", ""), ("x", "y", ""), ("x", "z", "")])
    # "x" == canonique -> ignoré ; "y" déjà alias -> ignoré ; "z" ajouté
    assert _aliases(new["x"]) == ["y", "z"]
