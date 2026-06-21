"""Génère de façon REPRODUCTIBLE les overrides de classification acteur/concept
(`config/glossary/overrides/{source_id}.yaml`) à partir des articles de définition,
via le modèle LM Studio local (API OpenAI-compatible).

Chaîne :
    data/raw/<ID>/*.html  --harvest_glossary-->  termes (fidèles au texte, déterministe)
                          --LLM LM Studio-------> type ∈ {actor,investor,supervisor,concept}
                          --harmonisation-------> un terme = un même type partout (vote majoritaire)
                          --write_text----------> config/glossary/overrides/<ID>.yaml

Ce script comble le seul maillon non reproductible de la chaîne du glossaire : la
classification acteur/concept (l'extraction terme+définition, elle, est déjà déterministe).

Reproductibilité :
  - décodage glouton (temperature=0, seed=0) => sortie stable d'un run à l'autre ;
  - cache JSON (data/classification_cache.json) clé par (modèle, source_id, label,
    empreinte du terme+définition) => re-run identique sans ré-interroger le modèle ;
    supprimer le cache (ou --no-cache) pour reclasser de zéro ;
  - en-tête de fichier UNIQUE et déterministe (un seul libellé, fin des variantes manuelles) ;
  - HARMONISATION inter-textes déterministe (sur un run complet, sans cible) : un même terme
    (libellé EN normalisé) reçoit le même type partout, par vote majoritaire strict ; les
    égalités sont laissées telles quelles et signalées (à trancher en relecture métier) ;
  - N'ÉCRASE JAMAIS un override relu à la main (en-tête « relu » : AIFMD_L1/L2).

Le `type` reste marqué « à RELIRE » : c'est une proposition automatique, à valider en relecture
métier (le terme et la définition, eux, sont fidèles au texte officiel).

Usage :
    uv run python scripts/classify_overrides.py                 # tous les actes (classe + harmonise)
    uv run python scripts/classify_overrides.py MIFID2 CRR      # actes ciblés (sans harmonisation)
    uv run python scripts/classify_overrides.py --model qwen2.5-7b-instruct
    uv run python scripts/classify_overrides.py --no-cache      # ignore le cache (reclasse tout)
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from openai import OpenAI

from regulatory_index.extraction.langextract_runner import RunnerConfig
from regulatory_index.glossary import DefinedTerm, harvest_glossary

RAW = Path("data/raw")
OVERRIDES = Path("config/glossary/overrides")
TIE_BREAKS = Path("config/glossary/tie_breaks.yaml")  # décisions métier (terme→type), autoritaires
CACHE = Path("data/classification_cache.json")
ALLOWED = ("actor", "investor", "supervisor", "concept")
PROTECTED = {"AIFMD_L1", "AIFMD_L2"}  # relus à la main — jamais écrasés (ceinture + bretelles)

# Tout dans le message utilisateur (certains gabarits GGUF locaux n'ont pas de rôle `system`).
PROMPT = """Tu es juriste spécialiste de la réglementation financière de l'Union européenne.
Classe le TERME DÉFINI ci-dessous dans EXACTEMENT une de ces catégories :
- actor : personne morale ou physique régulée ou qui agit (gestionnaire, dépositaire, \
établissement de crédit, entreprise d'investissement, prestataire de services, contrepartie, émetteur…).
- investor : un type d'investisseur ou de client (investisseur professionnel, client de détail, \
investisseur de détail, contrepartie éligible…).
- supervisor : une autorité de surveillance, de régulation ou de résolution (autorité compétente, \
AEMF/ESMA, ABE/EBA, AEAPP/EIOPA, autorité de résolution…).
- concept : tout le reste (notion juridique, instrument financier, opération, document, montant, \
seuil, état membre, groupe…).

Terme (EN) : {en}
Terme (FR) : {fr}
Définition : {definition}

Réponds par UN SEUL MOT, exactement l'une de ces valeurs : actor, investor, supervisor, concept."""


@dataclass
class _Doc:
    """Classification d'un acte en attente d'écriture (après harmonisation éventuelle)."""

    types: dict[str, str] = field(default_factory=dict)          # label -> type
    labels: list[tuple[str, str]] = field(default_factory=list)  # (label, terme EN normalisé)
    n_unres: int = 0


def _norm(term: str) -> str:
    return " ".join(term.lower().split())


def _largest_en(source_id: str) -> Path | None:
    files = sorted((RAW / source_id).glob("*_EN_*.html"), key=lambda p: p.stat().st_size, reverse=True)
    return files[0] if files else None


def _is_hand_curated(path: Path) -> bool:
    """Un override relu à la main porte « relu » en première ligne — on ne le régénère pas."""
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    return bool(lines) and "relu" in lines[0].lower()


def _fingerprint(term: DefinedTerm) -> str:
    raw = f"{term.term_en}␟{term.term_fr}␟{term.definition_en}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _parse_type(text: str | None) -> str | None:
    """Premier mot de catégorie reconnu dans la réponse (les libellés ne se chevauchent pas)."""
    low = (text or "").lower()
    hits = [(low.index(a), a) for a in ALLOWED if a in low]
    return min(hits)[1] if hits else None


def _classify(client: OpenAI, model: str, term: DefinedTerm) -> str | None:
    prompt = PROMPT.format(
        en=term.term_en or "(absent)",
        fr=term.term_fr or "(absent)",
        definition=(term.definition_en or term.definition_fr or "(définition non extraite)").strip(),
    )
    for _ in range(2):  # une relance si la réponse n'est pas exploitable
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            seed=0,
            max_tokens=10,
        )
        result = _parse_type(resp.choices[0].message.content)
        if result is not None:
            return result
    return None


