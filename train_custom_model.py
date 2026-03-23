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

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Train custom YOLOv8n on wire mesh panel dataset")
    parser.add_argument("--data", type=str, required=True, help="Path to data.yaml from Roboflow export")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs (default: 50)")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size (default: 640)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (default: 16, use 8 for low RAM)")
    parser.add_argument("--device", type=str, default="cpu", help="Device: 'cpu' or '0' for GPU")
    parser.add_argument("--base-model", type=str, default="yolov8n.pt", help="Base model to fine-tune from")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: {data_path} not found.")
        print(f"Download your dataset from Roboflow and extract it first.")
        return

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
