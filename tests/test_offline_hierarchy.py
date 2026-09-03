from importlib import import_module
from importlib.util import find_spec
from types import ModuleType

import pytest

from trading.analysis.isolated import IsolatedPointScan
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
    ShortTermSuppressionReason,
    build_short_term_structure,
    short_term_point_from_recognition,
)
from trading.definitions.medium_term_structure import build_medium_term_structure
from trading.definitions.long_term_structure import build_long_term_structure


def load_hierarchy() -> ModuleType:
    return import_module("trading.analysis.hierarchy")


def test_hierarchy_module_is_discoverable_with_required_docstring() -> None:
    assert find_spec("trading.analysis.hierarchy") is not None
    hierarchy = load_hierarchy()
    assert hierarchy.__doc__


def test_hierarchy_module_exports_locked_composition_name() -> None:
    spec = find_spec("trading.analysis.hierarchy")
    assert spec is not None
    hierarchy = load_hierarchy()
    assert hasattr(hierarchy, "StructuralHierarchy")
    assert hasattr(hierarchy, "build_structural_hierarchy")
    assert callable(hierarchy.build_structural_hierarchy)


def recognition(
    index: int,
    kind: IsolatedPointKind,
    price: float,
    basis: IsolatedPointBasis = IsolatedPointBasis.STRICT,
) -> IsolatedPointRecognition:
    return IsolatedPointRecognition(
        IsolatedPoint(index, kind, IsolatedPointStatus.CONFIRMED, price),
        basis,
    )


def scan(*recognitions: IsolatedPointRecognition) -> IsolatedPointScan:
    return IsolatedPointScan(tuple(recognitions), None)


def build_hierarchy(isolated: IsolatedPointScan) -> object:
    return load_hierarchy().build_structural_hierarchy(isolated)


def expected_hierarchy(isolated: IsolatedPointScan) -> object:
    short_term = build_short_term_structure(
        tuple(
            short_term_point_from_recognition(item)
            for item in isolated.recognitions
        )
    )
    medium_term = build_medium_term_structure(short_term)
    long_term = build_long_term_structure(medium_term)
    return load_hierarchy().StructuralHierarchy(
        isolated,
        short_term,
        medium_term,
        long_term,
    )


def alternating_recognitions(
    high_prices: list[float],
    low_prices: list[float],
    *,
    inside_high_position: int | None = None,
) -> tuple[IsolatedPointRecognition, ...]:
    assert len(high_prices) == len(low_prices)
    result: list[IsolatedPointRecognition] = []
    for position, (high, low) in enumerate(zip(high_prices, low_prices)):
        basis = (
            IsolatedPointBasis.RIGHT_INSIDE_BAR
            if position == inside_high_position
            else IsolatedPointBasis.STRICT
        )
        result.extend(
            (
                recognition(position * 2 + 1, IsolatedPointKind.HIGH, high, basis),
                recognition(position * 2 + 2, IsolatedPointKind.LOW, low),
            )
        )
    return tuple(result)


def test_composes_supplied_recognitions_through_all_structural_levels() -> None:
    recognitions = alternating_recognitions(
        high_prices=[100, 110, 105, 120, 107, 115, 100],
        low_prices=[90, 95, 80, 96, 85, 97, 70],
        inside_high_position=3,
    )
    isolated = scan(*recognitions)

    result = build_hierarchy(isolated)

    assert result == expected_hierarchy(isolated)
    expected_short_points = tuple(
        short_term_point_from_recognition(item) for item in recognitions
    )
    assert result.isolated is isolated
    assert result.short_term.points == expected_short_points
    assert result.short_term.vertices == expected_short_points
    assert result.short_term.points[6].recognition_basis is recognitions[6].basis
    assert [point.price for point in result.medium_term.vertices] == [
        110,
        80,
        120,
        85,
        115,
    ]
    medium_high_120 = result.medium_term.vertices[2]
    medium_high_115 = result.medium_term.vertices[4]
    assert medium_high_120.pivot is result.short_term.vertices[6]
    assert medium_high_120.confirmed_by is result.short_term.vertices[8]
    assert medium_high_115.pivot is result.short_term.vertices[10]
    long_high = result.long_term.points[0]
    assert long_high.pivot is medium_high_120
    assert long_high.confirmed_by is medium_high_115
    assert long_high.pivot.pivot.recognition_basis is recognitions[6].basis


def test_consecutive_same_kind_recognitions_stay_short_but_promote_only_winner() -> None:
    isolated = scan(
        recognition(1, IsolatedPointKind.LOW, 90),
        recognition(2, IsolatedPointKind.HIGH, 108),
        recognition(3, IsolatedPointKind.HIGH, 110),
        recognition(4, IsolatedPointKind.HIGH, 109),
        recognition(5, IsolatedPointKind.LOW, 95),
    )

    result = build_hierarchy(isolated)

    assert result == expected_hierarchy(isolated)
    assert [point.price for point in result.short_term.points] == [90, 108, 110, 109, 95]
    assert [point.price for point in result.short_term.vertices] == [90, 110, 95]
    assert [item.point.price for item in result.short_term.suppressed] == [108, 109]
    assert all(
        item.reason is ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND
        for item in result.short_term.suppressed
    )


