from importlib import import_module, util
from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.long_term_structure import (
    LongCourseEvidence,
    LongTermPoint,
    LongTermStructure,
    LongTermSuppressionReason,
    PotentialLongTermPoint,
    SuppressedLongTermPoint,
    build_long_term_structure,
)
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumTermPoint,
    MediumTermStructure,
    MediumTermSuppressionReason,
    SuppressedMediumTermPoint,
)
from trading.definitions.short_term_structure import ShortTermPoint


def test_long_term_module_exists() -> None:
    assert (
        util.find_spec("trading.definitions.long_term_structure")
        is not None
    )


def test_locked_long_term_api_is_exposed() -> None:
    module = import_module("trading.definitions.long_term_structure")
    expected_names = {
        "LongTermSuppressionReason",
        "LongTermPoint",
        "PotentialLongTermPoint",
        "SuppressedLongTermPoint",
        "LongCourseEvidence",
        "LongTermStructure",
        "build_long_term_structure",
        "attach_course_evidence",
    }

    missing = sorted(
        name for name in expected_names if not hasattr(module, name)
    )

    assert missing == []


def medium_point(
    pivot_index: int,
    kind: IsolatedPointKind,
    price: float,
    *,
    confirmed_by_index: int | None = None,
) -> MediumTermPoint:
    confirmer_index = (
        pivot_index + 1
        if confirmed_by_index is None
        else confirmed_by_index
    )
    return MediumTermPoint(
        ShortTermPoint(pivot_index, kind, price, None),
        ShortTermPoint(confirmer_index, kind, price, None),
    )


def medium_structure(
    vertices: list[MediumTermPoint] | tuple[MediumTermPoint, ...],
    *,
    points: list[MediumTermPoint] | tuple[MediumTermPoint, ...] | None = None,
    suppressed: tuple[SuppressedMediumTermPoint, ...] = (),
) -> MediumTermStructure:
    vertex_tuple = tuple(vertices)
    return MediumTermStructure(
        points=vertex_tuple if points is None else tuple(points),
        potentials=(),
        vertices=vertex_tuple,
        suppressed=suppressed,
        course_evidence=(),
    )


