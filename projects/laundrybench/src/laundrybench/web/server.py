from __future__ import annotations

import json
import math
import mimetypes
import os
import re
import stat
import tempfile
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

import yaml

from laundrybench.evaluation.media import (
    MediaError,
    copy_byte_range,
    parse_byte_range,
    read_episode_media,
    resolve_media,
)
from laundrybench.evaluation.metadata import (
    MetadataError,
    compare_run_context,
    read_experiment_metadata,
)
from laundrybench.evaluation.outcomes import (
    LABEL_FILE,
    OUTCOME_SCHEMA_VERSION,
    resolve_episode,
    summarize_outcomes,
    validate_episode_records,
    validate_labels,
)
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
        labels = self.read(run, LABEL_FILE, {"revision": 0, "labels": {}})
        try:
            return validate_labels(labels, episode_ids)
        except (TypeError, ValueError) as error:
            raise APIError(422, str(error)) from error

    def detail(self, run_id: str) -> dict:
        with self.lock:
            run = self.run_path(run_id)
            episodes_path = self.artifact(run, "episodes.jsonl")
            if not episodes_path.exists():
                raise APIError(404, "run has no episode evidence")
            records = [
                json.loads(line) for line in episodes_path.read_text().splitlines() if line.strip()
            ]
            try:
                validate_episode_records(records)
            except (TypeError, ValueError) as error:
                raise APIError(422, str(error)) from error
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
            episodes = []
            for record in records:
                label = labels["labels"].get(record["episode_id"])
                resolved = resolve_episode(record, label)
                effective = dict(record)
                effective.update(resolved["effective_outcome"])
                category = effective.get("failure_category")
                result = EpisodeResult(
                    episode_id=effective["episode_id"],
                    success=effective["success"],
                    duration_s=effective["duration_s"],
                    intervention=effective.get("intervention", False),
                    failure_category=FailureCategory(category) if category else None,
                    metadata=effective.get("metadata", {}),
                )
                annotation_status = {
                    "reviewed": "labelled",
                    "excluded": "excluded",
                    "provisional": "unlabelled",
                }[resolved["review_status"]]
                episodes.append(
                    {
                        **asdict(result),
                        **resolved,
                        "annotation": {**(label or {}), "status": annotation_status},
                    }
                )
            summary = summarize_outcomes(records, labels["labels"], revision)
            quality = self.read(run, "quality.json")
            manifest = self.read(run, "manifest.yaml", {}) or {}
            try:
                experiment = read_experiment_metadata(run)
            except MetadataError as error:
                raise APIError(422, str(error)) from error
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
                "experiment": experiment,
                "quality": quality,
                "episodes": episodes,
                "revision": revision,
                "labelled_episodes": sum(
                    e["annotation"]["status"] != "unlabelled" for e in episodes
                ),
            }

    def compare(
        self, candidate_id: str, baseline_id: str, *, acknowledge_incompatible: bool = False
    ) -> dict:
        candidate = self.detail(candidate_id)
        baseline = self.detail(baseline_id)
        comparison = compare_run_context(
            candidate["experiment"],
            baseline["experiment"],
            candidate_manifest=candidate["manifest"],
            baseline_manifest=baseline["manifest"],
            candidate_summary=candidate["summary"],
            baseline_summary=baseline["summary"],
            acknowledge_incompatible=acknowledge_incompatible,
        )
        return {
            "candidate_id": candidate_id,
            "baseline_id": baseline_id,
            "candidate_context": candidate["experiment"],
            "baseline_context": baseline["experiment"],
            "candidate_label_revision": candidate["revision"],
            "baseline_label_revision": baseline["revision"],
            **comparison,
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

    def media_manifest(self, run_id: str, episode_id: str) -> dict:
        detail = self.detail(run_id)
        if episode_id not in {episode["episode_id"] for episode in detail["episodes"]}:
            raise APIError(404, "episode not found")
        try:
            manifest = read_episode_media(self.run_path(run_id), episode_id)
        except MediaError as error:
            raise APIError(422, str(error)) from error
        for stream in manifest["streams"]:
            stream["url"] = (
                f"/api/runs/{quote(run_id, safe='')}/episodes/{quote(episode_id, safe='')}"
                f"/media/{quote(stream['camera'], safe='')}"
            )
        return manifest

    def media_file(self, run_id: str, episode_id: str, camera: str) -> tuple[Path, str]:
        manifest = self.media_manifest(run_id, episode_id)
        try:
            stream = next((item for item in manifest["streams"] if item["camera"] == camera), None)
            if stream is None:
                raise APIError(404, "camera media not found")
            path = resolve_media(self.run_path(run_id), episode_id, camera)
        except MediaError as error:
            raise APIError(422, str(error)) from error
        return path, stream["mime_type"]

    @staticmethod
    def validate_label(payload: dict) -> None:
        """Task success excludes assistance; failed assists retain their root-cause category."""
        if isinstance(payload, dict) and payload.get("status") == "excluded":
            if set(payload) != {"status", "exclusion_reason", "expected_revision"}:
                raise APIError(
                    422,
                    "excluded labels require status, exclusion_reason and expected_revision",
                )
            reason = payload["exclusion_reason"]
            if (
                not isinstance(reason, str)
                or not reason.strip()
                or len(reason) > 4000
                or type(payload["expected_revision"]) is not int
                or payload["expected_revision"] < 0
            ):
                raise APIError(422, "invalid exclusion reason or expected_revision")
            return
        required = {"success", "intervention", "failure_category", "notes", "expected_revision"}
        if not isinstance(payload, dict) or set(payload) not in (required, required | {"status"}):
            raise APIError(
                422,
                "provide reviewed success, intervention, failure_category, "
                "notes and expected_revision",
            )
        if payload.get("status", "reviewed") != "reviewed":
            raise APIError(422, "status must be reviewed or excluded")
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
            labels = {
                "schema_version": OUTCOME_SCHEMA_VERSION,
                "revision": labels["revision"],
                "labels": {
                    episode_id: (
                        {"status": "reviewed", **entry} if "status" not in entry else entry
                    )
                    for episode_id, entry in labels["labels"].items()
                },
            }
            labels["revision"] += 1
            new_entry = {key: value for key, value in payload.items() if key != "expected_revision"}
            new_entry.setdefault("status", "reviewed")
            new_entry.update(revision=labels["revision"], updated_at=datetime.now(UTC).isoformat())
            labels["labels"][episode_id] = new_entry
            target = self.artifact(run, LABEL_FILE)
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
            if self.command != "HEAD":
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

        def serve_episode_media(
            self, run_id: str, episode_id: str, camera: str, *, head: bool
        ) -> None:
            handle = None
            try:
                media_path, mime_type = store.media_file(run_id, episode_id, camera)
                flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                handle = os.fdopen(os.open(media_path, flags), "rb")
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise APIError(422, "media artifact is not a regular file")
                size = info.st_size
                if size <= 0:
                    raise APIError(422, "media artifact is empty")
                range_header = self.headers.get("Range")
                if (
                    head
                    or self.headers.get("If-Range")
                    or (range_header and "," in range_header)
                    or (
                        range_header
                        and "=" in range_header
                        and range_header.split("=", 1)[0].strip().lower() != "bytes"
                    )
                ):
                    # Range applies to GET; unsupported multipart ranges and
                    # conditional ranges without validators safely fall back
                    # to a complete representation.
                    range_header = None
                elif range_header and "=" in range_header:
                    unit, spec = range_header.split("=", 1)
                    if unit.strip().lower() == "bytes":
                        range_header = f"bytes={spec}"
                try:
                    byte_range = parse_byte_range(range_header, size) if range_header else None
                except MediaError:
                    self.send_response(416)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                if byte_range is None:
                    status, start, end = 200, 0, size - 1
                else:
                    status, (start, end) = 206, byte_range
                self.send_response(status)
                self.send_header("Content-Type", mime_type)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(end - start + 1))
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                if not head:
                    try:
                        copy_byte_range(handle, self.wfile, start, end)
                    except (MediaError, OSError):
                        # Headers are already sent; a JSON error here would corrupt
                        # the video response. Close the connection instead.
                        self.close_connection = True
            except APIError as error:
                self.send_json(error.status, {"error": error.message})
            except (OSError, ValueError, KeyError, TypeError):
                self.send_json(422, {"error": "run media artifacts are missing or invalid"})
            finally:
                if handle is not None:
                    try:
                        handle.close()
                    except OSError:
                        self.close_connection = True

        def do_HEAD(self):
            try:
                _, parts = self.parts()
                if (
                    len(parts) == 7
                    and parts[:2] == ["api", "runs"]
                    and parts[3] == "episodes"
                    and parts[5] == "media"
                ):
                    return self.serve_episode_media(parts[2], parts[4], parts[6], head=True)
                raise APIError(404, "API route not found")
            except APIError as error:
                self.send_json(error.status, {"error": error.message})
            except (OSError, ValueError, KeyError, TypeError):
                self.send_json(422, {"error": "run artifacts are missing or invalid"})

        def do_GET(self):
            try:
                path, parts = self.parts()
                if parts == ["api", "runs"]:
                    return self.send_json(200, {"runs": store.runs()})
                if len(parts) == 3 and parts[:2] == ["api", "runs"]:
                    return self.send_json(200, store.detail(parts[2]))
                if len(parts) == 5 and parts[:2] == ["api", "runs"] and parts[3] == "compare":
                    query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                    ack_values = query.get("acknowledge_incompatible", [])
                    if ack_values not in ([], ["1"]):
                        raise APIError(400, "acknowledge_incompatible must be 1 when provided")
                    return self.send_json(
                        200,
                        store.compare(
                            parts[2], parts[4], acknowledge_incompatible=ack_values == ["1"]
                        ),
                    )
                if (
                    len(parts) == 6
                    and parts[:2] == ["api", "runs"]
                    and parts[3] == "episodes"
                    and parts[5] == "media"
                ):
                    return self.send_json(200, store.media_manifest(parts[2], parts[4]))
                if (
                    len(parts) == 7
                    and parts[:2] == ["api", "runs"]
                    and parts[3] == "episodes"
                    and parts[5] == "media"
                ):
                    return self.serve_episode_media(parts[2], parts[4], parts[6], head=False)
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
