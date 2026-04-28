import json
from pathlib import Path

import pytest

from scripts.run_factory2_morning_proof import (
    default_fp_output,
    default_positive_output,
    run_factory2_morning_proof,
)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_dataset(tmp_path: Path) -> Path:
    data_yaml = tmp_path / "dataset" / "data.yaml"
    data_yaml.parent.mkdir(parents=True, exist_ok=True)
    data_yaml.write_text("path: .\ntrain: images/train\nnames:\n  0: active_panel\n", encoding="utf-8")
    return data_yaml


def write_diagnostic(tmp_path: Path) -> Path:
    return write_json(
        tmp_path / "diag" / "diagnostic.json",
        {
            "video_path": "data/videos/from-pc/factory2.MOV",
            "start_timestamp": 78.0,
            "end_timestamp": 118.0,
            "fps": 3.0,
            "perception_gate_summary": {
                "allowed_source_token_tracks": [],
                "track_count": 3,
                "decision_counts": {"reject": 2, "uncertain": 1},
                "reason_counts": {"worker_body_overlap": 2, "source_without_output_settle": 1},
            },
            "track_receipts": ["diag/track-000001.json"],
            "track_receipt_cards": ["diag/track-000001-sheet.jpg"],
            "overlay_sheet_path": "diag/overlay_sheet.jpg",
            "hard_negative_manifest_path": "diag/hard_negative_manifest.json",
        },
    )


def write_worker_overlap_diagnostic(tmp_path: Path) -> Path:
    diag_dir = tmp_path / "diag"
    receipts_dir = diag_dir / "track_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / "track-000005.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-track-receipt-v1",
                "track_id": 5,
                "timestamps": {"first": 80.0, "last": 110.0},
                "evidence": {
                    "track_id": 5,
                    "first_timestamp": 80.0,
                    "last_timestamp": 110.0,
                    "first_zone": "source",
                    "zones_seen": ["source", "output"],
                    "source_frames": 38,
                    "output_frames": 1,
                    "max_displacement": 603.294,
                    "mean_internal_motion": 0.337425,
                    "max_internal_motion": 0.730217,
                    "detections": 39,
                    "static_location_ratio": 0.333333,
                    "flow_coherence": 0.501419,
                    "static_stack_overlap_ratio": 0.0,
                    "person_overlap_ratio": 1.0,
                    "outside_person_ratio": 0.0,
                    "observations": [],
                },
                "diagnosis": {
                    "track_id": 5,
                    "decision": "candidate",
                    "reason": "source_to_output_motion",
                    "flags": [],
                    "evidence": {"track_id": 5},
                },
                "perception_gate": {
                    "track_id": 5,
                    "decision": "reject",
                    "reason": "worker_body_overlap",
                    "flags": ["high_person_overlap", "not_enough_object_outside_person"],
                    "evidence": {
                        "track_id": 5,
                        "source_frames": 38,
                        "output_frames": 1,
                        "zones_seen": ["source", "output"],
                        "first_zone": "source",
                        "max_displacement": 603.294,
                        "mean_internal_motion": 0.337425,
                        "max_internal_motion": 0.730217,
                        "detections": 39,
                        "person_overlap_ratio": 1.0,
                        "outside_person_ratio": 0.0,
                        "static_stack_overlap_ratio": 0.0,
                        "static_location_ratio": 0.333333,
                        "flow_coherence": 0.501419,
                        "edge_like_ratio": 0.0,
                    },
                },
                "review_assets": {
                    "overlay_sheet_path": "diag/overlay_sheet.jpg",
                    "overlay_video_path": "diag/overlay_video.mp4",
                    "track_sheet_path": "diag/track_receipts/track-000005-sheet.jpg",
                    "raw_crop_paths": ["diag/track_receipts/track-000005-crops/crop-01-source.jpg"],
                },
            }
        ),
        encoding="utf-8",
    )
    return write_json(
        diag_dir / "diagnostic.json",
        {
            "video_path": "data/videos/from-pc/factory2.MOV",
            "start_timestamp": 78.0,
            "end_timestamp": 118.0,
            "fps": 3.0,
            "perception_gate_summary": {
                "allowed_source_token_tracks": [],
                "track_count": 1,
                "decision_counts": {"allow_source_token": 0, "reject": 1, "uncertain": 0},
                "reason_counts": {"worker_body_overlap": 1},
            },
            "perception_gate": [
                {
                    "track_id": 5,
                    "decision": "reject",
                    "reason": "worker_body_overlap",
                    "flags": ["high_person_overlap", "not_enough_object_outside_person"],
                    "evidence": {
                        "track_id": 5,
                        "detections": 39,
                        "first_zone": "source",
                        "zones_seen": ["source", "output"],
                        "source_frames": 38,
                        "output_frames": 1,
                        "max_displacement": 603.294,
                        "mean_internal_motion": 0.337425,
                        "max_internal_motion": 0.730217,
                        "person_overlap_ratio": 1.0,
                        "outside_person_ratio": 0.0,
                        "static_stack_overlap_ratio": 0.0,
                        "static_location_ratio": 0.333333,
                        "flow_coherence": 0.501419,
                        "edge_like_ratio": 0.0,
                    },
                }
            ],
            "diagnosis": [
                {
                    "track_id": 5,
                    "decision": "candidate",
                    "reason": "source_to_output_motion",
                    "flags": [],
                    "evidence": {"track_id": 5},
                }
            ],
            "track_receipts": [str(receipt_path)],
            "track_receipt_cards": ["diag/track_receipts/track-000005-sheet.jpg"],
            "overlay_sheet_path": "diag/overlay_sheet.jpg",
            "overlay_video_path": "diag/overlay_video.mp4",
            "hard_negative_manifest_path": "diag/hard_negative_manifest.json",
        },
    )


