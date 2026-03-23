import sqlite3
from pathlib import Path

from app.core.settings import get_db_path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    camera_ip TEXT,
    camera_username TEXT,
    camera_password TEXT,
    baseline_rate_per_min REAL,
    stream_profile TEXT CHECK (stream_profile IN ('sub', 'main')),
    roi_polygon_json TEXT,
    line_p1_x REAL,
    line_p1_y REAL,
    line_p2_x REAL,
    line_p2_y REAL,
    line_direction TEXT CHECK (line_direction IN ('both', 'left_to_right', 'right_to_left', 'top_to_bottom', 'bottom_to_top', 'p1_to_p2', 'p2_to_p1')),
    operator_zone_enabled INTEGER DEFAULT 0,
    operator_zone_polygon_json TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    state_from TEXT,
    state_to TEXT,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS counts_minute (
    bucket_start TEXT NOT NULL,
    count_source TEXT NOT NULL DEFAULT 'vision',
    count_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bucket_start, count_source)
);

CREATE TABLE IF NOT EXISTS counts_hour (
    bucket_start TEXT NOT NULL,
    count_source TEXT NOT NULL DEFAULT 'vision',
    count_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bucket_start, count_source)
);

CREATE TABLE IF NOT EXISTS health_samples (
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
);
"""


def ensure_db_directory(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    ensure_db_directory(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_config_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(config)").fetchall()}
    missing_statements = {
        "baseline_rate_per_min": "ALTER TABLE config ADD COLUMN baseline_rate_per_min REAL",
        "roi_polygon_json": "ALTER TABLE config ADD COLUMN roi_polygon_json TEXT",
        "line_p1_x": "ALTER TABLE config ADD COLUMN line_p1_x REAL",
        "line_p1_y": "ALTER TABLE config ADD COLUMN line_p1_y REAL",
        "line_p2_x": "ALTER TABLE config ADD COLUMN line_p2_x REAL",
        "line_p2_y": "ALTER TABLE config ADD COLUMN line_p2_y REAL",
        "line_direction": "ALTER TABLE config ADD COLUMN line_direction TEXT",
        "operator_zone_enabled": "ALTER TABLE config ADD COLUMN operator_zone_enabled INTEGER DEFAULT 0",
        "operator_zone_polygon_json": "ALTER TABLE config ADD COLUMN operator_zone_polygon_json TEXT",
    }
    for column, statement in missing_statements.items():
        if column not in columns:
            conn.execute(statement)


def _ensure_config_direction_constraint(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'config'").fetchone()
    if row is None:
        return

    create_sql = row["sql"] or ""
    if all(direction in create_sql for direction in ("left_to_right", "right_to_left", "top_to_bottom", "bottom_to_top")):
        return

    conn.execute("ALTER TABLE config RENAME TO config_old")
    conn.executescript(
        """
        CREATE TABLE config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            camera_ip TEXT,
            camera_username TEXT,
            camera_password TEXT,
            baseline_rate_per_min REAL,
            stream_profile TEXT CHECK (stream_profile IN ('sub', 'main')),
            roi_polygon_json TEXT,
            line_p1_x REAL,
            line_p1_y REAL,
            line_p2_x REAL,
            line_p2_y REAL,
            line_direction TEXT CHECK (line_direction IN ('both', 'left_to_right', 'right_to_left', 'top_to_bottom', 'bottom_to_top', 'p1_to_p2', 'p2_to_p1')),
            operator_zone_enabled INTEGER DEFAULT 0,
            operator_zone_polygon_json TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        INSERT INTO config (
            id,
            camera_ip,
            camera_username,
            camera_password,
            baseline_rate_per_min,
            stream_profile,
            roi_polygon_json,
            line_p1_x,
            line_p1_y,
            line_p2_x,
            line_p2_y,
            line_direction,
            operator_zone_enabled,
            operator_zone_polygon_json,
            updated_at
        )
        SELECT
            id,
            camera_ip,
            camera_username,
            camera_password,
            baseline_rate_per_min,
            stream_profile,
            roi_polygon_json,
            line_p1_x,
            line_p1_y,
            line_p2_x,
            line_p2_y,
            line_direction,
            operator_zone_enabled,
            operator_zone_polygon_json,
            updated_at
        FROM config_old
        """
    )
    conn.execute("DROP TABLE config_old")


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_config_columns(conn)
        _ensure_config_direction_constraint(conn)
        conn.execute("INSERT OR IGNORE INTO config (id) VALUES (1)")
        conn.commit()
