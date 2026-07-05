from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.teacher_provider import build_teacher_labels_from_windows, provider_for_name, write_teacher_labels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate advisory teacher labels from onboarding windows")
    parser.add_argument("--window-manifest", type=Path, required=True)
    parser.add_argument("--provider", default="dry_run_fixture")
    parser.add_argument("--allow-cloud", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        provider = provider_for_name(args.provider, allow_cloud=args.allow_cloud)
        payload = build_teacher_labels_from_windows(window_manifest_path=args.window_manifest, provider=provider)
        write_teacher_labels(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "label_count": len(payload["labels"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
