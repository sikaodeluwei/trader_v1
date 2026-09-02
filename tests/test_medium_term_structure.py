from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumCourseEvidence,
    MediumTermPoint,
    MediumTermStructure,
    MediumTermSuppressionReason,
    PotentialMediumTermPoint,
    SuppressedMediumTermPoint,
    attach_course_evidence,
    build_medium_term_structure,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    ShortTermSuppressionReason,
    SuppressedShortTermPoint,
)


def short_point(index: int, kind: IsolatedPointKind, price: float) -> ShortTermPoint:
    return ShortTermPoint(index, kind, price, None)


def short_structure(
    vertices: list[ShortTermPoint] | tuple[ShortTermPoint, ...],
    *,
    points: list[ShortTermPoint] | tuple[ShortTermPoint, ...] | None = None,
    suppressed: tuple[SuppressedShortTermPoint, ...] = (),
) -> ShortTermStructure:
    vertex_tuple = tuple(vertices)
    return ShortTermStructure(
        points=vertex_tuple if points is None else tuple(points),
        vertices=vertex_tuple,
        suppressed=suppressed,
    )


def alternating_source(
    high_prices: list[float],
    low_prices: list[float],
    *,
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> ShortTermStructure:
    assert len(high_prices) == len(low_prices)
    vertices: list[ShortTermPoint] = []
    for high, low in zip(high_prices, low_prices):
        if first_kind is IsolatedPointKind.HIGH:
            vertices.append(short_point(len(vertices), IsolatedPointKind.HIGH, high))
            vertices.append(short_point(len(vertices), IsolatedPointKind.LOW, low))
        else:
            vertices.append(short_point(len(vertices), IsolatedPointKind.LOW, low))
            vertices.append(short_point(len(vertices), IsolatedPointKind.HIGH, high))
    return short_structure(vertices)


def test_enum_values_are_stable() -> None:
    assert {reason.value for reason in MediumTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }
    assert {match.value for match in CourseRuleMatch} == {
        "yes",
        "no",
        "unknown",
    }


def test_medium_records_preserve_provenance_and_are_frozen() -> None:
    pivot = short_point(3, IsolatedPointKind.HIGH, 112.0)
    confirmed_by = short_point(7, IsolatedPointKind.HIGH, 108.0)
    point = MediumTermPoint(pivot, confirmed_by)
    potential = PotentialMediumTermPoint(short_point(1, IsolatedPointKind.HIGH, 105.0), pivot)
    suppressed = SuppressedMediumTermPoint(point, MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND)
    evidence = MediumCourseEvidence(point, CourseRuleMatch.UNKNOWN)
    structure = MediumTermStructure(
        points=(point,), potentials=(potential,), vertices=(point,), suppressed=(suppressed,), course_evidence=(evidence,)
    )

    assert point.pivot is pivot
    assert point.confirmed_by is confirmed_by
    assert point.pivot_index == 3
    assert point.confirmed_by_index == 7
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 112.0
    assert not hasattr(point, "known_at_index")
    assert structure.course_evidence == (evidence,)
    with pytest.raises(FrozenInstanceError):
        point.confirmed_by = short_point(8, IsolatedPointKind.HIGH, 107.0)  # type: ignore[misc]


def test_confirmed_point_requires_same_kind_source_points() -> None:
    pivot = short_point(3, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="same-kind pivot and confirmed_by"):
        MediumTermPoint(pivot, short_point(5, IsolatedPointKind.LOW, 95.0))


@pytest.mark.parametrize("confirmed_by_index", [2, 3])
def test_confirmed_point_requires_later_confirmed_by(confirmed_by_index: int) -> None:
    pivot = short_point(3, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="confirmed_by index must be after pivot index"):
        MediumTermPoint(
            pivot,
            short_point(confirmed_by_index, IsolatedPointKind.HIGH, 108.0),
        )


def test_potential_requires_same_kind_chronological_sources() -> None:
    previous = short_point(3, IsolatedPointKind.HIGH, 105.0)

    with pytest.raises(ValueError, match="same-kind source points"):
        PotentialMediumTermPoint(previous, short_point(5, IsolatedPointKind.LOW, 95.0))
    with pytest.raises(ValueError, match="indexes must be chronological"):
        PotentialMediumTermPoint(previous, short_point(2, IsolatedPointKind.HIGH, 110.0))


@pytest.mark.parametrize(
    "previous,pivot",
    [
        (short_point(1, IsolatedPointKind.HIGH, 110.0), short_point(3, IsolatedPointKind.HIGH, 110.0)),
        (short_point(1, IsolatedPointKind.LOW, 90.0), short_point(3, IsolatedPointKind.LOW, 90.0)),
    ],
)
def test_potential_requires_strictly_more_extreme_edge(previous: ShortTermPoint, pivot: ShortTermPoint) -> None:
    with pytest.raises(ValueError, match="must be more extreme"):
        PotentialMediumTermPoint(previous, pivot)


@pytest.mark.parametrize(
    "vertices",
    [
        [short_point(2, IsolatedPointKind.HIGH, 110.0), short_point(1, IsolatedPointKind.LOW, 90.0)],
        [short_point(1, IsolatedPointKind.HIGH, 110.0), short_point(1, IsolatedPointKind.LOW, 90.0)],
    ],
)
def test_source_rejects_non_increasing_vertex_indexes(vertices: list[ShortTermPoint]) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_medium_term_structure(short_structure(vertices))


def test_complete_source_chronology_is_validated_before_recognition() -> None:
    vertices = [
        short_point(1, IsolatedPointKind.HIGH, 105.0),
        short_point(4, IsolatedPointKind.HIGH, 112.0),
        short_point(3, IsolatedPointKind.HIGH, 108.0),
    ]

    with pytest.raises(ValueError, match="strictly increasing"):
        build_medium_term_structure(short_structure(vertices))


def test_vertices_must_belong_to_short_term_points() -> None:
    vertex = short_point(3, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="must come from structure points"):
        build_medium_term_structure(short_structure([vertex], points=[]))


def test_suppressed_short_term_point_cannot_be_a_medium_source_vertex() -> None:
    vertex = short_point(3, IsolatedPointKind.HIGH, 112.0)
    suppression = SuppressedShortTermPoint(vertex, ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND)

    with pytest.raises(ValueError, match="must not be medium-recognition vertices"):
        build_medium_term_structure(short_structure([vertex], suppressed=(suppression,)))


def test_empty_and_one_vertex_sources_are_neutral() -> None:
    empty = build_medium_term_structure(short_structure([]))
    one = build_medium_term_structure(short_structure([short_point(1, IsolatedPointKind.HIGH, 105.0)]))

    assert empty == MediumTermStructure((), (), (), (), ())
    assert one.points == ()
    assert one.potentials == ()
    assert one.vertices == ()
    assert one.suppressed == ()


def test_two_same_kind_vertices_can_produce_only_a_potential() -> None:
    source = short_structure([
        short_point(1, IsolatedPointKind.HIGH, 105.0),
        short_point(3, IsolatedPointKind.HIGH, 112.0),
    ])

    result = build_medium_term_structure(source)

    assert result.points == ()
    assert result.vertices == ()
    assert result.potentials == (PotentialMediumTermPoint(source.vertices[0], source.vertices[1]),)


def test_basic_ith_uses_strict_same_kind_neighbors() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0], low_prices=[90.0, 91.0, 92.0]
    )

    result = build_medium_term_structure(source)

    point = result.points[0]
    assert point.pivot is source.vertices[2]
    assert point.confirmed_by is source.vertices[4]
    assert point.pivot_index == 2
    assert point.confirmed_by_index == 4
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 112.0
    assert result.vertices == result.points


