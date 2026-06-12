from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = "factory-vision-teacher-grade-vs-truth-v1"
GENERATED_BY = "teacher_truth_grader_v1"
CLAIM_BOUNDARY = "teacher_grading_diagnostic_only_not_validation_proof"


def grade_teacher_labels_against_truth(
    *,
    teacher_labels_path: Path,
    truth_ledger_path: Path,
    tolerances_sec: Sequence[float] = (2.0, 5.0, 10.0),
    packet_manifest_path: Path | None = None,
    segment_manifest_path: Path | None = None,
    segment_offset_sec: float = 0.0,
    dedupe_window_sec: float = 2.0,
) -> dict[str, Any]:
    labels_payload = json.loads(teacher_labels_path.read_text(encoding="utf-8"))
    truth_payload = json.loads(truth_ledger_path.read_text(encoding="utf-8"))

    truth_events = sorted(
        (
            {
                "truth_event_id": event.get("truth_event_id"),
                "event_ts": float(event.get("event_ts") or 0.0),
            }
            for event in truth_payload.get("events") or []
        ),
        key=lambda event: event["event_ts"],
    )

    packet_segments = _packet_segment_index(packet_manifest_path)
    segment_offsets = _segment_offsets_from_manifest(segment_manifest_path)

    labels = list(labels_payload.get("labels") or [])
    histogram = {"assert_completed": 0, "refute_completed": 0, "unclear": 0, "provider_error": 0}
    predictions: list[dict[str, Any]] = []
    unmappable_predictions: list[dict[str, Any]] = []
    for label in labels:
        decision = str(label.get("verification_decision") or "unclear")
        if decision not in histogram:
            decision = "unclear"
        histogram[decision] += 1
        if str(label.get("rationale") or "").startswith("provider_error:"):
            histogram["provider_error"] += 1
        if decision != "assert_completed" or label.get("suggested_event_ts_sec") is None:
            continue
        mapped = _map_to_source_timeline(
            label,
            packet_segments=packet_segments,
            segment_offsets=segment_offsets,
            global_offset_sec=segment_offset_sec,
        )
        if mapped is None:
            unmappable_predictions.append({"packet_id": label.get("packet_id"), "reason": "unknown_segment_offset"})
            continue
        predictions.append(
            {
                "packet_id": label.get("packet_id"),
                "label_id": label.get("label_id"),
                "event_ts": mapped,
                "confidence_tier": label.get("confidence_tier"),
            }
        )
    predictions.sort(key=lambda row: (row["event_ts"], str(row["packet_id"])))
    deduped, duplicate_merged_count = _dedupe_predictions(predictions, dedupe_window_sec)

    per_tolerance: dict[str, Any] = {}
    for tolerance in tolerances_sec:
        matched, missing_truth, unexpected = _match_predictions_to_truth(truth_events, deduped, float(tolerance))
        timing_errors = [abs(row["delta_sec"]) for row in matched]
        true_positives = len(matched)
        false_positives = len(unexpected)
        false_negatives = len(missing_truth)
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else None
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else None
        f1 = None
        if precision is not None and recall is not None and (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)
        per_tolerance[f"{float(tolerance):g}"] = {
            "tolerance_sec": float(tolerance),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": _rounded(precision),
            "recall": _rounded(recall),
            "f1": _rounded(f1),
            "mean_abs_timing_error_sec": _rounded(statistics.fmean(timing_errors)) if timing_errors else None,
            "median_abs_timing_error_sec": _rounded(statistics.median(timing_errors)) if timing_errors else None,
            "max_abs_timing_error_sec": _rounded(max(timing_errors)) if timing_errors else None,
            "matched": matched,
            "missing_truth": missing_truth,
            "unexpected_predictions": unexpected,
        }

    diagnostics = _missed_truth_diagnostics(
        per_tolerance=per_tolerance,
        labels=labels,
        packet_segments=packet_segments,
        segment_offsets=segment_offsets,
        global_offset_sec=segment_offset_sec,
    )

    provider = labels_payload.get("provider") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "claim_boundary": CLAIM_BOUNDARY,
        "refuses_validation_truth": True,
        "teacher_labels_path": str(teacher_labels_path),
        "truth_ledger_path": str(truth_ledger_path),
        "truth_ledger_schema_version": truth_payload.get("schema_version"),
        "expected_human_total": truth_payload.get("expected_human_total"),
        "provider": {
            "name": provider.get("name"),
            "mode": provider.get("mode"),
            "model": provider.get("model"),
            "prompt_version": provider.get("prompt_version"),
        },
        "label_count": len(labels),
        "decision_histogram": histogram,
        "truth_event_count": len(truth_events),
        "prediction_count": len(predictions),
        "deduped_prediction_count": len(deduped),
        "duplicate_merged_count": duplicate_merged_count,
        "unmappable_predictions": unmappable_predictions,
        "dedupe_window_sec": float(dedupe_window_sec),
        "global_segment_offset_sec": float(segment_offset_sec),
        "segment_offsets": segment_offsets,
        "per_tolerance": per_tolerance,
        "diagnostics": diagnostics,
    }


