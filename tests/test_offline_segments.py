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
    StructurePoint,
    StructurePointKind,
)
from trading.definitions.pullback_structure import PullbackStructureStatus
from trading.definitions.sms_structure import SMSStructureStatus
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


def test_sms_request_returns_explicit_evaluation() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({}, count=5), sms_uptrend_hierarchy(), sms_request()
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.AVAILABLE
    assert result.sms.value is not None
    assert result.sms.value.status is SMSStructureStatus.PENDING


def range_window(ranges: dict[int, tuple[float, float]], count: int = 9) -> OfflineMarketWindow:
    """Build valid closed OHLC observations with selected high/low ranges."""
    timestamp = datetime(2026, 9, 3, 9, 30, tzinfo=timezone.utc)
    candles = []
    for index in range(count):
        high, low = ranges.get(index, (110.0, 100.0))
        midpoint = (high + low) / 2
        candles.append(
            ClosedCandleObservation(
                timestamp=timestamp + timedelta(minutes=index),
                open=midpoint,
                high=high,
                low=low,
                close=midpoint,
            )
        )
    return OfflineMarketWindow("MNQ", "1m", 0, tuple(candles))


def bms_uptrend_hierarchy(*, include_pullback: bool = True) -> StructuralHierarchy:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 100.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
        short_point(3, IsolatedPointKind.LOW, 95.0),
        short_point(4, IsolatedPointKind.HIGH, 120.0),
    ]
    if include_pullback:
        points.append(short_point(6, IsolatedPointKind.LOW, 105.0))
    return hierarchy(short=tuple(points))


def bms_request() -> SegmentAnalysisRequest:
    return SegmentAnalysisRequest(
        MarketSegment(0, 4),
        StructuralLevel.SHORT,
        bms=BMSAnalysisRequest(
            trend_origin_index=3,
            previous_extreme_index=4,
            pullback_extreme_index=6,
        ),
    )


def test_bms_resolves_canonical_vertices_and_passes_dense_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    segments = load_segments_api()
    observed: list[object] = []
    original = segments.evaluate_bms

    def spy(context: object, observations: object) -> object:
        observed.extend(observations)  # type: ignore[arg-type]
        return original(context, observations)  # type: ignore[arg-type]

    monkeypatch.setattr(segments, "evaluate_bms", spy)
    result = segments.evaluate_selected_segment(
        range_window({7: (120.0, 104.0), 8: (121.0, 104.0)}),
        bms_uptrend_hierarchy(),
        bms_request(),
    )

    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.AVAILABLE
    assert result.bms.value is not None
    assert result.bms.value.status is PullbackStructureStatus.BMS_CONFIRMED
    assert result.bms.value.broken_extreme == StructurePoint(4, StructurePointKind.HIGH, 120.0)
    assert result.bms.value.breakout_index == 8
    assert [item.index for item in observed] == [7, 8]


def test_bms_touch_remains_pullback_only() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (120.0, 104.0)}),
        bms_uptrend_hierarchy(),
        bms_request(),
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.AVAILABLE
    assert result.bms.value is not None
    assert result.bms.value.status is PullbackStructureStatus.PULLBACK_ONLY


def test_bms_ohlc_dual_crossing_is_explicitly_ambiguous() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (121.0, 94.0)}),
        bms_uptrend_hierarchy(),
        bms_request(),
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.INVALID
    assert result.bms.reason is EvaluationReason.OHLC_INTRABAR_ORDER_AMBIGUOUS
    assert result.bms.message == "OHLC cannot determine the intrabar boundary order"


@pytest.mark.parametrize("bad_index", [999, 5])
def test_bms_rejects_missing_or_noncanonical_boundary_indexes(bad_index: int) -> None:
    source = bms_uptrend_hierarchy()
    if bad_index == 5:
        short = source.short_term
        suppressed = SuppressedShortTermPoint(
            short_point(5, IsolatedPointKind.LOW, 105.0),
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        )
        source = StructuralHierarchy(
            source.isolated,
            ShortTermStructure(short.points + (suppressed.point,), short.vertices, (suppressed,)),
            source.medium_term,
            source.long_term,
        )
    request_value = SegmentAnalysisRequest(
        MarketSegment(0, 4),
        StructuralLevel.SHORT,
        bms=BMSAnalysisRequest(3, 4, bad_index),
    )
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (120.0, 104.0)}), source, request_value
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.INVALID
    assert result.bms.reason is EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX


