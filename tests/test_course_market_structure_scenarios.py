"""Human-labelled Chapter 2 scenarios for the Lesson 8 validation gate."""

import pytest

from trading.definitions.candles import Candle
from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    confirm_isolated_point_with_deformation,
)
from trading.definitions.isolated_points import (
    IsolatedPointKind,
    detect_confirmed_isolated_point,
    get_potential_isolated_point,
)
from trading.definitions.long_term_structure import (
    LongTermPoint,
    build_long_term_structure,
)
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    classify_market_state,
)
from trading.definitions.medium_term_structure import (
    MediumTermPoint,
    build_medium_term_structure,
)
from trading.definitions.pullback_structure import (
    BMSObservation,
    PullbackContext,
    PullbackStructureStatus,
    evaluate_bms,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)
from trading.definitions.sms_structure import (
    SMSContext,
    SMSObservation,
    SMSStructureStatus,
    evaluate_sms,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def candle(high_price: float, low_price: float) -> Candle:
    midpoint = (high_price + low_price) / 2
    return Candle(midpoint, high_price, low_price, midpoint)


def classified_uptrend() -> tuple[
    MarketSegment,
    MarketState,
    list[StructurePoint],
]:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 100.0),
        low(1, 90.0),
        low(2, 95.0),
        high(3, 110.0),
    ]
    state = classify_market_state(segment, points)
    assert state is MarketState.UPTREND
    return segment, state, points


def strict_short_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> ShortTermPoint:
    if kind is IsolatedPointKind.HIGH:
        left = candle(price - 2.0, price - 10.0)
        middle = candle(price, price - 8.0)
        right = candle(price - 1.0, price - 9.0)
    else:
        left = candle(price + 10.0, price + 2.0)
        middle = candle(price + 8.0, price)
        right = candle(price + 9.0, price + 1.0)

    point = detect_confirmed_isolated_point(
        left,
        middle,
        right,
        index=index,
    )
    assert point is not None
    return short_term_point_from_isolated_point(point)


def right_inside_high(index: int, price: float) -> ShortTermPoint:
    left = candle(price - 2.0, price - 10.0)
    middle = candle(price, price - 8.0)
    potential = get_potential_isolated_point(left, middle, index=index)
    assert potential is not None

    recognition = confirm_isolated_point_with_deformation(
        potential,
        middle,
        candle(price, price - 7.0),
    )
    assert recognition is not None
    assert recognition.basis is IsolatedPointBasis.RIGHT_INSIDE_BAR
    return short_term_point_from_recognition(recognition)


def recognized_short_points(
    high_prices: list[float],
    low_prices: list[float],
    *,
    deformation_high_position: int | None = None,
) -> list[ShortTermPoint]:
    assert len(high_prices) == len(low_prices)
    points: list[ShortTermPoint] = []
    for position, (high_price, low_price) in enumerate(
        zip(high_prices, low_prices)
    ):
        high_index = position * 2 + 1
        high_point = (
            right_inside_high(high_index, high_price)
            if position == deformation_high_position
            else strict_short_point(
                high_index,
                IsolatedPointKind.HIGH,
                high_price,
            )
        )
        points.extend(
            (
                high_point,
                strict_short_point(
                    high_index + 1,
                    IsolatedPointKind.LOW,
                    low_price,
                ),
            )
        )
    return points


def test_trend_is_classified_only_for_the_explicit_defined_segment() -> None:
    segment, state, points = classified_uptrend()

    assert segment == MarketSegment(0, 3)
    assert state is MarketState.UPTREND
    with pytest.raises(ValueError, match="outside segment"):
        classify_market_state(MarketSegment(1, 3), points)


def test_touch_is_not_a_break_but_strict_crossing_confirms_bms_and_sms() -> None:
    segment, state, _ = classified_uptrend()
    bms_context = PullbackContext(
        segment,
        state,
        trend_origin=low(2, 95.0),
        previous_extreme=high(3, 110.0),
        pullback_extreme=low(4, 100.0),
    )
    bms_touch = BMSObservation(5, candle(110.0, 98.0))
    bms_cross = BMSObservation(6, candle(111.0, 98.0))

    assert evaluate_bms(bms_context, [bms_touch]).status is (
        PullbackStructureStatus.PULLBACK_ONLY
    )
    bms_result = evaluate_bms(bms_context, [bms_touch, bms_cross])
    assert bms_result.status is PullbackStructureStatus.BMS_CONFIRMED
    assert bms_result.breakout_index == 6

    sms_context = SMSContext(
        segment,
        state,
        trend_extreme=high(3, 110.0),
        creator_point=low(2, 95.0),
    )
    sms_touch = SMSObservation(4, candle(110.0, 95.0))
    sms_cross = SMSObservation(5, candle(109.0, 94.0))

    assert evaluate_sms(sms_context, [sms_touch]).status is (
        SMSStructureStatus.PULLBACK_ONLY
    )
    sms_result = evaluate_sms(sms_context, [sms_touch, sms_cross])
    assert sms_result.status is SMSStructureStatus.SMS_CONFIRMED
    assert sms_result.event_index == 5


