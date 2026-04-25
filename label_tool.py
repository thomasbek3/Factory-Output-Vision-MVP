"""
Local YOLO labeling tool with zoom/pan, display enhancement, and prelabel review.

HOW TO USE:
1. Run: python label_tool.py
2. Each image appears in a window
3. Left-click and drag to draw a box around the panel the worker is HOLDING
4. Press ENTER to save and go to next image
5. Press S to save as negative (no panel visible)
6. Press U to undo last box
7. Press Q to quit early

Useful controls for low-contrast mesh:
- Mouse wheel or +/-: zoom in/out around cursor/center
- Right-click drag, W/A/D, or arrow keys: pan (S stays skip/save-negative)
- C: contrast mode
- H: sharpen mode
- E: edge overlay mode
- G: grayscale mode
- I: invert mode
- O: original mode
- R: reset zoom/pan

Prelabels:
- Existing YOLO labels are loaded when present.
- By default, already-labeled images are skipped to preserve the old workflow.
- Use --review-existing to review/edit prelabels from an auto-prelabel step.

Boxes are saved in YOLO format to training_frames/labels/ by default.
"""

from __future__ import annotations

import argparse
import glob
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

FRAMES_DIR = "training_frames"
LABELS_DIR = os.path.join(FRAMES_DIR, "labels")
CLASS_NAME = "panel"
WINDOW = "Label Tool - HELD panel | Enter=save S=negative U=undo Q=quit"
WINDOW_MAX_W = 1400
WINDOW_MAX_H = 900
MIN_BOX_PX = 10
MAX_ABS_NORMALIZED_LABEL_VALUE = 10.0
ARROW_LEFT_KEYS = {2424832, 63234, 65361}
ARROW_UP_KEYS = {2490368, 63232, 65362}
ARROW_RIGHT_KEYS = {2555904, 63235, 65363}
ARROW_DOWN_KEYS = {2621440, 63233, 65364}

# State
boxes: list[tuple[int, int, int, int]] = []  # pixel coords in source image
current_frame = None
view_state: "ViewState | None" = None
drawing = False
panning = False
start_x_img = 0
start_y_img = 0
last_pan_screen_x = 0
last_pan_screen_y = 0
display_mode = "original"


@dataclass
class ViewState:
    """Viewport state for mapping image pixels to window pixels."""

    img_w: int
    img_h: int
    window_w: int
    window_h: int
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0

    def __post_init__(self) -> None:
        self.clamp()

    @property
    def view_w(self) -> float:
        return self.window_w / self.zoom

    @property
    def view_h(self) -> float:
        return self.window_h / self.zoom

    def clamp(self) -> None:
        self.zoom = max(0.2, min(float(self.zoom), 20.0))
        max_pan_x = max(0.0, self.img_w - self.view_w)
        max_pan_y = max(0.0, self.img_h - self.view_h)
        self.pan_x = max(0.0, min(float(self.pan_x), max_pan_x))
        self.pan_y = max(0.0, min(float(self.pan_y), max_pan_y))

    def screen_to_image(self, x: int, y: int) -> tuple[int, int]:
        img_x = int(round(self.pan_x + x / self.zoom))
        img_y = int(round(self.pan_y + y / self.zoom))
        img_x = max(0, min(img_x, self.img_w))
        img_y = max(0, min(img_y, self.img_h))
        return img_x, img_y

    def image_to_screen(self, x: int, y: int) -> tuple[int, int]:
        sx = int(round((x - self.pan_x) * self.zoom))
        sy = int(round((y - self.pan_y) * self.zoom))
        return sx, sy

    def zoom_at(self, factor: float, cursor_x: int | None = None, cursor_y: int | None = None) -> None:
        if cursor_x is None:
            cursor_x = self.window_w // 2
        if cursor_y is None:
            cursor_y = self.window_h // 2
        before_x, before_y = self.screen_to_image(cursor_x, cursor_y)
        self.zoom *= factor
        self.clamp()
        self.pan_x = before_x - cursor_x / self.zoom
        self.pan_y = before_y - cursor_y / self.zoom
        self.clamp()

    def pan_by_screen_delta(self, dx: int, dy: int) -> None:
        self.pan_x -= dx / self.zoom
        self.pan_y -= dy / self.zoom
        self.clamp()

    def reset(self) -> None:
        self.zoom = min(self.window_w / self.img_w, self.window_h / self.img_h, 1.0)
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.clamp()

    def visible_crop_bounds(self) -> tuple[int, int, int, int]:
        x1 = int(round(self.pan_x))
        y1 = int(round(self.pan_y))
        x2 = int(round(min(self.img_w, self.pan_x + self.view_w)))
        y2 = int(round(min(self.img_h, self.pan_y + self.view_h)))
        return x1, y1, x2, y2

    def display_size_for_crop(self, crop_w: int, crop_h: int) -> tuple[int, int]:
        """Displayed crop size preserving the same uniform scale used by coordinate mapping."""
        display_w = max(1, min(self.window_w, int(round(crop_w * self.zoom))))
        display_h = max(1, min(self.window_h, int(round(crop_h * self.zoom))))
        return display_w, display_h


