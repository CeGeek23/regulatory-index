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

from bs4 import BeautifulSoup, Tag

from .unit_loader import NormativeUnit


def _clean_whitespace(s: str) -> str:
    return " ".join(s.split())


def _extract_article_number(article_div: Tag) -> str | None:
    """Le paragraphe 'oj-ti-art' contient 'Article 15' / 'Article 15 a'."""
    title = article_div.find("p", class_="oj-ti-art")
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
    title = article_div.find("p", class_="oj-ti-art")
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
    soup = BeautifulSoup(html, "lxml")

    units: list[NormativeUnit] = []
    seen: set[str] = set()
    for div in soup.select('div.eli-subdivision[id^="art_"]'):
        elem_id_raw = div.get("id") or ""
        elem_id = elem_id_raw if isinstance(elem_id_raw, str) else " ".join(elem_id_raw)
        # Ignore les sous-éléments comme 'art_15.1', on ne veut que les articles de premier niveau.
        if "." in elem_id:
            continue
        if elem_id in seen:
            continue
        seen.add(elem_id)

        article_num = _extract_article_number(div)
        if article_num is None:
            continue
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
