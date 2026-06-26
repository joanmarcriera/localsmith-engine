# Engineering preferences

You are working inside Marc's project pipeline. Apply these defaults unless the project idea
explicitly contradicts them, in which case follow the idea.

## Language & runtime defaults

- **Default MVP stack: Go + SQLite + stdlib `net/http`.** Single binary, no cgo. Use
  `modernc.org/sqlite` (pure-Go SQLite) so the binary stays portable. Go module path
  follows the project slug. Migrations as `.sql` files embedded with `embed.FS`.
- **Python projects: use `uv`.** `pyproject.toml` is the source of truth. Run things with
  `uv run`, install with `uv add`, lock with `uv lock`. No `requirements.txt` unless an
  existing project already has one. Lint/format with `ruff`. Test with `pytest`.
- **JavaScript/TypeScript: prefer Bun over Node.** Use `bun install`, `bun run`. Plain
  TypeScript over JavaScript when a build step is already involved.

## Containerization

- **Every project gets a `Dockerfile`.** Even one-file scripts — it forces dependency
  hygiene and gives unattended deploy parity. Multi-stage builds: builder + slim runtime.
  Use `gcr.io/distroless/static-debian12` for Go, `python:3.12-slim` for Python, `oven/bun`
  for Bun.
- Include a minimal `compose.yaml` whenever the project has more than one process
  (e.g. app + sqlite-volume + reverse proxy). Single-process projects can skip compose.
- Health check in the Dockerfile (`HEALTHCHECK` directive) when the project exposes HTTP.

## Frontend

- **Decide per project.** If the project idea spells out the approach, follow it. Otherwise
  pick by feature surface:
  - Static or one-page game / dashboard → vanilla HTML+JS, no build step.
  - Server-rendered CRUD with light interactivity → HTMX + Go html/template (or Jinja2 if
    Python).
  - Real SPA-level interaction needed → Vite + React + TypeScript, served by the Go/Python
    backend as static assets in production.

## Code quality bars

- Standards over cleverness. Idiomatic for the language. Documented public APIs.
- Lint clean: `gofmt`/`go vet` for Go, `ruff check` for Python, `bun lint` if a project
  defines it.
- Tests for non-trivial logic — table-driven in Go, `pytest` in Python. Skip tests for
  prompt-only / glue scripts where reading the code is faster than running it.
- Shell scripts: `set -euo pipefail`, shellcheck-clean, prefer bash over sh when arrays or
  `[[ ]]` are useful.

## Project layout (when not constrained by the idea)

For Go MVPs:
```
<slug>/
├── cmd/<slug>/main.go
├── internal/<pkg>/...
├── migrations/0001_init.sql
├── Dockerfile
├── compose.yaml          # only if multi-process
├── go.mod
└── README.md
```

For Python projects:
```
<slug>/
├── src/<slug>/__init__.py
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Things to avoid

- `pip install` in instructions — always use `uv` for Python.
- Heavy frameworks for tiny problems (no Django for a 50-line CRUD).
- Inventing API names. If unsure whether `socketserver.ThreadingHTTPServer` exists, use
  `http.server.ThreadingHTTPServer`. Prefer stdlib symbols you can name with certainty.
- Background daemons or `systemd` units in the README — the Dockerfile is the deploy unit.
