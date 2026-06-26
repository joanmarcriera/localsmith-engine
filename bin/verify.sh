#!/usr/bin/env bash
# verify.sh — static checks + local-model code review for a generated project.
#
# Usage: bin/verify.sh PROJECT_DIR
#
# Two free passes (no cloud tokens):
#   1. Static — per-extension toolchain check (py_compile, gofmt -l, go vet, shellcheck, ...).
#   2. Review — pipe each source file to Ollama with prompts/review.txt as --system, expecting "OK"
#      or a bulleted issue list.
#
# Aggregates into <project>/report.md. Exits non-zero (and marks state error) when any check
# fails OR the reviewer returns non-"OK" for any file.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PD="${1:?usage: verify.sh PROJECT_DIR}"
[ -d "$PD" ] || { echo "[verify] not a dir: $PD" >&2; exit 1; }

REPORT="$PD/report.md"
PROVIDER="${REVIEW_PROVIDER:-ollama}"
OUT_FILE="$(mktemp "${TMPDIR:-/tmp}/aiwf-verify-out.XXXXXX")"
trap 'rm -f "$OUT_FILE"' EXIT

# Source files only. Use tree.json as an input, but also scan the actual project.
# Generated plans can add build-critical files after scaffold; verification must
# catch those instead of only checking the original empty tree.
tree_files() {
    [ -f "$PD/tree.json" ] || return 0
    python3 - "$PD" <<'PY'
import json, pathlib, sys
pd = pathlib.Path(sys.argv[1])
doc = json.loads((pd / "tree.json").read_text())
source_names = {
    "Dockerfile", "go.mod", "go.sum", "pyproject.toml", "package.json", "tsconfig.json",
    "compose.yaml", "compose.yml",
}
source_suffixes = {".py", ".go", ".sh", ".js", ".jsx", ".ts", ".tsx", ".html", ".sql", ".css"}
wanted = []
for rel in doc.get("paths", []):
    if rel.endswith("/"):
        continue
    p = pd / rel
    if p.exists() and p.is_file() and (p.name in source_names or p.suffix in source_suffixes):
        wanted.append(str(p))
for p in sorted(wanted):
    print(p)
PY
}

found_files() {
    find "$PD" -type f \
        \( -name '*.py' -o -name '*.go' -o -name '*.sh' -o -name '*.js' -o -name '*.jsx' \
           -o -name '*.ts' -o -name '*.tsx' -o -name '*.html' -o -name '*.sql' -o -name '*.css' \
           -o -name 'Dockerfile' -o -name 'go.mod' -o -name 'go.sum' -o -name 'pyproject.toml' \
           -o -name 'package.json' -o -name 'tsconfig.json' -o -name 'compose.yaml' -o -name 'compose.yml' \) \
        ! -path '*/node_modules/*' ! -path '*/.venv/*' ! -path '*/.next/*' ! -path '*/dist/*'
}

mapfile -t FILES < <({ tree_files; found_files; } | sort -u)

{
    echo "# Verification report"
    echo
    echo "Project: \`$(basename "$PD")\`"
    echo "Generated: $(date -Iseconds 2>/dev/null || date)"
    echo
    echo "## Files inspected"
    echo
    for f in "${FILES[@]}"; do echo "- \`${f#"$PD"/}\`"; done
    echo
} > "$REPORT"

fail=0
go_test_passed=0

# --- Pass 1: static checks ---------------------------------------------------
echo "## Static checks" >> "$REPORT"
echo >> "$REPORT"

run_check() {
    local label="$1" file="$2"; shift 2
    if "$@" >"$OUT_FILE" 2>&1; then
        echo "- [OK] $label \`${file#"$PD"/}\`" >> "$REPORT"
    else
        echo "- [FAIL] $label \`${file#"$PD"/}\`" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        sed 's/^/  /' "$OUT_FILE" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        fail=$((fail + 1))
    fi
}

run_check_empty() {
    local label="$1" file="$2"; shift 2
    if "$@" >"$OUT_FILE" 2>&1 && [ ! -s "$OUT_FILE" ]; then
        echo "- [OK] $label \`${file#"$PD"/}\`" >> "$REPORT"
    else
        echo "- [FAIL] $label \`${file#"$PD"/}\`" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        sed 's/^/  /' "$OUT_FILE" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        fail=$((fail + 1))
    fi
}

run_project_check() {
    local label="$1"; shift
    if (cd "$PD" && "$@") >"$OUT_FILE" 2>&1; then
        echo "- [OK] $label" >> "$REPORT"
    else
        echo "- [FAIL] $label" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        sed 's/^/  /' "$OUT_FILE" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        fail=$((fail + 1))
    fi
}

