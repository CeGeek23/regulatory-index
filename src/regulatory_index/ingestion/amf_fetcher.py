"""Fetch AMF doctrine pages (Positions, Recommendations, Instructions).

AMF publishes its doctrine at:
    https://www.amf-france.org/fr/reglementation/doctrine/{DOC_CODE}

These pages embed a `<div class="amf-content">` or similar container with the
operative text in `<p>` tags. PDFs are also linked but we avoid them on
purpose. This fetcher just downloads the HTML; the parser extracts numbered
sections heuristically (no regex; we rely on DOM structure).

Note: AMF HTML is much less standardised than EUR-Lex. The parser here is
best-effort and produces ONE NormativeUnit per doctrine document (the whole
operative text), with hierarchy_path = doctrine title. Per-section splitting
is a refinement for later.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .unit_loader import NormativeUnit

USER_AGENT = "regulatory-index-poc/0.1 (research; contact: tchakontecedrick@gmail.com)"


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
    html = fetch_html(doc_code)
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    path = out_dir / f"{doc_code}_{sha}.html"
    path.write_text(html, encoding="utf-8")
    return path


def parse_doctrine(
    html: str,
    *,
    source_id: str,
    doc_code: str,
    title: str,
    url: str,
) -> list[NormativeUnit]:
    """Extract the operative text as one NormativeUnit (whole doctrine document)."""
    soup = BeautifulSoup(html, "lxml")
    # AMF wraps the operative content in a main article tag. We pull all
    # paragraphs and headings inside <main> to skip menus/footers.
    main = soup.find("main") or soup.body
    if main is None:
        return []
    paragraphs: list[str] = []
    for p in main.find_all(["p", "li", "h2", "h3", "h4"]):
        text = " ".join(p.get_text(" ").split())
        if text and len(text) > 20:  # skip nav links and tiny tags
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
                "level": "national",
                "issuer": "AMF",
                "doc_code": doc_code,
                "url": url,
            },
        )
    ]
