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
    point = MediumTermPoint(pivot, confirmation_index=7)
    potential = PotentialMediumTermPoint(short_point(1, IsolatedPointKind.HIGH, 105.0), pivot)
    suppressed = SuppressedMediumTermPoint(point, MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND)
    evidence = MediumCourseEvidence(point, CourseRuleMatch.UNKNOWN)
    structure = MediumTermStructure(
        points=(point,), potentials=(potential,), vertices=(point,), suppressed=(suppressed,), course_evidence=(evidence,)
    )

    assert point.pivot is pivot
    assert point.pivot_index == 3
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 112.0
    assert structure.course_evidence == (evidence,)
    with pytest.raises(FrozenInstanceError):
        point.confirmation_index = 8  # type: ignore[misc]


@pytest.mark.parametrize("confirmation_index", [2, 3])
def test_confirmed_point_requires_later_confirmation_index(confirmation_index: int) -> None:
    pivot = short_point(3, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="after pivot index"):
        MediumTermPoint(pivot, confirmation_index)


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
    assert point.pivot_index == 2
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 112.0
    assert point.confirmation_index == 4
    assert result.vertices == result.points


def test_basic_itl_uses_strict_same_kind_neighbors() -> None:
    source = alternating_source(
        high_prices=[110.0, 111.0, 112.0], low_prices=[100.0, 94.0, 98.0]
    )

    result = build_medium_term_structure(source)

    point = result.points[0]
    assert point.pivot is source.vertices[3]
    assert point.pivot_index == 3
    assert point.kind is IsolatedPointKind.LOW
    assert point.price == 94.0
    assert point.confirmation_index == 5


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
    assert result.points[0].confirmation_index == 4
    assert result.points[1].confirmation_index == 5


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
    assert after.points[0].confirmation_index == 5


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


def test_confirmed_points_use_pivot_order_and_keep_confirmation_timing() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0], low_prices=[100.0, 94.0, 98.0]
    )

    result = build_medium_term_structure(source)

    assert [point.pivot_index for point in result.points] == [2, 3]
    assert [point.confirmation_index for point in result.points] == [4, 5]
    assert all(point.confirmation_index > point.pivot_index for point in result.points)


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