for f in "${FILES[@]}"; do
    case "$f" in
        *.py)
            run_check py_compile "$f" python3 -m py_compile "$f"
            command -v ruff >/dev/null && run_check ruff "$f" ruff check "$f"
            ;;
        *.go)
            command -v gofmt >/dev/null && run_check_empty gofmt "$f" gofmt -l "$f"
            ;;
        *.sh)
            run_check 'bash -n' "$f" bash -n "$f"
            command -v shellcheck >/dev/null && run_check shellcheck "$f" shellcheck "$f"
            ;;
        *.js)
            command -v node >/dev/null && run_check 'node --check' "$f" node --check "$f"
            ;;
        *.jsx)
            echo "- [SKIP] JSX syntax \`${f#"$PD"/}\` (covered by package build when available)" >> "$REPORT"
            ;;
        *.ts)
            if command -v tsc >/dev/null && [ -f "$PD/tsconfig.json" ]; then
                run_check 'tsc --noEmit' "$f" tsc --noEmit --project "$PD/tsconfig.json"
            else
                echo "- [SKIP] TypeScript \`${f#"$PD"/}\` (no tsc + tsconfig.json check available)" >> "$REPORT"
            fi
            ;;
        *.tsx)
            if command -v tsc >/dev/null && [ -f "$PD/tsconfig.json" ]; then
                run_check 'tsc --noEmit' "$f" tsc --noEmit --project "$PD/tsconfig.json"
            else
                echo "- [SKIP] TypeScript JSX \`${f#"$PD"/}\` (no tsc + tsconfig.json check available)" >> "$REPORT"
            fi
            ;;
        Dockerfile|*/Dockerfile)
            command -v hadolint >/dev/null && run_check hadolint "$f" hadolint "$f"
            ;;
    esac
done

if [ "${VERIFY_PACKAGE_INSTALL:-1}" = "1" ] && [ -f "$PD/package.json" ]; then
    if python3 - "$PD/package.json" >"$OUT_FILE" 2>&1 <<'PY'
import json, pathlib, sys
pkg = json.loads(pathlib.Path(sys.argv[1]).read_text())
known_bad = {"react-hookform": "react-hook-form"}
found = []
for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
    deps = pkg.get(section, {})
    if isinstance(deps, dict):
        for bad, good in known_bad.items():
            if bad in deps:
                found.append(f"{section}.{bad} is not a published package; use {good}")
if found:
    raise SystemExit("\n".join(found))
PY
    then
        echo "- [OK] package dependency names" >> "$REPORT"
    else
        echo "- [FAIL] package dependency names" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        sed 's/^/  /' "$OUT_FILE" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        fail=$((fail + 1))
    fi

    if command -v bun >/dev/null; then
        if [ -f "$PD/bun.lock" ] || [ -f "$PD/bun.lockb" ]; then
            run_project_check 'bun install --frozen-lockfile' bun install --frozen-lockfile
        else
            run_project_check 'bun install' bun install
        fi
        if [ "${VERIFY_PACKAGE_BUILD:-1}" = "1" ] && python3 - "$PD/package.json" <<'PY'
import json, pathlib, sys
pkg = json.loads(pathlib.Path(sys.argv[1]).read_text())
raise SystemExit(0 if "build" in pkg.get("scripts", {}) else 1)
PY
        then
            run_project_check 'bun run build' bun run build
        elif [ "${VERIFY_PACKAGE_BUILD:-1}" != "1" ]; then
            echo "- [SKIP] package build (VERIFY_PACKAGE_BUILD=0)" >> "$REPORT"
        fi
    else
        echo "- [SKIP] package build (bun not installed)" >> "$REPORT"
    fi
elif [ -f "$PD/package.json" ]; then
    echo "- [SKIP] package install/build (VERIFY_PACKAGE_INSTALL=0)" >> "$REPORT"
fi

if [ "${VERIFY_DOCKER_BUILD:-0}" = "1" ] && [ -f "$PD/Dockerfile" ]; then
    if command -v docker >/dev/null; then
        run_project_check 'docker build .' docker build .
    else
        echo "- [SKIP] docker build (docker not installed)" >> "$REPORT"
    fi
fi

