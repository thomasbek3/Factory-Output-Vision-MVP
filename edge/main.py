from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import requests

from counter import FillLevelCounter, SlotOccupancyCounter
from state import CameraState, apply_state_logic


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("edge")


@dataclass
class CameraRuntime:
    config: Dict[str, Any]
    state: CameraState
    counter: Any
    cap: Optional[cv2.VideoCapture] = None
    failure_count: int = 0


def load_config(config_path: Path) -> Dict[str, Any]:
    cfg = json.loads(config_path.read_text())
    if "backend_url" not in cfg or "cameras" not in cfg or not cfg["cameras"]:
        raise ValueError("Invalid config: backend_url and at least one camera are required")
    return cfg


def connect_rtsp(rtsp_url: str, retries: int = 3, backoff_s: int = 2) -> cv2.VideoCapture:
    last_exc = None
    for attempt in range(1, retries + 1):
        cap = cv2.VideoCapture(rtsp_url)
        if cap.isOpened():
            return cap
        cap.release()
        last_exc = RuntimeError(f"RTSP connection failed, attempt={attempt}")
        time.sleep(backoff_s * attempt)
    raise last_exc or RuntimeError("Unknown RTSP failure")


def crop_roi(frame, roi):
    x, y, w, h = map(int, roi)
    h_max, w_max = frame.shape[:2]
    if x < 0 or y < 0 or w <= 0 or h <= 0 or (x + w) > w_max or (y + h) > h_max:
        raise ValueError(f"ROI {roi} is out of bounds for frame shape={frame.shape[:2]}")
    return frame[y : y + h, x : x + w]


def scale_roi(roi: list[int], scale: float) -> list[int]:
    return [int(round(v * scale)) for v in roi]


def encode_jpeg(frame) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("Failed to encode JPEG")
    return buf.tobytes()


