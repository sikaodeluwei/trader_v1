import pytest

from trading.definitions.candles import (
    Advantage,
    Candle,
    CandleGeometry,
    CandleSide,
    CandleType,
    classify_candle,
    get_advantage,
    get_geometry,
    get_side,
)


@pytest.mark.parametrize(
    ("candle", "expected_side"),
    [
        (Candle(open=100, high=110, low=90, close=108), CandleSide.BULLISH),
        (Candle(open=108, high=110, low=90, close=100), CandleSide.BEARISH),
        (Candle(open=100, high=110, low=90, close=100), CandleSide.DOJI),
    ],
)
def test_get_side_distinguishes_bullish_bearish_and_doji(
    candle: Candle, expected_side: CandleSide
) -> None:
    assert get_side(candle) is expected_side


def test_get_geometry_calculates_shape_ratios_from_ohlc() -> None:
    geometry = get_geometry(Candle(open=100, high=110, low=90, close=108))

    assert geometry.body_ratio == pytest.approx(0.40)
    assert geometry.upper_wick_ratio == pytest.approx(0.10)
    assert geometry.lower_wick_ratio == pytest.approx(0.50)
    assert geometry.open_position == pytest.approx(0.50)
    assert geometry.close_position == pytest.approx(0.90)


def test_get_geometry_uses_neutral_positions_for_zero_range() -> None:
    geometry = get_geometry(Candle(open=100, high=100, low=100, close=100))

    assert geometry == CandleGeometry(
        body_ratio=0.0,
        upper_wick_ratio=0.0,
        lower_wick_ratio=0.0,
        open_position=0.5,
        close_position=0.5,
    )


@pytest.mark.parametrize(
    ("candle_type", "expected_advantage"),
    [
        (CandleType.BULL_1, Advantage.BUYER),
        (CandleType.BULL_2, Advantage.BUYER),
        (CandleType.BULL_3, Advantage.BUYER),
        (CandleType.BULL_4, Advantage.SELLER),
        (CandleType.BULL_5, Advantage.BUYER),
        (CandleType.BULL_6, Advantage.NONE),
        (CandleType.BULL_7, Advantage.NONE),
        (CandleType.BULL_8, Advantage.NONE),
    ],
)
def test_get_advantage_maps_all_bullish_archetypes(
    candle_type: CandleType, expected_advantage: Advantage
) -> None:
    assert get_advantage(candle_type) is expected_advantage


@pytest.mark.parametrize(
    ("candle_type", "expected_advantage"),
    [
        (CandleType.BEAR_1, Advantage.SELLER),
        (CandleType.BEAR_2, Advantage.SELLER),
        (CandleType.BEAR_3, Advantage.SELLER),
        (CandleType.BEAR_4, Advantage.SELLER),
        (CandleType.BEAR_5, Advantage.BUYER),
        (CandleType.BEAR_6, Advantage.NONE),
        (CandleType.BEAR_7, Advantage.NONE),
        (CandleType.BEAR_8, Advantage.NONE),
    ],
)
def test_get_advantage_maps_all_bearish_archetypes(
    candle_type: CandleType, expected_advantage: Advantage
) -> None:
    assert get_advantage(candle_type) is expected_advantage


def test_classify_candle_is_explicitly_unimplemented() -> None:
    candle = Candle(open=100, high=110, low=90, close=108)

    with pytest.raises(NotImplementedError, match="fuzzy"):
        classify_candle(candle)