def _pick_model(client: OpenAI, requested: str | None) -> str:
    if requested:
        return requested
    ids = [m.id for m in client.models.list().data]
    if not ids:
        raise SystemExit("Aucun modèle chargé dans LM Studio (GET /v1/models vide). Charge un modèle.")
    return ids[0]


def _harmonize(docs: dict[str, _Doc]) -> tuple[int, list[str]]:
    """Force un même terme (EN normalisé) au même type partout, par vote majoritaire STRICT.

    Déterministe (donc reproductible) : ne dépend que des types déjà attribués. Les termes à
    égalité de votes sont laissés tels quels et renvoyés pour signalement (relecture métier).
    Renvoie (nombre de types modifiés, termes à égalité).
    """
    tally: dict[str, Counter[str]] = defaultdict(Counter)
    for doc in docs.values():
        for label, term in doc.labels:
            tally[term][doc.types[label]] += 1

    majority: dict[str, str] = {}
    ties: list[str] = []
    for term, counts in tally.items():
        ranked = counts.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            ties.append(term)  # pas de majorité stricte — on ne tranche pas
        else:
            majority[term] = ranked[0][0]

    changes = 0
    for doc in docs.values():
        for label, term in doc.labels:
            winner = majority.get(term)
            if winner and doc.types[label] != winner:
                doc.types[label] = winner
                changes += 1
    return changes, sorted(ties)


def _load_tie_breaks() -> dict[str, str]:
    """Décisions métier terme→type (relecture humaine), appliquées APRÈS l'harmonisation.

    C'est le seul endroit où une décision manuelle se pose : elle est versionnée et fait foi,
    donc elle survit à toute régénération (le générateur la ré-applique à l'identique).
    """
    if not TIE_BREAKS.exists():
        return {}
    raw = yaml.safe_load(TIE_BREAKS.read_text(encoding="utf-8")) or {}
    return {_norm(str(k)): str(v) for k, v in raw.items()}


def _apply_tie_breaks(docs: dict[str, _Doc], tie_breaks: dict[str, str]) -> int:
    """Force le type décidé (tie_breaks) sur tout terme concerné, partout. Renvoie le nb de changements."""
    applied = 0
    for doc in docs.values():
        for label, term in doc.labels:
            forced = tie_breaks.get(term)
            if forced and doc.types[label] != forced:
                doc.types[label] = forced
                applied += 1
    return applied


def _write_override(sid: str, model: str, types: dict[str, str]) -> None:
    header = (
        f"# Glossaire {sid} — classification acteur/concept générée par scripts/classify_overrides.py\n"
        f"# Modèle LM Studio : {model}. type ∈ actor|investor|supervisor|concept. À RELIRE (validation métier).\n"
        f"# Indexé par étiquette de point. Reproductible : relancer le script régénère ce fichier à l'identique.\n\n"
    )
    body = yaml.safe_dump({lbl: {"type": t} for lbl, t in types.items()}, sort_keys=False, allow_unicode=True)
    (OVERRIDES / f"{sid}.yaml").write_text(header + body, encoding="utf-8")


