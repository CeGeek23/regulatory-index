"""Génère de façon REPRODUCTIBLE les overrides de classification acteur/concept
(`config/glossary/overrides/{source_id}.yaml`) à partir des articles de définition,
via le modèle LM Studio local (API OpenAI-compatible).

Chaîne :
    data/raw/<ID>/*.html  --harvest_glossary-->  termes (fidèles au texte, déterministe)
                          --LLM LM Studio-------> type ∈ {acteur,produit,activite}  (typologie client)
                          --harmonisation-------> un terme = un même type partout (vote majoritaire)
                          --write_text----------> config/glossary/overrides/<ID>.yaml

Ce script comble le seul maillon non reproductible de la chaîne du glossaire : la
classification acteur/concept (l'extraction terme+définition, elle, est déjà déterministe).

Reproductibilité :
  - décodage glouton (temperature=0, seed=0) => sortie stable d'un run à l'autre ;
  - cache JSON (data/classification_cache.json) clé par (modèle, empreinte du prompt/typologie,
    source_id, label, empreinte du terme+définition) => re-run identique sans ré-interroger le
    modèle ; un changement de typologie/prompt invalide AUTOMATIQUEMENT le cache (clé distincte) ;
    supprimer le cache (ou --no-cache) pour reclasser de zéro ;
  - en-tête de fichier UNIQUE et déterministe (un seul libellé, fin des variantes manuelles) ;
  - HARMONISATION inter-textes déterministe (sur un run complet, sans cible) : un même terme
    (libellé EN normalisé) reçoit le même type partout, par vote majoritaire ; en cas d'égalité,
    on tranche par la définition SUBSTANTIELLE (la plus longue — pas un simple renvoi « as defined
    in… »), règle GÉNÉRALE et reproductible (aucune liste de décisions à maintenir) ;
  - N'ÉCRASE JAMAIS un override relu à la main (mécanisme général : « relu » en 1ʳᵉ ligne).

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
CACHE = Path("data/classification_cache.json")
ALLOWED = ("acteur", "produit", "activite")  # typologie STRICTE du client (articles de définition)
# Aucun texte protégé en dur : corpus uniforme (tout classé par le même modèle, tout « à relire »).
# Un override qu'un humain valide ensuite reste néanmoins préservé via _is_hand_curated (« relu » L1).
PROTECTED: set[str] = set()

# Tout dans le message utilisateur (certains gabarits GGUF locaux n'ont pas de rôle `system`).
PROMPT = """Tu es juriste de la réglementation financière de l'Union européenne. Classe le TERME \
DÉFINI ci-dessous dans EXACTEMENT une catégorie (typologie du client), en raisonnant SUR SA \
DÉFINITION (pas seulement son nom). Applique les tests DANS L'ORDRE et arrête-toi au premier qui \
s'applique :

1) acteur — une PERSONNE ou une ENTITÉ (un « QUI ») qu'on peut agréer, surveiller ou sanctionner : \
gestionnaire, dépositaire, entreprise d'investissement, établissement de crédit, autorité compétente, \
AEMF/AMF, investisseur, émetteur, contrepartie, courtier, dépositaire central de titres, société \
(holding, mère, filiale).

2) activite — une ACTION, un SERVICE ou une OPÉRATION (un « CE QU'ON FAIT ») : la gestion de FIA \
(assurer des fonctions de gestion de portefeuille/des risques), la commercialisation, la \
pré-commercialisation, l'octroi de prêts, la conservation, la tenue de marché, la négociation. Indice : \
la définition décrit une activité « exercée », des « fonctions assurées », un « service fourni ».

3) produit — TOUT LE RESTE : ni un qui, ni une action, donc un OBJET ou une NOTION. Inclut : tout \
instrument financier ; tout FONDS/FIA quel que soit son nom (feeder, master, FIA octroyant des prêts, \
FIA à effet de levier) ; un prêt, une part ; ET toute notion juridique ou géographique : un ÉTAT MEMBRE \
(d'origine, de référence, d'accueil), le contrôle, les liens étroits, une participation qualifiée, \
l'effet de levier, les fonds propres, le capital, une succursale.

ATTENTION : un terme qui DÉSIGNE UN PAYS OU UN TERRITOIRE — un « État membre », même qualifié \
(« d'origine », « d'accueil », « de référence », « où le risque est situé », « de l'AIFM/de l'OPCVM ») \
— est une NOTION GÉOGRAPHIQUE, donc produit, JAMAIS un acteur (l'« État membre d'origine de l'AIFM » \
reste un lieu, pas l'AIFM).