def test_basic_itl_uses_strict_same_kind_neighbors() -> None:
    source = alternating_source(
        high_prices=[110.0, 111.0, 112.0], low_prices=[100.0, 94.0, 98.0]
    )

    result = build_medium_term_structure(source)

    point = result.points[0]
    assert point.pivot is source.vertices[3]
    assert point.confirmed_by is source.vertices[5]
    assert point.pivot_index == 3
    assert point.confirmed_by_index == 5
    assert point.kind is IsolatedPointKind.LOW
    assert point.price == 94.0


@pytest.mark.parametrize(
    "high_prices", [[112.0, 112.0, 108.0], [105.0, 112.0, 112.0]]
)
def test_ith_equality_on_either_side_rejects_confirmation(high_prices: list[float]) -> None:
    source = alternating_source(high_prices=high_prices, low_prices=[90.0, 91.0, 92.0])

    result = build_medium_term_structure(source)

    assert all(point.kind is not IsolatedPointKind.HIGH for point in result.points)


@pytest.mark.parametrize(
    "low_prices", [[94.0, 94.0, 98.0], [100.0, 94.0, 94.0]]
)
def test_itl_equality_on_either_side_rejects_confirmation(low_prices: list[float]) -> None:
    source = alternating_source(high_prices=[110.0, 111.0, 112.0], low_prices=low_prices)

    result = build_medium_term_structure(source)

    assert all(point.kind is not IsolatedPointKind.LOW for point in result.points)


