#!/usr/bin/env bash
# impl.sh — implement each task in plan.json by calling Z.AI for the file body.
#
# Usage: bin/impl.sh PROJECT_DIR
#
# Per task:
#   - skip if target file already exists AND is non-empty (idempotent resume)
#   - build prompt: prompts/impl.txt + intent + each dep file's current contents
#   - call bin/ai $IMPL_PROVIDER (default zai)
#   - write file atomically
#   - on any task failure: stop, leave state intact, exit non-zero
#
# After all tasks succeed, mark step done.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PD="${1:?usage: impl.sh PROJECT_DIR}"
[ -f "$PD/plan.json"  ] || { echo "[impl] no plan.json in $PD"  >&2; exit 1; }
[ -f "$PD/state.json" ] || { echo "[impl] no state.json in $PD" >&2; exit 1; }

PROVIDER="${IMPL_PROVIDER:-zai}"

# Walk tasks in order. Emit one line per task: status<TAB>path<TAB>tokens_in<TAB>tokens_out.
python3 - "$ROOT" "$PD" "$PROVIDER" <<'PY'
import json, os, pathlib, subprocess, sys, tempfile

root = pathlib.Path(sys.argv[1])
pd   = pathlib.Path(sys.argv[2])
provider = sys.argv[3]

plan = json.loads((pd / "plan.json").read_text())
tpl  = (root / "prompts" / "impl.txt").read_text()
sys.path.insert(0, str(root / "bin"))
from validate_plan import expected_slug_for, validate_doc

validate_doc(plan, expected_slug_for(pd))

prefs = root / "prefs.md"
sys_args = ["--system", f"@{prefs}"] if prefs.exists() else []
if sys_args:
    print("[impl] using prefs.md as system prompt", file=sys.stderr)

def call_ai(prompt: str) -> str:
    """Subprocess bin/ai PROVIDER - --system @prefs.md (read prompt from stdin)."""
    fd, usage = tempfile.mkstemp(prefix=".impl-usage-", dir=str(pd))
    os.close(fd)
    env = os.environ.copy()
    env["AIWF_PROJECT"] = plan.get("project", pd.name)
    env["AIWF_STEP"] = "implement"
    try:
        proc = subprocess.run(
            [str(root / "bin" / "ai"), provider, "-", *sys_args, "--usage-file", usage],
            input=prompt, capture_output=True, text=True, env=env, check=True,
        )
        return proc.stdout
    finally:
        usage_path = pathlib.Path(usage)
        if usage_path.exists() and usage_path.stat().st_size > 0:
            subprocess.run(
                [str(root / "bin" / "state.py"), "addusage", str(pd), str(usage_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
        usage_path.unlink(missing_ok=True)

def is_nonempty(p: pathlib.Path) -> bool:
    return p.exists() and p.stat().st_size > 0

failures = 0
for task in plan["tasks"]:
    rel = task["path"]
    target = pd / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    if is_nonempty(target):
        print(f"[impl] skip {rel} (already filled)", file=sys.stderr)
        continue

    # Assemble dep context
    dep_blocks = []
    for dep in task.get("deps", []):
        dep_path = pd / dep
        if dep_path.exists():
            dep_blocks.append(f"--- DEP {dep} ---\n{dep_path.read_text()}\n")
    deps_text = "".join(dep_blocks) if dep_blocks else "(no deps)\n"

    prompt = (
        f"{tpl}\n"
        f"--- FILE TO IMPLEMENT ---\n{rel}\n\n"
        f"--- INTENT ---\n{task['intent']}\n\n"
        f"--- DEPENDENCY FILES (read-only context) ---\n{deps_text}"
    )

    try:
        body = call_ai(prompt)
    except subprocess.CalledProcessError as exc:
        print(f"[impl] FAIL {rel}: {exc.stderr.strip()}", file=sys.stderr)
        failures += 1
        break

    # Atomic write
    fd, tmp = tempfile.mkstemp(prefix=".impl-", dir=str(target.parent))
    with os.fdopen(fd, "w") as f:
        f.write(body)
    os.replace(tmp, target)
    print(f"[impl] wrote {rel} ({len(body)} bytes)", file=sys.stderr)

sys.exit(failures)
PY

"$ROOT/bin/state.py" mark "$PD" implement done >/dev/null
echo "[impl] done" >&2
