#!/usr/bin/env python3
"""Adjudicate Factory2's final runtime-only events at the chain/source-authority level."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory2-final-two-chain-adjudication-v1"
REVIEW_SCHEMA = "factory2-divergent-chain-review-v1"
RESCUE_SCHEMA = "factory2-final-two-rescue-dataset-v1"
DEFAULT_REVIEW_REPORT = Path("data/reports/factory2_divergent_chain_review.v1.json")
DEFAULT_RESCUE_REPORT = Path("data/reports/factory2_final_two_rescue_dataset.v1.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_final_two_chain_adjudication.v1.json")
DEFAULT_PACKAGE_DIR = Path("data/datasets/factory2_final_two_chain_adjudication_v1")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_review_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = {}
        for row in reader:
            item_id = str(row.get("item_id") or "").strip()
            if item_id:
                rows[item_id] = dict(row)
        return rows


def _resolve_review_labels_csv(
    review_report: dict[str, Any],
    review_report_path: Path,
    review_labels_csv_path: Path | None,
) -> Path:
    if review_labels_csv_path is not None:
        return review_labels_csv_path
    csv_path = Path(str(review_report.get("review_labels_csv_path") or ""))
    if csv_path.is_absolute():
        return csv_path
    if csv_path.exists():
        return csv_path.resolve()
    return (review_report_path.parent / csv_path).resolve()


def _track_label_index(
    *,
    review_items: list[dict[str, Any]],
    review_rows: dict[str, dict[str, str]],
) -> dict[str, dict[int, dict[str, Any]]]:
    per_track: dict[str, dict[int, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    notes: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    roles: dict[str, dict[int, str]] = defaultdict(dict)
    classes: dict[str, dict[int, str]] = defaultdict(dict)
    for item in review_items:
        item_id = str(item.get("item_id") or "")
        review_row = review_rows.get(item_id)
        if review_row is None:
            raise ValueError(f"Missing review_labels row for item_id {item_id}")
        crop_label = str(review_row.get("crop_label") or "").strip()
        relation_label = str(review_row.get("relation_label") or "").strip()
        if crop_label != "carried_panel" or not relation_label:
            continue
        event_id = str(item.get("event_id") or "")
        track_id = int(item.get("track_id") or 0)
        per_track[event_id][track_id][relation_label] += 1
        note = str(review_row.get("notes") or "").strip()
        if note:
            notes[event_id][track_id].append(note)
        roles[event_id][track_id] = str(item.get("track_role") or "")
        classes[event_id][track_id] = str(item.get("track_class") or "")

    result: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for event_id, tracks in per_track.items():
        for track_id, counter in tracks.items():
            unique_labels = [label for label in sorted(counter) if label]
            resolved_label = unique_labels[0] if len(unique_labels) == 1 else "mixed"
            result[event_id][track_id] = {
                "resolved_relation_label": resolved_label,
                "relation_label_counts": {label: counter[label] for label in sorted(counter)},
                "notes": notes[event_id][track_id],
                "track_role": roles[event_id].get(track_id),
                "track_class": classes[event_id].get(track_id),
            }
    return result


def _source_track_ids(event: dict[str, Any], *, prior_track_id: int | None, runtime_track_id: int) -> list[int]:
    values = []
    for row in as_list(event.get("track_summaries")):
        if not isinstance(row, dict):
            continue
        track_id = int(row.get("track_id") or 0)
        if track_id in {0, runtime_track_id, prior_track_id or -1}:
            continue
        if int(row.get("source_frames") or 0) > 0:
            values.append(track_id)
    return sorted(set(values))


def _output_context_track_ids(event: dict[str, Any], *, prior_track_id: int | None, runtime_track_id: int) -> list[int]:
    values = []
    for row in as_list(event.get("track_summaries")):
        if not isinstance(row, dict):
            continue
        track_id = int(row.get("track_id") or 0)
        if track_id in {0, prior_track_id or -1}:
            continue
        if int(row.get("output_frames") or 0) > 0:
            values.append(track_id)
    if runtime_track_id not in values:
        values.append(runtime_track_id)
    return sorted(set(values))


def _track_ids_with_label(track_index: dict[int, dict[str, Any]], label: str) -> list[int]:
    return sorted(track_id for track_id, row in track_index.items() if row.get("resolved_relation_label") == label)


def _adjudicate_event(event: dict[str, Any], track_index: dict[int, dict[str, Any]]) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "")
    event_ts = round(float(event.get("event_ts") or 0.0), 3)
    runtime_track_id = int(event.get("runtime_track_id") or 0)
    source_track_id = int(event["source_track_id"]) if event.get("source_track_id") is not None else None
    prior_event = event.get("prior_runtime_event") or {}
    prior_track_id = int(prior_event["track_id"]) if prior_event.get("track_id") is not None else None
    prior_event_ts = round(float(prior_event.get("event_ts") or 0.0), 3) if prior_event.get("event_ts") is not None else None

    runtime_track_row = track_index.get(runtime_track_id, {})
    source_track_row = track_index.get(source_track_id, {}) if source_track_id is not None else {}
    divergent_track_relation_label = str(runtime_track_row.get("resolved_relation_label") or "unlabeled")
    source_track_relation_label = str(source_track_row.get("resolved_relation_label") or "unlabeled")
    same_delivery_track_ids = _track_ids_with_label(track_index, "same_delivery_as_prior")
    distinct_new_delivery_track_ids = _track_ids_with_label(track_index, "distinct_new_delivery")
    static_resident_track_ids = _track_ids_with_label(track_index, "static_resident")
    mixed_relation_track_ids = _track_ids_with_label(track_index, "mixed")

    candidate_source_track_ids = _source_track_ids(
        event,
        prior_track_id=prior_track_id,
        runtime_track_id=runtime_track_id,
    )
    candidate_output_context_track_ids = _output_context_track_ids(
        event,
        prior_track_id=prior_track_id,
        runtime_track_id=runtime_track_id,
    )

    adjudication = "unresolved"
    proof_action = "do_not_mint"
    runtime_action = "leave_runtime_inferred_only"
    duplicate_of_event_ts = None
    countable = False
    source_authority_status = "unknown"
    blocking_reason = ""

    if divergent_track_relation_label == "same_delivery_as_prior" and prior_event_ts is not None:
        adjudication = "duplicate_of_prior_runtime_event"
        runtime_action = "suppress_or_mark_duplicate"
        duplicate_of_event_ts = prior_event_ts
        source_authority_status = "already_consumed_or_not_fresh"
        blocking_reason = (
            f"divergent runtime track {runtime_track_id} is labeled same_delivery_as_prior "
            f"relative to prior event {prior_event_ts:.3f}s"
        )
    elif divergent_track_relation_label == "static_resident":
        adjudication = "static_resident"
        runtime_action = "suppress_or_mark_static"
        source_authority_status = "no_fresh_source_authority"
        blocking_reason = f"divergent runtime track {runtime_track_id} is labeled static_resident"
    elif divergent_track_relation_label == "distinct_new_delivery":
        source_is_consumed = False
        if source_track_id is None:
            source_authority_status = "missing_source_anchor"
            blocking_reason = "no source_track_id recorded for divergent runtime event"
        elif prior_track_id is not None and source_track_id == prior_track_id:
            source_is_consumed = True
            source_authority_status = "already_consumed_or_not_fresh"
            blocking_reason = f"source_track_id {source_track_id} already belongs to prior runtime event {prior_event_ts:.3f}s"
        elif source_track_relation_label == "same_delivery_as_prior":
            source_is_consumed = True
            source_authority_status = "already_consumed_or_not_fresh"
            blocking_reason = f"source_track_id {source_track_id} is labeled same_delivery_as_prior"
        elif source_track_relation_label == "static_resident":
            source_authority_status = "invalid_static_source"
            blocking_reason = f"source_track_id {source_track_id} is labeled static_resident"
        elif source_track_relation_label in {"distinct_new_delivery", "unlabeled"}:
            adjudication = "source_backed_new_candidate"
            proof_action = "candidate_reserve_fresh_source"
            runtime_action = "leave_runtime_inferred_only"
            source_authority_status = "candidate_fresh_source_needs_reservation"
            blocking_reason = (
                f"divergent runtime track {runtime_track_id} is labeled distinct_new_delivery; "
                f"fresh source reservation still required"
            )
            countable = True
        else:
            source_authority_status = "unknown"
            blocking_reason = f"unsupported source_track relation label {source_track_relation_label!r}"

        if source_is_consumed:
            adjudication = "source_authority_blocked"
            countable = False
    else:
        source_authority_status = "insufficient_relation_evidence"
        blocking_reason = (
            f"divergent runtime track {runtime_track_id} has unresolved relation label "
            f"{divergent_track_relation_label!r}"
        )

    return {
        "event_id": event_id,
        "event_ts": event_ts,
        "runtime_track_id": runtime_track_id,
        "source_track_id": source_track_id,
        "prior_runtime_event_ts": prior_event_ts,
        "prior_runtime_track_id": prior_track_id,
        "candidate_source_track_ids": candidate_source_track_ids,
        "candidate_output_context_track_ids": candidate_output_context_track_ids,
        "divergent_track_relation_label": divergent_track_relation_label,
        "source_track_relation_label": source_track_relation_label,
        "same_delivery_track_ids": same_delivery_track_ids,
        "distinct_new_delivery_track_ids": distinct_new_delivery_track_ids,
        "static_resident_track_ids": static_resident_track_ids,
        "mixed_relation_track_ids": mixed_relation_track_ids,
        "adjudication": adjudication,
        "human_relation_vote": divergent_track_relation_label,
        "proof_action": proof_action,
        "runtime_action": runtime_action,
        "duplicate_of_event_ts": duplicate_of_event_ts,
        "source_authority_status": source_authority_status,
        "countable": countable,
        "blocking_reason": blocking_reason,
    }


def _write_adjudication_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "event_id",
        "event_ts",
        "runtime_track_id",
        "source_track_id",
        "prior_runtime_event_ts",
        "prior_runtime_track_id",
        "divergent_track_relation_label",
        "source_track_relation_label",
        "human_relation_vote",
        "adjudication",
        "proof_action",
        "runtime_action",
        "duplicate_of_event_ts",
        "source_authority_status",
        "countable",
        "candidate_source_track_ids",
        "candidate_output_context_track_ids",
        "distinct_new_delivery_track_ids",
        "same_delivery_track_ids",
        "static_resident_track_ids",
        "mixed_relation_track_ids",
        "blocking_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "candidate_source_track_ids": ",".join(str(value) for value in row.get("candidate_source_track_ids") or []),
                    "candidate_output_context_track_ids": ",".join(
                        str(value) for value in row.get("candidate_output_context_track_ids") or []
                    ),
                    "distinct_new_delivery_track_ids": ",".join(
                        str(value) for value in row.get("distinct_new_delivery_track_ids") or []
                    ),
                    "same_delivery_track_ids": ",".join(str(value) for value in row.get("same_delivery_track_ids") or []),
                    "static_resident_track_ids": ",".join(
                        str(value) for value in row.get("static_resident_track_ids") or []
                    ),
                }
            )


def _write_evidence_pairs_csv(
    path: Path,
    *,
    review_items: list[dict[str, Any]],
    review_rows: dict[str, dict[str, str]],
    event_rows: dict[str, dict[str, Any]],
) -> None:
    fieldnames = [
        "event_id",
        "event_ts",
        "runtime_track_id",
        "item_id",
        "track_id",
        "track_role",
        "track_class",
        "relation_label",
        "crop_label",
        "notes",
        "event_adjudication",
        "event_proof_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in sorted(
            review_items,
            key=lambda row: (
                str(row.get("event_id") or ""),
                int(row.get("track_id") or 0),
                str(row.get("item_id") or ""),
            ),
        ):
            item_id = str(item.get("item_id") or "")
            review_row = review_rows.get(item_id, {})
            event_id = str(item.get("event_id") or "")
            event_row = event_rows[event_id]
            writer.writerow(
                {
                    "event_id": event_id,
                    "event_ts": event_row.get("event_ts"),
                    "runtime_track_id": event_row.get("runtime_track_id"),
                    "item_id": item_id,
                    "track_id": item.get("track_id"),
                    "track_role": item.get("track_role"),
                    "track_class": item.get("track_class"),
                    "relation_label": review_row.get("relation_label"),
                    "crop_label": review_row.get("crop_label"),
                    "notes": review_row.get("notes"),
                    "event_adjudication": event_row.get("adjudication"),
                    "event_proof_action": event_row.get("proof_action"),
                }
            )


def build_final_two_chain_adjudication(
    *,
    review_report_path: Path,
    rescue_report_path: Path,
    output_report_path: Path,
    package_dir: Path,
    review_labels_csv_path: Path | None,
    force: bool,
) -> dict[str, Any]:
    if output_report_path.exists() and not force:
        raise FileExistsError(output_report_path)
    if package_dir.exists():
        if not force:
            raise FileExistsError(package_dir)
        shutil.rmtree(package_dir)

    review_report = load_json(review_report_path)
    if review_report.get("schema_version") != REVIEW_SCHEMA:
        raise ValueError(f"Expected {REVIEW_SCHEMA} review report")
    rescue_report = load_json(rescue_report_path)
    if rescue_report.get("schema_version") != RESCUE_SCHEMA:
        raise ValueError(f"Expected {RESCUE_SCHEMA} rescue report")

    resolved_review_csv = _resolve_review_labels_csv(review_report, review_report_path, review_labels_csv_path)
    review_rows = _load_review_rows(resolved_review_csv)
    review_items = [item for item in as_list(review_report.get("items")) if isinstance(item, dict)]
    track_index = _track_label_index(review_items=review_items, review_rows=review_rows)

    event_rows = [
        _adjudicate_event(event, track_index.get(str(event.get("event_id") or ""), {}))
        for event in as_list(review_report.get("events"))
        if isinstance(event, dict)
    ]
    event_rows.sort(key=lambda row: (float(row.get("event_ts") or 0.0), str(row.get("event_id") or "")))

    package_dir.mkdir(parents=True, exist_ok=True)
    adjudication_rows_csv_path = package_dir / "adjudication_rows.csv"
    evidence_pairs_csv_path = package_dir / "evidence_pairs.csv"
    _write_adjudication_rows_csv(adjudication_rows_csv_path, event_rows)
    _write_evidence_pairs_csv(
        evidence_pairs_csv_path,
        review_items=review_items,
        review_rows=review_rows,
        event_rows={row["event_id"]: row for row in event_rows},
    )

    summary_counter = Counter(row["adjudication"] for row in event_rows)
    proof_mints_allowed = sum(1 for row in event_rows if row.get("proof_action") == "candidate_reserve_fresh_source")
    summary = {
        "duplicate_of_prior_runtime_event": summary_counter["duplicate_of_prior_runtime_event"],
        "proof_mints_allowed": proof_mints_allowed,
        "source_authority_blocked": summary_counter["source_authority_blocked"],
        "source_backed_new_candidates": summary_counter["source_backed_new_candidate"],
        "static_resident": summary_counter["static_resident"],
        "unresolved": summary_counter["unresolved"],
    }

    result = {
        "schema_version": SCHEMA_VERSION,
        "input_review_report_path": str(review_report_path),
        "input_rescue_report_path": str(rescue_report_path),
        "input_review_labels_csv_path": str(resolved_review_csv),
        "package_dir": str(package_dir),
        "adjudication_rows_csv_path": str(adjudication_rows_csv_path),
        "evidence_pairs_csv_path": str(evidence_pairs_csv_path),
        "event_count": len(event_rows),
        "events": event_rows,
        "summary": summary,
        "rescue_relation_label_counts": rescue_report.get("relation_label_counts"),
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Factory2 final-two chain/source-authority adjudication report.")
    parser.add_argument("--review-report", type=Path, default=DEFAULT_REVIEW_REPORT)
    parser.add_argument("--rescue-report", type=Path, default=DEFAULT_RESCUE_REPORT)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--review-labels-csv", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_final_two_chain_adjudication(
        review_report_path=args.review_report,
        rescue_report_path=args.rescue_report,
        output_report_path=args.output_report,
        package_dir=args.package_dir,
        review_labels_csv_path=args.review_labels_csv,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
