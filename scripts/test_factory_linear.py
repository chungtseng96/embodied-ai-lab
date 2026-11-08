import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factory_linear

GROUP = {
    "id": "g1",
    "name": "Factory",
    "isGroup": True,
    "parent": None,
    "team": {"id": "t1", "key": "JWA"},
}
LABELS = [
    {
        "id": f"l-{s}",
        "name": f"factory:{s}",
        "isGroup": False,
        "parent": {"id": "g1", "name": "Factory"},
        "team": {"id": "t1", "key": "JWA"},
    }
    for s in factory_linear.STATES
]
PHASE_A = {
    "id": "pa",
    "name": "phase-a",
    "isGroup": False,
    "parent": None,
    "team": {"id": "t1", "key": "JWA"},
}


class FakeLinear:
    """Answers GraphQL documents by the operation they name; records writes."""

    def __init__(self, issues: dict, catalog: list):
        self.issues = issues
        self.catalog = catalog
        self.writes = []
        self.pages = {}
        self.ready_pages = None

    def __call__(self, payload):
        query, variables = payload["query"], payload["variables"]
        if "issueLabels(first" in query:
            return {"data": {"issueLabels": {"nodes": self.catalog}}}
        if "$after: String!" in query:
            field = query.split("issue(id: $id) { ")[1].split("(")[0]
            page = self.pages[(field, variables["after"])]
            return {"data": {"issue": {field: page}}}
        if query.lstrip().startswith("query($id: String!)"):
            found = self.issues.get(variables["id"])
            if found:
                for field in ("comments", "relations", "inverseRelations"):
                    found[field].setdefault("pageInfo", {"hasNextPage": False, "endCursor": None})
            return {"data": {"issue": found}}
        if (
            "issueUpdate" in query
            or "commentUpdate" in query
            or "commentCreate" in query
            or "issueLabelCreate" in query
        ):
            self.writes.append(payload)
            if "commentCreate" in query:
                return {
                    "data": {
                        "commentCreate": {
                            "comment": {"id": "c-new", "url": "https://linear.app/c-new"}
                        }
                    }
                }
            if "issueLabelCreate" in query:
                return {
                    "data": {
                        "issueLabelCreate": {
                            "issueLabel": {"id": "g-new", "name": variables["input"]["name"]}
                        }
                    }
                }
            return {"data": {"ok": {"success": True}}}
        if "labels: {name: {eq: $label}}" in query and "project" in query:
            return {"data": {"issues": {"nodes": self.project_rows()}}}
        if "orderBy: createdAt" in query:
            if self.ready_pages is not None:
                return {"data": {"issues": self.ready_pages[variables.get("after")]}}
            rows = [
                {
                    "identifier": i,
                    "title": v["title"],
                    "branchName": v["branchName"],
                    "createdAt": "x",
                }
                for i, v in self.issues.items()
                if any(l["name"] == variables["label"] for l in v["labels"]["nodes"])
            ]
            return {"data": {"issues": {"nodes": rows, "pageInfo": {"hasNextPage": False}}}}
        if "teams(filter" in query:
            return {"data": {"teams": {"nodes": [{"id": "t1"}]}}}
        raise AssertionError(f"unexpected query: {query[:80]}")

    def project_rows(self):
        return [
            {"identifier": i, "comments": v["comments"]}
            for i, v in self.issues.items()
            if any(l["name"] == "factory:working" for l in v["labels"]["nodes"])
        ]


def make_issue(identifier, labels=(), comments=(), blocked_by=(), blocks=(), project=True):
    return {
        "id": f"id-{identifier}",
        "identifier": identifier,
        "title": f"title {identifier}",
        "description": "Acceptance:\n- it works",
        "branchName": f"chungtseng96/{identifier.lower()}-slug",
        "url": f"https://linear.app/x/{identifier}",
        "state": {"name": "Todo", "type": "unstarted"},
        "team": {"id": "t1", "key": "JWA"},
        "project": {"id": "p1", "name": "P"} if project else None,
        "labels": {"nodes": list(labels)},
        "relations": {
            "nodes": [{"type": "blocks", "relatedIssue": {"identifier": b}} for b in blocks]
        },
        "inverseRelations": {
            "nodes": [{"type": "blocks", "issue": {"identifier": b}} for b in blocked_by]
        },
        "comments": {"nodes": list(comments)},
    }


