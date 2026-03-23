import asyncio
import mimetypes
import time
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.api.schemas import (
    CameraConfigRequest,
    CameraTestResponse,
    ConfigResponse,
    DemoPlaybackRequest,
    DemoVideoListResponse,
    DemoVideoSelectRequest,
    DiagnosticsResponse,
    EventsResponse,
    LineConfigRequest,
    ManualCountAdjustRequest,
    OperatorZoneRequest,
    PersonIgnoreRequest,
    RoiConfigRequest,
    SimpleOkResponse,
    StatusResponse,
)
from app.core.settings import get_db_path, get_log_dir
from app.db.config_repo import (
    clear_count_line,
    clear_roi_polygon,
    get_config,
    update_camera_config,
    update_count_line,
    update_operator_zone,
    update_roi_polygon,
)
from app.db.event_repo import list_events
from app.services.camera_probe import ffprobe_stream
from app.services.demo_video_library import get_active_demo_video, list_demo_videos, save_demo_video_upload
from app.services.frame_reader import encode_jpeg
from app.services.support_bundle import build_support_bundle
from app.services.video_source import get_active_source

api_router = APIRouter()
_MJPEG_BOUNDARY = "frame"


@api_router.get("/status", response_model=StatusResponse)
def get_status(request: Request) -> dict[str, object]:
    return request.app.state.vision_worker.get_status()


@api_router.get("/config", response_model=ConfigResponse)
def api_get_config() -> dict[str, Any]:
    config = get_config()
    masked_password = "***" if config.get("camera_password") else None
    return {
        "id": config.get("id", 1),
        "camera_ip": config.get("camera_ip"),
        "camera_username": config.get("camera_username"),
        "camera_password": masked_password,
        "baseline_rate_per_min": config.get("baseline_rate_per_min"),
        "stream_profile": config.get("stream_profile"),
        "roi_polygon": config.get("roi_polygon"),
        "line": config.get("line"),
        "operator_zone": config.get("operator_zone"),
    }


@api_router.get("/events", response_model=EventsResponse)
def api_get_events(limit: int = Query(default=20, ge=1, le=200)) -> EventsResponse:
    return EventsResponse(items=list_events(limit=limit), limit=limit)


@api_router.post("/config/camera", response_model=SimpleOkResponse)
def api_post_config_camera(payload: CameraConfigRequest) -> SimpleOkResponse:
    update_camera_config(
        camera_ip=payload.camera_ip,
        camera_username=payload.camera_username,
        camera_password=payload.camera_password,
        stream_profile=payload.stream_profile,
    )
    return SimpleOkResponse()


@api_router.post("/config/roi", response_model=SimpleOkResponse)
def api_post_config_roi(payload: RoiConfigRequest) -> SimpleOkResponse:
    if len(payload.roi_polygon) < 3:
        raise HTTPException(status_code=400, detail="ROI polygon requires at least 3 points")
    roi = [{"x": p.x, "y": p.y} for p in payload.roi_polygon]
    update_roi_polygon(roi_polygon=roi)
    return SimpleOkResponse()


@api_router.post("/config/roi/clear", response_model=SimpleOkResponse)
def api_post_config_roi_clear() -> SimpleOkResponse:
    clear_roi_polygon()
    return SimpleOkResponse()


@api_router.post("/config/line", response_model=SimpleOkResponse)
def api_post_config_line(payload: LineConfigRequest) -> SimpleOkResponse:
    update_count_line(
        p1={"x": payload.p1.x, "y": payload.p1.y},
        p2={"x": payload.p2.x, "y": payload.p2.y},
        direction=payload.direction,
    )
    return SimpleOkResponse()


@api_router.post("/config/line/clear", response_model=SimpleOkResponse)
def api_post_config_line_clear() -> SimpleOkResponse:
    clear_count_line()
    return SimpleOkResponse()


@api_router.post("/config/operator_zone", response_model=SimpleOkResponse)
def api_post_operator_zone(payload: OperatorZoneRequest) -> SimpleOkResponse:
    if payload.enabled:
        if not payload.polygon or len(payload.polygon) < 3:
            raise HTTPException(status_code=400, detail="Operator zone polygon requires at least 3 points")
        polygon = [{"x": p.x, "y": p.y} for p in payload.polygon]
        update_operator_zone(enabled=True, polygon=polygon)
    else:
        update_operator_zone(enabled=False, polygon=None)
    return SimpleOkResponse()


