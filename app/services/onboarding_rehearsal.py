from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "factory-vision-autonomous-onboarding-rehearsal-v1"
GENERATED_BY = "autonomous_onboarding_rehearsal_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_RAW_VIDEOS = Path("/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/videos/raw")

DEFAULT_STATIONS: list[dict[str, str]] = [
    {
        "station_id": "factory2_auto",
        "video": str(ARCHIVE_RAW_VIDEOS / "factory2.MOV"),
        "truth_ledger": "data/reports/factory2_human_truth_ledger.v1.json",
        "baseline_case_id": "factory2_test_case_1",
    },
    {
        "station_id": "img3262_auto",
        "video": str(ARCHIVE_RAW_VIDEOS / "IMG_3262.MOV"),
        "truth_ledger": "data/reports/img3262_human_truth_ledger.v2.json",
        "baseline_case_id": "img3262_candidate",
    },
    {
        "station_id": "img3254_auto",
        "video": str(ARCHIVE_RAW_VIDEOS / "IMG_3254.MOV"),
        "truth_ledger": "data/reports/img3254_human_truth_ledger.clean_cycle_v1.json",
        "baseline_case_id": "img3254_clean22_candidate",
    },
    {
        "station_id": "img2628_auto",
        "video": str(ARCHIVE_RAW_VIDEOS / "IMG_2628.MOV"),
        "truth_ledger": "data/reports/img2628_human_truth_ledger.reviewed_v1.json",
        "baseline_case_id": "img2628_candidate",
    },
]

# Stages allowed to see a truth ledger path. Everything else is the blind training lane.
TRUTH_TOUCHING_STAGES = {"split", "gate", "grade"}

StageRunner = Callable[[list[str]], "StageOutcome"]


class StageOutcome:
    def __init__(self, *, exit_code: int, stderr_tail: str = "") -> None:
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail


def default_stage_runner(command: list[str]) -> StageOutcome:
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return StageOutcome(exit_code=completed.returncode, stderr_tail=completed.stderr.strip()[-2000:])


