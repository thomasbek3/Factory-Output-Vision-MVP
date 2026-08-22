"""StationPipeline (CP5): one declarative stage graph per Track B station.

Deep module over the existing onboarding stages. `build_station_stages`
(onboarding_rehearsal) already owns the full YOLO-era stage chain with the
truth-leakage guard; this module adds the missing Track B lane — tripwire
mining -> recall validation -> clip extraction -> labeling -> training ->
blind exam — as composable stage dicts in the SAME shape, so one executor,
one artifact-cache rule, and one truth-leak guard cover both lanes.

ADR-0004: clip action-recognition is the live lane. ADR-0002: the exam gate
is the promotion gate. The exam and recall stages consume ONLY the sealed
exam key at validation/exam/exam_gold_positives.json (schema
exam_gold_positives_v1, `training_eligible: false`) — NEVER teacher labels,
candidate data, or anything a training stage reads. reviewed_labels.json is
the TRAIN manifest only; if it ever appears in an exam/recall argv that is a
truth leak.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.onboarding_rehearsal import (  # noqa: E402
    StageOutcome,
    default_stage_runner,
    run_station,
)

# Repo-sealed exam key: the ONLY gold both recall and exam may consume.
EXAM_GOLD_POSITIVES = REPO_ROOT / "validation" / "exam" / "exam_gold_positives.json"

TRAIN_MANIFEST_NAME = "reviewed_labels.json"


def assert_no_truth_leakage_track_b(stages: list[dict[str, Any]]) -> None:
    """Fail closed if any exam/recall stage consumes the train manifest, or if
    any train-side stage (extract/label/train) consumes the sealed exam key."""
    for stage in stages:
        command = stage.get("command", [])
        name = stage.get("name", "?")
        if name in {"recall", "exam"}:
            gold_index = command.index("--gold-positives")
            gold_path = Path(command[gold_index + 1])
            if gold_path.name == TRAIN_MANIFEST_NAME:
                raise AssertionError(
                    f"TRUTH LEAK: stage '{name}' uses {TRAIN_MANIFEST_NAME} as gold; "
                    f"exam gold must be the sealed key ({EXAM_GOLD_POSITIVES.name})"
                )
        elif name in {"extract", "label", "train"}:
            if any(str(EXAM_GOLD_POSITIVES) == str(part) for part in command):
                raise AssertionError(
                    f"TRUTH LEAK: stage '{name}' references the sealed exam key; "
                    "training lanes must never read it"
                )


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

    Order: mine -> extract -> label -> train -> recall -> exam.
    Recall runs against the SEALED exam key after training so the report shows
    candidate quality vs promotion truth without ever feeding it to training.
    Exam gold is always the sealed key; reviewed labels are train-only.
    """
    if python is None:
        candidate = REPO_ROOT / ".venv" / "bin" / "python"
        python = str(candidate) if candidate.exists() else sys.executable
    work = work_root / station_id
    tripwire_candidates = work / "tripwire_candidates.json"
    recall_report = work / "tripwire_recall.json"
    clip_manifest = work / "clips" / "clip_manifest.json"
    reviewed_labels = work / TRAIN_MANIFEST_NAME
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
            ]
            + (
                [
                    "--times",
                    placement_times,
                ]
                if placement_times is not None
                else []
            ),
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
            "name": "recall",
            "artifact": str(recall_report),
            # Recall of tripwire candidates vs the SEALED exam key: this is a
            # measurement report, never a training input.
            "command": [
                python,
                "scripts/validate_tripwire_recall.py",
                "--tripwire-candidates",
                str(tripwire_candidates),
                "--gold-positives",
                str(EXAM_GOLD_POSITIVES),
                "--station-calibration",
                str(calibration),
                "--match-tolerance-sec",
                f"{match_tolerance_sec:g}",
                "--out",
                str(recall_report),
            ],
        },
        {
            "name": "exam",
            "artifact": str(exam_report),
            # Blind exam: gold positives come from the sealed exam key only.
            # The student trained on reviewed_labels (exam rows are firewalled
            # out by validate_training_manifest inside train_clip_student).
            "command": [
                python,
                "scripts/run_clip_exam.py",
                "--video",
                str(video),
                "--gold-positives",
                str(EXAM_GOLD_POSITIVES),
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
    assert_no_truth_leakage_track_b(stages)
    return stages


__all__ = [
    "EXAM_GOLD_POSITIVES",
    "TRAIN_MANIFEST_NAME",
    "assert_no_truth_leakage_track_b",
    "build_track_b_stages",
    "default_stage_runner",
    "run_station",
    "StageOutcome",
]
