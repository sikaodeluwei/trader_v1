import pytest

from trading.definitions.analysis import analyze_prices
from trading.definitions.candles import Advantage, CandleSide, CandleType
from trading.definitions.extremes import ExtremeOrder
from trading.definitions.features import (
    CandleFeatures,
    LabeledCandleSample,
    create_labeled_sample,
    get_features,
)
from trading.definitions.movements import MovementSide


def test_features_capture_bullish_candle_with_seller_like_evidence() -> None:
    features = get_features(analyze_prices([91, 90, 110, 92]))

    assert features.side is CandleSide.BULLISH
    assert features.control_score == pytest.approx(-0.8)
    assert features.extreme_order is ExtremeOrder.LOW_THEN_HIGH
    assert features.initial_side is MovementSide.SELLER
    assert features.initial_ratio == pytest.approx(1 / 20)
    assert features.final_side is MovementSide.SELLER
    assert features.final_ratio == pytest.approx(18 / 20)
    assert features.displacement_ratio == pytest.approx(1 / 20)


def test_features_capture_bearish_candle_with_buyer_like_evidence() -> None:
    features = get_features(analyze_prices([109, 110, 90, 108]))

    assert features.side is CandleSide.BEARISH
    assert features.control_score == pytest.approx(0.8)
    assert features.extreme_order is ExtremeOrder.HIGH_THEN_LOW
    assert features.initial_side is MovementSide.BUYER
    assert features.initial_ratio == pytest.approx(1 / 20)
    assert features.final_side is MovementSide.BUYER
    assert features.final_ratio == pytest.approx(18 / 20)
    assert features.displacement_ratio == pytest.approx(-1 / 20)


def test_features_capture_strong_bullish_movement() -> None:
    features = get_features(analyze_prices([100, 105, 110]))

    assert features.side is CandleSide.BULLISH
    assert features.body_ratio == 1
    assert features.upper_wick_ratio == 0
    assert features.lower_wick_ratio == 0
    assert features.open_position == 0
    assert features.close_position == 1
    assert features.control_score == 1
    assert features.displacement_ratio == 1
    assert features.total_buyer_movement_ratio == 1
    assert features.total_seller_movement_ratio == 0


def test_features_capture_strong_bearish_movement() -> None:
    features = get_features(analyze_prices([110, 105, 100]))

    assert features.side is CandleSide.BEARISH
    assert features.body_ratio == 1
    assert features.upper_wick_ratio == 0
    assert features.lower_wick_ratio == 0
    assert features.open_position == 1
    assert features.close_position == 0
    assert features.control_score == -1
    assert features.displacement_ratio == -1
    assert features.total_buyer_movement_ratio == 0
    assert features.total_seller_movement_ratio == 1


def test_features_capture_balanced_doji_example() -> None:
    features = get_features(analyze_prices([100, 90, 110, 100]))

    assert features.side is CandleSide.DOJI
    assert features.body_ratio == 0
    assert features.upper_wick_ratio == pytest.approx(0.5)
    assert features.lower_wick_ratio == pytest.approx(0.5)
    assert features.open_position == pytest.approx(0.5)
    assert features.close_position == pytest.approx(0.5)
    assert features.control_score == 0
    assert features.displacement_ratio == 0
    assert features.total_buyer_movement_ratio == 1
    assert features.total_seller_movement_ratio == 1


def test_features_handle_zero_range_candle() -> None:
    features = get_features(analyze_prices([100, 100]))

    assert features.side is CandleSide.DOJI
    assert features.extreme_order is ExtremeOrder.FLAT
    assert features.initial_side is None
    assert features.initial_ratio == 0
    assert features.final_side is None
    assert features.final_ratio == 0
    assert features.displacement_ratio == 0
    assert features.total_buyer_movement_ratio == 0
    assert features.total_seller_movement_ratio == 0


def test_features_normalize_total_buyer_and_seller_movement() -> None:
    features = get_features(analyze_prices([100, 99, 110, 101]))

    assert features.total_buyer_movement_ratio == 1
    assert features.total_seller_movement_ratio == pytest.approx(10 / 11)


def test_create_labeled_sample_preserves_explicit_advantage() -> None:
    analysis = analyze_prices([91, 90, 110, 92])

    sample = create_labeled_sample(analysis, Advantage.SELLER)

    assert isinstance(sample, LabeledCandleSample)
    assert isinstance(sample.features, CandleFeatures)
    assert sample.features == get_features(analysis)
    assert sample.advantage is Advantage.SELLER
    assert sample.candle_type is None


def test_create_labeled_sample_preserves_optional_candle_type() -> None:
    analysis = analyze_prices([91, 90, 110, 92])

    sample = create_labeled_sample(
        analysis,
        Advantage.SELLER,
        candle_type=CandleType.BULL_4,
    )

    assert sample.advantage is Advantage.SELLER
    assert sample.candle_type is CandleType.BULL_4
