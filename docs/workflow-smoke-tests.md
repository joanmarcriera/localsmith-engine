# Workflow smoke tests

The end-to-end smoke tests live in `tests/test_orchestrator.py` under
`WorkflowSmokeTest`. They run three tiny projects through the same shell scripts as
the normal workflow:

1. `smoke-python`
2. `smoke-shell`
3. `smoke-go`

Each project executes:

```text
scaffold.sh -> state.py init -> plan.sh -> impl.sh -> verify.sh
```

The tests intentionally use a deterministic `fixture` provider instead of calling
Claude, Z.AI, Ollama, LM Studio, or Codex. This keeps the checks fast, repeatable,
and zero-cost while still exercising the orchestration contracts that usually break
when prompt outputs or step glue drift.

## What Gets Tested

The three smoke projects cover the full project lifecycle:

- `scaffold.sh` reads a queued idea, asks `bin/ai fixture` for `tree.json`, and
  materializes the project directory.
- `state.py init` creates `state.json` and marks `scaffold` complete.
- `plan.sh` asks `bin/ai fixture` for `plan.json`, validates it with
  `validate_plan.py`, writes it atomically, and marks `plan` complete.
- `impl.sh` loops over every plan task, calls `bin/ai fixture` for each file body,
  writes source files atomically, and records usage back into project state.
- `verify.sh` runs static checks and then uses `bin/ai fixture` for local-review
  answers where a review pass is needed.
- `logs/tokens.jsonl` receives normal usage records containing `project` and `step`.
- `state.json["tokens"]` accumulates fixture token counts through the existing
  `state.py addusage` path.
- `report.md` must finish with `## Result: PASS`.

The Go smoke project also proves the Go verifier path still runs `go test ./...`.
The shell smoke project proves `bash -n` is reported. The Python smoke project
proves regular source-file materialization works.

## Fixture Provider Contract

`bin/ai fixture` reads from this layout:

```text
$AI_FIXTURE_ROOT/<project>/
├── tree.json
├── plan.json
├── review.txt        optional; defaults to OK
└── files/
    └── <task paths from plan.json>
```

The workflow scripts already set `AIWF_PROJECT` and `AIWF_STEP`, so the provider
can choose the right fixture:

- `AIWF_STEP=scaffold` returns `tree.json`.
- `AIWF_STEP=plan` returns `plan.json`.
- `AIWF_STEP=implement` parses the `--- FILE TO IMPLEMENT ---` prompt marker and
  returns `files/<path>`.
- `AIWF_STEP=verify` returns `review.txt` or `OK`.

Path traversal in implementation fixtures is rejected before reading files.

## Run The Tests

Run only the workflow smoke tests:

```bash
python3 tests/test_orchestrator.py WorkflowSmokeTest
```

Run the full current test suite:

```bash
python3 tests/test_orchestrator.py
```

The tests create temporary queue, project, fixture, and log roots. They do not write
into real `queue/`, `projects/`, or `logs/`, and they do not require live network
access.

## What This Protects

These tests should catch:

- provider routing drift between `SCAFFOLD_PROVIDER`, `PLAN_PROVIDER`,
  `IMPL_PROVIDER`, `REVIEW_PROVIDER`, and `bin/ai`;
- plan schema changes that `impl.sh` cannot consume;
- state transitions that fail to advance or record usage;
- verification regressions for Python, shell, and Go output;
- accidental token-log shape changes that would break the dashboard or stats tools.

They are not a substitute for live LAN checks. Use the dashboard `/tools` page or
`bin/search` for SearXNG/Ollama health when you need to verify the real
`192.168.0.5` services.
