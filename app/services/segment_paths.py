"""Resolve a segment path from a segment-manifest row.

Two services (zone_tripwire, onboarding_event_proposer) used to each own a
copy of this three-line helper. Absolute paths stay as-is; relatives resolve
against the manifest directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


def resolve_segment_path(segment_manifest_path: Path, segment: Mapping[str, object]) -> Path:
    raw = Path(str(segment["path"])).expanduser()
    return raw if raw.is_absolute() else (segment_manifest_path.parent / raw).resolve()
