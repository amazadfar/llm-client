from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
GUIDE_INDEX = ROOT / "docs" / "telic-guides-index.md"


EXPECTED_GUIDES = [
    "telic-guides-index.md",
    "telic-build-and-recipes-guide.md",
    "telic-provider-setup-guide.md",
    "telic-routing-and-failover-guide.md",
    "telic-tool-runtime-guide.md",
    "telic-structured-outputs-guide.md",
    "telic-context-and-memory-guide.md",
    "telic-observability-and-redaction-guide.md",
    "telic-migration-from-direct-sdk-guide.md",
]


def test_guides_exist() -> None:
    missing = [name for name in EXPECTED_GUIDES if not (ROOT / "docs" / name).exists()]
    assert missing == []


def test_readme_links_guides_index() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "docs/telic-guides-index.md" in readme


def test_guide_index_lists_expected_guides() -> None:
    guide_index = GUIDE_INDEX.read_text(encoding="utf-8")
    for name in EXPECTED_GUIDES[1:]:
        assert name in guide_index


def test_guide_index_excludes_archived_transition_docs() -> None:
    guide_index = GUIDE_INDEX.read_text(encoding="utf-8")
    assert "telic-modernization-roadmap-2026-03-09.md" not in guide_index
    assert "telic-repo-split-guidance.md" not in guide_index
    assert "telic-release-notes-1.0.0-rc1.md" not in guide_index
