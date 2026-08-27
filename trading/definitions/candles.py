"""Candle data, geometry, archetypes, and trading-side interpretations.

OHLC values produce exact candle geometry. Mapping geometry and ordered
intrabar price movement to one of the 16 visual archetypes is intentionally
deferred until the fuzzy shapes have been calibrated.
"""

from dataclasses import dataclass
from enum import Enum


@dataclass
class Candle:
    """A single market candle represented by open, high, low, and close."""

    open: float
    high: float
    low: float
    close: float


@dataclass
class CandleGeometry:
    """Normalized measurements that describe a candle's shape."""

    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    open_position: float
    close_position: float


class CandleSide(Enum):
    """The direction of the candle body, also called its color."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    DOJI = "doji"


class Advantage(Enum):
    """Which market side clearly prevailed within the candle archetype.

    Advantage is context for a future strategy, not a BUY or SELL signal.
    Strategies must combine it with information such as market structure,
    support and resistance, ranges, breakouts, and retests.
    """

    BUYER = "buyer"
    SELLER = "seller"
    NONE = "none"


class CandleType(Enum):
    """The 16 currently defined visual/fuzzy candle archetypes."""

    BULL_1 = "bull_1"
    BULL_2 = "bull_2"
    BULL_3 = "bull_3"
    BULL_4 = "bull_4"
    BULL_5 = "bull_5"
    BULL_6 = "bull_6"
    BULL_7 = "bull_7"
    BULL_8 = "bull_8"

    BEAR_1 = "bear_1"
    BEAR_2 = "bear_2"
    BEAR_3 = "bear_3"
    BEAR_4 = "bear_4"
    BEAR_5 = "bear_5"
    BEAR_6 = "bear_6"
    BEAR_7 = "bear_7"
    BEAR_8 = "bear_8"


_ADVANTAGE_BY_CANDLE_TYPE: dict[CandleType, Advantage] = {
    CandleType.BULL_1: Advantage.BUYER,
    CandleType.BULL_2: Advantage.BUYER,
    CandleType.BULL_3: Advantage.BUYER,
    CandleType.BULL_4: Advantage.SELLER,
    CandleType.BULL_5: Advantage.BUYER,
    CandleType.BULL_6: Advantage.NONE,
    CandleType.BULL_7: Advantage.NONE,
    CandleType.BULL_8: Advantage.NONE,
    CandleType.BEAR_1: Advantage.SELLER,
    CandleType.BEAR_2: Advantage.SELLER,
    CandleType.BEAR_3: Advantage.SELLER,
    CandleType.BEAR_4: Advantage.SELLER,
    CandleType.BEAR_5: Advantage.BUYER,
    CandleType.BEAR_6: Advantage.NONE,
    CandleType.BEAR_7: Advantage.NONE,
    CandleType.BEAR_8: Advantage.NONE,
}


def get_geometry(candle: Candle) -> CandleGeometry:
    """Calculate normalized candle geometry directly from OHLC values.

    The ratios describe candle shape independently of its absolute price size,
    which allows equally shaped candles at different price scales to be
    compared. A zero-range candle has no measurable body or wicks; its open
    and close use the neutral midpoint because no position within the range
    exists.
    """

    total_range = candle.high - candle.low
    if total_range == 0:
        return CandleGeometry(
            body_ratio=0.0,
            upper_wick_ratio=0.0,
            lower_wick_ratio=0.0,
            open_position=0.5,
            close_position=0.5,
        )

    body = abs(candle.close - candle.open)
    upper_wick = candle.high - max(candle.open, candle.close)
    lower_wick = min(candle.open, candle.close) - candle.low

    return CandleGeometry(
        body_ratio=body / total_range,
        upper_wick_ratio=upper_wick / total_range,
        lower_wick_ratio=lower_wick / total_range,
        open_position=(candle.open - candle.low) / total_range,
        close_position=(candle.close - candle.low) / total_range,
    )


def get_side(candle: Candle) -> CandleSide:
    """Return bullish/阳线, bearish/阴线, or doji from open and close.

    Candle side (or color) does not automatically identify which market side
    had the advantage; wick rejection and the full archetype also matter.
    """

    if candle.close > candle.open:
        return CandleSide.BULLISH
    if candle.close < candle.open:
        return CandleSide.BEARISH
    return CandleSide.DOJI


def get_advantage(candle_type: CandleType) -> Advantage:
    """Return the defined market advantage for a candle archetype."""

    return _ADVANTAGE_BY_CANDLE_TYPE[candle_type]


def classify_candle(candle: Candle) -> CandleType:
    """Classify a candle once the visual/fuzzy archetypes are calibrated.

    Exact percentage cutoffs are deliberately not guessed here. A future
    calibrated or learned classifier may combine exact ``CandleGeometry``
    measurements with ordered intrabar price movement and map that evidence
    to a ``CandleType``.
    """

    raise NotImplementedError(
        "Candle classification is unavailable until the visual/fuzzy "
        "archetypes have been calibrated."
    )
