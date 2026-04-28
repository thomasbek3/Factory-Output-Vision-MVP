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
DEFAULT_POSITIVE_REPORTS = [
    "data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf025_iou030.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def failure_link_for(row: dict[str, Any]) -> str:
    """Map a gate/diagnosis row to the physical-evidence link that failed.

    The morning report should not merely say "count is zero". It should say
    which required source-token evidence link failed, in product language.
    """
    decision = str(row.get("decision") or "unknown")
    reason = str(row.get("reason") or "unknown")
    flags = {str(flag) for flag in as_list(row.get("flags"))}
    evidence = row.get("evidence") or {}

    if decision == "allow_source_token":
        return "source_token_approved"
    if reason == "worker_body_overlap" or "high_person_overlap" in flags or "not_enough_object_outside_person" in flags:
        return "worker_body_overlap"
    if reason in {"source_without_output_settle", "source_to_output_evidence_incomplete"}:
        if int(evidence.get("output_frames") or 0) <= 0:
            return "missing_output_settle"
        return "incomplete_source_to_output_path"
    if reason in {"static_stack_edge", "output_only_no_source_token"}:
        return "static_stack_or_resident_output"
    if reason == "insufficient_panel_evidence" or "low_flow_coherence" in flags or "low_track_displacement" in flags:
        return "insufficient_active_panel_evidence"
    return "unclassified_evidence_failure"


def track_id_from_path(path: str) -> Optional[int]:
    stem = Path(path).stem
    if not stem.startswith("track-"):
        return None
    raw_id = stem.replace("track-", "", 1).replace("-sheet", "")
    try:
        return int(raw_id)
    except ValueError:
        return None


def load_receipt_assets(path: str) -> dict[str, Any]:
    try:
        payload = load_json(Path(path))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload.get("review_assets") or {}


def build_track_receipts(gate_rows: list[Any], receipt_paths: list[str], card_paths: list[str]) -> list[dict[str, Any]]:
    receipt_by_track = {track_id: path for path in receipt_paths if (track_id := track_id_from_path(path)) is not None}
    card_by_track = {track_id: path for path in card_paths if (track_id := track_id_from_path(path)) is not None}
    rows: list[dict[str, Any]] = []
    for row in gate_rows:
        if not isinstance(row, dict):
            continue
        track_id = row.get("track_id")
        try:
            normalized_track_id = int(track_id)
        except (TypeError, ValueError):
            normalized_track_id = None
        receipt_path = receipt_by_track.get(normalized_track_id) if normalized_track_id is not None else None
        receipt_assets = load_receipt_assets(receipt_path) if receipt_path else {}
        rows.append(
            {
                "track_id": normalized_track_id,
                "decision": row.get("decision") or "unknown",
                "reason": row.get("reason") or "unknown",
                "failure_link": failure_link_for(row),
                "flags": as_list(row.get("flags")),
                "evidence_summary": {
                    key: (row.get("evidence") or {}).get(key)
                    for key in [
                        "source_frames",
                        "output_frames",
                        "person_overlap_ratio",
                        "outside_person_ratio",
                        "max_displacement",
                        "flow_coherence",
                        "static_stack_overlap_ratio",
                    ]
                },
                "receipt_json_path": receipt_path,
                "receipt_card_path": card_by_track.get(normalized_track_id) or receipt_assets.get("track_sheet_path"),
                "raw_crop_paths": as_list(receipt_assets.get("raw_crop_paths")),
            }
        )
    return rows


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
    track_receipts = build_track_receipts(gate_rows, receipt_paths, card_paths)
    failure_link_counts = Counter(str(item.get("failure_link") or "unknown") for item in track_receipts)

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
        "failure_link_counts": counter_to_dict(failure_link_counts),
        "has_source_to_output_candidate": bool((payload.get("summary") or {}).get("has_source_to_output_candidate")),
        "overlay_sheet_path": payload.get("overlay_sheet_path"),
        "overlay_video_path": payload.get("overlay_video_path"),
        "hard_negative_manifest_path": payload.get("hard_negative_manifest_path"),
        "track_receipts": receipt_paths,
        "track_receipt_cards": card_paths,
        "track_decision_receipts": track_receipts,
        "sample_receipts": receipt_paths[:3],
        "sample_receipt_cards": card_paths[:3],
    }


def summarize_fp_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    summary = payload.get("summary") or {}
    hard_negative_images = int(summary.get("hard_negative_images") or payload.get("hard_negative_images") or len(as_list(payload.get("items"))))
    false_positive_detections = int(summary.get("false_positive_detections") or payload.get("false_positive_detections") or 0)
    images_with_false_positives = int(summary.get("images_with_false_positives") or payload.get("images_with_false_positives") or 0)
    rate = summary.get("false_positive_image_rate")
    if rate is None:
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


