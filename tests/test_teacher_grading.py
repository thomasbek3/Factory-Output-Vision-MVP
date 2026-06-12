from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.teacher_grading import (
    grade_teacher_labels_against_truth,
    write_teacher_grade_report,
)
from scripts import grade_teacher_labels_vs_truth


def _truth_ledger(tmp_path: Path, timestamps: list[float]) -> Path:
    path = tmp_path / "truth_ledger.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "human-truth-ledger-v1",
                "expected_human_total": len(timestamps),
                "events": [
                    {"truth_event_id": f"truth-{index:04d}", "event_ts": ts, "count_total": index + 1}
                    for index, ts in enumerate(timestamps)
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _labels_file(tmp_path: Path, entries: list[dict], name: str = "labels.json") -> Path:
    path = tmp_path / name
    labels = []
    for index, entry in enumerate(entries):
        labels.append(
            {
                "label_id": f"label-{index:04d}",
                "packet_id": entry.get("packet_id", f"packet-{index:04d}"),
                "verification_decision": entry["decision"],
                "suggested_event_ts_sec": entry.get("ts"),
                "confidence_tier": entry.get("confidence", "medium"),
                "rationale": entry.get("rationale", "test label"),
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-labels-v1",
                "provider": {"name": "fake_verifier", "mode": "fake_local_test", "model": None, "prompt_version": "test-v1"},
                "labels": labels,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_perfect_predictions_score_full_marks(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0, 20.0, 30.0])
    labels = _labels_file(
        tmp_path,
        [
            {"decision": "assert_completed", "ts": 10.0},
            {"decision": "assert_completed", "ts": 20.0},
            {"decision": "assert_completed", "ts": 30.0},
        ],
    )
    report = grade_teacher_labels_against_truth(teacher_labels_path=labels, truth_ledger_path=truth)
    grade = report["per_tolerance"]["5"]
    assert grade["precision"] == 1.0
    assert grade["recall"] == 1.0
    assert grade["f1"] == 1.0
    assert grade["mean_abs_timing_error_sec"] == 0.0


def test_false_positive_and_false_negative_counted(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0, 20.0, 30.0])
    labels = _labels_file(
        tmp_path,
        [
            {"decision": "assert_completed", "ts": 10.0},
            {"decision": "assert_completed", "ts": 50.0},  # false positive
            {"decision": "refute_completed"},  # not a prediction
        ],
    )
    report = grade_teacher_labels_against_truth(teacher_labels_path=labels, truth_ledger_path=truth)
    grade = report["per_tolerance"]["5"]
    assert grade["true_positives"] == 1
    assert grade["false_positives"] == 1
    assert grade["false_negatives"] == 2
    assert grade["precision"] == 0.5
    assert report["decision_histogram"]["refute_completed"] == 1


def test_tolerance_sweep_changes_matching(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0])
    labels = _labels_file(tmp_path, [{"decision": "assert_completed", "ts": 13.0}])
    report = grade_teacher_labels_against_truth(
        teacher_labels_path=labels, truth_ledger_path=truth, tolerances_sec=(2.0, 5.0)
    )
    assert report["per_tolerance"]["2"]["true_positives"] == 0
    assert report["per_tolerance"]["5"]["true_positives"] == 1
    assert report["per_tolerance"]["5"]["mean_abs_timing_error_sec"] == 3.0


def test_duplicate_asserts_are_deduped_not_punished(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0])
    labels = _labels_file(
        tmp_path,
        [
            {"decision": "assert_completed", "ts": 9.8, "packet_id": "packet-a"},
            {"decision": "assert_completed", "ts": 10.4, "packet_id": "packet-b"},  # overlap duplicate
        ],
    )
    report = grade_teacher_labels_against_truth(teacher_labels_path=labels, truth_ledger_path=truth)
    assert report["prediction_count"] == 2
    assert report["deduped_prediction_count"] == 1
    assert report["duplicate_merged_count"] == 1
    assert report["per_tolerance"]["5"]["false_positives"] == 0


def test_global_offset_shifts_predictions(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [70.0])
    labels = _labels_file(tmp_path, [{"decision": "assert_completed", "ts": 10.0}])
    report = grade_teacher_labels_against_truth(
        teacher_labels_path=labels, truth_ledger_path=truth, segment_offset_sec=60.0
    )
    assert report["per_tolerance"]["2"]["true_positives"] == 1


