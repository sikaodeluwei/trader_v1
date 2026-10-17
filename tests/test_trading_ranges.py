"""Synthetic checks of externally annotated Lesson 1 formation evidence."""

from dataclasses import replace

import pytest

from trading.definitions.key_levels import KeyLevelKind
from trading.definitions.market_structure import (
    MarketSegment, MarketState, StructurePoint, StructurePointKind,
    classify_market_state,
)
from trading.definitions.trading_ranges import (
    BoundaryAnchor, RangeBoundary, BoundaryObservation, BoundaryOutcome,
    TradingRangeContext, TradingRangeType, RangeFormationStatus,
    evaluate_range_formation,
)


UPPER = KeyLevelKind.RESISTANCE
LOWER = KeyLevelKind.SUPPORT
FAILED = BoundaryOutcome.UNSUCCESSFUL_ATTEMPT
REACTION = BoundaryOutcome.REACTION


def context(observations=(), kind=TradingRangeType.ORDINARY):
    return TradingRangeContext(
        segment=MarketSegment(0, 9),
        range_type=kind,
        upper=RangeBoundary(UPPER, (BoundaryAnchor(0, 110),)),
        lower=RangeBoundary(LOWER, (BoundaryAnchor(0, 100),)),
        observations=observations,
    )


@pytest.mark.parametrize(('observations', 'expected'), [
    ((), RangeFormationStatus.INSUFFICIENT_EVIDENCE),
    ((BoundaryObservation(1, UPPER, REACTION),
      BoundaryObservation(2, LOWER, REACTION)),
     RangeFormationStatus.INSUFFICIENT_EVIDENCE),
    ((BoundaryObservation(1, UPPER, REACTION),
      BoundaryObservation(2, LOWER, REACTION),
      BoundaryObservation(3, UPPER, REACTION)), RangeFormationStatus.POTENTIAL),
    ((BoundaryObservation(1, UPPER, FAILED),
      BoundaryObservation(2, LOWER, FAILED),
      BoundaryObservation(3, UPPER, FAILED),
      BoundaryObservation(4, LOWER, FAILED)), RangeFormationStatus.CONFIRMED),
    ((BoundaryObservation(1, UPPER, FAILED),
      BoundaryObservation(2, LOWER, FAILED),
      BoundaryObservation(3, UPPER, FAILED),
      BoundaryObservation(4, UPPER, FAILED)), RangeFormationStatus.POTENTIAL),
])
def test_counts_explicit_reactions_and_requires_two_failures_on_each_side(
    observations, expected,
):
    assert evaluate_range_formation(context(observations)).status is expected


@pytest.mark.parametrize('side', [UPPER, LOWER])
@pytest.mark.parametrize('outcome', [REACTION, FAILED])
def test_three_same_side_reactions_are_insufficient(side, outcome):
    observations = tuple(BoundaryObservation(i, side, outcome) for i in (1, 2, 3))
    result = evaluate_range_formation(context(observations))
    assert result.reaction_count == 3
    assert result.status is RangeFormationStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize('sides', [
    (UPPER, LOWER, UPPER),
    (LOWER, UPPER, LOWER),
    (UPPER, UPPER, LOWER),
    (LOWER, LOWER, UPPER),
])
def test_mixed_side_potential_evidence_does_not_require_alternation(sides):
    observations = tuple(BoundaryObservation(i, side, REACTION)
                         for i, side in enumerate(sides, start=1))
    result = evaluate_range_formation(context(observations))
    assert result.status is RangeFormationStatus.POTENTIAL
    assert result.unsuccessful_upward_attempts == 0
    assert result.unsuccessful_downward_attempts == 0


@pytest.mark.parametrize('reaction_side,touch_side', [(UPPER, LOWER), (LOWER, UPPER)])
def test_touch_on_other_side_cannot_supply_missing_reaction_evidence(reaction_side, touch_side):
    observations = tuple(BoundaryObservation(i, reaction_side, REACTION) for i in (1, 2, 3))
    observations += (BoundaryObservation(4, touch_side, BoundaryOutcome.TOUCH),)
    assert evaluate_range_formation(context(observations)).status is RangeFormationStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize('outcome,status,downward_count', [
    (BoundaryOutcome.TOUCH, RangeFormationStatus.POTENTIAL, 1),
    (REACTION, RangeFormationStatus.POTENTIAL, 1),
    (FAILED, RangeFormationStatus.CONFIRMED, 2),
])
def test_only_explicit_unsuccessful_attempt_supplies_confirmation(outcome, status, downward_count):
    observations = (
        BoundaryObservation(1, UPPER, FAILED),
        BoundaryObservation(2, LOWER, FAILED),
        BoundaryObservation(3, UPPER, FAILED),
        BoundaryObservation(4, LOWER, outcome),
    )
    result = evaluate_range_formation(context(observations))
    assert result.status is status
    assert result.unsuccessful_downward_attempts == downward_count


