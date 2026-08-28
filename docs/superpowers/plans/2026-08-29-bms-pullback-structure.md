# BMS Pullback Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Chapter 2, Lesson 2 pullback/BMS evaluation from an explicit parent trend and a complete dense sequence of later OHLC observations, then prove the Lesson 1 and Lesson 2 interfaces compose through a small focused integration check.

**Architecture:** Add one focused `trading.definitions.pullback_structure` module that reuses the existing `MarketSegment`, `MarketState`, `StructurePoint`, and `StructurePointKind` definitions without reclassifying the parent structure. An immutable `PullbackContext` validates the explicit parent boundary, while the stateless `evaluate_bms()` function validates a complete ordered observation sequence and resolves the first strict origin or BMS boundary event.

**Tech Stack:** Python standard library (`collections.abc.Sequence`, `dataclasses`, `enum`), pytest, existing `trading.definitions.candles.Candle`, and existing `trading.definitions.market_structure` domain types and `classify_market_state()`.

**Spec:** `docs/superpowers/specs/2026-08-29-bms-pullback-structure-design.md`

## Global Constraints

- Implement only Chapter 2, Lesson 2: BMS Pullback Structure.
- Add only `PullbackContext`, `PullbackStructureStatus`, `BMSObservation`, `BMSResult`, `evaluate_bms()`, focused unit tests, and a small Lesson 1 + Lesson 2 integration smoke test.
- Reuse `MarketSegment`, `MarketState`, `StructurePoint`, `StructurePointKind`, and `classify_market_state()` from `trading/definitions/market_structure.py`; do not duplicate or modify their behavior.
- `PullbackContext` receives an already-established directional `parent_state`; it must not accept the full parent point sequence or call `classify_market_state()`.
- The parent segment ends exactly at the previous trend extreme: `parent_segment.end_index == previous_extreme.index`.
- Preserve strict chronology: `trend_origin.index < previous_extreme.index < pullback_extreme.index`.
- Indexes are dense ordinal candle positions in one ordered market series/timeframe. `index + 1` means the immediately following candle, not a fixed clock duration or arbitrary external identifier.
- A non-empty observation sequence begins at `pullback_extreme.index + 1` and advances by exactly one index per observation.
- Preserve caller order; never sort, repair, interpolate, discard, or synthesize observations.
- Repeated, decreasing, same-index, or skipped observation indexes are invalid.
- An empty observation sequence is valid and yields `PULLBACK_ONLY` for a valid pullback.
- Strict wick crossing counts. Candle close, body, and color are irrelevant.
- Equality with the BMS level is not a break. Equality with the trend origin is not invalidation.
- Add no percentage penetration, tick buffer, tolerance, or confirmation-candle requirement.
- Same-candle pullback-extreme/BMS ordering is unsupported by the OHLC-only evaluator.
- The first terminal boundary event wins. Later observations cannot overwrite it.
- If one OHLC candle crosses both boundaries, raise `ValueError` containing `OHLC cannot determine the intrabar boundary order`.
- Repeated and nested structures use separate explicit contexts; add no counter, one-BMS limit, parent/child identifier, hierarchy level, or recursive discovery.
- Do not add automatic swing detection, zig-zag extraction, structure-point discovery, pullback discovery, trend/segment/timeframe selection, hierarchy inference, or isolated-point-to-structure-point mapping.
- Do not add SMS, reversal structure, BOS, CHOCH, strategy, signals, entries, exits, stop loss, take profit, position sizing, or broker execution.
- Do not modify existing production files unless a spec-supported compatibility issue is proven during implementation. The approved design requires no such edit.
- BMS completion requires its Level 1 unit tests, the focused Lesson 1 + Lesson 2 integration tests, and the full regression suite to pass. Chapter 2 may then continue to Lesson 3.
- Formal Level 2 course-scenario validation is deferred until every Chapter 2 market-structure lesson is implemented.

## File Map

- Create `trading/definitions/pullback_structure.py`: immutable Lesson 2 domain records, context validation, dense observation validation, and chronological BMS evaluation.
- Create `tests/test_pullback_structure.py`: focused Level 1 domain, validation, pullback, observation, boundary, ambiguity, and composability tests.
- Create `tests/test_pullback_structure_integration.py`: a small smoke suite composing `classify_market_state()` with the new Lesson 2 API.
- Keep `trading/definitions/market_structure.py` unchanged as the Lesson 1 source of truth.
- No package-level re-export is needed because this repository imports definition modules directly.

## Approved Interfaces

```python
@dataclass(frozen=True)
class PullbackContext:
    parent_segment: MarketSegment
    parent_state: MarketState
    trend_origin: StructurePoint
    previous_extreme: StructurePoint
    pullback_extreme: StructurePoint


class PullbackStructureStatus(Enum):
    PULLBACK_ONLY = "pullback_only"
    BMS_CONFIRMED = "bms_confirmed"
    NOT_A_PULLBACK = "not_a_pullback"


@dataclass(frozen=True)
class BMSObservation:
    index: int
    candle: Candle


@dataclass(frozen=True)
class BMSResult:
    status: PullbackStructureStatus
    broken_extreme: StructurePoint | None = None
    breakout_index: int | None = None
```

Evaluator signature:

```text
evaluate_bms(context: PullbackContext, observations: Sequence[BMSObservation]) -> BMSResult
```

