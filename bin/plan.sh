#!/usr/bin/env bash
# plan.sh — produce projects/<slug>/plan.json from idea + tree, using Claude.
#
# Usage: bin/plan.sh PROJECT_DIR
#
# Pipeline:
#   1. Read idea_path and tree.json paths.
#   2. Concatenate prompts/plan.txt + idea + tree into one prompt.
#   3. Call bin/ai <PROVIDER> --json (default: claude — free under Pro quota).
#   4. Lightly validate the JSON output (project slug + tasks[] non-empty).
#   5. Write plan.json atomically and mark the step done.
#
# Override provider with $PLAN_PROVIDER (e.g. zai for cost comparison).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PD="${1:?usage: plan.sh PROJECT_DIR}"
[ -d "$PD" ] || { echo "[plan] not a dir: $PD" >&2; exit 1; }
[ -f "$PD/state.json" ] || { echo "[plan] no state.json in $PD" >&2; exit 1; }
[ -f "$PD/tree.json"  ] || { echo "[plan] no tree.json in $PD" >&2; exit 1; }

PROVIDER="${PLAN_PROVIDER:-claude}"
IDEA="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["idea_path"])' "$PD/state.json")"
[ -f "$IDEA" ] || { echo "[plan] idea_path missing: $IDEA" >&2; exit 1; }

# Build the full prompt: template + idea + tree
PROMPT="$(cat "$ROOT/prompts/plan.txt"; echo '---IDEA---'; cat "$IDEA"; echo '---TREE---'; cat "$PD/tree.json")"

# Inject engineering preferences as the system prompt (if present)
SYS_ARGS=()
if [ -f "$ROOT/prefs.md" ]; then
    SYS_ARGS=(--system "@$ROOT/prefs.md")
    echo "[plan] using prefs.md as system prompt" >&2
fi

echo "[plan] dispatching to $PROVIDER with --json..." >&2
# Persist raw model output INSIDE the project dir so it survives debugging.
# Overwritten on every plan attempt; deleted only when plan.json is written.
RAW_FILE="$PD/.plan-raw.txt"
USAGE_FILE="$(mktemp "${TMPDIR:-/tmp}/aiwf-plan-usage.XXXXXX")"
cleanup_usage() {
    if [ -s "$USAGE_FILE" ]; then
        "$ROOT/bin/state.py" addusage "$PD" "$USAGE_FILE" >/dev/null || true
    fi
    rm -f "$USAGE_FILE"
}
trap cleanup_usage EXIT

SLUG="$(basename "$PD")"
printf '%s' "$PROMPT" | AIWF_PROJECT="$SLUG" AIWF_STEP=plan "$ROOT/bin/ai" "$PROVIDER" - --json "${SYS_ARGS[@]}" --usage-file "$USAGE_FILE" > "$RAW_FILE"

RAW_SIZE=$(wc -c < "$RAW_FILE")
echo "[plan] raw response: $RAW_SIZE bytes (saved to $RAW_FILE)" >&2

# Validate with progressively-lenient JSON extraction strategies.
# Strategy 1: parse the file as-is.
# Strategy 2: find the first '{' and matching last '}' (handles preamble/postamble).
# Strategy 3: scan for any balanced {...} substring containing '"tasks"'.
# If strategy 2/3 succeeds we keep .plan-raw.txt for forensic value AND write plan.json.
python3 - "$ROOT" "$PD" "$RAW_FILE" <<'PY'
import json, sys, pathlib, os, re, tempfile
root    = pathlib.Path(sys.argv[1])
pd      = pathlib.Path(sys.argv[2])
raw_p   = pathlib.Path(sys.argv[3])
raw     = raw_p.read_text().strip()
sys.path.insert(0, str(root / "bin"))
from validate_plan import expected_slug_for, validate_doc

def parse(s: str):
    return json.loads(s)

doc = None
err = None
# Strategy 1
try:
    doc = parse(raw)
except json.JSONDecodeError as e:
    err = e

# Strategy 2: first { ... last }
if doc is None:
    a, b = raw.find("{"), raw.rfind("}")
    if a != -1 and b > a:
        try:
            doc = parse(raw[a:b+1])
            print(f"[plan] recovered JSON span: bytes {a}..{b}", file=sys.stderr)
        except json.JSONDecodeError:
            pass

# Strategy 3: any balanced {...} containing "tasks"
if doc is None:
    for m in re.finditer(r"\{[\s\S]*?\}\s*(?=$|\Z|\n\S)", raw):
        candidate = m.group(0)
        if '"tasks"' in candidate:
            try:
                doc = parse(candidate)
                print("[plan] recovered JSON via tasks-anchored regex", file=sys.stderr)
                break
            except json.JSONDecodeError:
                continue

if doc is None:
    head = raw[:300].replace("\n", "\\n")
    sys.exit(
        f"[plan] could not extract JSON.\n"
        f"  raw saved to: {raw_p}\n"
        f"  size: {len(raw)} bytes\n"
        f"  parse error: {err}\n"
        f"  first 300 chars: {head}"
    )

for k in ("project", "tasks"):
    if k not in doc:
        sys.exit(f"[plan] missing field: {k} (raw kept at {raw_p})")
if not isinstance(doc["tasks"], list) or not doc["tasks"]:
    sys.exit(f"[plan] tasks must be a non-empty list (raw kept at {raw_p})")
for t in doc["tasks"]:
    if "path" not in t or "intent" not in t:
        sys.exit(f"[plan] task missing path/intent: {t} (raw kept at {raw_p})")

try:
    validate_doc(doc, expected_slug_for(pd))
except ValueError as exc:
    sys.exit(f"[plan] invalid plan: {exc} (raw kept at {raw_p})")

fd, tmp = tempfile.mkstemp(prefix=".plan-", dir=str(pd))
with os.fdopen(fd, "w") as f:
    json.dump(doc, f, indent=2)
    f.write("\n")
os.replace(tmp, pd / "plan.json")
print(f"[plan] wrote {pd / 'plan.json'} with {len(doc['tasks'])} task(s)", file=sys.stderr)
PY

# Success — remove the raw debug file
rm -f "$RAW_FILE"

"$ROOT/bin/state.py" mark "$PD" plan done plan.json >/dev/null
