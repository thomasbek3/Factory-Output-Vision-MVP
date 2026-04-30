#!/usr/bin/env python3
"""Capture observed count events from the live app diagnostics payload."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

SCHEMA_VERSION = "factory2-app-observed-events-v1"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda item: (float(item.get("event_ts") or 0.0), int(item.get("runtime_total_after_event") or 0)))


def write_observed_events_report(
    *,
    diagnostics_payload: dict[str, Any],
    output_path: Path,
    metadata: dict[str, Any],
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    events = _sort_events(list(diagnostics_payload.get("recent_count_events") or []))
    coverage_end_sec = diagnostics_payload.get("reader_last_source_timestamp_sec")
    event_end_sec = events[-1].get("event_ts") if events else None
    if coverage_end_sec is None:
        coverage_end_sec = event_end_sec
    elif event_end_sec is not None:
        coverage_end_sec = max(float(coverage_end_sec), float(event_end_sec))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": round(time.time(), 3),
        "observed_event_count": len(events),
        "current_state": diagnostics_payload.get("current_state"),
        "run_complete": bool(diagnostics_payload.get("demo_playback_finished") or diagnostics_payload.get("current_state") == "DEMO_COMPLETE"),
        "observed_coverage_end_sec": None if coverage_end_sec is None else round(float(coverage_end_sec), 3),
        "reader_last_sequence_index": int(diagnostics_payload.get("reader_last_sequence_index") or 0),
        "reader_last_source_timestamp_sec": None
        if diagnostics_payload.get("reader_last_source_timestamp_sec") is None
        else round(float(diagnostics_payload.get("reader_last_source_timestamp_sec")), 3),
        "metadata": metadata,
        "events": events,
    }
    _write_json(output_path, payload)
    return payload


def _read_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def capture_app_run_events(
    *,
    base_url: str,
    output_path: Path,
    poll_interval_sec: float,
    max_wait_sec: float,
    auto_start: bool,
    force: bool,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    if auto_start:
        with urlopen(Request(f"{base}/api/control/monitor/start", method="POST"), timeout=30) as response:  # noqa: S310
            response.read()

    started = time.time()
    last_payload: dict[str, Any] | None = None
    while True:
        diagnostics = _read_json(f"{base}/api/diagnostics/sysinfo")
        last_payload = diagnostics
        if diagnostics.get("current_state") == "DEMO_COMPLETE":
            break
        if time.time() - started >= max_wait_sec:
            break
        time.sleep(poll_interval_sec)

    if last_payload is None:
        raise RuntimeError("Unable to read diagnostics payload")

    return write_observed_events_report(
        diagnostics_payload=last_payload,
        output_path=output_path,
        metadata={
            "base_url": base,
            "auto_start": auto_start,
            "poll_interval_sec": poll_interval_sec,
            "max_wait_sec": max_wait_sec,
        },
        force=force,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture observed factory2 app run events from diagnostics")
    parser.add_argument("--base-url", default="http://127.0.0.1:8091")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--poll-interval-sec", type=float, default=5.0)
    parser.add_argument("--max-wait-sec", type=float, default=1800.0)
    parser.add_argument("--auto-start", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = capture_app_run_events(
        base_url=args.base_url,
        output_path=args.output,
        poll_interval_sec=args.poll_interval_sec,
        max_wait_sec=args.max_wait_sec,
        auto_start=args.auto_start,
        force=args.force,
    )
    print(json.dumps({"output": str(args.output), "observed_event_count": payload["observed_event_count"], "state": payload["current_state"]}))


if __name__ == "__main__":
    main()
