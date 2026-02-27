from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Tuple


@dataclass
class CameraState:
    camera_id: str
    last_committed_count: int = 0
    candidate_count: int = 0
    persistence_hits: int = 0
    history: Deque[int] = field(default_factory=lambda: deque(maxlen=24))
    last_ratio: float = 0.0


def apply_state_logic(
    state: CameraState,
    measured_count: int,
    persistence_required: int = 2,
    reset_threshold: int = 2,
) -> Tuple[int, bool]:
    state.history.append(measured_count)

    if measured_count < max(0, state.last_committed_count - reset_threshold):
        state.last_committed_count = measured_count
        state.candidate_count = measured_count
        state.persistence_hits = 0
        return 0, True

    if measured_count > state.last_committed_count:
        if measured_count != state.candidate_count:
            state.candidate_count = measured_count
            state.persistence_hits = 1
            return 0, False

        state.persistence_hits += 1
        if state.persistence_hits >= persistence_required:
            delta = measured_count - state.last_committed_count
            state.last_committed_count = measured_count
            state.persistence_hits = 0
            return max(0, delta), False
    else:
        state.candidate_count = measured_count
        state.persistence_hits = 0

    return 0, False
