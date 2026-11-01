from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

from laundrybench.web import create_server


def _run(root: Path, run_id: str, *, context: dict | None = None, config_hash: str = "same"):
    run = root / run_id
    run.mkdir()
    (run / "manifest.yaml").write_text(
        f"experiment_id: {run_id}\nconfig_hash: {config_hash}\n", encoding="utf-8"
    )
    (run / "episodes.jsonl").write_text(
        '{"episode_id":"episode-1","success":true,"duration_s":1.0}\n', encoding="utf-8"
    )
    if context is not None:
        (run / "experiment.json").write_text(json.dumps(context), encoding="utf-8")
    return run


@contextmanager
def _server(root: Path):
    server = create_server(root, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _get(port: int, path: str):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    response = connection.getresponse()
    result = response.status, json.loads(response.read())
    connection.close()
    return result


def _context():
    return {
        "schema_version": 1,
        "revision": 0,
        "name": "First run",
        "task": {"id": "fold-shirt", "version": "2"},
        "protocol": {"id": "tabletop", "version": "1"},
        "dataset": {"id": "dataset-a", "revision": "1"},
        "checkpoint": {"identity": "sha256:a"},
        "effective_overrides": {"control_hz": 10},
        "evidence_links": [],
    }


def test_detail_and_list_include_optional_experiment_context(tmp_path):
    _run(tmp_path, "exp-001-legacy")
    _run(tmp_path, "exp-002-context", context=_context())
    with _server(tmp_path) as port:
        status, detail = _get(port, "/api/runs/exp-001-legacy")
        assert status == 200
        assert detail["id"] == "exp-001-legacy"
        assert detail["experiment"] is None

        status, detail = _get(port, "/api/runs/exp-002-context")
        assert status == 200
        assert detail["experiment"]["task"]["id"] == "fold-shirt"
        status, listing = _get(port, "/api/runs")
        assert status == 200
        assert {item["id"]: item["experiment"] for item in listing["runs"]} == {
            "exp-001-legacy": None,
            "exp-002-context": detail["experiment"],
        }


def test_compare_route_gates_delta_and_keeps_acknowledgment_visible(tmp_path):
    context = _context()
    _run(tmp_path, "exp-001-baseline", context=context)
    candidate = _context()
    candidate["dataset"] = {"id": "dataset-b", "revision": "1"}
    candidate["protocol"]["version"] = "2"
    _run(tmp_path, "exp-002-candidate", context=candidate, config_hash="other")
    route = "/api/runs/exp-002-candidate/compare/exp-001-baseline"
    with _server(tmp_path) as port:
        status, comparison = _get(port, route)
        assert status == 200
        assert comparison["compatibility"]["status"] == "mismatched"
        assert comparison["candidate_context"]["protocol"]["version"] == "2"
        assert comparison["baseline_label_revision"] == 0
        assert comparison["delta"] is None
        assert comparison["candidate"]["reviewed_episodes"] == 0
        assert comparison["baseline"]["reviewed_episodes"] == 0

        status, acknowledged = _get(port, route + "?acknowledge_incompatible=1")
        assert status == 200
        assert acknowledged["compatibility"]["status"] == "mismatched"
        assert acknowledged["delta"]["success_rate"] is None
        assert acknowledged["delta"]["intervention_rate"] is None

        status, invalid = _get(port, route + "?acknowledge_incompatible=yes")
        assert status == 400
        assert "must be 1" in invalid["error"]


def test_compare_with_missing_required_context_is_unknown_and_has_no_delta(tmp_path):
    _run(tmp_path, "exp-001-legacy")
    _run(tmp_path, "exp-002-context", context=_context())
    with _server(tmp_path) as port:
        status, result = _get(port, "/api/runs/exp-002-context/compare/exp-001-legacy")
        assert status == 200
        assert result["compatibility"]["status"] == "unknown"
        assert result["delta"] is None
