import pytest

from trading.definitions.movements import MovementSide, PriceLeg, get_price_legs


def test_get_price_legs_returns_one_upward_leg() -> None:
    assert get_price_legs([100, 103, 108, 110]) == [
        PriceLeg(
            side=MovementSide.BUYER,
            start_price=100,
            end_price=110,
            distance=10,
        )
    ]


def test_get_price_legs_returns_one_downward_leg() -> None:
    assert get_price_legs([110, 106, 103, 100]) == [
        PriceLeg(
            side=MovementSide.SELLER,
            start_price=110,
            end_price=100,
            distance=10,
        )
    ]


def test_get_price_legs_separates_down_up_down_path() -> None:
    assert get_price_legs([100, 99, 102, 106, 110, 107, 103, 101]) == [
        PriceLeg(MovementSide.SELLER, 100, 99, 1),
        PriceLeg(MovementSide.BUYER, 99, 110, 11),
        PriceLeg(MovementSide.SELLER, 110, 101, 9),
    ]


def test_get_price_legs_separates_up_down_up_path() -> None:
    assert get_price_legs([100, 104, 102, 99, 101, 105]) == [
        PriceLeg(MovementSide.BUYER, 100, 104, 4),
        PriceLeg(MovementSide.SELLER, 104, 99, 5),
        PriceLeg(MovementSide.BUYER, 99, 105, 6),
    ]


def test_get_price_legs_merges_consecutive_same_direction_prices() -> None:
    legs = get_price_legs([1, 2, 4, 7])

    assert legs == [PriceLeg(MovementSide.BUYER, 1, 7, 6)]


def test_get_price_legs_ignores_unchanged_consecutive_prices() -> None:
    legs = get_price_legs([100, 100, 103, 103, 103, 101, 101])

    assert legs == [
        PriceLeg(MovementSide.BUYER, 100, 103, 3),
        PriceLeg(MovementSide.SELLER, 103, 101, 2),
    ]


@pytest.mark.parametrize("prices", [[], [100]])
def test_get_price_legs_returns_no_legs_for_fewer_than_two_prices(
    prices: list[float],
) -> None:
    assert get_price_legs(prices) == []
