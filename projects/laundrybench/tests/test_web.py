from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

import pytest

from laundrybench.evaluation.report import build_summary
from laundrybench.web import create_server


def seed(root: Path) -> Path:
    run = root / "exp-001-smoke"
    run.mkdir()
    (run / "manifest.yaml").write_text(
        "experiment_id: exp-001-smoke\nrobot_implementation: MockRobot\n"
    )
    episodes = [
        {
            "episode_id": "episode-001",
            "success": True,
            "duration_s": 2.0,
            "intervention": False,
            "failure_category": None,
        },
        {
            "episode_id": "episode-002",
            "success": False,
            "duration_s": 4.0,
            "intervention": False,
            "failure_category": "timeout",
        },
    ]
    (run / "episodes.jsonl").write_text("\n".join(json.dumps(e) for e in episodes) + "\n")
    (run / "summary.json").write_text('{"success_rate": 0.99}')
    (run / "traces").mkdir()
    (run / "traces/steps.jsonl").write_text(
        '{"episode_id":"episode-001","step":0,"joint_targets":[NaN]}\n'
    )
    return run


@contextmanager
def running(root, frontend=None):
    server = create_server(root, frontend, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def request(port, path, method="GET", payload=None, headers=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    body = json.dumps(payload) if payload is not None else None
    defaults = {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"}
    connection.request(method, path, body=body, headers={**defaults, **(headers or {})})
    response = connection.getresponse()
    raw = response.read()
    status = response.status
    connection.close()
    return status, json.loads(raw) if raw.startswith((b"{", b"[")) else raw


def label(revision=0, **kwargs):
    return {
        "success": False,
        "failure_category": "missed_grasp",
        "intervention": False,
        "notes": "operator outcome after episode",
        "expected_revision": revision,
        **kwargs,
    }


PATH = "/api/runs/exp-001-smoke"
LABEL = PATH + "/episodes/episode-001/label"


def test_labels_persist_and_overlay_current_evidence_without_rewriting_originals(tmp_path):
    run = seed(tmp_path)
    original = (run / "episodes.jsonl").read_bytes()
    with running(tmp_path) as port:
        status, listing = request(port, "/api/runs")
        assert status == 200
        assert listing["runs"][0]["summary"]["success_rate"] is None
        status, detail = request(port, PATH)
        assert detail["episodes"][0]["annotation"]["status"] == "unlabelled"
        assert detail["episodes"][0]["review_status"] == "provisional"
        assert detail["episodes"][0]["outcome_source"] == "recorded"
        status, detail = request(port, LABEL, "PUT", label())
        assert status == 200
        assert detail["revision"] == 1
        assert detail["summary"]["reviewed_episodes"] == 1
        assert detail["summary"]["pending_episodes"] == 1
        assert detail["summary"]["success_rate"] == 0
        assert detail["summary"]["failure_category_counts"] == {"missed_grasp": 1}
        assert detail["episodes"][0]["original_outcome"]["success"] is True
        assert detail["episodes"][0]["effective_outcome"]["success"] is False
        assert detail["episodes"][0]["review_status"] == "reviewed"
        assert detail["episodes"][0]["outcome_source"] == "label"
        assert detail["episodes"][0]["annotation"]["status"] == "labelled"
        assert detail["episodes"][0]["annotation"]["notes"] == "operator outcome after episode"
        assert detail["summary"] == build_summary(run)
        assert request(port, LABEL, "PUT", label())[0] == 409
        status, trace = request(port, PATH + "/episodes/episode-001/trace")
        assert status == 200
        assert trace["steps"][0]["joint_targets"] == [None]
    assert (run / "episodes.jsonl").read_bytes() == original
    sidecar = json.loads((run / "labels.json").read_text())
    assert sidecar["schema_version"] == 2
    assert json.loads((run / "summary.json").read_text())["success_rate"] == 0.99
    with running(tmp_path) as port:
        _, detail = request(port, PATH)
        assert detail["revision"] == 1
        assert detail["labelled_episodes"] == 1
        # Original artifacts are reloaded, rather than trusting cached summary.json.
        with (run / "episodes.jsonl").open("a") as handle:
            handle.write(
                json.dumps({"episode_id": "episode-003", "success": True, "duration_s": 3}) + "\n"
            )
        _, detail = request(port, PATH)
        assert detail["summary"]["episodes"] == 3
        assert detail["summary"]["success_rate"] == 0
        assert detail["summary"]["pending_episodes"] == 2


def test_concurrent_labels_only_one_stale_revision_can_win(tmp_path):
    seed(tmp_path)
    with running(tmp_path) as port:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: request(port, LABEL, "PUT", label()), range(2)))
        assert sorted(status for status, _ in responses) == [200, 409]
        assert request(port, PATH)[1]["revision"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"success": "false"},
        {"expected_revision": True},
        {"expected_revision": -1},
        {"notes": "x" * 4001},
        {"failure_category": "made_up"},
        {"success": True},
        {"failure_category": None},
        {"unexpected": "field"},
    ],
)
def test_strict_label_validation(tmp_path, changes):
    seed(tmp_path)
    with running(tmp_path) as port:
        assert request(port, LABEL, "PUT", label(**changes))[0] == 422
        assert request(port, PATH)[1]["revision"] == 0


