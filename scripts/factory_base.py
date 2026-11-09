"""Factory Base rule: move a stacked child onto main once its parent squash-merged.

Prints one result line on stdout, for the factory state record:
  verdict=ok base=main parent_head=<F> pushed=<sha> [resolved=<files>]
  verdict=noop reason=<why nothing was needed>
  verdict=hard_stop reason=<why the run must stop>
  verdict=error reason=<command that failed>
Exit status: 0 for ok and noop, 1 for hard_stop, 3 for error.
Every merge is gated by its own ancestry test, so a re-run after a session
died at any step converges on the same pushed result.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

MAIN = "main"
READY_LABEL = "factory-ready"
SHA = re.compile(r"[0-9a-f]{40}")


class HardStop(Exception):
    pass


class CommandError(Exception):
    pass


@dataclass(frozen=True)
class Parent:
    number: int
    state: str
    base: str
    head: str
    squash: str | None


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise CommandError(
            f"{' '.join(cmd[:3])}: {detail[-1] if detail else result.returncode}"
        )
    return result


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], cwd, check).stdout.strip()


def is_ancestor(cwd: Path, commit: str, of: str = "HEAD") -> bool:
    return (
        run(["git", "merge-base", "--is-ancestor", commit, of], cwd, False).returncode
        == 0
    )


def log(message: str) -> None:
    print(f"factory_base: {message}", file=sys.stderr, flush=True)


def parent_from_json(raw: object) -> Parent:
    if not isinstance(raw, dict) or not isinstance(raw.get("number"), int):
        raise CommandError("malformed parent PR JSON")
    head = raw.get("headRefOid")
    if not isinstance(head, str) or not SHA.fullmatch(head):
        raise CommandError("parent PR has no head SHA")
    merge = raw.get("mergeCommit") or {}
    squash = merge.get("oid") if isinstance(merge, dict) else None
    if not raw.get("mergedAt"):
        squash = None
    return Parent(
        raw["number"], str(raw.get("state")), str(raw.get("baseRefName")), head, squash
    )


def query_parent(args: argparse.Namespace, cwd: Path) -> Parent | None:
    fields = "number,state,baseRefName,headRefOid,mergedAt,mergeCommit"
    if args.parent_pr:
        cmd = [
            "gh",
            "pr",
            "view",
            str(args.parent_pr),
            "--repo",
            args.repo,
            "--json",
            fields,
        ]
        return parent_from_json(json.loads(run(cmd, cwd).stdout))
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        args.repo,
        "--head",
        args.parent_branch,
        "--state",
        "all",
        "--json",
        fields,
    ]
    prs = [parent_from_json(raw) for raw in json.loads(run(cmd, cwd).stdout)]
    if not prs:
        return None
    if len(prs) == 1:
        return prs[0]
    # A branch name can be reused. The PR at the recorded head is the parent;
    # otherwise an open PR beside a merged one is ambiguous, and the newest wins.
    for pr in prs:
        if pr.head == args.parent_head:
            return pr
    states = {pr.state for pr in prs}
    if "OPEN" in states and "MERGED" in states:
        numbers = ", ".join(
            f"#{pr.number}" for pr in sorted(prs, key=lambda p: p.number)
        )
        raise HardStop(
            f"branch {args.parent_branch} has both an open and a merged PR "
            f"({numbers}); pass --parent-pr"
        )
    return max(prs, key=lambda p: p.number)


def merge_parent_head(cwd: Path, final_head: str, recorded_head: str) -> list[str]:
    """Merge the parent's final head; resolve only hunks where one side equals the recorded head."""
    message = f"Merge parent final head {final_head}"
    if (
        run(
            ["git", "merge", "--no-ff", "-m", message, final_head], cwd, False
        ).returncode
        == 0
    ):
        return []
    conflicted = [
        path
        for path in git(cwd, "diff", "--name-only", "--diff-filter=U").splitlines()
        if path
    ]
    try:
        if not conflicted:
            raise HardStop("parent head merge failed without a content conflict")
        if (
            run(
                ["git", "cat-file", "-e", f"{recorded_head}^{{commit}}"], cwd, False
            ).returncode
            != 0
        ):
            raise HardStop(
                f"recorded parent head {recorded_head} is not available; "
                f"conflict in {conflicted[0]}"
            )
        for path in conflicted:
            resolve_against(cwd, path, recorded_head)
    except HardStop:
        run(["git", "merge", "--abort"], cwd, False)
        raise
    git(cwd, "commit", "--no-edit")
    return conflicted


