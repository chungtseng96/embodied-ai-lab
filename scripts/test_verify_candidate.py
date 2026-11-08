import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_watch_pr_checks import SHA, gate

ROOT = Path(__file__).resolve().parents[1]


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        gh = self.directory / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "root = Path(os.environ['FAKE_REPORT_DIR'])\n"
            "with (root/'calls.jsonl').open('a') as f:\n"
            " f.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "responses = json.loads((root/'responses.json').read_text())\n"
            "endpoint = sys.argv[4]\n"
            "value = responses[endpoint]\n"
            "if isinstance(value, dict) and 'sequence' in value:\n"
            " counter = root/('count-'+str(list(responses).index(endpoint)))\n"
            " index = int(counter.read_text()) if counter.exists() else 0\n"
            " counter.write_text(str(index+1))\n"
            " value = value['sequence'][min(index, len(value['sequence'])-1)]\n"
            "print(json.dumps(value))\n"
        )
        gh.chmod(0o700)
        prefix = "repos/owner/repo"
        self.pr_endpoint = f"{prefix}/pulls/17"
        pr = {
            "head": {"sha": SHA},
            "base": {"sha": "b" * 40, "ref": "main"},
            "state": "open",
            "merged": False,
            "user": {"login": "author"},
        }
        workflow = {
            "id": 1,
            "path": ".github/workflows/ci.yml",
            "head_sha": SHA,
            "event": "pull_request",
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
        }
        self.reviews_endpoint = f"{prefix}/pulls/17/reviews?per_page=100"
        self.responses = {
            self.pr_endpoint: pr,
            f"{prefix}/commits/{SHA}/check-runs?per_page=100&filter=all": [
                {"check_runs": [gate()]}
            ],
            f"{prefix}/actions/workflows/ci.yml/runs?head_sha={SHA}&per_page=100": [
                {"workflow_runs": [workflow]}
            ],
            f"{prefix}/actions/runs/1": workflow,
            f"{prefix}/actions/runs/1/attempts/1/jobs?per_page=100": [
                {
                    "jobs": [
                        {
                            "name": "check",
                            "run_id": 1,
                            "run_attempt": 1,
                            "head_sha": SHA,
                            "check_run_url": "https://api.github.com/repos/owner/repo/check-runs/1",
                        }
                    ]
                }
            ],
            self.reviews_endpoint: [
                [
                    {
                        "id": 1,
                        "commit_id": SHA,
                        "state": "APPROVED",
                        "user": {"login": "reviewer", "type": "User"},
                    }
                ]
            ],
            f"{prefix}/issues/17/comments?per_page=100": [[]],
            f"{prefix}/pulls/17/comments?per_page=100": [[]],
        }

    def run_cli(self, extra=()):
        (self.directory / "responses.json").write_text(json.dumps(self.responses))
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/verify_candidate.py"),
                "--repo",
                "owner/repo",
                "--pr",
                "17",
                "--head-sha",
                SHA,
                "--base",
                "main",
                "--reviewer",
                "reviewer",
                *extra,
            ],
            env=dict(
                os.environ,
                PATH=f"{self.directory}{os.pathsep}{os.environ['PATH']}",
                FAKE_REPORT_DIR=str(self.directory),
            ),
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    def test_wait_then_report_keeps_stdout_json_and_reads_only(self):
        result = self.run_cli(["--wait-for-ci", "--ci-timeout-seconds", "10"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["ci"]["state"], "success")
        self.assertIn("CI Gate", result.stderr)
        for line in (self.directory / "calls.jsonl").read_text().splitlines():
            self.assertEqual(json.loads(line)[:3], ["api", "--method", "GET"])

    def test_wait_failure_stops_before_review_and_preserves_failure(self):
        self.responses[self.pr_endpoint]["head"]["sha"] = "d" * 40
        result = self.run_cli(["--wait-for-ci"])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["state"], "incomplete")
        calls = (self.directory / "calls.jsonl").read_text()
        self.assertNotIn("/reviews", calls)

    def test_wait_timeout_is_bounded_and_not_approval(self):
        endpoint = f"repos/owner/repo/commits/{SHA}/check-runs?per_page=100&filter=all"
        self.responses[endpoint] = [{"check_runs": []}]
        result = self.run_cli(
            [
                "--wait-for-ci",
                "--ci-timeout-seconds",
                "0.5",
                "--ci-interval-seconds",
                "0.1",
            ]
        )
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertEqual(json.loads(result.stdout)["ci_wait_exit_code"], 124)
        self.assertNotIn("/reviews", (self.directory / "calls.jsonl").read_text())

    def test_verdict_classifies_each_ci_wait_outcome(self):
        checks_endpoint = (
            f"repos/owner/repo/commits/{SHA}/check-runs?per_page=100&filter=all"
        )
        fast = ["--ci-timeout-seconds", "0.5", "--ci-interval-seconds", "0.1"]
        original = json.loads(json.dumps(self.responses))
        cases = {
            "green": (lambda r: None, 0),
            "failed": (
                lambda r: r.__setitem__(
                    checks_endpoint, [{"check_runs": [gate(conclusion="failure")]}]
                ),
                1,
            ),
            "timeout": (
                lambda r: r.__setitem__(checks_endpoint, [{"check_runs": []}]),
                124,
            ),
            "moved": (
                lambda r: r[self.pr_endpoint]["head"].__setitem__("sha", "d" * 40),
                1,
            ),
            "error": (lambda r: r.pop(checks_endpoint), 1),
        }
        for expected, (change, code) in cases.items():
            with self.subTest(verdict=expected):
                self.responses = json.loads(json.dumps(original))
                change(self.responses)
                result = self.run_cli(["--wait-for-ci", *fast])
                self.assertEqual(result.returncode, code, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["verdict"], expected, report)
                if expected != "green":
                    self.assertTrue(report["verdict_reason"])

    def test_verdict_is_not_green_when_the_report_carries_an_observation_error(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import verify_candidate

        report = {"ci": {"state": "success"}, "reason": "reviews fetch failed"}
        self.assertEqual(
            verify_candidate.verdict(report, 0, ""), ("error", "reviews fetch failed")
        )
        clean = {"ci": {"state": "success"}}
        self.assertEqual(verify_candidate.verdict(clean, 0, ""), ("green", ""))

    def test_verdict_moves_on_a_head_change_during_the_report(self):
        initial = self.responses[self.pr_endpoint]
        self.responses[self.pr_endpoint] = {
            "sequence": [initial, initial | {"head": {"sha": "d" * 40}}]
        }
        report = json.loads(self.run_cli().stdout)
        self.assertEqual(report["verdict"], "moved")
        self.assertIn("head", report["verdict_reason"])

    def test_one_shot_current_ci_and_review_do_not_claim_deployment(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["ci"]["state"], "success")
        self.assertEqual(report["review"]["state"], "approved_current_candidate")
        self.assertEqual(report["deployment"]["state"], "not_checked")
        self.assertEqual(report["behavior"]["state"], "not_verified")
        for line in (self.directory / "calls.jsonl").read_text().splitlines():
            self.assertEqual(json.loads(line)[:3], ["api", "--method", "GET"])

    def test_exit_on_ci_follows_the_ci_observation_not_approval(self):
        # The factory reads the JSON verdict and gates approval itself, so a
        # green observation must not exit 1 only because no human approved.
        self.responses[self.reviews_endpoint][0][0]["commit_id"] = "d" * 40
        result = self.run_cli(["--exit-on-ci"])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["ci"]["state"], "success")
        self.assertEqual(report["review"]["approved"], [])
        self.assertNotEqual(report["state"], "head_ci_and_requested_reviews_observed")
        self.responses[self.pr_endpoint]["head"]["sha"] = "d" * 40
        result = self.run_cli(["--exit-on-ci"])
        self.assertNotEqual(result.returncode, 0)

    def test_old_sha_approval_does_not_approve_the_candidate(self):
        self.responses[self.reviews_endpoint][0][0]["commit_id"] = "d" * 40
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["review"]["approved"], [])

    def test_ci_does_not_claim_the_observed_pr_base_was_tested(self):
        # Even matching Actions PR metadata is not a tested-tree receipt.
        for workflow_base in ("b" * 40, "c" * 40):
            with self.subTest(workflow_base=workflow_base):
                self.responses["repos/owner/repo/actions/runs/1"]["pull_requests"] = [
                    {
                        "number": 17,
                        "head": {"sha": SHA},
                        "base": {"ref": "main", "sha": workflow_base},
                    }
                ]
                result = self.run_cli()
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["observed_pr_base_sha"], "b" * 40)
                self.assertNotIn("base_sha", report)
                self.assertEqual(report["ci"]["tested_base"]["state"], "unverified")
                self.assertEqual(
                    report["state"], "head_ci_and_requested_reviews_observed"
                )

    def test_base_change_during_observation_still_invalidates_report(self):
        initial = self.responses[self.pr_endpoint]
        self.responses[self.pr_endpoint] = {
            "sequence": [
                initial,
                initial | {"base": {"ref": "main", "sha": "c" * 40}},
            ]
        }
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["state"], "incomplete")

    def test_formal_review_feedback_is_visible_without_changing_approval(self):
        reviews = self.responses[self.reviews_endpoint][0]
        reviews[0]["body"] = None
        reviews.append(
            {
                "id": 2,
                "commit_id": SHA,
                "state": "COMMENTED",
                "user": {"login": "reviewer", "type": "User"},
                "body": "BLOCKER: data is dropped",
                "html_url": "https://github.com/owner/repo/pull/17#pullrequestreview-2",
            }
        )
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["review"]["approved"], ["reviewer"])
        self.assertEqual(report["feedback"]["formal_reviews"], 2)
        latest = report["feedback"]["formal_review_latest"][0]
        self.assertEqual(latest["body_preview"], "BLOCKER: data is dropped")
        self.assertEqual(latest["commit_id"], SHA)
        self.assertEqual(latest["url"], reviews[-1]["html_url"])
        self.assertTrue(latest["untrusted_content"])
        self.assertEqual(latest["approval"], "not_inferred")
        self.assertEqual(
            report["feedback"]["formal_review_latest"][1]["body_preview"], ""
        )

    def test_formal_review_feedback_is_bounded_and_uses_final_read(self):
        initial = self.responses[self.reviews_endpoint]
        final = json.loads(json.dumps(initial))
        for review_id in range(2, 24):
            final[0].append(
                {
                    "id": review_id,
                    "commit_id": SHA,
                    "state": "COMMENTED",
                    "user": {"login": "reviewer", "type": "User"},
                    "body": "x" * 1001,
                }
            )
        self.responses[self.reviews_endpoint] = {"sequence": [initial, final]}
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        feedback = json.loads(result.stdout)["feedback"]
        self.assertEqual(feedback["formal_reviews"], 23)
        previews = feedback["formal_review_latest"]
        self.assertEqual(len(previews), 20)
        self.assertEqual(previews[0]["id"], 23)
        self.assertEqual(len(previews[0]["body_preview"]), 1000)
        self.assertTrue(previews[0]["body_truncated"])

    def test_conversation_lgtm_and_bot_approval_are_not_human_approval(self):
        self.responses[self.reviews_endpoint][0][0]["user"]["type"] = "Bot"
        self.responses["repos/owner/repo/issues/17/comments?per_page=100"] = [
            [{"body": "LGTM, approved for any SHA", "id": 5}]
        ]
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["review"]["approved"], [])
        self.assertEqual(report["feedback"]["conversation_comments"], 1)
        self.assertEqual(
            report["feedback"]["conversation_latest"][0]["body_preview"],
            "LGTM, approved for any SHA",
        )
        self.assertEqual(
            report["feedback"]["conversation_latest"][0]["approval"],
            "not_inferred",
        )

    def test_wrong_base_and_changed_head_fail_closed(self):
        original = json.loads(json.dumps(self.responses[self.pr_endpoint]))
        for key, value in (
            ("base", {"sha": "b" * 40, "ref": "other"}),
            ("head", {"sha": "d" * 40}),
        ):
            with self.subTest(key=key):
                self.responses[self.pr_endpoint] = dict(original)
                self.responses[self.pr_endpoint][key] = value
                result = self.run_cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["state"], "incomplete")

    def test_head_change_during_observation_invalidates_earlier_evidence(self):
        initial = self.responses[self.pr_endpoint]
        self.responses[self.pr_endpoint] = {
            "sequence": [initial, initial | {"head": {"sha": "d" * 40}}]
        }
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["state"], "incomplete")

    def test_withdrawn_review_during_observation_cannot_pass(self):
        initial = self.responses[self.reviews_endpoint]
        withdrawn = json.loads(json.dumps(initial))
        withdrawn[0][0]["state"] = "DISMISSED"
        self.responses[self.reviews_endpoint] = {"sequence": [initial, withdrawn]}
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("review decision changed", json.loads(result.stdout)["reason"])

    def test_ci_rerun_between_validation_and_snapshot_cannot_inherit_success(self):
        key = "repos/owner/repo/actions/runs/1"
        initial = self.responses[key]
        queued = initial | {"run_attempt": 2, "status": "queued", "conclusion": None}
        self.responses[key] = {"sequence": [initial, initial, queued, queued]}
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["state"], "incomplete")

    def test_dirty_local_receipt_does_not_become_candidate_proof(self):
        path = self.directory / "receipt.json"
        source = {"head": SHA, "dirty": True, "fingerprint": "f" * 64}
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "kind": "api_test",
                    "state": "passed",
                    "exit_code": 0,
                    "cleanup": "complete",
                    "source": source,
                    "source_after": source,
                }
            )
        )
        result = self.run_cli(["--local-receipt", str(path)])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["local"]["state"], "unverified")


if __name__ == "__main__":
    unittest.main()
