"""Récupère les pages de doctrine AMF (Positions, Recommandations, Instructions).

L'AMF publie sa doctrine à :
    https://www.amf-france.org/fr/reglementation/doctrine/{DOC_CODE}

Des PDF sont aussi liés mais on les évite volontairement. Ce fetcher télécharge
seulement le HTML ; le parser collecte les paragraphes et titres (`<p>`, `<li>`,
`<h2>`-`<h4>`) du conteneur `<main>` et les concatène (pas de regex ; on s'appuie
sur la structure du DOM).

Note : le HTML de l'AMF est bien moins standardisé que celui d'EUR-Lex. Le parser ici
fait au mieux et produit UNE NormativeUnit par document de doctrine (tout le texte
opérationnel), avec hierarchy_path = titre de la doctrine. Le découpage par section
n'est pas implémenté.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from ._disk import persist_html
from .unit_loader import NormativeUnit

USER_AGENT = "regulatory-index-poc/0.1 (research; contact: tchakontecedrick@gmail.com)"

# Les pages AMF mêlent texte opérationnel et liens de navigation / libellés courts ; on ignore
# les fragments <p>/<li> plus courts que ceci pour que menus et items d'un mot ne polluent pas le corps.
_MIN_PARAGRAPH_CHARS = 20


def amf_url(doc_code: str) -> str:
    return f"https://www.amf-france.org/fr/reglementation/doctrine/{doc_code.lower()}"


def fetch_html(doc_code: str, *, timeout: float = 30.0) -> str:
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        response = client.get(amf_url(doc_code))
        response.raise_for_status()
    return response.text


def fetch_to_disk(doc_code: str, out_dir: Path) -> Path:
    return persist_html(fetch_html(doc_code), out_dir, doc_code)


def parse_doctrine(
    html: str,
    *,
    source_id: str,
    doc_code: str,
    title: str,
    level: int | str,
    issuer: str,
    url: str,
) -> list[NormativeUnit]:
    """Extrait le texte opérationnel en une seule NormativeUnit (tout le document de doctrine)."""
    soup = BeautifulSoup(html, "lxml")
    # L'AMF englobe le contenu opérationnel dans une balise <main>. On récupère tous
    # les paragraphes et titres dans <main> pour ignorer les menus/pieds de page.
    main = soup.find("main") or soup.body
    if main is None:
        return []
    paragraphs: list[str] = []
    for p in main.find_all(["p", "li", "h2", "h3", "h4"]):
        text = " ".join(p.get_text(" ").split())
        if text and len(text) > _MIN_PARAGRAPH_CHARS:
            paragraphs.append(text)
    body = "\n".join(paragraphs)
    if not body:
        return []
    return [
        NormativeUnit(
            unit_id=f"{source_id}#fr#full",
            source_id=source_id,
            hierarchy_path=title,
            text=f"{title}\n\n{body}",
            language="FR",
            source_meta={
                "title": title,
                "level": level,
                "issuer": issuer,
                "doc_code": doc_code,
                "url": url,
            },
        )
    ]
