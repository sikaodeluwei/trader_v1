"""Ordered buyer and seller movement legs within a single candle.

This module measures an observed intrabar price path. It does not reconstruct
price order from OHLC values and does not decide candle type or market
advantage.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class MovementSide(Enum):
    """The side responsible for one directional price movement."""

    BUYER = "buyer"
    SELLER = "seller"


@dataclass
class PriceLeg:
    """One continuous movement in a single direction."""

    side: MovementSide
    start_price: float
    end_price: float
    distance: float


def get_price_legs(prices: Sequence[float]) -> list[PriceLeg]:
    """Split an ordered intrabar price sequence into directional legs.

    Rising prices form buyer legs and falling prices form seller legs.
    Unchanged prices are ignored, while consecutive moves in the same
    direction remain part of one leg. The sequence order is authoritative;
    no path is inferred from candle OHLC geometry.
    """

    if len(prices) < 2:
        return []

    legs: list[PriceLeg] = []
    current_leg: PriceLeg | None = None
    previous_price = prices[0]

    for price in prices[1:]:
        if price == previous_price:
            continue

        movement_side = (
            MovementSide.BUYER
            if price > previous_price
            else MovementSide.SELLER
        )

        if current_leg is None or current_leg.side is not movement_side:
            if current_leg is not None:
                legs.append(current_leg)
            current_leg = PriceLeg(
                side=movement_side,
                start_price=previous_price,
                end_price=price,
                distance=abs(price - previous_price),
            )
        else:
            current_leg.end_price = price
            current_leg.distance = abs(price - current_leg.start_price)

        previous_price = price

    if current_leg is not None:
        legs.append(current_leg)

    return legs
