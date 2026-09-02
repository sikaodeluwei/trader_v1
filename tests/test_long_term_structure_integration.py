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
    LongCourseEvidence,
    LongTermStructure,
    attach_course_evidence,
    build_long_term_structure,
)
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumTermStructure,
    build_medium_term_structure,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def candle(high: float, low: float) -> Candle:
    midpoint = (high + low) / 2
    return Candle(midpoint, high, low, midpoint)


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

    recognized = detect_confirmed_isolated_point(
        left,
        middle,
        right,
        index=index,
    )
    assert recognized is not None
    return short_term_point_from_isolated_point(recognized)


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
    for position, (high, low) in enumerate(zip(high_prices, low_prices)):
        high_index = position * 2 + 1
        if position == deformation_high_position:
            high_point = right_inside_high(high_index, high)
        else:
            high_point = strict_short_point(
                high_index,
                IsolatedPointKind.HIGH,
                high,
            )
        low_point = strict_short_point(
            high_index + 1,
            IsolatedPointKind.LOW,
            low,
        )
        points.extend((high_point, low_point))
    return points


def build_real_hierarchy() -> tuple[
    list[ShortTermPoint],
    ShortTermStructure,
    MediumTermStructure,
    LongTermStructure,
]:
    points = recognized_short_points(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[90.0, 95.0, 80.0, 96.0, 85.0, 97.0, 70.0],
        deformation_high_position=3,
    )
    short_structure = build_short_term_structure(points)
    medium_structure = build_medium_term_structure(short_structure)
    long_structure = build_long_term_structure(medium_structure)
    return points, short_structure, medium_structure, long_structure


def test_real_strict_and_deformation_hierarchy_reaches_long_structure() -> None:
    points, short_structure, medium_structure, long_structure = (
        build_real_hierarchy()
    )
    deformation_high = points[6]

    assert short_structure.vertices == tuple(points)
    assert deformation_high.recognition_basis is (
        IsolatedPointBasis.RIGHT_INSIDE_BAR
    )
    assert [point.price for point in medium_structure.vertices] == [
        110.0,
        80.0,
        120.0,
        85.0,
        115.0,
    ]
    assert len(long_structure.points) == 1
    long_high = long_structure.points[0]
    assert long_high.pivot is medium_structure.vertices[2]
    assert long_high.confirmed_by is medium_structure.vertices[4]
    assert long_high.pivot.pivot is deformation_high
    assert long_high.pivot.pivot.recognition_basis is (
        IsolatedPointBasis.RIGHT_INSIDE_BAR
    )
    assert long_high.confirmed_by.pivot is points[10]
    assert not hasattr(long_high, "known_at_index")


def test_suppressed_medium_points_are_not_long_recognition_neighbors() -> None:
    points = recognized_short_points(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0],
    )
    short_structure = build_short_term_structure(points)
    medium_structure = build_medium_term_structure(short_structure)
    long_structure = build_long_term_structure(medium_structure)

    assert [point.price for point in medium_structure.points] == [
        110.0,
        120.0,
        115.0,
    ]
    assert [point.price for point in medium_structure.vertices] == [120.0]
    assert [item.point.price for item in medium_structure.suppressed] == [
        110.0,
        115.0,
    ]
    assert all(
        item.point in medium_structure.points
        and item.point not in medium_structure.vertices
        for item in medium_structure.suppressed
    )
    assert long_structure.points == ()
    assert long_structure.vertices == ()


def test_external_evidence_cannot_change_integrated_long_output() -> None:
    _, _, _, canonical = build_real_hierarchy()
    evidence = LongCourseEvidence(
        canonical.points[0],
        CourseRuleMatch.UNKNOWN,
    )

    enriched = attach_course_evidence(canonical, [evidence])

    assert enriched.points == canonical.points
    assert enriched.potentials == canonical.potentials
    assert enriched.vertices == canonical.vertices
    assert enriched.suppressed == canonical.suppressed
    assert enriched.course_evidence == (evidence,)
    assert enriched.points[0].pivot is canonical.points[0].pivot
    assert (
        enriched.points[0].confirmed_by
        is canonical.points[0].confirmed_by
    )
