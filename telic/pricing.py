"""Multidimensional pricing resolver (Phase 5).

Computes cost from a model's catalog v2 pricing dimensions and actual usage, selecting
rates by execution mode, service tier, region, and long-context threshold. Unknown rates
(``rate is None``) are never treated as zero: the result carries an explicit
``cost_status`` (``complete`` | ``partial`` | ``unknown``) and the list of missing
dimensions.

Provider batch discounts apply only when ``mode == "provider_batch"`` (an actual provider
Batch API result), never to local concurrency (Architecture Decision 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .model_catalog import Pricing, PricingDimension

_MILLION = Decimal(1_000_000)

# Execution modes -> the pricing-dimension ``mode`` they bill at.
_MODE_TO_DIMENSION_MODE = {
    "standard": "standard",
    "concurrent": "standard",  # local concurrency bills at standard (no batch discount)
    "provider_batch": "batch",
}


@dataclass(frozen=True)
class ResolvedCost:
    input_cost: float | None = None
    output_cost: float | None = None
    cache_read_cost: float | None = None
    cache_write_cost: float | None = None
    total_cost: float | None = None
    cost_status: str = "unknown"  # complete | partial | unknown
    missing: tuple[str, ...] = ()
    currency: str = "USD"
    effective_date: str | None = None
    pricing_source: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "cache_read_cost": self.cache_read_cost,
            "cache_write_cost": self.cache_write_cost,
            "total_cost": self.total_cost,
            "cost_status": self.cost_status,
            "missing": list(self.missing),
            "currency": self.currency,
            "effective_date": self.effective_date,
            "pricing_source": dict(self.pricing_source) if self.pricing_source else None,
        }


@dataclass(frozen=True)
class ResolvedDecimalCost:
    """Exact monetary result for persistence and reconciliation."""

    input_cost: Decimal | None = None
    output_cost: Decimal | None = None
    cache_read_cost: Decimal | None = None
    cache_write_cost: Decimal | None = None
    other_costs: tuple[tuple[str, Decimal], ...] = ()
    total_cost: Decimal | None = None
    cost_status: str = "unknown"
    missing: tuple[str, ...] = ()
    currency: str = "USD"
    effective_date: str | None = None
    pricing_source: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "cache_read_cost": self.cache_read_cost,
            "cache_write_cost": self.cache_write_cost,
            "other_costs": dict(self.other_costs),
            "total_cost": self.total_cost,
            "cost_status": self.cost_status,
            "missing": list(self.missing),
            "currency": self.currency,
            "effective_date": self.effective_date,
            "pricing_source": dict(self.pricing_source) if self.pricing_source else None,
        }


def _dimension_matches(
    dim: PricingDimension,
    *,
    metric: str,
    mode: str,
    tier: str | None,
    speed: str | None,
    region: str | None,
    tokens: int,
) -> bool:
    if dim.metric != metric or dim.mode != mode:
        return False
    # tier: a dimension with tier=None applies to any/standard tier.
    if dim.tier is not None and dim.tier != tier:
        return False
    if dim.speed is not None and dim.speed != speed:
        return False
    # region: a dimension with region=None/"default" applies unless a specific region asked.
    if dim.region not in (None, "default") and dim.region != region:
        return False
    # threshold band (e.g. long-context > N tokens).
    if dim.threshold is not None:
        lo = dim.threshold.get("min_tokens")
        hi = dim.threshold.get("max_tokens")
        if lo is not None and tokens < lo:
            return False
        if hi is not None and tokens > hi:
            return False
    return True


def _select_dimension(
    pricing: Pricing,
    *,
    metric: str,
    mode: str,
    tier: str | None,
    speed: str | None,
    region: str | None,
    tokens: int,
) -> PricingDimension | None:
    """Most specific matching dimension wins."""
    candidates = [
        d for d in pricing.dimensions
        if _dimension_matches(
            d,
            metric=metric,
            mode=mode,
            tier=tier,
            speed=speed,
            region=region,
            tokens=tokens,
        )
    ]
    if not candidates:
        return None

    def specificity(d: PricingDimension) -> int:
        return (
            (1 if d.threshold is not None else 0)
            + (1 if d.region not in (None, "default") else 0)
            + (1 if d.tier is not None else 0)
            + (1 if d.speed is not None else 0)
        )

    return max(candidates, key=specificity)


def _rate_for(
    pricing: Pricing,
    *,
    metric: str,
    mode: str,
    tier: str | None,
    speed: str | None,
    region: str | None,
    tokens: int,
) -> tuple[float | None, bool]:
    """Return ``(per_token_rate_or_None, dimension_present)``.

    ``dimension_present`` is False when the catalog has no dimension at all for this
    metric/selection, True when a dimension exists (even if its rate is unknown/None).
    """
    dim = _select_dimension(
        pricing,
        metric=metric,
        mode=mode,
        tier=tier,
        speed=speed,
        region=region,
        tokens=tokens,
    )
    if dim is None:
        return None, False
    if dim.rate is None:
        return None, True
    rate = Decimal(str(dim.rate))
    per_token = float(rate / _MILLION) if dim.unit == "million_tokens" else float(rate)
    return per_token, True


def _decimal_cost_for(
    pricing: Pricing,
    *,
    metrics: tuple[str, ...],
    mode: str,
    tier: str | None,
    speed: str | None,
    region: str | None,
    quantity: Decimal,
    threshold_tokens: int,
) -> tuple[Decimal | None, bool]:
    dimension = None
    for metric in metrics:
        dimension = _select_dimension(
            pricing,
            metric=metric,
            mode=mode,
            tier=tier,
            speed=speed,
            region=region,
            tokens=threshold_tokens,
        )
        if dimension is not None:
            break
    if dimension is None:
        return None, False
    if dimension.rate is None:
        return None, True
    rate = Decimal(str(dimension.rate))
    if dimension.unit == "million_tokens":
        return quantity * rate / _MILLION, True
    return quantity * rate, True


def resolve_cost_decimal(
    pricing: Pricing | None,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_ttl: str = "5m",
    mode: str = "standard",
    tier: str | None = None,
    speed: str | None = None,
    region: str | None = None,
    regional_uplift: Decimal | str | float | None = None,
    other_billed_units: dict[str, Decimal | int] | None = None,
) -> ResolvedDecimalCost:
    """Resolve catalog pricing without crossing a binary floating-point boundary."""

    billed_units = dict(other_billed_units or {})
    if pricing is None or not pricing.dimensions:
        missing = ["input", "output"]
        if cache_read_tokens:
            missing.append("cached_input")
        if cache_creation_tokens:
            missing.append("cache_write_1h" if cache_ttl == "1h" else "cache_write_5m")
        missing.extend(metric for metric, quantity in billed_units.items() if quantity)
        return ResolvedDecimalCost(cost_status="unknown", missing=tuple(missing))

    dim_mode = _MODE_TO_DIMENSION_MODE.get(mode, "standard")
    uncached_input = max(0, input_tokens - cache_read_tokens)
    missing: list[str] = []

    input_cost, _ = _decimal_cost_for(
        pricing,
        metrics=("input",),
        mode=dim_mode,
        tier=tier,
        speed=speed,
        region=region,
        quantity=Decimal(uncached_input),
        threshold_tokens=input_tokens,
    )
    output_cost, _ = _decimal_cost_for(
        pricing,
        metrics=("output",),
        mode=dim_mode,
        tier=tier,
        speed=speed,
        region=region,
        quantity=Decimal(max(0, output_tokens)),
        threshold_tokens=output_tokens,
    )
    if input_cost is None:
        missing.append("input")
    if output_cost is None:
        missing.append("output")

    cache_read_cost: Decimal | None = Decimal("0")
    if cache_read_tokens:
        cache_read_cost, _ = _decimal_cost_for(
            pricing,
            metrics=("cache_read", "cached_input"),
            mode=dim_mode,
            tier=tier,
            speed=speed,
            region=region,
            quantity=Decimal(max(0, cache_read_tokens)),
            threshold_tokens=cache_read_tokens,
        )
        if cache_read_cost is None:
            missing.append("cached_input")

    cache_write_cost: Decimal | None = Decimal("0")
    if cache_creation_tokens:
        cache_metric = "cache_write_1h" if cache_ttl == "1h" else "cache_write_5m"
        cache_write_cost, _ = _decimal_cost_for(
            pricing,
            metrics=(cache_metric,),
            mode=dim_mode,
            tier=tier,
            speed=speed,
            region=region,
            quantity=Decimal(max(0, cache_creation_tokens)),
            threshold_tokens=cache_creation_tokens,
        )
        if cache_write_cost is None:
            missing.append(cache_metric)

    other_costs: list[tuple[str, Decimal]] = []
    for metric, raw_quantity in sorted(billed_units.items()):
        quantity = Decimal(str(raw_quantity))
        if not quantity.is_finite() or quantity < 0:
            raise ValueError("other billed units must be finite and non-negative")
        if not quantity:
            other_costs.append((metric, Decimal("0")))
            continue
        cost, _ = _decimal_cost_for(
            pricing,
            metrics=(metric,),
            mode=dim_mode,
            tier=tier,
            speed=speed,
            region=region,
            quantity=quantity,
            threshold_tokens=int(quantity),
        )
        if cost is None:
            missing.append(metric)
        else:
            other_costs.append((metric, cost))

    parts = [input_cost, output_cost, cache_read_cost, cache_write_cost]
    parts.extend(cost for _, cost in other_costs)
    total: Decimal | None
    if any(part is None for part in parts) or missing:
        total = None
    else:
        total = sum((part for part in parts if part is not None), Decimal("0"))
        if regional_uplift is not None:
            uplift = Decimal(str(regional_uplift))
            if not uplift.is_finite() or uplift < 0:
                raise ValueError("regional uplift must be finite and non-negative")
            total *= uplift

    any_known = any(part is not None for part in parts)
    if not missing:
        status = "complete"
    elif any_known:
        status = "partial"
    else:
        status = "unknown"

    return ResolvedDecimalCost(
        input_cost=input_cost,
        output_cost=output_cost,
        cache_read_cost=cache_read_cost,
        cache_write_cost=cache_write_cost,
        other_costs=tuple(other_costs),
        total_cost=total,
        cost_status=status,
        missing=tuple(missing),
        currency=pricing.currency,
        effective_date=pricing.effective_date,
        pricing_source=dict(pricing.source) if pricing.source else None,
    )


def resolve_cost(
    pricing: Pricing | None,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_ttl: str = "5m",
    mode: str = "standard",
    tier: str | None = None,
    speed: str | None = None,
    region: str | None = None,
    regional_uplift: float | None = None,
) -> ResolvedCost:
    """Resolve cost from catalog v2 pricing dimensions and usage.

    ``mode`` is the execution mode (``standard`` / ``concurrent`` / ``provider_batch``).
    Only ``provider_batch`` bills at batch rates. ``cache_read_tokens`` are billed against
    the ``cache_read`` metric and discounted off the (uncached) input. Unknown required
    rates yield ``partial``/``unknown`` status and never a fabricated zero.
    """
    if pricing is None or not pricing.dimensions:
        return ResolvedCost(cost_status="unknown", missing=("input", "output"))

    dim_mode = _MODE_TO_DIMENSION_MODE.get(mode, "standard")
    uncached_input = max(0, input_tokens - cache_read_tokens)
    missing: list[str] = []

    input_rate, _ = _rate_for(
        pricing,
        metric="input",
        mode=dim_mode,
        tier=tier,
        speed=speed,
        region=region,
        tokens=input_tokens,
    )
    output_rate, _ = _rate_for(
        pricing,
        metric="output",
        mode=dim_mode,
        tier=tier,
        speed=speed,
        region=region,
        tokens=output_tokens,
    )

    input_cost = None if input_rate is None else uncached_input * input_rate
    output_cost = None if output_rate is None else output_tokens * output_rate
    if input_rate is None:
        missing.append("input")
    if output_rate is None:
        missing.append("output")

    cache_read_cost: float | None = 0.0
    if cache_read_tokens:
        cr_rate, dimension_present = _rate_for(
            pricing,
            metric="cache_read",
            mode=dim_mode,
            tier=tier,
            speed=speed,
            region=region,
            tokens=cache_read_tokens,
        )
        if not dimension_present:
            cr_rate, _ = _rate_for(
                pricing,
                metric="cached_input",
                mode=dim_mode,
                tier=tier,
                speed=speed,
                region=region,
                tokens=cache_read_tokens,
            )
        if cr_rate is None:
            cache_read_cost = None
            missing.append("cache_read")
        else:
            cache_read_cost = cache_read_tokens * cr_rate

    cache_write_cost: float | None = 0.0
    if cache_creation_tokens:
        metric = "cache_write_1h" if cache_ttl == "1h" else "cache_write_5m"
        cw_rate, _ = _rate_for(
            pricing,
            metric=metric,
            mode=dim_mode,
            tier=tier,
            speed=speed,
            region=region,
            tokens=cache_creation_tokens,
        )
        if cw_rate is None:
            cache_write_cost = None
            missing.append(metric)
        else:
            cache_write_cost = cache_creation_tokens * cw_rate

    parts = [input_cost, output_cost, cache_read_cost, cache_write_cost]
    known = [p for p in parts if p is not None]
    total: float | None
    if any(p is None for p in parts):
        # Required input/output unknown -> can't total honestly.
        total = None
    else:
        total = sum(known)
        if regional_uplift:
            total *= regional_uplift

    # Status keys off resolved rates: complete = nothing missing; partial = some known
    # and some unknown; unknown = nothing could be priced.
    any_known = input_cost is not None or output_cost is not None or bool(
        [p for p in (cache_read_cost, cache_write_cost) if p not in (None, 0.0)]
    )
    if not missing:
        status = "complete"
    elif any_known:
        status = "partial"
    else:
        status = "unknown"

    return ResolvedCost(
        input_cost=input_cost,
        output_cost=output_cost,
        cache_read_cost=cache_read_cost,
        cache_write_cost=cache_write_cost,
        total_cost=total,
        cost_status=status,
        missing=tuple(missing),
        currency=pricing.currency,
        effective_date=pricing.effective_date,
        pricing_source=dict(pricing.source) if pricing.source else None,
    )


def compute_model_cost(
    model: Any,
    usage: Any,
    *,
    mode: str = "standard",
    tier: str | None = None,
    speed: str | None = None,
    region: str | None = None,
    regional_uplift: float | None = None,
    cache_ttl: str = "5m",
) -> ResolvedCost:
    """Resolve cost for a model and a ``Usage`` via the catalog v2 pricing dimensions.

    ``model`` is a catalog key (resolved against the default catalog) or a
    ``ModelMetadata``. ``usage`` is any object exposing the token-count attributes.
    """
    from .model_catalog import ModelMetadata, get_default_model_catalog

    metadata = model if isinstance(model, ModelMetadata) else get_default_model_catalog().get(str(model))
    return resolve_cost(
        metadata.pricing,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0),
        cache_ttl=cache_ttl,
        mode=mode,
        tier=tier,
        speed=speed,
        region=region,
        regional_uplift=regional_uplift,
    )


__all__ = [
    "ResolvedCost",
    "ResolvedDecimalCost",
    "resolve_cost",
    "resolve_cost_decimal",
    "compute_model_cost",
]
