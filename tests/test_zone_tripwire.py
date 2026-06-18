from __future__ import annotations

import builtins
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.services.zone_tripwire import (
    PersonDetection,
    PersonOccupancySample,
    TripwireConfig,
    VisitEpisode,
    box_touches_trigger_zone,
    build_visit_episodes,
    expand_zone,
    load_person_detector,
    merge_person_visits_with_backstop,
    person_occupancy_for_frame,
    run_tripwire_on_video,
    split_visit_episode,
    tiled_change_score,
    visit_candidates_from_episodes,
    whole_zone_absdiff,
)
from scripts.validate_tripwire_recall import build_multi_recall_report_from_payloads, build_tripwire_recall_report


def test_tiled_absdiff_sees_thin_bar_that_whole_zone_mean_hides() -> None:
    before = np.zeros((80, 80), dtype=np.uint8)
    after = before.copy()
    after[0:10, 0:10] = 255
    after[10:20, 10:20] = 255
    after[20:30, 20:30] = 255

    tiled = tiled_change_score(before, after, grid_size=8, method="tiled_absdiff")
    whole = whole_zone_absdiff(before, after)

    assert tiled == 1.0
    assert whole < 0.05


def test_quiet_state_diff_fires_after_calm_before_after_pair(tmp_path: Path) -> None:
    video = tmp_path / "quiet.mp4"
    frames = []
    for index in range(30):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        if index >= 10:
            frame[40:44, 40:60] = 255
        frames.append(frame)
    write_video(video, frames, fps=10)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        config=TripwireConfig(
            trigger="pixel",
            sample_fps=10,
            burst_threshold=0.95,
            state_interval_sec=0.2,
            calm_threshold=0.01,
            state_threshold=0.2,
            min_flash_ratio=0.1,
            bracket_sec=1.0,
        ),
    )

    assert any(row["trigger_mode"] == "quiet_state_diff" for row in payload["candidates"])


def test_uniform_flash_is_rejected(tmp_path: Path) -> None:
    video = tmp_path / "flash.mp4"
    frames = []
    for index in range(20):
        value = 0 if index < 5 else 128
        frames.append(np.full((64, 64, 3), value, dtype=np.uint8))
    write_video(video, frames, fps=10)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        config=TripwireConfig(
            trigger="pixel",
            sample_fps=10,
            burst_threshold=0.1,
            state_interval_sec=0.2,
            calm_threshold=0.01,
            state_threshold=0.1,
            min_flash_ratio=1.5,
            bracket_sec=1.0,
        ),
    )

    assert payload["candidates"] == []
    assert payload["summary"]["dropped_flash_count"] > 0


def test_local_zone_placement_survives_large_outside_bench_motion(tmp_path: Path) -> None:
    video = tmp_path / "placement-plus-bench-motion.mp4"
    frames = []
    for index in range(20):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        if index >= 5:
            frame[:, :24] = 255
            frame[48:56, 48:56] = 255
        frames.append(frame)
    write_video(video, frames, fps=10)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        config=TripwireConfig(
            trigger="pixel",
            sample_fps=10,
            burst_threshold=0.5,
            state_interval_sec=0.2,
            calm_threshold=0.01,
            state_threshold=0.5,
            min_flash_ratio=1.5,
            bracket_sec=1.0,
        ),
    )

    assert any(row["trigger_mode"] == "motion_burst" for row in payload["candidates"])


def test_run_tripwire_samples_frames_at_approximately_target_fps(tmp_path: Path) -> None:
    video = tmp_path / "sampling.mp4"
    frames = []
    for index in range(30):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, :] = index
        frames.append(frame)
    write_video(video, frames, fps=30)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]],
        config=TripwireConfig(
            trigger="pixel",
            sample_fps=10,
            burst_threshold=1.0,
            state_interval_sec=0.5,
            calm_threshold=0.0,
            state_threshold=1.0,
            min_flash_ratio=1.5,
            bracket_sec=1.0,
        ),
    )

    sampled_frame_count = payload["summary"]["sample_count"] + 1
    assert 9 <= sampled_frame_count <= 11


