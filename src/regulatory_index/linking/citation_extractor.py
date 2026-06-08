"""Résout les chaînes `cited_references` vers des source_ids connus par correspondance d'alias.

Sans regex : simple recherche de sous-chaîne insensible à la casse dans l'index
des alias construit depuis config/sources_registry.yaml. Renvoie un target_source
candidat par citation qui correspond ; les citations non résolues sont reportées à part.

On parse aussi le numéro d'article cité par tokenisation de chaîne (toujours
sans regex), afin que le constructeur de graphe puisse relier aux obligations cibles
précises de cet article plutôt qu'au seul nœud document.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.obligation import Obligation
from ..schemas.sources_registry import load_alias_index

# Tokens qui introduisent un numéro d'article, EN + FR (minuscules, ponctuation retirée).
_ARTICLE_KEYWORDS = frozenset({"article", "articles", "art"})
# Ponctuation qui sépare les tokens dans une citation. Les parenthèses sont incluses pour
# que "Article 15(3)" se tokenise en ["article", "15", "3"] et qu'on garde l'article.
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
    """Met en minuscules, remplace la ponctuation de citation par des espaces, découpe sur les blancs."""
    folded = "".join(" " if ch in _CITATION_PUNCT else ch for ch in citation.lower())
    return folded.split()


def normalize_article(value: str) -> str:
    """Forme canonique pour la correspondance : minuscules, sans espaces internes ('15 a' -> '15a')."""
    return "".join(value.lower().split())


def parse_article_locator(citation: str) -> str | None:
    """Renvoie le premier numéro d'article cité (ex. '15' depuis 'Article 15(3) ...'), sinon None.

    Tokenisation de chaîne pure, sans regex. Reconnaît les formes EN/FR ('Article', 'article',
    'Art.', 'articles'). Prend le premier token commençant par un chiffre dans les 3
    tokens qui suivent le mot-clé, donc 'Article 15(3)' -> '15' et 'Articles 38 to 40' -> '38' (premier
    article seulement ; les citations multi-articles ne sont pas entièrement développées).
    """
    tokens = _tokenize(citation)
    for i, tok in enumerate(tokens):
        if tok in _ARTICLE_KEYWORDS:
            for nxt in tokens[i + 1 : i + 4]:
                if nxt and nxt[0].isdigit():
                    return nxt
    return None


def resolve_citation(citation: str) -> str | None:
    """Renvoie le source_id dont l'alias le plus long est une sous-chaîne de citation, sinon None."""
    needle = citation.lower()
    for alias, source_id in load_alias_index():
        if alias and alias in needle:
            return source_id
    return None


def resolve_all(
    obligations: list[Obligation],
) -> tuple[list[ResolvedCitation], list[UnresolvedCitation]]:
    """Parcourt les cited_references de chaque obligation ; classe chacune en résolue/non résolue."""
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
