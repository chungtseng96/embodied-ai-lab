"""Serve an exported LaundryBench Showcase directory as a read-only fixture."""
from __future__ import annotations

import argparse
import os
import re
import stat
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class ReadOnlyHandler(SimpleHTTPRequestHandler):
    """Static files plus deterministic API-to-JSON route rewriting."""

    _range = re.compile(r"bytes=(\d*)-(\d*)\Z")

    def translate_path(self, path: str) -> str:
        # The Showcase API is a static projection. Keep this mapping exact so
        # the browser still exercises the production frontend's /api/ calls.
        if path.startswith("/api/"):
            parts = urlsplit(path)
            mapped = "/data/" + parts.path[len("/api/"):]
            acknowledged = parse_qs(parts.query).get("acknowledge_incompatible") == ["1"]
            suffix = ".acknowledged.json" if acknowledged and "/compare/" in mapped else ".json"
            path = mapped + suffix
        return super().translate_path(path)

    def send_head(self):
        """Serve files with single byte-range support for seekable media."""
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        # The inherited GET/HEAD methods close this returned stream after use.
        try:
            source = open(path, "rb")  # noqa: SIM115
        except OSError:
            self.send_error(404, "File not found")
            return None

        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            source.close()
            self.send_error(404, "File not found")
            return None

        size = metadata.st_size
        # RFC 9110: Range applies to GET. HEAD reports the full GET metadata.
        byte_range = self._requested_range(size) if self.command == "GET" else None
        if byte_range is False:
            source.close()
            self.send_response(416, "Requested Range Not Satisfiable")
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None

        self.send_response(206 if byte_range else 200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Last-Modified", self.date_time_string(metadata.st_mtime))
        self.send_header("Accept-Ranges", "bytes")
        if byte_range:
            first, last = byte_range
            source.seek(first)
            length = last - first + 1
            self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
        else:
            length = size
        self._response_length = length
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return source

    def _requested_range(self, size: int) -> tuple[int, int] | None | bool:
        value = self.headers.get("Range")
        if value is None:
            return None
        if not value.lower().startswith("bytes="):
            # Unknown range units are ignored and receive the whole resource.
            return None
        match = self._range.fullmatch(value.strip())
        if not match or size == 0:
            return False
        first_text, last_text = match.groups()
        if not first_text:
            suffix_length = int(last_text or "0")
            if suffix_length <= 0:
                return False
            first, last = max(0, size - suffix_length), size - 1
        else:
            first = int(first_text)
            last = int(last_text) if last_text else size - 1
            if first >= size or last < first:
                return False
            last = min(last, size - 1)
        return first, last

    def copyfile(self, source, output) -> None:
        length = getattr(self, "_response_length", None)
        if length is None:
            return super().copyfile(source, output)
        remaining = length
        while remaining:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            output.write(chunk)
            remaining -= len(chunk)

    def do_POST(self) -> None:
        self.send_error(405, "Showcase fixtures are read-only")

    def do_PUT(self) -> None:
        self.send_error(405, "Showcase fixtures are read-only")

    def do_PATCH(self) -> None:
        self.send_error(405, "Showcase fixtures are read-only")

    def do_DELETE(self) -> None:
        self.send_error(405, "Showcase fixtures are read-only")

    def log_message(self, _format: str, *_args: object) -> None:
        # Avoid noisy request logs in Playwright output.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    root = args.dist.resolve(strict=True)
    if not (root / "index.html").is_file() or not (root / "showcase.json").is_file():
        parser.error("--dist must contain index.html and showcase.json")

    handler = partial(ReadOnlyHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    server.daemon_threads = True
    print(f"http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
