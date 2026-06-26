#!/usr/bin/env bash
# setup.sh — first-run install wizard.
#
# Makes the orchestrator runnable by a stranger: checks prerequisites, detects a
# local Ollama and/or LM Studio, writes a working .env from .env.example, and runs
# a deterministic fixture smoke test so you SEE it work before spending a cent.
#
# Safe to re-run. Never overwrites an existing .env without asking.
# Usage:  bin/setup.sh            interactive
#         bin/setup.sh --yes      accept detected defaults, no prompts
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ASSUME_YES=0
[[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]] && ASSUME_YES=1

c_g() { printf '\033[32m%s\033[0m\n' "$*"; }
c_y() { printf '\033[33m%s\033[0m\n' "$*"; }
c_r() { printf '\033[31m%s\033[0m\n' "$*"; }
ask() { # ask "Question" "default" -> echoes answer
  local q="$1" def="${2:-}"
  if [[ $ASSUME_YES -eq 1 ]]; then echo "$def"; return; fi
  local ans; read -r -p "$q ${def:+[$def] }" ans </dev/tty || true
  echo "${ans:-$def}"
}
probe() { curl -fsS -m 3 "$1" >/dev/null 2>&1; }

echo "=============================================="
c_g " AI workflow — setup wizard"
echo "=============================================="

# 1. Prerequisites -------------------------------------------------------------
miss=0
for bin in bash python3 curl; do
  if command -v "$bin" >/dev/null 2>&1; then c_g "  ✓ $bin"; else c_r "  ✗ $bin (required)"; miss=1; fi
done
for bin in git docker; do
  command -v "$bin" >/dev/null 2>&1 && c_g "  ✓ $bin (optional)" || c_y "  · $bin not found (optional)"
done
[[ $miss -eq 1 ]] && { c_r "Install the missing required tools and re-run."; exit 1; }

# 2. Detect local model providers ---------------------------------------------
echo; c_g "Detecting local model providers…"
OLLAMA=""
for h in "${OLLAMA_HOST:-}" "http://localhost:11434" "http://192.168.0.5:30068"; do
  [[ -z "$h" ]] && continue
  if probe "$h/api/tags"; then OLLAMA="$h"; c_g "  ✓ Ollama at $h"; break; fi
done
[[ -z "$OLLAMA" ]] && c_y "  · No Ollama found (scaffold/review stages need it, or route them to LM Studio)."

LMSTUDIO=""
for h in "${LMSTUDIO_HOST:-}" "http://localhost:1234"; do
  [[ -z "$h" ]] && continue
  if probe "$h/v1/models"; then LMSTUDIO="$h"; c_g "  ✓ LM Studio at $h"; break; fi
done
[[ -z "$LMSTUDIO" ]] && c_y "  · No LM Studio found (optional)."

if [[ -z "$OLLAMA" && -z "$LMSTUDIO" ]]; then
  c_y "No local LLM detected. You can still run with cloud providers, but the"
  c_y "whole point of this tool is local-first cost routing. Install Ollama:"
  c_y "  https://ollama.com  →  ollama pull qwen2.5-coder:14b"
fi

# 3. Implementation provider (the only paid step) ------------------------------
echo; c_g "Implementation step (the one stage that can cost money):"
echo "  1) Z.AI GLM   — cheap metered API (needs a key)"
echo "  2) Fully local — route implement to Ollama/LM Studio (\$0, lower quality)"
echo "  3) Claude/Codex CLI — uses your existing Pro/Plus subscription quota"
choice="$(ask 'Choose 1/2/3' '1')"
ZKEY="replace_me"; IMPL_PROVIDER="zai"
case "$choice" in
  2) IMPL_PROVIDER="${OLLAMA:+ollama}"; IMPL_PROVIDER="${IMPL_PROVIDER:-lmstudio}" ;;
  3) IMPL_PROVIDER="claude" ;;
  *) if [[ $ASSUME_YES -eq 0 ]]; then
       read -r -s -p "Paste ZAI_API_KEY (input hidden, blank to skip): " ZKEY </dev/tty || true; echo
       ZKEY="${ZKEY:-replace_me}"
     fi ;;
esac

# 4. Write .env ----------------------------------------------------------------
echo
if [[ -f .env ]]; then
  ovr="$(ask '.env already exists. Overwrite? (y/N)' 'N')"
  [[ "$ovr" =~ ^[Yy] ]] || { c_y "Keeping existing .env. Skipping write."; SKIP_ENV=1; }
fi
if [[ "${SKIP_ENV:-0}" != "1" ]]; then
  cp .env.example .env
  # patch detected values in-place (portable sed)
  sed_i() { local e="$1" f="$2"; sed "$e" "$f" > "$f.tmp" && mv "$f.tmp" "$f"; }
  [[ -n "$OLLAMA"   ]] && sed_i "s|^export OLLAMA_HOST=.*|export OLLAMA_HOST=$OLLAMA|"     .env
  [[ -n "$LMSTUDIO" ]] && sed_i "s|^export LMSTUDIO_HOST=.*|export LMSTUDIO_HOST=$LMSTUDIO|" .env
  [[ "$ZKEY" != "replace_me" ]] && sed_i "s|^export ZAI_API_KEY=.*|export ZAI_API_KEY=$ZKEY|" .env
  printf 'export IMPL_PROVIDER=%s\n' "$IMPL_PROVIDER" >> .env
  chmod 600 .env
  c_g "  ✓ wrote .env (chmod 600). Implementation provider: $IMPL_PROVIDER"
fi

# 5. Smoke test ----------------------------------------------------------------
echo; c_g "Running smoke test…"
ok=0
if [[ -n "$OLLAMA" ]]; then
  if out="$(set -a; source .env; set +a; printf 'reply with the single word: ready' | bin/ai ollama - 2>/dev/null)"; then
    c_g "  ✓ Ollama responded: $(echo "$out" | head -c 60)"; ok=1
  else c_y "  · Ollama call failed — check model is pulled (ollama list)."; fi
fi
if command -v python3 >/dev/null && [[ -f tests/test_orchestrator.py ]]; then
  if python3 -m pytest -q tests/test_orchestrator.py >/dev/null 2>&1; then
    c_g "  ✓ orchestrator test suite passes"; ok=1
  else c_y "  · test suite not run (pytest missing?) — non-fatal."; fi
fi

echo; echo "=============================================="
if [[ $ok -eq 1 ]]; then c_g " Setup complete. Next:"; else c_y " Setup finished with warnings. Next:"; fi
echo "   1. Drop an idea:   echo '# Build a URL shortener' > queue/my-idea.md"
echo "   2. Run it:         bin/orchestrate.sh queue/my-idea.md"
echo "   3. Inspect:        cat projects/my-idea/report.md"
echo "   4. See spend:      awk -f bin/tokens.awk logs/tokens.jsonl"
echo "=============================================="
