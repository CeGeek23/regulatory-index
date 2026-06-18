"""Sommaire (table des matières) d'un acte EUR-Lex, depuis son HTML.

Mise en page Journal Officiel :
    <p class="oj-ti-section-1">CHAPTER II</p>             -> libellé de chapitre/section
    <p class="oj-ti-section-2">AUTHORISATION OF AIFMs</p>  -> son titre
    <p class="oj-ti-art">Article 6</p>                     -> article
    <p class="oj-sti-art">Conditions for ...</p>           -> sous-titre

Parcours du DOM dans l'ordre du document, aucune regex. Générique : fonctionne sur
n'importe quel acte EUR-Lex, pas seulement AIFMD.
"""

from __future__ import annotations

import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from ..schemas.source import Language
from .models import TableOfContents, TocArticle, TocSection

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Sous-titres d'article qui marquent l'article de définitions, EN + FR (minuscule).
_DEFINITION_SUBTITLES = frozenset({"definitions", "définitions"})

_SECTION_LABEL = "oj-ti-section-1"
_SECTION_TITLE = "oj-ti-section-2"
_ARTICLE_TITLE = "oj-ti-art"
_ARTICLE_SUBTITLE = "oj-sti-art"
_INTERESTING = frozenset({_SECTION_LABEL, _SECTION_TITLE, _ARTICLE_TITLE, _ARTICLE_SUBTITLE})

_ARTICLE_PREFIX = "Article "


def _clean(text: str) -> str:
    return " ".join(text.split())


def build_toc(html: str, *, source_id: str, language: Language) -> TableOfContents:
    """Construit le sommaire d'un acte depuis son HTML EUR-Lex."""
    soup = BeautifulSoup(html, "lxml")
    sections: list[TocSection] = []
    current: TocSection | None = None
    current_article: TocArticle | None = None

    def ensure_section() -> TocSection:
        nonlocal current
        if current is None:
            current = TocSection(label="", title="")
            sections.append(current)
        return current

    for p in soup.find_all("p"):
        classes = set(p.get("class") or [])
        hit = classes & _INTERESTING
        if not hit:
            continue
        kind = next(iter(hit))
        text = _clean(p.get_text(" "))
        if not text:
            continue

        if kind == _SECTION_LABEL:
            current = TocSection(label=text, title="")
            sections.append(current)
            current_article = None
        elif kind == _SECTION_TITLE:
            if current is not None and not current.title:
                current.title = text
        elif kind == _ARTICLE_TITLE:
            number = text[len(_ARTICLE_PREFIX) :].strip() if text.startswith(_ARTICLE_PREFIX) else text
            current_article = TocArticle(article=number)
            ensure_section().articles.append(current_article)
        elif kind == _ARTICLE_SUBTITLE:
            if current_article is not None and current_article.subtitle is None:
                current_article.subtitle = text
                if text.strip().lower() in _DEFINITION_SUBTITLES:
                    current_article.is_definitions = True

    return TableOfContents(source_id=source_id, language=language, sections=sections)
