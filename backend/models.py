from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from backend.database import Base


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    count = Column(Integer, nullable=False)
    delta = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    ratio = Column(Float, nullable=False, default=0.0)
    downtime = Column(Boolean, nullable=False, default=False)
    reset_detected = Column(Boolean, nullable=False, default=False)


class EvidenceFrame(Base):
    __tablename__ = "evidence_frames"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    event_type = Column(String(32), nullable=False)
    file_path = Column(Text, nullable=False)
