#!/usr/bin/env python3
"""Run the repeatable Factory2 morning proof sequence.

This is the one-command wrapper for the current representative proof path. It
reruns detector evaluation on positives and hard negatives, then rebuilds the
accepted/suppressed/uncertain proof report from diagnostic receipts.

It deliberately does not promote raw detector detections into counts. Counts
still come only from perception-gate-approved source-token evidence already
captured in diagnostic receipts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_morning_proof_report import DEFAULT_DIAGNOSTICS, build_report, render_markdown
from scripts.eval_detector_false_positives import evaluate_false_positives
from scripts.eval_detector_positives import evaluate_detector_positives

DATA_YAML = Path("data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml")
REPORT_JSON = Path("data/reports/factory2_morning_proof_report.json")
REPORT_MD = Path("data/reports/factory2_morning_proof_report.md")
RUN_SUMMARY_JSON = Path("data/reports/factory2_morning_proof_run_summary.json")
DEFAULT_MODELS = [Path("models/panel_in_transit.pt"), Path("models/caleb_metal_panel.pt")]
DEFAULT_CONFIDENCES = [0.25, 0.10]
DEFAULT_IOU_THRESHOLD = 0.30

FalsePositiveEvaluator = Callable[..., dict[str, Any]]
PositiveEvaluator = Callable[..., dict[str, Any]]


def model_slug(model_path: Path) -> str:
    return model_path.stem.replace(" ", "_").replace(".", "_")


def confidence_slug(confidence: float) -> str:
    return f"conf{int(round(confidence * 100)):03d}"


def iou_slug(iou_threshold: float) -> str:
    return f"iou{int(round(iou_threshold * 100)):03d}"


def default_fp_output(model_path: Path, confidence: float) -> Path:
    return Path("data/eval/detector_false_positives") / f"active_panel_hard_negatives_v1_{model_slug(model_path)}_{confidence_slug(confidence)}.json"


def default_positive_output(model_path: Path, confidence: float, iou_threshold: float) -> Path:
    return Path("data/eval/detector_positives") / f"active_panel_positives_v1_{model_slug(model_path)}_{confidence_slug(confidence)}_{iou_slug(iou_threshold)}.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_factory2_morning_proof(
    *,
    data_yaml: Path = DATA_YAML,
    models: Optional[list[Path]] = None,
    confidences: Optional[list[float]] = None,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    diagnostic_paths: Optional[list[Path]] = None,
    report_json: Path = REPORT_JSON,
    report_md: Path = REPORT_MD,
    run_summary_json: Path = RUN_SUMMARY_JSON,
    force: bool = False,
    fp_evaluator: FalsePositiveEvaluator = evaluate_false_positives,
    positive_evaluator: PositiveEvaluator = evaluate_detector_positives,
) -> dict[str, Any]:
    selected_models = models if models is not None else DEFAULT_MODELS
    selected_confidences = confidences if confidences is not None else DEFAULT_CONFIDENCES
    selected_diagnostics = diagnostic_paths if diagnostic_paths is not None else [Path(path) for path in DEFAULT_DIAGNOSTICS]

    if not data_yaml.exists():
        raise FileNotFoundError(data_yaml)
    for diagnostic_path in selected_diagnostics:
        if not diagnostic_path.exists():
            raise FileNotFoundError(diagnostic_path)

    fp_report_paths: list[Path] = []
    positive_report_paths: list[Path] = []
    skipped_models: list[dict[str, str]] = []

    for model_path in selected_models:
        if not model_path.exists():
            skipped_models.append({"model_path": str(model_path), "reason": "missing_model_file"})
            continue
        for confidence in selected_confidences:
            fp_output = default_fp_output(model_path, confidence)
            fp_evaluator(
                data_yaml=data_yaml,
                dataset_manifest=None,
                model_path=model_path,
                output_path=fp_output,
                confidence=confidence,
                force=force,
            )
            fp_report_paths.append(fp_output)

            positive_output = default_positive_output(model_path, confidence, iou_threshold)
            positive_evaluator(
                data_yaml=data_yaml,
                dataset_manifest=None,
                model_path=model_path,
                output_path=positive_output,
                confidence=confidence,
                iou_threshold=iou_threshold,
                force=force,
            )
            positive_report_paths.append(positive_output)

    if not fp_report_paths:
        raise RuntimeError("No detector false-positive reports were produced; no available model files found")
    if not positive_report_paths:
        raise RuntimeError("No detector positive reports were produced; no available model files found")

    if (report_json.exists() or report_md.exists() or run_summary_json.exists()) and not force:
        existing = [str(path) for path in [report_json, report_md, run_summary_json] if path.exists()]
        raise FileExistsError(f"Output exists; pass --force: {existing}")

    report = build_report(
        diagnostic_paths=selected_diagnostics,
        fp_report_paths=fp_report_paths,
        positive_report_paths=positive_report_paths,
    )
    write_json(report_json, report)
    write_text(report_md, render_markdown(report))

    run_summary = {
        "schema_version": "factory2-morning-proof-run-v1",
        "data_yaml": str(data_yaml),
        "models_requested": [str(path) for path in selected_models],
        "confidences": selected_confidences,
        "iou_threshold": iou_threshold,
        "diagnostics": [str(path) for path in selected_diagnostics],
        "fp_reports": [str(path) for path in fp_report_paths],
        "positive_reports": [str(path) for path in positive_report_paths],
        "skipped_models": skipped_models,
        "report_json": str(report_json),
        "report_md": str(report_md),
        "verdict": report["verdict"],
        "accepted_count": report["accepted_count"],
        "suppressed_count": report["suppressed_count"],
        "uncertain_count": report["uncertain_count"],
        "bottleneck": report["bottleneck"],
        "note": "Raw detector outputs are eval evidence only; they do not increment counts.",
    }
    write_json(run_summary_json, run_summary)
    return run_summary


def parse_models(values: Optional[list[str]]) -> Optional[list[Path]]:
    if values is None:
        return None
    return [Path(value) for value in values]


def parse_confidences(values: Optional[list[str]]) -> Optional[list[float]]:
    if values is None:
        return None
    return [float(value) for value in values]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the repeatable Factory2 morning proof report path")
    parser.add_argument("--data-yaml", type=Path, default=DATA_YAML)
    parser.add_argument("--model", action="append", dest="models", default=None, help="model path; may repeat")
    parser.add_argument("--confidence", action="append", dest="confidences", default=None, help="confidence threshold; may repeat")
    parser.add_argument("--iou-threshold", type=float, default=DEFAULT_IOU_THRESHOLD)
    parser.add_argument("--diagnostic", action="append", dest="diagnostics", default=None, help="diagnostic.json path; may repeat")
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--run-summary-json", type=Path, default=RUN_SUMMARY_JSON)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    summary = run_factory2_morning_proof(
        data_yaml=args.data_yaml,
        models=parse_models(args.models),
        confidences=parse_confidences(args.confidences),
        iou_threshold=args.iou_threshold,
        diagnostic_paths=[Path(path) for path in args.diagnostics] if args.diagnostics else None,
        report_json=args.report_json,
        report_md=args.report_md,
        run_summary_json=args.run_summary_json,
        force=args.force,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
