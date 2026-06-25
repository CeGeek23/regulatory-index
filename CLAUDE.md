# Instructions projet — regulatory-index

## Principe directeur : généraliser, jamais spécialiser

**J'ai vraiment besoin d'un code qui généralise, et non de quelque chose qui ne marche que de façon spécifique.**

Toute correction, tout traitement, toute règle doit valoir pour **n'importe quel** texte / article / source du corpus — pas seulement pour le cas sous les yeux.

Concrètement, dans ce dépôt :
- **Ancrer les règles au bon endroit, général par construction** : prompt d'extraction (`prompts/prompt_template_*.j2`) et exemples few-shot (`prompts/examples_*.yaml`) pour la sémantique LLM ; post-traitement déterministe (`materialize/builder.py`, `linking/`, etc.) pour ce qui doit tenir quel que soit le modèle.
- **Proscrire les patchs spécifiques** : pas d'index de lignes codés en dur, pas de listes blanches/noires par article, pas de `if article == 6`. Le projet a déjà supprimé `prune.yaml`/`tie_breaks.yaml` au profit de règles générales — rester dans cet esprit.
- **Toute règle générale est testée** sur un cas minimal et abstrait (voir `tests/test_obligation_builder.py`), pas sur un article précis.
- Un correctif ponctuel sur un livrable (ex. un CSV d'export) est tolérable **comme rustine temporaire**, mais le vrai correctif vit dans le code/pipeline général et est signalé comme tel.
