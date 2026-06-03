"""Materialise final Obligation objects from RawObligation + NormativeUnit.

Assigns a deterministic obligation_id from theme code + a sequence number that
is stable across re-runs (it depends only on a sort key, not on disk iteration
order).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime

from ..ingestion.unit_loader import NormativeUnit
from .obligation import Obligation
from .raw import ExtractionMeta, RawObligation, UnitExtraction
from .source import AlignmentStatus, Source
from .sources_registry import load_sources_registry
from .vocab import load_vocabulary

# Controlled-vocabulary fields and the vocab file that normalises each one.
_FIELD_VOCAB: dict[str, str] = {
    "actor": "actors",
    "action": "actions",
    "object": "objects",
    "theme": "themes",
}


def _theme_code_for(theme: str) -> str:
    """Resolve a (possibly localised) theme to its stable code, else MISC."""
    entry = load_vocabulary("themes").resolve(theme)
    if entry is None:
        return "MISC"
    return str(entry.extra.get("code") or entry.id[:4].upper())


def _canonicalize(field: str, value: str, language: str) -> str:
    """Map a controlled-vocab value to its canonical pivot label; keep raw if unknown."""
    entry = load_vocabulary(_FIELD_VOCAB[field]).resolve(value)
    return entry.canonical(language) if entry is not None else value


def collect_vocab_gaps(
    extractions: Iterable[UnitExtraction],
) -> dict[str, list[tuple[str, int]]]:
    """Per controlled-vocab field, the off-vocabulary raw values and their counts.

    Surfaces what the LLM emitted that the vocabularies don't yet cover — the role
    the former 03_vocab_gaps notebook played.
    """
    counters: dict[str, Counter[str]] = {field: Counter() for field in _FIELD_VOCAB}
    for ue in extractions:
        for raw in ue.obligations:
            for field, vocab_name in _FIELD_VOCAB.items():
                value = getattr(raw, field)
                if value and load_vocabulary(vocab_name).resolve(value) is None:
                    counters[field][value] += 1
    return {field: counter.most_common() for field, counter in counters.items() if counter}


def _make_source(unit: NormativeUnit, raw_align: str | None) -> Source:
    registry = load_sources_registry()
    entry = registry.get(unit.source_id)
    meta = unit.source_meta or {}

    title = (entry.title if entry else None) or str(meta.get("title", unit.source_id))
    celex = (entry.celex if entry else None) or meta.get("celex")
    level = (entry.level if entry else None) or meta.get("level", "national")
    issuer = (entry.issuer if entry else None) or meta.get("issuer", "AMF")
    url = (entry.url if entry else None) or meta.get("url", "")
    language = unit.language

    alignment: AlignmentStatus | None = (
        raw_align if raw_align in ("match_exact", "match_fuzzy") else None  # type: ignore[assignment]
    )

    return Source(
        source_id=f"{unit.source_id}#{unit.unit_id.split('#', 1)[-1]}",
        title=title,
        celex=celex,
        level=level,
        issuer=issuer,
        article=str(meta.get("article")) if meta.get("article") is not None else None,
        paragraph=str(meta.get("paragraph")) if meta.get("paragraph") is not None else None,
        point=str(meta.get("point")) if meta.get("point") is not None else None,
        url=url,
        language=language,
        alignment_status=alignment,
    )


def build_obligations(
    extractions: Iterable[UnitExtraction],
    *,
    prefix: str = "AIFMD",
    canonical_language: str = "EN",
) -> list[Obligation]:
    """Flatten UnitExtractions into Obligations with stable ids assigned per-theme.

    Controlled-vocab fields (actor, action, object, theme) are normalised to their
    canonical label in `canonical_language` so FR/EN surface forms collapse to one
    value. Off-vocabulary values are kept verbatim (see `collect_vocab_gaps`).
    """

    items: list[tuple[str, NormativeUnit, RawObligation, ExtractionMeta]] = []
    for ue in extractions:
        for raw in ue.obligations:
            sort_key = (ue.unit.source_id, ue.unit.unit_id, raw.char_interval[0])
            items.append((repr(sort_key), ue.unit, raw, ue.extraction_meta))

    items.sort(key=lambda t: t[0])

    counter: dict[str, int] = {}
    out: list[Obligation] = []
    now = datetime.now(UTC)
    for _, unit, raw, meta in items:
        code = _theme_code_for(raw.theme)
        counter[code] = counter.get(code, 0) + 1
        oid = f"{prefix}-{code}-{counter[code]:04d}"
        source = _make_source(unit, raw.alignment_status)
        out.append(
            Obligation(
                obligation_id=oid,
                actor=_canonicalize("actor", raw.actor, canonical_language),
                action=_canonicalize("action", raw.action, canonical_language),
                object=_canonicalize("object", raw.object, canonical_language),
                condition=raw.condition,
                source=source,
                theme=_canonicalize("theme", raw.theme, canonical_language),
                sub_theme=raw.sub_theme,
                scope=raw.scope,
                exception=raw.exception,
                expected_evidence=raw.expected_evidence,
                associated_control=raw.associated_control,
                verbatim_text=raw.verbatim_text,
                char_interval=raw.char_interval,
                cited_references=raw.cited_references,
                extraction_model=meta.model_id,
                extracted_at=meta.extracted_at or now,
            )
        )
    return out