def fake_fp_evaluator(**kwargs):
    report = {
        "schema_version": "active-panel-false-positive-eval-v1",
        "model_path": str(kwargs["model_path"]),
        "data_yaml": str(kwargs["data_yaml"]),
        "confidence": kwargs["confidence"],
        "summary": {
            "hard_negative_images": 16,
            "images_with_false_positives": 0,
            "false_positive_detections": 0,
            "false_positive_image_rate": 0.0,
        },
        "items": [],
    }
    output_path = kwargs["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report), encoding="utf-8")
    return report


def fake_positive_evaluator(**kwargs):
    report = {
        "schema_version": "active-panel-positive-detector-eval-v1",
        "model_path": str(kwargs["model_path"]),
        "data_yaml": str(kwargs["data_yaml"]),
        "confidence": kwargs["confidence"],
        "iou_threshold": kwargs["iou_threshold"],
        "summary": {
            "positive_images": 8,
            "positive_labels": 8,
            "matched_labels": 8,
            "missed_labels": 0,
            "label_recall": 1.0,
            "images_with_match": 8,
            "images_with_any_detection": 8,
            "total_detections": 8,
        },
        "items": [],
    }
    output_path = kwargs["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report), encoding="utf-8")
    return report


def fake_crop_evidence_analyzer(report, *, limit):
    assert limit == 10
    return {
        "schema_version": "factory-panel-crop-evidence-v1",
        "receipt_count": 1,
        "summary": {"panel_texture_candidate_receipts": 1, "low_panel_texture_receipts": 0},
        "receipts": [{"track_id": 7, "recommendation": "inspect_as_possible_panel_texture"}],
    }


def fake_transfer_packet_builder(proof_report, output, *, repo_root, limit, force):
    assert limit == 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "factory-transfer-review-packets-v1",
                "packet_count": 1,
                "packets": [{"track_id": 5}],
            }
        ),
        encoding="utf-8",
    )
    return {"schema_version": "factory-transfer-review-packets-v1", "packet_count": 1, "packets": [{"track_id": 5}]}


def fake_person_panel_separation_analyzer(packets_report, output, *, repo_root, limit, packet_ids, force):
    assert limit == 0
    assert packet_ids is None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "factory-person-panel-separation-v1",
                "diagnostic_only": True,
                "packet_count": 1,
                "packets": [{"packet_id": "event0002-track000005", "recommendation": "countable_panel_candidate"}],
            }
        ),
        encoding="utf-8",
    )
    return {
        "schema_version": "factory-person-panel-separation-v1",
        "diagnostic_only": True,
        "packet_count": 1,
        "packets": [{"packet_id": "event0002-track000005", "recommendation": "countable_panel_candidate"}],
    }


def test_run_factory2_morning_proof_runs_eval_matrix_and_report(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_yaml = write_dataset(tmp_path)
    diagnostic = write_diagnostic(tmp_path)
    model_a = tmp_path / "models" / "panel_in_transit.pt"
    model_b = tmp_path / "models" / "other_model.pt"
    model_a.parent.mkdir(parents=True, exist_ok=True)
    model_a.write_text("model-a", encoding="utf-8")
    model_b.write_text("model-b", encoding="utf-8")

    summary = run_factory2_morning_proof(
        data_yaml=data_yaml,
        models=[model_a, model_b],
        confidences=[0.25, 0.10],
        diagnostic_paths=[diagnostic],
        report_json=tmp_path / "report.json",
        report_md=tmp_path / "report.md",
        run_summary_json=tmp_path / "run_summary.json",
        panel_crop_evidence_json=tmp_path / "panel_crop_evidence.json",
        force=True,
        fp_evaluator=fake_fp_evaluator,
        positive_evaluator=fake_positive_evaluator,
        crop_evidence_analyzer=fake_crop_evidence_analyzer,
    )

    assert summary["verdict"] == "auditable_abstention_no_trusted_positive"
    assert summary["accepted_count"] == 0
    assert summary["suppressed_count"] == 2
    assert summary["uncertain_count"] == 1
    assert summary["bottleneck"] == "perception_gate_worker_body_overlap"
    assert len(summary["fp_reports"]) == 4
    assert len(summary["positive_reports"]) == 4
    assert summary["panel_crop_evidence_report"] == str(tmp_path / "panel_crop_evidence.json")
    assert summary["panel_crop_evidence_summary"] == {"panel_texture_candidate_receipts": 1, "low_panel_texture_receipts": 0}
    assert not summary["skipped_models"]
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "panel_crop_evidence.json").exists()
    assert "Raw detector outputs are eval evidence only" in (tmp_path / "run_summary.json").read_text(encoding="utf-8")

    assert default_fp_output(model_a, 0.25).exists()
    assert default_positive_output(model_b, 0.10, 0.30).exists()


