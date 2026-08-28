# Market Structure Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Chapter 2, Lesson 1 market-structure vocabulary, relationship comparison, explicit-segment trend classification, and strict two-candle outside-bar recognition without inferring structural points or trading decisions.

**Architecture:** Add one focused `trading.definitions.market_structure` module. It accepts an explicit inclusive `MarketSegment` plus caller-supplied chronological `StructurePoint` objects, derives adjacent same-kind relationships without sorting, and classifies the complete selected segment; the module also owns the simple outside-bar predicate while reusing the existing Chapter 1 inside-bar predicate unchanged.

**Tech Stack:** Python standard library (`collections.abc`, `dataclasses`, `enum`), pytest, existing `trading.definitions.candles.Candle`, and existing `trading.definitions.isolated_point_deformations.is_inside_bar`.

**Spec:** `docs/superpowers/specs/2026-08-28-market-structure-foundation-design.md`

## Global Constraints

- Implement only Chapter 2, Lesson 1: Trend and Non-Trend.
- Every market-state classification call must receive an explicit `MarketSegment`; never infer a segment from history or points.
- Segment boundaries are inclusive: `start_index <= point.index <= end_index`.
- Structural points are supplied explicitly; never scan candles or map isolated points to structure points.
- The minimum trend contains exactly two highs and two lows: one high relationship and one low relationship.
- Preserve caller chronology; never sort points by index or price.
- For more than two same-kind points, every adjacent relationship must continue the claimed direction; never skip an intermediate point.
- Equality is explicit and non-directional and therefore breaks trend continuity.
- Keep Chapter 1 isolated-point semantics and files unchanged.
- Reuse `trading.definitions.isolated_point_deformations.is_inside_bar`; do not duplicate it.
- Outside-bar recognition compares exactly two candles with strict inequalities and does not create a multi-candle range algorithm.
- Do not add automatic swing extraction, isolated-point mapping, BMS, BOS, CHOCH, timeframe or segment selection, strategy, signals, entries, exits, position management, execution, or broker integration.
- This plan creates no package-level re-exports because the repository currently imports definition modules directly.

## Course Minimum

The minimum uptrend is one relationship from two highs plus one relationship from two lows:

```text
H1 -> H2 = HIGHER_HIGH
L1 -> L2 = HIGHER_LOW
```

The minimum downtrend is one relationship from two highs plus one relationship from two lows:

```text
H1 -> H2 = LOWER_HIGH
L1 -> L2 = LOWER_LOW
```

Neither definition requires an `H3` or `L3`. Longer segments are valid only when every additional adjacent same-kind relationship continues the claimed direction.

## File Map

- Create `trading/definitions/market_structure.py`: immutable market-structure domain types, relationship comparison, explicit-segment classification, and strict outside-bar recognition.
- Create `tests/test_market_structure.py`: focused domain, validation, relationship, classification, outside-bar, and inside-bar compatibility tests.
- Do not modify `trading/definitions/isolated_points.py` or `trading/definitions/isolated_point_deformations.py`.

---

### Task 1: Core Domain Model and Segment Validation

**Files:**
- Create: `trading/definitions/market_structure.py`
- Create: `tests/test_market_structure.py`

**Interfaces:**
- Consumes: no new project interfaces.
- Produces: `MarketSegment(start_index: int, end_index: int)`, `StructurePointKind`, `StructurePoint(index: int, kind: StructurePointKind, price: float)`, `StructureRelationship`, and `MarketState`.

- [ ] **Step 1: Write the failing domain-model tests**

Create `tests/test_market_structure.py` with:

