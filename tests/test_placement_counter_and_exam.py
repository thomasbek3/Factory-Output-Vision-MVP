from __future__ import annotations

from app.services.placement_counter import PlacementCounter, PlacementVerdict, count_placements
from scripts.run_clip_exam import run_exam_from_candidates, score_counts_against_gold, split_edge_truncated_candidates


def test_placement_counter_counts_quiet_placement_quiet_and_debounces_double_trigger() -> None:
    counter = PlacementCounter(debounce_sec=25)

    events = []
    events.extend(counter.update(PlacementVerdict(center_sec=10, decision="assert", candidate_id="a1")))
    events.extend(counter.update(PlacementVerdict(center_sec=12, decision="refute", candidate_id="q1")))
    events.extend(counter.update(PlacementVerdict(center_sec=20, decision="assert", candidate_id="a2")))
    events.extend(counter.update(PlacementVerdict(center_sec=22, decision="refute", candidate_id="q2")))
    events.extend(counter.update(PlacementVerdict(center_sec=50, decision="assert", candidate_id="a3")))
    events.extend(counter.update(PlacementVerdict(center_sec=55, decision="assert", candidate_id="a4")))
    events.extend(counter.update(PlacementVerdict(center_sec=60, decision="refute", candidate_id="q3")))

    assert [event.center_sec for event in events] == [10.0, 52.5]
    assert counter.total_count == 2


def test_count_placements_requires_return_to_quiet() -> None:
    events = count_placements([PlacementVerdict(center_sec=10, decision="assert")])

    assert events == []


def test_count_placements_default_does_not_finalize_trailing_assert() -> None:
    events = count_placements([PlacementVerdict(center_sec=10, decision="assert", candidate_id="a1")])

    assert events == []


def test_count_placements_exam_mode_finalizes_trailing_assert() -> None:
    events = count_placements(
        [PlacementVerdict(center_sec=10, decision="assert", candidate_id="a1")],
        finalize_at_end=True,
    )

    assert len(events) == 1
    assert events[0].center_sec == 10
    assert events[0].candidate_ids == ["a1"]


def test_exam_scorer_reports_matched_missed_and_false_counts() -> None:
    score = score_counts_against_gold(count_times=[100, 250, 999], gold_times=[101, 260, 400], match_tolerance_sec=20)

    assert score["matched"] == 2
    assert score["missed"] == 1
    assert score["false_counts"] == 1
    assert not score["passed"]


def test_run_exam_from_synthetic_verdicts_passes_only_clean_counts() -> None:
    candidates = [
        {"candidate_id": "c1", "center_sec": 100},
        {"candidate_id": "quiet1", "center_sec": 105},
        {"candidate_id": "c2", "center_sec": 300},
        {"candidate_id": "quiet2", "center_sec": 305},
    ]

    def judge(candidate):
        return {"decision": "assert" if candidate["candidate_id"].startswith("c") else "refute", "score": 0.9}

    result = run_exam_from_candidates(
        candidates=candidates,
        gold_offsets=[100, 300],
        judge=judge,
        debounce_sec=25,
        match_tolerance_sec=20,
    )

    assert result["matched"] == 2
    assert result["missed"] == 0
    assert result["false_counts"] == 0
    assert result["passed"]


def test_edge_truncated_candidate_is_refuted_without_judge_call(caplog) -> None:
    ready, refutes = split_edge_truncated_candidates(
        candidates=[{"candidate_id": "edge-1", "center_sec": 9.8, "start_sec": 9.2, "end_sec": 10.0}],
        duration_sec=10.0,
        bracket_sec=1.0,
    )

    def judge(_candidate):
        raise AssertionError("edge-truncated candidate should not reach judge")

    result = run_exam_from_candidates(
        candidates=[*ready, *refutes],
        gold_offsets=[9.8],
        judge=judge,
        debounce_sec=0.5,
        match_tolerance_sec=1.0,
        finalize_at_end=True,
    )

    assert ready == []
    assert refutes[0]["skip_judge_reason"] == "clip window truncated at video edge"
    assert result["count_times"] == []
    assert "edge-1 judged refute: clip window truncated at video edge" in caplog.text
