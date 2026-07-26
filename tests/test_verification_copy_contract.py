from __future__ import annotations

import ast
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
    assert "worker-ground-truth-es-419-v1" in lexicon
    assert "+1 PIEZA" in lexicon
    assert "primer cuadro en que el trabajador la suelta" in lexicon
    assert "queda en el área de salida indicada" in lexicon
    assert "llegue al pallet" not in lexicon
    assert "+1 CONTEO" not in lexicon
    assert "Contexto del video anterior. No cuentes aquí." in lexicon
    assert "Contexto del siguiente video. No cuentes aquí." in lexicon
    assert (
        "Count one piece on the first frame where the worker has released the "
        "finished piece and it remains in the designated output area."
    ) in lexicon
    assert "VOLVER A EDITAR" in lexicon
    assert "BACK TO EDIT" in lexicon
    assert "COMENZAR SIGUIENTE VIDEO" in lexicon
    assert "CONTINUAR VIDEO" not in lexicon
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
    guarded_paths = {
        "app/services/clip_dataset.py": "validate_training_row",
        "app/services/clip_models.py": "validate_training_manifest",
        "app/services/yolo26_training_runner.py": "validate_training_manifest",
        "scripts/legacy/train_custom_model.py": "validate_training_manifest",
        "scripts/research/factory2/assemble_active_panel_dataset.py": "validate_training_row",
        "scripts/research/factory2/run_yolo26_training_eval.py": (
            "from app.services.yolo26_training_runner import run_yolo26_training_eval"
        ),
    }
    discovered: set[str] = set()
    for root in (REPO_ROOT / "app", REPO_ROOT / "scripts"):
        for path in root.rglob("*.py"):
            relative = path.relative_to(REPO_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if (
                            isinstance(key, ast.Constant)
                            and key.value == "training_eligible"
                            and isinstance(value, ast.Constant)
                            and value.value is True
                        ):
                            discovered.add(relative)
                if isinstance(node, ast.Call):
                    call_name = (
                        node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else node.func.id
                        if isinstance(node.func, ast.Name)
                        else ""
                    )
                    if call_name in {
                        "fit",
                        "train",
                        "train_sequence_classifier",
                        "run_yolo26_training_eval",
                    }:
                        discovered.add(relative)

    assert discovered == set(guarded_paths), (
        "training-path discovery changed; every new emitter or trainer must be "
        f"reviewed and firewall-wired: {sorted(discovered)}"
    )
    for relative, guard_token in guarded_paths.items():
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert guard_token in source, f"{relative} is missing {guard_token}"

    for relative in (
        "app/services/onboarding_rehearsal.py",
        "scripts/research/factory2/run_factory_day1_pipeline.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "run_yolo26_training_eval.py" in source
        assert "dataset_manifest" in source


def test_clip_trainer_firewall_is_not_conditional_on_manifest_content() -> None:
    path = REPO_ROOT / "app" / "services" / "clip_models.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    guard_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "validate_training_manifest"
    ]
    assert guard_calls, "clip trainer must validate its training manifest"
    for call in guard_calls:
        ancestor = parents.get(call)
        while ancestor is not None and not isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert not isinstance(ancestor, ast.If), (
                "clip trainer firewall must not depend on a caller-controlled "
                "manifest field"
            )
            ancestor = parents.get(ancestor)
