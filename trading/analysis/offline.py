"""Objective offline composition for validated market-data windows."""

from dataclasses import dataclass

from .candles import OfflineCandleResult, analyze_closed_candle
from .hierarchy import StructuralHierarchy, build_structural_hierarchy
from .isolated import find_isolated_point_recognitions
from .models import (
    OfflineMarketWindow,
    SegmentAnalysisRequest,
    SegmentAnalysisResult,
)
from .segments import evaluate_selected_segment


@dataclass(frozen=True)
class OfflineMarketAnalysis:
    window: OfflineMarketWindow
    candles: tuple[OfflineCandleResult, ...]
    hierarchy: StructuralHierarchy
    segment: SegmentAnalysisResult | None


def analyze_market_window(
    window: OfflineMarketWindow,
    segment: SegmentAnalysisRequest | None = None,
) -> OfflineMarketAnalysis:
    """Analyze a validated window without inferring market semantics."""

    candles = tuple(
        analyze_closed_candle(item, index=window.start_index + offset)
        for offset, item in enumerate(window.candles)
    )
    scan = find_isolated_point_recognitions(
        tuple(item.candle for item in candles),
        start_index=window.start_index,
    )
    hierarchy = build_structural_hierarchy(scan)
    segment_result = (
        None
        if segment is None
        else evaluate_selected_segment(window, hierarchy, segment)
    )
    return OfflineMarketAnalysis(window, candles, hierarchy, segment_result)
