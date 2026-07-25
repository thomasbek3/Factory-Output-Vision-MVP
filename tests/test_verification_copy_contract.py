from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILES = [
    REPO_ROOT / "DESIGN.md",
    REPO_ROOT / "docs" / "specs" / "app_spec_v1.md",
    REPO_ROOT / "console" / "components" / "chrome" / "trust-line.tsx",
    REPO_ROOT / "console" / "components" / "live" / "live-dashboard.tsx",
    REPO_ROOT / "console" / "components" / "live" / "clip-drawer-provider.tsx",
    REPO_ROOT / "console" / "components" / "replay" / "replay-dashboard.tsx",
    REPO_ROOT / "console" / "components" / "ops" / "ops-console.tsx",
    REPO_ROOT / "console" / "lib" / "reviewLexicon.ts",
    REPO_ROOT / "console" / "lib" / "reviewStrings.ts",
]


def test_current_product_copy_does_not_claim_unproved_human_ai_verification() -> None:
    missing = [path for path in CONTRACT_FILES if not path.is_file()]
    assert not missing, f"contract files missing: {missing}"

    contents = {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in CONTRACT_FILES
    }

    assert all("Counts verified 100% HUMAN+AI" not in text for text in contents.values())
    assert all("100% Human + AI verified" not in text for text in contents.values())
    assert all("Every count verified by a person, live" not in text for text in contents.values())
    assert "Every click = a verified CountEvent" not in contents["docs/specs/app_spec_v1.md"]
    assert "golden chunks (known counts) injected" not in contents["docs/specs/app_spec_v1.md"]
    assert "chunks/hr" not in contents["docs/specs/app_spec_v1.md"]
    assert all("Verified by M. Reyes" not in text for text in contents.values())
    assert all("model agreed" not in text for text in contents.values())
    assert "VERIFICATION STATUS" in contents["console/components/live/live-dashboard.tsx"]
    assert "HISTORICAL" in contents["console/components/live/live-dashboard.tsx"]
    assert "REVIEW DATA" in contents["console/components/live/live-dashboard.tsx"]


def test_design_contract_contains_dated_verification_copy_amendment() -> None:
    design = (REPO_ROOT / "DESIGN.md").read_text(encoding="utf-8")

    assert "Verification-copy amendment (2026-07-25)" in design
    assert "Verification source and through-time are shown with every resolved count." in design

    app_spec = (REPO_ROOT / "docs" / "specs" / "app_spec_v1.md").read_text(encoding="utf-8")
    assert "Verification and reviewer amendment (2026-07-25)" in app_spec
    assert "hidden golden-chunk injection is prohibited" in app_spec


def test_ops_surface_contains_no_ai_exam_ranking_or_export_controls() -> None:
    ops = (
        REPO_ROOT / "console" / "components" / "ops" / "ops-console.tsx"
    ).read_text(encoding="utf-8").lower()

    forbidden = [
        "model agreement",
        "model ops",
        "held-out exam",
        "golden accuracy",
        "chunks/hr",
        "export labels",
    ]
    assert all(term not in ops for term in forbidden)
    assert not (
        REPO_ROOT / "console" / "app" / "api" / "ops" / "labels" / "export" / "route.ts"
    ).exists()


def test_owner_console_has_no_named_reviewer_claim() -> None:
    console_root = REPO_ROOT / "console"
    owner_paths = [
        path
        for root in ("app", "components", "lib")
        for extension in ("*.ts", "*.tsx", "*.json")
        for path in (console_root / root).rglob(extension)
        if "components/review/" not in path.as_posix()
    ]
    assert owner_paths, "owner console scan found no source files"
    owner_source = "\n".join(path.read_text(encoding="utf-8") for path in owner_paths)

    assert "Verified by M. Reyes" not in owner_source
    assert "M. Reyes" not in owner_source
    assert re.search(r"\bverified by\s+[A-Z]", owner_source, flags=re.IGNORECASE) is None


def test_worker_copy_uses_the_versioned_release_anchor() -> None:
    lexicon = (
        REPO_ROOT / "console" / "lib" / "reviewLexicon.ts"
    ).read_text(encoding="utf-8")
    strings = (
        REPO_ROOT / "console" / "lib" / "reviewStrings.ts"
    ).read_text(encoding="utf-8")

    assert "worker-ground-truth-es-419-v1" in lexicon
    assert "+1 PIEZA" in lexicon
    assert "primer cuadro en que el trabajador la suelta" in lexicon
    assert "queda en el área de salida indicada" in lexicon
    assert "llegue al pallet" not in strings
    assert "+1 CONTEO" not in strings
    assert "Contexto del video anterior. No cuentes aquí." in lexicon
    assert "Contexto del siguiente video. No cuentes aquí." in lexicon
    assert re.search(r"\b(?:bloque|cola|colocación)\b", lexicon, flags=re.IGNORECASE) is None


def test_worker_payload_sources_omit_golden_and_throughput_fields() -> None:
    next_route = (
        REPO_ROOT / "console" / "app" / "api" / "review" / "chunks" / "next" / "route.ts"
    ).read_text(encoding="utf-8")
    confirm_route = (
        REPO_ROOT
        / "console"
        / "app"
        / "api"
        / "review"
        / "chunks"
        / "[id]"
        / "confirm"
        / "route.ts"
    ).read_text(encoding="utf-8")
    chunks = (REPO_ROOT / "console" / "lib" / "reviewChunks.ts").read_text(encoding="utf-8")
    reviewer = (
        REPO_ROOT / "console" / "components" / "review" / "review-tally-console.tsx"
    ).read_text(encoding="utf-8")

    combined = "\n".join([next_route, confirm_route, chunks, reviewer])
    for forbidden in (
        "isGolden",
        "goldenCount",
        "queueDepth",
        "chunksPerHour",
        "nextChunk",
        "locked-by-other",
    ):
        assert forbidden not in combined


def test_training_paths_consume_the_registry_firewall() -> None:
    guard = (
        REPO_ROOT / "app" / "services" / "training_exam_guard.py"
    ).read_text(encoding="utf-8")
    extractor = (
        REPO_ROOT / "app" / "services" / "clip_dataset.py"
    ).read_text(encoding="utf-8")
    labeler = (REPO_ROOT / "scripts" / "label_clips.py").read_text(encoding="utf-8")
    trainer = (
        REPO_ROOT / "scripts" / "train_clip_student.py"
    ).read_text(encoding="utf-8")
    model_service = (
        REPO_ROOT / "app" / "services" / "clip_models.py"
    ).read_text(encoding="utf-8")

    assert "load_exam_firewall" in guard
    assert "assignment_overlaps_exam" in guard
    assert "validate_training_row" in extractor
    assert "validate_training_manifest" in labeler
    assert "validate_training_manifest" in trainer
    assert "validate_training_manifest" in model_service
