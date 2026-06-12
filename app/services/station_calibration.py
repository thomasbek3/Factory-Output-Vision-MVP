from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-vision-station-calibration-v1"


def build_station_calibration(
    *,
    station_id: str,
    source_polygons: list[list[list[float]]],
    output_polygons: list[list[list[float]]],
    ignore_polygons: list[list[list[float]]] | None = None,
    gate: dict[str, Any] | None = None,
    source_artifacts: dict[str, str] | None = None,
    confidence_notes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "station_id": station_id,
        "created_at": utc_now_iso(),
        "source_artifacts": source_artifacts or {},
        "confidence_notes": confidence_notes or {},
        "source_polygons": source_polygons,
        "output_polygons": output_polygons,
        "ignore_polygons": ignore_polygons or [],
        "refuses_validation_truth": True,
        "activation_status": "candidate",
    }
    if gate is not None:
        payload["gate"] = gate
    validate_station_calibration(payload)
    return payload


def validate_station_calibration(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported station calibration schema: {payload.get('schema_version')}")
    if not payload.get("station_id"):
        raise ValueError("station calibration must include station_id")
    _validate_polygons(payload.get("source_polygons"), field="source_polygons")
    _validate_polygons(payload.get("output_polygons"), field="output_polygons")
    _validate_polygons(payload.get("ignore_polygons") or [], field="ignore_polygons", allow_empty=True)
    if payload.get("refuses_validation_truth") is not True:
        raise ValueError("station calibration must refuse validation truth")
    if payload.get("activation_status") not in {"candidate", "ready_for_replay", "ready_for_live", "live"}:
        raise ValueError("unsupported station calibration activation_status")
    gate = payload.get("gate")
    if gate is not None:
        _validate_point(gate.get("start"), field="gate.start")
        _validate_point(gate.get("end"), field="gate.end")
        if "source_side" not in gate:
            raise ValueError("gate.source_side is required")
        source_side = gate["source_side"]
        if isinstance(source_side, bool) or not isinstance(source_side, int) or source_side not in {-1, 1}:
            raise ValueError("gate.source_side must be -1 or 1")


def write_station_calibration(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    validate_station_calibration(payload)
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_station_calibration(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_station_calibration(payload)
    return payload


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_polygons(value: Any, *, field: str, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"station calibration must include {field}")
    for polygon_index, polygon in enumerate(value):
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ValueError(f"{field}[{polygon_index}] must contain at least 3 points")
        for point_index, point in enumerate(polygon):
            _validate_point(point, field=f"{field}[{polygon_index}][{point_index}]")


def _validate_point(value: Any, *, field: str) -> None:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field} must be [x, y]")
    float(value[0])
    float(value[1])
