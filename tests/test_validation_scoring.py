"""Contract tests for deterministic, source-bound validation scoring."""

import importlib.util
from dataclasses import replace
from datetime import UTC, datetime
from importlib import import_module

import pytest

from trading.analysis.candles import analyze_closed_candle
from trading.analysis.hierarchy import StructuralHierarchy
from trading.analysis.isolated import IsolatedPointScan
from trading.analysis.models import (
    ClosedCandleObservation,
    Evaluation,
    EvaluationReason,
    EvaluationStatus,
    BMSAnalysisRequest,
    OfflineMarketWindow,
    SMSAnalysisRequest,
    SegmentAnalysisRequest,
    SegmentAnalysisResult,
    StructuralLevel,
)
from trading.analysis.offline import OfflineMarketAnalysis
from trading.definitions.candles import CandleSide
from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from trading.definitions.isolated_points import IsolatedPoint, IsolatedPointKind, IsolatedPointStatus
from trading.definitions.market_structure import MarketSegment, MarketState, StructurePoint, StructurePointKind
from trading.definitions.medium_term_structure import (
    MediumTermPoint,
    MediumTermStructure,
    PotentialMediumTermPoint,
    MediumTermSuppressionReason,
    SuppressedMediumTermPoint,
)
from trading.definitions.short_term_structure import ShortTermPoint, ShortTermStructure
from trading.definitions.long_term_structure import (
    LongTermPoint,
    LongTermStructure,
    PotentialLongTermPoint,
    LongTermSuppressionReason,
    SuppressedLongTermPoint,
)
from trading.definitions.pullback_structure import BMSResult, PullbackStructureStatus
from trading.definitions.sms_structure import SMSResult, SMSStructureStatus
from trading.validation.ground_truth import (
    ExpectedBMS,
    ExpectedChapter1Candle,
    ExpectedControl,
    ExpectedGeometry,
    ExpectedMarketState,
    ExpectedPotential,
    ExpectedPoint,
    ExpectedSegment,
    ExpectedSMS,
    ExpectedSuppression,
    ExpectedStructure,
    GroundTruthAmbiguity,
    GroundTruthCase,
    GroundTruthSource,
)
from trading.validation.scoring import (
    DiscrepancyClass,
    report_engine_failure,
    score_analysis,
)

def test_validation_scoring_module_is_discoverable() -> None:
    """A missing scorer must be caught before its public contract is tested."""

    assert importlib.util.find_spec("trading.validation.scoring") is not None


def test_scoring_module_exposes_locked_public_names() -> None:
    module = import_module("trading.validation.scoring")
    missing = [
        name
        for name in (
            "DiscrepancyClass",
            "DetectionMetrics",
            "LayerScore",
            "ValidationReport",
            "score_analysis",
            "report_engine_failure",
        )
        if not hasattr(module, name)
    ]
    assert missing == []


def _point(index: int, kind: IsolatedPointKind, price: float) -> ExpectedPoint:
    return ExpectedPoint(index, kind, price, IsolatedPointBasis.STRICT)


def _analysis(
    points: tuple[ExpectedPoint, ...],
    *,
    segment: SegmentAnalysisResult | None = None,
    short_points: tuple[ExpectedPoint, ...] | None = None,
) -> OfflineMarketAnalysis:
    observation = ClosedCandleObservation(
        datetime(2026, 1, 1, tzinfo=UTC), 10.0, 12.0, 9.0, 11.0
    )
    candle = analyze_closed_candle(observation, index=0)
    recognitions = tuple(
        IsolatedPointRecognition(
            IsolatedPoint(point.index, point.kind, IsolatedPointStatus.CONFIRMED, point.price),
            point.recognition_basis,
        )
        for point in points
    )
    source_points = points if short_points is None else short_points
    native_short_points = tuple(
        ShortTermPoint(point.index, point.kind, point.price, point.recognition_basis)
        for point in source_points
    )
    hierarchy = StructuralHierarchy(
        IsolatedPointScan(recognitions, None),
        ShortTermStructure(native_short_points, native_short_points, ()),
        MediumTermStructure((), (), (), ()),
        LongTermStructure((), (), (), ()),
    )
    return OfflineMarketAnalysis(
        OfflineMarketWindow("fixture", "1m", 0, (observation,)),
        (candle,),
        hierarchy,
        segment,
    )