---

### Task 1: Core BMS Domain Model and PullbackContext Validation

**Files:**
- Create: `trading/definitions/pullback_structure.py`
- Create: `tests/test_pullback_structure.py`

**Interfaces:**
- Consumes: `Candle`, `MarketSegment`, `MarketState`, `StructurePoint`, and `StructurePointKind` from existing definition modules.
- Produces: `PullbackContext`, `PullbackStructureStatus`, `BMSObservation`, and `BMSResult` with the exact approved fields and enum values.

- [ ] **Step 1: Write the failing domain and context-validation tests**

Create `tests/test_pullback_structure.py` with:

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
from trading.definitions.pullback_structure import (
    BMSObservation,
    BMSResult,
    PullbackContext,
    PullbackStructureStatus,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def uptrend_context(
    *,
    segment: MarketSegment = MarketSegment(0, 3),
    origin: StructurePoint = low(1, 90.0),
    previous: StructurePoint = high(3, 110.0),
    pullback: StructurePoint = low(4, 100.0),
) -> PullbackContext:
    return PullbackContext(
        parent_segment=segment,
        parent_state=MarketState.UPTREND,
        trend_origin=origin,
        previous_extreme=previous,
        pullback_extreme=pullback,
    )


def downtrend_context(
    *,
    segment: MarketSegment = MarketSegment(0, 3),
    origin: StructurePoint = high(2, 110.0),
    previous: StructurePoint = low(3, 90.0),
    pullback: StructurePoint = high(4, 100.0),
) -> PullbackContext:
    return PullbackContext(
        parent_segment=segment,
        parent_state=MarketState.DOWNTREND,
        trend_origin=origin,
        previous_extreme=previous,
        pullback_extreme=pullback,
    )


def test_pullback_status_values_are_stable() -> None:
    assert {status.value for status in PullbackStructureStatus} == {
        "pullback_only",
        "bms_confirmed",
        "not_a_pullback",
    }


def test_pullback_domain_records_preserve_supplied_values() -> None:
    context = uptrend_context()
    candle = Candle(100.0, 105.0, 95.0, 101.0)

    assert BMSObservation(5, candle) == BMSObservation(index=5, candle=candle)
    assert BMSResult(PullbackStructureStatus.PULLBACK_ONLY) == BMSResult(
        status=PullbackStructureStatus.PULLBACK_ONLY,
        broken_extreme=None,
        breakout_index=None,
    )
    assert context.previous_extreme == high(3, 110.0)


@pytest.mark.parametrize(
    ("instance", "attribute"),
    [
        (uptrend_context(), "parent_state"),
        (BMSObservation(5, Candle(100.0, 105.0, 95.0, 101.0)), "index"),
        (BMSResult(PullbackStructureStatus.PULLBACK_ONLY), "status"),
    ],
)
def test_pullback_domain_records_are_frozen(
    instance: object,
    attribute: str,
) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, None)


def test_context_rejects_non_directional_parent_state() -> None:
    with pytest.raises(ValueError, match="directional"):
        PullbackContext(
            MarketSegment(0, 3),
            MarketState.NON_TREND,
            low(1, 90.0),
            high(3, 110.0),
            low(4, 100.0),
        )


@pytest.mark.parametrize(
    ("state", "origin", "previous", "pullback"),
    [
        (MarketState.UPTREND, high(1, 90.0), high(3, 110.0), low(4, 100.0)),
        (MarketState.UPTREND, low(1, 90.0), low(3, 110.0), low(4, 100.0)),
        (MarketState.UPTREND, low(1, 90.0), high(3, 110.0), high(4, 100.0)),
        (MarketState.DOWNTREND, low(1, 110.0), low(3, 90.0), high(4, 100.0)),
        (MarketState.DOWNTREND, high(1, 110.0), high(3, 90.0), high(4, 100.0)),
        (MarketState.DOWNTREND, high(1, 110.0), low(3, 90.0), low(4, 100.0)),
    ],
)
def test_context_rejects_wrong_directional_point_kinds(
    state: MarketState,
    origin: StructurePoint,
    previous: StructurePoint,
    pullback: StructurePoint,
) -> None:
    with pytest.raises(ValueError, match="point kinds"):
        PullbackContext(
            MarketSegment(0, 3),
            state,
            origin,
            previous,
            pullback,
        )


@pytest.mark.parametrize(
    ("segment", "origin", "previous"),
    [
        (MarketSegment(1, 3), low(0, 90.0), high(3, 110.0)),
        (MarketSegment(0, 2), low(1, 90.0), high(3, 110.0)),
    ],
)
def test_context_rejects_parent_points_outside_segment(
    segment: MarketSegment,
    origin: StructurePoint,
    previous: StructurePoint,
) -> None:
    with pytest.raises(ValueError, match="outside parent segment"):
        uptrend_context(segment=segment, origin=origin, previous=previous)


def test_context_requires_parent_segment_to_end_at_previous_extreme() -> None:
    with pytest.raises(ValueError, match="end at previous extreme"):
        uptrend_context(segment=MarketSegment(0, 4))


