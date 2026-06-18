"""Construit le prompt_description LangExtract à partir des vocabulaires contrôlés + templates."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..refdata.vocab import load_acronyms, load_vocabulary

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@cache
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


def _csv(values: tuple[str, ...]) -> str:
    """Rend une liste de vocabulaire sous forme de chaîne séparée par des virgules pour l'injection dans le prompt."""
    return ", ".join(values)


@cache
def build_prompt_description(language: Literal["EN", "FR"]) -> str:
    """Rend le prompt_description pour LangExtract à partir des YAML de vocab + template Jinja."""
    actors = load_vocabulary("actors").canonical_values(language)
    actions = load_vocabulary("actions").canonical_values(language)
    objects_ = load_vocabulary("objects").canonical_values(language)
    themes = load_vocabulary("themes").canonical_values(language)
    conditions = load_vocabulary("conditions").canonical_values(language)
    acronyms = load_acronyms()

    template_name = "prompt_template_en.j2" if language == "EN" else "prompt_template_fr.j2"
    template = _env().get_template(template_name)
    return template.render(
        actors=_csv(actors),
        actions=_csv(actions),
        objects=_csv(objects_),
        themes=_csv(themes),
        conditions=_csv(conditions),
        acronyms=acronyms,
    )
