from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class MetricIn(BaseModel):
    camera_id: str
    timestamp: datetime
    count: int
    delta: int
    confidence: float
    ratio: float = 0.0
    downtime: bool = False
    reset_detected: bool = False


class MetricOut(MetricIn):
    id: int

    class Config:
        from_attributes = True