@pytest.mark.parametrize(
    ("origin", "previous", "pullback"),
    [
        (low(3, 90.0), high(3, 110.0), low(4, 100.0)),
        (low(1, 90.0), high(3, 110.0), low(3, 100.0)),
    ],
)
def test_context_rejects_invalid_chronology(
    origin: StructurePoint,
    previous: StructurePoint,
    pullback: StructurePoint,
) -> None:
    segment = MarketSegment(0, previous.index)
    with pytest.raises(ValueError, match="chronology"):
        uptrend_context(
            segment=segment,
            origin=origin,
            previous=previous,
            pullback=pullback,
        )


@pytest.mark.parametrize(
    "context_factory",
    [
        lambda: uptrend_context(origin=low(1, 110.0)),
        lambda: uptrend_context(origin=low(1, 111.0)),
        lambda: downtrend_context(origin=high(2, 90.0)),
        lambda: downtrend_context(origin=high(2, 89.0)),
    ],
)
def test_context_rejects_incoherent_origin_and_extreme_prices(
    context_factory: object,
) -> None:
    with pytest.raises(ValueError, match="boundary prices"):
        context_factory()  # type: ignore[operator]
```

- [ ] **Step 2: Run the focused test file and verify RED**

Run: `pytest tests/test_pullback_structure.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'trading.definitions.pullback_structure'` because the Lesson 2 module does not exist.

- [ ] **Step 3: Implement the immutable types and context invariants**

Create `trading/definitions/pullback_structure.py` with:

```python
"""Explicit Chapter 2 pullback and BMS structure definitions."""

from dataclasses import dataclass
from enum import Enum

from .candles import Candle
from .market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
)


class PullbackStructureStatus(Enum):
    """Course-defined result of evaluating one explicit pullback context."""

    PULLBACK_ONLY = "pullback_only"
    BMS_CONFIRMED = "bms_confirmed"
    NOT_A_PULLBACK = "not_a_pullback"


@dataclass(frozen=True)
class PullbackContext:
    """Explicit parent-trend boundaries and the later pullback extreme."""

    parent_segment: MarketSegment
    parent_state: MarketState
    trend_origin: StructurePoint
    previous_extreme: StructurePoint
    pullback_extreme: StructurePoint

    def __post_init__(self) -> None:
        if self.parent_state not in {MarketState.UPTREND, MarketState.DOWNTREND}:
            raise ValueError("parent_state must be directional")

        expected_kinds = (
            (
                StructurePointKind.LOW,
                StructurePointKind.HIGH,
                StructurePointKind.LOW,
            )
            if self.parent_state is MarketState.UPTREND
            else (
                StructurePointKind.HIGH,
                StructurePointKind.LOW,
                StructurePointKind.HIGH,
            )
        )
        actual_kinds = (
            self.trend_origin.kind,
            self.previous_extreme.kind,
            self.pullback_extreme.kind,
        )
        if actual_kinds != expected_kinds:
            raise ValueError("structure point kinds do not match parent direction")

        for point in (self.trend_origin, self.previous_extreme):
            if not (
                self.parent_segment.start_index
                <= point.index
                <= self.parent_segment.end_index
            ):
                raise ValueError("parent structure point is outside parent segment")

        if self.parent_segment.end_index != self.previous_extreme.index:
            raise ValueError("parent segment must end at previous extreme")

        if not (
            self.trend_origin.index
            < self.previous_extreme.index
            < self.pullback_extreme.index
        ):
            raise ValueError("pullback context chronology is invalid")

        coherent_prices = (
            self.trend_origin.price < self.previous_extreme.price
            if self.parent_state is MarketState.UPTREND
            else self.trend_origin.price > self.previous_extreme.price
        )
        if not coherent_prices:
            raise ValueError("trend origin and previous extreme boundary prices conflict")


@dataclass(frozen=True)
class BMSObservation:
    """One OHLC candle at a dense ordinal position after the pullback."""

    index: int
    candle: Candle


@dataclass(frozen=True)
class BMSResult:
    """The course outcome and BMS details when a break is confirmed."""

    status: PullbackStructureStatus
    broken_extreme: StructurePoint | None = None
    breakout_index: int | None = None
```

- [ ] **Step 4: Run the Task 1 tests and verify GREEN**

Run: `pytest tests/test_pullback_structure.py -v`

Expected: all Task 1 tests pass.

- [ ] **Step 5: Run the Lesson 1 domain regressions**

Run: `pytest tests/test_market_structure.py -v`

Expected: all existing Lesson 1 market-structure tests pass unchanged.

- [ ] **Step 6: Commit the domain-model task**

```bash
git add trading/definitions/pullback_structure.py tests/test_pullback_structure.py
git commit -m "Add BMS pullback domain model"
```

---

### Task 2: Basic Pullback Outcome Evaluation

**Files:**
- Modify: `trading/definitions/pullback_structure.py`
- Modify: `tests/test_pullback_structure.py`

**Interfaces:**
- Consumes: Task 1 `PullbackContext`, `PullbackStructureStatus`, `BMSObservation`, and `BMSResult`.
- Produces: `evaluate_bms(context: PullbackContext, observations: Sequence[BMSObservation]) -> BMSResult`, initially exercised with empty observation sequences and complete context-level pullback rules.

- [ ] **Step 1: Add failing empty-sequence pullback outcome tests**

Add `evaluate_bms` to the `trading.definitions.pullback_structure` import block, then append to `tests/test_pullback_structure.py`:

```python
@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (uptrend_context(), PullbackStructureStatus.PULLBACK_ONLY),
        (downtrend_context(), PullbackStructureStatus.PULLBACK_ONLY),
        (
            uptrend_context(pullback=low(4, 110.0)),
            PullbackStructureStatus.NOT_A_PULLBACK,
        ),
        (
            downtrend_context(pullback=high(4, 90.0)),
            PullbackStructureStatus.NOT_A_PULLBACK,
        ),
        (
            uptrend_context(pullback=low(4, 89.0)),
            PullbackStructureStatus.NOT_A_PULLBACK,
        ),
        (
            downtrend_context(pullback=high(4, 111.0)),
            PullbackStructureStatus.NOT_A_PULLBACK,
        ),
        (
            uptrend_context(pullback=low(4, 90.0)),
            PullbackStructureStatus.PULLBACK_ONLY,
        ),
        (
            downtrend_context(pullback=high(4, 110.0)),
            PullbackStructureStatus.PULLBACK_ONLY,
        ),
    ],
)
def test_empty_observations_return_context_level_pullback_outcome(
    context: PullbackContext,
    expected: PullbackStructureStatus,
) -> None:
    assert evaluate_bms(context, ()) == BMSResult(expected)
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `pytest tests/test_pullback_structure.py -k "empty_observations" -v`