def test_sms_confirmed_is_not_a_guaranteed_opposite_trend() -> None:
    segment, state, _ = classified_uptrend()
    context = SMSContext(
        segment,
        state,
        trend_extreme=high(3, 110.0),
        creator_point=low(2, 95.0),
    )

    sms_result = evaluate_sms(
        context,
        [SMSObservation(4, candle(109.0, 94.0))],
    )
    later_state = classify_market_state(
        MarketSegment(4, 7),
        [
            high(4, 109.0),
            low(5, 94.0),
            high(6, 108.0),
            low(7, 94.0),
        ],
    )

    assert sms_result.status is SMSStructureStatus.SMS_CONFIRMED
    assert later_state is MarketState.NON_TREND


def test_each_structure_line_contains_only_its_own_promoted_level() -> None:
    recognized = recognized_short_points(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[90.0, 95.0, 80.0, 96.0, 85.0, 97.0, 70.0],
        deformation_high_position=3,
    )

    short_structure = build_short_term_structure(recognized)
    medium_structure = build_medium_term_structure(short_structure)
    long_structure = build_long_term_structure(medium_structure)

    assert all(type(point) is ShortTermPoint for point in short_structure.vertices)
    assert all(type(point) is MediumTermPoint for point in medium_structure.vertices)
    assert all(
        type(point.pivot) is ShortTermPoint
        for point in medium_structure.vertices
    )
    assert all(type(point) is LongTermPoint for point in long_structure.vertices)
    assert len(long_structure.vertices) == 1
    long_high = long_structure.vertices[0]
    assert long_high.pivot is medium_structure.vertices[2]
    assert long_high.pivot.pivot is short_structure.vertices[6]
    assert long_high.pivot.pivot.recognition_basis is (
        IsolatedPointBasis.RIGHT_INSIDE_BAR
    )


def test_suppressed_medium_points_cannot_secretly_promote_to_long_term() -> None:
    recognized = recognized_short_points(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0],
    )
    medium_structure = build_medium_term_structure(
        build_short_term_structure(recognized)
    )

    assert [point.price for point in medium_structure.points] == [
        110.0,
        120.0,
        115.0,
    ]
    assert [point.price for point in medium_structure.vertices] == [120.0]
    assert all(
        item.point in medium_structure.points
        and item.point not in medium_structure.vertices
        for item in medium_structure.suppressed
    )

    long_structure = build_long_term_structure(medium_structure)
    assert long_structure.points == ()
    assert long_structure.vertices == ()


def test_prefix_potential_differs_from_later_confirmed_snapshot() -> None:
    """Live inside timing remains deferred; snapshots prove supported state."""

    prefix_points = [
        ShortTermPoint(1, IsolatedPointKind.HIGH, 100.0),
        ShortTermPoint(2, IsolatedPointKind.LOW, 90.0),
        ShortTermPoint(3, IsolatedPointKind.HIGH, 110.0),
        ShortTermPoint(4, IsolatedPointKind.LOW, 95.0),
    ]
    prefix_source = build_short_term_structure(prefix_points)
    prefix = build_medium_term_structure(prefix_source)

    assert prefix.points == ()
    assert len(prefix.potentials) == 1
    assert prefix.potentials[0].pivot is prefix_source.vertices[2]

    extended_source = build_short_term_structure(
        prefix_points
        + [ShortTermPoint(5, IsolatedPointKind.HIGH, 105.0)]
    )
    extended = build_medium_term_structure(extended_source)

    assert prefix.points == ()
    assert len(extended.points) == 1
    confirmed = extended.points[0]
    assert confirmed.pivot is extended_source.vertices[2]
    assert confirmed.confirmed_by is extended_source.vertices[4]
    assert not hasattr(confirmed, "known_at_index")
    assert not hasattr(confirmed, "confirmed_at_index")