def test_long_term_domain_values_are_stable_and_frozen() -> None:
    pivot = medium_point(30, IsolatedPointKind.HIGH, 120.0)
    confirmed_by = medium_point(50, IsolatedPointKind.HIGH, 115.0)
    point = LongTermPoint(pivot, confirmed_by)
    potential = PotentialLongTermPoint(
        medium_point(10, IsolatedPointKind.HIGH, 110.0),
        pivot,
    )
    suppressed = SuppressedLongTermPoint(
        point,
        LongTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    evidence = LongCourseEvidence(point, CourseRuleMatch.UNKNOWN)
    structure = LongTermStructure(
        points=(point,),
        potentials=(potential,),
        vertices=(point,),
        suppressed=(suppressed,),
        course_evidence=(evidence,),
    )

    assert {reason.value for reason in LongTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }
    assert point.pivot is pivot
    assert point.confirmed_by is confirmed_by
    assert point.pivot_index == 30
    assert point.confirmed_by_index == 50
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 120.0
    assert not hasattr(point, "known_at_index")
    assert not hasattr(point, "confirmed_at_index")
    assert structure.course_evidence == (evidence,)
    with pytest.raises(FrozenInstanceError):
        point.confirmed_by = pivot  # type: ignore[misc]


def test_confirmed_long_point_requires_same_kind_sources() -> None:
    with pytest.raises(ValueError, match="same-kind pivot and confirmed_by"):
        LongTermPoint(
            medium_point(30, IsolatedPointKind.HIGH, 120.0),
            medium_point(50, IsolatedPointKind.LOW, 90.0),
        )


@pytest.mark.parametrize("confirmed_by_index", [20, 30])
def test_confirmed_long_point_requires_later_source(confirmed_by_index: int) -> None:
    with pytest.raises(ValueError, match="confirmed_by pivot index must be after pivot index"):
        LongTermPoint(
            medium_point(30, IsolatedPointKind.HIGH, 120.0),
            medium_point(confirmed_by_index, IsolatedPointKind.HIGH, 115.0),
        )


def test_potential_long_point_validates_kind_chronology_and_extremity() -> None:
    previous_high = medium_point(10, IsolatedPointKind.HIGH, 110.0)
    with pytest.raises(ValueError, match="same-kind source points"):
        PotentialLongTermPoint(previous_high, medium_point(30, IsolatedPointKind.LOW, 90.0))
    with pytest.raises(ValueError, match="indexes must be chronological"):
        PotentialLongTermPoint(previous_high, medium_point(5, IsolatedPointKind.HIGH, 120.0))
    with pytest.raises(ValueError, match="must be more extreme"):
        PotentialLongTermPoint(previous_high, medium_point(30, IsolatedPointKind.HIGH, 110.0))


@pytest.mark.parametrize("vertices", [
    [medium_point(20, IsolatedPointKind.HIGH, 110.0), medium_point(10, IsolatedPointKind.LOW, 90.0)],
    [medium_point(10, IsolatedPointKind.HIGH, 110.0), medium_point(10, IsolatedPointKind.LOW, 90.0)],
])
def test_source_rejects_non_increasing_pivot_indexes(vertices: list[MediumTermPoint]) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_long_term_structure(medium_structure(vertices))


def test_complete_source_chronology_is_validated_before_output() -> None:
    vertices = [medium_point(10, IsolatedPointKind.HIGH, 105.0), medium_point(40, IsolatedPointKind.HIGH, 112.0), medium_point(30, IsolatedPointKind.HIGH, 108.0)]
    with pytest.raises(ValueError, match="strictly increasing"):
        build_long_term_structure(medium_structure(vertices))


def test_source_vertices_must_belong_to_medium_points() -> None:
    vertex = medium_point(30, IsolatedPointKind.HIGH, 112.0)
    with pytest.raises(ValueError, match="must come from structure points"):
        build_long_term_structure(medium_structure([vertex], points=[]))


def test_suppressed_medium_point_cannot_be_a_long_source_vertex() -> None:
    vertex = medium_point(30, IsolatedPointKind.HIGH, 112.0)
    suppression = SuppressedMediumTermPoint(vertex, MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND)
    with pytest.raises(ValueError, match="must not be long-term recognition vertices"):
        build_long_term_structure(medium_structure([vertex], suppressed=(suppression,)))


def test_empty_and_one_vertex_sources_are_neutral() -> None:
    empty = build_long_term_structure(medium_structure([]))
    one = build_long_term_structure(medium_structure([medium_point(10, IsolatedPointKind.HIGH, 105.0)]))
    assert empty == LongTermStructure((), (), (), (), ())
    assert one == LongTermStructure((), (), (), (), ())


def alternating_medium_source(
    *,
    high_prices: list[float],
    low_prices: list[float],
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> MediumTermStructure:
    vertices: list[MediumTermPoint] = []
    for index, (high_price, low_price) in enumerate(zip(high_prices, low_prices)):
        first_index = index * 20 + 10
        second_index = index * 20 + 20
        high = medium_point(
            first_index if first_kind is IsolatedPointKind.HIGH else second_index,
            IsolatedPointKind.HIGH,
            high_price,
        )
        low = medium_point(
            first_index if first_kind is IsolatedPointKind.LOW else second_index,
            IsolatedPointKind.LOW,
            low_price,
        )
        vertices.extend(
            (high, low)
            if first_kind is IsolatedPointKind.HIGH
            else (low, high)
        )
    return medium_structure(vertices)


def test_basic_long_high_uses_strict_same_kind_medium_neighbors() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 120.0, 115.0],
        low_prices=[90.0, 91.0, 92.0],
    )

    result = build_long_term_structure(source)

    assert len(result.points) == 1
    point = result.points[0]
    assert point.pivot is source.vertices[2]
    assert point.confirmed_by is source.vertices[4]
    assert point.pivot_index == source.vertices[2].pivot_index
    assert point.confirmed_by_index == source.vertices[4].pivot_index
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 120.0
    assert result.vertices == result.points
    assert result.potentials == ()


def test_basic_long_low_uses_strict_same_kind_medium_neighbors() -> None:
    source = alternating_medium_source(
        high_prices=[110.0, 111.0, 112.0],
        low_prices=[100.0, 80.0, 90.0],
    )

    result = build_long_term_structure(source)

    point = result.points[0]
    assert point.pivot is source.vertices[3]
    assert point.confirmed_by is source.vertices[5]
    assert point.kind is IsolatedPointKind.LOW
    assert point.price == 80.0


@pytest.mark.parametrize(
    "high_prices",
    [[120.0, 120.0, 115.0], [105.0, 120.0, 120.0]],
)
def test_long_high_equality_on_either_side_rejects_confirmation(
    high_prices: list[float],
) -> None:
    source = alternating_medium_source(
        high_prices=high_prices,
        low_prices=[90.0, 91.0, 92.0],
    )

    result = build_long_term_structure(source)

    assert all(
        point.kind is not IsolatedPointKind.HIGH
        for point in result.points
    )


@pytest.mark.parametrize(
    "low_prices",
    [[80.0, 80.0, 90.0], [100.0, 80.0, 80.0]],
)
def test_long_low_equality_on_either_side_rejects_confirmation(
    low_prices: list[float],
) -> None:
    source = alternating_medium_source(
        high_prices=[110.0, 111.0, 112.0],
        low_prices=low_prices,
    )

    result = build_long_term_structure(source)

    assert all(
        point.kind is not IsolatedPointKind.LOW
        for point in result.points
    )


