# Claude Max Power-User Playbook

**For:** Marc Riera — AI-datacenter work (Argentum / GB300 / Vera Rubin), 3-host TrueNAS/ZFS home lab, ActivaColours, Knaus campervan, CV/job-search, home-office automation.
**Goal:** turn the Max 20x upgrade into a machine for clearing the backlog of half-finished projects scattered across your computer.
**Date:** 2026-06-24. Figures verified against `support.claude.com` / `code.claude.com` (see Sources). Limits change often — re-check `Settings > Usage`.

---

## TL;DR — top 5 things to do first

1. **Authenticate Claude Code to your Max plan** (not an API key). One subscription now covers Claude web/desktop **and** Claude Code in the terminal/IDE. Run `claude` → log in with your Max credentials; if an `ANTHROPIC_API_KEY` is set in your shell it will silently bill API rates instead — unset it. (§1)
2. **Run a project inventory once** with the paste-ready `find` one-liner in §8, drop the result into Cowork, and let Claude triage every project into Now/Next/Later/Archive.
3. **Stop working serially.** Adopt the orchestrator → parallel tasks → subagents mental model (§2) and keep 3–5 independent work-streams moving at once (§3).
4. **Build two skills this week:** a `project-triage` skill and lean on your existing `truenas-health` one. Skills make recurring jobs one-word repeatable (§5).
5. **Wire up the MCP connectors that remove your copy-paste glue:** filesystem, git, and the `desktop-commander` MCP you already have installed (§6).

---

## 1. What Max actually unlocks

You moved from **Pro (~£20/mo)** to **Max**. Max has two tiers; you're on **20x ($200/mo)**.

| | Pro | Max 5x ($100) | **Max 20x ($200)** |
|---|---|---|---|
| Usage per session vs Pro | 1x | 5x | **20x** |
| Weekly limits | Yes | Yes (two caps) | **Yes (two caps)** |
| Claude Code (terminal/IDE) | Included | Included | **Included** |
| Cowork (this app) | Included | Included | **Included** |
| Claude Agent SDK on plan | Included | Included | **Included** |
| Priority access to new models/features | — | Yes | **Yes** |

What the numbers mean in practice (Anthropic does **not** publish exact token counts; these are the mechanics):

- **Two clocks run at once.** A rolling **5-hour session** window *and* **weekly** caps. Max has *two* weekly limits: one across **all models** and a separate, larger one for **Sonnet only**. Reset day/time is fixed to your account — see `Settings > Usage`.
- **Everything shares one pool.** Claude web, desktop, **Cowork, and Claude Code all draw from the same limits.** A heavy Claude Code run eats into your chat budget and vice-versa.
- **20x is roughly the difference** between "a few dozen prompts per window" (Pro) and enough headroom to keep multiple Claude Code sessions and Cowork tasks running in parallel for hours. Recent changes (May 2026) doubled the 5-hour caps and removed peak-hour throttling for Pro/Max; a temporary +50% weekly bump was running through mid-July 2026. Treat all of that as fluid.
- **Model strategy:** route cheap/parallel grunt work to **Sonnet** (it has its own bigger weekly bucket) and save **Opus** for planning, hard reasoning, and final review. In Claude Code: `/model sonnet` or `/model opus`.
- **Overflow valve:** if you hit a wall mid-sprint you can opt into **pay-as-you-go API credits** from a Console account — but that bills standard API rates, separate from your plan. Decline the prompt to stay within Max. Monitor with `/status` in Claude Code.

**Bottom line:** the upgrade is not "smarter Claude," it's *parallel, sustained* Claude. The whole rest of this playbook is about spending that capacity instead of letting it reset unused every week.

---

## 2. Mental model: orchestrator → parallel tasks → subagents

Three layers. Match the layer to the job.

```
YOU
 └─ ORCHESTRATOR            (one Claude session that holds the plan & delegates)
     ├─ TASK SESSION A      (independent work-stream, own context, runs in background)
     ├─ TASK SESSION B
     └─ TASK SESSION C
          └─ SUBAGENT       (short-lived worker inside a session; returns a summary)
          └─ SUBAGENT (reviewer)
```

