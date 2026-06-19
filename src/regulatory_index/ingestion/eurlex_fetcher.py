"""Récupère les actes EUR-Lex en HTML, via l'API Cellar de l'Office des publications.

Le rendu HTML public d'EUR-Lex (`legal-content/.../TXT/HTML`) est protégé par un WAF
anti-bot (réponse HTTP 202 + page de challenge) inexploitable en script. L'API **Cellar**
de l'Office des publications sert le **même contenu** (XHTML « Journal Officiel », classes
`oj-*` / `eli-*`) par négociation de contenu, **sans WAF** :

    http://publications.europa.eu/resource/celex/{CELEX}
    en-têtes : Accept: application/xhtml+xml ; Accept-Language: eng|fra

La structure reste prévisible (`div.eli-subdivision`, `p.oj-ti-art`, ...), donc parsée
structurellement avec BeautifulSoup, sans aucune regex sur le corps.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from ._disk import persist_html

USER_AGENT = "regulatory-index-poc/0.1 (research; contact: tchakontecedrick@gmail.com)"
CELLAR_URL = "http://publications.europa.eu/resource/celex/{celex}"
# Cellar attend les codes langue ISO 639-2/B à 3 lettres.
_LANGUAGE_CODE = {"EN": "eng", "FR": "fra"}


def cellar_url(celex: str) -> str:
    """URL Cellar pour un CELEX ; la langue est négociée via l'en-tête Accept-Language."""
    return CELLAR_URL.format(celex=celex)


def language_code(language: str) -> str:
    """Code langue 3 lettres attendu par Cellar (EN -> eng, FR -> fra)."""
    return _LANGUAGE_CODE.get(language.upper(), language.lower())


def fetch_html(celex: str, language: str, *, timeout: float = 45.0) -> str:
    """Récupère le XHTML EUR-Lex (via Cellar) pour (celex, langue). Lève en cas d'erreur HTTP."""
    with httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/xhtml+xml, text/html",
            "Accept-Language": language_code(language),
        },
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        response = client.get(cellar_url(celex))
        response.raise_for_status()
    return response.text


def fetch_to_disk(celex: str, language: str, out_dir: Path) -> Path:
    """Écrit le HTML brut sur disque. Le nom de fichier est reproductible à partir de (celex, langue, sha256)."""
    return persist_html(fetch_html(celex, language), out_dir, f"{celex}_{language.upper()}")