def main() -> int:
    argv = sys.argv[1:]
    use_cache = "--no-cache" not in argv
    argv = [a for a in argv if a != "--no-cache"]
    model_arg: str | None = None
    if "--model" in argv:
        i = argv.index("--model")
        model_arg = argv[i + 1]
        del argv[i : i + 2]
    targets = argv  # source_ids restants ; vide = tout le cache data/raw (+ harmonisation)

    cfg = RunnerConfig()
    client_holder: OpenAI | None = None

    def get_client() -> OpenAI:
        """Création paresseuse : on ne contacte LM Studio que pour un terme non caché."""
        nonlocal client_holder
        if client_holder is None:
            client_holder = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.request_timeout)
        return client_holder

    if model_arg:
        model = model_arg  # hors-ligne OK : aucune connexion tant que le cache couvre tout
    else:
        try:
            model = _pick_model(get_client(), None)
        except Exception as exc:  # LM Studio injoignable
            raise SystemExit(
                f"LM Studio injoignable sur {cfg.base_url} ({type(exc).__name__}). Si le cache est "
                f"déjà rempli, relance avec --model <id> (ex. qwen2.5-7b-instruct) pour tourner hors-ligne."
            ) from exc
    print(f"Modèle : {model}  (temperature=0, seed=0 — décodage déterministe)\n")

    cache: dict[str, str] = {}
    if use_cache and CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    if not RAW.exists():
        raise SystemExit(f"{RAW} absent — dépose d'abord le HTML EUR-Lex EN des actes.")
    source_ids = targets or sorted(p.name for p in RAW.iterdir() if p.is_dir())

    OVERRIDES.mkdir(parents=True, exist_ok=True)
    docs: dict[str, _Doc] = {}
    skipped = llm_calls = 0
    for sid in source_ids:
        path = OVERRIDES / f"{sid}.yaml"
        if sid in PROTECTED or _is_hand_curated(path):
            print(f"  {sid:16} relu à la main — conservé")
            skipped += 1
            continue
        en = _largest_en(sid)
        if en is None:
            print(f"  {sid:16} pas de HTML EN en cache — ignoré")
            continue
        try:
            terms = harvest_glossary(en.read_text(encoding="utf-8"), source_id=sid, celex=en.name.split("_", 1)[0], level=1)
        except Exception as exc:  # acte sans article de définitions, HTML inattendu
            print(f"  {sid:16} {type(exc).__name__}: {exc} — ignoré")
            continue
        terms = [t for t in terms if t.term_en.strip() or t.term_fr.strip()]
        if not terms:
            print(f"  {sid:16} 0 terme extrait — ignoré")
            continue

        doc = _Doc()
        for t in terms:
            cache_key = f"{model}|{sid}|{t.label}|{_fingerprint(t)}"
            typ = cache.get(cache_key) if use_cache else None
            if typ is None:
                try:
                    typ = _classify(get_client(), model, t)
                except Exception as exc:  # LM Studio injoignable pour un terme non caché
                    raise SystemExit(
                        f"Terme non caché ({sid}/{t.label}) et LM Studio injoignable ({type(exc).__name__}). "
                        f"Démarre LM Studio (modèle {model}) pour classer les nouveaux termes."
                    ) from exc
                llm_calls += 1
                if typ is None:
                    typ = "concept"  # proposition par défaut (tout le fichier est « à RELIRE »)
                    doc.n_unres += 1
                cache[cache_key] = typ
            doc.types[t.label] = typ
            doc.labels.append((t.label, _norm(t.term_en) or _norm(t.term_fr)))
        docs[sid] = doc
        flag = f"  ({doc.n_unres} indécis → concept)" if doc.n_unres else ""
        print(f"  {sid:16} {len(doc.types):>3} termes classés{flag}")

    harmonize = not targets  # l'harmonisation n'a de sens que sur le corpus complet
    changes, ties = _harmonize(docs) if harmonize else (0, [])

    # Décisions métier (tie_breaks.yaml) : appliquées en dernier, elles font foi sur tout.
    tie_breaks = _load_tie_breaks()
    tb_applied = _apply_tie_breaks(docs, tie_breaks)

    for sid, doc in docs.items():
        _write_override(sid, model, doc.types)

    if use_cache:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    unresolved = sum(d.n_unres for d in docs.values())
    print(
        f"\nTerminé : {len(docs)} override(s) écrit(s), {skipped} relu(s) conservé(s), "
        f"{llm_calls} appel(s) LLM, {unresolved} terme(s) indécis (→ concept)."
    )
    if harmonize:
        print(f"Harmonisation inter-textes : {changes} type(s) aligné(s) sur la majorité ; "
              f"{len(ties)} terme(s) à égalité laissés tels quels (à trancher) : {', '.join(ties[:8])}"
              f"{'…' if len(ties) > 8 else ''}")
    else:
        print("Harmonisation non appliquée (run ciblé) — relance sans argument pour ré-harmoniser le corpus.")
    if tie_breaks:
        print(f"Décisions métier (tie_breaks.yaml) : {len(tie_breaks)} terme(s) cadré(s), {tb_applied} type(s) forcé(s).")
    print(f"Cache : {CACHE}  (supprimer ou --no-cache pour reclasser)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
