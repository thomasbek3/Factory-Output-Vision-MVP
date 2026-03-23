from dataclasses import dataclass
from urllib.parse import quote

from app.core.settings import get_demo_video_path, is_demo_mode
from app.db.config_repo import get_config


@dataclass(frozen=True)
class SourceSelection:
    is_demo: bool
    source: str
    candidates: tuple[str, ...]


def _build_rtsp_candidates(*, camera_ip: str, username: str, password: str, stream_profile: str) -> tuple[str, ...]:
    profile = "sub" if stream_profile == "sub" else "main"
    user = quote(username, safe="")
    pw = quote(password, safe="")
    base = f"rtsp://{user}:{pw}@{camera_ip}:554"
    preferred = f"{base}/h264Preview_01_{profile}"
    alternate_profile = "main" if profile == "sub" else "sub"

    candidates = [
        preferred,
        f"{base}/h264Preview_01_{alternate_profile}",
        f"{base}/Preview_01_{profile}",
        f"{base}/cam/realmonitor?channel=1&subtype={1 if profile == 'sub' else 0}",
        f"{base}/live0",
    ]

    deduped: list[str] = []
    for c in candidates:
        if c not in deduped:
            deduped.append(c)
    return tuple(deduped)


def get_active_source() -> SourceSelection:
    if is_demo_mode():
        demo_path = get_demo_video_path()
        if not demo_path or not demo_path.exists():
            raise RuntimeError("Demo mode is enabled but FC_DEMO_VIDEO_PATH is missing or invalid")
        src = str(demo_path)
        return SourceSelection(is_demo=True, source=src, candidates=(src,))

    config = get_config()
    required = [config.get("camera_ip"), config.get("camera_username"), config.get("camera_password")]
    if not all(required):
        raise RuntimeError("Camera is not configured")

    stream_profile = str(config.get("stream_profile") or "sub")
    candidates = _build_rtsp_candidates(
        camera_ip=str(config["camera_ip"]),
        username=str(config["camera_username"]),
        password=str(config["camera_password"]),
        stream_profile=stream_profile,
    )
    return SourceSelection(is_demo=False, source=candidates[0], candidates=candidates)