Expected: collection fails with `ImportError: cannot import name 'evaluate_bms'` because the evaluator has not been added.

- [ ] **Step 3: Implement the context-level pullback outcomes**

Add `from collections.abc import Sequence` at the top of `trading/definitions/pullback_structure.py`, then append:

```python
def evaluate_bms(
    context: PullbackContext,
    observations: Sequence[BMSObservation],
) -> BMSResult:
    """Evaluate one explicit pullback through supplied later observations."""

    if context.parent_state is MarketState.UPTREND:
        no_pullback = (
            context.pullback_extreme.price >= context.previous_extreme.price
        )
        origin_invalidated = (
            context.pullback_extreme.price < context.trend_origin.price
        )
    else:
        no_pullback = (
            context.pullback_extreme.price <= context.previous_extreme.price
        )
        origin_invalidated = (
            context.pullback_extreme.price > context.trend_origin.price
        )

    if no_pullback or origin_invalidated:
        return BMSResult(PullbackStructureStatus.NOT_A_PULLBACK)

    return BMSResult(PullbackStructureStatus.PULLBACK_ONLY)
```

The unused `observations` parameter is intentional at this TDD checkpoint; Task 3 adds its complete dense-sequence contract and scan without changing the approved signature.

- [ ] **Step 4: Run the Task 2 tests and verify GREEN**

Run: `pytest tests/test_pullback_structure.py -k "empty_observations" -v`

Expected: all eight context-level outcome cases pass, including origin equality.

- [ ] **Step 5: Run all focused and Lesson 1 regressions**

Run: `pytest tests/test_pullback_structure.py tests/test_market_structure.py -v`

Expected: all tests in both files pass.

- [ ] **Step 6: Commit the pullback-outcome task**

```bash
git add trading/definitions/pullback_structure.py tests/test_pullback_structure.py
git commit -m "Add BMS pullback outcome evaluation"
```

---

### Task 3: Dense Observation Validation and Chronological BMS Scanning

**Files:**
- Modify: `trading/definitions/pullback_structure.py`
- Modify: `tests/test_pullback_structure.py`

**Interfaces:**
- Consumes: the Task 2 evaluator signature and immutable Task 1 records.
- Produces: complete dense observation validation, uptrend/downtrend strict boundary scanning, and first-terminal-event behavior.

- [ ] **Step 1: Add failing observation and chronological-scan tests**

Append to `tests/test_pullback_structure.py`:

```python
def observed(index: int, *, high_price: float, low_price: float) -> BMSObservation:
    midpoint = (high_price + low_price) / 2
    return BMSObservation(
        index,
        Candle(midpoint, high_price, low_price, midpoint),
    )


@pytest.mark.parametrize(
    ("context", "observation", "expected_extreme"),
    [
        (
            uptrend_context(),
            observed(5, high_price=111.0, low_price=95.0),
            high(3, 110.0),
        ),
        (
            downtrend_context(),
            observed(5, high_price=105.0, low_price=89.0),
            low(3, 90.0),
        ),
    ],
)
def test_immediate_strict_bms_break_is_confirmed(
    context: PullbackContext,
    observation: BMSObservation,
    expected_extreme: StructurePoint,
) -> None:
    assert evaluate_bms(context, [observation]) == BMSResult(
        PullbackStructureStatus.BMS_CONFIRMED,
        broken_extreme=expected_extreme,
        breakout_index=5,
    )


def test_multi_candle_scan_returns_first_later_bms() -> None:
    observations = [
        observed(5, high_price=109.0, low_price=95.0),
        observed(6, high_price=110.0, low_price=94.0),
        observed(7, high_price=111.0, low_price=96.0),
    ]

    assert evaluate_bms(uptrend_context(), observations) == BMSResult(
        PullbackStructureStatus.BMS_CONFIRMED,
        broken_extreme=high(3, 110.0),
        breakout_index=7,
    )


def test_first_bms_event_is_not_overwritten_by_later_origin_crossing() -> None:
    observations = [
        observed(5, high_price=111.0, low_price=96.0),
        observed(6, high_price=109.0, low_price=89.0),
    ]

    assert evaluate_bms(uptrend_context(), observations) == BMSResult(
        PullbackStructureStatus.BMS_CONFIRMED,
        broken_extreme=high(3, 110.0),
        breakout_index=5,
    )


def test_first_origin_event_is_not_overwritten_by_later_bms_crossing() -> None:
    observations = [
        observed(5, high_price=109.0, low_price=89.0),
        observed(6, high_price=111.0, low_price=95.0),
    ]

    assert evaluate_bms(uptrend_context(), observations) == BMSResult(
        PullbackStructureStatus.NOT_A_PULLBACK
    )


@pytest.mark.parametrize(
    "observations",
    [
        [observed(6, high_price=109.0, low_price=95.0)],
        [
            observed(5, high_price=109.0, low_price=95.0),
            observed(5, high_price=109.0, low_price=95.0),
        ],
        [
            observed(5, high_price=109.0, low_price=95.0),
            observed(4, high_price=109.0, low_price=95.0),
        ],
        [
            observed(5, high_price=109.0, low_price=95.0),
            observed(7, high_price=111.0, low_price=95.0),
        ],
    ],
)
def test_observation_indexes_must_be_complete_dense_chronology(
    observations: list[BMSObservation],
) -> None:
    with pytest.raises(ValueError, match="complete dense chronology"):
        evaluate_bms(uptrend_context(), observations)


def test_same_index_observation_is_ohlc_indeterminate() -> None:
    with pytest.raises(ValueError, match="same-candle pullback/BMS order"):
        evaluate_bms(
            uptrend_context(),
            [observed(4, high_price=111.0, low_price=95.0)],
        )
```

