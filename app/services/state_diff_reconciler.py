from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-vision-state-diff-reconciliation-v1"
GENERATED_BY = "state_diff_reconciler_v1"


def build_state_diff_reconciliation(
    *,
    packet_manifest_path: Path,
    teacher_labels_path: Path | None = None,
    diff_threshold: float = 0.02,
) -> dict[str, Any]:
    if diff_threshold <= 0:
        raise ValueError("diff_threshold must be positive")
    packet_manifest = json.loads(packet_manifest_path.read_text(encoding="utf-8"))
    labels_by_packet = _labels_by_packet(teacher_labels_path)
    rows: list[dict[str, Any]] = []
    for packet_row in packet_manifest.get("packets") or []:
        packet_path = Path(str(packet_row["packet_manifest_path"]))
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        diff_asset = _asset_by_kind(packet, "frame_diff_or_motion_heatmap")
        diff_score = _image_mean_score(Path(diff_asset["path"])) if diff_asset else None
        state_change_detected = bool(diff_score is not None and diff_score >= diff_threshold)
        label = labels_by_packet.get(str(packet["packet_id"]))
        rows.append(
            {
                "packet_id": packet["packet_id"],
                "candidate_id": packet.get("candidate_id"),
                "window_id": packet.get("window_id"),
                "diff_score": round(diff_score, 6) if diff_score is not None else None,
                "diff_threshold": diff_threshold,
                "state_change_detected": state_change_detected,
                "teacher_verification_decision": (label or {}).get("verification_decision"),
                "teacher_output_status": (label or {}).get("teacher_output_status"),
                "reconciliation_status": _reconciliation_status(
                    state_change_detected=state_change_detected,
                    label=label,
                ),
                "validation_truth_eligible": False,
                "training_eligible": False,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "packet_manifest_path": str(packet_manifest_path),
        "teacher_labels_path": str(teacher_labels_path) if teacher_labels_path else None,
        "generated_by": GENERATED_BY,
        "refuses_validation_truth": True,
        "diff_threshold": diff_threshold,
        "summary": {
            "packet_count": len(rows),
            "state_change_count": len([row for row in rows if row["state_change_detected"]]),
            "matched_assert_count": len([row for row in rows if row["reconciliation_status"] == "matched_asserted_change"]),
            "refuted_change_count": len([row for row in rows if row["reconciliation_status"] == "refuted_visible_change"]),
            "asserted_without_change_count": len(
                [row for row in rows if row["reconciliation_status"] == "asserted_without_visible_change"]
            ),
            "unclear_count": len([row for row in rows if row["reconciliation_status"] == "unclear"]),
        },
        "rows": rows,
    }


def write_state_diff_reconciliation(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _labels_by_packet(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels: dict[str, dict[str, Any]] = {}
    for label in payload.get("labels") or []:
        packet_id = label.get("packet_id")
        if packet_id:
            labels[str(packet_id)] = label
    return labels


def _asset_by_kind(packet: dict[str, Any], kind: str) -> dict[str, Any] | None:
    for asset in packet.get("assets") or []:
        if asset.get("kind") == kind:
            return asset
    return None


def _image_mean_score(path: Path) -> float:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("state-diff reconciliation requires cv2; use the repo .venv") from exc
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"could not read state diff image: {path}")
    return float(image.mean()) / 255.0


def _reconciliation_status(*, state_change_detected: bool, label: dict[str, Any] | None) -> str:
    decision = str((label or {}).get("verification_decision") or "unclear")
    if decision == "assert_completed" and state_change_detected:
        return "matched_asserted_change"
    if decision == "assert_completed" and not state_change_detected:
        return "asserted_without_visible_change"
    if decision == "refute_completed" and state_change_detected:
        return "refuted_visible_change"
    if decision == "refute_completed":
        return "matched_refuted_no_change"
    if state_change_detected:
        return "visible_change_without_teacher_assert"
    return "unclear"
