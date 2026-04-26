from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Any, Literal

Box = tuple[float, float, float, float]
Point = tuple[float, float]


class ReviewDecision(str, Enum):
    ACCEPT = "ACCEPT"
    FIX = "FIX"
    REJECT = "REJECT"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class CandidateLabel:
    label_id: str
    frame_id: str
    image_width: int
    image_height: int
    class_name: str
    box: Box | None = None
    polygon: list[Point] | None = None
    confidence: float | None = None
    source_type: Literal["box", "polygon"] = "box"
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReviewContext:
    previous_label: CandidateLabel | None = None
    next_label: CandidateLabel | None = None
    worker_boxes: list[Box] | None = None
    ignore_regions: list[Box] | None = None


@dataclass(frozen=True)
class LabelQualityConfig:
    allowed_class_names: tuple[str, ...] = ("active_panel", "panel")
    min_confidence: float = 0.75
    min_box_area_ratio: float = 0.001
    max_box_area_ratio: float = 0.65
    max_loose_area_multiplier: float = 8.0
    min_object_area_ratio: float = 0.0025
    overlap_threshold: float = 0.5
    temporal_center_jump_ratio: float = 0.35


@dataclass(frozen=True)
class ReviewOutcome:
    label_id: str
    decision: ReviewDecision
    reason_codes: list[str]
    score: float
    fixed_label: CandidateLabel | None = None


def polygon_to_box(points: list[Point] | None) -> Box:
    if not points:
        raise ValueError("polygon must contain at least one point")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def review_label(
    label: CandidateLabel,
    *,
    context: ReviewContext | None = None,
    config: LabelQualityConfig | None = None,
) -> ReviewOutcome:
    context = context or ReviewContext()
    config = config or LabelQualityConfig()
    reasons: list[str] = []
    fixed_label: CandidateLabel | None = None

    if label.class_name not in config.allowed_class_names:
        reasons.append("wrong_class")

    reasons.extend(_polygon_reasons(label))
    box = _candidate_box(label)
    if label.box is not None and label.polygon is not None and _polygon_has_area(label.polygon):
        if _coerce_box(label.box) != polygon_to_box(label.polygon):
            reasons.append("polygon_box_disagreement")

    clipped_box = _clip_box(box, label.image_width, label.image_height)
    if clipped_box != box:
        reasons.append(
            "polygon_box_clipped" if label.source_type == "polygon" else "box_out_of_bounds"
        )
        fixed_label = replace(
            label,
            box=clipped_box,
            polygon=_clip_polygon(label.polygon, label.image_width, label.image_height),
        )
        box = clipped_box

    if (label.metadata or {}).get("static_stack") is True:
        reasons.append("static_stack_negative")

    box_area = _box_area(box)
    image_area = label.image_width * label.image_height
    box_area_ratio = box_area / image_area if image_area else 0.0
    if box_area_ratio < config.min_box_area_ratio:
        reasons.append("box_too_tiny")
    if box_area_ratio > config.max_box_area_ratio:
        reasons.append("box_too_loose")

    object_box = (label.metadata or {}).get("object_box")
    if object_box is not None:
        object_area = _box_area(_coerce_box(object_box))
        if image_area and object_area / image_area < config.min_object_area_ratio:
            reasons.append("box_too_tiny")
        if object_area > 0 and box_area / object_area > config.max_loose_area_multiplier:
            reasons.append("box_too_loose")

    if label.confidence is not None and label.confidence < config.min_confidence:
        reasons.append("low_confidence")

    if _overlaps_any(box, context.worker_boxes, config.overlap_threshold):
        reasons.append("worker_overlap")
    if _overlaps_any(box, context.ignore_regions, config.overlap_threshold):
        reasons.append("ignore_region_overlap")

    if _has_temporal_jump(label, box, context, config):
        reasons.append("temporal_jump")

    reasons = _dedupe(reasons)
    decision = _decision_for(reasons, fixed_label)
    if decision == ReviewDecision.ACCEPT:
        reasons = ["active_panel_box_plausible"]
    score = _score_for(decision, reasons)
    return ReviewOutcome(
        label_id=label.label_id,
        decision=decision,
        reason_codes=reasons,
        score=score,
        fixed_label=fixed_label,
    )


def build_review_card(label: CandidateLabel, outcome: ReviewOutcome) -> dict[str, Any]:
    box = _candidate_box(outcome.fixed_label or label)
    prompt = (
        "Review this Factory Vision active_panel candidate. Decide whether the label "
        "should be ACCEPT, FIX, REJECT, or UNCERTAIN before model training."
    )
    return {
        "label_id": label.label_id,
        "frame_id": label.frame_id,
        "prompt": prompt,
        "candidate": {
            "class_name": label.class_name,
            "box_xyxy": _json_box(box),
            "polygon": _json_points(label.polygon),
            "confidence": label.confidence,
            "source_type": label.source_type,
            "metadata": label.metadata or {},
        },
        "deterministic_review": {
            "decision": outcome.decision.value,
            "reason_codes": outcome.reason_codes,
            "score": outcome.score,
        },
        "ai_reviewer_contract": {
            "schema_version": "label-quality-v1",
            "allowed_decisions": [decision.value for decision in ReviewDecision],
            "required_response_fields": ["decision", "reason_codes", "explanation"],
        },
    }


