"""Linear reads and writes the factory needs, without an MCP server.

The exchange-bidder factory used Ranger's Linear tools (`save_issue`
addLabels/removeLabels, comments). This repository has no agent platform,
so every phase calls this script instead. Each subcommand prints JSON on
stdout; writes are idempotent so a re-run after a dead session converges.

  issue <id>                     ticket, comments, labels, relations, branch
  set-label <id> <state>         single-select within the `Factory` group
  upsert-comment <id> --marker M --body-file F
                                 edit the comment whose first line is M, or create it
  working <id>                   the ticket's project's `working` tickets with heartbeats
  children <id>                  tickets blockedBy <id>, with their other parents and labels
  ensure-labels                  create the `Factory` group and its four labels if missing
  ready [--team KEY]             tickets carrying `factory:ready`, oldest first

The API key comes from LINEAR_API_KEY, else ~/.config/linear/embodied-ai-lab.key.
Never print the key.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.linear.app/graphql"
KEY_FILE = Path.home() / ".config" / "linear" / "embodied-ai-lab.key"
GROUP = "Factory"
STATES = ("ready", "working", "needs-human", "human-ready")
LABELS = {state: f"factory:{state}" for state in STATES}
DEFAULT_TEAM = "JWA"
HEARTBEAT = re.compile(r"^run: (?P<run>\S+) · heartbeat (?P<time>\S+)", re.MULTILINE)
STATE_LINE = re.compile(
    r"^phase: (?P<phase>\S+) · (?P<status>[a-z-]+) · head (?P<head>\S+)", re.MULTILINE
)


class LinearError(Exception):
    pass


def api_key() -> str:
    key = os.environ.get("LINEAR_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text().strip()
    except OSError as exc:
        raise LinearError(f"no Linear key: set LINEAR_API_KEY or create {KEY_FILE}") from exc


def graphql(query: str, variables: dict | None = None, transport=None) -> dict:
    """POST one GraphQL document. `transport` is injected by tests."""
    payload = {"query": query, "variables": variables or {}}
    if transport is not None:
        body = transport(payload)
    else:
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={"Authorization": api_key(), "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise LinearError(f"Linear HTTP {exc.code}: {exc.read()[:300]!r}") from exc
        except urllib.error.URLError as exc:
            raise LinearError(f"Linear unreachable: {exc.reason}") from exc
    if body.get("errors"):
        raise LinearError("; ".join(e.get("message", "?") for e in body["errors"]))
    return body.get("data") or {}


ISSUE_FIELDS = """
  id identifier title description branchName url
  state { name type }
  project { id name }
  labels { nodes { id name parent { name } } }
  relations { nodes { type relatedIssue { identifier } } }
  inverseRelations { nodes { type issue { identifier } } }
