# Short-Term Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the course-defined Chapter 2 Lesson 5 short-term structure layer by mapping confirmed isolated points to short-term points and normalizing them into a deterministic structure line while preserving all valid point evidence.

**Architecture:** Reuse the existing isolated-point recognition layer. Add a dedicated short-term domain layer that separates all confirmed short-term points from normalized line vertices and records objective suppressions. The builder consumes confirmed short-term points rather than rescanning raw candles.

**Tech Stack:** Python, dataclasses, Enum, pytest.

**Spec:** docs/superpowers/specs/2026-08-30-short-term-structure-design.md

## Global Constraints

- Implement Chapter 2, Lesson 5 short-term structure only.
- Reuse `trading/definitions/isolated_points.py` and `trading/definitions/isolated_point_deformations.py` as the single source of truth for strict and supported deformation-aware recognition.
- Only `IsolatedPointStatus.CONFIRMED` points may map to short-term points; reject `POTENTIAL` inputs.
- A bare confirmed `IsolatedPoint` maps with `recognition_basis=None`; never recompute recognition.
- An `IsolatedPointRecognition` maps with its exact `recognition.basis`.
- Preserve every valid short-term point in `ShortTermStructure.points`, including points suppressed from the final line.
- Connect and normalize short-term points only; do not infer or mix medium-term or long-term points.
- Period and structural level remain distinct; do not map 1-hour, 4-hour, daily, or any other timeframe to a structural level.
- Validate the complete input chronology before normalization: indexes must be strictly increasing, duplicate indexes are invalid, and caller input is never silently sorted.
- Consecutive `HIGH` runs retain the highest price as the vertex; consecutive `LOW` runs retain the lowest price.
- Equal highest `HIGH` or equal lowest `LOW` ties use the approved neutral engineering tie-break: retain the earliest tied extreme as the vertex and suppress later ties only from the line with `CONSECUTIVE_SAME_KIND`.
- Inside suppression requires both inclusive conditions: `later_high <= earlier_high` and `later_low >= earlier_low`.
- Equality at either inside boundary counts as contained; a breakout on either side prevents inside suppression.
- Apply only definite inside normalization repeatedly from left to right until stable.
- Preserve layouts that do not define comparable chronological opposite-kind ranges; do not invent pairings.
- Do not add ATR, percentage, minimum-distance, candle-count, or swing-strength thresholds.
- Do not add nearest-point selection, discretionary importance scoring, new deformation recognition, raw intrabar reconstruction, or automatic BMS/SMS dispute resolution.
- Do not infer medium-term or long-term structure, parent/child hierarchy, creator points, trend extremes, trend reversal, trading ranges, or cross-level propagation.
- Do not add a production short/medium/long level enum or any medium-term or long-term module.
- Do not add strategy, signal, entry, exit, stop-loss, risk, sizing, leverage, broker, order, execution, or trader-profile logic.
- Do not change existing Lesson 1 market-state, Lesson 2 BMS, or Lesson 3 SMS semantics.
- Do not create `tests/test_course_market_structure_scenarios.py`; formal Chapter 2 Level 2 validation remains deferred until all Chapter 2 lessons are complete.
- Actual implementation must not occur on `main`. At execution time use `superpowers:using-git-worktrees`, create an isolated `feature/short-term-structure` branch/worktree, and keep `main` unchanged until independent GitHub review approves integration.
- Use red-to-green TDD for every behavior, review every task for spec compliance and code quality, and run a broad final whole-branch review before integration.

---

## File Structure

Create exactly these implementation artifacts unless a verified integration defect requires a narrowly scoped change:

- `trading/definitions/short_term_structure.py` — immutable Lesson 5 domain records, confirmed-point mapping, chronology validation, and deterministic short-term line normalization.
- `tests/test_short_term_structure.py` — focused unit coverage for mapping, records, chronology, same-kind runs, ties, inside structures, repeated normalization, and ambiguity preservation.
- `tests/test_short_term_structure_integration.py` — real Chapter 1 recognition-to-Lesson 5 composition using strict and right-inside-bar paths.

Do not modify existing production modules merely to re-export the new API. Consumers import directly from `trading.definitions.short_term_structure`, matching current module-level import style.

## Locked Public API

