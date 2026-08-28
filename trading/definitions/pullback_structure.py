"""Explicit Chapter 2 pullback and BMS structure definitions."""

from dataclasses import dataclass
from enum import Enum

from .candles import Candle
from .market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
)


class PullbackStructureStatus(Enum):
    """Course-defined result of evaluating one explicit pullback context."""

    PULLBACK_ONLY = "pullback_only"
    BMS_CONFIRMED = "bms_confirmed"
    NOT_A_PULLBACK = "not_a_pullback"


@dataclass(frozen=True)
class PullbackContext:
    """Explicit parent-trend boundaries and the later pullback extreme."""

    parent_segment: MarketSegment
    parent_state: MarketState
    trend_origin: StructurePoint
    previous_extreme: StructurePoint
    pullback_extreme: StructurePoint

    def __post_init__(self) -> None:
        if self.parent_state not in {MarketState.UPTREND, MarketState.DOWNTREND}:
            raise ValueError("parent_state must be directional")

        expected_kinds = (
            (StructurePointKind.LOW, StructurePointKind.HIGH, StructurePointKind.LOW)
            if self.parent_state is MarketState.UPTREND
            else (StructurePointKind.HIGH, StructurePointKind.LOW, StructurePointKind.HIGH)
        )
        actual_kinds = (
            self.trend_origin.kind,
            self.previous_extreme.kind,
            self.pullback_extreme.kind,
        )
        if actual_kinds != expected_kinds:
            raise ValueError("structure point kinds do not match parent direction")

        for point in (self.trend_origin, self.previous_extreme):
            if not self.parent_segment.start_index <= point.index <= self.parent_segment.end_index:
                raise ValueError("parent structure point is outside parent segment")

        if self.parent_segment.end_index != self.previous_extreme.index:
            raise ValueError("parent segment must end at previous extreme")

        if not self.trend_origin.index < self.previous_extreme.index < self.pullback_extreme.index:
            raise ValueError("pullback context chronology is invalid")

        coherent_prices = (
            self.trend_origin.price < self.previous_extreme.price
            if self.parent_state is MarketState.UPTREND
            else self.trend_origin.price > self.previous_extreme.price
        )
        if not coherent_prices:
            raise ValueError("trend origin and previous extreme boundary prices conflict")


@dataclass(frozen=True)
class BMSObservation:
    """One OHLC candle at a dense ordinal position after the pullback."""

    index: int
    candle: Candle


@dataclass(frozen=True)
class BMSResult:
    """The course outcome and BMS details when a break is confirmed."""

    status: PullbackStructureStatus
    broken_extreme: StructurePoint | None = None
    breakout_index: int | None = None
