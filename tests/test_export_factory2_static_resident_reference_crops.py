from __future__ import annotations

import json
from pathlib import Path

from scripts import export_factory2_static_resident_reference_crops as exporter


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_image(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_export_static_resident_reference_crops_copies_static_stack_edge_receipts(tmp_path: Path) -> None:
    static_a = _write_image(tmp_path / "diag-a" / "crop-01-output.jpg", b"static-a")
    static_b = _write_image(tmp_path / "diag-b" / "crop-01-output.jpg", b"static-b")
    proof_report = _write_json(
        tmp_path / "proof_report.json",
        {
            "schema_version": "factory2-proof-report-v1",
            "decision_receipt_index": {
                "suppressed": [
                    {
                        "diagnostic_path": "diag-a/diagnostic.json",
                        "track_id": 3,
                        "decision": "reject",
                        "reason": "static_stack_edge",
                        "raw_crop_paths": [str(static_a)],
                        "receipt_json_path": "diag-a/track-000003.json",
                        "receipt_timestamps": {"first": 306.9, "last": 306.9},
                    },
                    {
                        "diagnostic_path": "diag-b/diagnostic.json",
                        "track_id": 6,
                        "decision": "reject",
                        "reason": "static_stack_edge",
                        "raw_crop_paths": [str(static_b)],
                        "receipt_json_path": "diag-b/track-000006.json",
                        "receipt_timestamps": {"first": 424.833, "last": 424.833},
                    },
                ]
            },
        },
    )
    output_report = tmp_path / "out" / "static_refs.json"
    dataset_dir = tmp_path / "out" / "dataset"

    result = exporter.export_static_resident_reference_crops(
        proof_report_path=proof_report,
        output_report_path=output_report,
        dataset_dir=dataset_dir,
        force=False,
    )

    assert result["schema_version"] == "factory2-static-resident-reference-crops-v1"
    assert result["candidate_count"] == 2
    assert result["items"][0]["label_placeholder"]["relation_label"] == "static_resident"
    assert Path(result["items"][0]["exported_crop_path"]).read_bytes() == b"static-a"
    assert Path(result["items"][1]["exported_crop_path"]).read_bytes() == b"static-b"
    assert json.loads(output_report.read_text(encoding="utf-8")) == result


def test_export_static_resident_reference_crops_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    static_crop = _write_image(tmp_path / "diag" / "crop.jpg", b"static")
    proof_report = _write_json(
        tmp_path / "proof_report.json",
        {
            "schema_version": "factory2-proof-report-v1",
            "decision_receipt_index": {
                "suppressed": [
                    {
                        "diagnostic_path": "diag/diagnostic.json",
                        "track_id": 3,
                        "decision": "reject",
                        "reason": "static_stack_edge",
                        "raw_crop_paths": [str(static_crop)],
                        "receipt_json_path": "diag/track-000003.json",
                        "receipt_timestamps": {"first": 1.0, "last": 1.0},
                    }
                ]
            },
        },
    )

    exporter.export_static_resident_reference_crops(
        proof_report_path=proof_report,
        output_report_path=tmp_path / "out" / "static_refs.json",
        dataset_dir=tmp_path / "out" / "dataset",
        force=False,
    )

    try:
        exporter.export_static_resident_reference_crops(
            proof_report_path=proof_report,
            output_report_path=tmp_path / "out" / "static_refs.json",
            dataset_dir=tmp_path / "out" / "dataset",
            force=False,
        )
    except FileExistsError:
        return
    raise AssertionError("expected FileExistsError")
