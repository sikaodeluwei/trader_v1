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


@dataclass
class MovementSummary:
    """Measurements aggregated from an ordered sequence of price legs."""

    first_side: MovementSide | None
    first_distance: float
    final_side: MovementSide | None
    final_distance: float
    largest_buyer_move: float
    largest_seller_move: float
    total_buyer_movement: float
    total_seller_movement: float
    final_retracement_ratio: float | None


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


def summarize_movements(legs: Sequence[PriceLeg]) -> MovementSummary:
    """Aggregate measurable movement without interpreting market advantage.

    The final retracement ratio compares the final leg's distance with the
    immediately preceding opposing leg. It remains a raw measurement: no
    threshold or buyer/seller/none conclusion is applied.
    """

    if not legs:
        return MovementSummary(
            first_side=None,
            first_distance=0.0,
            final_side=None,
            final_distance=0.0,
            largest_buyer_move=0.0,
            largest_seller_move=0.0,
            total_buyer_movement=0.0,
            total_seller_movement=0.0,
            final_retracement_ratio=None,
        )

    largest_buyer_move = 0.0
    largest_seller_move = 0.0
    total_buyer_movement = 0.0
    total_seller_movement = 0.0

    for leg in legs:
        if leg.side is MovementSide.BUYER:
            largest_buyer_move = max(largest_buyer_move, leg.distance)
            total_buyer_movement += leg.distance
        else:
            largest_seller_move = max(largest_seller_move, leg.distance)
            total_seller_movement += leg.distance

    final_leg = legs[-1]
    final_retracement_ratio: float | None = None
    if len(legs) >= 2:
        previous_leg = legs[-2]
        if (
            previous_leg.side is not final_leg.side
            and previous_leg.distance != 0
        ):
            final_retracement_ratio = final_leg.distance / previous_leg.distance

    return MovementSummary(
        first_side=legs[0].side,
        first_distance=legs[0].distance,
        final_side=final_leg.side,
        final_distance=final_leg.distance,
        largest_buyer_move=largest_buyer_move,
        largest_seller_move=largest_seller_move,
        total_buyer_movement=total_buyer_movement,
        total_seller_movement=total_seller_movement,
        final_retracement_ratio=final_retracement_ratio,
    )
