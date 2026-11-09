import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factory_dispatch

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def record(heartbeat):
    body = "**Factory state**\n\nTicket: JWA-5\n"
    if heartbeat:
        body += f"run: abcd1234 · heartbeat {heartbeat}\n"
    body += "\nphase: factory-implement · started · head 1a2b3c4 · t"
    return {"id": "c1", "body": body, "url": None}


def issue(identifier, state_comment=None):
    return {
        "id": f"id-{identifier}",
        "identifier": identifier,
        "title": f"title {identifier}",
        "description": "",
        "branchName": f"chungtseng96/{identifier.lower()}-slug",
        "url": "",
        "state": {"name": "Todo", "type": "unstarted"},
        "team": {"id": "t1", "key": "JWA"},
        "project": None,
        "labels": {
            "nodes": [{"id": "l-ready", "name": "factory:ready", "parent": {"name": "Factory"}}]
        },
        "relations": {"nodes": [], "pageInfo": {"hasNextPage": False}},
        "inverseRelations": {"nodes": [], "pageInfo": {"hasNextPage": False}},
        "comments": {
            "nodes": [state_comment] if state_comment else [],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        },
    }


def transport_for(issues):
    """Answers the `ready` listing and per-issue reads from one dict of issues."""

    def transport(payload):
        query, variables = payload["query"], payload["variables"]
        if "orderBy: createdAt" in query:
            rows = [
                {
                    "identifier": i,
                    "title": v["title"],
                    "branchName": v["branchName"],
                    "createdAt": i,
                }
                for i, v in issues.items()
            ]
            return {"data": {"issues": {"nodes": rows}}}
        return {"data": {"issue": issues[variables["id"]]}}

    return transport


class PickTests(unittest.TestCase):
    def test_pick_takes_the_oldest_ready_ticket(self):
        transport = transport_for({"JWA-5": issue("JWA-5"), "JWA-6": issue("JWA-6")})
        self.assertEqual(factory_dispatch.pick("JWA", transport, NOW)["identifier"], "JWA-5")

    def test_pick_skips_a_ticket_whose_run_holds_a_live_lease(self):
        transport = transport_for(
            {
                "JWA-5": issue("JWA-5", record("2026-11-08T11:50:00Z")),
                "JWA-6": issue("JWA-6"),
            }
        )
        self.assertEqual(factory_dispatch.pick("JWA", transport, NOW)["identifier"], "JWA-6")

    def test_pick_resumes_a_ticket_with_a_stale_lease_or_a_cleared_run_line(self):
        stale = transport_for({"JWA-5": issue("JWA-5", record("2026-11-08T11:00:00Z"))})
        self.assertEqual(factory_dispatch.pick("JWA", stale, NOW)["identifier"], "JWA-5")
        paused = transport_for({"JWA-5": issue("JWA-5", record(None))})
        self.assertEqual(factory_dispatch.pick("JWA", paused, NOW)["identifier"], "JWA-5")

    def test_pick_returns_none_when_nothing_is_ready(self):
        self.assertIsNone(factory_dispatch.pick("JWA", transport_for({}), NOW))

    def test_heartbeat_accepts_short_and_full_iso_times(self):
        self.assertEqual(
            factory_dispatch.heartbeat("run: x · heartbeat 2026-11-08T10:00Z"),
            datetime(2026, 11, 8, 10, 0, tzinfo=UTC),
        )
        self.assertEqual(
            factory_dispatch.heartbeat("run: x · heartbeat 2026-11-08T10:00:30+00:00"),
            datetime(2026, 11, 8, 10, 0, 30, tzinfo=UTC),
        )
        self.assertIsNone(factory_dispatch.heartbeat("run: x · heartbeat garbage"))
        self.assertIsNone(factory_dispatch.heartbeat(None))


class LockTests(unittest.TestCase):
    def test_lock_refuses_a_planted_symlink_and_never_truncates(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "victim"
            target.write_text("keep me")
            link = Path(tmp) / "lock"
            os.symlink(target, link)
            with self.assertRaises(OSError):
                factory_dispatch.open_lock(link)
            self.assertEqual(target.read_text(), "keep me")
            real = Path(tmp) / "real.lock"
            real.write_text("existing")
            with factory_dispatch.open_lock(real):
                pass
            self.assertEqual(real.read_text(), "existing")

    def test_lock_path_is_user_scoped(self):
        import os

        self.assertIn(f"-{os.getuid()}-", factory_dispatch.lock_path(Path("/repo")).name)


class CommandTests(unittest.TestCase):
    def test_worktree_and_command_shape(self):
        root = Path("/repo")
        worktree = factory_dispatch.worktree_for("JWA-5", root)
        self.assertEqual(worktree, root / ".claude" / "worktrees" / "factory-jwa-5")
        command = factory_dispatch.claude_command("JWA-5", worktree, "main")
        self.assertEqual(command[:3], ["claude", "-p", "/factory JWA-5"])
        self.assertIn("--permission-mode", command)

    def test_dry_run_prints_the_command_without_running(self):
        transport = transport_for({"JWA-5": issue("JWA-5")})
        with (
            mock.patch.object(factory_dispatch, "repo_root", return_value=Path("/repo")),
            mock.patch.object(factory_dispatch.subprocess, "run") as run,
            mock.patch("sys.stdout") as out,
        ):
            code = factory_dispatch.main(["run", "--dry-run"], transport)
        self.assertEqual(code, 0)
        run.assert_not_called()
        printed = json.loads(out.write.call_args_list[0].args[0])
        self.assertEqual(printed["ticket"], "JWA-5")
        self.assertIn("/factory JWA-5", printed["command"])

    def test_pick_command_prints_null_when_queue_is_empty(self):
        with (
            mock.patch.object(factory_dispatch, "repo_root", return_value=Path("/repo")),
            mock.patch("sys.stdout") as out,
        ):
            code = factory_dispatch.main(["pick"], transport_for({}))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.write.call_args_list[0].args[0]), {"ticket": None})


if __name__ == "__main__":
    unittest.main()
