from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.onboarding_windows import extract_candidate_windows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract onboarding candidate windows from recorded segments")
    parser.add_argument("--segment-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--window-sec", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = extract_candidate_windows(
            segment_manifest_path=args.segment_manifest,
            output_dir=args.output_dir,
            window_sec=args.window_sec,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
