#!/usr/bin/env python
"""Validate the checked-in provider catalog and its source snapshot.

Default validation is deterministic and offline. ``--online`` adds a bounded
reachability check for every source URL; it does not mutate reviewed dates or
silently accept provider changes.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Any
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker

from build_catalog_v2 import build


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "telic" / "assets"
CATALOG_PATH = ASSETS / "model_catalog.json"
SCHEMA_PATH = ASSETS / "model_catalog.schema.v2.json"
MANIFEST_PATH = ASSETS / "provider_source_manifest.json"


class CatalogValidationError(ValueError):
    pass


def _parse_date(value: Any, *, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise CatalogValidationError(f"{field} must be an ISO date, got {value!r}") from exc


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(
    manifest: dict[str, Any],
    *,
    as_of: date,
    max_age_days: int | None = None,
) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    if manifest.get("version") != 1:
        errors.append("provider source manifest version must be 1")
    reviewed_at = _parse_date(manifest.get("reviewed_at"), field="reviewed_at")
    stale_after = int(max_age_days or manifest.get("stale_after_days") or 30)
    age = (as_of - reviewed_at).days
    if age > stale_after:
        warnings.append(
            f"provider source snapshot is stale: reviewed {reviewed_at.isoformat()} "
            f"({age} days old; threshold {stale_after})"
        )

    ids: set[str] = set()
    providers: set[str] = set()
    for index, source in enumerate(manifest.get("sources") or []):
        prefix = f"sources[{index}]"
        source_id = str(source.get("id") or "")
        if not source_id or source_id in ids:
            errors.append(f"{prefix}.id is missing or duplicated: {source_id!r}")
        ids.add(source_id)
        provider = str(source.get("provider") or "")
        providers.add(provider)
        url = str(source.get("url") or "")
        if not url.startswith(("https://", "http://")):
            errors.append(f"{prefix}.url must be an HTTP(S) URL")
        if source.get("review_status") != "verified":
            errors.append(f"{prefix}.review_status must be 'verified'")
        fetched = _parse_date(source.get("fetched_at"), field=f"{prefix}.fetched_at")
        effective = _parse_date(source.get("effective_date"), field=f"{prefix}.effective_date")
        if effective > fetched:
            errors.append(f"{prefix}.effective_date cannot be after fetched_at")
        if fetched > as_of:
            errors.append(f"{prefix}.fetched_at cannot be in the future")
        if not source.get("scopes"):
            errors.append(f"{prefix}.scopes must not be empty")

    if not {"openai", "anthropic"}.issubset(providers):
        errors.append("source manifest must cover both openai and anthropic")

    matrix = manifest.get("sdk_matrix") or {}
    expected = {
        "openai": ("2.36", "3"),
        "anthropic": ("0.104", "1"),
    }
    for provider, (minimum, upper) in expected.items():
        item = matrix.get(provider) or {}
        if item.get("minimum") != minimum or item.get("upper_bound") != upper:
            errors.append(
                f"sdk_matrix.{provider} must declare minimum {minimum} and upper bound {upper}"
            )

    if errors:
        raise CatalogValidationError("\n".join(errors))
    return warnings


def validate_catalog(catalog: dict[str, Any], schema: dict[str, Any], *, as_of: date) -> None:
    schema_errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(catalog),
        key=lambda error: list(error.absolute_path),
    )
    if schema_errors:
        rendered = [
            f"{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in schema_errors
        ]
        raise CatalogValidationError("catalog schema validation failed:\n" + "\n".join(rendered))

    errors: list[str] = []
    keys: set[str] = set()
    identities: dict[str, str] = {}
    models = catalog.get("models") or []
    for model in models:
        key = str(model["key"])
        if key in keys:
            errors.append(f"duplicate model key: {key}")
        keys.add(key)
        # Compatibility keys may intentionally share a provider wire model_name.
        # Canonical keys, aliases, and snapshot lookup identities must remain unique.
        for identity in [key, *(model.get("aliases") or []), *(model.get("snapshots") or [])]:
            owner = identities.get(identity)
            if owner is not None and owner != key:
                errors.append(f"identity {identity!r} is shared by {owner!r} and {key!r}")
            identities[identity] = key

        lifecycle = model["lifecycle"]
        announced = lifecycle.get("announced_on")
        deprecated = lifecycle.get("deprecated_on")
        retires = lifecycle.get("retires_on")
        announced_date = _parse_date(announced, field=f"{key}.announced_on") if announced else None
        deprecated_date = _parse_date(deprecated, field=f"{key}.deprecated_on") if deprecated else None
        retires_date = _parse_date(retires, field=f"{key}.retires_on") if retires else None
        if announced_date and deprecated_date and announced_date > deprecated_date:
            errors.append(f"{key}: announced_on is after deprecated_on")
        if deprecated_date and retires_date and deprecated_date > retires_date:
            errors.append(f"{key}: deprecated_on is after retires_on")
        if retires_date and retires_date < as_of and lifecycle["status"] != "retired":
            errors.append(
                f"{key}: retirement date {retires_date.isoformat()} has passed but status is "
                f"{lifecycle['status']!r}"
            )
        replacement = lifecycle.get("replacement")
        if replacement and replacement not in keys and not any(
            candidate.get("key") == replacement for candidate in models
        ):
            errors.append(f"{key}: replacement {replacement!r} is not a catalog key")

        pricing = model["pricing"]
        rates = [dimension.get("rate") for dimension in pricing.get("dimensions") or []]
        if pricing["completeness"] == "complete" and any(rate is None for rate in rates):
            errors.append(f"{key}: complete pricing contains an unknown rate")
        if pricing["completeness"] == "unknown" and any(rate is not None for rate in rates):
            errors.append(f"{key}: unknown pricing contains a known rate")

    for provider, categories in (catalog.get("defaults") or {}).items():
        for category, key in categories.items():
            if key not in keys:
                errors.append(f"default {provider}.{category} references missing model {key!r}")

    generated = build()
    if generated != catalog:
        errors.append(
            "checked-in model_catalog.json differs from deterministic generator output; "
            "run .venv/bin/python scripts/catalog/build_catalog_v2.py"
        )
    if errors:
        raise CatalogValidationError("\n".join(errors))


def validate_online_sources(manifest: dict[str, Any], *, timeout: float) -> None:
    failures: list[str] = []
    for source in manifest["sources"]:
        request = Request(
            source["url"],
            headers={"User-Agent": "telic-catalog-validator/0.4"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                if int(getattr(response, "status", 200)) >= 400:
                    failures.append(f"{source['id']}: HTTP {response.status}")
        except Exception as exc:
            failures.append(f"{source['id']}: {type(exc).__name__}: {exc}")
    if failures:
        raise CatalogValidationError("online source checks failed:\n" + "\n".join(failures))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--max-age-days", type=int)
    parser.add_argument("--strict-staleness", action="store_true")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    as_of = _parse_date(args.as_of, field="--as-of")
    manifest = _load(MANIFEST_PATH)
    warnings = validate_manifest(manifest, as_of=as_of, max_age_days=args.max_age_days)
    validate_catalog(_load(CATALOG_PATH), _load(SCHEMA_PATH), as_of=as_of)
    if args.online:
        validate_online_sources(manifest, timeout=args.timeout)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if warnings and args.strict_staleness:
        raise CatalogValidationError("source snapshot staleness exceeds the configured threshold")
    print(
        "provider catalog validation passed "
        f"(as_of={as_of.isoformat()}, reviewed_at={manifest['reviewed_at']}, online={args.online})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CatalogValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
