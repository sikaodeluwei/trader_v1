from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from trading.definitions.isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    ShortTermSuppressionReason,
    SuppressedShortTermPoint,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def short_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> ShortTermPoint:
    return ShortTermPoint(index, kind, price, None)


def isolated_point(
    *,
    index: int = 3,
    kind: IsolatedPointKind = IsolatedPointKind.HIGH,
    status: IsolatedPointStatus = IsolatedPointStatus.CONFIRMED,
    price: float = 110.0,
) -> IsolatedPoint:
    return IsolatedPoint(index, kind, status, price)


def test_suppression_reason_values_are_stable() -> None:
    assert {reason.value for reason in ShortTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }


def test_short_term_records_preserve_values_and_are_frozen() -> None:
    point = ShortTermPoint(3, IsolatedPointKind.HIGH, 110.0, None)
    suppressed = SuppressedShortTermPoint(
        point,
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    structure = ShortTermStructure((point,), (point,), (suppressed,))

    assert structure.points == (point,)
    assert structure.vertices == (point,)
    assert structure.suppressed == (suppressed,)
    with pytest.raises(FrozenInstanceError):
        point.price = 111.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kind", "price"),
    [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 90.0),
    ],
)
def test_bare_confirmed_point_maps_without_recomputed_basis(
    kind: IsolatedPointKind,
    price: float,
) -> None:
    source = isolated_point(kind=kind, price=price)

    result = short_term_point_from_isolated_point(source)

    assert result == ShortTermPoint(
        index=source.index,
        kind=kind,
        price=price,
        recognition_basis=None,
    )


@pytest.mark.parametrize(
    "basis",
    [IsolatedPointBasis.STRICT, IsolatedPointBasis.RIGHT_INSIDE_BAR],
)
def test_recognition_mapping_preserves_exact_basis(
    basis: IsolatedPointBasis,
) -> None:
    source = isolated_point()
    recognition = IsolatedPointRecognition(source, basis)

    result = short_term_point_from_recognition(recognition)

    assert result == ShortTermPoint(
        source.index,
        source.kind,
        source.price,
        basis,
    )
    assert result.recognition_basis is basis


def test_bare_mapping_rejects_potential_point() -> None:
    with pytest.raises(ValueError, match="requires a confirmed isolated point"):
        short_term_point_from_isolated_point(
            isolated_point(status=IsolatedPointStatus.POTENTIAL)
        )


def test_recognition_mapping_rejects_wrapped_potential_point() -> None:
    recognition = IsolatedPointRecognition(
        isolated_point(status=IsolatedPointStatus.POTENTIAL),
        IsolatedPointBasis.RIGHT_INSIDE_BAR,
    )

    with pytest.raises(ValueError, match="requires a confirmed isolated point"):
        short_term_point_from_recognition(recognition)


def test_empty_points_return_empty_structure() -> None:
    assert build_short_term_structure(()) == ShortTermStructure((), (), ())


def test_one_point_remains_one_point_and_vertex() -> None:
    point = short_point(4, IsolatedPointKind.HIGH, 110.0)

    assert build_short_term_structure([point]) == ShortTermStructure(
        points=(point,),
        vertices=(point,),
        suppressed=(),
    )


def test_two_opposite_kind_points_remain_chronological_vertices() -> None:
    points = [
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
    ]

    assert build_short_term_structure(points).vertices == tuple(points)


