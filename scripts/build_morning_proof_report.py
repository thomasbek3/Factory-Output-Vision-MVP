#!/usr/bin/env python3
"""Build an end-to-end morning proof report from Factory Vision receipts.

The report intentionally separates accepted counts from suppressed/uncertain
tracks. It does not turn raw detections or unaudited counts into product counts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Optional

from app.services.perception_gate import GateTrackFeatures, evaluate_track

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


def worker_overlap_detail_for(row: dict[str, Any]) -> Optional[str]:
    """Classify worker/body-overlap failures into actionable perception buckets.

    A plain `worker_body_overlap` reason is safe but too blunt for the morning
    proof. The next engineering choice depends on whether the detector box is
    fully swallowed by the person box, whether there is possible protruding panel
    evidence, or whether a protruding track was actually allowed.
    """
    flags = {str(flag) for flag in as_list(row.get("flags"))}
    evidence = row.get("evidence") or {}
    reason = str(row.get("reason") or "unknown")
    decision = str(row.get("decision") or "unknown")
    person_overlap = float(evidence.get("person_overlap_ratio") or 0.0)
    outside_person = float(evidence.get("outside_person_ratio") or 0.0)

    if decision == "allow_source_token" and "source_token_allowed_by_protrusion" in flags:
        return "allowed_by_protrusion"
    if reason != "worker_body_overlap" and "high_person_overlap" not in flags:
        return None
    if "not_enough_object_outside_person" in flags or outside_person < 0.20:
        return "fully_entangled_with_worker"
    if "person_overlap_with_panel_protrusion" in flags or outside_person >= 0.35:
        return "protrusion_candidate_not_approved"
    if person_overlap > 0.70:
        return "high_overlap_partial_outside_worker"
    return "worker_overlap_unclear"


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


def person_panel_separation_path(receipt_path: str | None) -> str | None:
    if not receipt_path:
        return None
    path = Path(receipt_path)
    return str(path.with_name(path.stem + "-person-panel-separation.json"))


def load_person_panel_separation(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return load_json(Path(path))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def person_panel_separation_features(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    selected_frames = [item for item in as_list(payload.get("selected_frames")) if isinstance(item, dict)]
    total_candidate_frames = int(summary.get("separable_panel_candidate_frames") or 0)
    if not total_candidate_frames:
        total_candidate_frames = sum(1 for item in selected_frames if item.get("separation_decision") == "separable_panel_candidate")
    source_candidate_frames = sum(
        1
        for item in selected_frames
        if item.get("separation_decision") == "separable_panel_candidate" and str(item.get("zone") or "unknown") != "output"
    )
    return {
        "person_panel_recommendation": payload.get("recommendation"),
        "person_panel_total_candidate_frames": total_candidate_frames,
        "person_panel_source_candidate_frames": source_candidate_frames,
        "person_panel_max_visible_nonperson_ratio": float(summary.get("max_visible_nonperson_ratio") or 0.0),
        "person_panel_max_signal": float(summary.get("max_estimated_visible_signal") or 0.0),
        "person_panel_summary": summary if summary else None,
    }


def maybe_promote_worker_overlap_gate_row(row: dict[str, Any], receipt_path: str | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return row
    if str(row.get("decision") or "") != "reject" or str(row.get("reason") or "") != "worker_body_overlap":
        return row

    evidence = row.get("evidence") or {}
    separation_payload = load_person_panel_separation(person_panel_separation_path(receipt_path))
    separation = person_panel_separation_features(separation_payload)
    if separation.get("person_panel_recommendation") != "countable_panel_candidate":
        return row

    try:
        features = GateTrackFeatures(
            track_id=int(evidence.get("track_id") or row.get("track_id") or 0),
            source_frames=int(evidence.get("source_frames") or 0),
            output_frames=int(evidence.get("output_frames") or 0),
            zones_seen=[str(zone) for zone in as_list(evidence.get("zones_seen"))],
            first_zone=str(evidence.get("first_zone") or "unknown"),
            max_displacement=float(evidence.get("max_displacement") or 0.0),
            mean_internal_motion=float(evidence.get("mean_internal_motion") or 0.0),
            max_internal_motion=float(evidence.get("max_internal_motion") or 0.0),
            detections=int(evidence.get("detections") or 0),
            person_overlap_ratio=float(evidence.get("person_overlap_ratio") or 0.0),
            outside_person_ratio=float(evidence.get("outside_person_ratio") or 0.0),
            static_stack_overlap_ratio=float(evidence.get("static_stack_overlap_ratio") or 0.0),
            static_location_ratio=float(evidence.get("static_location_ratio") or 0.0),
            flow_coherence=float(evidence.get("flow_coherence") or 0.0),
            edge_like_ratio=float(evidence.get("edge_like_ratio") or 0.0),
            person_panel_recommendation=str(separation.get("person_panel_recommendation") or ""),
            person_panel_total_candidate_frames=int(separation.get("person_panel_total_candidate_frames") or 0),
            person_panel_source_candidate_frames=int(separation.get("person_panel_source_candidate_frames") or 0),
            person_panel_max_visible_nonperson_ratio=float(separation.get("person_panel_max_visible_nonperson_ratio") or 0.0),
            person_panel_max_signal=float(separation.get("person_panel_max_signal") or 0.0),
        )
    except (TypeError, ValueError):
        return row

    promoted = evaluate_track(features)
    if promoted.decision != "allow_source_token":
        return row
    return asdict(promoted)


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
        separation_path = person_panel_separation_path(receipt_path) if receipt_path else None
        separation_payload = load_person_panel_separation(separation_path)
        separation = person_panel_separation_features(separation_payload)
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
                "worker_overlap_detail": worker_overlap_detail_for(row),
                "receipt_json_path": receipt_path,
                "receipt_card_path": card_by_track.get(normalized_track_id) or receipt_assets.get("track_sheet_path"),
                "raw_crop_paths": as_list(receipt_assets.get("raw_crop_paths")),
                "person_panel_separation_path": separation_path if separation_payload else None,
                "person_panel_recommendation": separation.get("person_panel_recommendation"),
                "person_panel_summary": separation.get("person_panel_summary"),
            }
        )
    return rows


def summarize_diagnostic(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    gate_summary = payload.get("perception_gate_summary") or {}
    raw_gate_rows = [item for item in as_list(payload.get("perception_gate")) if isinstance(item, dict)]
    diagnosis_rows = as_list(payload.get("diagnosis"))
    receipt_paths = [str(p) for p in as_list(payload.get("track_receipts"))]
    receipt_by_track = {track_id: receipt for receipt in receipt_paths if (track_id := track_id_from_path(receipt)) is not None}
    gate_rows = [
        maybe_promote_worker_overlap_gate_row(row, receipt_by_track.get(int(row.get("track_id") or 0)))
        for row in raw_gate_rows
    ]

    decision_counts = Counter()
    reason_counts = Counter()
    for row in gate_rows or diagnosis_rows:
        decision = str(row.get("decision") or "unknown")
        reason = str(row.get("reason") or "unknown")
        decision_counts[decision] += 1
        reason_counts[reason] += 1

    if not gate_rows and gate_summary.get("decision_counts"):
        decision_counts = Counter({str(k): int(v) for k, v in gate_summary.get("decision_counts", {}).items()})
    if not gate_rows and gate_summary.get("reason_counts"):
        reason_counts = Counter({str(k): int(v) for k, v in gate_summary.get("reason_counts", {}).items()})

    if gate_rows:
        allowed_tracks = [
            int(row.get("track_id") or 0)
            for row in gate_rows
            if str(row.get("decision") or "") == "allow_source_token"
        ]
    else:
        allowed_tracks = [int(track_id) for track_id in as_list(gate_summary.get("allowed_source_token_tracks"))]
    accepted_count = len(allowed_tracks)
    track_count = int(gate_summary.get("track_count") or len(gate_rows) or len(diagnosis_rows))
    suppressed_count = int(decision_counts.get("reject", 0))
    uncertain_count = int(decision_counts.get("uncertain", 0))

    card_paths = [str(p) for p in as_list(payload.get("track_receipt_cards"))]
    track_receipts = build_track_receipts(gate_rows, receipt_paths, card_paths)
    failure_link_counts = Counter(str(item.get("failure_link") or "unknown") for item in track_receipts)
    worker_overlap_detail_counts = Counter(
        str(item.get("worker_overlap_detail")) for item in track_receipts if item.get("worker_overlap_detail")
    )

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
        "worker_overlap_detail_counts": counter_to_dict(worker_overlap_detail_counts),
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


def report_key(report: dict[str, Any]) -> tuple[str, Optional[float]]:
    return (str(report.get("model_path") or "unknown"), report.get("confidence"))


def select_detector_model(fp_reports: list[dict[str, Any]], positive_reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the safest currently evaluated detector/threshold pair.

    The proof report needs to say more than "we tested some models". For the
    current source-token pipeline, a detector candidate is usable only if it does
    not create hard-negative false positives; among safe candidates, prefer the
    highest positive-label recall. This selection is advisory evidence for the
    proof loop, not permission for raw detections to count.
    """
    fp_by_key = {report_key(report): report for report in fp_reports}
    candidates: list[dict[str, Any]] = []
    for positive in positive_reports:
        key = report_key(positive)
        fp = fp_by_key.get(key)
        if not fp:
            continue
        fp_detections = int(fp.get("false_positive_detections") or 0)
        fp_images_with_hits = int(fp.get("images_with_false_positives") or 0)
        positive_labels = int(positive.get("positive_labels") or 0)
        matched_labels = int(positive.get("matched_labels") or 0)
        label_recall = positive.get("label_recall")
        if label_recall is None:
            label_recall = matched_labels / positive_labels if positive_labels else 0.0
        candidates.append(
            {
                "model_path": positive.get("model_path"),
                "confidence": positive.get("confidence"),
                "iou_threshold": positive.get("iou_threshold"),
                "label_recall": label_recall,
                "positive_labels": positive_labels,
                "matched_labels": matched_labels,
                "missed_labels": int(positive.get("missed_labels") or max(0, positive_labels - matched_labels)),
                "hard_negative_images": int(fp.get("hard_negative_images") or 0),
                "false_positive_detections": fp_detections,
                "images_with_false_positives": fp_images_with_hits,
                "false_positive_image_rate": fp.get("false_positive_image_rate"),
                "positive_report_path": positive.get("report_path"),
                "false_positive_report_path": fp.get("report_path"),
                "safe_on_hard_negatives": fp_detections == 0 and fp_images_with_hits == 0,
            }
        )

    safe_candidates = [candidate for candidate in candidates if candidate["safe_on_hard_negatives"]]
    selection_pool = safe_candidates or candidates
    selected = None
    if selection_pool:
        selected = max(
            selection_pool,
            key=lambda candidate: (
                1 if candidate["safe_on_hard_negatives"] else 0,
                float(candidate.get("label_recall") or 0.0),
                int(candidate.get("matched_labels") or 0),
                float(candidate.get("confidence") or 0.0),
                str(candidate.get("model_path") or ""),
            ),
        )

    return {
        "selection_rule": "zero hard-negative false positives first, then highest positive-label recall",
        "candidate_count": len(candidates),
        "safe_candidate_count": len(safe_candidates),
        "selected": selected,
        "candidates": sorted(
            candidates,
            key=lambda candidate: (
                str(candidate.get("model_path") or ""),
                float(candidate.get("confidence") or 0.0),
            ),
        ),
    }


