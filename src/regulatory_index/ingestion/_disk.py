"""Shared helper: persist fetched HTML to disk with a content-hashed filename.

Every fetcher writes its raw HTML the same way — `{stem}_{sha}.html` where `sha`
is the first 12 hex chars of the SHA-256 of the content — so the path is stable
and re-downloads of identical content collide on the same file. Only the `stem`
differs per fetcher (CELEX+lang / doc code / article id).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def persist_html(html: str, out_dir: Path, stem: str) -> Path:
    """Write `html` to `{out_dir}/{stem}_{sha}.html` and return the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    path = out_dir / f"{stem}_{sha}.html"
    path.write_text(html, encoding="utf-8")
    return path