- **Orchestrator** — your main thread. It plans, splits work, and collects results. Keep it light: it should *delegate*, not do everything itself, or its context fills with logs you'll never re-read.
- **Task session** — a whole independent stream of work. In Cowork these are parallel **task sessions**; in Claude Code they're **background sessions** (`claude agents` / agent view). Use one per project or per feature branch.
- **Subagent** — a delegated worker *inside* a session that does a side task in its own context and hands back only a summary (search, audit, review). It keeps the parent conversation clean.

### When to parallelise vs serialize

**Parallelise when** tasks are *independent* — different projects, different repos, different files, or read-only research across many topics. No shared state = no collisions.

**Serialize when** tasks share state or have a dependency chain: design → implement → test → document on the *same* file must run in order. Trying to parallelise these produces merge conflicts and half-applied edits.

**The isolation rule:** if two parallel workers might touch the same files, give each its own **git worktree** (separate checkout, shared history). Cowork/agent view does this automatically for dispatched sessions; in Claude Code use `/batch` or worktrees explicitly. If you can't isolate, partition the work so each worker owns a distinct set of files.

---

## 3. Parallelisation playbook

Concrete patterns. All prompts are paste-ready — adjust paths.

### Pattern A — Fan out across independent projects (Cowork)
Best for clearing your scattered backlog. One orchestrator dispatches one background task per project.

> Paste into Cowork:
> ```
> I'm going to clear several stalled projects in parallel. For each project below,
> spawn a separate background task session. Each session should: read the project's
> README and recent git log, identify the single highest-value next step, do it,
> and report back a 5-line summary (what you changed, what's left, any blocker).
> Don't touch files outside the project's own folder.
>
> Projects:
> 1. ~/projects/activacolours       — finish the trade one-pager PDF
> 2. ~/projects/knaus-campervan     — consolidate the wiring/electrical notes into one doc
> 3. ~/projects/cv-kit              — refresh master CV with the last 3 months of evidence
> 4. ~/labs/truenas-runbooks        — turn my shell history into a documented runbook
> ```

### Pattern B — Parallel research, N topics at once
Read-only, zero collision risk — ideal for burning spare Sonnet capacity.

> ```
> Research these 4 topics in parallel, one subagent each. Each returns: a 150-word
> summary, the 3 best sources with URLs, and one "watch out" caveat. Use Sonnet.
> 1. GB300 NVL72 vs Vera Rubin rack power/cooling deltas
> 2. ZFS special vdev sizing rules of thumb for metadata-heavy pools
> 3. Photocatalytic TiO2 paint EU labelling/marketing-claims rules
> 4. Current best practice for headless Claude Code in CI
> Then synthesise into one comparison note.
> ```

### Pattern C — `/batch` a large mechanical change (Claude Code)
For repo-wide edits: `/batch` splits one change into 5–30 worktree-isolated subagents, each opening a PR.

> In Claude Code:
> ```
> /batch Add a standardised header comment block (purpose, usage, author, date) to
> every .sh and .py script under bin/, following the style already in bin/search.
> One PR per directory.
> ```

### Pattern D — Plan-then-parallelise (two phases)
Use **plan mode** to decompose *first* (so the split is clean), then fan out.

> Phase 1 (plan mode — Claude Code `Shift+Tab` to plan, or "make a plan, don't execute"):
> ```
> Plan how to migrate my home-office automations from cron + ad-hoc scripts to a
> single documented systemd-timer layout. Output a task list where independent
> tasks are clearly marked so I can run them in parallel. Don't write code yet.
> ```
> Phase 2: "Execute the independent tasks in parallel background sessions; serialize the dependent ones."

### Throughput rules of thumb
- **3–5 parallel streams** is the sweet spot. Beyond that you spend more time reviewing than you save, and token burn multiplies (running N agents ≈ N× usage).
- **One concern per session.** Mixing projects in one thread pollutes context.
- **Summaries, not transcripts.** Always ask workers to return a short structured summary; that's what keeps the orchestrator usable.
- **Checkpoint with git.** Commit before any big parallel run so you can `git reset` a bad batch cleanly.

---

## 4. Subagents

A **subagent** is a delegated worker spawned *inside* a session. It runs in its **own context window**, does one job, and returns a **summary** — so search results, logs, or 20 file reads never flood your main thread.

