"""Canonical major movement through an ordered candle price path.

The position of each global extreme comes from the supplied intrabar sequence,
never from an OHLC-only reconstruction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .movements import PriceLeg, get_price_legs


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
