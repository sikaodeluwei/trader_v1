"""Deterministic A-E integration checkpoints for offline market structure."""

from datetime import datetime, timedelta, timezone

import pytest

from trading.analysis.candles import analyze_closed_candle
from trading.analysis.hierarchy import StructuralHierarchy, build_structural_hierarchy
from trading.analysis.isolated import IsolatedPointScan, find_isolated_point_recognitions
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
from trading.analysis.offline import analyze_market_window
from trading.analysis.segments import evaluate_selected_segment
from trading.definitions.candles import Candle, CandleSide
from trading.definitions.extremes import ExtremeOrder
from trading.definitions.features import CandleFeatures
from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from trading.definitions.isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)
from trading.definitions.long_term_structure import LongTermStructure
from trading.definitions.market_structure import MarketSegment, MarketState, StructurePoint, StructurePointKind
from trading.definitions.medium_term_structure import (
    MediumTermPoint,
    MediumTermStructure,
    MediumTermSuppressionReason,
    SuppressedMediumTermPoint,
)
from trading.definitions.movements import MovementSide, PriceLeg
from trading.definitions.pullback_structure import PullbackStructureStatus
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    ShortTermSuppressionReason,
)
from trading.definitions.sms_structure import SMSStructureStatus


UTC_START = datetime(2026, 9, 3, 9, 30, tzinfo=timezone.utc)


def midpoint_candle(high: float, low: float) -> Candle:
    midpoint = (high + low) / 2
    return Candle(midpoint, high, low, midpoint)


def closed_window(
    ranges: dict[int, tuple[float, float]],
    *,
    count: int,
    start_index: int = 0,
) -> OfflineMarketWindow:
    candles = tuple(
        ClosedCandleObservation(
            timestamp=UTC_START + timedelta(minutes=offset),
            open=(high + low) / 2,
            high=high,
            low=low,
            close=(high + low) / 2,
        )
        for offset in range(count)
        for high, low in (ranges.get(start_index + offset, (110.0, 100.0)),)
    )
    return OfflineMarketWindow("MNQ", "1m", start_index, candles)


def confirmed(
    index: int,
    kind: IsolatedPointKind,
    price: float,
    basis: IsolatedPointBasis = IsolatedPointBasis.STRICT,
) -> IsolatedPointRecognition:
    return IsolatedPointRecognition(
        IsolatedPoint(index, kind, IsolatedPointStatus.CONFIRMED, price), basis
    )


def short_point(index: int, kind: IsolatedPointKind, price: float) -> ShortTermPoint:
    return ShortTermPoint(index, kind, price, IsolatedPointBasis.STRICT)


def medium_point(index: int, kind: IsolatedPointKind, price: float) -> MediumTermPoint:
    return MediumTermPoint(
        short_point(index, kind, price),
        short_point(index + 1, kind, price),
    )


def hand_built_hierarchy(
    *points: ShortTermPoint,
    medium: tuple[MediumTermPoint, ...] = (),
) -> StructuralHierarchy:
    short = ShortTermStructure(tuple(points), tuple(points), ())
    return StructuralHierarchy(
        IsolatedPointScan((), None),
        short,
        MediumTermStructure(medium, (), medium, ()),
        LongTermStructure((), (), (), ()),
    )


