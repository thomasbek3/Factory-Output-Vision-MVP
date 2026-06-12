from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.cloud_teacher_providers import (
    ClaudeCliTeacherVerificationProvider,
    CodexCliTeacherVerificationProvider,
    build_batch_prompt,
    parse_batch_response,
    select_packet_images,
)
from app.services.teacher_verification import (
    build_teacher_verifications_from_packets,
    verification_provider_for_name,
)
from scripts import generate_teacher_verifications


def _packet(tmp_path: Path, packet_id: str, *, center: float = 6.0, sequence_count: int = 0) -> dict:
    packet_dir = tmp_path / packet_id
    packet_dir.mkdir(parents=True, exist_ok=True)
    assets = []
    for kind, name, ts in (
        ("before_full_frame", "before_full.jpg", center - 4.0),
        ("during_full_frame", "during_full.jpg", center),
        ("after_full_frame", "after_full.jpg", center + 4.0),
        ("frame_diff_or_motion_heatmap", "diff.jpg", None),
        ("event_clip", "event_clip.mp4", None),
    ):
        asset_path = packet_dir / name
        asset_path.write_bytes(b"fake")
        assets.append({"kind": kind, "path": str(asset_path), "timestamp_sec": ts})
    for index in range(sequence_count):
        for kind, prefix in (("output_zone_crop_sequence", "zone"), ("stack_crop_sequence", "stack")):
            asset_path = packet_dir / f"{prefix}_{index:03d}.jpg"
            asset_path.write_bytes(b"fake")
            assets.append({"kind": kind, "path": str(asset_path), "timestamp_sec": center - 4.0 + index})
    return {
        "schema_version": "factory-vision-teacher-evidence-packets-v2",
        "packet_id": packet_id,
        "candidate_id": f"{packet_id}-candidate",
        "window_id": f"{packet_id}-window",
        "station_id": "line-a",
        "window": {
            "start_offset_sec": center - 4.0,
            "center_offset_sec": center,
            "end_offset_sec": center + 4.0,
        },
        "assets": assets,
        "packet_manifest_path": str(packet_dir / "packet_manifest.json"),
    }


def _assert_entry(packet_id: str, *, ts: float = 7.5, decision: str = "assert_completed") -> dict:
    return {
        "packet_id": packet_id,
        "verification_decision": decision,
        "suggested_event_ts_sec": ts,
        "confidence_tier": "medium",
        "duplicate_risk": "low",
        "miss_risk": "low",
        "rationale": "Stack gains one part between before and after frames.",
    }


def test_cli_providers_refuse_cloud_by_default() -> None:
    with pytest.raises(ValueError, match="disabled by default"):
        ClaudeCliTeacherVerificationProvider()
    with pytest.raises(ValueError, match="disabled by default"):
        CodexCliTeacherVerificationProvider()
    with pytest.raises(ValueError, match="disabled by default"):
        verification_provider_for_name("claude_cli")
    with pytest.raises(ValueError, match="disabled by default"):
        verification_provider_for_name("codex_cli")


