from datetime import datetime, timezone
import importlib.util
from importlib import import_module

import pytest

from trading.analysis.models import (
    ClosedCandleObservation,
    EvaluationReason,
    EvaluationStatus,
)
from trading.definitions.analysis import analyze_prices
from trading.definitions.candles import (
    Candle,
    CandleSide,
    get_control,
    get_geometry,
    get_side,
)
from trading.definitions.features import get_features
from trading.definitions.movements import MovementSide, PriceLeg


TIMESTAMP = datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc)
CANONICAL_PATH = (100.0, 99.0, 102.0, 106.0, 110.0, 107.0, 103.0, 101.0)


def test_adapter_module_is_discoverable() -> None:
    assert importlib.util.find_spec("trading.analysis.candles") is not None


def test_adapter_exposes_locked_public_names() -> None:
    module = import_module("trading.analysis.candles")
    assert all(
        hasattr(module, name)
        for name in ("OfflineCandleResult", "analyze_closed_candle")
    )


def observation(**overrides: object) -> ClosedCandleObservation:
    values: dict[str, object] = {
        "timestamp": TIMESTAMP,
        "open": 100.0,
        "high": 110.0,
        "low": 99.0,
        "close": 101.0,
        "intrabar_prices": CANONICAL_PATH,
    }
    values.update(overrides)
    return ClosedCandleObservation(**values)


def run_adapter(item: ClosedCandleObservation, index: int):
    from trading.analysis.candles import analyze_closed_candle

    try:
        return analyze_closed_candle(item, index=index)
    except NotImplementedError as error:
        pytest.fail(f"adapter behavior absent: {error}")


def test_analyze_closed_candle_reuses_authoritative_intrabar_outputs() -> None:
    result = run_adapter(observation(), index=40)
    direct = analyze_prices(CANONICAL_PATH)

    assert result.index == 40
    assert result.timestamp == TIMESTAMP
    assert result.observation == observation()
    assert result.candle == Candle(100.0, 110.0, 99.0, 101.0)
    assert result.side is CandleSide.BULLISH
    assert result.geometry == get_geometry(direct.candle)
    assert result.control == get_control(direct.candle)
    assert result.geometry.body_ratio == pytest.approx(1 / 11)
    assert result.geometry.upper_wick_ratio == pytest.approx(9 / 11)
    assert result.geometry.lower_wick_ratio == pytest.approx(1 / 11)
    assert result.geometry.open_position == pytest.approx(1 / 11)
    assert result.geometry.close_position == pytest.approx(2 / 11)
    assert result.control.control_score == pytest.approx(-7 / 11)
    assert result.intrabar_analysis.status is EvaluationStatus.AVAILABLE
    assert result.intrabar_analysis.value == direct
    assert result.features.status is EvaluationStatus.AVAILABLE
    assert result.features.value == get_features(direct)
    assert result.candle_type.status is EvaluationStatus.UNAVAILABLE
    assert result.candle_type.reason is EvaluationReason.CANDLE_TYPE_UNCALIBRATED

    assert direct.legs == [
        PriceLeg(MovementSide.SELLER, 100.0, 99.0, 1.0),
        PriceLeg(MovementSide.BUYER, 99.0, 110.0, 11.0),
        PriceLeg(MovementSide.SELLER, 110.0, 101.0, 9.0),
    ]
    assert direct.extreme_evidence.order.value == "low_then_high"
    assert direct.extreme_evidence.final_ratio == pytest.approx(9 / 11)
    assert direct.movements.final_retracement_ratio == pytest.approx(9 / 11)


def test_ohlc_only_keeps_candle_measurements_but_marks_intrabar_unavailable() -> None:
    item = observation(intrabar_prices=None)
    result = run_adapter(item, index=40)

    assert result.side is get_side(result.candle)
    assert result.geometry == get_geometry(result.candle)
    assert result.control == get_control(result.candle)
    assert result.intrabar_analysis.status is EvaluationStatus.UNAVAILABLE
    assert result.intrabar_analysis.reason is EvaluationReason.INTRABAR_DATA_UNAVAILABLE
    assert result.features.status is EvaluationStatus.UNAVAILABLE
    assert result.features.reason is EvaluationReason.INTRABAR_DATA_UNAVAILABLE
    assert result.candle_type.status is EvaluationStatus.UNAVAILABLE
    assert result.candle_type.reason is EvaluationReason.CANDLE_TYPE_UNCALIBRATED


@pytest.mark.parametrize(
    ("open", "high", "low", "close", "side"),
    [
        (110.0, 110.0, 99.0, 100.0, CandleSide.BEARISH),
        (100.0, 110.0, 99.0, 100.0, CandleSide.DOJI),
        (100.0, 100.0, 100.0, 100.0, CandleSide.DOJI),
    ],
)
def test_ohlc_only_supports_bearish_doji_and_zero_range(
    open: float, high: float, low: float, close: float, side: CandleSide
) -> None:
    result = run_adapter(
        observation(
            open=open,
            high=high,
            low=low,
            close=close,
            intrabar_prices=(),
        ),
        index=40,
    )

    assert result.side is side
    assert result.intrabar_analysis.status is EvaluationStatus.UNAVAILABLE
    assert result.features.status is EvaluationStatus.UNAVAILABLE
    assert result.candle_type.reason is EvaluationReason.CANDLE_TYPE_UNCALIBRATED


def test_adapter_never_calls_uncalibrated_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    import trading.definitions.candles as candle_definitions

    def fail_classifier(_candle: Candle) -> object:
        raise AssertionError("classify_candle must not be called")

    monkeypatch.setattr(candle_definitions, "classify_candle", fail_classifier)

    result = run_adapter(observation(), index=40)

    assert result.candle_type.reason is EvaluationReason.CANDLE_TYPE_UNCALIBRATED
