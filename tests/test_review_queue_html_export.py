from __future__ import annotations

import json
from pathlib import Path

from scripts.export_review_queue_html import build_review_queue_html


def _write_queue(path: Path, frame_path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-review-queue-v1",
                "case_id": "fixture_case",
                "source_evidence_path": "evidence.json",
                "teacher_labels_path": "teacher.json",
                "privacy_mode": "offline_local",
                "provider": {"name": "moondream_station", "model": "moondream-2"},
                "refuses_validation_truth": True,
                "queue": [
                    {
                        "queue_id": "review-0001",
                        "rank": 1,
                        "window_id": "needs-review",
                        "priority_score": 150,
                        "priority_bucket": "review_first",
                        "review_reasons": ["teacher_unclear", "duplicate_risk_high"],
                        "candidate_use": "needs_human_review",
                        "teacher_output_status": "unclear",
                        "confidence_tier": "low",
                        "duplicate_risk": "high",
                        "miss_risk": "unknown",
                        "rationale": "Cannot be determined from the image.",
                        "time_window": {"center_sec": 5.0},
                        "primary_frame_asset": {
                            "frame_path": frame_path.as_posix(),
                            "timestamp_sec": 5.0,
                            "sha256": "frame-sha",
                            "status": "written",
                        },
                        "frame_assets": [
                            {
                                "frame_path": frame_path.as_posix(),
                                "timestamp_sec": 5.0,
                                "sha256": "frame-sha",
                                "status": "written",
                            }
                        ],
                        "label_authority_tier": "bronze",
                        "review_status": "pending",
                        "validation_truth_eligible": False,
                        "training_eligible": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_review_queue_html_contains_safety_boundary_and_labels(tmp_path: Path) -> None:
    frame_path = tmp_path / "frames" / "review.jpg"
    frame_path.parent.mkdir()
    frame_path.write_bytes(b"fake-jpeg")
    queue_path = tmp_path / "queue.json"
    _write_queue(queue_path, frame_path)

    html_text = build_review_queue_html(queue_path=queue_path, output_path=tmp_path / "review.html")

    assert "Factory Vision Review Queue" in html_text
    assert "Advisory only" in html_text
    assert "validation truth" in html_text
    assert "needs-review" in html_text
    assert "teacher_unclear" in html_text
    assert "Cannot be determined from the image." in html_text


def test_review_queue_html_uses_relative_image_paths(tmp_path: Path) -> None:
    frame_path = tmp_path / "frames" / "review.jpg"
    frame_path.parent.mkdir()
    frame_path.write_bytes(b"fake-jpeg")
    queue_path = tmp_path / "queue.json"
    _write_queue(queue_path, frame_path)

    html_text = build_review_queue_html(queue_path=queue_path, output_path=tmp_path / "exports" / "review.html")

    assert 'src="../frames/review.jpg"' in html_text
    assert str(frame_path) not in html_text
