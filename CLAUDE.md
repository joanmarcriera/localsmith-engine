# localsmith-engine: Bash+Python LLM orchestrator

**Purpose:** Unattended, cost-efficient project generator that chains local (Ollama) and cloud (Claude, Z.AI) LLMs. One markdown idea → 4-step pipeline (scaffold → plan → implement → verify) → working codebase + validation report.

Designed for ~10–20 projects/month with **idempotent, resumable state** (`state.json` per project) and **atomic file writes** (safe to Ctrl-C). Meant to be run on a solo developer's Mac via launchd scheduler or triggered ad-hoc.

## Quick start

```bash
cp .env.example .env && $EDITOR .env       # set ZAI_API_KEY (minimum)
cat > queue/my-project.md <<'EOF'
# Project — my-project
Brief idea + constraints.
EOF
bin/orchestrate.sh queue/my-project.md     # runs until done or error
cat projects/my-project/report.md          # verification result
awk -f bin/tokens.awk logs/tokens.jsonl    # spend rollup
```

See `docs/scheduler.md` for unattended launchd setup.

## Layout

```
bin/                        executables (Python + Bash)
  ai                        6-provider LLM dispatcher (claude, codex, zai, ollama, lmstudio, fixture)
  {scaffold,plan,impl,verify}.sh   stage scripts
  state.py                  atomic state.json read/write
  orchestrate.sh            driver: reads state, dispatches next step
  materialize.py, validate_plan.py, tokens.awk  utilities
lib/schema/                 JSON Schemas (tree, state, plan)
prompts/                    stage-specific system prompts
tests/test_orchestrator.py  unit + smoke tests (fast, fixture-backed)
queue/                      ideas drop here (.md per project)
projects/                   generated projects (state.json, tree.json, src/, report.md)
.env                        secrets + routing (NOT in git)
prefs.md                    engineering defaults (Go+SQLite, Bun for JS, uv for Python)
```

## How to test

```bash
# Regression suite (stdlib only, no network, <1s)
python3 tests/test_orchestrator.py

# Specific test class
python3 tests/test_orchestrator.py WorkflowSmokeTest

# Check tokens spent
awk -f bin/tokens.awk logs/tokens.jsonl
```

## Conventions & gotchas

**State machine:** One `.md` file in `queue/` → `projects/<slug>/` (slug is filename, not LLM-chosen). Resumable: re-run `orchestrate.sh` on same idea to continue from `current_step`. Steps are idempotent (scaffold skips if `tree.json` exists, etc).

**Provider routing:** `SCAFFOLD_PROVIDER=ollama`, `PLAN_PROVIDER=claude`, `IMPL_PROVIDER=zai`, `REVIEW_PROVIDER=ollama` (defaults, per `.env.example`). Claude/Codex are NOT REST — they shell out to logged-in CLI sessions; no `.env` key makes them unavailable (not auth-fixable).

**Verification:** `bin/verify.sh` runs free checks (lint, py_compile, bun install) + optional docker build + local-model review. Model review catches hallucinated APIs that py_compile misses (e.g. `socketserver.ThreadingHTTPServer` compiles fine but crashes at runtime). Set strictness via `VERIFY_PACKAGE_INSTALL=1`, `VERIFY_DOCKER_BUILD=1` in `.env`.

**bun on macOS:** Needs `TMPDIR=/private/tmp` + escalated perms (`env TMPDIR=/private/tmp bin/verify.sh projects/<slug>`). Docker context balloons without `.dockerignore`.

**Engineering defaults:** See `prefs.md` — Go+SQLite+stdlib for MVPs, `uv` for Python, Bun for JS, every project gets a Dockerfile. Table-driven tests in Go, pytest in Python, skip tests for glue scripts.

**Token logging:** Every `bin/ai` call appends to `logs/tokens.jsonl` (provider, model, spend, seconds). Fold into `state.json["tokens"]` for per-project accounting.

**Git:** Real git repo. Commit per logical unit. Reference skill: `localsmith-engine-ops`.

## Known issues & reference

- See `CLAUDE_HANDOVER.md` for current state + blockers.
- Provider/flag docs: `docs/verification-flags.md`.
- License gate: `bin/license.sh activate <key>` (Lemon Squeezy Pro API).
- Offline grace: unreachable API keeps a previously-valid license active.
