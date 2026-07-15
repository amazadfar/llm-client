"""Phase 5 golden tests for the multidimensional pricing resolver.

Source-backed cases against the catalog v2 pricing dimensions: standard/tier/batch
selection, long-context thresholds, cache read/write, unknown-vs-zero, and the
provider-batch-only discount (Architecture Decision 6).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from telic.model_catalog import clear_model_catalog_cache, get_default_model_catalog
from telic.pricing import resolve_cost, resolve_cost_decimal


@pytest.fixture(scope="module")
def catalog():
    clear_model_catalog_cache()
    cat = get_default_model_catalog()
    yield cat
    clear_model_catalog_cache()


def test_gpt_5_5_standard(catalog) -> None:
    p = catalog.get("gpt-5.5").pricing
    # 100K tokens: below the 272K long-context threshold -> base rates.
    cost = resolve_cost(p, input_tokens=100_000, output_tokens=100_000)
    assert cost.cost_status == "complete"
    assert cost.input_cost == pytest.approx(100_000 * 5.0 / 1_000_000)
    assert cost.output_cost == pytest.approx(100_000 * 30.0 / 1_000_000)
    assert cost.total_cost == pytest.approx(0.5 + 3.0)


def test_gpt_5_5_priority_tier(catalog) -> None:
    p = catalog.get("gpt-5.5").pricing
    cost = resolve_cost(p, input_tokens=1_000_000, output_tokens=1_000_000, tier="priority")
    assert cost.input_cost == pytest.approx(12.5)
    assert cost.output_cost == pytest.approx(75.0)
    assert cost.total_cost == pytest.approx(87.5)


def test_gpt_5_5_provider_batch_discount(catalog) -> None:
    p = catalog.get("gpt-5.5").pricing
    # local concurrency bills standard (no discount)...
    concurrent = resolve_cost(p, input_tokens=100_000, output_tokens=100_000, mode="concurrent")
    assert concurrent.total_cost == pytest.approx(0.5 + 3.0)
    # ...only an actual provider batch gets the discount.
    batch = resolve_cost(p, input_tokens=100_000, output_tokens=100_000, mode="provider_batch")
    assert batch.input_cost == pytest.approx(100_000 * 2.5 / 1_000_000)
    assert batch.output_cost == pytest.approx(100_000 * 15.0 / 1_000_000)


def test_gpt_5_5_long_context_threshold(catalog) -> None:
    p = catalog.get("gpt-5.5").pricing
    # > 272K tokens -> 2x input, 1.5x output band.
    cost = resolve_cost(p, input_tokens=300_000, output_tokens=300_000)
    assert cost.input_cost == pytest.approx(300_000 * 10.0 / 1_000_000)
    assert cost.output_cost == pytest.approx(300_000 * 45.0 / 1_000_000)


def test_opus_4_8_with_cache(catalog) -> None:
    p = catalog.get("claude-opus-4-8").pricing
    cost = resolve_cost(
        p,
        input_tokens=1_000_000,
        output_tokens=200_000,
        cache_read_tokens=500_000,
        cache_creation_tokens=100_000,
        cache_ttl="5m",
    )
    # uncached input = 500K @ $5/MTok = $2.50; cache read = 500K @ $0.50 = $0.25
    assert cost.input_cost == pytest.approx(2.5)
    assert cost.cache_read_cost == pytest.approx(0.25)
    # output 200K @ $25/MTok = $5.00
    assert cost.output_cost == pytest.approx(5.0)
    # cache write 5m = 100K @ $6.25/MTok = $0.625
    assert cost.cache_write_cost == pytest.approx(0.625)
    assert cost.cost_status == "complete"


def test_opus_4_8_fast_mode_pricing(catalog) -> None:
    p = catalog.get("claude-opus-4-8").pricing
    cost = resolve_cost(
        p,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        speed="fast",
    )
    assert cost.input_cost == pytest.approx(10.0)
    assert cost.output_cost == pytest.approx(50.0)
    assert cost.total_cost == pytest.approx(60.0)


def test_gpt_5_5_pro_partial_pricing(catalog) -> None:
    p = catalog.get("gpt-5.5-pro").pricing
    # standard tier is known -> complete
    standard = resolve_cost(p, input_tokens=1_000_000, output_tokens=1_000_000)
    assert standard.cost_status == "complete"
    assert standard.input_cost == pytest.approx(30.0)
    assert standard.output_cost == pytest.approx(180.0)
    # priority tier rates are unknown -> cannot price this request; never a fake zero
    priority = resolve_cost(p, input_tokens=100_000, output_tokens=100_000, tier="priority")
    assert priority.cost_status == "unknown"
    assert priority.input_cost is None and priority.output_cost is None
    assert priority.total_cost is None
    assert "input" in priority.missing and "output" in priority.missing


def test_unknown_pricing_is_not_zero(catalog) -> None:
    p = catalog.get("gpt-oss-120b").pricing
    cost = resolve_cost(p, input_tokens=1_000, output_tokens=1_000)
    assert cost.cost_status == "unknown"
    assert cost.input_cost is None and cost.total_cost is None


def test_source_and_effective_date_exposed(catalog) -> None:
    p = catalog.get("claude-opus-4-8").pricing
    cost = resolve_cost(p, input_tokens=100, output_tokens=100)
    assert cost.effective_date == "2026-06-15"
    assert cost.pricing_source is not None


def test_compute_model_cost_by_key(catalog) -> None:
    from telic.pricing import compute_model_cost
    from telic.providers.types import Usage
    usage = Usage(input_tokens=100_000, output_tokens=100_000)
    cost = compute_model_cost("gpt-5.5", usage)
    assert cost.cost_status == "complete"
    assert cost.input_cost == pytest.approx(0.5)


def test_compute_model_cost_provider_batch(catalog) -> None:
    from telic.pricing import compute_model_cost
    from telic.providers.types import Usage
    usage = Usage(input_tokens=100_000, output_tokens=100_000)
    cost = compute_model_cost("gpt-5.5", usage, mode="provider_batch")
    assert cost.input_cost == pytest.approx(100_000 * 2.5 / 1_000_000)


def test_openai_cached_input_metric_is_resolved(catalog) -> None:
    pricing = catalog.get("gpt-5-mini").pricing

    cost = resolve_cost(
        pricing,
        input_tokens=1_000_000,
        cache_read_tokens=500_000,
        output_tokens=100_000,
    )

    assert cost.cost_status == "complete"
    assert cost.input_cost == pytest.approx(0.125)
    assert cost.cache_read_cost == pytest.approx(0.0125)
    assert cost.output_cost == pytest.approx(0.2)
    assert cost.total_cost == pytest.approx(0.3375)


def test_decimal_resolver_preserves_exact_cost_and_other_units(catalog) -> None:
    from dataclasses import replace

    from telic.model_catalog import Pricing, PricingDimension

    base = catalog.get("gpt-5-mini").pricing
    assert base is not None
    pricing = replace(
        base,
        dimensions=base.dimensions
        + (
            PricingDimension(metric="request", unit="request", rate=0.01),
        ),
    )

    cost = resolve_cost_decimal(
        pricing,
        input_tokens=1_000_000,
        cache_read_tokens=500_000,
        output_tokens=100_000,
        other_billed_units={"request": Decimal("2")},
    )

    assert isinstance(pricing, Pricing)
    assert cost.cost_status == "complete"
    assert cost.input_cost == Decimal("0.125")
    assert cost.cache_read_cost == Decimal("0.0125")
    assert cost.output_cost == Decimal("0.2")
    assert cost.other_costs == (("request", Decimal("0.02")),)
    assert cost.total_cost == Decimal("0.3575")


def test_decimal_resolver_never_prices_unknown_other_units_as_zero(catalog) -> None:
    cost = resolve_cost_decimal(
        catalog.get("gpt-5-mini").pricing,
        input_tokens=100,
        output_tokens=50,
        other_billed_units={"request": Decimal("1")},
    )

    assert cost.cost_status == "partial"
    assert cost.total_cost is None
    assert cost.missing == ("request",)
