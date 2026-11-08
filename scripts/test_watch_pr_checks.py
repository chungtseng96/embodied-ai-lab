import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import watch_pr_checks as watcher

SHA = "a" * 40
OTHER_SHA = "b" * 40
SCRIPT = Path(__file__).with_name("watch_pr_checks.py")
FAKE_GH = """#!{python}
import json
import os
from pathlib import Path
import sys
import time
root = Path(os.environ["FAKE_GH_DIR"])
steps = json.loads((root / "steps.json").read_text())
index_path = root / "index"
index = int(index_path.read_text()) if index_path.exists() else 0
with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
endpoint = sys.argv[4]
responses = json.loads((root / "runs.json").read_text())
if "/actions/workflows/" in endpoint:
    override = root / "workflow-list.json"
    if override.exists():
        step = json.loads(override.read_text())
    else:
        ids = json.loads((root / "last-checks.json").read_text())
        step = dict(data=[dict(workflow_runs=[responses[str(i)]["data"] for i in ids])])
elif "/attempts/" in endpoint:
    override = root / "jobs.json"
    run_id = int(endpoint.split("/runs/")[1].split("/")[0])
    attempt = int(endpoint.split("/attempts/")[1].split("/")[0])
    step = json.loads(override.read_text()) if override.exists() else dict(data=[dict(jobs=[dict(
        name="check", run_id=run_id, run_attempt=attempt,
        head_sha="a" * 40, status="completed", conclusion="success",
        check_run_url="https://api.github.com/repos/owner/repo/check-runs/" + str(run_id))])])
elif "/actions/runs/" in endpoint:
    step = responses[endpoint.rsplit("/", 1)[1]]
else:
    step = steps[index % len(steps)]
    index_path.write_text(str(index + 1))
    if "/check-runs?" in endpoint:
        ids = sorted(set(run["id"] for page in step.get("data", [])
                         for run in page.get("check_runs", []) if isinstance(run, dict)))
        (root / "last-checks.json").write_text(json.dumps(ids))
if "sleep" in step:
    (root / "gh-pid").write_text(str(os.getpid()))
    time.sleep(step["sleep"])
print(step.get("raw", json.dumps(step.get("data"))))
print(step.get("error", ""), file=sys.stderr)
sys.exit(step.get("exit", 0))
"""


def head(sha=SHA):
    return {"data": {"head": {"sha": sha}}}


def gate(run_id=1, status="completed", conclusion="success", **overrides):
    run = {
        "id": run_id,
        "name": "check",
        "app": {"slug": "github-actions"},
        "details_url": f"https://github.com/owner/repo/actions/runs/{run_id}/job/{run_id + 100}",
        "head_sha": SHA,
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-10-07T01:00:00Z",
        "completed_at": "2026-10-07T01:01:00Z" if status == "completed" else None,
    }
    run.update(overrides)
    return run


