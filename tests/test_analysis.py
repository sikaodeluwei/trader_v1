import pytest

from trading.definitions.analysis import CandleAnalysis, analyze_prices
from trading.definitions.candles import Candle, CandleSide
from trading.definitions.extremes import ExtremeOrder, ExtremePath
from trading.definitions.movements import MovementSide, PriceLeg


def test_analyze_prices_builds_complete_intrabar_analysis() -> None:
    analysis = analyze_prices([100, 99, 102, 106, 110, 107, 103, 101])

    assert isinstance(analysis, CandleAnalysis)
    assert analysis.candle == Candle(open=100, high=110, low=99, close=101)
    assert analysis.side is CandleSide.BULLISH
    assert analysis.geometry.body_ratio == pytest.approx(1 / 11)
    assert analysis.geometry.upper_wick_ratio == pytest.approx(9 / 11)
    assert analysis.geometry.lower_wick_ratio == pytest.approx(1 / 11)
    assert analysis.geometry.open_position == pytest.approx(1 / 11)
    assert analysis.geometry.close_position == pytest.approx(2 / 11)
    assert analysis.control.buyer_control == 2
    assert analysis.control.seller_control == 9
    assert analysis.control.buyer_control_ratio == pytest.approx(2 / 11)
    assert analysis.control.seller_control_ratio == pytest.approx(9 / 11)
    assert analysis.control.control_score == pytest.approx(-7 / 11)
    assert analysis.legs == [
        PriceLeg(MovementSide.SELLER, 100, 99, 1),
        PriceLeg(MovementSide.BUYER, 99, 110, 11),
        PriceLeg(MovementSide.SELLER, 110, 101, 9),
    ]
    assert analysis.extreme_path == ExtremePath(
        order=ExtremeOrder.LOW_THEN_HIGH,
        legs=[
            PriceLeg(MovementSide.SELLER, 100, 99, 1),
            PriceLeg(MovementSide.BUYER, 99, 110, 11),
            PriceLeg(MovementSide.SELLER, 110, 101, 9),
        ],
    )
    assert analysis.movements.largest_buyer_move == 11
    assert analysis.movements.largest_seller_move == 9
    assert analysis.movements.total_buyer_movement == 11
    assert analysis.movements.total_seller_movement == 10
    assert analysis.movements.final_side is MovementSide.SELLER
    assert analysis.movements.final_distance == 9
    assert analysis.movements.final_retracement_ratio == pytest.approx(9 / 11)


def test_analyze_prices_handles_one_direction_upward_path() -> None:
    analysis = analyze_prices([100, 103, 108, 110])

    assert analysis.candle == Candle(open=100, high=110, low=100, close=110)
    assert analysis.side is CandleSide.BULLISH
    assert analysis.legs == [PriceLeg(MovementSide.BUYER, 100, 110, 10)]
    assert analysis.movements.total_buyer_movement == 10
    assert analysis.movements.total_seller_movement == 0.0
    assert analysis.movements.final_retracement_ratio is None


def test_analyze_prices_handles_one_direction_downward_path() -> None:
    analysis = analyze_prices([110, 106, 103, 100])

    assert analysis.candle == Candle(open=110, high=110, low=100, close=100)
    assert analysis.side is CandleSide.BEARISH
    assert analysis.legs == [PriceLeg(MovementSide.SELLER, 110, 100, 10)]
    assert analysis.movements.total_buyer_movement == 0.0
    assert analysis.movements.total_seller_movement == 10
    assert analysis.movements.final_retracement_ratio is None


def test_analyze_prices_ignores_repeated_equal_prices_in_legs() -> None:
    analysis = analyze_prices([100, 100, 103, 103, 101, 101])

    assert analysis.candle == Candle(open=100, high=103, low=100, close=101)
    assert analysis.legs == [
        PriceLeg(MovementSide.BUYER, 100, 103, 3),
        PriceLeg(MovementSide.SELLER, 103, 101, 2),
    ]
    assert analysis.movements.final_retracement_ratio == pytest.approx(2 / 3)


def test_analyze_prices_marks_path_finishing_at_open_as_doji() -> None:
    analysis = analyze_prices([100, 95, 105, 100])

    assert analysis.candle == Candle(open=100, high=105, low=95, close=100)
    assert analysis.side is CandleSide.DOJI
    assert analysis.legs == [
        PriceLeg(MovementSide.SELLER, 100, 95, 5),
        PriceLeg(MovementSide.BUYER, 95, 105, 10),
        PriceLeg(MovementSide.SELLER, 105, 100, 5),
    ]


@pytest.mark.parametrize("prices", [[], [100]])
def test_analyze_prices_rejects_fewer_than_two_prices(
    prices: list[float],
) -> None:
    with pytest.raises(ValueError, match="at least two"):
        analyze_prices(prices)