@api_router.post("/config/operator_zone/clear", response_model=SimpleOkResponse)
def api_post_operator_zone_clear() -> SimpleOkResponse:
    update_operator_zone(enabled=False, polygon=None)
    return SimpleOkResponse()


@api_router.post("/control/calibrate/start", response_model=StatusResponse)
def api_control_calibrate_start(request: Request) -> dict[str, object]:
    return request.app.state.vision_worker.start_calibration()


@api_router.post("/control/monitor/start", response_model=StatusResponse)
def api_control_monitor_start(request: Request) -> dict[str, object]:
    return request.app.state.vision_worker.start_monitoring()


@api_router.post("/control/monitor/stop", response_model=StatusResponse)
def api_control_monitor_stop(request: Request) -> dict[str, object]:
    return request.app.state.vision_worker.stop_monitoring()


@api_router.post("/control/reset_calibration", response_model=StatusResponse)
def api_control_reset_calibration(request: Request) -> dict[str, object]:
    return request.app.state.vision_worker.reset_calibration()


@api_router.post("/control/reset_counts", response_model=StatusResponse)
def api_control_reset_counts(request: Request) -> dict[str, object]:
    return request.app.state.vision_worker.reset_counts()


@api_router.post("/control/restart_video", response_model=SimpleOkResponse)
def api_control_restart_video(request: Request) -> SimpleOkResponse:
    try:
        request.app.state.video_runtime.restart()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SimpleOkResponse()


@api_router.post("/control/demo/playback_speed", response_model=SimpleOkResponse)
def api_control_demo_playback_speed(request: Request, payload: DemoPlaybackRequest) -> SimpleOkResponse:
    try:
        request.app.state.video_runtime.set_demo_playback_speed(payload.speed_multiplier)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SimpleOkResponse()


@api_router.post("/control/person_ignore", response_model=StatusResponse)
def api_control_person_ignore(request: Request, payload: PersonIgnoreRequest) -> dict[str, object]:
    return request.app.state.vision_worker.set_person_ignore_enabled(payload.enabled)


@api_router.post("/control/adjust_count", response_model=StatusResponse)
def api_control_adjust_count(request: Request, payload: ManualCountAdjustRequest) -> dict[str, object]:
    return request.app.state.vision_worker.adjust_count(payload.delta)


@api_router.get("/control/demo/videos", response_model=DemoVideoListResponse)
def api_control_demo_videos(request: Request) -> DemoVideoListResponse:
    if request.app.state.video_runtime.current_source_kind() != "demo":
        return DemoVideoListResponse(items=[])
    return DemoVideoListResponse(items=list_demo_videos())


@api_router.post("/control/demo/videos/upload", response_model=SimpleOkResponse)
def api_control_demo_video_upload(request: Request, file: UploadFile = File(...)) -> SimpleOkResponse:
    try:
        saved = save_demo_video_upload(file)
        request.app.state.video_runtime.set_demo_video_source(str(saved))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        file.file.close()
    return SimpleOkResponse()


@api_router.post("/control/demo/videos/select", response_model=SimpleOkResponse)
def api_control_demo_video_select(request: Request, payload: DemoVideoSelectRequest) -> SimpleOkResponse:
    try:
        request.app.state.video_runtime.set_demo_video_source(payload.path)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SimpleOkResponse()


@api_router.get("/control/demo/videos/active/content")
def api_control_demo_video_active_content(request: Request) -> FileResponse:
    runtime = request.app.state.video_runtime
    if runtime.current_source_kind() != "demo":
        raise HTTPException(status_code=400, detail="Active demo video is only available in demo mode")

    active_video = get_active_demo_video()
    if active_video is None:
        selection = runtime.current_source_selection()
        source_path = selection.source
        if not source_path:
            raise HTTPException(status_code=404, detail="No active demo video is configured")
        active_video = source_path

    active_path = str(active_video)
    if not active_path:
        raise HTTPException(status_code=404, detail="No active demo video is configured")

    media_type, _ = mimetypes.guess_type(active_path)
    return FileResponse(
        active_path,
        media_type=media_type or "application/octet-stream",
        filename=runtime.current_demo_video_name() or "demo_video",
        headers={"Cache-Control": "no-store"},
    )


