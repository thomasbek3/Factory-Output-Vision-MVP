"""Tests for shared segment-path resolution."""

from __future__ import annotations

from pathlib import Path

from app.services.segment_paths import resolve_segment_path


def test_absolute_path_is_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"x")
    resolved = resolve_segment_path(tmp_path / "manifest.json", {"path": str(target)})
    assert resolved == target


def test_relative_path_resolves_against_manifest_dir(tmp_path: Path) -> None:
    manifest = tmp_path / "day" / "segments.json"
    manifest.parent.mkdir()
    clip = tmp_path / "day" / "clips" / "a.mp4"
    clip.parent.mkdir()
    clip.write_bytes(b"x")
    resolved = resolve_segment_path(manifest, {"path": "clips/a.mp4"})
    assert resolved == clip.resolve()
