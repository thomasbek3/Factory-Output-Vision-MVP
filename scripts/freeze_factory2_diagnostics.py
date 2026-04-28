#!/usr/bin/env python3
"""Freeze diagnostic directories into isolated copies for merged proof runs."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "factory-frozen-diagnostics-v1"


def _path_prefix_variants(path: Path) -> list[str]:
    variants = {str(path), path.as_posix()}
    try:
        cwd = Path.cwd().resolve()
        resolved = path.resolve()
        variants.add(str(resolved.relative_to(cwd)).replace("\\", "/"))
    except ValueError:
        pass
    return sorted((value for value in variants if value), key=len, reverse=True)


def _rewrite_string(value: str, replacements: list[tuple[str, str]]) -> str:
    for source_prefix, dest_prefix in replacements:
        if value.startswith(source_prefix):
            suffix = value[len(source_prefix) :]
            return f"{dest_prefix}{suffix}"
    return value


def _rewrite_payload_paths(payload: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(payload, dict):
        return {key: _rewrite_payload_paths(value, replacements) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_rewrite_payload_paths(item, replacements) for item in payload]
    if isinstance(payload, str):
        return _rewrite_string(payload, replacements)
    return payload


def _rewrite_json_tree_paths(*, source_dir: Path, frozen_dir: Path) -> None:
    source_variants = _path_prefix_variants(source_dir)
    frozen_variants = _path_prefix_variants(frozen_dir)
    replacements: list[tuple[str, str]] = []
    for source_prefix, dest_prefix in zip(source_variants, frozen_variants):
        replacements.append((source_prefix, dest_prefix))
    for source_prefix in source_variants:
        for dest_prefix in frozen_variants:
            if (source_prefix, dest_prefix) not in replacements:
                replacements.append((source_prefix, dest_prefix))

    for json_path in frozen_dir.rglob("*.json"):
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        rewritten = _rewrite_payload_paths(payload, replacements)
        json_path.write_text(json.dumps(rewritten, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def freeze_diagnostics(
    *,
    diagnostic_paths: Iterable[Path],
    output_root: Path,
    force: bool,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    rows: list[dict[str, str]] = []

    for diagnostic_path in diagnostic_paths:
        source_diagnostic = Path(diagnostic_path).resolve()
        if not source_diagnostic.exists():
            raise FileNotFoundError(source_diagnostic)
        source_dir = source_diagnostic.parent
        frozen_dir = output_root / source_dir.name
        if frozen_dir.exists():
            if not force:
                raise FileExistsError(frozen_dir)
            shutil.rmtree(frozen_dir)
        frozen_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, frozen_dir)
        _rewrite_json_tree_paths(source_dir=source_dir, frozen_dir=frozen_dir)
        rows.append(
            {
                "source_diagnostic_path": str(source_diagnostic),
                "source_directory": str(source_dir),
                "frozen_diagnostic_path": str(frozen_dir / source_diagnostic.name),
                "frozen_directory": str(frozen_dir),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "output_root": str(output_root),
        "diagnostics": rows,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze Factory2 diagnostics into isolated copies.")
    parser.add_argument("--diagnostic", action="append", dest="diagnostics", required=True, help="diagnostic.json path; may repeat")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = freeze_diagnostics(
        diagnostic_paths=[Path(value) for value in args.diagnostics],
        output_root=args.output_root,
        force=args.force,
    )
    output_manifest = args.output_manifest or (args.output_root / "frozen_diagnostics_manifest.json")
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
