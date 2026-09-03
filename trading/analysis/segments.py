"""Selected-level offline segment resolution and market-state availability."""

from trading.definitions import market_structure
from trading.definitions.candles import Candle
from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.market_structure import StructurePoint, StructurePointKind
from trading.definitions.pullback_structure import (
    BMSObservation,
    BMSResult,
    PullbackContext,
    evaluate_bms,
)
from trading.definitions.sms_structure import (
    SMSContext,
    SMSObservation,
    SMSResult,
    evaluate_sms,
)

from .hierarchy import StructuralHierarchy
from .models import (
    Evaluation,
    EvaluationReason,
    EvaluationStatus,
    OfflineMarketWindow,
    ResolvedStructurePoint,
    SegmentAnalysisRequest,
    SegmentAnalysisResult,
    StructuralLevel,
)


def _canonical_vertices(
    hierarchy: StructuralHierarchy,
    level: StructuralLevel,
) -> tuple[object, ...]:
    return {
        StructuralLevel.SHORT: hierarchy.short_term.vertices,
        StructuralLevel.MEDIUM: hierarchy.medium_term.vertices,
        StructuralLevel.LONG: hierarchy.long_term.vertices,
    }[level]


def _vertex_index(vertex: object, level: StructuralLevel) -> int:
    if level is StructuralLevel.SHORT:
        return vertex.index  # type: ignore[attr-defined]
    return vertex.pivot_index  # type: ignore[attr-defined]


def _vertex_to_point(vertex: object, level: StructuralLevel) -> StructurePoint:
    kind = vertex.kind  # type: ignore[attr-defined]
    if not isinstance(kind, IsolatedPointKind):
        raise TypeError("canonical vertex kind must be an isolated-point kind")
    return StructurePoint(
        index=_vertex_index(vertex, level),
        kind=StructurePointKind(kind.value),
        price=vertex.price,  # type: ignore[attr-defined]
    )


def _invalid_bms(reason: EvaluationReason, message: str) -> Evaluation[BMSResult]:
    return Evaluation(EvaluationStatus.INVALID, reason=reason, message=message)


def _resolve_bms_vertex(
    vertices: tuple[ResolvedStructurePoint, ...],
    index: int,
) -> ResolvedStructurePoint | None:
    matches = [item for item in vertices if item.point.index == index]
    return matches[0] if len(matches) == 1 else None


def _candle_at(window: OfflineMarketWindow, index: int) -> Candle:
    position = index - window.start_index
    observation = window.candles[position]
    return Candle(observation.open, observation.high, observation.low, observation.close)


def _evaluate_bms(
    window: OfflineMarketWindow,
    request: SegmentAnalysisRequest,
    all_vertices: tuple[ResolvedStructurePoint, ...],
    market_state: Evaluation,
) -> Evaluation[BMSResult]:
    bms_request = request.bms
    assert bms_request is not None

    if (
        market_state.status is not EvaluationStatus.AVAILABLE
        or market_state.value
        not in {market_structure.MarketState.UPTREND, market_structure.MarketState.DOWNTREND}
    ):
        return Evaluation(
            EvaluationStatus.UNAVAILABLE,
            reason=EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL,
        )

    trend_origin = _resolve_bms_vertex(all_vertices, bms_request.trend_origin_index)
    previous_extreme = _resolve_bms_vertex(all_vertices, bms_request.previous_extreme_index)
    pullback_extreme = _resolve_bms_vertex(all_vertices, bms_request.pullback_extreme_index)
    if trend_origin is None or previous_extreme is None or pullback_extreme is None:
        return _invalid_bms(
            EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX,
            "BMS boundary index must resolve to exactly one canonical vertex",
        )

    if not (
        window.start_index
        <= pullback_extreme.point.index
        <= window.start_index + len(window.candles) - 1
    ):
        return _invalid_bms(
            EvaluationReason.INVALID_CONTEXT,
            "pullback extreme is outside window",
        )

    try:
        context = PullbackContext(
            request.segment,
            market_state.value,
            trend_origin.point,
            previous_extreme.point,
            pullback_extreme.point,
        )
        window_end = window.start_index + len(window.candles) - 1
        observations = tuple(
            BMSObservation(index, _candle_at(window, index))
            for index in range(pullback_extreme.point.index + 1, window_end + 1)
        )
        result = evaluate_bms(context, observations)
    except ValueError as exc:
        message = str(exc)
        reason = (
            EvaluationReason.OHLC_INTRABAR_ORDER_AMBIGUOUS
            if message == "OHLC cannot determine the intrabar boundary order"
            else EvaluationReason.INVALID_CONTEXT
        )
        return _invalid_bms(reason, message)

    return Evaluation(EvaluationStatus.AVAILABLE, value=result)