def test_later_inclusive_inside_pair_is_suppressed_before_promotion() -> None:
    isolated = scan(
        recognition(1, IsolatedPointKind.HIGH, 110),
        recognition(2, IsolatedPointKind.LOW, 100),
        recognition(3, IsolatedPointKind.HIGH, 108),
        recognition(4, IsolatedPointKind.LOW, 102),
    )

    result = build_hierarchy(isolated)

    assert result == expected_hierarchy(isolated)
    assert [point.price for point in result.short_term.points] == [110, 100, 108, 102]
    assert [point.price for point in result.short_term.vertices] == [110, 100]
    assert [item.point.price for item in result.short_term.suppressed] == [108, 102]
    assert all(
        item.reason is ShortTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.short_term.suppressed
    )


@pytest.mark.parametrize(
    ("kind", "other_kind", "price", "other_price"),
    [
        (IsolatedPointKind.HIGH, IsolatedPointKind.LOW, 110, 90),
        (IsolatedPointKind.LOW, IsolatedPointKind.HIGH, 90, 110),
    ],
)
def test_equal_extreme_ties_keep_earliest_short_vertex(
    kind: IsolatedPointKind,
    other_kind: IsolatedPointKind,
    price: float,
    other_price: float,
) -> None:
    isolated = scan(
        recognition(1, kind, price),
        recognition(2, kind, price),
        recognition(3, other_kind, other_price),
    )

    result = build_hierarchy(isolated)

    assert result == expected_hierarchy(isolated)
    assert result.short_term.vertices[0] is result.short_term.points[0]
    assert result.short_term.suppressed[0].point is result.short_term.points[1]
    assert result.short_term.suppressed[0].reason is (
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND
    )


def test_right_edge_candidates_remain_existing_medium_and_long_potentials() -> None:
    medium_candidate_result = build_hierarchy(
        scan(
            *alternating_recognitions(
                high_prices=[100, 110],
                low_prices=[90, 80],
            )
        )
    )
    long_candidate_result = build_hierarchy(
        scan(
            *alternating_recognitions(
                high_prices=[100, 110, 105, 120, 115],
                low_prices=[90, 95, 80, 96, 85],
            )
        )
    )

    assert medium_candidate_result == expected_hierarchy(
        medium_candidate_result.isolated
    )
    assert long_candidate_result == expected_hierarchy(
        long_candidate_result.isolated
    )
    assert [point.price for point in medium_candidate_result.medium_term.potentials] == [
        110,
        80,
    ]
    assert medium_candidate_result.medium_term.potentials[0].pivot is (
        medium_candidate_result.short_term.vertices[2]
    )
    assert medium_candidate_result.medium_term.potentials[1].pivot is (
        medium_candidate_result.short_term.vertices[3]
    )
    assert [point.price for point in long_candidate_result.long_term.potentials] == [120]
    assert long_candidate_result.long_term.potentials[0].pivot is (
        long_candidate_result.medium_term.vertices[2]
    )


def test_suppressed_short_points_never_become_promotion_neighbors() -> None:
    isolated = scan(
        recognition(1, IsolatedPointKind.HIGH, 100),
        recognition(2, IsolatedPointKind.LOW, 90),
        recognition(3, IsolatedPointKind.HIGH, 108),
        recognition(4, IsolatedPointKind.HIGH, 110),
        recognition(5, IsolatedPointKind.HIGH, 109),
        recognition(6, IsolatedPointKind.LOW, 95),
        recognition(7, IsolatedPointKind.HIGH, 105),
        recognition(8, IsolatedPointKind.LOW, 80),
        recognition(9, IsolatedPointKind.HIGH, 120),
        recognition(10, IsolatedPointKind.LOW, 96),
        recognition(11, IsolatedPointKind.HIGH, 107),
        recognition(12, IsolatedPointKind.LOW, 85),
        recognition(13, IsolatedPointKind.HIGH, 115),
        recognition(14, IsolatedPointKind.LOW, 97),
        recognition(15, IsolatedPointKind.HIGH, 100),
        recognition(16, IsolatedPointKind.LOW, 70),
    )

    result = build_hierarchy(isolated)

    assert result == expected_hierarchy(isolated)
    suppressed = {item.point for item in result.short_term.suppressed}
    promoted_neighbors = {
        point
        for medium_point in result.medium_term.points
        for point in (medium_point.pivot, medium_point.confirmed_by)
    }
    assert suppressed
    assert not suppressed & promoted_neighbors
    assert all(
        point in result.short_term.vertices for point in promoted_neighbors
    )
    assert all(
        long_point.pivot in result.medium_term.vertices
        and long_point.confirmed_by in result.medium_term.vertices
        for long_point in result.long_term.points
    )
