"""Pre-count perception gate for Factory Vision tracks.

The count state machine should not receive a source token just because a detector
box crossed zones. This gate scores whether a track is physically plausible as a
moving panel instead of worker/body motion or a static output-stack edge.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GateConfig:
    min_source_frames: int = 1
    min_output_frames: int = 1
    min_displacement: float = 30.0
    min_internal_motion: float = 0.04
    max_person_overlap: float = 0.70
    min_outside_person_ratio: float = 0.20
    min_protruding_panel_ratio: float = 0.35
    max_static_stack_overlap: float = 0.65
    max_static_location_ratio: float = 0.70
    min_flow_coherence: float = 0.12
    min_person_panel_candidate_frames: int = 3
    min_person_panel_source_frames: int = 2
    min_person_panel_visible_ratio: float = 0.20
    min_person_panel_signal: float = 0.04
    min_person_panel_crop_positive_crops: int = 1
    min_person_panel_crop_positive_ratio: float = 0.75
    min_person_panel_crop_confidence: float = 0.95


@dataclass(frozen=True)
class GateTrackFeatures:
    track_id: int
    source_frames: int
    output_frames: int
    zones_seen: list[str]
    first_zone: str
    max_displacement: float
    mean_internal_motion: float
    max_internal_motion: float
    detections: int
    person_overlap_ratio: float = 0.0
    outside_person_ratio: float = 1.0
    static_stack_overlap_ratio: float = 0.0
    static_location_ratio: float = 0.0
    flow_coherence: float = 0.0
    edge_like_ratio: float = 0.0
    person_panel_recommendation: str | None = None
    person_panel_total_candidate_frames: int = 0
    person_panel_source_candidate_frames: int = 0
    person_panel_max_visible_nonperson_ratio: float = 0.0
    person_panel_max_signal: float = 0.0
    person_panel_crop_recommendation: str | None = None
    person_panel_crop_positive_crops: int = 0
    person_panel_crop_negative_crops: int = 0
    person_panel_crop_total_crops: int = 0
    person_panel_crop_positive_ratio: float = 0.0
    person_panel_crop_max_confidence: float = 0.0


@dataclass(frozen=True)
class GateDecision:
    track_id: int
    decision: str
    reason: str
    flags: list[str]
    evidence: dict[str, Any]


def evaluate_track(features: GateTrackFeatures, config: GateConfig | None = None) -> GateDecision:
    cfg = config or GateConfig()
    flags: list[str] = []
    saw_source = features.source_frames >= cfg.min_source_frames or "source" in features.zones_seen
    saw_output = features.output_frames >= cfg.min_output_frames or "output" in features.zones_seen
    low_motion = features.max_internal_motion < cfg.min_internal_motion
    low_displacement = features.max_displacement < cfg.min_displacement
    high_person_overlap = features.person_overlap_ratio > cfg.max_person_overlap
    low_outside_person = features.outside_person_ratio < cfg.min_outside_person_ratio
    protrudes_from_person = features.outside_person_ratio >= cfg.min_protruding_panel_ratio
    high_static_stack = features.static_stack_overlap_ratio > cfg.max_static_stack_overlap
    high_static_location = features.static_location_ratio > cfg.max_static_location_ratio
    low_flow_coherence = features.flow_coherence < cfg.min_flow_coherence
    strong_person_panel_separation = (
        features.person_panel_recommendation == "countable_panel_candidate"
        and features.person_panel_total_candidate_frames >= cfg.min_person_panel_candidate_frames
        and features.person_panel_source_candidate_frames >= cfg.min_person_panel_source_frames
        and features.person_panel_max_visible_nonperson_ratio >= cfg.min_person_panel_visible_ratio
        and features.person_panel_max_signal >= cfg.min_person_panel_signal
    )
    strong_person_panel_crop_classifier = (
        features.person_panel_crop_recommendation == "carried_panel"
        and features.person_panel_crop_positive_crops >= cfg.min_person_panel_crop_positive_crops
        and features.person_panel_crop_positive_ratio >= cfg.min_person_panel_crop_positive_ratio
        and features.person_panel_crop_max_confidence >= cfg.min_person_panel_crop_confidence
    )

    if saw_output and not saw_source:
        flags.append("output_only_no_source_token")
    if features.first_zone == "output":
        flags.append("started_in_output")
    if low_motion:
        flags.append("low_internal_motion")
    if low_displacement:
        flags.append("low_track_displacement")
    if high_person_overlap:
        flags.append("high_person_overlap")
    if low_outside_person:
        flags.append("not_enough_object_outside_person")
    if high_person_overlap and protrudes_from_person:
        flags.append("person_overlap_with_panel_protrusion")
    if strong_person_panel_separation:
        flags.append("strong_person_panel_separation")
    if strong_person_panel_crop_classifier:
        flags.append("strong_person_panel_crop_classifier")
    if high_static_stack:
        flags.append("high_static_stack_overlap")
    if high_static_location:
        flags.append("static_location_recurrence")
    if low_flow_coherence:
        flags.append("low_flow_coherence")

    if high_person_overlap and low_outside_person and not strong_person_panel_separation and not strong_person_panel_crop_classifier:
        decision = "reject"
        reason = "worker_body_overlap"
    elif saw_output and not saw_source and (high_static_stack or high_static_location or low_motion or low_displacement):
        decision = "reject"
        reason = "static_stack_edge"
    elif high_static_stack and (high_static_location or low_displacement):
        decision = "reject"
        reason = "static_stack_edge"
    elif saw_output and not saw_source:
        decision = "reject"
        reason = "output_only_no_source_token"
    elif (
        saw_source
        and saw_output
        and not low_displacement
        and not low_motion
        and not high_static_stack
        and (not high_person_overlap or protrudes_from_person or strong_person_panel_separation or strong_person_panel_crop_classifier)
    ):
        decision = "allow_source_token"
        reason = "moving_panel_candidate"
        if high_person_overlap and protrudes_from_person:
            flags.append("source_token_allowed_by_protrusion")
        if strong_person_panel_separation:
            flags.append("source_token_allowed_by_person_panel_separation")
        if strong_person_panel_crop_classifier:
            flags.append("source_token_allowed_by_crop_classifier")
        if low_flow_coherence:
            flags.append("flow_coherence_needs_review")
    elif saw_source and not saw_output:
        decision = "uncertain"
        reason = "source_without_output_settle"
    elif saw_source and saw_output:
        decision = "uncertain"
        reason = "source_to_output_evidence_incomplete"
    else:
        decision = "uncertain"
        reason = "insufficient_panel_evidence"

    return GateDecision(
        track_id=features.track_id,
        decision=decision,
        reason=reason,
        flags=flags,
        evidence=asdict(features),
    )


def summarize_gate_decisions(decisions: list[GateDecision]) -> dict[str, Any]:
    decision_counts = {"allow_source_token": 0, "reject": 0, "uncertain": 0}
    reason_counts: dict[str, int] = {}
    for item in decisions:
        decision_counts[item.decision] = decision_counts.get(item.decision, 0) + 1
        reason_counts[item.reason] = reason_counts.get(item.reason, 0) + 1
    return {
        "track_count": len(decisions),
        "decision_counts": decision_counts,
        "reason_counts": reason_counts,
        "allowed_source_token_tracks": [item.track_id for item in decisions if item.decision == "allow_source_token"],
    }