def test_opposite_kind_vertices_are_not_same_kind_neighbors() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 120.0, 115.0],
        low_prices=[100.0, 80.0, 90.0],
    )

    result = build_long_term_structure(source)

    assert [(point.pivot_index, point.kind) for point in result.points] == [
        (source.vertices[2].pivot_index, IsolatedPointKind.HIGH),
        (source.vertices[3].pivot_index, IsolatedPointKind.LOW),
    ]
    assert result.points[0].confirmed_by is source.vertices[4]
    assert result.points[1].confirmed_by is source.vertices[5]


def test_recognizer_does_not_skip_intervening_same_kind_medium_vertex() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 120.0, 105.0],
        low_prices=[80.0, 81.0, 82.0, 83.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [120.0]
    assert all(point.price != 110.0 for point in result.points)


def test_confirmed_long_points_use_pivot_order_and_exact_sources() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 120.0, 115.0],
        low_prices=[100.0, 80.0, 90.0],
    )

    result = build_long_term_structure(source)

    assert [point.pivot_index for point in result.points] == [
        source.vertices[2].pivot_index,
        source.vertices[3].pivot_index,
    ]
    assert [point.confirmed_by for point in result.points] == [
        source.vertices[4],
        source.vertices[5],
    ]
    assert all(not hasattr(point, "known_at_index") for point in result.points)


@pytest.mark.parametrize(
    "kind,prices",
    [
        (IsolatedPointKind.HIGH, [105.0, 120.0]),
        (IsolatedPointKind.LOW, [100.0, 80.0]),
    ],
)
def test_current_edge_candidate_is_only_a_potential(
    kind: IsolatedPointKind,
    prices: list[float],
) -> None:
    source = medium_structure(
        [
            medium_point(10, kind, prices[0]),
            medium_point(30, kind, prices[1]),
        ]
    )

    result = build_long_term_structure(source)

    assert result.points == ()
    assert result.vertices == ()
    assert result.suppressed == ()
    assert len(result.potentials) == 1
    assert result.potentials[0].previous_same_kind is source.vertices[0]
    assert result.potentials[0].pivot is source.vertices[1]


def test_potential_becomes_confirmed_after_passing_later_high() -> None:
    previous = medium_point(10, IsolatedPointKind.HIGH, 105.0)
    pivot = medium_point(30, IsolatedPointKind.HIGH, 120.0)
    later = medium_point(50, IsolatedPointKind.HIGH, 115.0)

    before = build_long_term_structure(medium_structure([previous, pivot]))
    after = build_long_term_structure(
        medium_structure([previous, pivot, later])
    )

    assert before.points == ()
    assert before.potentials[0].pivot is pivot
    assert after.potentials == ()
    assert after.points == (LongTermPoint(pivot, later),)


def test_failed_potential_is_not_promoted() -> None:
    previous = medium_point(10, IsolatedPointKind.HIGH, 105.0)
    pivot = medium_point(30, IsolatedPointKind.HIGH, 120.0)
    later = medium_point(50, IsolatedPointKind.HIGH, 125.0)

    before = build_long_term_structure(medium_structure([previous, pivot]))
    after = build_long_term_structure(
        medium_structure([previous, pivot, later])
    )

    assert before.potentials[0].pivot is pivot
    assert all(point.pivot is not pivot for point in after.points)
    assert after.potentials == (
        PotentialLongTermPoint(pivot, later),
    )


def test_non_extreme_right_edge_is_not_a_potential() -> None:
    source = medium_structure(
        [
            medium_point(10, IsolatedPointKind.LOW, 80.0),
            medium_point(30, IsolatedPointKind.LOW, 90.0),
        ]
    )

    result = build_long_term_structure(source)

    assert result.potentials == ()


def test_consecutive_long_highs_keep_highest_vertex_and_all_points() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0, 86.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0, 115.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [item.point.price for item in result.suppressed] == [110.0, 115.0]
    assert all(
        item.reason is LongTermSuppressionReason.CONSECUTIVE_SAME_KIND
        for item in result.suppressed
    )


def test_consecutive_long_lows_keep_lowest_vertex_and_all_points() -> None:
    source = alternating_medium_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0, 135.0, 136.0],
        low_prices=[120.0, 90.0, 100.0, 80.0, 95.0, 85.0, 110.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 80.0, 85.0]
    assert [point.price for point in result.vertices] == [80.0]
    assert [item.point.price for item in result.suppressed] == [90.0, 85.0]


