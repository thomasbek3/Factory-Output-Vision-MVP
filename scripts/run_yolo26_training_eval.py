from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.yolo26_training_runner import run_yolo26_training_eval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run YOLO26 station training/eval lane")
    parser.add_argument("--data-yaml", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path)
    parser.add_argument("--base-model", type=Path, default=Path("yolo26n.pt"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-project", type=Path, default=Path("runs/detect/training_runs"))
    parser.add_argument("--train-name", default="factory_onboarding_yolo26")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--execute-training", action="store_true")
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = run_yolo26_training_eval(
            data_yaml=args.data_yaml,
            dataset_manifest=args.dataset_manifest,
            base_model_path=args.base_model,
            output_path=args.output,
            train_project=args.train_project,
            train_name=args.train_name,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            confidence=args.confidence,
            execute_training=args.execute_training,
            allow_model_download=args.allow_model_download,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "status": payload["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
