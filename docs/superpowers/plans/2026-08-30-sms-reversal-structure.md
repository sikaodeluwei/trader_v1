# SMS Reversal Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Chapter 2, Lesson 3 SMS evaluation for one explicitly established directional trend by resolving the first strict creator-point or parent-extreme break in a complete dense sequence of later OHLC candles.

**Architecture:** Add one focused `trading.definitions.sms_structure` module that consumes existing Lesson 1 market-structure types without reclassifying the parent trend and remains independent of the Lesson 2 BMS evaluator. Immutable records validate the explicit trend boundaries and result shape; a stateless `evaluate_sms()` function validates the entire ordered observation sequence before scanning it once for the first terminal event.

**Tech Stack:** Python standard library (`collections.abc.Sequence`, `dataclasses`, `enum`), pytest, existing `trading.definitions.candles.Candle`, and existing `trading.definitions.market_structure` domain types and `classify_market_state()`.

**Spec:** `docs/superpowers/specs/2026-08-30-sms-reversal-structure-design.md`

## Global Constraints

- Implement only Chapter 2, Lesson 3: Shift in Market Structure (SMS).
- SMS is a reversal structure relative to one defined trend; `SMS_CONFIRMED` is not confirmation of an actual reversal or an opposite trend.
- Add only `SMSContext`, `SMSStructureStatus`, `SMSObservation`, `SMSResult`, `evaluate_sms()`, focused Level 1 unit tests, and a small adjacent-layer integration smoke test.
- Reuse `Candle`, `MarketSegment`, `MarketState`, `StructurePoint`, `StructurePointKind`, and `classify_market_state()` from their existing modules; do not duplicate or modify their behavior.
- `SMSContext` receives an already-established directional `parent_state`; it must not accept the full parent point sequence or call `classify_market_state()`.
- Keep `trading/definitions/sms_structure.py` independent of `trading/definitions/pullback_structure.py`; do not call `evaluate_bms()` or reinterpret `BMSResult`.
- The caller explicitly supplies the exact parent segment, trend extreme, and creator point. Never infer, repair, reorder, synthesize, or automatically select them.
- Preserve context chronology exactly: `parent_segment.start_index <= creator_point.index < trend_extreme.index == parent_segment.end_index`.
- For `UPTREND`, require a `LOW` creator below a later `HIGH` trend extreme. For `DOWNTREND`, require a `HIGH` creator above a later `LOW` trend extreme. Reject `NON_TREND`.
- Indexes are dense ordinal candle positions in one ordered market series and timeframe. `index + 1` means the immediately following candle, not elapsed clock time or an arbitrary identifier.
- A non-empty observation sequence begins at `trend_extreme.index + 1` and advances by exactly one index per observation.
- Validate the complete observation sequence before evaluating terminal events so an early boundary break cannot hide omitted, repeated, decreasing, or gapped later input.
- Preserve caller observation order; never sort, repair, interpolate, discard, or synthesize observations.
- Empty observations yield `PENDING`; non-empty observations with no strict boundary break yield `PULLBACK_ONLY`.
- A strict creator-point wick break first yields `SMS_CONFIRMED`. A strict parent-extreme wick break first yields terminal `PARENT_CONTINUED` for the old context.
- Equality with either boundary is not a break. Candle close, body, and color are irrelevant; add no buffer, tolerance, penetration percentage, or confirmation candle.
- One OHLC candle strictly crossing both boundaries raises exactly `ValueError("OHLC cannot determine the intrabar boundary order")`.
- The first terminal event wins. Later recovery or continuation cannot erase a historical SMS, and later creator crossing cannot reactivate a context that already returned `PARENT_CONTINUED`.
- Terminal results contain the exact supplied broken `StructurePoint` and first event index. Non-terminal results contain neither event field.
- Repeated and differently scaled structures use separate explicit contexts; add no hierarchy fields, automatic propagation, registry, counter, or replacement-context construction.
- Do not add automatic swing/zig-zag extraction, structure-point extraction, isolated-point mapping, parent-trend detection, segment selection, extreme discovery, creator discovery, short/medium/long-term hierarchy, timeframe/cycle hierarchy, or trading-range logic.
- Do not add confirmed opposite-trend or actual-reversal semantics, BOS/CHOCH terminology, strategy, bias, signals, entries, exits, risk, position sizing, broker, order, or execution logic.
- Do not create `tests/test_course_market_structure_scenarios.py`. Formal Chapter 2 Level 2 validation remains deferred until every Chapter 2 lesson is complete; Level 3 raw-chart validation remains conditional on later course rules.
- Do not modify the approved SMS design spec or existing production modules unless implementation proves a genuine compatibility defect and the user separately approves that scope change.

