"""Resolve `cited_references` strings to known source_ids using alias matching.

No regex: pure case-insensitive substring lookup against the alias index built
from config/sources_registry.yaml. Returns one candidate target_source per
citation that matches; unmatched citations are reported separately.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.obligation import Obligation
from ..schemas.sources_registry import load_alias_index


@dataclass(frozen=True)
class ResolvedCitation:
    obligation_id: str
    citation_text: str
    target_source_id: str


@dataclass(frozen=True)
class UnresolvedCitation:
    obligation_id: str
    citation_text: str


def resolve_citation(citation: str) -> str | None:
    """Return the source_id whose longest alias is a substring of citation, else None."""
    needle = citation.lower()
    for alias, source_id in load_alias_index():
        if alias and alias in needle:
            return source_id
    return None


def resolve_all(
    obligations: list[Obligation],
) -> tuple[list[ResolvedCitation], list[UnresolvedCitation]]:
    """Walk every obligation's cited_references; classify each as resolved/unresolved."""
    resolved: list[ResolvedCitation] = []
    unresolved: list[UnresolvedCitation] = []
    for ob in obligations:
        for citation in ob.cited_references:
            target = resolve_citation(citation)
            if target is None:
                unresolved.append(
                    UnresolvedCitation(obligation_id=ob.obligation_id, citation_text=citation)
                )
            else:
                resolved.append(
                    ResolvedCitation(
                        obligation_id=ob.obligation_id,
                        citation_text=citation,
                        target_source_id=target,
                    )
                )
    return resolved, unresolved
