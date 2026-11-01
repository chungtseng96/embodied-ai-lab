from __future__ import annotations

import json
import math
import mimetypes
import os
import re
import tempfile
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

from laundrybench.evaluation.metrics import summarize
from laundrybench.evaluation.report import wilson_interval
from laundrybench.types import EpisodeResult, FailureCategory

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z")
_MAX_BODY = 16384


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def _finite_json(value):
    """JSON traces may contain NaN from deliberately faulty policies."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _finite_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite_json(item) for item in value]
    return value


class RunStore:
    """Reload original artifacts on every request; only labels.json is mutable.

    RunStore serializes writes within this server process. Run a single writer
    server for a given outputs root. Labels are operator outcomes after an
    episode, not per-frame training labels or instructions to move a robot.
    """

    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        self.lock = threading.RLock()
        if not self.root.is_dir():
            raise ValueError("outputs root must be a directory")

    def run_path(self, run_id: str) -> Path:
        if not _ID.fullmatch(run_id):
            raise APIError(404, "run not found")
        path = self.root / run_id
        if path.is_symlink() or not path.is_dir() or path.resolve().parent != self.root:
            raise APIError(404, "run not found")
        return path

    def artifact(self, run: Path, relative: str) -> Path:
        path = run / relative
        cursor = run
        for part in Path(relative).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise APIError(422, "symlink artifacts are not supported")
        if not path.resolve().is_relative_to(run):
            raise APIError(422, "invalid artifact path")
        return path

    def read(self, run: Path, name: str, default=None):
        path = self.artifact(run, name)
        if not path.exists():
            return default
        content = path.read_text(encoding="utf-8")
        try:
            return yaml.safe_load(content) if name.endswith(".yaml") else json.loads(content)
        except yaml.YAMLError as error:
            raise ValueError("invalid YAML artifact") from error

    def labels(self, run: Path, episode_ids: set[str]) -> dict:
        labels = self.read(run, "labels.json", {"revision": 0, "labels": {}})
        if (
            not isinstance(labels, dict)
            or set(labels) != {"revision", "labels"}
            or type(labels["revision"]) is not int
            or labels["revision"] < 0
            or not isinstance(labels["labels"], dict)
        ):
            raise APIError(422, "invalid labels artifact")
        for episode_id, entry in labels["labels"].items():
            required = {
                "success",
                "intervention",
                "failure_category",
                "notes",
                "revision",
                "updated_at",
            }
            if (
                episode_id not in episode_ids
                or not isinstance(entry, dict)
                or set(entry) != required
                or type(entry["revision"]) is not int
                or not 1 <= entry["revision"] <= labels["revision"]
                or not isinstance(entry["updated_at"], str)
            ):
                raise APIError(422, "invalid stored episode label")
            self.validate_label(
                {
                    **{
                        key: entry[key]
                        for key in ("success", "intervention", "failure_category", "notes")
                    },
                    "expected_revision": labels["revision"],
                }
            )
        return labels

    def detail(self, run_id: str) -> dict:
        with self.lock:
            run = self.run_path(run_id)
            episodes_path = self.artifact(run, "episodes.jsonl")
            if not episodes_path.exists():
                raise APIError(404, "run has no episode evidence")
            records = [
                json.loads(line) for line in episodes_path.read_text().splitlines() if line.strip()
            ]
            episode_ids = set()
            for record in records:
                if (
                    not isinstance(record, dict)
                    or not isinstance(record.get("episode_id"), str)
                    or not _ID.fullmatch(record["episode_id"])
                    or record["episode_id"] in episode_ids
                    or type(record.get("success")) is not bool
                    or type(record.get("intervention", False)) is not bool
                    or type(record.get("duration_s")) not in (int, float)
                    or not math.isfinite(record["duration_s"])
                    or record["duration_s"] < 0
                    or not isinstance(record.get("metadata", {}), dict)
                ):
                    raise APIError(422, "invalid or duplicate episode evidence")
                episode_ids.add(record["episode_id"])
            labels = self.labels(run, episode_ids)
            revision = labels["revision"]
            results, episodes = [], []
            for record in records:
                original = {
                    key: record.get(key) for key in ("success", "failure_category", "intervention")
                }
                label = labels["labels"].get(record["episode_id"])
                effective = dict(record)
                if label:
                    effective.update({key: label[key] for key in original})
                category = effective.get("failure_category")
                result = EpisodeResult(
                    episode_id=effective["episode_id"],
                    success=effective["success"],
                    duration_s=effective["duration_s"],
                    intervention=effective.get("intervention", False),
                    failure_category=FailureCategory(category) if category else None,
                    metadata=effective.get("metadata", {}),
                )
                results.append(result)
                episodes.append(
                    {
                        **asdict(result),
                        "original_outcome": original,
                        "annotation": {"status": "labelled", **label}
                        if label
                        else {"status": "unlabelled"},
                    }
                )
            summary = dict(summarize(results))
            summary["success_rate_ci"] = list(
                wilson_interval(summary["successes"], summary["episodes"])
            )
            quality = self.read(run, "quality.json")
            manifest = self.read(run, "manifest.yaml", {}) or {}
            if not isinstance(manifest, dict) or (
                quality is not None and not isinstance(quality, dict)
            ):
                raise APIError(422, "invalid manifest or quality artifact")
            summary["manifest"] = manifest
            if quality:
                summary["quality"] = {key: quality[key] for key in ("episodes", "flagged")}
            return {
                "id": run_id,
                "summary": summary,
                "manifest": manifest,
                "quality": quality,
                "episodes": episodes,
                "revision": revision,
                "labelled_episodes": sum(e["annotation"]["status"] == "labelled" for e in episodes),
            }

    def runs(self) -> list[dict]:
        runs = []
        for path in sorted(self.root.iterdir()):
            if not path.is_dir() or path.is_symlink() or not _ID.fullmatch(path.name):
                continue
            try:
                detail = self.detail(path.name)
                runs.append(
                    {
                        key: value
                        for key, value in detail.items()
                        if key not in ("episodes", "quality")
                    }
                )
            except (APIError, OSError, ValueError, KeyError, TypeError):
                continue
        return runs

    def trace(self, run_id: str, episode_id: str) -> dict:
        detail = self.detail(run_id)
        if episode_id not in {e["episode_id"] for e in detail["episodes"]}:
            raise APIError(404, "episode not found")
        path = self.artifact(self.run_path(run_id), "traces/steps.jsonl")
        steps = []
        if path.exists():
            steps = [
                record
                for line in path.read_text().splitlines()
                if line.strip() and (record := json.loads(line))["episode_id"] == episode_id
            ]
        return {"episode_id": episode_id, "steps": steps}

    @staticmethod
    def validate_label(payload: dict) -> None:
        """Task success excludes assistance; failed assists retain their root-cause category."""
        required = {"success", "intervention", "failure_category", "notes", "expected_revision"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise APIError(
                422,
                "provide exactly success, intervention, failure_category, "
                "notes and expected_revision",
            )
        if (
            type(payload["success"]) is not bool
            or type(payload["intervention"]) is not bool
            or type(payload["expected_revision"]) is not int
            or payload["expected_revision"] < 0
            or not isinstance(payload["notes"], str)
            or len(payload["notes"]) > 4000
        ):
            raise APIError(422, "invalid label field types or notes longer than 4000 characters")
        category = payload["failure_category"]
        if category is not None and category not in [value.value for value in FailureCategory]:
            raise APIError(422, "unknown failure_category")
        if payload["success"] and (payload["intervention"] or category is not None):
            raise APIError(422, "success cannot have intervention or failure category")
        if not payload["success"] and category is None:
            raise APIError(422, "failed outcomes require a failure category")

    def label(self, run_id: str, episode_id: str, payload: dict) -> dict:
        self.validate_label(payload)
        with self.lock:
            detail = self.detail(run_id)
            if episode_id not in {e["episode_id"] for e in detail["episodes"]}:
                raise APIError(404, "episode not found")
            if payload["expected_revision"] != detail["revision"]:
                raise APIError(409, "labels changed; reload before saving")
            run = self.run_path(run_id)
            labels = self.labels(run, {e["episode_id"] for e in detail["episodes"]})
            labels["revision"] += 1
            labels["labels"][episode_id] = {
                key: value for key, value in payload.items() if key != "expected_revision"
            }
            labels["labels"][episode_id].update(
                revision=labels["revision"], updated_at=datetime.now(UTC).isoformat()
            )
            target = self.artifact(run, "labels.json")
            fd, name = tempfile.mkstemp(prefix=".labels-", dir=run)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(labels, handle, indent=2, allow_nan=False)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(name, target)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            return self.detail(run_id)


def create_server(
    outputs_root: Path, frontend_dir: Path | None = None, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    """Single-process local app server. Do not expose it as a hosted write API."""
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("operator server must bind to loopback")
    store = RunStore(outputs_root)
    frontend = frontend_dir.resolve(strict=True) if frontend_dir else None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, status, payload):
            body = json.dumps(_finite_json(payload), allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def parts(self):
            allowed = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            if self.headers.get("Host") not in allowed:
                raise APIError(403, "invalid host")
            path = unquote(urlsplit(self.path).path)
            if "\\" in path or any(part in (".", "..") for part in path.split("/")):
                raise APIError(404, "not found")
            return path, path.strip("/").split("/")

        def do_GET(self):
            try:
                path, parts = self.parts()
                if parts == ["api", "runs"]:
                    return self.send_json(200, {"runs": store.runs()})
                if len(parts) == 3 and parts[:2] == ["api", "runs"]:
                    return self.send_json(200, store.detail(parts[2]))
                if (
                    len(parts) == 6
                    and parts[:2] == ["api", "runs"]
                    and parts[3] == "episodes"
                    and parts[5] == "trace"
                ):
                    return self.send_json(200, store.trace(parts[2], parts[4]))
                if parts[0] == "api":
                    raise APIError(404, "API route not found")
                if not frontend:
                    raise APIError(404, "frontend not configured; build it and pass --frontend-dir")
                target = frontend / path.lstrip("/")
                if not target.resolve().is_relative_to(frontend):
                    raise APIError(404, "not found")
                if not target.is_file():
                    if Path(path).suffix:
                        raise APIError(404, "asset not found")
                    target = frontend / "index.html"
                if not target.resolve().is_relative_to(frontend) or not target.is_file():
                    raise APIError(404, "not found")
                body = target.read_bytes()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                )
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except APIError as error:
                self.send_json(error.status, {"error": error.message})
            except (OSError, ValueError, KeyError, TypeError):
                self.send_json(422, {"error": "run artifacts are missing or invalid"})

        def do_PUT(self):
            try:
                _, parts = self.parts()
                origin = self.headers.get("Origin")
                if origin != "http://" + self.headers.get("Host", ""):
                    raise APIError(403, "same-origin request required")
                if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin"):
                    raise APIError(403, "same-origin request required")
                if self.headers.get_content_type() != "application/json":
                    raise APIError(415, "application/json required")
                if self.headers.get("Transfer-Encoding"):
                    raise APIError(400, "transfer encoding not supported")
                try:
                    size = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    raise APIError(411, "Content-Length required") from None
                if not 0 < size <= _MAX_BODY:
                    raise APIError(413, "label body too large or empty")
                if (
                    len(parts) != 6
                    or parts[:2] != ["api", "runs"]
                    or parts[3] != "episodes"
                    or parts[5] != "label"
                ):
                    raise APIError(404, "API route not found")
                payload = json.loads(self.rfile.read(size))
                return self.send_json(200, store.label(parts[2], parts[4], payload))
            except APIError as error:
                self.send_json(error.status, {"error": error.message})
            except (OSError, ValueError, KeyError, TypeError):
                self.send_json(422, {"error": "invalid JSON or run artifacts"})

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
