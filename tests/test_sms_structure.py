from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.candles import Candle
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
)
from trading.definitions.sms_structure import (
    SMSContext,
    SMSObservation,
    SMSResult,
    SMSStructureStatus,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def uptrend_context(
    *,
    segment: MarketSegment = MarketSegment(0, 3),
    extreme: StructurePoint = high(3, 110.0),
    creator: StructurePoint = low(2, 95.0),
) -> SMSContext:
    return SMSContext(
        parent_segment=segment,
        parent_state=MarketState.UPTREND,
        trend_extreme=extreme,
        creator_point=creator,
    )


def downtrend_context(
    *,
    segment: MarketSegment = MarketSegment(0, 3),
    extreme: StructurePoint = low(3, 90.0),
    creator: StructurePoint = high(2, 105.0),
) -> SMSContext:
    return SMSContext(
        parent_segment=segment,
        parent_state=MarketState.DOWNTREND,
        trend_extreme=extreme,
        creator_point=creator,
    )


def test_sms_status_values_are_stable() -> None:
    assert {status.value for status in SMSStructureStatus} == {
        "pending",
        "pullback_only",
        "sms_confirmed",
        "parent_continued",
    }


def test_valid_directional_contexts_preserve_explicit_boundaries() -> None:
    uptrend = uptrend_context()
    downtrend = downtrend_context()

    assert uptrend.creator_point == low(2, 95.0)
    assert uptrend.trend_extreme == high(3, 110.0)
    assert downtrend.creator_point == high(2, 105.0)
    assert downtrend.trend_extreme == low(3, 90.0)


def test_sms_domain_records_preserve_supplied_values() -> None:
    candle = Candle(100.0, 105.0, 95.0, 101.0)
    creator = low(2, 95.0)

    assert SMSObservation(4, candle) == SMSObservation(index=4, candle=candle)
    assert SMSResult(SMSStructureStatus.PENDING) == SMSResult(
        status=SMSStructureStatus.PENDING,
        broken_point=None,
        event_index=None,
    )
    assert SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        creator,
        4,
    ) == SMSResult(
        status=SMSStructureStatus.SMS_CONFIRMED,
        broken_point=creator,
        event_index=4,
    )


@pytest.mark.parametrize(
    ("instance", "attribute"),
    [
        (uptrend_context(), "parent_state"),
        (SMSObservation(4, Candle(100.0, 105.0, 95.0, 101.0)), "index"),
        (SMSResult(SMSStructureStatus.PENDING), "status"),
    ],
)
def test_sms_domain_records_are_frozen(
    instance: object,
    attribute: str,
) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, None)


def test_context_rejects_non_directional_parent_state() -> None:
    with pytest.raises(ValueError, match="directional"):
        SMSContext(
            MarketSegment(0, 3),
            MarketState.NON_TREND,
            high(3, 110.0),
            low(2, 95.0),
        )


@pytest.mark.parametrize(
    ("state", "extreme", "creator"),
    [
        (MarketState.UPTREND, low(3, 110.0), low(2, 95.0)),
        (MarketState.UPTREND, high(3, 110.0), high(2, 95.0)),
        (MarketState.DOWNTREND, high(3, 90.0), high(2, 105.0)),
        (MarketState.DOWNTREND, low(3, 90.0), low(2, 105.0)),
    ],
)
def test_context_rejects_wrong_directional_point_kinds(
    state: MarketState,
    extreme: StructurePoint,
    creator: StructurePoint,
) -> None:
    with pytest.raises(ValueError, match="point kinds"):
        SMSContext(MarketSegment(0, 3), state, extreme, creator)


@pytest.mark.parametrize(
    ("segment", "extreme", "creator"),
    [
        (MarketSegment(1, 3), high(3, 110.0), low(0, 95.0)),
        (MarketSegment(0, 2), high(3, 110.0), low(1, 95.0)),
    ],
)
def test_context_rejects_boundaries_outside_parent_segment(
    segment: MarketSegment,
    extreme: StructurePoint,
    creator: StructurePoint,
) -> None:
    with pytest.raises(ValueError, match="outside parent segment"):
        uptrend_context(segment=segment, extreme=extreme, creator=creator)


def test_context_requires_parent_segment_to_end_at_trend_extreme() -> None:
    with pytest.raises(ValueError, match="end at trend extreme"):
        uptrend_context(segment=MarketSegment(0, 4))


def test_context_rejects_invalid_boundary_chronology() -> None:
    with pytest.raises(ValueError, match="chronology"):
        uptrend_context(
            extreme=high(3, 110.0),
            creator=low(3, 95.0),
        )


@pytest.mark.parametrize(
    "context_factory",
    [
        lambda: uptrend_context(creator=low(2, 110.0)),
        lambda: uptrend_context(creator=low(2, 111.0)),
        lambda: downtrend_context(creator=high(2, 90.0)),
        lambda: downtrend_context(creator=high(2, 89.0)),
    ],
)
def test_context_rejects_incoherent_directional_prices(
    context_factory: object,
) -> None:
    with pytest.raises(ValueError, match="boundary prices"):
        context_factory()  # type: ignore[operator]


@pytest.mark.parametrize(
    "status",
    [SMSStructureStatus.SMS_CONFIRMED, SMSStructureStatus.PARENT_CONTINUED],
)
def test_terminal_result_requires_both_event_fields(
    status: SMSStructureStatus,
) -> None:
    with pytest.raises(ValueError, match="terminal SMS result requires"):
        SMSResult(status)

    with pytest.raises(ValueError, match="terminal SMS result requires"):
        SMSResult(status, broken_point=low(2, 95.0))

    with pytest.raises(ValueError, match="terminal SMS result requires"):
        SMSResult(status, event_index=4)


@pytest.mark.parametrize(
    "status",
    [SMSStructureStatus.PENDING, SMSStructureStatus.PULLBACK_ONLY],
)
def test_non_terminal_result_rejects_event_fields(
    status: SMSStructureStatus,
) -> None:
    with pytest.raises(ValueError, match="non-terminal SMS result"):
        SMSResult(
            status,
            broken_point=low(2, 95.0),
            event_index=4,
        )