def test_tripwire_recall_gate_passes_at_six_of_seven_and_fails_at_five() -> None:
    gold = [{"id": f"gold-{index}", "time": float(index * 100)} for index in range(7)]

    pass_report = build_tripwire_recall_report(
        candidates=[{"candidate_id": f"c-{index}", "time": float(index * 100)} for index in range(6)],
        gold=gold,
        match_tolerance_sec=20,
    )
    fail_report = build_tripwire_recall_report(
        candidates=[{"candidate_id": f"c-{index}", "time": float(index * 100)} for index in range(5)],
        gold=gold,
        match_tolerance_sec=20,
    )

    assert pass_report["summary"]["caught"] == 6
    assert pass_report["verdict"] == "PASS"
    assert fail_report["summary"]["caught"] == 5
    assert fail_report["verdict"] == "FAIL"


def test_person_trigger_marks_occupancy_only_for_confident_person_in_trigger_zone() -> None:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    trigger_bbox = (40.0, 40.0, 100.0, 100.0)

    assert person_occupancy_for_frame(
        frame,
        detector=FakeDetector([[PersonDetection((60, 60, 90, 90), 0.7, 0)]]),
        trigger_bbox=trigger_bbox,
        person_conf=0.35,
    )
    assert person_occupancy_for_frame(
        frame,
        detector=FakeDetector([[PersonDetection((60, 60, 90, 90), 0.2, 0)]]),
        trigger_bbox=trigger_bbox,
        person_conf=0.35,
    ) is None
    assert person_occupancy_for_frame(
        frame,
        detector=FakeDetector([[PersonDetection((0, 0, 20, 20), 0.9, 0)]]),
        trigger_bbox=trigger_bbox,
        person_conf=0.35,
    ) is None


def test_oversized_trigger_zone_expands_clamps_and_catches_margin_overlap() -> None:
    polygon = [[0.5, 0.5], [0.9, 0.5], [0.9, 0.9], [0.5, 0.9]]

    bbox = expand_zone(polygon, margin=0.25, frame_w=100, frame_h=100)

    assert bbox == (40.0, 40.0, 100.0, 100.0)
    assert box_touches_trigger_zone((42, 42, 48, 48), bbox)
    assert not box_touches_trigger_zone((20, 20, 30, 30), bbox)


def test_person_visit_episodes_merge_short_gaps_and_split_long_gaps() -> None:
    samples = [
        PersonOccupancySample(0.0, 0.7),
        PersonOccupancySample(3.0, 0.8),
        PersonOccupancySample(10.9, 0.6),
        PersonOccupancySample(20.0, 0.9),
    ]

    episodes = build_visit_episodes(samples, presence_gap_sec=8.0)

    assert episodes == [
        VisitEpisode(start_sec=0.0, end_sec=10.9, peak_confidence=0.8),
        VisitEpisode(start_sec=20.0, end_sec=20.0, peak_confidence=0.9),
    ]


def test_visit_episode_to_candidate_span_and_long_visit_cap() -> None:
    episode = VisitEpisode(start_sec=0.0, end_sec=130.0, peak_confidence=0.91)

    parts = split_visit_episode(episode, episode_max_sec=60.0)
    candidates = visit_candidates_from_episodes(
        [episode],
        duration_sec=140.0,
        episode_max_sec=60.0,
        episode_pad_sec=2.0,
        source="synthetic",
    )

    assert [(part.start_sec, part.end_sec) for part in parts] == [(0.0, 60.0), (60.0, 120.0), (120.0, 130.0)]
    assert len(candidates) == 3
    assert candidates[0].trigger_mode == "person_visit"
    assert candidates[0].start_sec == 0.0
    assert candidates[0].end_sec == 62.0
    assert candidates[0].episode_split_index == 1
    assert candidates[0].episode_split_count == 3


def test_backstop_merge_drops_pile_diff_inside_episode_and_keeps_outside() -> None:
    person_candidates = visit_candidates_from_episodes(
        [VisitEpisode(start_sec=10.0, end_sec=20.0, peak_confidence=0.8)],
        duration_sec=40.0,
        episode_max_sec=60.0,
        episode_pad_sec=2.0,
        source="synthetic",
    )
    inside = person_candidates[0].__class__(
        center_sec=15.0,
        start_sec=13.0,
        end_sec=17.0,
        trigger_mode="quiet_state_diff",
        peak_tile_score=0.5,
        flash_ratio=2.0,
    )
    outside = person_candidates[0].__class__(
        center_sec=30.0,
        start_sec=28.0,
        end_sec=32.0,
        trigger_mode="quiet_state_diff",
        peak_tile_score=0.5,
        flash_ratio=2.0,
    )

    merged, dropped = merge_person_visits_with_backstop(person_candidates, [inside, outside])

    assert dropped == 1
    assert [candidate.trigger_mode for candidate in merged] == ["person_visit", "quiet_state_diff"]
    assert merged[-1].center_sec == 30.0