def _expected(
    points: tuple[ExpectedPoint, ...],
    *,
    chapter1: tuple[ExpectedChapter1Candle, ...] = (),
    segment: ExpectedSegment | None = None,
    ambiguities: tuple[GroundTruthAmbiguity, ...] = (),
) -> GroundTruthCase:
    short = ExpectedStructure(points, (), points, ())
    empty = ExpectedStructure((), (), (), ())
    return GroundTruthCase(
        1,
        "scoring-fixture",
        GroundTruthSource("fixture.csv", "source-hash", "fixture", "1m", 0, 1),
        chapter1,
        points,
        short,
        empty,
        empty,
        segment,
        ambiguities,
    )


def _expected_candle() -> ExpectedChapter1Candle:
    return ExpectedChapter1Candle(
        0,
        CandleSide.BULLISH,
        ExpectedGeometry(1 / 3, 1 / 3, 1 / 3, 1 / 3, 2 / 3),
        ExpectedControl(2.0, 1.0, 2 / 3, 1 / 3, 1 / 3),
        EvaluationStatus.UNAVAILABLE,
        EvaluationReason.INTRABAR_DATA_UNAVAILABLE,
        None,
        None,
        None,
        None,
        None,
        EvaluationStatus.UNAVAILABLE,
        EvaluationReason.CANDLE_TYPE_UNCALIBRATED,
    )


def test_scores_perfect_ordered_analysis_with_exact_detection_metrics() -> None:
    points = (
        _point(1, IsolatedPointKind.HIGH, 110.0),
        _point(2, IsolatedPointKind.LOW, 90.0),
        _point(3, IsolatedPointKind.HIGH, 120.0),
    )

    report = score_analysis(_analysis(points), _expected(points, chapter1=(_expected_candle(),)))

    assert report.case_id == "scoring-fixture"
    assert report.source_sha256 == "source-hash"
    assert report.chapter1.exact_match is True
    assert report.isolated.exact_match is True
    assert report.short_term.exact_match is True
    assert report.medium_term.exact_match is True
    assert report.long_term.exact_match is True
    assert report.isolated_metrics.true_positives == 3
    assert report.isolated_metrics.false_positives == 0
    assert report.isolated_metrics.false_negatives == 0
    assert report.isolated_metrics.precision == 1.0
    assert report.isolated_metrics.recall == 1.0
    assert report.isolated_metrics.f1 == 1.0
    assert report.outcomes == ()


def test_detection_metrics_treat_missing_extra_and_identity_mismatch_as_fp_and_fn() -> None:
    expected_points = (
        _point(1, IsolatedPointKind.HIGH, 110.0),
        _point(2, IsolatedPointKind.LOW, 90.0),
    )
    actual_points = (
        _point(1, IsolatedPointKind.HIGH, 110.0),
        _point(3, IsolatedPointKind.HIGH, 120.0),
    )

    report = score_analysis(_analysis(actual_points), _expected(expected_points))

    assert (report.isolated_metrics.true_positives, report.isolated_metrics.false_positives, report.isolated_metrics.false_negatives) == (1, 1, 1)
    assert report.isolated_metrics.precision == 0.5
    assert report.isolated_metrics.recall == 0.5
    assert report.isolated_metrics.f1 == 0.5
    assert report.isolated.exact_match is False