def _invalid_sms(reason: EvaluationReason, message: str) -> Evaluation[SMSResult]:
    return Evaluation(EvaluationStatus.INVALID, reason=reason, message=message)


def _evaluate_sms(
    window: OfflineMarketWindow,
    request: SegmentAnalysisRequest,
    all_vertices: tuple[ResolvedStructurePoint, ...],
    market_state: Evaluation,
) -> Evaluation[SMSResult]:
    sms_request = request.sms
    assert sms_request is not None

    if (
        market_state.status is not EvaluationStatus.AVAILABLE
        or market_state.value
        not in {market_structure.MarketState.UPTREND, market_structure.MarketState.DOWNTREND}
    ):
        return Evaluation(
            EvaluationStatus.UNAVAILABLE,
            reason=EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL,
        )

    trend_extreme = _resolve_bms_vertex(all_vertices, sms_request.trend_extreme_index)
    creator_point = _resolve_bms_vertex(all_vertices, sms_request.creator_point_index)
    if trend_extreme is None or creator_point is None:
        return _invalid_sms(
            EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX,
            "SMS boundary index must resolve to exactly one canonical vertex",
        )

    try:
        context = SMSContext(
            request.segment,
            market_state.value,
            trend_extreme.point,
            creator_point.point,
        )
        window_end = window.start_index + len(window.candles) - 1
        observations = tuple(
            SMSObservation(index, _candle_at(window, index))
            for index in range(trend_extreme.point.index + 1, window_end + 1)
        )
        result = evaluate_sms(context, observations)
    except ValueError as exc:
        message = str(exc)
        reason = (
            EvaluationReason.OHLC_INTRABAR_ORDER_AMBIGUOUS
            if message == "OHLC cannot determine the intrabar boundary order"
            else EvaluationReason.INVALID_CONTEXT
        )
        return _invalid_sms(reason, message)

    return Evaluation(EvaluationStatus.AVAILABLE, value=result)


def select_canonical_vertices(
    hierarchy: StructuralHierarchy,
    level: StructuralLevel,
) -> tuple[ResolvedStructurePoint, ...]:
    """Resolve only canonical vertices for one structural level."""

    return tuple(
        ResolvedStructurePoint(
            level=level,
            source_vertex=vertex,
            point=_vertex_to_point(vertex, level),
        )
        for vertex in _canonical_vertices(hierarchy, level)
    )


def evaluate_selected_segment(
    window: OfflineMarketWindow,
    hierarchy: StructuralHierarchy,
    request: SegmentAnalysisRequest,
) -> SegmentAnalysisResult:
    """Evaluate selected canonical structure within an explicit window segment."""

    window_end = window.start_index + len(window.candles) - 1
    if (
        request.segment.start_index < window.start_index
        or request.segment.end_index > window_end
    ):
        raise ValueError("segment is outside window")

    all_vertices = select_canonical_vertices(hierarchy, request.level)

    selected = tuple(
        item
        for item in all_vertices
        if request.segment.start_index <= item.point.index <= request.segment.end_index
    )
    points = tuple(item.point for item in selected)
    high_count = sum(point.kind is StructurePointKind.HIGH for point in points)
    low_count = sum(point.kind is StructurePointKind.LOW for point in points)

    if high_count < 2 or low_count < 2:
        market_state = Evaluation(
            EvaluationStatus.UNAVAILABLE,
            reason=EvaluationReason.INSUFFICIENT_STRUCTURE,
        )
    else:
        market_state = Evaluation(
            EvaluationStatus.AVAILABLE,
            value=market_structure.classify_market_state(request.segment, points),
        )

    bms = (
        None
        if request.bms is None
        else _evaluate_bms(window, request, all_vertices, market_state)
    )
    sms = (
        None
        if request.sms is None
        else _evaluate_sms(window, request, all_vertices, market_state)
    )

    return SegmentAnalysisResult(
        request=request,
        selected_points=selected,
        market_state=market_state,
        bms=bms,
        sms=sms,
    )
