from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.teacher_verification import (
    build_teacher_verifications_from_packets,
    verification_provider_for_name,
    write_teacher_verifications,
)


def _load_resume_labels(resume_path: Path, *, provider_name: str, model: str | None) -> dict[str, dict[str, Any]]:
    payload = json.loads(resume_path.read_text(encoding="utf-8"))
    prior_provider = payload.get("provider") or {}
    if str(prior_provider.get("name")) != provider_name:
        raise ValueError(
            f"resume file provider {prior_provider.get('name')!r} does not match requested provider {provider_name!r}"
        )
    requested_model = model or "cli_default"
    prior_model = prior_provider.get("model") or "cli_default"
    if prior_model != requested_model and prior_provider.get("mode") == "subscription_cli":
        raise ValueError(f"resume file model {prior_model!r} does not match requested model {requested_model!r}")
    resumable: dict[str, dict[str, Any]] = {}
    for label in payload.get("labels") or []:
        rationale = str(label.get("rationale") or "")
        if rationale.startswith("provider_error:"):
            continue  # re-run packets that previously failed transport/parsing
        resumable[str(label["packet_id"])] = label
    return resumable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate teacher verification labels from evidence packets")
    parser.add_argument("--packet-manifest", type=Path, required=True)
    parser.add_argument("--provider", default="dry_run_verifier")
    parser.add_argument("--allow-cloud", action="store_true")
    parser.add_argument("--teacher-model", default=None, help="model name/alias forwarded to the provider CLI")
    parser.add_argument("--batch-size", type=int, default=None, help="packets per CLI invocation for batch providers")
    parser.add_argument("--max-packets", type=int, default=None, help="cost guardrail: only label the first N packets")
    parser.add_argument("--resume", type=Path, default=None, help="prior output file; reuse its non-error labels by packet_id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        provider = verification_provider_for_name(
            args.provider,
            allow_cloud=args.allow_cloud,
            model=args.teacher_model,
            batch_size=args.batch_size,
        )
        resume_labels: dict[str, dict[str, Any]] = {}
        if args.resume is not None:
            resume_labels = _load_resume_labels(args.resume, provider_name=args.provider.strip().lower(), model=args.teacher_model)
        payload = build_teacher_verifications_from_packets(
            packet_manifest_path=args.packet_manifest,
            provider=provider,
            max_packets=args.max_packets,
            resume_labels=resume_labels,
        )
        write_teacher_verifications(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    summary = {
        "output": args.output.as_posix(),
        "label_count": len(payload["labels"]),
        "resumed_label_count": len(resume_labels),
        "provider": payload["provider"]["name"],
        "network_calls_made": payload["provider"]["network_calls_made"],
    }
    if payload["provider"].get("usage") is not None:
        summary["usage"] = payload["provider"]["usage"]
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