def test_cross_origin_and_non_json_writes_rejected(tmp_path):
    seed(tmp_path)
    with running(tmp_path) as port:
        assert request(port, LABEL, "PUT", label(), {"Origin": "https://evil.test"})[0] == 403
        assert request(port, LABEL, "PUT", label(), {"Content-Type": "text/plain"})[0] == 415
        assert request(port, LABEL, "PUT", label(), {"Sec-Fetch-Site": "cross-site"})[0] == 403
        assert request(port, PATH, headers={"Host": f"evil.test:{port}"})[0] == 403
        assert request(port, LABEL, "PUT", label(notes="x" * 17000))[0] == 413


def test_artifact_confinement_and_spa_fallback(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    run = seed(outputs)
    frontend = tmp_path / "dist"
    frontend.mkdir()
    (frontend / "index.html").write_text("<html>operator</html>")
    (frontend / "outside").symlink_to(tmp_path)
    (outputs / "exp-002-link").symlink_to(run, target_is_directory=True)
    with running(outputs, frontend) as port:
        assert len(request(port, "/api/runs")[1]["runs"]) == 1
        assert request(port, "/api/runs/exp-002-link")[0] == 404
        assert request(port, "/%2e%2e/secret")[0] == 404
        assert request(port, "/runs/exp-001-smoke")[1] == b"<html>operator</html>"
        assert request(port, "/missing.js")[0] == 404
        assert request(port, "/api/missing")[0] == 404
        (run / "labels.json").symlink_to(tmp_path / "outside-labels.json")
        assert request(port, LABEL, "PUT", label())[0] == 422
        assert not (tmp_path / "outside-labels.json").exists()


def test_server_is_loopback_only(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        create_server(tmp_path, host="0.0.0.0", port=0)


@pytest.mark.parametrize(
    "stored",
    [
        True,
        [],
        {"revision": True, "labels": {}},
        {"revision": 0, "labels": []},
        {"revision": 1, "labels": {"episode-001": True}},
        {"revision": 1, "labels": {"episode-001": {"success": False}}},
    ],
)
def test_malformed_stored_labels_return_clean_error(tmp_path, stored):
    run = seed(tmp_path)
    (run / "labels.json").write_text(json.dumps(stored))
    with running(tmp_path) as port:
        assert request(port, PATH)[0] == 422
        assert request(port, LABEL, "PUT", label())[0] == 422
        assert request(port, "/api/runs")[1]["runs"] == []


def test_duplicate_episode_ids_and_malformed_yaml_return_clean_error(tmp_path):
    run = seed(tmp_path)
    path = run / "episodes.jsonl"
    original = path.read_text()
    path.write_text(original + original.splitlines()[0] + "\n")
    with running(tmp_path) as port:
        assert request(port, PATH)[0] == 422
        path.write_text(original)
        (run / "manifest.yaml").write_text("broken: [")
        assert request(port, PATH)[0] == 422


def test_intervention_retains_the_failure_root_cause(tmp_path):
    seed(tmp_path)
    with running(tmp_path) as port:
        status, detail = request(port, LABEL, "PUT", label(intervention=True))
        assert status == 200
        assert detail["episodes"][0]["failure_category"] == "missed_grasp"
        assert detail["summary"]["intervention_rate"] == 1.0
        assert detail["summary"]["success_rate"] == 0


def test_excluded_episode_requires_reason_and_stays_out_of_reviewed_metrics(tmp_path):
    run = seed(tmp_path)
    original = (run / "episodes.jsonl").read_bytes()
    payload = {
        "status": "excluded",
        "exclusion_reason": "trace is incomplete",
        "expected_revision": 0,
    }
    with running(tmp_path) as port:
        assert request(port, LABEL, "PUT", {**payload, "exclusion_reason": " "})[0] == 422
        status, detail = request(port, LABEL, "PUT", payload)
        assert status == 200
        assert detail["episodes"][0]["review_status"] == "excluded"
        assert detail["episodes"][0]["outcome_source"] == "recorded"
        assert detail["episodes"][0]["effective_outcome"] == detail["episodes"][0][
            "original_outcome"
        ]
        assert detail["episodes"][0]["annotation"]["status"] == "excluded"
        assert detail["episodes"][0]["annotation"]["exclusion_reason"] == "trace is incomplete"
        assert detail["summary"]["excluded_episodes"] == 1
        assert detail["summary"]["metric_episodes"] == 0
        assert detail["summary"]["success_rate"] is None
        restored = request(
            port,
            LABEL,
            "PUT",
            label(revision=1, success=True, intervention=False, failure_category=None),
        )
        assert restored[0] == 200
        assert restored[1]["episodes"][0]["review_status"] == "reviewed"
        assert restored[1]["summary"]["excluded_episodes"] == 0
        assert restored[1]["summary"]["metric_episodes"] == 1
        assert restored[1]["summary"]["success_rate"] == 1.0
    assert (run / "episodes.jsonl").read_bytes() == original


def test_legacy_sidecar_is_upgraded_on_write_and_preserves_every_review(tmp_path):
    run = seed(tmp_path)
    third_record = {
        "episode_id": "episode-003",
        "success": True,
        "duration_s": 3.0,
        "intervention": False,
        "failure_category": None,
    }
    with (run / "episodes.jsonl").open("a") as handle:
        handle.write(json.dumps(third_record) + "\n")
    legacy_success = {
        "success": True,
        "intervention": False,
        "failure_category": None,
        "notes": "legacy success review",
        "revision": 1,
        "updated_at": "2026-11-01T00:00:00+00:00",
    }
    legacy_failure = {
        "success": False,
        "intervention": False,
        "failure_category": "timeout",
        "notes": "legacy failure review",
        "revision": 2,
        "updated_at": "2026-11-01T00:00:00+00:00",
    }
    (run / "labels.json").write_text(
        json.dumps(
            {
                "revision": 2,
                "labels": {
                    "episode-001": legacy_success,
                    "episode-002": legacy_failure,
                },
            }
        )
    )

    with running(tmp_path) as port:
        initial = request(port, PATH)[1]
        assert initial["episodes"][0]["review_status"] == "reviewed"
        assert initial["summary"]["success_rate"] == 0.5
        response = request(
            port,
            PATH + "/episodes/episode-003/label",
            "PUT",
            label(revision=2, success=True, failure_category=None),
        )
        assert response[0] == 200
        migrated = json.loads((run / "labels.json").read_text())
        assert migrated["schema_version"] == 2
        assert migrated["labels"]["episode-001"]["status"] == "reviewed"
        assert migrated["labels"]["episode-001"]["notes"] == "legacy success review"
        assert migrated["labels"]["episode-002"]["status"] == "reviewed"
        assert migrated["labels"]["episode-002"]["notes"] == "legacy failure review"
        assert migrated["labels"]["episode-003"]["status"] == "reviewed"
        assert request(port, PATH)[1]["summary"]["reviewed_episodes"] == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("episode_id", "../outside"),
        ("duration_s", float("nan")),
        ("duration_s", 10**400),
        ("duration_s", -1),
        ("duration_s", True),
        ("success", "false"),
        ("intervention", "false"),
    ],
)
def test_invalid_original_episode_fields_rejected(tmp_path, field, value):
    run = seed(tmp_path)
    path = run / "episodes.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0][field] = value
    path.write_text("\n".join(json.dumps(e) for e in records))
    with running(tmp_path) as port:
        assert request(port, PATH)[0] == 422
