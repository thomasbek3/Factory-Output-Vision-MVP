"""Guardrails for artifacts that are allowed to act as validation truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


DISALLOWED_TRUTH_SCHEMA_VERSIONS = {
    "factory-vision-teacher-labels-v1",
    "factory-vision-event-evidence-v1",
    "factory-vision-active-learning-dataset-v1",
}


class ValidationTruthError(ValueError):
    """Raised when an artifact is not eligible to serve as validation truth."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def validate_truth_payload(payload: dict[str, Any], *, source: str = "truth artifact") -> None:
    schema_version = str(payload.get("schema_version") or "")
    lowered_schema = schema_version.lower()
    if schema_version in DISALLOWED_TRUTH_SCHEMA_VERSIONS or "teacher" in lowered_schema or "vlm" in lowered_schema:
        raise ValidationTruthError(
            f"{source} uses schema_version {schema_version!r}; teacher/VLM artifacts cannot be validation truth"
        )

    for item in iter_dicts(payload):
        tier = str(item.get("label_authority_tier") or "").lower()
        review_status = str(item.get("review_status") or "").lower()
        truth_eligible = item.get("validation_truth_eligible")
        if truth_eligible is True and tier in {"bronze", "silver"}:
            raise ValidationTruthError(f"{source} marks {tier} label as validation truth eligible")
        if truth_eligible is True and review_status == "pending":
            raise ValidationTruthError(f"{source} marks a pending review label as validation truth eligible")


def validate_truth_file(path: Path, *, repo_root: Path | None = None) -> None:
    resolved_path = path
    if repo_root is not None and not resolved_path.is_absolute():
        resolved_path = repo_root / resolved_path
    if not resolved_path.exists():
        return
    validate_truth_payload(read_json(resolved_path), source=path.as_posix())
