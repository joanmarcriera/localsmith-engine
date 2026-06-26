# Project idea — silly-web-game

A small browser game, single HTML file, served by a tiny Python stdlib HTTP server.

## Constraints (intentionally tight — this is the Phase 5 test case)
- Single page, no build step, no npm.
- Vanilla JS + Canvas or DOM (your call during plan phase).
- Game must be "silly" — pick from: pigeon-vs-toast, cat-stacks-laundry, escape-the-Zoom-call,
  or invent one in plan.md.
- Total source ≤ 300 lines including HTML.
- One Python file (`server.py`) using `http.server` only, no Flask.
- README.md with one-line run command.

## Acceptance
- `python3 server.py` launches on :8080 and serves the game.
- Game has a win state and a lose state.
- `shellcheck` clean for any shell glue; `ruff check` clean for `server.py`.

## Used by
This is the test project for `orchestrate.sh` once Phases 1–4 are done. The orchestrator
should produce: `plan.md`, `tree.json`, `src/index.html`, `src/server.py`, `README.md`,
`report.md`, all under `projects/silly-web-game/`.
