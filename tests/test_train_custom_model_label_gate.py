import json

import pytest

import train_custom_model


def test_validate_reviewed_label_gate_accepts_trainable_reviewed_labels(tmp_path):
    manifest_path = tmp_path / "reviewed.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "label-quality-reviewed-v1",
                "trainable_labels": [{"label_id": "good", "box": [1, 2, 3, 4]}],
                "accepted": [{"label_id": "good", "training_eligible": True}],
                "fixed": [],
                "rejected": [],
                "uncertain": [],
            }
        ),
        encoding="utf-8",
    )

    summary = train_custom_model.validate_reviewed_label_gate(manifest_path)

    assert summary == {"trainable": 1, "blocked": 0}


def test_validate_reviewed_label_gate_blocks_unreviewed_or_empty_manifest(tmp_path):
    manifest_path = tmp_path / "reviewed.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "label-quality-reviewed-v1",
                "trainable_labels": [],
                "accepted": [],
                "fixed": [],
                "rejected": [{"label_id": "bad", "training_eligible": False}],
                "uncertain": [{"label_id": "hmm", "training_eligible": False}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No AI-reviewed trainable labels"):
        train_custom_model.validate_reviewed_label_gate(manifest_path)


def test_validate_reviewed_label_gate_rejects_bad_schema(tmp_path):
    manifest_path = tmp_path / "reviewed.json"
    manifest_path.write_text(json.dumps({"labels": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="label-quality-reviewed-v1"):
        train_custom_model.validate_reviewed_label_gate(manifest_path)


def test_resolve_reviewed_label_gate_requires_manifest_unless_explicitly_bypassed():
    with pytest.raises(ValueError, match="AI label QA manifest is required"):
        train_custom_model.resolve_reviewed_label_gate(None, allow_unreviewed_labels=False)

    assert train_custom_model.resolve_reviewed_label_gate(
        None,
        allow_unreviewed_labels=True,
    ) is None