def test_bms_rejects_index_present_only_as_nonvertex_or_at_another_level() -> None:
    base = bms_uptrend_hierarchy(include_pullback=False)
    medium = (medium_point(6, IsolatedPointKind.LOW, 105.0),)
    source = StructuralHierarchy(
        base.isolated,
        base.short_term,
        MediumTermStructure(medium, (), medium, ()),
        base.long_term,
    )
    request_value = SegmentAnalysisRequest(
        MarketSegment(0, 4),
        StructuralLevel.SHORT,
        bms=BMSAnalysisRequest(3, 4, 6),
    )
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (120.0, 104.0)}), source, request_value
    )
    assert result.bms is not None
    assert result.bms.reason is EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX


def test_bms_rejects_index_present_only_in_points_not_vertices() -> None:
    base = bms_uptrend_hierarchy(include_pullback=False)
    nonvertex = short_point(6, IsolatedPointKind.LOW, 105.0)
    source = StructuralHierarchy(
        base.isolated,
        ShortTermStructure(base.short_term.points + (nonvertex,), base.short_term.vertices, ()),
        base.medium_term,
        base.long_term,
    )
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (120.0, 104.0)}),
        source,
        bms_request(),
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.INVALID
    assert result.bms.reason is EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX


@pytest.mark.parametrize(
    ("segment", "request_value", "message"),
    [
        (MarketSegment(0, 4), BMSAnalysisRequest(0, 4, 6), "point kinds"),
        (MarketSegment(0, 4), BMSAnalysisRequest(3, 4, 1), "chronology"),
        (MarketSegment(0, 3), BMSAnalysisRequest(3, 4, 6), "outside parent segment"),
    ],
)
def test_bms_preserves_existing_context_validation(
    segment: MarketSegment,
    request_value: BMSAnalysisRequest,
    message: str,
) -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (120.0, 104.0)}),
        bms_uptrend_hierarchy(),
        SegmentAnalysisRequest(segment, StructuralLevel.SHORT, bms=request_value),
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.INVALID
    assert result.bms.reason is EvaluationReason.INVALID_CONTEXT
    assert result.bms.message is not None
    assert message in result.bms.message


def test_bms_parent_state_gate_does_not_construct_context(monkeypatch: pytest.MonkeyPatch) -> None:
    segments = load_segments_api()

    def fail_if_constructed(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("PullbackContext must not be constructed")

    monkeypatch.setattr(segments, "PullbackContext", fail_if_constructed)
    result = segments.evaluate_selected_segment(
        range_window({7: (120.0, 104.0)}),
        hierarchy(
            short=(
                short_point(0, IsolatedPointKind.HIGH, 100.0),
                short_point(1, IsolatedPointKind.LOW, 90.0),
                short_point(2, IsolatedPointKind.HIGH, 110.0),
            )
        ),
        bms_request(),
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.UNAVAILABLE
    assert result.bms.reason is EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL


def test_bms_sufficient_nontrend_parent_is_unavailable() -> None:
    points = (
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(2, IsolatedPointKind.HIGH, 105.0),
        short_point(3, IsolatedPointKind.LOW, 95.0),
        short_point(4, IsolatedPointKind.HIGH, 120.0),
        short_point(6, IsolatedPointKind.LOW, 105.0),
    )
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (121.0, 104.0)}),
        hierarchy(short=points),
        bms_request(),
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.UNAVAILABLE
    assert result.bms.reason is EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL


def test_downtrend_bms_resolves_and_evaluates_symmetrically() -> None:
    points = (
        short_point(0, IsolatedPointKind.HIGH, 120.0),
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
        short_point(3, IsolatedPointKind.LOW, 90.0),
        short_point(6, IsolatedPointKind.HIGH, 95.0),
    )
    request_value = SegmentAnalysisRequest(
        MarketSegment(0, 3),
        StructuralLevel.SHORT,
        bms=BMSAnalysisRequest(2, 3, 6),
    )
    result = load_segments_api().evaluate_selected_segment(
        range_window({7: (90.0, 90.0), 8: (95.0, 89.0)}),
        hierarchy(short=points),
        request_value,
    )
    assert result.bms is not None
    assert result.bms.status is EvaluationStatus.AVAILABLE
    assert result.bms.value is not None
    assert result.bms.value.status is PullbackStructureStatus.BMS_CONFIRMED
    assert result.bms.value.broken_extreme == StructurePoint(3, StructurePointKind.LOW, 90.0)
    assert result.bms.value.breakout_index == 8