def checks(*runs):
    return {"data": [{"check_runs": list(runs)}]}


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        gh = self.root / "gh"
        gh.write_text(FAKE_GH.format(python=sys.executable))
        gh.chmod(0o700)
        self.env = dict(
            os.environ,
            PATH=f"{self.root}{os.pathsep}{os.environ['PATH']}",
            TMPDIR=str(self.root),
            FAKE_GH_DIR=str(self.root),
        )
        self.command = [
            sys.executable,
            str(SCRIPT),
            "--repo",
            "owner/repo",
            "--pr",
            "17",
            "--head-sha",
            SHA,
            "--interval-seconds",
            "0.01",
            "--timeout-seconds",
            "5",
        ]

    def configure(self, steps):
        (self.root / "index").unlink(missing_ok=True)
        (self.root / "steps.json").write_text(json.dumps(steps))
        runs = {
            str(run_id): {
                "data": {
                    "id": run_id,
                    "path": ".github/workflows/ci.yml",
                    "head_sha": SHA,
                    "event": "pull_request",
                    "status": "completed",
                    "conclusion": "success",
                    "run_attempt": 1,
                }
            }
            for run_id in (1, 2)
        }
        (self.root / "runs.json").write_text(json.dumps(runs))

    def run_watch(self, steps, extra=()):
        self.configure(steps)
        return subprocess.run(
            self.command + list(extra),
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def calls(self):
        path = self.root / "calls.jsonl"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def test_pending_then_success_and_read_only_pinned_arguments(self):
        result = self.run_watch(
            [
                head(),
                checks(gate(status="in_progress", conclusion=None)),
                head(),
                head(),
                checks(gate(run_id=2)),
                head(),
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pending", result.stdout)
        self.assertIn("success (CI only)", result.stdout)
        self.assertGreater(len(self.calls()), 8)
        self.assertIn("actions/workflows/ci.yml/runs?head_sha=", self.calls()[2][3])
        self.assertEqual(self.calls()[-1][3], "repos/owner/repo/pulls/17")
        for call in self.calls():
            self.assertEqual(call[:3], ["api", "--method", "GET"])
        self.assertEqual(
            self.calls()[1],
            [
                "api",
                "--method",
                "GET",
                f"repos/owner/repo/commits/{SHA}/check-runs?per_page=100&filter=all",
                "--paginate",
                "--slurp",
            ],
        )

    def test_foreign_same_named_app_cannot_mask_failure_or_success(self):
        for actual in ("failure", "success"):
            for app in ({"slug": "other-app"}, None, {}):
                with self.subTest(actual=actual, app=app):
                    result = self.run_watch(
                        [
                            head(),
                            checks(gate(conclusion=actual), gate(2, app=app)),
                            head(),
                        ]
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("uncertain CI Gate provenance", result.stderr)
                    self.assertNotIn("success", result.stdout)
                    if (self.root / "index").exists():
                        (self.root / "index").unlink()

    def test_foreign_workflow_and_malformed_run_fail_closed(self):
        variants = [
            {"path": ".github/workflows/other.yml"},
            {"head_sha": OTHER_SHA},
            {"event": "workflow_dispatch"},
            {"id": 999},
            {"id": True},
            {"path": None},
        ]
        for overrides in variants:
            with self.subTest(overrides=overrides):
                self.configure(
                    [head(), checks(gate(conclusion="failure"), gate(2)), head()]
                )
                runs = json.loads((self.root / "runs.json").read_text())
                (self.root / "workflow-list.json").write_text(
                    json.dumps(
                        {
                            "data": [
                                {
                                    "workflow_runs": [
                                        runs["1"]["data"],
                                        runs["2"]["data"],
                                    ]
                                }
                            ]
                        }
                    )
                )
                runs["2"]["data"].update(overrides)
                (self.root / "runs.json").write_text(json.dumps(runs))
                result = subprocess.run(
                    self.command,
                    env=self.env,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("uncertain CI Gate provenance", result.stderr)
                self.assertNotIn("success", result.stdout)
                (self.root / "index").unlink()

    def test_invalid_details_url_never_queries_foreign_endpoint(self):
        urls = [
            None,
            "https://evil.example/owner/repo/actions/runs/2",
            "https://github.com/other/repo/actions/runs/2/job/102",
            "https://github.com/owner/repo/actions/runs/2?query=1",
            "https://github.com/owner/repo/actions/runs/not-a-number",
        ]
        for url in urls:
            with self.subTest(url=url):
                result = self.run_watch([head(), checks(gate(details_url=url)), head()])
                self.assertEqual(result.returncode, 1)
                self.assertIn("details_url", result.stderr)
                self.assertFalse(
                    any(
                        not call[3].startswith("repos/owner/repo/")
                        for call in self.calls()
                    )
                )
                (self.root / "index").unlink()

    def test_workflow_api_error_is_terminal(self):
        self.configure([head(), checks(gate()), head()])
        runs = json.loads((self.root / "runs.json").read_text())
        runs["1"]["exit"] = 1
        (self.root / "runs.json").write_text(json.dumps(runs))
        result = subprocess.run(
            self.command,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("gh API failed", result.stderr)
        self.assertNotIn("success", result.stdout)

    def run_configured(self, extra=()):
        return subprocess.run(
            self.command + list(extra),
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    def test_old_success_new_attempt_queued_without_new_gate(self):
        self.configure([head(), checks(gate()), head()])
        runs = json.loads((self.root / "runs.json").read_text())
        runs["1"]["data"].update(run_attempt=2, status="queued", conclusion=None)
        (self.root / "runs.json").write_text(json.dumps(runs))
        result = self.run_configured(["--timeout-seconds", "1"])
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertNotIn("success", result.stdout)

    def test_successful_gate_ignores_informational_workflow_result(self):
        for status, conclusion in (
            ("completed", "failure"),
            ("completed", "cancelled"),
            ("in_progress", None),
        ):
            with self.subTest(status=status, conclusion=conclusion):
                self.configure([head(), checks(gate()), head()])
                runs = json.loads((self.root / "runs.json").read_text())
                runs["1"]["data"].update(status=status, conclusion=conclusion)
                (self.root / "runs.json").write_text(json.dumps(runs))
                result = self.run_configured()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("CI Gate success (CI only)", result.stdout)

    def test_current_attempt_gate_result_controls_unfinished_workflow(self):
        for status, conclusion, expected in (
            ("completed", "failure", 1),
            ("completed", "skipped", 1),
            ("in_progress", None, 124),
        ):
            with self.subTest(status=status, conclusion=conclusion):
                self.configure(
                    [head(), checks(gate(status=status, conclusion=conclusion)), head()]
                )
                runs = json.loads((self.root / "runs.json").read_text())
                runs["1"]["data"].update(status="in_progress", conclusion=None)
                (self.root / "runs.json").write_text(json.dumps(runs))
                (self.root / "jobs.json").write_text(
                    json.dumps(
                        {
                            "data": [
                                {
                                    "jobs": [
                                        {
                                            "name": "check",
                                            "run_id": 1,
                                            "run_attempt": 1,
                                            "head_sha": SHA,
                                            "status": status,
                                            "conclusion": conclusion,
                                            "check_run_url": "https://api.github.com/repos/owner/repo/check-runs/1",
                                        }
                                    ]
                                }
                            ]
                        }
                    )
                )
                result = self.run_configured(["--timeout-seconds", "1"])
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn("success", result.stdout)
                if conclusion is not None:
                    self.assertIn(f"CI Gate concluded {conclusion}", result.stderr)

    def test_old_gate_not_in_unfinished_current_attempt(self):
        self.configure([head(), checks(gate()), head()])
        runs = json.loads((self.root / "runs.json").read_text())
        runs["1"]["data"].update(run_attempt=2, status="in_progress", conclusion=None)
        (self.root / "runs.json").write_text(json.dumps(runs))
        (self.root / "jobs.json").write_text(json.dumps({"data": [{"jobs": []}]}))
        result = self.run_configured(["--timeout-seconds", "1"])
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertNotIn("success", result.stdout)

    def test_old_gate_not_in_completed_current_attempt(self):
        self.configure([head(), checks(gate()), head()])
        runs = json.loads((self.root / "runs.json").read_text())
        runs["1"]["data"]["run_attempt"] = 2
        (self.root / "runs.json").write_text(json.dumps(runs))
        (self.root / "jobs.json").write_text(json.dumps({"data": [{"jobs": []}]}))
        result = self.run_configured(["--timeout-seconds", "1"])
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertNotIn("success", result.stdout)

    def test_new_workflow_queued_before_gate_exists(self):
        self.configure([head(), checks(gate()), head()])
        runs = json.loads((self.root / "runs.json").read_text())
        runs["2"]["data"].update(status="queued", conclusion=None)
        (self.root / "runs.json").write_text(json.dumps(runs))
        (self.root / "workflow-list.json").write_text(
            json.dumps(
                {
                    "data": [
                        {"workflow_runs": [runs["1"]["data"]]},
                        {"workflow_runs": [runs["2"]["data"]]},
                    ]
                }
            )
        )
        result = self.run_configured(["--timeout-seconds", "1"])
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertNotIn("success", result.stdout)

    def test_final_run_recheck_catches_attempt_change(self):
        args = watcher.arguments(
            ["--repo", "owner/repo", "--pr", "17", "--head-sha", SHA]
        )
        current = {
            "id": 1,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
        }
        changed = dict(current, run_attempt=2, status="queued", conclusion=None)
        with (
            mock.patch.object(
                watcher, "latest_workflow_run", side_effect=[current, changed]
            ),
            mock.patch.object(watcher, "attempt_gate_ids", return_value={1}),
            mock.patch.object(watcher, "verify_gate", return_value=current),
        ):
            self.assertEqual(
                watcher.ci_state(checks(gate())["data"], args, time.monotonic() + 2),
                "pending",
            )

    def test_initial_head_mismatch(self):
        result = self.run_watch([head(OTHER_SHA)])
        self.assertEqual(result.returncode, 1)
        self.assertIn("head changed", result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_head_changes_mid_poll_even_with_success(self):
        result = self.run_watch([head(), checks(gate()), head(OTHER_SHA)])
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("success", result.stdout)

    def test_head_changes_between_iterations(self):
        result = self.run_watch([head(), checks(), head(), head(OTHER_SHA)])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls()), 5)

    def test_check_sha_mismatch(self):
        result = self.run_watch([head(), checks(gate(head_sha=OTHER_SHA)), head()])
        self.assertEqual(result.returncode, 1)
        self.assertIn("check head_sha", result.stderr)

    def test_stale_success_newer_pending_without_start_time(self):
        result = self.run_watch(
            [head(), checks(gate(), gate(2, "queued", None, started_at=None)), head()],
            ["--timeout-seconds", "1"],
        )
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertNotIn("success", result.stdout)

    def test_stale_success_newer_failure_regardless_of_order(self):
        result = self.run_watch(
            [head(), checks(gate(2, conclusion="failure"), gate()), head()]
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("failure (check 2)", result.stderr)

    def test_newer_success_overrides_old_failure(self):
        result = self.run_watch(
            [head(), checks(gate(conclusion="failure"), gate(2)), head()]
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_missing_gate_is_pending_until_deadline(self):
        result = self.run_watch([head(), checks(), head()], ["--timeout-seconds", "1"])
        self.assertEqual(result.returncode, 124)
        self.assertNotIn("success", result.stdout)

    def test_paginated_latest_failure(self):
        result = self.run_watch(
            [
                head(),
                {
                    "data": [
                        {"check_runs": [gate()]},
                        {"check_runs": [gate(2, conclusion="cancelled")]},
                    ]
                },
                head(),
            ]
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("cancelled", result.stderr)

    def test_skipped_gate_fails_closed(self):
        result = self.run_watch([head(), checks(gate(conclusion="skipped")), head()])
        self.assertEqual(result.returncode, 1)
        self.assertIn("skipped", result.stderr)

    def test_api_auth_error_is_terminal_and_does_not_leak_stderr(self):
        result = self.run_watch([{"exit": 1, "error": "auth token SECRET"}])
        self.assertEqual(result.returncode, 1)
        self.assertIn("authentication", result.stderr)
        self.assertNotIn("SECRET", result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_malformed_json(self):
        result = self.run_watch([{"raw": "not JSON"}])
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed", result.stderr)

    def test_malformed_payloads(self):
        bad_pages = [
            None,
            [],
            {},
            [{"check_runs": None}],
            [{"check_runs": [None]}],
            [{"check_runs": [gate(id=True)]}],
            [{"check_runs": [gate(status="unknown")]}],
            [{"check_runs": [gate(status=[])]}],
            [{"check_runs": [gate(conclusion={})]}],
            [{"check_runs": [gate(conclusion=None)]}],
            [{"check_runs": [gate(started_at="bad")]}],
            [{"check_runs": [gate(completed_at=None)]}],
            [{"check_runs": [gate(), gate(conclusion="failure")]}],
        ]
        for pages in bad_pages:
            with self.subTest(pages=pages), self.assertRaises(watcher.WatchError):
                watcher.gate_state(pages, SHA)

    def test_gh_timeout_kills_owned_process(self):
        start = time.monotonic()
        result = self.run_watch([{"sleep": 10}], ["--timeout-seconds", "1"])
        self.assertEqual(result.returncode, 124)
        self.assertIn("subprocess timed out", result.stderr)
        self.assertLess(time.monotonic() - start, 2)
        with self.assertRaises(ProcessLookupError):
            os.kill(int((self.root / "gh-pid").read_text()), 0)

    def test_deadline_bounds_sleep(self):
        start = time.monotonic()
        result = self.run_watch(
            [head(), checks(), head()],
            ["--interval-seconds", "100", "--timeout-seconds", "1"],
        )
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(len(self.calls()), 4)

    def test_each_subprocess_has_capped_remaining_timeout(self):
        process = mock.Mock(returncode=0, pid=12345678)
        process.communicate.return_value = ("{}", "")
        with (
            mock.patch.object(watcher.subprocess, "Popen", return_value=process),
            mock.patch.object(watcher.os, "killpg"),
            mock.patch.object(watcher.time, "monotonic", return_value=100),
        ):
            watcher.gh_api("repos/owner/repo/pulls/17", 200)
            self.assertEqual(
                process.communicate.call_args.kwargs["timeout"],
                watcher.GH_TIMEOUT_SECONDS,
            )
            watcher.gh_api("repos/owner/repo/pulls/17", 100.5)
            self.assertEqual(process.communicate.call_args.kwargs["timeout"], 0.5)

    def test_completed_process_never_signals_group(self):
        for code, stdout in ((0, "{}"), (1, "{}"), (0, "invalid")):
            with self.subTest(code=code, stdout=stdout):
                process = mock.Mock(returncode=code, pid=12345678)
                process.communicate.return_value = (stdout, "")
                with (
                    mock.patch.object(
                        watcher.subprocess, "Popen", return_value=process
                    ),
                    mock.patch.object(
                        watcher.os, "killpg", side_effect=PermissionError
                    ) as killpg,
                ):
                    if code == 0 and stdout == "{}":
                        self.assertEqual(
                            watcher.gh_api(
                                "repos/owner/repo/pulls/17", time.monotonic() + 2
                            ),
                            {},
                        )
                    else:
                        with self.assertRaises(watcher.WatchError):
                            watcher.gh_api(
                                "repos/owner/repo/pulls/17", time.monotonic() + 2
                            )
                    killpg.assert_not_called()
                    process.kill.assert_not_called()
                    process.wait.assert_called_once_with(timeout=1)

    def test_cleanup_permission_error_preserves_timeout_and_interrupt(self):
        errors = [
            subprocess.TimeoutExpired("gh", 1),
            watcher.Interrupted(signal.SIGTERM),
        ]
        for error in errors:
            with self.subTest(error=error):
                process = mock.Mock(pid=12345678)
                process.poll.return_value = None
                process.communicate.side_effect = error
                expected = (
                    watcher.DeadlineError
                    if isinstance(error, subprocess.TimeoutExpired)
                    else watcher.Interrupted
                )
                with (
                    mock.patch.object(
                        watcher.subprocess, "Popen", return_value=process
                    ),
                    mock.patch.object(
                        watcher.os, "killpg", side_effect=PermissionError
                    ),
                    self.assertRaises(expected),
                ):
                    watcher.gh_api("repos/owner/repo/pulls/17", time.monotonic() + 2)
                process.kill.assert_called_once()
                process.wait.assert_called_once_with(timeout=1)

    def test_permission_denied_group_kill_fallback_reaps_real_child(self):
        self.configure([{"sleep": 10}])
        with (
            mock.patch.dict(os.environ, self.env),
            mock.patch.object(watcher.os, "killpg", side_effect=PermissionError),
            self.assertRaises(watcher.DeadlineError),
        ):
            watcher.gh_api("repos/owner/repo/pulls/17", time.monotonic() + 1)
        with self.assertRaises(ProcessLookupError):
            os.kill(int((self.root / "gh-pid").read_text()), 0)

    def test_invalid_arguments_never_invoke_gh(self):
        invalid = [
            ("--repo", "owner/repo;touch injected"),
            ("--repo", "../repo"),
            ("--repo", "$(id)/repo"),
            ("--head-sha", "a" * 39),
            ("--head-sha", "g" * 40),
            ("--pr", "0"),
            ("--pr", "-1"),
            ("--interval-seconds", "nan"),
            ("--timeout-seconds", "inf"),
            ("--timeout-seconds", "0"),
        ]
        for option, value in invalid:
            with self.subTest(option=option, value=value):
                result = self.run_watch([head()], [option, value])
                self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    @unittest.skipUnless(shutil.which("just"), "just is not installed")
    def test_just_recipe_passes_shell_syntax_as_data(self):
        self.configure([head()])
        marker = self.root / "injected"
        result = subprocess.run(
            ["just", "watch-pr-checks", f"owner/repo;touch {marker}", "17", SHA],
            cwd=SCRIPT.parent.parent,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertEqual(self.calls(), [])

    def test_duplicate_watcher_signal_cleanup_and_persistent_lock(self):
        self.configure([{"sleep": 10}])
        first = subprocess.Popen(
            self.command,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(lambda: first.poll() is None and first.kill())
        deadline = time.monotonic() + 2
        while not (self.root / "gh-pid").exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        second = subprocess.run(
            self.command + ["--repo", "OWNER/REPO", "--head-sha", OTHER_SHA],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        self.assertEqual(second.returncode, 1)
        self.assertIn("another local watcher", second.stderr)
        first.send_signal(signal.SIGTERM)
        _, stderr = first.communicate(timeout=2)
        self.assertEqual(first.returncode, 143, stderr)
        with self.assertRaises(ProcessLookupError):
            os.kill(int((self.root / "gh-pid").read_text()), 0)
        locks = list(self.root.glob("pr-ci-watch-*.lock"))
        self.assertEqual(len(locks), 1)
        inode = locks[0].stat().st_ino
        (self.root / "index").unlink()
        result = self.run_watch([head(), checks(gate()), head()])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(locks[0].stat().st_ino, inode)


if __name__ == "__main__":
    unittest.main()
