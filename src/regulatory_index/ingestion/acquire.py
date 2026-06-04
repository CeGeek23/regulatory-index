"""Orchestrate corpus acquisition from config/sources_manifest.yaml.

Reads the manifest, dispatches to the matching fetcher (eurlex / amf /
legifrance), persists raw HTML in data/raw/, parses to NormativeUnit, and
emits a single JSONL ready for `regindex extract`.

Strictly no regex in the parsing chain; DOM-based traversal only.

ESMA Guidelines / Q&A are not supported yet — ESMA publishes mostly as PDF,
which is out of scope for this iteration (no PDF parsing).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..schemas.sources_registry import load_sources_registry
from .amf_fetcher import fetch_to_disk as amf_fetch_to_disk
from .amf_fetcher import parse_doctrine as amf_parse_doctrine
from .eurlex_fetcher import fetch_to_disk as eurlex_fetch_to_disk
from .eurlex_html_parser import parse_articles as eurlex_parse_articles
from .legifrance_fetcher import fetch_to_disk as legifrance_fetch_to_disk
from .legifrance_fetcher import parse_article as legifrance_parse_article
from .unit_loader import NormativeUnit, write_units_jsonl

log = logging.getLogger(__name__)

MANIFEST_PATH = Path(__file__).resolve().parents[3] / "config" / "sources_manifest.yaml"


@dataclass(frozen=True)
class ManifestEntry:
    source_id: str
    fetcher: str
    celex: str | None
    language: str
    filter_articles: tuple[str, ...] | None
    # AMF: doctrine document code (e.g. "DOC-2014-06")
    doc_code: str | None = None
    # Légifrance: LEGIARTI identifier + display article number
    article_id: str | None = None
    article_number: str | None = None


def load_manifest(path: Path = MANIFEST_PATH) -> list[ManifestEntry]:
    with path.open(encoding="utf-8") as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f) or []
    entries: list[ManifestEntry] = []
    for item in raw:
        filter_arts = item.get("filter_articles")
        entries.append(
            ManifestEntry(
                source_id=str(item["source_id"]),
                fetcher=str(item["fetcher"]),
                celex=item.get("celex"),
                language=str(item["language"]),
                filter_articles=tuple(filter_arts) if filter_arts else None,
                doc_code=item.get("doc_code"),
                article_id=item.get("article_id"),
                article_number=item.get("article_number"),
            )
        )
    return entries


def acquire_one(
    entry: ManifestEntry,
    raw_dir: Path,
) -> list[NormativeUnit]:
    """Fetch + parse one manifest entry. Returns the NormativeUnits produced."""
    registry = load_sources_registry()
    reg_entry = registry.get(entry.source_id)
    if reg_entry is None:
        raise ValueError(
            f"source_id '{entry.source_id}' is not in sources_registry.yaml — add it first"
        )

    if entry.fetcher == "eurlex":
        if not entry.celex:
            raise ValueError(f"{entry.source_id}: eurlex fetcher requires celex")
        html_path = eurlex_fetch_to_disk(
            entry.celex, entry.language, raw_dir / entry.source_id
        )
        log.info("downloaded %s -> %s", entry.source_id, html_path.name)
        html = html_path.read_text(encoding="utf-8")
        keep = set(entry.filter_articles) if entry.filter_articles else None
        return eurlex_parse_articles(
            html,
            source_id=entry.source_id,
            celex=entry.celex,
            language=entry.language,
            title=reg_entry.title,
            level=reg_entry.level,
            issuer=reg_entry.issuer,
            url=reg_entry.url,
            keep=keep,
        )

    if entry.fetcher == "amf":
        if not entry.doc_code:
            raise ValueError(f"{entry.source_id}: amf fetcher requires doc_code")
        html_path = amf_fetch_to_disk(entry.doc_code, raw_dir / entry.source_id)
        log.info("downloaded %s -> %s", entry.source_id, html_path.name)
        return amf_parse_doctrine(
            html_path.read_text(encoding="utf-8"),
            source_id=entry.source_id,
            doc_code=entry.doc_code,
            title=reg_entry.title,
            level=reg_entry.level,
            issuer=reg_entry.issuer,
            url=reg_entry.url,
        )

    if entry.fetcher == "legifrance":
        if not entry.article_id or not entry.article_number:
            raise ValueError(
                f"{entry.source_id}: legifrance fetcher requires article_id and article_number"
            )
        html_path = legifrance_fetch_to_disk(entry.article_id, raw_dir / entry.source_id)
        log.info("downloaded %s -> %s", entry.source_id, html_path.name)
        return legifrance_parse_article(
            html_path.read_text(encoding="utf-8"),
            source_id=entry.source_id,
            article_id=entry.article_id,
            article_number=entry.article_number,
            title=reg_entry.title,
            level=reg_entry.level,
            issuer=reg_entry.issuer,
            url=reg_entry.url,
        )

    raise NotImplementedError(f"fetcher '{entry.fetcher}' is not implemented yet")


def acquire_all(
    *,
    manifest_path: Path = MANIFEST_PATH,
    raw_dir: Path = Path("data/raw"),
    units_out: Path = Path("data/units/corpus.jsonl"),
) -> dict[str, int]:
    """Run acquisition over the full manifest. Returns counters."""
    entries = load_manifest(manifest_path)
    all_units: list[NormativeUnit] = []
    counts: dict[str, int] = {"manifest_entries": len(entries), "units": 0, "failed": 0}

    for entry in entries:
        try:
            units = acquire_one(entry, raw_dir)
            log.info("parsed %s -> %d unit(s)", entry.source_id, len(units))
            all_units.extend(units)
        except Exception as e:  # per-entry isolation
            log.exception("acquisition failed for %s: %s", entry.source_id, e)
            counts["failed"] += 1

    write_units_jsonl(all_units, units_out)
    counts["units"] = len(all_units)
    return counts
