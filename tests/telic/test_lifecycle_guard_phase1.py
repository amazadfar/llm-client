"""Phase 1 tests for the temporary lifecycle warning layer (audit C-004 / A-CAT-005).

A narrow, temporary guard warns when a deprecated or retired model is selected. It is
superseded by structured Catalog v2 lifecycle handling in Phase 2.
"""

from __future__ import annotations

import warnings

import pytest

from telic.models import ModelProfile, warn_if_deprecated


def test_retired_model_warns_with_retirement_date() -> None:
    profile = ModelProfile.get("claude-3-haiku")
    with pytest.warns(DeprecationWarning, match="retired on 2026-04-20"):
        warn_if_deprecated(profile)


def test_retired_model_warning_names_replacement() -> None:
    profile = ModelProfile.get("claude-3-haiku")
    with pytest.warns(DeprecationWarning, match="claude-haiku-4-5"):
        warn_if_deprecated(profile)


def test_deprecated_model_warns() -> None:
    # claude-3-haiku is both retired and deprecated; pick a deprecated-but-not-retired one.
    profile = ModelProfile.get("claude-3-opus")
    assert profile.deprecated is True
    with pytest.warns(DeprecationWarning, match="deprecated"):
        warn_if_deprecated(profile)


def test_current_model_does_not_warn() -> None:
    profile = ModelProfile.get("claude-sonnet-4-6")
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        warn_if_deprecated(profile)  # must not raise


def test_unresolved_model_does_not_warn() -> None:
    profile = ModelProfile.get("totally-unknown-model-xyz-123")
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        warn_if_deprecated(profile)  # must not raise
