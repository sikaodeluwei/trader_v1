from dataclasses import FrozenInstanceError
from importlib import import_module
from types import ModuleType

import pytest

from trading.definitions.candles import Candle


def load_isolated_points() -> ModuleType:
    return import_module("trading.definitions.isolated_points")


def make_candle(high: float, low: float, bullish: bool = True) -> Candle:
    price_range = high - low
    lower_body = low + price_range * 0.25
    upper_body = low + price_range * 0.75
    open_price, close_price = (
        (lower_body, upper_body)
        if bullish
        else (upper_body, lower_body)
    )
    return Candle(
        open=open_price,
        high=high,
        low=low,
        close=close_price,
    )


@pytest.mark.parametrize(
    ("left", "current", "expected_kind", "expected_price"),
    [
        (make_candle(10, 5), make_candle(12, 7), "high", 12.0),
        (make_candle(10, 5), make_candle(8, 3), "low", 3.0),
        (make_candle(10, 5), make_candle(12, 4), None, None),
    ],
)
def test_get_potential_isolated_point_uses_strict_two_candle_structure(
    left: Candle,
    current: Candle,
    expected_kind: str | None,
    expected_price: float | None,
) -> None:
    isolated_points = load_isolated_points()

    point = isolated_points.get_potential_isolated_point(
        left,
        current,
        index=4,
    )

    if expected_kind is None:
        assert point is None
        return

    assert point == isolated_points.IsolatedPoint(
        index=4,
        kind=isolated_points.IsolatedPointKind(expected_kind),
        status=isolated_points.IsolatedPointStatus.POTENTIAL,
        price=expected_price,
    )


@pytest.mark.parametrize(
    ("kind", "middle", "right", "expected_price"),
    [
        ("high", make_candle(12, 7), make_candle(11, 6), 12.0),
        ("high", make_candle(12, 7), make_candle(13, 6), None),
        ("low", make_candle(8, 3), make_candle(9, 4), 3.0),
        ("low", make_candle(8, 3), make_candle(7, 4), None),
    ],
)
def test_confirm_isolated_point_confirms_or_rejects_using_right_candle(
    kind: str,
    middle: Candle,
    right: Candle,
    expected_price: float | None,
) -> None:
    isolated_points = load_isolated_points()
    point = isolated_points.IsolatedPoint(
        index=2,
        kind=isolated_points.IsolatedPointKind(kind),
        status=isolated_points.IsolatedPointStatus.POTENTIAL,
        price=middle.high if kind == "high" else middle.low,
    )

    result = isolated_points.confirm_isolated_point(point, middle, right)

    if expected_price is None:
        assert result is None
        return

    assert result == isolated_points.IsolatedPoint(
        index=2,
        kind=isolated_points.IsolatedPointKind(kind),
        status=isolated_points.IsolatedPointStatus.CONFIRMED,
        price=expected_price,
    )


@pytest.mark.parametrize(
    ("left", "middle", "right", "expected_kind", "expected_price"),
    [
        (
            make_candle(10, 5),
            make_candle(12, 7),
            make_candle(11, 6),
            "high",
            12.0,
        ),
        (
            make_candle(10, 5),
            make_candle(8, 3),
            make_candle(9, 4),
            "low",
            3.0,
        ),
    ],
)
def test_detect_confirmed_isolated_point_applies_strict_definition(
    left: Candle,
    middle: Candle,
    right: Candle,
    expected_kind: str,
    expected_price: float,
) -> None:
    isolated_points = load_isolated_points()

    point = isolated_points.detect_confirmed_isolated_point(
        left,
        middle,
        right,
        index=1,
    )

    assert point == isolated_points.IsolatedPoint(
        index=1,
        kind=isolated_points.IsolatedPointKind(expected_kind),
        status=isolated_points.IsolatedPointStatus.CONFIRMED,
        price=expected_price,
    )


@pytest.mark.parametrize("bullish", [True, False])
def test_isolated_point_detection_does_not_use_middle_candle_color(
    bullish: bool,
) -> None:
    isolated_points = load_isolated_points()

    point = isolated_points.detect_confirmed_isolated_point(
        make_candle(10, 5),
        make_candle(12, 7, bullish=bullish),
        make_candle(11, 6),
        index=1,
    )

    assert point is not None
    assert point.kind is isolated_points.IsolatedPointKind.HIGH


