"""Development/managed-preview launcher; use serve.py for the operator app."""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from pathlib import Path

from laundrybench.web import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="3000")
    parser.add_argument("--strictPort", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    outputs = project / "outputs"
    subprocess.run(
        [sys.executable, str(project / "scripts/demo_web.py"), "--output-dir", str(outputs)],
        check=True,
    )
    server = create_server(outputs, port=8765)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    command = ["npm", "run", "dev", "--", "--port", args.port, "--host", args.host]
    if args.strictPort:
        command.append("--strictPort")
    try:
        subprocess.run(command, cwd=project / "frontend", check=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
