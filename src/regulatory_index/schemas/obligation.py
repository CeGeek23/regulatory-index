from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .source import Source

Enforcement = Literal["ongoing", "annual", "ex_ante", "on_demand", "triggered"]


class Obligation(BaseModel):
    """A single normative requirement extracted from a regulatory text.

    Vocabulary fields (actor, action, object, theme, sub_theme, condition) are
    validated against controlled vocabularies loaded from config/vocabularies/*.yaml
    at runtime by the extraction pipeline. They are typed as `str` here to keep
    the schema decoupled from the YAML files; cross-checking happens in
    `extraction/schema_builder.py`.
    """

    obligation_id: str = Field(
        pattern=r"^[A-Z][A-Z0-9]+-[A-Z]+-\d{3,4}$",
        description="Pattern: {SCOPE}-{THEME_CODE}-{NNNN}, e.g. AIFMD-RISK-0042, MIFID2-EXEC-0017",
    )
    actor: str
    action: str
    object: str
    condition: str | None = None
    source: Source
    theme: str
    sub_theme: str | None = None
    scope: str | None = None
    exception: str | None = None
    enforcement: Enforcement | None = None
    expected_evidence: list[str] = Field(default_factory=list)
    associated_control: str | None = None
    verbatim_text: str = Field(
        description="Literal extract from source, guaranteed by LangExtract grounding"
    )
    char_interval: tuple[int, int] = Field(
        description="Offsets of verbatim_text within the source unit"
    )
    cited_references: list[str] = Field(
        default_factory=list,
        description="Other regulatory references cited in this obligation, "
        "e.g. ['Article 15(3) of Directive 2011/61/EU']",
    )
    extraction_model: str
    extracted_at: datetime
    human_validated: bool = False

    @field_validator("verbatim_text")
    @classmethod
    def _strip_verbatim(cls, v: str) -> str:
        return v.strip()
