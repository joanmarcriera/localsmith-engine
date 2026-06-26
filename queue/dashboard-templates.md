# Project — dashboard-templates

Generate Go `html/template` files for the **AI workflow dashboard**, reskinned in the
paper/terminal aesthetic from `claude.ai/design`. These templates **must drop in** to
the existing `cmd/dashboard/main.go` at `projects/dashboard/` without changing a line
of Go code. Same data contract, new look.

The output is **template files only** — no Go code, no Dockerfile (already exists).

## Constraints

- **Output exactly these 7 files** (and only these) under `templates/`:
  - `layout.html` — `{{define "layout"}}...{{end}}` with embedded `<style>`. Defines
    blocks `title` and `content`. Includes HTMX (1.9.12) and Google Fonts (JetBrains
    Mono 400/500/700, Caveat 500/700, Patrick Hand 400). NO Pico.css — we own the CSS.
  - `dashboard.html` — V1 Step-Segment Table (see reference below).
  - `project.html` — D2 Stacked Collapsibles (see reference below).
  - `queue.html` — list of queue files + "+ New idea" form (collapsed behind a button).
  - `spend.html` — "Today: $X.XX" big number + two tables (by day, by provider).
  - `partials/projects_partial.html` — just the `<tbody>` for the dashboard table.
  - `partials/health_partial.html` — three provider dots inline.
- **No build step, no JS framework.** HTMX from CDN is the only JavaScript. CSS lives
  entirely in `layout.html`'s `<style>` block.
- **No images, no SVG assets.** All visuals via Unicode + CSS.
- All files together must total **under 800 lines**.

## Visual tokens (lock these — do not invent new colours)

```css
--paper:   #f5f1e6;   /* canvas */
--paper2:  #ece6d4;   /* zebra rows, panel backs */
--ink:     #1a1a1a;   /* body text */
--ink2:    #4a4a4a;   /* secondary text */
--ink3:    #8a8478;   /* tertiary text + dotted borders */
--pen:     #1e4fa3;   /* designer annotation ink (blue) */
--pen-r:   #b03a2a;   /* annotation accent (red) */
--ok:      #4a7c4e;   /* status green (done) */
--err:     #a14545;   /* status red (error) */
--info:    #3b6aa5;   /* status blue (plan/implement/verify) */
--grey:    #5a5a5a;   /* status grey (scaffold) */

font-family: 'JetBrains Mono', ui-monospace, monospace;    /* body */
font-family: 'Caveat', 'Patrick Hand', cursive;            /* designer annotations only */
```

Paper grain background on `<body>`:

```css
body::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; opacity: 0.5; z-index: 0;
  background-image:
    radial-gradient(rgba(0,0,0,0.03) 1px, transparent 1px),
    radial-gradient(rgba(0,0,0,0.02) 1px, transparent 1px);
  background-size: 6px 6px, 11px 11px;
  background-position: 0 0, 3px 3px;
}
```

## Annotations toggle

The chat decision: ship the annotations as a `?notes=1` URL toggle, **off by default**.

- `main.go` (already done) sets `.ShowNotes` to `true` when `?notes=1` is in the URL.
- Templates render `<aside class="note">…</aside>` blocks ONLY when `{{if .ShowNotes}}`.
- Notes are absolutely positioned `<aside>` elements with `font-family: Caveat`,
  `color: var(--pen)` (or `--pen-r`), `font-size: 18-22px`. Rotation `transform:
  rotate(-1deg)` to feel hand-drawn.
- Each annotated page has a small fixed toggle in the corner:
  `<a href="?notes={{if .ShowNotes}}0{{else}}1{{end}}">{{if .ShowNotes}}hide notes{{else}}show notes{{end}}</a>`.

Annotations to include (text taken verbatim from the wireframe — do not paraphrase):

| Page | Note | Colour |
|---|---|---|
| dashboard | "V1 · STEP-SEGMENT TABLE — closest to `cat state.json`, just nicer" | pen |
| dashboard | "4 boxes = the 4 work steps, 5th state (done) is implicit when all filled. Error → red." | pen |
| dashboard | "HTMX swaps just the &lt;tbody&gt;; header + nav are static." | pen |
| dashboard | "QUESTION: do we want a sticky 'errored' section at top, or trust sort-by-updated?" | pen-r |
| project | "D2 · STACKED PANELS (the spec literal) — 4 collapsibles, scrollable" | pen |
| project | "default open: state + plan. files + report are heavy so they start collapsed." | pen |
| project | "PRO: everything on one page; ctrl-F works. CON: long page; scroll cost is real." | pen-r |

## Data contract — DO NOT BREAK

These struct fields and template funcs are provided by `main.go`. Templates must use
them exactly:

### Per-page data

| Page | Data shape (what `.` is) |
|---|---|
| `dashboard.html` | `{Health: HealthMap, Projects: []ProjectRow, TodaySpend: float64, QueueDepth: int, ActiveCounts: map[string]int, ShowNotes: bool}` |
| `project.html` | `{Project: ProjectDetail, ShowNotes: bool}` |
| `queue.html` | `{Items: []QueueItem, ShowNotes: bool}` |
| `spend.html` | `{Today: float64, ByDay: []DayRow, ByProvider: []ProviderRow, ShowNotes: bool}` |
| `partials/projects_partial.html` | `[]ProjectRow` (just the slice — `.` IS the slice) |
| `partials/health_partial.html` | `HealthMap` |

### `ProjectRow` fields

```
Slug, Step (one of scaffold/plan/implement/verify/done/error), StepColor (grey/blue/green/red),
Progress (int 0..4), Total (always 4), Age (string like "2h"), UpdatedAt (time.Time),
Spend (float64 USD), TokensIn, TokensOut (int), LastError (string, may be empty),
Completed ([]string of step names)
```

