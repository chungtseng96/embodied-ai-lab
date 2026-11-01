"""HTTP contract tests for the static Showcase fixture server."""
from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from showcase_fixture_server import ReadOnlyHandler  # noqa: E402


class ReadOnlyFixtureRangeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="showcase-http-test-")
        self.root = Path(self.temp_dir.name)
        (self.root / "index.html").write_text("fixture", encoding="utf-8")
        (self.root / "showcase.json").write_text("{}\n", encoding="utf-8")
        (self.root / "sample.bin").write_bytes(b"0123456789")
        handler = partial(ReadOnlyHandler, directory=str(self.root))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/sample.bin"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def test_get_range_returns_exact_requested_bytes_and_headers(self) -> None:
        request = Request(self.url, headers={"Range": "bytes=2-5"})
        with urlopen(request) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")
            self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
            self.assertEqual(response.headers["Content-Length"], "4")
            self.assertEqual(response.read(), b"2345")

    def test_get_suffix_range_returns_last_bytes(self) -> None:
        request = Request(self.url, headers={"Range": "bytes=-2"})
        with urlopen(request) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.headers["Content-Range"], "bytes 8-9/10")
            self.assertEqual(response.read(), b"89")

    def test_head_reports_resource_length_and_range_support_without_a_body(self) -> None:
        request = Request(self.url, method="HEAD")
        with urlopen(request) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")
            self.assertEqual(response.headers["Content-Length"], "10")
            self.assertEqual(response.read(), b"")

    def test_head_ignores_range_and_reports_full_get_headers_without_a_body(self) -> None:
        request = Request(self.url, headers={"Range": "bytes=1-1"}, method="HEAD")
        with urlopen(request) as response:
            self.assertEqual(response.status, 200)
            self.assertIsNone(response.headers.get("Content-Range"))
            self.assertEqual(response.headers["Content-Length"], "10")
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")
            self.assertEqual(response.read(), b"")

    def test_unsatisfiable_range_returns_416_with_total_length(self) -> None:
        request = Request(self.url, headers={"Range": "bytes=10-12"})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 416)
        self.assertEqual(error.exception.headers["Content-Range"], "bytes */10")
        self.assertEqual(error.exception.headers["Accept-Ranges"], "bytes")


if __name__ == "__main__":
    unittest.main()
