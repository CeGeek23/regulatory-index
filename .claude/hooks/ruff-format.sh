#!/usr/bin/env bash
# Hook PostToolUse (Write|Edit) : corrige + formate les fichiers Python édités via ruff.
# Reçoit le JSON du hook sur stdin (tool_input.file_path). Ne bloque JAMAIS l'édition :
# toute erreur ruff est avalée, le hook sort toujours 0.
#
# Câblé dans .claude/settings.json. Lancé depuis la racine du projet (uv résout l'env).
set -uo pipefail

f="$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)"
[ -n "$f" ] || exit 0

case "$f" in
  *.py)
    uv run --no-sync ruff check --fix "$f" >/dev/null 2>&1 || true
    uv run --no-sync ruff format "$f" >/dev/null 2>&1 || true
    ;;
esac
exit 0
