"""Serve an exported LaundryBench Showcase directory as a read-only fixture."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class ReadOnlyHandler(SimpleHTTPRequestHandler):
    """Static files plus deterministic API-to-JSON route rewriting."""

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