```python
class ShortTermSuppressionReason(Enum):
    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


@dataclass(frozen=True)
class ShortTermPoint:
    index: int
    kind: IsolatedPointKind
    price: float
    recognition_basis: IsolatedPointBasis | None = None


@dataclass(frozen=True)
class SuppressedShortTermPoint:
    point: ShortTermPoint
    reason: ShortTermSuppressionReason


@dataclass(frozen=True)
class ShortTermStructure:
    points: tuple[ShortTermPoint, ...]
    vertices: tuple[ShortTermPoint, ...]
    suppressed: tuple[SuppressedShortTermPoint, ...]
```

Exact public function signatures:

```text
short_term_point_from_isolated_point(point: IsolatedPoint) -> ShortTermPoint
short_term_point_from_recognition(recognition: IsolatedPointRecognition) -> ShortTermPoint
build_short_term_structure(points: Sequence[ShortTermPoint]) -> ShortTermStructure
```

Exact validation messages selected by this plan:

```text
short-term point mapping requires a confirmed isolated point
short-term point indexes must be strictly increasing
```

Suppression ordering is deterministic:

1. same-kind suppressions appear in original point chronology;
2. inside-structure suppressions follow in left-to-right removal order; and
3. the two points of one suppressed inside pair are recorded in their chronological order.

---

### Task 1: Short-Term Domain Model and Confirmed-Point Mapping

**Files:**
- Create: `trading/definitions/short_term_structure.py`
- Create: `tests/test_short_term_structure.py`

**Interfaces:**
- Consumes: `IsolatedPoint`, `IsolatedPointKind`, and `IsolatedPointStatus` from `trading.definitions.isolated_points`; `IsolatedPointBasis` and `IsolatedPointRecognition` from `trading.definitions.isolated_point_deformations`.
- Produces: `ShortTermSuppressionReason`, `ShortTermPoint`, `SuppressedShortTermPoint`, `ShortTermStructure`, `short_term_point_from_isolated_point(point: IsolatedPoint) -> ShortTermPoint`, and `short_term_point_from_recognition(recognition: IsolatedPointRecognition) -> ShortTermPoint`.

- [ ] **Step 1: Write the domain and mapping tests first**

Create `tests/test_short_term_structure.py` with these initial tests:

```python
from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from trading.definitions.isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    ShortTermSuppressionReason,
    SuppressedShortTermPoint,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def isolated_point(
    *,
    index: int = 3,
    kind: IsolatedPointKind = IsolatedPointKind.HIGH,
    status: IsolatedPointStatus = IsolatedPointStatus.CONFIRMED,
    price: float = 110.0,
) -> IsolatedPoint:
    return IsolatedPoint(index, kind, status, price)


def test_suppression_reason_values_are_stable() -> None:
    assert {reason.value for reason in ShortTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }


def test_short_term_records_preserve_values_and_are_frozen() -> None:
    point = ShortTermPoint(3, IsolatedPointKind.HIGH, 110.0, None)
    suppressed = SuppressedShortTermPoint(
        point,
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    structure = ShortTermStructure((point,), (point,), (suppressed,))

    assert structure.points == (point,)
    assert structure.vertices == (point,)
    assert structure.suppressed == (suppressed,)
    with pytest.raises(FrozenInstanceError):
        point.price = 111.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kind", "price"),
    [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 90.0),
    ],
)
def test_bare_confirmed_point_maps_without_recomputed_basis(
    kind: IsolatedPointKind,
    price: float,
) -> None:
    source = isolated_point(kind=kind, price=price)

    result = short_term_point_from_isolated_point(source)

    assert result == ShortTermPoint(
        index=source.index,
        kind=kind,
        price=price,
        recognition_basis=None,
    )


@pytest.mark.parametrize(
    "basis",
    [IsolatedPointBasis.STRICT, IsolatedPointBasis.RIGHT_INSIDE_BAR],
)
def test_recognition_mapping_preserves_exact_basis(
    basis: IsolatedPointBasis,
) -> None:
    source = isolated_point()
    recognition = IsolatedPointRecognition(source, basis)

    result = short_term_point_from_recognition(recognition)

    assert result == ShortTermPoint(
        source.index,
        source.kind,
        source.price,
        basis,
    )
    assert result.recognition_basis is basis


def test_bare_mapping_rejects_potential_point() -> None:
    with pytest.raises(ValueError, match="requires a confirmed isolated point"):
        short_term_point_from_isolated_point(
            isolated_point(status=IsolatedPointStatus.POTENTIAL)
        )


def test_recognition_mapping_rejects_wrapped_potential_point() -> None:
    recognition = IsolatedPointRecognition(
        isolated_point(status=IsolatedPointStatus.POTENTIAL),
        IsolatedPointBasis.RIGHT_INSIDE_BAR,
    )

    with pytest.raises(ValueError, match="requires a confirmed isolated point"):
        short_term_point_from_recognition(recognition)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
pytest tests/test_short_term_structure.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'trading.definitions.short_term_structure'`. The failure must be caused by the missing Lesson 5 module, not by a syntax or fixture error.

