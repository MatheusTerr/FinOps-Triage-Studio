from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FinOps Triage Studio.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--reset", action="store_true", help="Recreate local database and model.")
    args = parser.parse_args()

    load_env_file(ROOT / ".env")
    from finops_triage.server import run_server

    run_server(root=ROOT, host=args.host, port=args.port, reset=args.reset)


if __name__ == "__main__":
    main()
