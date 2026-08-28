import pytest

from trading.definitions.candles import (
    Advantage,
    Candle,
    CandleGeometry,
    CandleSide,
    CandleType,
    CandleTypeInterpretation,
    TrendStatus,
    classify_candle,
    get_advantage,
    get_geometry,
    get_side,
    get_trend_status,
    interpret_candle_type,
    is_trend_candle,
)


COURSE_INTERPRETATIONS = [
    (CandleType.BULL_1, Advantage.BUYER, "trend"),
    (CandleType.BULL_2, Advantage.BUYER, "trend"),
    (CandleType.BULL_3, Advantage.BUYER, "trend"),
    (CandleType.BULL_4, Advantage.SELLER, "trend"),
    (CandleType.BULL_5, Advantage.BUYER, "trend"),
    (CandleType.BULL_6, Advantage.NONE, "non_trend"),
    (CandleType.BULL_7, Advantage.NONE, "non_trend"),
    (CandleType.BULL_8, Advantage.NONE, "non_trend"),
    (CandleType.BEAR_1, Advantage.SELLER, "trend"),
    (CandleType.BEAR_2, Advantage.SELLER, "trend"),
    (CandleType.BEAR_3, Advantage.SELLER, "trend"),
    (CandleType.BEAR_4, Advantage.SELLER, "trend"),
    (CandleType.BEAR_5, Advantage.BUYER, "trend"),
    (CandleType.BEAR_6, Advantage.NONE, "non_trend"),
    (CandleType.BEAR_7, Advantage.NONE, "non_trend"),
    (CandleType.BEAR_8, Advantage.NONE, "non_trend"),
]


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
    ("candle_type", "expected_advantage", "expected_trend_value"),
    COURSE_INTERPRETATIONS,
)
def test_interpretation_matches_course_mapping_for_every_candle_type(
    candle_type: CandleType,
    expected_advantage: Advantage,
    expected_trend_value: str,
) -> None:
    expected_trend_status = TrendStatus(expected_trend_value)

    assert get_advantage(candle_type) is expected_advantage
    assert get_trend_status(candle_type) is expected_trend_status
    assert interpret_candle_type(candle_type) == (
        CandleTypeInterpretation(
            candle_type=candle_type,
            advantage=expected_advantage,
            trend_status=expected_trend_status,
        )
    )
    assert is_trend_candle(candle_type) is (
        expected_trend_status is TrendStatus.TREND
    )


def test_course_interpretation_reference_covers_all_candle_types() -> None:
    referenced_types = [candle_type for candle_type, _, _ in COURSE_INTERPRETATIONS]

    assert len(referenced_types) == len(CandleType)
    assert set(referenced_types) == set(CandleType)


def test_classify_candle_is_explicitly_unimplemented() -> None:
    candle = Candle(open=100, high=110, low=90, close=108)

    with pytest.raises(NotImplementedError, match="fuzzy"):
        classify_candle(candle)