- [ ] **Step 3: Implement the minimum immutable model and mapping boundary**

Create `trading/definitions/short_term_structure.py`:

```python
"""Course-defined Chapter 2 short-term structure normalization."""

from dataclasses import dataclass
from enum import Enum

from .isolated_point_deformations import (
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from .isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)


class ShortTermSuppressionReason(Enum):
    """Why a valid short-term point is omitted from the line."""

    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


@dataclass(frozen=True)
class ShortTermPoint:
    """One confirmed isolated point represented at short-term level."""

    index: int
    kind: IsolatedPointKind
    price: float
    recognition_basis: IsolatedPointBasis | None = None


@dataclass(frozen=True)
class SuppressedShortTermPoint:
    """A valid point omitted only from normalized line vertices."""

    point: ShortTermPoint
    reason: ShortTermSuppressionReason


@dataclass(frozen=True)
class ShortTermStructure:
    """All valid points, normalized vertices, and suppression evidence."""

    points: tuple[ShortTermPoint, ...]
    vertices: tuple[ShortTermPoint, ...]
    suppressed: tuple[SuppressedShortTermPoint, ...]


def _require_confirmed(point: IsolatedPoint) -> None:
    if point.status is not IsolatedPointStatus.CONFIRMED:
        raise ValueError(
            "short-term point mapping requires a confirmed isolated point"
        )


def short_term_point_from_isolated_point(
    point: IsolatedPoint,
) -> ShortTermPoint:
    """Map a bare confirmed point without recomputing recognition basis."""

    _require_confirmed(point)
    return ShortTermPoint(point.index, point.kind, point.price, None)


def short_term_point_from_recognition(
    recognition: IsolatedPointRecognition,
) -> ShortTermPoint:
    """Map a basis-carrying confirmed recognition exactly."""

    _require_confirmed(recognition.point)
    return ShortTermPoint(
        recognition.point.index,
        recognition.point.kind,
        recognition.point.price,
        recognition.basis,
    )
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
pytest tests/test_short_term_structure.py -v
```

Expected: PASS for every Task 1 test.

- [ ] **Step 5: Run Chapter 1 recognition regressions**

Run:

```bash
pytest tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v
```

Expected: PASS with no change to strict or deformation-aware recognition behavior.

- [ ] **Step 6: Review and commit Task 1**

Review the diff for frozen records, exact enum values, confirmed-only mapping, and absence of candle recognition logic. Then run `git diff --check`.

```bash
git add trading/definitions/short_term_structure.py tests/test_short_term_structure.py
git commit -m "Add short-term structure domain model"
```

---

### Task 2: Chronology and Consecutive Same-Kind Normalization

**Files:**
- Modify: `trading/definitions/short_term_structure.py`
- Modify: `tests/test_short_term_structure.py`

**Interfaces:**
- Consumes: `ShortTermPoint`, `ShortTermStructure`, `SuppressedShortTermPoint`, and `ShortTermSuppressionReason` from Task 1.
- Produces: `build_short_term_structure(points: Sequence[ShortTermPoint]) -> ShortTermStructure`, with complete chronology validation and same-kind run normalization.

- [ ] **Step 1: Add neutral input and chronology tests**

Extend the existing `from trading.definitions.short_term_structure import (...)` block to include `build_short_term_structure`. Then append these helpers and tests to `tests/test_short_term_structure.py`:

