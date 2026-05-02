import json
from pathlib import Path

import pytest

from scripts import assemble_active_panel_dataset as assembler


def _write_reviewed_manifest(tmp_path: Path) -> Path:
    image = tmp_path / "positive.jpg"
    image.write_text("positive-image", encoding="utf-8")
    path = tmp_path / "reviewed.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "label-quality-reviewed-v1",
                "trainable_labels": [
                    {
                        "label_id": "good-panel",
                        "frame_id": "frame-001",
                        "image_width": 100,
                        "image_height": 50,
                        "class_name": "active_panel",
                        "box": [10, 5, 50, 25],
                        "metadata": {"frame_path": str(image)},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_hard_negative_export(tmp_path: Path) -> Path:
    image = tmp_path / "negative.jpg"
    image.write_text("negative-image", encoding="utf-8")
    path = tmp_path / "hard_negative_export.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-hard-negative-export-v1",
                "count": 1,
                "items": [
                    {
                        "negative_id": "track-7-worker-body",
                        "reason": "worker_body_overlap",
                        "split": "train",
                        "source_asset_path": str(image),
                        "exported_image_path": str(image),
                        "review_only": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_yolo_line_from_xyxy_normalizes_box() -> None:
    assert assembler.yolo_line_from_xyxy([10, 5, 50, 25], width=100, height=50) == "0 0.300000 0.300000 0.400000 0.400000"


def test_assemble_dataset_writes_positive_and_empty_negative_labels(tmp_path: Path) -> None:
    reviewed = _write_reviewed_manifest(tmp_path)
    negatives = _write_hard_negative_export(tmp_path)
    out_dir = tmp_path / "dataset"

    manifest_path = assembler.assemble_dataset(
        out_dir=out_dir,
        reviewed_label_manifest=reviewed,
        hard_negative_export=negatives,
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "active-panel-yolo-dataset-v1"
    assert payload["summary"] == {
        "empty_negative_labels": 1,
        "hard_negative_count": 1,
        "positive_count": 1,
        "total_images": 2,
    }
    positive = next(item for item in payload["items"] if item["kind"] == "positive")
    negative = next(item for item in payload["items"] if item["kind"] == "hard_negative")
    assert Path(positive["image_path"]).read_text(encoding="utf-8") == "positive-image"
    assert Path(positive["label_path"]).read_text(encoding="utf-8") == "0 0.300000 0.300000 0.400000 0.400000\n"
    assert Path(negative["image_path"]).read_text(encoding="utf-8") == "negative-image"
    assert Path(negative["label_path"]).read_text(encoding="utf-8") == ""
    assert (out_dir / "data.yaml").read_text(encoding="utf-8").startswith("path: .\ntrain: images/train")


def test_assemble_dataset_honors_positive_split_metadata(tmp_path: Path) -> None:
    image = tmp_path / "positive-val.jpg"
    image.write_text("positive-val-image", encoding="utf-8")
    reviewed = tmp_path / "reviewed-val.json"
    reviewed.write_text(
        json.dumps(
            {
                "schema_version": "label-quality-reviewed-v1",
                "trainable_labels": [
                    {
                        "label_id": "good-panel-val",
                        "frame_id": "frame-val",
                        "image_width": 100,
                        "image_height": 50,
                        "class_name": "active_panel",
                        "box": [10, 5, 50, 25],
                        "metadata": {"frame_path": str(image), "split": "val"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest_path = assembler.assemble_dataset(
        out_dir=tmp_path / "dataset",
        reviewed_label_manifest=reviewed,
        hard_negative_export=None,
    )

    positive = json.loads(manifest_path.read_text(encoding="utf-8"))["items"][0]
    assert positive["split"] == "val"
    assert "/images/val/" in positive["image_path"]
    assert "/labels/val/" in positive["label_path"]


def test_refuses_negative_only_dataset_unless_explicit(tmp_path: Path) -> None:
    negatives = _write_hard_negative_export(tmp_path)

    with pytest.raises(ValueError, match="No reviewed positive labels"):
        assembler.assemble_dataset(
            out_dir=tmp_path / "dataset",
            reviewed_label_manifest=None,
            hard_negative_export=negatives,
        )

    manifest = assembler.assemble_dataset(
        out_dir=tmp_path / "dataset-negative-only",
        reviewed_label_manifest=None,
        hard_negative_export=negatives,
        allow_negative_only=True,
    )
    assert json.loads(manifest.read_text(encoding="utf-8"))["summary"]["hard_negative_count"] == 1


def test_refuses_to_overwrite_non_empty_dataset(tmp_path: Path) -> None:
    reviewed = _write_reviewed_manifest(tmp_path)
    out_dir = tmp_path / "dataset"
    out_dir.mkdir()
    (out_dir / "old.txt").write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing"):
        assembler.assemble_dataset(out_dir=out_dir, reviewed_label_manifest=reviewed, hard_negative_export=None)
