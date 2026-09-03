"""Behavioral tests for selected-level offline market-segment analysis."""

from datetime import datetime, timedelta, timezone
from importlib import import_module
from importlib.util import find_spec

import pytest

from trading.analysis.hierarchy import StructuralHierarchy
from trading.analysis.isolated import IsolatedPointScan
from trading.analysis.models import (
    BMSAnalysisRequest,
    ClosedCandleObservation,
    EvaluationReason,
    EvaluationStatus,
    OfflineMarketWindow,
    SegmentAnalysisRequest,
    SMSAnalysisRequest,
    StructuralLevel,
)
from trading.definitions.isolated_point_deformations import IsolatedPointBasis
from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.long_term_structure import (
    LongTermPoint,
    LongTermStructure,
)
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePointKind,
)
from trading.definitions.medium_term_structure import (
    MediumTermPoint,
    MediumTermStructure,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    SuppressedShortTermPoint,
    ShortTermSuppressionReason,
)


def load_segments() -> object:
    assert find_spec("trading.analysis.segments") is not None
    return import_module("trading.analysis.segments")


def load_segments_api() -> object:
    segments = load_segments()
    assert callable(getattr(segments, "select_canonical_vertices", None))
    assert callable(getattr(segments, "evaluate_selected_segment", None))
    return segments


def test_segments_module_is_discoverable_with_required_docstring() -> None:
    assert find_spec("trading.analysis.segments") is not None
    segments = load_segments()
    assert segments.__doc__


def test_segments_module_exports_locked_public_names() -> None:
    segments = load_segments()
    names = ("select_canonical_vertices", "evaluate_selected_segment")
    missing = [name for name in names if not hasattr(segments, name)]
    assert missing == []
    assert all(callable(getattr(segments, name, None)) for name in names)


def short_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> ShortTermPoint:
    return ShortTermPoint(index, kind, price, IsolatedPointBasis.STRICT)


def medium_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> MediumTermPoint:
    pivot = short_point(index, kind, price)
    confirmed_by = short_point(index + 1, kind, price)
    return MediumTermPoint(pivot, confirmed_by)


def long_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> LongTermPoint:
    pivot = medium_point(index, kind, price)
    confirmed_by = medium_point(index + 2, kind, price)
    return LongTermPoint(pivot, confirmed_by)


def hierarchy(
    *,
    short: tuple[ShortTermPoint, ...] = (),
    medium: tuple[MediumTermPoint, ...] = (),
    long: tuple[LongTermPoint, ...] = (),
) -> StructuralHierarchy:
    return StructuralHierarchy(
        IsolatedPointScan((), None),
        ShortTermStructure(short, short, ()),
        MediumTermStructure(medium, (), medium, ()),
        LongTermStructure(long, (), long, ()),
    )


def window(start_index: int = 0, count: int = 20) -> OfflineMarketWindow:
    timestamp = datetime(2026, 9, 3, 9, 30, tzinfo=timezone.utc)
    candles = tuple(
        ClosedCandleObservation(
            timestamp=timestamp + timedelta(minutes=index),
            open=99.0,
            high=100.0,
            low=98.0,
            close=99.5,
        )
        for index in range(count)
    )
    return OfflineMarketWindow("MNQ", "1m", start_index, candles)


def request(
    start: int,
    end: int,
    level: StructuralLevel = StructuralLevel.SHORT,
) -> SegmentAnalysisRequest:
    return SegmentAnalysisRequest(MarketSegment(start, end), level)


