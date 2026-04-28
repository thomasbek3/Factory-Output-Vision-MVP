#!/usr/bin/env python3
"""Analyze receipt crop texture for possible wire-mesh panel evidence.

This is not a counter and does not allow source tokens. It is a bounded
perception experiment for worker-entangled receipts: do the raw crops contain
mesh-like edge/line texture worth deeper person-mask review, or are they just
solid worker/body/background crops?
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Union

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ImageLoader = Callable[[str], Any]


def _to_gray_array(image: Any) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 3:
        array = array.astype(np.float32).mean(axis=2)
    elif array.ndim == 2:
        array = array.astype(np.float32)
    else:
        raise ValueError("image must be a 2D grayscale or 3D color array")
    if array.size == 0:
        raise ValueError("image cannot be empty")
    return array


def analyze_crop_array(image: Any) -> dict[str, Any]:
    """Return simple mesh/edge evidence metrics for one crop array.

    The metrics are intentionally conservative and model-free. Wire mesh tends
    to create many balanced horizontal and vertical gradients. Solid worker/body
    crops tend to have lower edge density and less grid-like balance.
    """
    gray = _to_gray_array(image)
    if gray.shape[0] < 4 or gray.shape[1] < 4:
        return {
            "decision": "texture_uncertain",
            "reason": "crop_too_small",
            "edge_density": 0.0,
            "vertical_edge_density": 0.0,
            "horizontal_edge_density": 0.0,
            "edge_balance": 0.0,
            "panel_texture_score": 0.0,
        }

    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    # Adaptive threshold; the floor avoids treating mild compression noise as mesh.
    contrast = float(np.percentile(gray, 95) - np.percentile(gray, 5))
    threshold = max(18.0, contrast * 0.20)
    vertical_edge_density = float(np.mean(dx >= threshold))
    horizontal_edge_density = float(np.mean(dy >= threshold))
    edge_density = (vertical_edge_density + horizontal_edge_density) / 2.0
    larger = max(vertical_edge_density, horizontal_edge_density, 1e-6)
    edge_balance = min(vertical_edge_density, horizontal_edge_density) / larger
    panel_texture_score = edge_density * edge_balance

    if panel_texture_score >= 0.035 and edge_density >= 0.055 and edge_balance >= 0.35:
        decision = "panel_texture_candidate"
        reason = "balanced_high_frequency_edges"
    elif edge_density < 0.025 or panel_texture_score < 0.012:
        decision = "low_panel_texture"
        reason = "not_enough_mesh_like_edges"
    else:
        decision = "texture_uncertain"
        reason = "some_edges_but_not_enough_grid_confidence"

    return {
        "decision": decision,
        "reason": reason,
        "edge_density": round(edge_density, 6),
        "vertical_edge_density": round(vertical_edge_density, 6),
        "horizontal_edge_density": round(horizontal_edge_density, 6),
        "edge_balance": round(edge_balance, 6),
        "panel_texture_score": round(panel_texture_score, 6),
    }


def default_image_loader(path: str) -> Any:
    try:
        import cv2
    except Exception as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime crop analysis requires cv2; use the repo .venv") from exc
    resolved = resolve_repo_path(path)
    image = cv2.imread(str(resolved))
    if image is None:
        raise FileNotFoundError(resolved)
    return image


def resolve_repo_path(value: Union[str, Path]) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def receipt_crop_paths(receipt: dict[str, Any]) -> list[str]:
    assets = receipt.get("review_assets") or {}
    return [str(path) for path in assets.get("raw_crop_paths") or []]


def analyze_receipt(receipt_path: Path, *, image_loader: ImageLoader = default_image_loader) -> dict[str, Any]:
    receipt = load_json(receipt_path)
    crop_paths = receipt_crop_paths(receipt)
    crop_results: list[dict[str, Any]] = []
    for crop_path in crop_paths:
        try:
            evidence = analyze_crop_array(image_loader(crop_path))
            evidence["crop_path"] = crop_path
        except Exception as exc:
            evidence = {
                "crop_path": crop_path,
                "decision": "texture_unreadable",
                "reason": str(exc),
                "edge_density": 0.0,
                "panel_texture_score": 0.0,
            }
        crop_results.append(evidence)

    panel_candidates = sum(1 for item in crop_results if item.get("decision") == "panel_texture_candidate")
    low_texture = sum(1 for item in crop_results if item.get("decision") == "low_panel_texture")
    unreadable = sum(1 for item in crop_results if item.get("decision") == "texture_unreadable")
    max_score = max((float(item.get("panel_texture_score") or 0.0) for item in crop_results), default=0.0)

    if panel_candidates > 0:
        recommendation = "inspect_as_possible_panel_texture"
    elif unreadable == len(crop_results) and crop_results:
        recommendation = "regenerate_crop_assets"
    else:
        recommendation = "treat_as_low_texture_until_stronger_evidence"

    return {
        "receipt_json_path": str(receipt_path),
        "track_id": receipt.get("track_id"),
        "gate_decision": (receipt.get("perception_gate") or {}).get("decision"),
        "gate_reason": (receipt.get("perception_gate") or {}).get("reason"),
        "crop_count": len(crop_results),
        "panel_texture_candidate_crops": panel_candidates,
        "low_panel_texture_crops": low_texture,
        "max_panel_texture_score": round(max_score, 6),
        "recommendation": recommendation,
        "crop_evidence": crop_results,
    }


def analyze_work_queue_report(
    proof_report: dict[str, Any],
    *,
    limit: int = 10,
    image_loader: ImageLoader = default_image_loader,
) -> dict[str, Any]:
    items = (proof_report.get("source_token_work_queue") or {}).get("top_items") or []
    selected_items = items[:limit]
    receipts: list[dict[str, Any]] = []
    for item in selected_items:
        path_value = item.get("receipt_json_path")
        if not path_value:
            continue
        receipt_result = analyze_receipt(resolve_repo_path(path_value), image_loader=image_loader)
        receipt_result["work_queue_item"] = item
        receipts.append(receipt_result)

    panel_like = sum(1 for item in receipts if item.get("panel_texture_candidate_crops", 0) > 0)
    low_texture = sum(
        1
        for item in receipts
        if item.get("crop_count", 0) > 0 and item.get("panel_texture_candidate_crops", 0) == 0
    )
    return {
        "schema_version": "factory-panel-crop-evidence-v1",
        "purpose": "texture evidence for worker-entangled source-token receipts; not a count source",
        "receipt_count": len(receipts),
        "summary": {
            "panel_texture_candidate_receipts": panel_like,
            "low_panel_texture_receipts": low_texture,
        },
        "receipts": receipts,
    }


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze raw receipt crops for wire-mesh-like texture evidence")
    parser.add_argument("--proof-report", type=Path, default=Path("data/reports/factory2_morning_proof_report.json"))
    parser.add_argument("--receipt", action="append", dest="receipts", default=None, help="receipt JSON path; may repeat")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("data/reports/factory2_panel_crop_evidence.json"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.receipts:
        results = [analyze_receipt(resolve_repo_path(path)) for path in args.receipts]
        payload = {
            "schema_version": "factory-panel-crop-evidence-v1",
            "purpose": "texture evidence for selected worker-entangled receipts; not a count source",
            "receipt_count": len(results),
            "summary": {
                "panel_texture_candidate_receipts": sum(1 for item in results if item.get("panel_texture_candidate_crops", 0) > 0),
                "low_panel_texture_receipts": sum(1 for item in results if item.get("panel_texture_candidate_crops", 0) == 0),
            },
            "receipts": results,
        }
    else:
        proof_report = load_json(resolve_repo_path(args.proof_report))
        payload = analyze_work_queue_report(proof_report, limit=args.limit)

    write_json(args.output, payload, force=args.force)
    print(json.dumps({"output": str(args.output), "summary": payload.get("summary"), "receipt_count": payload.get("receipt_count")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
