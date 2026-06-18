from __future__ import annotations

from pathlib import Path

from app.services.clip_models import ARCHES, arch_availability, train_student, write_synthetic_clip_manifest
from scripts.train_clip_student import synthetic_smoke_image_size


def test_arch_availability_reports_optional_dependency_skips() -> None:
    statuses = arch_availability()

    assert set(statuses) == set(ARCHES)
    assert statuses["video_x3d"].available
    assert statuses["video_vmae"].available
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