def resolve_against(cwd: Path, path: str, reference: str) -> None:
    # Re-merging with the recorded head as base takes the other side exactly
    # where one side still equals it; any hunk both sides changed stays a conflict.
    versions = []
    for spec in (f":2:{path}", f"{reference}:{path}", f":3:{path}"):
        shown = subprocess.run(
            ["git", "show", spec], cwd=cwd, capture_output=True, check=False
        )
        if shown.returncode != 0:
            raise HardStop(f"conflict in {path} is not mechanical (a side is missing)")
        versions.append(shown.stdout)
    with tempfile.TemporaryDirectory() as temp:
        files = [Path(temp, name) for name in ("ours", "reference", "theirs")]
        for file, content in zip(files, versions):
            file.write_bytes(content)
        merged = subprocess.run(
            ["git", "merge-file", "-p", *map(str, files)],
            capture_output=True,
            check=False,
        )
    if merged.returncode != 0:
        raise HardStop(f"conflict in {path} is not mechanical")
    (cwd / path).write_bytes(merged.stdout)
    git(cwd, "add", "--", path)


def child_tip(cwd: Path, main_ref: str, final_head: str) -> str:
    """The child's head before any main merge: walk first parents past merges of main history."""
    commit = git(cwd, "rev-parse", "HEAD")
    while True:
        parents = git(cwd, "rev-list", "--parents", "-n", "1", commit).split()[1:]
        if (
            len(parents) < 2
            or parents[1] == final_head
            or not is_ancestor(cwd, parents[1], main_ref)
        ):
            return commit
        commit = parents[0]


def patch_id(cwd: Path, old: str, new: str) -> str:
    diff = run(["git", "diff", "-U0", old, new], cwd).stdout
    ids = subprocess.run(
        ["git", "patch-id", "--stable"],
        cwd=cwd,
        input=diff,
        capture_output=True,
        text=True,
        check=True,
    )
    return ids.stdout.split(" ")[0].strip()


def restack(cwd: Path, parent: Parent, recorded_head: str) -> tuple[str, list[str]]:
    """Every merge Base makes, each gated by its own ancestry test.

    Returns (PRE, resolved files).
    """
    main_ref = f"origin/{MAIN}"
    git(cwd, "fetch", "origin", f"+refs/heads/{MAIN}:refs/remotes/origin/{MAIN}")
    squash = parent.squash
    if not squash or not is_ancestor(cwd, squash, main_ref):
        raise HardStop(f"parent squash commit {squash} is not on {main_ref}")
    resolved: list[str] = []
    if not is_ancestor(cwd, parent.head):
        git(cwd, "fetch", "origin", f"refs/pull/{parent.number}/head")
        if (
            run(
                ["git", "cat-file", "-e", f"{parent.head}^{{commit}}"], cwd, False
            ).returncode
            != 0
        ):
            raise CommandError(
                f"refs/pull/{parent.number}/head does not hold {parent.head}"
            )
        log(f"merging parent final head {parent.head}")
        resolved = merge_parent_head(cwd, parent.head, recorded_head)
    pre = child_tip(cwd, main_ref, parent.head)
    # The squash is content the child already holds: merge main before it,
    # declare the squash contained, then merge the rest of main.
    steps = [
        (
            f"{squash}^1",
            ["--no-ff", "-m", f"Merge {MAIN} before parent squash {squash}"],
        ),
        (squash, ["-s", "ours", "-m", f"Record parent squash {squash} as contained"]),
        (main_ref, ["--no-ff", "-m", f"Merge {main_ref}"]),
    ]
    for target, options in steps:
        if is_ancestor(cwd, target):
            continue
        log(f"merging {target}")
        if run(["git", "merge", *options, target], cwd, False).returncode != 0:
            run(["git", "merge", "--abort"], cwd, False)
            git(cwd, "reset", "--hard", pre)
            raise HardStop(f"conflict merging {target}")
    if patch_id(cwd, parent.head, pre) != patch_id(cwd, main_ref, "HEAD"):
        git(cwd, "reset", "--hard", pre)
        raise HardStop("main merge changed the child's diff")
    return pre, resolved


