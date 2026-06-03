"""Loader for controlled vocabularies stored as YAML in config/vocabularies/."""

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

    def by_id(self, vid: str) -> VocabEntry | None:
        return next((e for e in self.entries if e.id == vid), None)

    def resolve(self, value: str) -> VocabEntry | None:
        """Map any surface form (canonical EN/FR, id, or alias) to its entry.

        Case-insensitive. Returns None for empty or off-vocabulary values.
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
    """Load a vocab YAML by short name (e.g. 'actors', 'actions')."""
    path = VOCAB_DIR / f"{name}.yaml"
    with path.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f) or []
    entries = tuple(_entry_from_dict(item) for item in raw)
    return Vocabulary(name=name, entries=entries)


@cache
def _resolve_index(name: str) -> dict[str, VocabEntry]:
    """Reverse lookup {canonical_en, canonical_fr, id, *aliases} -> VocabEntry.

    Keys are lowercased. On collision the later entry wins (acceptable for v0).
    """
    index: dict[str, VocabEntry] = {}
    for entry in load_vocabulary(name).entries:
        for key in (entry.canonical_en, entry.canonical_fr, entry.id, *entry.aliases):
            if key:
                index[key.strip().lower()] = entry
    return index


def load_all_vocabularies() -> dict[str, Vocabulary]:
    """Load every vocab file in VOCAB_DIR (acronyms has a different shape, skipped)."""
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
