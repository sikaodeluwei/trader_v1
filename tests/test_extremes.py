from trading.definitions.extremes import ExtremeOrder, ExtremePath, get_extreme_path
from trading.definitions.movements import MovementSide, PriceLeg


def test_get_extreme_path_when_low_occurs_before_high() -> None:
    assert get_extreme_path([100, 99, 102, 106, 110, 107, 101]) == ExtremePath(
        order=ExtremeOrder.LOW_THEN_HIGH,
        legs=[
            PriceLeg(MovementSide.SELLER, 100, 99, 1),
            PriceLeg(MovementSide.BUYER, 99, 110, 11),
            PriceLeg(MovementSide.SELLER, 110, 101, 9),
        ],
    )


def test_get_extreme_path_when_high_occurs_before_low() -> None:
    assert get_extreme_path([100, 105, 110, 106, 95, 98]) == ExtremePath(
        order=ExtremeOrder.HIGH_THEN_LOW,
        legs=[
            PriceLeg(MovementSide.BUYER, 100, 110, 10),
            PriceLeg(MovementSide.SELLER, 110, 95, 15),
            PriceLeg(MovementSide.BUYER, 95, 98, 3),
        ],
    )


def test_get_extreme_path_omits_zero_leg_when_open_equals_low() -> None:
    assert get_extreme_path([100, 103, 110, 105]) == ExtremePath(
        order=ExtremeOrder.LOW_THEN_HIGH,
        legs=[
            PriceLeg(MovementSide.BUYER, 100, 110, 10),
            PriceLeg(MovementSide.SELLER, 110, 105, 5),
        ],
    )


def test_get_extreme_path_omits_zero_leg_when_open_equals_high() -> None:
    assert get_extreme_path([110, 105, 95, 98]) == ExtremePath(
        order=ExtremeOrder.HIGH_THEN_LOW,
        legs=[
            PriceLeg(MovementSide.SELLER, 110, 95, 15),
            PriceLeg(MovementSide.BUYER, 95, 98, 3),
        ],
    )


def test_get_extreme_path_omits_zero_leg_when_close_equals_high() -> None:
    assert get_extreme_path([100, 95, 105, 110]) == ExtremePath(
        order=ExtremeOrder.LOW_THEN_HIGH,
        legs=[
            PriceLeg(MovementSide.SELLER, 100, 95, 5),
            PriceLeg(MovementSide.BUYER, 95, 110, 15),
        ],
    )


def test_get_extreme_path_omits_zero_leg_when_close_equals_low() -> None:
    assert get_extreme_path([100, 105, 110, 95]) == ExtremePath(
        order=ExtremeOrder.HIGH_THEN_LOW,
        legs=[
            PriceLeg(MovementSide.BUYER, 100, 110, 10),
            PriceLeg(MovementSide.SELLER, 110, 95, 15),
        ],
    )


def test_get_extreme_path_returns_flat_without_legs() -> None:
    assert get_extreme_path([100, 100, 100]) == ExtremePath(
        order=ExtremeOrder.FLAT,
        legs=[],
    )
