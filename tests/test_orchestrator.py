#!/usr/bin/env python3
"""test_orchestrator — focused regression tests for the AI workflow orchestrator.

WHAT: Tests covering the parts most likely to regress silently:
  1. materialize.py — slug enforcement (the bug that swallowed Option A).
  2. state.py — full lifecycle: init → mark done → addtok, with step_entered_at
     timestamps and the state-events.jsonl append.
  3. bin/stats — output against a hand-crafted fixture (projects + logs).
  4. bin/ai — local-first routing helpers and project/step usage records.
  5. validate_plan.py — project/path safety before implementation.
  6. bin/search — default SearXNG endpoint construction.
  7. WorkflowSmokeTest — three fixture-backed projects that run the real
     scaffold, plan, implement, and verify scripts end to end.

WHY: We learned the hard way that silent failures here cost real tokens later.
These tests run in <1s, hit no network, and burn no API quota — fast enough to
attach to a pre-commit hook eventually.

KEY DECISIONS:
- Pure stdlib unittest; matches the rest of bin/ in dependency posture.
- Each test gets its own tempdir; nothing leaks into the real `projects/`.
- We exercise the scripts via subprocess (not Python import) so the tests
  catch shebang, exit-code, and arg-parsing regressions too.
- Synthetic fixtures, not real data — keeps assertions deterministic.

Usage:
    python3 tests/test_orchestrator.py            # verbose by default
    python3 tests/test_orchestrator.py WorkflowSmokeTest
    python3 -m unittest tests.test_orchestrator   # alt entry
"""

from __future__ import annotations

import json
import importlib.machinery
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parent.parent
BIN = REPO / "bin"


