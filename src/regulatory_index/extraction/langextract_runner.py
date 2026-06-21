"""Runner idempotent : soumet les unités normatives à LangExtract via un backend OpenAI-compatible (LM Studio) et persiste les sorties.

Pour chaque unité :
- Si `data/obligations/{source_id}/{unit_id}.json` existe déjà, on saute (réexécutions idempotentes).
- Sinon, on appelle LangExtract, on normalise le résultat en UnitExtraction, on persiste le JSON.
- Les échecs sont journalisés dans `data/obligations/_failed.jsonl` (une ligne par échec) et
  n'interrompent PAS l'exécution : l'unité suivante est traitée.

Pas de regex, pas de chaîne de repli : un appel LangExtract par unité, une écriture disque par résultat.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import langextract as lx
from langextract import factory

from ..ingestion.unit_loader import NormativeUnit
from ..schemas.raw import ExtractionMeta, RawObligation, UnitExtraction
from .examples_loader import load_examples
from .schema_builder import build_prompt_description

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunnerConfig:
    # Backend LLM local via API OpenAI-compatible (LM Studio par défaut, sur :1234/v1).
    model_id: str = "qwen2.5-7b-instruct"  # clé du modèle chargé dans LM Studio
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"  # factice : serveur local, pas d'authentification
    temperature: float = 0.0
    max_tokens: int = 8192  # généreux : une unité peut produire un gros JSON (12+ obligations)
    extraction_passes: int = 1
    fence_output: bool = False  # sortie structurée (JSON schema) -> pas de fences
    use_schema_constraints: bool = True  # LM Studio impose le JSON schema -> format garanti
    request_timeout: int = 600  # secondes


def _safe_path_segment(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(":", "_")


def output_path(out_dir: Path, unit: NormativeUnit) -> Path:
    """Retourne le chemin du fichier JSON de sortie pour une unité."""
    sub = out_dir / _safe_path_segment(unit.source_id)
    base = _safe_path_segment(unit.unit_id)
    return sub / f"{base}.json"


def _langextract_version() -> str | None:
    try:
        return version("langextract")
    except PackageNotFoundError:
        return None


def _as_text(value: Any) -> str:
    """Coerce un attribut en une chaîne unique (le LLM renvoie parfois une liste ou None)."""
    if value is None:
        return ""
    if isinstance(value, list | tuple):
        for item in value:
            if item is None:
                continue  # ne pas coercer None en la chaîne "None"
            text = str(item).strip()
            if text:
                return text
        return ""
    return str(value).strip()


def _to_raw_obligation(extraction: lx.data.Extraction) -> RawObligation:
    attrs: dict[str, Any] = dict(extraction.attributes or {})
    ci = extraction.char_interval
    if ci is None or ci.start_pos is None or ci.end_pos is None:
        raise ValueError("extraction has no usable char_interval (grounding missing)")
    alignment = (
        extraction.alignment_status.value
        if extraction.alignment_status is not None
        else None
    )
    actor = _as_text(attrs.get("actor"))
    action = _as_text(attrs.get("action"))
    if not actor or not action:
        raise ValueError(f"obligation sans actor/action exploitable (actor={actor!r}, action={action!r})")
    return RawObligation(
        actor=actor,
        action=action,
        object=_as_text(attrs.get("object")),
        theme=_as_text(attrs.get("theme")),
        sub_theme=attrs.get("sub_theme"),
        condition=attrs.get("condition"),
        scope=attrs.get("scope"),
        exception=attrs.get("exception"),
        expected_evidence=list(attrs.get("expected_evidence") or []),
        associated_control=attrs.get("associated_control"),
        cited_references=list(attrs.get("cited_references") or []),
        verbatim_text=(extraction.extraction_text or "").strip(),
        char_interval=(ci.start_pos, ci.end_pos),
        alignment_status=alignment,
    )


def extract_unit(unit: NormativeUnit, config: RunnerConfig) -> UnitExtraction:
    """Exécute un seul appel LangExtract sur une unité, retourne une UnitExtraction (éventuellement vide)."""
    prompt = build_prompt_description(unit.language)
    examples = load_examples(unit.language)

    model_config = factory.ModelConfig(
        model_id=config.model_id,
        provider="OpenAILanguageModel",
        provider_kwargs={
            "base_url": config.base_url,
            "api_key": config.api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "timeout": config.request_timeout,
        },
    )
    started = time.monotonic()
    result = lx.extract(
        text_or_documents=unit.text,
        prompt_description=prompt,
        examples=list(examples),
        config=model_config,
        fence_output=config.fence_output,
        use_schema_constraints=config.use_schema_constraints,
        extraction_passes=config.extraction_passes,
    )
    elapsed = time.monotonic() - started

    # lx.extract est encapsulée dans __init__.py sous la forme `(*args: Any, **kwargs: Any)`,
    # donc les analyseurs statiques ne voient pas sa vraie signature de retour
    # (`AnnotatedDocument | list[AnnotatedDocument]`). On passe une seule str, donc on
    # obtient la branche single-doc ; on force le rétrécissement de type avec cast.
    doc = cast(lx.data.AnnotatedDocument, result)
    extractions: list[lx.data.Extraction] = list(doc.extractions or [])

    obligations: list[RawObligation] = []
    errors: list[str] = []
    for ex in extractions:
        try:
            obligations.append(_to_raw_obligation(ex))
        except (ValueError, KeyError, TypeError) as e:
            # une extraction malformée est consignée, sans invalider les autres de l'unité
            # (ValidationError Pydantic est une sous-classe de ValueError → déjà couverte)
            errors.append(f"{type(e).__name__}: {e}")

    meta = ExtractionMeta(
        model_id=config.model_id,
        extraction_passes=config.extraction_passes,
        temperature=config.temperature,
        extracted_at=datetime.now(UTC),
        latency_seconds=round(elapsed, 2),
        langextract_version=_langextract_version(),
    )
    return UnitExtraction(unit=unit, obligations=obligations, extraction_meta=meta, errors=errors)


def _persist(extraction: UnitExtraction, out_dir: Path) -> Path:
    json_path = output_path(out_dir, extraction.unit)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(extraction.to_record_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return json_path


def _log_failure(unit: NormativeUnit, error: BaseException, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    failed_log = out_dir / "_failed.jsonl"
    record = {
        "unit_id": unit.unit_id,
        "source_id": unit.source_id,
        "language": unit.language,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "failed_at": datetime.now(UTC).isoformat(),
    }
    with failed_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(
    units: Iterable[NormativeUnit],
    out_dir: Path,
    config: RunnerConfig | None = None,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Traite les unités séquentiellement. Retourne les compteurs : {processed, skipped, failed}."""
    config = config or RunnerConfig()
    counts = {"processed": 0, "skipped": 0, "failed": 0}

    # Réinitialise le journal d'échecs pour que les rapports qualité ne reflètent que les échecs de cette exécution.
    # Une unité ayant échoué puis réussi ne doit pas laisser de ligne fantôme.
    out_dir.mkdir(parents=True, exist_ok=True)
    failed_log = out_dir / "_failed.jsonl"
    if failed_log.exists():
        failed_log.unlink()

    for unit in units:
        json_path = output_path(out_dir, unit)
        if json_path.exists() and not force:
            log.info("skip (already extracted): %s", unit.unit_id)
            counts["skipped"] += 1
            continue

        try:
            extraction = extract_unit(unit, config)
        except Exception as e:
            log.exception("extraction failed for %s", unit.unit_id)
            _log_failure(unit, e, out_dir)
            counts["failed"] += 1
            continue

        _persist(extraction, out_dir)
        counts["processed"] += 1
        log.info(
            "extracted %s: %d obligation(s) in %.1fs",
            unit.unit_id,
            len(extraction.obligations),
            extraction.extraction_meta.latency_seconds,
        )

    return counts
