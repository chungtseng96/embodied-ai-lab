import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factory_dispatch


def ready_transport(rows):
    def transport(payload):
        assert "orderBy: createdAt" in payload["query"]
        return {"data": {"issues": {"nodes": rows}}}

    return transport


ROWS = [
    {
        "identifier": "JWA-5",
        "title": "first",
        "branchName": "chungtseng96/jwa-5-first",
        "createdAt": "2026-11-01",
    },
    {
        "identifier": "JWA-6",
        "title": "second",
        "branchName": "chungtseng96/jwa-6-second",
        "createdAt": "2026-11-02",
    },
]


class PickTests(unittest.TestCase):
    def test_pick_takes_the_oldest_ready_ticket(self):
        chosen = factory_dispatch.pick(
            "JWA", Path("."), ready_transport(ROWS), remote=lambda b, c: False
        )
        self.assertEqual(chosen["identifier"], "JWA-5")

    def test_pick_skips_a_ticket_whose_claim_branch_already_exists(self):
        chosen = factory_dispatch.pick(
            "JWA", Path("."), ready_transport(ROWS), remote=lambda b, c: b.endswith("jwa-5-first")
        )
        self.assertEqual(chosen["identifier"], "JWA-6")

    def test_pick_returns_none_when_nothing_is_ready(self):
        self.assertIsNone(
            factory_dispatch.pick("JWA", Path("."), ready_transport([]), remote=lambda b, c: False)
        )


class CommandTests(unittest.TestCase):
    def test_worktree_and_command_shape(self):
        root = Path("/repo")
        worktree = factory_dispatch.worktree_for("JWA-5", root)
        self.assertEqual(worktree, root / ".claude" / "worktrees" / "factory-jwa-5")
        command = factory_dispatch.claude_command("JWA-5", worktree, "main")
        self.assertEqual(command[:3], ["claude", "-p", "/factory JWA-5"])
        self.assertIn("--permission-mode", command)

    def test_dry_run_prints_the_command_without_running(self):
        with (
            mock.patch.object(factory_dispatch, "repo_root", return_value=Path("/repo")),
            mock.patch.object(factory_dispatch, "branch_on_origin", return_value=False),
            mock.patch.object(factory_dispatch.subprocess, "run") as run,
            mock.patch("sys.stdout") as out,
        ):
            code = factory_dispatch.main(["run", "--dry-run"], ready_transport(ROWS))
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
            code = factory_dispatch.main(["pick"], ready_transport([]))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.write.call_args_list[0].args[0]), {"ticket": None})


if __name__ == "__main__":
    unittest.main()
