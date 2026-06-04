from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .source import Source


class Obligation(BaseModel):
    """A single normative requirement extracted from a regulatory text.

    The vocabulary fields actor, action, object and theme are canonicalised to a
    pivot label (FR/EN folded to one form) in `obligation_builder._canonicalize`;
    values outside the controlled vocabularies are kept verbatim and surfaced by
    `obligation_builder.collect_vocab_gaps`. They are typed as `str` here to keep the
    schema decoupled from the YAML files. (sub_theme and condition are free text.)
    """

    obligation_id: str = Field(
        description="Format SCOPE-THEME_CODE-NNNN, e.g. AIFMD-RISK-0042, MIFID2-EXEC-0017",
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

    @field_validator("obligation_id")
    @classmethod
    def _check_id_format(cls, v: str) -> str:
        """Validate SCOPE-THEME_CODE-NNNN with plain string ops (no regex).

        SCOPE: >=2 uppercase alphanumerics starting with a letter (e.g. AIFMD, MIFID2).
        THEME_CODE: uppercase letters (e.g. RISK). NNNN: a 3-4 digit number.
        """
        scope, theme, number = v.split("-") if v.count("-") == 2 else ("", "", "")
        valid = (
            len(scope) >= 2
            and scope[0].isalpha()
            and scope.isalnum()
            and scope.isupper()
            and theme.isalpha()
            and theme.isupper()
            and number.isdigit()
            and 3 <= len(number) <= 4
        )
        if not valid:
            raise ValueError(
                f"obligation_id {v!r} must be SCOPE-THEME_CODE-NNNN (e.g. AIFMD-RISK-0042)"
            )
        return v