@pytest.mark.parametrize('anchor_index,observations', [
    (9, ()),
    (0, (BoundaryObservation(4, UPPER, FAILED),)),
])
def test_annotation_cannot_be_known_before_its_anchor_or_failed_attempt_evidence(
    anchor_index, observations,
):
    upper = RangeBoundary(UPPER, (BoundaryAnchor(anchor_index, 110),))
    with pytest.raises(ValueError, match='known_at_index'):
        replace(context(observations), upper=upper, known_at_index=3)


def test_late_boundary_selection_is_not_backdated_to_early_anchors_or_reactions():
    observations = (
        BoundaryObservation(1, UPPER, REACTION),
        BoundaryObservation(2, LOWER, REACTION),
        BoundaryObservation(3, UPPER, REACTION),
    )
    # Selection may be retrospective, after the analyzed segment ends.
    supplied = replace(context(observations), known_at_index=12)
    result = evaluate_range_formation(supplied)
    assert result.status is RangeFormationStatus.POTENTIAL
    assert result.context.known_at_index == 12


def test_annotation_can_be_known_at_its_latest_anchor_index():
    upper = RangeBoundary(UPPER, (BoundaryAnchor(9, 110),))
    supplied = replace(context(), upper=upper, known_at_index=9)
    assert evaluate_range_formation(supplied).status is RangeFormationStatus.INSUFFICIENT_EVIDENCE


def test_undated_annotation_does_not_infer_historical_availability():
    observations = tuple(BoundaryObservation(i, side, FAILED)
                         for i, side in enumerate((UPPER, LOWER, UPPER, LOWER), start=1))
    result = evaluate_range_formation(context(observations))
    assert result.status is RangeFormationStatus.CONFIRMED
    assert result.context.known_at_index is None


@pytest.mark.parametrize('known_at_index', [1.5, float('nan'), '9', True])
def test_annotation_knowledge_time_requires_an_integer_index(known_at_index):
    with pytest.raises(ValueError, match='known_at_index'):
        replace(context(), known_at_index=known_at_index)


@pytest.mark.parametrize('outcome', [
    BoundaryOutcome.TOUCH, BoundaryOutcome.UNRESOLVED,
])
def test_touches_and_unknown_outcomes_do_not_supply_reactions_or_failures(outcome):
    observations = tuple(BoundaryObservation(i, side, outcome)
                         for i, side in enumerate((UPPER, LOWER, UPPER, LOWER)))
    result = evaluate_range_formation(context(observations))
    assert result.status is RangeFormationStatus.INSUFFICIENT_EVIDENCE
    assert result.reaction_count == 0
    assert result.unsuccessful_upward_attempts == 0
    assert result.unsuccessful_downward_attempts == 0


def test_unresolved_fourth_attempt_cannot_confirm_a_potential_range():
    observations = (
        BoundaryObservation(1, UPPER, FAILED),
        BoundaryObservation(2, LOWER, FAILED),
        BoundaryObservation(3, UPPER, FAILED),
        BoundaryObservation(4, LOWER, BoundaryOutcome.UNRESOLVED),
    )
    assert evaluate_range_formation(context(observations)).status is RangeFormationStatus.POTENTIAL


def test_reports_known_evidence_without_treating_a_later_unknown_as_failure():
    observations = (
        BoundaryObservation(1, UPPER, FAILED),
        BoundaryObservation(2, LOWER, FAILED),
        BoundaryObservation(3, UPPER, FAILED),
        BoundaryObservation(4, LOWER, FAILED),
        BoundaryObservation(5, UPPER, BoundaryOutcome.UNRESOLVED),
    )
    result = evaluate_range_formation(context(observations))
    assert result.status is RangeFormationStatus.CONFIRMED
    assert result.reaction_count == 4
    assert result.unsuccessful_upward_attempts == 2
    assert result.unsuccessful_downward_attempts == 2
    assert result.context.observations[-1].outcome is BoundaryOutcome.UNRESOLVED


@pytest.mark.parametrize('kind', [TradingRangeType.SLOPING, TradingRangeType.NARROW])
def test_ordinary_confirmation_rule_is_not_extended_to_other_type_labels(kind):
    observations = tuple(BoundaryObservation(i, side, FAILED)
                         for i, side in enumerate((UPPER, LOWER, UPPER, LOWER)))
    result = evaluate_range_formation(context(observations, kind))
    assert result.status is RangeFormationStatus.POTENTIAL
    assert result.context.range_type is kind


