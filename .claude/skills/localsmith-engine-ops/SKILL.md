---
name: localsmith-engine-ops
description: Operate and debug localsmith-engine, Marc's Bash+Python(stdlib) LLM orchestrator behind the Localsmith product (queue/<slug>.md -> scaffold -> plan -> implement -> verify, driven by orchestrate.sh + state.json). Use WHENEVER the task touches this repo (~/Development/Project/localsmith-engine): running or resuming a queued project, debugging orchestrate.sh/state.py/bin/ai provider routing (claude, codex, zai, ollama, lmstudio, fixture), interpreting or fixing bin/verify.sh failures (py_compile, bun install/build, docker build, model review), fixture-based smoke tests in tests/test_orchestrator.py, or bin/license.sh Lemon Squeezy Pro license activation. Trigger phrases: "run the orchestrator", "queue a project", "orchestrate.sh failed/stuck", "verify.sh failing", "add a provider", "AIWF_STEP/AIWF_PROJECT", "localsmith license", "WorkflowSmokeTest".
---

# localsmith-engine ops

Bash+Python(stdlib) LLM orchestrator — the engine behind the Localsmith product.
This is a real git repo; commit as usual.

## State machine

`queue/<slug>.md` is the source of truth for the slug (not whatever the LLM
names the project) — `scaffold.sh`'s idempotency check and `orchestrate.sh`'s
`run_project()` both derive `slug="$(basename "$idea" .md)"` this way.

Flow per project via `bin/orchestrate.sh queue/<slug>.md`:

1. `bin/scaffold.sh` creates `projects/<slug>/` + `tree.json` (idempotent).
2. `bin/state.py init` bootstraps `state.json` if missing.
3. Loop: read `current_step` (`bin/state.py get <pd> current_step`), dispatch
   to `bin/{plan,implement,verify}.sh <project_dir>`. `done` breaks the loop;
   an unimplemented step's script stops cleanly (lets steps land incrementally).
4. On failure, `bin/state.py mark <pd> <step> error "<msg>"` preserves state;
   orchestrate.sh returns non-zero for that project but keeps going in a batch
   (`bin/orchestrate.sh queue/*.md`).

**Re-running a step is always safe** — re-invoke `orchestrate.sh` on the same
idea file; it resumes from `current_step` rather than restarting. Ctrl-C-safe.

`orchestrate.sh` auto-loads `.env` (already-exported shell vars win as
overrides). Direct stage calls like `bin/verify.sh projects/<slug>` do NOT
auto-load `.env` — export flags first or `set -a; source .env; set +a`.

## bin/ai — 6-provider dispatcher

`bin/ai PROVIDER PROMPT` (or `-` for stdin). Providers: `claude`, `codex`,
`zai`, `ollama`, `lmstudio`, `fixture`. Per-stage routing via
`SCAFFOLD_PROVIDER`/`PLAN_PROVIDER`/`IMPL_PROVIDER`/`REVIEW_PROVIDER` in
`.env` (see `.env.example`; authoritative doc `docs/verification-flags.md`).

**Gotcha — subscription != API.** `claude`/`codex` are NOT REST calls: `bin/ai`
shells out to `subprocess.run(["claude","-p",...])` / `["codex","exec",...]`
(`call_claude`/`call_codex`), riding your logged-in Claude Pro/ChatGPT Plus
session (cost table reports `0.0`, real spend lives in the account dashboard).
No API-key path exists for these two — if the CLI isn't installed/logged-in on
the box, the stage fails with `CalledProcessError`, not an auth error fixable
via env var. `zai`/`ollama`/`lmstudio` are real REST calls with keys/hosts.

`fixture` is deterministic and token-free (see smoke-test section). LM Studio
accepts both `LMSTUDIO_*` and `LM_STUDIO_*` prefixes, incl. role-specific
`LMSTUDIO_{PLAN,IMPLEMENT,REVIEW}_MODEL`.

## bin/verify.sh — flag matrix + gotchas

Two free passes, aggregated into `<project>/report.md`, then
`bin/state.py mark <pd> verify done|error`:

