from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import build_factory2_final_two_chain_adjudication as builder


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_review_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "item_id",
                "crop_label",
                "relation_label",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _base_event(
    *,
    event_id: str,
    event_ts: float,
    runtime_track_id: int,
    source_track_id: int | None,
    prior_event_ts: float | None,
    prior_track_id: int | None,
    track_summaries: list[dict],
) -> dict:
    return {
        "event_id": event_id,
        "event_ts": event_ts,
        "runtime_track_id": runtime_track_id,
        "source_track_id": source_track_id,
        "prior_runtime_event": (
            {
                "event_ts": prior_event_ts,
                "track_id": prior_track_id,
                "provenance_status": "inherited_live_source_token",
            }
            if prior_event_ts is not None and prior_track_id is not None
            else None
        ),
        "track_summaries": track_summaries,
        "window_runtime_events": [],
        "review_window": {"start_seconds": event_ts - 4.0, "end_seconds": event_ts + 2.0},
        "count_total": 0,
        "source_gap_seconds": None,
    }


def test_chain_adjudication_marks_both_divergent_runtime_events_as_duplicates(tmp_path: Path) -> None:
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [
            {
                "item_id": "event-7-track-000105-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "same chain",
            },
            {
                "item_id": "event-7-track-000108-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "duplicate output",
            },
            {
                "item_id": "event-8-track-000145-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "distinct_new_delivery",
                "notes": "earlier separate delivery",
            },
            {
                "item_id": "event-8-track-000146-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "distinct_new_delivery",
                "notes": "earlier separate delivery output",
            },
            {
                "item_id": "event-8-track-000151-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "prior counted delivery",
            },
            {
                "item_id": "event-8-track-000152-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "duplicate output",
            },
        ],
    )
    review_report = _write_json(
        tmp_path / "divergent_chain_review.json",
        {
            "schema_version": "factory2-divergent-chain-review-v1",
            "review_labels_csv_path": str(review_csv),
            "events": [
                _base_event(
                    event_id="factory2-runtime-only-0007",
                    event_ts=305.708,
                    runtime_track_id=108,
                    source_track_id=105,
                    prior_event_ts=303.508,
                    prior_track_id=107,
                    track_summaries=[
                        {"track_id": 105, "track_role": "source_anchor", "track_class": "source_only", "source_frames": 12, "output_frames": 0},
                        {"track_id": 107, "track_role": "prior_runtime_event", "track_class": "source_to_output", "source_frames": 6, "output_frames": 3},
                        {"track_id": 108, "track_role": "divergent_runtime_event", "track_class": "output_only", "source_frames": 0, "output_frames": 2},
                        {"track_id": 109, "track_role": "window_context", "track_class": "output_only", "source_frames": 0, "output_frames": 2},
                    ],
                ),
                _base_event(
                    event_id="factory2-runtime-only-0008",
                    event_ts=425.012,
                    runtime_track_id=152,
                    source_track_id=145,
                    prior_event_ts=422.612,
                    prior_track_id=151,
                    track_summaries=[
                        {"track_id": 145, "track_role": "source_anchor", "track_class": "source_only", "source_frames": 2, "output_frames": 0},
                        {"track_id": 146, "track_role": "runtime_event_context", "track_class": "output_only", "source_frames": 0, "output_frames": 5},
                        {"track_id": 151, "track_role": "prior_runtime_event", "track_class": "source_to_output", "source_frames": 6, "output_frames": 5},
                        {"track_id": 152, "track_role": "divergent_runtime_event", "track_class": "output_only", "source_frames": 0, "output_frames": 2},
                    ],
                ),
            ],
            "items": [
                {"item_id": "event-7-track-000105-obs-01", "event_id": "factory2-runtime-only-0007", "track_id": 105, "track_role": "source_anchor", "track_class": "source_only"},
                {"item_id": "event-7-track-000108-obs-01", "event_id": "factory2-runtime-only-0007", "track_id": 108, "track_role": "divergent_runtime_event", "track_class": "output_only"},
                {"item_id": "event-8-track-000145-obs-01", "event_id": "factory2-runtime-only-0008", "track_id": 145, "track_role": "source_anchor", "track_class": "source_only"},
                {"item_id": "event-8-track-000146-obs-01", "event_id": "factory2-runtime-only-0008", "track_id": 146, "track_role": "runtime_event_context", "track_class": "output_only"},
                {"item_id": "event-8-track-000151-obs-01", "event_id": "factory2-runtime-only-0008", "track_id": 151, "track_role": "prior_runtime_event", "track_class": "source_to_output"},
                {"item_id": "event-8-track-000152-obs-01", "event_id": "factory2-runtime-only-0008", "track_id": 152, "track_role": "divergent_runtime_event", "track_class": "output_only"},
            ],
        },
    )
    rescue_report = _write_json(
        tmp_path / "rescue_dataset.json",
        {
            "schema_version": "factory2-final-two-rescue-dataset-v1",
            "relation_label_counts": {
                "distinct_new_delivery": 2,
                "same_delivery_as_prior": 4,
                "static_resident": 0,
            },
        },
    )
    output_report = tmp_path / "out" / "chain_adjudication.json"
    package_dir = tmp_path / "out" / "chain_adjudication"

    result = builder.build_final_two_chain_adjudication(
        review_report_path=review_report,
        rescue_report_path=rescue_report,
        output_report_path=output_report,
        package_dir=package_dir,
        review_labels_csv_path=None,
        force=False,
    )

    assert result["schema_version"] == "factory2-final-two-chain-adjudication-v1"
    assert result["event_count"] == 2
    assert result["summary"] == {
        "duplicate_of_prior_runtime_event": 2,
        "proof_mints_allowed": 0,
        "source_authority_blocked": 0,
        "source_backed_new_candidates": 0,
        "static_resident": 0,
        "unresolved": 0,
    }
    event_by_id = {row["event_id"]: row for row in result["events"]}
    first = event_by_id["factory2-runtime-only-0007"]
    second = event_by_id["factory2-runtime-only-0008"]
    assert first["adjudication"] == "duplicate_of_prior_runtime_event"
    assert first["proof_action"] == "do_not_mint"
    assert first["runtime_action"] == "suppress_or_mark_duplicate"
    assert first["duplicate_of_event_ts"] == 303.508
    assert first["divergent_track_relation_label"] == "same_delivery_as_prior"
    assert second["adjudication"] == "duplicate_of_prior_runtime_event"
    assert second["proof_action"] == "do_not_mint"
    assert second["runtime_action"] == "suppress_or_mark_duplicate"
    assert second["duplicate_of_event_ts"] == 422.612
    assert second["divergent_track_relation_label"] == "same_delivery_as_prior"
    assert second["distinct_new_delivery_track_ids"] == [145, 146]
    assert Path(result["adjudication_rows_csv_path"]).exists()
    assert Path(result["evidence_pairs_csv_path"]).exists()
    assert json.loads(output_report.read_text(encoding="utf-8")) == result


