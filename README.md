# AI workflow

Bash + Python orchestrator that chains local and cloud LLMs to ship small projects
unattended. Designed for ~10–20 projects/month on a personal stack.

Routes free work (scaffolding, code review) to local models and only spends money on
the implementation step. Resumable, idempotent, no external infra — `state.json` per
project is the whole state machine.

## Quickstart

```bash
# 1. One-time setup
cp .env.example .env && $EDITOR .env       # fill in ZAI_API_KEY at minimum
$EDITOR prefs.md                            # adjust engineering defaults / local-first routing

# 2. Add an idea
cat > queue/my-project.md <<'EOF'
# Project — my-project
Short description of what to build.
Constraints, acceptance criteria.
EOF

# 3. Run the pipeline
bin/orchestrate.sh queue/my-project.md

# 4. Inspect
cat projects/my-project/report.md          # verification result
awk -f bin/tokens.awk logs/tokens.jsonl    # spend rollup
bin/search "docs for the API I am about to use"  # local SearXNG grounding
```

For unattended execution see [`docs/scheduler.md`](docs/scheduler.md). For provider
routing and strict verification flags, including LM Studio/Gemma and Docker build
checks, see [`docs/verification-flags.md`](docs/verification-flags.md). For the
current Claude Opus/Sonnet handover, see [`CLAUDE_HANDOVER.md`](CLAUDE_HANDOVER.md).

## What gets executed

```
queue/<slug>.md
   │
   ▼
[ bin/scaffold.sh ]   Ollama qwen2.5-coder:14b — free          → tree.json (empty repo skeleton)
   │
   ▼
[ bin/plan.sh ]       Claude via `claude -p` — Pro quota       → plan.json (one task per file)
   │
   ▼
[ bin/impl.sh ]       Z.AI glm-4.6 — Coding Lite quota          → src/*, README, Dockerfile, …
   │
   ▼
[ bin/verify.sh ]     py_compile/ruff/gofmt/shellcheck + Ollama review — free → report.md
```

Provider routing is controlled by env vars (`PLAN_PROVIDER`, `IMPL_PROVIDER`,
`REVIEW_PROVIDER`, `SCAFFOLD_PROVIDER`) — defaults shown above. Model routing is
controlled by provider/role env vars such as `OLLAMA_MODEL`,
`OLLAMA_SCAFFOLD_MODEL`, and `OLLAMA_REVIEW_MODEL`. `bin/orchestrate.sh` is just a
small driver that reads `state.json` and dispatches the next step.

## Directory layout

```
AI workflow/
├── README.md                  this file
├── CLAUDE_HANDOVER.md         current handover for Claude Opus/Sonnet
├── orchestrator-plan.md       original design doc + phase plan
├── docs/scheduler.md          launchd install/manage instructions
├── docs/verification-flags.md  provider routing + strict verification flags
├── docs/workflow-smoke-tests.md fixture-backed full-step test docs
├── prefs.md                   engineering preferences injected as system prompt
├── .env                       secrets + endpoint config (NOT committed)
├── .env.example               template
├── requirements.txt           dependency notes — runtime scripts are stdlib-only today
│
├── bin/                       executables
│   ├── ai                     unified LLM dispatcher (6 providers)
│   ├── search                 local SearXNG search helper
│   ├── tokens.awk             spend rollup from JSONL log
│   ├── state.py               atomic read/write of state.json
│   ├── materialize.py         JSON tree → mkdir/touch
│   ├── validate_plan.py       strict plan.json safety validator
│   ├── scaffold.sh            idea → tree
│   ├── plan.sh                idea + tree → plan.json
│   ├── impl.sh                plan → source files
│   ├── implement.sh           symlink used by the state-machine step name
│   ├── verify.sh              static checks + local-model review → report.md
│   └── orchestrate.sh         driver: reads state, runs next step
│
├── lib/schema/                JSON Schemas (tree, state, plan)
├── prompts/                   prompt templates (scaffold, plan, impl, review)
├── launchd/                   macOS scheduler plist
│
├── queue/                     project ideas drop here, one .md per project
├── projects/                  generated projects, one folder per project
│   └── <slug>/
│       ├── state.json         the state machine
│       ├── tree.json          empty repo skeleton
│       ├── plan.json          per-file implementation plan
│       ├── report.md          verification report
│       ├── src/, cmd/, …      actual code
│       └── ...
└── logs/
    ├── tokens.jsonl           one line per API call (provider, tokens, $)
    ├── launchd.out            scheduler stdout
    └── launchd.err            scheduler stderr
```

