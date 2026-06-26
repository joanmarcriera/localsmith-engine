#!/usr/bin/env python3
"""state.py — read/write per-project state.json atomically.

Used by orchestrate.sh and the per-step scripts (plan.sh, impl.sh, verify.sh).

CLI:
  bin/state.py init  IDEA_FILE PROJECT_DIR        # create state.json from idea + tree.json
  bin/state.py get   PROJECT_DIR FIELD            # echo a top-level field (current_step, etc.)
  bin/state.py mark  PROJECT_DIR STEP done [OUT]  # mark step completed, optional output path
  bin/state.py mark  PROJECT_DIR STEP error MSG   # record last_error
  bin/state.py addtok PROJECT_DIR PROVIDER IN OUT # accumulate token counters
  bin/state.py addusage PROJECT_DIR USAGE_JSON    # accumulate one bin/ai usage record

Writes are atomic (tempfile + os.replace) — safe against Ctrl-C mid-write.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timezone

STEPS = ["scaffold", "plan", "implement", "verify"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(project_dir: pathlib.Path) -> pathlib.Path:
    return project_dir / "state.json"


def load(project_dir: pathlib.Path) -> dict:
    p = _path(project_dir)
    if not p.exists():
        sys.exit(f"[state] no state.json in {project_dir}")
    return json.loads(p.read_text())


def _log_event(state: dict, project_dir: pathlib.Path) -> None:
    """Append one record to ROOT/logs/state-events.jsonl per save. Cheap (one line).

    Lets the future dashboard activity-feed view watch state transitions without
    polling every state.json. Field shape is intentionally flat for awk-friendliness.
    """
    root = project_dir.parent.parent          # projects/<slug>/.. = workflow root
    events = root / "logs" / "state-events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": _now(),
        "project": state.get("project"),
        "step": state.get("current_step"),
        "completed": list(state.get("completed", [])),
        "last_error": state.get("last_error"),
    }
    with events.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def save(project_dir: pathlib.Path, state: dict) -> None:
    """Atomic write: tempfile in same dir, then os.replace.

    Records `step_entered_at[step] = now` the first time we see each step as current.
    Powers duration-aware views (Gantt etc.) without changing call sites.
    """
    now = _now()
    state["updated_at"] = now

    # Track when each step became current — write-once per step.
    entered = state.setdefault("step_entered_at", {})
    cs = state.get("current_step")
    if cs and cs not in entered:
        entered[cs] = now

    p = _path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state-", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    except Exception:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise

    # Best-effort event log; never fail the save because of it.
    try:
        _log_event(state, project_dir)
    except Exception:
        pass


def _next_step(state: dict) -> str:
    for s in state["steps"]:
        if s == "done":
            continue
        if s not in state["completed"]:
            return s
    return "done"


def cmd_init(idea_file: str, project_dir: str) -> None:
    pd = pathlib.Path(project_dir).resolve()
    tree = pd / "tree.json"
    if not tree.exists():
        sys.exit(f"[state] tree.json missing in {pd} — run scaffold.sh first")
    project = json.loads(tree.read_text())["project"]
    tokens: dict = {}
    scaffold_usage = pd / ".scaffold-usage.json"
    if scaffold_usage.exists():
        try:
            rec = json.loads(scaffold_usage.read_text())
            if not rec.get("project") or rec.get("project") == project:
                provider = rec.get("provider")
                if isinstance(provider, str) and provider:
                    tokens[provider] = {"in": int(rec.get("in", 0)), "out": int(rec.get("out", 0))}
        except Exception:
            pass
    state = {
        "project": project,
        "idea_path": str(pathlib.Path(idea_file).resolve()),
        "created_at": _now(),
        "updated_at": _now(),
        "steps": [*STEPS, "done"],
        "current_step": "plan",   # scaffold is already done by the time we init
        "completed": ["scaffold"],
        "outputs": {"scaffold": "tree.json"},
        "tokens": tokens,
        "last_error": None,
        "step_entered_at": {"scaffold": _now(), "plan": _now()},
    }
    save(pd, state)
    print(state["current_step"])


def cmd_get(project_dir: str, field: str) -> None:
    state = load(pathlib.Path(project_dir))
    val = state.get(field)
    if val is None:
        sys.exit(f"[state] no field: {field}")
    if isinstance(val, (dict, list)):
        json.dump(val, sys.stdout)
    else:
        sys.stdout.write(str(val))
    sys.stdout.write("\n")


def cmd_mark(project_dir: str, step: str, status: str, extra: str | None) -> None:
    pd = pathlib.Path(project_dir)
    state = load(pd)
    if status == "done":
        if step not in state["completed"]:
            state["completed"].append(step)
        if extra:
            state.setdefault("outputs", {})[step] = extra
        state["current_step"] = _next_step(state)
        state["last_error"] = None
    elif status == "error":
        if step in state.get("steps", []) and step != "done":
            state["current_step"] = step
        state["last_error"] = extra or "unspecified"
    else:
        sys.exit(f"[state] bad status: {status}")
    save(pd, state)
    print(state["current_step"])


def cmd_addtok(project_dir: str, provider: str, n_in: str, n_out: str) -> None:
    pd = pathlib.Path(project_dir)
    state = load(pd)
    bucket = state.setdefault("tokens", {}).setdefault(provider, {"in": 0, "out": 0})
    bucket["in"] += int(n_in)
    bucket["out"] += int(n_out)
    save(pd, state)


def cmd_addusage(project_dir: str, usage_file: str) -> None:
    pd = pathlib.Path(project_dir)
    state = load(pd)
    rec = json.loads(pathlib.Path(usage_file).read_text())
    if rec.get("project") and rec["project"] != state.get("project"):
        sys.exit(f"[state] usage project mismatch: {rec['project']} != {state.get('project')}")
    provider = rec.get("provider")
    if not isinstance(provider, str) or not provider:
        sys.exit("[state] usage missing provider")
    try:
        n_in = int(rec.get("in", 0))
        n_out = int(rec.get("out", 0))
    except (TypeError, ValueError):
        sys.exit("[state] usage in/out must be integers")
    if n_in < 0 or n_out < 0:
        sys.exit("[state] usage in/out must be non-negative")
    bucket = state.setdefault("tokens", {}).setdefault(provider, {"in": 0, "out": 0})
    bucket["in"] += n_in
    bucket["out"] += n_out
    save(pd, state)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    try:
        if cmd == "init":
            cmd_init(args[0], args[1])
        elif cmd == "get":
            cmd_get(args[0], args[1])
        elif cmd == "mark":
            cmd_mark(args[0], args[1], args[2], args[3] if len(args) > 3 else None)
        elif cmd == "addtok":
            cmd_addtok(args[0], args[1], args[2], args[3])
        elif cmd == "addusage":
            cmd_addusage(args[0], args[1])
        else:
            sys.exit(f"[state] unknown command: {cmd}")
    except IndexError:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
