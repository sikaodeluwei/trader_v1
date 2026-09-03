"""Selected-level offline segment resolution and market-state availability."""

from trading.definitions import market_structure
from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.market_structure import StructurePoint, StructurePointKind

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

    if request.bms is not None or request.sms is not None:
        raise NotImplementedError(
            "BMS and SMS segment analysis are implemented in later tasks"
        )

    selected = tuple(
        item
        for item in select_canonical_vertices(hierarchy, request.level)
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

    return SegmentAnalysisResult(
        request=request,
        selected_points=selected,
        market_state=market_state,
        bms=None,
        sms=None,
    )
