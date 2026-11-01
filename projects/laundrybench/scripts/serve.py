from __future__ import annotations

import argparse
from pathlib import Path

from laundrybench.web import create_server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local results UI and post-episode labels; no robot motion controls."
    )
    parser.add_argument("--outputs-root", required=True, type=Path)
    parser.add_argument("--frontend-dir", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.outputs_root, args.frontend_dir, port=args.port)
    print(f"LaundryBench operator app: http://127.0.0.1:{server.server_port}", flush=True)
    print("One writer server per outputs root. Labels overlay original episode evidence.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
