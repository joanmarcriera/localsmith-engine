#!/usr/bin/env bash
# scaffold.sh — generate empty project tree from an idea file, using local Ollama.
#
# Usage:
#   bin/scaffold.sh queue/silly-web-game.md
#   bin/scaffold.sh queue/silly-web-game.md projects/   # override projects root
#
# Pipeline:
#   1. Read idea file.
#   2. Concatenate with prompts/scaffold.txt.
#   3. Pipe to bin/ai ollama (qwen2.5-coder:14b by default) — zero cloud tokens.
#   4. Validate JSON against lib/schema/tree.schema.json.
#   5. Materialise dirs + empty files under PROJECTS_ROOT/<slug>/.
#   6. Save tree.json inside the project for the next phase.
#
# Standards: shellcheck-clean, set -euo pipefail, fails loud on bad JSON.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IDEA="${1:?usage: scaffold.sh IDEA_FILE [PROJECTS_ROOT]}"
PROJECTS_ROOT="${2:-$ROOT/projects}"

[ -f "$IDEA" ] || { echo "[scaffold] idea file not found: $IDEA" >&2; exit 1; }

mkdir -p "$PROJECTS_ROOT"

# Slug is ALWAYS the idea filename, never what the LLM picks. This is the only
# source of truth — fixes the bug where Ollama renamed dashboard → ai-workflow-dashboard.
SLUG="$(basename "$IDEA" .md)"
case "$SLUG" in
    [a-z0-9]*) ;;
    *) echo "[scaffold] bad slug from filename: '$SLUG' (must match ^[a-z0-9][a-z0-9-]*)" >&2; exit 1 ;;
esac

# Idempotency: if tree.json already exists for this slug, skip the LLM call.
# Set SCAFFOLD_FORCE=1 to regenerate tree.json and add any newly requested paths
# while still preserving existing file contents.
if [ -f "$PROJECTS_ROOT/$SLUG/tree.json" ] && [ "${SCAFFOLD_FORCE:-0}" != "1" ]; then
    echo "[scaffold] tree.json already present for $SLUG — skipping LLM call" >&2
    echo "[scaffold] done: $PROJECTS_ROOT/$SLUG/" >&2
    exit 0
fi

# Build prompt = idea body + output contract. Keep the contract at the end so
# long idea files that hit a model context limit still preserve the JSON schema.
PROMPT="$(printf 'PROJECT IDEA:\n'; cat "$IDEA"; printf '\n\n'; cat "$ROOT/prompts/scaffold.txt")"

PROVIDER="${SCAFFOLD_PROVIDER:-ollama}"
echo "[scaffold] dispatching to $PROVIDER with --json (may cold-load model)..." >&2

SYS_ARGS=()
if [ -f "$ROOT/prefs.md" ]; then
    SYS_ARGS=(--system "@$ROOT/prefs.md")
    echo "[scaffold] using prefs.md as system prompt" >&2
fi

# Tell the LLM the slug we expect. We also overwrite it post-parse, but mentioning
# it in the prompt makes the model less likely to fight us.
PROMPT="$PROMPT

The project slug MUST be exactly: $SLUG"

USAGE_FILE="$(mktemp "${TMPDIR:-/tmp}/aiwf-scaffold-usage.XXXXXX")"
JSON="$(printf '%s' "$PROMPT" | AIWF_PROJECT="$SLUG" AIWF_STEP=scaffold "$ROOT/bin/ai" "$PROVIDER" - --json "${SYS_ARGS[@]}" --usage-file "$USAGE_FILE")"

# Force the canonical slug regardless of what the model returned.
JSON="$(printf '%s' "$JSON" | python3 -c '
import json, sys
doc = json.loads(sys.stdin.read())
doc["project"] = sys.argv[1]
json.dump(doc, sys.stdout)
' "$SLUG")"

# Validate + materialise. SLUG passed so materialize can refuse mismatches.
TREE_OUT="$(printf '%s' "$JSON" | "$ROOT/bin/materialize.py" "$PROJECTS_ROOT" "$SLUG")"

# Persist tree.json inside the project.
printf '%s\n' "$TREE_OUT" > "$PROJECTS_ROOT/$SLUG/tree.json"
if [ -s "$USAGE_FILE" ]; then
    cp "$USAGE_FILE" "$PROJECTS_ROOT/$SLUG/.scaffold-usage.json"
fi
rm -f "$USAGE_FILE"

echo "[scaffold] done: $PROJECTS_ROOT/$SLUG/" >&2
