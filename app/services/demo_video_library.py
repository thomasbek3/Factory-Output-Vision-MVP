from __future__ import annotations

import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.settings import get_demo_video_library_dir, get_demo_video_path

_ACTIVE_DEMO_FILENAME = ".active_demo_video"
_ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mjpg", ".mjpeg"}


def ensure_demo_video_library() -> Path:
    library_dir = get_demo_video_library_dir()
    library_dir.mkdir(parents=True, exist_ok=True)
    return library_dir


def _active_demo_pointer_path() -> Path:
    return ensure_demo_video_library() / _ACTIVE_DEMO_FILENAME


def _sanitize_filename(filename: str) -> str:
    candidate = Path(filename).name.strip()
    if not candidate:
        raise ValueError("Uploaded file needs a valid filename")
    if Path(candidate).suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise ValueError("Only common video formats are supported for demo uploads")
    stem = Path(candidate).stem.strip()
    if not stem:
        raise ValueError("Uploaded file needs a valid filename")
    return f"{stem}.mp4"


def _unique_destination(filename: str) -> Path:
    library_dir = ensure_demo_video_library()
    destination = library_dir / filename
    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    counter = 1
    while True:
        candidate = library_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _transcode_upload_to_mp4(source: Path, destination: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not destination.exists():
        destination.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "").strip()
        if detail:
            raise RuntimeError(f"Unable to convert uploaded video into demo MP4: {detail}")
        raise RuntimeError("Unable to convert uploaded video into demo MP4")


def save_demo_video_upload(upload: UploadFile) -> Path:
    filename = _sanitize_filename(upload.filename or "")
    destination = _unique_destination(filename)
    source_suffix = Path(upload.filename or "").suffix or ".bin"
    temp_source = ensure_demo_video_library() / f".upload_{uuid4().hex}{source_suffix}"
    try:
        with temp_source.open("wb") as output:
            shutil.copyfileobj(upload.file, output)
        _transcode_upload_to_mp4(temp_source, destination)
        return destination.resolve()
    finally:
        temp_source.unlink(missing_ok=True)


def set_active_demo_video(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Demo video not found: {resolved}")
    pointer = _active_demo_pointer_path()
    pointer.write_text(str(resolved), encoding="utf-8")
    return resolved


def get_active_demo_video() -> Path | None:
    pointer = _active_demo_pointer_path()
    if pointer.exists():
        raw = pointer.read_text(encoding="utf-8").strip()
        if raw:
            candidate = Path(raw).expanduser().resolve()
            if candidate.exists():
                return candidate
    fallback = get_demo_video_path()
    if fallback and fallback.exists():
        return fallback
    return None


def list_demo_videos() -> list[dict[str, object]]:
    library_dir = ensure_demo_video_library()
    active = get_active_demo_video()
    items: list[dict[str, object]] = []

    seen: set[Path] = set()
    for path in sorted(library_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.name == _ACTIVE_DEMO_FILENAME:
            continue
        if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
            continue
        seen.add(path.resolve())
        items.append(_video_item(path.resolve(), active))

    if active is not None and active.resolve() not in seen:
        items.insert(0, _video_item(active.resolve(), active))

    return items


def _video_item(path: Path, active: Path | None) -> dict[str, object]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "selected": bool(active and path.resolve() == active.resolve()),
        "managed": path.parent.resolve() == ensure_demo_video_library().resolve(),
    }
