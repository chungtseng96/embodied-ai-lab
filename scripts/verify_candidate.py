"""One-shot head CI/review observation; tested base and merge readiness unverified."""

import argparse
import contextlib
import io
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import watch_pr_checks as ci

DEFAULT_TIMEOUT_SECONDS = 60
MAX_FEEDBACK_ITEMS = 20
MAX_FEEDBACK_BODY_CHARACTERS = 1000


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        required=True,
        type=ci.matching(
            r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", "use OWNER/REPO"
        ),
    )
    parser.add_argument(
        "--pr", required=True, type=ci.matching(r"[1-9][0-9]*", "use a PR number")
    )
    parser.add_argument(
        "--head-sha",
        required=True,
        type=ci.matching(r"[0-9a-fA-F]{40}", "use a full 40-hex candidate SHA"),
    )
    parser.add_argument("--base", required=True)
    parser.add_argument(
        "--reviewer",
        action="append",
        default=[],
        type=ci.matching(r"[A-Za-z0-9][A-Za-z0-9-]*", "use an explicit reviewer login"),
    )
    parser.add_argument("--local-receipt", type=Path)
    parser.add_argument(
        "--timeout-seconds", type=ci.positive_seconds, default=DEFAULT_TIMEOUT_SECONDS
    )
    parser.add_argument("--wait-for-ci", action="store_true")
    # Exit by the CI observation alone. Callers that gate approval themselves
    # (the factory reads the JSON verdict) otherwise see exit 1 on green CI.
    parser.add_argument("--exit-on-ci", action="store_true")
    parser.add_argument("--ci-timeout-seconds", type=ci.positive_seconds, default=1800)
    parser.add_argument("--ci-interval-seconds", type=ci.positive_seconds, default=15)
    args = parser.parse_args(argv)
    args.head_sha = args.head_sha.lower()
    return args


def pr_snapshot(pr: object, args: argparse.Namespace) -> tuple[str, str, str, str]:
    if not isinstance(pr, dict):
        raise ci.WatchError("malformed PR")
    head = pr.get("head", {}).get("sha")
    base = pr.get("base", {})
    sha = base.get("sha")
    author = pr.get("user", {}).get("login")
    if (
        head != args.head_sha
        or base.get("ref") != args.base
        or not isinstance(sha, str)
        or not re.fullmatch("[a-f0-9]{40}", sha)
        or not isinstance(author, str)
        or pr.get("state") not in {"open", "closed"}
    ):
        raise ci.WatchError("PR head/base differs from the expected candidate")
    return head, sha, author, pr["state"]


def list_pages(pages: object) -> list[dict]:
    if (
        not isinstance(pages, list)
        or not pages
        or any(
            not isinstance(page, list)
            or any(not isinstance(item, dict) for item in page)
            for page in pages
        )
    ):
        raise ci.WatchError("malformed review/comment pagination")
    return [item for page in pages for item in page]


def review_state(reviews: list[dict], args: argparse.Namespace, author: str) -> dict:
    latest = {}
    for review in reviews:
        user = review.get("user")
        if (
            not isinstance(user, dict)
            or not isinstance(user.get("login"), str)
            or type(review.get("id")) is not int
            or review["id"] <= 0
            or review.get("state")
            not in {
                "APPROVED",
                "CHANGES_REQUESTED",
                "COMMENTED",
                "DISMISSED",
                "PENDING",
            }
        ):
            raise ci.WatchError("malformed review")
        if review["state"] not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            continue
        login = user["login"].lower()
        if login not in latest or review["id"] > latest[login]["id"]:
            latest[login] = review
    blocking = sorted(
        login
        for login, review in latest.items()
        if review["state"] == "CHANGES_REQUESTED"
    )
    approved = sorted(
        login
        for login, review in latest.items()
        if review["state"] == "APPROVED"
        and review.get("commit_id") == args.head_sha
        and review["user"].get("type") == "User"
        and login != author.lower()
    )
    required = sorted({login.lower() for login in args.reviewer})
    state = (
        "approved_current_candidate"
        if (required and not blocking and set(required) <= set(approved))
        else "not_approved_current_candidate"
    )
    return {
        "state": state,
        "required": required,
        "approved": approved,
        "change_requests": blocking,
        "approval_source": "formal_reviews_only",
    }


