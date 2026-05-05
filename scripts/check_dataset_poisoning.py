#!/usr/bin/env python3
"""Check active-learning datasets for teacher-label and split-leakage hazards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation_truth_guard import ValidationTruthError, iter_dicts, validate_truth_file, validate_truth_payload


class DatasetPoisoningError(ValueError):
    """Raised when a dataset violates active-learning safety rules."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _label_identity(item: dict[str, Any]) -> str | None:
    for key in ("window_id", "event_id", "truth_event_id", "label_id", "item_id"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def extract_split_ids(payload: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                ids.add(item)
            elif isinstance(item, dict):
                identity = _label_identity(item)
                if identity:
                    ids.add(identity)
    elif isinstance(payload, dict):
        for key in ("window_ids", "event_ids", "item_ids"):
            raw = payload.get(key)
            if isinstance(raw, list):
                ids.update(str(item) for item in raw)
        for key in ("items", "labels", "windows", "events"):
            raw_items = payload.get(key)
            if isinstance(raw_items, list):
                ids.update(extract_split_ids(raw_items))
    return ids


def _failures_for_teacher_labels(payload: dict[str, Any], *, source: str) -> list[str]:
    failures: list[str] = []
    if str(payload.get("schema_version") or "") != "factory-vision-teacher-labels-v1":
        return failures
    for label in payload.get("labels") or []:
        label_id = label.get("label_id") or label.get("window_id") or "unknown"
        tier = str(label.get("label_authority_tier") or "").lower()
        review_status = str(label.get("review_status") or "").lower()
        if label.get("validation_truth_eligible") is True:
            failures.append(f"{source}:{label_id} teacher label is marked validation_truth_eligible")
        if tier == "gold" and review_status not in {"approved", "edited"}:
            failures.append(f"{source}:{label_id} unreviewed teacher label is in gold set")
        if tier == "bronze" and label.get("training_eligible") is True:
            failures.append(f"{source}:{label_id} bronze teacher label is marked training_eligible")
    return failures


def _failures_for_dataset(payload: dict[str, Any], *, source: str) -> list[str]:
    failures: list[str] = []
    if str(payload.get("schema_version") or "") != "factory-vision-active-learning-dataset-v1":
        return failures
    policy = payload.get("label_tier_policy") or {}
    if policy.get("validation_truth_requires_gold") is not True:
        failures.append(f"{source}: validation_truth_requires_gold must be true")
    if policy.get("silver_validation_allowed") is not False:
        failures.append(f"{source}: silver_validation_allowed must be false")

    for item in payload.get("items") or []:
        item_id = item.get("item_id") or item.get("window_id") or "unknown"
        tier = str(item.get("label_authority_tier") or "").lower()
        review_status = str(item.get("review_status") or "").lower()
        if item.get("validation_truth_eligible") is True and tier != "gold":
            failures.append(f"{source}:{item_id} non-gold item is validation_truth_eligible")
        if tier == "gold" and review_status not in {"approved", "edited"}:
            failures.append(f"{source}:{item_id} gold item is not reviewed")
        if tier == "bronze" and item.get("training_eligible") is True:
            failures.append(f"{source}:{item_id} bronze item is training_eligible")

    splits = payload.get("splits") or {}
    train_ids = extract_split_ids(splits.get("train") or [])
    test_ids = extract_split_ids(splits.get("test") or [])
    overlap = sorted(train_ids & test_ids)
    if overlap:
        failures.append(f"{source}: train/test split overlap: {', '.join(overlap)}")
    return failures


def _failures_for_generic_payload(payload: dict[str, Any], *, source: str) -> list[str]:
    failures: list[str] = []
    for item in iter_dicts(payload):
        tier = str(item.get("label_authority_tier") or "").lower()
        review_status = str(item.get("review_status") or "").lower()
        identity = _label_identity(item) or "unknown"
        if tier == "gold" and review_status == "pending":
            failures.append(f"{source}:{identity} pending label is in gold set")
        if item.get("validation_truth_eligible") is True and tier in {"bronze", "silver"}:
            failures.append(f"{source}:{identity} {tier} label is validation truth eligible")
    return failures


def check_payload(payload: dict[str, Any], *, source: str) -> list[str]:
    failures: list[str] = []
    failures.extend(_failures_for_teacher_labels(payload, source=source))
    failures.extend(_failures_for_dataset(payload, source=source))
    failures.extend(_failures_for_generic_payload(payload, source=source))
    return sorted(set(failures))


def check_split_files(train_split: Path | None, test_split: Path | None) -> list[str]:
    if train_split is None or test_split is None:
        return []
    train_ids = extract_split_ids(json.loads(train_split.read_text(encoding="utf-8")))
    test_ids = extract_split_ids(json.loads(test_split.read_text(encoding="utf-8")))
    overlap = sorted(train_ids & test_ids)
    if not overlap:
        return []
    return [f"split files overlap: {', '.join(overlap)}"]


def run_checks(
    *,
    datasets: list[Path],
    teacher_labels: list[Path],
    truth_artifacts: list[Path],
    train_split: Path | None = None,
    test_split: Path | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    for path in datasets + teacher_labels:
        failures.extend(check_payload(read_json(path), source=path.as_posix()))
    for path in truth_artifacts:
        try:
            validate_truth_file(path)
        except ValidationTruthError as exc:
            failures.append(str(exc))
        else:
            payload = read_json(path)
            try:
                validate_truth_payload(payload, source=path.as_posix())
            except ValidationTruthError as exc:
                failures.append(str(exc))
    failures.extend(check_split_files(train_split, test_split))
    if failures:
        raise DatasetPoisoningError("\n".join(sorted(set(failures))))
    return {
        "ok": True,
        "dataset_count": len(datasets),
        "teacher_label_count": len(teacher_labels),
        "truth_artifact_count": len(truth_artifacts),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check active-learning label artifacts for poisoning hazards")
    parser.add_argument("--dataset", type=Path, action="append", default=[])
    parser.add_argument("--teacher-labels", type=Path, action="append", default=[])
    parser.add_argument("--truth-artifact", type=Path, action="append", default=[])
    parser.add_argument("--train-split", type=Path)
    parser.add_argument("--test-split", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run_checks(
            datasets=args.dataset,
            teacher_labels=args.teacher_labels,
            truth_artifacts=args.truth_artifact,
            train_split=args.train_split,
            test_split=args.test_split,
        )
    except (DatasetPoisoningError, ValidationTruthError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