def test_opposite_kind_vertices_are_not_comparison_neighbors() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0], low_prices=[100.0, 94.0, 98.0]
    )

    result = build_medium_term_structure(source)

    assert [(point.pivot_index, point.kind) for point in result.points] == [
        (2, IsolatedPointKind.HIGH),
        (3, IsolatedPointKind.LOW),
    ]
    assert result.points[0].confirmed_by is source.vertices[4]
    assert result.points[1].confirmed_by is source.vertices[5]


def test_recognizer_does_not_skip_intervening_same_kind_vertex() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 120.0, 105.0],
        low_prices=[80.0, 81.0, 82.0, 83.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [120.0]
    assert all(point.price != 110.0 for point in result.points)


@pytest.mark.parametrize(
    "kind,prices",
    [
        (IsolatedPointKind.HIGH, [105.0, 112.0]),
        (IsolatedPointKind.LOW, [100.0, 94.0]),
    ],
)
def test_current_edge_candidate_is_separate_from_confirmed_output(
    kind: IsolatedPointKind, prices: list[float]
) -> None:
    source = short_structure([short_point(1, kind, prices[0]), short_point(3, kind, prices[1])])

    result = build_medium_term_structure(source)

    assert result.points == ()
    assert result.vertices == ()
    assert len(result.potentials) == 1
    assert result.potentials[0].pivot is source.vertices[1]
    assert result.potentials[0].previous_same_kind is source.vertices[0]


def test_potential_becomes_confirmed_only_after_right_high_exists() -> None:
    initial = short_structure([
        short_point(1, IsolatedPointKind.HIGH, 105.0),
        short_point(3, IsolatedPointKind.HIGH, 112.0),
    ])
    extended = short_structure([*initial.vertices, short_point(5, IsolatedPointKind.HIGH, 108.0)])

    before = build_medium_term_structure(initial)
    after = build_medium_term_structure(extended)

    assert before.points == ()
    assert before.potentials[0].pivot_index == 3
    assert after.potentials == ()
    assert after.points[0].pivot is initial.vertices[1]
    assert after.points[0].confirmed_by is extended.vertices[2]
    assert after.points[0].confirmed_by_index == 5


def test_failed_potential_is_not_promoted() -> None:
    initial = short_structure([
        short_point(1, IsolatedPointKind.HIGH, 105.0),
        short_point(3, IsolatedPointKind.HIGH, 112.0),
    ])
    extended = short_structure([*initial.vertices, short_point(5, IsolatedPointKind.HIGH, 115.0)])

    before = build_medium_term_structure(initial)
    after = build_medium_term_structure(extended)

    assert before.potentials[0].pivot_index == 3
    assert all(point.pivot_index != 3 for point in after.points)
    assert [potential.pivot_index for potential in after.potentials] == [5]


def test_confirmed_points_use_pivot_order_and_keep_confirming_sources() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0], low_prices=[100.0, 94.0, 98.0]
    )

    result = build_medium_term_structure(source)

    assert [point.pivot_index for point in result.points] == [2, 3]
    assert [point.confirmed_by_index for point in result.points] == [4, 5]
    assert all(
        point.confirmed_by.kind is point.pivot.kind
        and point.confirmed_by_index > point.pivot_index
        for point in result.points
    )


def test_consecutive_medium_highs_keep_highest_vertex_and_all_points() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0, 86.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0, 115.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [item.point.price for item in result.suppressed] == [110.0, 115.0]
    assert all(
        item.reason is MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND
        for item in result.suppressed
    )


def test_consecutive_medium_lows_keep_lowest_vertex_and_all_points() -> None:
    source = alternating_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0, 135.0, 136.0],
        low_prices=[120.0, 90.0, 100.0, 80.0, 95.0, 85.0, 110.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 80.0, 85.0]
    assert [point.price for point in result.vertices] == [80.0]
    assert [item.point.price for item in result.suppressed] == [90.0, 85.0]


