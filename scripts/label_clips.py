#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PLACEMENT_JUDGE_PROMPT = """You are judging a factory output-pallet clip.
Question: did a worker PLACE a finished wire frame onto the pallet/stack?
Assert only for carry-in, set-down, and worker leaving it there. Refute walk-by,
adjusting the pile, welding flashes, standing near the pallet, or no change.
Use the whole before/during/after sequence. Return JSON only:
{"decision":"assert|refute","confidence":"high|medium|low","note":"evidence"}.
"""

Runner = Callable[..., Any]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Label Day-4 placement clip samples with Codex or human timestamps.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--labeler", choices=["codex", "human"], required=True)
    parser.add_argument("--votes", type=int, default=1)
    parser.add_argument("--times", help="Human placement times as comma-separated seconds or a CSV path.")
    parser.add_argument("--match-tolerance-sec", type=float, default=20.0)
    parser.add_argument("--review-html", type=Path)
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    try:
        guard_no_exam_rows(manifest)
        if args.labeler == "codex":
            labeled = label_manifest_with_codex(manifest, votes=args.votes, work_dir=args.out.parent)
        else:
            if not args.times:
                parser.error("--times is required for --labeler human")
            labeled = label_manifest_with_human_times(
                manifest,
                times_sec=parse_time_list(args.times),
                match_tolerance_sec=args.match_tolerance_sec,
            )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(labeled, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.review_html:
            write_review_html(args.review_html, labeled)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"sample_count": len(labeled.get("samples") or []), "out": str(args.out)}, sort_keys=True))
    return 0


def label_manifest_with_codex(
    manifest: dict[str, Any],
    *,
    votes: int = 1,
    work_dir: Path,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    if votes <= 0:
        raise ValueError("votes must be positive")
    samples = []
    contact_dir = work_dir / "contact_sheets"
    contact_dir.mkdir(parents=True, exist_ok=True)
    for row in manifest.get("samples") or []:
        updated = dict(row)
        sheet_path = render_contact_sheet(row, contact_dir=contact_dir)
        vote_rows = [run_codex_vote(sheet_path=sheet_path, clip_id=str(row.get("candidate_id", "")), runner=runner) for _ in range(votes)]
        decision = majority_decision(vote_rows)
        updated["label"] = decision
        updated["label_source"] = "codex"
        updated["label_votes"] = vote_rows
        samples.append(updated)
    output = dict(manifest)
    output["samples"] = samples
    return output


def label_manifest_with_human_times(
    manifest: dict[str, Any],
    *,
    times_sec: list[float],
    match_tolerance_sec: float,
) -> dict[str, Any]:
    samples = [dict(row) for row in manifest.get("samples") or []]
    matched_indexes: set[int] = set()
    for target in times_sec:
        best_index = None
        best_delta = None
        for index, row in enumerate(samples):
            if index in matched_indexes:
                continue
            delta = float(row.get("center_sec", 0.0)) - target
            if best_delta is None or abs(delta) < abs(best_delta):
                best_index = index
                best_delta = delta
        if best_index is not None and best_delta is not None and abs(best_delta) <= match_tolerance_sec:
            matched_indexes.add(best_index)
    for index, row in enumerate(samples):
        row["label"] = "assert" if index in matched_indexes else "refute"
        row["label_source"] = "human_timestamp"
    output = dict(manifest)
    output["samples"] = samples
    return output


def run_codex_vote(*, sheet_path: Path, clip_id: str, runner: Runner = subprocess.run) -> dict[str, Any]:
    prompt = f"{PLACEMENT_JUDGE_PROMPT}\nClip id: {clip_id}\nContact sheet path: {sheet_path}\n"
    result = runner(
        ["codex", "exec", "--sandbox", "read-only", prompt],
        text=True,
        capture_output=True,
        check=False,
    )
    if getattr(result, "returncode", 0) != 0:
        raise RuntimeError(f"codex exec failed: {getattr(result, 'stderr', '')}")
    return parse_label_output(str(getattr(result, "stdout", "")), clip_id=clip_id)


def parse_label_output(text: str, *, clip_id: str = "") -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"could not parse label JSON for {clip_id}")
    payload = json.loads(match.group(0))
    decision = str(payload.get("decision", "")).lower()
    if decision not in {"assert", "refute"}:
        raise ValueError(f"unsupported label decision for {clip_id}: {decision}")
    confidence = str(payload.get("confidence", "low")).lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return {
        "clip": payload.get("clip", clip_id),
        "decision": decision,
        "confidence": confidence,
        "note": str(payload.get("note", "")),
    }


def majority_decision(votes: list[dict[str, Any]]) -> str:
    counts = Counter(vote["decision"] for vote in votes)
    return "assert" if counts["assert"] > counts["refute"] else "refute"


def render_contact_sheet(row: dict[str, Any], *, contact_dir: Path) -> Path:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("contact sheet rendering requires cv2; use the repo .venv") from exc
    frames = _frames_for_contact_sheet(row)
    sheet = np.concatenate(frames, axis=1)
    path = contact_dir / f"{safe_slug(str(row.get('candidate_id', 'clip')))}.jpg"
    cv2.imwrite(str(path), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    return path


def write_review_html(path: Path, manifest: dict[str, Any]) -> None:
    rows = []
    for sample in manifest.get("samples") or []:
        rows.append(
            "<tr>"
            f"<td>{sample.get('candidate_id')}</td>"
            f"<td>{sample.get('center_sec')}</td>"
            f"<td>{sample.get('label')}</td>"
            f"<td>{sample.get('source')}</td>"
            "</tr>"
        )
    html = "<html><body><table><tr><th>candidate</th><th>center</th><th>label</th><th>source</th></tr>"
    html += "\n".join(rows)
    html += "</table></body></html>\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def parse_time_list(value: str) -> list[float]:
    path = Path(value).expanduser()
    if path.exists():
        rows = []
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames:
                field = "time" if "time" in reader.fieldnames else reader.fieldnames[0]
                for row in reader:
                    rows.append(float(row[field]))
                return rows
        return []
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def guard_no_exam_rows(manifest: dict[str, Any]) -> None:
    for row in manifest.get("samples") or []:
        source = str(row.get("source", ""))
        candidate_id = str(row.get("candidate_id", ""))
        if row.get("training_eligible") is False:
            raise ValueError("refusing to label training-ineligible samples")
        if row.get("exam_only") is True or row.get("source_role") == "exam":
            raise ValueError("refusing to label exam window samples")
        lowered = f"{source} {candidate_id}".lower()
        if "exam_clip" in lowered or "pipeline_day2_full/exam" in lowered:
            raise ValueError("refusing to label exam window samples")


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-") or "clip"


def _frames_for_contact_sheet(row: dict[str, Any]) -> list[np.ndarray]:
    paths = row.get("paths") or {}
    if "stack3" in paths:
        data = np.load(Path(str(paths["stack3"])))["data"]
        return [frame.astype(np.uint8) for frame in data]
    if "clip" in paths:
        data = np.load(Path(str(paths["clip"])))["data"]
        indexes = np.linspace(0, len(data) - 1, num=min(5, len(data))).round().astype(int)
        return [data[int(index)].astype(np.uint8) for index in indexes]
    raise ValueError("sample must include stack3 or clip path for contact sheet")


if __name__ == "__main__":
    raise SystemExit(main())