def local_state(path: Path | None, expected_sha: str) -> dict:
    if path is None:
        return {"state": "not_provided"}
    try:
        if path.stat().st_size > 256 * 1024:
            return {"state": "unverified", "reason": "receipt exceeds size limit"}
        receipt = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"state": "unverified", "reason": "receipt is unreadable"}
    if not isinstance(receipt, dict):
        return {"state": "unverified", "reason": "invalid receipt"}
    source = receipt.get("source")
    if (
        receipt.get("version") != 1
        or receipt.get("kind") != "api_test"
        or receipt.get("state") != "passed"
        or receipt.get("exit_code") != 0
        or receipt.get("cleanup") != "complete"
        or not isinstance(source, dict)
        or source.get("head") != expected_sha
        or source.get("dirty") is not False
        or source != receipt.get("source_after")
        or not isinstance(source.get("fingerprint"), str)
        or not re.fullmatch("[a-f0-9]{64}", source["fingerprint"])
    ):
        return {
            "state": "unverified",
            "reason": "receipt is failed, dirty, stale, or incomplete",
        }
    return {
        "state": "recorded_pass_current_candidate",
        "limitation": "local unsigned receipt; not independent correctness proof",
    }


def feedback_observations(comments: list[dict]) -> list[dict]:
    observations = []
    for comment in comments:
        if type(comment.get("id")) is not int or comment["id"] <= 0:
            raise ci.WatchError("malformed feedback identity")
        body = comment.get("body", "")
        if body is None:
            body = ""
        user = comment.get("user", {})
        if not isinstance(body, str) or not isinstance(user, dict):
            raise ci.WatchError("malformed feedback")
        observations.append(
            {
                "id": comment["id"],
                "author": user.get("login"),
                "body_preview": body[:MAX_FEEDBACK_BODY_CHARACTERS],
                "body_truncated": len(body) > MAX_FEEDBACK_BODY_CHARACTERS,
                "url": comment.get("html_url"),
                "commit_id": comment.get("commit_id"),
                "untrusted_content": True,
                "approval": "not_inferred",
            }
        )
    return sorted(observations, key=lambda value: value["id"], reverse=True)[
        :MAX_FEEDBACK_ITEMS
    ]


def observe(args: argparse.Namespace) -> tuple[dict, int]:
    deadline = time.monotonic() + args.timeout_seconds
    prefix = f"repos/{args.repo}"
    tested_base = {
        "state": "unverified",
        "reason": "PR base observations are not evidence of the tree tested by CI",
    }
    report = {
        "version": 1,
        "kind": "candidate_observation",
        "observed_at": datetime.now(UTC).isoformat(),
        "repo": args.repo,
        "pr": args.pr,
        "candidate_sha": args.head_sha,
        "expected_base": args.base,
        "state": "incomplete",
        "ci": {"state": "unknown", "tested_base": tested_base},
        "review": {"state": "unknown"},
        "local": local_state(args.local_receipt, args.head_sha),
        "deployment": {"state": "not_checked"},
        "behavior": {"state": "not_verified"},
        "limitation": "one-shot evidence, not branch-policy or merge authorization",
    }
    try:
        initial = ci.gh_api(f"{prefix}/pulls/{args.pr}", deadline)
        snapshot = pr_snapshot(initial, args)
        report["observed_pr_base_sha"] = snapshot[1]
        checks = ci.gh_api(
            f"{prefix}/commits/{args.head_sha}/check-runs?per_page=100&filter=all",
            deadline,
            paginated=True,
        )
        report["ci"] = ci.ci_observation(checks, args, deadline)
        report["ci"]["tested_base"] = tested_base
        ci_snapshot = ci.workflow_snapshot(report["ci"]["workflow"])
        reviews = list_pages(
            ci.gh_api(
                f"{prefix}/pulls/{args.pr}/reviews?per_page=100",
                deadline,
                paginated=True,
            )
        )
        report["review"] = review_state(reviews, args, snapshot[2])
        conversation = list_pages(
            ci.gh_api(
                f"{prefix}/issues/{args.pr}/comments?per_page=100",
                deadline,
                paginated=True,
            )
        )
        inline = list_pages(
            ci.gh_api(
                f"{prefix}/pulls/{args.pr}/comments?per_page=100",
                deadline,
                paginated=True,
            )
        )
        report["feedback"] = {
            "conversation_comments": len(conversation),
            "inline_comments": len(inline),
            "conversation_latest": feedback_observations(conversation),
            "inline_latest": feedback_observations(inline),
            "formal_reviews": len(reviews),
            "formal_review_latest": feedback_observations(reviews),
            "confidential": True,
            "resolution": "not_inferred_from_comments_or_reactions",
        }
        final_reviews = list_pages(
            ci.gh_api(
                f"{prefix}/pulls/{args.pr}/reviews?per_page=100",
                deadline,
                paginated=True,
            )
        )
        if review_state(final_reviews, args, snapshot[2]) != report["review"]:
            raise ci.WatchError("review decision changed during observation")
        report["feedback"]["formal_reviews"] = len(final_reviews)
        report["feedback"]["formal_review_latest"] = feedback_observations(
            final_reviews
        )
        if ci.workflow_snapshot(ci.latest_workflow_run(args, deadline)) != ci_snapshot:
            report["ci"]["state"] = "pending"
            raise ci.WatchError("CI workflow/run attempt changed during observation")
        final = ci.gh_api(f"{prefix}/pulls/{args.pr}", deadline)
        if pr_snapshot(final, args) != snapshot:
            raise ci.WatchError("PR head/base/state changed during observation")
        report["merge"] = {
            "observed": final.get("merged") is True,
            "commit": final.get("merge_commit_sha")
            if final.get("merged") is True
            else None,
        }
        if (
            report["ci"]["state"] == "success"
            and report["review"]["state"] == "approved_current_candidate"
            and report["local"]["state"] != "unverified"
        ):
            report["state"] = "head_ci_and_requested_reviews_observed"
            return report, 0
        return report, 1
    except (ci.WatchError, OSError, AttributeError, TypeError, KeyError) as exc:
        report["reason"] = str(exc)
        return report, 1