STATE_COMMENT = {
    "id": "c1",
    "url": "https://linear.app/c1",
    "body": (
        "**Factory state**\n\nTicket: JWA-5\nrun: abcd1234 · heartbeat 2026-11-08T10:00Z\n\n"
        "phase: factory-implement · started · head 1a2b3c4 · 2026-11-08T10:00Z"
    ),
    "createdAt": "2026-11-08",
    "user": {"name": "me"},
}


class IssueTests(unittest.TestCase):
    def test_issue_derives_parents_children_label_and_state_record(self):
        fake = FakeLinear(
            {
                "JWA-5": make_issue(
                    "JWA-5",
                    labels=[LABELS[1], PHASE_A],
                    comments=[STATE_COMMENT],
                    blocked_by=["JWA-4"],
                    blocks=["JWA-6"],
                )
            },
            [GROUP, *LABELS, PHASE_A],
        )
        found = factory_linear.issue("JWA-5", fake)
        self.assertEqual(found["blockedBy"], ["JWA-4"])
        self.assertEqual(found["blocks"], ["JWA-6"])
        self.assertEqual(found["factoryLabel"], "working")
        self.assertEqual(found["factoryState"]["id"], "c1")

    def test_issue_follows_comment_pages_to_find_the_state_record(self):
        first = make_issue("JWA-5")
        first["comments"] = {
            "nodes": [{"id": "c0", "body": "older chatter", "url": None}],
            "pageInfo": {"hasNextPage": True, "endCursor": "cur-1"},
        }
        fake = FakeLinear({"JWA-5": first}, [])
        fake.pages[("comments", "cur-1")] = {
            "nodes": [STATE_COMMENT],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
        found = factory_linear.issue("JWA-5", fake)
        self.assertEqual([c["id"] for c in found["comments"]["nodes"]], ["c0", "c1"])
        self.assertEqual(found["factoryState"]["id"], "c1")

    def test_issue_follows_relation_pages_for_parents_and_children(self):
        first = make_issue("JWA-5", blocks=["JWA-6"], blocked_by=["JWA-4"])
        first["relations"]["pageInfo"] = {"hasNextPage": True, "endCursor": "r1"}
        first["inverseRelations"]["pageInfo"] = {"hasNextPage": True, "endCursor": "i1"}
        fake = FakeLinear({"JWA-5": first}, [])
        fake.pages[("relations", "r1")] = {
            "nodes": [{"type": "blocks", "relatedIssue": {"identifier": "JWA-7"}}],
            "pageInfo": {"hasNextPage": False},
        }
        fake.pages[("inverseRelations", "i1")] = {
            "nodes": [{"type": "blocks", "issue": {"identifier": "JWA-3"}}],
            "pageInfo": {"hasNextPage": False},
        }
        found = factory_linear.issue("JWA-5", fake)
        self.assertEqual(found["blocks"], ["JWA-6", "JWA-7"])
        self.assertEqual(found["blockedBy"], ["JWA-3", "JWA-4"])

    def test_missing_issue_is_an_error(self):
        fake = FakeLinear({}, [])
        with self.assertRaises(factory_linear.LinearError):
            factory_linear.issue("JWA-99", fake)


class LabelTests(unittest.TestCase):
    def test_set_label_replaces_only_the_factory_label(self):
        fake = FakeLinear(
            {"JWA-5": make_issue("JWA-5", labels=[LABELS[0], PHASE_A])}, [GROUP, *LABELS, PHASE_A]
        )
        result = factory_linear.set_label("JWA-5", "working", fake)
        self.assertEqual(result, {"issue": "JWA-5", "before": "ready", "after": "working"})
        self.assertEqual(len(fake.writes), 1)
        self.assertEqual(
            fake.writes[0]["variables"],
            {"id": "id-JWA-5", "added": ["l-working"], "removed": ["l-ready"]},
        )

    def test_set_label_touches_only_factory_ids(self):
        fake = FakeLinear(
            {"JWA-5": make_issue("JWA-5", labels=[LABELS[1], PHASE_A])}, [GROUP, *LABELS, PHASE_A]
        )
        factory_linear.set_label("JWA-5", "working", fake)
        self.assertEqual(fake.writes[0]["variables"]["added"], [])
        self.assertEqual(fake.writes[0]["variables"]["removed"], [])
        self.assertNotIn("labelIds", fake.writes[0]["variables"])

    def test_set_label_uses_only_the_tickets_team_labels(self):
        other_group = {
            "id": "g2",
            "name": "Factory",
            "isGroup": True,
            "parent": None,
            "team": {"id": "t2", "key": "ZZ"},
        }
        other = [
            {
                "id": f"z-{s}",
                "name": f"factory:{s}",
                "isGroup": False,
                "parent": {"id": "g2", "name": "Factory"},
                "team": {"id": "t2", "key": "ZZ"},
            }
            for s in factory_linear.STATES
        ]
        fake = FakeLinear(
            {"JWA-5": make_issue("JWA-5", labels=[LABELS[0]])},
            [other_group, *other, GROUP, *LABELS],
        )
        factory_linear.set_label("JWA-5", "working", fake)
        self.assertEqual(
            fake.writes[0]["variables"],
            {"id": "id-JWA-5", "added": ["l-working"], "removed": ["l-ready"]},
        )

    def test_set_label_requires_the_label_to_exist(self):
        fake = FakeLinear({"JWA-5": make_issue("JWA-5")}, [GROUP])
        with self.assertRaises(factory_linear.LinearError):
            factory_linear.set_label("JWA-5", "ready", fake)

    def test_ensure_labels_creates_group_then_missing_children_only(self):
        fake = FakeLinear({}, [PHASE_A, GROUP, LABELS[0]])
        result = factory_linear.ensure_labels("JWA", fake)
        self.assertEqual(
            result["created"], ["factory:working", "factory:needs-human", "factory:human-ready"]
        )
        self.assertTrue(all("issueLabelCreate" in w["query"] for w in fake.writes))
        self.assertEqual({w["variables"]["input"]["parentId"] for w in fake.writes}, {"g1"})

    def test_ensure_labels_ignores_another_teams_group(self):
        other_group = {
            "id": "g2",
            "name": "Factory",
            "isGroup": True,
            "parent": None,
            "team": {"id": "t2", "key": "ZZ"},
        }
        fake = FakeLinear({}, [other_group, PHASE_A])
        result = factory_linear.ensure_labels("JWA", fake)
        self.assertEqual(result["created"][0], "Factory")
        self.assertEqual(fake.writes[0]["variables"]["input"]["teamId"], "t1")

    def test_ensure_labels_is_idempotent(self):
        fake = FakeLinear({}, [GROUP, *LABELS])
        self.assertEqual(factory_linear.ensure_labels("JWA", fake)["created"], [])
        self.assertEqual(fake.writes, [])


class CommentTests(unittest.TestCase):
    def test_upsert_edits_the_marked_comment(self):
        fake = FakeLinear({"JWA-5": make_issue("JWA-5", comments=[STATE_COMMENT])}, [])
        body = "**Factory state**\n\nphase: factory-verify · done · head 9f9f9f9 · now"
        result = factory_linear.upsert_comment("JWA-5", "**Factory state**", body, fake)
        self.assertEqual(result["action"], "updated")
        self.assertEqual(fake.writes[0]["variables"], {"id": "c1", "body": body})

    def test_upsert_creates_when_absent(self):
        fake = FakeLinear({"JWA-5": make_issue("JWA-5")}, [])
        result = factory_linear.upsert_comment(
            "JWA-5", "**Proof of done**", "**Proof of done** · x", fake
        )
        self.assertEqual(result["action"], "created")
        self.assertEqual(fake.writes[0]["variables"]["issueId"], "id-JWA-5")

    def test_upsert_refuses_a_body_without_the_marker(self):
        fake = FakeLinear({"JWA-5": make_issue("JWA-5")}, [])
        with self.assertRaises(factory_linear.LinearError):
            factory_linear.upsert_comment("JWA-5", "**Factory state**", "something else", fake)


class WatchdogAndCascadeTests(unittest.TestCase):
    def test_working_reports_lease_and_state_line(self):
        fake = FakeLinear(
            {
                "JWA-5": make_issue("JWA-5", labels=[LABELS[1]], comments=[STATE_COMMENT]),
                "JWA-6": make_issue("JWA-6", labels=[LABELS[1]]),
            },
            [],
        )
        rows = factory_linear.working("JWA-5", fake)
        self.assertEqual(
            rows[0],
            {
                "identifier": "JWA-5",
                "run": "abcd1234",
                "heartbeat": "2026-11-08T10:00Z",
                "phase": "factory-implement",
                "status": "started",
            },
        )
        self.assertEqual(rows[1]["run"], None)

    def test_children_marks_single_parent_children(self):
        fake = FakeLinear(
            {
                "JWA-5": make_issue("JWA-5", blocks=["JWA-6", "JWA-7"]),
                "JWA-6": make_issue("JWA-6", blocked_by=["JWA-5"]),
                "JWA-7": make_issue("JWA-7", blocked_by=["JWA-5", "JWA-2"], labels=[LABELS[2]]),
            },
            [],
        )
        rows = factory_linear.children("JWA-5", fake)
        self.assertEqual(
            rows[0],
            {"identifier": "JWA-6", "parents": ["JWA-5"], "onlyParent": True, "factoryLabel": None},
        )
        self.assertEqual(rows[1]["onlyParent"], False)
        self.assertEqual(rows[1]["factoryLabel"], "needs-human")


class ReadyQueueTests(unittest.TestCase):
    def test_ready_reads_every_page_and_returns_oldest_first(self):
        fake = FakeLinear({}, [])
        fake.ready_pages = {
            None: {
                "nodes": [
                    {
                        "identifier": "JWA-9",
                        "title": "",
                        "branchName": "",
                        "createdAt": "2026-11-09",
                    },
                    {
                        "identifier": "JWA-8",
                        "title": "",
                        "branchName": "",
                        "createdAt": "2026-11-08",
                    },
                ],
                "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
            },
            "c1": {
                "nodes": [
                    {
                        "identifier": "JWA-2",
                        "title": "",
                        "branchName": "",
                        "createdAt": "2026-11-02",
                    }
                ],
                "pageInfo": {"hasNextPage": False},
            },
        }
        rows = factory_linear.ready("JWA", fake)
        self.assertEqual([r["identifier"] for r in rows], ["JWA-2", "JWA-8", "JWA-9"])


class CliTests(unittest.TestCase):
    def test_cli_prints_json_and_reads_body_file(self):
        fake = FakeLinear({"JWA-5": make_issue("JWA-5")}, [])
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write("**Factory state**\n\nphase: factory-pickup · done · head abc1234 · now\n")
        out = io.StringIO()
        with redirect_stdout(out):
            code = factory_linear.main(
                [
                    "upsert-comment",
                    "JWA-5",
                    "--marker",
                    "**Factory state**",
                    "--body-file",
                    handle.name,
                ],
                fake,
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["action"], "created")

    def test_cli_reports_errors_on_stderr_with_exit_1(self):
        fake = FakeLinear({}, [])
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", err):
            code = factory_linear.main(["issue", "JWA-404"], fake)
        self.assertEqual(code, 1)
        self.assertIn("not found", err.getvalue())


if __name__ == "__main__":
    unittest.main()
