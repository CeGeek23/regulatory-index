"""Chargeur pour config/sources_registry.yaml — mappe source_id vers les métadonnées Source complètes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from ..schemas.source import Issuer, Language, Level

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "sources_registry.yaml"
)


@dataclass(frozen=True)
class RegistryEntry:
    source_id: str
    celex: str | None
    title: str
    level: Level
    issuer: Issuer
    language: Language
    url: str
    aliases: tuple[str, ...]


@cache
def load_sources_registry() -> dict[str, RegistryEntry]:
    """Retourne {source_id: RegistryEntry}."""
    with REGISTRY_PATH.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f) or []
    out: dict[str, RegistryEntry] = {}
    for item in raw:
        entry = RegistryEntry(
            source_id=str(item["source_id"]),
            celex=item.get("celex"),
            title=str(item["title"]),
            level=item["level"],
            issuer=item["issuer"],
            language=item["language"],
            url=str(item["url"]),
            aliases=tuple(item.get("aliases") or []),
        )
        out[entry.source_id] = entry
    return out


@cache
def load_alias_index() -> tuple[tuple[str, str], ...]:
    """Retourne un ((alias_lowercase, source_id), ...) plat trié par longueur d'alias DESC.

    Les alias les plus longs en premier, pour que la correspondance préfère l'alias
    le plus spécifique quand plusieurs partagent une sous-chaîne (ex. 'AIFMD' vs
    'Directive 2011/61/EU').
    """
    registry = load_sources_registry()
    pairs: list[tuple[str, str]] = [
        (alias.lower(), entry.source_id)
        for entry in registry.values()
        for alias in entry.aliases
    ]
    pairs.sort(key=lambda p: -len(p[0]))
    return tuple(pairs)
