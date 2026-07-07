# Environnements & données — la doctrine

Où vivent les données de l'index réglementaire, ce qui est reconstructible,
ce qui ne l'est pas, et comment on promeut local → dev → prod sans jamais
copier de données à la main.

## Le principe : la base regindex est une donnée DÉRIVÉE

Tout le contenu du schéma `regindex` se reconstruit depuis trois sources de
vérité, en quelques minutes :

1. **La base documentaire Lalande** (faite par Louis) — la source unique du
   corpus. En local : un dump du staging (jamais de la prod).
2. **Le code et la config versionnés** de ce repo — `db/schema.sql`,
   `config/dictionary_seed.yaml`, les vocabulaires, la CLI `regindex`.
3. **Les décisions humaines** (revue des candidats, plus tard revue des
   statements) — **la seule chose non-reproductible**. Règle : toute décision
   validée doit être capturée dans un fichier versionné (le seed grandit),
   jamais seulement en base. Tant que c'est respecté, n'importe quel
   environnement se reconstruit à l'identique.

Corollaire : **on ne promeut jamais des données**, on promeut du code et on
rejoue le pipeline (toutes les commandes sont idempotentes, prouvé par
re-run 0 créé / 0 modifié).

## Reconstruire de zéro (local)

```bash
# 1. Un Postgres local avec le dump Lalande (conteneur `lalande-pg`, port 5433,
#    restart unless-stopped — survit aux reboots). Si perdu : re-dump du
#    staging vps-work (JAMAIS de la prod), puis pg_restore.
# 2. Le schéma + le pipeline, dans l'ordre :
uv run --no-sync regindex db apply
uv run --no-sync regindex ingest --all-registry   # regulation + source_unit + coverage
uv run --no-sync regindex dict seed               # 100 entrées du modèle client (autoritaire)
uv run --no-sync regindex dict candidates         # vocab + glossaire, inactifs, DO NOTHING
uv run --no-sync regindex db status               # contrôle : compte par table
```

Le DSN se résout par `LALANDE_DSN` (défaut : le conteneur local). `db/schema.sql`
est appliqué tel quel ; `dict seed` est autoritaire sur ses colonnes ;
`dict candidates` ne réécrit **jamais** une ligne existante (une revue humaine
n'est pas clobbée par un re-run).

## Local → dev → prod

| Environnement | Rôle | Source corpus | Comment ça avance |
| --- | --- | --- | --- |
| **Local (Mac)** | valider AVANT de pousser | dump staging dans `lalande-pg:5433` | rejouer le pipeline, jetable à volonté |
| **Dev (vps-work)** | intégration continue | DB staging vps-work (`LALANDE_DSN`) | mêmes commandes idempotentes, après merge |
| **Prod** | plus tard, par release | DB prod | même principe ; frontière : jamais de copie locale→prod, jamais d'agent sur prod |

## Ce qu'il ne faut PAS faire

- Copier des lignes de la base locale vers dev/prod (les ids sont stables et
  structurels, un rejeu produit les MÊMES ids — la copie n'apporte rien et
  contourne la revue).
- Prendre une décision de revue uniquement en base locale : elle serait
  perdue au prochain rebuild. La revue s'exporte en YAML versionné d'abord.
- Sourcer le corpus ailleurs que dans la DB Lalande (le chemin HTML
  `data/textes_sources` est legacy).
