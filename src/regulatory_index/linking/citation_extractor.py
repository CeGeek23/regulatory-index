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

from ..refdata.sources_registry import load_alias_index
from ..schemas.obligation import Obligation

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


def _matches_as_token(needle: str, alias: str) -> bool:
    """`alias` présent dans `needle` avec frontières de mot (caractères adjacents non alphanumériques).

    Évite les faux positifs de sous-chaîne : 'aifmd' ne matche pas 'aifmdx', 'cmf' pas 'cmfp',
    '2011/61/eu' pas '2011/61/eur'. Sans regex.
    """
    if not alias:
        return False
    start = 0
    while (i := needle.find(alias, start)) != -1:
        before = needle[i - 1] if i > 0 else " "
        after_idx = i + len(alias)
        after = needle[after_idx] if after_idx < len(needle) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        start = i + 1
    return False


def resolve_citations(citation: str) -> list[str]:
    """Tous les source_ids dont un alias matche (en token) dans la citation, dédupliqués.

    Une citation peut viser PLUSIEURS textes (ex. « Règlement 231/2013 pris en application de la
    Directive 2011/61/UE » → AIFMD_L2 et AIFMD_L1). Ordre déterministe (alias les plus longs d'abord).
    """
    needle = citation.lower()
    seen: set[str] = set()
    out: list[str] = []
    for alias, source_id in load_alias_index():
        if source_id not in seen and _matches_as_token(needle, alias):
            seen.add(source_id)
            out.append(source_id)
    return out


def resolve_all(
    obligations: list[Obligation],
) -> tuple[list[ResolvedCitation], list[UnresolvedCitation]]:
    """Parcourt les cited_references de chaque obligation ; classe chacune en résolue/non résolue."""
    resolved: list[ResolvedCitation] = []
    unresolved: list[UnresolvedCitation] = []
    for ob in obligations:
        for citation in ob.cited_references:
            targets = resolve_citations(citation)
            if not targets:
                unresolved.append(
                    UnresolvedCitation(obligation_id=ob.obligation_id, citation_text=citation)
                )
                continue
            article = parse_article_locator(citation)
            for target in targets:  # une citation peut viser plusieurs textes
                resolved.append(
                    ResolvedCitation(
                        obligation_id=ob.obligation_id,
                        citation_text=citation,
                        target_source_id=target,
                        target_article=article,
                    )
                )
    return resolved, unresolved
