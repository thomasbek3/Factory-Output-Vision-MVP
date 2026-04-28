from pathlib import Path

from scripts.build_morning_proof_report import build_report, main, render_markdown


def write_json(path: Path, payload: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def test_build_report_separates_accepted_suppressed_uncertain(tmp_path: Path):
    receipt = tmp_path / "diag" / "track_receipts" / "track-000001.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        """
        {
          "review_assets": {
            "track_sheet_path": "diag/track_receipts/track-000001-sheet.jpg",
            "raw_crop_paths": ["diag/track_receipts/track-000001-crops/crop-01.jpg"]
          }
        }
        """,
        encoding="utf-8",
    )
    diagnostic = write_json(
        tmp_path / "diag" / "diagnostic.json",
        """
        {
          "schema_version": "factory-event-diagnostic-v1",
          "video_path": "data/videos/from-pc/factory2.MOV",
          "model_path": "models/panel_in_transit.pt",
          "person_model_path": "yolo11n.pt",
          "start_timestamp": 78.0,
          "end_timestamp": 118.0,
          "fps": 3.0,
          "frame_count": 120,
          "overlay_sheet_path": "diag/overlay_sheet.jpg",
          "overlay_video_path": "diag/overlay_video.mp4",
          "hard_negative_manifest_path": "diag/hard_negative_manifest.json",
          "perception_gate_summary": {
            "allowed_source_token_tracks": [],
            "track_count": 3,
            "decision_counts": {"allow_source_token": 0, "reject": 2, "uncertain": 1},
            "reason_counts": {"worker_body_overlap": 2, "source_without_output_settle": 1}
          },
          "perception_gate": [
            {
              "track_id": 1,
              "decision": "reject",
              "reason": "worker_body_overlap",
              "flags": ["high_person_overlap", "not_enough_object_outside_person"],
              "evidence": {"source_frames": 5, "output_frames": 0, "person_overlap_ratio": 1.0, "outside_person_ratio": 0.0, "max_displacement": 100.0, "flow_coherence": 0.2}
            },
            {
              "track_id": 2,
              "decision": "reject",
              "reason": "worker_body_overlap",
              "flags": ["high_person_overlap"],
              "evidence": {"source_frames": 4, "output_frames": 0, "person_overlap_ratio": 0.95, "outside_person_ratio": 0.05}
            },
            {
              "track_id": 3,
              "decision": "uncertain",
              "reason": "source_without_output_settle",
              "flags": [],
              "evidence": {"source_frames": 8, "output_frames": 0, "person_overlap_ratio": 0.0, "outside_person_ratio": 1.0}
            }
          ],
          "summary": {"has_source_to_output_candidate": true},
          "track_receipts": ["RECEIPT_PATH", "diag/track_receipts/track-000002.json"],
          "track_receipt_cards": ["diag/track_receipts/track-000001-sheet.jpg"]
        }
        """.replace("RECEIPT_PATH", str(receipt)),
    )
    fp_report = write_json(
        tmp_path / "fp.json",
        """
        {
          "confidence": 0.25,
          "model_path": "models/panel_in_transit.pt",
          "hard_negative_images": 16,
          "images_with_false_positives": 0,
          "false_positive_detections": 0,
          "false_positive_image_rate": 0.0
        }
        """,
    )
    positive_report = write_json(
        tmp_path / "positive.json",
        """
        {
          "confidence": 0.25,
          "iou_threshold": 0.3,
          "model_path": "models/panel_in_transit.pt",
          "summary": {"positive_images": 2, "positive_labels": 2, "matched_labels": 1, "missed_labels": 1, "label_recall": 0.5}
        }
        """,
    )

    report = build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report], positive_report_paths=[positive_report])

    assert report["verdict"] == "auditable_abstention_no_trusted_positive"
    assert report["accepted_count"] == 0
    assert report["suppressed_count"] == 2
    assert report["uncertain_count"] == 1
    assert report["bottleneck"] == "perception_gate_worker_body_overlap"
    assert report["detector_false_positive_eval"]["false_positive_detections"] == 0
    assert report["detector_positive_eval"]["positive_labels"] == 2
    assert report["detector_positive_eval"]["matched_labels"] == 1
    assert report["detector_positive_eval"]["label_recall"] == 0.5
    assert report["failure_link_counts"] == {"missing_output_settle": 1, "worker_body_overlap": 2}
    assert report["diagnostics"][0]["failure_link_counts"] == {"missing_output_settle": 1, "worker_body_overlap": 2}
    track_receipt = report["diagnostics"][0]["track_decision_receipts"][0]
    assert track_receipt["failure_link"] == "worker_body_overlap"
    assert track_receipt["receipt_json_path"] == str(receipt)
    assert track_receipt["raw_crop_paths"] == ["diag/track_receipts/track-000001-crops/crop-01.jpg"]


def test_build_report_counts_allowed_source_tokens(tmp_path: Path):
    diagnostic = write_json(
        tmp_path / "diagnostic.json",
        """
        {
          "perception_gate_summary": {
            "allowed_source_token_tracks": [4, 9],
            "track_count": 3,
            "decision_counts": {"allow_source_token": 2, "reject": 1},
            "reason_counts": {"source_token_allowed_by_protrusion": 2, "worker_body_overlap": 1}
          }
        }
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"items\": []}")

    report = build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report])

    assert report["verdict"] == "accepted_positive_count_available"
    assert report["accepted_count"] == 2
    assert report["suppressed_count"] == 1
    assert report["uncertain_count"] == 0
    assert report["bottleneck"] == "none"


def test_render_markdown_includes_receipt_paths(tmp_path: Path):
    diagnostic = write_json(
        tmp_path / "diagnostic.json",
        """
        {
          "perception_gate_summary": {"allowed_source_token_tracks": [], "track_count": 1, "decision_counts": {"reject": 1}, "reason_counts": {"worker_body_overlap": 1}},
          "track_receipts": ["receipts/track-1.json"],
          "overlay_sheet_path": "overlay.jpg"
        }
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"hard_negative_images\": 1, \"false_positive_detections\": 0}")
    markdown = render_markdown(build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report]))

    assert "accepted_count: 0" in markdown
    assert "receipts/track-1.json" in markdown
    assert "overlay.jpg" in markdown


def test_main_writes_json_and_markdown(tmp_path: Path):
    diagnostic = write_json(
        tmp_path / "diagnostic.json",
        """
        {
          "perception_gate_summary": {"allowed_source_token_tracks": [], "track_count": 1, "decision_counts": {"uncertain": 1}, "reason_counts": {"source_without_output_settle": 1}}
        }
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"hard_negative_images\": 1, \"false_positive_detections\": 0}")
    positive_report = write_json(tmp_path / "positive.json", "{\"summary\": {\"positive_labels\": 1, \"matched_labels\": 1, \"missed_labels\": 0, \"label_recall\": 1.0}}")
    output = tmp_path / "report.json"
    markdown = tmp_path / "report.md"

    assert main([
        "--diagnostic",
        str(diagnostic),
        "--fp-report",
        str(fp_report),
        "--positive-report",
        str(positive_report),
        "--output",
        str(output),
        "--markdown-output",
        str(markdown),
    ]) == 0

    assert output.exists()
    assert markdown.exists()
    assert "auditable_abstention" in output.read_text(encoding="utf-8")
