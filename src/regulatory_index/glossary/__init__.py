"""Extraction du glossaire et du sommaire d'un acte EUR-Lex, à partir de son contenu.

Ce sous-paquet part directement du **texte de l'acte** (HTML EUR-Lex tel qu'il est déjà
stocké dans une base d'actes) — pas d'acquisition réseau. Trois briques :

- `models`                      -> DefinedTerm, TableOfContents (modèles du domaine glossaire)
- `build_toc(html, ...)`        -> TableOfContents (sommaire ; localise l'article de définitions)
- `harvest_glossary(html_en, html_fr, ...)` -> list[DefinedTerm] (termes définis, bilingue)

Tout est déterministe (parcours DOM + tokenisation `str`), sans regex, conformément aux
règles du projet.
"""

from __future__ import annotations

from .definitions import ParsedPoint, harvest_glossary, parse_points
from .models import DefinedTerm, TableOfContents, TocArticle, TocSection
from .toc import build_toc

__all__ = [
    "DefinedTerm",
    "ParsedPoint",
    "TableOfContents",
    "TocArticle",
    "TocSection",
    "build_toc",
    "harvest_glossary",
    "parse_points",
]
