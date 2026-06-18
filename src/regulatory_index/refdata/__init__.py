"""Données de référence chargées depuis `config/` : vocabulaires contrôlés + registre des sources.

Séparé des `schemas/` (modèles de données purs) : ici on *charge* et *résout* des YAML
de configuration (vocab actors/actions/objects/themes/conditions/acronyms, registre des
sources + alias de citation).
"""

from __future__ import annotations

from .sources_registry import RegistryEntry, load_alias_index, load_sources_registry
from .vocab import (
    Acronym,
    VocabEntry,
    Vocabulary,
    load_acronyms,
    load_all_vocabularies,
    load_vocabulary,
)

__all__ = [
    "Acronym",
    "RegistryEntry",
    "VocabEntry",
    "Vocabulary",
    "load_acronyms",
    "load_alias_index",
    "load_all_vocabularies",
    "load_sources_registry",
    "load_vocabulary",
]