"""

ISSUE_QUERY = f"""
query($id: String!) {{
  issue(id: $id) {{
    {ISSUE_FIELDS}
    comments(first: 100) {{ nodes {{ id body createdAt url user {{ name }} }} }}
  }}
}}
"""

LABEL_CREATE = (
    "mutation($input: IssueLabelCreateInput!) "
    "{ issueLabelCreate(input: $input) { issueLabel { id name } } }"
)
ISSUE_LABELS_UPDATE = (
    "mutation($id: String!, $labelIds: [String!]!) "
    "{ issueUpdate(id: $id, input: {labelIds: $labelIds}) { success } }"
)
COMMENT_UPDATE = (
    "mutation($id: String!, $body: String!) "
    "{ commentUpdate(id: $id, input: {body: $body}) { success } }"
)
COMMENT_CREATE = (
    "mutation($issueId: String!, $body: String!) "
    "{ commentCreate(input: {issueId: $issueId, body: $body}) { comment { id url } } }"
)


def issue(identifier: str, transport=None) -> dict:
    data = graphql(ISSUE_QUERY, {"id": identifier}, transport)
    found = data.get("issue")
    if not found:
        raise LinearError(f"issue {identifier} not found")
    found["blockedBy"] = sorted(
        r["issue"]["identifier"]
        for r in found["inverseRelations"]["nodes"]
        if r["type"] == "blocks"
    )
    found["blocks"] = sorted(
        r["relatedIssue"]["identifier"]
        for r in found["relations"]["nodes"]
        if r["type"] == "blocks"
    )
    found["factoryLabel"] = factory_label(found["labels"]["nodes"])
    found["factoryState"] = next(
        (c for c in found["comments"]["nodes"] if first_line(c["body"]) == "**Factory state**"),
        None,
    )
    return found


def first_line(text: str) -> str:
    return (text or "").strip().splitlines()[0].strip() if (text or "").strip() else ""


def factory_label(labels: list[dict]) -> str | None:
    """The one `Factory` label a ticket carries, as its state name, or None."""
    for label in labels:
        name = label["name"]
        if (label.get("parent") or {}).get("name") == GROUP or name in LABELS.values():
            return name.split(":", 1)[1] if ":" in name else name
    return None


LABELS_QUERY = """
query { issueLabels(first: 250) { nodes { id name isGroup parent { id name } team { id key } } } }
"""


def label_catalog(transport=None) -> list[dict]:
    return graphql(LABELS_QUERY, None, transport)["issueLabels"]["nodes"]


def ensure_labels(team_key: str, transport=None) -> dict:
    """Create the `Factory` group and its four labels on the team, if absent.

    The group is single-select, so a ticket carries one factory state at a
    time; Linear enforces that when the child labels share a group parent.
    """
    catalog = label_catalog(transport)
    team_id = next(
        (l["team"]["id"] for l in catalog if l.get("team") and l["team"]["key"] == team_key), None
    )
    if team_id is None:
        team_id = graphql(
            "query($key: String!) { teams(filter: {key: {eq: $key}}) { nodes { id } } }",
            {"key": team_key},
            transport,
        )["teams"]["nodes"][0]["id"]
    group = next((l for l in catalog if l["name"] == GROUP and l["isGroup"]), None)
    created = []
    if group is None:
        group = graphql(
            LABEL_CREATE,
            {"input": {"name": GROUP, "teamId": team_id, "isGroup": True, "color": "#5E6AD2"}},
            transport,
        )["issueLabelCreate"]["issueLabel"]
        created.append(GROUP)
    existing = {l["name"] for l in catalog if (l.get("parent") or {}).get("name") == GROUP}
    colors = {
        "ready": "#26B5CE",
        "working": "#F2C94C",
        "needs-human": "#EB5757",
        "human-ready": "#4CB782",
    }
    for state, name in LABELS.items():
        if name in existing:
            continue
        graphql(
            LABEL_CREATE,
            {
                "input": {
                    "name": name,
                    "teamId": team_id,
                    "parentId": group["id"],
                    "color": colors[state],
                }
            },
            transport,
        )
        created.append(name)
    return {"group": GROUP, "created": created, "labels": list(LABELS.values())}


def set_label(identifier: str, state: str, transport=None) -> dict:
    """Swap the ticket's `Factory` label to `state` (one write, single-select)."""
    if state not in STATES:
        raise LinearError(f"state must be one of {', '.join(STATES)}")
    found = issue(identifier, transport)
    catalog = label_catalog(transport)
    wanted = next(
        (
            l["id"]
            for l in catalog
            if l["name"] == LABELS[state] and (l.get("parent") or {}).get("name") == GROUP
        ),
        None,
    )
    if wanted is None:
        raise LinearError(f"label {LABELS[state]} missing; run ensure-labels")
    group_ids = {l["id"] for l in catalog if (l.get("parent") or {}).get("name") == GROUP}
    kept = [l["id"] for l in found["labels"]["nodes"] if l["id"] not in group_ids]
    before = found["factoryLabel"]
    graphql(
        ISSUE_LABELS_UPDATE,
        {"id": found["id"], "labelIds": kept + [wanted]},
        transport,
    )
    return {"issue": identifier, "before": before, "after": state}