| Flag | Default | Effect |
|---|---:|---|
| `VERIFY_PACKAGE_INSTALL` | 1 | `bun install` (`--frozen-lockfile` if lockfile exists) for `package.json` |
| `VERIFY_PACKAGE_BUILD` | 1 | `bun run build` if a `build` script exists |
| `VERIFY_MODEL_REVIEW` | 1 | pipes each file to `$REVIEW_PROVIDER` w/ `prompts/review.txt`, expects literal `OK` |
| `VERIFY_DOCKER_BUILD` | 0 | `docker build .` if `Dockerfile` exists — opt-in, slow, mutates cache |

Gotchas (see `CLAUDE_HANDOVER.md`):

- **`py_compile` catches syntax errors only, not hallucinated APIs** — a file
  can `py_compile` clean while calling a method that doesn't exist. That's why
  `VERIFY_MODEL_REVIEW=1` exists as a semantic-level gate; don't skip it and
  assume a green `py_compile` means correct code.
- **`bun install` needs `TMPDIR=/private/tmp` + escalated perms** on macOS
  (sandboxed tempdirs -> `PermissionDenied`):
  `env TMPDIR=/private/tmp VERIFY_MODEL_REVIEW=0 VERIFY_DOCKER_BUILD=1 bin/verify.sh projects/<slug>`.
- **Docker context balloons without `.dockerignore`** — one project went from
  ~525MB to ~202KB context once added; add it before `VERIFY_DOCKER_BUILD=1`.
- **`--frozen-lockfile` only fires once `bun.lock` exists** — first run does a
  plain `bun install`; commit the resulting `bun.lock`.
- Also covers `gofmt -l`/`go vet`/`go test ./...` (Go), `shellcheck`+`bash -n`
  (shell), `tsc --noEmit` (TS, only if `tsc`+`tsconfig.json` present, else
  `[SKIP]`), `hadolint` (Dockerfile), and a known-bad package-name check
  (`react-hookform` -> `react-hook-form`) before `bun install` runs.

## fixture provider — token-free gate before "done"

`tests/test_orchestrator.py::WorkflowSmokeTest` runs three synthetic projects
through the *real* scaffold -> state init -> plan -> impl -> verify chain, all
providers forced to `fixture`, `AI_FIXTURE_ROOT` pointing at pre-baked
`tree.json`/`plan.json`/`files/<task-path>` (`call_fixture` in `bin/ai` reads
these keyed by `$AIWF_STEP`). No network, no tokens, deterministic. Run before
calling any orchestrator change done:

```bash
python3 tests/test_orchestrator.py WorkflowSmokeTest   # or full suite:
python3 tests/test_orchestrator.py
```

## Lemon Squeezy license gate (bin/license.sh)

Client-side Pro-feature gate on Lemon Squeezy's **public** License API
(`https://api.lemonsqueezy.com/v1/licenses`) — no server key ships client-side,
only the customer's license key, stored `chmod 600` in `.license` (or
`$LOCALSMITH_LICENSE_FILE`).

```bash
bin/license.sh activate <license-key>   # once per machine; records instance_id
bin/license.sh validate                 # exit 0 = Pro, exit 2 = free tier
bin/license.sh status                   # human-readable
bin/license.sh deactivate               # release this machine's seat
```

Gate Pro-only behavior (e.g. the planned repair loop, `REPAIR_ENABLED=1` per
`docs/verification-flags.md`) behind `bin/license.sh validate`. Note the
**offline grace**: an unreachable Lemon Squeezy API keeps a previously-active
license valid (exit 0) rather than locking out a paying customer — only an
explicit `valid=False` reverts to free tier.

## Reference files

`AGENTS.md` (conventions) · `CLAUDE_HANDOVER.md` (latest state + known issues)
· `docs/verification-flags.md` (authoritative flags/providers) ·
`bin/orchestrate.sh`, `bin/ai`, `bin/verify.sh`, `bin/license.sh`,
`tests/test_orchestrator.py`.
