"""Shared helpers for promoting worker-overlap tracks using separation receipts."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.services.perception_gate import GateTrackFeatures, evaluate_track


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def person_panel_separation_path(receipt_path: str | None) -> str | None:
    if not receipt_path:
        return None
    path = Path(receipt_path)
    return str(path.with_name(path.stem + "-person-panel-separation.json"))


def load_person_panel_separation(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def person_panel_separation_features(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    selected_frames = [item for item in as_list(payload.get("selected_frames")) if isinstance(item, dict)]
    total_candidate_frames = int(summary.get("separable_panel_candidate_frames") or 0)
    if not total_candidate_frames:
        total_candidate_frames = sum(
            1 for item in selected_frames if item.get("separation_decision") == "separable_panel_candidate"
        )
    source_candidate_frames = sum(
        1
        for item in selected_frames
        if item.get("separation_decision") == "separable_panel_candidate" and str(item.get("zone") or "unknown") != "output"
    )
    max_signal = float(summary.get("max_estimated_visible_signal") or 0.0)
    for item in selected_frames:
        max_signal = max(
            max_signal,
            float(item.get("estimated_visible_nonperson_region_signal") or 0.0),
            float(item.get("mesh_signal_nonperson_score") or 0.0),
            float(item.get("mesh_signal_border_score") or 0.0),
        )
    return {
        "person_panel_recommendation": payload.get("recommendation"),
        "person_panel_total_candidate_frames": total_candidate_frames,
        "person_panel_source_candidate_frames": source_candidate_frames,
        "person_panel_max_visible_nonperson_ratio": float(summary.get("max_visible_nonperson_ratio") or 0.0),
        "person_panel_max_signal": max_signal,
        "person_panel_summary": summary if summary else None,
    }


def promote_worker_overlap_gate_row(row: dict[str, Any], receipt_path: str | None) -> dict[str, Any]:
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
