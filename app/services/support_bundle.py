from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from app.core.settings import get_db_path, get_log_dir


def build_support_bundle(
    *,
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    latest_snapshot: bytes | None,
) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        db_path = get_db_path()
        if db_path.exists():
            zf.write(db_path, arcname="factory_counter.db")

        zf.writestr("config_snapshot.json", json.dumps(config, indent=2))
        zf.writestr("diagnostics.json", json.dumps(diagnostics, indent=2))

        if latest_snapshot is not None:
            zf.writestr("latest_snapshot.jpg", latest_snapshot)

        log_dir = get_log_dir()
        if log_dir.exists():
            for log_file in log_dir.glob("factory_counter.log*"):
                if log_file.is_file():
                    zf.write(log_file, arcname=str(Path("logs") / log_file.name))

    return out.getvalue()
