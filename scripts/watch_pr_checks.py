import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

GH_TIMEOUT_SECONDS = 30
REQUIRED_CHECK = "check"


class WatchError(Exception):
    pass


class DeadlineError(WatchError):
    pass


class Interrupted(WatchError):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f"interrupted by signal {signum}")


def positive_seconds(value):
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be positive finite seconds") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be positive finite seconds")
    return seconds


def matching(pattern, description):
    def validate(value):
        if not re.fullmatch(pattern, value):
            raise argparse.ArgumentTypeError(description)
        return value

    return validate


def arguments(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Read-only, SHA-pinned CI Gate watcher; not review or merge approval."
        )
    )
    parser.add_argument(
        "--repo",
        required=True,
        type=matching(
            r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*",
            "must be OWNER/REPO without whitespace or shell syntax",
        ),
    )
    parser.add_argument(
        "--pr",
        required=True,
        type=matching(r"[1-9][0-9]*", "must be a positive PR number"),
    )
    parser.add_argument(
        "--head-sha",
        required=True,
        type=matching(r"[0-9a-fA-F]{40}", "must be exactly 40 hex characters"),
    )
    parser.add_argument("--interval-seconds", type=positive_seconds, default=15)
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=1800)
    args = parser.parse_args(argv)
    args.head_sha = args.head_sha.lower()
    return args


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise DeadlineError("watch deadline expired")
    return seconds


def gh_api(endpoint, deadline, paginated=False):
    command = ["gh", "api", "--method", "GET", endpoint]
    if paginated:
        command.extend(["--paginate", "--slurp"])
    timeout_seconds = min(GH_TIMEOUT_SECONDS, remaining(deadline))
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        raise WatchError("could not start gh") from exc
    communicated = False
    try:
        try:
            stdout, _ = process.communicate(timeout=timeout_seconds)
            communicated = True
        except subprocess.TimeoutExpired as exc:
            raise DeadlineError("gh API subprocess timed out") from exc
        remaining(deadline)
        if process.returncode:
            raise WatchError(
                f"gh API failed (exit {process.returncode}); "
                "check authentication and API access"
            )
        try:
            return json.loads(stdout)
        except (ValueError, RecursionError) as exc:
            raise WatchError("malformed gh API JSON") from exc
    finally:
        if not communicated:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                if process.poll() is None:
                    try:
                        process.kill()
                    except (ProcessLookupError, PermissionError):
                        pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            print(
                "warning: owned gh process could not be reaped during cleanup",
                file=sys.stderr,
            )
        finally:
            process.stdout.close()
            process.stderr.close()