def test_price_tolerance_is_explicit_nonnegative_and_never_relaxes_point_identity() -> None:
    expected_points = (_point(1, IsolatedPointKind.HIGH, 110.0),)
    actual_points = (_point(1, IsolatedPointKind.HIGH, 110.25),)

    exact = score_analysis(_analysis(actual_points), _expected(expected_points))
    tolerant = score_analysis(_analysis(actual_points), _expected(expected_points), price_tolerance=0.25)
    wrong_index = score_analysis(_analysis((_point(2, IsolatedPointKind.HIGH, 110.0),)), _expected(expected_points), price_tolerance=1.0)

    assert (exact.isolated_metrics.false_positives, exact.isolated_metrics.false_negatives) == (1, 1)
    assert tolerant.isolated_metrics.true_positives == 1
    assert wrong_index.isolated_metrics.true_positives == 0
    with pytest.raises(ValueError, match="non-negative"):
        score_analysis(_analysis(expected_points), _expected(expected_points), price_tolerance=-0.01)


def test_empty_detection_denominators_have_documented_deterministic_semantics() -> None:
    empty = _expected(())
    both_empty = score_analysis(_analysis(()), empty)
    extra = score_analysis(_analysis((_point(1, IsolatedPointKind.HIGH, 110.0),)), empty)
    missing = score_analysis(_analysis(()), _expected((_point(1, IsolatedPointKind.HIGH, 110.0),)))

    assert (both_empty.isolated_metrics.precision, both_empty.isolated_metrics.recall, both_empty.isolated_metrics.f1) == (1.0, 1.0, 1.0)
    assert extra.isolated_metrics.precision == 0.0
    assert missing.isolated_metrics.recall == 0.0


def test_compares_chapter1_capabilities_structure_order_and_segment_statuses() -> None:
    points = (_point(1, IsolatedPointKind.HIGH, 110.0),)
    request = SegmentAnalysisRequest(MarketSegment(0, 0), StructuralLevel.SHORT)
    actual_segment = SegmentAnalysisResult(
        request,
        (),
        Evaluation(EvaluationStatus.AVAILABLE, value=MarketState.UPTREND),
        None,
        None,
    )
    expected_segment = ExpectedSegment(
        0,
        0,
        StructuralLevel.SHORT,
        ExpectedMarketState(EvaluationStatus.AVAILABLE, None, MarketState.UPTREND),
        None,
        None,
        None,
        None,
    )
    expected = _expected(points, chapter1=(_expected_candle(),), segment=expected_segment)

    report = score_analysis(_analysis(points, segment=actual_segment), expected)
    changed_capability = score_analysis(
        _analysis(points, segment=actual_segment),
        replace(expected, chapter1=(replace(_expected_candle(), intrabar_reason=EvaluationReason.INVALID_CONTEXT),)),
    )
    changed_segment = score_analysis(
        _analysis(points, segment=actual_segment),
        replace(expected, segment=replace(expected_segment, market_state=ExpectedMarketState(EvaluationStatus.UNAVAILABLE, EvaluationReason.INSUFFICIENT_STRUCTURE, None))),
    )

    assert report.segment is not None and report.segment.exact_match is True
    assert changed_capability.chapter1.exact_match is False
    assert "chapter1[0].intrabar_reason" in changed_capability.chapter1.discrepancies
    assert changed_segment.segment is not None and changed_segment.segment.exact_match is False
    assert "segment.market_state.status" in changed_segment.segment.discrepancies


def test_chapter1_reversed_expected_sequence_is_a_disagreement() -> None:
    observation = ClosedCandleObservation(
        datetime(2026, 1, 1, tzinfo=UTC), 10.0, 12.0, 9.0, 11.0
    )
    later = replace(observation, timestamp=datetime(2026, 1, 2, tzinfo=UTC))
    analysis = _analysis(())
    analysis = replace(
        analysis,
        window=OfflineMarketWindow("fixture", "1m", 0, (observation, later)),
        candles=(
            analyze_closed_candle(observation, index=0),
            analyze_closed_candle(later, index=1),
        ),
    )
    expected = _expected(
        (),
        chapter1=(replace(_expected_candle(), index=1), _expected_candle()),
    )

    report = score_analysis(analysis, expected)

    assert report.chapter1.exact_match is False
    assert "chapter1[0].index" in report.chapter1.discrepancies
    assert DiscrepancyClass.GROUND_TRUTH_DISAGREEMENT in report.outcomes


