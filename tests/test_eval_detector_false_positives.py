import json
from pathlib import Path

import pytest

from scripts import eval_detector_false_positives as fp_eval


def _write_dataset(tmp_path: Path) -> Path:
    out_dir = tmp_path / "dataset"
    (out_dir / "images" / "train").mkdir(parents=True)
    (out_dir / "labels" / "train").mkdir(parents=True)
    neg_image = out_dir / "images" / "train" / "neg-worker.jpg"
    pos_image = out_dir / "images" / "train" / "pos-panel.jpg"
    neg_label = out_dir / "labels" / "train" / "neg-worker.txt"
    pos_label = out_dir / "labels" / "train" / "pos-panel.txt"
    neg_image.write_text("negative", encoding="utf-8")
    pos_image.write_text("positive", encoding="utf-8")
    neg_label.write_text("", encoding="utf-8")
    pos_label.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    data_yaml = out_dir / "data.yaml"
    data_yaml.write_text(
        "path: .\ntrain: images/train\nval: images/val\nnames:\n  0: active_panel\n",
        encoding="utf-8",
    )
    manifest = out_dir / "dataset_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "active-panel-yolo-dataset-v1",
                "items": [
                    {
                        "kind": "hard_negative",
                        "negative_id": "neg-worker",
                        "reason": "worker_body_overlap",
                        "image_path": str(neg_image),
                        "label_path": str(neg_label),
                        "split": "train",
                    },
                    {
                        "kind": "positive",
                        "image_path": str(pos_image),
                        "label_path": str(pos_label),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return data_yaml


def test_loads_hard_negatives_from_dataset_manifest_next_to_data_yaml(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)

    rows = fp_eval.load_negative_items(data_yaml=data_yaml, dataset_manifest=None)

    assert len(rows) == 1
    assert rows[0]["negative_id"] == "neg-worker"
    assert rows[0]["reason"] == "worker_body_overlap"


def test_scans_empty_labels_when_manifest_is_missing(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)
    (data_yaml.parent / "dataset_manifest.json").unlink()

    rows = fp_eval.load_negative_items(data_yaml=data_yaml, dataset_manifest=None)

    assert len(rows) == 1
    assert rows[0]["negative_id"] == "neg-worker"
    assert Path(rows[0]["image_path"]).name == "neg-worker.jpg"


def test_evaluate_false_positives_writes_receipt_report(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)
    output = tmp_path / "fp_report.json"

    def fake_detector(*, image_paths: list[Path], model_path: Path, confidence: float):
        assert model_path == Path("models/panel_in_transit.pt")
        assert confidence == 0.4
        return {
            str(image_paths[0]): [
                {
                    "box": [1, 2, 20, 30],
                    "confidence": 0.7,
                    "class_index": 0,
                    "class_name": "active_panel",
                },
                {"box": [3, 4, 5, 6], "confidence": 0.1, "class_index": 0, "class_name": "active_panel"},
            ]
        }

    report = fp_eval.evaluate_false_positives(
        data_yaml=data_yaml,
        dataset_manifest=None,
        model_path=Path("models/panel_in_transit.pt"),
        output_path=output,
        confidence=0.4,
        detector_runner=fake_detector,
    )

    assert report["schema_version"] == "active-panel-false-positive-eval-v1"
    assert report["summary"] == {
        "false_positive_detections": 1,
        "false_positive_image_rate": 1.0,
        "hard_negative_images": 1,
        "images_with_false_positives": 1,
    }
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["items"][0]["detections"][0]["confidence"] == 0.7


def test_refuses_to_overwrite_existing_report(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)
    output = tmp_path / "fp_report.json"
    output.write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        fp_eval.evaluate_false_positives(
            data_yaml=data_yaml,
            dataset_manifest=None,
            model_path=Path("model.pt"),
            output_path=output,
            detector_runner=lambda **kwargs: {},
        )