def sms_uptrend_hierarchy() -> StructuralHierarchy:
    return hierarchy(
        short=(
            short_point(0, IsolatedPointKind.HIGH, 100.0),
            short_point(1, IsolatedPointKind.LOW, 90.0),
            short_point(2, IsolatedPointKind.HIGH, 110.0),
            short_point(3, IsolatedPointKind.LOW, 95.0),
            short_point(4, IsolatedPointKind.HIGH, 120.0),
        )
    )


def sms_request(
    *,
    segment: MarketSegment = MarketSegment(0, 4),
    trend_extreme_index: int = 4,
    creator_point_index: int = 3,
    level: StructuralLevel = StructuralLevel.SHORT,
) -> SegmentAnalysisRequest:
    return SegmentAnalysisRequest(
        segment,
        level,
        sms=SMSAnalysisRequest(trend_extreme_index, creator_point_index),
    )


def test_sms_empty_suffix_is_available_pending() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({}, count=5), sms_uptrend_hierarchy(), sms_request()
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.AVAILABLE
    assert result.sms.value is not None
    assert result.sms.value.status is SMSStructureStatus.PENDING


def test_sms_exact_touches_do_not_break() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({5: (120.0, 95.0), 6: (120.0, 95.0)}),
        sms_uptrend_hierarchy(),
        sms_request(),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.AVAILABLE
    assert result.sms.value is not None
    assert result.sms.value.status is SMSStructureStatus.PULLBACK_ONLY


def test_sms_confirmation_returns_creator_and_first_event() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({6: (120.0, 94.0), 7: (121.0, 94.0)}),
        sms_uptrend_hierarchy(),
        sms_request(),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.AVAILABLE
    assert result.sms.value is not None
    assert result.sms.value.status is SMSStructureStatus.SMS_CONFIRMED
    assert result.sms.value.broken_point == StructurePoint(
        3, StructurePointKind.LOW, 95.0
    )
    assert result.sms.value.event_index == 6


def test_sms_parent_continuation_returns_trend_extreme_and_first_event() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({6: (121.0, 100.0), 7: (121.0, 94.0)}),
        sms_uptrend_hierarchy(),
        sms_request(),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.AVAILABLE
    assert result.sms.value is not None
    assert result.sms.value.status is SMSStructureStatus.PARENT_CONTINUED
    assert result.sms.value.broken_point == StructurePoint(
        4, StructurePointKind.HIGH, 120.0
    )
    assert result.sms.value.event_index == 6


def test_sms_builds_complete_dense_suffix_before_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    segments = load_segments_api()
    observed: list[object] = []
    original = segments.evaluate_sms

    def spy(context: object, observations: object) -> object:
        observed.extend(observations)  # type: ignore[arg-type]
        return original(context, observations)  # type: ignore[arg-type]

    monkeypatch.setattr(segments, "evaluate_sms", spy)
    result = segments.evaluate_selected_segment(
        range_window({}, count=9), sms_uptrend_hierarchy(), sms_request()
    )

    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.AVAILABLE
    assert [item.index for item in observed] == [5, 6, 7, 8]


def test_sms_ohlc_dual_crossing_is_explicitly_ambiguous() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({6: (121.0, 94.0)}),
        sms_uptrend_hierarchy(),
        sms_request(),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.INVALID
    assert result.sms.reason is EvaluationReason.OHLC_INTRABAR_ORDER_AMBIGUOUS
    assert result.sms.message == "OHLC cannot determine the intrabar boundary order"


