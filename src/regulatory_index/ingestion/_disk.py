"""Utilitaire commun : écrire le HTML récupéré sur disque avec un nom basé sur un hash du contenu.

Chaque fetcher écrit son HTML brut de la même façon — `{stem}_{sha}.html` où `sha`
correspond aux 12 premiers caractères hexadécimaux du SHA-256 du contenu — afin que le
chemin soit stable et que les re-téléchargements d'un contenu identique pointent vers le
même fichier. Seul le `stem` diffère selon le fetcher (CELEX+langue / code doc / id article).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def persist_html(html: str, out_dir: Path, stem: str) -> Path:
    """Écrit `html` dans `{out_dir}/{stem}_{sha}.html` et retourne le chemin."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    path = out_dir / f"{stem}_{sha}.html"
    path.write_text(html, encoding="utf-8")
    return path
