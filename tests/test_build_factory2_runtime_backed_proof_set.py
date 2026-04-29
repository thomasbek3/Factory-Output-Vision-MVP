from __future__ import annotations

import json

from scripts.build_factory2_runtime_backed_proof_set import build_runtime_backed_proof_set


def test_build_runtime_backed_proof_set_appends_preferred_runtime_only_diagnostics(tmp_path) -> None:
    queue_path = tmp_path / "queue.json"
    output_path = tmp_path / "proof_set.json"
    active_a = "data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/diagnostic.json"
    active_b = "data/diagnostics/event-windows/factory2-review-0003-258-311s-panel-v1/diagnostic.json"
    extra_a = "data/diagnostics/event-windows/factory2-review-0014-000-030s-panel-v1-5fps/diagnostic.json"
    extra_b = "data/diagnostics/event-windows/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json"

    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "event_id": "factory2-runtime-only-0001",
                        "preferred_diagnostic_path": extra_a,
                    },
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "preferred_diagnostic_path": extra_b,
                    },
                    {
                        "event_id": "factory2-runtime-only-0008",
                        "preferred_diagnostic_path": active_b,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_runtime_backed_proof_set(
        queue_path=queue_path,
        output_path=output_path,
        default_diagnostic_paths=[active_a, active_b],
        force=True,
    )

    assert report["default_diagnostic_count"] == 2
    assert report["added_diagnostic_count"] == 2
    assert report["diagnostic_count"] == 4
    assert report["diagnostic_paths"] == [active_a, active_b, extra_a, extra_b]
    assert report["added_diagnostic_paths"] == [extra_a, extra_b]
    assert output_path.exists()
