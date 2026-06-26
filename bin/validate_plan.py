#!/usr/bin/env python3
"""validate_plan.py — strict stdlib validation for generated plan.json files."""

from __future__ import annotations

import json
import pathlib
import re
import sys

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
PATH_RE = re.compile(r"^[A-Za-z0-9._-][A-Za-z0-9._/-]*$")
ROOT_KEYS = {"project", "decisions", "tasks"}
TASK_KEYS = {"path", "intent", "deps"}


def _safe_rel_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 200:
        raise ValueError(f"{field} must be a string of length 1..200")
    if value.startswith("/") or value.endswith("/"):
        raise ValueError(f"unsafe path in {field}: {value!r}")
    if ".." in value.split("/"):
        raise ValueError(f"unsafe path in {field}: {value!r}")
    if not PATH_RE.fullmatch(value):
        raise ValueError(f"{field} fails path pattern: {value!r}")
    return value


def validate_doc(doc: object, expected_slug: str) -> dict:
    """Validate a plan document and return it typed as a dict."""
    if not isinstance(doc, dict):
        raise ValueError("root must be an object")
    extra = set(doc) - ROOT_KEYS
    if extra:
        raise ValueError(f"unexpected root field(s): {', '.join(sorted(extra))}")

    project = doc.get("project")
    if not isinstance(project, str) or not SLUG_RE.fullmatch(project):
        raise ValueError(f"invalid project slug: {project!r}")
    if project != expected_slug:
        raise ValueError(f"project mismatch: plan says {project!r}, expected {expected_slug!r}")

    if "decisions" in doc and (not isinstance(doc["decisions"], str) or len(doc["decisions"]) > 2000):
        raise ValueError("decisions must be a string <=2000 chars")

    tasks = doc.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 50:
        raise ValueError("tasks must be a list of 1..50 items")

    seen_paths: set[str] = set()
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"task {idx} must be an object")
        extra = set(task) - TASK_KEYS
        if extra:
            raise ValueError(f"task {idx} unexpected field(s): {', '.join(sorted(extra))}")
        for key in ("path", "intent"):
            if key not in task:
                raise ValueError(f"task {idx} missing field: {key}")

        path = _safe_rel_path(task["path"], f"task {idx} path")
        if path in seen_paths:
            raise ValueError(f"duplicate task path: {path}")
        seen_paths.add(path)

        intent = task["intent"]
        if not isinstance(intent, str) or not 1 <= len(intent) <= 1000:
            raise ValueError(f"task {idx} intent must be a string of length 1..1000")

        deps = task.get("deps", [])
        if not isinstance(deps, list):
            raise ValueError(f"task {idx} deps must be a list")
        if len(set(deps)) != len(deps):
            raise ValueError(f"task {idx} deps contains duplicates")
        for dep_idx, dep in enumerate(deps):
            _safe_rel_path(dep, f"task {idx} deps[{dep_idx}]")

    return doc


def expected_slug_for(project_dir: pathlib.Path) -> str:
    tree = project_dir / "tree.json"
    if tree.exists():
        try:
            doc = json.loads(tree.read_text())
            if isinstance(doc.get("project"), str):
                return doc["project"]
        except (OSError, json.JSONDecodeError):
            pass
    return project_dir.name


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: validate_plan.py PROJECT_DIR [PLAN_FILE]")
    project_dir = pathlib.Path(sys.argv[1]).resolve()
    plan_path = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else project_dir / "plan.json"

    try:
        doc = json.loads(plan_path.read_text())
        validate_doc(doc, expected_slug_for(project_dir))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[validate_plan] {exc}", file=sys.stderr)
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
