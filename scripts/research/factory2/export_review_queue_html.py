#!/usr/bin/env python3
"""Export a static HTML contact sheet for a review queue."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _asset_src(frame_path: str | None, *, queue_path: Path, output_path: Path) -> str:
    if not frame_path:
        return ""
    raw_path = Path(frame_path)
    if raw_path.is_absolute():
        absolute = raw_path
    else:
        queue_relative = (queue_path.parent / raw_path).resolve()
        cwd_relative = raw_path.resolve()
        absolute = queue_relative if queue_relative.exists() else cwd_relative
    relative = os.path.relpath(absolute, start=output_path.parent.resolve())
    return relative.replace(os.sep, "/")


def _chip(label: str, value: Any) -> str:
    return f'<span class="chip"><span>{html.escape(label)}</span>{html.escape(_display(value))}</span>'


def _entry_card(entry: dict[str, Any], *, queue_path: Path, output_path: Path) -> str:
    primary = entry.get("primary_frame_asset") or {}
    src = _asset_src(primary.get("frame_path"), queue_path=queue_path, output_path=output_path)
    alt = f"Review frame for {entry.get('window_id')}"
    reasons = entry.get("review_reasons") or []
    time_window = entry.get("time_window") or {}
    center_sec = time_window.get("center_sec")
    count_event = entry.get("count_event_evidence") or {}
    runtime_total = count_event.get("runtime_total_after_event")
    image_html = (
        f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" loading="lazy">'
        if src
        else '<div class="missing-frame">No frame</div>'
    )
    reason_html = "".join(f"<li>{html.escape(str(reason))}</li>" for reason in reasons)
    frame_links = []
    for asset in entry.get("frame_assets") or []:
        asset_src = _asset_src(asset.get("frame_path"), queue_path=queue_path, output_path=output_path)
        timestamp = _display(asset.get("timestamp_sec"))
        if asset_src:
            frame_links.append(
                f'<a href="{html.escape(asset_src)}">{html.escape(timestamp or "frame")}</a>'
            )
    frame_links_html = " ".join(frame_links)
    return f"""
    <article class="card {html.escape(str(entry.get('priority_bucket') or 'routine_review'))}">
      <div class="media">{image_html}</div>
      <div class="body">
        <div class="rank">#{html.escape(_display(entry.get('rank')))} · {html.escape(str(entry.get('window_id') or ''))}</div>
        <h2>{html.escape(str(entry.get('priority_bucket') or 'review'))}</h2>
        <div class="chips">
          {_chip("status", entry.get("teacher_output_status"))}
          {_chip("confidence", entry.get("confidence_tier"))}
          {_chip("duplicate", entry.get("duplicate_risk"))}
          {_chip("miss", entry.get("miss_risk"))}
          {_chip("use", entry.get("candidate_use"))}
          {_chip("t", center_sec)}
          {_chip("runtime", runtime_total)}
        </div>
        <p class="rationale">{html.escape(str(entry.get('rationale') or ''))}</p>
        <ul class="reasons">{reason_html}</ul>
        <div class="frames">{frame_links_html}</div>
        <div class="review-line">
          <label><input type="checkbox"> reviewed</label>
          <label>decision <select><option></option><option>countable</option><option>worker_only</option><option>static_stack</option><option>unclear</option></select></label>
        </div>
      </div>
    </article>
    """


def build_review_queue_html(*, queue_path: Path, output_path: Path) -> str:
    payload = read_json(queue_path)
    entries = list(payload.get("queue") or [])
    counts: dict[str, int] = {}
    for entry in entries:
        bucket = str(entry.get("priority_bucket") or "unknown")
        counts[bucket] = counts.get(bucket, 0) + 1
    cards = "\n".join(_entry_card(entry, queue_path=queue_path, output_path=output_path) for entry in entries)
    summary = " · ".join(f"{html.escape(bucket)}: {count}" for bucket, count in sorted(counts.items()))
    case_id = html.escape(str(payload.get("case_id") or "unknown_case"))
    provider = payload.get("provider") or {}
    provider_text = " / ".join(
        part for part in [str(provider.get("name") or ""), str(provider.get("model") or "")] if part
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Factory Vision Review Queue · {case_id}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f8f5;
      color: #1c211d;
    }}
    body {{ margin: 0; }}
    header {{
      padding: 24px 28px 18px;
      background: #ffffff;
      border-bottom: 1px solid #d9ded7;
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    h1 {{ font-size: 22px; margin: 0 0 8px; letter-spacing: 0; }}
    .meta, .warning {{ font-size: 13px; line-height: 1.45; color: #4f5a52; }}
    .warning {{ margin-top: 8px; color: #7a3f00; font-weight: 650; }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 16px;
      padding: 18px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #d8ddd5;
      border-radius: 8px;
      overflow: hidden;
      display: grid;
      grid-template-rows: auto 1fr;
      min-width: 0;
    }}
    .card.review_first {{ border-top: 4px solid #a94421; }}
    .card.hard_negative_review {{ border-top: 4px solid #246b58; }}
    .media {{ aspect-ratio: 16 / 9; background: #111; display: flex; align-items: center; justify-content: center; }}
    img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
    .missing-frame {{ color: #fff; font-size: 14px; }}
    .body {{ padding: 14px; min-width: 0; }}
    .rank {{ font-size: 12px; color: #687269; margin-bottom: 6px; overflow-wrap: anywhere; }}
    h2 {{ font-size: 17px; margin: 0 0 10px; letter-spacing: 0; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
    .chip {{ border: 1px solid #d7ddd5; border-radius: 999px; padding: 4px 8px; font-size: 12px; background: #f7f8f5; }}
    .chip span {{ color: #667064; margin-right: 4px; }}
    .rationale {{ font-size: 13px; line-height: 1.45; margin: 8px 0; overflow-wrap: anywhere; }}
    .reasons {{ margin: 8px 0; padding-left: 18px; font-size: 12px; color: #526056; }}
    .frames {{ display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; margin-top: 10px; }}
    .frames a {{ color: #165c8a; }}
    .review-line {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 12px; font-size: 13px; }}
    select {{ font: inherit; max-width: 160px; }}
  </style>
</head>
<body>
  <header>
    <h1>Factory Vision Review Queue</h1>
    <div class="meta">Case: {case_id} · Entries: {len(entries)} · {summary}</div>
    <div class="meta">Provider: {html.escape(provider_text or "unknown")} · Queue: {html.escape(queue_path.as_posix())}</div>
    <div class="warning">Advisory only. This page is not validation truth and does not make labels training eligible.</div>
  </header>
  <main>
    {cards}
  </main>
</body>
</html>
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a static HTML contact sheet for a review queue")
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    html_text = build_review_queue_html(queue_path=args.queue, output_path=args.output)
    write_text(args.output, html_text, force=args.force)
    print(json.dumps({"output": args.output.as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
