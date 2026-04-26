#!/usr/bin/env python3
"""Review Factory Vision label manifests with deterministic AI-review contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.label_quality import (
    CandidateLabel,
    LabelQualityConfig,
    ReviewContext,
    ReviewDecision,
    build_review_card,
    label_to_manifest,
    polygon_to_box,
    review_label,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review YOLO box and polygon-derived Factory Vision labels."
    )
    parser.add_argument("manifest", type=Path, help="Input label manifest JSON")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output reviewed manifest JSON. Required to avoid overwriting source labels.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=LabelQualityConfig.min_confidence,
        help="Minimum deterministic confidence before a label becomes uncertain.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output.resolve() == args.manifest.resolve():
        raise ValueError("--output must not overwrite the input manifest")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    reviewed = review_manifest(
        manifest,
        config=LabelQualityConfig(min_confidence=args.min_confidence),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reviewed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def review_manifest(
    manifest: dict[str, Any],
    *,
    config: LabelQualityConfig | None = None,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "accepted": [],
        "fixed": [],
        "rejected": [],
        "uncertain": [],
    }
    review_cards: list[dict[str, Any]] = []
    trainable_labels: list[dict[str, Any]] = []

    for row in manifest.get("labels", []):
        label = _candidate_from_manifest(row)
        context = ReviewContext(
            previous_label=_optional_candidate(row.get("previous_label")),
            next_label=_optional_candidate(row.get("next_label")),
            worker_boxes=[_tuple_box(box) for box in row.get("worker_boxes", [])],
            ignore_regions=[_tuple_box(box) for box in row.get("ignore_regions", [])],
        )
        outcome = review_label(label, context=context, config=config)
        review_cards.append(build_review_card(label, outcome))
        reviewed_row = _reviewed_row(label, outcome)
        buckets[_bucket_name(outcome.decision)].append(reviewed_row)
        if reviewed_row["training_eligible"]:
            trainable_labels.append(_trainable_label_manifest(outcome.fixed_label or label))

    return {
        "schema_version": "label-quality-reviewed-v1",
        **buckets,
        "trainable_labels": trainable_labels,
        "review_cards": review_cards,
    }


def _candidate_from_manifest(row: dict[str, Any]) -> CandidateLabel:
    polygon = row.get("polygon")
    return CandidateLabel(
        label_id=str(row["label_id"]),
        frame_id=str(row["frame_id"]),
        image_width=int(row["image_width"]),
        image_height=int(row["image_height"]),
        class_name=str(row["class_name"]),
        box=_tuple_box(row["box"]) if row.get("box") is not None else None,
        polygon=[(float(x), float(y)) for x, y in polygon] if polygon is not None else None,
        confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
        source_type=row.get("source_type", "box"),
        metadata=row.get("metadata"),
    )


def _optional_candidate(row: dict[str, Any] | None) -> CandidateLabel | None:
    if row is None:
        return None
    return _candidate_from_manifest(row)


def _reviewed_row(label: CandidateLabel, outcome: Any) -> dict[str, Any]:
    training_eligible = outcome.decision in {ReviewDecision.ACCEPT, ReviewDecision.FIX}
    payload = {
        "label_id": label.label_id,
        "decision": outcome.decision.value,
        "reason_codes": outcome.reason_codes,
        "score": outcome.score,
        "training_eligible": training_eligible,
        "label": label_to_manifest(label),
    }
    if outcome.fixed_label is not None:
        payload["fixed_label"] = label_to_manifest(outcome.fixed_label)
    return payload


def _trainable_label_manifest(label: CandidateLabel) -> dict[str, Any]:
    payload = label_to_manifest(label)
    if "box" not in payload and label.polygon is not None:
        payload["box"] = [_json_number(value) for value in polygon_to_box(label.polygon)]
    return payload


def _bucket_name(decision: ReviewDecision) -> str:
    return {
        ReviewDecision.ACCEPT: "accepted",
        ReviewDecision.FIX: "fixed",
        ReviewDecision.REJECT: "rejected",
        ReviewDecision.UNCERTAIN: "uncertain",
    }[decision]


def _tuple_box(value: Any) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = value
    return (float(x1), float(y1), float(x2), float(y2))


def _json_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


if __name__ == "__main__":
    raise SystemExit(main())