```python
def short_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> ShortTermPoint:
    return ShortTermPoint(index, kind, price, None)


def test_empty_points_return_empty_structure() -> None:
    assert build_short_term_structure(()) == ShortTermStructure((), (), ())


def test_one_point_remains_one_point_and_vertex() -> None:
    point = short_point(4, IsolatedPointKind.HIGH, 110.0)

    assert build_short_term_structure([point]) == ShortTermStructure(
        points=(point,),
        vertices=(point,),
        suppressed=(),
    )


def test_two_opposite_kind_points_remain_chronological_vertices() -> None:
    points = [
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
    ]

    assert build_short_term_structure(points).vertices == tuple(points)


@pytest.mark.parametrize(
    "points",
    [
        [
            short_point(2, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 100.0),
        ],
        [
            short_point(1, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 100.0),
        ],
    ],
)
def test_builder_rejects_non_increasing_indexes(
    points: list[ShortTermPoint],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_short_term_structure(points)


def test_complete_chronology_is_validated_before_normalization() -> None:
    points = [
        short_point(1, IsolatedPointKind.HIGH, 108.0),
        short_point(3, IsolatedPointKind.HIGH, 110.0),
        short_point(2, IsolatedPointKind.HIGH, 109.0),
    ]

    with pytest.raises(ValueError, match="strictly increasing"):
        build_short_term_structure(points)
```

- [ ] **Step 2: Add alternating, same-kind, suppression, and tie tests**

Append:

```python
def test_alternating_points_remain_unchanged() -> None:
    points = [
        short_point(0, IsolatedPointKind.LOW, 100.0),
        short_point(1, IsolatedPointKind.HIGH, 110.0),
        short_point(2, IsolatedPointKind.LOW, 103.0),
        short_point(3, IsolatedPointKind.HIGH, 112.0),
    ]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == tuple(points)
    assert result.suppressed == ()


def test_consecutive_high_run_keeps_highest_vertex_and_all_points() -> None:
    points = [
        short_point(0, IsolatedPointKind.LOW, 100.0),
        short_point(1, IsolatedPointKind.HIGH, 108.0),
        short_point(2, IsolatedPointKind.HIGH, 110.0),
        short_point(3, IsolatedPointKind.HIGH, 109.0),
        short_point(4, IsolatedPointKind.LOW, 103.0),
    ]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == (points[0], points[2], points[4])
    assert result.suppressed == (
        SuppressedShortTermPoint(
            points[1],
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
        SuppressedShortTermPoint(
            points[3],
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
    )


def test_consecutive_low_run_keeps_lowest_vertex() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 102.0),
        short_point(2, IsolatedPointKind.LOW, 98.0),
        short_point(3, IsolatedPointKind.LOW, 100.0),
        short_point(4, IsolatedPointKind.HIGH, 108.0),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == (points[0], points[2], points[4])
    assert [item.point for item in result.suppressed] == [points[1], points[3]]


@pytest.mark.parametrize(
    ("kind", "price"),
    [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 90.0),
    ],
)
def test_equal_extreme_tie_keeps_earliest_vertex(
    kind: IsolatedPointKind,
    price: float,
) -> None:
    points = [
        short_point(1, kind, price),
        short_point(2, kind, price),
        short_point(3, kind, price),
    ]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == (points[0],)
    assert result.suppressed == tuple(
        SuppressedShortTermPoint(
            point,
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        )
        for point in points[1:]
    )
```

The parametrized tie test explicitly covers equal highest `HIGH` and equal lowest `LOW`. Earliest-on-equality is an engineering tie-break; do not describe it as market significance.

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```bash
pytest tests/test_short_term_structure.py -v
```

Expected: collection fails because `build_short_term_structure` is not defined, or the newly added behavior tests fail until the builder exists. Confirm the failure is tied to the missing Task 2 interface or behavior.

- [ ] **Step 4: Implement chronology validation and same-kind run reduction**

Add the `Sequence` import and these private helpers to `trading/definitions/short_term_structure.py`:

