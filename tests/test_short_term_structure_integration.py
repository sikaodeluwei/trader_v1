from trading.definitions.candles import Candle
from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    confirm_isolated_point_with_deformation,
)
from trading.definitions.isolated_points import (
    IsolatedPointKind,
    detect_confirmed_isolated_point,
    find_confirmed_isolated_points,
    get_potential_isolated_point,
)
from trading.definitions.short_term_structure import (
    ShortTermSuppressionReason,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def candle(high: float, low: float) -> Candle:
    midpoint = (high + low) / 2
    return Candle(midpoint, high, low, midpoint)


def test_strict_isolated_high_maps_to_short_term_high() -> None:
    recognized = detect_confirmed_isolated_point(
        candle(10.0, 5.0),
        candle(12.0, 7.0),
        candle(11.0, 6.0),
        index=1,
    )
    assert recognized is not None

    point = short_term_point_from_isolated_point(recognized)

    assert point.index == 1
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 12.0
    assert point.recognition_basis is None


def test_strict_isolated_low_maps_to_short_term_low() -> None:
    recognized = detect_confirmed_isolated_point(
        candle(10.0, 5.0),
        candle(8.0, 3.0),
        candle(9.0, 4.0),
        index=1,
    )
    assert recognized is not None

    point = short_term_point_from_isolated_point(recognized)

    assert point.kind is IsolatedPointKind.LOW
    assert point.price == 3.0


def test_right_inside_bar_recognition_composes_into_structure() -> None:
    middle = candle(12.0, 7.0)
    potential = get_potential_isolated_point(
        candle(10.0, 5.0),
        middle,
        index=1,
    )
    assert potential is not None
    recognition = confirm_isolated_point_with_deformation(
        potential,
        middle,
        candle(12.0, 8.0),
    )
    assert recognition is not None

    point = short_term_point_from_recognition(recognition)
    result = build_short_term_structure([point])

    assert point.kind is IsolatedPointKind.HIGH
    assert point.recognition_basis is IsolatedPointBasis.RIGHT_INSIDE_BAR
    assert result.points == (point,)
    assert result.vertices == (point,)
    assert result.suppressed == ()
    assert result.points[0].recognition_basis is IsolatedPointBasis.RIGHT_INSIDE_BAR


def test_strict_candle_sequence_preserves_points_while_normalizing_line() -> None:
    candles = [
        candle(10.0, 5.0),
        candle(12.0, 7.0),
        candle(11.0, 6.0),
        candle(13.0, 5.5),
        candle(14.0, 7.0),
        candle(12.0, 6.0),
    ]
    recognized = find_confirmed_isolated_points(candles)
    assert [(point.index, point.kind, point.price) for point in recognized] == [
        (1, IsolatedPointKind.HIGH, 12.0),
        (4, IsolatedPointKind.HIGH, 14.0),
    ]
    points = [short_term_point_from_isolated_point(point) for point in recognized]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == (points[1],)
    assert len(result.suppressed) == 1
    assert result.suppressed[0].point is points[0]
    assert result.suppressed[0].reason is (
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND
    )