@contextmanager
def watcher_lock(repo, pr):
    key = hashlib.sha256(f"{repo.lower()}#{pr}".encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / f"pr-ci-watch-{os.getuid()}-{key}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WatchError("another local watcher owns this repository/PR") from exc
        yield


def check_head(args, deadline):
    data = gh_api(f"repos/{args.repo}/pulls/{args.pr}", deadline)
    if not isinstance(data, dict) or not isinstance(data.get("head"), dict):
        raise WatchError("malformed PR head response")
    sha = data["head"].get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise WatchError("malformed PR head SHA")
    if sha.lower() != args.head_sha:
        raise WatchError(
            f"PR head changed or differs from expected SHA {args.head_sha}"
        )


def timestamp(value):
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if not isinstance(value, str):
        raise WatchError("malformed check timestamp")
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError("missing timezone")
        return result.astimezone(UTC)
    except ValueError as exc:
        raise WatchError("malformed check timestamp") from exc


def verify_gate(run, args, deadline, verified_runs):
    app = run.get("app")
    if not isinstance(app, dict) or app.get("slug") != "github-actions":
        raise WatchError("uncertain CI Gate provenance: foreign or missing app")
    url = run.get("details_url")
    pattern = (
        rf"https://github\.com/{re.escape(args.repo)}/actions/runs/([1-9][0-9]*)"
        r"(?:/job/[1-9][0-9]*)?"
    )
    match = (
        re.fullmatch(pattern, url, flags=re.IGNORECASE)
        if isinstance(url, str)
        else None
    )
    if match is None:
        raise WatchError("uncertain CI Gate provenance: invalid Actions details_url")
    run_id = int(match[1])
    if run_id not in verified_runs:
        data = gh_api(f"repos/{args.repo}/actions/runs/{run_id}", deadline)
        validate_workflow_run(data, args, run_id)
        verified_runs[run_id] = data
    return verified_runs[run_id]


def validate_workflow_run(data, args, run_id=None):
    if (
        not isinstance(data, dict)
        or type(data.get("id")) is not int
        or data["id"] <= 0
        or (run_id is not None and data["id"] != run_id)
        or data.get("path") != ".github/workflows/ci.yml"
        or not isinstance(data.get("head_sha"), str)
        or data["head_sha"].lower() != args.head_sha
        or data.get("event") not in ("pull_request", "push", "merge_group")
        or type(data.get("run_attempt")) is not int
        or data["run_attempt"] <= 0
        or data.get("status")
        not in ("queued", "in_progress", "completed", "waiting", "pending", "requested")
        or (
            data["status"] == "completed"
            and data.get("conclusion")
            not in (
                "success",
                "failure",
                "cancelled",
                "skipped",
                "neutral",
                "timed_out",
                "action_required",
                "stale",
                "startup_failure",
            )
        )
        or (data["status"] != "completed" and data.get("conclusion") is not None)
    ):
        raise WatchError(
            "uncertain CI Gate provenance: workflow, SHA, event, "
            "run ID or attempt mismatch"
        )


def page_items(pages, key):
    if not isinstance(pages, list) or not pages:
        raise WatchError(f"malformed {key} pages")
    items = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get(key), list):
            raise WatchError(f"malformed {key} page")
        items.extend(page[key])
    return items


def latest_workflow_run(args, deadline):
    pages = gh_api(
        f"repos/{args.repo}/actions/workflows/ci.yml/runs?head_sha={args.head_sha}&per_page=100",
        deadline,
        paginated=True,
    )
    runs = {}
    for run in page_items(pages, "workflow_runs"):
        validate_workflow_run(run, args)
        if run["id"] in runs and runs[run["id"]] != run:
            raise WatchError("conflicting duplicate workflow runs")
        runs[run["id"]] = run
    if not runs:
        return None
    run_id = max(runs)
    current = gh_api(f"repos/{args.repo}/actions/runs/{run_id}", deadline)
    validate_workflow_run(current, args, run_id)
    return current


def attempt_gate_ids(current, args, deadline):
    pages = gh_api(
        f"repos/{args.repo}/actions/runs/{current['id']}/attempts/{current['run_attempt']}/jobs?per_page=100",
        deadline,
        paginated=True,
    )
    ids = set()
    for job in page_items(pages, "jobs"):
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            raise WatchError("malformed attempt job")
        if job["name"] != REQUIRED_CHECK:
            continue
        url = job.get("check_run_url")
        pattern = rf"https://api\.github\.com/repos/{re.escape(args.repo)}/check-runs/([1-9][0-9]*)"
        match = (
            re.fullmatch(pattern, url, flags=re.IGNORECASE)
            if isinstance(url, str)
            else None
        )
        if (
            match is None
            or type(job.get("run_id")) is not int
            or job["run_id"] != current["id"]
            or type(job.get("run_attempt")) is not int
            or job["run_attempt"] != current["run_attempt"]
            or not isinstance(job.get("head_sha"), str)
            or job["head_sha"].lower() != args.head_sha
        ):
            raise WatchError(
                "uncertain CI Gate provenance: current attempt job mismatch"
            )
        ids.add(int(match[1]))
    return ids


def workflow_snapshot(run):
    if run is None:
        return None
    return tuple(run[key] for key in ("id", "run_attempt", "status", "conclusion"))


def ci_state(pages, args, deadline):
    return ci_observation(pages, args, deadline)["state"]


