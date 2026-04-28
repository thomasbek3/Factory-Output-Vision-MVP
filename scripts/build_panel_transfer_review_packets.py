#!/usr/bin/env python3
"""Build temporal transfer review packets for worker-entangled Factory2 tracks.

This is a PRD Milestone 1 tool. It does not count. It re-ranks diagnostic
receipts by transfer evidence and emits compact packet JSON/image artifacts for
human/VLM/AI audit.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


DEFAULT_PROOF_REPORT = Path("data/reports/factory2_morning_proof_report.json")
DEFAULT_OUTPUT = Path("data/reports/factory2_transfer_review_packets.json")
SCHEMA_VERSION = "factory-transfer-review-packets-v1"
PACKET_SCHEMA_VERSION = "factory-transfer-review-packet-v1"


JsonDict = Dict[str, Any]
PathLike = Union[str, Path]


def read_json(path: PathLike) -> Any:
    with Path(path).open() as fh:
        return json.load(fh)


def write_json(path: PathLike, data: Any, *, force: bool = False) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _repo_rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _resolve(path_value: Optional[str], repo_root: Path, base_dir: Optional[Path] = None) -> Optional[Path]:
    if not path_value:
        return None
    p = Path(path_value)
    if p.is_absolute():
        return p
    candidate = repo_root / p
    if candidate.exists() or base_dir is None:
        return candidate
    return base_dir / p


def _load_diagnostic(report_diag: JsonDict, repo_root: Path) -> Tuple[JsonDict, Path]:
    diag_path_value = report_diag.get("diagnostic_path")
    if not diag_path_value:
        return report_diag, repo_root
    diag_path = _resolve(str(diag_path_value), repo_root)
    if diag_path and diag_path.exists():
        diagnostic = read_json(diag_path)
        # The top-level morning proof report carries normalized track decision
        # receipts. Older/raw diagnostic.json files keep the lower-level
        # perception_gate array instead. Preserve the report-normalized rows
        # because they include receipt paths and evidence summaries.
        for key in (
            "track_decision_receipts",
            "window",
            "diagnostic_path",
            "overlay_sheet_path",
            "overlay_video_path",
        ):
            if key in report_diag and not diagnostic.get(key):
                diagnostic[key] = report_diag[key]
        return diagnostic, diag_path.parent
    return report_diag, repo_root


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _evidence(track: JsonDict) -> JsonDict:
    return dict(track.get("evidence_summary") or {})


def ranking_features(track: JsonDict) -> JsonDict:
    ev = _evidence(track)
    source_frames = int(_num(ev.get("source_frames")))
    output_frames = int(_num(ev.get("output_frames")))
    max_displacement = _num(ev.get("max_displacement"))
    flow_coherence = _num(ev.get("flow_coherence"))
    static_stack_overlap_ratio = _num(ev.get("static_stack_overlap_ratio"))
    outside_person_ratio = _num(ev.get("outside_person_ratio"))
    single_frame = (source_frames + output_frames) <= 1
    source_output_presence = source_frames > 0 and output_frames > 0
    source_temporal_strength = min(source_frames, 40) / 40.0
    output_temporal_strength = min(output_frames, 5) / 5.0
    displacement_strength = min(max_displacement, 650.0) / 650.0
    flow_strength = max(0.0, min(flow_coherence, 1.0))
    non_static_strength = max(0.0, 1.0 - min(static_stack_overlap_ratio, 1.0))

    score = 0.0
    score += 3.0 if source_output_presence else 0.0
    score += 2.0 * source_temporal_strength
    score += 1.5 * output_temporal_strength
    score += 2.0 * displacement_strength
    score += 1.5 * flow_strength
    score += 1.0 * non_static_strength
    score += 0.5 * outside_person_ratio
    if single_frame:
        score -= 3.0
    if static_stack_overlap_ratio >= 0.5:
        score -= 2.0
    if source_frames <= 0:
        score -= 2.0

    return {
        "score": round(score, 6),
        "source_frames": source_frames,
        "output_frames": output_frames,
        "max_displacement": round(max_displacement, 6),
        "flow_coherence": round(flow_coherence, 6),
        "person_overlap_ratio": round(_num(ev.get("person_overlap_ratio")), 6),
        "outside_person_ratio": round(outside_person_ratio, 6),
        "static_stack_overlap_ratio": round(static_stack_overlap_ratio, 6),
        "source_output_presence": source_output_presence,
        "single_frame_penalty": single_frame,
    }


def _packet_paths(track: JsonDict, repo_root: Path, base_dir: Path) -> Tuple[Path, Path]:
    receipt_json = _resolve(track.get("receipt_json_path"), repo_root, base_dir)
    if receipt_json is not None:
        stem = receipt_json.with_suffix("")
        return Path(str(stem) + "-transfer-packet.json"), Path(str(stem) + "-transfer-packet.jpg")
    track_id = int(track.get("track_id", 0))
    packet_dir = base_dir / "track_receipts"
    return packet_dir / f"track-{track_id:06d}-transfer-packet.json", packet_dir / f"track-{track_id:06d}-transfer-packet.jpg"


def _review_template() -> JsonDict:
    return {
        "reviewer": "",
        "discrete_panel_visible": None,
        "separable_from_worker": None,
        "source_origin_supported": None,
        "output_entry_supported": None,
        "should_mint_source_token": None,
        "should_increment_count": None,
        "evidence_frame_indices": [],
        "notes": "",
    }


def make_packet(track: JsonDict, diagnostic: JsonDict, repo_root: Path, base_dir: Path) -> JsonDict:
    features = ranking_features(track)
    packet_json_path, packet_image_path = _packet_paths(track, repo_root, base_dir)
    window = diagnostic.get("window", {})
    assets = {
        "diagnostic_path": diagnostic.get("diagnostic_path"),
        "overlay_sheet_path": diagnostic.get("overlay_sheet_path"),
        "overlay_video_path": diagnostic.get("overlay_video_path"),
        "receipt_json_path": track.get("receipt_json_path"),
        "receipt_card_path": track.get("receipt_card_path"),
        "raw_crop_paths": list(track.get("raw_crop_paths") or []),
        "transfer_packet_json_path": _repo_rel(packet_json_path, repo_root),
        "transfer_packet_image_path": _repo_rel(packet_image_path, repo_root),
    }
    return {
        "schema_version": PACKET_SCHEMA_VERSION,
        "track_id": track.get("track_id"),
        "window": window,
        "decision": track.get("decision"),
        "reason": track.get("reason"),
        "failure_link": track.get("failure_link"),
        "worker_overlap_detail": track.get("worker_overlap_detail"),
        "flags": list(track.get("flags") or []),
        "ranking_features": features,
        "priority_score": features["score"],
        "assets": assets,
        "review_question": (
            "Does this temporal packet prove a discrete carried wire-mesh panel "
            "separate from worker/body/static-stack ambiguity, with source-to-output context?"
        ),
        "review_label_template": _review_template(),
        "evidence_requirements": [
            "visible panel evidence persists across multiple sampled frames",
            "panel evidence is separable from worker body/arms/clothing, preferably outside person silhouette/mask",
            "source/transfer origin is supported before output evidence",
            "output entry or settle/disappearance evidence exists before any count increment",
            "static-stack/resident/reposition suppressors still pass",
        ],
    }


def _copy_packet_image(packet: JsonDict, repo_root: Path, force: bool) -> None:
    image_rel = packet["assets"].get("transfer_packet_image_path")
    if not image_rel:
        return
    dest = repo_root / image_rel
    if dest.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {dest}; pass --force")
    receipt_card_path = _resolve(packet["assets"].get("receipt_card_path"), repo_root)
    if receipt_card_path and receipt_card_path.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(receipt_card_path, dest)


def iter_candidate_tracks(report: JsonDict, repo_root: Path) -> Iterable[Tuple[JsonDict, JsonDict, Path]]:
    for report_diag in report.get("diagnostics") or []:
        diagnostic, base_dir = _load_diagnostic(report_diag, repo_root)
        for track in diagnostic.get("track_decision_receipts") or []:
            yield track, diagnostic, base_dir


def build_transfer_review_packets(
    proof_report: PathLike = DEFAULT_PROOF_REPORT,
    output: PathLike = DEFAULT_OUTPUT,
    *,
    repo_root: PathLike = Path("."),
    limit: int = 10,
    force: bool = False,
) -> JsonDict:
    repo_root = Path(repo_root)
    proof_report_path = Path(proof_report)
    output_path = Path(output)
    if not proof_report_path.is_absolute():
        proof_report_path = repo_root / proof_report_path
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    if output_path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {output_path}; pass --force")

    report = read_json(proof_report_path)
    packets: List[JsonDict] = []
    for track, diagnostic, base_dir in iter_candidate_tracks(report, repo_root):
        packets.append(make_packet(track, diagnostic, repo_root, base_dir))

    packets.sort(key=lambda p: p["priority_score"], reverse=True)
    if limit and limit > 0:
        packets = packets[:limit]

    result = {
        "schema_version": SCHEMA_VERSION,
        "proof_report": _repo_rel(proof_report_path, repo_root),
        "packet_count": len(packets),
        "ranking_rule": (
            "Prioritize source/output continuity, source/output frame counts, displacement, "
            "flow coherence, and non-static evidence; penalize single-frame/output-only/static-stack candidates."
        ),
        "packets": packets,
    }

    for packet in packets:
        packet_json_path = repo_root / packet["assets"]["transfer_packet_json_path"]
        write_json(packet_json_path, packet, force=force)
        _copy_packet_image(packet, repo_root, force=force)
    write_json(output_path, result, force=force)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-report", type=Path, default=DEFAULT_PROOF_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    result = build_transfer_review_packets(
        args.proof_report,
        args.output,
        repo_root=repo_root,
        limit=args.limit,
        force=args.force,
    )
    print(json.dumps({"packet_count": result["packet_count"], "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
