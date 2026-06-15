from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "catalog" / "validate_provider_catalog.py"
MANIFEST = ROOT / "llm_client" / "assets" / "provider_source_manifest.json"


def test_offline_provider_catalog_validation_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--as-of", "2026-06-15"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "provider catalog validation passed" in completed.stdout


def test_manifest_staleness_warns_without_network() -> None:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        from validate_provider_catalog import validate_manifest
    finally:
        sys.path.pop(0)
    manifest = deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
    manifest["reviewed_at"] = "2026-01-01"
    warnings = validate_manifest(manifest, as_of=date(2026, 6, 15), max_age_days=30)
    assert warnings and "stale" in warnings[0]


def test_manifest_rejects_unreviewed_source() -> None:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        from validate_provider_catalog import CatalogValidationError, validate_manifest
    finally:
        sys.path.pop(0)
    manifest = deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
    manifest["sources"][0]["review_status"] = "needs_review"
    with pytest.raises(CatalogValidationError, match="review_status"):
        validate_manifest(manifest, as_of=date(2026, 6, 15))


def test_locked_provider_sdk_floors_match_package_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies = set(project["dependencies"])
    anthropic_extra = set(project["optional-dependencies"]["anthropic"])
    assert "openai>=2.36,<3" in dependencies
    assert "anthropic>=0.104,<1" in anthropic_extra