def test_run_factory2_morning_proof_builds_transfer_and_person_panel_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_yaml = write_dataset(tmp_path)
    diagnostic = write_diagnostic(tmp_path)
    model = tmp_path / "models" / "panel_in_transit.pt"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_text("model", encoding="utf-8")

    summary = run_factory2_morning_proof(
        data_yaml=data_yaml,
        models=[model],
        confidences=[0.25],
        diagnostic_paths=[diagnostic],
        report_json=tmp_path / "report.json",
        report_md=tmp_path / "report.md",
        run_summary_json=tmp_path / "run_summary.json",
        panel_crop_evidence_json=tmp_path / "panel_crop_evidence.json",
        force=True,
        fp_evaluator=fake_fp_evaluator,
        positive_evaluator=fake_positive_evaluator,
        crop_evidence_analyzer=fake_crop_evidence_analyzer,
        transfer_packet_builder=fake_transfer_packet_builder,
        person_panel_separation_analyzer=fake_person_panel_separation_analyzer,
    )

    assert summary["transfer_review_packets_report"] == "data/reports/factory2_transfer_review_packets.json"
    assert summary["person_panel_separation_report"] == "data/reports/factory2_person_panel_separation.json"
    assert (tmp_path / "data" / "reports" / "factory2_transfer_review_packets.json").exists()
    assert (tmp_path / "data" / "reports" / "factory2_person_panel_separation.json").exists()


