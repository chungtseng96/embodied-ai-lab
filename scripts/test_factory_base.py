import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import factory_base

ROOT = Path(__file__).resolve().parents[1]
LINES = [f"L{n}" for n in range(1, 21)]
REPO = "owner/repo"


class Stack:
    """A bare origin, a GitHub-side clone that squash-merges, and a child clone."""

    def __init__(self, root: Path):
        self.root = root
        empty = root / "gitconfig"
        empty.write_text("")
        self.env = dict(
            os.environ,
            GIT_CONFIG_GLOBAL=str(empty),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.com",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.com",
            PATH=f"{root}{os.pathsep}{os.environ['PATH']}",
            FAKE_GH=str(root / "gh.json"),
        )
        self.prs: dict[str, dict] = {}
        self.write_gh()
        gh = root / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "state = json.load(open(os.environ['FAKE_GH']))\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['FAKE_GH'] + '.calls', 'a') as f:\n"
            "    f.write(json.dumps(args) + '\\n')\n"
            "if args[:2] == ['pr', 'list']:\n"
            "    head = args[args.index('--head') + 1]\n"
            "    print(json.dumps([p for p in state['prs'].values()"
            " if p['headRefName'] == head]))\n"
            "elif args[:2] == ['pr', 'view']:\n"
            "    print(json.dumps(state['prs'][args[2]]))\n"
            "elif args[:2] == ['pr', 'edit']:\n"
            "    pass\n"
            "else:\n"
            "    sys.exit('unexpected gh call')\n"
        )
        gh.chmod(0o700)
        self.origin = root / "origin.git"
        self.hub = root / "hub"
        self.child = root / "child"
        self.git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.git(root, "clone", "-q", str(self.origin), str(self.hub))
        self.write(self.hub, "a.txt", LINES)
        self.commit(self.hub, "main0")
        self.git(self.hub, "push", "-q", "origin", "HEAD:refs/heads/main")

    def git(self, cwd: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {result.stderr}")
        return result.stdout.strip()

    def write(self, cwd: Path, name: str, lines: list[str]) -> None:
        (cwd / name).write_text("".join(f"{line}\n" for line in lines))

    def lines(self, cwd: Path, name: str = "a.txt") -> list[str]:
        return (cwd / name).read_text().splitlines()

    def edit(self, cwd: Path, message: str, change) -> str:
        lines = self.lines(cwd)
        change(lines)
        self.write(cwd, "a.txt", lines)
        return self.commit(cwd, message)

    def commit(self, cwd: Path, message: str) -> str:
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", message)
        return self.git(cwd, "rev-parse", "HEAD")

    def write_gh(self) -> None:
        (self.root / "gh.json").write_text(json.dumps({"prs": self.prs}))

    def open_pr(self, number: int, branch: str) -> None:
        head = self.git(self.hub, "rev-parse", f"origin/{branch}")
        self.prs[str(number)] = {
            "number": number,
            "headRefName": branch,
            "state": "OPEN",
            "baseRefName": "main",
            "headRefOid": head,
            "mergedAt": None,
            "mergeCommit": None,
            "labels": [],
        }
        self.write_gh()

    def branch(self, cwd: Path, name: str, start: str) -> None:
        self.git(cwd, "fetch", "-q", "origin")
        self.git(cwd, "switch", "-q", "-c", name, start)

    def push(self, cwd: Path, branch: str) -> None:
        self.git(cwd, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")

    def squash_merge(self, number: int, branch: str) -> str:
        """What GitHub does: squash onto main, keep refs/pull/<n>/head, delete the branch."""
        hub = self.hub
        self.git(hub, "fetch", "-q", "origin")
        self.git(hub, "switch", "-q", "main")
        self.git(hub, "merge", "-q", "--ff-only", "origin/main")
        head = self.git(hub, "rev-parse", f"origin/{branch}")
        self.git(hub, "merge", "-q", "--squash", head)
        squash = self.commit(hub, f"{branch} (#{number})")
        self.git(hub, "push", "-q", "origin", "main", f"{head}:refs/pull/{number}/head")
        self.git(hub, "push", "-q", "origin", "--delete", branch)
        pr = self.prs[str(number)]
        pr.update(
            state="MERGED",
            headRefOid=head,
            mergedAt="2026-11-06T00:00:00Z",
            mergeCommit={"oid": squash},
        )
        self.write_gh()
        return squash

    def hotfix_main(self, message: str, change) -> str:
        self.git(self.hub, "fetch", "-q", "origin")
        self.git(self.hub, "switch", "-q", "main")
        self.git(self.hub, "merge", "-q", "--ff-only", "origin/main")
        sha = self.edit(self.hub, message, change)
        self.git(self.hub, "push", "-q", "origin", "main")
        return sha

    def run_base(
        self,
        cwd: Path,
        branch: str,
        parent_branch: str,
        parent_head: str,
        base: str | None = None,
    ):
        argv = [
            "--repo",
            REPO,
            "--branch",
            branch,
            "--base",
            base or parent_branch,
            "--parent-branch",
            parent_branch,
            "--parent-head",
            parent_head,
        ]
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/factory_base.py"), *argv],
            cwd=cwd,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return result

    def diff_vs_main(self, cwd: Path) -> str:
        self.git(cwd, "fetch", "-q", "origin")
        return self.git(cwd, "diff", "-U0", "origin/main", "HEAD")


def changed_lines(diff: str) -> list[str]:
    return [
        line
        for line in diff.splitlines()
        if line[:1] in "+-" and line[:3] not in ("+++", "---")
    ]


class FactoryBaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.s = Stack(Path(temp.name))
        s = self.s
        # Parent edits line 5; the child, cut from that recorded head, edits line 15.
        s.git(s.hub, "switch", "-q", "-c", "parent")
        self.recorded = s.edit(
            s.hub, "parent", lambda lines: lines.__setitem__(4, "P5")
        )
        s.push(s.hub, "parent")
        s.open_pr(1, "parent")
        s.git(s.root, "clone", "-q", str(s.origin), str(s.child))
        s.branch(s.child, "child", "origin/parent")
        s.edit(s.child, "child", lambda lines: lines.__setitem__(14, "C15"))
        s.push(s.child, "child")

    def parent_late_fix(self, index: int, text: str) -> str:
        s = self.s
        s.git(s.hub, "switch", "-q", "parent")
        sha = s.edit(s.hub, "late fix", lambda lines: lines.__setitem__(index, text))
        s.push(s.hub, "parent")
        return sha

    def assert_ok(self, result, cwd: Path, branch: str = "child") -> str:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        line = result.stdout.strip()
        self.assertRegex(
            line, r"^verdict=ok base=main parent_head=[0-9a-f]{40} pushed=[0-9a-f]{40}"
        )
        head = self.s.git(cwd, "rev-parse", "HEAD")
        self.assertIn(f"pushed={head}", line)
        self.assertEqual(
            self.s.git(cwd, "ls-remote", "origin", f"refs/heads/{branch}").split()[0],
            head,
        )
        return line

    def test_a_parent_late_fix_on_untouched_line_is_brought_in(self):
        s = self.s
        final = self.parent_late_fix(9, "P10fix")
        s.squash_merge(1, "parent")
        line = self.assert_ok(
            s.run_base(s.child, "child", "parent", self.recorded), s.child
        )
        self.assertIn(f"parent_head={final}", line)
        lines = s.lines(s.child)
        self.assertEqual((lines[4], lines[9], lines[14]), ("P5", "P10fix", "C15"))
        self.assertEqual(changed_lines(s.diff_vs_main(s.child)), ["-L15", "+C15"])

    def test_b_parent_late_fix_on_child_line_is_a_hard_stop(self):
        s = self.s
        self.parent_late_fix(14, "P15fix")
        s.squash_merge(1, "parent")
        before = s.git(s.child, "rev-parse", "HEAD")
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "verdict=hard_stop reason=conflict in a.txt is not mechanical",
        )
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD"), before)
        self.assertEqual(s.git(s.child, "status", "--porcelain"), "")
        self.assertEqual(
            s.git(s.child, "ls-remote", "origin", "refs/heads/child").split()[0], before
        )

    def test_c_child_already_restacked_still_records_the_squash(self):
        s = self.s
        final = self.parent_late_fix(9, "P10fix")
        s.git(s.child, "fetch", "-q", "origin")
        s.git(s.child, "merge", "-q", "--no-ff", "-m", "restack", final)
        s.push(s.child, "child")
        squash = s.squash_merge(1, "parent")
        self.assert_ok(s.run_base(s.child, "child", "parent", final), s.child)
        s.git(s.child, "merge-base", "--is-ancestor", squash, "HEAD")
        self.assertEqual(changed_lines(s.diff_vs_main(s.child)), ["-L15", "+C15"])

    def test_d_child_deletion_of_a_parent_line_survives(self):
        s = self.s
        s.git(s.hub, "switch", "-q", "parent")
        s.edit(s.hub, "parent adds", lambda lines: lines.insert(7, "PADD"))
        s.push(s.hub, "parent")
        s.git(s.child, "fetch", "-q", "origin")
        s.git(s.child, "merge", "-q", "--no-ff", "-m", "restack", "origin/parent")
        recorded = s.git(s.child, "rev-parse", "origin/parent")
        s.edit(s.child, "child deletes", lambda lines: lines.remove("PADD"))
        s.push(s.child, "child")
        before = s.git(s.child, "rev-parse", "HEAD")
        s.squash_merge(1, "parent")
        # Control: a plain main merge brings the deleted line back.
        s.git(s.child, "fetch", "-q", "origin")
        s.git(s.child, "switch", "-q", "-c", "naive", before)
        s.git(s.child, "merge", "-q", "--no-ff", "-m", "naive", "origin/main")
        self.assertIn("PADD", s.lines(s.child))
        s.git(s.child, "switch", "-q", "child")
        self.assert_ok(s.run_base(s.child, "child", "parent", recorded), s.child)
        self.assertNotIn("PADD", s.lines(s.child))
        self.assertEqual(
            changed_lines(s.diff_vs_main(s.child)), ["-PADD", "-L15", "+C15"]
        )

    def test_e_main_hotfix_reverting_a_parent_line_survives(self):
        s = self.s
        s.squash_merge(1, "parent")
        s.hotfix_main("hotfix", lambda lines: lines.__setitem__(4, "L5"))
        self.assert_ok(s.run_base(s.child, "child", "parent", self.recorded), s.child)
        self.assertEqual(s.lines(s.child)[4], "L5")
        self.assertEqual(changed_lines(s.diff_vs_main(s.child)), ["-L15", "+C15"])

    def test_f_sibling_deletion_on_main_stays_deleted(self):
        s = self.s
        s.git(s.hub, "switch", "-q", "parent")
        s.edit(s.hub, "parent adds", lambda lines: lines.insert(7, "PADD"))
        s.push(s.hub, "parent")
        recorded = s.git(s.hub, "rev-parse", "HEAD")
        s.git(s.child, "fetch", "-q", "origin")
        s.git(s.child, "merge", "-q", "--no-ff", "-m", "restack", "origin/parent")
        s.push(s.child, "child")
        sibling = s.root / "sibling"
        s.git(s.root, "clone", "-q", str(s.origin), str(sibling))
        s.branch(sibling, "sibling", "origin/parent")
        s.edit(sibling, "sibling deletes", lambda lines: lines.remove("PADD"))
        s.push(sibling, "sibling")
        s.squash_merge(1, "parent")
        self.assert_ok(
            s.run_base(sibling, "sibling", "parent", recorded), sibling, "sibling"
        )
        s.open_pr(2, "sibling")
        s.squash_merge(2, "sibling")
        self.assert_ok(s.run_base(s.child, "child", "parent", recorded), s.child)
        self.assertNotIn("PADD", s.lines(s.child))
        self.assertEqual(changed_lines(s.diff_vs_main(s.child)), ["-L15", "+C15"])

    def test_g_rerun_after_session_death_reaches_the_same_end_state(self):
        s = self.s
        self.parent_late_fix(9, "P10fix")
        s.squash_merge(1, "parent")
        s.hotfix_main("hotfix", lambda lines: lines.__setitem__(1, "H2"))
        start = s.git(s.child, "rev-parse", "HEAD")
        with mock.patch.dict(os.environ, s.env, clear=True):
            parent = factory_base.query_parent(
                factory_base.arguments(
                    [
                        "--repo",
                        REPO,
                        "--branch",
                        "child",
                        "--base",
                        "parent",
                        "--parent-branch",
                        "parent",
                        "--parent-head",
                        self.recorded,
                    ]
                ),
                s.child,
            )
            # Death after the merges, before the push: keep the merges, then discard them.
            factory_base.restack(s.child, parent, self.recorded)
        kept = s.git(s.child, "rev-parse", "HEAD")
        self.assertNotEqual(kept, start)
        self.assertEqual(
            s.git(s.child, "ls-remote", "origin", "refs/heads/child").split()[0], start
        )
        self.assert_ok(s.run_base(s.child, "child", "parent", self.recorded), s.child)
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD"), kept)
        tree = s.git(s.child, "rev-parse", "HEAD^{tree}")
        s.git(s.child, "push", "-q", "--force", "origin", f"{start}:refs/heads/child")
        s.git(s.child, "reset", "-q", "--hard", start)
        self.assert_ok(s.run_base(s.child, "child", "parent", self.recorded), s.child)
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD^{tree}"), tree)
        again = s.run_base(s.child, "child", "parent", self.recorded)
        self.assert_ok(again, s.child)
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD^{tree}"), tree)
        self.assertEqual(changed_lines(s.diff_vs_main(s.child)), ["-L15", "+C15"])

    def test_guard_resets_when_a_clean_main_merge_changes_the_child_diff(self):
        s = self.s
        s.squash_merge(1, "parent")
        s.hotfix_main(
            "same edit as the child", lambda lines: lines.__setitem__(14, "C15")
        )
        before = s.git(s.child, "rev-parse", "HEAD")
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "verdict=hard_stop reason=main merge changed the child's diff",
        )
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD"), before)
        self.assertEqual(
            s.git(s.child, "ls-remote", "origin", "refs/heads/child").split()[0], before
        )

    def test_dirty_worktree_is_a_hard_stop_before_any_merge(self):
        s = self.s
        s.squash_merge(1, "parent")
        (s.child / "a.txt").write_text("unsaved edit\n")
        before = s.git(s.child, "rev-parse", "HEAD")
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "verdict=hard_stop reason=worktree has uncommitted changes; commit them before Base",
        )
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD"), before)
        self.assertEqual((s.child / "a.txt").read_text(), "unsaved edit\n")

    def test_reused_branch_name_with_open_and_merged_prs_is_a_hard_stop(self):
        s = self.s
        # A late fix moves the merged head off the recorded one, so neither PR
        # matches --parent-head and the open/merged pair is ambiguous.
        self.parent_late_fix(2, "P3")
        s.squash_merge(1, "parent")
        # A later PR reuses the branch name and is still open.
        s.prs["7"] = dict(
            s.prs["1"], number=7, state="OPEN", mergedAt=None, mergeCommit=None
        )
        s.prs["7"]["headRefOid"] = "f" * 40
        s.write_gh()
        before = s.git(s.child, "rev-parse", "HEAD")
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "both an open and a merged PR (#1, #7); pass --parent-pr", result.stdout
        )
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD"), before)

    def test_push_failure_that_is_not_a_rejection_is_an_error_not_a_hard_stop(self):
        s = self.s
        s.squash_merge(1, "parent")
        s.git(
            s.child,
            "remote",
            "set-url",
            "--push",
            "origin",
            str(s.root / "missing.git"),
        )
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertTrue(
            result.stdout.startswith("verdict=error reason=push to child failed:"),
            result.stdout,
        )

    def test_h_parent_closed_unmerged_is_a_hard_stop(self):
        s = self.s
        s.prs["1"]["state"] = "CLOSED"
        s.write_gh()
        before = s.git(s.child, "rev-parse", "HEAD")
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.strip(), "verdict=hard_stop reason=parent #1 closed unmerged"
        )
        self.assertEqual(s.git(s.child, "rev-parse", "HEAD"), before)

    def test_parent_merged_elsewhere_is_a_hard_stop_and_open_parent_is_noop(self):
        s = self.s
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(
            (result.returncode, result.stdout.strip()),
            (0, "verdict=noop reason=parent #1 open"),
        )
        result = s.run_base(s.child, "child", "parent", self.recorded, base="main")
        self.assertEqual(
            (result.returncode, result.stdout.strip()),
            (0, "verdict=noop reason=base is main"),
        )
        s.prs["1"].update(
            state="MERGED",
            baseRefName="dev-deploy",
            mergedAt="2026-11-06T00:00:00Z",
            mergeCommit={"oid": "e" * 40},
        )
        s.write_gh()
        result = s.run_base(s.child, "child", "parent", self.recorded)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stdout.strip(),
            "verdict=hard_stop reason=parent #1 merged into dev-deploy, not main",
        )


if __name__ == "__main__":
    unittest.main()
