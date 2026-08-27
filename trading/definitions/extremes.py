"""Canonical major movement through an ordered candle price path.

The position of each global extreme comes from the supplied intrabar sequence,
never from an OHLC-only reconstruction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .candles import Candle
from .movements import MovementSide, PriceLeg, get_price_legs


class ExtremeOrder(Enum):
    """The observed order of a candle's global low and high."""

    LOW_THEN_HIGH = "low_then_high"
    HIGH_THEN_LOW = "high_then_low"
    FLAT = "flat"


@dataclass
class ExtremePath:
    """A simplified open/extreme/extreme/close movement path."""

    order: ExtremeOrder
    legs: list[PriceLeg]


@dataclass
class ExtremePathEvidence:
    """Normalized raw evidence from the canonical extreme path."""

    order: ExtremeOrder
    initial_side: MovementSide | None
    initial_distance: float
    initial_ratio: float
    main_side: MovementSide | None
    main_distance: float
    main_ratio: float
    final_side: MovementSide | None
    final_distance: float
    final_ratio: float
    signed_displacement: float
    displacement_ratio: float


def get_extreme_path(prices: Sequence[float]) -> ExtremePath:
    """Build the canonical path through the ordered global extremes.

    The first occurrence of each extreme determines whether the low or high
    happened first. Existing price-leg logic converts the canonical
    checkpoints into directional legs and omits zero-distance movements.

    Raises:
        ValueError: If the price sequence is empty.
    """

    if not prices:
        raise ValueError("get_extreme_path requires at least one ordered price")

    low = min(prices)
    high = max(prices)
    if low == high:
        return ExtremePath(order=ExtremeOrder.FLAT, legs=[])

    low_index = prices.index(low)
    high_index = prices.index(high)

    if low_index < high_index:
        order = ExtremeOrder.LOW_THEN_HIGH
        checkpoints = [prices[0], low, high, prices[-1]]
    else:
        order = ExtremeOrder.HIGH_THEN_LOW
        checkpoints = [prices[0], high, low, prices[-1]]

    return ExtremePath(order=order, legs=get_price_legs(checkpoints))


def summarize_extreme_path(
    candle: Candle,
    extreme_path: ExtremePath,
) -> ExtremePathEvidence:
    """Normalize the canonical initial, main, and final movements.

    Conceptual movements are derived from candle OHLC and the observed extreme
    order, not from fixed positions in ``extreme_path.legs``. This preserves
    their roles when zero-distance legs have been omitted. The measurements
    are raw fuzzy evidence and are not converted into advantage decisions.
    """

    total_range = candle.high - candle.low
    if total_range == 0 or extreme_path.order is ExtremeOrder.FLAT:
        return ExtremePathEvidence(
            order=extreme_path.order,
            initial_side=None,
            initial_distance=0.0,
            initial_ratio=0.0,
            main_side=None,
            main_distance=0.0,
            main_ratio=0.0,
            final_side=None,
            final_distance=0.0,
            final_ratio=0.0,
            signed_displacement=0.0,
            displacement_ratio=0.0,
        )

    if extreme_path.order is ExtremeOrder.LOW_THEN_HIGH:
        initial_side = MovementSide.SELLER
        initial_distance = candle.open - candle.low
        main_side = MovementSide.BUYER
        final_side = MovementSide.SELLER
        final_distance = candle.high - candle.close
    else:
        initial_side = MovementSide.BUYER
        initial_distance = candle.high - candle.open
        main_side = MovementSide.SELLER
        final_side = MovementSide.BUYER
        final_distance = candle.close - candle.low

    main_distance = total_range
    signed_displacement = candle.close - candle.open

    return ExtremePathEvidence(
        order=extreme_path.order,
        initial_side=initial_side if initial_distance != 0 else None,
        initial_distance=initial_distance,
        initial_ratio=initial_distance / total_range,
        main_side=main_side,
        main_distance=main_distance,
        main_ratio=main_distance / total_range,
        final_side=final_side if final_distance != 0 else None,
        final_distance=final_distance,
        final_ratio=final_distance / total_range,
        signed_displacement=signed_displacement,
        displacement_ratio=signed_displacement / total_range,
    )