def summarize_positive_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    summary = payload.get("summary") or {}
    positive_images = int(summary.get("positive_images") or payload.get("positive_images") or len(as_list(payload.get("items"))))
    positive_labels = int(summary.get("positive_labels") or payload.get("positive_labels") or 0)
    matched_labels = int(summary.get("matched_labels") or payload.get("matched_labels") or 0)
    missed_labels = int(summary.get("missed_labels") or payload.get("missed_labels") or max(0, positive_labels - matched_labels))
    label_recall = summary.get("label_recall")
    if label_recall is None:
        label_recall = payload.get("label_recall")
    if label_recall is None:
        label_recall = matched_labels / positive_labels if positive_labels else 0.0
    return {
        "report_path": str(path),
        "model_path": payload.get("model_path"),
        "confidence": payload.get("confidence"),
        "iou_threshold": payload.get("iou_threshold"),
        "data_yaml": payload.get("data_yaml"),
        "dataset_manifest": payload.get("dataset_manifest"),
        "positive_images": positive_images,
        "positive_labels": positive_labels,
        "images_with_any_detection": int(summary.get("images_with_any_detection") or payload.get("images_with_any_detection") or 0),
        "images_with_match": int(summary.get("images_with_match") or payload.get("images_with_match") or 0),
        "matched_labels": matched_labels,
        "missed_labels": missed_labels,
        "total_detections": int(summary.get("total_detections") or payload.get("total_detections") or 0),
        "label_recall": label_recall,
        "image_match_rate": summary.get("image_match_rate"),
    }


def build_report(*, diagnostic_paths: Iterable[Path], fp_report_paths: Iterable[Path], positive_report_paths: Iterable[Path] = ()) -> dict[str, Any]:
    diagnostics = [summarize_diagnostic(path) for path in diagnostic_paths]
    fp_reports = [summarize_fp_report(path) for path in fp_report_paths]
    positive_reports = [summarize_positive_report(path) for path in positive_report_paths]

    accepted_count = sum(int(item["accepted_count"]) for item in diagnostics)
    suppressed_count = sum(int(item["suppressed_count"]) for item in diagnostics)
    uncertain_count = sum(int(item["uncertain_count"]) for item in diagnostics)
    track_count = sum(int(item["track_count"]) for item in diagnostics)

    reason_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    failure_link_counts: Counter[str] = Counter()
    for item in diagnostics:
        reason_counts.update({str(k): int(v) for k, v in item.get("reason_counts", {}).items()})
        decision_counts.update({str(k): int(v) for k, v in item.get("decision_counts", {}).items()})
        failure_link_counts.update({str(k): int(v) for k, v in item.get("failure_link_counts", {}).items()})

    fp_images = sum(int(item["hard_negative_images"]) for item in fp_reports)
    fp_detections = sum(int(item["false_positive_detections"]) for item in fp_reports)
    fp_images_with_hits = sum(int(item["images_with_false_positives"]) for item in fp_reports)
    positive_labels = sum(int(item["positive_labels"]) for item in positive_reports)
    matched_positive_labels = sum(int(item["matched_labels"]) for item in positive_reports)
    missed_positive_labels = sum(int(item["missed_labels"]) for item in positive_reports)

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
        "failure_link_counts": counter_to_dict(failure_link_counts),
        "bottleneck": bottleneck,
        "diagnostics": diagnostics,
        "detector_false_positive_eval": {
            "report_count": len(fp_reports),
            "hard_negative_images": fp_images,
            "images_with_false_positives": fp_images_with_hits,
            "false_positive_detections": fp_detections,
            "reports": fp_reports,
        },
        "detector_positive_eval": {
            "report_count": len(positive_reports),
            "positive_labels": positive_labels,
            "matched_labels": matched_positive_labels,
            "missed_labels": missed_positive_labels,
            "label_recall": matched_positive_labels / positive_labels if positive_labels else None,
            "reports": positive_reports,
        },
        "morning_bar_moved": bool(diagnostics and fp_reports and positive_reports),
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
        f"- failure_links: `{report.get('failure_link_counts')}`",
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
        ]
    )
    positive_eval = report.get("detector_positive_eval") or {}
    lines.extend(
        [
            "## Detector positive eval",
            "",
            f"- positive_labels: {positive_eval.get('positive_labels')}",
            f"- matched_labels: {positive_eval.get('matched_labels')}",
            f"- missed_labels: {positive_eval.get('missed_labels')}",
            f"- label_recall: {positive_eval.get('label_recall')}",
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
                f"- failure_links: `{item.get('failure_link_counts')}`",
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
    parser.add_argument("--positive-report", action="append", dest="positive_reports", default=None, help="detector positive eval report JSON; may repeat")
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
    positive_report_paths = existing_paths(args.positive_reports or DEFAULT_POSITIVE_REPORTS)
    report = build_report(
        diagnostic_paths=diagnostic_paths,
        fp_report_paths=fp_report_paths,
        positive_report_paths=positive_report_paths,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({"output": str(args.output), "markdown_output": str(args.markdown_output), "verdict": report["verdict"], "accepted_count": report["accepted_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
