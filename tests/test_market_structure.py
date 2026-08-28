from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    StructureRelationship,
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