def write_teacher_grade_report(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _match_predictions_to_truth(
    truth_events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    tolerance_sec: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """One-to-one monotonic two-pointer matching (same semantics as the app-vs-truth comparer)."""
    truth_index = 0
    prediction_index = 0
    matched: list[dict[str, Any]] = []
    missing_truth: list[dict[str, Any]] = []
    unexpected: list[dict[str, Any]] = []

    while truth_index < len(truth_events) and prediction_index < len(predictions):
        truth_event = truth_events[truth_index]
        prediction = predictions[prediction_index]
        delta = prediction["event_ts"] - truth_event["event_ts"]
        if abs(delta) <= tolerance_sec:
            matched.append(
                {
                    "truth_event_id": truth_event.get("truth_event_id"),
                    "truth_event_ts": truth_event["event_ts"],
                    "predicted_event_ts": prediction["event_ts"],
                    "delta_sec": round(delta, 3),
                    "packet_id": prediction.get("packet_id"),
                }
            )
            truth_index += 1
            prediction_index += 1
            continue
        if prediction["event_ts"] < truth_event["event_ts"]:
            unexpected.append(
                {
                    "predicted_event_ts": prediction["event_ts"],
                    "packet_id": prediction.get("packet_id"),
                }
            )
            prediction_index += 1
            continue
        missing_truth.append(
            {
                "truth_event_id": truth_event.get("truth_event_id"),
                "event_ts": truth_event["event_ts"],
            }
        )
        truth_index += 1

    for truth_event in truth_events[truth_index:]:
        missing_truth.append(
            {
                "truth_event_id": truth_event.get("truth_event_id"),
                "event_ts": truth_event["event_ts"],
            }
        )
    for prediction in predictions[prediction_index:]:
        unexpected.append(
            {
                "predicted_event_ts": prediction["event_ts"],
                "packet_id": prediction.get("packet_id"),
            }
        )
    return matched, missing_truth, unexpected


def _dedupe_predictions(
    predictions: list[dict[str, Any]],
    dedupe_window_sec: float,
) -> tuple[list[dict[str, Any]], int]:
    """Merge asserts within the window; adjacent proposal windows overlap by design."""
    if dedupe_window_sec <= 0 or not predictions:
        return list(predictions), 0
    deduped: list[dict[str, Any]] = []
    merged = 0
    for prediction in predictions:
        if deduped and (prediction["event_ts"] - deduped[-1]["event_ts"]) <= dedupe_window_sec:
            merged += 1
            continue
        deduped.append(prediction)
    return deduped, merged


def _packet_segment_index(packet_manifest_path: Path | None) -> dict[str, dict[str, Any]]:
    if packet_manifest_path is None:
        return {}
    manifest = json.loads(packet_manifest_path.read_text(encoding="utf-8"))
    index: dict[str, dict[str, Any]] = {}
    for row in manifest.get("packets") or []:
        packet_path = Path(str(row.get("packet_manifest_path")))
        if not packet_path.exists():
            continue
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        index[str(packet.get("packet_id"))] = {
            "segment_id": packet.get("segment_id"),
            "window": packet.get("window") or {},
        }
    return index


def _segment_offsets_from_manifest(segment_manifest_path: Path | None) -> dict[str, float] | None:
    """Cumulative start offsets of sequential file-backed segments within the source video."""
    if segment_manifest_path is None:
        return None
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    # Sort by path, not start_wall_ts: the ffmpeg segment index in the filename is the true
    # source order. File-replay recordings transcode faster than realtime, so wall timestamps
    # of different segments can be identical or even inverted.
    segments = sorted(manifest.get("segments") or [], key=lambda row: str(row.get("path")))
    offsets: dict[str, float] = {}
    cumulative = 0.0
    for segment in segments:
        segment_id = str(segment.get("segment_id"))
        offsets[segment_id] = round(cumulative, 3)
        duration = segment.get("duration_sec")
        cumulative += float(duration) if duration is not None else 0.0
    return offsets


def _map_to_source_timeline(
    label: dict[str, Any],
    *,
    packet_segments: dict[str, dict[str, Any]],
    segment_offsets: dict[str, float] | None,
    global_offset_sec: float,
) -> float | None:
    timestamp = float(label.get("suggested_event_ts_sec") or 0.0)
    if segment_offsets is None:
        return round(timestamp + global_offset_sec, 3)
    packet_info = packet_segments.get(str(label.get("packet_id")))
    segment_id = str((packet_info or {}).get("segment_id"))
    if packet_info is None or segment_id not in segment_offsets:
        return None
    return round(timestamp + segment_offsets[segment_id] + global_offset_sec, 3)


def _missed_truth_diagnostics(
    *,
    per_tolerance: dict[str, Any],
    labels: list[dict[str, Any]],
    packet_segments: dict[str, dict[str, Any]],
    segment_offsets: dict[str, float] | None,
    global_offset_sec: float,
) -> dict[str, Any]:
    """For each missed truth event (at the loosest tolerance), find the nearest covering packet and its decision."""
    if not per_tolerance:
        return {"missed_truth_events": []}
    loosest_key = max(per_tolerance, key=lambda key: per_tolerance[key]["tolerance_sec"])
    missed = per_tolerance[loosest_key]["missing_truth"]

    packet_windows: list[dict[str, Any]] = []
    for label in labels:
        packet_id = str(label.get("packet_id"))
        packet_info = packet_segments.get(packet_id)
        if packet_info is None:
            continue
        window = packet_info.get("window") or {}
        start = window.get("start_offset_sec")
        end = window.get("end_offset_sec")
        if start is None or end is None:
            continue
        offset = global_offset_sec
        if segment_offsets is not None:
            segment_id = str(packet_info.get("segment_id"))
            if segment_id not in segment_offsets:
                continue
            offset += segment_offsets[segment_id]
        packet_windows.append(
            {
                "packet_id": packet_id,
                "decision": label.get("verification_decision"),
                "window_start_sec": round(float(start) + offset, 3),
                "window_end_sec": round(float(end) + offset, 3),
            }
        )

    diagnostics_rows = []
    for miss in missed:
        truth_ts = float(miss["event_ts"])
        covering = [row for row in packet_windows if row["window_start_sec"] <= truth_ts <= row["window_end_sec"]]
        nearest = None
        if covering:
            nearest = covering[0]
        elif packet_windows:
            nearest = min(
                packet_windows,
                key=lambda row: min(
                    abs(row["window_start_sec"] - truth_ts),
                    abs(row["window_end_sec"] - truth_ts),
                ),
            )
        diagnostics_rows.append(
            {
                "truth_event_id": miss.get("truth_event_id"),
                "event_ts": truth_ts,
                "covered_by_packet": bool(covering),
                "nearest_packet": nearest,
            }
        )
    return {"missed_truth_events": diagnostics_rows, "diagnostics_tolerance_sec": per_tolerance[loosest_key]["tolerance_sec"]}


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 4)
