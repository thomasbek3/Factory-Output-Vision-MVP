from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.db.config_repo import get_config
from app.db.database import init_db
from app.services.live_activation import apply_live_activation, build_live_activation_payload
from app.services.station_calibration import build_station_calibration, write_station_calibration
from app.services.video_source import get_active_source
from scripts import apply_live_activation as apply_live_activation_cli


SOURCE = [[[0, 0], [40, 0], [40, 100], [0, 100]]]
OUTPUT = [[[60, 0], [100, 0], [100, 100], [60, 100]]]


@pytest.fixture()
def isolated_db(tmp_path: Path):
    previous = {key: os.environ.get(key) for key in ("FC_DB_PATH", "FC_DEMO_MODE")}
    os.environ["FC_DB_PATH"] = str(tmp_path / "factory.db")
    os.environ["FC_DEMO_MODE"] = "0"
    init_db()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _write_gate(path: Path, *, passed: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-blind-replay-gate-v1",
                "passed": passed,
                "status": "passed" if passed else "failed",
            }
        ),
        encoding="utf-8",
    )


def _write_calibration(path: Path) -> None:
    write_station_calibration(
        path,
        build_station_calibration(station_id="line-a", source_polygons=SOURCE, output_polygons=OUTPUT),
        force=True,
    )


def test_apply_live_activation_updates_camera_config_and_keeps_count_authority(tmp_path: Path, isolated_db) -> None:
    gate = tmp_path / "gate.json"
    calibration = tmp_path / "station_calibration.json"
    output = tmp_path / "activation.json"
    _write_gate(gate)
    _write_calibration(calibration)

    payload = apply_live_activation(
        station_id="line-a",
        gate_report_path=gate,
        station_calibration_path=calibration,
        camera_config={
            "camera_ip": "192.168.1.20",
            "camera_username": "admin",
            "camera_password": "secret",
            "stream_profile": "sub",
        },
        output_path=output,
        model_path=Path("models/station.pt"),
        force=True,
    )

    config = get_config()
    source = get_active_source()
    serialized = output.read_text()
    assert payload["status"] == "applied"
    assert payload["count_authority"] == "existing_yolo_event_runtime_only"
    assert payload["runtime_total_mutation_allowed"] is False
    assert payload["env_overrides"]["FC_DEMO_MODE"] == "0"
    assert payload["env_overrides"]["FC_RUNTIME_CALIBRATION_PATH"] == str(calibration)
    assert payload["env_overrides"]["FC_YOLO_MODEL_PATH"] == "models/station.pt"
    assert config["camera_ip"] == "192.168.1.20"
    assert source.is_demo is False
    assert source.source.startswith("rtsp://admin:secret@192.168.1.20:554/")
    assert "secret" not in serialized
    assert "<redacted>" in serialized


def test_live_activation_requires_passed_gate(tmp_path: Path) -> None:
    gate = tmp_path / "gate.json"
    calibration = tmp_path / "station_calibration.json"
    _write_gate(gate, passed=False)
    _write_calibration(calibration)

    with pytest.raises(ValueError, match="passed blind replay gate"):
        build_live_activation_payload(
            station_id="line-a",
            gate_report_path=gate,
            station_calibration_path=calibration,
            camera_config={
                "camera_ip": "192.168.1.20",
                "camera_username": "admin",
                "camera_password": "secret",
                "stream_profile": "sub",
            },
        )


def test_apply_live_activation_cli_redacts_password(tmp_path: Path, isolated_db, capsys) -> None:
    gate = tmp_path / "gate.json"
    calibration = tmp_path / "station_calibration.json"
    output = tmp_path / "activation.json"
    _write_gate(gate)
    _write_calibration(calibration)

    exit_code = apply_live_activation_cli.main(
        [
            "--station-id",
            "line-a",
            "--gate-report",
            str(gate),
            "--station-calibration",
            str(calibration),
            "--camera-ip",
            "192.168.1.20",
            "--camera-username",
            "admin",
            "--camera-password",
            "secret",
            "--output",
            str(output),
            "--force",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "applied"' in captured.out
    assert "secret" not in output.read_text()