def classify_proof_readiness(
    *,
    accepted_count: int,
    suppressed_count: int,
    uncertain_count: int,
    bottleneck: str,
    detector_selection: dict[str, Any],
    failure_link_counts: Counter[str],
) -> dict[str, Any]:
    """Turn the morning evidence into a product-facing readiness verdict.

    The report already has the raw ingredients. This compact classifier states
    whether the current failure is detector coverage, detector hard-negative
    safety, or source-token gate evidence. That keeps the morning artifact from
    saying only "count is zero" when the positive detector eval is actually fine.
    """
    selected = detector_selection.get("selected") or {}
    selected_recall = float(selected.get("label_recall") or 0.0)
    selected_fp_detections = int(selected.get("false_positive_detections") or 0)
    selected_fp_images = int(selected.get("images_with_false_positives") or 0)
    safe_candidate_count = int(detector_selection.get("safe_candidate_count") or 0)
    has_safe_selected_detector = bool(selected) and selected_fp_detections == 0 and selected_fp_images == 0
    selected_detector_positive_pass = bool(selected) and selected_recall >= 0.80
    dominant_failure_link = "none"
    if failure_link_counts:
        dominant_failure_link = failure_link_counts.most_common(1)[0][0]

    if accepted_count > 0:
        status = "trusted_positive_count_available"
        next_action = "Audit accepted count receipts on more representative windows before broadening deployment."
    elif not selected:
        status = "missing_paired_detector_eval"
        next_action = "Run paired positive and hard-negative detector eval before judging the count path."
    elif not has_safe_selected_detector:
        status = "detector_not_safe_on_hard_negatives"
        next_action = "Improve or retrain the detector before allowing it into source-token clip eval."
    elif not selected_detector_positive_pass:
        status = "detector_positive_recall_too_low"
        next_action = "Improve active-panel recall on reviewed positives before chasing count-state behavior."
    elif bottleneck == "perception_gate_worker_body_overlap":
        status = "detector_seed_passes_but_worker_overlap_blocks_source_tokens"
        next_action = "Add crop/shape/person-mask or pose-aware evidence for worker-entangled tracks before minting source tokens."
    else:
        status = "source_token_evidence_incomplete_after_detector_pass"
        next_action = "Inspect the dominant failure link and improve event evidence before loosening count logic."

    return {
        "status": status,
        "dominant_failure_link": dominant_failure_link,
        "selected_detector_positive_pass": selected_detector_positive_pass,
        "has_safe_selected_detector": has_safe_selected_detector,
        "selected_detector_label_recall": selected_recall if selected else None,
        "selected_detector_false_positive_detections": selected_fp_detections if selected else None,
        "safe_detector_candidates": safe_candidate_count,
        "accepted_count": accepted_count,
        "suppressed_count": suppressed_count,
        "uncertain_count": uncertain_count,
        "next_action": next_action,
    }