@pytest.mark.parametrize("bad_index", [999, 5])
def test_sms_rejects_missing_or_noncanonical_boundary_indexes(bad_index: int) -> None:
    source = sms_uptrend_hierarchy()
    if bad_index == 5:
        short = source.short_term
        suppressed = SuppressedShortTermPoint(
            short_point(5, IsolatedPointKind.LOW, 105.0),
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        )
        source = StructuralHierarchy(
            source.isolated,
            ShortTermStructure(
                short.points + (suppressed.point,), short.vertices, (suppressed,)
            ),
            source.medium_term,
            source.long_term,
        )
    result = load_segments_api().evaluate_selected_segment(
        range_window({}, count=9),
        source,
        sms_request(creator_point_index=bad_index),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.INVALID
    assert result.sms.reason is EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX


def test_sms_rejects_index_present_only_at_another_level() -> None:
    base = sms_uptrend_hierarchy()
    medium = (medium_point(5, IsolatedPointKind.LOW, 105.0),)
    source = StructuralHierarchy(
        base.isolated,
        base.short_term,
        MediumTermStructure(medium, (), medium, ()),
        base.long_term,
    )
    result = load_segments_api().evaluate_selected_segment(
        range_window({}, count=9),
        source,
        sms_request(creator_point_index=5),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.INVALID
    assert result.sms.reason is EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX


@pytest.mark.parametrize(
    ("segment", "trend_extreme_index", "creator_point_index"),
    [
        (MarketSegment(0, 4), 3, 2),
        (MarketSegment(0, 3), 4, 3),
    ],
)
def test_sms_preserves_existing_context_validation(
    segment: MarketSegment,
    trend_extreme_index: int,
    creator_point_index: int,
) -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({}, count=9),
        sms_uptrend_hierarchy(),
        sms_request(
            segment=segment,
            trend_extreme_index=trend_extreme_index,
            creator_point_index=creator_point_index,
        ),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.INVALID
    assert result.sms.reason is EvaluationReason.INVALID_CONTEXT


def test_sms_parent_state_gate_does_not_construct_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    segments = load_segments_api()

    def fail_if_constructed(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("SMSContext must not be constructed")

    monkeypatch.setattr(segments, "SMSContext", fail_if_constructed)
    result = segments.evaluate_selected_segment(
        range_window({}, count=9),
        hierarchy(
            short=(
                short_point(0, IsolatedPointKind.HIGH, 100.0),
                short_point(1, IsolatedPointKind.LOW, 90.0),
                short_point(2, IsolatedPointKind.HIGH, 110.0),
            )
        ),
        sms_request(segment=MarketSegment(0, 2), trend_extreme_index=2, creator_point_index=1),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.UNAVAILABLE
    assert result.sms.reason is EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL


def test_sms_sufficient_nontrend_parent_is_unavailable() -> None:
    result = load_segments_api().evaluate_selected_segment(
        range_window({}, count=9),
        hierarchy(
            short=(
                short_point(0, IsolatedPointKind.HIGH, 110.0),
                short_point(1, IsolatedPointKind.LOW, 90.0),
                short_point(2, IsolatedPointKind.HIGH, 105.0),
                short_point(3, IsolatedPointKind.LOW, 95.0),
                short_point(4, IsolatedPointKind.HIGH, 120.0),
            )
        ),
        sms_request(),
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.UNAVAILABLE
    assert result.sms.reason is EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL


def test_downtrend_sms_resolves_and_evaluates_symmetrically() -> None:
    source = hierarchy(
        short=(
            short_point(0, IsolatedPointKind.HIGH, 120.0),
            short_point(1, IsolatedPointKind.LOW, 100.0),
            short_point(2, IsolatedPointKind.HIGH, 110.0),
            short_point(3, IsolatedPointKind.LOW, 90.0),
        )
    )
    request_value = sms_request(
        segment=MarketSegment(0, 3), trend_extreme_index=3, creator_point_index=2
    )
    result = load_segments_api().evaluate_selected_segment(
        range_window({4: (111.0, 90.0), 5: (111.0, 89.0)}), source, request_value
    )
    assert result.sms is not None
    assert result.sms.status is EvaluationStatus.AVAILABLE
    assert result.sms.value is not None
    assert result.sms.value.status is SMSStructureStatus.SMS_CONFIRMED
    assert result.sms.value.broken_point == StructurePoint(
        2, StructurePointKind.HIGH, 110.0
    )
    assert result.sms.value.event_index == 4


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