def _load_bin_module(name: str):
    """Load extensionless scripts from bin/ as Python modules for focused unit tests."""
    path = BIN / name
    loader = importlib.machinery.SourceFileLoader(f"aiwf_{name.replace('-', '_')}", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"could not load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _run(
    cmd: list[str],
    *,
    input_text: str | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess with text I/O, never raising on non-zero exit."""
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


class SlugEnforcementTest(unittest.TestCase):
    """materialize.py must refuse to write when project slug != expected slug.

    Reason this exists: the original Option A failure had Ollama produce
    project='ai-workflow-dashboard' while orchestrate.sh expected 'dashboard'.
    The new enforcement closes that loop.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="aiwf-slug-")
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_accepts_matching_slug(self) -> None:
        doc = json.dumps({
            "project": "demo-proj",
            "summary": "a tiny demo",
            "paths": ["README.md", "src/", "src/main.go"],
        })
        proc = _run(
            [str(BIN / "materialize.py"), self.tmp, "demo-proj"],
            input_text=doc,
        )
        self.assertEqual(proc.returncode, 0, msg=f"stderr: {proc.stderr}")
        self.assertTrue((pathlib.Path(self.tmp) / "demo-proj" / "README.md").exists())
        self.assertTrue((pathlib.Path(self.tmp) / "demo-proj" / "src" / "main.go").exists())

    def test_rejects_mismatched_slug(self) -> None:
        doc = json.dumps({
            "project": "wrong-name",
            "summary": "the LLM hallucinated a different slug",
            "paths": ["README.md"],
        })
        proc = _run(
            [str(BIN / "materialize.py"), self.tmp, "demo-proj"],
            input_text=doc,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("slug mismatch", proc.stderr)
        # Nothing should have been written under either name.
        self.assertFalse((pathlib.Path(self.tmp) / "demo-proj").exists())
        self.assertFalse((pathlib.Path(self.tmp) / "wrong-name").exists())


class StateLifecycleTest(unittest.TestCase):
    """state.py: init → get → mark done → addtok must round-trip and emit events."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="aiwf-state-"))
        self.addCleanup(shutil.rmtree, self.tmp)

        # state.py expects a workflow root with projects/<slug>/ structure so it
        # can write logs/state-events.jsonl two levels up. Build that shape.
        self.proj = self.tmp / "projects" / "demo-proj"
        self.proj.mkdir(parents=True)
        (self.tmp / "logs").mkdir()

        # tree.json is a prerequisite of `state.py init`.
        (self.proj / "tree.json").write_text(json.dumps({
            "project": "demo-proj",
            "paths": ["README.md"],
        }))

        # Idea file referenced by state.json.
        (self.tmp / "queue").mkdir()
        self.idea = self.tmp / "queue" / "demo-proj.md"
        self.idea.write_text("# Project — demo-proj\nSmall test idea.\n")

    def _state(self) -> dict:
        return json.loads((self.proj / "state.json").read_text())

    def test_full_lifecycle(self) -> None:
        # 1. init bootstraps state.json with scaffold pre-completed.
        proc = _run([str(BIN / "state.py"), "init", str(self.idea), str(self.proj)])
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(proc.stdout.strip(), "plan")

        state = self._state()
        self.assertEqual(state["project"], "demo-proj")
        self.assertEqual(state["current_step"], "plan")
        self.assertIn("scaffold", state["completed"])
        self.assertIn("scaffold", state["step_entered_at"])
        self.assertIn("plan", state["step_entered_at"])

        # 2. mark plan done with an output, current_step advances.
        proc = _run([str(BIN / "state.py"), "mark", str(self.proj), "plan", "done", "plan.json"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "implement")

        state = self._state()
        self.assertIn("plan", state["completed"])
        self.assertEqual(state["outputs"]["plan"], "plan.json")
        self.assertIsNone(state["last_error"])

        # 3. addtok accumulates the per-provider counters.
        proc = _run([str(BIN / "state.py"), "addtok", str(self.proj), "zai", "100", "200"])
        self.assertEqual(proc.returncode, 0)
        proc = _run([str(BIN / "state.py"), "addtok", str(self.proj), "zai", "50", "75"])
        self.assertEqual(proc.returncode, 0)

        state = self._state()
        self.assertEqual(state["tokens"]["zai"], {"in": 150, "out": 275})

        # 4. state-events.jsonl was appended on every save. Each save = one line.
        events_path = self.tmp / "logs" / "state-events.jsonl"
        self.assertTrue(events_path.exists(), "state-events.jsonl should be written by state.py save()")
        lines = [ln for ln in events_path.read_text().splitlines() if ln.strip()]
        # init writes 1, mark writes 1, two addtok writes write 2 → 4 events total.
        self.assertGreaterEqual(len(lines), 4, f"expected ≥4 events, got {len(lines)}")
        # Last event reflects post-addtok state.
        last = json.loads(lines[-1])
        self.assertEqual(last["project"], "demo-proj")
        self.assertEqual(last["step"], "implement")
        self.assertIsNone(last["last_error"])

    def test_mark_error_records_message_without_advancing(self) -> None:
        _run([str(BIN / "state.py"), "init", str(self.idea), str(self.proj)])
        proc = _run([str(BIN / "state.py"), "mark", str(self.proj), "plan", "error", "boom"])
        self.assertEqual(proc.returncode, 0)
        # Error path keeps current_step where it was — the step itself failed.
        self.assertEqual(proc.stdout.strip(), "plan")
        self.assertEqual(self._state()["last_error"], "boom")

    def test_mark_error_on_completed_project_returns_to_failed_step(self) -> None:
        _run([str(BIN / "state.py"), "init", str(self.idea), str(self.proj)])
        _run([str(BIN / "state.py"), "mark", str(self.proj), "plan", "done", "plan.json"])
        _run([str(BIN / "state.py"), "mark", str(self.proj), "implement", "done"])
        _run([str(BIN / "state.py"), "mark", str(self.proj), "verify", "done", "report.md"])
        self.assertEqual(self._state()["current_step"], "done")

        proc = _run([str(BIN / "state.py"), "mark", str(self.proj), "verify", "error", "verification failed"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "verify")
        state = self._state()
        self.assertEqual(state["current_step"], "verify")
        self.assertEqual(state["last_error"], "verification failed")

    def test_addusage_accumulates_usage_file_tokens(self) -> None:
        _run([str(BIN / "state.py"), "init", str(self.idea), str(self.proj)])
        usage = self.tmp / "usage.json"
        usage.write_text(json.dumps({
            "provider": "ollama",
            "model": "qwen3:4b",
            "in": 12,
            "out": 8,
            "project": "demo-proj",
            "step": "review",
        }))
        proc = _run([str(BIN / "state.py"), "addusage", str(self.proj), str(usage)])
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(self._state()["tokens"]["ollama"], {"in": 12, "out": 8})


class StatsParsingTest(unittest.TestCase):
    """bin/stats over a fully synthetic fixture must produce predictable numbers."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="aiwf-stats-"))
        self.addCleanup(shutil.rmtree, self.tmp)

        # Layout: projects/{alpha,beta} with state.json, logs/{state-events,tokens,costs}.
        (self.tmp / "projects" / "alpha").mkdir(parents=True)
        (self.tmp / "projects" / "beta").mkdir(parents=True)
        (self.tmp / "logs").mkdir()

        now = datetime.now(timezone.utc)
        t0 = (now - timedelta(hours=2)).isoformat()
        t1 = (now - timedelta(hours=1)).isoformat()
        t2 = now.isoformat()

        (self.tmp / "projects" / "alpha" / "state.json").write_text(json.dumps({
            "project": "alpha",
            "current_step": "done",
            "completed": ["scaffold", "plan", "implement", "verify"],
            "step_entered_at": {
                "scaffold": t0, "plan": t0, "implement": t1, "verify": t2,
            },
            "updated_at": t2,
            "tokens": {"zai": {"in": 100, "out": 200}},
            "last_error": None,
        }))
        (self.tmp / "projects" / "beta" / "state.json").write_text(json.dumps({
            "project": "beta",
            "current_step": "implement",
            "completed": ["scaffold", "plan"],
            "step_entered_at": {"scaffold": t0, "plan": t0, "implement": t2},
            "updated_at": t2,
            "tokens": {},
            "last_error": "step implement failed",
        }))

        # Three error events for plan, two oks for plan, one ok for scaffold (alpha+beta).
        events = [
            {"ts": t0, "project": "alpha", "step": "plan",      "completed": ["scaffold"],                    "last_error": None},
            {"ts": t0, "project": "alpha", "step": "plan",      "completed": ["scaffold"],                    "last_error": "boom"},
            {"ts": t1, "project": "alpha", "step": "implement", "completed": ["scaffold", "plan"],            "last_error": None},
            {"ts": t2, "project": "alpha", "step": "done",      "completed": ["scaffold", "plan", "implement", "verify"], "last_error": None},
            {"ts": t0, "project": "beta",  "step": "plan",      "completed": ["scaffold"],                    "last_error": "boom2"},
            {"ts": t2, "project": "beta",  "step": "implement", "completed": ["scaffold", "plan"],            "last_error": "step implement failed"},
        ]
        (self.tmp / "logs" / "state-events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n"
        )

        # Two token calls: one zai, one ollama, both within the 7-day window.
        tokens = [
            {"ts": t0, "provider": "zai",    "model": "glm-4.6",          "in": 100, "out": 200, "usd": 0.0, "sec": 1.0},
            {"ts": t2, "provider": "ollama", "model": "qwen2.5-coder",    "in": 500, "out":  50, "usd": 0.0, "sec": 9.5},
        ]
        (self.tmp / "logs" / "tokens.jsonl").write_text(
            "\n".join(json.dumps(t) for t in tokens) + "\n"
        )

        # Cost rates: zai paid, ollama free.
        (self.tmp / "logs" / "costs.json").write_text(json.dumps({
            "zai":    {"in_per_million": 0.6, "out_per_million": 2.2},
            "ollama": {"in_per_million": 0.0, "out_per_million": 0.0},
        }))

    def _bin_stats_pointing_at_fixture(self) -> subprocess.CompletedProcess:
        """bin/stats computes ROOT = parent.parent of __file__. Easiest way to
        retarget it: copy the script into <fixture>/bin/stats and run it from there.
        No monkey-patching, no path tricks — the script behaves identically to
        production, just rooted at our tempdir.
        """
        fixture_bin = self.tmp / "bin"
        fixture_bin.mkdir(exist_ok=True)
        shutil.copy(BIN / "stats", fixture_bin / "stats")
        os.chmod(fixture_bin / "stats", 0o755)
        return _run([sys.executable, str(fixture_bin / "stats"), "--json"])

    def test_stats_json_against_fixture(self) -> None:
        proc = self._bin_stats_pointing_at_fixture()
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout)

        # Project listing.
        slugs = {p["project"] for p in payload["projects"]}
        self.assertEqual(slugs, {"alpha", "beta"})

        # Outcomes: scaffold succeeded twice (alpha, beta), plan succeeded twice,
        # implement succeeded once (alpha), verify once (alpha). Errors: 2 on plan,
        # 1 on implement.
        outcomes = payload["step_outcomes"]
        self.assertEqual(outcomes["scaffold"]["ok"],  2)
        self.assertEqual(outcomes["scaffold"]["err"], 0)
        self.assertEqual(outcomes["plan"]["ok"],      2)
        self.assertEqual(outcomes["plan"]["err"],     2)
        self.assertEqual(outcomes["implement"]["ok"], 1)
        self.assertEqual(outcomes["implement"]["err"], 1)
        self.assertEqual(outcomes["verify"]["ok"],    1)

        # Provider summary cost: zai = 100 * 0.6/1M + 200 * 2.2/1M = 0.00050.
        provs = {p["provider"]: p for p in payload["providers"]}
        self.assertAlmostEqual(provs["zai"]["usd"],  0.0005, places=6)
        self.assertAlmostEqual(provs["ollama"]["usd"], 0.0,    places=6)

        # Recent errors: at least 3 distinct error records visible.
        errs = payload["recent_errors"]
        self.assertGreaterEqual(len(errs), 3)


