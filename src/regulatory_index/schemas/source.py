from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Level = Literal[1, 2, 3, "national"]
Issuer = Literal["EU_Parliament_Council", "EU_Commission", "ESMA", "AMF", "FR_Legislator"]
Language = Literal["EN", "FR"]
AlignmentStatus = Literal["match_exact", "match_fuzzy"]


class Source(BaseModel):
    source_id: str = Field(description="Stable identifier, e.g. 'AIFMD_L1#art_15_para_3'")
    title: str
    celex: str | None = Field(default=None, description="EUR-Lex CELEX number when applicable")
    level: Level
    issuer: Issuer
    article: str | None = None
    paragraph: str | None = None
    point: str | None = None
    url: str
    language: Language
    publication_date: date | None = None
    char_interval: tuple[int, int] | None = Field(
        default=None,
        description="Character offsets in source text, populated by LangExtract grounding",
    )
    alignment_status: AlignmentStatus | None = None
