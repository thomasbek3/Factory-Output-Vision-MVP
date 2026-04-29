from __future__ import annotations

import json
from pathlib import Path

from app.services.event_ledger import (
    CorrectionEvent,
    CountEventRecord,
    EventLedger,
    ResidentObject,
    SourceToken,
    UncertainEvent,
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_event_ledger_appends_count_and_uncertain_events(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path)

    token = SourceToken(
        token_id="token-1",
        track_id=7,
        created_frame=10,
        last_frame=14,
        source_bbox=(5, 10, 20, 20),
        evidence_score=0.91,
    )
    resident = ResidentObject(
        resident_id="resident-1",
        track_id=7,
        created_frame=22,
        bbox=(65, 12, 20, 20),
        source_token_id="token-1",
    )
    ledger.record_count(
        CountEventRecord(
            event_id="count-1",
            frame_index=22,
            track_id=7,
            source_token_id=token.token_id,
            resident_id=resident.resident_id,
            reason="stable_in_output",
            bbox=(65, 12, 20, 20),
            state_path=["NEW_TRACK", "SOURCE_CONFIRMED", "IN_OUTPUT_UNSETTLED", "COUNTED_OUTPUT_RESIDENT"],
            count_authority="source_token_authorized",
            evidence_score=0.88,
        ),
        source_token=token,
        resident=resident,
    )
    ledger.record_uncertain(
        UncertainEvent(
            event_id="uncertain-1",
            frame_index=30,
            track_id=8,
            reason="token_expired_before_output",
            bbox=(42, 12, 20, 20),
            state_path=["NEW_TRACK", "SOURCE_CONFIRMED", "OBSERVING"],
            evidence_score=0.41,
        )
    )

    events = read_jsonl(tmp_path / "events.jsonl")
    residents = read_jsonl(tmp_path / "residents.jsonl")

    assert [event["type"] for event in events] == ["count", "uncertain"]
    assert events[0]["source_token_id"] == "token-1"
    assert events[0]["count_authority"] == "source_token_authorized"
    assert events[0]["state_path"][-1] == "COUNTED_OUTPUT_RESIDENT"
    assert events[1]["reason"] == "token_expired_before_output"
    assert residents == [
        {
            "type": "resident",
            "resident_id": "resident-1",
            "track_id": 7,
            "created_frame": 22,
            "bbox": [65, 12, 20, 20],
            "source_token_id": "token-1",
            "matched_track_ids": [7],
            "active": True,
        }
    ]


def test_event_ledger_records_runtime_inferred_only_count(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path)

    ledger.record_count(
        CountEventRecord(
            event_id="count-2",
            frame_index=42,
            track_id=15,
            source_token_id=None,
            resident_id="resident-2",
            reason="approved_delivery_chain",
            bbox=(80, 18, 25, 20),
            state_path=["OBSERVING", "IN_OUTPUT_UNSETTLED", "COUNTED_OUTPUT_RESIDENT"],
            count_authority="runtime_inferred_only",
            evidence_score=0.52,
        )
    )

    events = read_jsonl(tmp_path / "events.jsonl")

    assert events == [
        {
            "type": "count",
            "event_id": "count-2",
            "frame_index": 42,
            "track_id": 15,
            "source_token_id": None,
            "resident_id": "resident-2",
            "reason": "approved_delivery_chain",
            "bbox": [80, 18, 25, 20],
            "state_path": ["OBSERVING", "IN_OUTPUT_UNSETTLED", "COUNTED_OUTPUT_RESIDENT"],
            "count_authority": "runtime_inferred_only",
            "evidence_score": 0.52,
        }
    ]


def test_event_ledger_records_corrections_and_reload_residents(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path)
    ledger.record_resident(
        ResidentObject(
            resident_id="resident-existing",
            track_id=3,
            created_frame=5,
            bbox=(70, 15, 18, 18),
            source_token_id=None,
            matched_track_ids=[3, 9],
        )
    )
    ledger.record_correction(
        CorrectionEvent(
            event_id="correction-1",
            frame_index=50,
            target_event_id="count-1",
            action="delete_count",
            reason="operator marked duplicate reposition",
        )
    )

    reloaded = EventLedger(tmp_path)

    assert reloaded.residents["resident-existing"].matched_track_ids == [3, 9]
    events = read_jsonl(tmp_path / "events.jsonl")
    assert events == [
        {
            "type": "correction",
            "event_id": "correction-1",
            "frame_index": 50,
            "target_event_id": "count-1",
            "action": "delete_count",
            "reason": "operator marked duplicate reposition",
        }
    ]
