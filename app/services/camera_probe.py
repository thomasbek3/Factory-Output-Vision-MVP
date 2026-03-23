import json
import subprocess
from typing import Any


def ffprobe_stream(source: str) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-select_streams",
        "v:0",
        "-of",
        "json",
        source,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams", [])
    if not streams:
        raise RuntimeError("No video stream detected")

    stream = streams[0]
    rate_text = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
    num, denom = rate_text.split("/") if "/" in rate_text else (rate_text, "1")
    fps = float(num) / float(denom) if float(denom) != 0 else 0.0

    return {
        "width": int(stream.get("width", 0) or 0),
        "height": int(stream.get("height", 0) or 0),
        "fps": round(fps, 2),
        "codec": stream.get("codec_name"),
    }
