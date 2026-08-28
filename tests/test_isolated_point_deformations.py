from importlib import import_module
from types import ModuleType

import pytest

from trading.definitions.candles import Candle
from trading.definitions.isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
    IsolatedPointTracker,
    confirm_isolated_point,
    get_potential_isolated_point,
)


def load_deformations() -> ModuleType:
    return import_module("trading.definitions.isolated_point_deformations")


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
    ("inner", "expected"),
    [
        (make_candle(11, 8), True),
        (make_candle(12, 8), True),
        (make_candle(11, 7), True),
        (make_candle(13, 6), False),
        (make_candle(13, 8), False),
    ],
)
def test_is_inside_bar_uses_geometric_containment(
    inner: Candle,
    expected: bool,
) -> None:
    deformations = load_deformations()

    assert deformations.is_inside_bar(make_candle(12, 7), inner) is expected


def potential_high() -> tuple[IsolatedPoint, Candle]:
    middle = make_candle(12, 7)
    point = get_potential_isolated_point(make_candle(10, 5), middle, index=1)
    assert point is not None
    return point, middle


def potential_low() -> tuple[IsolatedPoint, Candle]:
    middle = make_candle(8, 3)
    point = get_potential_isolated_point(make_candle(10, 5), middle, index=1)
    assert point is not None
    return point, middle


def test_inside_bar_confirms_high_rejected_by_strict_rule() -> None:
    deformations = load_deformations()
    point, middle = potential_high()
    right = make_candle(12, 8)
    assert confirm_isolated_point(point, middle, right) is None

    recognition = deformations.confirm_isolated_point_with_deformation(
        point,
        middle,
        right,
    )

    assert recognition == deformations.IsolatedPointRecognition(
        point=IsolatedPoint(
            index=1,
            kind=IsolatedPointKind.HIGH,
            status=IsolatedPointStatus.CONFIRMED,
            price=12.0,
        ),
        basis=deformations.IsolatedPointBasis.RIGHT_INSIDE_BAR,
    )


def test_inside_bar_confirms_low_rejected_by_strict_rule() -> None:
    deformations = load_deformations()
    point, middle = potential_low()
    right = make_candle(7, 3)
    assert confirm_isolated_point(point, middle, right) is None

    recognition = deformations.confirm_isolated_point_with_deformation(
        point,
        middle,
        right,
    )

    assert recognition is not None
    assert recognition.point.kind is IsolatedPointKind.LOW
    assert recognition.point.price == 3.0
    assert recognition.basis is deformations.IsolatedPointBasis.RIGHT_INSIDE_BAR


@pytest.mark.parametrize(
    ("point_factory", "right"),
    [
        (potential_high, make_candle(11, 6)),
        (potential_low, make_candle(9, 4)),
    ],
)
def test_strict_confirmation_retains_strict_recognition_basis(
    point_factory,
    right: Candle,
) -> None:
    deformations = load_deformations()
    point, middle = point_factory()

    recognition = deformations.confirm_isolated_point_with_deformation(
        point,
        middle,
        right,
    )

    assert recognition is not None
    assert recognition.basis is deformations.IsolatedPointBasis.STRICT
    assert recognition.point.status is IsolatedPointStatus.CONFIRMED


def test_unrelated_right_candle_rejects_deformation_confirmation() -> None:
    deformations = load_deformations()
    point, middle = potential_high()

    recognition = deformations.confirm_isolated_point_with_deformation(
        point,
        middle,
        make_candle(13, 8),
    )

    assert recognition is None


@pytest.mark.parametrize("bullish", [True, False])
def test_deformation_confirmation_does_not_use_candle_color(
    bullish: bool,
) -> None:
    deformations = load_deformations()
    middle = make_candle(12, 7, bullish=bullish)
    point = get_potential_isolated_point(make_candle(10, 5), middle, index=1)
    assert point is not None

    recognition = deformations.confirm_isolated_point_with_deformation(
        point,
        middle,
        make_candle(12, 8, bullish=not bullish),
    )

    assert recognition is not None
    assert recognition.point.kind is IsolatedPointKind.HIGH


