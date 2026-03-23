"""
Simple local labeling tool for YOLO training.

HOW TO USE:
1. Run: python label_tool.py
2. Each image appears in a window
3. Click and drag to draw a box around any panel the worker is HOLDING
4. Press ENTER to save and go to next image
5. Press S to skip (no panel visible — this is a negative example)
6. Press U to undo last box
7. Press Q to quit early

Boxes are saved in YOLO format to training_frames/labels/
"""

import cv2
import os
import glob

FRAMES_DIR = "training_frames"
LABELS_DIR = os.path.join(FRAMES_DIR, "labels")
CLASS_NAME = "panel"
WINDOW = "Label Tool - Draw box around panel being HELD (Enter=save, S=skip, U=undo, Q=quit)"

os.makedirs(LABELS_DIR, exist_ok=True)

# State
drawing = False
start_x, start_y = 0, 0
boxes = []  # list of (x1, y1, x2, y2) in pixel coords
current_frame = None
display_frame = None


def mouse_callback(event, x, y, flags, param):
    global drawing, start_x, start_y, boxes, display_frame

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x, start_y = x, y

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        display_frame = current_frame.copy()
        # Draw existing boxes
        for bx1, by1, bx2, by2 in boxes:
            cv2.rectangle(display_frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
        # Draw current drag
        cv2.rectangle(display_frame, (start_x, start_y), (x, y), (0, 165, 255), 2)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, y1 = min(start_x, x), min(start_y, y)
        x2, y2 = max(start_x, x), max(start_y, y)
        if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
            boxes.append((x1, y1, x2, y2))
        display_frame = current_frame.copy()
        for bx1, by1, bx2, by2 in boxes:
            cv2.rectangle(display_frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
            cv2.putText(display_frame, CLASS_NAME, (bx1, by1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)


def save_labels(image_path, img_boxes, img_h, img_w):
    """Save in YOLO format: class_id cx cy w h (all normalized 0-1)"""
    base = os.path.splitext(os.path.basename(image_path))[0]
    label_path = os.path.join(LABELS_DIR, base + ".txt")

    if not img_boxes:
        # Save empty file for negative examples
        with open(label_path, "w") as f:
            pass
        return

    with open(label_path, "w") as f:
        for x1, y1, x2, y2 in img_boxes:
            cx = ((x1 + x2) / 2) / img_w
            cy = ((y1 + y2) / 2) / img_h
            bw = (x2 - x1) / img_w
            bh = (y2 - y1) / img_h
            f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")


def main():
    global current_frame, display_frame, boxes

    image_files = sorted(glob.glob(os.path.join(FRAMES_DIR, "*.jpg")))
    if not image_files:
        print(f"No images found in {FRAMES_DIR}/")
        return

    # Skip already labeled
    already_labeled = set()
    for lf in glob.glob(os.path.join(LABELS_DIR, "*.txt")):
        already_labeled.add(os.path.splitext(os.path.basename(lf))[0])

    remaining = [f for f in image_files
                 if os.path.splitext(os.path.basename(f))[0] not in already_labeled]

    print(f"\n{'='*60}")
    print(f"  LABELING TOOL")
    print(f"  Total images: {len(image_files)}")
    print(f"  Already labeled: {len(already_labeled)}")
    print(f"  Remaining: {len(remaining)}")
    print(f"{'='*60}")
    print(f"\n  INSTRUCTIONS:")
    print(f"  - Click & drag to draw a box around the panel")
    print(f"    the worker is HOLDING (not stacked panels)")
    print(f"  - ENTER = save boxes and next image")
    print(f"  - S = skip (no panel being held)")
    print(f"  - U = undo last box")
    print(f"  - Q = quit\n")

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW, mouse_callback)

    labeled_count = len(already_labeled)
    positive_count = 0

    for i, img_path in enumerate(remaining):
        boxes = []
        current_frame = cv2.imread(img_path)
        if current_frame is None:
            continue

        h, w = current_frame.shape[:2]
        display_frame = current_frame.copy()

        # Show image name and progress
        fname = os.path.basename(img_path)
        progress = f"[{labeled_count + 1}/{len(image_files)}] {fname}"
        cv2.putText(display_frame, progress, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        cv2.putText(display_frame, "Draw box around HELD panel | ENTER=save S=skip U=undo Q=quit",
                    (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1)

        cv2.resizeWindow(WINDOW, min(w, 1400), min(h, 900))

        while True:
            show = display_frame.copy()
            cv2.imshow(WINDOW, show)
            key = cv2.waitKey(30) & 0xFF

            if key == 13:  # ENTER - save
                save_labels(img_path, boxes, h, w)
                labeled_count += 1
                if boxes:
                    positive_count += 1
                    print(f"  ✓ {fname}: {len(boxes)} box(es) saved")
                else:
                    print(f"  ○ {fname}: saved as negative (no boxes)")
                break

            elif key == ord('s') or key == ord('S'):  # Skip = negative
                save_labels(img_path, [], h, w)
                labeled_count += 1
                print(f"  ○ {fname}: skipped (negative)")
                break

            elif key == ord('u') or key == ord('U'):  # Undo
                if boxes:
                    boxes.pop()
                    display_frame = current_frame.copy()
                    for bx1, by1, bx2, by2 in boxes:
                        cv2.rectangle(display_frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                    print(f"  ↩ Undid last box")

            elif key == ord('q') or key == ord('Q'):  # Quit
                print(f"\n  Quit early. Labeled {labeled_count} images ({positive_count} positive).")
                cv2.destroyAllWindows()
                _write_dataset_yaml(positive_count)
                return

    cv2.destroyAllWindows()
    print(f"\n{'='*60}")
    print(f"  DONE! Labeled {labeled_count} images ({positive_count} positive)")
    print(f"  Labels saved to: {LABELS_DIR}/")
    print(f"{'='*60}\n")
    _write_dataset_yaml(positive_count)


def _write_dataset_yaml(positive_count):
    """Write dataset.yaml for YOLO training."""
    yaml_path = os.path.join(FRAMES_DIR, "dataset.yaml")
    abs_frames = os.path.abspath(FRAMES_DIR)
    with open(yaml_path, "w") as f:
        f.write(f"path: {abs_frames}\n")
        f.write(f"train: .\n")
        f.write(f"val: .\n")
        f.write(f"names:\n")
        f.write(f"  0: {CLASS_NAME}\n")
    print(f"  Dataset config: {yaml_path}")
    print(f"\n  To train: python -c \"")
    print(f"    from ultralytics import YOLO")
    print(f"    model = YOLO('yolov8n.pt')")
    print(f"    model.train(data='{yaml_path}', epochs=50, imgsz=640)\"")


if __name__ == "__main__":
    main()
