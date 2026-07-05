#!/usr/bin/env python3
"""Build a recall-oriented work queue for uncovered Factory2 positive windows.

This is a diagnostic planning artifact, not a count source. It bridges from
reviewed positive frame labels to the current proof coverage so the next recall
work targets uncovered likely carries instead of hand-picked windows.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_REVIEWED_MANIFEST = Path("data/labels/active_panel_reviewed_autopilot-v1_minconf050.json")
DEFAULT_PROOF_REPORT = Path("data/reports/factory2_morning_proof_report.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_recall_work_queue.json")
DEFAULT_VIDEO_PATH = "data/videos/from-pc/factory2.MOV"
SCHEMA_VERSION = "factory2-recall-work-queue-v1"


@dataclass(frozen=True)
class ReviewedAccept:
    label_id: str
    frame_id: str
    frame_path: str
    video_path: str
    timestamp_seconds: float
    confidence: float


@dataclass(frozen=True)
class PositiveCluster:
    cluster_id: str
    video_path: str
    frame_ids: list[str]
    label_ids: list[str]
    frame_paths: list[str]
    timestamps: list[float]
    first_timestamp: float
    last_timestamp: float
    center_timestamp: float
    peak_confidence: float


@dataclass(frozen=True)
class DiagnosticWindow:
    diagnostic_path: str
    start_timestamp: float
    end_timestamp: float


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Factory2 reviewed-positive recall work queue."
    )
    parser.add_argument("--reviewed-manifest", type=Path, default=DEFAULT_REVIEWED_MANIFEST)
    parser.add_argument("--proof-report", type=Path, default=DEFAULT_PROOF_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--video-path", default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--cluster-gap-seconds", type=float, default=25.0)
    parser.add_argument("--window-padding-seconds", type=float, default=20.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def load_reviewed_accepts(manifest_path: Path, *, video_path: str) -> list[ReviewedAccept]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    accepted_rows = payload.get("accepted") or []
    rows: list[ReviewedAccept] = []
    for row in accepted_rows:
        if not isinstance(row, dict):
            continue
        label = row.get("label") or {}
        metadata = label.get("metadata") or {}
        if str(metadata.get("video_path") or "") != video_path:
            continue
        rows.append(
            ReviewedAccept(
                label_id=str(row.get("label_id") or label.get("label_id") or ""),
                frame_id=str(label.get("frame_id") or ""),
                frame_path=str(metadata.get("frame_path") or ""),
                video_path=str(metadata.get("video_path") or ""),
                timestamp_seconds=float(metadata.get("timestamp_seconds") or 0.0),
                confidence=float(label.get("confidence") or 0.0),
            )
        )
    rows.sort(key=lambda item: item.timestamp_seconds)
    return rows


def cluster_reviewed_accepts(
    accepts: list[ReviewedAccept],
    *,
    cluster_gap_seconds: float,
) -> list[PositiveCluster]:
    if cluster_gap_seconds < 0:
        raise ValueError("cluster_gap_seconds must be non-negative")
    if not accepts:
        return []

    buckets: list[list[ReviewedAccept]] = [[accepts[0]]]
    for item in accepts[1:]:
        current = buckets[-1]
        if item.timestamp_seconds - current[-1].timestamp_seconds <= cluster_gap_seconds:
            current.append(item)
        else:
            buckets.append([item])

    clusters: list[PositiveCluster] = []
    for index, bucket in enumerate(buckets, start=1):
        timestamps = [item.timestamp_seconds for item in bucket]
        clusters.append(
            PositiveCluster(
                cluster_id=f"factory2-review-{index:04d}",
                video_path=bucket[0].video_path,
                frame_ids=[item.frame_id for item in bucket],
                label_ids=[item.label_id for item in bucket],
                frame_paths=[item.frame_path for item in bucket],
                timestamps=timestamps,
                first_timestamp=timestamps[0],
                last_timestamp=timestamps[-1],
                center_timestamp=sum(timestamps) / len(timestamps),
                peak_confidence=max(item.confidence for item in bucket),
            )
        )
    return clusters


def load_proof_diagnostic_windows(proof_report_path: Path) -> list[DiagnosticWindow]:
    payload = json.loads(proof_report_path.read_text(encoding="utf-8"))
    diagnostics = payload.get("diagnostics") or []
    windows: list[DiagnosticWindow] = []
    for row in diagnostics:
        if not isinstance(row, dict):
            continue
        window = row.get("window") or {}
        try:
            start = float(window["start_timestamp"])
            end = float(window["end_timestamp"])
        except (KeyError, TypeError, ValueError):
            continue
        windows.append(
            DiagnosticWindow(
                diagnostic_path=str(row.get("diagnostic_path") or ""),
                start_timestamp=start,
                end_timestamp=end,
            )
        )
    return windows


def build_work_queue(
    *,
    reviewed_manifest_path: Path,
    proof_report_path: Path,
    output_path: Path,
    video_path: str,
    cluster_gap_seconds: float,
    window_padding_seconds: float,
    force: bool,
) -> dict[str, Any]:
    if window_padding_seconds < 0:
        raise ValueError("window_padding_seconds must be non-negative")
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")

    accepts = load_reviewed_accepts(reviewed_manifest_path, video_path=video_path)
    clusters = cluster_reviewed_accepts(accepts, cluster_gap_seconds=cluster_gap_seconds)
    proof_windows = load_proof_diagnostic_windows(proof_report_path)

    cluster_rows: list[dict[str, Any]] = []
    covered_count = 0
    for cluster in clusters:
        covering = [
            window.diagnostic_path
            for window in proof_windows
            if cluster.first_timestamp >= window.start_timestamp and cluster.last_timestamp <= window.end_timestamp
        ]
        covered = bool(covering)
        if covered:
            covered_count += 1
        cluster_rows.append(
            {
                **asdict(cluster),
                "covered_by_existing_diagnostic": covered,
                "covering_diagnostic_paths": covering,
                "suggested_start_timestamp": round(max(0.0, cluster.first_timestamp - window_padding_seconds), 3),
                "suggested_end_timestamp": round(cluster.last_timestamp + window_padding_seconds, 3),
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "reviewed_manifest_path": str(reviewed_manifest_path),
        "proof_report_path": str(proof_report_path),
        "video_path": video_path,
        "accepted_frame_count": len(accepts),
        "cluster_count": len(cluster_rows),
        "covered_cluster_count": covered_count,
        "uncovered_cluster_count": len(cluster_rows) - covered_count,
        "cluster_gap_seconds": cluster_gap_seconds,
        "window_padding_seconds": window_padding_seconds,
        "clusters": cluster_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_work_queue(
        reviewed_manifest_path=args.reviewed_manifest,
        proof_report_path=args.proof_report,
        output_path=args.output,
        video_path=str(args.video_path),
        cluster_gap_seconds=float(args.cluster_gap_seconds),
        window_padding_seconds=float(args.window_padding_seconds),
        force=bool(args.force),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
