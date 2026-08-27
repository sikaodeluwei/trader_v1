"""Integrated candle analysis from an authoritative intrabar price path.

This module composes existing measurements. It does not classify candle
archetypes, decide market advantage, or apply thresholds.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from .candles import (
    Candle,
    CandleControl,
    CandleGeometry,
    CandleSide,
    get_control,
    get_geometry,
    get_side,
)
from .extremes import (
    ExtremePath,
    ExtremePathEvidence,
    get_extreme_path,
    summarize_extreme_path,
)
from .movements import (
    MovementSummary,
    PriceLeg,
    get_price_legs,
    summarize_movements,
)


@dataclass
class CandleAnalysis:
    """Candle geometry and ordered movement measurements in one result."""

    candle: Candle
    side: CandleSide
    geometry: CandleGeometry
    control: CandleControl
    legs: list[PriceLeg]
    extreme_path: ExtremePath
    extreme_evidence: ExtremePathEvidence
    movements: MovementSummary


def analyze_prices(prices: Sequence[float]) -> CandleAnalysis:
    """Build a complete measurement set from ordered intrabar prices.

    The supplied order is authoritative. OHLC values are derived from that
    sequence, while existing candle and movement functions calculate each
    component of the result.

    Raises:
        ValueError: If fewer than two prices are supplied.
    """

    if len(prices) < 2:
        raise ValueError("analyze_prices requires at least two ordered prices")

    candle = Candle(
        open=prices[0],
        high=max(prices),
        low=min(prices),
        close=prices[-1],
    )
    legs = get_price_legs(prices)
    extreme_path = get_extreme_path(prices)

    return CandleAnalysis(
        candle=candle,
        side=get_side(candle),
        geometry=get_geometry(candle),
        control=get_control(candle),
        legs=legs,
        extreme_path=extreme_path,
        extreme_evidence=summarize_extreme_path(candle, extreme_path),
        movements=summarize_movements(legs),
    )
