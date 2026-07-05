from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.blind_replay_gate import run_blind_replay_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Factory Vision blind replay gate")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend-port", type=int)
    parser.add_argument("--frontend-port", type=int)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--no-auto-start", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = run_blind_replay_gate(
            manifest_path=args.manifest,
            output_path=args.output,
            execute=args.execute,
            backend_port=args.backend_port,
            frontend_port=args.frontend_port,
            auto_start=not args.no_auto_start,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "status": payload["status"], "passed": payload["passed"]}, sort_keys=True))
    return 0 if payload["passed"] or not args.execute else 1


if __name__ == "__main__":
    raise SystemExit(main())
