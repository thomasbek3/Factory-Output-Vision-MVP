from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from app.services.calibration import Box

CountAuthority = Literal["source_token_authorized", "runtime_inferred_only"]
CountReason = Literal["stable_in_output", "disappeared_in_output", "approved_delivery_chain"]
UncertainReason = Literal[
    "token_expired_before_output",
    "missing_gate_crossing",
    "ambiguous_resident_match",
    "disappeared_outside_output",
    "wrong_direction",
    "low_confidence",
]
CorrectionAction = Literal["delete_count", "add_count", "mark_uncertain", "merge_resident"]


@dataclass(frozen=True)
class SourceToken:
    token_id: str
    track_id: int
    created_frame: int
    last_frame: int
    source_bbox: Box
    evidence_score: float = 1.0


@dataclass
class ResidentObject:
    resident_id: str
    track_id: int
    created_frame: int
    bbox: Box
    source_token_id: str | None
    matched_track_ids: list[int] = field(default_factory=list)
    active: bool = True

    def __post_init__(self) -> None:
        if not self.matched_track_ids:
            self.matched_track_ids = [self.track_id]


@dataclass(frozen=True)
class CountEventRecord:
    event_id: str
    frame_index: int
    track_id: int
    source_token_id: str | None
    resident_id: str
    reason: CountReason
    bbox: Box
    state_path: list[str]
    count_authority: CountAuthority = "source_token_authorized"
    evidence_score: float = 1.0


@dataclass(frozen=True)
class UncertainEvent:
    event_id: str
    frame_index: int
    track_id: int
    reason: UncertainReason | str
    bbox: Box | None
    state_path: list[str]
    evidence_score: float = 0.0


@dataclass(frozen=True)
class CorrectionEvent:
    event_id: str
    frame_index: int
    target_event_id: str
    action: CorrectionAction | str
    reason: str


class EventLedger:
    """Append-only JSONL ledger for count evidence and resident output objects."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root_dir / "events.jsonl"
        self.residents_path = self.root_dir / "residents.jsonl"
        self.residents: dict[str, ResidentObject] = self._load_residents()

    def record_count(
        self,
        event: CountEventRecord,
        *,
        source_token: SourceToken | None = None,
        resident: ResidentObject | None = None,
    ) -> None:
        if resident is not None:
            self.record_resident(resident)
        payload = self._with_type("count", event)
        if source_token is not None:
            payload["source_token"] = self._normalize(asdict(source_token))
        self._append_jsonl(self.events_path, payload)

    def record_uncertain(self, event: UncertainEvent) -> None:
        self._append_jsonl(self.events_path, self._with_type("uncertain", event))

    def record_correction(self, event: CorrectionEvent) -> None:
        self._append_jsonl(self.events_path, self._with_type("correction", event))

    def record_resident(self, resident: ResidentObject) -> None:
        self.residents[resident.resident_id] = resident
        self._append_jsonl(self.residents_path, self._with_type("resident", resident))

    def _load_residents(self) -> dict[str, ResidentObject]:
        residents: dict[str, ResidentObject] = {}
        if not self.residents_path.exists():
            return residents
        for line in self.residents_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("type") != "resident":
                continue
            residents[row["resident_id"]] = ResidentObject(
                resident_id=row["resident_id"],
                track_id=row["track_id"],
                created_frame=row["created_frame"],
                bbox=tuple(row["bbox"]),  # type: ignore[arg-type]
                source_token_id=row.get("source_token_id"),
                matched_track_ids=list(row.get("matched_track_ids", [])),
                active=bool(row.get("active", True)),
            )
        return residents

    def _with_type(self, event_type: str, record: object) -> dict:
        payload = self._normalize(asdict(record))
        return {"type": event_type, **payload}

    def _append_jsonl(self, path: Path, payload: dict) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")

    def _normalize(self, value):
        if isinstance(value, tuple):
            return [self._normalize(item) for item in value]
        if isinstance(value, list):
            return [self._normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._normalize(item) for key, item in value.items()}
        return value
