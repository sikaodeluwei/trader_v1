from trading.definitions.candles import Candle
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    classify_market_state,
)
from trading.definitions.pullback_structure import (
    BMSObservation,
    PullbackContext,
    PullbackStructureStatus,
    evaluate_bms,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def observed(index: int, *, high_price: float, low_price: float) -> BMSObservation:
    midpoint = (high_price + low_price) / 2
    return BMSObservation(
        index,
        Candle(midpoint, high_price, low_price, midpoint),
    )


def classified_uptrend_context(
    *,
    pullback: StructurePoint = low(4, 100.0),
) -> PullbackContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 100.0),
        low(1, 90.0),
        low(2, 95.0),
        high(3, 110.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.UPTREND
    return PullbackContext(
        segment,
        parent_state,
        trend_origin=low(2, 95.0),
        previous_extreme=high(3, 110.0),
        pullback_extreme=pullback,
    )


def classified_downtrend_context() -> PullbackContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 110.0),
        low(1, 100.0),
        high(2, 105.0),
        low(3, 90.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.DOWNTREND
    return PullbackContext(
        segment,
        parent_state,
        trend_origin=high(2, 105.0),
        previous_extreme=low(3, 90.0),
        pullback_extreme=high(4, 100.0),
    )


def test_classified_uptrend_composes_with_confirmed_bms() -> None:
    context = classified_uptrend_context()
    observations = [observed(5, high_price=111.0, low_price=98.0)]

    assert evaluate_bms(context, observations).status is (
        PullbackStructureStatus.BMS_CONFIRMED
    )


def test_classified_downtrend_composes_with_confirmed_bms() -> None:
    context = classified_downtrend_context()
    observations = [observed(5, high_price=102.0, low_price=89.0)]

    assert evaluate_bms(context, observations).status is (
        PullbackStructureStatus.BMS_CONFIRMED
    )


def test_classified_parent_without_later_break_remains_pullback_only() -> None:
    context = classified_uptrend_context()
    observations = [observed(5, high_price=109.0, low_price=98.0)]

    assert evaluate_bms(context, observations).status is (
        PullbackStructureStatus.PULLBACK_ONLY
    )


def test_classified_parent_origin_invalidation_is_not_a_pullback() -> None:
    context = classified_uptrend_context(pullback=low(4, 94.0))

    assert evaluate_bms(context, ()).status is (
        PullbackStructureStatus.NOT_A_PULLBACK
    )