def test_short_level_selects_only_canonical_vertices_in_caller_order() -> None:
    vertices = (
        short_point(4, IsolatedPointKind.HIGH, 120.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(3, IsolatedPointKind.HIGH, 110.0),
    )
    suppressed = SuppressedShortTermPoint(
        short_point(2, IsolatedPointKind.HIGH, 115.0),
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    source = ShortTermStructure(
        points=vertices + (suppressed.point,),
        vertices=vertices,
        suppressed=(suppressed,),
    )
    result = load_segments_api().select_canonical_vertices(
        StructuralHierarchy(
            IsolatedPointScan((), None),
            source,
            MediumTermStructure((), (), (), ()),
            LongTermStructure((), (), (), ()),
        ),
        StructuralLevel.SHORT,
    )

    assert [item.source_vertex for item in result] == list(vertices)
    assert [item.point.index for item in result] == [4, 1, 3]
    assert all(item.source_vertex is source_vertex for item, source_vertex in zip(result, vertices))
    assert all(
        item.point.kind in {StructurePointKind.HIGH, StructurePointKind.LOW}
        for item in result
    )
    assert suppressed.point not in [item.source_vertex for item in result]


@pytest.mark.parametrize("level", [StructuralLevel.SHORT, StructuralLevel.MEDIUM, StructuralLevel.LONG])
def test_selected_level_maps_exactly_to_vertices_and_pivot_indexes(
    level: StructuralLevel,
) -> None:
    short = (short_point(1, IsolatedPointKind.HIGH, 100.0),)
    medium = (medium_point(7, IsolatedPointKind.LOW, 90.0),)
    long = (long_point(12, IsolatedPointKind.HIGH, 110.0),)
    source = StructuralHierarchy(
        IsolatedPointScan((), None),
        ShortTermStructure(short, short, ()),
        MediumTermStructure(medium, (), medium, ()),
        LongTermStructure(long, (), long, ()),
    )

    result = load_segments_api().select_canonical_vertices(source, level)
    expected = {StructuralLevel.SHORT: short, StructuralLevel.MEDIUM: medium, StructuralLevel.LONG: long}[level]

    assert tuple(item.source_vertex for item in result) == expected
    assert all(item.level is level for item in result)
    assert [item.point.index for item in result] == [
        item.index if level is StructuralLevel.SHORT else item.pivot_index
        for item in expected
    ]
    assert [item.point.price for item in result] == [item.price for item in expected]
    assert all(item.source_vertex is source_vertex for item, source_vertex in zip(result, expected))


def resolved_state(
    points: tuple[tuple[IsolatedPointKind, float], ...],
) -> object:
    short = tuple(short_point(index, kind, price) for index, (kind, price) in enumerate(points))
    source = hierarchy(short=short)
    return load_segments_api().evaluate_selected_segment(
        window(count=len(points)),
        source,
        request(0, len(points) - 1),
    )


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        (
            (
                (IsolatedPointKind.HIGH, 100.0),
                (IsolatedPointKind.LOW, 90.0),
                (IsolatedPointKind.HIGH, 110.0),
                (IsolatedPointKind.LOW, 95.0),
                (IsolatedPointKind.HIGH, 120.0),
            ),
            MarketState.UPTREND,
        ),
        (
            (
                (IsolatedPointKind.HIGH, 120.0),
                (IsolatedPointKind.LOW, 100.0),
                (IsolatedPointKind.HIGH, 110.0),
                (IsolatedPointKind.LOW, 90.0),
            ),
            MarketState.DOWNTREND,
        ),
        (
            (
                (IsolatedPointKind.HIGH, 110.0),
                (IsolatedPointKind.LOW, 90.0),
                (IsolatedPointKind.HIGH, 105.0),
                (IsolatedPointKind.LOW, 95.0),
            ),
            MarketState.NON_TREND,
        ),
    ],
)
def test_market_state_uses_selected_canonical_points(
    points: tuple[tuple[IsolatedPointKind, float], ...],
    expected: MarketState,
) -> None:
    result = resolved_state(points)
    assert result.market_state.status is EvaluationStatus.AVAILABLE
    assert result.market_state.value is expected


