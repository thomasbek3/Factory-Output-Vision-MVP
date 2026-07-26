#!/usr/bin/env python3
"""Turn stable hard-negative onboarding proposals into a YOLO empty-label negative export.

Bridges the onboarding event proposer (stable low-motion windows) into the existing
hard-negative export chain so auto-onboarding datasets get real hard negatives.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.research.factory2.export_hard_negatives import export_hard_negatives

MANIFEST_SCHEMA = "factory-hard-negative-manifest-v1"


def build_stable_negative_manifest(
    *,
    event_proposals_path: Path,
    work_dir: Path,
    frames_per_negative: int = 1,
    frame_provider: Any = None,
) -> Path:
    proposals_payload = json.loads(event_proposals_path.read_text(encoding="utf-8"))
    negatives = [
        proposal
        for proposal in proposals_payload.get("proposals") or []
        if proposal.get("candidate_type") == "hard_negative_candidate"
    ]
    reader = frame_provider or _default_frame_provider()

    frames_dir = work_dir / "negative_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for index, proposal in enumerate(negatives, start=1):
        segment_path = Path(str(proposal.get("segment_path")))
        center = float(proposal.get("center_offset_sec") or 0.0)
        end = float(proposal.get("end_offset_sec") or center)
        raw_crop_paths: list[str] = []
        step = (end - center) / frames_per_negative if frames_per_negative > 1 else 0.0
        for frame_index in range(max(1, frames_per_negative)):
            timestamp_sec = round(center + frame_index * step, 3)
            try:
                frame = reader(segment_path, timestamp_sec)
            except Exception:  # noqa: BLE001 - unreadable frame skips, never aborts
                continue
            frame_path = frames_dir / f"neg_{index:04d}_{frame_index:02d}_{timestamp_sec:.3f}s.jpg"
            if _write_frame(frame_path, frame):
                raw_crop_paths.append(str(frame_path))
        if not raw_crop_paths:
            continue
        items.append(
            {
                "label": "hard_negative",
                "reason": "stable_low_motion_window",
                "track_id": index,
                "assets": {"raw_crop_paths": raw_crop_paths},
                "evidence": {
                    "candidate_id": proposal.get("candidate_id"),
                    "segment_id": proposal.get("segment_id"),
                    "motion_summary": proposal.get("motion_summary"),
                    "training_provenance": proposal.get("training_provenance"),
                },
            }
        )

    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "source_event_proposals": str(event_proposals_path),
        "station_id": proposals_payload.get("station_id"),
        "items": items,
    }
    manifest_path = work_dir / "stable_negative_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def _write_frame(path: Path, frame: Any) -> bool:
    import cv2  # noqa: PLC0415

    return bool(cv2.imwrite(str(path), frame))


def _default_frame_provider() -> Any:
    def _read(video_path: Path, timestamp_sec: float) -> Any:
        import cv2  # noqa: PLC0415

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"could not open video: {video_path}")
        try:
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_sec) * 1000.0)
            ok, frame = capture.read()
        finally:
            capture.release()
        if not ok or frame is None:
            raise RuntimeError(f"could not read frame at {timestamp_sec:.3f}s from {video_path}")
        return frame

    return _read


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export stable onboarding negatives as YOLO empty-label images")
    parser.add_argument("--event-proposals", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--frames-per-negative", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest_path = build_stable_negative_manifest(
            event_proposals_path=args.event_proposals,
            work_dir=args.work_dir,
            frames_per_negative=args.frames_per_negative,
        )
        export_path = export_hard_negatives(
            manifest_paths=[manifest_path],
            out_dir=args.out_dir,
            write_yolo_negatives=True,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    export = json.loads(export_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "stable_negative_manifest": manifest_path.as_posix(),
                "hard_negative_export": export_path.as_posix(),
                "negative_count": export.get("count"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
