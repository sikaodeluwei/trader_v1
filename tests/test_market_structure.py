from dataclasses import FrozenInstanceError

import pytest

from trading.definitions import market_structure
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    StructureRelationship,
    classify_market_state,
    compare_structure_points,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def test_market_segment_accepts_inclusive_equal_boundaries() -> None:
    assert MarketSegment(4, 4) == MarketSegment(start_index=4, end_index=4)


@pytest.mark.parametrize(("start_index", "end_index"), [(2, 1), (1, -1)])
def test_market_segment_rejects_start_after_end(
    start_index: int,
    end_index: int,
) -> None:
    with pytest.raises(ValueError, match="start_index"):
        MarketSegment(start_index, end_index)


def test_market_structure_enum_values_are_stable() -> None:
    assert {kind.value for kind in StructurePointKind} == {"high", "low"}
    assert {relationship.value for relationship in StructureRelationship} == {
        "higher_high",
        "lower_high",
        "equal_high",
        "higher_low",
        "lower_low",
        "equal_low",
    }
    assert {state.value for state in MarketState} == {
        "uptrend",
        "downtrend",
        "non_trend",
    }


def test_structure_point_preserves_caller_supplied_values() -> None:
    assert high(7, 112.5) == StructurePoint(
        index=7,
        kind=StructurePointKind.HIGH,
        price=112.5,
    )


@pytest.mark.parametrize(
    "instance",
    [MarketSegment(0, 2), high(0, 100.0), low(1, 90.0)],
)
def test_market_structure_dataclasses_are_frozen(instance: object) -> None:
    with pytest.raises(FrozenInstanceError):
        instance.index = 99  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("previous", "later", "expected"),
    [
        (high(1, 100.0), high(2, 110.0), StructureRelationship.HIGHER_HIGH),
        (high(1, 100.0), high(2, 90.0), StructureRelationship.LOWER_HIGH),
        (high(1, 100.0), high(2, 100.0), StructureRelationship.EQUAL_HIGH),
        (low(1, 90.0), low(2, 95.0), StructureRelationship.HIGHER_LOW),
        (low(1, 90.0), low(2, 85.0), StructureRelationship.LOWER_LOW),
        (low(1, 90.0), low(2, 90.0), StructureRelationship.EQUAL_LOW),
    ],
)
def test_compare_structure_points_returns_same_kind_relationship(
    previous: StructurePoint,
    later: StructurePoint,
    expected: StructureRelationship,
) -> None:
    assert compare_structure_points(previous, later) is expected


def test_compare_structure_points_rejects_different_kinds() -> None:
    with pytest.raises(ValueError, match="same kind"):
        compare_structure_points(high(1, 100.0), low(2, 90.0))


@pytest.mark.parametrize("later_index", [3, 2])
def test_compare_structure_points_rejects_non_increasing_chronology(
    later_index: int,
) -> None:
    with pytest.raises(ValueError, match="chronological"):
        compare_structure_points(high(3, 100.0), high(later_index, 110.0))


def test_classify_market_state_accepts_minimum_uptrend() -> None:
    points = [
        high(0, 100.0),
        low(1, 90.0),
        high(2, 110.0),
        low(3, 95.0),
    ]

    assert classify_market_state(MarketSegment(0, 3), points) is MarketState.UPTREND


def test_classify_market_state_accepts_minimum_downtrend() -> None:
    points = [
        high(0, 110.0),
        low(1, 100.0),
        high(2, 105.0),
        low(3, 90.0),
    ]

    assert classify_market_state(MarketSegment(0, 3), points) is MarketState.DOWNTREND


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        (
            [
                high(0, 100.0),
                low(1, 90.0),
                high(2, 110.0),
                low(3, 95.0),
                high(4, 120.0),
                low(5, 100.0),
            ],
            MarketState.UPTREND,
        ),
        (
            [
                high(0, 120.0),
                low(1, 100.0),
                high(2, 110.0),
                low(3, 90.0),
                high(4, 105.0),
                low(5, 80.0),
            ],
            MarketState.DOWNTREND,
        ),
    ],
)
def test_classify_market_state_accepts_extended_continuous_trends(
    points: list[StructurePoint],
    expected: MarketState,
) -> None:
    assert classify_market_state(MarketSegment(0, 5), points) is expected


