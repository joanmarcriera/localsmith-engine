#!/usr/bin/env python3
"""materialize.py — validate a tree.json against the schema, then create dirs/files.

Usage:
  bin/materialize.py PROJECTS_ROOT < tree.json
  bin/materialize.py projects/ < projects/silly-web-game/tree.json

Reads JSON from stdin, validates against lib/schema/tree.schema.json (stdlib-only
validator — minimal subset sufficient for our schema), then creates:
    PROJECTS_ROOT/<project>/<each path>

Refuses to overwrite existing files. Idempotent: re-running is a no-op.
Exits non-zero on any validation or filesystem error.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "lib" / "schema" / "tree.schema.json"


def validate(doc: dict) -> None:
    """Tiny ad-hoc validator. Covers the rules our schema declares.

    Avoids the jsonschema dependency for Phase 2. Phase 3 swaps this for
    `jsonschema.Draft202012Validator` once we add the dep.
    """
    if not isinstance(doc, dict):
        raise ValueError("root must be an object")
    for key in ("project", "paths"):
        if key not in doc:
            raise ValueError(f"missing required field: {key}")

    project = doc["project"]
    if not isinstance(project, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", project):
        raise ValueError(f"invalid project slug: {project!r}")

    if "summary" in doc and (not isinstance(doc["summary"], str) or len(doc["summary"]) > 280):
        raise ValueError("summary must be a string <=280 chars")

    paths = doc["paths"]
    if not isinstance(paths, list) or not 1 <= len(paths) <= 200:
        raise ValueError("paths must be a list of 1..200 items")
    if len(set(paths)) != len(paths):
        raise ValueError("paths contains duplicates")

    path_re = re.compile(r"[A-Za-z0-9._-][A-Za-z0-9._/-]*/?")
    for p in paths:
        if not isinstance(p, str) or not 1 <= len(p) <= 200:
            raise ValueError(f"bad path: {p!r}")
        if not path_re.fullmatch(p):
            raise ValueError(f"path fails pattern: {p!r}")
        if p.startswith("/") or ".." in p.split("/"):
            raise ValueError(f"unsafe path: {p!r}")


def materialize(doc: dict, root: pathlib.Path) -> tuple[int, int]:
    """Create dirs and empty files. Returns (dirs_created, files_created)."""
    base = root / doc["project"]
    base.mkdir(parents=True, exist_ok=True)
    n_dirs = n_files = 0
    for raw in doc["paths"]:
        target = base / raw
        if raw.endswith("/"):
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                n_dirs += 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.touch()
                n_files += 1
    return n_dirs, n_files


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: materialize.py PROJECTS_ROOT [EXPECTED_SLUG]  (reads JSON from stdin)")
    root = pathlib.Path(sys.argv[1]).resolve()
    expected_slug = sys.argv[2] if len(sys.argv) == 3 else None
    root.mkdir(parents=True, exist_ok=True)

    try:
        doc = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.exit(f"[materialize] invalid JSON: {exc}")

    try:
        validate(doc)
    except ValueError as exc:
        sys.exit(f"[materialize] schema violation: {exc}")

    # Enforce the canonical slug — scaffold.sh passes the idea-filename slug.
    if expected_slug and doc["project"] != expected_slug:
        sys.exit(
            f"[materialize] slug mismatch: tree says {doc['project']!r}, "
            f"expected {expected_slug!r}. Idea filename is the only source of truth."
        )

    n_dirs, n_files = materialize(doc, root)
    sys.stderr.write(
        f"[materialize] {doc['project']}: created {n_dirs} dirs, {n_files} files under {root}\n"
    )
    # echo tree.json on stdout so callers can pipe / save
    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
