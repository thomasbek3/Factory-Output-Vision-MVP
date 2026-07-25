from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILES = [
    REPO_ROOT / "DESIGN.md",
    REPO_ROOT / "docs" / "specs" / "app_spec_v1.md",
    REPO_ROOT / "console" / "components" / "chrome" / "trust-line.tsx",
    REPO_ROOT / "console" / "components" / "live" / "live-dashboard.tsx",
]


def test_current_product_copy_does_not_claim_unproved_human_ai_verification() -> None:
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
    assert "VERIFICATION STATUS" in contents["console/components/live/live-dashboard.tsx"]
    assert "SEEDED REVIEW" in contents["console/components/live/live-dashboard.tsx"]


def test_design_contract_contains_dated_verification_copy_amendment() -> None:
    design = (REPO_ROOT / "DESIGN.md").read_text(encoding="utf-8")

    assert "Verification-copy amendment (2026-07-25)" in design
    assert "Verification source and through-time are shown with every resolved count." in design

    app_spec = (REPO_ROOT / "docs" / "specs" / "app_spec_v1.md").read_text(encoding="utf-8")
    assert "Verification and reviewer amendment (2026-07-25)" in app_spec
    assert "hidden golden-chunk injection is prohibited" in app_spec