def test_run_factory2_morning_proof_regenerates_diagnostics_before_reporting(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_yaml = write_dataset(tmp_path)
    diagnostic = write_diagnostic(tmp_path)
    model = tmp_path / "models" / "panel_in_transit.pt"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_text("model", encoding="utf-8")
    calls = []

    def fake_diagnostic_regenerator(*, diagnostic_path):
        calls.append(str(diagnostic_path))
        return json.loads(Path(diagnostic_path).read_text(encoding="utf-8"))

    run_factory2_morning_proof(
        data_yaml=data_yaml,
        models=[model],
        confidences=[0.25],
        diagnostic_paths=[diagnostic],
        report_json=tmp_path / "report.json",
        report_md=tmp_path / "report.md",
        run_summary_json=tmp_path / "run_summary.json",
        panel_crop_evidence_json=tmp_path / "panel_crop_evidence.json",
        force=True,
        fp_evaluator=fake_fp_evaluator,
        positive_evaluator=fake_positive_evaluator,
        crop_evidence_analyzer=fake_crop_evidence_analyzer,
        diagnostic_regenerator=fake_diagnostic_regenerator,
    )

    assert calls == [str(diagnostic)]


def test_run_factory2_morning_proof_refreshes_diagnostic_receipts_after_separation(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_yaml = write_dataset(tmp_path)
    diagnostic = write_worker_overlap_diagnostic(tmp_path)
    model = tmp_path / "models" / "panel_in_transit.pt"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_text("model", encoding="utf-8")

    def fake_transfer_packet_builder(proof_report, output, *, repo_root, limit, force):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"schema_version": "factory-transfer-review-packets-v1", "packet_count": 1, "packets": [{"track_id": 5}]}), encoding="utf-8")
        return {"schema_version": "factory-transfer-review-packets-v1", "packet_count": 1, "packets": [{"track_id": 5}]}

    def fake_person_panel_separation_analyzer(packets_report, output, *, repo_root, limit, packet_ids, force):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "schema_version": "factory-person-panel-separation-v1",
                    "diagnostic_only": True,
                    "packet_count": 1,
                    "packets": [{"packet_id": "event0002-track000005", "recommendation": "countable_panel_candidate"}],
                }
            ),
            encoding="utf-8",
        )
        receipt = tmp_path / "diag" / "track_receipts" / "track-000005-person-panel-separation.json"
        receipt.write_text(
            json.dumps(
                {
                    "packet_id": "event0002-track000005",
                    "diagnostic_only": True,
                    "recommendation": "countable_panel_candidate",
                    "summary": {
                        "frame_count": 3,
                        "separable_panel_candidate_frames": 3,
                        "worker_body_overlap_frames": 0,
                        "static_or_background_edge_frames": 0,
                        "max_visible_nonperson_ratio": 0.542531,
                        "max_estimated_visible_signal": 0.075512,
                    },
                    "selected_frames": [
                        {"zone": "source", "separation_decision": "separable_panel_candidate"},
                        {"zone": "source", "separation_decision": "separable_panel_candidate"},
                        {"zone": "output", "separation_decision": "separable_panel_candidate"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return {
            "schema_version": "factory-person-panel-separation-v1",
            "diagnostic_only": True,
            "packet_count": 1,
            "packets": [{"packet_id": "event0002-track000005", "recommendation": "countable_panel_candidate"}],
        }

    summary = run_factory2_morning_proof(
        data_yaml=data_yaml,
        models=[model],
        confidences=[0.25],
        diagnostic_paths=[diagnostic],
        report_json=tmp_path / "report.json",
        report_md=tmp_path / "report.md",
        run_summary_json=tmp_path / "run_summary.json",
        panel_crop_evidence_json=tmp_path / "panel_crop_evidence.json",
        force=True,
        fp_evaluator=fake_fp_evaluator,
        positive_evaluator=fake_positive_evaluator,
        crop_evidence_analyzer=fake_crop_evidence_analyzer,
        transfer_packet_builder=fake_transfer_packet_builder,
        person_panel_separation_analyzer=fake_person_panel_separation_analyzer,
    )

    assert summary["accepted_count"] == 1
    refreshed_diagnostic = json.loads(diagnostic.read_text(encoding="utf-8"))
    assert refreshed_diagnostic["perception_gate_summary"]["allowed_source_token_tracks"] == [5]
    refreshed_receipt = json.loads((tmp_path / "diag" / "track_receipts" / "track-000005.json").read_text(encoding="utf-8"))
    assert refreshed_receipt["perception_gate"]["decision"] == "allow_source_token"
    assert refreshed_receipt["perception_gate"]["reason"] == "moving_panel_candidate"


def test_run_factory2_morning_proof_skips_missing_models_but_records_them(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_yaml = write_dataset(tmp_path)
    diagnostic = write_diagnostic(tmp_path)
    present_model = tmp_path / "models" / "panel_in_transit.pt"
    missing_model = tmp_path / "models" / "missing.pt"
    present_model.parent.mkdir(parents=True, exist_ok=True)
    present_model.write_text("model", encoding="utf-8")

    summary = run_factory2_morning_proof(
        data_yaml=data_yaml,
        models=[present_model, missing_model],
        confidences=[0.25],
        diagnostic_paths=[diagnostic],
        report_json=tmp_path / "report.json",
        report_md=tmp_path / "report.md",
        run_summary_json=tmp_path / "run_summary.json",
        force=True,
        fp_evaluator=fake_fp_evaluator,
        positive_evaluator=fake_positive_evaluator,
    )

    assert len(summary["fp_reports"]) == 1
    assert len(summary["positive_reports"]) == 1
    assert summary["skipped_models"] == [{"model_path": str(missing_model), "reason": "missing_model_file"}]


def test_run_factory2_morning_proof_refuses_without_any_available_model(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_yaml = write_dataset(tmp_path)
    diagnostic = write_diagnostic(tmp_path)

    with pytest.raises(RuntimeError, match="No detector false-positive reports"):
        run_factory2_morning_proof(
            data_yaml=data_yaml,
            models=[tmp_path / "models" / "missing.pt"],
            confidences=[0.25],
            diagnostic_paths=[diagnostic],
            report_json=tmp_path / "report.json",
            report_md=tmp_path / "report.md",
            run_summary_json=tmp_path / "run_summary.json",
            force=True,
            fp_evaluator=fake_fp_evaluator,
            positive_evaluator=fake_positive_evaluator,
        )


def test_run_factory2_morning_proof_refuses_to_clobber_reports(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_yaml = write_dataset(tmp_path)
    diagnostic = write_diagnostic(tmp_path)
    model = tmp_path / "models" / "panel_in_transit.pt"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_text("model", encoding="utf-8")
    report_json = tmp_path / "report.json"
    report_json.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        run_factory2_morning_proof(
            data_yaml=data_yaml,
            models=[model],
            confidences=[0.25],
            diagnostic_paths=[diagnostic],
            report_json=report_json,
            report_md=tmp_path / "report.md",
            run_summary_json=tmp_path / "run_summary.json",
            force=False,
            fp_evaluator=fake_fp_evaluator,
            positive_evaluator=fake_positive_evaluator,
        )
