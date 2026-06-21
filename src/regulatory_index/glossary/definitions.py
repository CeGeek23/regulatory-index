"""Moissonne les termes définis d'un acte EUR-Lex, à partir de son HTML.

Point de départ = le **contenu de l'acte** (déjà disponible, p. ex. en base d'actes) ;
aucune acquisition réseau. La sortie est bilingue (`DefinedTerm`).

Étapes :
1. localiser l'article de définitions (passé en paramètre, ou détecté via le sommaire) ;
2. découper sa liste de points (a), (b), ... — ou (1), (2), ... — de façon déterministe ;
3. apparier EN/FR par étiquette de point ;
4. y attacher l'enrichissement relu (`type` acteur/concept..., `cites` renvois inter-actes).

**Un seul chemin, sans heuristique** : l'extraction (terme/définition/base légale) est
automatique ; l'enrichissement (`type`, `cites`) vient exclusivement d'un fichier relu par
acte (`config/glossary/overrides/{source_id}.yaml`). Acte sans override = glossaire complet
mais `type`/`cites` non renseignés (jamais devinés). Pur `str` / parcours DOM, sans regex.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from ..ingestion.eurlex_html_parser import parse_articles
from ..schemas.source import Language, Level
from .models import DefinedTerm
from .toc import build_toc

OVERRIDES_DIR = Path(__file__).resolve().parents[3] / "config" / "glossary" / "overrides"

# Délimiteurs de terme rencontrés dans les rendus EUR-Lex, par langue (essayés ensemble ;
# on retient celui dont l'ouvrant apparaît en premier). EUR-Lex panache les styles :
# guillemets simples courbes U+2018/U+2019, point U+2027 (ex. CRR), guillemets doubles
# courbes U+201C/U+201D, guillemets droits doubles, et apostrophe droite U+0027 (ex. CRD IV).
_QUOTE_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    "EN": (
        (chr(0x2018), chr(0x2019)),
        (chr(0x2027), chr(0x2027)),
        (chr(0x201C), chr(0x201D)),
        ('"', '"'),
        ("'", "'"),
    ),
    "FR": (
        (chr(0x00AB), chr(0x00BB)),
        (chr(0x2018), chr(0x2019)),
        (chr(0x2027), chr(0x2027)),
        (chr(0x201C), chr(0x201D)),
        ('"', '"'),
        ("'", "'"),
    ),
}
# Fermants qui servent AUSSI d'apostrophe (possessif/élision) : U+2019 et l'apostrophe droite
# U+0027. Quand l'un est suivi d'une minuscule, ce n'est pas le vrai fermant (« employees' … »).
_POSSESSIVE_CLOSES = (chr(0x2019), "'")


@dataclass(frozen=True)
class ParsedPoint:
    """Un point de la liste de définitions : étiquette, terme cité, corps de la définition."""

    label: str
    term: str
    definition: str


def _letter_labels() -> Iterator[str]:
    """a, b, ..., z, aa, ab, ... — étiquettes alphabétiques des points."""
    for i in range(26):
        yield chr(ord("a") + i)
    prefix = 0
    while True:
        for i in range(26):
            yield chr(ord("a") + prefix) + chr(ord("a") + i)
        prefix += 1


def _number_labels() -> Iterator[str]:
    """1, 2, 3, ... — étiquettes numériques (certains actes numérotent leurs définitions)."""
    n = 1
    while True:
        yield str(n)
        n += 1


def _fmt(label: str, language: str) -> str:
    """Forme de l'étiquette telle qu'elle apparaît seule sur sa ligne : EN '(a)', FR 'a)'."""
    return f"({label})" if language.upper() == "EN" else f"{label})"


def _first_quoted(text: str, language: str) -> str:
    """Premier terme entre guillemets ; gère les différents styles de guillemets EUR-Lex.

    On retient le délimiteur dont l'ouvrant apparaît en premier (U+2018/U+2019, U+2027,
    U+201C/U+201D ou guillemets droits). Le fermant U+2019 servant aussi d'apostrophe
    possessive, on l'ignore quand il est suivi d'une minuscule pour ne pas tronquer le terme.
    """
    best: tuple[int, str, str] | None = None
    for open_q, close_q in _QUOTE_PAIRS[language.upper()]:
        pos = text.find(open_q)
        if pos != -1 and (best is None or pos < best[0]):
            best = (pos, open_q, close_q)
    if best is None:
        return ""
    start, open_q, close_q = best
    cursor = start + 1
    while True:
        end = text.find(close_q, cursor)
        if end == -1:
            return ""
        if close_q in _POSSESSIVE_CLOSES and text[end + 1 : end + 2].islower():
            cursor = end + 1  # apostrophe de possessif, pas le vrai fermant
            continue
        return text[start + 1 : end].strip()


def _parse_unlabelled(lines: list[str], language: str) -> list[ParsedPoint]:
    """Repli pour les versions CONSOLIDÉES : pas d'étiquette (a)(b), une définition par ligne.

    Dans le rendu consolidé EUR-Lex, chaque définition est une ligne « 'terme' … » sans
    étiquette de point. On prend chaque ligne commençant par un guillemet ouvrant comme un
    terme défini, et on synthétise des étiquettes séquentielles (a, b, c, ... — positionnelles).
    """
    opens = tuple(open_q for open_q, _ in _QUOTE_PAIRS[language.upper()])
    labels = _letter_labels()
    points: list[ParsedPoint] = []
    for line in lines:
        if not line.startswith(opens):
            continue
        term = _first_quoted(line, language)
        if term:
            points.append(ParsedPoint(label=next(labels), term=term, definition=line))
    return points


def _is_paragraph_boundary(line: str) -> bool:
    """Vrai si la ligne ouvre un nouveau paragraphe de premier niveau ('2.', '3.' ...).

    Sert à borner la définition du DERNIER point : sans cela, elle absorberait les
    paragraphes 2, 3, 4 de l'article (ex. AIFMD art. 4(2)-(4)).
    """
    head = line.split(" ", 1)[0]
    return len(head) <= 3 and head.endswith(".") and head[:-1].isdigit()


def parse_points(text: str, *, language: Language) -> list[ParsedPoint]:
    """Découpe la liste de définitions d'un article en points {label, term, definition}.

    On recherche les étiquettes DANS L'ORDRE (lettres a,b,... ou nombres 1,2,...) : à
    chaque étape, seule la PROCHAINE étiquette attendue est cherchée, ce qui évite de
    confondre un sous-point (i)/(ii) avec un point de premier niveau. La liste se termine
    dès qu'on ne trouve plus l'étiquette attendue ou qu'un nouveau paragraphe commence.
    """
    lines = [line.strip() for line in text.splitlines()]

    def first_index(token: str) -> int:
        target = _fmt(token, language)
        for i, line in enumerate(lines):
            if line == target:
                return i
        return -1

    letters_at = first_index("a")
    numbers_at = first_index("1")
    if letters_at == -1 and numbers_at == -1:
        return _parse_unlabelled(lines, language)  # versions consolidées : pas d'étiquettes
    use_letters = letters_at != -1 and (numbers_at == -1 or letters_at <= numbers_at)
    labels = _letter_labels() if use_letters else _number_labels()

    positions: list[tuple[str, int]] = []
    cursor = 0
    for label in labels:
        target = _fmt(label, language)
        found = -1
        for j in range(cursor, len(lines)):
            if lines[j] == target:
                found = j
                break
        if found == -1:
            break  # fin de la liste de définitions
        positions.append((label, found))
        cursor = found + 1

    points: list[ParsedPoint] = []
    for idx, (label, pos) in enumerate(positions):
        end = positions[idx + 1][1] if idx + 1 < len(positions) else len(lines)
        body: list[str] = []
        for line in lines[pos + 1 : end]:
            if not line:
                continue
            if _is_paragraph_boundary(line):
                break
            body.append(line)
        joined = " ".join(body).strip()
        points.append(
            ParsedPoint(label=label, term=_first_quoted(joined, language), definition=joined)
        )
    return points


# Amorces de l'article de définitions, EN + FR (minuscules). Indépendant des sous-titres :
# certains rendus EUR-Lex (API Cellar) n'ont pas de <p oj-sti-art> ; on repère l'article
# par la phrase qui ouvre toute liste de définitions.
_DEF_TRIGGERS = ("the following definitions", "on entend par", "définitions suivantes")


_DEF_SUBTITLES = ("definitions", "définitions")


def _article_subtitle(unit_text: str) -> str:
    """Sous-titre d'un article = 1ʳᵉ ligne non vide APRÈS l'en-tête « Article N ».

    Le texte d'un `NormativeUnit` se présente « Article 2\\n\\nDefinitions\\nFor the purposes… » ;
    certains rendus consolidés (Cellar) logent ce sous-titre dans un `<p class="norm">` que le
    parseur ne reconnaît pas comme sous-titre — on le relit donc ici dans le corps.
    """
    lines = [ln.strip() for ln in unit_text.splitlines() if ln.strip()]
    return lines[1].lower() if len(lines) > 1 else ""


def find_definitions_article(html: str, language: Language) -> str | None:
    """Numéro de l'article de définitions, repéré par son sous-titre OU sa phrase d'amorce.

    Complète la détection par sommaire (`TableOfContents.definitions_article`) : fonctionne aussi
    quand le rendu n'a pas de sous-titres d'article reconnus (cas des versions consolidées dont le
    sous-titre « Definitions » est dans un `<p class="norm">`, ou des articles ouvrant directement
    par « For the purposes of this Directive: (1) … » sans la formule « the following definitions »).
    """
    units = parse_articles(
        html,
        source_id="_",
        celex="",
        language=language,
        title="_",
        level=1,
        issuer="EU_Parliament_Council",
        url="",
        keep=None,
    )
    # 1) sous-titre explicite « Definitions »/« Définitions » (capté ou non par le parseur).
    for unit in units:
        subtitle = str(unit.source_meta.get("subtitle") or "").strip().lower()
        if subtitle in _DEF_SUBTITLES or _article_subtitle(unit.text) in _DEF_SUBTITLES:
            return str(unit.source_meta["article"])
    # 2) à défaut, phrase d'amorce dans le corps.
    for unit in units:
        low = unit.text.lower()
        if any(trigger in low for trigger in _DEF_TRIGGERS):
            return str(unit.source_meta["article"])
    return None


# Mots introduisant un acte cité dans une définition (EN + FR) et marqueurs faisant partie
# de la référence (clause d'adoption, numérotation).
_CITE_ACTS = ("Directive", "Regulation", "Règlement", "Decision", "Décision")
_CITE_MARKERS = {
    "(EU)",
    "(EC)",
    "(EEC)",
    "(ECSC)",
    "(Euratom)",
    "(UE)",
    "(CE)",
    "(CEE)",
    "No",
    "No.",
    "n°",
}


def extract_citations(text: str) -> list[str]:
    """Renvois explicites à d'autres actes cités DANS une définition. Déterministe, sans regex.

    Repère « Directive 2009/65/EC », « Regulation (EU) No 575/2013 », « Directive (EU) 2024/927 » :
    après un mot d'acte (Directive/Regulation/Règlement…), on agrège les marqueurs (« (EU) », « No »)
    jusqu'au NUMÉRO de l'acte (token contenant un chiffre et un « / »). FIDÈLE au texte (le renvoi est
    écrit noir sur blanc, ce n'est pas une interprétation). Dédupliqué, dans l'ordre d'apparition.
    """
    out: list[str] = []
    toks = text.split()
    i = 0
    while i < len(toks):
        if toks[i].strip(".,;:") in _CITE_ACTS:
            ref = [toks[i].strip(".,;:")]
            j, numbered = i + 1, False
            while j < len(toks):
                tc = toks[j].strip(".,;:")
                if tc in _CITE_MARKERS:
                    ref.append(tc)
                    j += 1
                    continue
                if "/" in tc and any(ch.isdigit() for ch in tc):
                    ref.append(tc)  # numéro de l'acte (ex. 575/2013, 2009/65/EC)
                    numbered = True
                    j += 1
                break
            if numbered:
                out.append(" ".join(ref))
            i = j
        else:
            i += 1
    seen: set[str] = set()
    deduped: list[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


@cache
def load_overrides(source_id: str) -> dict[str, dict[str, Any]]:
    """Charge config/glossary/overrides/{source_id}.yaml (enrichissement relu), {} si absent."""
    path = OVERRIDES_DIR / f"{source_id}.yaml"
    if not path.exists():
        return {}
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(label): (value or {}) for label, value in raw.items()}


def _slug(text: str) -> str:
    """Identifiant snake_case depuis un libellé (alnum conservés, reste -> '_')."""
    out: list[str] = []
    prev_us = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
        elif not prev_us:
            out.append("_")
            prev_us = True
    return "".join(out).strip("_")


def harvest_glossary(
    html_en: str,
    html_fr: str = "",
    *,
    source_id: str,
    celex: str | None = None,
    level: Level = 1,
    act_label: str | None = None,
    definitions_article: str | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[DefinedTerm]:
    """Termes définis d'un acte, bilingue, depuis son HTML EN (+ FR optionnel).

    Extraction automatique (terme/définition/base légale) ; `type` et `cites` proviennent
    UNIQUEMENT de l'override relu (`config/glossary/overrides/{source_id}.yaml`), sinon
    laissés à `None`/`[]` (jamais devinés). `definitions_article` détecté via le sommaire
    EN si None. `act_label` : préfixe de `legal_basis` (défaut : source_id).
    """
    if definitions_article is None:
        toc = build_toc(html_en, source_id=source_id, language="EN")
        definitions_article = toc.definitions_article or find_definitions_article(html_en, "EN")
        if definitions_article is None:
            raise ValueError(
                f"{source_id}: article de définitions introuvable (ni sous-titre, ni amorce) ; "
                "passez definitions_article explicitement."
            )
    if overrides is None:
        overrides = load_overrides(source_id)
    prefix = act_label or source_id

    en_text = _definitions_text(html_en, definitions_article, source_id, celex, "EN", level)
    en_points = parse_points(en_text, language="EN")
    fr_points: dict[str, ParsedPoint] = {}
    if html_fr:  # FR optionnel et best-effort : ne doit jamais casser l'extraction EN
        try:
            fr_text = _definitions_text(html_fr, definitions_article, source_id, celex, "FR", level)
            fr_points = {p.label: p for p in parse_points(fr_text, language="FR")}
        except ValueError:
            fr_points = {}  # article de définitions absent/illisible en FR -> EN seul

    terms: list[DefinedTerm] = []
    for ep in en_points:
        fp = fr_points.get(ep.label)
        ov = overrides.get(ep.label, {})
        term_en = str(ov.get("term_en") or ep.term)
        term_fr = str(ov.get("term_fr") or (fp.term if fp else ""))
        definition_en = ep.definition
        definition_fr = fp.definition if fp else ""
        term_id = str(ov.get("id") or _slug(term_en) or f"{source_id.lower()}_{ep.label}")
        type_value = ov.get("type")
        type_ = str(type_value) if type_value else None
        # cites : l'override relu prime ; sinon, renvois extraits automatiquement de la définition
        # (fidèles au texte). Restaure le graphe inter-textes pour TOUS les actes, reproductible.
        cites = list(ov.get("cites") or extract_citations(definition_en))
        terms.append(
            DefinedTerm(
                term_id=term_id,
                label=ep.label,
                type=type_,
                term_en=term_en,
                term_fr=term_fr,
                legal_basis=f"{prefix} Art. {definitions_article}(1)({ep.label})",
                source_id=source_id,
                celex=celex,
                level=level,
                cites=cites,
                definition_en=definition_en,
                definition_fr=definition_fr,
            )
        )
    return terms


def _definitions_text(
    html: str, article: str, source_id: str, celex: str | None, language: Language, level: Level
) -> str:
    """Texte de l'article de définitions extrait du HTML (réutilise le parseur EUR-Lex)."""
    units = parse_articles(
        html,
        source_id=source_id,
        celex=celex or "",
        language=language,
        title=source_id,
        level=level,
        issuer="EU_Parliament_Council",
        url="",
        keep={article},
    )
    if not units:
        raise ValueError(f"{source_id}: article {article} introuvable dans le HTML {language}.")
    return units[0].text
