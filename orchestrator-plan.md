# Lean Multi-AI Orchestrator — Plan & Learning Path

**Profile**: 10–20 projects/month · save money · bash/python/awk · learn while building.

## Verified provider matrix (2026-05-17)

| Provider | Access path | Endpoint / command | Auth | Status |
|---|---|---|---|---|
| Claude | Pro subscription via Claude Code CLI | `claude -p "..."` (subprocess) | login session | available in sandbox |
| OpenAI | Plus subscription via Codex CLI | `codex exec "..."` (subprocess, runs on Mac M5) | login session | install on Mac |
| Z.AI GLM | Coding Lite API key | `POST https://api.z.ai/api/anthropic/v1/messages` | `x-api-key` header | confirmed working |
| Ollama (remote) | LAN box, 8GB VRAM | `POST http://192.168.0.5:30068/api/generate` | none | reachable, 19 models incl. `qwen2.5-coder:14b`, `glm-4.7-flash`, `mistral-small:24b` |
| LM Studio (Mac M5) | Local, Gemma 4 31B | `POST http://localhost:1234/v1/chat/completions` (OpenAI-compat) | none | pending (boots in ~30 min) |
| llama.cpp (Mac M5) | Future | `llama-server` → `:8080/v1/...` | none | not used yet |
| Perplexity | Pro subscription (web) | no API access — skip or use sonar API top-up | n/a | optional |

**Key implication**: Claude and OpenAI are reached via CLI subprocess, not REST. Z.AI uses
the Anthropic-compatible endpoint (the standard `/v4/chat/completions` route returns 1113
"insufficient balance" because Coding Lite quota lives on the Anthropic-compat path).

**Routing strategy** (cheapest first):
1. Scaffolding, classification, JSON shaping → **remote Ollama qwen2.5-coder:14b** (free)
2. Planning / architecture → **Claude Code** (Pro quota, no marginal cost)
3. Implementation → **Z.AI glm-4.6** (API key, included in Coding Lite plan)
4. Heavy reasoning / fallback → **Codex CLI** (Plus quota, no marginal cost)
5. Local final review → **LM Studio Gemma 4 31B** on Mac M5 (free, quality > Ollama)


**Verdict from your own analysis**: full LangGraph/Temporal stack does not pay off at this volume.
Break-even is 10–30 months. The "Simpler alternative" (better prompting + shell glue) captures
~80% of the savings with ~5% of the complexity. This plan codifies that path and leaves a
clean exit ramp to LangGraph later if volume grows.

---

## Architecture (final shape, 4 phases)

```
project_idea.md
   │
   ▼
[ scaffold.sh ]   ─ local Ollama (free) ─►  tree.json   (dirs + empty files only)
   │
   ▼
[ plan.sh ]       ─ Claude API (Opus)  ─►  plan.md      (task list, 1 task = 1 file)
   │
   ▼
[ impl.sh ]       ─ GPT-5 / Codex      ─►  src/*        (one task at a time, resumable)
   │
   ▼
[ research.sh ]   ─ Perplexity (only when plan flags "needs sources") ─► refs/*.md
   │
   ▼
[ verify.sh ]     ─ local Ollama       ─►  report.md    (lint, tests, sanity)
```

Single shared state file `state.json` per project. Bash drives orchestration; Python does
JSON, retries, and API calls. AWK handles log/token accounting. `cron` or `at` runs it
unattended. No new infra.

---

## Phase 1 — Foundations (Week 1, ~6h) · Goal: immediate token savings

**Learn**
- Token-counting basics: `tiktoken` (OpenAI), `anthropic.count_tokens`, request/response separation.
- Prompt scoping: ask for *structure only* first, *implementation* second. This is the trick
  that delivers 80% of the savings your analysis cited.
- HTTP retry patterns: exponential backoff with jitter (RFC 7231 §6.6.4 spirit; `tenacity` lib).

**Build**
- `bin/ai` — single Python CLI dispatcher: `ai claude "..."`, `ai gpt "..."`, `ai pplx "..."`,
  `ai ollama "..."`. One auth layer, one retry policy, one token logger (JSONL).
- `bin/tokens.awk` — parses the JSONL log; prints daily $ spend per provider.

**Exit criteria**: you can run `ai claude "hi" | ai gpt -` in a pipe, and `tokens.awk` shows
spend.

**Resources**
- Anthropic API docs: <https://docs.claude.com/en/api>
- OpenAI cookbook on retries: <https://cookbook.openai.com/examples/how_to_handle_rate_limits>
- `tenacity`: <https://tenacity.readthedocs.io>

---

## Phase 2 — Local scaffolding (Week 2, ~6h) · Goal: free project skeletons