## File Map

- Create `trading/definitions/sms_structure.py`: immutable Lesson 3 domain records, explicit context validation, dense observation validation, and chronological SMS/parent-continuation evaluation.
- Create `tests/test_sms_structure.py`: focused Level 1 domain, validation, chronology, boundary, ambiguity, historical, and independence tests.
- Create `tests/test_sms_structure_integration.py`: small smoke coverage composing `classify_market_state()` with the explicit SMS API.
- Keep `trading/definitions/market_structure.py` unchanged as the Lesson 1 source of truth.
- Keep `trading/definitions/pullback_structure.py` unchanged as the Lesson 2 source of truth.
- Keep `trading/definitions/candles.py` unchanged; SMS reads existing OHLC fields directly.
- No package-level re-export is needed because this repository imports definition modules directly.

## Approved Public Interfaces

```python
@dataclass(frozen=True)
class SMSContext:
    parent_segment: MarketSegment
    parent_state: MarketState
    trend_extreme: StructurePoint
    creator_point: StructurePoint


class SMSStructureStatus(Enum):
    PENDING = "pending"
    PULLBACK_ONLY = "pullback_only"
    SMS_CONFIRMED = "sms_confirmed"
    PARENT_CONTINUED = "parent_continued"


@dataclass(frozen=True)
class SMSObservation:
    index: int
    candle: Candle


@dataclass(frozen=True)
class SMSResult:
    status: SMSStructureStatus
    broken_point: StructurePoint | None = None
    event_index: int | None = None
```

Evaluator signature:

```text
evaluate_sms(
    context: SMSContext,
    observations: Sequence[SMSObservation],
) -> SMSResult
```

---

### Task 1: SMS Domain Model, Context Validation, and Result Invariants

**Files:**
- Create: `trading/definitions/sms_structure.py`
- Create: `tests/test_sms_structure.py`

**Interfaces:**
- Consumes: `Candle`, `MarketSegment`, `MarketState`, `StructurePoint`, and `StructurePointKind` from existing definition modules.
- Produces: immutable `SMSContext`, `SMSStructureStatus`, `SMSObservation`, and `SMSResult` with the exact approved fields and enum values.

- [ ] **Step 1: Write the failing domain and validation tests**

Create `tests/test_sms_structure.py` with:

```python
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
```

- [ ] **Step 2: Run the focused test file and verify RED**

Run: `pytest tests/test_sms_structure.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'trading.definitions.sms_structure'` because the Lesson 3 module does not exist.

- [ ] **Step 3: Implement the immutable domain records and context/result invariants**

Create `trading/definitions/sms_structure.py` with:

```python
"""Explicit Chapter 2 SMS reversal-structure definitions."""

from dataclasses import dataclass
from enum import Enum

from .candles import Candle
from .market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
)


class SMSStructureStatus(Enum):
    """Outcome of evaluating one explicit SMS context."""

    PENDING = "pending"
    PULLBACK_ONLY = "pullback_only"
    SMS_CONFIRMED = "sms_confirmed"
    PARENT_CONTINUED = "parent_continued"


@dataclass(frozen=True)
class SMSContext:
    """Explicit creator and extreme boundaries for one directional trend."""

    parent_segment: MarketSegment
    parent_state: MarketState
    trend_extreme: StructurePoint
    creator_point: StructurePoint

    def __post_init__(self) -> None:
        if self.parent_state not in {MarketState.UPTREND, MarketState.DOWNTREND}:
            raise ValueError("parent_state must be directional")

        expected_kinds = (
            (StructurePointKind.HIGH, StructurePointKind.LOW)
            if self.parent_state is MarketState.UPTREND
            else (StructurePointKind.LOW, StructurePointKind.HIGH)
        )
        actual_kinds = (self.trend_extreme.kind, self.creator_point.kind)
        if actual_kinds != expected_kinds:
            raise ValueError("structure point kinds do not match parent direction")

        for point in (self.creator_point, self.trend_extreme):
            if not (
                self.parent_segment.start_index
                <= point.index
                <= self.parent_segment.end_index
            ):
                raise ValueError("SMS boundary is outside parent segment")

        if self.parent_segment.end_index != self.trend_extreme.index:
            raise ValueError("parent segment must end at trend extreme")

        if not self.creator_point.index < self.trend_extreme.index:
            raise ValueError("SMS context chronology is invalid")

        coherent_prices = (
            self.creator_point.price < self.trend_extreme.price
            if self.parent_state is MarketState.UPTREND
            else self.creator_point.price > self.trend_extreme.price
        )
        if not coherent_prices:
            raise ValueError("creator and trend-extreme boundary prices conflict")


@dataclass(frozen=True)
class SMSObservation:
    """One OHLC candle at a dense ordinal position after the trend extreme."""

    index: int
    candle: Candle


@dataclass(frozen=True)
class SMSResult:
    """SMS-layer status and terminal boundary details when present."""

    status: SMSStructureStatus
    broken_point: StructurePoint | None = None
    event_index: int | None = None

    def __post_init__(self) -> None:
        is_terminal = self.status in {
            SMSStructureStatus.SMS_CONFIRMED,
            SMSStructureStatus.PARENT_CONTINUED,
        }
        has_all_event_fields = (
            self.broken_point is not None and self.event_index is not None
        )
        has_any_event_field = (
            self.broken_point is not None or self.event_index is not None
        )

        if is_terminal and not has_all_event_fields:
            raise ValueError(
                "terminal SMS result requires broken point and event index"
            )
        if not is_terminal and has_any_event_field:
            raise ValueError("non-terminal SMS result cannot contain event details")
```

