"""Behavioral tests for immutable offline market-window models."""

import importlib.util
from datetime import datetime, timedelta, timezone
from dataclasses import FrozenInstanceError
from importlib import import_module

import pytest

from trading.analysis.models import (
    BMSAnalysisRequest,
    ClosedCandleObservation,
    Evaluation,
    EvaluationReason,
    EvaluationStatus,
    OfflineMarketWindow,
    SMSAnalysisRequest,
    SegmentAnalysisRequest,
    SegmentAnalysisResult,
    ResolvedStructurePoint,
    StructuralLevel,
)
from trading.definitions.market_structure import MarketSegment, MarketState, StructurePoint, StructurePointKind
from trading.definitions.pullback_structure import BMSResult, PullbackStructureStatus
from trading.definitions.short_term_structure import ShortTermPoint
from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.sms_structure import SMSResult, SMSStructureStatus


def test_analysis_package_is_discoverable() -> None:
    """The new offline analysis package must exist before its API is tested."""

    assert importlib.util.find_spec("trading.analysis") is not None


def test_models_module_is_discoverable() -> None:
    """The model module must exist before its locked API is imported."""

    assert importlib.util.find_spec("trading.analysis.models") is not None


def test_models_expose_locked_public_names() -> None:
    """Future analysis tasks need the approved model names to be importable."""

    module = import_module("trading.analysis.models")
    names = (
        "EvaluationStatus",
        "EvaluationReason",
        "Evaluation",
        "ClosedCandleObservation",
        "OfflineMarketWindow",
        "StructuralLevel",
        "BMSAnalysisRequest",
        "SMSAnalysisRequest",
        "SegmentAnalysisRequest",
        "ResolvedStructurePoint",
        "SegmentAnalysisResult",
    )
    missing = [name for name in names if not hasattr(module, name)]
    assert missing == []


def test_evaluation_enums_have_the_locked_serialized_values() -> None:
    """Changing any public status/reason value breaks persisted contracts."""

    def serialized_value(owner: object, name: str) -> object:
        return getattr(getattr(owner, name, None), "value", None)

    assert serialized_value(EvaluationStatus, "AVAILABLE") == "available"
    assert serialized_value(EvaluationStatus, "UNAVAILABLE") == "unavailable"
    assert serialized_value(EvaluationStatus, "INVALID") == "invalid"
    assert serialized_value(EvaluationReason, "INSUFFICIENT_STRUCTURE") == "insufficient_structure"
    assert serialized_value(EvaluationReason, "INTRABAR_DATA_UNAVAILABLE") == "intrabar_data_unavailable"
    assert serialized_value(EvaluationReason, "CANDLE_TYPE_UNCALIBRATED") == "candle_type_uncalibrated"
    assert serialized_value(EvaluationReason, "BOUNDARY_NOT_CANONICAL_VERTEX") == "boundary_not_canonical_vertex"
    assert serialized_value(EvaluationReason, "INVALID_CONTEXT") == "invalid_context"
    assert serialized_value(EvaluationReason, "PARENT_STATE_NOT_DIRECTIONAL") == "parent_state_not_directional"
    assert serialized_value(EvaluationReason, "OHLC_INTRABAR_ORDER_AMBIGUOUS") == "ohlc_intrabar_order_ambiguous"
    assert serialized_value(StructuralLevel, "SHORT") == "short"
    assert serialized_value(StructuralLevel, "MEDIUM") == "medium"
    assert serialized_value(StructuralLevel, "LONG") == "long"


def observation(index: int, **overrides: object) -> ClosedCandleObservation:
    """Create one hand-checked closed candle in a UTC chronological series."""

    values = dict(
        timestamp=datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc)
        + timedelta(seconds=index),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        intrabar_prices=None,
    )
    values.update(overrides)
    return ClosedCandleObservation(**values)


def test_evaluation_requires_a_value_only_for_available_status() -> None:
    """A capability result must not blur unavailable and evaluated outcomes."""

    available = Evaluation(EvaluationStatus.AVAILABLE, value=MarketState.UPTREND)
    unavailable = Evaluation(
        EvaluationStatus.UNAVAILABLE,
        reason=EvaluationReason.INSUFFICIENT_STRUCTURE,
        message="two highs are required",
    )
    invalid = Evaluation(
        EvaluationStatus.INVALID,
        reason=EvaluationReason.INVALID_CONTEXT,
    )

    assert available.value is MarketState.UPTREND
    assert available.reason is None
    assert unavailable.value is None
    assert unavailable.message == "two highs are required"
    assert invalid.value is None


