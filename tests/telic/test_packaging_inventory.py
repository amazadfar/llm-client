from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
GUIDE_INDEX = ROOT / "docs" / "telic-guides-index.md"
PY_TYPED = ROOT / "telic" / "py.typed"

EXPECTED_DOCS = [
    "telic-installation-matrix.md",
    "telic-changelog-process.md",
    "telic-semver-policy.md",
    "telic-support-policy.md",
]

EXPECTED_SCRIPTS = [
    "scripts/ci/run_telic_examples.py",
    "scripts/ci/verify_telic_artifacts.py",
]

EXPECTED_OSS_FILES = [
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
]


def test_pyproject_declares_standalone_package_metadata() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    assert project["name"] == "telic"
    assert project["readme"] == "README.md"
    assert project["license"] == "Apache-2.0"
    assert "authors" in project
    assert "maintainers" in project
    assert "classifiers" in project
    assert "keywords" in project
    extras = project["optional-dependencies"]
    for key in [
        "anthropic",
        "google",
        "postgres",
        "mysql",
        "redis",
        "qdrant",
        "adapters",
        "telemetry",
        "performance",
        "server",
        "dev",
        "all",
    ]:
        assert key in extras


def test_docs_exist() -> None:
    missing = [name for name in EXPECTED_DOCS if not (ROOT / "docs" / name).exists()]
    assert missing == []


def test_release_docs_and_scripts_exist() -> None:
    missing_scripts = [name for name in EXPECTED_SCRIPTS if not (ROOT / name).exists()]
    assert missing_scripts == []
    assert not (ROOT / ".github" / "workflows" / "telic-package-ci.yml").exists()
    assert not (ROOT / ".github" / "workflows" / "telic-publish.yml").exists()


def test_typing_marker_and_governance_files_exist() -> None:
    assert PY_TYPED.exists()
    missing = [name for name in EXPECTED_OSS_FILES if not (ROOT / name).exists()]
    assert missing == []


def test_readme_and_guide_index_reference_packaging_docs() -> None:
    readme = README.read_text(encoding="utf-8")
    guide_index = GUIDE_INDEX.read_text(encoding="utf-8")
    assert "docs/telic-installation-matrix.md" in readme
    assert "docs/telic-semver-policy.md" in readme
    assert "docs/telic-support-policy.md" in readme
    assert "telic-installation-matrix.md" in guide_index
    assert "telic-semver-policy.md" in guide_index


def test_packaging_inventory_does_not_depend_on_archived_transition_docs() -> None:
    guide_index = GUIDE_INDEX.read_text(encoding="utf-8")
    assert "telic-modernization-roadmap-2026-03-09.md" not in guide_index
    assert "telic-final-stage-release-checklist-2026-03-24.md" not in guide_index
    assert "telic-packaging-readiness.md" not in guide_index
    assert "telic-release-automation.md" not in guide_index