- [ ] **Step 4: Run the Task 1 tests and verify GREEN**

Run: `pytest tests/test_sms_structure.py -v`

Expected: all Task 1 domain, immutability, context-validation, and result-invariant tests pass.

- [ ] **Step 5: Run existing Lesson 1 and Lesson 2 regressions**

Run: `pytest tests/test_market_structure.py tests/test_pullback_structure.py -v`

Expected: all existing Lesson 1 and Lesson 2 tests pass unchanged.

- [ ] **Step 6: Commit the domain-model task**

```bash
git add trading/definitions/sms_structure.py tests/test_sms_structure.py
git commit -m "Add SMS reversal domain model"
```

---

### Task 2: Dense Observation Validation and Non-Terminal States

**Files:**
- Modify: `trading/definitions/sms_structure.py`
- Modify: `tests/test_sms_structure.py`

**Interfaces:**
- Consumes: Task 1 `SMSContext`, `SMSStructureStatus`, `SMSObservation`, and `SMSResult`.
- Produces: `evaluate_sms(context: SMSContext, observations: Sequence[SMSObservation]) -> SMSResult` with complete pre-scan chronology validation, `PENDING`, and `PULLBACK_ONLY` behavior.

- [ ] **Step 1: Add failing observation-contract and non-terminal tests**

Add `evaluate_sms` to the `trading.definitions.sms_structure` import block in `tests/test_sms_structure.py`, then append:

```python
def observed(
    index: int,
    *,
    high_price: float,
    low_price: float,
) -> SMSObservation:
    midpoint = (high_price + low_price) / 2
    return SMSObservation(
        index=index,
        candle=Candle(midpoint, high_price, low_price, midpoint),
    )


@pytest.mark.parametrize("context", [uptrend_context(), downtrend_context()])
def test_empty_observations_return_pending(context: SMSContext) -> None:
    assert evaluate_sms(context, ()) == SMSResult(SMSStructureStatus.PENDING)


@pytest.mark.parametrize(
    ("context", "observations"),
    [
        (
            uptrend_context(),
            [observed(4, high_price=109.0, low_price=96.0)],
        ),
        (
            downtrend_context(),
            [
                observed(4, high_price=104.0, low_price=91.0),
                observed(5, high_price=105.0, low_price=90.0),
            ],
        ),
    ],
)
def test_non_empty_inside_boundary_history_is_pullback_only(
    context: SMSContext,
    observations: list[SMSObservation],
) -> None:
    assert evaluate_sms(context, observations) == SMSResult(
        SMSStructureStatus.PULLBACK_ONLY
    )


@pytest.mark.parametrize(
    "observations",
    [
        [observed(3, high_price=109.0, low_price=96.0)],
        [observed(5, high_price=109.0, low_price=96.0)],
        [
            observed(4, high_price=109.0, low_price=96.0),
            observed(6, high_price=109.0, low_price=96.0),
        ],
        [
            observed(4, high_price=109.0, low_price=96.0),
            observed(4, high_price=109.0, low_price=96.0),
        ],
        [
            observed(4, high_price=109.0, low_price=96.0),
            observed(3, high_price=109.0, low_price=96.0),
        ],
    ],
)
def test_observation_indexes_require_complete_dense_chronology(
    observations: list[SMSObservation],
) -> None:
    with pytest.raises(ValueError, match="complete dense chronology"):
        evaluate_sms(uptrend_context(), observations)


def test_complete_sequence_is_validated_before_an_early_terminal_candidate() -> None:
    observations = [
        observed(4, high_price=109.0, low_price=94.0),
        observed(6, high_price=109.0, low_price=96.0),
    ]

    with pytest.raises(ValueError, match="complete dense chronology"):
        evaluate_sms(uptrend_context(), observations)
```

