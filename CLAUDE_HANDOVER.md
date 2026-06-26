# Claude Handover - AI Workflow

Date: 2026-05-19  
Audience: Claude Opus/Sonnet taking over the local `AI workflow` workspace.

## Read This First

Workspace:

```bash
cd "/Users/marc/Development/Project/localsmith-engine"
```

This workspace is not a Git repository. Treat changes as local workspace edits,
not a PR branch.

Current state: the `zfs-website` generated project is fixed and verified. The
workflow now has stricter gates so a generated package project should not be
marked done just because static review passed.

## Current Verification Baseline

These commands were run successfully after the latest changes:

```bash
bash -n bin/orchestrate.sh
bash -n bin/verify.sh
python3 -m py_compile bin/ai tests/test_orchestrator.py
python3 tests/test_orchestrator.py
env TMPDIR=/private/tmp VERIFY_MODEL_REVIEW=0 VERIFY_DOCKER_BUILD=1 \
  bin/verify.sh projects/zfs-website
```

Observed results:

- Full test suite: 27 tests passed.
- `projects/zfs-website/report.md`: `## Result: PASS`.
- Strict `zfs-website` verifier includes `[OK] package dependency names`,
  `[OK] bun install --frozen-lockfile`, `[OK] bun run build`, and
  `[OK] docker build .`.

Docker access may need to run outside a sandbox because the local Docker socket is
under the user's Colima directory.

## What Changed In The Latest Session

Core workflow changes:

- `bin/orchestrate.sh` now loads `.env` before dispatching stages. Values already
  exported in the shell still override `.env`.
- `bin/verify.sh` now has package and build verification flags:
  `VERIFY_PACKAGE_INSTALL`, `VERIFY_PACKAGE_BUILD`, `VERIFY_MODEL_REVIEW`, and
  `VERIFY_DOCKER_BUILD`.
- `bin/ai` accepts both `LMSTUDIO_*` and `LM_STUDIO_*` variable prefixes for the
  LM Studio provider.
- `.env.example` groups provider routing, LM Studio/Gemma, and verification
  strictness flags.
- `docs/verification-flags.md` is now the authoritative flag reference.
- `README.md` links the verification flag docs and documents the stricter verify
  behavior.
- `docs/scheduler.md` now states that scheduled runs inherit `.env` through
  `bin/orchestrate.sh`.

Test coverage added:

- `OrchestrateExitStatusTest` now covers `.env` loading into child stages and
  explicit shell override priority.
- `DispatcherConfigTest` now covers the `LM_STUDIO_*` alias path for LM Studio.

## zfs-website Status

Project path:

```bash
projects/zfs-website
```

State:

- `projects/zfs-website/state.json` has `current_step: "done"`.
- `last_error` is `null`.
- `projects/zfs-website/report.md` passes with strict Docker verification when
  `VERIFY_DOCKER_BUILD=1` is enabled.

Important fixes already made there:

- Corrected package dependency typo: `react-hookform` to `react-hook-form`.
- Added/fixed dependencies needed for the Next.js app.
- Resolved App Router build conflicts and TypeScript/import/export problems.
- Added `bun.lock`.
- Hardened the Dockerfile to use frozen lockfile installs in builder and release
  stages.
- Added `.dockerignore`; Docker context dropped from roughly 525 MB to roughly
  202 KB.

Host-generated artifacts currently exist in the project:

- `node_modules/`
- `.next/`
- `next-env.d.ts`

They are expected after local verification/build work and are ignored by the
Docker context through `.dockerignore`.

## Provider And Flag Setup

For strict local-heavy runs with LM Studio/Gemma:

```bash
export PLAN_PROVIDER=lmstudio
export IMPL_PROVIDER=lmstudio
export REVIEW_PROVIDER=lmstudio
export LMSTUDIO_HOST=http://localhost:1234
export LMSTUDIO_MODEL=google/gemma-4-31b
export VERIFY_PACKAGE_INSTALL=1
export VERIFY_PACKAGE_BUILD=1
export VERIFY_MODEL_REVIEW=1
export VERIFY_DOCKER_BUILD=1
```

Aliases also work:

```bash
export LM_STUDIO_HOST=http://localhost:1234
export LM_STUDIO_MODEL=google/gemma-4-31b
```

`bin/orchestrate.sh` loads `.env` automatically. Direct stage calls such as
`bin/verify.sh projects/zfs-website` do not load `.env` by themselves, so export
flags first or run:

```bash
set -a
source .env
set +a
```

## What Is Not Implemented Yet

There is still no automatic safe repair loop. The verifier can now fail a project
before marking it done, but it does not ask a model to patch files and retry.

The planned shape is documented in `docs/verification-flags.md`:

```bash
export REPAIR_ENABLED=1
export REPAIR_PROVIDER=lmstudio
export REPAIR_MAX_ATTEMPTS=3
export REPAIR_REQUIRE_CLEAN_PATCH=1
```

A robust repair loop should:

1. read `report.md`, the failed command output, `plan.json`, and relevant files,
2. request a unified diff only,
3. validate paths before applying the patch,
4. rerun `bin/verify.sh`,
5. stop after `REPAIR_MAX_ATTEMPTS`,
6. preserve the final report and state error if repair fails.

Suggested implementation files:

- `bin/repair.sh`
- `prompts/repair.txt`
- tests in `tests/test_orchestrator.py`
- optional orchestrator integration after `verify` fails

Do not make the repair loop apply free-form model output. Require a clean unified
diff and reject paths outside the project.

## Known Remaining Issues

- `projects/wordcount-cli-realtest` is still intentionally failed in
  `current_step: "verify"`. It contains markdown/prose in generated Python files
  from an earlier local-only model run.
- TypeScript files show as skipped by direct static TypeScript checks when `tsc`
  is not available as a global command, but `bun run build` catches the Next.js
  build and type failures for package projects.
- `VERIFY_DOCKER_BUILD=1` is off by default because Docker builds are slower and
  mutate the local Docker cache.
- The workflow can detect build failures but cannot yet self-repair them.

## Recommended Next Steps For Claude

1. Implement the safe repair loop behind `REPAIR_ENABLED=1`.
2. Add tests for repair retry limits, unsafe patch rejection, and successful patch
   application followed by verifier success.
3. Consider a verifier test that stubs `docker` and proves `VERIFY_DOCKER_BUILD=1`
   blocks completion on Docker failure.
4. Improve Python project verification by running standard-library tests when a
   generated project includes `tests/`.
5. Only revisit `wordcount-cli-realtest` if Marc wants that sample project repaired;
   it is not blocking the `zfs-website` outcome.

## Quick Commands

Run the normal suite:

```bash
python3 tests/test_orchestrator.py
```

Run strict verification for `zfs-website`:

```bash
env TMPDIR=/private/tmp VERIFY_MODEL_REVIEW=0 VERIFY_DOCKER_BUILD=1 \
  bin/verify.sh projects/zfs-website
```

Run a queued project using the environment from `.env`:

```bash
bin/orchestrate.sh queue/my-project.md
```

Read the flag reference:

```bash
sed -n '1,220p' docs/verification-flags.md
```