### Template funcs available in funcMap

`relTime`, `truncate`, `sprintf`, `hasPrefix`, `hasSuffix`, `trimSuffix`, `add`, `pct`.

## V1 dashboard reference markup (paraphrase into Go template, do not literally copy)

Header strip with monospace URL, then nav tabs, then the table:

```html
<div class="page-strip"><span class="dot"></span><span class="dot"></span>
  <code>http://localhost:7777/</code> <span class="title">dashboard</span></div>

<header class="hdr">
  <div class="health">
    <span class="dot {{.Health.ollama}}"></span> ollama
    <span class="dot {{.Health.zai}}"></span> z.ai
    <span class="dot {{.Health.lmstudio}}"></span> lm-studio
  </div>
  <div class="counts">{{.QueueDepth}} queued · {{index .ActiveCounts "implement"}} implementing · …</div>
  <div class="today">today ${{sprintf "%.4f" .TodaySpend}}</div>
</header>

<nav class="tabs">
  <a class="active" href="/">[ dashboard ]</a>
  <a href="/queue">queue</a>
  <a href="/spend">spend</a>
</nav>

<table class="grid">
  <thead><tr>
    <th>slug</th><th>step</th><th>progress</th><th>age</th>
    <th>updated</th><th>spend</th><th>tokens (in/out)</th><th>last_error</th>
  </tr></thead>
  <tbody hx-get="/partials/projects" hx-trigger="every 5s" hx-swap="innerHTML">
    {{template "projects_partial" .Projects}}
  </tbody>
</table>

<footer class="summary">{{len .Projects}} projects · poll: every 5s</footer>
```

`projects_partial.html` renders one `<tr>` per project. The "progress" cell is **4
small filled/empty boxes**:

```html
<span class="bars">
  {{range $i := iter 4}}
    <span class="bar
      {{if lt $i $.Progress}}filled{{end}}
      {{if eq $.Step "error"}}err{{end}}"></span>
  {{end}}
</span>
<span class="frac">{{.Progress}}/{{.Total}}</span>
```

If `iter` is not in funcMap, use `range` over a slice you build from `.Completed`
(check `index of $.Step in pipeline-order` — simpler is fine as long as it renders 4
boxes).

Box CSS (terminal cell aesthetic):

```css
.bars { display: inline-flex; gap: 2px; }
.bar  { width: 10px; height: 10px; border: 1px solid var(--ink); background: var(--paper); }
.bar.filled { background: var(--ink); }
.bar.err    { background: var(--err); border-color: var(--err); }
```

Step badge (used in the `step` column):

```html
<span class="badge {{.StepColor}}">{{.Step}}</span>
```

```css
.badge { font-size: 10px; padding: 1px 6px; border: 1px solid; text-transform: lowercase; }
.badge.grey  { color: var(--grey); border-color: var(--grey); }
.badge.blue  { color: var(--info); border-color: var(--info); }
.badge.green { color: var(--ok);   border-color: var(--ok); background: rgba(74,124,78,0.08); }
.badge.red   { color: var(--err);  border-color: var(--err); background: rgba(161,69,69,0.08); }
```

Density: row height ~24px, font 11px monospace, dotted bottom-borders (`border-bottom:
1px dotted var(--ink3)`).

## D2 project detail reference markup

Two-column grid (1fr 240px). Left column: 4 stacked panels — state (open), plan (open),
files (collapsed), report (collapsed). Right column: token usage table.

```html
<section class="panel open">
  <header class="panelhead">
    <span class="idx">1</span> <span class="ptitle">state</span>
    <span class="phint">state.json · last touched {{relTime .Project.State.UpdatedAt}}</span>
  </header>
  <div class="pbody"><pre>{{.Project.StateJSON}}</pre></div>
</section>

<section class="panel"><header class="panelhead">…</header></section>  <!-- collapsed -->
```

Use `<details>` for the collapsibles so it works without JS:

```html
<details {{if .DefaultOpen}}open{{end}}>
  <summary>…</summary>
  <div class="pbody">…</div>
</details>
```

Plan tasks list:

```html
<ul class="tasks">
  {{range .Project.Plan.Tasks}}
    <li>
      <span class="check {{if .Done}}done{{end}}">{{if .Done}}✓{{else}}·{{end}}</span>
      <code>{{.Path}}</code>
      <span class="intent">{{.Intent}}</span>
      {{range .Deps}}<span class="pill">{{.}}</span>{{end}}
    </li>
  {{end}}
</ul>
```

## Acceptance

- `go build ./cmd/dashboard` succeeds against the unchanged `main.go`.
- `gofmt -l templates/` returns empty (templates aren't Go, but the build linking them
  must succeed).
- Loading `http://localhost:7777/` shows the paper background, monospace table, four
  step-segment bars per row.
- `http://localhost:7777/?notes=1` shows the handwritten annotations in Caveat font,
  positioned in the margins.
- Loading `http://localhost:7777/?notes=0` hides them. The toggle link is visible.
- `http://localhost:7777/p/silly-web-game` shows the D2 stacked-panel layout. State and
  Plan panels open by default; Files and Report panels are `<details>` collapsed.
- No console errors.

## Out of scope

- V2, V3, V4 dashboard variants. V1 only — explicit per the chat decision.
- D1 and D3 detail variants. D2 only.
- Charts and graphs. Tables only.
- Mobile layout. Desktop browser only.
- The activity-feed view (V4) — defer; needs more dogfooding of the new
  `logs/state-events.jsonl` first.