- [ ] **Step 2: Run the scan tests and verify RED**

Run: `pytest tests/test_pullback_structure.py -k "immediate_strict or multi_candle or first_bms_event or first_origin_event or observation_indexes or same_index" -v`

Expected: BMS assertions fail because Task 2 always returns `PULLBACK_ONLY`, and malformed observation sequences are not yet rejected.

- [ ] **Step 3: Implement dense validation and the chronological scan**

Add this helper before `evaluate_bms()` in `trading/definitions/pullback_structure.py`:

```python
def _validate_observations(
    context: PullbackContext,
    observations: Sequence[BMSObservation],
) -> None:
    expected_index = context.pullback_extreme.index + 1
    for position, observation in enumerate(observations):
        if (
            position == 0
            and observation.index == context.pullback_extreme.index
        ):
            raise ValueError(
                "OHLC cannot determine same-candle pullback/BMS order"
            )
        if observation.index != expected_index:
            raise ValueError(
                "observations must use complete dense chronology after pullback"
            )
        expected_index += 1
```

Replace `evaluate_bms()` with:

```python
def evaluate_bms(
    context: PullbackContext,
    observations: Sequence[BMSObservation],
) -> BMSResult:
    """Evaluate the first boundary event after one explicit pullback."""

    _validate_observations(context, observations)

    if context.parent_state is MarketState.UPTREND:
        no_pullback = (
            context.pullback_extreme.price >= context.previous_extreme.price
        )
        origin_invalidated = (
            context.pullback_extreme.price < context.trend_origin.price
        )
    else:
        no_pullback = (
            context.pullback_extreme.price <= context.previous_extreme.price
        )
        origin_invalidated = (
            context.pullback_extreme.price > context.trend_origin.price
        )

    if no_pullback or origin_invalidated:
        return BMSResult(PullbackStructureStatus.NOT_A_PULLBACK)

    for observation in observations:
        if context.parent_state is MarketState.UPTREND:
            origin_crossed = observation.candle.low < context.trend_origin.price
            bms_crossed = (
                observation.candle.high > context.previous_extreme.price
            )
        else:
            origin_crossed = observation.candle.high > context.trend_origin.price
            bms_crossed = observation.candle.low < context.previous_extreme.price

        if origin_crossed:
            return BMSResult(PullbackStructureStatus.NOT_A_PULLBACK)
        if bms_crossed:
            return BMSResult(
                PullbackStructureStatus.BMS_CONFIRMED,
                broken_extreme=context.previous_extreme,
                breakout_index=observation.index,
            )

    return BMSResult(PullbackStructureStatus.PULLBACK_ONLY)
```

The deliberate origin-first branch leaves the same-candle dual-boundary case RED for Task 4 rather than guessing its course outcome.

- [ ] **Step 4: Run the Task 3 tests and verify GREEN**

Run: `pytest tests/test_pullback_structure.py -k "immediate_strict or multi_candle or first_bms_event or first_origin_event or observation_indexes or same_index" -v`

Expected: all dense-sequence, immediate/multi-candle, mirrored BMS, and first-event cases pass.

- [ ] **Step 5: Run all focused regressions**

Run: `pytest tests/test_pullback_structure.py tests/test_market_structure.py -v`

Expected: all Task 1-3 and Lesson 1 tests pass.

- [ ] **Step 6: Commit the chronological-scan task**

```bash
git add trading/definitions/pullback_structure.py tests/test_pullback_structure.py
git commit -m "Add chronological BMS observation scanning"
```

---

### Task 4: Wick, Equality, Ambiguity, Result Invariants, and Composability

**Files:**
- Modify: `trading/definitions/pullback_structure.py`
- Modify: `tests/test_pullback_structure.py`