## `bin/ai` — the dispatcher

Single Python script, stdlib only, talks to six providers behind one interface:

| Provider | How it reaches the model | Auth | Marginal cost |
|---|---|---|---|
| `claude` | subprocess `claude -p` | Claude Pro session | 0 (subscription) |
| `codex` | subprocess `codex exec` | ChatGPT Plus session | 0 (subscription) |
| `zai` | POST `api.z.ai/api/anthropic/v1/messages` | `ZAI_API_KEY` env | included in Coding Lite plan |
| `ollama` | POST `OLLAMA_HOST/api/generate` | none | 0 (local) |
| `lmstudio` | POST `LMSTUDIO_HOST/v1/chat/completions` | none | 0 (local) |
| `fixture` | local files under `AI_FIXTURE_ROOT` | none | 0 (tests only) |

Usage:

```bash
bin/ai zai "what is the capital of Portugal?"
echo "translate to bash" | bin/ai claude -                    # stdin
bin/ai ollama "explain pipes" --system @prefs.md              # system prompt from file
bin/ai ollama "review this" --model qwen2.5-coder:7b          # one-off model override
bin/ai zai "return the empty object" --json                   # JSON-constrained output
```

The `lmstudio` provider uses OpenAI-compatible `/v1/chat/completions` so the same
code path works against llama.cpp's `llama-server` later — just point `LMSTUDIO_HOST`
at it.

`bin/ai` also writes `project` and `step` fields to `tokens.jsonl` when callers set
`AIWF_PROJECT` and `AIWF_STEP`. The workflow scripts do this automatically and fold
usage back into each project's `state.json["tokens"]`.

For deterministic end-to-end tests, use the `fixture` provider. It is documented in
[`docs/workflow-smoke-tests.md`](docs/workflow-smoke-tests.md) and exists only to
exercise the workflow without spending tokens or depending on LAN services.

## Local search and model inventory

The LAN box at `192.168.0.5` exposes:

- Ollama: `http://192.168.0.5:30068`
- SearXNG: `http://192.168.0.5:30053`

Use `bin/search` to ground prompts before spending cloud quota:

```bash
bin/search "go html/template block inheritance" --limit 5
bin/search "sqlite modernc busy_timeout WAL" --json
bin/search "json schema 2020-12 oneOf" --backend brave   # force Brave Web Search
```

`bin/search` defaults to `--backend auto`: SearXNG first, **Brave Search** as a fallback
when SearXNG is unreachable or returns nothing. Brave needs `BRAVE_API_SEARCH` in `.env`
(free tier: 2000 req/month).

The dashboard's `/tools` page lists Ollama models, shows SearXNG health, and provides
a local search box. The intended default is: SearXNG for fresh facts, small/fast
Ollama models for routing and scaffolding, stronger local code models for review,
and cloud providers only when local tools are insufficient.

## The state machine

Every project has a `state.json` with this shape (see
[`lib/schema/state.schema.json`](lib/schema/state.schema.json)):

```json
{
  "project": "my-project",
  "current_step": "implement",
  "completed": ["scaffold", "plan"],
  "outputs": {"scaffold": "tree.json", "plan": "plan.json"},
  "tokens": {"zai": {"in": 1234, "out": 5678}},
  "last_error": null
}
```

Writes are atomic (`tempfile` + `os.replace`) so Ctrl-C never leaves it corrupt.
The orchestrator picks `current_step` and runs the matching `bin/<step>.sh`. Steps
are idempotent: re-running a completed step is safe (impl skips non-empty files,
scaffold skips when `tree.json` exists, verify rewrites `report.md`).

## Verification