def test_evaluation_preserves_external_annotations_and_supports_sloping_anchors():
    supplied = TradingRangeContext(
        MarketSegment(0, 9), TradingRangeType.SLOPING,
        RangeBoundary(UPPER, (BoundaryAnchor(0, 110), BoundaryAnchor(9, 115))),
        RangeBoundary(LOWER, (BoundaryAnchor(0, 100), BoundaryAnchor(9, 105))),
        [BoundaryObservation(3, UPPER, BoundaryOutcome.UNRESOLVED)],
    )
    result = evaluate_range_formation(supplied)
    assert result.context is supplied
    assert result.context.upper.anchors[1].price == 115
    assert result.context.observations[0].outcome is BoundaryOutcome.UNRESOLVED


def test_successful_attempt_requires_later_lesson_lifecycle_rules():
    observations = tuple(BoundaryObservation(i, side, FAILED)
                         for i, side in enumerate((UPPER, LOWER, UPPER, LOWER)))
    observations += (BoundaryObservation(5, UPPER, BoundaryOutcome.SUCCESSFUL_ATTEMPT),)
    assert evaluate_range_formation(context(observations)).status is RangeFormationStatus.UNRESOLVED


def test_chapter2_nontrend_does_not_establish_a_trading_range():
    segment = MarketSegment(0, 9)
    points = (StructurePoint(1, StructurePointKind.HIGH, 110),
              StructurePoint(2, StructurePointKind.LOW, 100),
              StructurePoint(3, StructurePointKind.HIGH, 110),
              StructurePoint(4, StructurePointKind.LOW, 100))
    assert classify_market_state(segment, points) is MarketState.NON_TREND
    assert evaluate_range_formation(context()).status is RangeFormationStatus.INSUFFICIENT_EVIDENCE
    assert classify_market_state(segment, points) is MarketState.NON_TREND


@pytest.mark.parametrize('observations', [
    (BoundaryObservation(2, UPPER, FAILED), BoundaryObservation(1, LOWER, FAILED)),
    (BoundaryObservation(1, UPPER, FAILED), BoundaryObservation(1, UPPER, FAILED)),
    (BoundaryObservation(10, UPPER, FAILED),),
    (BoundaryObservation(1, UPPER, FAILED), BoundaryObservation(1, LOWER, FAILED)),
])
def test_rejects_unsorted_duplicate_outside_or_same_candle_ambiguous_events(observations):
    with pytest.raises(ValueError):
        context(observations)


@pytest.mark.parametrize('upper,lower', [
    (RangeBoundary(LOWER, (BoundaryAnchor(0, 110),)), RangeBoundary(LOWER, (BoundaryAnchor(0, 100),))),
    (RangeBoundary(UPPER, (BoundaryAnchor(0, 100),)), RangeBoundary(LOWER, (BoundaryAnchor(0, 100),))),
    (RangeBoundary(UPPER, (BoundaryAnchor(0, 90),)), RangeBoundary(LOWER, (BoundaryAnchor(0, 100),))),
    (RangeBoundary(UPPER, (BoundaryAnchor(10, 110),)), RangeBoundary(LOWER, (BoundaryAnchor(0, 100),))),
])
def test_rejects_invalid_boundary_roles_order_or_segment(upper, lower):
    with pytest.raises(ValueError):
        TradingRangeContext(MarketSegment(0, 9), TradingRangeType.ORDINARY, upper, lower)


@pytest.mark.parametrize('anchors', [(), (BoundaryAnchor(1, 110), BoundaryAnchor(0, 110))])
def test_rejects_missing_or_unsorted_anchors(anchors):
    with pytest.raises(ValueError):
        RangeBoundary(UPPER, anchors)


@pytest.mark.parametrize('price', [float('nan'), float('inf'), -float('inf')])
def test_rejects_nonfinite_boundary_prices(price):
    with pytest.raises(ValueError):
        BoundaryAnchor(0, price)


def test_ordinary_label_rejects_nonhorizontal_boundary_anchors():
    with pytest.raises(ValueError):
        TradingRangeContext(
            MarketSegment(0, 9), TradingRangeType.ORDINARY,
            RangeBoundary(UPPER, (BoundaryAnchor(0, 110), BoundaryAnchor(9, 115))),
            RangeBoundary(LOWER, (BoundaryAnchor(0, 100),)),
        )
