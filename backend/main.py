from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.database import Base, SessionLocal, engine
from backend.models import EvidenceFrame, Metric
from backend.schemas import MetricIn

app = FastAPI(title="Factory Throughput API", version="1.1.0")
security = HTTPBasic()

API_USER = os.getenv("API_USER", "admin")
API_PASSWORD = os.getenv("API_PASSWORD", "changeme")
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", "backend/data/evidence"))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def verify_auth(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    good_user = secrets.compare_digest(credentials.username, API_USER)
    good_pass = secrets.compare_digest(credentials.password, API_PASSWORD)
    if not (good_user and good_pass):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return credentials.username


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_metrics_cam_ts ON metrics(camera_id, timestamp)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_evidence_cam_ts ON evidence_frames(camera_id, timestamp)"))


@app.on_event("startup")
def on_startup():
    migrate()


@app.get("/health")
def health():
    return {"ok": True, "service": "factory-throughput-api"}


@app.post("/ingest")
def ingest(payload: MetricIn, _: Annotated[str, Depends(verify_auth)], db: Session = Depends(get_db)):
    row = Metric(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ok": True}


@app.post("/evidence")
async def upload_evidence(
    _: Annotated[str, Depends(verify_auth)],
    camera_id: str = Form(...),
    event_type: str = Form(...),
    timestamp: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ts = datetime.fromisoformat(timestamp)
    file_name = f"{camera_id}_{event_type}_{int(ts.timestamp())}.jpg"
    out_path = EVIDENCE_DIR / file_name
    out_path.write_bytes(await file.read())

    row = EvidenceFrame(camera_id=camera_id, event_type=event_type, timestamp=ts, file_path=str(out_path))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "path": str(out_path)}


@app.get("/cameras")
def cameras(_: Annotated[str, Depends(verify_auth)], db: Session = Depends(get_db)):
    rows = db.query(Metric.camera_id).distinct().all()
    return {"cameras": [r[0] for r in rows]}


@app.get("/series/{camera_id}")
def series(
    camera_id: str,
    _: Annotated[str, Depends(verify_auth)],
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        db.query(Metric)
        .filter(Metric.camera_id == camera_id, Metric.timestamp >= since)
        .order_by(Metric.timestamp.asc())
        .all()
    )
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "count": r.count,
            "delta": r.delta,
            "confidence": r.confidence,
            "downtime": r.downtime,
            "ratio": r.ratio,
        }
        for r in rows
    ]


@app.get("/status/{camera_id}")
def status(
    camera_id: str,
    _: Annotated[str, Depends(verify_auth)],
    window_minutes: int = Query(default=60, ge=5, le=720),
    downtime_minutes: int = Query(default=20, ge=1, le=240),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=window_minutes)

    rows = (
        db.query(Metric)
        .filter(Metric.camera_id == camera_id, Metric.timestamp >= since)
        .order_by(Metric.timestamp.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No data for camera")

    units = sum(r.delta for r in rows if r.delta > 0)
    units_per_hour = units * (60 / max(window_minutes, 1))

    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    today_total = (
        db.query(Metric)
        .filter(Metric.camera_id == camera_id, Metric.timestamp >= today_start)
        .with_entities(func.coalesce(func.sum(Metric.delta), 0))
        .scalar()
    )

    last_row = rows[-1]
    last_increment = (
        db.query(Metric)
        .filter(Metric.camera_id == camera_id, Metric.delta > 0)
        .order_by(Metric.timestamp.desc())
        .first()
    )
    downtime = True
    if last_increment:
        downtime = (now - last_increment.timestamp).total_seconds() > downtime_minutes * 60

    return {
        "camera_id": camera_id,
        "units_per_hour": round(units_per_hour, 2),
        "total_units_today": int(today_total or 0),
        "last_update": last_row.timestamp.isoformat(),
        "current_count": last_row.count,
        "downtime": downtime,
    }


@app.get("/evidence/{camera_id}")
def evidence(
    camera_id: str,
    _: Annotated[str, Depends(verify_auth)],
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(EvidenceFrame)
        .filter(EvidenceFrame.camera_id == camera_id)
        .order_by(EvidenceFrame.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "event_type": r.event_type,
            "image_url": f"/evidence/file/{r.id}",
        }
        for r in rows
    ]


@app.get("/evidence/file/{evidence_id}")
def evidence_file(evidence_id: int, _: Annotated[str, Depends(verify_auth)], db: Session = Depends(get_db)):
    row = db.query(EvidenceFrame).filter(EvidenceFrame.id == evidence_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if not Path(row.file_path).exists():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(row.file_path, media_type="image/jpeg")
