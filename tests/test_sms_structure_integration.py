from trading.definitions.candles import Candle
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    classify_market_state,
)
from trading.definitions.sms_structure import (
    SMSContext,
    SMSObservation,
    SMSResult,
    SMSStructureStatus,
    evaluate_sms,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def observed(
    index: int,
    *,
    high_price: float,
    low_price: float,
) -> SMSObservation:
    midpoint = (high_price + low_price) / 2
    return SMSObservation(
        index,
        Candle(midpoint, high_price, low_price, midpoint),
    )


def classified_uptrend_context() -> SMSContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 100.0),
        low(1, 90.0),
        low(2, 95.0),
        high(3, 110.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.UPTREND
    return SMSContext(
        parent_segment=segment,
        parent_state=parent_state,
        trend_extreme=high(3, 110.0),
        creator_point=low(2, 95.0),
    )


def classified_downtrend_context() -> SMSContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 110.0),
        low(1, 100.0),
        high(2, 105.0),
        low(3, 90.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.DOWNTREND
    return SMSContext(
        parent_segment=segment,
        parent_state=parent_state,
        trend_extreme=low(3, 90.0),
        creator_point=high(2, 105.0),
    )


def test_classified_uptrend_composes_with_confirmed_sms() -> None:
    context = classified_uptrend_context()

    assert evaluate_sms(
        context,
        [observed(4, high_price=109.0, low_price=94.0)],
    ) == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=context.creator_point,
        event_index=4,
    )


def test_classified_downtrend_composes_with_confirmed_sms() -> None:
    context = classified_downtrend_context()

    assert evaluate_sms(
        context,
        [observed(4, high_price=106.0, low_price=91.0)],
    ) == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=context.creator_point,
        event_index=4,
    )


def test_classified_parent_without_boundary_break_remains_pullback_only() -> None:
    context = classified_uptrend_context()

    assert evaluate_sms(
        context,
        [
            observed(4, high_price=109.0, low_price=96.0),
            observed(5, high_price=110.0, low_price=95.0),
        ],
    ) == SMSResult(SMSStructureStatus.PULLBACK_ONLY)


def test_classified_parent_extreme_break_returns_parent_continued() -> None:
    context = classified_uptrend_context()

    assert evaluate_sms(
        context,
        [observed(4, high_price=111.0, low_price=96.0)],
    ) == SMSResult(
        SMSStructureStatus.PARENT_CONTINUED,
        broken_point=context.trend_extreme,
        event_index=4,
    )


def test_small_context_sms_does_not_infer_larger_context_sms() -> None:
    large_segment = MarketSegment(0, 7)
    large_points = [
        high(0, 100.0),
        low(1, 90.0),
        high(3, 110.0),
        low(4, 95.0),
        low(6, 105.0),
        high(7, 120.0),
    ]
    small_segment = MarketSegment(3, 7)
    small_points = [
        high(3, 110.0),
        low(4, 95.0),
        low(6, 105.0),
        high(7, 120.0),
    ]
    large_state = classify_market_state(large_segment, large_points)
    small_state = classify_market_state(small_segment, small_points)
    assert large_state is MarketState.UPTREND
    assert small_state is MarketState.UPTREND

    large_context = SMSContext(
        large_segment,
        large_state,
        trend_extreme=high(7, 120.0),
        creator_point=low(4, 95.0),
    )
    small_context = SMSContext(
        small_segment,
        small_state,
        trend_extreme=high(7, 120.0),
        creator_point=low(6, 105.0),
    )
    observation = observed(8, high_price=119.0, low_price=100.0)

    assert evaluate_sms(small_context, [observation]).status is (
        SMSStructureStatus.SMS_CONFIRMED
    )
    assert evaluate_sms(large_context, [observation]).status is (
        SMSStructureStatus.PULLBACK_ONLY
    )