def build_station_stages(
    station: dict[str, str],
    *,
    work_root: Path,
    playback_speed: float,
    teacher_provider: str,
    allow_cloud: bool,
    teacher_batch_size: int,
    box_backend: str,
    base_model: Path,
    epochs: int,
    device: str,
    train_fraction: float = 0.7,
    min_holdout_truth_events: int = 3,
    stable_negative_count: int = 3,
    enable_mining: bool = False,
) -> list[dict[str, Any]]:
    """Build the full per-station stage list. Commands are fully resolved up front so the
    truth-leakage assertion can inspect every training-lane command before anything runs."""
    python = str(REPO_ROOT / ".venv" / "bin" / "python")
    if not Path(python).exists():
        python = sys.executable
    station_id = station["station_id"]
    work = work_root / station_id
    video = station["video"]
    truth_ledger = station["truth_ledger"]
    suffix = Path(video).suffix or ".mp4"

    split_dir = work / "split"
    train_clip = split_dir / f"{station_id}_train{suffix}"
    holdout_manifest = split_dir / f"{station_id}_holdout_case_manifest.json"
    segment_manifest = work / "recordings" / station_id / "segment_manifest.json"
    proposals = work / "event_proposals.json"
    packets_dir = work / "packets"
    packet_manifest = packets_dir / "teacher_evidence_manifest.json"
    teacher_labels = work / "teacher_verifications.json"
    state_diff = work / "state_diff.json"
    fusion = work / "teacher_fusion.json"
    silver = work / "silver_candidates.json"
    auto_boxes = work / "auto_boxes.json"
    reviewed = work / "reviewed_labels.json"
    hard_negatives = work / "hard_negatives" / "hard_negative_export.json"
    dataset_dir = work / "dataset"
    dataset_manifest = dataset_dir / "dataset_manifest.json"
    training_report = work / "training_eval.json"
    mined_negatives = work / "hard_negatives_v2" / "hard_negative_export.json"
    dataset_v2_dir = work / "dataset_v2"
    dataset_v2_manifest = dataset_v2_dir / "dataset_manifest.json"
    training_v2_report = work / "training_eval_v2.json"
    trained_model = work / "train" / "model" / "weights" / "best.pt"
    auto_calibration = work / "calibration" / "station_calibration.json"
    gate_report = work / "blind_replay_gate.json"
    grade_report = work / "teacher_grade_vs_truth.json"

    teacher_command = [
        python,
        "scripts/generate_teacher_verifications.py",
        "--packet-manifest",
        str(packet_manifest),
        "--provider",
        teacher_provider,
        "--batch-size",
        str(teacher_batch_size),
        "--output",
        str(teacher_labels),
        "--force",
    ]
    if allow_cloud:
        teacher_command.insert(6, "--allow-cloud")

    publish_source_report = training_v2_report if enable_mining else training_report
    stages = [
        {
            "name": "split",
            "artifact": str(holdout_manifest),
            "command": [
                python,
                "scripts/build_holdout_case.py",
                "--video",
                video,
                "--truth-ledger",
                truth_ledger,
                "--station-id",
                station_id,
                "--work-dir",
                str(split_dir),
                "--model-path",
                str(trained_model),
                "--playback-speed",
                f"{playback_speed:g}",
                "--train-fraction",
                f"{train_fraction:g}",
                "--min-holdout-truth-events",
                str(min_holdout_truth_events),
                "--force",
            ],
        },
        {
            "name": "segments",
            "artifact": str(segment_manifest),
            "command": [
                python,
                "scripts/record_stream_segments.py",
                "--source",
                str(train_clip),
                "--station-id",
                station_id,
                "--output-root",
                str(work / "recordings"),
                "--segment-seconds",
                "60",
                "--retention-minutes",
                "10080",
                "--container",
                "mkv",
            ],
        },
        {
            "name": "proposals",
            "artifact": str(proposals),
            "command": [
                python,
                "scripts/propose_onboarding_events.py",
                "--segment-manifest",
                str(segment_manifest),
                "--output",
                str(proposals),
                "--sample-fps",
                "2",
                "--motion-threshold",
                "0.01",
                "--min-cluster-gap-sec",
                "1.5",
                # 6s margins (not the proposer's 4s default): Factory2 grading showed truth events
                # sitting ~1s outside 4s windows, which the teacher then can never assert.
                "--window-before-sec",
                "6",
                "--window-after-sec",
                "6",
                "--stable-negative-count",
                str(stable_negative_count),
                "--force",
            ],
        },
        {
            "name": "packets",
            "artifact": str(packet_manifest),
            "command": [
                python,
                "scripts/build_teacher_evidence_packets.py",
                "--event-proposals",
                str(proposals),
                "--output-dir",
                str(packets_dir),
                "--sequence-fps",
                "2",
                "--max-width",
                "960",
                "--force",
            ],
        },
        {
            "name": "teacher",
            "artifact": str(teacher_labels),
            "command": teacher_command,
        },
        {
            "name": "reconcile",
            "artifact": str(state_diff),
            "command": [
                python,
                "scripts/reconcile_state_diff.py",
                "--packet-manifest",
                str(packet_manifest),
                "--teacher-labels",
                str(teacher_labels),
                "--output",
                str(state_diff),
                "--force",
            ],
        },
        {
            "name": "fuse",
            "artifact": str(silver),
            "command": [
                python,
                "scripts/fuse_teacher_verifications.py",
                "--teacher-labels",
                str(teacher_labels),
                "--state-diff",
                str(state_diff),
                "--silver-dataset",
                str(silver),
                "--output",
                str(fusion),
                "--force",
            ],
        },
        {
            "name": "boxes",
            "artifact": str(auto_boxes),
            "command": [
                python,
                "scripts/propose_auto_boxes.py",
                "--silver-dataset",
                str(silver),
                "--packet-manifest",
                str(packet_manifest),
                "--work-dir",
                str(work / "boxes"),
                "--output",
                str(auto_boxes),
                "--backend",
                box_backend,
                "--frames-per-event",
                "6",
                "--force",
            ],
        },
        {
            "name": "review",
            "artifact": str(reviewed),
            "command": [
                python,
                "scripts/review_labels_ai.py",
                str(auto_boxes),
                "--output",
                str(reviewed),
            ],
        },
        {
            "name": "calibration",
            "artifact": str(auto_calibration),
            "command": [
                python,
                "scripts/derive_auto_station_calibration.py",
                "--auto-boxes",
                str(auto_boxes),
                "--train-clip",
                str(train_clip),
                "--output",
                str(auto_calibration),
                "--force",
            ],
        },
        {
            "name": "negatives",
            "artifact": str(hard_negatives),
            "command": [
                python,
                "scripts/export_onboarding_stable_negatives.py",
                "--event-proposals",
                str(proposals),
                "--work-dir",
                str(work / "negatives"),
                "--out-dir",
                str(work / "hard_negatives"),
                "--force",
            ],
        },
        {
            "name": "dataset",
            "artifact": str(dataset_manifest),
            "command": [
                python,
                "scripts/assemble_active_panel_dataset.py",
                "--reviewed-label-manifest",
                str(reviewed),
                "--hard-negative-export",
                str(hard_negatives),
                "--out-dir",
                str(dataset_dir),
                "--force",
            ],
        },
        {
            "name": "train",
            "artifact": str(training_report),
            "retry_device_cpu": True,
            "command": [
                python,
                "scripts/run_yolo26_training_eval.py",
                "--data-yaml",
                str(dataset_dir / "data.yaml"),
                "--dataset-manifest",
                str(dataset_manifest),
                "--base-model",
                str(base_model),
                "--train-project",
                str(work / "train"),
                "--train-name",
                "model",
                "--epochs",
                str(epochs),
                "--device",
                device,
                "--execute-training",
                "--output",
                str(training_report),
                "--force",
            ],
        },
        {
            "name": "mine",
            "artifact": str(mined_negatives),
            # Self-correction round: the v1 model's false positives inside teacher-refuted,
            # state-diff-confirmed negative windows become extra empty-label hard negatives.
            "command": [
                python,
                "scripts/mine_hard_negative_frames.py",
                "--model-report",
                str(training_report),
                "--teacher-labels",
                str(teacher_labels),
                "--segment-manifest",
                str(segment_manifest),
                "--base-hard-negative-export",
                str(hard_negatives),
                "--work-dir",
                str(work / "hard_negatives_v2"),
                "--output",
                str(mined_negatives),
                # Balance against the positive set: only the most confident false positives,
                # capped, so negatives never drown the positive signal (observed: a 3:1
                # negative flood collapses training to zero confidence).
                "--confidence",
                "0.4",
                "--max-mined-frames",
                "40",
                "--force",
            ],
        },
        {
            "name": "dataset2",
            "artifact": str(dataset_v2_manifest),
            "command": [
                python,
                "scripts/assemble_active_panel_dataset.py",
                "--reviewed-label-manifest",
                str(reviewed),
                "--hard-negative-export",
                str(mined_negatives),
                "--out-dir",
                str(dataset_v2_dir),
                "--force",
            ],
        },
        {
            "name": "train2",
            "artifact": str(training_v2_report),
            "retry_device_cpu": True,
            "command": [
                python,
                "scripts/run_yolo26_training_eval.py",
                "--data-yaml",
                str(dataset_v2_dir / "data.yaml"),
                "--dataset-manifest",
                str(dataset_v2_manifest),
                "--base-model",
                str(base_model),
                "--train-project",
                str(work / "train_v2"),
                "--train-name",
                "model",
                "--epochs",
                str(epochs),
                "--device",
                device,
                "--execute-training",
                "--output",
                str(training_v2_report),
                "--force",
            ],
        },
        {
            "name": "publish",
            "artifact": str(trained_model),
            # Ultralytics versions disagree about honoring the run name, so the training
            # report's trained_model_path is authoritative; copy it to the path the holdout
            # manifest was authored against.
            "command": [
                python,
                "-c",
                (
                    "import json,shutil,sys;from pathlib import Path;"
                    "report=json.loads(Path(sys.argv[1]).read_text());"
                    "src=Path(report['trained_model_path']);dst=Path(sys.argv[2]);"
                    "dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);"
                    "print(json.dumps({'published_model':str(dst)}))"
                ),
                str(publish_source_report),
                str(trained_model),
            ],
        },
        {
            "name": "gate",
            "artifact": str(gate_report),
            "command": [
                python,
                "scripts/run_blind_replay_gate.py",
                "--manifest",
                str(holdout_manifest),
                "--output",
                str(gate_report),
                "--execute",
                "--backend-port",
                "8093",
                "--frontend-port",
                "5175",
                "--force",
            ],
        },
        {
            "name": "grade",
            "artifact": str(grade_report),
            "command": [
                python,
                "scripts/grade_teacher_labels_vs_truth.py",
                "--teacher-labels",
                str(teacher_labels),
                "--truth-ledger",
                truth_ledger,
                "--packet-manifest",
                str(packet_manifest),
                "--segment-manifest",
                str(segment_manifest),
                "--output",
                str(grade_report),
                "--force",
            ],
        },
    ]
    if not enable_mining:
        # Mining is opt-in: it anti-trains real placements whenever the teacher misses an
        # event (observed on Factory2 with teacher recall ~0.87), so the v1 model ships by
        # default and the self-correction round stays behind an explicit flag.
        stages = [stage for stage in stages if stage["name"] not in {"mine", "dataset2", "train2"}]
    return stages


