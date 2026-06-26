# Project — dashboard

A local-only web dashboard for the AI workflow orchestrator. Read-mostly view over
the existing filesystem state — no database, no auth, no users. Single-user, runs on
the same Mac as the orchestrator.

## Why

The orchestrator already works headlessly. Today the only visibility is `cat state.json`
and `awk -f bin/tokens.awk logs/tokens.jsonl`. As the queue grows past 5–10 projects
this becomes painful. A dashboard collapses all signals into one tab.

## User

One operator (Marc). Knows the system. Wants glance-friendly status, not training wheels.
Optimise for information density over hand-holding.

## Stack (mandatory)

- **Backend**: Go 1.22+, stdlib `net/http` only. No external HTTP framework.
  Single binary. Module path `github.com/marc/ai-workflow-dashboard`.
- **Frontend**: HTMX (loaded from CDN, single `<script>` tag), Go `html/template`
  server-rendered. No build step, no npm, no React.
- **Styling**: inline `<style>` in the layout template. Pico.css from CDN for sane
  defaults if it keeps the CSS under 100 lines.
- **No database.** All state is read from JSON files on every request. The files are
  tiny (<10 KB total) and request rate is one operator polling every few seconds.
- **Dockerfile required** (per prefs.md), multi-stage, distroless static runtime.

Polling via HTMX `hx-trigger="every 5s"` is fine; do not introduce WebSockets.

## Data sources (read these paths, do not invent fields)

All paths relative to the workflow root, configured via `--root` flag (default `.`).

### `projects/<slug>/state.json`

```json
{
  "project": "silly-web-game",
  "idea_path": "/abs/path/queue/silly-web-game.md",
  "created_at": "2026-05-17T20:11:37+00:00",
  "updated_at": "2026-05-17T21:16:36+00:00",
  "steps": ["scaffold","plan","implement","verify","done"],
  "current_step": "done",
  "completed": ["scaffold","plan","implement","verify"],
  "outputs": {"scaffold":"tree.json","plan":"plan.json","verify":"report.md"},
  "tokens": {"zai":{"in":5757,"out":5364}},
  "last_error": null
}
```

### `projects/<slug>/plan.json`

```json
{
  "project": "silly-web-game",
  "decisions": "free-text architectural notes",
  "tasks": [
    {"path":"README.md","intent":"...","deps":[]},
    {"path":"src/server.py","intent":"...","deps":["src/index.html"]}
  ]
}
```

### `projects/<slug>/tree.json`

```json
{"project":"slug","summary":"one-liner","paths":["README.md","src/","src/index.html"]}
```

### `projects/<slug>/report.md`

Free-form markdown. Render with a minimal markdown→HTML pass (the stdlib doesn't
include one — use `github.com/yuin/goldmark` as the single allowed dependency, or
roll a tiny converter that handles headings + code fences + lists only).

### `logs/tokens.jsonl`

One JSON object per line:

```json
{"ts":"2026-05-17T...","provider":"zai","model":"glm-4.6","in":42,"out":108,"usd":0.000262,"sec":1.4}
```

Read the whole file on each request (under 1 MB even at high volume — fine).

### `queue/*.md`

Idea files. Filename without `.md` = project slug. File body is the idea text.

## Views

### 1. `/` — Dashboard

Table of every project with one row per project. Columns:

- **Slug** (link to `/p/<slug>`)
- **Step** — badge: `scaffold` / `plan` / `implement` / `verify` / `done` / `error`.
  Colour: grey / blue / blue / blue / green / red. Show `error` if `last_error != null`.
- **Progress** — `n/4` plus a tiny progress bar (CSS-only, no JS).
- **Updated** — relative time ("2 min ago"), computed client-side from `updated_at`.
- **Spend** — sum across providers in tokens.json (sum of in+out for that project,
  matched by accumulating tokens.jsonl entries whose project matches — see below).
- **Last error** — truncated, hover tooltip.

Header row: total spend today (£/$), Ollama reachability dot, Z.AI reachability dot,
queue depth.

Auto-refresh every 5s.

### 2. `/p/<slug>` — Project detail

Four collapsible panels:

1. **State** — pretty-printed state.json. Highlight `current_step` and `last_error`.
2. **Plan** — task list rendered from plan.json. Each task: path, one-line intent,
   deps as inline pills. Tick mark next to tasks whose target file exists and is
   non-empty. (This is how impl.sh decides "done", so the UI should mirror that.)
3. **Files** — tree.json paths rendered as a `<details>` tree. Click a file → opens
   its source in a syntax-highlighted code block (server-side, language detected by
   extension; use Goldmark for `.md`, otherwise dump as `<pre><code>`).
