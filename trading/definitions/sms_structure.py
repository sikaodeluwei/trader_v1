"""Explicit Chapter 2 SMS reversal-structure definitions."""

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


class SMSStructureStatus(Enum):
    """Outcome of evaluating one explicit SMS context."""

    PENDING = "pending"
    PULLBACK_ONLY = "pullback_only"
    SMS_CONFIRMED = "sms_confirmed"
    PARENT_CONTINUED = "parent_continued"


@dataclass(frozen=True)
class SMSContext:
    """Explicit creator and extreme boundaries for one directional trend."""

    parent_segment: MarketSegment
    parent_state: MarketState
    trend_extreme: StructurePoint
    creator_point: StructurePoint

    def __post_init__(self) -> None:
        if self.parent_state not in {MarketState.UPTREND, MarketState.DOWNTREND}:
            raise ValueError("parent_state must be directional")

        expected_kinds = (
            (StructurePointKind.HIGH, StructurePointKind.LOW)
            if self.parent_state is MarketState.UPTREND
            else (StructurePointKind.LOW, StructurePointKind.HIGH)
        )
        actual_kinds = (self.trend_extreme.kind, self.creator_point.kind)
        if actual_kinds != expected_kinds:
            raise ValueError("structure point kinds do not match parent direction")

        for point in (self.creator_point, self.trend_extreme):
            if not (
                self.parent_segment.start_index
                <= point.index
                <= self.parent_segment.end_index
            ):
                raise ValueError("SMS boundary is outside parent segment")

        if self.parent_segment.end_index != self.trend_extreme.index:
            raise ValueError("parent segment must end at trend extreme")

        if not self.creator_point.index < self.trend_extreme.index:
            raise ValueError("SMS context chronology is invalid")

        coherent_prices = (
            self.creator_point.price < self.trend_extreme.price
            if self.parent_state is MarketState.UPTREND
            else self.creator_point.price > self.trend_extreme.price
        )
        if not coherent_prices:
            raise ValueError("creator and trend-extreme boundary prices conflict")


@dataclass(frozen=True)
class SMSObservation:
    """One OHLC candle at a dense ordinal position after the trend extreme."""

    index: int
    candle: Candle


@dataclass(frozen=True)
class SMSResult:
    """SMS-layer status and terminal boundary details when present."""

    status: SMSStructureStatus
    broken_point: StructurePoint | None = None
    event_index: int | None = None

    def __post_init__(self) -> None:
        is_terminal = self.status in {
            SMSStructureStatus.SMS_CONFIRMED,
            SMSStructureStatus.PARENT_CONTINUED,
        }
        has_all_event_fields = (
            self.broken_point is not None and self.event_index is not None
        )
        has_any_event_field = (
            self.broken_point is not None or self.event_index is not None
        )

        if is_terminal and not has_all_event_fields:
            raise ValueError(
                "terminal SMS result requires broken point and event index"
            )
        if not is_terminal and has_any_event_field:
            raise ValueError("non-terminal SMS result cannot contain event details")


def _validate_observations(
    context: SMSContext,
    observations: Sequence[SMSObservation],
) -> None:
    expected_index = context.trend_extreme.index + 1
    for observation in observations:
        if observation.index != expected_index:
            raise ValueError(
                "observations must use complete dense chronology after trend extreme"
            )
        expected_index += 1


def evaluate_sms(
    context: SMSContext,
    observations: Sequence[SMSObservation],
) -> SMSResult:
    """Evaluate the first boundary event for one explicit SMS context."""

    _validate_observations(context, observations)

    if not observations:
        return SMSResult(SMSStructureStatus.PENDING)

    for observation in observations:
        if context.parent_state is MarketState.UPTREND:
            sms_crossed = observation.candle.low < context.creator_point.price
            continuation_crossed = (
                observation.candle.high > context.trend_extreme.price
            )
        else:
            sms_crossed = observation.candle.high > context.creator_point.price
            continuation_crossed = (
                observation.candle.low < context.trend_extreme.price
            )

        if sms_crossed and continuation_crossed:
            raise ValueError(
                "OHLC cannot determine the intrabar boundary order"
            )
        if sms_crossed:
            return SMSResult(
                SMSStructureStatus.SMS_CONFIRMED,
                broken_point=context.creator_point,
                event_index=observation.index,
            )
        if continuation_crossed:
            return SMSResult(
                SMSStructureStatus.PARENT_CONTINUED,
                broken_point=context.trend_extreme,
                event_index=observation.index,
            )

    return SMSResult(SMSStructureStatus.PULLBACK_ONLY)
