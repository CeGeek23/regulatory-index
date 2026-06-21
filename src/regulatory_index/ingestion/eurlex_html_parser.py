"""Parse le HTML EUR-Lex en objets NormativeUnit, un par article.

Mise en page HTML EUR-Lex (classes Journal Officiel `oj-*` + ELI `eli-*`) :
    <div class="eli-container">
      <div class="eli-subdivision" id="art_15">
        <p class="oj-ti-art">Article 15</p>
        <p class="oj-sti-art">Risk management</p>
        <div class="eli-subdivision" id="art_15.1">
          <p class="oj-normal">1.   AIFMs shall ...</p>
        </div>
        ...
      </div>
    </div>

On extrait une NormativeUnit par div `id="art_N"`. Le corps est la
concaténation des paragraphes `<p>` de l'article (hors paragraphes titre/sous-titre)
dans l'ordre du document, joints par des sauts de ligne. Pas de regex ; pure traversée du DOM.
"""

from __future__ import annotations

import warnings

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from .unit_loader import NormativeUnit

# EUR-Lex sert du HTML "Office Journal" que bs4 détecte parfois comme XML ; on parse
# volontairement en HTML (lxml), donc on neutralise cet avertissement spécifique.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def _clean_whitespace(s: str) -> str:
    return " ".join(s.split())


# Classe du paragraphe de titre d'article : "oj-ti-art" dans le rendu de base, et
# "title-article-norm" dans les versions CONSOLIDÉES (même structure eli-subdivision,
# classes renommées). On accepte les deux.
_ARTICLE_TITLE_CLASSES = ("oj-ti-art", "title-article-norm")


def _find_article_title(article_div: Tag) -> Tag | None:
    for css_class in _ARTICLE_TITLE_CLASSES:
        title = article_div.find("p", class_=css_class)
        if isinstance(title, Tag):
            return title
    return None


def _extract_article_number(article_div: Tag) -> str | None:
    """Le paragraphe de titre contient 'Article 15' / 'Article 15 a'."""
    title = _find_article_title(article_div)
    if title is None:
        return None
    text = _clean_whitespace(title.get_text(" "))
    # 'Article 15' -> '15' ; 'Article 15 a' -> '15 a' ; pur DOM, pas de regex
    prefix = "Article "
    if text.startswith(prefix):
        return text[len(prefix) :].strip() or None
    return text.strip() or None


def _extract_article_subtitle(article_div: Tag) -> str | None:
    """Le paragraphe 'oj-sti-art' contient le sous-titre de l'article (ex. 'Risk management')."""
    sub = article_div.find("p", class_="oj-sti-art")
    if sub is None:
        return None
    return _clean_whitespace(sub.get_text(" ")) or None


def _extract_article_body(article_div: Tag) -> str:
    """Retourne le texte littéral de l'article sans les paragraphes titre/sous-titre."""
    title = _find_article_title(article_div)
    subtitle = article_div.find("p", class_="oj-sti-art")
    skip_ids = {id(title), id(subtitle)}
    chunks: list[str] = []
    for descendant in article_div.descendants:
        if isinstance(descendant, Tag) and descendant.name == "p":
            if id(descendant) in skip_ids:
                continue
            text = _clean_whitespace(descendant.get_text(" "))
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def parse_articles(
    html: str,
    *,
    source_id: str,
    celex: str,
    language: str,
    title: str,
    level: int | str,
    issuer: str,
    url: str,
    keep: set[str] | None = None,
) -> list[NormativeUnit]:
    """Retourne une NormativeUnit par article. `keep` filtre par numéro d'article."""
    language = language.upper()
    if language not in ("EN", "FR"):
        raise ValueError(f"Langue non supportée : {language!r} (attendu 'EN' ou 'FR').")
    soup = BeautifulSoup(html, "lxml")

    units: list[NormativeUnit] = []
    seen: set[str] = set()
    for div in soup.select('div.eli-subdivision[id^="art_"]'):
        elem_id = str(div.get("id") or "")
        # Ignore les sous-éléments comme 'art_15.1', on ne veut que les articles de premier niveau.
        if "." in elem_id:
            continue

        article_num = _extract_article_number(div)
        if article_num is None:
            continue
        # Dédup sur le NUMÉRO d'article extrait, pas sur l'id HTML : EUR-Lex (consolidé) peut donner
        # deux articles DISTINCTS partageant le même id (ex. « Article 69a » et « Article 69-a »).
        if article_num in seen:
            continue
        seen.add(article_num)
        if keep is not None and article_num not in keep:
            continue

        subtitle = _extract_article_subtitle(div)
        body = _extract_article_body(div)
        if not body:
            continue

        hierarchy = f"Article {article_num}" + (f" — {subtitle}" if subtitle else "")
        unit = NormativeUnit(
            unit_id=f"{source_id}#{language.lower()}#art_{article_num.replace(' ', '_')}",
            source_id=source_id,
            hierarchy_path=hierarchy,
            text=f"{hierarchy}\n\n{body}",
            language=language,  # type: ignore[arg-type]
            source_meta={
                "title": title,
                "celex": celex,
                "level": level,
                "issuer": issuer,
                "article": article_num,
                "url": url,
                "subtitle": subtitle,
            },
        )
        units.append(unit)
    return units
