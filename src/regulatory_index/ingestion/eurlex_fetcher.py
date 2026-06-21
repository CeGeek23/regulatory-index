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
    # Le WAF EUR-Lex répond par un challenge en HTTP 202 (un 2xx, donc raise_for_status ne lève
    # PAS) : on exige explicitement 200 + un corps non vide pour ne pas prendre une page de
    # challenge (ou un 204) pour du contenu légitime.
    if response.status_code != 200 or not response.text.strip():
        raise httpx.HTTPStatusError(
            f"Réponse inattendue {response.status_code} pour CELEX {celex} "
            f"(WAF/challenge probable, corps de {len(response.text)} car.)",
            request=response.request,
            response=response,
        )
    return response.text


def latest_consolidated_celex(base_celex: str, *, timeout: float = 60.0) -> str | None:
    """CELEX de la dernière version CONSOLIDÉE (« à jour ») d'un acte, sinon None.

    Lit les métadonnées RDF Cellar de l'acte de base et y cherche les CELEX consolidés
    (préfixe « 0 » + corps, suffixe -AAAAMMJJ), puis retient la date la plus récente.
    Ex. base 32009L0065 -> 02009L0065-20240109. Tokenisation `str`, sans regex.
    """
    prefix = "0" + base_celex[1:]
    needle = f"celex/{prefix}-"
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/rdf+xml"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        rdf = client.get(cellar_url(base_celex)).text
    dates: set[str] = set()
    cursor = 0
    while True:
        pos = rdf.find(needle, cursor)
        if pos == -1:
            break
        date = rdf[pos + len(needle) : pos + len(needle) + 8]
        if date.isdigit():
            dates.add(date)
        cursor = pos + len(needle)
    return f"{prefix}-{max(dates)}" if dates else None


def fetch_to_disk(celex: str, language: str, out_dir: Path) -> Path:
    """Écrit le HTML brut sur disque. Le nom de fichier est reproductible à partir de (celex, langue, sha256)."""
    return persist_html(fetch_html(celex, language), out_dir, f"{celex}_{language.upper()}")
