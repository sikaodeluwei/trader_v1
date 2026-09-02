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
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumCourseEvidence,
    attach_course_evidence,
    build_medium_term_structure,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def candle(high: float, low: float) -> Candle:
    midpoint = (high + low) / 2
    return Candle(midpoint, high, low, midpoint)


def require_strict_short_point(
    candles: list[Candle],
    index: int,
) -> ShortTermPoint:
    recognized = detect_confirmed_isolated_point(
        candles[index - 1],
        candles[index],
        candles[index + 1],
        index=index,
    )
    assert recognized is not None
    return short_term_point_from_isolated_point(recognized)


def test_real_strict_and_deformation_paths_reach_medium_structure() -> None:
    candles = [
        candle(100.0, 90.0),
        candle(105.0, 95.0),
        candle(102.0, 92.0),
        candle(112.0, 96.0),
        candle(106.0, 98.0),
        candle(104.0, 94.0),
        candle(108.0, 99.0),
        candle(105.0, 96.0),
    ]
    strict_high_1 = require_strict_short_point(candles, 1)
    strict_low_1 = require_strict_short_point(candles, 2)

    potential = get_potential_isolated_point(
        candles[2],
        candles[3],
        index=3,
    )
    assert potential is not None
    deformation = confirm_isolated_point_with_deformation(
        potential,
        candles[3],
        candles[4],
    )
    assert deformation is not None
    deformation_high = short_term_point_from_recognition(deformation)

    strict_low_2 = require_strict_short_point(candles, 5)
    strict_high_3 = require_strict_short_point(candles, 6)
    short_points = [
        strict_high_1,
        strict_low_1,
        deformation_high,
        strict_low_2,
        strict_high_3,
    ]

    short_structure = build_short_term_structure(short_points)
    medium_structure = build_medium_term_structure(short_structure)

    assert short_structure.vertices == tuple(short_points)
    assert deformation_high.recognition_basis is (
        IsolatedPointBasis.RIGHT_INSIDE_BAR
    )
    assert len(medium_structure.points) == 1
    medium_high = medium_structure.points[0]
    assert medium_high.pivot is deformation_high
    assert medium_high.pivot_index == 3
    assert medium_high.confirmed_by is strict_high_3
    assert medium_high.confirmed_by_index == 6
    assert not hasattr(medium_high, "known_at_index")


def test_suppressed_short_term_point_is_not_a_medium_neighbor() -> None:
    short_points = [
        ShortTermPoint(1, IsolatedPointKind.HIGH, 120.0, None),
        ShortTermPoint(2, IsolatedPointKind.LOW, 90.0, None),
        ShortTermPoint(3, IsolatedPointKind.HIGH, 100.0, None),
        ShortTermPoint(4, IsolatedPointKind.HIGH, 110.0, None),
        ShortTermPoint(5, IsolatedPointKind.LOW, 80.0, None),
        ShortTermPoint(6, IsolatedPointKind.HIGH, 105.0, None),
    ]

    short_structure = build_short_term_structure(short_points)
    medium_structure = build_medium_term_structure(short_structure)

    suppressed_short_point = short_points[2]
    assert suppressed_short_point in short_structure.points
    assert suppressed_short_point not in short_structure.vertices
    assert all(point.pivot is not short_points[3] for point in medium_structure.points)


def test_external_course_evidence_cannot_change_integrated_output() -> None:
    short_points = [
        ShortTermPoint(1, IsolatedPointKind.HIGH, 105.0, None),
        ShortTermPoint(2, IsolatedPointKind.LOW, 90.0, None),
        ShortTermPoint(3, IsolatedPointKind.HIGH, 112.0, None),
        ShortTermPoint(4, IsolatedPointKind.LOW, 92.0, None),
        ShortTermPoint(5, IsolatedPointKind.HIGH, 108.0, None),
    ]
    canonical = build_medium_term_structure(
        build_short_term_structure(short_points)
    )
    evidence = MediumCourseEvidence(
        canonical.points[0],
        CourseRuleMatch.UNKNOWN,
    )

    enriched = attach_course_evidence(canonical, [evidence])

    assert enriched.points == canonical.points
    assert enriched.potentials == canonical.potentials
    assert enriched.vertices == canonical.vertices
    assert enriched.suppressed == canonical.suppressed
    assert enriched.course_evidence == (evidence,)