def test_equal_highest_medium_high_keeps_earliest_pivot() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 105.0, 110.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 110.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed == (
        SuppressedMediumTermPoint(
            result.points[1],
            MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
    )


def test_equal_lowest_medium_low_keeps_earliest_pivot() -> None:
    source = alternating_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0],
        low_prices=[120.0, 90.0, 100.0, 90.0, 110.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 90.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed[0].point is result.points[1]


def test_same_kind_normalization_does_not_change_potentials() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 125.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [potential.price for potential in result.potentials] == [125.0]


def paired_medium_source(
    earlier_high: float,
    earlier_low: float,
    later_high: float,
    later_low: float,
    *,
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> ShortTermStructure:
    return alternating_source(
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
def test_complete_inside_pair_is_suppressed_in_both_orientations(
    first_kind: IsolatedPointKind,
) -> None:
    source = paired_medium_source(
        110.0,
        100.0,
        108.0,
        102.0,
        first_kind=first_kind,
    )

    result = build_medium_term_structure(source)

    assert len(result.points) == 4
    assert result.vertices == result.points[:2]
    assert result.suppressed == tuple(
        SuppressedMediumTermPoint(
            point,
            MediumTermSuppressionReason.INSIDE_STRUCTURE,
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
def test_equality_at_medium_inside_boundary_counts_as_contained(
    later_high: float,
    later_low: float,
) -> None:
    source = paired_medium_source(110.0, 100.0, later_high, later_low)

    result = build_medium_term_structure(source)

    assert result.vertices == result.points[:2]


@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (111.0, 102.0),
        (108.0, 99.0),
    ],
)
def test_one_side_breakout_preserves_later_medium_pair(
    later_high: float,
    later_low: float,
) -> None:
    source = paired_medium_source(110.0, 100.0, later_high, later_low)

    result = build_medium_term_structure(source)

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_incomplete_later_medium_range_is_preserved() -> None:
    source = alternating_source(
        high_prices=[105.0, 110.0, 104.0, 108.0, 103.0],
        low_prices=[105.0, 100.0, 106.0, 107.0, 108.0],
    )

    result = build_medium_term_structure(source)

    assert [(point.kind, point.price) for point in result.points] == [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 100.0),
        (IsolatedPointKind.HIGH, 108.0),
    ]
    assert result.vertices == result.points
    assert result.suppressed == ()


def test_repeated_inside_medium_pairs_normalize_until_stable() -> None:
    source = alternating_source(
        high_prices=[100.0, 120.0, 99.0, 115.0, 98.0, 110.0, 97.0],
        low_prices=[110.0, 90.0, 111.0, 95.0, 112.0, 100.0, 113.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.vertices] == [120.0, 90.0]
    assert [item.point for item in result.suppressed] == list(result.points[2:])
    assert all(
        item.reason is MediumTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.suppressed
    )


def test_inside_pair_is_compared_with_immediately_previous_pair() -> None:
    source = alternating_source(
        high_prices=[105.0, 110.0, 104.0, 120.0, 103.0, 115.0, 102.0],
        low_prices=[105.0, 100.0, 106.0, 90.0, 107.0, 95.0, 108.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.vertices] == [110.0, 100.0, 120.0, 90.0]
    assert [item.point.price for item in result.suppressed] == [115.0, 95.0]
    assert all(
        item.reason is MediumTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.suppressed
    )


def test_non_contained_layout_is_preserved_without_chart_matching() -> None:
    source = paired_medium_source(110.0, 100.0, 115.0, 95.0)

    result = build_medium_term_structure(source)

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_suppression_order_is_phase_then_pivot_chronology() -> None:
    source = alternating_source(
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

    result = build_medium_term_structure(source)

    reasons = [item.reason for item in result.suppressed]
    assert reasons[0] is MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND
    assert reasons[1:] == [
        MediumTermSuppressionReason.INSIDE_STRUCTURE,
        MediumTermSuppressionReason.INSIDE_STRUCTURE,
    ]


def test_course_evidence_attachment_preserves_all_canonical_output() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0],
        low_prices=[90.0, 91.0, 92.0],
    )
    structure = build_medium_term_structure(source)
    evidence = MediumCourseEvidence(
        structure.points[0],
        CourseRuleMatch.UNKNOWN,
    )

    enriched = attach_course_evidence(structure, [evidence])

    assert enriched.points == structure.points
    assert enriched.potentials == structure.potentials
    assert enriched.vertices == structure.vertices
    assert enriched.suppressed == structure.suppressed
    assert enriched.course_evidence == (evidence,)
    assert structure.course_evidence == ()


def test_course_evidence_requires_an_existing_confirmed_point() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0],
        low_prices=[90.0, 91.0, 92.0],
    )
    structure = build_medium_term_structure(source)
    unrelated = MediumTermPoint(
        short_point(20, IsolatedPointKind.HIGH, 130.0),
        short_point(22, IsolatedPointKind.HIGH, 125.0),
    )

    with pytest.raises(ValueError, match="requires a confirmed medium point"):
        attach_course_evidence(
            structure,
            [MediumCourseEvidence(unrelated, CourseRuleMatch.YES)],
        )
