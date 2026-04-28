#!/usr/bin/env python3
"""Build an end-to-end morning proof report from Factory Vision receipts.

The report intentionally separates accepted counts from suppressed/uncertain
tracks. It does not turn raw detections or unaudited counts into product counts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA_VERSION = "factory-morning-proof-report-v1"
DEFAULT_DIAGNOSTICS = [
    "data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/diagnostic.json",
    "data/diagnostics/event-windows/factory2-event0006-370s-panel-v4-protrusion-gated/diagnostic.json",
]
DEFAULT_FP_REPORTS = [
    "data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def summarize_diagnostic(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    gate_summary = payload.get("perception_gate_summary") or {}
    gate_rows = as_list(payload.get("perception_gate"))
    diagnosis_rows = as_list(payload.get("diagnosis"))

    decision_counts = Counter()
    reason_counts = Counter()
    for row in gate_rows or diagnosis_rows:
        decision = str(row.get("decision") or "unknown")
        reason = str(row.get("reason") or "unknown")
        decision_counts[decision] += 1
        reason_counts[reason] += 1

    if gate_summary.get("decision_counts"):
        decision_counts = Counter({str(k): int(v) for k, v in gate_summary.get("decision_counts", {}).items()})
    if gate_summary.get("reason_counts"):
        reason_counts = Counter({str(k): int(v) for k, v in gate_summary.get("reason_counts", {}).items()})

    allowed_tracks = [int(track_id) for track_id in as_list(gate_summary.get("allowed_source_token_tracks"))]
    accepted_count = len(allowed_tracks)
    track_count = int(gate_summary.get("track_count") or len(gate_rows) or len(diagnosis_rows))
    suppressed_count = int(decision_counts.get("reject", 0))
    uncertain_count = int(decision_counts.get("uncertain", 0))

    receipt_paths = [str(p) for p in as_list(payload.get("track_receipts"))]
    card_paths = [str(p) for p in as_list(payload.get("track_receipt_cards"))]

    return {
        "diagnostic_path": str(path),
        "video_path": payload.get("video_path"),
        "window": {
            "start_timestamp": payload.get("start_timestamp"),
            "end_timestamp": payload.get("end_timestamp"),
            "fps": payload.get("fps"),
            "frame_count": payload.get("frame_count"),
        },
        "model_path": payload.get("model_path"),
        "person_model_path": payload.get("person_model_path"),
        "accepted_count": accepted_count,
        "allowed_source_token_tracks": allowed_tracks,
        "suppressed_count": suppressed_count,
        "uncertain_count": uncertain_count,
        "track_count": track_count,
        "decision_counts": counter_to_dict(decision_counts),
        "reason_counts": counter_to_dict(reason_counts),
        "has_source_to_output_candidate": bool((payload.get("summary") or {}).get("has_source_to_output_candidate")),
        "overlay_sheet_path": payload.get("overlay_sheet_path"),
        "overlay_video_path": payload.get("overlay_video_path"),
        "hard_negative_manifest_path": payload.get("hard_negative_manifest_path"),
        "track_receipts": receipt_paths,
        "track_receipt_cards": card_paths,
        "sample_receipts": receipt_paths[:3],
        "sample_receipt_cards": card_paths[:3],
    }


def summarize_fp_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    hard_negative_images = int(payload.get("hard_negative_images") or len(as_list(payload.get("items"))))
    false_positive_detections = int(payload.get("false_positive_detections") or 0)
    images_with_false_positives = int(payload.get("images_with_false_positives") or 0)
    rate = payload.get("false_positive_image_rate")
    if rate is None:
        rate = images_with_false_positives / hard_negative_images if hard_negative_images else None
    return {
        "report_path": str(path),
        "model_path": payload.get("model_path"),
        "confidence": payload.get("confidence"),
        "data_yaml": payload.get("data_yaml"),
        "dataset_manifest": payload.get("dataset_manifest"),
        "hard_negative_images": hard_negative_images,
        "images_with_false_positives": images_with_false_positives,
        "false_positive_detections": false_positive_detections,
        "false_positive_image_rate": rate,
    }


def build_report(*, diagnostic_paths: Iterable[Path], fp_report_paths: Iterable[Path]) -> dict[str, Any]:
    diagnostics = [summarize_diagnostic(path) for path in diagnostic_paths]
    fp_reports = [summarize_fp_report(path) for path in fp_report_paths]

    accepted_count = sum(int(item["accepted_count"]) for item in diagnostics)
    suppressed_count = sum(int(item["suppressed_count"]) for item in diagnostics)
    uncertain_count = sum(int(item["uncertain_count"]) for item in diagnostics)
    track_count = sum(int(item["track_count"]) for item in diagnostics)

    reason_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    for item in diagnostics:
        reason_counts.update({str(k): int(v) for k, v in item.get("reason_counts", {}).items()})
        decision_counts.update({str(k): int(v) for k, v in item.get("decision_counts", {}).items()})

    fp_images = sum(int(item["hard_negative_images"]) for item in fp_reports)
    fp_detections = sum(int(item["false_positive_detections"]) for item in fp_reports)
    fp_images_with_hits = sum(int(item["images_with_false_positives"]) for item in fp_reports)

    bottleneck = "none"
    if accepted_count == 0:
        if reason_counts.get("worker_body_overlap", 0):
            bottleneck = "perception_gate_worker_body_overlap"
        elif reason_counts.get("source_without_output_settle", 0):
            bottleneck = "source_without_output_settle"
        else:
            bottleneck = "no_gate_approved_source_tokens"

    verdict = "accepted_positive_count_available" if accepted_count else "auditable_abstention_no_trusted_positive"

    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "accepted_count": accepted_count,
        "suppressed_count": suppressed_count,
        "uncertain_count": uncertain_count,
        "track_count": track_count,
        "decision_counts": counter_to_dict(decision_counts),
        "reason_counts": counter_to_dict(reason_counts),
        "bottleneck": bottleneck,
        "diagnostics": diagnostics,
        "detector_false_positive_eval": {
            "report_count": len(fp_reports),
            "hard_negative_images": fp_images,
            "images_with_false_positives": fp_images_with_hits,
            "false_positive_detections": fp_detections,
            "reports": fp_reports,
        },
        "morning_bar_moved": bool(diagnostics and fp_reports),
        "note": (
            "Counts remain zero unless a perception-gate-approved source token exists. "
            "Suppressed/uncertain tracks are evidence, not failures to be force-counted."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Factory2 Morning Proof Report",
        "",
        f"Verdict: `{report['verdict']}`",
        "",
        "## Count decision summary",
        "",
        f"- accepted_count: {report['accepted_count']}",
        f"- suppressed_count: {report['suppressed_count']}",
        f"- uncertain_count: {report['uncertain_count']}",
        f"- total_tracks_reviewed: {report['track_count']}",
        f"- bottleneck: `{report['bottleneck']}`",
        "",
        "## Detector false-positive eval",
        "",
    ]
    fp = report["detector_false_positive_eval"]
    lines.extend(
        [
            f"- hard_negative_images: {fp['hard_negative_images']}",
            f"- images_with_false_positives: {fp['images_with_false_positives']}",
            f"- false_positive_detections: {fp['false_positive_detections']}",
            "",
            "## Representative diagnostic windows",
            "",
        ]
    )
    for item in report["diagnostics"]:
        window = item.get("window") or {}
        lines.extend(
            [
                f"### {item['diagnostic_path']}",
                "",
                f"- window: {window.get('start_timestamp')}–{window.get('end_timestamp')}s at {window.get('fps')} fps",
                f"- accepted: {item['accepted_count']}; suppressed: {item['suppressed_count']}; uncertain: {item['uncertain_count']}",
                f"- reasons: `{item['reason_counts']}`",
                f"- overlay_sheet: `{item.get('overlay_sheet_path')}`",
                f"- hard_negative_manifest: `{item.get('hard_negative_manifest_path')}`",
                f"- sample_receipts: `{item.get('sample_receipts')}`",
                "",
            ]
        )
    lines.extend(["## Operating note", "", str(report["note"]), ""])
    return "\n".join(lines)


def existing_paths(paths: Iterable[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(path)
        resolved.append(path)
    return resolved


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build Factory2 morning proof report from existing receipts")
    parser.add_argument("--diagnostic", action="append", dest="diagnostics", default=None, help="diagnostic.json path; may repeat")
    parser.add_argument("--fp-report", action="append", dest="fp_reports", default=None, help="detector FP report JSON; may repeat")
    parser.add_argument("--output", type=Path, default=Path("data/reports/factory2_morning_proof_report.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("data/reports/factory2_morning_proof_report.md"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.output.exists() and not args.force:
        raise FileExistsError(f"{args.output} exists; pass --force")
    if args.markdown_output.exists() and not args.force:
        raise FileExistsError(f"{args.markdown_output} exists; pass --force")

    diagnostic_paths = existing_paths(args.diagnostics or DEFAULT_DIAGNOSTICS)
    fp_report_paths = existing_paths(args.fp_reports or DEFAULT_FP_REPORTS)
    report = build_report(diagnostic_paths=diagnostic_paths, fp_report_paths=fp_report_paths)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({"output": str(args.output), "markdown_output": str(args.markdown_output), "verdict": report["verdict"], "accepted_count": report["accepted_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
