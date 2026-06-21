---
name: gate
description: Lance le gate qualité du projet (ruff + mypy + pytest) via `just check` et rapporte concisément. À utiliser avant tout commit, ou quand on demande de vérifier que le code est sain.
---

Lance le gate qualité du projet avec `just check` (ruff lint + mypy strict + pytest).

Rapporte de façon **concise** :
- si tout passe → une seule ligne « gate vert » avec le nombre de tests.
- si quelque chose échoue → liste uniquement les vérifications/tests en échec et les **lignes d'erreur clés** (pas le dump complet).

Ne corrige rien sauf demande explicite.