def push(cwd: Path, args: argparse.Namespace) -> str:
    head = git(cwd, "rev-parse", "HEAD")
    remote = git(cwd, "ls-remote", "origin", f"refs/heads/{args.branch}").split("\t")[0]
    if remote == head:
        return head
    if args.pr:
        view = [
            "gh",
            "pr",
            "view",
            str(args.pr),
            "--repo",
            args.repo,
            "--json",
            "labels",
        ]
        labels = json.loads(run(view, cwd).stdout).get("labels", [])
        if any(label.get("name") == READY_LABEL for label in labels):
            run(
                [
                    "gh",
                    "pr",
                    "edit",
                    str(args.pr),
                    "--repo",
                    args.repo,
                    "--remove-label",
                    READY_LABEL,
                ],
                cwd,
            )
    pushed = run(
        ["git", "push", "origin", f"HEAD:refs/heads/{args.branch}"], cwd, False
    )
    if pushed.returncode != 0:
        lines = pushed.stderr.strip().splitlines()
        detail = lines[-1] if lines else f"git push exit {pushed.returncode}"
        rejected = any(
            marker in pushed.stderr
            for marker in (
                "[rejected]",
                "non-fast-forward",
                "fetch first",
                "stale info",
            )
        )
        if rejected:
            raise HardStop(f"push to {args.branch} rejected (foreign push?): {detail}")
        raise CommandError(f"push to {args.branch} failed: {detail}")
    return head


def base(args: argparse.Namespace, cwd: Path) -> str:
    if args.base == MAIN:
        return "verdict=noop reason=base is main"
    if git(cwd, "rev-parse", "--abbrev-ref", "HEAD") != args.branch:
        raise HardStop(f"HEAD is not on {args.branch}")
    if git(cwd, "status", "--porcelain"):
        # The merge steps reset --hard on failure; never do that over unsaved work.
        raise HardStop("worktree has uncommitted changes; commit them before Base")
    parent = query_parent(args, cwd)
    if parent is None:
        if not git(cwd, "ls-remote", "--heads", "origin", args.parent_branch):
            raise HardStop("unmerged parent with no branch on origin")
        return "verdict=noop reason=parent has no PR yet"
    if parent.state == "OPEN":
        return f"verdict=noop reason=parent #{parent.number} open"
    if parent.state != "MERGED" or parent.squash is None:
        raise HardStop(f"parent #{parent.number} closed unmerged")
    if parent.base != MAIN:
        raise HardStop(f"parent #{parent.number} merged into {parent.base}, not {MAIN}")
    _, resolved = restack(cwd, parent, args.parent_head)
    pushed = push(cwd, args)
    line = f"verdict=ok base={MAIN} parent_head={parent.head} pushed={pushed}"
    return line + (f" resolved={','.join(resolved)}" if resolved else "")


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument(
        "--branch", required=True, help="the child's own branch (BRANCH)"
    )
    parser.add_argument("--base", required=True, help="the state record's base (BASE)")
    parser.add_argument("--pr", type=int, help="the child's PR number, if it has one")
    parent = parser.add_mutually_exclusive_group(required=True)
    parent.add_argument("--parent-pr", type=int)
    parent.add_argument("--parent-branch")
    parser.add_argument(
        "--parent-head", required=True, help="the recorded parent head SHA (40 hex)"
    )
    args = parser.parse_args(argv)
    if not SHA.fullmatch(args.parent_head):
        parser.error("--parent-head must be a full 40-hex SHA")
    return args


def main(argv: list[str] | None = None, cwd: Path | None = None) -> int:
    args = arguments(argv)
    cwd = cwd or Path.cwd()
    try:
        line, status = base(args, cwd), 0
    except HardStop as exc:
        line, status = f"verdict=hard_stop reason={exc}", 1
    except (CommandError, OSError, ValueError) as exc:
        line, status = f"verdict=error reason={exc}", 3
    print(line, flush=True)
    return status


if __name__ == "__main__":
    sys.exit(main())