def _probe_source_for_test(request: Request) -> tuple[bool, dict[str, Any] | None, str | None]:
    selection = request.app.state.video_runtime.current_source_selection()
    if selection.is_demo:
        return True, ffprobe_stream(selection.source), None

    last_error = None
    for candidate in selection.candidates:
        try:
            return False, ffprobe_stream(candidate), None
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    return False, None, last_error


@api_router.post("/control/test_camera", response_model=CameraTestResponse)
def api_test_camera(request: Request) -> CameraTestResponse:
    try:
        is_demo, details, error = _probe_source_for_test(request)
        if details is None:
            raise RuntimeError(error or "Unknown error")
        message = "Demo video connected" if is_demo else "Camera connected"
        return CameraTestResponse(ok=True, message=message, details=details)
    except Exception as exc:  # noqa: BLE001
        return CameraTestResponse(
            ok=False,
            message="Can't connect. Most often camera streaming is turned off.",
            action_hint="Enable RTSP in Reolink settings.",
            details={"error_code": "UNKNOWN", "error": str(exc)},
        )


def _draw_overlays(frame: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]

    roi_polygon = config.get("roi_polygon")
    if roi_polygon and len(roi_polygon) >= 3:
        pts = np.array([[int(p["x"] * w), int(p["y"] * h)] for p in roi_polygon], dtype=np.int32)
        cv2.polylines(out, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

    line = config.get("line")
    if line and line.get("p1") and line.get("p2"):
        p1 = line["p1"]
        p2 = line["p2"]
        p1_px = (int(p1["x"] * w), int(p1["y"] * h))
        p2_px = (int(p2["x"] * w), int(p2["y"] * h))
        cv2.line(out, p1_px, p2_px, color=(0, 165, 255), thickness=2)

    operator_zone = config.get("operator_zone") or {}
    polygon = operator_zone.get("polygon")
    if operator_zone.get("enabled") and polygon and len(polygon) >= 3:
        pts = np.array([[int(p["x"] * w), int(p["y"] * h)] for p in polygon], dtype=np.int32)
        cv2.polylines(out, [pts], isClosed=True, color=(255, 0, 0), thickness=2)

    return out


def _draw_debug_detection_overlays(frame: np.ndarray, debug_overlay: dict[str, Any] | None) -> np.ndarray:
    if not debug_overlay:
        return frame

    out = frame.copy()
    for person_box in debug_overlay.get("person_boxes", []):
        x = int(person_box.get("x", 0))
        y = int(person_box.get("y", 0))
        w = int(person_box.get("w", 0))
        h = int(person_box.get("h", 0))
        confidence = person_box.get("confidence")
        cv2.rectangle(out, (x, y), (x + w, y + h), color=(255, 0, 255), thickness=2)
        if confidence is not None:
            cv2.putText(
                out,
                f"person {float(confidence):.2f}",
                (x + 4, max(14, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 0, 255),
                1,
                cv2.LINE_AA,
            )

    for detection in debug_overlay.get("detections", []):
        bbox = detection.get("bbox")
        centroid = detection.get("centroid")
        if bbox and len(bbox) == 4:
            x, y, w, h = bbox
            cv2.rectangle(out, (int(x), int(y)), (int(x + w), int(y + h)), color=(0, 255, 0), thickness=2)
        if centroid and len(centroid) == 2:
            cv2.circle(out, (int(centroid[0]), int(centroid[1])), radius=4, color=(0, 255, 0), thickness=-1)

    for track in debug_overlay.get("tracks", []):
        centroid = track.get("centroid")
        if not centroid or len(centroid) != 2:
            continue
        label = f"ID {track.get('track_id', '?')}"
        if track.get("counted"):
            label = f"{label} counted"
        anchor = (int(centroid[0]) + 6, max(12, int(centroid[1]) - 8))
        cv2.putText(
            out,
            label,
            anchor,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return out


def _compose_live_frame(request: Request, frame: np.ndarray, overlay_mode: str) -> np.ndarray:
    composed = _draw_overlays(frame, get_config())
    if overlay_mode == "calibration":
        composed = _draw_debug_detection_overlays(composed, request.app.state.vision_worker.get_debug_overlay())
    return composed


@api_router.get("/snapshot")
def api_snapshot(
    request: Request,
    overlay_mode: str = Query(default="default", pattern="^(default|calibration)$"),
) -> Response:
    runtime = request.app.state.video_runtime
    try:
        runtime.ensure_running()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    snap = runtime.reader.snapshot()
    if snap.frame is None:
        raise HTTPException(status_code=503, detail="Frame not available yet")

    frame = _compose_live_frame(request, snap.frame, overlay_mode)
    return Response(content=encode_jpeg(frame), media_type="image/jpeg")


@api_router.get("/stream.mjpg")
async def api_stream_mjpeg(
    request: Request,
    overlay_mode: str = Query(default="default", pattern="^(default|calibration)$"),
    frame_limit: int | None = Query(default=None, ge=1, le=120),
) -> StreamingResponse:
    runtime = request.app.state.video_runtime
    try:
        runtime.ensure_running()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def iter_mjpeg():
        last_frame_time = 0.0
        frames_sent = 0
        while True:
            if await request.is_disconnected():
                break

            snap = runtime.reader.snapshot()
            if snap.frame is None or snap.last_frame_time <= 0:
                await asyncio.sleep(0.05)
                continue

            if snap.last_frame_time <= last_frame_time:
                await asyncio.sleep(0.03)
                continue

            jpeg = encode_jpeg(_compose_live_frame(request, snap.frame, overlay_mode))
            last_frame_time = snap.last_frame_time
            yield (
                f"--{_MJPEG_BOUNDARY}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg)}\r\n\r\n"
            ).encode("ascii") + jpeg + b"\r\n"
            frames_sent += 1
            if frame_limit is not None and frames_sent >= frame_limit:
                break

    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        iter_mjpeg(),
        media_type=f"multipart/x-mixed-replace; boundary={_MJPEG_BOUNDARY}",
        headers=headers,
    )


@api_router.get("/diagnostics/snapshot/debug")
def api_diagnostics_debug_snapshot(
    request: Request,
    view: str = Query(default="tracks", pattern="^(roi|mask|tracks|people)$"),
) -> Response:
    artifact = request.app.state.vision_worker.get_debug_snapshot_artifact()
    if artifact is None:
        raise HTTPException(status_code=503, detail="Debug snapshot not available yet")

    config = get_config()
    if view == "roi":
        base_frame = artifact.get("roi_frame")
        if base_frame is None:
            raise HTTPException(status_code=503, detail="ROI debug snapshot not available yet")
        frame = _draw_overlays(base_frame, config)
    elif view == "mask":
        base_frame = artifact.get("mask_frame")
        if base_frame is None:
            raise HTTPException(status_code=503, detail="Mask debug snapshot not available yet")
        frame = _draw_debug_detection_overlays(base_frame, artifact)
    elif view == "people":
        base_frame = artifact.get("source_frame")
        if base_frame is None:
            raise HTTPException(status_code=503, detail="People debug snapshot not available yet")
        frame = base_frame.copy()
        people_only_overlay = {
            "detections": [],
            "tracks": [],
            "person_boxes": artifact.get("person_boxes", []),
        }
        frame = _draw_debug_detection_overlays(frame, people_only_overlay)
    else:
        base_frame = artifact.get("source_frame")
        if base_frame is None:
            raise HTTPException(status_code=503, detail="Track debug snapshot not available yet")
        frame = _draw_overlays(base_frame, config)
        frame = _draw_debug_detection_overlays(frame, artifact)

    return Response(content=encode_jpeg(frame), media_type="image/jpeg")


@api_router.get("/diagnostics/sysinfo", response_model=DiagnosticsResponse)
def api_diagnostics_sysinfo(request: Request) -> dict[str, object]:
    uptime_sec = time.time() - request.app.state.started_at
    return request.app.state.vision_worker.get_diagnostics(
        uptime_sec=uptime_sec,
        db_path=str(get_db_path()),
        log_directory=str(get_log_dir()),
    )


@api_router.get("/diagnostics/support_bundle.zip")
def api_support_bundle(request: Request) -> Response:
    diagnostics = api_diagnostics_sysinfo(request)
    snapshot = None
    runtime = request.app.state.video_runtime
    try:
        runtime.ensure_running()
        snap = runtime.reader.snapshot()
        if snap.frame is not None:
            snapshot = encode_jpeg(_draw_overlays(snap.frame, get_config()))
    except Exception:  # noqa: BLE001
        snapshot = None

    bundle = build_support_bundle(
        config=api_get_config(),
        diagnostics=diagnostics,
        latest_snapshot=snapshot,
    )
    headers = {"Content-Disposition": 'attachment; filename="support_bundle.zip"'}
    return Response(content=bundle, media_type="application/zip", headers=headers)