The last test deliberately supplies a creator-breaking first candle followed by a gap. The evaluator must reject the incomplete history before considering the apparent terminal event.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `pytest tests/test_sms_structure.py -k "empty_observations or inside_boundary or observation_indexes or complete_sequence" -v`

Expected: collection fails with `ImportError: cannot import name 'evaluate_sms'` because the evaluator has not been added.

- [ ] **Step 3: Implement complete dense chronology validation and non-terminal outcomes**

Add `from collections.abc import Sequence` above the dataclass import in `trading/definitions/sms_structure.py`, then append:

```python
def _validate_observations(
    context: SMSContext,
    observations: Sequence[SMSObservation],
) -> None:
    expected_index = context.trend_extreme.index + 1
    for observation in observations:
        if observation.index != expected_index:
            raise ValueError(
                "observations must use complete dense chronology after trend extreme"
            )
        expected_index += 1


def evaluate_sms(
    context: SMSContext,
    observations: Sequence[SMSObservation],
) -> SMSResult:
    """Evaluate one explicit SMS context through supplied later candles."""

    _validate_observations(context, observations)

    if not observations:
        return SMSResult(SMSStructureStatus.PENDING)

    return SMSResult(SMSStructureStatus.PULLBACK_ONLY)
```

Validation occurs before the empty/non-empty outcome branch. Caller order remains authoritative because `_validate_observations()` walks the supplied sequence directly and never sorts it.

- [ ] **Step 4: Run the Task 2 tests and verify GREEN**

Run: `pytest tests/test_sms_structure.py -k "empty_observations or inside_boundary or observation_indexes or complete_sequence" -v`

Expected: all empty-history, unresolved-history, missing-first, same-index, repeated, decreasing, skipped-index, and full-prevalidation tests pass.

- [ ] **Step 5: Run all SMS domain/chronology tests plus existing BMS tests**

Run: `pytest tests/test_sms_structure.py tests/test_pullback_structure.py -v`

Expected: all Task 1-2 SMS tests and all existing Lesson 2 BMS tests pass.

- [ ] **Step 6: Commit the observation-contract task**

```bash
git add trading/definitions/sms_structure.py tests/test_sms_structure.py
git commit -m "Add SMS observation chronology"
```

---

### Task 3: Strict SMS and Parent-Continuation Evaluation

**Files:**
- Modify: `trading/definitions/sms_structure.py`
- Modify: `tests/test_sms_structure.py`

**Interfaces:**
- Consumes: Task 2 `evaluate_sms()` with complete pre-scan chronology validation.
- Produces: strict directional boundary evaluation, exact terminal details, first-event historical semantics, wick/equality behavior, and the approved same-candle ambiguity error.

- [ ] **Step 1: Add failing terminal-event and boundary-semantics tests**

Append to `tests/test_sms_structure.py`:

