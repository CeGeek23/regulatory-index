"""Matérialise les objets Obligation finaux à partir de RawObligation + NormativeUnit.

Attribue un obligation_id déterministe à partir du code de theme + un numéro de
séquence stable entre exécutions (il dépend uniquement d'une clé de tri, pas de
l'ordre d'itération sur disque).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from ..ingestion.unit_loader import NormativeUnit
from .obligation import Obligation
from .raw import ExtractionMeta, RawObligation, UnitExtraction
from .source import AlignmentStatus, Source
from .sources_registry import load_sources_registry
from .vocab import load_vocabulary

# Champs à vocabulaire contrôlé et le fichier vocab qui normalise chacun.
_FIELD_VOCAB: dict[str, str] = {
    "actor": "actors",
    "action": "actions",
    "object": "objects",
    "theme": "themes",
}


def _theme_code_for(theme: str) -> str:
    """Résout un theme (éventuellement localisé) en son code stable, sinon MISC."""
    entry = load_vocabulary("themes").resolve(theme)
    if entry is None:
        return "MISC"
    code = entry.extra.get("code")
    if code:
        return str(code)
    # Repli : seulement les lettres de l'id (cohérent avec _check_id_format), sinon MISC.
    return "".join(c for c in entry.id if c.isalpha())[:4].upper() or "MISC"


def _canonicalize(field: str, value: str, language: str) -> str:
    """Mappe une valeur de vocab contrôlé sur son label pivot canonique ; garde la valeur brute si inconnue."""
    entry = load_vocabulary(_FIELD_VOCAB[field]).resolve(value)
    return entry.canonical(language) if entry is not None else value


def collect_vocab_gaps(
    extractions: Iterable[UnitExtraction],
) -> dict[str, list[tuple[str, int]]]:
    """Par champ de vocab contrôlé, les valeurs brutes hors vocab et leurs comptes.

    Remonte ce que le LLM a produit et que les vocabulaires ne couvrent pas encore
    (candidats à ajouter dans config/vocabularies/).
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
    """Aplatit les UnitExtractions en Obligations avec des ids stables attribués par theme.

    Les champs de vocab contrôlé (actor, action, object, theme) sont normalisés vers
    leur label canonique dans `canonical_language` afin que les formes de surface FR/EN
    se ramènent à une seule valeur. Les valeurs hors vocab sont conservées telles
    quelles (voir `collect_vocab_gaps`).
    """

    items: list[tuple[str, NormativeUnit, RawObligation, ExtractionMeta]] = []
    for ue in extractions:
        for raw in ue.obligations:
            sort_key = (ue.unit.source_id, ue.unit.unit_id, raw.char_interval[0])
            items.append((repr(sort_key), ue.unit, raw, ue.extraction_meta))

    items.sort(key=lambda t: t[0])

    counter: dict[str, int] = {}
    out: list[Obligation] = []
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
                extracted_at=meta.extracted_at,
            )
        )
    return out