def label_path_for(image_path: str) -> Path:
    base = Path(image_path).stem
    return Path(LABELS_DIR) / f"{base}.txt"


def load_labels(image_path: str, img_h: int, img_w: int) -> list[tuple[int, int, int, int]]:
    """Load YOLO-format labels for an image as pixel-space boxes."""
    label_path = label_path_for(image_path)
    if not label_path.exists():
        return []

    loaded: list[tuple[int, int, int, int]] = []
    for line in label_path.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        try:
            _, cx_s, cy_s, bw_s, bh_s = parts
            cx = float(cx_s)
            cy = float(cy_s)
            bw = float(bw_s)
            bh = float(bh_s)
        except ValueError:
            continue

        values = np.array([cx, cy, bw, bh], dtype=float)
        if not np.isfinite(values).all() or np.abs(values).max() > MAX_ABS_NORMALIZED_LABEL_VALUE:
            continue

        x1 = int(round((cx - bw / 2) * img_w))
        y1 = int(round((cy - bh / 2) * img_h))
        x2 = int(round((cx + bw / 2) * img_w))
        y2 = int(round((cy + bh / 2) * img_h))
        x1 = max(0, min(x1, img_w))
        y1 = max(0, min(y1, img_h))
        x2 = max(0, min(x2, img_w))
        y2 = max(0, min(y2, img_h))
        if x2 - x1 >= 1 and y2 - y1 >= 1:
            loaded.append((x1, y1, x2, y2))
    return loaded


def save_labels(image_path, img_boxes, img_h, img_w):
    """Save in YOLO format: class_id cx cy w h (all normalized 0-1)."""
    os.makedirs(LABELS_DIR, exist_ok=True)
    label_path = label_path_for(image_path)

    if not img_boxes:
        # Save empty file for negative examples
        label_path.write_text("")
        return

    with label_path.open("w") as f:
        for x1, y1, x2, y2 in img_boxes:
            x1 = max(0, min(int(x1), img_w))
            y1 = max(0, min(int(y1), img_h))
            x2 = max(0, min(int(x2), img_w))
            y2 = max(0, min(int(y2), img_h))
            if x2 <= x1 or y2 <= y1:
                continue
            cx = ((x1 + x2) / 2) / img_w
            cy = ((y1 + y2) / 2) / img_h
            bw = (x2 - x1) / img_w
            bh = (y2 - y1) / img_h
            f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")


def apply_display_mode(frame, mode: str):
    """Return a display-only enhanced frame; original image is preserved for labels/training."""
    if mode == "original":
        return frame.copy()
    if mode == "contrast":
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced_l = clahe.apply(l_chan)
        merged = cv2.merge((enhanced_l, a_chan, b_chan))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    if mode == "sharpen":
        blur = cv2.GaussianBlur(frame, (0, 0), 1.2)
        return cv2.addWeighted(frame, 1.8, blur, -0.8, 0)
    if mode == "edges":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        overlay = frame.copy()
        overlay[edges > 0] = (0, 255, 255)
        return cv2.addWeighted(frame, 0.75, overlay, 0.25, 0)
    if mode == "gray":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if mode == "invert":
        return 255 - frame
    return frame.copy()


