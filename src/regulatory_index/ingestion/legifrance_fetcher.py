"""Récupère les articles législatifs français via l'API publique DILA de Légifrance.

Légifrance expose une API REST publique sur api.piste.gouv.fr/dila/legifrance/lf-engine-app
qui retourne du JSON structuré pour tout identifiant LEGIARTI/LEGITEXT. Une authentification
est requise en production ; pour le POC on se rabat sur le scraping du HTML public de
legifrance.gouv.fr (structure du DOM stable, pas de regex).

Pour le petit corpus réel, on cible les articles du Code monétaire et financier (CMF)
liés à la transposition de l'AIFMD, ex. L. 214-24-8 (obligations du dépositaire).
"""

from __future__ import annotations

from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from ._disk import persist_html
from .unit_loader import NormativeUnit

USER_AGENT = "regulatory-index-poc/0.1 (research; contact: tchakontecedrick@gmail.com)"


def legifrance_url(article_id: str) -> str:
    """ex. article_id = 'LEGIARTI000027780446' (article L. 214-24-8 du CMF)."""
    return f"https://www.legifrance.gouv.fr/codes/article_lc/{article_id}"


def fetch_html(article_id: str, *, timeout: float = 30.0) -> str:
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        response = client.get(legifrance_url(article_id))
        response.raise_for_status()
    if response.status_code != 200 or not response.text.strip():  # WAF/challenge en 202 (un 2xx)
        raise httpx.HTTPStatusError(
            f"Réponse inattendue {response.status_code} pour {article_id} (challenge probable).",
            request=response.request, response=response,
        )
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
