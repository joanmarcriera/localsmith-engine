# Workflow Flags and Strict Verification

This repository is configured through environment variables. Copy
`.env.example` to `.env`, edit it, then run commands from the workflow root:

```bash
cp .env.example .env
$EDITOR .env
```

`bin/orchestrate.sh` loads `.env` before dispatching stages, so provider routing
and verification flags set there apply to unattended runs. Already-exported shell
variables take priority, which keeps one-off overrides available:

```bash
VERIFY_DOCKER_BUILD=1 bin/orchestrate.sh queue/my-project.md
```

For direct stage runs such as `bin/verify.sh projects/my-project`, export the
flags in your shell first or run `set -a; source .env; set +a`.

## Provider Routing

Each workflow stage can use a different provider:

```bash
export SCAFFOLD_PROVIDER=ollama
export PLAN_PROVIDER=claude
export IMPL_PROVIDER=zai
export REVIEW_PROVIDER=lmstudio
```

Supported providers are `claude`, `codex`, `zai`, `ollama`, `lmstudio`, and
`fixture`.

LM Studio uses its OpenAI-compatible endpoint:

```bash
export LMSTUDIO_HOST=http://localhost:1234
export LMSTUDIO_MODEL=google/gemma-4-31b
```

The canonical variable prefix is `LMSTUDIO_*`, but `LM_STUDIO_HOST`,
`LM_STUDIO_MODEL`, and role-specific `LM_STUDIO_*_MODEL` aliases are also
accepted.

Role-specific model overrides also work:

```bash
export LMSTUDIO_PLAN_MODEL=google/gemma-4-31b
export LMSTUDIO_IMPLEMENT_MODEL=google/gemma-4-31b
export LMSTUDIO_REVIEW_MODEL=google/gemma-4-31b
```

Recommended local-heavy routing for frontend projects:

```bash
export PLAN_PROVIDER=lmstudio
export IMPL_PROVIDER=lmstudio
export REVIEW_PROVIDER=lmstudio
export LMSTUDIO_MODEL=google/gemma-4-31b
```

Use this only when LM Studio is already running and has the model loaded. If the
model is not loaded or the endpoint is down, the stage fails and state is
preserved for retry.

## Verification Flags

`bin/verify.sh` now checks generated package projects by running their own build
commands. This is what catches errors like invalid package names, App Router vs
Pages Router conflicts, missing dependencies, and TypeScript build failures.

Defaults:

```bash
export VERIFY_PACKAGE_INSTALL=1
export VERIFY_PACKAGE_BUILD=1
export VERIFY_MODEL_REVIEW=1
# export VERIFY_DOCKER_BUILD=1
```

Flags:

| Flag | Default | Effect |
|---|---:|---|
| `VERIFY_PACKAGE_INSTALL` | `1` | For `package.json` projects, runs `bun install` or `bun install --frozen-lockfile`. |
| `VERIFY_PACKAGE_BUILD` | `1` | If `package.json` has a `build` script, runs `bun run build`. |
| `VERIFY_MODEL_REVIEW` | `1` | Runs the configured `REVIEW_PROVIDER` code-review pass after static checks. |
| `VERIFY_DOCKER_BUILD` | `0` | If a `Dockerfile` exists, runs `docker build .`. Slower, but closest to deployment truth. |

Strict mode for projects where "done" must mean "container builds":

```bash
export VERIFY_PACKAGE_INSTALL=1
export VERIFY_PACKAGE_BUILD=1
export VERIFY_DOCKER_BUILD=1
export REVIEW_PROVIDER=lmstudio
export LMSTUDIO_MODEL=google/gemma-4-31b
bin/orchestrate.sh queue/my-project.md
```

Fast local mode for early experiments:

```bash
export VERIFY_PACKAGE_INSTALL=0
export VERIFY_PACKAGE_BUILD=0
export VERIFY_DOCKER_BUILD=0
export REVIEW_PROVIDER=ollama
bin/orchestrate.sh queue/my-project.md
```

## What Is Automated Today

The workflow can now fail a project before marking it done when:

- a package dependency name does not resolve,
- the generated app cannot install,
- the generated app cannot build,
- the Docker image cannot build when `VERIFY_DOCKER_BUILD=1`,
- static syntax checks fail,
- the local review model reports issues.

The workflow does not yet have a safe automatic repair loop that edits files after
verification fails. A failed project remains in `current_step: "verify"` with
`last_error` set, and the next run retries verification after a human or another
agent fixes the files.

## Future Repair Loop

LM Studio with Gemma can be used as the local model for a repair stage, but the
missing piece is not model access; it is safe patch application. A robust repair
stage should:

1. read `report.md`, the failed command output, `plan.json`, and relevant files,
2. ask a configured provider for a unified diff only,
3. apply the patch with path-safety checks,
4. rerun `bin/verify.sh`,
5. repeat up to `REPAIR_MAX_ATTEMPTS`,
6. stop with the report preserved if the same class of failure repeats.

Suggested future flags:

```bash
export REPAIR_ENABLED=1
export REPAIR_PROVIDER=lmstudio
export REPAIR_MAX_ATTEMPTS=3
export REPAIR_REQUIRE_CLEAN_PATCH=1
```

Until that exists, strict verification is the important guardrail: the workflow
should not call a project done unless the generated project passes the checks you
enabled.