def build_decision_receipt_index(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a compact index from every gate decision to its review assets.

    The full diagnostic summaries are intentionally detailed, but the morning
    proof report also needs a top-level receipt index that answers, at a glance:
    which tracks counted, which were suppressed, which are uncertain, and where
    the corresponding JSON/card/crop evidence lives. This is still evidence
    bookkeeping only; it does not let raw detections become counts.
    """
    groups: dict[str, list[dict[str, Any]]] = {
        "accepted": [],
        "suppressed": [],
        "uncertain": [],
    }
    missing_review_assets: Counter[str] = Counter()

    for diagnostic in diagnostics:
        diagnostic_path = diagnostic.get("diagnostic_path")
        window = diagnostic.get("window") or {}
        for receipt in as_list(diagnostic.get("track_decision_receipts")):
            if not isinstance(receipt, dict):
                continue
            decision = str(receipt.get("decision") or "unknown")
            if decision == "allow_source_token":
                bucket = "accepted"
            elif decision == "uncertain":
                bucket = "uncertain"
            else:
                bucket = "suppressed"

            receipt_json_path = receipt.get("receipt_json_path")
            receipt_card_path = receipt.get("receipt_card_path")
            raw_crop_paths = as_list(receipt.get("raw_crop_paths"))
            if not receipt_json_path:
                missing_review_assets["receipt_json_path"] += 1
            if not receipt_card_path:
                missing_review_assets["receipt_card_path"] += 1
            if not raw_crop_paths:
                missing_review_assets["raw_crop_paths"] += 1

            groups[bucket].append(
                {
                    "diagnostic_path": diagnostic_path,
                    "window": window,
                    "track_id": receipt.get("track_id"),
                    "decision": decision,
                    "reason": receipt.get("reason") or "unknown",
                    "failure_link": receipt.get("failure_link") or "unknown",
                    "worker_overlap_detail": receipt.get("worker_overlap_detail"),
                    "evidence_summary": receipt.get("evidence_summary") or {},
                    "receipt_json_path": receipt_json_path,
                    "receipt_card_path": receipt_card_path,
                    "raw_crop_paths": raw_crop_paths,
                    "person_panel_separation_path": receipt.get("person_panel_separation_path"),
                    "person_panel_recommendation": receipt.get("person_panel_recommendation"),
                    "person_panel_summary": receipt.get("person_panel_summary"),
                }
            )

    return {
        "schema_version": "factory-proof-decision-receipt-index-v1",
        "accepted": groups["accepted"],
        "suppressed": groups["suppressed"],
        "uncertain": groups["uncertain"],
        "counts": {key: len(value) for key, value in groups.items()},
        "missing_review_asset_counts": counter_to_dict(missing_review_assets),
    }


def build_source_token_work_queue(decision_receipt_index: dict[str, Any]) -> dict[str, Any]:
    """Rank the next evidence tasks for converting abstention into trusted counts.

    This is deliberately not a count path. It is a small operational queue built
    from suppressed/uncertain receipts so the next slice attacks the precise
    failed source-token link instead of rummaging through montages by hand.
    """
    priority_by_detail = {
        "protrusion_candidate_not_approved": 10,
        "high_overlap_partial_outside_worker": 8,
        "worker_overlap_unclear": 6,
        "fully_entangled_with_worker": 4,
    }
    action_by_detail = {
        "protrusion_candidate_not_approved": "add crop/shape/person-mask evidence; this may become a true carried-panel source token if the crop proves panel protrusion rather than arm/torso motion",
        "high_overlap_partial_outside_worker": "inspect raw crops and add finer person/part separation before allowing source tokens",
        "worker_overlap_unclear": "inspect receipt card/crops and classify whether the box is panel, worker, or static stack edge",
        "fully_entangled_with_worker": "needs person-mask/pose or better active-panel crop evidence; do not count from the current box alone",
    }
    requirements_by_detail = {
        "protrusion_candidate_not_approved": [
            "panel-shaped pixels protrude outside the worker silhouette/body box in multiple consecutive frames",
            "protruding region moves coherently with the candidate track rather than the torso/arm boundary",
            "candidate has source-zone evidence and later output-zone/settle evidence in the same receipt window",
        ],
        "high_overlap_partial_outside_worker": [
            "raw crops show a discrete wire-mesh/panel edge separate from worker clothing or arms",
            "outside-person pixels are large enough and stable enough to be a physical panel, not detector jitter",
            "source and output evidence both survive after person/part separation",
        ],
        "worker_overlap_unclear": [
            "receipt card/crops classify the box as active_panel rather than worker/body/background edge",
            "motion evidence follows the panel-sized object, not whole-worker motion",
            "static-stack overlap is low or the track visibly separates from the resident stack",
        ],
        "fully_entangled_with_worker": [
            "person-mask or pose-aware crop evidence exposes a panel-like region inside the coarse person box",
            "panel evidence persists for several frames instead of appearing as a single noisy detector box",
            "the track can be separated from torso/arm motion before a source token is allowed",
        ],
    }
    audit_question_by_detail = {
        "protrusion_candidate_not_approved": "Does the protruding crop region look like a carried wire-mesh panel, and does it remain the same object from source toward output?",
        "high_overlap_partial_outside_worker": "Is the partially outside-person evidence a real panel edge/sheet, or just worker limbs/clothing/background?",
        "worker_overlap_unclear": "What physical object does this receipt actually show: active panel, worker/body, static stack, or background edge?",
        "fully_entangled_with_worker": "Can any panel-shaped evidence be separated from the worker body, or should this remain suppressed?",
    }
    rows: list[dict[str, Any]] = []
    for bucket in ["uncertain", "suppressed"]:
        for row in as_list(decision_receipt_index.get(bucket)):
            if not isinstance(row, dict):
                continue
            if row.get("failure_link") != "worker_body_overlap":
                continue
            detail = row.get("worker_overlap_detail") or "worker_overlap_unclear"
            evidence = row.get("evidence_summary") or {}
            outside_person = float(evidence.get("outside_person_ratio") or 0.0)
            person_overlap = float(evidence.get("person_overlap_ratio") or 0.0)
            priority = priority_by_detail.get(str(detail), 5) + outside_person
            rows.append(
                {
                    "priority": round(priority, 3),
                    "bucket": bucket,
                    "diagnostic_path": row.get("diagnostic_path"),
                    "window": row.get("window"),
                    "track_id": row.get("track_id"),
                    "reason": row.get("reason") or "unknown",
                    "worker_overlap_detail": detail,
                    "person_overlap_ratio": person_overlap,
                    "outside_person_ratio": outside_person,
                    "recommended_action": action_by_detail.get(str(detail), action_by_detail["worker_overlap_unclear"]),
                    "evidence_requirements_to_allow_source_token": requirements_by_detail.get(str(detail), requirements_by_detail["worker_overlap_unclear"]),
                    "audit_question": audit_question_by_detail.get(str(detail), audit_question_by_detail["worker_overlap_unclear"]),
                    "receipt_json_path": row.get("receipt_json_path"),
                    "receipt_card_path": row.get("receipt_card_path"),
                    "raw_crop_paths": as_list(row.get("raw_crop_paths")),
                }
            )

    rows.sort(key=lambda item: (-float(item.get("priority") or 0.0), str(item.get("diagnostic_path") or ""), int(item.get("track_id") or 0)))
    detail_counts = Counter(str(row.get("worker_overlap_detail") or "unknown") for row in rows)
    return {
        "schema_version": "factory-source-token-work-queue-v1",
        "purpose": "actionable receipt queue for worker-entangled tracks; not a count source",
        "item_count": len(rows),
        "worker_overlap_detail_counts": counter_to_dict(detail_counts),
        "top_items": rows[:10],
    }


def build_evidence_gap_matrix(decision_receipt_index: dict[str, Any]) -> dict[str, Any]:
    """Summarize which physical proof link blocked each non-counted receipt.

    A zero accepted count is only useful if the report says *why* it is zero.
    This matrix turns the suppressed/uncertain receipt index into product-level
    evidence links: worker/part separation, output settle, static-stack rejection,
    and receipt completeness. It remains reporting only; it cannot approve a count.
    """
    gap_by_failure_link = {
        "worker_body_overlap": {
            "evidence_link": "panel_vs_worker_separation",
            "description": "prove the candidate is a discrete active panel rather than worker torso/arms/clothing/background motion",
            "next_evidence": "crop/shape/person-mask or pose-aware separation on the linked receipt crops/cards",
        },
        "missing_output_settle": {
            "evidence_link": "output_entry_and_settle",
            "description": "prove the same source-origin panel entered/settled in output or disappeared into the output stack",
            "next_evidence": "denser before/during/after frames or longer diagnostic window around the receipt",
        },
        "incomplete_source_to_output_path": {
            "evidence_link": "continuous_source_to_output_path",
            "description": "prove the track has a credible source-to-output path rather than partial motion evidence",
            "next_evidence": "tracker continuity, occlusion TTL/relink evidence, and before/after frames",
        },
        "static_stack_or_resident_output": {
            "evidence_link": "non_resident_active_panel",
            "description": "prove the candidate is not a resident output stack edge or repositioned output panel",
            "next_evidence": "resident baseline/static-stack anchors and raw crops showing separation from the stack",
        },
        "insufficient_active_panel_evidence": {
            "evidence_link": "active_panel_visual_evidence",
            "description": "prove the detector crop contains an active panel with coherent motion",
            "next_evidence": "hard-negative harvesting, optical-flow coherence, and crop-level active-panel review",
        },
        "unclassified_evidence_failure": {
            "evidence_link": "unclassified_evidence_failure",
            "description": "classify the physical evidence failure before changing count logic",
            "next_evidence": "inspect the linked receipt card/crops and add a more specific failure link",
        },
    }
    rows_by_link: dict[str, list[dict[str, Any]]] = {}
    bucket_counts_by_link: dict[str, Counter[str]] = {}
    accepted_rows = as_list(decision_receipt_index.get("accepted"))

    for bucket in ["suppressed", "uncertain"]:
        for row in as_list(decision_receipt_index.get(bucket)):
            if not isinstance(row, dict):
                continue
            failure_link = str(row.get("failure_link") or "unclassified_evidence_failure")
            spec = gap_by_failure_link.get(failure_link, gap_by_failure_link["unclassified_evidence_failure"])
            evidence_link = spec["evidence_link"]
            bucket_counts_by_link.setdefault(evidence_link, Counter())[bucket] += 1
            rows_by_link.setdefault(evidence_link, []).append(
                {
                    "bucket": bucket,
                    "diagnostic_path": row.get("diagnostic_path"),
                    "track_id": row.get("track_id"),
                    "reason": row.get("reason") or "unknown",
                    "failure_link": failure_link,
                    "worker_overlap_detail": row.get("worker_overlap_detail"),
                    "receipt_json_path": row.get("receipt_json_path"),
                    "receipt_card_path": row.get("receipt_card_path"),
                    "raw_crop_paths": as_list(row.get("raw_crop_paths")),
                }
            )

    evidence_links: list[dict[str, Any]] = []
    for evidence_link, rows in rows_by_link.items():
        spec = next(
            (item for item in gap_by_failure_link.values() if item["evidence_link"] == evidence_link),
            gap_by_failure_link["unclassified_evidence_failure"],
        )
        counts = bucket_counts_by_link.get(evidence_link, Counter())
        evidence_links.append(
            {
                "evidence_link": evidence_link,
                "blocked_count": len(rows),
                "bucket_counts": counter_to_dict(counts),
                "description": spec["description"],
                "next_evidence": spec["next_evidence"],
                "sample_receipts": rows[:3],
            }
        )

    evidence_links.sort(key=lambda item: (-int(item.get("blocked_count") or 0), str(item.get("evidence_link") or "")))
    return {
        "schema_version": "factory-proof-evidence-gap-matrix-v1",
        "purpose": "explain which physical evidence link blocks trusted source-token counts; not a count source",
        "accepted_receipts": len(accepted_rows),
        "blocked_receipts": sum(int(item.get("blocked_count") or 0) for item in evidence_links),
        "dominant_gap": evidence_links[0]["evidence_link"] if evidence_links else "none",
        "why_accepted_count_is_zero": "no perception-gate-approved source-token receipts" if not accepted_rows else None,
        "missing_review_asset_counts": decision_receipt_index.get("missing_review_asset_counts") or {},
        "evidence_links": evidence_links,
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
    worker_overlap_detail_counts: Counter[str] = Counter()
    for item in diagnostics:
        reason_counts.update({str(k): int(v) for k, v in item.get("reason_counts", {}).items()})
        decision_counts.update({str(k): int(v) for k, v in item.get("decision_counts", {}).items()})
        failure_link_counts.update({str(k): int(v) for k, v in item.get("failure_link_counts", {}).items()})
        worker_overlap_detail_counts.update({str(k): int(v) for k, v in item.get("worker_overlap_detail_counts", {}).items()})

    fp_images = sum(int(item["hard_negative_images"]) for item in fp_reports)
    fp_detections = sum(int(item["false_positive_detections"]) for item in fp_reports)
    fp_images_with_hits = sum(int(item["images_with_false_positives"]) for item in fp_reports)
    positive_labels = sum(int(item["positive_labels"]) for item in positive_reports)
    matched_positive_labels = sum(int(item["matched_labels"]) for item in positive_reports)
    missed_positive_labels = sum(int(item["missed_labels"]) for item in positive_reports)
    detector_selection = select_detector_model(fp_reports, positive_reports)

    bottleneck = "none"
    if accepted_count == 0:
        if reason_counts.get("worker_body_overlap", 0):
            bottleneck = "perception_gate_worker_body_overlap"
        elif reason_counts.get("source_without_output_settle", 0):
            bottleneck = "source_without_output_settle"
        else:
            bottleneck = "no_gate_approved_source_tokens"

    verdict = "accepted_positive_count_available" if accepted_count else "auditable_abstention_no_trusted_positive"
    proof_readiness = classify_proof_readiness(
        accepted_count=accepted_count,
        suppressed_count=suppressed_count,
        uncertain_count=uncertain_count,
        bottleneck=bottleneck,
        detector_selection=detector_selection,
        failure_link_counts=failure_link_counts,
    )
    decision_receipt_index = build_decision_receipt_index(diagnostics)
    source_token_work_queue = build_source_token_work_queue(decision_receipt_index)
    evidence_gap_matrix = build_evidence_gap_matrix(decision_receipt_index)

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
        "worker_overlap_detail_counts": counter_to_dict(worker_overlap_detail_counts),
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
        "detector_selection": detector_selection,
        "proof_readiness": proof_readiness,
        "decision_receipt_index": decision_receipt_index,
        "source_token_work_queue": source_token_work_queue,
        "evidence_gap_matrix": evidence_gap_matrix,
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
        f"- worker_overlap_details: `{report.get('worker_overlap_detail_counts')}`",
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
    detector_selection = report.get("detector_selection") or {}
    selected_detector = detector_selection.get("selected") or {}
    proof_readiness = report.get("proof_readiness") or {}
    lines.extend(
        [
            "## Detector positive eval",
            "",
            f"- positive_labels: {positive_eval.get('positive_labels')}",
            f"- matched_labels: {positive_eval.get('matched_labels')}",
            f"- missed_labels: {positive_eval.get('missed_labels')}",
            f"- label_recall: {positive_eval.get('label_recall')}",
            "",
            "## Detector selection",
            "",
            f"- selection_rule: {detector_selection.get('selection_rule')}",
            f"- candidates: {detector_selection.get('candidate_count')}; safe_on_hard_negatives: {detector_selection.get('safe_candidate_count')}",
            f"- selected_model: `{selected_detector.get('model_path')}`",
            f"- selected_confidence: {selected_detector.get('confidence')}",
            f"- selected_label_recall: {selected_detector.get('label_recall')}",
            f"- selected_false_positive_detections: {selected_detector.get('false_positive_detections')}",
            "",
            "## Proof readiness",
            "",
            f"- status: `{proof_readiness.get('status')}`",
            f"- dominant_failure_link: `{proof_readiness.get('dominant_failure_link')}`",
            f"- selected_detector_positive_pass: {proof_readiness.get('selected_detector_positive_pass')}",
            f"- has_safe_selected_detector: {proof_readiness.get('has_safe_selected_detector')}",
            f"- next_action: {proof_readiness.get('next_action')}",
            "",
            "## Decision receipt index",
            "",
            f"- counts: `{(report.get('decision_receipt_index') or {}).get('counts')}`",
            f"- missing_review_asset_counts: `{(report.get('decision_receipt_index') or {}).get('missing_review_asset_counts')}`",
            "",
            "## Source-token work queue",
            "",
            f"- purpose: {(report.get('source_token_work_queue') or {}).get('purpose')}",
            f"- item_count: {(report.get('source_token_work_queue') or {}).get('item_count')}",
            f"- worker_overlap_detail_counts: `{(report.get('source_token_work_queue') or {}).get('worker_overlap_detail_counts')}`",
            "",
            "## Representative diagnostic windows",
            "",
        ]
    )
    work_queue = report.get("source_token_work_queue") or {}
    work_items = as_list(work_queue.get("top_items"))
    evidence_gap_matrix = report.get("evidence_gap_matrix") or {}
    evidence_links = as_list(evidence_gap_matrix.get("evidence_links"))
    if evidence_links:
        lines.extend(
            [
                "## Evidence gap matrix",
                "",
                f"- purpose: {evidence_gap_matrix.get('purpose')}",
                f"- dominant_gap: `{evidence_gap_matrix.get('dominant_gap')}`",
                f"- why_accepted_count_is_zero: {evidence_gap_matrix.get('why_accepted_count_is_zero')}",
                f"- missing_review_asset_counts: `{evidence_gap_matrix.get('missing_review_asset_counts')}`",
                "",
            ]
        )
        for gap in evidence_links[:5]:
            lines.extend(
                [
                    f"- `{gap.get('evidence_link')}` blocked {gap.get('blocked_count')} receipts; buckets: `{gap.get('bucket_counts')}`",
                    f"  - description: {gap.get('description')}",
                    f"  - next_evidence: {gap.get('next_evidence')}",
                    f"  - sample_receipts: `{gap.get('sample_receipts')}`",
                ]
            )
        lines.append("")
    if work_items:
        lines.extend(["### Highest-priority worker-entangled receipts", ""])
        for row in work_items[:5]:
            lines.extend(
                [
                    f"- track {row.get('track_id')} priority {row.get('priority')} in `{row.get('diagnostic_path')}`: `{row.get('worker_overlap_detail')}`",
                    f"  - action: {row.get('recommended_action')}",
                    f"  - audit_question: {row.get('audit_question')}",
                    f"  - evidence_required: `{row.get('evidence_requirements_to_allow_source_token')}`",
                    f"  - person_overlap/outside_person: {row.get('person_overlap_ratio')} / {row.get('outside_person_ratio')}",
                    f"  - receipt_json: `{row.get('receipt_json_path')}`",
                    f"  - receipt_card: `{row.get('receipt_card_path')}`",
                    f"  - raw_crops: `{row.get('raw_crop_paths')}`",
                ]
            )
        lines.append("")
    decision_index = report.get("decision_receipt_index") or {}
    for bucket in ["accepted", "suppressed", "uncertain"]:
        rows = as_list(decision_index.get(bucket))
        if not rows:
            continue
        lines.extend([f"### {bucket.title()} receipt samples", ""])
        for row in rows[:5]:
            lines.extend(
                [
                    f"- track {row.get('track_id')} in `{row.get('diagnostic_path')}`: `{row.get('reason')}` / `{row.get('failure_link')}`",
                    f"  - receipt_json: `{row.get('receipt_json_path')}`",
                    f"  - receipt_card: `{row.get('receipt_card_path')}`",
                    f"  - raw_crops: `{row.get('raw_crop_paths')}`",
                ]
            )
        lines.append("")
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
                f"- worker_overlap_details: `{item.get('worker_overlap_detail_counts')}`",
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
