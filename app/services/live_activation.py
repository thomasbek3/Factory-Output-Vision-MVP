from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.db.config_repo import update_camera_config
from app.services.station_calibration import read_station_calibration


SCHEMA_VERSION = "factory-vision-live-activation-v1"


def build_live_activation_payload(
    *,
    station_id: str,
    gate_report_path: Path,
    station_calibration_path: Path,
    camera_config: dict[str, str],
    model_path: Path | None = None,
    yolo_confidence: float | None = None,
    event_count_rule: str = "placed_and_stayed",
) -> dict[str, Any]:
    gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    if gate_report.get("passed") is not True:
        raise ValueError("live activation requires a passed blind replay gate")
    calibration = read_station_calibration(station_calibration_path)
    _validate_camera_config(camera_config)
    env_overrides = {
        "FC_DEMO_MODE": "0",
        "FC_COUNTING_MODE": "event_based",
        "FC_RUNTIME_CALIBRATION_PATH": str(station_calibration_path),
        "FC_EVENT_COUNT_RULE": event_count_rule,
    }
    if model_path is not None:
        env_overrides["FC_YOLO_MODEL_PATH"] = str(model_path)
    if yolo_confidence is not None:
        env_overrides["FC_YOLO_CONF_THRESHOLD"] = f"{float(yolo_confidence):g}"
    return {
        "schema_version": SCHEMA_VERSION,
        "station_id": station_id,
        "status": "ready_to_apply",
        "count_authority": "existing_yolo_event_runtime_only",
        "runtime_total_mutation_allowed": False,
        "blind_replay_gate_report": str(gate_report_path),
        "station_calibration_path": str(station_calibration_path),
        "station_calibration_activation_status": calibration.get("activation_status"),
        "camera_config": {
            "camera_ip": camera_config["camera_ip"],
            "camera_username": camera_config["camera_username"],
            "camera_password": "<redacted>",
            "stream_profile": camera_config["stream_profile"],
        },
        "env_overrides": env_overrides,
    }


def apply_live_activation(
    *,
    station_id: str,
    gate_report_path: Path,
    station_calibration_path: Path,
    camera_config: dict[str, str],
    output_path: Path,
    model_path: Path | None = None,
    yolo_confidence: float | None = None,
    event_count_rule: str = "placed_and_stayed",
    force: bool = False,
) -> dict[str, Any]:
    payload = build_live_activation_payload(
        station_id=station_id,
        gate_report_path=gate_report_path,
        station_calibration_path=station_calibration_path,
        camera_config=camera_config,
        model_path=model_path,
        yolo_confidence=yolo_confidence,
        event_count_rule=event_count_rule,
    )
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    update_camera_config(
        camera_ip=camera_config["camera_ip"],
        camera_username=camera_config["camera_username"],
        camera_password=camera_config["camera_password"],
        stream_profile=camera_config["stream_profile"],
    )
    payload["status"] = "applied"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _validate_camera_config(camera_config: dict[str, str]) -> None:
    required = ("camera_ip", "camera_username", "camera_password", "stream_profile")
    missing = [key for key in required if not camera_config.get(key)]
    if missing:
        raise ValueError(f"camera_config missing required key(s): {', '.join(missing)}")
    if camera_config["stream_profile"] not in {"sub", "main"}:
        raise ValueError("camera_config stream_profile must be sub or main")