def test_chapter1_sparse_expectations_keep_only_declared_actual_indexes_in_order() -> None:
    observation = ClosedCandleObservation(
        datetime(2026, 1, 1, tzinfo=UTC), 10.0, 12.0, 9.0, 11.0
    )
    later = replace(observation, timestamp=datetime(2026, 1, 2, tzinfo=UTC))
    analysis = replace(
        _analysis(()),
        window=OfflineMarketWindow("fixture", "1m", 0, (observation, later)),
        candles=(
            analyze_closed_candle(observation, index=0),
            analyze_closed_candle(later, index=1),
        ),
    )

    report = score_analysis(
        analysis,
        _expected((), chapter1=(replace(_expected_candle(), index=1),)),
    )

    assert report.chapter1.exact_match is True
    assert report.chapter1.discrepancies == ()


def test_compares_medium_long_provenance_potentials_suppressions_and_bms_sms_details() -> None:
    short_a = ShortTermPoint(1, IsolatedPointKind.HIGH, 110.0)
    short_b = ShortTermPoint(3, IsolatedPointKind.HIGH, 120.0)
    short_c = ShortTermPoint(5, IsolatedPointKind.HIGH, 130.0)
    short_d = ShortTermPoint(7, IsolatedPointKind.HIGH, 140.0)
    medium = MediumTermPoint(short_a, short_b)
    medium_confirmer = MediumTermPoint(short_c, short_d)
    long = LongTermPoint(medium, medium_confirmer)
    hierarchy = StructuralHierarchy(
        IsolatedPointScan((), None),
        ShortTermStructure((), (), ()),
        MediumTermStructure(
            (medium,),
            (PotentialMediumTermPoint(short_a, short_c),),
            (medium,),
            (SuppressedMediumTermPoint(medium, MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND),),
        ),
        LongTermStructure(
            (long,),
            (PotentialLongTermPoint(medium, medium_confirmer),),
            (long,),
            (SuppressedLongTermPoint(long, LongTermSuppressionReason.CONSECUTIVE_SAME_KIND),),
        ),
    )
    request = SegmentAnalysisRequest(
        MarketSegment(0, 7),
        StructuralLevel.LONG,
        BMSAnalysisRequest(1, 3, 5),
        SMSAnalysisRequest(3, 1),
    )
    segment = SegmentAnalysisResult(
        request,
        (),
        Evaluation(EvaluationStatus.AVAILABLE, value=MarketState.UPTREND),
        Evaluation(
            EvaluationStatus.AVAILABLE,
            value=BMSResult(
                PullbackStructureStatus.BMS_CONFIRMED,
                StructurePoint(3, StructurePointKind.HIGH, 120.0),
                8,
            ),
        ),
        Evaluation(
            EvaluationStatus.AVAILABLE,
            value=SMSResult(
                SMSStructureStatus.SMS_CONFIRMED,
                StructurePoint(1, StructurePointKind.LOW, 100.0),
                9,
            ),
        ),
    )
    point = ExpectedPoint(1, IsolatedPointKind.HIGH, 110.0, None, 3)
    expected_medium = ExpectedStructure(
        (point,),
        (ExpectedPotential(1, 5, IsolatedPointKind.HIGH, 130.0),),
        (point,),
        (ExpectedSuppression(point, MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND),),
    )
    expected_long_point = ExpectedPoint(1, IsolatedPointKind.HIGH, 110.0, None, 5)
    expected_long = ExpectedStructure(
        (expected_long_point,),
        (ExpectedPotential(1, 5, IsolatedPointKind.HIGH, 130.0),),
        (expected_long_point,),
        (ExpectedSuppression(expected_long_point, LongTermSuppressionReason.CONSECUTIVE_SAME_KIND),),
    )
    expected_segment = ExpectedSegment(
        0,
        7,
        StructuralLevel.LONG,
        ExpectedMarketState(EvaluationStatus.AVAILABLE, None, MarketState.UPTREND),
        BMSAnalysisRequest(1, 3, 5),
        ExpectedBMS(EvaluationStatus.AVAILABLE, None, PullbackStructureStatus.BMS_CONFIRMED, 3, 8),
        SMSAnalysisRequest(3, 1),
        ExpectedSMS(EvaluationStatus.AVAILABLE, None, SMSStructureStatus.SMS_CONFIRMED, 1, 9),
    )
    expected = replace(_expected((), segment=expected_segment), medium_term=expected_medium, long_term=expected_long)
    analysis = replace(_analysis((), segment=segment), hierarchy=hierarchy)

    report = score_analysis(analysis, expected)
    wrong_provenance = score_analysis(
        analysis,
        replace(expected, medium_term=replace(expected_medium, vertices=(replace(point, confirmed_by_index=4),))),
    )
    wrong_sms = score_analysis(
        analysis,
        replace(expected, segment=replace(expected_segment, sms=replace(expected_segment.sms, event_index=10))),  # type: ignore[arg-type]
    )

    assert report.medium_term.exact_match is True
    assert report.long_term.exact_match is True
    assert report.segment is not None and report.segment.exact_match is True
    assert "medium_term.vertices[0].confirmed_by_index" in wrong_provenance.medium_term.discrepancies
    assert wrong_sms.segment is not None
    assert "segment.sms.event_index" in wrong_sms.segment.discrepancies


