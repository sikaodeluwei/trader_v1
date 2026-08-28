from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    StructureRelationship,
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