```python
@pytest.mark.parametrize(
    ("context", "observation"),
    [
        (
            uptrend_context(),
            observed(4, high_price=109.0, low_price=94.0),
        ),
        (
            downtrend_context(),
            observed(4, high_price=106.0, low_price=91.0),
        ),
    ],
)
def test_strict_creator_wick_break_confirms_sms(
    context: SMSContext,
    observation: SMSObservation,
) -> None:
    result = evaluate_sms(context, [observation])

    assert result == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=context.creator_point,
        event_index=4,
    )
    assert result.broken_point is context.creator_point


@pytest.mark.parametrize(
    ("context", "observation"),
    [
        (
            uptrend_context(),
            observed(4, high_price=111.0, low_price=96.0),
        ),
        (
            downtrend_context(),
            observed(4, high_price=104.0, low_price=89.0),
        ),
    ],
)
def test_strict_parent_extreme_wick_break_terminates_old_context(
    context: SMSContext,
    observation: SMSObservation,
) -> None:
    result = evaluate_sms(context, [observation])

    assert result == SMSResult(
        SMSStructureStatus.PARENT_CONTINUED,
        broken_point=context.trend_extreme,
        event_index=4,
    )
    assert result.broken_point is context.trend_extreme


def test_first_sms_event_is_not_erased_by_later_parent_continuation() -> None:
    observations = [
        observed(4, high_price=109.0, low_price=94.0),
        observed(5, high_price=111.0, low_price=96.0),
    ]

    assert evaluate_sms(uptrend_context(), observations) == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=low(2, 95.0),
        event_index=4,
    )


def test_first_parent_continuation_ends_the_old_context() -> None:
    observations = [
        observed(4, high_price=111.0, low_price=96.0),
        observed(5, high_price=109.0, low_price=94.0),
    ]

    assert evaluate_sms(uptrend_context(), observations) == SMSResult(
        SMSStructureStatus.PARENT_CONTINUED,
        broken_point=high(3, 110.0),
        event_index=4,
    )


@pytest.mark.parametrize(
    ("context", "observation"),
    [
        (
            uptrend_context(),
            observed(4, high_price=110.0, low_price=95.0),
        ),
        (
            downtrend_context(),
            observed(4, high_price=105.0, low_price=90.0),
        ),
    ],
)
def test_exact_contact_with_both_boundaries_is_not_a_break(
    context: SMSContext,
    observation: SMSObservation,
) -> None:
    result = evaluate_sms(context, [observation])

    assert result == SMSResult(SMSStructureStatus.PULLBACK_ONLY)


@pytest.mark.parametrize(
    "candle",
    [
        Candle(100.0, 109.0, 94.0, 101.0),
        Candle(105.0, 109.0, 94.0, 100.0),
        Candle(100.0, 109.0, 94.0, 100.0),
    ],
)
def test_sms_wick_break_is_independent_of_close_body_and_color(
    candle: Candle,
) -> None:
    context = uptrend_context()
    result = evaluate_sms(context, [SMSObservation(4, candle)])

    assert result.status is SMSStructureStatus.SMS_CONFIRMED
    assert result.broken_point is context.creator_point
    assert result.event_index == 4


@pytest.mark.parametrize("context", [uptrend_context(), downtrend_context()])
def test_same_candle_dual_boundary_crossing_is_ohlc_ambiguous(
    context: SMSContext,
) -> None:
    with pytest.raises(
        ValueError,
        match="OHLC cannot determine the intrabar boundary order",
    ):
        evaluate_sms(
            context,
            [observed(4, high_price=111.0, low_price=89.0)],
        )


def test_repeated_explicit_sms_contexts_are_evaluated_independently() -> None:
    first = uptrend_context()
    second = uptrend_context(
        segment=MarketSegment(4, 7),
        extreme=high(7, 120.0),
        creator=low(6, 105.0),
    )

    first_result = evaluate_sms(
        first,
        [observed(4, high_price=109.0, low_price=94.0)],
    )
    second_result = evaluate_sms(
        second,
        [observed(8, high_price=119.0, low_price=104.0)],
    )

    assert first_result == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=first.creator_point,
        event_index=4,
    )
    assert second_result == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=second.creator_point,
        event_index=8,
    )
```

- [ ] **Step 2: Run the terminal-event tests and verify RED**

Run: `pytest tests/test_sms_structure.py -k "strict_creator or strict_parent or first_sms or first_parent or exact_contact or wick_break or dual_boundary or repeated_explicit" -v`

Expected: strict creator and continuation cases return `PULLBACK_ONLY`, first-event expectations fail, and dual-boundary cases do not raise because Task 2 has not implemented boundary evaluation.

- [ ] **Step 3: Implement strict directional evaluation and first-event resolution**

Replace Task 2's `evaluate_sms()` in `trading/definitions/sms_structure.py` with:

```python
def evaluate_sms(
    context: SMSContext,
    observations: Sequence[SMSObservation],
) -> SMSResult:
    """Evaluate the first boundary event for one explicit SMS context."""

    _validate_observations(context, observations)

    if not observations:
        return SMSResult(SMSStructureStatus.PENDING)

    for observation in observations:
        if context.parent_state is MarketState.UPTREND:
            sms_crossed = observation.candle.low < context.creator_point.price
            continuation_crossed = (
                observation.candle.high > context.trend_extreme.price
            )
        else:
            sms_crossed = observation.candle.high > context.creator_point.price
            continuation_crossed = (
                observation.candle.low < context.trend_extreme.price
            )

        if sms_crossed and continuation_crossed:
            raise ValueError(
                "OHLC cannot determine the intrabar boundary order"
            )
        if sms_crossed:
            return SMSResult(
                SMSStructureStatus.SMS_CONFIRMED,
                broken_point=context.creator_point,
                event_index=observation.index,
            )
        if continuation_crossed:
            return SMSResult(
                SMSStructureStatus.PARENT_CONTINUED,
                broken_point=context.trend_extreme,
                event_index=observation.index,
            )

    return SMSResult(SMSStructureStatus.PULLBACK_ONLY)
```