def test_insufficient_structure_is_unavailable_without_calling_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market_structure = import_module("trading.definitions.market_structure")

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("classifier must not run for insufficient structure")

    monkeypatch.setattr(market_structure, "classify_market_state", fail_if_called)
    result = resolved_state(
        (
            (IsolatedPointKind.HIGH, 100.0),
            (IsolatedPointKind.LOW, 90.0),
            (IsolatedPointKind.HIGH, 110.0),
        )
    )

    assert result.market_state.status is EvaluationStatus.UNAVAILABLE
    assert result.market_state.reason is EvaluationReason.INSUFFICIENT_STRUCTURE


@pytest.mark.parametrize("segment", [MarketSegment(-1, 4), MarketSegment(0, 5)])
def test_segment_outside_window_raises_without_clamping(segment: MarketSegment) -> None:
    with pytest.raises(ValueError, match="outside window"):
        load_segments_api().evaluate_selected_segment(
            window(start_index=0, count=5),
            hierarchy(short=(short_point(0, IsolatedPointKind.HIGH, 100.0),)),
            SegmentAnalysisRequest(segment, StructuralLevel.SHORT),
        )


@pytest.mark.parametrize(
    "deferred_request",
    [
        SegmentAnalysisRequest(
            MarketSegment(-1, 3),
            StructuralLevel.SHORT,
            bms=BMSAnalysisRequest(0, 1, 2),
        ),
        SegmentAnalysisRequest(
            MarketSegment(0, 4),
            StructuralLevel.SHORT,
            sms=SMSAnalysisRequest(2, 1),
        ),
    ],
)
def test_outside_segment_validation_precedes_deferred_boundaries(
    deferred_request: SegmentAnalysisRequest,
) -> None:
    with pytest.raises(ValueError, match="outside window"):
        load_segments_api().evaluate_selected_segment(
            window(start_index=0, count=4),
            hierarchy(short=(short_point(0, IsolatedPointKind.HIGH, 100.0),)),
            deferred_request,
        )


def test_segment_without_bms_or_sms_returns_none_optional_results() -> None:
    result = resolved_state(
        (
            (IsolatedPointKind.HIGH, 100.0),
            (IsolatedPointKind.LOW, 90.0),
            (IsolatedPointKind.HIGH, 110.0),
            (IsolatedPointKind.LOW, 95.0),
        )
    )
    assert result.bms is None
    assert result.sms is None


def test_bms_and_sms_requests_remain_explicit_task_boundaries() -> None:
    from trading.analysis.models import BMSAnalysisRequest, SMSAnalysisRequest

    short = tuple(
        short_point(index, kind, price)
        for index, (kind, price) in enumerate(
            (
                (IsolatedPointKind.HIGH, 100.0),
                (IsolatedPointKind.LOW, 90.0),
                (IsolatedPointKind.HIGH, 110.0),
                (IsolatedPointKind.LOW, 95.0),
            )
        )
    )
    source = hierarchy(short=short)
    with pytest.raises(NotImplementedError):
        load_segments_api().evaluate_selected_segment(
            window(count=4),
            source,
            SegmentAnalysisRequest(
                MarketSegment(0, 3),
                StructuralLevel.SHORT,
                bms=BMSAnalysisRequest(0, 1, 2),
            ),
        )
    with pytest.raises(NotImplementedError):
        load_segments_api().evaluate_selected_segment(
            window(count=4),
            source,
            SegmentAnalysisRequest(
                MarketSegment(0, 3),
                StructuralLevel.SHORT,
                sms=SMSAnalysisRequest(2, 1),
            ),
        )


def test_offline_facade_wires_selected_segment_after_objective_hierarchy() -> None:
    from trading.analysis.offline import analyze_market_window

    source_window = window(count=4)
    segment_request = request(0, 3)
    result = analyze_market_window(source_window, segment=segment_request)

    assert result.window is source_window
    assert result.segment is not None
    assert result.segment.request is segment_request
    assert result.segment.selected_points == ()
    assert result.segment.market_state.status is EvaluationStatus.UNAVAILABLE