def test_equal_high_prevents_strict_isolated_high() -> None:
    isolated_points = load_isolated_points()

    point = isolated_points.detect_confirmed_isolated_point(
        make_candle(10, 5),
        make_candle(12, 7),
        make_candle(12, 6),
        index=1,
    )

    assert point is None


def test_equal_low_prevents_strict_isolated_low() -> None:
    isolated_points = load_isolated_points()

    point = isolated_points.detect_confirmed_isolated_point(
        make_candle(10, 5),
        make_candle(8, 3),
        make_candle(9, 3),
        index=1,
    )

    assert point is None


def alternating_candles() -> list[Candle]:
    return [
        make_candle(10, 5),
        make_candle(12, 7),
        make_candle(9, 4),
        make_candle(11, 6),
        make_candle(8, 3),
    ]


def test_find_confirmed_isolated_points_preserves_indexes_and_order() -> None:
    isolated_points = load_isolated_points()

    points = isolated_points.find_confirmed_isolated_points(
        alternating_candles()
    )

    assert [(point.index, point.kind.value, point.price) for point in points] == [
        (1, "high", 12.0),
        (2, "low", 4.0),
        (3, "high", 11.0),
    ]


@pytest.mark.parametrize(
    "candles",
    [
        [],
        [make_candle(10, 5)],
        [make_candle(10, 5), make_candle(12, 7)],
    ],
)
def test_find_confirmed_isolated_points_returns_empty_for_short_sequences(
    candles: list[Candle],
) -> None:
    isolated_points = load_isolated_points()

    assert isolated_points.find_confirmed_isolated_points(candles) == []


def test_tracker_first_candle_produces_no_state_change() -> None:
    isolated_points = load_isolated_points()
    tracker = isolated_points.IsolatedPointTracker()

    assert tracker.add_candle(make_candle(10, 5)) == []


def test_tracker_second_candle_can_create_a_potential_point() -> None:
    isolated_points = load_isolated_points()
    tracker = isolated_points.IsolatedPointTracker()
    tracker.add_candle(make_candle(10, 5))

    changes = tracker.add_candle(make_candle(12, 7))

    assert changes == [
        isolated_points.IsolatedPoint(
            index=1,
            kind=isolated_points.IsolatedPointKind.HIGH,
            status=isolated_points.IsolatedPointStatus.POTENTIAL,
            price=12.0,
        )
    ]


def test_tracker_third_candle_confirms_previous_and_creates_next_potential() -> None:
    isolated_points = load_isolated_points()
    tracker = isolated_points.IsolatedPointTracker()
    tracker.add_candle(make_candle(10, 5))
    tracker.add_candle(make_candle(12, 7))

    changes = tracker.add_candle(make_candle(9, 4))

    observed_changes = [
        (point.index, point.kind.value, point.status.value)
        for point in changes
    ]
    assert observed_changes == [
        (1, "high", "confirmed"),
        (2, "low", "potential"),
    ]


def test_tracker_uses_full_middle_ohlc_when_rejecting_a_potential() -> None:
    isolated_points = load_isolated_points()
    tracker = isolated_points.IsolatedPointTracker()
    tracker.add_candle(make_candle(10, 5))
    tracker.add_candle(make_candle(12, 7))

    changes = tracker.add_candle(make_candle(11, 8))

    assert changes == []


def test_tracker_confirmed_points_match_strict_sequence_scanning() -> None:
    isolated_points = load_isolated_points()
    candles = alternating_candles()
    tracker = isolated_points.IsolatedPointTracker()
    incremental_confirmed = []

    for candle in candles:
        incremental_confirmed.extend(
            point
            for point in tracker.add_candle(candle)
            if point.status is isolated_points.IsolatedPointStatus.CONFIRMED
        )

    assert incremental_confirmed == (
        isolated_points.find_confirmed_isolated_points(candles)
    )


def test_isolated_point_is_immutable() -> None:
    isolated_points = load_isolated_points()
    point = isolated_points.IsolatedPoint(
        index=1,
        kind=isolated_points.IsolatedPointKind.HIGH,
        status=isolated_points.IsolatedPointStatus.POTENTIAL,
        price=12.0,
    )

    with pytest.raises(FrozenInstanceError):
        point.price = 13.0