The complete `_validate_observations()` call remains before the loop. The strict `<`/`>` comparisons use only candle wicks, and returning inside the loop preserves the first terminal event without creating a replacement context.

- [ ] **Step 4: Run the Task 3 tests and verify GREEN**

Run: `pytest tests/test_sms_structure.py -k "strict_creator or strict_parent or first_sms or first_parent or exact_contact or wick_break or dual_boundary or repeated_explicit" -v`

Expected: all mirrored creator/continuation, exact-point, first-event, equality, wick/body/color, ambiguity, and repeated-context tests pass.

- [ ] **Step 5: Run the complete SMS unit suite and existing Chapter 2 regressions**

Run: `pytest tests/test_sms_structure.py tests/test_market_structure.py tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v`

Expected: all SMS Level 1 tests and all existing Lesson 1/Lesson 2 tests pass without changes to existing production code.

- [ ] **Step 6: Commit the terminal-evaluation task**

```bash
git add trading/definitions/sms_structure.py tests/test_sms_structure.py
git commit -m "Add chronological SMS boundary evaluation"
```

---

### Task 4: Focused Lesson 1 + Lesson 3 Cross-Layer Integration

**Files:**
- Create: `tests/test_sms_structure_integration.py`
- Do not modify: `trading/definitions/market_structure.py`
- Do not modify: `trading/definitions/pullback_structure.py`
- Do not create: `tests/test_course_market_structure_scenarios.py`

**Interfaces:**
- Consumes: existing `classify_market_state(segment: MarketSegment, points: Sequence[StructurePoint]) -> MarketState` and all approved Lesson 3 interfaces completed in Tasks 1-3.
- Produces: focused smoke evidence that explicit Lesson 1 parent classification composes with explicit `SMSContext`, a complete `SMSObservation` sequence, and `evaluate_sms()` without inferring hierarchy.

- [ ] **Step 1: Verify the required integration artifact is absent (RED)**

Run: `pytest tests/test_sms_structure_integration.py -v`

Expected: pytest exits with `ERROR: file or directory not found: tests/test_sms_structure_integration.py`. This is the integration-artifact RED: the required adjacent-layer composition check has not been created.

- [ ] **Step 2: Create the focused integration tests**

Create `tests/test_sms_structure_integration.py` with:

