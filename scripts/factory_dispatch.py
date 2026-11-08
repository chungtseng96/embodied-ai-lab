"""Factory dispatcher: the poll that replaces a Ranger `linear_event` automation.

The exchange-bidder factory starts a run when Linear fires an
`Issue.update.label` event into Ranger. This repository has no agent platform
listening for webhooks, so a scheduler (a Superset automation, launchd, or
cron) runs this script instead. It lists the tickets labeled `factory:ready`,
oldest first, and either prints the one to run or launches a headless Claude
Code session on it in a fresh worktree.

  factory_dispatch.py pick            print the ticket id a run should take, or nothing
  factory_dispatch.py run             pick, then run `claude -p "/factory <id>"` in a worktree
  factory_dispatch.py run --dry-run   print the command instead of running it

The run itself swaps the label to `factory:working` as it claims, so the next
poll does not pick the same ticket. A `ready` ticket whose state record still
holds a live lease (a run between its claim and its label write) is skipped;
one whose branch already exists is not, because a paused or re-released run
resumes from that branch. One dispatcher runs at a
time per repository (a lock file), so two polls never start two sessions.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import factory_linear

SLUG = re.compile(r"[^a-z0-9]+")
LIVE_LEASE = timedelta(minutes=30)


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def heartbeat(record: str | None) -> datetime | None:
    """The `run:` heartbeat of a Factory state comment, or None when it has none."""
    match = factory_linear.HEARTBEAT.search(record or "")
    if not match:
        return None
    raw = match.group("time").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def live_lease(found: dict, now: datetime) -> bool:
    state = found.get("factoryState") or {}
    beat = heartbeat(state.get("body"))
    return beat is not None and now - beat < LIVE_LEASE


def pick(team: str, transport=None, now: datetime | None = None) -> dict | None:
    """The oldest `ready` ticket that no live run holds."""
    now = now or datetime.now(UTC)
    for row in factory_linear.ready(team, transport):
        if live_lease(factory_linear.issue(row["identifier"], transport), now):
            continue
        return row
    return None


def worktree_for(ticket: str, root: Path) -> Path:
    slug = SLUG.sub("-", ticket.lower()).strip("-")
    return root / ".claude" / "worktrees" / f"factory-{slug}"


def claude_command(ticket: str, worktree: Path, base: str) -> list[str]:
    return [
        "claude",
        "-p",
        f"/factory {ticket}",
        "--permission-mode",
        "bypassPermissions",
        "--add-dir",
        str(worktree),
    ]


def ensure_worktree(worktree: Path, base: str, root: Path) -> None:
    if worktree.exists():
        return
    subprocess.run(["git", "fetch", "origin", base], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree), f"origin/{base}"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def lock_path(root: Path) -> Path:
    digest = re.sub(r"[^a-zA-Z0-9]", "_", str(root))
    return Path(tempfile.gettempdir()) / f"factory-dispatch-{digest}.lock"


def main(argv: list[str] | None = None, transport=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["pick", "run"])
    parser.add_argument("--team", default=factory_linear.DEFAULT_TEAM)
    parser.add_argument("--base", default="main")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root()
    with open(lock_path(root), "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("factory_dispatch: another dispatcher holds the lock", file=sys.stderr)
            return 2
        try:
            chosen = pick(args.team, transport)
        except factory_linear.LinearError as exc:
            print(f"factory_dispatch: {exc}", file=sys.stderr)
            return 1
        if chosen is None:
            print(json.dumps({"ticket": None}))
            return 0
        ticket = chosen["identifier"]
        if args.command == "pick":
            print(
                json.dumps(
                    {"ticket": ticket, "title": chosen["title"], "branch": chosen.get("branchName")}
                )
            )
            return 0
        worktree = worktree_for(ticket, root)
        command = claude_command(ticket, worktree, args.base)
        if args.dry_run:
            print(
                json.dumps(
                    {"ticket": ticket, "worktree": str(worktree), "command": shlex.join(command)}
                )
            )
            return 0
        ensure_worktree(worktree, args.base, root)
        env = dict(os.environ)
        result = subprocess.run(command, cwd=worktree, env=env, check=False)
        print(json.dumps({"ticket": ticket, "worktree": str(worktree), "exit": result.returncode}))
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