**Use one when:**
- A side task would dump noise into your main conversation (codebase search, log triage, reading 30 files to answer one question).
- You want a *fresh, unbiased* pass — e.g. a reviewer that hasn't seen the implementation reasoning.
- The work is independent enough to run while you continue elsewhere.

**Don't use one when** the task is trivial (just do it inline) or needs the full conversation history — in that case use a **forked subagent** (inherits your context) instead of a fresh one.

### Example: research/explore subagent
> ```
> Spawn an Explore subagent: find everywhere in ~/labs/truenas-runbooks that
> references the optiplex7040 replication target, list each file + line, and tell me
> if any still point at the old IP. Return just the findings, not file dumps.
> ```

### Example: the verification / reviewer pattern (do this on anything important)
Spawn a *second, independent* agent to check the first one's work. This catches hallucinated APIs and silent errors that a single pass misses.

> After any non-trivial change:
> ```
> Spawn a reviewer subagent with fresh context. Give it ONLY the diff and the
> original requirements (not my reasoning). It should check:
>  - correctness & edge cases
>  - any invented/incorrect library or API calls (verify each import exists)
>  - bash: shellcheck-style issues; python: would it actually run
>  - whether the change matches the stated requirement
> Return a PASS/FAIL per item with line references. Don't fix anything — just report.
> ```

> For high-stakes work (e.g. a ZFS disk-replacement runbook), make the reviewer a **separate agent** and have it *run* the verification, not just read it:
> ```
> Reviewer subagent: dry-run the commands in this runbook against a scratch pool in
> the sandbox, capture output, and confirm each step does what the doc claims.
> ```

