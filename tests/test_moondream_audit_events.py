from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.moondream_audit_events import (
    DryRunAuditProvider,
    MoondreamStationProvider,
    build_moondream_audit_labels,
    build_moondream_question,
)


def _write_evidence(path: Path, image_path: Path) -> None:
    image_path.write_bytes(b"fake-jpeg-bytes")
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-event-evidence-v1",
                "case_id": "fixture_case",
                "privacy_mode": "offline_local",
                "video": {"path": "video.mov", "sha256": "abc"},
                "source_artifacts": {"observed_events_path": "observed.json"},
                "model_settings": {},
                "windows": [
                    {
                        "window_id": "fixture-count-0001",
                        "window_type": "count_event",
                        "time_window": {"start_sec": 1.0, "center_sec": 2.0, "end_sec": 3.0},
                        "frame_window": {},
                        "count_event_evidence": {"event_ts": 2.0},
                        "review_window": {
                            "sample_timestamps_sec": [1.0, 2.0, 3.0],
                            "asset_status": "frames_extracted",
                            "frame_assets": [
                                {
                                    "timestamp_sec": 2.0,
                                    "frame_path": image_path.as_posix(),
                                    "sha256": "abc",
                                    "status": "written",
                                }
                            ],
                        },
                        "confidence_tier": "unknown",
                        "duplicate_risk": "unknown",
                        "miss_risk": "unknown",
                        "label_authority_tier": "bronze",
                    }
                ],
                "review_window_metadata": [],
            }
        ),
        encoding="utf-8",
    )


def test_moondream_audit_dry_run_outputs_bronze_pending(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    _write_evidence(evidence_path, tmp_path / "frame.jpg")

    payload = build_moondream_audit_labels(
        evidence_path=evidence_path,
        provider=DryRunAuditProvider(),
    )

    assert payload["provider"]["network_calls_made"] is False
    assert payload["refuses_validation_truth"] is True
    label = payload["labels"][0]
    assert label["teacher_output_status"] == "unclear"
    assert label["label_authority_tier"] == "bronze"
    assert label["review_status"] == "pending"
    assert label["validation_truth_eligible"] is False
    assert label["training_eligible"] is False


def test_moondream_station_provider_refuses_nonlocal_endpoint() -> None:
    with pytest.raises(ValueError, match="localhost"):
        MoondreamStationProvider(endpoint="https://api.moondream.ai/v1")


def test_moondream_station_provider_uses_local_query_and_keeps_advisory_labels(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    _write_evidence(evidence_path, tmp_path / "frame.jpg")
    requests: list[tuple[str, dict, float]] = []

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        requests.append((url, payload, timeout))
        return {
            "request_id": "local-request-1",
            "answer": json.dumps(
                {
                    "teacher_output_status": "completed",
                    "confidence_tier": "high",
                    "duplicate_risk": "low",
                    "miss_risk": "low",
                    "rationale": "The frame appears to show a completed placement.",
                }
            ),
        }

    provider = MoondreamStationProvider(
        endpoint="http://127.0.0.1:2020/v1",
        timeout_sec=7.0,
        post_json=fake_post,
    )
    payload = build_moondream_audit_labels(evidence_path=evidence_path, provider=provider)

    assert requests
    assert requests[0][0] == "http://127.0.0.1:2020/v1/query"
    assert requests[0][1]["image_url"].startswith("data:image/jpeg;base64,")
    assert "Return JSON only" in requests[0][1]["question"]
    assert requests[0][1]["temperature"] == 0
    assert requests[0][1]["max_tokens"] == 192
    assert requests[0][2] == 7.0
    assert payload["provider"]["network_calls_made"] is True
    label = payload["labels"][0]
    assert label["teacher_output_status"] == "completed"
    assert label["confidence_tier"] == "high"
    assert label["label_authority_tier"] == "bronze"
    assert label["review_status"] == "pending"
    assert label["validation_truth_eligible"] is False
    assert label["audit_metadata"]["request_id"] == "local-request-1"


def test_moondream_station_provider_records_provider_errors_as_unclear(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    _write_evidence(evidence_path, tmp_path / "frame.jpg")

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        return {"error": "model weights are not cached"}

    provider = MoondreamStationProvider(endpoint="http://127.0.0.1:2020/v1", post_json=fake_post)
    payload = build_moondream_audit_labels(evidence_path=evidence_path, provider=provider)

    label = payload["labels"][0]
    assert label["teacher_output_status"] == "unclear"
    assert label["confidence_tier"] == "low"
    assert label["label_authority_tier"] == "bronze"
    assert label["review_status"] == "pending"
    assert label["audit_metadata"]["provider_error"] == "model weights are not cached"
    assert "Moondream Station error" in label["rationale"]


def test_moondream_prompt_constrains_all_enum_fields(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    image_path = tmp_path / "frame.jpg"
    _write_evidence(evidence_path, image_path)
    window = json.loads(evidence_path.read_text(encoding="utf-8"))["windows"][0]

    question = build_moondream_question(window)

    assert "Allowed confidence_tier values are: high, medium, low, unknown" in question
    assert "Allowed duplicate_risk and miss_risk values are: high, medium, low, unknown" in question
    assert "Do not repeat the window metadata as the rationale" in question


def test_moondream_station_provider_normalizes_common_md2_aliases(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    _write_evidence(evidence_path, tmp_path / "frame.jpg")

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        return {
            "answer": json.dumps(
                {
                    "teacher_output_status": "countable",
                    "confidence_tier": "confident",
                    "duplicate_risk": "no",
                    "miss_risk": "yes",
                    "rationale": "A visible part is being carried through the frame.",
                }
            ),
        }

    provider = MoondreamStationProvider(endpoint="http://127.0.0.1:2020/v1", post_json=fake_post)
    payload = build_moondream_audit_labels(evidence_path=evidence_path, provider=provider)

    label = payload["labels"][0]
    assert label["confidence_tier"] == "high"
    assert label["duplicate_risk"] == "low"
    assert label["miss_risk"] == "high"


def test_moondream_station_provider_degrades_contradictory_uncertain_rationale(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    _write_evidence(evidence_path, tmp_path / "frame.jpg")

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        return {
            "answer": json.dumps(
                {
                    "teacher_output_status": "countable",
                    "confidence_tier": "high",
                    "duplicate_risk": "low",
                    "miss_risk": "low",
                    "rationale": "Cannot be determined from the image.",
                }
            ),
        }

    provider = MoondreamStationProvider(endpoint="http://127.0.0.1:2020/v1", post_json=fake_post)
    payload = build_moondream_audit_labels(evidence_path=evidence_path, provider=provider)

    label = payload["labels"][0]
    assert label["teacher_output_status"] == "unclear"
    assert label["confidence_tier"] == "low"
    assert label["duplicate_risk"] == "unknown"
    assert label["miss_risk"] == "unknown"
