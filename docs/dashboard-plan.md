# Dashboard convergence plan

Three different routes were tried with the same prompt:

| Route | Output | Verdict |
|---|---|---|
| **A — Local orchestrator** | Scaffolded under wrong slug, never reached `plan` | **Failed** (orchestrator bug) |
| **B — v0.dev** | 614-line `main.go` + 7 templates + Dockerfile + Next.js noise | Backend usable; UI generic |
| **C — claude.ai/design** | Wireframes.html exploring 4 dashboard × 3 detail variants, paper/TUI aesthetic, rich annotations | Best design thinking; no production code |

Goal: keep the design intent from C, the working Go backend from B, hand as much as possible
back to the local orchestrator, and fix the bugs that caused A to fail.

---

## 1. Why Option A failed — root cause

```
[scaffold] dispatching to ollama with --json ...
[materialize] ai-workflow-dashboard: created 2 dirs, 9 files under .../projects
[scaffold] done: .../projects/ai-workflow-dashboard/
[orchestrate] no tree.json in .../projects/dashboard — scaffold may have written under a different slug
```

Two sources of truth for the slug:

- **scaffold.sh** asks Ollama for a slug; Ollama chose `ai-workflow-dashboard` from the idea body's title
- **orchestrate.sh** (after the fix from last session) expects `slug = basename(idea, ".md") = dashboard`

Materialise wrote to `projects/ai-workflow-dashboard/`. Orchestrator looked in `projects/dashboard/`,
didn't find `tree.json`, gave up cleanly.

**Fix**: the idea filename is the slug. Period. `scaffold.sh` should:
1. Compute slug from filename.
2. Pass it into the prompt as a fixed value (`"project": "<slug>"` must be exactly this).
3. After parsing the LLM response, **overwrite** the `project` field with the canonical
   filename slug — defence in depth against models that still rename it.

Five-line change in `scaffold.sh`. High leverage — same bug would burn every future rerun.

---

## 2. Lessons worth pulling back into the orchestrator

### From v0.dev (Option B)

- **The Go backend mostly works.** 614 lines, slightly over our 600-line budget,
  but `go vet` clean and all required structs/handlers present. Useful as a paste-in
  starting point.
- **Provider cost table got wrong numbers** — v0 used GPT-4 pricing for `zai`. The
  cost table lives in `bin/ai` and should be the single source. Future improvement:
  emit a `costs.json` from `bin/ai` and have generated code read it instead of hardcoding.
- **shadcn/ui noise**: v0 always scaffolds Next.js. ~80 React files we threw away.
  Tells us: when the agent is React-by-default, even an explicit "use Go" spec gets
  React anyway. **Our local orchestrator's discipline (only generate files in tree.json)
  is genuinely valuable.** Don't copy v0's freewheeling behaviour.

### From claude.ai/design (Option C)

- **Multi-variant exploration up front saved iteration time.** The chat shows the
  designer asked targeted questions (info_density, vibe, dashboard_layouts, detail_layouts,
  header content, progress_viz, colour_usage, queue_form, spend_emphasis, tweaks,
  annotations) before drawing anything. Marc's answers locked the direction in
  ~10 questions. **Our plan.sh produces one plan; for UI work, generating 3-4 variants
  with a small "pick one" loop would be more honest about uncertainty.**
- **Rationale lives in the design, not the code.** Wireframes.html carries dense
  margin-note annotations explaining trade-offs. Our generated code has zero comments
  explaining *why* a choice was made. **Update `prompts/impl.txt` to require a short
  rationale comment at the top of each non-trivial file.**
- **Surfaced data-model gaps the spec missed.** The designer flagged:
  - V2/V3 (Gantt-flavoured views) need *per-step durations* — `state.py` only logs
    `updated_at`, not entry/exit per step.
  - V4 (activity feed) needs a *state-mutation event source* — currently nothing tails
    state changes.
- **Chose specific variants on Marc's behalf**: V1 (Step-Segment Table) closest to
  Marc's `cat state.json` mental model; D2 (Stacked Collapsibles) matches our original
  spec. We adopt those choices below.

---

## 3. Orchestrator improvements — ranked by leverage

| # | Change | Where | Effort | Why |
|---|---|---|---|---|
| 1 | Force `tree.json["project"] == basename(idea, ".md")` | `scaffold.sh` + `materialize.py` | XS | Same bug breaks every rerun otherwise |
| 2 | Log step `entry` and `exit` timestamps in `state.json` | `bin/state.py` (mark/init), `orchestrate.sh` | S | Unlocks any duration-aware view (V2, V3, future) |
| 3 | Add rationale-comment requirement to `prompts/impl.txt` | one prompt edit | XS | Future Marc / future Claude can read intent |
| 4 | `plan.sh --variants N` for UI-heavy projects | `plan.sh`, `prompts/plan.txt` | M | Matches design-process best practice |
| 5 | State-mutation event log `logs/state-events.jsonl` | `bin/state.py save()` | S | Enables V4 activity feed cheaply; one append per save |
| 6 | Costs.json emitted by `bin/ai` for downstream consumers | `bin/ai` | XS | One source of truth, dashboard reads it |

We do 1, 2, 3, 5, 6 **before** implementing the dashboard — they each take <15 minutes
and the dashboard needs the data 2 and 5 produce. Skip 4 for now (variants are a Phase 6
discussion, not a blocker).

---

## 4. Dashboard implementation strategy — what the orchestrator handles vs not