def assert_no_truth_leakage(stages: list[dict[str, Any]], *, truth_ledger: str) -> None:
    """Training-lane stages must never receive a truth ledger path."""
    truth_name = Path(truth_ledger).name
    for stage in stages:
        if stage["name"] in TRUTH_TOUCHING_STAGES:
            continue
        joined = " ".join(stage["command"])
        if truth_ledger in joined or truth_name in joined or "holdout_truth_ledger" in joined:
            raise ValueError(f"truth leakage: stage {stage['name']} command references a truth ledger")


def run_station(
    station: dict[str, str],
    *,
    stages: list[dict[str, Any]],
    stage_runner: StageRunner | None = None,
    force_stages: set[str] = frozenset(),
    device: str = "mps",
) -> dict[str, Any]:
    runner = stage_runner or default_stage_runner
    results: list[dict[str, Any]] = []
    failed_stage: str | None = None
    for stage in stages:
        artifact = Path(stage["artifact"])
        if failed_stage is not None:
            results.append({"name": stage["name"], "status": "not_run", "artifact": str(artifact)})
            continue
        if artifact.exists() and stage["name"] not in force_stages:
            results.append({"name": stage["name"], "status": "skipped_existing", "artifact": str(artifact)})
            continue
        started = time.time()
        outcome = runner(stage["command"])
        if outcome.exit_code != 0 and stage.get("retry_device_cpu") and device == "mps":
            retry_command = ["cpu" if part == "mps" else part for part in stage["command"]]
            outcome = runner(retry_command)
        duration = round(time.time() - started, 1)
        if outcome.exit_code != 0:
            failed_stage = stage["name"]
            results.append(
                {
                    "name": stage["name"],
                    "status": "failed",
                    "artifact": str(artifact),
                    "duration_sec": duration,
                    "error": outcome.stderr_tail[-600:],
                }
            )
            continue
        results.append(
            {
                "name": stage["name"],
                "status": "completed",
                "artifact": str(artifact),
                "duration_sec": duration,
            }
        )
    return {
        "station_id": station["station_id"],
        "failed_stage": failed_stage,
        "stages": results,
    }