def test_a_exact_candle_and_intrabar_capabilities() -> None:
    """Test A catches a broken Chapter 1 adapter or fabricated capability."""

    path = (100.0, 99.0, 102.0, 106.0, 110.0, 107.0, 103.0, 101.0)
    observation = ClosedCandleObservation(
        UTC_START, 100.0, 110.0, 99.0, 101.0, path
    )

    result = analyze_closed_candle(observation, index=40)

    assert result.index == 40
    assert result.timestamp == UTC_START
    assert result.observation is observation
    assert result.candle == Candle(100.0, 110.0, 99.0, 101.0)
    assert result.side is CandleSide.BULLISH
    assert result.geometry.body_ratio == pytest.approx(1 / 11)
    assert result.geometry.upper_wick_ratio == pytest.approx(9 / 11)
    assert result.geometry.lower_wick_ratio == pytest.approx(1 / 11)
    assert result.geometry.open_position == pytest.approx(1 / 11)
    assert result.geometry.close_position == pytest.approx(2 / 11)
    assert result.control.buyer_control == 2.0
    assert result.control.seller_control == 9.0
    assert result.control.buyer_control_ratio == pytest.approx(2 / 11)
    assert result.control.seller_control_ratio == pytest.approx(9 / 11)
    assert result.control.control_score == pytest.approx(-7 / 11)

    assert result.intrabar_analysis.status is EvaluationStatus.AVAILABLE
    analysis = result.intrabar_analysis.value
    assert analysis is not None
    assert analysis.legs == [
        PriceLeg(MovementSide.SELLER, 100.0, 99.0, 1.0),
        PriceLeg(MovementSide.BUYER, 99.0, 110.0, 11.0),
        PriceLeg(MovementSide.SELLER, 110.0, 101.0, 9.0),
    ]
    assert analysis.movements.first_side is MovementSide.SELLER
    assert analysis.movements.first_distance == 1.0
    assert analysis.movements.final_side is MovementSide.SELLER
    assert analysis.movements.final_distance == 9.0
    assert analysis.movements.total_buyer_movement == 11.0
    assert analysis.movements.total_seller_movement == 10.0
    assert analysis.movements.final_retracement_ratio == pytest.approx(9 / 11)
    assert analysis.extreme_path.order is ExtremeOrder.LOW_THEN_HIGH
    assert analysis.extreme_path.legs == analysis.legs
    assert analysis.extreme_evidence.order is ExtremeOrder.LOW_THEN_HIGH
    assert analysis.extreme_evidence.initial_side is MovementSide.SELLER
    assert analysis.extreme_evidence.initial_ratio == pytest.approx(1 / 11)
    assert analysis.extreme_evidence.main_side is MovementSide.BUYER
    assert analysis.extreme_evidence.main_ratio == 1.0
    assert analysis.extreme_evidence.final_side is MovementSide.SELLER
    assert analysis.extreme_evidence.final_ratio == pytest.approx(9 / 11)

    assert result.features.status is EvaluationStatus.AVAILABLE
    assert result.features.value == CandleFeatures(
        side=CandleSide.BULLISH,
        body_ratio=1 / 11,
        upper_wick_ratio=9 / 11,
        lower_wick_ratio=1 / 11,
        open_position=1 / 11,
        close_position=2 / 11,
        control_score=-7 / 11,
        extreme_order=ExtremeOrder.LOW_THEN_HIGH,
        initial_side=MovementSide.SELLER,
        initial_ratio=1 / 11,
        final_side=MovementSide.SELLER,
        final_ratio=9 / 11,
        displacement_ratio=1 / 11,
        total_buyer_movement_ratio=1.0,
        total_seller_movement_ratio=10 / 11,
    )
    assert result.candle_type.status is EvaluationStatus.UNAVAILABLE
    assert result.candle_type.reason is EvaluationReason.CANDLE_TYPE_UNCALIBRATED

    ohlc_only = analyze_closed_candle(
        ClosedCandleObservation(UTC_START, 100.0, 110.0, 99.0, 101.0),
        index=41,
    )
    assert ohlc_only.side is CandleSide.BULLISH
    assert ohlc_only.intrabar_analysis.status is EvaluationStatus.UNAVAILABLE
    assert ohlc_only.intrabar_analysis.reason is EvaluationReason.INTRABAR_DATA_UNAVAILABLE
    assert ohlc_only.features.status is EvaluationStatus.UNAVAILABLE
    assert ohlc_only.features.reason is EvaluationReason.INTRABAR_DATA_UNAVAILABLE
    assert ohlc_only.candle_type.reason is EvaluationReason.CANDLE_TYPE_UNCALIBRATED


def test_b_isolated_recognition_is_offset_chronological_and_unresolved() -> None:
    """Test B catches changed confirmation/equality/deformation scan behavior."""

    candles = tuple(
        midpoint_candle(high, low)
        for high, low in (
            (10, 5), (12, 7), (11, 6), (13, 8),
            (13, 9), (15, 10), (15, 8), (12, 7),
        )
    )

    result = find_isolated_point_recognitions(candles, start_index=100)

    assert result.recognitions == (
        confirmed(101, IsolatedPointKind.HIGH, 12.0),
        confirmed(102, IsolatedPointKind.LOW, 6.0),
        confirmed(103, IsolatedPointKind.HIGH, 13.0, IsolatedPointBasis.RIGHT_INSIDE_BAR),
    )
    assert [item.point.index for item in result.recognitions] == [101, 102, 103]
    assert all(item.point.index != 105 for item in result.recognitions)
    assert result.unresolved_potential == IsolatedPoint(
        107, IsolatedPointKind.LOW, IsolatedPointStatus.POTENTIAL, 7.0
    )