```python
from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
    StructurePointKind,
    StructureRelationship,
)


def high(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.HIGH, price)


def low(index: int, price: float) -> StructurePoint:
    return StructurePoint(index, StructurePointKind.LOW, price)


def test_market_segment_accepts_inclusive_equal_boundaries() -> None:
    assert MarketSegment(4, 4) == MarketSegment(start_index=4, end_index=4)


@pytest.mark.parametrize(("start_index", "end_index"), [(2, 1), (1, -1)])
def test_market_segment_rejects_start_after_end(
    start_index: int,
    end_index: int,
) -> None:
    with pytest.raises(ValueError, match="start_index"):
        MarketSegment(start_index, end_index)


def test_market_structure_enum_values_are_stable() -> None:
    assert {kind.value for kind in StructurePointKind} == {"high", "low"}
    assert {relationship.value for relationship in StructureRelationship} == {
        "higher_high",
        "lower_high",
        "equal_high",
        "higher_low",
        "lower_low",
        "equal_low",
    }
    assert {state.value for state in MarketState} == {
        "uptrend",
        "downtrend",
        "non_trend",
    }


def test_structure_point_preserves_caller_supplied_values() -> None:
    assert high(7, 112.5) == StructurePoint(
        index=7,
        kind=StructurePointKind.HIGH,
        price=112.5,
    )


@pytest.mark.parametrize(
    "instance",
    [MarketSegment(0, 2), high(0, 100.0), low(1, 90.0)],
)
def test_market_structure_dataclasses_are_frozen(instance: object) -> None:
    with pytest.raises(FrozenInstanceError):
        instance.index = 99  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run the new test module and verify RED**

Run: `pytest tests/test_market_structure.py -v`

Expected: test collection fails with `ModuleNotFoundError: No module named 'trading.definitions.market_structure'` because the domain module does not exist yet.

- [ ] **Step 3: Implement the immutable domain model and boundary validation**

Create `trading/definitions/market_structure.py` with:

```python
"""Explicit, segment-relative Chapter 2 market-structure definitions."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class MarketSegment:
    """Inclusive candle-index boundaries selected by the caller."""

    start_index: int
    end_index: int

    def __post_init__(self) -> None:
        if self.start_index > self.end_index:
            raise ValueError("start_index must not be after end_index")


class StructurePointKind(Enum):
    """Whether an explicitly supplied structural point is a high or low."""

    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True)
class StructurePoint:
    """A structural price point already identified by the caller."""

    index: int
    kind: StructurePointKind
    price: float


class StructureRelationship(Enum):
    """The directional relationship between chronological same-kind points."""

    HIGHER_HIGH = "higher_high"
    LOWER_HIGH = "lower_high"
    EQUAL_HIGH = "equal_high"
    HIGHER_LOW = "higher_low"
    LOWER_LOW = "lower_low"
    EQUAL_LOW = "equal_low"


class MarketState(Enum):
    """The course-defined state of one explicit market segment."""

    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    NON_TREND = "non_trend"
```

- [ ] **Step 4: Run the domain-model tests and verify GREEN**

Run: `pytest tests/test_market_structure.py -v`

Expected: all Task 1 tests pass.

- [ ] **Step 5: Run the Chapter 1 isolation regressions**

Run: `pytest tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v`

Expected: all existing strict and deformation-aware isolated-point tests pass unchanged.

- [ ] **Step 6: Commit the domain-model task**

```bash
git add trading/definitions/market_structure.py tests/test_market_structure.py
git commit -m "Add market structure domain model"
```

---

### Task 2: Structure-Point Relationship Comparison

**Files:**
- Modify: `trading/definitions/market_structure.py`
- Modify: `tests/test_market_structure.py`

**Interfaces:**
- Consumes: `StructurePoint`, `StructurePointKind`, and `StructureRelationship` from Task 1.
- Produces: `compare_structure_points(previous: StructurePoint, later: StructurePoint) -> StructureRelationship`.

- [ ] **Step 1: Write failing relationship tests**

Add `compare_structure_points` to the import block in `tests/test_market_structure.py`, then append:

```python
@pytest.mark.parametrize(
    ("previous", "later", "expected"),
    [
        (high(1, 100.0), high(2, 110.0), StructureRelationship.HIGHER_HIGH),
        (high(1, 100.0), high(2, 90.0), StructureRelationship.LOWER_HIGH),
        (high(1, 100.0), high(2, 100.0), StructureRelationship.EQUAL_HIGH),
        (low(1, 90.0), low(2, 95.0), StructureRelationship.HIGHER_LOW),
        (low(1, 90.0), low(2, 85.0), StructureRelationship.LOWER_LOW),
        (low(1, 90.0), low(2, 90.0), StructureRelationship.EQUAL_LOW),
    ],
)
def test_compare_structure_points_returns_same_kind_relationship(
    previous: StructurePoint,
    later: StructurePoint,
    expected: StructureRelationship,
) -> None:
    assert compare_structure_points(previous, later) is expected


def test_compare_structure_points_rejects_different_kinds() -> None:
    with pytest.raises(ValueError, match="same kind"):
        compare_structure_points(high(1, 100.0), low(2, 90.0))


@pytest.mark.parametrize("later_index", [3, 2])
def test_compare_structure_points_rejects_non_increasing_chronology(
    later_index: int,
) -> None:
    with pytest.raises(ValueError, match="chronological"):
        compare_structure_points(high(3, 100.0), high(later_index, 110.0))
```

- [ ] **Step 2: Run the relationship tests and verify RED**

Run: `pytest tests/test_market_structure.py -k "compare_structure_points" -v`

Expected: collection fails with `ImportError: cannot import name 'compare_structure_points'` because the function has not been added.

- [ ] **Step 3: Implement deterministic same-kind comparison**

Append to `trading/definitions/market_structure.py`:

```python
def compare_structure_points(
    previous: StructurePoint,
    later: StructurePoint,
) -> StructureRelationship:
    """Compare chronological structural points of the same kind."""

    if previous.kind is not later.kind:
        raise ValueError("structure-point comparison requires the same kind")
    if later.index <= previous.index:
        raise ValueError("same-kind structure points must be chronological")

    if previous.kind is StructurePointKind.HIGH:
        if later.price > previous.price:
            return StructureRelationship.HIGHER_HIGH
        if later.price < previous.price:
            return StructureRelationship.LOWER_HIGH
        return StructureRelationship.EQUAL_HIGH

    if later.price > previous.price:
        return StructureRelationship.HIGHER_LOW
    if later.price < previous.price:
        return StructureRelationship.LOWER_LOW
    return StructureRelationship.EQUAL_LOW
```

- [ ] **Step 4: Run the relationship tests and verify GREEN**

Run: `pytest tests/test_market_structure.py -k "compare_structure_points" -v`

Expected: all six directional/equality cases and both validation groups pass.

- [ ] **Step 5: Run all market-structure tests and Chapter 1 regressions**

Run: `pytest tests/test_market_structure.py tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v`

Expected: all tests pass; no Chapter 1 behavior changes.

- [ ] **Step 6: Commit the relationship task**

```bash
git add trading/definitions/market_structure.py tests/test_market_structure.py
git commit -m "Add structure point relationships"
```

---

### Task 3: Explicit-Segment Market-State Classification

**Files:**
- Modify: `trading/definitions/market_structure.py`
- Modify: `tests/test_market_structure.py`

**Interfaces:**
- Consumes: `MarketSegment`, `MarketState`, `StructurePoint`, `StructurePointKind`, `StructureRelationship`, and `compare_structure_points(...)` from Tasks 1-2.
- Produces: `classify_market_state(segment: MarketSegment, points: Sequence[StructurePoint]) -> MarketState`.
- Internal invariant helper: `_resolve_market_state(uptrend: bool, downtrend: bool) -> MarketState`; it exists only to make the contradictory-candidate rejection directly testable.

- [ ] **Step 1: Write the failing minimum and extended trend tests**

Add `classify_market_state` to the import block in `tests/test_market_structure.py`, then append:

```python
def test_classify_market_state_accepts_minimum_uptrend() -> None:
    points = [
        high(0, 100.0),
        low(1, 90.0),
        high(2, 110.0),
        low(3, 95.0),
    ]

    assert classify_market_state(MarketSegment(0, 3), points) is MarketState.UPTREND


def test_classify_market_state_accepts_minimum_downtrend() -> None:
    points = [
        high(0, 110.0),
        low(1, 100.0),
        high(2, 105.0),
        low(3, 90.0),
    ]

    assert classify_market_state(MarketSegment(0, 3), points) is MarketState.DOWNTREND


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        (
            [
                high(0, 100.0),
                low(1, 90.0),
                high(2, 110.0),
                low(3, 95.0),
                high(4, 120.0),
                low(5, 100.0),
            ],
            MarketState.UPTREND,
        ),
        (
            [
                high(0, 120.0),
                low(1, 100.0),
                high(2, 110.0),
                low(3, 90.0),
                high(4, 105.0),
                low(5, 80.0),
            ],
            MarketState.DOWNTREND,
        ),
    ],
)
def test_classify_market_state_accepts_extended_continuous_trends(
    points: list[StructurePoint],
    expected: MarketState,
) -> None:
    assert classify_market_state(MarketSegment(0, 5), points) is expected
```

- [ ] **Step 2: Write the failing non-trend and no-skipping tests**

Append to `tests/test_market_structure.py`:

```python
@pytest.mark.parametrize(
    "points",
    [
        [],
        [high(0, 100.0), low(1, 90.0), low(2, 95.0)],
        [high(0, 100.0), high(1, 110.0), low(2, 90.0)],
    ],
)
def test_classify_market_state_returns_non_trend_for_insufficient_points(
    points: list[StructurePoint],
) -> None:
    assert classify_market_state(MarketSegment(0, 2), points) is MarketState.NON_TREND


@pytest.mark.parametrize(
    "points",
    [
        [high(0, 100.0), low(1, 90.0), high(2, 100.0), low(3, 95.0)],
        [high(0, 100.0), low(1, 90.0), high(2, 110.0), low(3, 90.0)],
    ],
)
def test_classify_market_state_returns_non_trend_for_equality(
    points: list[StructurePoint],
) -> None:
    assert classify_market_state(MarketSegment(0, 3), points) is MarketState.NON_TREND


def test_classify_market_state_rejects_interrupted_direction_as_non_trend() -> None:
    points = [
        high(0, 100.0),
        low(1, 90.0),
        high(2, 110.0),
        low(3, 95.0),
        high(4, 105.0),
        low(5, 100.0),
    ]

    assert classify_market_state(MarketSegment(0, 5), points) is MarketState.NON_TREND


def test_classify_market_state_does_not_skip_intermediate_same_kind_point() -> None:
    points = [
        high(0, 100.0),
        low(1, 90.0),
        high(2, 95.0),
        low(3, 100.0),
        high(4, 110.0),
        low(5, 105.0),
    ]

    assert classify_market_state(MarketSegment(0, 5), points) is MarketState.NON_TREND
```

- [ ] **Step 3: Write the failing explicit-segment and chronology tests**

Append to `tests/test_market_structure.py`:

```python
def test_classify_market_state_requires_explicit_segment() -> None:
    points = [high(0, 100.0), low(1, 90.0), high(2, 110.0), low(3, 95.0)]

    with pytest.raises(TypeError):
        classify_market_state(points)  # type: ignore[call-arg]


def test_classify_market_state_includes_segment_boundaries() -> None:
    points = [high(10, 100.0), low(11, 90.0), high(12, 110.0), low(13, 95.0)]

    assert classify_market_state(MarketSegment(10, 13), points) is MarketState.UPTREND


@pytest.mark.parametrize(
    ("segment", "points"),
    [
        (
            MarketSegment(0, 3),
            [high(-1, 100.0), low(0, 90.0), high(1, 110.0), low(2, 95.0)],
        ),
        (
            MarketSegment(0, 2),
            [high(0, 100.0), low(1, 90.0), high(2, 110.0), low(3, 95.0)],
        ),
    ],
)
def test_classify_market_state_rejects_out_of_segment_points(
    segment: MarketSegment,
    points: list[StructurePoint],
) -> None:
    with pytest.raises(ValueError, match="outside segment"):
        classify_market_state(segment, points)


def test_classify_market_state_rejects_decreasing_caller_order() -> None:
    points = [high(0, 100.0), low(2, 90.0), high(1, 110.0), low(3, 95.0)]

    with pytest.raises(ValueError, match="chronological"):
        classify_market_state(MarketSegment(0, 3), points)


def test_classify_market_state_rejects_duplicate_same_kind_index() -> None:
    points = [high(0, 100.0), low(0, 90.0), high(0, 110.0), low(1, 95.0)]

    with pytest.raises(ValueError, match="same-kind"):
        classify_market_state(MarketSegment(0, 1), points)


def test_classify_market_state_allows_high_and_low_at_same_index() -> None:
    points = [high(0, 100.0), low(0, 90.0), high(1, 110.0), low(1, 95.0)]

    assert classify_market_state(MarketSegment(0, 1), points) is MarketState.UPTREND
```

- [ ] **Step 4: Write the failing contradictory-candidate invariant test**

Add this module import near the top of `tests/test_market_structure.py`:

```python
from trading.definitions import market_structure
```

Then append:

```python
def test_market_state_resolution_rejects_contradictory_candidates() -> None:
    with pytest.raises(ValueError, match="contradictory"):
        market_structure._resolve_market_state(uptrend=True, downtrend=True)
```

- [ ] **Step 5: Run the classification tests and verify RED**

Run: `pytest tests/test_market_structure.py -k "classify_market_state or market_state_resolution" -v`

Expected: collection fails with `ImportError: cannot import name 'classify_market_state'` because classification has not been implemented.

- [ ] **Step 6: Implement explicit validation and whole-segment classification**

Add `from collections.abc import Sequence` to `trading/definitions/market_structure.py`, then append:

```python
def _validate_segment_points(
    segment: MarketSegment,
    points: Sequence[StructurePoint],
) -> None:
    previous_index: int | None = None
    seen_same_kind_indexes: set[tuple[int, StructurePointKind]] = set()

    for point in points:
        if not segment.start_index <= point.index <= segment.end_index:
            raise ValueError("structure point is outside segment")
        if previous_index is not None and point.index < previous_index:
            raise ValueError("structure points must be chronological")

        point_identity = (point.index, point.kind)
        if point_identity in seen_same_kind_indexes:
            raise ValueError("duplicate same-kind structure-point index")
        seen_same_kind_indexes.add(point_identity)
        previous_index = point.index


def _relationships_for_kind(
    points: Sequence[StructurePoint],
    kind: StructurePointKind,
) -> list[StructureRelationship]:
    same_kind_points = [point for point in points if point.kind is kind]
    return [
        compare_structure_points(previous, later)
        for previous, later in zip(same_kind_points, same_kind_points[1:])
    ]


def _all_relationships_are(
    relationships: Sequence[StructureRelationship],
    expected: StructureRelationship,
) -> bool:
    return bool(relationships) and all(
        relationship is expected for relationship in relationships
    )


def _resolve_market_state(uptrend: bool, downtrend: bool) -> MarketState:
    if uptrend and downtrend:
        raise ValueError("contradictory market-state candidates")
    if uptrend:
        return MarketState.UPTREND
    if downtrend:
        return MarketState.DOWNTREND
    return MarketState.NON_TREND


def classify_market_state(
    segment: MarketSegment,
    points: Sequence[StructurePoint],
) -> MarketState:
    """Classify one explicit segment from supplied chronological points."""

    _validate_segment_points(segment, points)
    high_relationships = _relationships_for_kind(points, StructurePointKind.HIGH)
    low_relationships = _relationships_for_kind(points, StructurePointKind.LOW)

    uptrend = _all_relationships_are(
        high_relationships,
        StructureRelationship.HIGHER_HIGH,
    ) and _all_relationships_are(
        low_relationships,
        StructureRelationship.HIGHER_LOW,
    )
    downtrend = _all_relationships_are(
        high_relationships,
        StructureRelationship.LOWER_HIGH,
    ) and _all_relationships_are(
        low_relationships,
        StructureRelationship.LOWER_LOW,
    )
    return _resolve_market_state(uptrend, downtrend)
```

This implementation deliberately uses every adjacent same-kind relationship. With exactly two highs and two lows, each relationship list has length one, which preserves the course's four-point minimum.

- [ ] **Step 7: Run the classification tests and verify GREEN**

Run: `pytest tests/test_market_structure.py -k "classify_market_state or market_state_resolution" -v`

Expected: minimum four-point trends, extended trends, non-trends, explicit boundaries, chronology validation, no-skipping behavior, and the contradictory-candidate guard all pass.

- [ ] **Step 8: Run all market-structure tests and Chapter 1 regressions**

Run: `pytest tests/test_market_structure.py tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v`

Expected: all tests pass and existing isolated-point behavior remains unchanged.

- [ ] **Step 9: Commit the classification task**

```bash
git add trading/definitions/market_structure.py tests/test_market_structure.py
git commit -m "Add explicit market state classification"
```

---

### Task 4: Outside-Bar Recognition and Inside-Bar Compatibility

**Files:**
- Modify: `trading/definitions/market_structure.py`
- Modify: `tests/test_market_structure.py`
- Verify unchanged: `trading/definitions/isolated_point_deformations.py`

**Interfaces:**
- Consumes: `trading.definitions.candles.Candle` and existing `trading.definitions.isolated_point_deformations.is_inside_bar(outer: Candle, inner: Candle) -> bool`.
- Produces: `is_outside_bar(left: Candle, right: Candle) -> bool`.

- [ ] **Step 1: Write failing outside-bar tests and inside-bar regressions**

Add these imports to `tests/test_market_structure.py`:

```python
from trading.definitions.candles import Candle
from trading.definitions.isolated_point_deformations import is_inside_bar
```

Add `is_outside_bar` to the `trading.definitions.market_structure` import block. Then add this helper and the tests:

```python
def make_candle(high_price: float, low_price: float, bullish: bool) -> Candle:
    lower_body = low_price + (high_price - low_price) * 0.25
    upper_body = low_price + (high_price - low_price) * 0.75
    open_price, close_price = (
        (lower_body, upper_body)
        if bullish
        else (upper_body, lower_body)
    )
    return Candle(open_price, high_price, low_price, close_price)


@pytest.mark.parametrize("bullish", [True, False])
def test_is_outside_bar_uses_strict_range_not_candle_color(bullish: bool) -> None:
    left = make_candle(10.0, 5.0, bullish=not bullish)
    right = make_candle(11.0, 4.0, bullish=bullish)

    assert is_outside_bar(left, right) is True


@pytest.mark.parametrize(
    "right",
    [
        make_candle(10.0, 4.0, bullish=True),
        make_candle(11.0, 5.0, bullish=False),
        make_candle(10.0, 5.0, bullish=True),
    ],
)
def test_is_outside_bar_rejects_equal_boundary(right: Candle) -> None:
    assert is_outside_bar(make_candle(10.0, 5.0, bullish=True), right) is False


@pytest.mark.parametrize(
    "right",
    [
        make_candle(9.0, 4.0, bullish=True),
        make_candle(11.0, 6.0, bullish=False),
        make_candle(9.0, 6.0, bullish=True),
    ],
)
def test_is_outside_bar_requires_both_extremes_to_break(right: Candle) -> None:
    assert is_outside_bar(make_candle(10.0, 5.0, bullish=False), right) is False


def test_multiple_later_candles_can_share_one_inside_bar_mother() -> None:
    mother = make_candle(12.0, 7.0, bullish=True)
    later_candles = [
        make_candle(11.0, 8.0, bullish=True),
        make_candle(12.0, 8.0, bullish=False),
        make_candle(11.0, 7.0, bullish=True),
    ]

    assert [is_inside_bar(mother, candle) for candle in later_candles] == [
        True,
        True,
        True,
    ]
```

- [ ] **Step 2: Run the bar-recognition tests and verify RED**

Run: `pytest tests/test_market_structure.py -k "outside_bar or inside_bar" -v`

Expected: collection fails with `ImportError: cannot import name 'is_outside_bar'`; the inside-bar regression already targets the existing Chapter 1 helper and requires no replacement implementation.

- [ ] **Step 3: Implement only the strict two-candle outside predicate**

Add this import to `trading/definitions/market_structure.py`:

```python
from .candles import Candle
```

Append:

```python
def is_outside_bar(left: Candle, right: Candle) -> bool:
    """Return whether the right candle strictly contains the left range."""

    return right.high > left.high and right.low < left.low
```

Do not add a sequence-based overload, mother-range tracker, candle-color branch, or call to `is_inside_bar` from production code.

- [ ] **Step 4: Run the bar-recognition tests and verify GREEN**

Run: `pytest tests/test_market_structure.py -k "outside_bar or inside_bar" -v`

Expected: all strict outside-bar cases and the shared-mother inside-bar regression pass.

- [ ] **Step 5: Run the complete focused market-structure module**

Run: `pytest tests/test_market_structure.py -v`

Expected: every Task 1-4 market-structure test passes.

- [ ] **Step 6: Run the existing inside-bar and isolated-point regressions**

Run: `pytest tests/test_isolated_point_deformations.py tests/test_isolated_points.py -v`

Expected: all Chapter 1 tests pass without modifying their production modules.

- [ ] **Step 7: Commit the bar-recognition task**

```bash
git add trading/definitions/market_structure.py tests/test_market_structure.py
git commit -m "Add market structure bar recognition"
```

---

### Task 5: Full Verification and Scope Audit

**Files:**
- Verify: `trading/definitions/market_structure.py`
- Verify: `tests/test_market_structure.py`
- Verify unchanged: `trading/definitions/isolated_points.py`
- Verify unchanged: `trading/definitions/isolated_point_deformations.py`

**Interfaces:**
- Consumes: the four committed task deliverables.
- Produces: verification evidence only; no additional behavior or commit.

- [ ] **Step 1: Run the complete test suite**

Run: `pytest`

Expected: the complete repository suite passes with zero failures or errors. Do not claim implementation completion if this command fails.

- [ ] **Step 2: Check patch formatting**

Run: `git diff --check HEAD~4..HEAD`

Expected: no output and exit code 0.

- [ ] **Step 3: Verify the implementation changed only the two planned files**

Run: `git diff --name-only HEAD~4..HEAD`

Expected output contains exactly:

```text
tests/test_market_structure.py
trading/definitions/market_structure.py
```

- [ ] **Step 4: Verify Chapter 1 production modules are unchanged**

Run: `git diff --exit-code HEAD~4..HEAD -- trading/definitions/isolated_points.py trading/definitions/isolated_point_deformations.py`

Expected: no output and exit code 0.

- [ ] **Step 5: Confirm the implementation commit sequence and clean worktree**

Run: `git log -4 --oneline`

Expected: four commits in reverse order for bar recognition, classification, relationships, and the domain model.

Run: `git status --short`

Expected: no output. The implementation is ready for review only after both the full suite and the clean-worktree check succeed.
