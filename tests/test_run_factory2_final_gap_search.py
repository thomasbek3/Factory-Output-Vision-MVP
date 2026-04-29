from __future__ import annotations

import json
from pathlib import Path

from scripts.run_factory2_final_gap_search import run_final_gap_search


def test_run_final_gap_search_writes_candidate_manifest_without_running_vision(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "search.json"
    plan_path.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "baseline_source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                        "candidates": [
                            {
                                "candidate_id": "0007-lead040-tail020-fps080",
                                "event_id": "factory2-runtime-only-0007",
                                "event_ts": 305.708,
                                "start_seconds": 301.708,
                                "end_seconds": 307.708,
                                "fps": 8.0,
                                "lead_seconds": 4.0,
                                "tail_seconds": 2.0,
                                "duration_seconds": 6.0,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    seen: list[dict[str, object]] = []

    def fake_runner(**kwargs):
        seen.append(kwargs)
        out_dir = Path(kwargs["out_dir"])
        return {"diagnostic_path": out_dir / "diagnostic.json"}

    payload = run_final_gap_search(
        plan_path=plan_path,
        output_path=output_path,
        diagnostics_root=tmp_path / "diagnostics",
        video_path=Path("/tmp/factory2.MOV"),
        calibration_path=Path("/tmp/calibration.json"),
        model_path=Path("/tmp/model.pt"),
        person_model_path=Path("/tmp/person.pt"),
        diagnostic_runner=fake_runner,
        candidate_limit_per_event=None,
        event_ids=None,
        force=True,
    )

    assert payload["result_count"] == 1
    assert payload["results"][0]["event_id"] == "factory2-runtime-only-0007"
    assert payload["results"][0]["diagnostic_slug"].startswith("factory2-final-gap-search-0007-")
    assert payload["results"][0]["baseline_source_token_key"] == "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002"
    assert seen[0]["start_timestamp"] == 301.708
    assert seen[0]["fps"] == 8.0
    assert output_path.exists()


def test_run_final_gap_search_honors_event_filter_and_candidate_limit(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "search.json"
    plan_path.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "baseline_source_token_key": "key-7",
                        "candidates": [
                            {"candidate_id": "a", "event_id": "factory2-runtime-only-0007", "event_ts": 305.708, "start_seconds": 301.0, "end_seconds": 307.0, "fps": 5.0},
                            {"candidate_id": "b", "event_id": "factory2-runtime-only-0007", "event_ts": 305.708, "start_seconds": 299.0, "end_seconds": 307.0, "fps": 8.0},
                        ],
                    },
                    {
                        "event_id": "factory2-runtime-only-0008",
                        "event_ts": 425.012,
                        "baseline_source_token_key": "key-8",
                        "candidates": [
                            {"candidate_id": "c", "event_id": "factory2-runtime-only-0008", "event_ts": 425.012, "start_seconds": 421.0, "end_seconds": 427.0, "fps": 5.0}
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_final_gap_search(
        plan_path=plan_path,
        output_path=output_path,
        diagnostics_root=tmp_path / "diagnostics",
        video_path=Path("/tmp/factory2.MOV"),
        calibration_path=Path("/tmp/calibration.json"),
        model_path=Path("/tmp/model.pt"),
        person_model_path=Path("/tmp/person.pt"),
        diagnostic_runner=lambda **kwargs: {"diagnostic_path": Path(kwargs["out_dir"]) / "diagnostic.json"},
        candidate_limit_per_event=1,
        event_ids={"factory2-runtime-only-0008"},
        force=True,
    )

    assert payload["result_count"] == 1
    assert payload["results"][0]["event_id"] == "factory2-runtime-only-0008"
    assert payload["results"][0]["candidate_id"] == "c"
