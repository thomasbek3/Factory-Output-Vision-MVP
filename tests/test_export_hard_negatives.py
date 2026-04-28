import json
from pathlib import Path

import pytest

from scripts import export_hard_negatives as exporter


def _write_manifest(tmp_path: Path, *, label: str = "hard_negative", asset_name: str = "track.jpg") -> Path:
    asset = tmp_path / asset_name
    asset.write_text("image-ish", encoding="utf-8")
    manifest = tmp_path / "hard_negative_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "factory-hard-negative-manifest-v1",
                "source": "diagnose_event_window",
                "count": 1,
                "items": [
                    {
                        "track_id": 7,
                        "label": label,
                        "reason": "worker_body_overlap",
                        "assets": {"track_sheet_path": str(asset)},
                        "evidence": {"person_overlap_ratio": 1.0},
                        "gate_decision": {"decision": "reject", "reason": "worker_body_overlap"},
                        "diagnosis": {"decision": "uncertain", "reason": "source_without_output_settle"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_load_hard_negative_manifest_validates_schema(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "wrong", "items": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported"):
        exporter.load_hard_negative_manifest(bad)


def test_export_writes_review_manifest_without_copying_images_by_default(tmp_path):
    manifest = _write_manifest(tmp_path)
    out_dir = tmp_path / "export"

    export_path = exporter.export_hard_negatives(
        manifest_paths=[manifest],
        out_dir=out_dir,
        force=False,
    )

    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "factory-hard-negative-export-v1"
    assert payload["count"] == 1
    row = payload["items"][0]
    assert row["negative_id"].endswith("track-000007-hard-negative-worker-body-overlap")
    assert row["source_asset_path"].endswith("track.jpg")
    assert row["exported_image_path"] is None
    assert row["exported_label_path"] is None
    assert row["review_only"] is True


def test_export_can_write_empty_yolo_negative_labels(tmp_path):
    manifest = _write_manifest(tmp_path)
    out_dir = tmp_path / "export"

    export_path = exporter.export_hard_negatives(
        manifest_paths=[manifest],
        out_dir=out_dir,
        split="val",
        write_yolo_negatives=True,
        force=False,
    )

    payload = json.loads(export_path.read_text(encoding="utf-8"))
    row = payload["items"][0]
    image_path = Path(row["exported_image_path"])
    label_path = Path(row["exported_label_path"])
    assert image_path.exists()
    assert image_path.read_text(encoding="utf-8") == "image-ish"
    assert label_path.exists()
    assert label_path.read_text(encoding="utf-8") == ""


def test_uncertain_negatives_are_filtered_unless_requested(tmp_path):
    manifest = _write_manifest(tmp_path, label="uncertain_negative")

    first = exporter.export_hard_negatives(
        manifest_paths=[manifest],
        out_dir=tmp_path / "hard-only",
        force=False,
    )
    second = exporter.export_hard_negatives(
        manifest_paths=[manifest],
        out_dir=tmp_path / "with-uncertain",
        include_uncertain=True,
        force=False,
    )

    assert json.loads(first.read_text(encoding="utf-8"))["count"] == 0
    assert json.loads(second.read_text(encoding="utf-8"))["count"] == 1


def test_export_refuses_non_empty_output_without_force(tmp_path):
    manifest = _write_manifest(tmp_path)
    out_dir = tmp_path / "export"
    out_dir.mkdir()
    (out_dir / "old.txt").write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing"):
        exporter.export_hard_negatives(manifest_paths=[manifest], out_dir=out_dir, force=False)