This maps directly to your existing rule (py_compile can't catch hallucinated APIs) — the reviewer subagent *is* the catch.

---

## 5. Skills — your recurring jobs, made one-word repeatable

A **skill** is a folder with a `SKILL.md` (instructions + when-to-use description) plus optional scripts/templates. Claude auto-loads it when your request matches the description, or you invoke it explicitly. You already have a strong set: `truenas-health`, `truenas-disk-replacement`, `truenas-replication-audit`, `cv-tailor`, `interview-prep`, `activacolours-pdf`. That's exactly the right instinct — keep building them.

**Using existing ones:** just describe the job. "How are my servers?" triggers `truenas-health`; "tailor my CV for this JD" triggers `cv-tailor`. No special syntax needed.

### Worked example: build a `project-triage` skill

This is the skill that pays for the whole upgrade — it turns "what's rotting in my home folder?" into a one-word command.

**Step 1 — use the skill-creator.** It scaffolds, tests, and optimises the trigger description for you:
> ```
> Use skill-creator to build a new skill called "project-triage".
> Purpose: scan a directory tree of code/projects and produce a triage table.
> For each project dir it should report: name, path, primary language (bash/python/
> awk/other), last-commit date (or "no git"), whether tests exist, whether a README
> exists, rough LOC, and a one-line "next action" + Now/Next/Later/Archive bucket.
> Output a markdown table sorted by staleness. Standards-compliant, documented code.
> Trigger phrases: "triage my projects", "what's stalled", "project inventory".
> ```

**Step 2 — what the SKILL.md skeleton looks like** (so you know what's being generated):
```markdown
---
name: project-triage
description: Inventory and triage project directories under a given path —
  language, git freshness, tests/README presence, and a Now/Next/Later/Archive
  bucket per project. Use for "triage my projects", "what's stalled",
  "project inventory".
---
# Project Triage
1. Run scripts/scan.sh <root> to collect raw facts (git log, file counts).
2. Classify each project into Now/Next/Later/Archive using the rubric below.
3. Emit a sorted markdown table + a 3-line executive summary.
## Rubric
- Now: clear next step, recent activity, high value.
- Archive: no commits >12mo AND no README AND no clear purpose.
...
```
With a `scripts/scan.sh` doing the heavy lifting in bash (your language) — Claude calls it, then reasons over the output. Documented, standards-based, reusable.

**Step 3 — iterate.** Run it, then "the triage missed sub-projects nested two levels deep — update the skill to recurse one more level." skill-creator edits and re-tests.

**Other high-ROI skills for you:** `argentum-status` (assemble a deployment status note from logs/notes), `home-office-backup-check`, `campervan-spec-sheet`. Same pattern every time.

> Note: in this Cowork session you can *use* skills but not *save* new ones to disk — create/edit skills from **Settings > Capabilities** or in Claude Code with skill-creator.

---

## 6. MCP — give Claude direct hands on your tools

**MCP (Model Context Protocol)** servers expose external tools/data to Claude as callable tools — the difference between Claude *telling you* a command and Claude *running it*. Skills tell Claude *how*; MCP gives it the *means*.

### Recommended for your work (highest leverage first)
- **`desktop-commander`** — you already have it installed. Persistent shells/REPLs, long-running processes, filesystem access beyond the workspace, ripgrep at scale, SSH. This is your bridge to the **3 ZFS hosts** and to any project folder. Use it for the TrueNAS fleet and for editing files outside the Cowork folder.
- **Filesystem MCP** — scoped read/write to specific project roots. Cleaner than broad shell access when you just want Claude editing files in `~/projects`.
- **Git MCP** — branch/commit/diff/log as structured tools; pairs with worktrees for parallel work.
- **Data connectors** (you have BigQuery/Hex/Definite via plugins) — point Claude at deployment metrics or telemetry for Argentum without exporting CSVs by hand.
- **Postiz** (installed) — schedule ActivaColours social posts across channels.

### How to add one
- **Cowork/Claude desktop:** Settings → Connectors → add from the registry, or ask me "search the connector registry for X" and I'll suggest installable ones.
- **Claude Code (HTTP server):**
  ```bash
  # syntax: claude mcp add --transport http <label> <url>
  claude mcp add --transport http git http://localhost:7000
  claude mcp list          # verify
  ```
- **Local stdio server (e.g. your Ollama LAN box wrapped as a tool):** add via `claude mcp add <label> -- <command> [args]`.

### Building your own MCP (sketch)
When no connector exists — say you want Claude to query your **TrueNAS API** or your **AI-workflow orchestrator** directly — wrap it as an MCP server. Use the **`mcp-builder`** skill; the fast path is Python **FastMCP**:

```python
# truenas_mcp.py — minimal FastMCP server exposing pool health as a tool
from fastmcp import FastMCP
import subprocess, json

mcp = FastMCP("truenas")

@mcp.tool()
def pool_status(host: str) -> str:
    """Return `zpool status -x` for a host in the fleet (192.168.0.5/.3/.234)."""
    out = subprocess.run(
        ["ssh", host, "zpool", "status", "-x"],
        capture_output=True, text=True, timeout=30,
    )
    return out.stdout or out.stderr

if __name__ == "__main__":
    mcp.run()   # stdio transport; register with: claude mcp add truenas -- python truenas_mcp.py
```
Good-tool principles from `mcp-builder`: one clear job per tool, descriptive docstrings (Claude reads them to decide when to call), typed args, and human-readable output. Then your `truenas-health` skill can *call* this MCP instead of shelling out each time.

---

## 7. Reusable prompt library

Keep these in a `~/prompts/` file (or as snippets). Copy-paste, fill the brackets.

**Inventory & triage everything**
```
Inventory all project directories under ~. For each: name, path, primary language,
last git commit date (or "no git"), README? tests? and a one-line next action.
Bucket each into Now / Next / Later / Archive. Output one markdown table sorted by
staleness, then a 3-line summary of where my time is best spent this week.
```

**Parallel research, N topics**
```
Research these [N] topics in parallel (one subagent each, use Sonnet). Each returns
a 150-word summary, 3 sourced URLs, one caveat. Then synthesise into a single note.
Topics: [...]
```

**Review my repo with a subagent**
```
Spawn a fresh reviewer subagent for the repo at [path]. It should: summarise what
the project does, flag the top 5 risks/bugs, list dead code, check the README is
accurate, and verify every external import/API actually exists. PASS/FAIL list with
file:line refs. Report only — no edits.
```

**Finish a stalled project**
```
Project at [path] is stalled. Read README + last 10 commits, tell me the single
highest-value next step and why, then do it. Documented bash/python/awk, follow
existing conventions. End with: what changed, what's left, any blocker.
```

**Plan before executing**
```
Make a plan for [goal]. Output a task list; mark which tasks are independent
(parallelisable) vs dependent (must serialize). Don't write code yet — wait for
my go-ahead.
```

**Verify (run after anything important)**
```
Independent verification pass: given only the diff and the requirement, check
correctness, edge cases, hallucinated APIs, and requirement-match. PASS/FAIL each.
```

**Document as you go** (your standing preference)
```
Add a documented header (purpose/usage/author/date) and inline comments to every
script you touched. Bash/python/awk, follow the style in bin/search. Concise.
```

---

## 8. First-week action plan

A concrete ramp from "I just upgraded" to "the backlog is moving."

### Day 1 — Plumbing (30 min)
- Authenticate Claude Code to Max: `claude` → log in with Max creds. Confirm with `/status`. Unset any `ANTHROPIC_API_KEY` so you don't accidentally bill API rates.
- Confirm `desktop-commander` MCP is connected; add **git** + **filesystem** MCP if not already.
- Check `Settings > Usage` to learn your weekly reset day — plan big parallel runs just *after* a reset.

### Day 2 — Inventory (the keystone step)
Run this read-only scan, then feed the output to Claude for triage:
```bash
# Quick project inventory — prints dir, last-commit date, language hint, README/tests flags
find ~ -maxdepth 3 -type d \( -name .git -o -name node_modules -o -name .venv \) -prune -false \
  -o -maxdepth 3 -type d -print 2>/dev/null | while read -r d; do
  [ -d "$d/.git" ] || continue
  last=$(git -C "$d" log -1 --format=%cs 2>/dev/null || echo "no-commits")
  lang=$(ls "$d" 2>/dev/null | grep -qE '\.py$' && echo py || (ls "$d" | grep -qE '\.sh$' && echo sh || echo other))
  rd=$( [ -f "$d/README.md" ] && echo README || echo - )
  printf '%s\t%s\t%s\t%s\n' "$last" "$lang" "$rd" "$d"
done | sort
```
Then: *"Here's my project inventory. Triage into Now/Next/Later/Archive with a one-line next action each."* (Or build the `project-triage` skill from §5 so this is one word forever after.)

### Day 3 — Batch the quick wins
Pick the 4–5 "Now" projects that each need one small step. Run **Pattern A** (§3) — one background task per project, in parallel. Review summaries, commit the good ones.

### Day 4 — One deep project, properly
Take your highest-value project (likely Argentum status tooling or the AI-workflow orchestrator). **Plan mode first** (Pattern D), then execute serially with a **reviewer subagent** (§4) on every meaningful change.

### Day 5 — Systematise
- Build the `project-triage` skill (§5) and one domain skill (e.g. `argentum-status`).
- Stand up one custom MCP if a recurring job needs it (§6).
- Save the §7 prompt library to `~/prompts/`.

### Weeks 2–4 — Cadence
- **Monday:** run `project-triage`, pick the week's 3–5 streams.
- **Throughout:** keep 3–5 parallel streams live; reviewer subagent on anything that ships.
- **Friday:** archive what's done, capture any new recurring job as a skill.
- **Watch usage:** front-load heavy parallel runs early in your weekly window; let Sonnet absorb the bulk grunt work so you keep Opus headroom for planning/review.

### Success check (end of month)
Every project is in a bucket (none "unknown"); the "Now" list is shrinking; recurring chores are skills not ad-hoc prompts; and you're routinely running parallel streams instead of waiting on one.

---

## Sources
- [What is the Max plan? — support.claude.com](https://support.claude.com/en/articles/11049741-what-is-the-max-plan)
- [Use Claude Code with your Pro or Max plan — support.claude.com](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)
- [Use the Claude Agent SDK with your Claude plan — support.claude.com](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)
- [How do usage and length limits work? — support.claude.com](https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work)
- [Usage limit best practices — support.claude.com](https://support.claude.com/en/articles/9797557-usage-limit-best-practices)
- [Run agents in parallel — code.claude.com](https://code.claude.com/docs/en/agents)
- [Subagents — code.claude.com](https://code.claude.com/docs/en/sub-agents)
- [Worktrees — code.claude.com](https://code.claude.com/docs/en/worktrees)
- [Extend Claude with skills — code.claude.com](https://code.claude.com/docs/en/skills)
- [How to create custom skills — support.claude.com](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
- [Extending Claude with skills & MCP servers — claude.com/blog](https://claude.com/blog/extending-claude-capabilities-with-skills-mcp-servers)