`bin/verify.sh` runs local checks before a project can be marked done:

1. **Static checks** per file extension: `python3 -m py_compile`, `ruff check`,
   `gofmt -l`, `go vet`, `bash -n`, `shellcheck`, `node --check`, `hadolint`.
   Catches syntax errors, lint violations, dead imports.
2. **Package checks** for `package.json` projects: dependency-name sanity,
   `bun install` or `bun install --frozen-lockfile`, and `bun run build` when a
   build script exists.
3. **Optional Docker check** with `VERIFY_DOCKER_BUILD=1`, which runs
   `docker build .` for projects with a Dockerfile.
4. **Local-model review** via the configured `REVIEW_PROVIDER` with
   `prompts/review.txt` as the system prompt.
   Looks for hallucinated APIs (the `socketserver.ThreadingHTTPServer` class of bug
   that compiles but crashes at runtime), obvious logic errors, and security smells.

Result aggregated into `report.md`. Non-zero exit + `last_error` set on any failure;
state preserved so the next orchestrate tick can retry.

Set strictness in `.env` or your shell:

```bash
export REVIEW_PROVIDER=lmstudio
export LMSTUDIO_MODEL=google/gemma-4-31b
export VERIFY_PACKAGE_INSTALL=1
export VERIFY_PACKAGE_BUILD=1
export VERIFY_DOCKER_BUILD=1
```

The full flag reference is in
[`docs/verification-flags.md`](docs/verification-flags.md).

The workflow step contracts are covered by three fixture-backed smoke projects:

```bash
python3 tests/test_orchestrator.py WorkflowSmokeTest
```

## Engineering preferences

`prefs.md` is injected as the `--system` prompt for both `plan` and `impl` steps.
Edit it to change defaults globally (current defaults: Go + SQLite for MVPs, uv for
Python, Dockerfile for every project, frontend chosen per project).

## Cost ledger

Every dispatch appends one JSONL record to `logs/tokens.jsonl`:

```json
{"ts":"2026-05-17T...","provider":"zai","model":"glm-4.6","in":42,"out":108,"usd":0.000262,"sec":1.4}
```

Daily rollup:

```bash
awk -f bin/tokens.awk logs/tokens.jsonl
```

First end-to-end project (silly-web-game): **$0.015**, 17 calls, ~7 min wall time.

## Status of the build (May 2026)

- [x] Phase 1: dispatcher + token logger
- [x] Phase 2: scaffold (Ollama, free, structured JSON output)
- [x] Phase 3: state machine + orchestrator + plan + impl
- [x] Phase 4: verify (static + local-model review) + launchd plist
- [x] Engineering preferences via `prefs.md`
- [x] End-to-end verified on `silly-web-game`
- [ ] Rate limiter (deferred — no throttling encountered in testing)
- [ ] Notification webhook on completion (optional)

## When to migrate off this

If volume hits 50+ projects/month, or runs start exceeding 5+ hours with rate-limit
pauses, the same prompts and state schema map cleanly onto LangGraph nodes. Until
then the bash glue is genuinely simpler — see
[`orchestrator-plan.md`](orchestrator-plan.md) for the migration ramp.

## Lessons learned (real failures encountered during the build)

1. **`python3 - "$arg" <<'PY'`** consumes stdin for the script body — you can't pipe
   data in too. Use tempfiles or `-c`.
2. **LLMs in JSON mode still wrap output in `` ```json `` fences** sometimes. `bin/ai`
   strips them centrally when `--json` is set.
3. **`py_compile` does not catch hallucinated APIs.** `socketserver.ThreadingHTTPServer`
   compiles fine, fails at runtime. The local-model review pass is what catches these.
4. **Subscription ≠ API access.** Claude Pro and ChatGPT Plus only reach their models
   via the `claude` / `codex` CLIs, not raw REST.
5. **`ls -1t | head -1` is not a slug**. Always derive project slug from the idea
   filename — `queue/<slug>.md` → `projects/<slug>/`.

<!-- vikunja-tracking -->
## Tracking

Vikunja project **69 · Localsmith** — https://familia.riera.co.uk/projects/69