def test_predeclared_exact_ambiguity_is_separate_and_excluded_but_unrelated_difference_is_not() -> None:
    expected_points = (_point(1, IsolatedPointKind.HIGH, 110.0),)
    actual_points = (_point(1, IsolatedPointKind.HIGH, 111.0),)
    item = "index:1|kind:high|price:110.0|recognition_basis:strict"
    expected = _expected(
        expected_points,
        ambiguities=(GroundTruthAmbiguity("isolated", item, "declared before scoring"),),
    )

    ambiguous = score_analysis(_analysis(actual_points, short_points=expected_points), expected)
    unrelated = score_analysis(_analysis((_point(2, IsolatedPointKind.HIGH, 111.0),)), expected)

    assert ambiguous.outcomes == (DiscrepancyClass.COURSE_AMBIGUITY,)
    assert (ambiguous.isolated_metrics.true_positives, ambiguous.isolated_metrics.false_positives, ambiguous.isolated_metrics.false_negatives) == (0, 0, 0)
    assert DiscrepancyClass.GROUND_TRUTH_DISAGREEMENT in unrelated.outcomes


def test_isolated_reordering_remains_a_disagreement_when_one_identity_is_ambiguous() -> None:
    first = _point(1, IsolatedPointKind.HIGH, 110.0)
    second = _point(2, IsolatedPointKind.LOW, 90.0)
    expected = _expected(
        (first, second),
        ambiguities=(
            GroundTruthAmbiguity(
                "isolated",
                "index:1|kind:high|price:110.0|recognition_basis:strict",
                "declared before scoring",
            ),
        ),
    )

    report = score_analysis(
        _analysis((second, first), short_points=(first, second)),
        expected,
    )

    assert report.isolated.exact_match is False
    assert "isolated[0].index" in report.isolated.discrepancies
    assert DiscrepancyClass.GROUND_TRUTH_DISAGREEMENT in report.outcomes


def test_engine_failure_is_explicit_and_does_not_claim_layer_matches() -> None:
    report = report_engine_failure(_expected(()), RuntimeError("analyzer crashed"))

    assert report.case_id == "scoring-fixture"
    assert report.source_sha256 == "source-hash"
    assert report.outcomes == (DiscrepancyClass.ENGINE_FAILURE,)
    assert report.chapter1.exact_match is False
    assert report.isolated.exact_match is False
    assert "RuntimeError: analyzer crashed" in report.chapter1.discrepancies[0]
