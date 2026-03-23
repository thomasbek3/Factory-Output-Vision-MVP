from __future__ import annotations

import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient


def reset_logging_for_tests() -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)
    if hasattr(root, "_factory_counter_configured"):
        delattr(root, "_factory_counter_configured")


@contextmanager
def app_client(*, demo: bool = False, extra_env: dict[str, str] | None = None) -> Iterator[tuple[TestClient, str]]:
    temp_dir = tempfile.mkdtemp(prefix="factory_counter_test_")
    env_updates = {
        "FC_DB_PATH": os.path.join(temp_dir, "test.db"),
        "FC_LOG_DIR": os.path.join(temp_dir, "logs"),
        "FC_DEMO_VIDEO_LIBRARY_DIR": os.path.join(temp_dir, "demo_videos"),
        "FC_HEALTH_SAMPLE_INTERVAL_SEC": "0.1",
        "FC_PERSON_DETECT_ENABLED": "0",
        "FC_PERSON_IGNORE_ENABLED": "0",
        "FC_DEMO_PLAYBACK_SPEED": "1.0",
        "FC_DEMO_MODE": "1" if demo else "0",
    }
    if demo:
        env_updates["FC_DEMO_VIDEO_PATH"] = str(Path("demo/demo.mp4").resolve())
        env_updates["FC_FRAME_STALL_TIMEOUT_SEC"] = "30"
    if extra_env:
        env_updates.update(extra_env)

    previous: dict[str, str | None] = {key: os.environ.get(key) for key in env_updates}
    try:
        for key, value in env_updates.items():
            os.environ[key] = value
        reset_logging_for_tests()
        from app.main import create_app

        app = create_app()
        with TestClient(app) as client:
            yield client, temp_dir
    finally:
        reset_logging_for_tests()
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        shutil.rmtree(temp_dir, ignore_errors=True)