The honest split, given v0 already produced compiling Go code and claude.ai/design
produced the visual language:

| Workstream | Handled by | Why |
|---|---|---|
| Bug fixes 1, 2, 3, 5, 6 above | **Manual** (me, this turn) | Five small edits, faster than a planner round |
| Port v0's `main.go` + Dockerfile + go.mod into `projects/dashboard/` | **Manual** (single copy) | Already exists; regenerating wastes tokens |
| Adjust v0's cost table to match `bin/ai`'s table | **Manual** | One-line correction |
| Reskin templates with claude.ai/design visual language (paper grain, JetBrains Mono, Caveat for annotations, B&W + status colours, terminal/TUI density) | **Orchestrator** | Real generation work; LLM is good at this |
| Implement V1 dashboard variant + D2 detail variant inside the templates | **Orchestrator** | Per design decisions in chat transcript |
| Verify with static checks + Ollama review | **Orchestrator** (`verify.sh`) | Already works |

So roughly **20% manual fixes / paste**, **80% orchestrator** — with the orchestrator
doing the work it's actually good at (text-heavy template generation against a tight spec)
rather than re-inventing what v0 already produced.

---

## 5. Concrete steps to execute

### Step A — Fix the orchestrator (manual, ~15 min)

1. `scaffold.sh` — derive slug from filename, pass to LLM as fixed, overwrite after parse.
2. `materialize.py` — refuse to write if `doc["project"] != expected_slug`.
3. `bin/state.py` — add `entered_at` per step, append a record to `logs/state-events.jsonl`
   on every save.
4. `prompts/impl.txt` — add "Each file must open with a comment block stating: WHAT this
   file does, WHY this design, KEY DECISIONS."
5. `bin/ai` — write `costs.json` next to logs on every call (small, cached).

### Step B — Seed the dashboard project from v0 (manual, ~5 min)

1. Extract `cmd/dashboard/main.go`, `cmd/dashboard/templates/*.html`, `Dockerfile`,
   `go.mod`, `go.sum` from the uploaded zip into `projects/dashboard/`.
2. Patch the cost table in `main.go` to match `bin/ai`'s `COSTS` dict.
3. Verify it compiles: `cd projects/dashboard && go vet ./...`.
4. Verify it runs: `go run ./cmd/dashboard --root .. --addr :7777` — open and confirm.

This is the "make sure the engine starts" gate. If it doesn't run after Step B,
no point reskinning.

### Step C — Generate the reskinned templates via the orchestrator (LLM work, ~10 min)

Write a focused idea file `queue/dashboard-templates.md` that:
- Points at the existing `projects/dashboard/cmd/dashboard/main.go` so the planner sees
  the route handlers and template names that must exist.
- Embeds the relevant chunks of `Wireframes.html` (the V1 and D2 variants only) as
  reference markup.
- Specifies the visual tokens: paper-grain background, JetBrains Mono body,
  Caveat for designer annotations, B&W + status colours `#4a7c4e` green / `#a14545` red
  / `#3b6aa5` blue / `#5a5a5a` grey, terminal/TUI density.
- Lists exactly the template files to produce (override, not generate from scratch):
  `layout.html`, `dashboard.html`, `project.html`, `queue.html`, `spend.html`,
  `partials/projects_partial.html`, `partials/health_partial.html`.

Then `bin/orchestrate.sh queue/dashboard-templates.md`. The orchestrator scaffolds,
plans (Claude), implements (Z.AI), verifies (Ollama). Templates land under
`projects/dashboard-templates/templates/` — we copy them over `projects/dashboard/cmd/dashboard/templates/`.

### Step D — Final verify and ship (~5 min)

1. `cd projects/dashboard && go build -o ai-workflow-dashboard ./cmd/dashboard`
2. `./ai-workflow-dashboard --root ../../ --addr :7777` and check both views render.
3. `bin/verify.sh projects/dashboard` for the static-check + review pass.
4. `docker build -t ai-workflow-dashboard projects/dashboard/`.

---

## 6. Out of scope for this stage

- **D1 and D3 detail variants, V2/V3/V4 dashboard variants.** Designer recommended V1+D2;
  stick with that for v1. The other variants stay in `Wireframes.html` for future
  reference.
- **`--variants N` flag for plan.sh.** Useful idea, not a blocker; revisit if we
  build more UI-heavy projects.
- **A "design review" step in the pipeline.** Same — useful, not now.
- **Triggering orchestrator runs from the dashboard.** Original spec ruled this out for
  v1; honour that.

---

## 7. Open questions to confirm before Step C

1. **Visual aesthetic — keep claude.ai/design's paper/sketchy look, or strip back to a
   clean terminal monochrome?** The design uses Caveat (handwritten) for annotations,
   JetBrains Mono for content, and a paper-grain background. Strong opinions if any.
2. **Annotations toggle in production?** The wireframes have a "show notes" tweak. We
   could ship that as a `?notes=1` query param. Useful or noise?
3. **V1 alone, or include V4's activity feed as a side panel?** V4 needs the new
   state-events log (improvement #5 above). If yes, dashboard gets a 30-40% wider
   layout.

Answer these three and I'll start executing Steps A → D. Otherwise I'll proceed with
defaults: keep the paper aesthetic (it's distinctive, not generic), annotations OFF by
default with `?notes=1` toggle, V1 only — V4 feed deferred to a follow-up since the
data plumbing (#5) needs a few orchestrator ticks of dogfooding first.