class DispatcherConfigTest(unittest.TestCase):
    """bin/ai config helpers must support local-first routing without API calls."""

    def test_dotenv_log_file_resolves_after_load_env(self) -> None:
        ai = _load_bin_module("ai")
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="aiwf-ai-"))
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / ".env").write_text("export LOG_FILE=custom/tokens.jsonl\n")

        with mock.patch.object(ai, "ROOT", tmp), mock.patch.dict(os.environ, {}, clear=True):
            ai.load_env()
            self.assertEqual(ai.resolve_log_path(), tmp / "custom" / "tokens.jsonl")

    def test_select_model_prefers_role_specific_ollama_model(self) -> None:
        ai = _load_bin_module("ai")
        env = {
            "AIWF_STEP": "review",
            "OLLAMA_MODEL": "qwen2.5-coder:14b",
            "OLLAMA_REVIEW_MODEL": "qwen2.5-coder:7b",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(ai.select_model("ollama"), "qwen2.5-coder:7b")
            self.assertEqual(ai.select_model("ollama", "qwen3:4b"), "qwen3:4b")

    def test_select_model_accepts_lm_studio_alias_prefix(self) -> None:
        ai = _load_bin_module("ai")
        env = {
            "AIWF_STEP": "review",
            "LM_STUDIO_MODEL": "google/gemma-4-31b",
            "LM_STUDIO_REVIEW_MODEL": "google/gemma-4-31b-review",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(ai.select_model("lmstudio"), "google/gemma-4-31b-review")

    def test_usage_record_includes_project_and_step(self) -> None:
        ai = _load_bin_module("ai")
        env = {"AIWF_PROJECT": "demo-proj", "AIWF_STEP": "plan"}
        with mock.patch.dict(os.environ, env, clear=True):
            rec = ai.usage_record("ollama", "qwen3:4b", 10, 5, 0.0, 1.25)
        self.assertEqual(rec["project"], "demo-proj")
        self.assertEqual(rec["step"], "plan")
        self.assertEqual(rec["provider"], "ollama")
        self.assertEqual(rec["model"], "qwen3:4b")
        self.assertEqual(rec["in"], 10)
        self.assertEqual(rec["out"], 5)


class PlanValidationTest(unittest.TestCase):
    """plan.json validation protects impl.sh from writing outside project dirs."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="aiwf-plan-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.proj = self.tmp / "projects" / "demo-proj"
        self.proj.mkdir(parents=True)
        (self.proj / "tree.json").write_text(json.dumps({
            "project": "demo-proj",
            "paths": ["README.md", "src/main.py"],
        }))

    def _write_plan(self, doc: dict) -> pathlib.Path:
        path = self.proj / "plan.json"
        path.write_text(json.dumps(doc))
        return path

    def _validate(self, path: pathlib.Path) -> subprocess.CompletedProcess:
        return _run([str(BIN / "validate_plan.py"), str(self.proj), str(path)])

    def test_accepts_valid_plan(self) -> None:
        plan = self._write_plan({
            "project": "demo-proj",
            "decisions": "Use Python stdlib.",
            "tasks": [
                {"path": "README.md", "intent": "Document how to run.", "deps": []},
                {"path": "src/main.py", "intent": "Print hello.", "deps": ["README.md"]},
            ],
        })
        proc = self._validate(plan)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    def test_rejects_path_traversal(self) -> None:
        plan = self._write_plan({
            "project": "demo-proj",
            "tasks": [{"path": "../evil.py", "intent": "Write outside.", "deps": []}],
        })
        proc = self._validate(plan)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unsafe path", proc.stderr)

    def test_rejects_project_mismatch(self) -> None:
        plan = self._write_plan({
            "project": "other-proj",
            "tasks": [{"path": "README.md", "intent": "Document.", "deps": []}],
        })
        proc = self._validate(plan)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("project mismatch", proc.stderr)


class SearchToolTest(unittest.TestCase):
    """SearXNG helper should target the local LAN instance by default."""

    def test_build_search_url_uses_default_lan_host_and_json_format(self) -> None:
        search = _load_bin_module("search")
        with mock.patch.dict(os.environ, {}, clear=True):
            url = search.build_search_url("local llm routing")
        self.assertTrue(url.startswith("http://192.168.0.5:30053/search?"), url)
        self.assertIn("format=json", url)
        self.assertIn("q=local+llm+routing", url)


class WorkflowSmokeTest(unittest.TestCase):
    """Three tiny fixture-backed projects exercise scaffold -> plan -> impl -> verify."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="aiwf-smoke-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.queue = self.tmp / "queue"
        self.projects = self.tmp / "projects"
        self.logs = self.tmp / "logs"
        self.fixtures = self.tmp / "fixtures"
        for p in (self.queue, self.projects, self.logs, self.fixtures):
            p.mkdir(parents=True)

    def _write_fixture(self, slug: str, paths: list[str], tasks: list[dict], files: dict[str, str]) -> pathlib.Path:
        root = self.fixtures / slug
        (root / "files").mkdir(parents=True)
        (root / "tree.json").write_text(json.dumps({
            "project": slug,
            "summary": f"Fixture project {slug}",
            "paths": paths,
        }))
        (root / "plan.json").write_text(json.dumps({
            "project": slug,
            "decisions": "Fixture-backed smoke plan for testing the workflow without model calls.",
            "tasks": tasks,
        }))
        for rel, body in files.items():
            path = root / "files" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
        idea = self.queue / f"{slug}.md"
        idea.write_text(f"# Project - {slug}\nFixture workflow smoke test.\n")
        return idea

    def _run_workflow(self, slug: str, paths: list[str], tasks: list[dict], files: dict[str, str]) -> pathlib.Path:
        idea = self._write_fixture(slug, paths, tasks, files)
        env = {
            **os.environ,
            "AI_FIXTURE_ROOT": str(self.fixtures),
            "LOG_FILE": str(self.logs / "tokens.jsonl"),
            "SCAFFOLD_PROVIDER": "fixture",
            "PLAN_PROVIDER": "fixture",
            "IMPL_PROVIDER": "fixture",
            "REVIEW_PROVIDER": "fixture",
        }

        proc = subprocess.run(
            [str(BIN / "scaffold.sh"), str(idea), str(self.projects)],
            capture_output=True, text=True, env=env, check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        project_dir = self.projects / slug

        for cmd in (
            [str(BIN / "state.py"), "init", str(idea), str(project_dir)],
            [str(BIN / "plan.sh"), str(project_dir)],
            [str(BIN / "impl.sh"), str(project_dir)],
            [str(BIN / "verify.sh"), str(project_dir)],
        ):
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
            self.assertEqual(proc.returncode, 0, msg=f"{cmd}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")

        state = json.loads((project_dir / "state.json").read_text())
        self.assertEqual(state["current_step"], "done")
        self.assertEqual(state["completed"], ["scaffold", "plan", "implement", "verify"])
        self.assertIn("fixture", state["tokens"])
        self.assertGreater(state["tokens"]["fixture"]["in"], 0)
        self.assertGreater(state["tokens"]["fixture"]["out"], 0)
        self.assertIn("## Result: PASS", (project_dir / "report.md").read_text())

        token_lines = [json.loads(line) for line in (self.logs / "tokens.jsonl").read_text().splitlines()]
        self.assertTrue(any(r.get("project") == slug and r.get("step") == "scaffold" for r in token_lines))
        self.assertTrue(any(r.get("project") == slug and r.get("step") == "plan" for r in token_lines))
        self.assertTrue(any(r.get("project") == slug and r.get("step") == "implement" for r in token_lines))
        self.assertTrue((self.logs / "costs.json").exists(), "cost snapshots should follow LOG_FILE's directory")
        return project_dir

    def test_python_project_uses_full_workflow(self) -> None:
        project_dir = self._run_workflow(
            "smoke-python",
            ["README.md", "src/main.py"],
            [
                {"path": "README.md", "intent": "Document the Python smoke app.", "deps": []},
                {"path": "src/main.py", "intent": "Print a smoke-test greeting.", "deps": ["README.md"]},
            ],
            {
                "README.md": "# smoke-python\n\nRun `python3 src/main.py`.\n",
                "src/main.py": "print(\"hello from smoke-python\")\n",
            },
        )
        self.assertEqual((project_dir / "src" / "main.py").read_text(), "print(\"hello from smoke-python\")\n")

    def test_shell_project_uses_full_workflow(self) -> None:
        project_dir = self._run_workflow(
            "smoke-shell",
            ["README.md", "run.sh"],
            [
                {"path": "README.md", "intent": "Document the shell smoke script.", "deps": []},
                {"path": "run.sh", "intent": "Print a smoke-test greeting with safe shell settings.", "deps": ["README.md"]},
            ],
            {
                "README.md": "# smoke-shell\n\nRun `bash run.sh`.\n",
                "run.sh": "#!/usr/bin/env bash\nset -euo pipefail\necho \"hello from smoke-shell\"\n",
            },
        )
        self.assertIn("[OK] bash -n `run.sh`", (project_dir / "report.md").read_text())

    def test_go_project_uses_full_workflow(self) -> None:
        project_dir = self._run_workflow(
            "smoke-go",
            ["README.md", "go.mod", "cmd/smoke/main.go"],
            [
                {"path": "README.md", "intent": "Document the Go smoke binary.", "deps": []},
                {"path": "go.mod", "intent": "Define a tiny Go module.", "deps": []},
                {"path": "cmd/smoke/main.go", "intent": "Print a smoke-test greeting.", "deps": ["go.mod"]},
            ],
            {
                "README.md": "# smoke-go\n\nRun `go run ./cmd/smoke`.\n",
                "go.mod": "module smoke-go\n\ngo 1.21\n",
                "cmd/smoke/main.go": "package main\n\nimport \"fmt\"\n\nfunc main() {\n\tfmt.Println(\"hello from smoke-go\")\n}\n",
            },
        )
        report = (project_dir / "report.md").read_text()
        self.assertIn("[OK] go test ./...", report)


class ScaffoldPromptShapeTest(unittest.TestCase):
    """scaffold.sh must keep the output contract after long project ideas."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="aiwf-scaffold-prompt-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        for rel in ("bin", "prompts", "queue", "projects", "lib/schema"):
            (self.tmp / rel).mkdir(parents=True, exist_ok=True)

        shutil.copy(BIN / "scaffold.sh", self.tmp / "bin" / "scaffold.sh")
        shutil.copy(BIN / "materialize.py", self.tmp / "bin" / "materialize.py")
        shutil.copy(REPO / "prompts" / "scaffold.txt", self.tmp / "prompts" / "scaffold.txt")
        shutil.copy(REPO / "lib" / "schema" / "tree.schema.json", self.tmp / "lib" / "schema" / "tree.schema.json")
        os.chmod(self.tmp / "bin" / "scaffold.sh", 0o755)
        os.chmod(self.tmp / "bin" / "materialize.py", 0o755)

        (self.tmp / "bin" / "ai").write_text("""#!/usr/bin/env bash
set -euo pipefail
prompt="$(cat)"
printf '%s' "$prompt" > "$CAPTURE_PROMPT"
usage_path=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --usage-file)
            shift
            usage_path="${1:-}"
            ;;
    esac
    shift || break
done
if [ -n "$usage_path" ]; then
    printf '{"provider":"fake","model":"fake","in":1,"out":1}\\n' > "$usage_path"
fi
printf '{"project":"ignored","summary":"fake scaffold","paths":["README.md","src/","src/app.js"]}\\n'
""")
        os.chmod(self.tmp / "bin" / "ai", 0o755)

    def test_output_contract_is_after_long_idea_body(self) -> None:
        idea = self.tmp / "queue" / "long-idea.md"
        idea.write_text("# Long idea\n\n" + ("Detailed product requirement text.\n" * 1000))
        capture = self.tmp / "captured-prompt.txt"

        env = {
            **os.environ,
            "CAPTURE_PROMPT": str(capture),
            "SCAFFOLD_PROVIDER": "fake",
        }
        proc = subprocess.run(
            [str(self.tmp / "bin" / "scaffold.sh"), str(idea), str(self.tmp / "projects")],
            capture_output=True, text=True, env=env, check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

        prompt = capture.read_text()
        idea_idx = prompt.find("PROJECT IDEA:")
        contract_idx = prompt.rfind("You are a scaffolding generator.")
        slug_idx = prompt.rfind("The project slug MUST be exactly: long-idea")
        self.assertGreaterEqual(idea_idx, 0)
        self.assertGreater(contract_idx, idea_idx)
        self.assertGreater(slug_idx, contract_idx)
        self.assertIn('"paths": [', prompt[contract_idx:])
        self.assertLess(len(prompt) - contract_idx, 1200)


class PlanPromptContractTest(unittest.TestCase):
    """plan.txt must advertise the validator's length limits."""

    def test_plan_prompt_mentions_schema_length_limits(self) -> None:
        prompt = (REPO / "prompts" / "plan.txt").read_text()
        self.assertIn("intent MUST be 1..1000 characters", prompt)
        self.assertIn("decisions MUST be <=2000 characters", prompt)


class OrchestrateExitStatusTest(unittest.TestCase):
    """orchestrate.sh should continue batches but still report any project failure."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="aiwf-orch-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "bin").mkdir()
        (self.tmp / "queue").mkdir()
        shutil.copy(BIN / "orchestrate.sh", self.tmp / "bin" / "orchestrate.sh")
        os.chmod(self.tmp / "bin" / "orchestrate.sh", 0o755)
        (self.tmp / "queue" / "failing-project.md").write_text("# Project - failing-project\n")

        (self.tmp / "bin" / "scaffold.sh").write_text("""#!/usr/bin/env bash
set -euo pipefail
idea="$1"
projects="$2"
slug="$(basename "$idea" .md)"
pd="$projects/$slug"
mkdir -p "$pd"
printf '{"project":"%s","paths":["README.md"]}\\n' "$slug" > "$pd/tree.json"
printf '{"current_step":"verify"}\\n' > "$pd/state.json"
""")
        (self.tmp / "bin" / "state.py").write_text("""#!/usr/bin/env python3
import json
import pathlib
import sys

cmd = sys.argv[1]
if cmd == "get":
    pd = pathlib.Path(sys.argv[2])
    key = sys.argv[3]
    print(json.loads((pd / "state.json").read_text())[key])
elif cmd == "mark":
    sys.exit(0)
elif cmd == "init":
    sys.exit(0)
else:
    sys.exit(f"unexpected state.py command: {cmd}")
""")
        (self.tmp / "bin" / "verify.sh").write_text("""#!/usr/bin/env bash
exit 1
""")
        for script in ("scaffold.sh", "state.py", "verify.sh"):
            os.chmod(self.tmp / "bin" / script, 0o755)

    def test_returns_nonzero_when_a_project_step_fails(self) -> None:
        proc = _run(
            [str(self.tmp / "bin" / "orchestrate.sh"), str(self.tmp / "queue" / "failing-project.md")],
            cwd=str(self.tmp),
        )
        self.assertNotEqual(proc.returncode, 0, msg=f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        self.assertIn("verify failed, state preserved", proc.stderr)

    def test_reports_scaffold_failure_without_tree_json_followup(self) -> None:
        (self.tmp / "bin" / "scaffold.sh").write_text("""#!/usr/bin/env bash
set -euo pipefail
echo "[stub] scaffold failed" >&2
exit 7
""")
        os.chmod(self.tmp / "bin" / "scaffold.sh", 0o755)

        proc = _run(
            [str(self.tmp / "bin" / "orchestrate.sh"), str(self.tmp / "queue" / "failing-project.md")],
            cwd=str(self.tmp),
        )
        self.assertNotEqual(proc.returncode, 0, msg=f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        self.assertIn("failing-project: scaffold failed, state not initialised", proc.stderr)
        self.assertNotIn("no tree.json", proc.stderr)

    def test_loads_dotenv_for_child_stages_but_preserves_explicit_env(self) -> None:
        (self.tmp / ".env").write_text("export AIWF_TEST_FROM_DOTENV=from_dotenv\n")
        (self.tmp / "bin" / "verify.sh").write_text("""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "${AIWF_TEST_FROM_DOTENV:-missing}" > "$1/dotenv-value.txt"
exit 1
""")
        os.chmod(self.tmp / "bin" / "verify.sh", 0o755)

        proc = _run(
            [str(self.tmp / "bin" / "orchestrate.sh"), str(self.tmp / "queue" / "failing-project.md")],
            cwd=str(self.tmp),
        )
        self.assertNotEqual(proc.returncode, 0)
        value_path = self.tmp / "projects" / "failing-project" / "dotenv-value.txt"
        self.assertEqual(value_path.read_text().strip(), "from_dotenv")

        value_path.unlink()
        env = {**os.environ, "AIWF_TEST_FROM_DOTENV": "from_shell"}
        proc = _run(
            [str(self.tmp / "bin" / "orchestrate.sh"), str(self.tmp / "queue" / "failing-project.md")],
            cwd=str(self.tmp),
            env=env,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(value_path.read_text().strip(), "from_shell")


class SearchBackendTest(unittest.TestCase):
    """bin/search dispatcher: auto must prefer SearXNG, fall back to Brave."""

    def setUp(self) -> None:
        # Import bin/search via SourceFileLoader since it has no .py suffix.
        import importlib.util
        loader = importlib.util.spec_from_loader(
            "search_mod",
            importlib.machinery.SourceFileLoader("search_mod", str(BIN / "search")),
        )
        self.mod = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(self.mod)
        # Snapshot originals so we can monkey-patch safely.
        self._orig_searxng = self.mod.searxng_search
        self._orig_brave = self.mod.brave_search
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        self.mod.searxng_search = self._orig_searxng
        self.mod.brave_search = self._orig_brave

    def test_auto_uses_searxng_when_it_returns_results(self) -> None:
        sample = [{"title": "x", "url": "https://x", "content": "c", "engine": "google"}]
        self.mod.searxng_search = lambda q, *, host, limit, timeout: sample
        self.mod.brave_search   = lambda q, *, limit, timeout: self.fail("brave must not be called")
        results, backend, notes = self.mod.do_search("q", "auto", host=None, limit=5, timeout=5)
        self.assertEqual(backend, "searxng")
        self.assertEqual(results, sample)
        self.assertEqual(notes, [])

    def test_auto_falls_back_to_brave_when_searxng_empty(self) -> None:
        brave_sample = [{"title": "b", "url": "https://b", "content": "c", "engine": "brave"}]
        self.mod.searxng_search = lambda q, *, host, limit, timeout: []
        self.mod.brave_search   = lambda q, *, limit, timeout: brave_sample
        results, backend, notes = self.mod.do_search("q", "auto", host=None, limit=5, timeout=5)
        self.assertEqual(backend, "brave")
        self.assertEqual(results, brave_sample)
        self.assertEqual(len(notes), 1)
        self.assertIn("0 results", notes[0])

    def test_auto_falls_back_to_brave_when_searxng_raises(self) -> None:
        import urllib.error
        brave_sample = [{"title": "b", "url": "https://b", "content": "c", "engine": "brave"}]
        def boom(*a, **k):
            raise urllib.error.URLError("no route to host")
        self.mod.searxng_search = boom
        self.mod.brave_search   = lambda q, *, limit, timeout: brave_sample
        results, backend, notes = self.mod.do_search("q", "auto", host=None, limit=5, timeout=5)
        self.assertEqual(backend, "brave")
        self.assertEqual(results, brave_sample)
        self.assertEqual(len(notes), 1)
        self.assertIn("URLError", notes[0])

    def test_brave_without_key_raises_runtime_error(self) -> None:
        # Save and clear BRAVE_API_SEARCH for this test, then put it back.
        orig = os.environ.pop("BRAVE_API_SEARCH", None)
        self.addCleanup(lambda: os.environ.__setitem__("BRAVE_API_SEARCH", orig) if orig is not None else None)
        with self.assertRaises(RuntimeError) as ctx:
            self.mod.brave_search("q", limit=1, timeout=1)
        self.assertIn("BRAVE_API_SEARCH", str(ctx.exception))


if __name__ == "__main__":
    import importlib.machinery  # noqa: F401  (used by SearchBackendTest at runtime)
    unittest.main(verbosity=2)
