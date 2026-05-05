from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.register_test_case import register_manifest, upsert_registry_entry


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_register_manifest_adds_manifest_to_empty_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"

    result = register_manifest(
        manifest_path=REPO_ROOT / "validation/test_cases/img3254_clean22.json",
        registry_path=registry_path,
        repo_root=REPO_ROOT,
        force=False,
        dry_run=False,
    )

    assert result["entry"]["case_id"] == "img3254_clean22_candidate"
    written = json.loads(registry_path.read_text(encoding="utf-8"))
    assert written["cases"][0]["manifest_path"] == "validation/test_cases/img3254_clean22.json"


def test_register_manifest_dry_run_does_not_write_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"

    result = register_manifest(
        manifest_path=REPO_ROOT / "validation/test_cases/img3262.json",
        registry_path=registry_path,
        repo_root=REPO_ROOT,
        force=False,
        dry_run=True,
    )

    assert result["entry"]["case_id"] == "img3262_candidate"
    assert not registry_path.exists()


def test_upsert_registry_entry_requires_force_for_existing_case() -> None:
    registry = {"schema_version": "factory-vision-validation-registry-v1", "cases": [{"case_id": "same"}]}

    with pytest.raises(FileExistsError, match="same"):
        upsert_registry_entry(registry=registry, entry={"case_id": "same"}, force=False)

    updated = upsert_registry_entry(registry=registry, entry={"case_id": "same", "status": "ok"}, force=True)
    assert updated["cases"] == [{"case_id": "same", "status": "ok"}]
