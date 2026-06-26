## Imported Claude Cowork Project Instructions

Project aiming for unattended work leveraging Claude, ChatGPT/Codex, local
Ollama, LM Studio, Perplexity, and Z.AI when needed.

## Current Handover

Read `CLAUDE_HANDOVER.md` first. It is the current single handover for Claude
Opus/Sonnet and supersedes the older local handoff notes.

Important local conventions:

- The workspace is `/Users/marc/Documents/Claude/Projects/AI workflow`.
- This workspace is not currently a Git repository.
- `bin/orchestrate.sh` is the main entry point and now loads `.env` before
  dispatching stages.
- `docs/verification-flags.md` is the authoritative flag reference for provider
  routing, LM Studio/Gemma, and strict verification.
- Do not treat a generated project as done unless `bin/verify.sh` passes with the
  verification flags required for that project.


<claude-mem-context>
# Memory Context

# [AI workflow] recent context, 2026-05-19 9:49pm GMT+1

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (21,848t read) | 273,672t work | 92% savings

### May 17, 2026
S37 Implementation plan generated for url-shortener project (POST /shorten + GET /:code redirect service) (May 17 at 4:39 PM)
S36 Translate "read a file line by line" to bash (May 17 at 4:39 PM)
S38 dashboard-templates: Generate 7 Go html/template files with paper/terminal aesthetic for AI workflow dashboard (May 17 at 10:14 PM)
### May 19, 2026
S44 Debug and fix "missing required field: paths" schema violation in bin/orchestrate.sh for zfs-website project, then get the full pipeline running (May 19 at 8:25 PM)
524 8:51p 🔴 zfs-website: `react-dnd` Ref Typing Fixed in ManualPoolBuilder — `ConnectDragSource` Not Assignable to `Ref`
525 " 🔴 zfs-website: Named vs Default Export Mismatch for `FailureSimulator`
526 " 🔴 zfs-website: `generator.ts` Referenced Non-Existent `cap.usableBytes` Property
527 " 🔴 zfs-website: Next.js Build Succeeded — Dockerfile Fails at Production Stage Missing `bun.lockb`
528 8:54p 🔴 zfs-website Docker Image Successfully Built — All Errors Resolved
529 " 🔵 zfs-website: Full Catalogue of AI Workflow Build Errors Requiring Manual Fixes
530 8:55p 🔵 AI Workflow `verify.sh` Could Catch TypeScript Errors but NOT npm Package Name 404s
531 8:56p 🟣 `verify.sh` Enhanced with npm Dependency Validation, Bun Build Check, and Optional Docker Build
532 " ✅ All 25 Orchestrator Tests Pass After `verify.sh` Changes; zfs-website Docker Build Confirmed Clean
533 8:57p 🔵 `verify.sh` Run on zfs-website: TypeScript Skipped (No `tsc`), `bun install` Fails with `PermissionDenied` on tempdir
534 8:59p ✅ zfs-website Passes `verify.sh` End-to-End with Escalated Permissions — `bun install` + `bun run build` Both Green
535 " ✅ zfs-website Dockerfile Restored to `--frozen-lockfile` Now That `bun.lock` Exists
536 9:00p 🔵 zfs-website Docker Build Context Ballooned to 525MB After Host `bun install`
537 9:05p ✅ zfs-website Final Docker Image `28b9099423ed` Built Successfully with `--frozen-lockfile` in Both Stages
538 " 🔴 `.dockerignore` Added to zfs-website — Docker Build Context Reduced from 525MB to 202KB
539 " ✅ zfs-website Docker Build Fully Optimized — 202KB Context, All Layers Cached, Built in 20s
540 9:06p 🔵 zfs-website Final State: All Steps `done`, Token Usage Breakdown, `node_modules` and `.next` Present on Host
541 9:11p ⚖️ Iterative Test-Fix Workflow with LM Studio + Stage-Based Verification Flags
542 " 🔵 AI Workflow Project: Existing Env Var Architecture and Verification Flag Patterns
543 " 🟣 Added VERIFY_PACKAGE_INSTALL and VERIFY_MODEL_REVIEW Flags to bin/verify.sh
544 9:12p 🟣 Added VERIFY_PACKAGE_BUILD Flag to bin/verify.sh
545 " ✅ Centralized Verification Flags and Provider Routing Docs in .env.example
546 " 🟣 Created docs/verification-flags.md — Authoritative Flag Reference and Repair Loop Design
547 9:13p 🔵 verification-before-completion Skill: Existing Guardrail Against Premature Done Claims
548 " 🔵 AI Workflow Project Is Not a Git Repository
549 9:14p ✅ README.md Updated to Document New Verification System and Link to Flags Reference
550 " 🔵 VERIFY_* Flags Require Manual .env Sourcing — bin/ai Auto-Loads .env but Shell Scripts Don't
551 9:15p 🔴 orchestrate.sh Now Auto-Sources .env for Shell-Stage Vars (VERIFY_* and PROVIDER Flags)
552 " ✅ Documentation Updated to Reflect orchestrate.sh Auto-Loading .env
553 " 🟣 Test Added for orchestrate.sh .env Auto-Loading with Shell Override Priority
554 9:16p 🔴 All Three OrchestrateExitStatusTest Tests Pass Including New .env Loading Test
555 " 🟣 Full Test Suite (26 Tests) Passes and VERIFY_MODEL_REVIEW=0 Verified Live on zfs-website
556 " 🔵 zfs-website Verification Profile: TypeScript Checks Skipped, bun Build Passes, Docker Test In Progress
557 9:17p 🔵 VERIFY_DOCKER_BUILD=1 Fails on zfs-website: Colima Docker Socket Permission Denied
558 9:23p 🔵 Orchestration Pipeline Failure: Missing `paths` Field in Scaffold Output
559 9:24p 🔵 zfs-website Project Passes Full Verification
560 " 🔵 AI Workflow Orchestration Architecture: Full Pipeline Map
561 " 🔵 `bin/ai` Provider JSON Mode: Ollama Uses `format:json`, Not Schema-Constrained Output
562 " 🟣 Added `LM_STUDIO_*` Env Var Aliases for LM Studio Provider in `bin/ai`
563 9:25p 🟣 Test Coverage Added for `LM_STUDIO_*` Alias in `select_model()`
564 " ✅ Full Test Suite Passes After `LM_STUDIO_*` Alias Changes: 27/27 OK
565 9:39p 🔵 AI Workflow Project Memory Context Gathered for Handover
566 " 🔵 AI Workflow Project: Full .md File Inventory and Structure
567 " 🔵 CLAUDE_FIX_NOTES.md: Six Priority Bugs and RTX 4060 Ollama Request
568 " 🔵 wordcount-cli-realtest: Ollama Run Failed at Verify; Orchestrator Exit-Code Bug Fixed
569 " 🔵 zfs-website Project: Full Verification PASS with Docker Build
570 9:40p 🔵 Project Portfolio State Snapshot: Current Step Status for All Five Tracked Projects
571 9:41p ✅ Created CLAUDE_HANDOVER.md and Cleared Four Stale Handoff Documents
572 " ✅ Handover Cleanup Confirmed: All Old Content Purged, README Updated
573 " 🔵 Test Suite Confirmed: 27 Tests Pass After Handover Document Cleanup

Access 274k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>