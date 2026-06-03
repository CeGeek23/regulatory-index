"""Fetch EUR-Lex acts as HTML (Office Journal layout, no PDF needed).

EUR-Lex serves a stable HTML rendering at:
    https://eur-lex.europa.eu/legal-content/{LANG}/TXT/HTML/?uri=CELEX:{CELEX}

The HTML structure is predictable (`div.eli-subdivision`, `p.oj-normal` etc.),
which lets us extract articles structurally with BeautifulSoup without any
regex on the body.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

USER_AGENT = "regulatory-index-poc/0.1 (research; contact: tchakontecedrick@gmail.com)"


def eurlex_url(celex: str, language: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/{language.upper()}/TXT/HTML/?uri=CELEX:{celex}"


def fetch_html(celex: str, language: str, *, timeout: float = 30.0) -> str:
    """Fetch the EUR-Lex HTML for a CELEX in a given language. Raises on HTTP error."""
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
    """Persist the raw HTML on disk. Filename is reproducible from (celex, lang, sha256)."""
    html = fetch_html(celex, language)
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    path = out_dir / f"{celex}_{language.upper()}_{sha}.html"
    path.write_text(html, encoding="utf-8")
    return path
