"""Explicit Chapter 2 pullback and BMS structure definitions."""

from collections.abc import Sequence
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

    def __post_init__(self) -> None:
        has_break_details = (
            self.broken_extreme is not None and self.breakout_index is not None
        )
        has_partial_break_details = (
            self.broken_extreme is not None or self.breakout_index is not None
        )

        if (
            self.status is PullbackStructureStatus.BMS_CONFIRMED
            and not has_break_details
        ):
            raise ValueError("confirmed BMS requires broken extreme and breakout index")
        if (
            self.status is not PullbackStructureStatus.BMS_CONFIRMED
            and has_partial_break_details
        ):
            raise ValueError("non-BMS result cannot contain break details")


def _validate_observations(
    context: PullbackContext,
    observations: Sequence[BMSObservation],
) -> None:
    expected_index = context.pullback_extreme.index + 1
    for position, observation in enumerate(observations):
        if (
            position == 0
            and observation.index == context.pullback_extreme.index
        ):
            raise ValueError(
                "OHLC cannot determine same-candle pullback/BMS order"
            )
        if observation.index != expected_index:
            raise ValueError(
                "observations must use complete dense chronology after pullback"
            )
        expected_index += 1


def evaluate_bms(
    context: PullbackContext,
    observations: Sequence[BMSObservation],
) -> BMSResult:
    """Evaluate the first boundary event after one explicit pullback."""

    _validate_observations(context, observations)

    if context.parent_state is MarketState.UPTREND:
        no_pullback = (
            context.pullback_extreme.price >= context.previous_extreme.price
        )
        origin_invalidated = (
            context.pullback_extreme.price < context.trend_origin.price
        )
    else:
        no_pullback = (
            context.pullback_extreme.price <= context.previous_extreme.price
        )
        origin_invalidated = (
            context.pullback_extreme.price > context.trend_origin.price
        )

    if no_pullback or origin_invalidated:
        return BMSResult(PullbackStructureStatus.NOT_A_PULLBACK)

    for observation in observations:
        if context.parent_state is MarketState.UPTREND:
            origin_crossed = observation.candle.low < context.trend_origin.price
            bms_crossed = (
                observation.candle.high > context.previous_extreme.price
            )
        else:
            origin_crossed = observation.candle.high > context.trend_origin.price
            bms_crossed = observation.candle.low < context.previous_extreme.price

        if origin_crossed and bms_crossed:
            raise ValueError(
                "OHLC cannot determine the intrabar boundary order"
            )
        if origin_crossed:
            return BMSResult(PullbackStructureStatus.NOT_A_PULLBACK)
        if bms_crossed:
            return BMSResult(
                PullbackStructureStatus.BMS_CONFIRMED,
                broken_extreme=context.previous_extreme,
                breakout_index=observation.index,
            )

    return BMSResult(PullbackStructureStatus.PULLBACK_ONLY)