@pytest.mark.parametrize(
    ("status", "value", "reason"),
    [
        (EvaluationStatus.AVAILABLE, None, None),
        (EvaluationStatus.AVAILABLE, MarketState.UPTREND, EvaluationReason.INVALID_CONTEXT),
        (EvaluationStatus.UNAVAILABLE, None, None),
        (EvaluationStatus.UNAVAILABLE, MarketState.NON_TREND, EvaluationReason.INSUFFICIENT_STRUCTURE),
        (EvaluationStatus.INVALID, None, None),
        (EvaluationStatus.INVALID, MarketState.NON_TREND, EvaluationReason.INVALID_CONTEXT),
    ],
)
def test_evaluation_rejects_invalid_status_value_reason_combinations(
    status: EvaluationStatus,
    value: MarketState | None,
    reason: EvaluationReason | None,
) -> None:
    """Missing or conflicting evaluation metadata must be rejected at creation."""

    with pytest.raises(ValueError):
        Evaluation(status, value=value, reason=reason)


def test_window_preserves_dense_input_metadata_without_sorting() -> None:
    """The caller's supplied chronology defines dense offline indexes."""

    first = observation(0)
    second = observation(1)
    window = OfflineMarketWindow("MNQ", "1m", 40, (first, second))

    assert window.candles == (first, second)
    assert [window.start_index + i for i in range(len(window.candles))] == [40, 41]


@pytest.mark.parametrize("count", [0, 251])
def test_window_rejects_outside_approved_size(count: int) -> None:
    """The validation window must reject, never trim, out-of-range input."""

    candles = tuple(observation(i) for i in range(count))

    with pytest.raises(ValueError, match="1 through 250"):
        OfflineMarketWindow("MNQ", "1m", 0, candles)


def test_window_accepts_exactly_250_candles_without_truncation() -> None:
    """The approved upper boundary remains fully available to downstream work."""

    candles = tuple(observation(i) for i in range(250))
    window = OfflineMarketWindow("MNQ", "1m", 7, candles)

    assert len(window.candles) == 250
    assert window.candles[-1] == candles[-1]
    assert window.start_index + len(window.candles) - 1 == 256


@pytest.mark.parametrize("field", ["instrument", "timeframe"])
def test_window_rejects_empty_required_metadata(field: str) -> None:
    """Opaque metadata still needs a caller-supplied non-empty identity."""

    values: dict[str, object] = {
        "instrument": "MNQ",
        "timeframe": "1m",
        "start_index": 0,
        "candles": (observation(0),),
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        OfflineMarketWindow(**values)


@pytest.mark.parametrize(
    "timestamp_pair",
    [
        (datetime(2026, 8, 28, 9, 30), None),
        (datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc), datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc)),
        (datetime(2026, 8, 28, 9, 31, tzinfo=timezone.utc), datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc)),
    ],
)
def test_window_rejects_naive_duplicate_or_decreasing_timestamps(
    timestamp_pair: tuple[datetime, datetime | None],
) -> None:
    """Closed observations must be timezone-aware and strictly chronological."""

    first_timestamp, second_timestamp = timestamp_pair
    if first_timestamp.tzinfo is None:
        with pytest.raises(ValueError, match="timezone-aware"):
            observation(0, timestamp=first_timestamp)
        return
    first = observation(0, timestamp=first_timestamp)
    candles = (first,) if second_timestamp is None else (first, observation(1, timestamp=second_timestamp))

    with pytest.raises(ValueError, match="timezone-aware|strictly increasing"):
        OfflineMarketWindow("MNQ", "1m", 0, candles)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_observation_rejects_non_finite_ohlc_values(field: str, value: float) -> None:
    """NaN and infinities must not enter an immutable historical snapshot."""

    with pytest.raises(ValueError, match="finite"):
        observation(0, **{field: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"low": 100.5},
        {"open": 102.5},
        {"close": 102.5},
        {"high": 100.5},
    ],
)
def test_observation_rejects_invalid_ohlc_geometry(overrides: dict[str, float]) -> None:
    """Each violated low/open-close/high ordering is invalid historical OHLC."""

    with pytest.raises(ValueError, match=r"low <= min\(open, close\) <= max\(open, close\) <= high"):
        observation(0, **overrides)