```python
from collections.abc import Sequence


def _validate_chronology(points: Sequence[ShortTermPoint]) -> None:
    for previous, current in zip(points, points[1:]):
        if current.index <= previous.index:
            raise ValueError(
                "short-term point indexes must be strictly increasing"
            )


def _is_more_extreme(
    candidate: ShortTermPoint,
    current: ShortTermPoint,
) -> bool:
    if current.kind is IsolatedPointKind.HIGH:
        return candidate.price > current.price
    return candidate.price < current.price


def _normalize_same_kind_runs(
    points: tuple[ShortTermPoint, ...],
) -> tuple[
    list[ShortTermPoint],
    list[SuppressedShortTermPoint],
]:
    vertices: list[ShortTermPoint] = []
    suppressed: list[SuppressedShortTermPoint] = []
    run: list[ShortTermPoint] = []

    def flush_run() -> None:
        if not run:
            return
        winner = run[0]
        for candidate in run[1:]:
            if _is_more_extreme(candidate, winner):
                winner = candidate
        vertices.append(winner)
        suppressed.extend(
            SuppressedShortTermPoint(
                point,
                ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
            )
            for point in run
            if point is not winner
        )

    for point in points:
        if run and point.kind is not run[-1].kind:
            flush_run()
            run = []
        run.append(point)
    flush_run()
    return vertices, suppressed


def build_short_term_structure(
    points: Sequence[ShortTermPoint],
) -> ShortTermStructure:
    """Normalize confirmed short-term points without losing evidence."""

    all_points = tuple(points)
    _validate_chronology(all_points)
    vertices, suppressed = _normalize_same_kind_runs(all_points)
    return ShortTermStructure(
        points=all_points,
        vertices=tuple(vertices),
        suppressed=tuple(suppressed),
    )
```

The strict comparisons in `_is_more_extreme()` preserve the earliest point on equal price. `flush_run()` records every non-winning point in original chronology.

- [ ] **Step 5: Run Task 2 tests and verify GREEN**

Run:

```bash
pytest tests/test_short_term_structure.py -v
```

Expected: PASS for Task 1 and Task 2 tests.

- [ ] **Step 6: Run focused Chapter 1 regressions and inspect scope**

Run:

```bash
pytest tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v
git diff --check
```

Expected: PASS and no whitespace errors. Confirm `points` always preserves the original tuple and no existing recognition module changed.

- [ ] **Step 7: Review and commit Task 2**

Review specifically that validation occurs before any normalization return, duplicate indexes are rejected, alternating input is unchanged, later ties are suppressed only from `vertices`, and no trend state is produced.

```bash
git add trading/definitions/short_term_structure.py tests/test_short_term_structure.py
git commit -m "Add short-term same-kind normalization"
```

---

### Task 3: Inside-Structure Normalization

**Files:**
- Modify: `trading/definitions/short_term_structure.py`
- Modify: `tests/test_short_term_structure.py`

**Interfaces:**
- Consumes: the alternating vertex candidates and same-kind suppression records produced by `_normalize_same_kind_runs()`.
- Produces: `build_short_term_structure()` results with inclusive, mirrored, repeated definite inside-structure normalization and `INSIDE_STRUCTURE` suppression evidence.

**Exact pairing representation:** After same-kind normalization, vertices alternate by kind. Starting at vertex zero, each two consecutive vertices form one chronological opposite-kind range: `[0, 1]`, `[2, 3]`, and so on. An unmatched final vertex is preserved and does not form a synthetic pair. Compare each complete later pair with the complete pair immediately before it in the current candidate list. When a later pair is contained, remove that entire pair and compare the newly adjacent pair against the same earlier pair. When it is not contained, advance the earlier range by two vertices. This implements left-to-right repeated definite containment without overlapping, skipping points, or inventing pairings.

- [ ] **Step 1: Add inclusive and mirrored inside tests**

Append to `tests/test_short_term_structure.py`:

```python
@pytest.mark.parametrize(
    "points",
    [
        [
            short_point(0, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 100.0),
            short_point(2, IsolatedPointKind.HIGH, 108.0),
            short_point(3, IsolatedPointKind.LOW, 102.0),
        ],
        [
            short_point(0, IsolatedPointKind.LOW, 100.0),
            short_point(1, IsolatedPointKind.HIGH, 110.0),
            short_point(2, IsolatedPointKind.LOW, 102.0),
            short_point(3, IsolatedPointKind.HIGH, 108.0),
        ],
    ],
)
def test_complete_inside_pair_is_suppressed_in_both_orientations(
    points: list[ShortTermPoint],
) -> None:
    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == tuple(points[:2])
    assert result.suppressed == tuple(
        SuppressedShortTermPoint(
            point,
            ShortTermSuppressionReason.INSIDE_STRUCTURE,
        )
        for point in points[2:]
    )


@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (110.0, 102.0),
        (108.0, 100.0),
        (110.0, 100.0),
    ],
)
def test_equality_at_either_inside_boundary_counts_as_contained(
    later_high: float,
    later_low: float,
) -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, later_high),
        short_point(3, IsolatedPointKind.LOW, later_low),
    ]

    assert build_short_term_structure(points).vertices == tuple(points[:2])
```