@pytest.mark.parametrize(
    "points",
    [
        [
            short_point(2, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 100.0),
        ],
        [
            short_point(1, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 100.0),
        ],
    ],
)
def test_builder_rejects_non_increasing_indexes(
    points: list[ShortTermPoint],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_short_term_structure(points)


def test_complete_chronology_is_validated_before_normalization() -> None:
    points = [
        short_point(1, IsolatedPointKind.HIGH, 108.0),
        short_point(3, IsolatedPointKind.HIGH, 110.0),
        short_point(2, IsolatedPointKind.HIGH, 109.0),
    ]

    with pytest.raises(ValueError, match="strictly increasing"):
        build_short_term_structure(points)


def test_alternating_points_remain_unchanged() -> None:
    points = [
        short_point(0, IsolatedPointKind.LOW, 100.0),
        short_point(1, IsolatedPointKind.HIGH, 110.0),
        short_point(2, IsolatedPointKind.LOW, 103.0),
        short_point(3, IsolatedPointKind.HIGH, 112.0),
    ]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == tuple(points)
    assert result.suppressed == ()


def test_consecutive_high_run_keeps_highest_vertex_and_all_points() -> None:
    points = [
        short_point(0, IsolatedPointKind.LOW, 100.0),
        short_point(1, IsolatedPointKind.HIGH, 108.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
        short_point(3, IsolatedPointKind.HIGH, 109.0),
        short_point(4, IsolatedPointKind.LOW, 103.0),
    ]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == (points[0], points[2], points[4])
    assert result.suppressed == (
        SuppressedShortTermPoint(
            points[1],
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
        SuppressedShortTermPoint(
            points[3],
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
    )


def test_consecutive_low_run_keeps_lowest_vertex() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 102.0),
        short_point(2, IsolatedPointKind.LOW, 98.0),
        short_point(3, IsolatedPointKind.LOW, 100.0),
        short_point(4, IsolatedPointKind.HIGH, 108.0),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == (points[0], points[2], points[4])
    assert [item.point for item in result.suppressed] == [points[1], points[3]]


@pytest.mark.parametrize(
    ("kind", "price"),
    [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 90.0),
    ],
)
def test_equal_extreme_tie_keeps_earliest_vertex(
    kind: IsolatedPointKind,
    price: float,
) -> None:
    points = [
        short_point(1, kind, price),
        short_point(2, kind, price),
        short_point(3, kind, price),
    ]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == (points[0],)
    assert result.suppressed == tuple(
        SuppressedShortTermPoint(
            point,
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        )
        for point in points[1:]
    )


@pytest.mark.parametrize(
    "points",
    [
        [
            short_point(0, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 100.0),
            short_point(2, IsolatedPointKind.HIGH, 108.0),
            short_point(3, IsolatedPointKind.LOW, 102.0),
        ],
        [
            short_point(0, IsolatedPointKind.LOW, 100.0),
            short_point(1, IsolatedPointKind.HIGH, 110.0),
            short_point(2, IsolatedPointKind.LOW, 102.0),
            short_point(3, IsolatedPointKind.HIGH, 108.0),
        ],
    ],
)
def test_complete_inside_pair_is_suppressed_in_both_orientations(
    points: list[ShortTermPoint],
) -> None:
    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == tuple(points[:2])
    assert result.suppressed == tuple(
        SuppressedShortTermPoint(
            point,
            ShortTermSuppressionReason.INSIDE_STRUCTURE,
        )
        for point in points[2:]
    )


@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (110.0, 102.0),
        (108.0, 100.0),
        (110.0, 100.0),
    ],
)
def test_equality_at_either_inside_boundary_counts_as_contained(
    later_high: float,
    later_low: float,
) -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, later_high),
        short_point(3, IsolatedPointKind.LOW, later_low),
    ]

    assert build_short_term_structure(points).vertices == tuple(points[:2])


@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (111.0, 102.0),
        (108.0, 99.0),
    ],
)
def test_one_side_breakout_prevents_inside_suppression(
    later_high: float,
    later_low: float,
) -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, later_high),
        short_point(3, IsolatedPointKind.LOW, later_low),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == tuple(points)
    assert result.suppressed == ()


def test_repeated_inside_pairs_normalize_until_stable() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 120.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(2, IsolatedPointKind.HIGH, 115.0),
        short_point(3, IsolatedPointKind.LOW, 95.0),
        short_point(4, IsolatedPointKind.HIGH, 110.0),
        short_point(5, IsolatedPointKind.LOW, 100.0),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == tuple(points[:2])
    assert [item.point for item in result.suppressed] == points[2:]
    assert all(
        item.reason is ShortTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.suppressed
    )


def test_incomplete_later_range_is_preserved_without_invented_pairing() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, 108.0),
    ]

    assert build_short_term_structure(points).vertices == tuple(points)


def test_suppression_order_is_phase_then_chronology() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.HIGH, 112.0),
        short_point(2, IsolatedPointKind.LOW, 100.0),
        short_point(3, IsolatedPointKind.HIGH, 108.0),
        short_point(4, IsolatedPointKind.LOW, 102.0),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == (points[1], points[2])
    assert result.suppressed == (
        SuppressedShortTermPoint(
            points[0],
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
        SuppressedShortTermPoint(
            points[3],
            ShortTermSuppressionReason.INSIDE_STRUCTURE,
        ),
        SuppressedShortTermPoint(
            points[4],
            ShortTermSuppressionReason.INSIDE_STRUCTURE,
        ),
    )
