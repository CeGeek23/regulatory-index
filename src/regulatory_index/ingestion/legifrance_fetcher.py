"""Fetch French legislative articles via the Légifrance public DILA API.

Légifrance exposes a public REST API at api.piste.gouv.fr/dila/legifrance/lf-engine-app
that returns structured JSON for any LEGIARTI/LEGITEXT identifier. Authentication
is required for production use; for the POC we fall back to scraping the public
HTML at legifrance.gouv.fr (DOM structure is stable, no regex).

For the small real corpus, we target Code monétaire et financier (CMF) articles
related to AIFMD transposition, e.g. L. 214-24-8 (depositary duties).
"""

from __future__ import annotations

from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from ._disk import persist_html
from .unit_loader import NormativeUnit

USER_AGENT = "regulatory-index-poc/0.1 (research; contact: tchakontecedrick@gmail.com)"


def legifrance_url(article_id: str) -> str:
    """e.g. article_id = 'LEGIARTI000027780446' (CMF article L. 214-24-8)."""
    return f"https://www.legifrance.gouv.fr/codes/article_lc/{article_id}"


def fetch_html(article_id: str, *, timeout: float = 30.0) -> str:
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        response = client.get(legifrance_url(article_id))
        response.raise_for_status()
    return response.text


def fetch_to_disk(article_id: str, out_dir: Path) -> Path:
    return persist_html(fetch_html(article_id), out_dir, article_id)


def parse_article(
    html: str,
    *,
    source_id: str,
    article_id: str,
    article_number: str,
    title: str,
    level: int | str,
    issuer: str,
    url: str,
) -> list[NormativeUnit]:
    soup = BeautifulSoup(html, "lxml")
    body_div = soup.find("div", class_="article-content") or soup.find("div", id="contenu_article")
    if body_div is None:
        body_div = soup.body
    if body_div is None:
        return []
    paragraphs = [" ".join(p.get_text(" ").split()) for p in body_div.find_all(["p", "li"])]
    body = "\n".join(p for p in paragraphs if p)
    if not body:
        return []
    return [
        NormativeUnit(
            unit_id=f"{source_id}#fr#art_{article_number.replace(' ', '_').replace('.', '_')}",
            source_id=source_id,
            hierarchy_path=f"Article {article_number}",
            text=f"Article {article_number}\n\n{body}",
            language="FR",
            source_meta={
                "title": title,
                "level": level,
                "issuer": issuer,
                "article": article_number,
                "legifrance_id": article_id,
                "url": url,
            },
        )
    ]
