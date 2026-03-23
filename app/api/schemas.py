from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class CountLine(BaseModel):
    p1: Point
    p2: Point
    direction: Literal["both", "left_to_right", "right_to_left", "top_to_bottom", "bottom_to_top", "p1_to_p2", "p2_to_p1"]


class OperatorZone(BaseModel):
    enabled: bool = False
    polygon: list[Point] | None = None


class CameraConfigRequest(BaseModel):
    camera_ip: str
    camera_username: str
    camera_password: str
    stream_profile: Literal["sub", "main"]


class RoiConfigRequest(BaseModel):
    roi_polygon: list[Point]


class LineConfigRequest(BaseModel):
    p1: Point
    p2: Point
    direction: Literal["both", "left_to_right", "right_to_left", "top_to_bottom", "bottom_to_top", "p1_to_p2", "p2_to_p1"]


class OperatorZoneRequest(BaseModel):
    enabled: bool
    polygon: list[Point] | None = None


class DemoPlaybackRequest(BaseModel):
    speed_multiplier: float = Field(ge=0.25, le=8.0)


class PersonIgnoreRequest(BaseModel):
    enabled: bool


class ManualCountAdjustRequest(BaseModel):
    delta: int = Field(ge=-1000, le=1000)


class DemoVideoItemResponse(BaseModel):
    name: str
    path: str
    size_bytes: int
    modified_at: str
    selected: bool = False
    managed: bool = True


class DemoVideoListResponse(BaseModel):
    items: list[DemoVideoItemResponse]


class DemoVideoSelectRequest(BaseModel):
    path: str


class SimpleOkResponse(BaseModel):
    ok: bool = True


class ConfigResponse(BaseModel):
    id: int = 1
    camera_ip: str | None = None
    camera_username: str | None = None
    camera_password: str | None = None
    baseline_rate_per_min: float | None = None
    stream_profile: Literal["sub", "main"] | None = None
    roi_polygon: list[Point] | None = None
    line: CountLine | None = None
    operator_zone: OperatorZone = Field(default_factory=OperatorZone)


class StatusResponse(BaseModel):
    state: str
    count_source: Literal["vision"] = "vision"
    baseline_rate_per_min: float | None = None
    calibration_progress_pct: int = 0
    calibration_elapsed_sec: int = 0
    calibration_target_duration_sec: int = 0
    rolling_rate_per_min: float = 0.0
    counts_this_minute: int = 0
    counts_this_hour: int = 0
    last_frame_age_sec: float | None = None
    reconnect_attempts_total: int = 0
    operator_absent: bool = False


class EventResponse(BaseModel):
    id: int | None = None
    event_type: str
    state_from: str | None = None
    state_to: str | None = None
    message: str
    created_at: str | None = None


class EventsResponse(BaseModel):
    items: list[EventResponse]
    limit: int


class CameraTestResponse(BaseModel):
    ok: bool
    message: str
    action_hint: str | None = None
    details: dict[str, Any] | None = None


class DiagnosticsResponse(BaseModel):
    app_version: str
    uptime_sec: float
    current_state: str
    count_source: Literal["vision"] = "vision"
    last_frame_age_sec: float | None = None
    reconnect_attempts_total: int = 0
    reader_alive: bool
    vision_loop_alive: bool
    person_detect_loop_alive: bool
    db_path: str
    log_directory: str
    source_kind: Literal["camera", "demo"]
    demo_playback_speed: float = 1.0
    demo_video_name: str | None = None
    person_ignore_enabled: bool = False
    people_detected_count: int = 0
    counting_mode: str = "track_based"
    latest_error_code: str | None = None
    latest_error_message: str | None = None