def upsert_comment(identifier: str, marker: str, body: str, transport=None) -> dict:
    """Edit the comment whose first line starts with `marker`, or create it.

    The state record's first line is exactly `**Factory state**`; the packet's
    first line is `**Proof of done** · <ticket> · ...`, so match by prefix.
    """
    if not first_line(body).startswith(marker):
        raise LinearError(f"body must start with the marker line {marker!r}")
    found = issue(identifier, transport)
    existing = next(
        (c for c in found["comments"]["nodes"] if first_line(c["body"]).startswith(marker)), None
    )
    if existing:
        graphql(
            COMMENT_UPDATE,
            {"id": existing["id"], "body": body},
            transport,
        )
        return {
            "issue": identifier,
            "comment": existing["id"],
            "url": existing.get("url"),
            "action": "updated",
        }
    made = graphql(
        COMMENT_CREATE,
        {"issueId": found["id"], "body": body},
        transport,
    )["commentCreate"]["comment"]
    return {"issue": identifier, "comment": made["id"], "url": made.get("url"), "action": "created"}


PROJECT_WORKING_QUERY = """
query($project: ID!, $label: String!) {
  issues(first: 50, filter: {project: {id: {eq: $project}}, labels: {name: {eq: $label}}}) {
    nodes { identifier comments(first: 50) { nodes { body } } }
  }
}
"""


def working(identifier: str, transport=None) -> list[dict]:
    """Every `working` ticket in the ticket's project, with its lease and state line.

    Pickup's watchdog flips the ones whose heartbeat is over three hours old.
    """
    found = issue(identifier, transport)
    if not found.get("project"):
        return []
    rows = graphql(
        PROJECT_WORKING_QUERY,
        {"project": found["project"]["id"], "label": LABELS["working"]},
        transport,
    )["issues"]["nodes"]
    out = []
    for row in rows:
        record = next(
            (
                c["body"]
                for c in row["comments"]["nodes"]
                if first_line(c["body"]) == "**Factory state**"
            ),
            "",
        )
        beat = HEARTBEAT.search(record)
        state = STATE_LINE.findall(record)
        out.append(
            {
                "identifier": row["identifier"],
                "run": beat.group("run") if beat else None,
                "heartbeat": beat.group("time") if beat else None,
                "phase": state[-1][0] if state else None,
                "status": state[-1][1] if state else None,
            }
        )
    return out


def children(identifier: str, transport=None) -> list[dict]:
    """Tickets blockedBy this one: identifier, every parent, current factory label."""
    found = issue(identifier, transport)
    out = []
    for child_id in found["blocks"]:
        child = issue(child_id, transport)
        out.append(
            {
                "identifier": child_id,
                "parents": child["blockedBy"],
                "onlyParent": child["blockedBy"] == [identifier],
                "factoryLabel": child["factoryLabel"],
            }
        )
    return out


READY_QUERY = """
query($team: String!, $label: String!) {
  issues(first: 50, orderBy: createdAt,
         filter: {team: {key: {eq: $team}}, labels: {name: {eq: $label}},
                  state: {type: {nin: ["completed", "canceled"]}}}) {
    nodes { identifier title branchName createdAt }
  }
}
"""


def ready(team_key: str, transport=None) -> list[dict]:
    return graphql(READY_QUERY, {"team": team_key, "label": LABELS["ready"]}, transport)["issues"][
        "nodes"
    ]


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("issue").add_argument("id")
    p = sub.add_parser("set-label")
    p.add_argument("id")
    p.add_argument("state", choices=STATES)
    p = sub.add_parser("upsert-comment")
    p.add_argument("id")
    p.add_argument("--marker", required=True)
    p.add_argument("--body-file", required=True, type=Path)
    sub.add_parser("working").add_argument("id")
    sub.add_parser("children").add_argument("id")
    sub.add_parser("ensure-labels").add_argument("--team", default=DEFAULT_TEAM)
    sub.add_parser("ready").add_argument("--team", default=DEFAULT_TEAM)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, transport=None) -> int:
    args = arguments(argv)
    try:
        if args.command == "issue":
            result = issue(args.id, transport)
        elif args.command == "set-label":
            result = set_label(args.id, args.state, transport)
        elif args.command == "upsert-comment":
            result = upsert_comment(args.id, args.marker, args.body_file.read_text(), transport)
        elif args.command == "working":
            result = working(args.id, transport)
        elif args.command == "children":
            result = children(args.id, transport)
        elif args.command == "ensure-labels":
            result = ensure_labels(args.team, transport)
        else:
            result = ready(args.team, transport)
    except LinearError as exc:
        print(f"factory_linear: {exc}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
