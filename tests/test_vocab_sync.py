"""Tests de la normalisation de déduplication du vocabulaire (scripts/vocab_sync.py).

`_norm` unifie casse, espaces et variantes de tiret/trait d'union : les variantes purement
typographiques fusionnent d'office à la déduplication, sans table de correspondance à maintenir."""

from __future__ import annotations

import vocab_sync as vs


def test_norm_lowercases_and_collapses_spaces() -> None:
    assert vs._norm("  Money   Market ") == "money market"
    assert vs._norm("Issuer") == "issuer"


def test_norm_unifies_hyphen_and_space() -> None:
    assert vs._norm("money-market instruments") == vs._norm("money market instruments")
    assert vs._norm("risk-mitigation techniques") == "risk mitigation techniques"


def test_norm_unifies_unicode_dashes() -> None:
    u2010 = chr(0x2010)  # tiret Unicode vs trait d'union ASCII -> même clé
    assert vs._norm(f"insurance{u2010}based product") == vs._norm("insurance-based product")
    assert vs._norm(f"pan{u2010}European Personal Pension Product") == "pan european personal pension product"


def test_norm_is_idempotent() -> None:
    once = vs._norm("Title-Transfer  Collateral Arrangement")
    assert vs._norm(once) == once