4. **Report** — render report.md with the markdown pass.

Sidebar: token usage broken down by provider (table, not chart).

### 3. `/queue` — Queue

List queue/*.md files. Filename, file size, mtime. Each item links to the project
detail if `projects/<slug>/` exists, else shows "not yet processed".

A `<textarea>` + form to **add a new idea**. POST to `/queue` writes
`queue/<slug>.md` where slug comes from the form (validated against
`^[a-z0-9][a-z0-9-]{0,63}$`). No filesystem writes outside `queue/` ever.

### 4. `/spend` — Spend

Read full `logs/tokens.jsonl`. Render two tables (no chart libraries):

- **By day**: date, calls, in_tok, out_tok, usd, sec — same columns as
  `bin/tokens.awk` output. Last 14 days.
- **By provider**: provider, calls, in_tok, out_tok, usd — lifetime.

Plus a single number at the top: "Today: $X.XX". Style it big.

## Project-to-token attribution

`tokens.jsonl` has no project field. Two options, pick the simpler:

- **Option A (recommended)**: read each project's `state.json["tokens"]` directly.
  This is the source of truth maintained by `bin/state.py addtok`. Per-project spend
  = sum of in+out across providers, multiplied by the provider rate from a tiny
  hardcoded table in the Go code (mirror `bin/ai`'s COSTS dict).
- **Option B**: parse tokens.jsonl and attribute by timestamp proximity to project
  steps. More accurate but fragile. Skip unless A is insufficient.

## API endpoints (internal — consumed by HTMX hx-get)

```
GET  /                      → dashboard page
GET  /p/<slug>              → project detail page
GET  /queue                 → queue page
POST /queue                 → write new idea file, redirect to /
GET  /spend                 → spend page
GET  /partials/projects     → just the dashboard table tbody (for hx-target)
GET  /partials/health       → provider health dots
GET  /file/<slug>/<...>     → raw file under projects/<slug>/, served as text/plain
                              with a path traversal guard
```

No DELETE, no PATCH. Anything write-shaped that isn't "add idea to queue" stays out
of v1.

## Health checks

- **Ollama**: `GET http://192.168.0.5:30068/api/tags` with 2s timeout.
- **Z.AI**: `POST https://api.z.ai/api/anthropic/v1/messages` with `max_tokens=1` and
  the literal prompt `ping` — wasteful but only happens when the user opens the page.
  Cache the result for 60s in memory.
- **LM Studio**: `GET http://localhost:1234/v1/models` with 1s timeout.

Each check returns ok / fail / unknown. Render as a coloured dot in the header.

## Run instructions

```bash
# build
go build -o ai-workflow-dashboard ./cmd/dashboard

# run, pointing at the workflow root
./ai-workflow-dashboard --root /Users/marc/Documents/Claude/Projects/AI\ workflow --addr :7777

# open
open http://localhost:7777
```

The orchestrator continues to run from launchd; the dashboard is purely a viewer.

## Constraints

- **Total Go source ≤ 600 lines** including templates (inline `_ "embed"`).
  Comments don't count.
- **Single binary**, no runtime config files. Flags only: `--root`, `--addr`.
- **No external HTTP framework.** stdlib `net/http` and `html/template`.
- **One allowed Go dependency**: `github.com/yuin/goldmark` for markdown rendering.
  Plus pure-stdlib transitive only (no cgo, no `database/sql` drivers).
- **HTMX from CDN** is fine. Pico.css from CDN is fine. Nothing self-hosted in JS/CSS.
- Path traversal guard on every filesystem access — refuse anything containing `..`
  or absolute paths in URL params.
- Refuse to start if `--root` is not a directory containing both `projects/` and
  `queue/`.

## Acceptance

- `go vet ./...` clean.
- `gofmt -l .` returns empty.
- Open `http://localhost:7777` after running the binary against this very workflow
  directory: the dashboard table lists `silly-web-game` (step=done) and `url-shortener`
  (step=plan, last_error visible).
- Clicking `silly-web-game` opens the detail page with plan task list, every task
  ticked, and the verification report rendered.
- Adding a new idea via `/queue` creates the file on disk and shows up in the next
  poll on `/`.
- Docker build succeeds: `docker build -t ai-workflow-dashboard .`.
- Killing the orchestrator mid-run and reopening the dashboard shows the project
  with `last_error` populated; the dashboard does not crash on missing `plan.json`
  or `report.md`.

## Out of scope (v1)

- Triggering orchestrator runs from the UI. Use launchd or the CLI for that.
- Editing prefs.md from the UI.
- Multi-user, auth, accounts.
- Charts and graphs — tables only.
- Mobile layout. Desktop browser only.
