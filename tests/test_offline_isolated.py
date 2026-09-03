from dataclasses import FrozenInstanceError
from importlib import import_module

import pytest

from trading.definitions.candles import Candle
from trading.definitions.isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)


def load_isolated() -> object:
    return import_module("trading.analysis.isolated")


def make_candle(high: float, low: float) -> Candle:
    return Candle(
        open=low + (high - low) * 0.25,
        high=high,
        low=low,
        close=low + (high - low) * 0.75,
    )


def fixture_candles() -> list[Candle]:
    return [make_candle(high, low) for high, low in [
        (10, 5),
        (12, 7),
        (11, 6),
        (13, 8),
        (13, 9),
        (15, 10),
        (15, 8),
        (12, 7),
    ]]


def test_scan_collects_strict_deformed_and_unresolved_points_with_offset() -> None:
    isolated = load_isolated()

    result = isolated.find_isolated_point_recognitions(
        fixture_candles(), start_index=100
    )

    assert result.recognitions == (
        isolated.IsolatedPointRecognition(
            point=IsolatedPoint(101, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 12),
            basis=isolated.IsolatedPointBasis.STRICT,
        ),
        isolated.IsolatedPointRecognition(
            point=IsolatedPoint(102, IsolatedPointKind.LOW, IsolatedPointStatus.CONFIRMED, 6),
            basis=isolated.IsolatedPointBasis.STRICT,
        ),
        isolated.IsolatedPointRecognition(
            point=IsolatedPoint(103, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 13),
            basis=isolated.IsolatedPointBasis.RIGHT_INSIDE_BAR,
        ),
    )
    assert result.unresolved_potential == IsolatedPoint(
        107, IsolatedPointKind.LOW, IsolatedPointStatus.POTENTIAL, 7
    )


def test_scan_does_not_pre_suppress_chronological_recognitions() -> None:
    isolated = load_isolated()

    result = isolated.find_isolated_point_recognitions(fixture_candles())

    assert [recognition.point.index for recognition in result.recognitions] == [1, 2, 3]
    assert [recognition.point.kind for recognition in result.recognitions] == [
        IsolatedPointKind.HIGH,
        IsolatedPointKind.LOW,
        IsolatedPointKind.HIGH,
    ]


@pytest.mark.parametrize("candles", [[], [make_candle(10, 5)]])
def test_scan_short_inputs_are_neutral(candles: list[Candle]) -> None:
    isolated = load_isolated()

    result = isolated.find_isolated_point_recognitions(candles)

    assert result.recognitions == ()
    assert result.unresolved_potential is None


def test_scan_result_and_points_are_immutable() -> None:
    isolated = load_isolated()

    result = isolated.find_isolated_point_recognitions(fixture_candles())

    with pytest.raises(FrozenInstanceError):
        result.unresolved_potential = None


def test_replacement_equality_behavior_remains_separate() -> None:
    deformations = import_module("trading.definitions.isolated_point_deformations")
    existing = IsolatedPoint(1, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 10)
    equal = IsolatedPoint(4, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 10)

    assert deformations.replace_with_more_extreme_point(existing, equal) is existing