def post_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    attempts: int = 3,
    timeout: int = 10,
    **kwargs,
) -> requests.Response:
    last_exc = None
    for idx in range(attempts):
        try:
            resp = session.request(method=method, url=url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if idx < attempts - 1:
                time.sleep(0.5 * (idx + 1))
    raise RuntimeError(f"HTTP request failed after {attempts} attempts: {url}") from last_exc


def should_sample_motion(prev_gray, frame_gray, threshold: float) -> bool:
    if prev_gray is None:
        return True
    return float(cv2.absdiff(prev_gray, frame_gray).mean()) >= threshold


def _normalize_reference(reference, roi: list[int], roi_shape: Tuple[int, int]) -> Any:
    if reference is None:
        raise FileNotFoundError("Empty reference frame cannot be loaded")
    if reference.shape[:2] == roi_shape:
        return reference
    try:
        cropped = crop_roi(reference, roi)
        if cropped.shape[:2] == roi_shape:
            return cropped
    except ValueError:
        pass
    return cv2.resize(reference, (roi_shape[1], roi_shape[0]))


def build_counter(camera_cfg: Dict[str, Any], roi_shape: Tuple[int, int]):
    mode = camera_cfg.get("mode", "fill")
    if mode == "fill":
        reference = cv2.imread(camera_cfg["empty_reference_path"])
        reference = _normalize_reference(reference, camera_cfg["roi"], roi_shape)
        return FillLevelCounter(
            reference,
            max_units=int(camera_cfg.get("max_units", 20)),
            diff_threshold=int(camera_cfg.get("diff_threshold", 25)),
        )
    if mode == "slot":
        return SlotOccupancyCounter(
            grid_rows=int(camera_cfg.get("grid_rows", 3)),
            grid_cols=int(camera_cfg.get("grid_cols", 4)),
            threshold=float(camera_cfg.get("slot_threshold", 0.15)),
        )
    raise ValueError(f"Unsupported mode: {mode}")


def initialize_camera(camera_cfg: Dict[str, Any]) -> CameraRuntime:
    cap = connect_rtsp(camera_cfg["rtsp_url"], retries=3)
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        raise RuntimeError(f"Unable to read initial frame for {camera_cfg['camera_id']}")

    resize_width = int(camera_cfg.get("resize_width", 960))
    scale = resize_width / frame.shape[1]
    scaled_roi = scale_roi(camera_cfg["roi"], scale)
    resized = cv2.resize(frame, (resize_width, int(frame.shape[0] * scale)))
    roi_frame = crop_roi(resized, scaled_roi)

    cam_cfg = dict(camera_cfg)
    cam_cfg["roi"] = scaled_roi
    counter = build_counter(cam_cfg, roi_frame.shape[:2])

    return CameraRuntime(config=cam_cfg, state=CameraState(camera_id=cam_cfg["camera_id"]), counter=counter, cap=cap)


def run(config_path: Path) -> None:
    cfg = load_config(config_path)
    sample_seconds = int(cfg.get("sample_seconds", 15))
    downtime_minutes = int(cfg.get("downtime_minutes", 20))
    persistence_required = int(cfg.get("persistence_frames", 2))
    motion_threshold = float(cfg.get("motion_threshold", 3.0))

    auth = (cfg["api_user"], cfg["api_password"])
    backend_url = cfg["backend_url"].rstrip("/")

    session = requests.Session()
    session.auth = auth

    runtimes = [initialize_camera(cam) for cam in cfg["cameras"]]
    prev_gray_by_camera: Dict[str, Any] = {}
    last_increment_ts = {rt.config["camera_id"]: datetime.now(timezone.utc) for rt in runtimes}

    logger.info("Starting edge loop for %d camera(s)", len(runtimes))

    while True:
        cycle_started = time.time()
        for runtime in runtimes:
            cam = runtime.config
            camera_id = cam["camera_id"]

            try:
                if runtime.cap is None or not runtime.cap.isOpened():
                    runtime.cap = connect_rtsp(cam["rtsp_url"], retries=3)

                ok, frame = runtime.cap.read()
                if not ok or frame is None:
                    raise RuntimeError("Frame grab failed")

                resize_width = int(cam.get("resize_width", 960))
                scale = resize_width / frame.shape[1]
                resized = cv2.resize(frame, (resize_width, int(frame.shape[0] * scale)))
                roi_frame = crop_roi(resized, cam["roi"])
                gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)

                if cam.get("adaptive_sampling", True) and not should_sample_motion(
                    prev_gray_by_camera.get(camera_id), gray, motion_threshold
                ):
                    prev_gray_by_camera[camera_id] = gray
                    continue
                prev_gray_by_camera[camera_id] = gray

                measured, confidence, ratio = runtime.counter.estimate(roi_frame)
                delta, reset = apply_state_logic(
                    runtime.state,
                    measured,
                    persistence_required=persistence_required,
                    reset_threshold=int(cam.get("reset_threshold", 2)),
                )

                now = datetime.now(timezone.utc)
                if delta > 0:
                    last_increment_ts[camera_id] = now
                downtime = (now - last_increment_ts[camera_id]).total_seconds() >= downtime_minutes * 60

                payload = {
                    "camera_id": camera_id,
                    "timestamp": now.isoformat(),
                    "count": runtime.state.last_committed_count,
                    "delta": delta,
                    "confidence": round(confidence, 4),
                    "ratio": round(ratio, 4),
                    "downtime": downtime,
                    "reset_detected": reset,
                }
                post_with_retry(session, "POST", f"{backend_url}/ingest", json=payload, timeout=10)

                if delta > 0 or downtime or confidence < float(cam.get("min_confidence", 0.2)):
                    event_type = "increment" if delta > 0 else ("downtime" if downtime else "low_confidence")
                    files = {
                        "file": (
                            f"{camera_id}_{event_type}_{int(time.time())}.jpg",
                            encode_jpeg(resized),
                            "image/jpeg",
                        )
                    }
                    data = {"camera_id": camera_id, "event_type": event_type, "timestamp": now.isoformat()}
                    post_with_retry(session, "POST", f"{backend_url}/evidence", files=files, data=data, timeout=15)

                runtime.failure_count = 0

            except Exception as exc:  # noqa: BLE001
                runtime.failure_count += 1
                logger.exception("Camera %s failed: %s", camera_id, exc)
                if runtime.cap:
                    runtime.cap.release()
                    runtime.cap = None

        elapsed = time.time() - cycle_started
        time.sleep(max(1.0, sample_seconds - elapsed))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Factory throughput edge agent")
    parser.add_argument("--config", default="config/config.json", help="Path to config.json")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(Path(args.config))
