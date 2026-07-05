from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARDING_CLI_SCRIPTS = [
    "scripts/research/factory2/extract_onboarding_windows.py",
    "scripts/propose_onboarding_events.py",
    "scripts/build_teacher_evidence_packets.py",
    "scripts/generate_teacher_verifications.py",
    "scripts/reconcile_state_diff.py",
    "scripts/fuse_teacher_verifications.py",
    "scripts/run_teacher_loop_benchmark.py",
    "scripts/research/factory2/generate_onboarding_teacher_labels.py",
    "scripts/research/factory2/run_blind_replay_gate.py",
    "scripts/research/factory2/apply_live_activation.py",
    "scripts/research/factory2/run_periodic_audit.py",
    "scripts/research/factory2/run_yolo26_training_eval.py",
]


def test_onboarding_cli_scripts_can_show_help_from_repo_root() -> None:
    for script in ONBOARDING_CLI_SCRIPTS:
        result = subprocess.run(
            [sys.executable, script, "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"{script} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
