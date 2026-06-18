from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VerdictLabel = Literal["assert", "refute"]


@dataclass(frozen=True)
class PlacementVerdict:
    center_sec: float
    decision: VerdictLabel
    score: float | None = None
    candidate_id: str | None = None


@dataclass(frozen=True)
class PlacementCountEvent:
    count: int
    center_sec: float
    start_sec: float
    end_sec: float
    candidate_ids: list[str]


class PlacementCounter:
    """Count quiet -> placement -> quiet transitions from clip-level verdicts."""

    def __init__(self, *, debounce_sec: float = 25.0) -> None:
        if debounce_sec <= 0:
            raise ValueError("debounce_sec must be positive")
        self.debounce_sec = float(debounce_sec)
        self.total_count = 0
        self._state = "quiet"
        self._pending_start: float | None = None
        self._pending_last: float | None = None
        self._pending_ids: list[str] = []
        self._last_count_center: float | None = None

    @property
    def state(self) -> str:
        return self._state

    def update(self, verdict: PlacementVerdict) -> list[PlacementCountEvent]:
        if verdict.decision == "assert":
            self._observe_placement(verdict)
            return []
        return self._observe_quiet(verdict.center_sec)

    def _observe_placement(self, verdict: PlacementVerdict) -> None:
        if self._last_count_center is not None and verdict.center_sec - self._last_count_center <= self.debounce_sec:
            return
        if self._state == "quiet":
            self._state = "placement"
            self._pending_start = verdict.center_sec
            self._pending_ids = []
        self._pending_last = verdict.center_sec
        if verdict.candidate_id:
            self._pending_ids.append(verdict.candidate_id)

    def _observe_quiet(self, quiet_sec: float) -> list[PlacementCountEvent]:
        if self._state != "placement" or self._pending_start is None or self._pending_last is None:
            self._state = "quiet"
            return []
        center_sec = (self._pending_start + self._pending_last) / 2.0
        if self._last_count_center is not None and center_sec - self._last_count_center <= self.debounce_sec:
            self._reset_pending()
            return []
        self.total_count += 1
        event = PlacementCountEvent(
            count=self.total_count,
            center_sec=center_sec,
            start_sec=self._pending_start,
            end_sec=quiet_sec,
            candidate_ids=list(self._pending_ids),
        )
        self._last_count_center = center_sec
        self._reset_pending()
        return [event]

    def _reset_pending(self) -> None:
        self._state = "quiet"
        self._pending_start = None
        self._pending_last = None
        self._pending_ids = []


def count_placements(verdicts: list[PlacementVerdict], *, debounce_sec: float = 25.0) -> list[PlacementCountEvent]:
    counter = PlacementCounter(debounce_sec=debounce_sec)
    events: list[PlacementCountEvent] = []
    for verdict in sorted(verdicts, key=lambda row: row.center_sec):
        events.extend(counter.update(verdict))
    return events