def test_segment_manifest_maps_per_segment_offsets(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0, 70.0])

    packet_rows = []
    for packet_id, segment_id, center in (("packet-a", "chunk_000", 10.0), ("packet-b", "chunk_001", 10.0)):
        packet_path = tmp_path / f"{packet_id}.json"
        packet_path.write_text(
            json.dumps(
                {
                    "packet_id": packet_id,
                    "segment_id": segment_id,
                    "window": {"start_offset_sec": center - 4.0, "center_offset_sec": center, "end_offset_sec": center + 4.0},
                }
            ),
            encoding="utf-8",
        )
        packet_rows.append({"packet_id": packet_id, "packet_manifest_path": str(packet_path)})
    packet_manifest = tmp_path / "evidence_manifest.json"
    packet_manifest.write_text(json.dumps({"packets": packet_rows}), encoding="utf-8")

    segment_manifest = tmp_path / "segment_manifest.json"
    segment_manifest.write_text(
        json.dumps(
            {
                "segments": [
                    {"segment_id": "chunk_000", "path": "a.mkv", "start_wall_ts": "2026-01-01T00:00:00", "duration_sec": 60.0},
                    {"segment_id": "chunk_001", "path": "b.mkv", "start_wall_ts": "2026-01-01T00:01:00", "duration_sec": 60.0},
                ]
            }
        ),
        encoding="utf-8",
    )

    labels = _labels_file(
        tmp_path,
        [
            {"decision": "assert_completed", "ts": 10.0, "packet_id": "packet-a"},
            {"decision": "assert_completed", "ts": 10.0, "packet_id": "packet-b"},
        ],
    )
    report = grade_teacher_labels_against_truth(
        teacher_labels_path=labels,
        truth_ledger_path=truth,
        packet_manifest_path=packet_manifest,
        segment_manifest_path=segment_manifest,
    )
    grade = report["per_tolerance"]["2"]
    assert grade["true_positives"] == 2
    assert report["segment_offsets"] == {"chunk_000": 0.0, "chunk_001": 60.0}


def test_unknown_segment_is_unmappable_not_wrong(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0])
    segment_manifest = tmp_path / "segment_manifest.json"
    segment_manifest.write_text(json.dumps({"segments": []}), encoding="utf-8")
    labels = _labels_file(tmp_path, [{"decision": "assert_completed", "ts": 10.0, "packet_id": "packet-x"}])

    report = grade_teacher_labels_against_truth(
        teacher_labels_path=labels,
        truth_ledger_path=truth,
        segment_manifest_path=segment_manifest,
    )
    assert report["deduped_prediction_count"] == 0
    assert report["unmappable_predictions"] == [{"packet_id": "packet-x", "reason": "unknown_segment_offset"}]


def test_missed_truth_diagnostics_names_covering_packet(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0])
    packet_path = tmp_path / "packet-a.json"
    packet_path.write_text(
        json.dumps(
            {
                "packet_id": "packet-a",
                "segment_id": "chunk_000",
                "window": {"start_offset_sec": 6.0, "center_offset_sec": 10.0, "end_offset_sec": 14.0},
            }
        ),
        encoding="utf-8",
    )
    packet_manifest = tmp_path / "evidence_manifest.json"
    packet_manifest.write_text(
        json.dumps({"packets": [{"packet_id": "packet-a", "packet_manifest_path": str(packet_path)}]}),
        encoding="utf-8",
    )

    labels = _labels_file(tmp_path, [{"decision": "refute_completed", "packet_id": "packet-a"}])
    report = grade_teacher_labels_against_truth(
        teacher_labels_path=labels,
        truth_ledger_path=truth,
        packet_manifest_path=packet_manifest,
    )
    missed = report["diagnostics"]["missed_truth_events"]
    assert len(missed) == 1
    assert missed[0]["covered_by_packet"] is True
    assert missed[0]["nearest_packet"]["packet_id"] == "packet-a"
    assert missed[0]["nearest_packet"]["decision"] == "refute_completed"


def test_report_is_deterministic_and_respects_force(tmp_path: Path) -> None:
    truth = _truth_ledger(tmp_path, [10.0])
    labels = _labels_file(tmp_path, [{"decision": "assert_completed", "ts": 10.0}])
    first = grade_teacher_labels_against_truth(teacher_labels_path=labels, truth_ledger_path=truth)
    second = grade_teacher_labels_against_truth(teacher_labels_path=labels, truth_ledger_path=truth)
    assert first == second

    output = tmp_path / "grade.json"
    write_teacher_grade_report(output, first)
    with pytest.raises(FileExistsError):
        write_teacher_grade_report(output, first)
    write_teacher_grade_report(output, first, force=True)


def test_cli_smoke(tmp_path: Path, capsys) -> None:
    truth = _truth_ledger(tmp_path, [10.0, 20.0])
    labels = _labels_file(tmp_path, [{"decision": "assert_completed", "ts": 10.0}])
    output = tmp_path / "grade.json"

    exit_code = grade_teacher_labels_vs_truth.main(
        ["--teacher-labels", str(labels), "--truth-ledger", str(truth), "--output", str(output), "--force"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    summary = json.loads(captured.out)
    assert summary["recall@5s"] == 0.5
    assert summary["true_positives"] == 1
    assert output.exists()