if printf '%s\n' "${FILES[@]}" | grep -q '\.go$'; then
    if [ -f "$PD/go.mod" ]; then
        if (cd "$PD" && go test ./...) >"$OUT_FILE" 2>&1; then
            echo "- [OK] go test ./..." >> "$REPORT"
            go_test_passed=1
        else
            echo "- [FAIL] go test ./..." >> "$REPORT"
            echo '  ```' >> "$REPORT"
            sed 's/^/  /' "$OUT_FILE" >> "$REPORT"
            echo '  ```' >> "$REPORT"
            fail=$((fail + 1))
        fi
    else
        echo "- [FAIL] go module \`go.mod\` missing for Go project" >> "$REPORT"
        fail=$((fail + 1))
    fi
fi
echo >> "$REPORT"

# --- Pass 2: local-model review ---------------------------------------------
echo "## Code review (provider: $PROVIDER)" >> "$REPORT"
echo >> "$REPORT"

if [ "${VERIFY_MODEL_REVIEW:-1}" != "1" ]; then
    echo "- [SKIP] model review (VERIFY_MODEL_REVIEW=0)" >> "$REPORT"
    echo >> "$REPORT"
    if [ "$fail" -eq 0 ]; then
        echo "## Result: PASS" >> "$REPORT"
        "$ROOT/bin/state.py" mark "$PD" verify done report.md >/dev/null
        echo "[verify] PASS — see $REPORT" >&2
        exit 0
    fi
    echo "## Result: $fail issue(s) — FAIL" >> "$REPORT"
    "$ROOT/bin/state.py" mark "$PD" verify error "$fail verification issue(s)" >/dev/null
    echo "[verify] $fail issue(s) — see $REPORT" >&2
    exit 1
fi

if [ "$go_test_passed" -eq 1 ]; then
    echo "- [OK] Go project (go test ./... passed; local model review skipped to avoid compiler-contradicting false positives)" >> "$REPORT"
fi

for f in "${FILES[@]}"; do
    rel="${f#"$PD"/}"
    # Skip markup/config/generated manifests — static checks cover what matters.
    case "$f" in *.html|*.sql|*.md|*/go.mod|*/go.sum|*/Dockerfile|*/compose.yaml|*/compose.yml) continue ;; esac
    # Skip empty files.
    [ -s "$f" ] || continue

    if [[ "$f" == *.go && "$go_test_passed" -eq 1 ]]; then
        continue
    fi

    echo "[verify] reviewing $rel" >&2
    usage_file="$(mktemp "${TMPDIR:-/tmp}/aiwf-verify-usage.XXXXXX")"
    review="$(
        {
            echo "Static checks for this project have already run before this review pass."
            if [[ "$f" == *.go ]]; then
                if [ "$go_test_passed" -eq 1 ]; then
                    echo "For this Go project, go test ./... passed. Do not report compile-time missing symbols."
                fi
                echo "Review the Go project as a whole for runtime bugs, resource leaks, and security issues."
                echo
                echo '--- all go files for context ---'
                for g in "${FILES[@]}"; do
                    [[ "$g" == *.go ]] || continue
                    echo
                    echo "--- GO FILE ${g#"$PD"/} ---"
                    cat "$g"
                done
            else
                echo "File: $rel"
                echo
                echo '--- file contents ---'
                cat "$f"
            fi
        } | AIWF_PROJECT="$(basename "$PD")" AIWF_STEP=verify "$ROOT/bin/ai" "$PROVIDER" - --system "@$ROOT/prompts/review.txt" --usage-file "$usage_file" 2>/dev/null || echo 'ERROR'
    )"
    if [ -s "$usage_file" ] && [ -f "$PD/state.json" ]; then
        "$ROOT/bin/state.py" addusage "$PD" "$usage_file" >/dev/null || true
    fi
    rm -f "$usage_file"
    trimmed="$(echo "$review" | tr -d '[:space:]')"

    if [ "$trimmed" = "OK" ]; then
        echo "- [OK] \`$rel\`" >> "$REPORT"
    else
        echo "- [ISSUES] \`$rel\`" >> "$REPORT"
        echo '  ```' >> "$REPORT"
        echo "$review" | sed 's/^/  /' >> "$REPORT"
        echo '  ```' >> "$REPORT"
        fail=$((fail + 1))
    fi
done

# --- Mark state and exit -----------------------------------------------------
echo >> "$REPORT"
if [ "$fail" -eq 0 ]; then
    echo "## Result: PASS" >> "$REPORT"
    "$ROOT/bin/state.py" mark "$PD" verify done report.md >/dev/null
    echo "[verify] PASS — see $REPORT" >&2
else
    echo "## Result: $fail issue(s) — FAIL" >> "$REPORT"
    "$ROOT/bin/state.py" mark "$PD" verify error "$fail verification issue(s)" >/dev/null
    echo "[verify] $fail issue(s) — see $REPORT" >&2
    exit 1
fi