def ci_observation(pages, args, deadline):
    current = latest_workflow_run(args, deadline)
    verified_runs = {} if current is None else {current["id"]: current}
    # Informational jobs may still be running or fail after CI Gate succeeds.
    active = current is not None and current["status"] in ("in_progress", "completed")
    gate_ids = attempt_gate_ids(current, args, deadline) if active else set()
    eligible_ids = set()

    def eligible(check):
        run = verify_gate(check, args, deadline, verified_runs)
        accepted = active and run["id"] == current["id"] and check["id"] in gate_ids
        if accepted:
            eligible_ids.add(check["id"])
        return accepted

    state = gate_state(pages, args.head_sha, verify=eligible)
    if state == "success":
        final = latest_workflow_run(args, deadline)
        if workflow_snapshot(final) != workflow_snapshot(current):
            state = "pending"
    return {
        "state": state,
        "workflow": None
        if current is None
        else {
            key: current[key] for key in ("id", "run_attempt", "status", "conclusion")
        },
        "check_ids": sorted(eligible_ids),
    }


def gate_state(pages, expected_sha, verify=None):
    if not isinstance(pages, list) or not pages:
        raise WatchError("malformed check-runs pages")
    gates = {}
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("check_runs"), list):
            raise WatchError("malformed check-runs page")
        for run in page["check_runs"]:
            if not isinstance(run, dict) or not isinstance(run.get("name"), str):
                raise WatchError("malformed check run")
            sha = run.get("head_sha")
            if not isinstance(sha, str) or sha.lower() != expected_sha:
                raise WatchError("check head_sha differs from expected SHA")
            if run["name"] != REQUIRED_CHECK:
                continue
            run_id = run.get("id")
            if type(run_id) is not int or run_id <= 0:
                raise WatchError("malformed CI Gate id")
            if run_id in gates and gates[run_id] != run:
                raise WatchError("conflicting duplicate CI Gate records")
            status = run.get("status")
            conclusion = run.get("conclusion")
            if not isinstance(status, str) or status not in {
                "queued",
                "in_progress",
                "completed",
                "waiting",
                "pending",
                "requested",
            }:
                raise WatchError("malformed CI Gate status")
            if status == "completed":
                if not isinstance(conclusion, str) or conclusion not in {
                    "success",
                    "failure",
                    "cancelled",
                    "skipped",
                    "neutral",
                    "timed_out",
                    "action_required",
                    "stale",
                    "startup_failure",
                }:
                    raise WatchError("malformed CI Gate conclusion")
                if run.get("completed_at") is None:
                    raise WatchError("completed CI Gate has no completion timestamp")
            elif conclusion is not None:
                raise WatchError("unfinished CI Gate has a conclusion")
            timestamp(run.get("started_at"))
            timestamp(run.get("completed_at"))
            if verify is not None and not verify(run):
                continue
            gates[run_id] = run
    if not gates:
        return "pending"
    latest = max(
        gates.values(),
        key=lambda run: (
            run["id"],
            timestamp(run.get("started_at")),
            timestamp(run.get("completed_at")),
        ),
    )
    if latest["status"] != "completed":
        return "pending"
    if latest["conclusion"] != "success":
        raise WatchError(
            f"CI Gate concluded {latest['conclusion']} (check {latest['id']})"
        )
    return "success"


def watch(args):
    deadline = time.monotonic() + args.timeout_seconds
    with watcher_lock(args.repo, args.pr):
        while True:
            check_head(args, deadline)
            pages = gh_api(
                f"repos/{args.repo}/commits/{args.head_sha}/check-runs?per_page=100&filter=all",
                deadline,
                paginated=True,
            )
            state = ci_state(pages, args, deadline)
            check_head(args, deadline)
            remaining(deadline)
            print(
                f"{args.repo} PR #{args.pr} {args.head_sha}: CI Gate {state} (CI only)",
                flush=True,
            )
            if state == "success":
                return 0
            time.sleep(min(args.interval_seconds, remaining(deadline)))


def interrupted(signum, frame):
    raise Interrupted(signum)


def main(argv=None):
    args = arguments(argv)
    previous = {
        sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        return watch(args)
    except Interrupted as exc:
        print(str(exc), file=sys.stderr)
        return 128 + exc.signum
    except DeadlineError as exc:
        print(str(exc), file=sys.stderr)
        return 124
    except (WatchError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