@pytest.mark.parametrize("prices", [None, (), (100.0,)])
def test_observation_accepts_intrabar_insufficient_inputs(
    prices: tuple[float, ...] | None,
) -> None:
    """Absent or one-price paths remain valid OHLC without fabricated evidence."""

    item = observation(0, intrabar_prices=prices)

    assert item.intrabar_prices == prices


def test_observation_accepts_exact_intrabar_ohlc_agreement() -> None:
    """A complete ordered path must agree exactly with its supplied OHLC."""

    item = observation(0, intrabar_prices=(100.0, 99.0, 102.0, 101.0))

    assert (item.open, item.high, item.low, item.close) == (100.0, 102.0, 99.0, 101.0)


@pytest.mark.parametrize(
    "prices",
    [
        (100.0, 99.0, 102.0, 100.0),
        (100.0, 99.0, 101.0),
    ],
)
def test_observation_rejects_intrabar_paths_that_do_not_derive_ohlc(
    prices: tuple[float, ...],
) -> None:
    """Path data may not be silently reconciled with a contradictory OHLC bar."""

    with pytest.raises(ValueError, match="derive the supplied OHLC exactly"):
        observation(0, intrabar_prices=prices)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_observation_rejects_non_finite_intrabar_prices(value: float) -> None:
    """An attached ordered path requires finite values even when insufficient."""

    with pytest.raises(ValueError, match="finite"):
        observation(0, intrabar_prices=(value,))


def test_public_records_are_frozen_and_preserve_source_values() -> None:
    """Callers cannot mutate validated data or later provenance-bearing results."""

    item = observation(0)
    window = OfflineMarketWindow("MNQ", "1m", 0, (item,))
    request = SegmentAnalysisRequest(MarketSegment(0, 0), StructuralLevel.SHORT)
    source = ShortTermPoint(0, IsolatedPointKind.HIGH, 102.0)
    point = StructurePoint(0, StructurePointKind.HIGH, 102.0)
    resolved = ResolvedStructurePoint(StructuralLevel.SHORT, source, point)
    bms = BMSResult(PullbackStructureStatus.PULLBACK_ONLY)
    sms = SMSResult(SMSStructureStatus.PENDING)
    result = SegmentAnalysisResult(
        request,
        (resolved,),
        Evaluation(EvaluationStatus.AVAILABLE, value=MarketState.UPTREND),
        Evaluation(EvaluationStatus.AVAILABLE, value=bms),
        Evaluation(EvaluationStatus.AVAILABLE, value=sms),
    )

    with pytest.raises(FrozenInstanceError):
        item.close = 0.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        window.instrument = "ES"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        request.level = StructuralLevel.LONG  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        resolved.point = point  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.bms = None  # type: ignore[misc]

    assert result.selected_points == (resolved,)


def test_sequence_inputs_are_snapshotted_as_immutable_tuples() -> None:
    """Frozen records must not retain caller-owned mutable sequence state."""

    intrabar_prices = [100.0, 99.0, 102.0, 101.0]
    item = observation(0, intrabar_prices=intrabar_prices)
    intrabar_prices.append(100.5)

    candles = [item]
    window = OfflineMarketWindow("MNQ", "1m", 0, candles)
    candles.clear()

    result = SegmentAnalysisResult(
        SegmentAnalysisRequest(MarketSegment(0, 0), StructuralLevel.SHORT),
        [],
        Evaluation(EvaluationStatus.AVAILABLE, value=MarketState.NON_TREND),
        None,
        None,
    )

    assert item.intrabar_prices == (100.0, 99.0, 102.0, 101.0)
    assert window.candles == (item,)
    assert result.selected_points == ()
    assert isinstance(item.intrabar_prices, tuple)
    assert isinstance(window.candles, tuple)
    assert isinstance(result.selected_points, tuple)