def test_chain_adjudication_blocks_distinct_label_when_source_authority_is_consumed(tmp_path: Path) -> None:
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [
            {
                "item_id": "event-9-track-000207-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "already counted source",
            },
            {
                "item_id": "event-9-track-000210-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "distinct_new_delivery",
                "notes": "candidate new output",
            },
        ],
    )
    review_report = _write_json(
        tmp_path / "divergent_chain_review.json",
        {
            "schema_version": "factory2-divergent-chain-review-v1",
            "review_labels_csv_path": str(review_csv),
            "events": [
                _base_event(
                    event_id="factory2-runtime-only-0009",
                    event_ts=512.0,
                    runtime_track_id=210,
                    source_track_id=207,
                    prior_event_ts=510.0,
                    prior_track_id=207,
                    track_summaries=[
                        {"track_id": 207, "track_role": "prior_runtime_event", "track_class": "source_to_output", "source_frames": 5, "output_frames": 4},
                        {"track_id": 210, "track_role": "divergent_runtime_event", "track_class": "output_only", "source_frames": 0, "output_frames": 2},
                    ],
                )
            ],
            "items": [
                {"item_id": "event-9-track-000207-obs-01", "event_id": "factory2-runtime-only-0009", "track_id": 207, "track_role": "prior_runtime_event", "track_class": "source_to_output"},
                {"item_id": "event-9-track-000210-obs-01", "event_id": "factory2-runtime-only-0009", "track_id": 210, "track_role": "divergent_runtime_event", "track_class": "output_only"},
            ],
        },
    )
    rescue_report = _write_json(
        tmp_path / "rescue_dataset.json",
        {"schema_version": "factory2-final-two-rescue-dataset-v1"},
    )

    result = builder.build_final_two_chain_adjudication(
        review_report_path=review_report,
        rescue_report_path=rescue_report,
        output_report_path=tmp_path / "out" / "chain_adjudication.json",
        package_dir=tmp_path / "out" / "chain_adjudication",
        review_labels_csv_path=None,
        force=False,
    )

    event = result["events"][0]
    assert event["divergent_track_relation_label"] == "distinct_new_delivery"
    assert event["adjudication"] == "source_authority_blocked"
    assert event["proof_action"] == "do_not_mint"
    assert event["runtime_action"] == "leave_runtime_inferred_only"
    assert event["source_authority_status"] == "already_consumed_or_not_fresh"
    assert event["countable"] is False


