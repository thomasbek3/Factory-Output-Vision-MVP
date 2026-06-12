from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_event_counter import load_runtime_calibration
from app.services.station_calibration import (
    SCHEMA_VERSION,
    build_station_calibration,
    read_station_calibration,
    validate_station_calibration,
    write_station_calibration,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = [[[0, 0], [40, 0], [40, 100], [0, 100]]]
OUTPUT = [[[60, 0], [100, 0], [100, 100], [60, 100]]]


def test_station_calibration_schema_is_present() -> None:
    schema = json.loads((REPO_ROOT / "validation/schemas/station_calibration.schema.json").read_text())

    assert schema["type"] == "object"
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert "source_polygons" in schema["required"]
    assert "output_polygons" in schema["required"]
    assert schema["properties"]["refuses_validation_truth"]["const"] is True


def test_station_calibration_validates_and_app_runtime_can_load_it(tmp_path: Path) -> None:
    path = tmp_path / "station_calibration.json"
    payload = build_station_calibration(
        station_id="line-a",
        source_polygons=SOURCE,
        output_polygons=OUTPUT,
        gate={"start": [50, 0], "end": [50, 100], "source_side": 1},
        source_artifacts={"teacher_labels": "/tmp/teacher_labels.json"},
        confidence_notes={"source_zone_confidence": 0.7, "output_zone_confidence": 0.8},
    )

    write_station_calibration(path, payload)
    loaded = read_station_calibration(path)
    zones, gate = load_runtime_calibration(path)

    assert loaded["activation_status"] == "candidate"
    assert loaded["refuses_validation_truth"] is True
    assert zones.source_polygons[0][0] == (0.0, 0.0)
    assert zones.output_polygons[0][0] == (60.0, 0.0)
    assert gate is not None
    assert gate.start == (50, 0)
    assert gate.end == (50, 100)


def test_station_calibration_rejects_missing_output_zone() -> None:
    with pytest.raises(ValueError, match="output_polygons"):
        build_station_calibration(
            station_id="line-a",
            source_polygons=SOURCE,
            output_polygons=[],
        )


def test_station_calibration_must_refuse_validation_truth() -> None:
    payload = build_station_calibration(station_id="line-a", source_polygons=SOURCE, output_polygons=OUTPUT)
    payload["refuses_validation_truth"] = False

    with pytest.raises(ValueError, match="refuse validation truth"):
        validate_station_calibration(payload)


def test_station_calibration_rejects_invalid_gate_source_side() -> None:
    invalid_values = [0, 2, 1.5, "1", True, None]
    for value in invalid_values:
        with pytest.raises(ValueError, match="source_side"):
            build_station_calibration(
                station_id="line-a",
                source_polygons=SOURCE,
                output_polygons=OUTPUT,
                gate={"start": [50, 0], "end": [50, 100], "source_side": value},
            )


def test_station_calibration_requires_gate_source_side_when_gate_is_present() -> None:
    with pytest.raises(ValueError, match="source_side"):
        build_station_calibration(
            station_id="line-a",
            source_polygons=SOURCE,
            output_polygons=OUTPUT,
            gate={"start": [50, 0], "end": [50, 100]},
        )