- [ ] **Step 2: Add breakout, repetition, ambiguity, and ordering tests**

Append:

```python
@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (111.0, 102.0),
        (108.0, 99.0),
    ],
)
def test_one_side_breakout_prevents_inside_suppression(
    later_high: float,
    later_low: float,
) -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, later_high),
        short_point(3, IsolatedPointKind.LOW, later_low),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == tuple(points)
    assert result.suppressed == ()


def test_repeated_inside_pairs_normalize_until_stable() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 120.0),
        short_point(1, IsolatedPointKind.LOW, 90.0),
        short_point(2, IsolatedPointKind.HIGH, 115.0),
        short_point(3, IsolatedPointKind.LOW, 95.0),
        short_point(4, IsolatedPointKind.HIGH, 110.0),
        short_point(5, IsolatedPointKind.LOW, 100.0),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == tuple(points[:2])
    assert [item.point for item in result.suppressed] == points[2:]
    assert all(
        item.reason is ShortTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.suppressed
    )


def test_incomplete_later_range_is_preserved_without_invented_pairing() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.LOW, 100.0),
        short_point(2, IsolatedPointKind.HIGH, 108.0),
    ]

    assert build_short_term_structure(points).vertices == tuple(points)


def test_suppression_order_is_phase_then_chronology() -> None:
    points = [
        short_point(0, IsolatedPointKind.HIGH, 110.0),
        short_point(1, IsolatedPointKind.HIGH, 112.0),
        short_point(2, IsolatedPointKind.LOW, 100.0),
        short_point(3, IsolatedPointKind.HIGH, 108.0),
        short_point(4, IsolatedPointKind.LOW, 102.0),
    ]

    result = build_short_term_structure(points)

    assert result.vertices == (points[1], points[2])
    assert result.suppressed == (
        SuppressedShortTermPoint(
            points[0],
            ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
        SuppressedShortTermPoint(
            points[3],
            ShortTermSuppressionReason.INSIDE_STRUCTURE,
        ),
        SuppressedShortTermPoint(
            points[4],
            ShortTermSuppressionReason.INSIDE_STRUCTURE,
        ),
    )
```

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```bash
pytest tests/test_short_term_structure.py -v
```

Expected: the inside-structure tests fail because `build_short_term_structure()` currently returns all alternating candidates as vertices and records no `INSIDE_STRUCTURE` suppressions. Existing Task 1–2 tests must remain green.

- [ ] **Step 4: Implement the smallest private inside helpers**

Add to `trading/definitions/short_term_structure.py`:

```python
def _pair_bounds(
    first: ShortTermPoint,
    second: ShortTermPoint,
) -> tuple[float, float] | None:
    if first.kind is second.kind:
        return None
    high = first if first.kind is IsolatedPointKind.HIGH else second
    low = first if first.kind is IsolatedPointKind.LOW else second
    return high.price, low.price


def _later_pair_is_inside(
    earlier: tuple[ShortTermPoint, ShortTermPoint],
    later: tuple[ShortTermPoint, ShortTermPoint],
) -> bool:
    earlier_bounds = _pair_bounds(*earlier)
    later_bounds = _pair_bounds(*later)
    if earlier_bounds is None or later_bounds is None:
        return False
    earlier_high, earlier_low = earlier_bounds
    later_high, later_low = later_bounds
    return later_high <= earlier_high and later_low >= earlier_low


def _normalize_inside_structures(
    vertices: list[ShortTermPoint],
) -> tuple[list[ShortTermPoint], list[SuppressedShortTermPoint]]:
    normalized = list(vertices)
    suppressed: list[SuppressedShortTermPoint] = []
    changed = True

    while changed:
        changed = False
        pair_start = 0
        while pair_start + 3 < len(normalized):
            earlier = (
                normalized[pair_start],
                normalized[pair_start + 1],
            )
            later = (
                normalized[pair_start + 2],
                normalized[pair_start + 3],
            )
            if not _later_pair_is_inside(earlier, later):
                pair_start += 2
                continue

            removed = normalized[pair_start + 2 : pair_start + 4]
            del normalized[pair_start + 2 : pair_start + 4]
            suppressed.extend(
                SuppressedShortTermPoint(
                    point,
                    ShortTermSuppressionReason.INSIDE_STRUCTURE,
                )
                for point in removed
            )
            changed = True

    return normalized, suppressed
```