def evaluate_train_gate(
    training_report: dict[str, Any] | None,
    dataset_manifest: dict[str, Any] | None,
    *,
    min_positive_ratio: float,
    max_hard_negative_false_positives: int,
) -> dict[str, Any]:
    summary = (training_report or {}).get("summary") or {}
    matched = summary.get("matched_positive_labels")
    false_positives = summary.get("hard_negative_false_positive_detections")
    positive_count = ((dataset_manifest or {}).get("summary") or {}).get("positive_count")
    ratio = None
    if matched is not None and positive_count:
        ratio = round(float(matched) / float(positive_count), 4)
    passed = (
        ratio is not None
        and ratio >= min_positive_ratio
        and false_positives is not None
        and int(false_positives) <= max_hard_negative_false_positives
    )
    return {
        "matched_positive_labels": matched,
        "positive_count": positive_count,
        "matched_positive_ratio": ratio,
        "min_positive_ratio": min_positive_ratio,
        "hard_negative_false_positive_detections": false_positives,
        "max_hard_negative_false_positives": max_hard_negative_false_positives,
        "passed": passed,
    }


def collect_station_metrics(station: dict[str, str], *, work_root: Path, train_gate_thresholds: dict[str, Any]) -> dict[str, Any]:
    work = work_root / station["station_id"]
    split_dir = work / "split"
    split_report = _load_json(split_dir / f"{station['station_id']}_split_report.json")
    fusion = _load_json(work / "teacher_fusion.json")
    auto_boxes = _load_json(work / "auto_boxes.json")
    dataset_manifest = _load_json(work / "dataset" / "dataset_manifest.json")
    training_report = _load_json(work / "training_eval.json")
    gate_report = _load_json(work / "blind_replay_gate.json")
    grade_report = _load_json(work / "teacher_grade_vs_truth.json")
    validation_report = None
    if gate_report:
        validation_path = gate_report.get("validation_report_path")
        if validation_path:
            validation_report = _load_json(Path(validation_path))

    train_gate = evaluate_train_gate(
        training_report,
        dataset_manifest,
        min_positive_ratio=float(train_gate_thresholds["min_positive_ratio"]),
        max_hard_negative_false_positives=int(train_gate_thresholds["max_hard_negative_false_positives"]),
    )
    grade_headline = None
    if grade_report:
        tolerance = grade_report.get("per_tolerance") or {}
        headline = tolerance.get("5") or next(iter(tolerance.values()), None)
        if headline:
            grade_headline = {
                "tolerance_sec": headline.get("tolerance_sec"),
                "precision": headline.get("precision"),
                "recall": headline.get("recall"),
                "f1": headline.get("f1"),
                "metric_provenance": "diagnostic_only_ran_after_gate_never_an_input",
            }
    return {
        "split": (split_report or {}).get("split"),
        "teacher_fusion_summary": (fusion or {}).get("summary"),
        "auto_box_summary": (auto_boxes or {}).get("summary"),
        "dataset_summary": (dataset_manifest or {}).get("summary"),
        "training_status": (training_report or {}).get("status"),
        "train_gate": train_gate,
        "gate": _gate_summary(gate_report, validation_report),
        "teacher_grade_at_5s": grade_headline,
    }