def test_chain_adjudication_marks_static_resident_divergent_track(tmp_path: Path) -> None:
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [
            {
                "item_id": "event-10-track-000310-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "static_resident",
                "notes": "stack edge",
            }
        ],
    )
    review_report = _write_json(
        tmp_path / "divergent_chain_review.json",
        {
            "schema_version": "factory2-divergent-chain-review-v1",
            "review_labels_csv_path": str(review_csv),
            "events": [
                _base_event(
                    event_id="factory2-runtime-only-0010",
                    event_ts=600.0,
                    runtime_track_id=310,
                    source_track_id=None,
                    prior_event_ts=598.0,
                    prior_track_id=307,
                    track_summaries=[
                        {"track_id": 307, "track_role": "prior_runtime_event", "track_class": "source_to_output", "source_frames": 6, "output_frames": 5},
                        {"track_id": 310, "track_role": "divergent_runtime_event", "track_class": "output_only", "source_frames": 0, "output_frames": 2},
                    ],
                )
            ],
            "items": [
                {"item_id": "event-10-track-000310-obs-01", "event_id": "factory2-runtime-only-0010", "track_id": 310, "track_role": "divergent_runtime_event", "track_class": "output_only"}
            ],
        },
    )
    rescue_report = _write_json(
        tmp_path / "rescue_dataset.json",
        {"schema_version": "factory2-final-two-rescue-dataset-v1"},
    )

    result = builder.build_final_two_chain_adjudication(
        review_report_path=review_report,
        rescue_report_path=rescue_report,
        output_report_path=tmp_path / "out" / "chain_adjudication.json",
        package_dir=tmp_path / "out" / "chain_adjudication",
        review_labels_csv_path=None,
        force=False,
    )

    event = result["events"][0]
    assert event["adjudication"] == "static_resident"
    assert event["proof_action"] == "do_not_mint"
    assert event["runtime_action"] == "suppress_or_mark_static"
    assert event["countable"] is False


def test_chain_adjudication_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    review_csv = _write_review_csv(
        tmp_path / "review_labels.csv",
        [
            {
                "item_id": "event-7-track-000108-obs-01",
                "crop_label": "carried_panel",
                "relation_label": "same_delivery_as_prior",
                "notes": "",
            }
        ],
    )
    review_report = _write_json(
        tmp_path / "divergent_chain_review.json",
        {
            "schema_version": "factory2-divergent-chain-review-v1",
            "review_labels_csv_path": str(review_csv),
            "events": [
                _base_event(
                    event_id="factory2-runtime-only-0007",
                    event_ts=305.708,
                    runtime_track_id=108,
                    source_track_id=105,
                    prior_event_ts=303.508,
                    prior_track_id=107,
                    track_summaries=[
                        {"track_id": 108, "track_role": "divergent_runtime_event", "track_class": "output_only", "source_frames": 0, "output_frames": 2}
                    ],
                )
            ],
            "items": [
                {"item_id": "event-7-track-000108-obs-01", "event_id": "factory2-runtime-only-0007", "track_id": 108, "track_role": "divergent_runtime_event", "track_class": "output_only"}
            ],
        },
    )
    rescue_report = _write_json(
        tmp_path / "rescue_dataset.json",
        {"schema_version": "factory2-final-two-rescue-dataset-v1"},
    )
    output_report = tmp_path / "out" / "chain_adjudication.json"
    package_dir = tmp_path / "out" / "chain_adjudication"

    builder.build_final_two_chain_adjudication(
        review_report_path=review_report,
        rescue_report_path=rescue_report,
        output_report_path=output_report,
        package_dir=package_dir,
        review_labels_csv_path=None,
        force=False,
    )

    with pytest.raises(FileExistsError):
        builder.build_final_two_chain_adjudication(
            review_report_path=review_report,
            rescue_report_path=rescue_report,
            output_report_path=output_report,
            package_dir=package_dir,
            review_labels_csv_path=None,
            force=False,
        )