Then replace the return block in `build_short_term_structure()` with:

```python
    same_kind_vertices, same_kind_suppressed = _normalize_same_kind_runs(
        all_points
    )
    vertices, inside_suppressed = _normalize_inside_structures(
        same_kind_vertices
    )
    return ShortTermStructure(
        points=all_points,
        vertices=tuple(vertices),
        suppressed=tuple(same_kind_suppressed + inside_suppressed),
    )
```

The complete chronology is still validated before either normalization phase. `_pair_bounds()` returns `None` rather than inventing a range for a non-comparable pair. The stable loop uses only inclusive complete containment.

- [ ] **Step 5: Run Task 3 tests and verify GREEN**

Run:

```bash
pytest tests/test_short_term_structure.py -v
```

Expected: PASS for all short-term unit tests.

- [ ] **Step 6: Run existing structure regressions and inspect the implementation**

Run:

```bash
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
git diff --check
```

Expected: PASS and no whitespace errors. Inspect that there are no thresholds, BMS/SMS imports, level enums, generic hierarchy logic, or public helpers beyond the locked API.

- [ ] **Step 7: Review and commit Task 3**

Review both orientations, equality, one-side breakouts, stable repeated processing, unmatched-point preservation, all-points evidence, and deterministic suppression ordering.

```bash
git add trading/definitions/short_term_structure.py tests/test_short_term_structure.py
git commit -m "Add short-term inside normalization"
```

---

### Task 4: Cross-Layer Integration and Regression Verification

**Files:**
- Create: `tests/test_short_term_structure_integration.py`
- Modify only if a genuine RED integration defect requires it: `trading/definitions/short_term_structure.py`

**Interfaces:**
- Consumes: existing `detect_confirmed_isolated_point()`, `find_confirmed_isolated_points()`, `get_potential_isolated_point()`, and `confirm_isolated_point_with_deformation()`; Task 1 mapping functions; Task 2–3 `build_short_term_structure()`.
- Produces: focused evidence that real Chapter 1 recognition results compose into the Lesson 5 domain and normalized line without duplicate candle-pattern logic.

- [ ] **Step 1: Verify the integration test artifact is absent for RED**

Run before creating the file:

```bash
pytest tests/test_short_term_structure_integration.py -v
```

Expected: pytest reports `file or directory not found: tests/test_short_term_structure_integration.py`. This is the integration-artifact RED checkpoint; production behavior was developed red-to-green in Tasks 1–3.

- [ ] **Step 2: Add real strict and deformation-aware composition tests**

Create `tests/test_short_term_structure_integration.py`:

```python
from trading.definitions.candles import Candle
from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    confirm_isolated_point_with_deformation,
)
from trading.definitions.isolated_points import (
    IsolatedPointKind,
    detect_confirmed_isolated_point,
    find_confirmed_isolated_points,
    get_potential_isolated_point,
)
from trading.definitions.short_term_structure import (
    ShortTermSuppressionReason,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def candle(high: float, low: float) -> Candle:
    midpoint = (high + low) / 2
    return Candle(midpoint, high, low, midpoint)


def test_strict_isolated_high_maps_to_short_term_high() -> None:
    recognized = detect_confirmed_isolated_point(
        candle(10.0, 5.0),
        candle(12.0, 7.0),
        candle(11.0, 6.0),
        index=1,
    )
    assert recognized is not None

    point = short_term_point_from_isolated_point(recognized)

    assert point.index == 1
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 12.0
    assert point.recognition_basis is None


def test_strict_isolated_low_maps_to_short_term_low() -> None:
    recognized = detect_confirmed_isolated_point(
        candle(10.0, 5.0),
        candle(8.0, 3.0),
        candle(9.0, 4.0),
        index=1,
    )
    assert recognized is not None

    point = short_term_point_from_isolated_point(recognized)

    assert point.kind is IsolatedPointKind.LOW
    assert point.price == 3.0


def test_right_inside_bar_recognition_preserves_basis() -> None:
    middle = candle(12.0, 7.0)
    potential = get_potential_isolated_point(
        candle(10.0, 5.0),
        middle,
        index=1,
    )
    assert potential is not None
    recognition = confirm_isolated_point_with_deformation(
        potential,
        middle,
        candle(12.0, 8.0),
    )
    assert recognition is not None

    point = short_term_point_from_recognition(recognition)

    assert point.kind is IsolatedPointKind.HIGH
    assert point.recognition_basis is IsolatedPointBasis.RIGHT_INSIDE_BAR


def test_strict_candle_sequence_preserves_points_while_normalizing_line() -> None:
    candles = [
        candle(10.0, 5.0),
        candle(12.0, 7.0),
        candle(11.0, 6.0),
        candle(13.0, 5.5),
        candle(14.0, 7.0),
        candle(12.0, 6.0),
    ]
    recognized = find_confirmed_isolated_points(candles)
    assert [(point.index, point.kind, point.price) for point in recognized] == [
        (1, IsolatedPointKind.HIGH, 12.0),
        (4, IsolatedPointKind.HIGH, 14.0),
    ]
    points = [short_term_point_from_isolated_point(point) for point in recognized]

    result = build_short_term_structure(points)

    assert result.points == tuple(points)
    assert result.vertices == (points[1],)
    assert len(result.suppressed) == 1
    assert result.suppressed[0].point is points[0]
    assert result.suppressed[0].reason is (
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND
    )
```

