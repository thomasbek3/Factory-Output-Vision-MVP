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
        force=True,
        fp_evaluator=fake_fp_evaluator,
        positive_evaluator=fake_positive_evaluator,
    )

    assert summary["verdict"] == "auditable_abstention_no_trusted_positive"
    assert summary["accepted_count"] == 0
    assert summary["suppressed_count"] == 2
    assert summary["uncertain_count"] == 1
    assert summary["bottleneck"] == "perception_gate_worker_body_overlap"
    assert len(summary["fp_reports"]) == 4
    assert len(summary["positive_reports"]) == 4
    assert not summary["skipped_models"]
    assert (tmp_path / "report.json").exists()
    assert "Raw detector outputs are eval evidence only" in (tmp_path / "run_summary.json").read_text(encoding="utf-8")

    assert default_fp_output(model_a, 0.25).exists()
    assert default_positive_output(model_b, 0.10, 0.30).exists()


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
