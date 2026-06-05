from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class CrossLevelRelationType(StrEnum):
    """Comment une obligation en aval se rapporte à une obligation en amont."""

    CLARIFIES = "clarifies"
    STRENGTHENS = "strengthens"
    OPERATIONALIZES = "operationalizes"
    INTERPRETS = "interprets"
    # Réservé : la dérogation est une relation cross-level valide, mais l'heuristique
    # graph_builder._derive_relation_type ne sait pas encore la détecter, donc elle
    # n'est jamais produite aujourd'hui (gardée pour la complétude de la taxonomie
    # + la couleur du graphe HTML).
    DEROGATES = "derogates"
    REFERENCES = "references"


class CrossLevelRelation(BaseModel):
    source_obligation_id: str
    target_obligation_id: str
    relation_type: CrossLevelRelationType
    evidence_text: str = Field(description="Sentence or clause supporting the relation")
    citation_in_text: str = Field(description="Exact citation as captured by LangExtract")
    char_interval: tuple[int, int]
    validated: bool = False
