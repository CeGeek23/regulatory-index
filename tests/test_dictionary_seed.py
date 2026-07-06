"""Tests des règles pures du dictionnaire d'amorçage (aucune base requise).

Cas RÉELS inline tirés de `config/dictionary_seed.yaml` (onglet 15) et des vocabulaires :
mapping seed -> lignes, alignement statement_type sur la CHECK, tri parents-avant-enfants,
normalisation de dédup (casse/espaces/tirets, sans regex) et déduplication des candidats.
"""

from __future__ import annotations

from regulatory_index.db.dictionary import (
    Candidate,
    dedup_candidates,
    dictionary_entry_rows,
    load_dictionary_seed,
    normalize_name,
    parents_before_children,
    seed_name_index,
    seed_plan,
)

# La CHECK de regindex.statement.statement_type (db/schema.sql l.79-82).
_STATEMENT_TYPE_CHECK = {
    "obligation",
    "prohibition",
    "definition",
    "condition",
    "exception",
    "power",
    "right",
    "authorisation",
    "scope",
    "reference",
}


# === Chargement + mapping seed -> lignes ===================================


def test_seed_has_the_minimal_v1_shape() -> None:
    seed = load_dictionary_seed()
    assert len(seed.actors) == 20
    assert len(seed.actions) == 30
    assert len(seed.objects) == 30
    assert len(seed.statement_types) == 10
    assert len(seed.themes) == 10


def test_dictionary_entry_rows_cover_all_five_families() -> None:
    rows = dictionary_entry_rows(load_dictionary_seed())
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r.dictionary_type] = by_type.get(r.dictionary_type, 0) + 1
    assert by_type == {"actor": 20, "action": 30, "object": 30, "statement_type": 10, "theme": 10}
    assert len(rows) == 100


def test_dictionary_entry_maps_action_verb_and_theme_subtheme() -> None:
    rows = dictionary_entry_rows(load_dictionary_seed())
    establish = next(r for r in rows if r.code == "ACTN-ESTABLISH")
    assert establish.dictionary_type == "action"
    assert establish.canonical_name == "Establish"  # canonical_verb -> canonical_name
    assert establish.category == "Governance / Set-up"  # action_category -> category
    gov = next(r for r in rows if r.code == "THM-GOV")
    assert gov.dictionary_type == "theme"
    assert gov.canonical_name == "Governance"  # theme_name -> canonical_name
    assert gov.category == "Organisation"  # default_subtheme -> category


def test_statement_type_seed_lowercases_onto_the_check() -> None:
    rows = dictionary_entry_rows(load_dictionary_seed())
    seeded = {r.canonical_name.lower() for r in rows if r.dictionary_type == "statement_type"}
    assert seeded == _STATEMENT_TYPE_CHECK  # 1:1, orthographe britannique 'authorisation' incluse


def test_seed_plan_counts_target_rows() -> None:
    plan = seed_plan(load_dictionary_seed())
    assert plan["actor"] == 20
    assert plan["action"] == 30
    assert plan["regulatory_object"] == 30
    assert plan["dictionary_entry"]["total"] == 100


def test_seed_actor_and_object_hierarchies_are_present() -> None:
    seed = load_dictionary_seed()
    custodian = next(a for a in seed.actors if a.code == "ACT-CUSTODIAN")
    assert custodian.parent_code == "ACT-DEPOSITARY"
    policy = next(o for o in seed.objects if o.code == "OBJ-RISK-MGMT-POLICY")
    assert policy.parent_code == "OBJ-RISK-MGMT-SYSTEM"


# === parents_before_children (FK auto-référencée) ==========================


def test_parents_emitted_before_children_regardless_of_input_order() -> None:
    order = parents_before_children([("ACT-CUSTODIAN", "ACT-DEPOSITARY"), ("ACT-DEPOSITARY", None)])
    assert order.index("ACT-DEPOSITARY") < order.index("ACT-CUSTODIAN")


def test_parents_before_children_handles_multi_level_chain() -> None:
    order = parents_before_children([("C", "B"), ("B", "A"), ("A", None)])
    assert order == ["A", "B", "C"]


def test_parents_before_children_treats_external_parent_as_root() -> None:
    # Un parent absent du lot ne bloque pas l'émission (candidats sans parent chargé).
    order = parents_before_children([("X", "NOT-IN-BATCH")])
    assert order == ["X"]


# === normalize_name (sans regex) ===========================================


def test_normalize_unifies_case_space_and_hyphen() -> None:
    assert normalize_name("Risk-Management  System") == "risk management system"
    assert normalize_name("risk management system") == normalize_name("Risk-Management-System")


def test_normalize_unifies_unicode_dashes() -> None:
    u2013 = chr(0x2013)  # en-dash Unicode == trait d'union ASCII après normalisation
    assert normalize_name(f"pan{u2013}european product") == "pan european product"


# === dedup_candidates =======================================================


def test_candidate_matching_seed_name_is_skipped() -> None:
    seed = load_dictionary_seed()
    index = seed_name_index(seed)
    # 'AIFM' (id différent, casse/tiret différents) est déjà un acteur du seed -> écarté.
    cand = Candidate("actor", "ACT-VOC-AIFM", "aifm", "Gestionnaire", "[CANDIDATE ...]")
    plan = dedup_candidates([cand], index)
    assert plan.kept == []
    assert plan.skipped_as_seed == [cand]


def test_new_candidate_is_kept() -> None:
    index = seed_name_index(load_dictionary_seed())
    cand = Candidate("actor", "ACT-GLO-TRUSTEE", "Trustee", "Fiduciaire", "[CANDIDATE ...]")
    plan = dedup_candidates([cand], index)
    assert plan.kept == [cand]
    assert plan.skipped_as_seed == []


def test_intra_batch_duplicate_is_skipped_first_wins() -> None:
    index = seed_name_index(load_dictionary_seed())
    first = Candidate("actor", "ACT-VOC-TRUSTEE", "Trustee", None, "[from vocab]")
    dup = Candidate("actor", "ACT-GLO-TRUSTEE", "trustee", None, "[from glossary]")
    plan = dedup_candidates([first, dup], index)
    assert plan.kept == [first]
    assert plan.skipped_duplicate == [dup]


def test_same_name_different_type_is_not_a_duplicate() -> None:
    index = seed_name_index(load_dictionary_seed())
    an_actor = Candidate("actor", "ACT-VOC-VALUER", "Valuer", None, "p")
    an_object = Candidate("object", "OBJ-VOC-VALUER", "Valuer", None, "p")
    plan = dedup_candidates([an_actor, an_object], index)
    assert plan.kept == [an_actor, an_object]