```python
from trading.definitions.candles import Candle
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    classify_market_state,
)
from trading.definitions.sms_structure import (
    SMSContext,
    SMSObservation,
    SMSResult,
    SMSStructureStatus,
    evaluate_sms,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def observed(
    index: int,
    *,
    high_price: float,
    low_price: float,
) -> SMSObservation:
    midpoint = (high_price + low_price) / 2
    return SMSObservation(
        index,
        Candle(midpoint, high_price, low_price, midpoint),
    )


def classified_uptrend_context() -> SMSContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 100.0),
        low(1, 90.0),
        low(2, 95.0),
        high(3, 110.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.UPTREND
    return SMSContext(
        parent_segment=segment,
        parent_state=parent_state,
        trend_extreme=high(3, 110.0),
        creator_point=low(2, 95.0),
    )


def classified_downtrend_context() -> SMSContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 110.0),
        low(1, 100.0),
        high(2, 105.0),
        low(3, 90.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.DOWNTREND
    return SMSContext(
        parent_segment=segment,
        parent_state=parent_state,
        trend_extreme=low(3, 90.0),
        creator_point=high(2, 105.0),
    )


def test_classified_uptrend_composes_with_confirmed_sms() -> None:
    context = classified_uptrend_context()

    assert evaluate_sms(
        context,
        [observed(4, high_price=109.0, low_price=94.0)],
    ) == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=context.creator_point,
        event_index=4,
    )


def test_classified_downtrend_composes_with_confirmed_sms() -> None:
    context = classified_downtrend_context()

    assert evaluate_sms(
        context,
        [observed(4, high_price=106.0, low_price=91.0)],
    ) == SMSResult(
        SMSStructureStatus.SMS_CONFIRMED,
        broken_point=context.creator_point,
        event_index=4,
    )


def test_classified_parent_without_boundary_break_remains_pullback_only() -> None:
    context = classified_uptrend_context()

    assert evaluate_sms(
        context,
        [
            observed(4, high_price=109.0, low_price=96.0),
            observed(5, high_price=110.0, low_price=95.0),
        ],
    ) == SMSResult(SMSStructureStatus.PULLBACK_ONLY)


def test_classified_parent_extreme_break_returns_parent_continued() -> None:
    context = classified_uptrend_context()

    assert evaluate_sms(
        context,
        [observed(4, high_price=111.0, low_price=96.0)],
    ) == SMSResult(
        SMSStructureStatus.PARENT_CONTINUED,
        broken_point=context.trend_extreme,
        event_index=4,
    )


def test_small_context_sms_does_not_infer_larger_context_sms() -> None:
    large_segment = MarketSegment(0, 7)
    large_points = [
        high(0, 100.0),
        low(1, 90.0),
        high(3, 110.0),
        low(4, 95.0),
        low(6, 105.0),
        high(7, 120.0),
    ]
    small_segment = MarketSegment(3, 7)
    small_points = [
        high(3, 110.0),
        low(4, 95.0),
        low(6, 105.0),
        high(7, 120.0),
    ]
    large_state = classify_market_state(large_segment, large_points)
    small_state = classify_market_state(small_segment, small_points)
    assert large_state is MarketState.UPTREND
    assert small_state is MarketState.UPTREND

    large_context = SMSContext(
        large_segment,
        large_state,
        trend_extreme=high(7, 120.0),
        creator_point=low(4, 95.0),
    )
    small_context = SMSContext(
        small_segment,
        small_state,
        trend_extreme=high(7, 120.0),
        creator_point=low(6, 105.0),
    )
    observation = observed(8, high_price=119.0, low_price=100.0)

    assert evaluate_sms(small_context, [observation]).status is (
        SMSStructureStatus.SMS_CONFIRMED
    )
    assert evaluate_sms(large_context, [observation]).status is (
        SMSStructureStatus.PULLBACK_ONLY
    )
```

The final case uses two separately classified, explicitly bounded contexts. A break of the small context's creator does not mutate, infer, or propagate an SMS into the larger context.

- [ ] **Step 3: Run the focused integration file and verify GREEN**

Run: `pytest tests/test_sms_structure_integration.py -v`

Expected: all five explicit Lesson 1 + Lesson 3 composition tests pass.

- [ ] **Step 4: Run SMS unit and focused integration tests together**

Run: `pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v`

Expected: all SMS Level 1 and focused adjacent-layer integration tests pass.

- [ ] **Step 5: Run existing Lesson 1 and Lesson 2 tests beside the new integration file**

Run: `pytest tests/test_market_structure.py tests/test_pullback_structure.py tests/test_pullback_structure_integration.py tests/test_sms_structure_integration.py -v`

Expected: all existing Chapter 2 tests and the five SMS composition tests pass.

- [ ] **Step 6: Commit the focused integration task**

```bash
git add tests/test_sms_structure_integration.py
git commit -m "Add SMS cross-layer integration tests"
```

---

### Task 5: Full SMS Regression, Scope, and Chapter-Continuation Gate

**Files:**
- Verify: `trading/definitions/sms_structure.py`
- Verify: `tests/test_sms_structure.py`
- Verify: `tests/test_sms_structure_integration.py`
- Verify unchanged: `trading/definitions/market_structure.py`
- Verify unchanged: `trading/definitions/pullback_structure.py`
- Verify unchanged: `trading/definitions/candles.py`

**Interfaces:**
- Consumes: all Task 1-4 implementation commits.
- Produces: fresh evidence that SMS Level 1 tests, focused adjacent-layer integration, existing BMS behavior, and the complete repository regression suite pass with design-limited scope.

- [ ] **Step 1: Run the complete SMS Level 1 unit suite**

Run: `pytest tests/test_sms_structure.py -v`

Expected: all focused SMS unit tests pass.

- [ ] **Step 2: Run the focused Lesson 1 + Lesson 3 integration suite**

Run: `pytest tests/test_sms_structure_integration.py -v`

Expected: all five focused composition tests pass.

- [ ] **Step 3: Run the complete existing BMS regression suites**

Run: `pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v`

Expected: all Lesson 2 unit and integration tests pass unchanged.

