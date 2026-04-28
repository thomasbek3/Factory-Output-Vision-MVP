#!/usr/bin/env python3
"""Diagnostic-only person/panel separation probe for transfer review packets.

This script does not mint source tokens and does not increment counts. It reads
transfer review packets plus receipt/frame artifacts and estimates whether
mesh-like evidence is visible outside an estimated human silhouette, not merely
outside a coarse person bbox.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_PACKETS_REPORT = Path("data/reports/factory2_transfer_review_packets.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_person_panel_separation.json")
SCHEMA_VERSION = "factory-person-panel-separation-v1"
PACKET_SCHEMA_VERSION = "factory-person-panel-separation-packet-v1"

Box = Tuple[float, float, float, float]
JsonDict = Dict[str, Any]
PathLike = Union[str, Path]
FrameLoader = Callable[[Path], np.ndarray]
PersonBoxDetector = Callable[[Path], List[Box]]
SilhouetteEstimator = Callable[[np.ndarray, Box, Box], np.ndarray]


def read_json(path: PathLike) -> Any:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: PathLike, data: Any, *, force: bool = False) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _resolve(path_value: Optional[str], repo_root: Path, base_dir: Optional[Path] = None) -> Optional[Path]:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidate = repo_root / path
    if candidate.exists() or base_dir is None:
        return candidate
    return base_dir / path


def default_frame_loader(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def box_overlap_fraction(box: Box, other: Box) -> float:
    x1, y1, w1, h1 = box
    x2, y2, w2, h2 = other
    left = max(x1, x2)
    top = max(y1, y2)
    right = min(x1 + w1, x2 + w2)
    bottom = min(y1 + h1, y2 + h2)
    if right <= left or bottom <= top or w1 <= 0 or h1 <= 0:
        return 0.0
    return ((right - left) * (bottom - top)) / (w1 * h1)


def _box_center(box: Box) -> Tuple[float, float]:
    return (box[0] + box[2] / 2.0, box[1] + box[3] / 2.0)


def _distance(left: Tuple[float, float], right: Tuple[float, float]) -> float:
    return float(np.hypot(left[0] - right[0], left[1] - right[1]))


def _clip_box(box: Box, shape: Tuple[int, int]) -> Box:
    height, width = shape
    x, y, w, h = box
    left = max(0.0, min(float(width), x))
    top = max(0.0, min(float(height), y))
    right = max(left, min(float(width), x + max(0.0, w)))
    bottom = max(top, min(float(height), y + max(0.0, h)))
    return (left, top, max(0.0, right - left), max(0.0, bottom - top))


def _box_mask(shape: Tuple[int, int], box: Box) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    x, y, w, h = [int(round(value)) for value in _clip_box(box, shape)]
    if w <= 0 or h <= 0:
        return mask
    mask[y : y + h, x : x + w] = True
    return mask


def _bool_mask(value: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    mask = np.asarray(value).astype(bool)
    if mask.shape != shape:
        raise ValueError(f"person mask shape {mask.shape} does not match image shape {shape}")
    return mask


def _dilate_mask(mask: np.ndarray, *, size: int = 7) -> np.ndarray:
    image = Image.fromarray(mask.astype(np.uint8) * 255)
    return np.asarray(image.filter(ImageFilter.MaxFilter(size=size))) > 0


def _erode_mask(mask: np.ndarray, *, size: int = 7) -> np.ndarray:
    image = Image.fromarray(mask.astype(np.uint8) * 255)
    return np.asarray(image.filter(ImageFilter.MinFilter(size=size))) > 0


def _gray_image(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.float32)
    return image.astype(np.float32).mean(axis=2)


def masked_mesh_signal(gray: np.ndarray, mask: np.ndarray) -> JsonDict:
    mask = mask.astype(bool)
    if mask.sum() < 16:
        return {
            "edge_density": 0.0,
            "vertical_edge_density": 0.0,
            "horizontal_edge_density": 0.0,
            "edge_balance": 0.0,
            "mesh_texture_score": 0.0,
        }

    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    mask_dx = mask[:, 1:] & mask[:, :-1]
    mask_dy = mask[1:, :] & mask[:-1, :]
    active = gray[mask]
    contrast = float(np.percentile(active, 95) - np.percentile(active, 5)) if active.size else 0.0
    threshold = max(18.0, contrast * 0.20)
    vertical_edge_density = float(np.mean(dx[mask_dx] >= threshold)) if mask_dx.any() else 0.0
    horizontal_edge_density = float(np.mean(dy[mask_dy] >= threshold)) if mask_dy.any() else 0.0
    edge_density = (vertical_edge_density + horizontal_edge_density) / 2.0
    larger = max(vertical_edge_density, horizontal_edge_density, 1e-6)
    edge_balance = min(vertical_edge_density, horizontal_edge_density) / larger
    mesh_texture_score = edge_density * edge_balance
    return {
        "edge_density": round(edge_density, 6),
        "vertical_edge_density": round(vertical_edge_density, 6),
        "horizontal_edge_density": round(horizontal_edge_density, 6),
        "edge_balance": round(edge_balance, 6),
        "mesh_texture_score": round(mesh_texture_score, 6),
    }


def estimate_person_silhouette(image: np.ndarray, person_box: Box, panel_box: Box) -> np.ndarray:
    """Estimate a conservative person silhouette within the frame.

    The estimator is diagnostic-only. It uses GrabCut when cv2 is available,
    seeded from a coarse person box and a smaller sure-person core. If runtime
    support is missing, it falls back to the coarse person box.
    """

    try:
        import cv2
    except Exception:
        return _box_mask(image.shape[:2], person_box)

    height, width = image.shape[:2]
    person_box = _clip_box(person_box, (height, width))
    panel_box = _clip_box(panel_box, (height, width))
    margin = max(24, int(round(min(max(person_box[2], 1.0), max(person_box[3], 1.0)) * 0.08)))

    left = max(0, int(round(min(person_box[0], panel_box[0]) - margin)))
    top = max(0, int(round(min(person_box[1], panel_box[1]) - margin)))
    right = min(width, int(round(max(person_box[0] + person_box[2], panel_box[0] + panel_box[2]) + margin)))
    bottom = min(height, int(round(max(person_box[1] + person_box[3], panel_box[1] + panel_box[3]) + margin)))
    if right <= left or bottom <= top:
        return _box_mask((height, width), person_box)

    roi = image[top:bottom, left:right].copy()
    mask = np.full(roi.shape[:2], cv2.GC_PR_BGD, dtype=np.uint8)

    px, py, pw, ph = [int(round(value)) for value in person_box]
    px -= left
    py -= top
    if pw <= 1 or ph <= 1:
        return _box_mask((height, width), person_box)
    mask[py : py + ph, px : px + pw] = cv2.GC_PR_FGD

    core_left = px + int(round(pw * 0.18))
    core_top = py + int(round(ph * 0.12))
    core_width = max(1, int(round(pw * 0.64)))
    core_height = max(1, int(round(ph * 0.72)))
    core_right = min(mask.shape[1], core_left + core_width)
    core_bottom = min(mask.shape[0], core_top + core_height)
    mask[core_top:core_bottom, core_left:core_right] = cv2.GC_FGD

    panel_mask = _box_mask(mask.shape, (panel_box[0] - left, panel_box[1] - top, panel_box[2], panel_box[3]))
    bbox_overlap = _box_mask(mask.shape, (px, py, pw, ph))
    outside_bbox_panel = panel_mask & ~bbox_overlap
    if outside_bbox_panel.any():
        mask[outside_bbox_panel] = cv2.GC_PR_BGD

    bgd_model = np.zeros((1, 65), dtype=np.float64)
    fgd_model = np.zeros((1, 65), dtype=np.float64)
    try:
        cv2.grabCut(roi, mask, None, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_MASK)
    except Exception:
        return _box_mask((height, width), person_box)

    foreground = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD])
    output = np.zeros((height, width), dtype=bool)
    output[top:bottom, left:right] = foreground
    return output


def analyze_frame_person_panel_separation(
    image: np.ndarray,
    *,
    panel_box_xywh: Sequence[float],
    person_box_xywh: Sequence[float],
    person_mask: Optional[np.ndarray] = None,
    frame_path: Optional[str] = None,
    timestamp: Optional[float] = None,
    zone: Optional[str] = None,
) -> JsonDict:
    height, width = image.shape[:2]
    panel_box = _clip_box(tuple(float(value) for value in panel_box_xywh), (height, width))
    person_box = _clip_box(tuple(float(value) for value in person_box_xywh), (height, width))
    person_mask_bool = _bool_mask(person_mask, (height, width)) if person_mask is not None else _box_mask((height, width), person_box)
    panel_mask = _box_mask((height, width), panel_box)

    panel_area = int(panel_mask.sum())
    person_bbox_overlap_ratio = round(box_overlap_fraction(panel_box, person_box), 6)
    bbox_outside_person_ratio = round(max(0.0, 1.0 - person_bbox_overlap_ratio), 6)
    visible_nonperson_mask = panel_mask & ~person_mask_bool
    visible_nonperson_area = int(visible_nonperson_mask.sum())
    visible_nonperson_ratio = round((visible_nonperson_area / panel_area) if panel_area else 0.0, 6)

    silhouette_band = _dilate_mask(person_mask_bool, size=7) & ~_erode_mask(person_mask_bool, size=7)
    border_mask = panel_mask & silhouette_band
    border_area = int(border_mask.sum())
    silhouette_border_contact_ratio = round((border_area / panel_area) if panel_area else 0.0, 6)

    gray = _gray_image(image)
    nonperson_signal = masked_mesh_signal(gray, visible_nonperson_mask)
    border_signal = masked_mesh_signal(gray, border_mask)
    max_mesh_signal = max(
        float(nonperson_signal.get("mesh_texture_score") or 0.0),
        float(border_signal.get("mesh_texture_score") or 0.0),
    )
    estimated_visible_signal = round(
        (visible_nonperson_ratio * float(nonperson_signal.get("mesh_texture_score") or 0.0))
        + (silhouette_border_contact_ratio * float(border_signal.get("mesh_texture_score") or 0.0)),
        6,
    )

    reasons: List[str] = []
    if person_bbox_overlap_ratio <= 0.05 and silhouette_border_contact_ratio <= 0.03:
        if max_mesh_signal >= 0.04 or visible_nonperson_ratio >= 0.18:
            separation_decision = "static_or_background_edge"
            reasons.append("mesh-like region is not attached to the detected person silhouette")
        else:
            separation_decision = "insufficient_visibility"
            reasons.append("no meaningful person contact or nonperson panel signal was visible")
    elif visible_nonperson_ratio >= 0.22 and max_mesh_signal >= 0.06 and silhouette_border_contact_ratio >= 0.03:
        separation_decision = "separable_panel_candidate"
        reasons.append("mesh-like signal remains outside the estimated person silhouette")
        if bbox_outside_person_ratio <= 0.05:
            reasons.append("separation exists inside a coarse person bbox, not only outside it")
    elif visible_nonperson_ratio <= 0.08 or estimated_visible_signal < 0.01:
        separation_decision = "worker_body_overlap"
        reasons.append("candidate remains swallowed by the estimated person silhouette")
    else:
        separation_decision = "insufficient_visibility"
        reasons.append("some nonperson signal exists, but not enough to prove a discrete panel")

    return {
        "frame_path": frame_path or "",
        "timestamp": timestamp,
        "zone": zone or "unknown",
        "panel_box_xywh": [round(float(value), 3) for value in panel_box],
        "person_box_xywh": [round(float(value), 3) for value in person_box],
        "person_bbox_overlap_ratio": person_bbox_overlap_ratio,
        "bbox_outside_person_ratio": bbox_outside_person_ratio,
        "visible_nonperson_area": visible_nonperson_area,
        "visible_nonperson_ratio": visible_nonperson_ratio,
        "estimated_visible_nonperson_region_signal": estimated_visible_signal,
        "silhouette_border_contact_ratio": silhouette_border_contact_ratio,
        "mesh_signal_nonperson_score": round(float(nonperson_signal.get("mesh_texture_score") or 0.0), 6),
        "mesh_signal_border_score": round(float(border_signal.get("mesh_texture_score") or 0.0), 6),
        "nonperson_edge_density": nonperson_signal.get("edge_density", 0.0),
        "border_edge_density": border_signal.get("edge_density", 0.0),
        "separation_decision": separation_decision,
        "reason_strings": reasons,
    }


def _blend_mask(image: np.ndarray, mask: np.ndarray, color: Tuple[int, int, int], alpha: float) -> None:
    if not mask.any():
        return
    color_array = np.array(color, dtype=np.float32)
    image[mask] = np.clip(image[mask].astype(np.float32) * (1.0 - alpha) + color_array * alpha, 0, 255).astype(np.uint8)


def write_visual_receipt(
    image: np.ndarray,
    *,
    person_mask: np.ndarray,
    frame_result: JsonDict,
    path: Path,
    force: bool,
) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    visual = image.copy()
    person_mask_bool = person_mask.astype(bool)
    panel_mask = _box_mask(visual.shape[:2], tuple(float(value) for value in frame_result["panel_box_xywh"]))
    visible_nonperson_mask = panel_mask & ~person_mask_bool
    _blend_mask(visual, person_mask_bool, (200, 50, 50), 0.32)
    _blend_mask(visual, visible_nonperson_mask, (40, 200, 80), 0.48)

    output = Image.fromarray(visual)
    draw = ImageDraw.Draw(output)
    px, py, pw, ph = [int(round(value)) for value in frame_result["person_box_xywh"]]
    bx, by, bw, bh = [int(round(value)) for value in frame_result["panel_box_xywh"]]
    draw.rectangle((px, py, px + pw, py + ph), outline=(255, 0, 0), width=3)
    draw.rectangle((bx, by, bx + bw, by + bh), outline=(255, 255, 0), width=3)
    output.save(path)


def _event_from_packet(packet: JsonDict) -> str:
    for candidate in (
        (packet.get("assets") or {}).get("receipt_json_path"),
        (packet.get("assets") or {}).get("diagnostic_path"),
    ):
        if not candidate:
            continue
        match = re.search(r"(event\d+)", str(candidate))
        if match:
            return match.group(1)
    return "event-unknown"


def _packet_id(event: str, track_id: int) -> str:
    return f"{event}-track{track_id:06d}"


def _select_person_box(panel_box: Box, person_boxes: Sequence[Box]) -> Optional[Box]:
    if not person_boxes:
        return None
    panel_center = _box_center(panel_box)

    def key(box: Box) -> Tuple[float, float]:
        overlap = box_overlap_fraction(panel_box, box)
        distance = _distance(panel_center, _box_center(box))
        return (overlap, -distance)

    return max(person_boxes, key=key)


def _observation_rows(receipt: JsonDict) -> List[JsonDict]:
    for key in ("evidence", "diagnosis"):
        payload = receipt.get(key)
        if isinstance(payload, dict):
            observations = payload.get("observations")
            if isinstance(observations, list):
                return [item for item in observations if isinstance(item, dict)]
    return []


def _select_observations(observations: Sequence[JsonDict]) -> List[JsonDict]:
    if len(observations) <= 3:
        return list(observations)
    indices = sorted({0, len(observations) // 2, len(observations) - 1})
    return [observations[index] for index in indices]


def _packet_output_path(packet: JsonDict, repo_root: Path, base_dir: Path) -> Path:
    receipt_path = _resolve((packet.get("assets") or {}).get("receipt_json_path"), repo_root, base_dir)
    if receipt_path is not None:
        return receipt_path.with_name(receipt_path.stem + "-person-panel-separation.json")
    track_id = int(packet.get("track_id") or 0)
    return base_dir / "track_receipts" / f"track-{track_id:06d}-person-panel-separation.json"


def _frame_visual_path(packet_path: Path, frame_path: str) -> Path:
    frame_name = Path(frame_path).stem
    return packet_path.with_name(packet_path.stem + f"-{frame_name}.png")


def _default_person_box_detector(repo_root: Path) -> PersonBoxDetector:
    model_cache: Dict[str, Any] = {}

    def detector(frame_path: Path) -> List[Box]:
        if "model" not in model_cache:
            try:
                from scripts.diagnose_event_window import detect_person_boxes, load_yolo_model
            except Exception:
                model_cache["model"] = None
                model_cache["detect"] = None
            else:
                model_path = repo_root / "yolov8n.pt"
                if not model_path.exists():
                    model_cache["model"] = None
                    model_cache["detect"] = detect_person_boxes
                else:
                    model_cache["model"] = load_yolo_model(model_path)
                    model_cache["detect"] = detect_person_boxes
        detect = model_cache.get("detect")
        model = model_cache.get("model")
        if detect is None or model is None:
            return []
        try:
            return [tuple(float(value) for value in box) for box in detect(model, frame_path=frame_path, confidence=0.20)]
        except Exception:
            return []

    return detector


def _recommend_packet(packet: JsonDict, frame_results: Sequence[JsonDict]) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    if not frame_results:
        return "insufficient_visibility", ["no sampled frames were readable"]

    separable_source_frames = sum(
        1
        for frame in frame_results
        if frame.get("separation_decision") == "separable_panel_candidate" and str(frame.get("zone")) != "output"
    )
    separable_total_frames = sum(1 for frame in frame_results if frame.get("separation_decision") == "separable_panel_candidate")
    worker_overlap_frames = sum(1 for frame in frame_results if frame.get("separation_decision") == "worker_body_overlap")
    static_frames = sum(1 for frame in frame_results if frame.get("separation_decision") == "static_or_background_edge")
    max_signal = max(float(frame.get("estimated_visible_nonperson_region_signal") or 0.0) for frame in frame_results)
    max_visible_ratio = max(float(frame.get("visible_nonperson_ratio") or 0.0) for frame in frame_results)

    if separable_source_frames >= 2:
        reasons.append("at least two source/transfer frames show mesh-like signal outside the estimated person silhouette")
        reasons.append("diagnostic only: this is a candidate for later gate integration, not a source-token approval")
        return "countable_panel_candidate", reasons

    if separable_total_frames == 0 and static_frames > 0 and worker_overlap_frames == 0:
        reasons.append("mesh-like evidence appears detached from the worker rather than carried with them")
        return "not_panel", reasons

    if worker_overlap_frames == len(frame_results):
        reasons.append("all sampled frames remain swallowed by the estimated person silhouette")
        return "not_panel", reasons

    if separable_total_frames > 0:
        reasons.append("some frames show outside-silhouette signal, but not enough source/transfer persistence yet")
    else:
        reasons.append("outside-silhouette evidence stayed below the diagnostic threshold")
    reasons.append(f"max_visible_nonperson_ratio={max_visible_ratio:.3f}, max_signal={max_signal:.3f}")
    return "insufficient_visibility", reasons


def build_person_panel_separation_report(
    packets_report: PathLike = DEFAULT_PACKETS_REPORT,
    output: PathLike = DEFAULT_OUTPUT,
    *,
    repo_root: PathLike = Path("."),
    limit: int = 3,
    packet_ids: Optional[Sequence[str]] = None,
    force: bool = False,
    frame_loader: FrameLoader = default_frame_loader,
    person_box_detector: Optional[PersonBoxDetector] = None,
    silhouette_estimator: SilhouetteEstimator = estimate_person_silhouette,
) -> JsonDict:
    repo_root = Path(repo_root)
    packets_report_path = Path(packets_report)
    output_path = Path(output)
    if not packets_report_path.is_absolute():
        packets_report_path = repo_root / packets_report_path
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    if output_path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {output_path}; pass --force")

    report = read_json(packets_report_path)
    packets = [packet for packet in (report.get("packets") or []) if isinstance(packet, dict)]
    if packet_ids:
        wanted = set(packet_ids)
        packets = [packet for packet in packets if _packet_id(_event_from_packet(packet), int(packet.get("track_id") or 0)) in wanted]
    elif limit > 0:
        packets = packets[:limit]

    detector = person_box_detector or _default_person_box_detector(repo_root)
    packet_results: List[JsonDict] = []
    for packet in packets:
        assets = packet.get("assets") or {}
        receipt_path = _resolve(assets.get("receipt_json_path"), repo_root, packets_report_path.parent)
        if receipt_path is None or not receipt_path.exists():
            continue

        receipt = read_json(receipt_path)
        observations = _select_observations(_observation_rows(receipt))
        event = _event_from_packet(packet)
        track_id = int(packet.get("track_id") or receipt.get("track_id") or 0)
        packet_id = _packet_id(event, track_id)
        packet_output_path = _packet_output_path(packet, repo_root, receipt_path.parent)
        selected_frames: List[JsonDict] = []

        for observation in observations:
            frame_path = _resolve(observation.get("frame_path"), repo_root, receipt_path.parent)
            if frame_path is None or not frame_path.exists():
                selected_frames.append(
                    {
                        "frame_path": observation.get("frame_path") or "",
                        "timestamp": observation.get("timestamp"),
                        "zone": observation.get("zone") or "unknown",
                        "separation_decision": "frame_unreadable",
                        "reason_strings": ["frame asset is missing"],
                    }
                )
                continue

            image = frame_loader(frame_path)
            panel_box = tuple(float(value) for value in observation.get("box_xywh") or (0.0, 0.0, 0.0, 0.0))
            person_boxes = detector(frame_path)
            selected_person_box = _select_person_box(panel_box, person_boxes)
            if selected_person_box is None:
                frame_result = {
                    "frame_path": _repo_rel(frame_path, repo_root),
                    "timestamp": observation.get("timestamp"),
                    "zone": observation.get("zone") or "unknown",
                    "panel_box_xywh": [round(float(value), 3) for value in panel_box],
                    "person_box_xywh": [],
                    "person_bbox_overlap_ratio": 0.0,
                    "bbox_outside_person_ratio": 1.0,
                    "visible_nonperson_area": 0,
                    "visible_nonperson_ratio": 0.0,
                    "estimated_visible_nonperson_region_signal": 0.0,
                    "silhouette_border_contact_ratio": 0.0,
                    "mesh_signal_nonperson_score": 0.0,
                    "mesh_signal_border_score": 0.0,
                    "nonperson_edge_density": 0.0,
                    "border_edge_density": 0.0,
                    "separation_decision": "insufficient_visibility",
                    "reason_strings": ["no person box detected on sampled frame"],
                }
                selected_frames.append(frame_result)
                continue

            person_mask = _bool_mask(silhouette_estimator(image, selected_person_box, panel_box), image.shape[:2])
            frame_result = analyze_frame_person_panel_separation(
                image,
                panel_box_xywh=panel_box,
                person_box_xywh=selected_person_box,
                person_mask=person_mask,
                frame_path=_repo_rel(frame_path, repo_root),
                timestamp=observation.get("timestamp"),
                zone=observation.get("zone"),
            )
            frame_result["receipt_person_overlap_ratio"] = round(float(observation.get("person_overlap") or 0.0), 6)
            visual_path = _frame_visual_path(packet_output_path, frame_path.name)
            write_visual_receipt(image, person_mask=person_mask, frame_result=frame_result, path=visual_path, force=force)
            frame_result["visual_receipt_path"] = _repo_rel(visual_path, repo_root)
            selected_frames.append(frame_result)

        recommendation, reason_strings = _recommend_packet(packet, selected_frames)
        summary = {
            "frame_count": len(selected_frames),
            "separable_panel_candidate_frames": sum(
                1 for frame in selected_frames if frame.get("separation_decision") == "separable_panel_candidate"
            ),
            "worker_body_overlap_frames": sum(
                1 for frame in selected_frames if frame.get("separation_decision") == "worker_body_overlap"
            ),
            "static_or_background_edge_frames": sum(
                1 for frame in selected_frames if frame.get("separation_decision") == "static_or_background_edge"
            ),
            "max_visible_nonperson_ratio": round(
                max((float(frame.get("visible_nonperson_ratio") or 0.0) for frame in selected_frames), default=0.0),
                6,
            ),
            "max_estimated_visible_signal": round(
                max((float(frame.get("estimated_visible_nonperson_region_signal") or 0.0) for frame in selected_frames), default=0.0),
                6,
            ),
            "packet_person_overlap_ratio": round(
                float(((packet.get("ranking_features") or {}).get("person_overlap_ratio") or 0.0)),
                6,
            ),
            "packet_outside_person_ratio": round(
                float(((packet.get("ranking_features") or {}).get("outside_person_ratio") or 0.0)),
                6,
            ),
        }
        packet_result = {
            "schema_version": PACKET_SCHEMA_VERSION,
            "diagnostic_only": True,
            "packet_id": packet_id,
            "event": event,
            "track_id": track_id,
            "receipt_json_path": _repo_rel(receipt_path, repo_root),
            "packet_diagnostic_path": _repo_rel(packet_output_path, repo_root),
            "selected_frames": selected_frames,
            "summary": summary,
            "recommendation": recommendation,
            "reason_strings": reason_strings,
            "note": "Diagnostic only. Does not approve source tokens or counts.",
        }
        write_json(packet_output_path, packet_result, force=force)
        packet_results.append(packet_result)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "purpose": "person/panel separation evidence for transfer packets; not a source-token or count approval",
        "packets_report": _repo_rel(packets_report_path, repo_root),
        "packet_count": len(packet_results),
        "packets": packet_results,
    }
    write_json(output_path, payload, force=force)
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets-report", type=Path, default=DEFAULT_PACKETS_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--packet-id", action="append", dest="packet_ids", default=None, help="packet id like event0002-track000005; may repeat")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    result = build_person_panel_separation_report(
        packets_report=args.packets_report,
        output=args.output,
        repo_root=REPO_ROOT,
        limit=args.limit,
        packet_ids=args.packet_ids,
        force=args.force,
    )
    print(json.dumps({"output": str(args.output), "packet_count": result["packet_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
