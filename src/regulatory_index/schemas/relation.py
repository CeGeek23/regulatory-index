from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class CrossLevelRelationType(StrEnum):
    """How a downstream obligation relates to an upstream one."""

    CLARIFIES = "clarifies"
    STRENGTHENS = "strengthens"
    OPERATIONALIZES = "operationalizes"
    INTERPRETS = "interprets"
    # Reserved: derogation is a valid cross-level relation, but the heuristic
    # graph_builder._derive_relation_type cannot detect it yet, so it is never
    # produced today (kept for taxonomy completeness + the html graph colour).
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
