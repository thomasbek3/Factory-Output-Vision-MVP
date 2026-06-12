from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.state_diff_reconciler import SCHEMA_VERSION, build_state_diff_reconciliation
from scripts import reconcile_state_diff


def test_state_diff_reconciles_asserts_refutes_and_unclear(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    manifest = _write_packet_manifest(tmp_path, cv2=cv2, np=np)
    labels = _write_labels(tmp_path)

    payload = build_state_diff_reconciliation(
        packet_manifest_path=manifest,
        teacher_labels_path=labels,
        diff_threshold=0.02,
    )

    rows = {row["packet_id"]: row for row in payload["rows"]}
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["refuses_validation_truth"] is True
    assert rows["packet-change"]["reconciliation_status"] == "matched_asserted_change"
    assert rows["packet-stable"]["reconciliation_status"] == "matched_refuted_no_change"
    assert rows["packet-change"]["validation_truth_eligible"] is False
    assert rows["packet-stable"]["training_eligible"] is False


def test_reconcile_state_diff_cli_reports_errors(tmp_path: Path, capsys) -> None:
    exit_code = reconcile_state_diff.main(
        ["--packet-manifest", str(tmp_path / "missing.json"), "--output", str(tmp_path / "out.json")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err


def _write_packet_manifest(tmp_path: Path, *, cv2, np) -> Path:
    packets = []
    for packet_id, changed in [("packet-change", True), ("packet-stable", False)]:
        packet_dir = tmp_path / packet_id
        packet_dir.mkdir()
        diff_path = packet_dir / "before_after_diff_heatmap.jpg"
        image = np.full((20, 20, 3), 80 if changed else 0, dtype=np.uint8)
        assert cv2.imwrite(str(diff_path), image)
        packet_path = packet_dir / "packet_manifest.json"
        packet_path.write_text(
            json.dumps(
                {
                    "schema_version": "factory-vision-teacher-evidence-packets-v2",
                    "packet_id": packet_id,
                    "candidate_id": f"{packet_id}-candidate",
                    "window_id": f"{packet_id}-window",
                    "assets": [{"kind": "frame_diff_or_motion_heatmap", "path": diff_path.as_posix()}],
                    "validation_truth_eligible": False,
                    "training_eligible": False,
                }
            ),
            encoding="utf-8",
        )
        packets.append({"packet_id": packet_id, "packet_manifest_path": packet_path.as_posix()})
    manifest = tmp_path / "teacher_evidence_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-evidence-packets-v2",
                "station_id": "line-a",
                "packets": packets,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _write_labels(tmp_path: Path) -> Path:
    labels = tmp_path / "teacher_labels.json"
    labels.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-labels-v1",
                "labels": [
                    {
                        "label_id": "change-label",
                        "packet_id": "packet-change",
                        "window_id": "packet-change-window",
                        "verification_decision": "assert_completed",
                        "teacher_output_status": "completed",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                    {
                        "label_id": "stable-label",
                        "packet_id": "packet-stable",
                        "window_id": "packet-stable-window",
                        "verification_decision": "refute_completed",
                        "teacher_output_status": "worker_only",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return labels