- [ ] **Step 3: Run the focused integration suite and verify GREEN**

Run:

```bash
pytest tests/test_short_term_structure_integration.py -v
```

Expected: PASS. If a genuine integration defect appears, first preserve the failing test, then make the smallest change in `trading/definitions/short_term_structure.py`; do not modify Chapter 1 recognition behavior.

- [ ] **Step 4: Run all short-term tests together**

Run:

```bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
```

Expected: PASS for the complete Lesson 5 unit and focused integration suites.

- [ ] **Step 5: Run required Chapter 1 and Chapter 2 regressions**

Run each command separately:

```bash
pytest tests/test_isolated_points.py -v
pytest tests/test_isolated_point_deformations.py -v
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
```

Expected: PASS for every existing suite. Do not record a predicted pass count in advance.

- [ ] **Step 6: Run the complete repository verification**

Run:

```bash
pytest -q
git diff --check
python -c "from pathlib import Path; assert not Path('tests/test_course_market_structure_scenarios.py').exists()"
```

Expected: the full repository suite passes, the diff check has no output, and the forbidden formal Chapter 2 Level 2 file remains absent.

- [ ] **Step 7: Inspect final feature scope and deferred-concept boundary**

Run:

```bash
git status --short
git diff --name-only main...HEAD
git grep -n -E "ATR|percentage threshold|minimum distance|swing strength|evaluate_bms|evaluate_sms|medium.term|long.term|strategy|broker|execution" -- trading/definitions/short_term_structure.py
```

Expected:

- changed production/test paths are limited to `trading/definitions/short_term_structure.py`, `tests/test_short_term_structure.py`, and `tests/test_short_term_structure_integration.py`;
- the grep returns no forbidden coupling or future-course logic; and
- no existing Lesson 1–3 production file changed.

- [ ] **Step 8: Review and commit Task 4**

Review the complete integration path, point-evidence preservation, absence of duplicated recognition logic, and unchanged existing layers.

```bash
git add tests/test_short_term_structure_integration.py
git add trading/definitions/short_term_structure.py
git commit -m "Add short-term structure integration coverage"
```

If Task 4 required no production correction, the second `git add` is harmless. Do not stage unrelated files.

---

## Final Review and Execution Handoff

After all four task commits:

- dispatch a broad whole-branch spec-compliance and code-quality review;
- fix every valid finding in the feature worktree;
- re-run the affected focused suites and the complete repository suite;
- re-run `git diff --check` and the formal-suite absence check;
- confirm the final diff contains only the three planned production/test files;
- confirm no timeframe-to-level, medium/long-term, BMS/SMS ambiguity resolution, strategy, risk, or execution logic was added;
- keep the feature worktree clean; and
- push `feature/short-term-structure` for independent GitHub review.

Do not push implementation commits directly to `origin/main`. Do not merge the feature branch into `main` until independent review is complete and the user explicitly approves the repository's local-merge workflow.

At implementation time, use:

1. `superpowers:using-git-worktrees` to create or verify the isolated feature worktree;
2. `superpowers:subagent-driven-development` as the recommended plan executor, with a fresh implementer and task review for each task; or
3. `superpowers:executing-plans` when subagent-driven execution is unavailable.
