#!/usr/bin/env python3
"""Build a review package for Factory2's runtime-only divergent delivery chains."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

import cv2


SCHEMA_VERSION = "factory2-divergent-chain-review-v1"
DEFAULT_RUNTIME_AUDIT = Path("data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json")
DEFAULT_LINEAGE_REPORT = Path("data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json")
DEFAULT_DIVERGENCE_REPORT = Path("data/reports/factory2_proof_runtime_divergence.final_two_v1.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_divergent_chain_review.v1.json")
DEFAULT_PACKAGE_DIR = Path("data/datasets/factory2_divergent_chain_review_v1")
CROP_LABELS = ["carried_panel", "worker_only", "static_stack", "unclear"]
RELATION_LABELS = ["distinct_new_delivery", "same_delivery_as_prior", "static_resident", "unclear"]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _track_class(observations: list[dict[str, Any]]) -> str:
    source_frames = sum(1 for row in observations if str(row.get("zone") or "") == "source")
    output_frames = sum(1 for row in observations if str(row.get("zone") or "") == "output")
    if source_frames > 0 and output_frames > 0:
        return "source_to_output"
    if source_frames > 0:
        return "source_only"
    if output_frames > 0:
        return "output_only"
    return "unknown"


def _unique_zones(observations: list[dict[str, Any]]) -> list[str]:
    output: list[str] = []
    for row in observations:
        zone = str(row.get("zone") or "unknown")
        if zone not in output:
            output.append(zone)
    return output


def _track_summary(track_id: int, observations: list[dict[str, Any]], track_role: str) -> dict[str, Any]:
    ordered = sorted(observations, key=lambda row: float(row.get("timestamp") or 0.0))
    person_overlap_max = max((float(row.get("person_overlap") or 0.0) for row in ordered), default=0.0)
    outside_person_min = min((float(row.get("outside_person_ratio") or 1.0) for row in ordered), default=1.0)
    static_overlap_max = max((float(row.get("static_stack_overlap_ratio") or 0.0) for row in ordered), default=0.0)
    return {
        "track_id": track_id,
        "track_role": track_role,
        "track_class": _track_class(ordered),
        "first_timestamp": round(float(ordered[0].get("timestamp") or 0.0), 3),
        "last_timestamp": round(float(ordered[-1].get("timestamp") or 0.0), 3),
        "detection_count": len(ordered),
        "source_frames": sum(1 for row in ordered if str(row.get("zone") or "") == "source"),
        "output_frames": sum(1 for row in ordered if str(row.get("zone") or "") == "output"),
        "zones_seen": _unique_zones(ordered),
        "person_overlap_max": round(person_overlap_max, 6),
        "outside_person_min": round(outside_person_min, 6),
        "static_stack_overlap_max": round(static_overlap_max, 6),
    }


def _select_representative_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not observations:
        return []
    ordered = sorted(observations, key=lambda row: float(row.get("timestamp") or 0.0))
    indexes = sorted({0, len(ordered) // 2, len(ordered) - 1})
    result: list[dict[str, Any]] = []
    seen_timestamps: set[float] = set()
    for index in indexes:
        row = ordered[index]
        timestamp = round(float(row.get("timestamp") or 0.0), 6)
        if timestamp in seen_timestamps:
            continue
        seen_timestamps.add(timestamp)
        result.append(row)
    return result


def _read_frame(capture: cv2.VideoCapture, frame_index: int) -> Any:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    if not ok or frame is None:
        return None
    return frame


def _crop_frame(frame: Any, box_xywh: list[float], *, padding: int = 20) -> Any:
    height, width = frame.shape[:2]
    x, y, w, h = [int(round(float(value))) for value in box_xywh]
    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(width, x + max(w, 1) + padding)
    y1 = min(height, y + max(h, 1) + padding)
    return frame[y0:y1, x0:x1]


def _draw_box(frame: Any, box_xywh: list[float]) -> Any:
    image = frame.copy()
    x, y, w, h = [int(round(float(value))) for value in box_xywh]
    cv2.rectangle(image, (x, y), (x + max(w, 1), y + max(h, 1)), (0, 255, 0), 2)
    return image


def _write_classes(path: Path, classes: list[str]) -> None:
    path.write_text("\n".join(classes) + "\n", encoding="utf-8")


def _write_readme(path: Path) -> None:
    path.write_text(
        "# Factory2 Divergent Chain Review Package\n\n"
        "This package isolates the final runtime-only divergent events and the nearby track fragments.\n\n"
        "- `images/` contains extracted frame and crop assets.\n"
        "- `review_manifest.json` keeps the full provenance for every review item.\n"
        "- `review_labels.csv` is the writable review sheet for crop and relation labels.\n"
        "- `crop_classes.txt` and `relation_classes.txt` list the allowed labels.\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    fieldnames = [
        "item_id",
        "event_id",
        "event_ts",
        "track_id",
        "track_role",
        "track_class",
        "timestamp_seconds",
        "zone",
        "confidence",
        "person_overlap_ratio",
        "outside_person_ratio",
        "static_stack_overlap_ratio",
        "frame_image_path",
        "crop_image_path",
        "crop_label",
        "relation_label",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            placeholder = item.get("label_placeholder") or {}
            writer.writerow(
                {
                    "item_id": item.get("item_id"),
                    "event_id": item.get("event_id"),
                    "event_ts": item.get("event_ts"),
                    "track_id": item.get("track_id"),
                    "track_role": item.get("track_role"),
                    "track_class": item.get("track_class"),
                    "timestamp_seconds": item.get("timestamp_seconds"),
                    "zone": item.get("zone"),
                    "confidence": item.get("confidence"),
                    "person_overlap_ratio": item.get("person_overlap_ratio"),
                    "outside_person_ratio": item.get("outside_person_ratio"),
                    "static_stack_overlap_ratio": item.get("static_stack_overlap_ratio"),
                    "frame_image_path": item.get("frame_image_path"),
                    "crop_image_path": item.get("crop_image_path"),
                    "crop_label": placeholder.get("crop_label"),
                    "relation_label": placeholder.get("relation_label"),
                    "notes": placeholder.get("notes"),
                }
            )


def _track_role(
    *,
    track_id: int,
    runtime_track_id: int,
    source_track_id: int | None,
    prior_runtime_track_id: int | None,
    runtime_event_track_ids: set[int],
) -> str:
    if track_id == runtime_track_id:
        return "divergent_runtime_event"
    if source_track_id is not None and track_id == source_track_id:
        return "source_anchor"
    if prior_runtime_track_id is not None and track_id == prior_runtime_track_id:
        return "prior_runtime_event"
    if track_id in runtime_event_track_ids:
        return "runtime_event_context"
    return "window_context"


def build_divergent_chain_review(
    *,
    runtime_audit_path: Path,
    lineage_report_path: Path,
    divergence_report_path: Path,
    output_report_path: Path,
    package_dir: Path,
    force: bool,
) -> dict[str, Any]:
    if output_report_path.exists() and not force:
        raise FileExistsError(output_report_path)
    if package_dir.exists():
        if not force:
            raise FileExistsError(package_dir)
        shutil.rmtree(package_dir)

    runtime_audit = load_json(runtime_audit_path)
    lineage_report = load_json(lineage_report_path)
    divergence_report = load_json(divergence_report_path)
    track_histories = runtime_audit.get("track_histories") or {}
    runtime_events = [row for row in as_list(runtime_audit.get("events")) if isinstance(row, dict)]
    divergent_ids_by_ts = {
        round(float(row["event_ts"]), 3): str(row.get("event_id") or f"factory2-runtime-only-{index:04d}")
        for index, row in enumerate(as_list(divergence_report.get("divergent_events")), start=1)
        if isinstance(row, dict) and row.get("event_ts") is not None
    }

    video_path = Path(str(runtime_audit.get("video_path") or ""))
    video_fps = float(runtime_audit.get("video_fps") or 0.0)
    capture = cv2.VideoCapture(str(video_path))
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    event_entries: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    try:
        for lineage_row in as_list(lineage_report.get("synthetic_events")):
            if not isinstance(lineage_row, dict) or not lineage_row.get("is_divergent"):
                continue
            event_ts = round(float(lineage_row.get("event_ts") or 0.0), 3)
            event_id = divergent_ids_by_ts.get(event_ts, f"factory2-runtime-only-ts-{str(event_ts).replace('.', '_')}")
            runtime_track_id = int(lineage_row.get("track_id") or 0)
            source_track_id = (
                int(lineage_row["source_track_id"]) if lineage_row.get("source_track_id") is not None else None
            )
            window_start = float(lineage_row.get("recommended_search_start_seconds") or event_ts)
            window_end = float(lineage_row.get("recommended_search_end_seconds") or event_ts)
            window_events = [
                row
                for row in runtime_events
                if window_start <= float(row.get("event_ts") or 0.0) <= window_end
            ]
            prior_runtime_event = max(
                (
                    row
                    for row in window_events
                    if float(row.get("event_ts") or 0.0) < event_ts
                ),
                key=lambda row: float(row.get("event_ts") or 0.0),
                default=None,
            )
            runtime_event_track_ids = {int(row.get("track_id") or 0) for row in window_events}
            relevant_tracks: list[tuple[int, list[dict[str, Any]]]] = []
            for track_id_str, history in track_histories.items():
                if not isinstance(history, list):
                    continue
                observations = [
                    row
                    for row in history
                    if window_start <= float(row.get("timestamp") or 0.0) <= window_end
                ]
                if observations:
                    relevant_tracks.append((int(track_id_str), observations))
            relevant_tracks.sort(key=lambda item: float(item[1][0].get("timestamp") or 0.0))

            track_summaries: list[dict[str, Any]] = []
            for track_id, observations in relevant_tracks:
                role = _track_role(
                    track_id=track_id,
                    runtime_track_id=runtime_track_id,
                    source_track_id=source_track_id,
                    prior_runtime_track_id=int(prior_runtime_event.get("track_id") or 0) if prior_runtime_event else None,
                    runtime_event_track_ids=runtime_event_track_ids,
                )
                track_summaries.append(_track_summary(track_id, observations, role))
                for observation_index, observation in enumerate(_select_representative_observations(observations), start=1):
                    timestamp = float(observation.get("timestamp") or 0.0)
                    frame_index = max(0, int(round(timestamp * video_fps)))
                    frame = _read_frame(capture, frame_index)
                    if frame is None:
                        continue
                    frame_image = _draw_box(frame, list(observation.get("box_xywh") or [0, 0, 1, 1]))
                    crop_image = _crop_frame(frame, list(observation.get("box_xywh") or [0, 0, 1, 1]))
                    item_id = (
                        f"{event_id}-track-{track_id:06d}-obs-{observation_index:02d}-"
                        f"{str(observation.get('zone') or 'unknown')}"
                    )
                    frame_path = images_dir / f"{item_id}-frame.jpg"
                    crop_path = images_dir / f"{item_id}-crop.jpg"
                    cv2.imwrite(str(frame_path), frame_image)
                    cv2.imwrite(str(crop_path), crop_image)
                    items.append(
                        {
                            "item_id": item_id,
                            "event_id": event_id,
                            "event_ts": event_ts,
                            "track_id": track_id,
                            "track_role": role,
                            "track_class": _track_class(observations),
                            "timestamp_seconds": round(timestamp, 3),
                            "zone": str(observation.get("zone") or "unknown"),
                            "confidence": float(observation.get("confidence") or 0.0),
                            "person_overlap_ratio": round(float(observation.get("person_overlap") or 0.0), 6),
                            "outside_person_ratio": round(float(observation.get("outside_person_ratio") or 0.0), 6),
                            "static_stack_overlap_ratio": round(
                                float(observation.get("static_stack_overlap_ratio") or 0.0), 6
                            ),
                            "frame_image_path": str(frame_path),
                            "crop_image_path": str(crop_path),
                            "label_placeholder": {
                                "crop_label": "unclear",
                                "relation_label": "unclear",
                                "notes": "",
                            },
                        }
                    )

            event_entries.append(
                {
                    "event_id": event_id,
                    "event_ts": event_ts,
                    "runtime_track_id": runtime_track_id,
                    "source_track_id": source_track_id,
                    "count_total": int(lineage_row.get("count_total") or 0),
                    "source_gap_seconds": lineage_row.get("source_gap_seconds"),
                    "review_window": {
                        "start_seconds": round(window_start, 3),
                        "end_seconds": round(window_end, 3),
                    },
                    "prior_runtime_event": (
                        {
                            "event_ts": round(float(prior_runtime_event.get("event_ts") or 0.0), 3),
                            "track_id": int(prior_runtime_event.get("track_id") or 0),
                            "provenance_status": prior_runtime_event.get("provenance_status"),
                        }
                        if prior_runtime_event
                        else None
                    ),
                    "window_runtime_events": [
                        {
                            "event_ts": round(float(row.get("event_ts") or 0.0), 3),
                            "track_id": int(row.get("track_id") or 0),
                            "provenance_status": row.get("provenance_status"),
                            "reason": row.get("reason"),
                        }
                        for row in sorted(window_events, key=lambda item: float(item.get("event_ts") or 0.0))
                    ],
                    "track_summaries": track_summaries,
                }
            )
    finally:
        capture.release()

    items.sort(
        key=lambda item: (
            item["event_id"],
            int(item["track_id"]),
            float(item["timestamp_seconds"]),
            item["zone"],
        )
    )

    package_dir.mkdir(parents=True, exist_ok=True)
    review_manifest_path = package_dir / "review_manifest.json"
    review_labels_csv_path = package_dir / "review_labels.csv"
    crop_classes_path = package_dir / "crop_classes.txt"
    relation_classes_path = package_dir / "relation_classes.txt"
    readme_path = package_dir / "README.md"
    _write_csv(review_labels_csv_path, items)
    _write_classes(crop_classes_path, CROP_LABELS)
    _write_classes(relation_classes_path, RELATION_LABELS)
    _write_readme(readme_path)

    result = {
        "schema_version": SCHEMA_VERSION,
        "runtime_audit_path": str(runtime_audit_path),
        "lineage_report_path": str(lineage_report_path),
        "divergence_report_path": str(divergence_report_path),
        "package_dir": str(package_dir),
        "review_manifest_path": str(review_manifest_path),
        "review_labels_csv_path": str(review_labels_csv_path),
        "crop_classes_path": str(crop_classes_path),
        "relation_classes_path": str(relation_classes_path),
        "event_count": len(event_entries),
        "item_count": len(items),
        "events": event_entries,
        "items": items,
    }
    write_json(review_manifest_path, result)
    write_json(output_report_path, result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review package for Factory2 divergent delivery chains.")
    parser.add_argument("--runtime-audit", type=Path, default=DEFAULT_RUNTIME_AUDIT)
    parser.add_argument("--lineage-report", type=Path, default=DEFAULT_LINEAGE_REPORT)
    parser.add_argument("--divergence-report", type=Path, default=DEFAULT_DIVERGENCE_REPORT)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_divergent_chain_review(
        runtime_audit_path=args.runtime_audit,
        lineage_report_path=args.lineage_report,
        divergence_report_path=args.divergence_report,
        output_report_path=args.output_report,
        package_dir=args.package_dir,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
