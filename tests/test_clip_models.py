from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.services.clip_models import (
    ARCHES,
    arch_availability,
    create_model,
    encodings_for_arch,
    load_student_judge,
    labeled_rows,
    train_student,
    write_synthetic_clip_manifest,
)
from app.services.training_exam_guard import sha256_file
from scripts.train_clip_student import synthetic_smoke_image_size


def test_arch_availability_reports_optional_dependency_skips() -> None:
    statuses = arch_availability()

    assert set(statuses) == set(ARCHES)
    if importlib.util.find_spec("torch") and importlib.util.find_spec("torchvision"):
        assert statuses["video_x3d"].available
    else:
        assert not statuses["video_x3d"].available
        assert "requires" in statuses["video_x3d"].reason
    if (
        importlib.util.find_spec("torch")
        and importlib.util.find_spec("transformers")
        and importlib.util.find_spec("timm")
    ):
        assert statuses["video_vmae"].available
    else:
        assert not statuses["video_vmae"].available
        assert "requires" in statuses["video_vmae"].reason
    for name, status in statuses.items():
        if not status.available:
            assert status.reason
            assert "requires" in status.reason


def test_cli_synthetic_smoke_uses_video_sized_frames_for_video_archs() -> None:
    assert synthetic_smoke_image_size("stack3_mobilenet") == 32
    assert synthetic_smoke_image_size("twostream") == 32
    assert synthetic_smoke_image_size("video_x3d") == 64
    assert synthetic_smoke_image_size("video_vmae") == 64
    assert synthetic_smoke_image_size("all") == 64


def test_exam_encoding_mapping_matches_student_arch_inputs() -> None:
    assert encodings_for_arch("stack3_mobilenet") == ("stack3",)
    assert encodings_for_arch("twostream") == ("stack3", "flow")
    assert encodings_for_arch("video_x3d") == ("clip",)
    assert encodings_for_arch("video_vmae") == ("clip",)


def test_student_judge_missing_candidate_path_names_candidate_and_key(tmp_path: Path) -> None:
    import torch

    model_path = tmp_path / "stack3_mobilenet.pt"
    model = create_model("stack3_mobilenet", pretrained=False)
    torch.save(
        {
            "arch": "stack3_mobilenet",
            "state_dict": model.state_dict(),
            "flow_channels": 30,
            "pretrained": False,
        },
        model_path,
    )
    judge = load_student_judge(model_path=model_path)

    with pytest.raises(ValueError, match="candidate pathless-1 missing required path: stack3"):
        judge({"candidate_id": "pathless-1"})


def test_student_judge_uses_cli_arch_fallback_for_legacy_bundle(tmp_path: Path) -> None:
    import torch

    model_path = tmp_path / "legacy_stack3_mobilenet.pt"
    model = create_model("stack3_mobilenet", pretrained=False)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "flow_channels": 30,
            "pretrained": False,
        },
        model_path,
    )

    judge = load_student_judge(model_path=model_path, arch="stack3_mobilenet")

    assert callable(judge)


def test_each_available_arch_runs_one_epoch_synthetic_smoke_train(tmp_path: Path) -> None:
    statuses = arch_availability()

    for arch, status in statuses.items():
        manifest_path = tmp_path / arch / "manifest.json"
        image_size = 64 if arch in {"video_x3d", "video_vmae"} else 32
        write_synthetic_clip_manifest(manifest_path, sample_count=4, image_size=image_size)
        result = train_student(
            manifest_path=manifest_path,
            arch=arch,
            out_dir=tmp_path / arch / "models",
            epochs=1,
            batch_size=2,
            device="cpu",
            pretrained=False,
        )
        if status.available:
            assert result["status"] == "trained"
            assert Path(result["model_path"]).exists()
            assert result["metrics"]["validation_samples"] >= 1
        else:
            assert result["status"] == "skipped"
            assert result["reason"] == status.reason


def test_manifest_cannot_self_declare_synthetic_smoke_to_bypass_firewall(tmp_path: Path) -> None:
    source = tmp_path / "protected.mp4"
    source.write_bytes(b"protected-source")
    source_sha256 = sha256_file(source)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "purpose": "synthetic_smoke",
                "samples": [
                    {
                        "source": str(source),
                        "source_sha256": source_sha256,
                        "lineage_source_sha256": [source_sha256],
                        "lineage_is_transitive_complete": True,
                        "training_eligible": False,
                        "start_at": "2026-07-25T12:00:00Z",
                        "end_at": "2026-07-25T12:01:00Z",
                        "label": "assert",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="training-ineligible"):
        labeled_rows(manifest_path)