**Learn**
- Ollama HTTP API (`POST /api/generate`), structured JSON output via `format: "json"`.
- Why Gemma/Qwen-coder 7B is enough for *file trees* but not for *implementation*.
- The "scaffold-then-implement" split — the single biggest cost lever.

**Build**
- `scaffold.sh PROJECT_DESC` → calls Ollama with a strict JSON schema prompt, writes
  `tree.json`, then `mkdir -p` / `touch` to materialise the empty repo.
- Schema validation in Python (`jsonschema`) so a bad model output fails loud, not silent.

**Exit criteria**: `scaffold.sh "todo cli in python"` produces an empty tree with no cloud
tokens spent.

**Resources**
- Ollama API: <https://github.com/ollama/ollama/blob/main/docs/api.md>
- JSON Schema: <https://json-schema.org/learn/getting-started-step-by-step>

---

## Phase 3 — Resumable orchestration (Week 3, ~8h) · Goal: survive rate limits unattended

**Learn**
- The cheap version of "durable execution": state machine in a JSON file + idempotent steps.
- Token-bucket rate limiting (Wikipedia: Token bucket) — implement in ~30 lines of Python.
- Why "one task = one file = one API call" makes retries trivial.

**Build**
- `state.json` schema: `{project, current_step, completed_steps, step_outputs, tokens}`.
- `orchestrate.sh` — reads `state.json`, dispatches the next step, writes back on success.
  Safe to Ctrl-C and re-run. Skips completed steps.
- `ratelimit.py` — token bucket per provider, sleeps when empty. Reads RPM/TPM from `.env`.

**Exit criteria**: kill the process mid-run; restart picks up at the last incomplete step.

**Resources**
- Token bucket explained: <https://en.wikipedia.org/wiki/Token_bucket>
- Idempotency patterns: <https://stripe.com/blog/idempotency>

---

## Phase 4 — Verification + scheduling (Week 4, ~4h) · Goal: unattended runs

**Learn**
- `cron` vs `at` vs `launchd` (macOS); when to pick which.
- Cheap verification: local model reads diff, runs `pytest`/`shellcheck`, scores.

**Build**
- `verify.sh` — runs linters + tests + local-LLM review, appends to `report.md`.
- `cron` entry: `*/30 * * * * /path/orchestrate.sh ~/queue/*` to drain a queue folder.
- Slack/email notify on completion (optional; `curl` to a webhook).

**Exit criteria**: drop an idea file in `~/queue/`, walk away, come back to a finished project.

**Resources**
- `launchd` on macOS: `man launchd.plist`
- `shellcheck`: <https://www.shellcheck.net>

---

## Exit ramp (only if volume hits 50+/month)

Each step above maps 1:1 to a LangGraph node. When/if you migrate:
- `state.json` → `StateGraph` typed state
- `orchestrate.sh` → graph edges
- `ratelimit.py` → keep as-is, call from node functions
- No rewrite of the *prompts*, which is where the real value lives.

You will have spent ~24h to save the £20–50/month you projected — break-even in 6–10 months
if your time is valued at £10/h, much faster if you'd otherwise have spent that time
context-switching between tools manually.

---

## File layout (target)

```
AI workflow/
├── bin/
│   ├── ai                 # python dispatcher (all providers)
│   ├── tokens.awk         # spend report from log
│   ├── ratelimit.py       # token bucket
│   └── orchestrate.sh     # main driver
├── lib/
│   ├── providers/         # one file per: claude.py, gpt.py, pplx.py, ollama.py, zai.py
│   └── schema/            # JSON schemas (tree, plan, state)
├── prompts/               # versioned prompt templates (git-tracked)
├── queue/                 # drop project_idea.md files here
├── projects/<name>/
│   ├── state.json
│   ├── tree.json
│   ├── plan.md
│   ├── src/
│   └── report.md
├── logs/
│   └── tokens.jsonl       # one line per API call
└── .env                   # API keys, RPM/TPM limits
```

Standards: shellcheck-clean bash, `python -m pip install` from `requirements.txt`, all configs
in `.env` (12-factor), JSON Schema for every persisted blob.

---

## What I need from you next

1. **Rotate the Z.AI key after the project** (it was pasted in plain text). Meanwhile I'll
   read it from `AI workflow/.env` only — never hard-coded.
2. **Install Codex CLI on your Mac M5** so the dispatcher can shell out to it:
   `npm i -g @openai/codex` (or use `brew install codex` if available), then `codex login`
   once. Sandbox can't install it for you; this is a one-time Mac action.
3. **Pick one real project idea** for Phase 5 (the end-to-end test). A small CLI tool is
   ideal — small enough to finish, real enough to exercise every step.
4. **Say "go Phase 1"** and I'll write `bin/ai`, `bin/tokens.awk`, `.env.example`, and a
   `requirements.txt` into this folder — documented, shellcheck/ruff-clean, tested against
   the live Z.AI + Ollama endpoints.
