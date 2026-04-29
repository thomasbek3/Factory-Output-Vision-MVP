from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from app.db.database import init_db
from app.db.health_repo import insert_health_sample


def test_init_db_upgrades_health_samples_and_persists_count_authority_fields() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        previous = os.environ.get("FC_DB_PATH")
        os.environ["FC_DB_PATH"] = str(db_path)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE health_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    current_state TEXT NOT NULL,
                    last_frame_age_sec REAL,
                    reconnect_attempts_total INTEGER NOT NULL DEFAULT 0,
                    reader_alive INTEGER NOT NULL DEFAULT 0,
                    vision_loop_alive INTEGER NOT NULL DEFAULT 0,
                    person_detect_loop_alive INTEGER NOT NULL DEFAULT 0,
                    source_kind TEXT NOT NULL,
                    rolling_rate_per_min REAL,
                    baseline_rate_per_min REAL,
                    counts_this_minute INTEGER NOT NULL DEFAULT 0,
                    counts_this_hour INTEGER NOT NULL DEFAULT 0,
                    last_error_code TEXT,
                    last_error_message TEXT
                )
                """
            )
            conn.commit()
            conn.close()

            init_db()

            insert_health_sample(
                sample={
                    "current_state": "RUNNING_GREEN",
                    "last_frame_age_sec": 0.4,
                    "reconnect_attempts_total": 1,
                    "reader_alive": True,
                    "vision_loop_alive": True,
                    "person_detect_loop_alive": False,
                    "source_kind": "demo",
                    "rolling_rate_per_min": 2.5,
                    "baseline_rate_per_min": 3.0,
                    "counts_this_minute": 1,
                    "counts_this_hour": 23,
                    "runtime_total": 23,
                    "proof_backed_total": 21,
                    "runtime_inferred_only": 2,
                    "last_error_code": None,
                    "last_error_message": None,
                }
            )

            conn = sqlite3.connect(db_path)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(health_samples)").fetchall()}
            row = conn.execute(
                """
                SELECT counts_this_hour, runtime_total, proof_backed_total, runtime_inferred_only
                FROM health_samples
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            conn.close()

            assert {"runtime_total", "proof_backed_total", "runtime_inferred_only"}.issubset(columns)
            assert row == (23, 23, 21, 2)
        finally:
            if previous is None:
                os.environ.pop("FC_DB_PATH", None)
            else:
                os.environ["FC_DB_PATH"] = previous