Terme (EN) : {en}
Terme (FR) : {fr}
Définition : {definition}

Réponds par UN SEUL MOT : acteur, produit, ou activite."""

# Empreinte du prompt + des catégories : intégrée à la clé de cache pour qu'un changement de
# typologie/prompt INVALIDE automatiquement les anciennes entrées (sinon le cache renverrait des
# types calculés sous un ancien schéma — bug à éviter). Reproductible : même prompt → même empreinte.
PROMPT_FP = hashlib.sha1((PROMPT + "|" + "|".join(ALLOWED)).encode("utf-8")).hexdigest()[:8]


@dataclass
class _Doc:
    """Classification d'un acte en attente d'écriture (après harmonisation éventuelle)."""

    types: dict[str, str] = field(default_factory=dict)          # label -> type
    labels: list[tuple[str, str]] = field(default_factory=list)  # (label, terme EN normalisé)
    n_unres: int = 0


def _norm(term: str) -> str:
    return " ".join(term.lower().split())


def _largest_en(source_id: str) -> Path | None:
    files = sorted((RAW / source_id).glob("*_EN_*.html"), key=lambda p: (-p.stat().st_size, p.name))
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
    low = (text or "").lower().replace("é", "e")  # « activité » -> « activite »
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


def _harmonize(docs: dict[str, _Doc], longest: dict[str, tuple[int, str]]) -> tuple[int, int]:
    """Force un même terme (EN normalisé) au même type partout. Déterministe, reproductible.

    Règle GÉNÉRALE (aucune liste de décisions à maintenir) : vote majoritaire ; en cas d'ÉGALITÉ,
    on tranche par la définition SUBSTANTIELLE — le type issu de la plus longue définition du terme
    (un simple renvoi « as defined in… » est court et peu informatif ; la vraie définition est
    longue). `longest` = {terme normalisé: (longueur de définition, type)}.
    Renvoie (nombre de types modifiés, nombre d'égalités tranchées).
    """
    tally: dict[str, Counter[str]] = defaultdict(Counter)
    for doc in docs.values():
        for label, term in doc.labels:
            tally[term][doc.types[label]] += 1

    winner_of: dict[str, str] = {}
    tie_resolved = 0
    for term, counts in tally.items():
        ranked = counts.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            winner_of[term] = longest[term][1]  # égalité → définition substantielle
            tie_resolved += 1
        else:
            winner_of[term] = ranked[0][0]

    changes = 0
    for doc in docs.values():
        for label, term in doc.labels:
            if doc.types[label] != winner_of[term]:
                doc.types[label] = winner_of[term]
                changes += 1
    return changes, tie_resolved


def _write_override(sid: str, model: str, types: dict[str, str]) -> None:
    header = (
        f"# Glossaire {sid} — classification acteur/concept générée par scripts/classify_overrides.py\n"
        f"# Modèle LM Studio : {model}. type ∈ acteur|produit|activite (typologie client). À RELIRE (validation métier).\n"
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
    longest: dict[str, tuple[int, str]] = {}  # terme normalisé -> (longueur de déf., type) la plus longue
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
            cache_key = f"{model}|{PROMPT_FP}|{sid}|{t.label}|{_fingerprint(t)}"
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
                    typ = "produit"  # défaut = objet/notion (tout le fichier est « à RELIRE »)
                    doc.n_unres += 1
                cache[cache_key] = typ
            term_norm = _norm(t.term_en) or _norm(t.term_fr)
            doc.types[t.label] = typ
            doc.labels.append((t.label, term_norm))
            dlen = len((t.definition_en or "").strip())
            if term_norm not in longest or dlen > longest[term_norm][0]:
                longest[term_norm] = (dlen, typ)  # garde le type de la définition la plus longue
        docs[sid] = doc
        flag = f"  ({doc.n_unres} indécis → concept)" if doc.n_unres else ""
        print(f"  {sid:16} {len(doc.types):>3} termes classés{flag}")

    harmonize = not targets  # l'harmonisation n'a de sens que sur le corpus complet
    changes, tie_resolved = _harmonize(docs, longest) if harmonize else (0, 0)

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
        print(f"Harmonisation inter-textes : {changes} type(s) alignés ; "
              f"{tie_resolved} égalité(s) tranchée(s) par la définition substantielle (la plus longue).")
    else:
        print("Harmonisation non appliquée (run ciblé) — relance sans argument pour ré-harmoniser le corpus.")
    print(f"Cache : {CACHE}  (supprimer ou --no-cache pour reclasser)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
