from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.candles import Candle
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
)
from trading.definitions.pullback_structure import (
    BMSObservation,
    BMSResult,
    PullbackContext,
    PullbackStructureStatus,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def uptrend_context(*, segment: MarketSegment = MarketSegment(0, 3), origin: StructurePoint = low(1, 90.0), previous: StructurePoint = high(3, 110.0), pullback: StructurePoint = low(4, 100.0)) -> PullbackContext:
    return PullbackContext(segment, MarketState.UPTREND, origin, previous, pullback)


def downtrend_context(*, segment: MarketSegment = MarketSegment(0, 3), origin: StructurePoint = high(2, 110.0), previous: StructurePoint = low(3, 90.0), pullback: StructurePoint = high(4, 100.0)) -> PullbackContext:
    return PullbackContext(segment, MarketState.DOWNTREND, origin, previous, pullback)


def test_pullback_status_values_are_stable() -> None:
    assert {status.value for status in PullbackStructureStatus} == {"pullback_only", "bms_confirmed", "not_a_pullback"}


def test_pullback_domain_records_preserve_supplied_values() -> None:
    context = uptrend_context()
    candle = Candle(100.0, 105.0, 95.0, 101.0)
    assert BMSObservation(5, candle) == BMSObservation(index=5, candle=candle)
    assert BMSResult(PullbackStructureStatus.PULLBACK_ONLY) == BMSResult(status=PullbackStructureStatus.PULLBACK_ONLY, broken_extreme=None, breakout_index=None)
    assert context.previous_extreme == high(3, 110.0)


@pytest.mark.parametrize("instance, attribute", [(uptrend_context(), "parent_state"), (BMSObservation(5, Candle(100.0, 105.0, 95.0, 101.0)), "index"), (BMSResult(PullbackStructureStatus.PULLBACK_ONLY), "status")])
def test_pullback_domain_records_are_frozen(instance: object, attribute: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, None)


def test_context_rejects_non_directional_parent_state() -> None:
    with pytest.raises(ValueError, match="directional"):
        PullbackContext(MarketSegment(0, 3), MarketState.NON_TREND, low(1, 90.0), high(3, 110.0), low(4, 100.0))


@pytest.mark.parametrize("state, origin, previous, pullback", [(MarketState.UPTREND, high(1, 90.0), high(3, 110.0), low(4, 100.0)), (MarketState.UPTREND, low(1, 90.0), low(3, 110.0), low(4, 100.0)), (MarketState.UPTREND, low(1, 90.0), high(3, 110.0), high(4, 100.0)), (MarketState.DOWNTREND, low(1, 110.0), low(3, 90.0), high(4, 100.0)), (MarketState.DOWNTREND, high(1, 110.0), high(3, 90.0), high(4, 100.0)), (MarketState.DOWNTREND, high(1, 110.0), low(3, 90.0), low(4, 100.0))])
def test_context_rejects_wrong_directional_point_kinds(state: MarketState, origin: StructurePoint, previous: StructurePoint, pullback: StructurePoint) -> None:
    with pytest.raises(ValueError, match="point kinds"):
        PullbackContext(MarketSegment(0, 3), state, origin, previous, pullback)


@pytest.mark.parametrize("segment, origin, previous", [(MarketSegment(1, 3), low(0, 90.0), high(3, 110.0)), (MarketSegment(0, 2), low(1, 90.0), high(3, 110.0))])
def test_context_rejects_parent_points_outside_segment(segment: MarketSegment, origin: StructurePoint, previous: StructurePoint) -> None:
    with pytest.raises(ValueError, match="outside parent segment"):
        uptrend_context(segment=segment, origin=origin, previous=previous)


def test_context_requires_parent_segment_to_end_at_previous_extreme() -> None:
    with pytest.raises(ValueError, match="end at previous extreme"):
        uptrend_context(segment=MarketSegment(0, 4))


@pytest.mark.parametrize("origin, previous, pullback", [(low(3, 90.0), high(3, 110.0), low(4, 100.0)), (low(1, 90.0), high(3, 110.0), low(3, 100.0))])
def test_context_rejects_invalid_chronology(origin: StructurePoint, previous: StructurePoint, pullback: StructurePoint) -> None:
    segment = MarketSegment(0, previous.index)
    with pytest.raises(ValueError, match="chronology"):
        uptrend_context(segment=segment, origin=origin, previous=previous, pullback=pullback)


@pytest.mark.parametrize("context_factory", [lambda: uptrend_context(origin=low(1, 110.0)), lambda: uptrend_context(origin=low(1, 111.0)), lambda: downtrend_context(origin=high(2, 90.0)), lambda: downtrend_context(origin=high(2, 89.0))])
def test_context_rejects_incoherent_origin_and_extreme_prices(context_factory: object) -> None:
    with pytest.raises(ValueError, match="boundary prices"):
        context_factory()  # type: ignore[operator]