def test_run_tripwire_person_presence_with_fake_detector_emits_one_visit(tmp_path: Path) -> None:
    video = tmp_path / "visit.mp4"
    frames = [np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(5)]
    write_video(video, frames, fps=1)

    payload = run_tripwire_on_video(
        video_path=video,
        output_zone_polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        config=TripwireConfig(
            trigger="person_presence",
            sample_fps=1,
            burst_threshold=1.0,
            state_threshold=1.0,
            presence_gap_sec=8.0,
            episode_max_sec=60.0,
            episode_pad_sec=2.0,
        ),
        person_detector=FakeDetector(
            [
                [],
                [PersonDetection((45, 45, 60, 60), 0.8, 0)],
                [PersonDetection((46, 45, 60, 60), 0.85, 0)],
                [],
                [],
            ]
        ),
    )

    assert payload["summary"]["person_detector"]["loaded_model"] == "injected"
    assert payload["summary"]["person_visit_count"] == 1
    assert payload["candidates"][0]["trigger_mode"] == "person_visit"
    assert payload["candidates"][0]["center_sec"] == 1.5


def test_multi_recall_report_scores_exam_and_pm_sets_with_dedup_counts() -> None:
    payload = {
        "summary": {"candidate_count_before_dedup": 1142, "candidate_count_after_dedup": 64},
        "candidates": [{"candidate_id": f"c-{index}", "center_sec": float(index * 100)} for index in range(7)],
    }
    gold = {"events": [{"id": f"gold-{index}", "clip_offset_sec": float(index * 100)} for index in range(7)]}

    report = build_multi_recall_report_from_payloads(
        tripwire_payload=payload,
        recall_sets={"exam": gold, "pm": gold},
        mode="clip_offsets",
        match_tolerance_sec=20.0,
    )

    assert report["verdict"] == "PASS"
    assert report["candidate_counts"]["before_dedup"] == 1142
    assert report["candidate_counts"]["after_dedup"] == 64
    assert report["recall_sets"]["exam"]["summary"]["caught"] == 7
    assert report["recall_sets"]["pm"]["summary"]["caught"] == 7


def test_load_person_detector_falls_back_to_yolov8n_when_medium_unavailable(monkeypatch) -> None:
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ultralytics":
            def fake_yolo(model_name):
                if model_name == "yolov8m.pt":
                    raise FileNotFoundError(model_name)
                return object()

            return SimpleNamespace(YOLO=fake_yolo)
        return real_import(name, globals, locals, fromlist, level)

    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    loaded = load_person_detector(TripwireConfig(trigger="person_presence"))

    assert loaded.status == "fallback_loaded"
    assert loaded.loaded_model == "yolov8n.pt"


def test_load_person_detector_skips_cleanly_when_ultralytics_missing(monkeypatch) -> None:
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ultralytics":
            raise ImportError("no ultralytics")
        return real_import(name, globals, locals, fromlist, level)

    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    loaded = load_person_detector(TripwireConfig(trigger="person_presence"))

    assert loaded.status == "skipped"
    assert "ultralytics unavailable" in loaded.message


def test_run_zone_tripwire_script_help() -> None:
    path = Path("scripts/run_zone_tripwire.py")
    assert path.exists()
    assert "Run Day-5 zone tripwire" in path.read_text(encoding="utf-8")


class FakeDetector:
    def __init__(self, detections_by_call: list[list[PersonDetection]]) -> None:
        self.detections_by_call = detections_by_call
        self.calls = 0

    def detect(self, frame: np.ndarray) -> list[PersonDetection]:
        del frame
        if self.calls >= len(self.detections_by_call):
            return []
        detections = self.detections_by_call[self.calls]
        self.calls += 1
        return detections


def write_video(path: Path, frames: list[np.ndarray], *, fps: int) -> None:
    import cv2  # type: ignore

    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()
    assert path.exists()
