---
name: lms
description: Vérifie et démarre si besoin LM Studio (serveur OpenAI-compatible sur localhost:1234) avec le modèle standard qwen2.5-7b-instruct. À utiliser avant toute classification ou extraction qui dépend du LLM local.
---

Vérifie que LM Studio est prêt, et démarre-le sinon — sans demander à chaque étape.

1. `curl -s --max-time 5 http://localhost:1234/v1/models` pour voir si le serveur répond et quel(s)
   modèle(s) sont chargés.
2. Si le serveur ne répond pas OU si `qwen2.5-7b-instruct` n'est pas chargé →
   `just lms-load` (charge `qwen2.5-7b-instruct` @32k + démarre le serveur).
3. Re-teste l'endpoint et confirme en une ligne : modèle chargé + serveur up.

Rappel : ouvrir l'app LM Studio ne suffit pas — le **serveur** doit être démarré (d'où `lms server start`).
