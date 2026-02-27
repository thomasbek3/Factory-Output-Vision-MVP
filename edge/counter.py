from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


class FillLevelCounter:
    def __init__(self, empty_reference: np.ndarray, max_units: int = 20, diff_threshold: int = 25) -> None:
        self.empty_reference = empty_reference
        self.max_units = max_units
        self.diff_threshold = diff_threshold

    def estimate(self, roi_frame: np.ndarray) -> Tuple[int, float, float]:
        if roi_frame.shape[:2] != self.empty_reference.shape[:2]:
            reference = cv2.resize(self.empty_reference, (roi_frame.shape[1], roi_frame.shape[0]))
        else:
            reference = self.empty_reference

        roi_gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        empty_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

        roi_blur = cv2.GaussianBlur(roi_gray, (5, 5), 0)
        empty_blur = cv2.GaussianBlur(empty_gray, (5, 5), 0)

        diff = cv2.absdiff(roi_blur, empty_blur)
        _, thresh = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)

        kernel = np.ones((3, 3), np.uint8)
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        cleaned = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=2)

        filled_pixels = int(np.count_nonzero(cleaned))
        total_pixels = int(cleaned.shape[0] * cleaned.shape[1])
        ratio = filled_pixels / max(total_pixels, 1)

        pseudo_count = int(round(ratio * self.max_units))
        pseudo_count = max(0, min(self.max_units, pseudo_count))
        confidence = min(1.0, max(0.05, ratio * 1.8))
        return pseudo_count, confidence, ratio


class SlotOccupancyCounter:
    def __init__(self, grid_rows: int = 3, grid_cols: int = 4, threshold: float = 0.15) -> None:
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.threshold = threshold

    def estimate(self, roi_frame: np.ndarray) -> Tuple[int, float, float]:
        gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        h, w = binary.shape
        cell_h = max(1, h // self.grid_rows)
        cell_w = max(1, w // self.grid_cols)

        occupied = 0
        total_cells = self.grid_rows * self.grid_cols
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                y0, x0 = r * cell_h, c * cell_w
                y1 = h if r == self.grid_rows - 1 else (r + 1) * cell_h
                x1 = w if c == self.grid_cols - 1 else (c + 1) * cell_w
                cell = binary[y0:y1, x0:x1]
                fill_ratio = float(np.count_nonzero(cell)) / max(cell.size, 1)
                if fill_ratio >= self.threshold:
                    occupied += 1

        occupancy_ratio = occupied / max(total_cells, 1)
        confidence = min(1.0, max(0.1, occupancy_ratio + 0.25))
        return occupied, confidence, occupancy_ratio
