from datetime import datetime, timedelta, timezone
from importlib import import_module
from importlib.util import find_spec
from types import ModuleType

import pytest

from trading.analysis.models import (
    ClosedCandleObservation,
    EvaluationReason,
    EvaluationStatus,
    OfflineMarketWindow,
    SegmentAnalysisRequest,
    StructuralLevel,
)
from trading.definitions.isolated_point_deformations import IsolatedPointBasis
from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.market_structure import MarketSegment


HIGH_LOW = [
    (96, 95), (100, 99), (91, 90), (110, 109), (96, 95),
    (105, 104), (81, 80), (120, 119), (120, 119.2),
    (97, 96), (107, 106), (86, 85), (115, 114),
    (98, 97), (100, 99), (71, 70), (80, 79),
]


def load_offline() -> ModuleType:
    return import_module("trading.analysis.offline")


def test_offline_module_is_discoverable_with_required_docstring() -> None:
    assert find_spec("trading.analysis.offline") is not None
    assert load_offline().__doc__


def test_offline_module_exports_locked_facade_names() -> None:
    offline = load_offline()
    assert hasattr(offline, "OfflineMarketAnalysis")
    assert hasattr(offline, "analyze_market_window")
    assert callable(offline.analyze_market_window)


def bridge_window() -> OfflineMarketWindow:
    start = datetime(2026, 9, 3, 9, 30, tzinfo=timezone.utc)
    candles = tuple(
        ClosedCandleObservation(
            timestamp=start + timedelta(minutes=index),
            open=(high + low) / 2,
            high=high,
            low=low,
            close=(high + low) / 2,
        )
        for index, (high, low) in enumerate(HIGH_LOW)
    )
    return OfflineMarketWindow("MNQ", "1m", 40, candles)


def fail_if_called(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("segment market semantics must not run for segment=None")


def test_facade_composes_only_objective_ohlc_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market_structure = import_module("trading.definitions.market_structure")
    pullback_structure = import_module("trading.definitions.pullback_structure")
    sms_structure = import_module("trading.definitions.sms_structure")
    monkeypatch.setattr(market_structure, "classify_market_state", fail_if_called)
    monkeypatch.setattr(pullback_structure, "evaluate_bms", fail_if_called)
    monkeypatch.setattr(sms_structure, "evaluate_sms", fail_if_called)

    window = bridge_window()
    result = load_offline().analyze_market_window(window)

    assert result.window is window
    assert [item.index for item in result.candles] == list(range(40, 57))
    assert all(item.observation.intrabar_prices is None for item in result.candles)
    assert all(
        item.intrabar_analysis.status is EvaluationStatus.UNAVAILABLE
        and item.intrabar_analysis.reason is EvaluationReason.INTRABAR_DATA_UNAVAILABLE
        and item.features.status is EvaluationStatus.UNAVAILABLE
        and item.features.reason is EvaluationReason.INTRABAR_DATA_UNAVAILABLE
        for item in result.candles
    )
    assert result.hierarchy.isolated.recognitions[6].point.index == 47
    assert result.hierarchy.isolated.recognitions[6].basis is IsolatedPointBasis.RIGHT_INSIDE_BAR
    assert [point.price for point in result.hierarchy.short_term.points] == [
        100, 90, 110, 95, 105, 80, 120, 96, 107, 85, 115, 97, 100, 70,
    ]
    assert [point.price for point in result.hierarchy.medium_term.vertices] == [
        110, 80, 120, 85, 115,
    ]
    long_high = result.hierarchy.long_term.points[0]
    medium_high_120 = result.hierarchy.medium_term.vertices[2]
    medium_high_115 = result.hierarchy.medium_term.vertices[4]
    assert long_high.kind is IsolatedPointKind.HIGH
    assert long_high.price == 120
    assert long_high.pivot is medium_high_120
    assert long_high.confirmed_by is medium_high_115
    assert long_high.pivot.pivot.recognition_basis is IsolatedPointBasis.RIGHT_INSIDE_BAR
    assert result.segment is None


def test_segment_request_is_resolved_after_objective_hierarchy() -> None:
    request = SegmentAnalysisRequest(
        MarketSegment(40, 47),
        StructuralLevel.SHORT,
    )

    result = load_offline().analyze_market_window(bridge_window(), segment=request)

    assert result.segment is not None
    assert result.segment.request is request
    assert result.segment.bms is None
    assert result.segment.sms is None
