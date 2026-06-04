"""Resolve `cited_references` strings to known source_ids using alias matching.

No regex: pure case-insensitive substring lookup against the alias index built
from config/sources_registry.yaml. Returns one candidate target_source per
citation that matches; unmatched citations are reported separately.

We also parse the cited *article* number with plain string tokenisation (still
no regex), so the graph builder can link to the specific target obligations of
that article rather than only the document node.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.obligation import Obligation
from ..schemas.sources_registry import load_alias_index

# Tokens that introduce an article number, EN + FR (lowercased, punctuation-stripped).
_ARTICLE_KEYWORDS = frozenset({"article", "articles", "art"})
# Punctuation that separates tokens inside a citation. Parentheses are included so
# that "Article 15(3)" tokenises to ["article", "15", "3"] and we keep the article.
_CITATION_PUNCT = "()[]{},;:.§/"


@dataclass(frozen=True)
class ResolvedCitation:
    obligation_id: str
    citation_text: str
    target_source_id: str
    target_article: str | None = None


@dataclass(frozen=True)
class UnresolvedCitation:
    obligation_id: str
    citation_text: str


def _tokenize(citation: str) -> list[str]:
    """Lowercase, replace citation punctuation with spaces, split on whitespace."""
    folded = "".join(" " if ch in _CITATION_PUNCT else ch for ch in citation.lower())
    return folded.split()


def normalize_article(value: str) -> str:
    """Canonical form for matching: lowercase, no internal spaces ('15 a' -> '15a')."""
    return "".join(value.lower().split())


def parse_article_locator(citation: str) -> str | None:
    """Return the first cited article number (e.g. '15' from 'Article 15(3) ...'), else None.

    Pure string tokenisation, no regex. Recognises EN/FR forms ('Article', 'article',
    'Art.', 'articles'). Picks the first digit-leading token shortly after the
    keyword, so 'Article 15(3)' -> '15' and 'Articles 38 to 40' -> '38' (first
    article only; multi-article citations are not fully expanded).
    """
    tokens = _tokenize(citation)
    for i, tok in enumerate(tokens):
        if tok in _ARTICLE_KEYWORDS:
            for nxt in tokens[i + 1 : i + 4]:
                if nxt and nxt[0].isdigit():
                    return nxt
    return None


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
                        target_article=parse_article_locator(citation),
                    )
                )
    return resolved, unresolved
