#!/usr/bin/env bash
# orchestrate.sh — resumable driver that walks a project through scaffold → plan →
# implement → verify, idempotently. Safe to Ctrl-C and re-run.
#
# Usage:
#   bin/orchestrate.sh queue/silly-web-game.md             # one project
#   bin/orchestrate.sh queue/*.md                          # batch
#
# Per project the steps are:
#   1. scaffold  — bin/scaffold.sh creates projects/<slug>/ with empty tree.
#   2. state     — bin/state.py init bootstraps state.json.
#   3. plan      — (Phase 3+) bin/plan.sh writes plan.md, marks step done.
#   4. implement — (Phase 3+) bin/implement.sh fills src/*, marks step done.
#   5. verify    — (Phase 4)  bin/verify.sh runs linters/tests, writes report.md.
#
# Each step is a separate executable; this driver just dispatches based on
# state.json's current_step. If a step's script is missing, we stop with a clear
# message rather than crash — lets us land steps incrementally.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECTS_ROOT="$ROOT/projects"

load_env_defaults() {
    [ -f "$ROOT/.env" ] || return 0

    # Source .env for the shell stages, but keep explicit caller exports as
    # overrides. bin/ai has its own default-preserving loader for provider calls.
    declare -A preserve=()
    local line key
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        case "$line" in
            ""|\#*) continue ;;
        esac
        line="${line#export }"
        [[ "$line" == *=* ]] || continue
        key="${line%%=*}"
        key="${key%"${key##*[![:space:]]}"}"
        if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && [ "${!key+x}" = x ]; then
            preserve["$key"]="${!key}"
        fi
    done < "$ROOT/.env"

    set -a
    # shellcheck disable=SC1091
    . "$ROOT/.env"
    set +a

    for key in "${!preserve[@]}"; do
        export "$key=${preserve[$key]}"
    done
}

load_env_defaults

run_project() {
    local idea="$1"
    [ -f "$idea" ] || { echo "[orchestrate] missing idea: $idea" >&2; return 1; }

    # Project slug = idea filename without .md. Convention: queue/<slug>.md
    # is the source of truth, NOT whatever the LLM picked. This is what scaffold.sh's
    # idempotency check uses too — keep them aligned.
    local slug pd
    slug="$(basename "$idea" .md)"
    pd="$PROJECTS_ROOT/$slug"

    # --- step 1: scaffold (idempotent — scaffold.sh / materialize.py skip existing files) ---
    if ! "$ROOT/bin/scaffold.sh" "$idea" "$PROJECTS_ROOT"; then
        echo "[orchestrate] $slug: scaffold failed, state not initialised" >&2
        return 1
    fi

    [ -f "$pd/tree.json" ] || {
        echo "[orchestrate] no tree.json in $pd — scaffold may have written under a different slug" >&2
        return 1
    }

    # --- step 2: ensure state.json exists ---
    if [ ! -f "$pd/state.json" ]; then
        "$ROOT/bin/state.py" init "$idea" "$pd" >/dev/null
        echo "[orchestrate] $slug: state initialised" >&2
    fi

    # --- step 3..N: loop until done ---
    while :; do
        local step
        step="$("$ROOT/bin/state.py" get "$pd" current_step)"
        case "$step" in
            done)
                echo "[orchestrate] $slug: complete" >&2
                break
                ;;
            plan|implement|verify)
                local script="$ROOT/bin/${step}.sh"
                if [ ! -x "$script" ]; then
                    echo "[orchestrate] $slug: step '$step' not yet implemented" \
                         "(missing $script) — stopping cleanly" >&2
                    break
                fi
                echo "[orchestrate] $slug: running $step" >&2
                if ! "$script" "$pd"; then
                    "$ROOT/bin/state.py" mark "$pd" "$step" error "step $step failed" >/dev/null
                    echo "[orchestrate] $slug: $step failed, state preserved" >&2
                    return 1
                fi
                ;;
            *)
                echo "[orchestrate] $slug: unknown step '$step'" >&2
                return 1
                ;;
        esac
    done
}

failed=0
for idea in "$@"; do
    if ! run_project "$idea"; then
        failed=1
        echo "[orchestrate] continuing to next project" >&2
    fi
done

exit "$failed"