def test_equal_highest_long_high_keeps_earliest_pivot() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 105.0, 110.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 110.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed == (
        SuppressedLongTermPoint(
            result.points[1],
            LongTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
    )


def test_equal_lowest_long_low_keeps_earliest_pivot() -> None:
    source = alternating_medium_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0],
        low_prices=[120.0, 90.0, 100.0, 90.0, 110.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 90.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed[0].point is result.points[1]


def test_same_kind_normalization_does_not_change_potentials() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 125.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [potential.price for potential in result.potentials] == [125.0]


def paired_long_source(
    earlier_high: float,
    earlier_low: float,
    later_high: float,
    later_low: float,
    *,
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> MediumTermStructure:
    return alternating_medium_source(
        high_prices=[
            earlier_high - 5.0,
            earlier_high,
            min(earlier_high, later_high) - 6.0,
            later_high,
            later_high - 5.0,
        ],
        low_prices=[
            earlier_low + 5.0,
            earlier_low,
            max(earlier_low, later_low) + 6.0,
            later_low,
            later_low + 5.0,
        ],
        first_kind=first_kind,
    )


@pytest.mark.parametrize(
    "first_kind",
    [IsolatedPointKind.HIGH, IsolatedPointKind.LOW],
)
def test_complete_inside_long_pair_is_suppressed_in_both_orientations(
    first_kind: IsolatedPointKind,
) -> None:
    source = paired_long_source(
        110.0,
        100.0,
        108.0,
        102.0,
        first_kind=first_kind,
    )

    result = build_long_term_structure(source)

    assert len(result.points) == 4
    assert result.vertices == result.points[:2]
    assert result.suppressed == tuple(
        SuppressedLongTermPoint(
            point,
            LongTermSuppressionReason.INSIDE_STRUCTURE,
        )
        for point in result.points[2:]
    )


@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (110.0, 102.0),
        (108.0, 100.0),
        (110.0, 100.0),
    ],
)
def test_equality_at_long_inside_boundary_counts_as_contained(
    later_high: float,
    later_low: float,
) -> None:
    result = build_long_term_structure(
        paired_long_source(110.0, 100.0, later_high, later_low)
    )

    assert result.vertices == result.points[:2]


@pytest.mark.parametrize(
    "later_high,later_low",
    [(111.0, 102.0), (108.0, 99.0)],
)
def test_one_side_breakout_preserves_later_long_pair(
    later_high: float,
    later_low: float,
) -> None:
    result = build_long_term_structure(
        paired_long_source(110.0, 100.0, later_high, later_low)
    )

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_incomplete_later_long_range_is_preserved() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 110.0, 104.0, 108.0, 103.0],
        low_prices=[105.0, 100.0, 106.0, 107.0, 108.0],
    )

    result = build_long_term_structure(source)

    assert [(point.kind, point.price) for point in result.points] == [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 100.0),
        (IsolatedPointKind.HIGH, 108.0),
    ]
    assert result.vertices == result.points
    assert result.suppressed == ()


def test_repeated_inside_long_pairs_normalize_until_stable() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 120.0, 99.0, 115.0, 98.0, 110.0, 97.0],
        low_prices=[110.0, 90.0, 111.0, 95.0, 112.0, 100.0, 113.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.vertices] == [120.0, 90.0]
    assert [item.point for item in result.suppressed] == list(
        result.points[2:]
    )
    assert all(
        item.reason is LongTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.suppressed
    )


def test_inside_pair_uses_immediately_previous_complete_pair() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 110.0, 104.0, 120.0, 103.0, 115.0, 102.0],
        low_prices=[105.0, 100.0, 106.0, 90.0, 107.0, 95.0, 108.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.vertices] == [
        110.0,
        100.0,
        120.0,
        90.0,
    ]
    assert [item.point.price for item in result.suppressed] == [115.0, 95.0]


def test_non_contained_long_layout_is_preserved_without_guessing() -> None:
    result = build_long_term_structure(
        paired_long_source(110.0, 100.0, 115.0, 95.0)
    )

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_suppression_order_is_phase_then_pivot_chronology() -> None:
    source = alternating_medium_source(
        high_prices=[
            100.0,
            110.0,
            105.0,
            120.0,
            107.0,
            115.0,
            100.0,
            101.0,
        ],
        low_prices=[
            100.0,
            99.0,
            98.0,
            97.0,
            90.0,
            96.0,
            92.0,
            98.0,
        ],
    )

    result = build_long_term_structure(source)

    reasons = [item.reason for item in result.suppressed]
    assert reasons[0] is LongTermSuppressionReason.CONSECUTIVE_SAME_KIND
    assert reasons[1:] == [
        LongTermSuppressionReason.INSIDE_STRUCTURE,
        LongTermSuppressionReason.INSIDE_STRUCTURE,
    ]
