"""Génère de façon REPRODUCTIBLE les overrides de classification acteur/concept
(`config/glossary/overrides/{source_id}.yaml`) à partir des articles de définition,
via le modèle LM Studio local (API OpenAI-compatible).

Chaîne :
    data/raw/<ID>/*.html  --harvest_glossary-->  termes (fidèles au texte, déterministe)
                          --LLM LM Studio-------> type ∈ {actor,investor,supervisor,concept}
                          --write_text----------> config/glossary/overrides/<ID>.yaml

Ce script comble le seul maillon non reproductible de la chaîne du glossaire : la
classification acteur/concept (l'extraction terme+définition, elle, est déjà déterministe).

Reproductibilité :
  - décodage glouton (temperature=0, seed=0) => sortie stable d'un run à l'autre ;
  - cache JSON (data/classification_cache.json) clé par (modèle, source_id, label,
    empreinte du terme+définition) => re-run identique sans ré-interroger le modèle ;
    supprimer le cache (ou --no-cache) pour reclasser de zéro ;
  - en-tête de fichier UNIQUE et déterministe (un seul libellé, fin des variantes manuelles) ;
  - N'ÉCRASE JAMAIS un override relu à la main (en-tête « relu » : AIFMD_L1/L2).

Le `type` reste marqué « à RELIRE » : c'est une proposition automatique, à valider en relecture
métier (le terme et la définition, eux, sont fidèles au texte officiel).

Usage :
    uv run python scripts/classify_overrides.py                 # tous les actes en cache (sauf relus)
    uv run python scripts/classify_overrides.py MIFID2 CRR      # actes ciblés
    uv run python scripts/classify_overrides.py --model qwen2.5-7b-instruct
    uv run python scripts/classify_overrides.py --no-cache      # ignore le cache (reclasse tout)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml
from openai import OpenAI

from regulatory_index.extraction.langextract_runner import RunnerConfig
from regulatory_index.glossary import DefinedTerm, harvest_glossary

RAW = Path("data/raw")
OVERRIDES = Path("config/glossary/overrides")
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


def main() -> int:
    argv = sys.argv[1:]
    use_cache = "--no-cache" not in argv
    argv = [a for a in argv if a != "--no-cache"]
    model_arg: str | None = None
    if "--model" in argv:
        i = argv.index("--model")
        model_arg = argv[i + 1]
        del argv[i : i + 2]
    targets = argv  # source_ids restants ; vide = tout le cache data/raw

    cfg = RunnerConfig()
    client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.request_timeout)
    try:
        model = _pick_model(client, model_arg)
    except Exception as exc:  # LM Studio injoignable
        raise SystemExit(f"LM Studio injoignable sur {cfg.base_url} ({type(exc).__name__}: {exc}).") from exc
    print(f"Modèle LM Studio : {model}  (temperature=0, seed=0 — décodage déterministe)\n")

    cache: dict[str, str] = {}
    if use_cache and CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    if not RAW.exists():
        raise SystemExit(f"{RAW} absent — dépose d'abord le HTML EUR-Lex EN des actes.")
    source_ids = targets or sorted(p.name for p in RAW.iterdir() if p.is_dir())

    OVERRIDES.mkdir(parents=True, exist_ok=True)
    written = skipped = llm_calls = unresolved = 0
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

        classified: dict[str, dict[str, str]] = {}
        n_unres = 0
        for t in terms:
            key = f"{model}|{sid}|{t.label}|{_fingerprint(t)}"
            typ = cache.get(key) if use_cache else None
            if typ is None:
                typ = _classify(client, model, t)
                llm_calls += 1
                if typ is None:
                    typ = "concept"  # proposition par défaut (tout le fichier est « à RELIRE »)
                    n_unres += 1
                cache[key] = typ
            classified[t.label] = {"type": typ}

        header = (
            f"# Glossaire {sid} — classification acteur/concept générée par scripts/classify_overrides.py\n"
            f"# Modèle LM Studio : {model}. type ∈ actor|investor|supervisor|concept. À RELIRE (validation métier).\n"
            f"# Indexé par étiquette de point. Reproductible : relancer le script régénère ce fichier à l'identique.\n\n"
        )
        body = yaml.safe_dump(classified, sort_keys=False, allow_unicode=True)
        path.write_text(header + body, encoding="utf-8")
        unresolved += n_unres
        flag = f"  ({n_unres} indécis → concept)" if n_unres else ""
        print(f"  {sid:16} {len(classified):>3} termes classés{flag}")
        written += 1

    if use_cache:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"\nTerminé : {written} override(s) écrit(s), {skipped} relu(s) conservé(s), "
        f"{llm_calls} appel(s) LLM, {unresolved} terme(s) indécis (→ concept)."
    )
    print(f"Cache : {CACHE}  (supprimer ou --no-cache pour reclasser)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
