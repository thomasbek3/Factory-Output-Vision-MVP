# Custom Model Training — Per-Customer YOLO Fine-Tuning

## Why custom training is needed
YOLOv8n ships pre-trained on COCO (80 common object classes: people, cars, bottles, etc.).
Factory-specific parts (wire mesh panels, stamped brackets, molded parts) are NOT in COCO.
Zero-shot models (YOLO-World, Grounding DINO) were evaluated but proved unreliable for
niche industrial objects at production confidence levels.

## What was tested and ruled out
- **YOLO-World (yolov8s-worldv2.pt)**: Text-prompted zero-shot detection. Tested with prompts
  like "wire mesh panel", "metal grating", "steel grid", "industrial part". Result: only detected
  people reliably. Custom factory parts returned zero or very low confidence detections.
- **Grounding DINO**: Similar zero-shot approach. Better for common objects but same limitation
  with niche industrial parts.
- **Standard YOLOv8n on factory video**: Detected people (class 0) at 85%+ confidence. Also
  produced false positives on factory equipment (bench, suitcase, car classes at 30-40% confidence).
  Did NOT detect the actual wire mesh panels being manufactured.

## The solution: Roboflow + Colab fine-tuning

### Step 1: Extract frames (~2 min)
```python
# Extract 50 diverse frames from customer video
import cv2
cap = cv2.VideoCapture("customer_video.mp4")
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
for i, idx in enumerate(range(0, total, total // 50)):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(f"frames/frame_{i:03d}.jpg", frame)
```

### Step 2: Label on Roboflow (~15 min)
1. Create free Roboflow account
2. Create project, upload frames
3. Use auto-label (Grounding DINO + SAM) with text prompt for the part
4. Review and adjust bounding boxes
5. Export in YOLOv8 format

### Step 3: Train on Google Colab (~20 min)
```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")  # start from pre-trained
model.train(data="dataset.yaml", epochs=50, imgsz=640, batch=16)
# Output: runs/detect/train/weights/best.pt
```

### Step 4: Deploy
Set `FC_YOLO_MODEL_PATH=path/to/custom_model.pt` and restart.
No code changes needed — the pipeline is model-agnostic.

## Timeline per customer
| Step | Time |
|------|------|
| Extract frames | 2 min |
| Upload + auto-label on Roboflow | 15 min |
| Train on Colab (free GPU) | 20 min |
| Deploy + verify | 10 min |
| **Total** | **~1 hour** |

## Future: in-app training (v2.0+)
The labeling and training steps could be built into the web UI:
1. Wizard records 2 min of production footage
2. System auto-extracts frames
3. User clicks on parts in a simple labeling UI ("this is a part")
4. System trains model in background
5. Counting starts automatically with the custom model
