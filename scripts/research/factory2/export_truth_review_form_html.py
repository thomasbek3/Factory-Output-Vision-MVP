#!/usr/bin/env python3
"""Export an interactive local HTML form for human truth review worksheets."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path
from typing import Any


REQUIRED_WORKSHEET_COLUMNS = {
    "candidate_id",
    "draft_center_ts_sec",
    "window_start_sec",
    "window_end_sec",
    "motion_score",
    "contact_strip_path",
    "human_decision_accept_countable",
    "exact_event_ts",
    "truth_event_id_if_accepted",
    "count_total_if_accepted",
    "reviewer",
    "review_notes",
}
EXPORT_COLUMNS = [
    "candidate_id",
    "draft_center_ts_sec",
    "window_start_sec",
    "window_end_sec",
    "motion_score",
    "contact_strip_path",
    "human_decision_accept_countable",
    "exact_event_ts",
    "truth_event_id_if_accepted",
    "count_total_if_accepted",
    "reviewer",
    "review_notes",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_WORKSHEET_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(sorted(missing))}")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _asset_src(raw_path: str, *, output_path: Path) -> str:
    candidate = Path(raw_path)
    absolute = candidate if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    return os.path.relpath(absolute, start=output_path.parent.resolve()).replace(os.sep, "/")


def _option(value: str, label: str, selected: str) -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(label)}</option>'


def _input(name: str, value: str, *, placeholder: str = "", input_type: str = "text") -> str:
    return (
        f'<input data-field="{html.escape(name)}" type="{html.escape(input_type)}" '
        f'value="{html.escape(value)}" placeholder="{html.escape(placeholder)}">'
    )


def _card(row: dict[str, str], *, output_path: Path) -> str:
    candidate_id = row["candidate_id"]
    src = _asset_src(row["contact_strip_path"], output_path=output_path)
    decision = row["human_decision_accept_countable"].strip().lower()
    options = "\n".join(
        [
            _option("", "Pending", decision),
            _option("yes", "Accept countable", decision),
            _option("no", "Reject", decision),
        ]
    )
    return f"""
    <article class="card" data-candidate-id="{html.escape(candidate_id)}">
      <div class="card-head">
        <div>
          <strong>{html.escape(candidate_id)}</strong>
          <span>{html.escape(row['window_start_sec'])}s - {html.escape(row['window_end_sec'])}s</span>
        </div>
        <div class="score">draft center {html.escape(row['draft_center_ts_sec'])}s · motion {html.escape(row['motion_score'])}</div>
      </div>
      <a href="{html.escape(src)}"><img src="{html.escape(src)}" alt="{html.escape(candidate_id)} contact strip" loading="lazy"></a>
      <div class="fields">
        <label>Decision <select data-field="human_decision_accept_countable">{options}</select></label>
        <label>Exact timestamp {_input("exact_event_ts", row["exact_event_ts"], placeholder="seconds or MM:SS.s")}</label>
        <label>Truth event id {_input("truth_event_id_if_accepted", row["truth_event_id_if_accepted"], placeholder="optional")}</label>
        <label>Count # {_input("count_total_if_accepted", row["count_total_if_accepted"], placeholder="optional", input_type="number")}</label>
        <label>Reviewer {_input("reviewer", row["reviewer"], placeholder="name")}</label>
        <label class="wide">Notes <textarea data-field="review_notes" placeholder="review notes">{html.escape(row["review_notes"])}</textarea></label>
      </div>
    </article>
    """


def build_html(
    *,
    worksheet_path: Path,
    candidate_windows_path: Path,
    output_path: Path,
    expected_total: int,
) -> str:
    rows = read_csv_rows(worksheet_path)
    candidate_windows = read_json(candidate_windows_path)
    cards = "\n".join(_card(row, output_path=output_path) for row in rows)
    export_columns_json = json.dumps(EXPORT_COLUMNS)
    base_rows_json = json.dumps(
        [{key: row.get(key, "") for key in EXPORT_COLUMNS} for row in rows],
        ensure_ascii=True,
    )
    case_id = str(candidate_windows.get("case_id") or "unknown_case")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IMG_2628 Interactive Truth Review</title>
  <style>
    :root {{
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f4;
      color: #1d2420;
    }}
    body {{ margin: 0; }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: #fff;
      border-bottom: 1px solid #d8ddd5;
      padding: 16px 22px;
    }}
    h1 {{ font-size: 22px; margin: 0 0 8px; letter-spacing: 0; }}
    .meta {{ color: #526057; font-size: 13px; line-height: 1.45; max-width: 1180px; }}
    .warning {{ color: #823700; font-weight: 700; }}
    .toolbar {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 12px; }}
    button {{
      appearance: none;
      border: 1px solid #1f5e44;
      background: #1f5e44;
      color: white;
      border-radius: 6px;
      padding: 8px 12px;
      font: inherit;
      cursor: pointer;
    }}
    .status {{ font-size: 13px; color: #38433d; }}
    main {{ display: grid; gap: 14px; padding: 16px; }}
    .card {{ background: #fff; border: 1px solid #d8ddd5; border-radius: 8px; overflow: hidden; }}
    .card-head {{ display: flex; justify-content: space-between; gap: 12px; padding: 12px 14px; border-bottom: 1px solid #e5e8e2; font-size: 14px; }}
    .card-head span, .score {{ color: #59645c; font-size: 12px; }}
    img {{ width: 100%; display: block; background: #111; }}
    .fields {{ display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 10px; padding: 12px 14px 14px; }}
    label {{ display: grid; gap: 5px; font-size: 12px; color: #4e5a52; }}
    input, select, textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #cbd2ca; border-radius: 6px; padding: 8px; font: inherit; background: #fff; color: #1d2420; }}
    textarea {{ min-height: 38px; resize: vertical; }}
    .wide {{ grid-column: span 2; }}
    @media (max-width: 840px) {{ .fields {{ grid-template-columns: 1fr; }} .wide {{ grid-column: auto; }} .card-head {{ display: block; }} }}
  </style>
</head>
<body>
  <header>
    <h1>IMG_2628 Interactive Truth Review</h1>
    <div class="meta">Case: {html.escape(case_id)} · Candidate rows: {len(rows)} · Expected accepted placements: {expected_total}</div>
    <div class="meta">Worksheet source: {html.escape(worksheet_path.as_posix())}</div>
    <div class="meta warning">Human review aid only. Exported CSV is not validation truth until a reviewer fills decisions/timestamps and the ledger builder accepts exactly {expected_total} events.</div>
    <div class="toolbar">
      <button type="button" id="exportCsv">Export worksheet CSV</button>
      <span class="status" id="statusText"></span>
    </div>
  </header>
  <main>
    {cards}
  </main>
  <script>
    const exportColumns = {export_columns_json};
    const baseRows = {base_rows_json};
    function csvEscape(value) {{
      const text = String(value ?? "");
      if (/[",\\n\\r]/.test(text)) {{
        return '"' + text.replaceAll('"', '""') + '"';
      }}
      return text;
    }}
    function collectRows() {{
      return [...document.querySelectorAll(".card")].map((card, index) => {{
        const row = {{...baseRows[index]}};
        card.querySelectorAll("[data-field]").forEach((field) => {{
          row[field.dataset.field] = field.value;
        }});
        return row;
      }});
    }}
    function updateStatus() {{
      const rows = collectRows();
      const accepted = rows.filter((row) => row.human_decision_accept_countable === "yes").length;
      const rejected = rows.filter((row) => row.human_decision_accept_countable === "no").length;
      const pending = rows.length - accepted - rejected;
      const acceptedWithTs = rows.filter((row) => row.human_decision_accept_countable === "yes" && row.exact_event_ts.trim()).length;
      document.getElementById("statusText").textContent = `accepted ${{accepted}} / rejected ${{rejected}} / pending ${{pending}} / accepted timestamps ${{acceptedWithTs}}`;
    }}
    function exportCsv() {{
      const rows = collectRows();
      const csv = [exportColumns.join(",")]
        .concat(rows.map((row) => exportColumns.map((column) => csvEscape(row[column])).join(",")))
        .join("\\n") + "\\n";
      const blob = new Blob([csv], {{type: "text/csv;charset=utf-8"}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "img2628_human_truth_review_worksheet.cv_motion_draft_v1.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }}
    document.getElementById("exportCsv").addEventListener("click", exportCsv);
    document.querySelectorAll("[data-field]").forEach((field) => field.addEventListener("input", updateStatus));
    updateStatus();
  </script>
</body>
</html>
"""


def write_text(path: Path, text: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export an interactive local HTML truth-review form")
    parser.add_argument("--worksheet", type=Path, required=True)
    parser.add_argument("--candidate-windows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-total", type=int, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        html_text = build_html(
            worksheet_path=args.worksheet,
            candidate_windows_path=args.candidate_windows,
            output_path=args.output,
            expected_total=args.expected_total,
        )
        write_text(args.output, html_text, force=args.force)
    except (FileExistsError, ValueError) as exc:
        print(f"error: {exc}")
        return 1
    print(json.dumps({"output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
