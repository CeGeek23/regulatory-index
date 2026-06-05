"""Récupère les actes EUR-Lex en HTML (mise en page Journal Officiel, sans PDF).

EUR-Lex fournit un rendu HTML stable à :
    https://eur-lex.europa.eu/legal-content/{LANG}/TXT/HTML/?uri=CELEX:{CELEX}

La structure HTML est prévisible (`div.eli-subdivision`, `p.oj-normal`, etc.),
ce qui permet d'extraire les articles structurellement avec BeautifulSoup sans
aucune regex sur le corps.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from ._disk import persist_html

USER_AGENT = "regulatory-index-poc/0.1 (research; contact: tchakontecedrick@gmail.com)"


def eurlex_url(celex: str, language: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/{language.upper()}/TXT/HTML/?uri=CELEX:{celex}"


def fetch_html(celex: str, language: str, *, timeout: float = 30.0) -> str:
    """Récupère le HTML EUR-Lex d'un CELEX dans une langue donnée. Lève une exception en cas d'erreur HTTP."""
    url = eurlex_url(celex, language)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
    return response.text


def fetch_to_disk(celex: str, language: str, out_dir: Path) -> Path:
    """Écrit le HTML brut sur disque. Le nom de fichier est reproductible à partir de (celex, langue, sha256)."""
    return persist_html(fetch_html(celex, language), out_dir, f"{celex}_{language.upper()}")
