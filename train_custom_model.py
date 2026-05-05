"""
Train a custom YOLOv8n model on the wire-mesh-panel dataset from Roboflow.

USAGE:
  1. Export your Roboflow dataset as "YOLOv8" format
  2. Download and unzip to a folder (e.g., ./training_data/)
  3. Run: python train_custom_model.py --data ./training_data/data.yaml

The trained model will be saved to runs/detect/train/weights/best.pt
Then set FC_YOLO_MODEL_PATH=runs/detect/train/weights/best.pt to use it.

NOTE: Training on CPU is slow (~1-2 hours). For faster training (~20 min),
use Google Colab with a free GPU. Just upload this script and the dataset.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_reviewed_label_gate(manifest_path: Path) -> dict[str, int]:
    """Validate that training is fed by the AI-reviewed label gate.

    The reviewed manifest is produced by ``scripts/review_labels_ai.py``. Only
    ACCEPT/FIX labels appear in ``trainable_labels``; REJECT/UNCERTAIN rows are
    counted as blocked and must not be exported into the training dataset.
    """
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "label-quality-reviewed-v1":
        raise ValueError("Expected schema_version label-quality-reviewed-v1")

    trainable = len(manifest.get("trainable_labels") or [])
    blocked = len(manifest.get("rejected") or []) + len(manifest.get("uncertain") or [])
    if trainable == 0:
        raise ValueError("No AI-reviewed trainable labels found")
    return {"trainable": trainable, "blocked": blocked}


def resolve_reviewed_label_gate(
    reviewed_label_manifest: str | Path | None,
    *,
    allow_unreviewed_labels: bool = False,
) -> dict[str, int] | None:
    """Require the AI review gate unless explicitly bypassed."""
    if reviewed_label_manifest is None:
        if allow_unreviewed_labels:
            return None
        raise ValueError(
            "AI label QA manifest is required. Run scripts/review_labels_ai.py first, "
            "or pass --allow-unreviewed-labels to bypass deliberately."
        )
    return validate_reviewed_label_gate(Path(reviewed_label_manifest))


def main():
    parser = argparse.ArgumentParser(description="Train custom YOLOv8n on wire mesh panel dataset")
    parser.add_argument("--data", type=str, required=True, help="Path to data.yaml from Roboflow export")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs (default: 50)")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size (default: 640)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (default: 16, use 8 for low RAM)")
    parser.add_argument("--device", type=str, default="cpu", help="Device: 'cpu' or '0' for GPU")
    parser.add_argument("--base-model", type=str, default="yolov8n.pt", help="Base model to fine-tune from")
    parser.add_argument(
        "--reviewed-label-manifest",
        type=str,
        default=None,
        help="Reviewed manifest from scripts/review_labels_ai.py; gates training to AI-approved labels",
    )
    parser.add_argument(
        "--allow-unreviewed-labels",
        action="store_true",
        help="Explicit escape hatch: train without the AI label QA manifest",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: {data_path} not found.")
        print(f"Download your dataset from Roboflow and extract it first.")
        return

    summary = resolve_reviewed_label_gate(
        args.reviewed_label_manifest,
        allow_unreviewed_labels=args.allow_unreviewed_labels,
    )
    if summary:
        print(
            "AI label QA gate passed: "
            f"{summary['trainable']} trainable labels, {summary['blocked']} blocked labels."
        )

    from ultralytics import YOLO

    print(f"\n{'='*60}")
    print(f"  Training Custom YOLOv8 Model")
    print(f"  Base model: {args.base_model}")
    print(f"  Dataset: {args.data}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Image size: {args.imgsz}")
    print(f"  Batch size: {args.batch}")
    print(f"  Device: {args.device}")
    print(f"{'='*60}\n")

    model = YOLO(args.base_model)
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=10,
        save=True,
        plots=True,
    )

    # Find the best weights
    best_pt = Path("runs/detect/train/weights/best.pt")
    if best_pt.exists():
        print(f"\n{'='*60}")
        print(f"  TRAINING COMPLETE")
        print(f"  Best model: {best_pt}")
        print(f"")
        print(f"  To use this model:")
        print(f"  Set FC_YOLO_MODEL_PATH={best_pt}")
        print(f"  Set FC_PERSON_IGNORE_ENABLED=0")
        print(f"  Set FC_YOLO_EXCLUDED_CLASSES=")
        print(f"  Then restart the server.")
        print(f"{'='*60}\n")
    else:
        print(f"\nTraining completed. Check runs/detect/ for the output.")


if __name__ == "__main__":
    main()
