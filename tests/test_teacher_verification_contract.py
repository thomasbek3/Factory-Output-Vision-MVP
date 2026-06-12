from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.teacher_verification import (
    DryRunVerificationProvider,
    FakeVerificationProvider,
    build_teacher_verifications_from_packets,
    verification_provider_for_name,
)
from scripts import generate_teacher_verifications


def test_dry_run_verification_outputs_unclear_bronze_no_network(tmp_path: Path) -> None:
    manifest = _write_packet_manifest(tmp_path)

    payload = build_teacher_verifications_from_packets(
        packet_manifest_path=manifest,
        provider=DryRunVerificationProvider(),
    )

    assert payload["schema_version"] == "factory-vision-teacher-labels-v1"
    assert payload["provider"]["network_calls_made"] is False
    assert payload["teacher_task"] == "verify_candidate_event"
    assert payload["refuses_validation_truth"] is True
    assert len(payload["labels"]) == 2
    for label in payload["labels"]:
        assert label["verification_decision"] == "unclear"
        assert label["teacher_output_status"] == "unclear"
        assert label["label_authority_tier"] == "bronze"
        assert label["review_status"] == "pending"
        assert label["validation_truth_eligible"] is False
        assert label["training_eligible"] is False


def test_fake_verification_can_assert_and_refute_without_truth_promotion(tmp_path: Path) -> None:
    manifest = _write_packet_manifest(tmp_path)

    payload = build_teacher_verifications_from_packets(
        packet_manifest_path=manifest,
        provider=FakeVerificationProvider(
            decisions_by_packet_id={
                "packet-one": "assert_completed",
                "packet-two": "refute_completed",
            }
        ),
    )

    labels = {label["packet_id"]: label for label in payload["labels"]}
    assert labels["packet-one"]["verification_decision"] == "assert_completed"
    assert labels["packet-one"]["teacher_output_status"] == "completed"
    assert labels["packet-one"]["suggested_event_ts_sec"] == 2.0
    assert labels["packet-two"]["verification_decision"] == "refute_completed"
    assert labels["packet-two"]["teacher_output_status"] == "worker_only"
    assert all(label["validation_truth_eligible"] is False for label in labels.values())
    assert all(label["training_eligible"] is False for label in labels.values())


def test_verification_provider_refuses_cloud_by_default() -> None:
    with pytest.raises(ValueError, match="disabled by default"):
        verification_provider_for_name("openai")


def test_generate_teacher_verifications_cli_dry_run(tmp_path: Path, capsys) -> None:
    manifest = _write_packet_manifest(tmp_path)
    output = tmp_path / "teacher_verifications.json"

    exit_code = generate_teacher_verifications.main(
        ["--packet-manifest", str(manifest), "--output", str(output), "--force"]
    )

    captured = capsys.readouterr()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert '"label_count": 2' in captured.out
    assert payload["provider"]["network_calls_made"] is False


def _write_packet_manifest(tmp_path: Path) -> Path:
    packet_paths = []
    for packet_id, center in [("packet-one", 2.0), ("packet-two", 6.0)]:
        packet_dir = tmp_path / packet_id
        packet_dir.mkdir()
        packet_path = packet_dir / "packet_manifest.json"
        packet_path.write_text(
            json.dumps(
                {
                    "schema_version": "factory-vision-teacher-evidence-packets-v2",
                    "packet_id": packet_id,
                    "candidate_id": f"{packet_id}-candidate",
                    "window_id": f"{packet_id}-window",
                    "station_id": "line-a",
                    "window": {
                        "start_offset_sec": center - 1.0,
                        "center_offset_sec": center,
                        "end_offset_sec": center + 1.0,
                    },
                    "assets": [],
                    "validation_truth_eligible": False,
                    "training_eligible": False,
                }
            ),
            encoding="utf-8",
        )
        packet_paths.append(packet_path)
    manifest = tmp_path / "teacher_evidence_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-evidence-packets-v2",
                "station_id": "line-a",
                "privacy_mode": "offline_local",
                "packets": [
                    {"packet_id": "packet-one", "packet_manifest_path": packet_paths[0].as_posix()},
                    {"packet_id": "packet-two", "packet_manifest_path": packet_paths[1].as_posix()},
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest
