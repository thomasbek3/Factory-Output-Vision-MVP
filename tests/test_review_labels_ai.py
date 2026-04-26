import json

from scripts import review_labels_ai


def test_review_labels_manifest_separates_decision_buckets(tmp_path):
    manifest_path = tmp_path / "labels_manifest.json"
    output_path = tmp_path / "reviewed_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "labels": [
                    {
                        "label_id": "good",
                        "frame_id": "frame-001",
                        "image_width": 1000,
                        "image_height": 800,
                        "class_name": "active_panel",
                        "box": [200, 160, 520, 420],
                        "confidence": 0.94,
                        "source_type": "box",
                    },
                    {
                        "label_id": "fixed",
                        "frame_id": "frame-002",
                        "image_width": 640,
                        "image_height": 480,
                        "class_name": "active_panel",
                        "polygon": [[-8, 10], [100, 6], [120, 90], [12, 96]],
                        "confidence": 0.88,
                        "source_type": "polygon",
                    },
                    {
                        "label_id": "static-stack",
                        "frame_id": "frame-003",
                        "image_width": 1000,
                        "image_height": 800,
                        "class_name": "active_panel",
                        "box": [80, 120, 500, 500],
                        "confidence": 0.91,
                        "source_type": "box",
                        "metadata": {"static_stack": True},
                    },
                    {
                        "label_id": "jump",
                        "frame_id": "frame-011",
                        "image_width": 1000,
                        "image_height": 800,
                        "class_name": "active_panel",
                        "box": [720, 510, 920, 690],
                        "confidence": 0.86,
                        "source_type": "box",
                        "previous_label": {
                            "label_id": "frame-010-panel-1",
                            "frame_id": "frame-010",
                            "image_width": 1000,
                            "image_height": 800,
                            "class_name": "active_panel",
                            "box": [200, 180, 400, 360],
                            "confidence": 0.92,
                            "source_type": "box",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = review_labels_ai.main([str(manifest_path), "--output", str(output_path)])

    assert exit_code == 0
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["labels"][0]["label_id"] == "good"
    reviewed = json.loads(output_path.read_text(encoding="utf-8"))
    assert [item["label_id"] for item in reviewed["accepted"]] == ["good"]
    assert [item["label_id"] for item in reviewed["fixed"]] == ["fixed"]
    assert reviewed["fixed"][0]["fixed_label"]["box"] == [0, 6, 120, 96]
    assert [item["label_id"] for item in reviewed["rejected"]] == ["static-stack"]
    assert [item["label_id"] for item in reviewed["uncertain"]] == ["jump"]
    assert reviewed["review_cards"][0]["ai_reviewer_contract"]["schema_version"] == "label-quality-v1"


def test_reviewed_manifest_exports_only_accept_and_fix_as_trainable_labels(tmp_path):
    manifest_path = tmp_path / "labels_manifest.json"
    output_path = tmp_path / "reviewed_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "labels": [
                    {
                        "label_id": "good",
                        "frame_id": "frame-001",
                        "image_width": 1000,
                        "image_height": 800,
                        "class_name": "active_panel",
                        "box": [200, 160, 520, 420],
                        "confidence": 0.94,
                        "source_type": "box",
                    },
                    {
                        "label_id": "fixed",
                        "frame_id": "frame-002",
                        "image_width": 640,
                        "image_height": 480,
                        "class_name": "active_panel",
                        "polygon": [[-8, 10], [100, 6], [120, 90], [12, 96]],
                        "confidence": 0.88,
                        "source_type": "polygon",
                    },
                    {
                        "label_id": "rejected",
                        "frame_id": "frame-003",
                        "image_width": 1000,
                        "image_height": 800,
                        "class_name": "active_panel",
                        "box": [80, 120, 500, 500],
                        "confidence": 0.91,
                        "source_type": "box",
                        "metadata": {"static_stack": True},
                    },
                    {
                        "label_id": "uncertain",
                        "frame_id": "frame-004",
                        "image_width": 1000,
                        "image_height": 800,
                        "class_name": "active_panel",
                        "box": [200, 160, 520, 420],
                        "confidence": 0.40,
                        "source_type": "box",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = review_labels_ai.main([str(manifest_path), "--output", str(output_path)])

    assert exit_code == 0
    reviewed = json.loads(output_path.read_text(encoding="utf-8"))
    assert [item["label_id"] for item in reviewed["trainable_labels"]] == ["good", "fixed"]
    assert reviewed["accepted"][0]["training_eligible"] is True
    assert reviewed["fixed"][0]["training_eligible"] is True
    assert reviewed["rejected"][0]["training_eligible"] is False
    assert reviewed["uncertain"][0]["training_eligible"] is False
    assert reviewed["trainable_labels"][1]["box"] == [0, 6, 120, 96]


def test_trainable_export_includes_box_for_accepted_polygon_labels(tmp_path):
    manifest_path = tmp_path / "labels_manifest.json"
    output_path = tmp_path / "reviewed_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "labels": [
                    {
                        "label_id": "poly-good",
                        "frame_id": "frame-005",
                        "image_width": 640,
                        "image_height": 480,
                        "class_name": "active_panel",
                        "polygon": [[10, 20], [110, 20], [110, 90], [10, 90]],
                        "confidence": 0.95,
                        "source_type": "polygon",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = review_labels_ai.main([str(manifest_path), "--output", str(output_path)])

    assert exit_code == 0
    reviewed = json.loads(output_path.read_text(encoding="utf-8"))
    assert reviewed["trainable_labels"] == [
        {
            "label_id": "poly-good",
            "frame_id": "frame-005",
            "image_width": 640,
            "image_height": 480,
            "class_name": "active_panel",
            "confidence": 0.95,
            "source_type": "polygon",
            "box": [10, 20, 110, 90],
            "polygon": [[10, 20], [110, 20], [110, 90], [10, 90]],
        }
    ]