def test_strict_tracker_still_rejects_equal_high_inside_bar() -> None:
    tracker = IsolatedPointTracker()
    tracker.add_candle(make_candle(10, 5))
    tracker.add_candle(make_candle(12, 7))

    assert tracker.add_candle(make_candle(12, 8)) == []


def test_deformation_tracker_emits_raw_potential_before_confirmation() -> None:
    deformations = load_deformations()
    tracker = deformations.DeformationAwareIsolatedPointTracker()

    assert tracker.add_candle(make_candle(10, 5)) == []
    changes = tracker.add_candle(make_candle(12, 7))

    assert len(changes) == 1
    assert isinstance(changes[0], IsolatedPoint)
    assert changes[0].status is IsolatedPointStatus.POTENTIAL


@pytest.mark.parametrize(
    ("left", "middle", "right", "expected_kind", "expected_price"),
    [
        (
            make_candle(10, 5),
            make_candle(12, 7),
            make_candle(12, 8),
            IsolatedPointKind.HIGH,
            12.0,
        ),
        (
            make_candle(10, 5),
            make_candle(8, 3),
            make_candle(7, 3),
            IsolatedPointKind.LOW,
            3.0,
        ),
    ],
)
def test_deformation_tracker_confirms_right_inside_bar(
    left: Candle,
    middle: Candle,
    right: Candle,
    expected_kind: IsolatedPointKind,
    expected_price: float,
) -> None:
    deformations = load_deformations()
    tracker = deformations.DeformationAwareIsolatedPointTracker()
    tracker.add_candle(left)
    tracker.add_candle(middle)

    changes = tracker.add_candle(right)

    assert len(changes) == 1
    recognition = changes[0]
    assert isinstance(recognition, deformations.IsolatedPointRecognition)
    assert recognition.point.kind is expected_kind
    assert recognition.point.price == expected_price
    assert recognition.basis is deformations.IsolatedPointBasis.RIGHT_INSIDE_BAR


@pytest.mark.parametrize(
    ("existing", "new_point", "expected"),
    [
        (
            IsolatedPoint(1, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 10),
            IsolatedPoint(4, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 12),
            "new",
        ),
        (
            IsolatedPoint(1, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 10),
            IsolatedPoint(4, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 9),
            "existing",
        ),
        (
            IsolatedPoint(1, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 10),
            IsolatedPoint(4, IsolatedPointKind.HIGH, IsolatedPointStatus.CONFIRMED, 10),
            "existing",
        ),
        (
            IsolatedPoint(1, IsolatedPointKind.LOW, IsolatedPointStatus.CONFIRMED, 5),
            IsolatedPoint(4, IsolatedPointKind.LOW, IsolatedPointStatus.CONFIRMED, 3),
            "new",
        ),
        (
            IsolatedPoint(1, IsolatedPointKind.LOW, IsolatedPointStatus.CONFIRMED, 5),
            IsolatedPoint(4, IsolatedPointKind.LOW, IsolatedPointStatus.CONFIRMED, 6),
            "existing",
        ),
        (
            IsolatedPoint(1, IsolatedPointKind.LOW, IsolatedPointStatus.CONFIRMED, 5),
            IsolatedPoint(4, IsolatedPointKind.LOW, IsolatedPointStatus.CONFIRMED, 5),
            "existing",
        ),
    ],
)
def test_replace_with_more_extreme_point(
    existing: IsolatedPoint,
    new_point: IsolatedPoint,
    expected: str,
) -> None:
    deformations = load_deformations()

    result = deformations.replace_with_more_extreme_point(existing, new_point)

    assert result is (new_point if expected == "new" else existing)


def test_replacing_point_with_different_kind_is_rejected() -> None:
    deformations = load_deformations()
    high = IsolatedPoint(
        1,
        IsolatedPointKind.HIGH,
        IsolatedPointStatus.CONFIRMED,
        10,
    )
    low = IsolatedPoint(
        2,
        IsolatedPointKind.LOW,
        IsolatedPointStatus.CONFIRMED,
        5,
    )

    with pytest.raises(ValueError, match="kind"):
        deformations.replace_with_more_extreme_point(high, low)
