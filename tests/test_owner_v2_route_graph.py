from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "console"
IMPORT_RE = re.compile(
    r"""(?:from\s+|import\s*(?:\(\s*)?)["'](@/[^"']+|\.[^"']+)["']"""
)
BANNED = {
    "demoData",
    "historyRecords",
    "ownerDashboard",
    "paceMath",
    "pinnedJobs",
}


def resolve_import(source: Path, specifier: str) -> Path | None:
    base = CONSOLE / specifier.removeprefix("@/") if specifier.startswith("@/") else source.parent / specifier
    for candidate in (
        base,
        base.with_suffix(".ts"),
        base.with_suffix(".tsx"),
        base / "index.ts",
        base / "index.tsx",
    ):
        if candidate.is_file():
            return candidate.resolve()
    return None


def reachable_files(entries: list[Path]) -> set[Path]:
    pending = [entry.resolve() for entry in entries]
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        text = path.read_text(encoding="utf-8")
        for specifier in IMPORT_RE.findall(text):
            resolved = resolve_import(path, specifier)
            if resolved and resolved not in visited:
                pending.append(resolved)
    return visited


class OwnerV2RouteGraphTests(unittest.TestCase):
    def test_production_owner_routes_do_not_reach_fixture_modules(self) -> None:
        entries = list((CONSOLE / "app/(owner)").glob("**/page.tsx"))
        entries.append(CONSOLE / "app/(owner)/layout.tsx")
        entries.extend((CONSOLE / "app/api/owner").glob("**/route.ts"))
        reachable = reachable_files(entries)
        offenders = sorted(
            str(path.relative_to(CONSOLE))
            for path in reachable
            if path.stem in BANNED
            or "preview" in path.relative_to(CONSOLE).parts
            or "PREVIEW_ONLY_OWNER_FIXTURE" in path.read_text(encoding="utf-8")
        )
        self.assertEqual(offenders, [])

    def test_production_owner_routes_do_not_reach_other_role_modules(self) -> None:
        entries = list((CONSOLE / "app/(owner)").glob("**/page.tsx"))
        entries.append(CONSOLE / "app/(owner)/layout.tsx")
        entries.extend((CONSOLE / "app/api/owner").glob("**/route.ts"))
        reachable = reachable_files(entries)
        offenders = sorted(
            str(path.relative_to(CONSOLE))
            for path in reachable
            if (
                path.is_relative_to(CONSOLE / "components/review")
                or path.is_relative_to(CONSOLE / "components/ops")
                or path.name in {"reviewServer.ts", "opsServer.ts"}
            )
        )
        self.assertEqual(offenders, [])

    def test_preview_components_have_no_direct_clock_or_network_reads(self) -> None:
        entries = list((CONSOLE / "app/owner-preview").glob("**/page.tsx"))
        reachable = reachable_files(entries)
        offenders = sorted(
            str(path.relative_to(CONSOLE))
            for path in reachable
            if path.is_relative_to(CONSOLE / "components/owner-v2")
            and re.search(r"\b(?:Date\.now|fetch)\s*\(", path.read_text(encoding="utf-8"))
        )
        self.assertEqual(offenders, [])

    def test_e2e_does_not_navigate_to_retired_owner_routes(self) -> None:
        offenders: list[str] = []
        for path in (CONSOLE / "e2e").glob("*.spec.ts"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"""\b(?:goto|toHaveURL)\s*\(\s*["']/+(?:tv|replay)""", text):
                offenders.append(str(path.relative_to(CONSOLE)))
        self.assertEqual(sorted(offenders), [])

    def test_removed_production_routes_are_absent(self) -> None:
        self.assertFalse((CONSOLE / "app/tv/page.tsx").exists())
        self.assertFalse((CONSOLE / "app/(owner)/replay/page.tsx").exists())
        self.assertFalse((CONSOLE / "app/api/jobs/route.ts").exists())
        self.assertFalse((CONSOLE / "app/api/jobs/[id]/route.ts").exists())


if __name__ == "__main__":
    unittest.main()