def test_assert_response_yields_schema_compliant_label(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one")

    def transport(request):  # noqa: ANN001
        return json.dumps([_assert_entry("packet-one")])

    provider = ClaudeCliTeacherVerificationProvider(allow_cloud=True, transport=transport)
    label = provider.verify_packet(packet=packet)

    assert label["verification_decision"] == "assert_completed"
    assert label["teacher_output_status"] == "completed"
    assert label["suggested_event_ts_sec"] == 7.5
    assert label["confidence_tier"] == "medium"
    assert label["duplicate_risk"] == "low"
    assert label["miss_risk"] == "low"
    assert label["label_authority_tier"] == "bronze"
    assert label["review_status"] == "pending"
    assert label["validation_truth_eligible"] is False
    assert label["training_eligible"] is False
    assert provider.usage.invocations == 1
    assert provider.provider_metadata()["network_calls_made"] is True


def test_suggested_timestamp_clamped_to_window(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one", center=6.0)

    def transport(request):  # noqa: ANN001
        return json.dumps([_assert_entry("packet-one", ts=99.0)])

    provider = ClaudeCliTeacherVerificationProvider(allow_cloud=True, transport=transport)
    label = provider.verify_packet(packet=packet)
    assert label["suggested_event_ts_sec"] == 10.0  # clamped to end_offset_sec


def test_malformed_response_yields_unclear_not_crash(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one")

    def transport(request):  # noqa: ANN001
        return "I could not determine anything useful."

    provider = ClaudeCliTeacherVerificationProvider(allow_cloud=True, transport=transport)
    label = provider.verify_packet(packet=packet)
    assert label["verification_decision"] == "unclear"
    assert label["rationale"].startswith("provider_error:")
    assert provider.usage.parse_failures == 1


def test_transport_exception_yields_unclear_not_crash(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one")

    def transport(request):  # noqa: ANN001
        raise RuntimeError("cli exploded")

    provider = CodexCliTeacherVerificationProvider(allow_cloud=True, transport=transport)
    label = provider.verify_packet(packet=packet)
    assert label["verification_decision"] == "unclear"
    assert label["rationale"].startswith("provider_error: transport")
    assert provider.usage.transport_errors == 1


def test_invalid_enum_decision_normalized_to_unclear(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one")

    def transport(request):  # noqa: ANN001
        return json.dumps([_assert_entry("packet-one", decision="definitely_yes")])

    provider = ClaudeCliTeacherVerificationProvider(allow_cloud=True, transport=transport)
    label = provider.verify_packet(packet=packet)
    assert label["verification_decision"] == "unclear"
    assert label["suggested_event_ts_sec"] is None


def test_image_selection_deterministic_and_capped(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one", sequence_count=20)

    first = select_packet_images(packet, max_sequence_images=8, max_images=12)
    second = select_packet_images(packet, max_sequence_images=8, max_images=12)

    assert first == second
    assert len(first) == 12
    paths = [path for path, _ in first]
    assert not any("stack_" in path for path in paths)
    assert not any(path.endswith(".mp4") for path in paths)
    assert sum(1 for path in paths if "zone_" in path) == 8
    sequence_captions = [caption for path, caption in first if "zone_" in path]
    assert all("t=" in caption for caption in sequence_captions)


def test_image_selection_skips_missing_files(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one", sequence_count=2)
    packet["assets"].append({"kind": "output_zone_crop_sequence", "path": str(tmp_path / "missing.jpg"), "timestamp_sec": 9.0})

    images = select_packet_images(packet, max_sequence_images=8, max_images=12)
    assert all(Path(path).exists() for path, _ in images)


def test_batch_failure_splits_and_isolates_bad_packet(tmp_path: Path) -> None:
    packets = [_packet(tmp_path, f"packet-{index}") for index in range(4)]
    calls: list[int] = []

    def transport(request):  # noqa: ANN001
        requested_ids = [line.split()[1] for line in request.prompt.splitlines() if line.startswith("PACKET ")]
        calls.append(len(requested_ids))
        if "packet-3" in requested_ids and len(requested_ids) > 1:
            return "garbage that does not parse"
        if requested_ids == ["packet-3"]:
            return "still garbage"
        return json.dumps([_assert_entry(packet_id) for packet_id in requested_ids])

    provider = ClaudeCliTeacherVerificationProvider(allow_cloud=True, transport=transport, batch_size=4)
    labels = provider.verify_packets(packets=packets)

    by_id = {label["packet_id"]: label for label in labels}
    assert len(labels) == 4
    assert by_id["packet-0"]["verification_decision"] == "assert_completed"
    assert by_id["packet-1"]["verification_decision"] == "assert_completed"
    assert by_id["packet-2"]["verification_decision"] == "assert_completed"
    assert by_id["packet-3"]["verification_decision"] == "unclear"
    assert provider.usage.retries >= 1
    assert provider.usage.packets_labeled == 4


def test_prompt_modes_reference_images_correctly(tmp_path: Path) -> None:
    packet = _packet(tmp_path, "packet-one", sequence_count=2)
    images = select_packet_images(packet, max_sequence_images=8, max_images=12)

    read_prompt = build_batch_prompt([(packet, images)], image_reference_mode="read_tool_paths")
    attach_prompt = build_batch_prompt([(packet, images)], image_reference_mode="attached_in_order")

    assert "Use the Read tool" in read_prompt
    assert str(tmp_path) in read_prompt
    assert "attached to this message" in attach_prompt
    assert "Image 1:" in attach_prompt
    assert str(tmp_path) not in attach_prompt.split("attached to this message")[1]
    assert "Respond with ONLY a JSON array" in read_prompt


def test_parse_batch_response_handles_fences_and_single_object() -> None:
    entry = _assert_entry("packet-one")
    fenced = "```json\n" + json.dumps([entry]) + "\n```"
    assert parse_batch_response(fenced)["packet-one"]["verification_decision"] == "assert_completed"
    prose = "Here is my answer:\n" + json.dumps([entry]) + "\nThanks!"
    assert parse_batch_response(prose)["packet-one"]["verification_decision"] == "assert_completed"
    single = json.dumps(entry)
    assert parse_batch_response(single)["packet-one"]["verification_decision"] == "assert_completed"
    assert parse_batch_response("no json here") is None


def test_full_payload_metadata_reports_usage_after_labels(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, ["packet-one", "packet-two"])

    def transport(request):  # noqa: ANN001
        requested_ids = [line.split()[1] for line in request.prompt.splitlines() if line.startswith("PACKET ")]
        return json.dumps([_assert_entry(packet_id) for packet_id in requested_ids])

    provider = ClaudeCliTeacherVerificationProvider(allow_cloud=True, transport=transport, batch_size=2)
    payload = build_teacher_verifications_from_packets(packet_manifest_path=manifest, provider=provider)

    assert len(payload["labels"]) == 2
    assert payload["provider"]["network_calls_made"] is True
    assert payload["provider"]["usage"]["invocations"] == 1
    assert payload["provider"]["usage"]["packets_labeled"] == 2
    assert payload["refuses_validation_truth"] is True


def test_cli_resume_reuses_prior_labels(tmp_path: Path, capsys) -> None:
    manifest = _write_manifest(tmp_path, ["packet-one", "packet-two"])
    first_output = tmp_path / "labels_v1.json"
    second_output = tmp_path / "labels_v2.json"

    prior_payload = {
        "schema_version": "factory-vision-teacher-labels-v1",
        "provider": {"name": "fake_verifier", "mode": "fake_local_test", "model": None},
        "labels": [
            {
                "packet_id": "packet-one",
                "verification_decision": "assert_completed",
                "rationale": "prior good label",
            },
            {
                "packet_id": "packet-two",
                "verification_decision": "unclear",
                "rationale": "provider_error: transport RuntimeError",
            },
        ],
    }
    first_output.write_text(json.dumps(prior_payload), encoding="utf-8")

    exit_code = generate_teacher_verifications.main(
        [
            "--packet-manifest",
            str(manifest),
            "--provider",
            "fake_verifier",
            "--resume",
            str(first_output),
            "--output",
            str(second_output),
            "--force",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(second_output.read_text(encoding="utf-8"))
    by_id = {label["packet_id"]: label for label in payload["labels"]}
    assert exit_code == 0
    assert '"resumed_label_count": 1' in captured.out
    assert by_id["packet-one"]["rationale"] == "prior good label"  # reused
    assert by_id["packet-two"]["rationale"] != "provider_error: transport RuntimeError"  # re-run


def test_cli_resume_rejects_provider_mismatch(tmp_path: Path, capsys) -> None:
    manifest = _write_manifest(tmp_path, ["packet-one"])
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"provider": {"name": "codex_cli"}, "labels": []}), encoding="utf-8")

    exit_code = generate_teacher_verifications.main(
        [
            "--packet-manifest",
            str(manifest),
            "--provider",
            "fake_verifier",
            "--resume",
            str(prior),
            "--output",
            str(tmp_path / "out.json"),
            "--force",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "does not match requested provider" in captured.err


def test_max_packets_limits_work(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, ["packet-one", "packet-two", "packet-three"])

    def transport(request):  # noqa: ANN001
        requested_ids = [line.split()[1] for line in request.prompt.splitlines() if line.startswith("PACKET ")]
        return json.dumps([_assert_entry(packet_id) for packet_id in requested_ids])

    provider = ClaudeCliTeacherVerificationProvider(allow_cloud=True, transport=transport)
    payload = build_teacher_verifications_from_packets(packet_manifest_path=manifest, provider=provider, max_packets=2)
    assert len(payload["labels"]) == 2


def _write_manifest(tmp_path: Path, packet_ids: list[str]) -> Path:
    rows = []
    for packet_id in packet_ids:
        packet = _packet(tmp_path, packet_id)
        packet_path = Path(packet["packet_manifest_path"])
        packet_payload = {key: value for key, value in packet.items() if key != "packet_manifest_path"}
        packet_path.write_text(json.dumps(packet_payload), encoding="utf-8")
        rows.append({"packet_id": packet_id, "packet_manifest_path": str(packet_path)})
    manifest = tmp_path / "teacher_evidence_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-teacher-evidence-packets-v2",
                "station_id": "line-a",
                "privacy_mode": "offline_local",
                "packets": rows,
            }
        ),
        encoding="utf-8",
    )
    return manifest