def test_c_supplied_recognitions_compose_cleaned_hierarchy_and_provenance() -> None:
    """Test C catches incorrect promotion or provenance after supplied recognition."""

    recognitions = tuple(
        item
        for position, (high, low) in enumerate(
            zip(
                (100, 110, 105, 120, 107, 115, 100),
                (90, 95, 80, 96, 85, 97, 70),
            )
        )
        for item in (
            confirmed(
                position * 2 + 1,
                IsolatedPointKind.HIGH,
                float(high),
                IsolatedPointBasis.RIGHT_INSIDE_BAR if position == 3 else IsolatedPointBasis.STRICT,
            ),
            confirmed(position * 2 + 2, IsolatedPointKind.LOW, float(low)),
        )
    )
    hierarchy = build_structural_hierarchy(IsolatedPointScan(recognitions, None))

    assert hierarchy.isolated.recognitions == recognitions
    expected_short_points = (
        ShortTermPoint(1, IsolatedPointKind.HIGH, 100.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(2, IsolatedPointKind.LOW, 90.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(3, IsolatedPointKind.HIGH, 110.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(4, IsolatedPointKind.LOW, 95.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(5, IsolatedPointKind.HIGH, 105.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(6, IsolatedPointKind.LOW, 80.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(7, IsolatedPointKind.HIGH, 120.0, IsolatedPointBasis.RIGHT_INSIDE_BAR),
        ShortTermPoint(8, IsolatedPointKind.LOW, 96.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(9, IsolatedPointKind.HIGH, 107.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(10, IsolatedPointKind.LOW, 85.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(11, IsolatedPointKind.HIGH, 115.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(12, IsolatedPointKind.LOW, 97.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(13, IsolatedPointKind.HIGH, 100.0, IsolatedPointBasis.STRICT),
        ShortTermPoint(14, IsolatedPointKind.LOW, 70.0, IsolatedPointBasis.STRICT),
    )
    assert hierarchy.short_term.points == expected_short_points
    assert [point.index for point in hierarchy.short_term.points] == list(range(1, 15))
    assert [point.recognition_basis for point in hierarchy.short_term.points] == [
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.RIGHT_INSIDE_BAR,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
        IsolatedPointBasis.STRICT,
    ]
    assert hierarchy.short_term.vertices == expected_short_points
    assert hierarchy.short_term.suppressed == ()
    assert [point.price for point in hierarchy.medium_term.points] == [110, 80, 120, 85, 115]
    assert len(hierarchy.medium_term.potentials) == 1
    medium_potential = hierarchy.medium_term.potentials[0]
    assert medium_potential.previous_same_kind is hierarchy.short_term.vertices[11]
    assert medium_potential.pivot is hierarchy.short_term.vertices[13]
    assert medium_potential.price == 70
    assert [point.price for point in hierarchy.medium_term.vertices] == [110, 80, 120, 85, 115]
    assert hierarchy.medium_term.suppressed == ()
    assert [point.price for point in hierarchy.long_term.points] == [120]
    assert hierarchy.long_term.potentials == ()
    assert hierarchy.long_term.vertices == hierarchy.long_term.points
    assert hierarchy.long_term.suppressed == ()
    long_high = hierarchy.long_term.points[0]
    assert long_high.pivot is hierarchy.medium_term.vertices[2]
    assert long_high.confirmed_by is hierarchy.medium_term.vertices[4]
    assert long_high.pivot.pivot is hierarchy.short_term.vertices[6]
    assert long_high.pivot.pivot.recognition_basis is IsolatedPointBasis.RIGHT_INSIDE_BAR

    cleaned = build_structural_hierarchy(
        IsolatedPointScan(
            (
                confirmed(1, IsolatedPointKind.HIGH, 100.0),
                confirmed(2, IsolatedPointKind.LOW, 90.0),
                confirmed(3, IsolatedPointKind.HIGH, 108.0),
                confirmed(4, IsolatedPointKind.HIGH, 110.0),
                confirmed(5, IsolatedPointKind.HIGH, 109.0),
                confirmed(6, IsolatedPointKind.LOW, 95.0),
                confirmed(7, IsolatedPointKind.HIGH, 105.0),
                confirmed(8, IsolatedPointKind.LOW, 80.0),
                confirmed(9, IsolatedPointKind.HIGH, 120.0),
                confirmed(10, IsolatedPointKind.LOW, 96.0),
                confirmed(11, IsolatedPointKind.HIGH, 107.0),
                confirmed(12, IsolatedPointKind.LOW, 85.0),
                confirmed(13, IsolatedPointKind.HIGH, 115.0),
                confirmed(14, IsolatedPointKind.LOW, 97.0),
                confirmed(15, IsolatedPointKind.HIGH, 100.0),
                confirmed(16, IsolatedPointKind.LOW, 70.0),
            ),
            None,
        )
    )
    suppressed_short = tuple(item.point for item in cleaned.short_term.suppressed)
    short_points_only = tuple(
        point
        for point in cleaned.short_term.points
        if not any(point is vertex for vertex in cleaned.short_term.vertices)
    )
    assert [point.price for point in suppressed_short] == [108.0, 109.0]
    assert cleaned.medium_term.points
    assert cleaned.long_term.points
    for medium_point in cleaned.medium_term.points:
        for source in (medium_point.pivot, medium_point.confirmed_by):
            assert any(source is vertex for vertex in cleaned.short_term.vertices)
            assert not any(source is suppressed for suppressed in suppressed_short)
            assert not any(source is points_only for points_only in short_points_only)
    medium_points_only = tuple(
        point
        for point in cleaned.medium_term.points
        if not any(point is vertex for vertex in cleaned.medium_term.vertices)
    )
    suppressed_medium = tuple(item.point for item in cleaned.medium_term.suppressed)
    for long_point in cleaned.long_term.points:
        for source in (long_point.pivot, long_point.confirmed_by):
            assert any(source is vertex for vertex in cleaned.medium_term.vertices)
            assert not any(source is suppressed for suppressed in suppressed_medium)
            assert not any(source is points_only for points_only in medium_points_only)

    same_kind = build_structural_hierarchy(
        IsolatedPointScan(
            (
                confirmed(1, IsolatedPointKind.LOW, 90.0),
                confirmed(2, IsolatedPointKind.HIGH, 108.0),
                confirmed(3, IsolatedPointKind.HIGH, 110.0),
                confirmed(4, IsolatedPointKind.HIGH, 109.0),
                confirmed(5, IsolatedPointKind.LOW, 95.0),
            ),
            None,
        )
    )
    assert [point.price for point in same_kind.short_term.vertices] == [90, 110, 95]
    assert [item.point.price for item in same_kind.short_term.suppressed] == [108, 109]
    assert all(
        item.reason is ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND
        for item in same_kind.short_term.suppressed
    )

    inside = build_structural_hierarchy(
        IsolatedPointScan(
            (
                confirmed(1, IsolatedPointKind.HIGH, 110.0),
                confirmed(2, IsolatedPointKind.LOW, 100.0),
                confirmed(3, IsolatedPointKind.HIGH, 108.0),
                confirmed(4, IsolatedPointKind.LOW, 102.0),
            ),
            None,
        )
    )
    assert [point.price for point in inside.short_term.vertices] == [110, 100]
    assert [item.point.price for item in inside.short_term.suppressed] == [108, 102]
    assert all(
        item.reason is ShortTermSuppressionReason.INSIDE_STRUCTURE
        for item in inside.short_term.suppressed
    )

    potential_hierarchy = build_structural_hierarchy(
        IsolatedPointScan(
            (
                confirmed(1, IsolatedPointKind.HIGH, 100.0),
                confirmed(2, IsolatedPointKind.LOW, 90.0),
                confirmed(3, IsolatedPointKind.HIGH, 110.0),
                confirmed(4, IsolatedPointKind.LOW, 80.0),
            ),
            None,
        )
    )
    assert [item.price for item in potential_hierarchy.medium_term.potentials] == [110, 80]
    assert potential_hierarchy.medium_term.potentials[0].pivot is potential_hierarchy.short_term.vertices[2]

    long_potential = build_structural_hierarchy(
        IsolatedPointScan(
            tuple(
                item
                for position, (high, low) in enumerate(
                    zip((100, 110, 105, 120, 115), (90, 95, 80, 96, 85))
                )
                for item in (
                    confirmed(position * 2 + 1, IsolatedPointKind.HIGH, float(high)),
                    confirmed(position * 2 + 2, IsolatedPointKind.LOW, float(low)),
                )
            ),
            None,
        )
    )
    assert [item.price for item in long_potential.long_term.potentials] == [120]
    assert long_potential.long_term.potentials[0].pivot is long_potential.medium_term.vertices[2]


def test_d_raw_ohlc_bridges_to_all_objective_levels() -> None:
    """Test D catches broken raw-OHLC-to-hierarchy composition."""

    high_low = (
        (96, 95), (100, 99), (91, 90), (110, 109), (96, 95),
        (105, 104), (81, 80), (120, 119), (120, 119.2),
        (97, 96), (107, 106), (86, 85), (115, 114),
        (98, 97), (100, 99), (71, 70), (80, 79),
    )
    window = OfflineMarketWindow(
        "MNQ",
        "1m",
        40,
        tuple(
            ClosedCandleObservation(
                UTC_START + timedelta(minutes=offset),
                (high + low) / 2,
                high,
                low,
                (high + low) / 2,
            )
            for offset, (high, low) in enumerate(high_low)
        ),
    )

    result = analyze_market_window(window)

    assert [item.index for item in result.candles] == list(range(40, 57))
    assert result.segment is None
    assert [item.point.index for item in result.hierarchy.isolated.recognitions] == [41, 42, 43, 44, 45, 46, 47, 49, 50, 51, 52, 53, 54, 55]
    assert 48 not in [item.point.index for item in result.hierarchy.isolated.recognitions]
    assert result.hierarchy.isolated.recognitions[6].basis is IsolatedPointBasis.RIGHT_INSIDE_BAR
    assert [point.price for point in result.hierarchy.short_term.points] == [
        100, 90, 110, 95, 105, 80, 120, 96, 107, 85, 115, 97, 100, 70,
    ]
    assert [point.price for point in result.hierarchy.medium_term.vertices] == [110, 80, 120, 85, 115]
    long_high = result.hierarchy.long_term.points[0]
    assert long_high.price == 120
    assert long_high.pivot is result.hierarchy.medium_term.vertices[2]
    assert long_high.confirmed_by is result.hierarchy.medium_term.vertices[4]
    assert long_high.pivot.pivot.recognition_basis is IsolatedPointBasis.RIGHT_INSIDE_BAR


def test_e_market_state_handles_directional_nontrend_and_insufficient_cases() -> None:
    """Test E catches incorrect explicit selected-segment state availability."""

    cases = (
        (
            (
                short_point(0, IsolatedPointKind.HIGH, 100.0),
                short_point(1, IsolatedPointKind.LOW, 90.0),
                short_point(2, IsolatedPointKind.HIGH, 110.0),
                short_point(3, IsolatedPointKind.LOW, 95.0),
                short_point(4, IsolatedPointKind.HIGH, 120.0),
            ),
            MarketState.UPTREND,
        ),
        (
            (
                short_point(0, IsolatedPointKind.HIGH, 120.0),
                short_point(1, IsolatedPointKind.LOW, 100.0),
                short_point(2, IsolatedPointKind.HIGH, 110.0),
                short_point(3, IsolatedPointKind.LOW, 90.0),
            ),
            MarketState.DOWNTREND,
        ),
        (
            (
                short_point(0, IsolatedPointKind.HIGH, 110.0),
                short_point(1, IsolatedPointKind.LOW, 90.0),
                short_point(2, IsolatedPointKind.HIGH, 105.0),
                short_point(3, IsolatedPointKind.LOW, 95.0),
            ),
            MarketState.NON_TREND,
        ),
    )
    for points, expected in cases:
        result = evaluate_selected_segment(
            closed_window({}, count=5),
            hand_built_hierarchy(*points),
            SegmentAnalysisRequest(MarketSegment(0, len(points) - 1), StructuralLevel.SHORT),
        )
        assert result.market_state.status is EvaluationStatus.AVAILABLE
        assert result.market_state.value is expected

    insufficient = evaluate_selected_segment(
        closed_window({}, count=3),
        hand_built_hierarchy(
            short_point(0, IsolatedPointKind.HIGH, 100.0),
            short_point(1, IsolatedPointKind.LOW, 90.0),
            short_point(2, IsolatedPointKind.HIGH, 110.0),
        ),
        SegmentAnalysisRequest(MarketSegment(0, 2), StructuralLevel.SHORT),
    )
    assert insufficient.market_state.status is EvaluationStatus.UNAVAILABLE
    assert insufficient.market_state.reason is EvaluationReason.INSUFFICIENT_STRUCTURE

    with pytest.raises(ValueError, match="outside window"):
        evaluate_selected_segment(
            closed_window({}, count=4),
            hand_built_hierarchy(short_point(0, IsolatedPointKind.HIGH, 100.0)),
            SegmentAnalysisRequest(MarketSegment(0, 4), StructuralLevel.SHORT),
        )


def test_e_bms_requires_selected_level_vertices_and_preserves_touch_and_break() -> None:
    """Test E catches automatic/cross-level BMS boundary resolution."""

    points = (
        short_point(0, IsolatedPointKind.HIGH, 100.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
        short_point(3, IsolatedPointKind.LOW, 95.0),
        short_point(4, IsolatedPointKind.HIGH, 120.0),
        short_point(6, IsolatedPointKind.LOW, 105.0),
    )
    request = SegmentAnalysisRequest(
        MarketSegment(0, 4),
        StructuralLevel.SHORT,
        bms=BMSAnalysisRequest(3, 4, 6),
    )
    source = hand_built_hierarchy(*points)

    touch = evaluate_selected_segment(
        closed_window({7: (120.0, 104.0)}, count=8), source, request
    )
    assert touch.bms is not None
    assert touch.bms.status is EvaluationStatus.AVAILABLE
    assert touch.bms.value is not None
    assert touch.bms.value.status is PullbackStructureStatus.PULLBACK_ONLY

    strict = evaluate_selected_segment(
        closed_window({7: (120.0, 104.0), 8: (121.0, 104.0)}, count=9),
        source,
        request,
    )
    assert strict.bms is not None
    assert strict.bms.value is not None
    assert strict.bms.value.status is PullbackStructureStatus.BMS_CONFIRMED
    assert strict.bms.value.broken_extreme == StructurePoint(4, StructurePointKind.HIGH, 120.0)
    assert strict.bms.value.breakout_index == 8

    cross_level_pullback = MediumTermPoint(
        short_point(6, IsolatedPointKind.LOW, 105.0),
        short_point(7, IsolatedPointKind.LOW, 105.0),
    )
    cross_level = StructuralHierarchy(
        source.isolated,
        ShortTermStructure(points[:-1], points[:-1], ()),
        MediumTermStructure(
            (cross_level_pullback,), (), (cross_level_pullback,), ()
        ),
        LongTermStructure((), (), (), ()),
    )
    invalid = evaluate_selected_segment(
        closed_window({7: (120.0, 104.0)}, count=8), cross_level, request
    )
    assert invalid.bms is not None
    assert invalid.bms.status is EvaluationStatus.INVALID
    assert invalid.bms.reason is EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX


def test_e_medium_selection_uses_only_competing_medium_vertices() -> None:
    """Test E catches ignored levels and same-level nonvertex boundaries."""

    short_vertices = (
        short_point(0, IsolatedPointKind.HIGH, 100.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(2, IsolatedPointKind.HIGH, 99.0),
        short_point(3, IsolatedPointKind.LOW, 95.0),
        short_point(4, IsolatedPointKind.HIGH, 101.0),
    )
    medium_vertices = (
        medium_point(0, IsolatedPointKind.HIGH, 200.0),
        medium_point(1, IsolatedPointKind.LOW, 180.0),
        medium_point(2, IsolatedPointKind.HIGH, 220.0),
        medium_point(3, IsolatedPointKind.LOW, 190.0),
        medium_point(4, IsolatedPointKind.HIGH, 240.0),
    )
    nonvertex_pullback = medium_point(6, IsolatedPointKind.LOW, 205.0)
    hierarchy = StructuralHierarchy(
        IsolatedPointScan((), None),
        ShortTermStructure(short_vertices, short_vertices, ()),
        MediumTermStructure(
            medium_vertices + (nonvertex_pullback,),
            (),
            medium_vertices,
            (
                SuppressedMediumTermPoint(
                    nonvertex_pullback,
                    MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND,
                ),
            ),
        ),
        LongTermStructure((), (), (), ()),
    )
    selected_window = closed_window({}, count=8)
    medium_result = evaluate_selected_segment(
        selected_window,
        hierarchy,
        SegmentAnalysisRequest(MarketSegment(0, 4), StructuralLevel.MEDIUM),
    )
    short_result = evaluate_selected_segment(
        selected_window,
        hierarchy,
        SegmentAnalysisRequest(MarketSegment(0, 4), StructuralLevel.SHORT),
    )

    assert medium_result.market_state.value is MarketState.UPTREND
    assert short_result.market_state.value is MarketState.NON_TREND
    assert [item.point.index for item in medium_result.selected_points] == [0, 1, 2, 3, 4]
    assert [item.point.price for item in medium_result.selected_points] == [200, 180, 220, 190, 240]
    assert all(item.level is StructuralLevel.MEDIUM for item in medium_result.selected_points)
    assert all(
        item.source_vertex is source_vertex
        for item, source_vertex in zip(medium_result.selected_points, medium_vertices)
    )
    assert all(
        not any(item.source_vertex is short_vertex for short_vertex in short_vertices)
        for item in medium_result.selected_points
    )

    rejected_boundary = evaluate_selected_segment(
        selected_window,
        hierarchy,
        SegmentAnalysisRequest(
            MarketSegment(0, 4),
            StructuralLevel.MEDIUM,
            bms=BMSAnalysisRequest(3, 4, 6),
        ),
    )
    assert rejected_boundary.bms is not None
    assert rejected_boundary.bms.status is EvaluationStatus.INVALID
    assert rejected_boundary.bms.reason is EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX


def test_e_sms_preserves_touch_first_event_and_dual_crossing_ambiguity() -> None:
    """Test E catches altered SMS strict/touch/first-event/ambiguity behavior."""

    source = hand_built_hierarchy(
        short_point(0, IsolatedPointKind.HIGH, 100.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
        short_point(3, IsolatedPointKind.LOW, 95.0),
        short_point(4, IsolatedPointKind.HIGH, 120.0),
    )
    request = SegmentAnalysisRequest(
        MarketSegment(0, 4),
        StructuralLevel.SHORT,
        sms=SMSAnalysisRequest(4, 3),
    )

    touch = evaluate_selected_segment(
        closed_window({5: (120.0, 95.0)}, count=6), source, request
    )
    assert touch.sms is not None
    assert touch.sms.status is EvaluationStatus.AVAILABLE
    assert touch.sms.value is not None
    assert touch.sms.value.status is SMSStructureStatus.PULLBACK_ONLY

    first_event = evaluate_selected_segment(
        closed_window({5: (120.0, 95.0), 6: (120.0, 94.0), 7: (121.0, 94.0)}, count=8),
        source,
        request,
    )
    assert first_event.sms is not None
    assert first_event.sms.value is not None
    assert first_event.sms.value.status is SMSStructureStatus.SMS_CONFIRMED
    assert first_event.sms.value.broken_point == StructurePoint(3, StructurePointKind.LOW, 95.0)
    assert first_event.sms.value.event_index == 6

    ambiguous = evaluate_selected_segment(
        closed_window({5: (121.0, 94.0)}, count=6), source, request
    )
    assert ambiguous.sms is not None
    assert ambiguous.sms.status is EvaluationStatus.INVALID
    assert ambiguous.sms.reason is EvaluationReason.OHLC_INTRABAR_ORDER_AMBIGUOUS
    assert ambiguous.sms.message == "OHLC cannot determine the intrabar boundary order"