**Interfaces:**
- Consumes: Task 3 dense chronological evaluator.
- Produces: explicit dual-boundary rejection, enforced `BMSResult` field invariants, strict wick/equality behavior, and proof that repeated/nested explicit contexts remain independent.

- [ ] **Step 1: Add failing boundary-ambiguity and result-invariant tests plus complete semantic coverage**

Append to `tests/test_pullback_structure.py`:

```python
@pytest.mark.parametrize(
    ("context", "observation"),
    [
        (
            uptrend_context(),
            observed(5, high_price=111.0, low_price=89.0),
        ),
        (
            downtrend_context(),
            observed(5, high_price=111.0, low_price=89.0),
        ),
    ],
)
def test_dual_boundary_ohlc_candle_is_rejected_as_ambiguous(
    context: PullbackContext,
    observation: BMSObservation,
) -> None:
    with pytest.raises(
        ValueError,
        match="OHLC cannot determine the intrabar boundary order",
    ):
        evaluate_bms(context, [observation])


def test_exact_bms_level_touch_is_not_a_break() -> None:
    result = evaluate_bms(
        uptrend_context(),
        [observed(5, high_price=110.0, low_price=95.0)],
    )

    assert result == BMSResult(PullbackStructureStatus.PULLBACK_ONLY)


def test_exact_origin_touch_does_not_prevent_later_wick_bms() -> None:
    result = evaluate_bms(
        uptrend_context(),
        [observed(5, high_price=111.0, low_price=90.0)],
    )

    assert result == BMSResult(
        PullbackStructureStatus.BMS_CONFIRMED,
        broken_extreme=high(3, 110.0),
        breakout_index=5,
    )


@pytest.mark.parametrize(
    "candle",
    [
        Candle(100.0, 111.0, 95.0, 101.0),
        Candle(105.0, 111.0, 95.0, 100.0),
        Candle(100.0, 111.0, 95.0, 100.0),
    ],
)
def test_wick_bms_is_independent_of_close_body_and_color(candle: Candle) -> None:
    context = uptrend_context()
    result = evaluate_bms(context, [BMSObservation(5, candle)])

    assert result.status is PullbackStructureStatus.BMS_CONFIRMED
    assert result.broken_extreme is context.previous_extreme
    assert result.breakout_index == 5


def test_downtrend_equality_and_wick_rules_mirror_uptrend() -> None:
    touch = observed(5, high_price=105.0, low_price=90.0)
    wick_break = observed(5, high_price=110.0, low_price=89.0)

    assert evaluate_bms(downtrend_context(), [touch]).status is (
        PullbackStructureStatus.PULLBACK_ONLY
    )
    assert evaluate_bms(downtrend_context(), [wick_break]) == BMSResult(
        PullbackStructureStatus.BMS_CONFIRMED,
        broken_extreme=low(3, 90.0),
        breakout_index=5,
    )


def test_bms_result_requires_break_details_only_for_confirmed_status() -> None:
    with pytest.raises(ValueError, match="confirmed BMS requires"):
        BMSResult(PullbackStructureStatus.BMS_CONFIRMED)

    with pytest.raises(ValueError, match="non-BMS result cannot contain"):
        BMSResult(
            PullbackStructureStatus.PULLBACK_ONLY,
            broken_extreme=high(3, 110.0),
            breakout_index=5,
        )


def test_repeated_explicit_contexts_are_evaluated_independently() -> None:
    first = uptrend_context()
    second = uptrend_context(
        segment=MarketSegment(5, 8),
        origin=low(6, 105.0),
        previous=high(8, 120.0),
        pullback=low(9, 115.0),
    )

    first_result = evaluate_bms(
        first,
        [observed(5, high_price=111.0, low_price=96.0)],
    )
    second_result = evaluate_bms(
        second,
        [observed(10, high_price=121.0, low_price=116.0)],
    )

    assert first_result.breakout_index == 5
    assert second_result.breakout_index == 10


def test_nested_explicit_contexts_need_no_hierarchy_fields() -> None:
    outer = uptrend_context(pullback=low(8, 99.0))
    inner = downtrend_context(
        segment=MarketSegment(4, 7),
        origin=high(6, 106.0),
        previous=low(7, 100.0),
        pullback=high(8, 103.0),
    )
    shared_observation = observed(9, high_price=105.0, low_price=99.0)

    assert evaluate_bms(outer, [shared_observation]).status is (
        PullbackStructureStatus.PULLBACK_ONLY
    )
    assert evaluate_bms(inner, [shared_observation]).status is (
        PullbackStructureStatus.BMS_CONFIRMED
    )
```

- [ ] **Step 2: Run the ambiguity and result-invariant tests and verify RED**

Run: `pytest tests/test_pullback_structure.py -k "dual_boundary or result_requires" -v`

Expected: dual-boundary cases return `NOT_A_PULLBACK` instead of raising, and direct invalid `BMSResult` instances are accepted.

- [ ] **Step 3: Enforce result invariants and reject dual-boundary OHLC observations**

Add to `BMSResult` in `trading/definitions/pullback_structure.py`:

```python
    def __post_init__(self) -> None:
        has_break_details = (
            self.broken_extreme is not None and self.breakout_index is not None
        )
        has_partial_break_details = (
            self.broken_extreme is not None or self.breakout_index is not None
        )

        if (
            self.status is PullbackStructureStatus.BMS_CONFIRMED
            and not has_break_details
        ):
            raise ValueError("confirmed BMS requires broken extreme and breakout index")
        if (
            self.status is not PullbackStructureStatus.BMS_CONFIRMED
            and has_partial_break_details
        ):
            raise ValueError("non-BMS result cannot contain break details")
```

Inside the observation loop in `evaluate_bms()`, insert this branch immediately before the existing `if origin_crossed:` branch:

```python
        if origin_crossed and bms_crossed:
            raise ValueError(
                "OHLC cannot determine the intrabar boundary order"
            )
```

- [ ] **Step 4: Run the complete Task 4 coverage and verify GREEN**

Run: `pytest tests/test_pullback_structure.py -k "dual_boundary or exact_bms or exact_origin or wick_bms or downtrend_equality or result_requires or repeated_explicit or nested_explicit" -v`

Expected: all strict wick, equality, ambiguity, result-invariant, mirrored, repeated, and nested cases pass.

- [ ] **Step 5: Run all Level 1 and Lesson 1 regressions**

Run: `pytest tests/test_pullback_structure.py tests/test_market_structure.py -v`

Expected: all focused Lesson 2 and existing Lesson 1 tests pass.

- [ ] **Step 6: Commit the completed boundary semantics**

```bash
git add trading/definitions/pullback_structure.py tests/test_pullback_structure.py
git commit -m "Complete BMS boundary semantics"
```

---

### Task 5: Focused Lesson 1 + Lesson 2 Cross-Layer Integration

**Files:**
- Create: `tests/test_pullback_structure_integration.py`
- Do not modify: `trading/definitions/market_structure.py`
- Do not create: `tests/test_course_market_structure_scenarios.py`

**Interfaces:**
- Consumes: existing `classify_market_state(segment: MarketSegment, points: Sequence[StructurePoint]) -> MarketState` plus all approved Lesson 2 interfaces completed in Tasks 1-4.
- Produces: focused smoke evidence that an explicit Lesson 1 parent state composes with `PullbackContext`, a complete `BMSObservation` sequence, and `evaluate_bms()`.

- [ ] **Step 1: Verify the focused integration artifact is currently absent (RED)**

Run: `pytest tests/test_pullback_structure_integration.py -v`

Expected: pytest exits with `ERROR: file or directory not found: tests/test_pullback_structure_integration.py`. This is an integration-artifact RED: the required cross-layer smoke check does not yet exist.

- [ ] **Step 2: Create the four-case cross-layer smoke test**

Create `tests/test_pullback_structure_integration.py` with:

```python
from trading.definitions.candles import Candle
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    classify_market_state,
)
from trading.definitions.pullback_structure import (
    BMSObservation,
    PullbackContext,
    PullbackStructureStatus,
    evaluate_bms,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def observed(index: int, *, high_price: float, low_price: float) -> BMSObservation:
    midpoint = (high_price + low_price) / 2
    return BMSObservation(
        index,
        Candle(midpoint, high_price, low_price, midpoint),
    )


def classified_uptrend_context(
    *,
    pullback: StructurePoint = low(4, 100.0),
) -> PullbackContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 100.0),
        low(1, 90.0),
        low(2, 95.0),
        high(3, 110.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.UPTREND
    return PullbackContext(
        segment,
        parent_state,
        trend_origin=low(2, 95.0),
        previous_extreme=high(3, 110.0),
        pullback_extreme=pullback,
    )


def classified_downtrend_context() -> PullbackContext:
    segment = MarketSegment(0, 3)
    points = [
        high(0, 110.0),
        low(1, 100.0),
        high(2, 105.0),
        low(3, 90.0),
    ]
    parent_state = classify_market_state(segment, points)
    assert parent_state is MarketState.DOWNTREND
    return PullbackContext(
        segment,
        parent_state,
        trend_origin=high(2, 105.0),
        previous_extreme=low(3, 90.0),
        pullback_extreme=high(4, 100.0),
    )


def test_classified_uptrend_composes_with_confirmed_bms() -> None:
    context = classified_uptrend_context()
    observations = [observed(5, high_price=111.0, low_price=98.0)]

    assert evaluate_bms(context, observations).status is (
        PullbackStructureStatus.BMS_CONFIRMED
    )


def test_classified_downtrend_composes_with_confirmed_bms() -> None:
    context = classified_downtrend_context()
    observations = [observed(5, high_price=102.0, low_price=89.0)]

    assert evaluate_bms(context, observations).status is (
        PullbackStructureStatus.BMS_CONFIRMED
    )


def test_classified_parent_without_later_break_remains_pullback_only() -> None:
    context = classified_uptrend_context()
    observations = [observed(5, high_price=109.0, low_price=98.0)]

    assert evaluate_bms(context, observations).status is (
        PullbackStructureStatus.PULLBACK_ONLY
    )


def test_classified_parent_origin_invalidation_is_not_a_pullback() -> None:
    context = classified_uptrend_context(pullback=low(4, 94.0))

    assert evaluate_bms(context, ()).status is (
        PullbackStructureStatus.NOT_A_PULLBACK
    )
```

- [ ] **Step 3: Run the focused cross-layer integration check and verify GREEN**

Run: `pytest tests/test_pullback_structure_integration.py -v`