def label_to_manifest(label: CandidateLabel) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label_id": label.label_id,
        "frame_id": label.frame_id,
        "image_width": label.image_width,
        "image_height": label.image_height,
        "class_name": label.class_name,
        "confidence": label.confidence,
        "source_type": label.source_type,
    }
    if label.box is not None:
        payload["box"] = _json_box(label.box)
    if label.polygon is not None:
        payload["polygon"] = _json_points(label.polygon)
    if label.metadata:
        payload["metadata"] = label.metadata
    return payload


def _candidate_box(label: CandidateLabel) -> Box:
    if label.box is not None:
        return _coerce_box(label.box)
    if label.polygon is not None and len(label.polygon) == 0:
        return (0.0, 0.0, 0.0, 0.0)
    return polygon_to_box(label.polygon)


def _polygon_reasons(label: CandidateLabel) -> list[str]:
    if label.polygon is None:
        return []
    if len(label.polygon) < 3:
        return ["polygon_too_few_points"]
    if not _polygon_has_area(label.polygon):
        return ["polygon_degenerate"]
    return []


def _polygon_has_area(points: list[Point]) -> bool:
    return abs(_polygon_area(points)) > 0


def _polygon_area(points: list[Point]) -> float:
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += point[0] * next_point[1] - next_point[0] * point[1]
    return area / 2


def _coerce_box(value: Any) -> Box:
    x1, y1, x2, y2 = value
    return (float(x1), float(y1), float(x2), float(y2))


def _clip_box(box: Box, image_width: int, image_height: int) -> Box:
    x1, y1, x2, y2 = box
    return (
        min(max(x1, 0), image_width),
        min(max(y1, 0), image_height),
        min(max(x2, 0), image_width),
        min(max(y2, 0), image_height),
    )


def _clip_polygon(
    points: list[Point] | None,
    image_width: int,
    image_height: int,
) -> list[Point] | None:
    if points is None:
        return None
    return [
        (
            min(max(x, 0), image_width),
            min(max(y, 0), image_height),
        )
        for x, y in points
    ]


def _box_area(box: Box) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _intersection_area(a: Box, b: Box) -> float:
    return _box_area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def _overlaps_any(box: Box, regions: list[Box] | None, threshold: float) -> bool:
    if not regions:
        return False
    area = _box_area(box)
    if area == 0:
        return False
    return any(_intersection_area(box, _coerce_box(region)) / area >= threshold for region in regions)


def _has_temporal_jump(
    label: CandidateLabel,
    box: Box,
    context: ReviewContext,
    config: LabelQualityConfig,
) -> bool:
    neighbors = [candidate for candidate in (context.previous_label, context.next_label) if candidate]
    if not neighbors:
        return False
    diagonal = math.hypot(label.image_width, label.image_height)
    center = _box_center(box)
    for neighbor in neighbors:
        if neighbor.class_name != label.class_name:
            continue
        neighbor_center = _box_center(_candidate_box(neighbor))
        if math.dist(center, neighbor_center) / diagonal > config.temporal_center_jump_ratio:
            return True
    return False


def _box_center(box: Box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _decision_for(reasons: list[str], fixed_label: CandidateLabel | None) -> ReviewDecision:
    reject_reasons = {
        "wrong_class",
        "static_stack_negative",
        "box_out_of_bounds",
        "ignore_region_overlap",
        "box_too_tiny",
        "box_too_loose",
        "polygon_too_few_points",
        "polygon_degenerate",
    }
    if any(reason in reject_reasons for reason in reasons):
        return ReviewDecision.REJECT
    uncertain_reasons = {
        "temporal_jump",
        "low_confidence",
        "worker_overlap",
        "polygon_box_disagreement",
    }
    if any(reason in uncertain_reasons for reason in reasons):
        return ReviewDecision.UNCERTAIN
    if fixed_label is not None:
        return ReviewDecision.FIX
    return ReviewDecision.ACCEPT


def _score_for(decision: ReviewDecision, reasons: list[str]) -> float:
    if decision == ReviewDecision.ACCEPT:
        return 0.96
    if decision == ReviewDecision.FIX:
        return 0.84
    if decision == ReviewDecision.UNCERTAIN:
        return 0.5
    return max(0.05, 0.35 - 0.04 * len(reasons))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _json_box(box: Box) -> list[int | float]:
    return [_json_number(value) for value in box]


def _json_points(points: list[Point] | None) -> list[list[int | float]] | None:
    if points is None:
        return None
    return [[_json_number(x), _json_number(y)] for x, y in points]


def _json_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value