def build_scoreboard(
    *,
    stations: list[dict[str, str]],
    station_runs: list[dict[str, Any]],
    work_root: Path,
    config: dict[str, Any],
    registry_path: Path = Path("validation/registry.json"),
) -> dict[str, Any]:
    registry = _load_json(REPO_ROOT / registry_path) or {}
    baselines = {}
    for entry in registry.get("cases") or []:
        manifest = _load_json(REPO_ROOT / str(entry.get("manifest_path")))
        if manifest:
            baselines[str(entry.get("case_id"))] = {
                "case_id": entry.get("case_id"),
                "proof_summary": manifest.get("proof_summary"),
            }
    rows = []
    passed_count = 0
    for station, run in zip(stations, station_runs):
        metrics = collect_station_metrics(
            station,
            work_root=work_root,
            train_gate_thresholds=config["train_gate"],
        )
        gate = metrics.get("gate") or {}
        station_passed = bool(gate.get("passed"))
        passed_count += int(station_passed)
        rows.append(
            {
                "station_id": station["station_id"],
                "video": station["video"],
                "baseline": baselines.get(station.get("baseline_case_id", "")),
                "failed_stage": run.get("failed_stage"),
                "stages": run.get("stages"),
                "metrics": metrics,
                "passed": station_passed,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "created_at": round(time.time(), 3),
        "config": config,
        "count_authority": "existing_yolo_event_runtime_only",
        "promotion_claim": False,
        "refuses_validation_truth": True,
        "playback_speed_note": "rehearsal gate runs use accelerated playback; promotion proof still requires 1.0x",
        "stations": rows,
        "summary": {
            "station_count": len(rows),
            "gate_passed_count": passed_count,
            "target": ">=3 of 4 stations pass the blind replay gate with zero human labels",
        },
    }


def _gate_summary(gate_report: dict[str, Any] | None, validation_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not gate_report:
        return None
    summary: dict[str, Any] = {
        "passed": gate_report.get("passed"),
        "fail_reasons": gate_report.get("fail_reasons"),
        "expected_total": gate_report.get("expected_total"),
        "matched_count": gate_report.get("matched_count"),
        "missing_truth_count": gate_report.get("missing_truth_count"),
        "unexpected_observed_count": gate_report.get("unexpected_observed_count"),
        "first_divergence": gate_report.get("first_divergence"),
    }
    if validation_report:
        runtime = validation_report.get("runtime") or {}
        proof = validation_report.get("proof_summary") or {}
        summary["playback_speed"] = runtime.get("playback_speed")
        summary["wall_per_source"] = proof.get("wall_per_source")
    return summary


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
