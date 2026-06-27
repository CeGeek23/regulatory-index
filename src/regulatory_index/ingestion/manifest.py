"""Chargement du manifeste de corpus (config/sources_manifest.yaml).

Le manifeste déclare, pour chaque texte EUR-Lex du corpus, le CELEX, la langue et
les articles à conserver. Il pilote la (re)construction hors-ligne du corpus
(`scripts/build_corpus_offline.py`) à partir du HTML déjà en cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MANIFEST_PATH = Path(__file__).resolve().parents[3] / "config" / "sources_manifest.yaml"


@dataclass(frozen=True)
class ManifestEntry:
    source_id: str
    celex: str
    language: str
    filter_articles: tuple[str, ...] | None


def load_manifest(path: Path = MANIFEST_PATH) -> list[ManifestEntry]:
    with path.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f) or []
    entries: list[ManifestEntry] = []
    for item in raw:
        filter_arts = item.get("filter_articles")
        entries.append(
            ManifestEntry(
                source_id=str(item["source_id"]),
                celex=str(item["celex"]),
                language=str(item["language"]),
                filter_articles=tuple(filter_arts) if filter_arts else None,
            )
        )
    return entries