- [ ] **Step 4: Run the complete repository test suite**

Run: `pytest`

Expected: the entire test suite passes with zero failures.

- [ ] **Step 5: Check formatting and whitespace**

No dedicated formatter or linter configuration exists at the planning checkpoint. Run the repository's existing whitespace check:

Run: `git diff --check e847d9c375765799dd6300c80f9fe774506646af..HEAD`

Expected: exit code 0 with no whitespace errors.

- [ ] **Step 6: Verify the complete implementation scope**

Run: `git diff --name-only e847d9c375765799dd6300c80f9fe774506646af..HEAD`

Expected paths only:

```text
docs/superpowers/plans/2026-08-30-sms-reversal-structure.md
tests/test_sms_structure.py
tests/test_sms_structure_integration.py
trading/definitions/sms_structure.py
```

The approved design spec predates this comparison base and remains unchanged. The plan plus three implementation paths contain only SMS production, Level 1 unit, and focused adjacent-layer integration work.

- [ ] **Step 7: Prove existing production layers were not edited**

Run: `git diff --exit-code e847d9c375765799dd6300c80f9fe774506646af..HEAD -- trading/definitions/market_structure.py trading/definitions/pullback_structure.py trading/definitions/candles.py`

Expected: exit code 0 and no diff.

- [ ] **Step 8: Confirm the formal Chapter 2 Level 2 suite remains absent**

Run in PowerShell:

```powershell
if (Test-Path -LiteralPath "tests/test_course_market_structure_scenarios.py") {
    throw "Formal Chapter 2 Level 2 validation was added too early"
}
```

Expected: exit code 0 with no output.

- [ ] **Step 9: Inspect production code for forbidden coupling and terminology**

Run: `rg -n "classify_market_state|evaluate_bms|zig.?zag|BOS|CHOCH|strategy|broker" trading/definitions/sms_structure.py`

Expected: exit code 1 with no matches. `sms_structure.py` must consume the explicit `parent_state` and boundaries without calling Lesson 1 classification, Lesson 2 BMS, or adding future-course/strategy/execution concepts.

- [ ] **Step 10: Inspect implementation commits without rewriting valid history**

Run: `git log --oneline e847d9c375765799dd6300c80f9fe774506646af..HEAD`

Expected: the implementation-plan commit plus the four focused implementation/test commits from Tasks 1-4. Review any additional in-scope fix commit rather than rewriting or hiding valid history.

- [ ] **Step 11: Enforce the Lesson 3 completion gate**

Record SMS implementation complete only when all conditions are true:

```text
SMS Level 1 unit tests: PASS
Lesson 1 + Lesson 3 focused integration tests: PASS
Existing Lesson 2 BMS regressions: PASS
Full repository regression suite: PASS
Whitespace and scope checks: PASS
Final spec-compliance review: PASS
```

Do not claim that SMS confirms an opposite trend or actual reversal. Do not claim that the complete Chapter 2 model has passed formal Level 2 validation.

No Task 5 commit is expected when verification is clean because this task changes no files. If verification exposes an in-scope defect, return to the owning task, reproduce the failure, make the minimum correction, rerun its targeted and regression commands, and commit the correction with a message describing the actual behavior fixed.

## Future Mandatory Level 2 Chapter-Completion Gate

Formal Level 2 course-scenario validation is not part of Lesson 3 implementation. After every Chapter 2 market-structure lesson is implemented:

1. review the complete Chapter 2 course material;
2. design comprehensive hand-labelled scenarios using only concepts actually taught;
3. create or update `tests/test_course_market_structure_scenarios.py`;
4. exercise all relevant Chapter 2 structure layers together;
5. run the full regression suite; and
6. only then call the Chapter 2 market-structure foundation validated.

The future suite may cover trend/non-trend, pullbacks, BMS, SMS, later course structures, short/medium/long-term structures, cycles/timeframes, levels/hierarchy, nested structures, and other relationships actually defined by the completed chapter. This Lesson 3 plan does not define those future relationships.

## Conditional Level 3 Validation Milestone

At the Chapter 2 completion checkpoint, reassess whether the course has supplied legitimate rules for automatically extracting structural points, trend levels, cycles/timeframes, and hierarchy from raw candles. If those rules are sufficient, design a later raw-chart validation phase comparing automatically derived structures against manually labelled teacher/course examples. If the rules remain insufficient, keep Level 3 deferred rather than inventing swing, zig-zag, creator-selection, or hierarchy logic.
