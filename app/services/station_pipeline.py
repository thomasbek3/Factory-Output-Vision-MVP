"""StationPipeline (CP5): one declarative stage graph per Track B station.

Deep module over the existing onboarding stages. `build_station_stages`
(onboarding_rehearsal) already owns the full YOLO-era stage chain with the
truth-leakage guard; this module adds the missing Track B lane — tripwire
mining -> recall validation -> clip extraction -> labeling -> training ->
blind exam — as composable stage dicts in the SAME shape, so one executor,
one artifact-cache rule, and one truth-leak guard cover both lanes.

ADR-0004: clip action-recognition is the live lane; ADR-0002: the exam gate
is the promotion gate. The exam stage here consumes gold positives derived
ONLY from reviewed placement times, never from teacher proposals.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.onboarding_rehearsal import (  # noqa: E402
    TRUTH_TOUCHING_STAGES,
    StageOutcome,
    default_stage_runner,
    run_station,
)

TRACK_B_TRUTH_TOUCHING_STAGES = {"label", "exam"}

StageRunner = Any


def build_track_b_stages(
    *,
    station_id: str,
    video: Path,
    calibration: Path,
    work_root: Path,
    python: str | None = None,
    labeler: str = "codex",
    label_votes: int = 1,
    placement_times: str | None = None,
    match_tolerance_sec: float = 20.0,
    arch: str = "stack3_mobilenet",
    epochs: int = 12,
    device: str = "mps",
    tripwire_trigger: str = "person_presence",
    bracket_sec: float = 8.0,
) -> list[dict[str, Any]]:
    """Build the Track B stage list for one station.

    Gold positives for the exam are the reviewed placement times recorded by
    `label` (reviewed_labels.json), NOT raw tripwire candidates: candidates are
    high-recall hints, labels are the promotion-grade truth.
    """
    if python is None:
        candidate = REPO_ROOT / ".venv" / "bin" / "python"
        python = str(candidate) if candidate.exists() else sys.executable
    work = work_root / station_id
    suffix = video.suffix or ".mp4"
    split_dir = work / "split"
    train_clip = split_dir / f"{station_id}_train{suffix}"
    segment_manifest = work / "recordings" / station_id / "segment_manifest.json"
    tripwire_candidates = work / "tripwire_candidates.json"
    recall_report = work / "tripwire_recall.json"
    clip_manifest = work / "clips" / "clip_manifest.json"
    reviewed_labels = work / "reviewed_labels.json"
    model_dir = work / "train" / "student"
    exam_report = work / "clip_exam.json"

    stages: list[dict[str, Any]] = [
        {
            "name": "mine",
            "artifact": str(tripwire_candidates),
            "command": [
                python,
                "scripts/run_zone_tripwire.py",
                "--video",
                str(video),
                "--station-calibration",
                str(calibration),
                "--trigger",
                tripwire_trigger,
                "--bracket-sec",
                f"{bracket_sec:g}",
                "--out",
                str(tripwire_candidates),
            ],
        },
        {
            "name": "recall",
            "artifact": str(recall_report),
            # Recall is measured against reviewed placements (promotion-grade
            # truth), not raw candidates.
            "command": [
                python,
                "scripts/validate_tripwire_recall.py",
                "--tripwire-candidates",
                str(tripwire_candidates),
                "--gold-positives",
                str(reviewed_labels),
                "--station-calibration",
                str(calibration),
                "--match-tolerance-sec",
                f"{match_tolerance_sec:g}",
                "--out",
                str(recall_report),
            ],
        },
        {
            "name": "extract",
            "artifact": str(clip_manifest),
            "command": [
                python,
                "scripts/extract_clip_dataset.py",
                "--candidates",
                str(tripwire_candidates),
                "--video",
                str(video),
                "--station-calibration",
                str(calibration),
                "--encoding",
                "clip",
                "--out-dir",
                str(work / "clips"),
                "--manifest-out",
                str(clip_manifest),
            ],
        },
        {
            "name": "label",
            "artifact": str(reviewed_labels),
            "command": [
                python,
                "scripts/label_clips.py",
                "--manifest",
                str(clip_manifest),
                "--out",
                str(reviewed_labels),
                "--labeler",
                labeler,
                "--votes",
                str(label_votes),
            ],
        },
        {
            "name": "train",
            # clip_models.train_arch_selection saves to out_dir / f"{arch}.pt".
            "artifact": str(model_dir / f"{arch}.pt"),
            "command": [
                python,
                "scripts/train_clip_student.py",
                "--manifest",
                str(reviewed_labels),
                "--arch",
                arch,
                "--out-dir",
                str(model_dir),
                "--epochs",
                str(epochs),
                "--device",
                device,
            ],
        },
        {
            "name": "exam",
            "artifact": str(exam_report),
            # Blind exam: gold positives come from reviewed placements, the
            # student never saw holdout clips (exam firewall lives inside
            # label_clips/train via held-out manifest entries).
            "command": [
                python,
                "scripts/run_clip_exam.py",
                "--video",
                str(video),
                "--gold-positives",
                str(reviewed_labels),
                "--station-calibration",
                str(calibration),
                "--model",
                str(model_dir / f"{arch}.pt"),
                "--arch",
                arch,
                "--debounce-sec",
                "25",
                "--match-tolerance-sec",
                f"{match_tolerance_sec:g}",
                "--out",
                str(exam_report),
            ],
        },
    ]
    return stages


__all__ = [
    "TRACK_B_TRUTH_TOUCHING_STAGES",
    "TRUTH_TOUCHING_STAGES",
    "build_track_b_stages",
    "default_stage_runner",
    "run_station",
    "StageOutcome",
]