def render_view(frame, progress: str):
    if view_state is None:
        return frame.copy()

    enhanced = apply_display_mode(frame, display_mode)
    x1, y1, x2, y2 = view_state.visible_crop_bounds()
    crop = enhanced[y1:y2, x1:x2]
    if crop.size == 0:
        crop = enhanced

    crop_h, crop_w = crop.shape[:2]
    display_w, display_h = view_state.display_size_for_crop(crop_w, crop_h)
    resized = cv2.resize(crop, (display_w, display_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((view_state.window_h, view_state.window_w, 3), dtype=resized.dtype)
    canvas[:display_h, :display_w] = resized

    for bx1, by1, bx2, by2 in boxes:
        sx1, sy1 = view_state.image_to_screen(bx1, by1)
        sx2, sy2 = view_state.image_to_screen(bx2, by2)
        if sx2 < 0 or sy2 < 0 or sx1 > view_state.window_w or sy1 > view_state.window_h:
            continue
        cv2.rectangle(canvas, (sx1, sy1), (sx2, sy2), (0, 255, 0), 2)
        cv2.putText(canvas, CLASS_NAME, (max(0, sx1), max(18, sy1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    if drawing:
        sx1, sy1 = view_state.image_to_screen(start_x_img, start_y_img)
        mx, my = view_state.image_to_screen(_current_mouse_img[0], _current_mouse_img[1])
        cv2.rectangle(canvas, (sx1, sy1), (mx, my), (0, 165, 255), 2)

    cv2.putText(canvas, progress, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 0), 2)
    help_text = f"mode={display_mode} zoom={view_state.zoom:.1f}x | wheel/+/- zoom | RMB/arrows pan | C/H/E/G/I/O modes | Enter save"
    cv2.putText(canvas, help_text, (10, view_state.window_h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 0), 1)
    return canvas


_current_mouse_img = (0, 0)


def mouse_callback(event, x, y, flags, param):
    global drawing, panning, start_x_img, start_y_img, last_pan_screen_x, last_pan_screen_y, _current_mouse_img

    if view_state is None:
        return
    _current_mouse_img = view_state.screen_to_image(x, y)

    if event == cv2.EVENT_MOUSEWHEEL:
        # flags is positive when scrolling up in OpenCV's highgui.
        view_state.zoom_at(1.25 if flags > 0 else 0.8, x, y)
        return

    if event == cv2.EVENT_RBUTTONDOWN:
        panning = True
        last_pan_screen_x, last_pan_screen_y = x, y
        return

    if event == cv2.EVENT_MOUSEMOVE and panning:
        view_state.pan_by_screen_delta(x - last_pan_screen_x, y - last_pan_screen_y)
        last_pan_screen_x, last_pan_screen_y = x, y
        return

    if event == cv2.EVENT_RBUTTONUP:
        panning = False
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x_img, start_y_img = view_state.screen_to_image(x, y)
        _current_mouse_img = (start_x_img, start_y_img)
        return

    if event == cv2.EVENT_MOUSEMOVE and drawing:
        _current_mouse_img = view_state.screen_to_image(x, y)
        return

    if event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_x, end_y = view_state.screen_to_image(x, y)
        x1, y1 = min(start_x_img, end_x), min(start_y_img, end_y)
        x2, y2 = max(start_x_img, end_x), max(start_y_img, end_y)
        if abs(x2 - x1) > MIN_BOX_PX and abs(y2 - y1) > MIN_BOX_PX:
            boxes.append((x1, y1, x2, y2))


def _image_files(frames_dir: str) -> list[str]:
    patterns = ["*.jpg", "*.jpeg", "*.png"]
    files: list[str] = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(frames_dir, pattern)))
    return sorted(files)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YOLO box labeler with zoom/enhancement/prelabel review")
    parser.add_argument("--frames-dir", default=FRAMES_DIR, help="Directory containing images to label")
    parser.add_argument("--labels-dir", default=None, help="Directory for YOLO txt labels; defaults to <frames-dir>/labels")
    parser.add_argument("--review-existing", action="store_true", help="Review images that already have label txt files")
    return parser


def key_to_action(key: int) -> str | None:
    """Map cv2.waitKeyEx values to actions without arrow/ASCII collisions."""
    if key < 0:
        return None
    if key in ARROW_UP_KEYS:
        return "pan_up"
    if key in ARROW_LEFT_KEYS:
        return "pan_left"
    if key in ARROW_RIGHT_KEYS:
        return "pan_right"
    if key in ARROW_DOWN_KEYS:
        return "pan_down"
    if key >= 256:
        return None

    char = chr(key).lower()
    if key in (10, 13):
        return "save"
    if char == "s":
        return "negative"
    if char == "u":
        return "undo"
    if char == "q":
        return "quit"
    if char == "r":
        return "reset"
    if char in {"+", "="}:
        return "zoom_in"
    if char in {"-", "_"}:
        return "zoom_out"
    if char == "w":
        return "pan_up"
    if char == "a":
        return "pan_left"
    if char == "d":
        return "pan_right"
    if char == "c":
        return "contrast"
    if char == "h":
        return "sharpen"
    if char == "e":
        return "edges"
    if char == "g":
        return "gray"
    if char == "i":
        return "invert"
    if char == "o":
        return "original"
    return None


def main():
    global boxes, current_frame, view_state, display_mode, FRAMES_DIR, LABELS_DIR, drawing, panning

    args = _build_parser().parse_args()
    FRAMES_DIR = args.frames_dir
    LABELS_DIR = args.labels_dir or os.path.join(FRAMES_DIR, "labels")
    os.makedirs(LABELS_DIR, exist_ok=True)

    image_files = _image_files(FRAMES_DIR)
    if not image_files:
        print(f"No images found in {FRAMES_DIR}/")
        return

    already_labeled = {Path(lf).stem for lf in glob.glob(os.path.join(LABELS_DIR, "*.txt"))}
    if args.review_existing:
        remaining = image_files
    else:
        remaining = [f for f in image_files if Path(f).stem not in already_labeled]

    print(f"\n{'=' * 72}")
    print("  LABELING TOOL")
    print(f"  Frames dir: {FRAMES_DIR}")
    print(f"  Labels dir: {LABELS_DIR}")
    print(f"  Total images: {len(image_files)}")
    print(f"  Existing label files: {len(already_labeled)}")
    print(f"  Images in this pass: {len(remaining)}")
    print(f"{'=' * 72}")
    print("\n  CONTROLS:")
    print("  - Left-drag: draw box around HELD panel")
    print("  - Right-drag, W/A/D, or arrows: pan (S saves negative)")
    print("  - Mouse wheel or +/-: zoom")
    print("  - C contrast | H sharpen | E edges | G grayscale | I invert | O original")
    print("  - ENTER save | S negative | U undo | R reset view | Q quit\n")

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW, mouse_callback)

    labeled_count = len(already_labeled)
    positive_count = 0

    for img_path in remaining:
        boxes = []
        drawing = False
        panning = False
        display_mode = "original"
        current_frame = cv2.imread(img_path)
        if current_frame is None:
            continue

        h, w = current_frame.shape[:2]
        window_w = min(w, WINDOW_MAX_W)
        window_h = min(h, WINDOW_MAX_H)
        view_state = ViewState(img_w=w, img_h=h, window_w=window_w, window_h=window_h)
        view_state.reset()
        cv2.resizeWindow(WINDOW, window_w, window_h)

        boxes = load_labels(img_path, h, w)
        fname = os.path.basename(img_path)
        prelabel_note = f" prelabels={len(boxes)}" if boxes else ""

        while True:
            progress = f"[{labeled_count + 1}/{len(image_files)}] {fname}{prelabel_note}"
            cv2.imshow(WINDOW, render_view(current_frame, progress))
            action = key_to_action(cv2.waitKeyEx(30))

            if action == "save":
                save_labels(img_path, boxes, h, w)
                labeled_count += 1
                if boxes:
                    positive_count += 1
                    print(f"  ✓ {fname}: {len(boxes)} box(es) saved")
                else:
                    print(f"  ○ {fname}: saved as negative (no boxes)")
                break

            if action == "negative":
                boxes = []
                save_labels(img_path, boxes, h, w)
                labeled_count += 1
                print(f"  ○ {fname}: skipped/saved negative")
                break

            if action == "undo":
                if boxes:
                    boxes.pop()
                    print("  ↩ Undid last box")
                continue

            if action == "quit":
                print(f"\n  Quit early. Processed up to {fname}.")
                cv2.destroyAllWindows()
                _write_dataset_yaml(positive_count)
                return

            if action == "reset":
                view_state.reset()
            elif action == "zoom_in":
                view_state.zoom_at(1.25)
            elif action == "zoom_out":
                view_state.zoom_at(0.8)
            elif action == "pan_up":
                view_state.pan_by_screen_delta(0, 80)
            elif action == "pan_left":
                view_state.pan_by_screen_delta(80, 0)
            elif action == "pan_right":
                view_state.pan_by_screen_delta(-80, 0)
            elif action == "pan_down":
                view_state.pan_by_screen_delta(0, -80)
            elif action in {"contrast", "sharpen", "edges", "gray", "invert", "original"}:
                display_mode = action

    cv2.destroyAllWindows()
    print(f"\n{'=' * 60}")
    print(f"  DONE! Labels saved to: {LABELS_DIR}/")
    print(f"{'=' * 60}\n")
    _write_dataset_yaml(positive_count)


def _write_dataset_yaml(positive_count):
    """Write dataset.yaml for YOLO training."""
    yaml_path = os.path.join(FRAMES_DIR, "dataset.yaml")
    abs_frames = os.path.abspath(FRAMES_DIR)
    with open(yaml_path, "w") as f:
        f.write(f"path: {abs_frames}\n")
        f.write("train: .\n")
        f.write("val: .\n")
        f.write("names:\n")
        f.write(f"  0: {CLASS_NAME}\n")
    print(f"  Dataset config: {yaml_path}")
    print("\n  To train: python -c \"")
    print("    from ultralytics import YOLO")
    print("    model = YOLO('yolov8n.pt')")
    print(f"    model.train(data='{yaml_path}', epochs=50, imgsz=960)\"")


if __name__ == "__main__":
    main()
