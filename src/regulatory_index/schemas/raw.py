"""Schémas intermédiaires entre la sortie de LangExtract et l'Obligation finale.

Une RawObligation est la sortie structurée du LLM, normalisée par rapport au vocab
mais sans l'obligation_id final, l'imbrication complète de Source ni la provenance
d'extraction. Les lignes Obligation finales sont construites par
`obligation_builder.build_obligations` (orchestré par `materialize.py`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..ingestion.unit_loader import NormativeUnit


class RawObligation(BaseModel):
    actor: str
    action: str
    object: str
    theme: str
    sub_theme: str | None = None
    condition: str | None = None
    scope: str | None = None
    exception: str | None = None
    expected_evidence: list[str] = Field(default_factory=list)
    associated_control: str | None = None
    cited_references: list[str] = Field(default_factory=list)
    verbatim_text: str
    char_interval: tuple[int, int]
    alignment_status: str | None = None  # 'match_exact' | 'match_fuzzy'


class ExtractionMeta(BaseModel):
    model_id: str
    extraction_passes: int
    temperature: float
    extracted_at: datetime
    latency_seconds: float
    langextract_version: str | None = None


class UnitExtraction(BaseModel):
    """Forme du fichier persisté : un par (source_id, unit_id)."""

    unit: NormativeUnit
    obligations: list[RawObligation]
    extraction_meta: ExtractionMeta
    errors: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.obligations) == 0

    def to_record_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