Expected: all four Lesson 1 + Lesson 2 composition tests pass.

- [ ] **Step 4: Run Level 1 and focused integration together**

Run: `pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v`

Expected: all focused BMS unit and cross-layer smoke tests pass.

- [ ] **Step 5: Run the Lesson 1 regression beside the new smoke check**

Run: `pytest tests/test_market_structure.py tests/test_pullback_structure_integration.py -v`

Expected: all existing Lesson 1 tests and the four composition tests pass.

- [ ] **Step 6: Commit the focused integration task**

```bash
git add tests/test_pullback_structure_integration.py
git commit -m "Add BMS cross-layer integration tests"
```

---

### Task 6: Full BMS Regression, Scope, and Continuation Gate Verification

**Files:**
- Verify: `trading/definitions/pullback_structure.py`
- Verify: `tests/test_pullback_structure.py`
- Verify: `tests/test_pullback_structure_integration.py`
- Verify unchanged: `trading/definitions/market_structure.py`

**Interfaces:**
- Consumes: all Task 1-5 implementation commits.
- Produces: fresh evidence that BMS Level 1 tests, the focused Lesson 1 + Lesson 2 integration check, and the complete repository regression suite pass with design-limited scope.

- [ ] **Step 1: Run the complete Level 1 BMS unit suite**

Run: `pytest tests/test_pullback_structure.py -v`

Expected: all focused BMS pullback unit tests pass.

- [ ] **Step 2: Run the focused Lesson 1 + Lesson 2 integration check**

Run: `pytest tests/test_pullback_structure_integration.py -v`

Expected: all four cross-layer smoke tests pass.

- [ ] **Step 3: Run the complete repository test suite**

Run: `pytest`

Expected: the entire test suite passes with zero failures.

- [ ] **Step 4: Check formatting and whitespace**

Run: `git diff --check 1da60f33165740ab3300b7fe5eb5c159cbcdc353..HEAD`

Expected: exit code 0 with no whitespace errors.

- [ ] **Step 5: Verify the complete implementation scope**

Run: `git diff --name-only 1da60f33165740ab3300b7fe5eb5c159cbcdc353..HEAD`

Expected paths only:

```text
docs/superpowers/plans/2026-08-29-bms-pullback-structure.md
docs/superpowers/specs/2026-08-29-bms-pullback-structure-design.md
tests/test_pullback_structure.py
tests/test_pullback_structure_integration.py
trading/definitions/pullback_structure.py
```

The two documentation paths contain this approved validation-timing revision. The three implementation paths contain only BMS production, Level 1 unit, and focused integration work.

- [ ] **Step 6: Prove Lesson 1 production behavior was not edited**

Run: `git diff --exit-code 1da60f33165740ab3300b7fe5eb5c159cbcdc353..HEAD -- trading/definitions/market_structure.py`

Expected: exit code 0 and no diff.

- [ ] **Step 7: Inspect the implementation commits**

Run: `git log --oneline 1da60f33165740ab3300b7fe5eb5c159cbcdc353..HEAD`

Expected: the validation-timing documentation revision plus the five focused implementation/test commits from Tasks 1-5. Review any additional fix commit rather than rewriting or hiding valid history.

- [ ] **Step 8: Enforce the BMS completion gate**

Record BMS completion only when all three conditions are true:

```text
Level 1 BMS unit tests: PASS
Lesson 1 + Lesson 2 integration smoke tests: PASS
Full repository regression suite: PASS
```

After these conditions, Chapter 2 may continue to Lesson 3. Do not claim that the complete Chapter 2 market-structure model has been validated.

No Task 6 commit is expected when verification is clean because this task changes no files. If verification exposes an in-scope defect, return to the relevant earlier task, reproduce RED, make the minimum correction, rerun its targeted and regression commands, and commit the correction with a message describing the actual behavior fixed.


## Future Mandatory Level 2 Chapter-Completion Gate

Formal Level 2 course-scenario validation is not part of BMS implementation. After every Chapter 2 market-structure lesson is implemented:

1. review the complete Chapter 2 course material;
2. design comprehensive hand-labelled scenarios using only concepts actually taught;
3. create or update `tests/test_course_market_structure_scenarios.py`;
4. test all relevant Chapter 2 structure layers together;
5. run the full regression suite; and
6. only then call the Chapter 2 market-structure foundation validated.

The future suite may cover trend/non-trend, pullbacks, BMS, later reversal structures, short-, medium-, and long-term structure, cycles/timeframes, levels/hierarchy, nested structures, and other relationships actually defined by the completed chapter. Do not invent their behavior or detailed scenarios in this Lesson 2 plan.

## Conditional Level 3 Validation Milestone

At the end of Chapter 2, reassess whether the course has supplied legitimate rules for automatically extracting:

- short-term structure;
- medium-term structure;
- long-term structure;
- cycles/timeframes;
- levels/hierarchy; and
- structural points and zig-zags.

If the rules are sufficient, design a later end-to-end validation phase:

```text
raw historical candles
        |
        v
automatic structure extraction
        |
        v
trend
        |
        v
pullback
        |
        v
BMS and later market structures
        |
        v
comparison with manually labelled teacher/course examples
```

If the course still lacks sufficient extraction rules, keep Level 3 deferred. Do not invent swing or hierarchy logic to force this milestone.
