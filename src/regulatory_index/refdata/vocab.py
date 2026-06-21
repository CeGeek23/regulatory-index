"""Chargeur pour les vocabulaires contrôlés stockés en YAML dans config/vocabularies/."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class VocabEntry:
    id: str
    canonical_en: str
    canonical_fr: str
    aliases: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def canonical(self, language: str) -> str:
        return self.canonical_en if language.upper() == "EN" else self.canonical_fr


@dataclass(frozen=True)
class Vocabulary:
    name: str
    entries: tuple[VocabEntry, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(e.id for e in self.entries)

    def canonical_values(self, language: str = "EN") -> tuple[str, ...]:
        return tuple(e.canonical(language) for e in self.entries)

    def resolve(self, value: str) -> VocabEntry | None:
        """Mappe toute forme de surface (canonique EN/FR, id ou alias) sur son entrée.

        Insensible à la casse. Retourne None pour les valeurs vides ou hors vocab.
        """
        if not value:
            return None
        return _resolve_index(self.name).get(value.strip().lower())


VOCAB_DIR = Path(__file__).resolve().parents[3] / "config" / "vocabularies"

_KNOWN_FIELDS = {"id", "canonical_en", "canonical_fr", "aliases"}


def _entry_from_dict(raw: dict[str, Any]) -> VocabEntry:
    aliases_raw: list[str] = raw.get("aliases") or []
    extra: dict[str, Any] = {k: v for k, v in raw.items() if k not in _KNOWN_FIELDS}
    return VocabEntry(
        id=str(raw["id"]),
        canonical_en=str(raw["canonical_en"]),
        canonical_fr=str(raw["canonical_fr"]),
        aliases=tuple(aliases_raw),
        extra=extra,
    )


@cache
def load_vocabulary(name: str) -> Vocabulary:
    """Charge un YAML de vocab par nom court (ex. 'actors', 'actions')."""
    path = VOCAB_DIR / f"{name}.yaml"
    with path.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f) or []
    entries = tuple(_entry_from_dict(item) for item in raw)
    return Vocabulary(name=name, entries=entries)


@cache
def _resolve_index(name: str) -> dict[str, VocabEntry]:
    """Index inverse {canonical_en, canonical_fr, id, *aliases} -> VocabEntry (clés en minuscules).

    Priorité déterministe en cas de collision : une **forme canonique** l'emporte sur un id/alias
    d'une AUTRE entrée (sinon « participation », canonique d'une entrée, pourrait résoudre vers une
    entrée dont ce n'est qu'un id/alias). Deux passes : id/alias d'abord (1er gagne), puis canoniques
    (qui écrasent). Une vraie collision canonique↔canonique (homonyme) reste tranchée par l'ordre YAML.
    """
    index: dict[str, VocabEntry] = {}
    entries = load_vocabulary(name).entries
    for entry in entries:  # passe 1 : id + alias (priorité basse, premier gagne)
        for key in (entry.id, *entry.aliases):
            if key:
                index.setdefault(key.strip().lower(), entry)
    for entry in entries:  # passe 2 : canoniques EN/FR (priorité haute, écrasent)
        for key in (entry.canonical_en, entry.canonical_fr):
            if key:
                index[key.strip().lower()] = entry
    return index


def load_all_vocabularies() -> dict[str, Vocabulary]:
    """Charge tous les fichiers vocab de VOCAB_DIR (acronyms a une forme différente, ignoré)."""
    out: dict[str, Vocabulary] = {}
    for path in sorted(VOCAB_DIR.glob("*.yaml")):
        if path.stem == "acronyms":
            continue
        out[path.stem] = load_vocabulary(path.stem)
    return out


@dataclass(frozen=True)
class Acronym:
    short: str
    long_en: str
    long_fr: str


@lru_cache(maxsize=1)
def load_acronyms() -> tuple[Acronym, ...]:
    path = VOCAB_DIR / "acronyms.yaml"
    with path.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f) or []
    return tuple(
        Acronym(
            short=str(item["short"]),
            long_en=str(item["long_en"]),
            long_fr=str(item["long_fr"]),
        )
        for item in raw
    )