class Tee(io.StringIO):
    """Pass watcher output through to stderr while keeping a copy to classify."""

    def __init__(self, target):
        super().__init__()
        self.target = target

    def write(self, text: str) -> int:
        self.target.write(text)
        return super().write(text)


def verdict(report: dict, status: int | None, watcher: str) -> tuple[str, str]:
    """One word for the factory CI wait: green, failed, timeout, moved or error."""
    lines = [line for line in watcher.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    if status == 124:
        return "timeout", last
    if status:
        if status == 1 and "CI Gate concluded" in watcher:
            return "failed", last
        if status == 1 and ("head changed" in watcher or "differs" in watcher):
            return "moved", last
        return "error", last or f"watcher exit {status}"
    reason = report.get("reason", "")
    if re.search("head|base", reason) and re.search("changed|differs", reason):
        return "moved", reason
    if report.get("ci", {}).get("state") == "success" and not reason:
        return "green", ""
    if "CI Gate concluded" in reason:
        return "failed", reason
    return "error", reason or f"ci.state {report.get('ci', {}).get('state')}"


def with_verdict(report: dict, status: int | None, watcher: str) -> dict:
    report["verdict"], detail = verdict(report, status, watcher)
    if detail:
        report["verdict_reason"] = detail
    return report


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    watcher = ""
    if args.wait_for_ci:
        # Keep stdout a single JSON document; watcher progress belongs on stderr.
        tee = Tee(sys.stderr)
        with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
            status = ci.main(
                [
                    "--repo",
                    args.repo,
                    "--pr",
                    args.pr,
                    "--head-sha",
                    args.head_sha,
                    "--timeout-seconds",
                    str(args.ci_timeout_seconds),
                    "--interval-seconds",
                    str(args.ci_interval_seconds),
                ]
            )
        watcher = tee.getvalue()
        if status:
            failure = {
                "state": "incomplete",
                "head_sha": args.head_sha,
                "ci_wait_exit_code": status,
                "reason": "CI watcher did not succeed; see stderr. No approval inferred.",
            }
            print(json.dumps(with_verdict(failure, status, watcher), indent=2))
            return status
    report, status = observe(args)
    print(json.dumps(with_verdict(report, None, watcher), indent=2))
    if args.exit_on_ci and report.get("ci", {}).get("state") == "success":
        return 0
    return status


if __name__ == "__main__":
    sys.exit(main())