@pytest.mark.parametrize(
    "points",
    [
        [],
        [high(0, 100.0), low(1, 90.0), low(2, 95.0)],
        [high(0, 100.0), high(1, 110.0), low(2, 90.0)],
    ],
)
def test_classify_market_state_returns_non_trend_for_insufficient_points(
    points: list[StructurePoint],
) -> None:
    assert classify_market_state(MarketSegment(0, 2), points) is MarketState.NON_TREND


@pytest.mark.parametrize(
    "points",
    [
        [high(0, 100.0), low(1, 90.0), high(2, 100.0), low(3, 95.0)],
        [high(0, 100.0), low(1, 90.0), high(2, 110.0), low(3, 90.0)],
    ],
)
def test_classify_market_state_returns_non_trend_for_equality(
    points: list[StructurePoint],
) -> None:
    assert classify_market_state(MarketSegment(0, 3), points) is MarketState.NON_TREND


def test_classify_market_state_rejects_interrupted_direction_as_non_trend() -> None:
    points = [
        high(0, 100.0),
        low(1, 90.0),
        high(2, 110.0),
        low(3, 95.0),
        high(4, 105.0),
        low(5, 100.0),
    ]

    assert classify_market_state(MarketSegment(0, 5), points) is MarketState.NON_TREND


def test_classify_market_state_does_not_skip_intermediate_same_kind_point() -> None:
    points = [
        high(0, 100.0),
        low(1, 90.0),
        high(2, 95.0),
        low(3, 100.0),
        high(4, 110.0),
        low(5, 105.0),
    ]

    assert classify_market_state(MarketSegment(0, 5), points) is MarketState.NON_TREND


def test_classify_market_state_requires_explicit_segment() -> None:
    points = [high(0, 100.0), low(1, 90.0), high(2, 110.0), low(3, 95.0)]

    with pytest.raises(TypeError):
        classify_market_state(points)  # type: ignore[call-arg]


def test_classify_market_state_includes_segment_boundaries() -> None:
    points = [high(10, 100.0), low(11, 90.0), high(12, 110.0), low(13, 95.0)]

    assert classify_market_state(MarketSegment(10, 13), points) is MarketState.UPTREND


@pytest.mark.parametrize(
    ("segment", "points"),
    [
        (
            MarketSegment(0, 3),
            [high(-1, 100.0), low(0, 90.0), high(1, 110.0), low(2, 95.0)],
        ),
        (
            MarketSegment(0, 2),
            [high(0, 100.0), low(1, 90.0), high(2, 110.0), low(3, 95.0)],
        ),
    ],
)
def test_classify_market_state_rejects_out_of_segment_points(
    segment: MarketSegment,
    points: list[StructurePoint],
) -> None:
    with pytest.raises(ValueError, match="outside segment"):
        classify_market_state(segment, points)


def test_classify_market_state_rejects_decreasing_caller_order() -> None:
    points = [high(0, 100.0), low(2, 90.0), high(1, 110.0), low(3, 95.0)]

    with pytest.raises(ValueError, match="chronological"):
        classify_market_state(MarketSegment(0, 3), points)


def test_classify_market_state_rejects_duplicate_same_kind_index() -> None:
    points = [high(0, 100.0), low(0, 90.0), high(0, 110.0), low(1, 95.0)]

    with pytest.raises(ValueError, match="same-kind"):
        classify_market_state(MarketSegment(0, 1), points)


def test_classify_market_state_allows_high_and_low_at_same_index() -> None:
    points = [high(0, 100.0), low(0, 90.0), high(1, 110.0), low(1, 95.0)]

    assert classify_market_state(MarketSegment(0, 1), points) is MarketState.UPTREND


def test_market_state_resolution_rejects_contradictory_candidates() -> None:
    with pytest.raises(ValueError, match="contradictory"):
        market_structure._resolve_market_state(uptrend=True, downtrend=True)
