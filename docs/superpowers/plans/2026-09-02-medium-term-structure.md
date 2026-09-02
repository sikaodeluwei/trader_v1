# Medium-Term Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Chapter 2 Lesson 6 medium-term structure layer from cleaned short-term vertices, with strict ITH/ITL recognition, explicit right-side structural confirmation provenance, separate edge potentials, deterministic normalization, and evidence-only course metadata. Exact real-time knowability remains deferred because `ShortTermPoint` does not carry availability timing.

**Architecture:** Add one focused module whose canonical entry point accepts a `ShortTermStructure`, validates its cleaned `vertices`, recognizes medium points from previous/middle/next same-kind vertices, and then normalizes only confirmed medium points. Immutable domain records preserve both the source pivot and the immediate next same-kind cleaned short-term point that structurally confirms it, plus potentials, suppressions, and optional externally supplied course evidence, without rescanning candles or changing existing Chapter 1/Lesson 1-5 behavior.

**Tech Stack:** Python, frozen dataclasses, `Enum`, `collections.abc.Sequence`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-02-medium-term-structure-design.md`

## Global Constraints

- Implement Chapter 2, Lesson 6 medium/intermediate structure only.
- Treat the approved spec as binding authority if any plan wording is read ambiguously.
- Canonical recognition must accept an explicit `ShortTermStructure` and consume only `ShortTermStructure.vertices` as same-kind neighbors.
- Do not rescan candles, duplicate isolated-point recognition, consume `ShortTermStructure.points` as canonical neighbors, consume suppressed short-term points, or rebuild a competing short-term line.
- Canonical ITH recognition is strictly `previous HIGH < middle HIGH > next HIGH` over chronological cleaned short-term highs.
- Canonical ITL recognition is strictly `previous LOW > middle LOW < next LOW` over chronological cleaned short-term lows.
- Previous and next always mean the immediately previous and next cleaned short-term vertex of the same kind; never skip an intervening same-kind vertex.
- Equality on either side prevents canonical confirmation.
- Preserve the source `ShortTermPoint` as `pivot` and the immediate next same-kind cleaned vertex as `confirmed_by`.
- `confirmed_by_index` is structural source information only. It is not necessarily the candle index when `confirmed_by` itself became knowable.
- Do not invent `known_at_index`; exact real-time knowability is deferred until the lower short-term layer supplies its own availability timing.
- Order confirmed medium points and final line vertices by pivot chronology, never by confirming-source chronology.
- Never expose a point as confirmed before its right-side same-kind source vertex exists.
- Represent eligible current right-edge potentials separately from confirmed `points` and `vertices`.
- A right-edge high is potential only when a previous cleaned high exists and the edge high is strictly higher; mirror with a strictly lower edge low.
- Failed potentials are omitted rather than promoted or assigned invented market meaning.
- Preserve all confirmed medium points in `MediumTermStructure.points`, including points suppressed from final vertices.
- Consecutive confirmed medium highs retain the highest price; consecutive lows retain the lowest price.
- Equal highest-high and lowest-low ties retain the earliest pivot as a neutral engineering tie-break.
- Medium inside suppression is provisional and requires both inclusive conditions: `later_high <= earlier_high` and `later_low >= earlier_low`.
- Equality at either inside boundary counts as contained; a breakout on either boundary prevents inside suppression.
- Apply only the definite inside rule from left to right repeatedly until stable.
- Do not add range extension, boundary replacement, nearest-pair selection, discretionary chart matching, trend-based cleanup, ATR, percentage, movement, distance, or candle-count thresholds.
- Course creator/break evidence is optional, external, immutable diagnostic metadata only; do not calculate creator selection or break evidence automatically.
- Course evidence must not alter confirmed points, pivots, `confirmed_by` sources, potentials, suppressions, or vertices.
- Do not add a generic structural-level enum, fixed timeframe mapping, long-term recognition, recursive promotion, or automatic parent/child hierarchy.
- Do not reinterpret or invoke BMS/SMS, infer market state or reversal, or add strategy, signals, entries, exits, stop losses, risk, sizing, leverage, broker, order, execution, or AI/ML logic.
- Do not modify existing production modules merely to re-export the new API; consumers import directly from `trading.definitions.medium_term_structure`.
- Do not create `tests/test_course_market_structure_scenarios.py`; formal Chapter 2 Level 2 validation remains deferred until all Chapter 2 lessons are complete.
- Actual implementation must not occur on `main`. At execution time use `superpowers:using-git-worktrees` and create an isolated `feature/medium-term-structure` branch/worktree from the approved implementation base.
- Use red-to-green TDD for every behavioral task, review every task for spec compliance and code quality, and run a broad final whole-branch review before integration.

---

## File Structure

Create exactly these implementation artifacts unless a failing integration test proves a narrowly scoped correction is required:

- `trading/definitions/medium_term_structure.py` - immutable Lesson 6 records, cleaned-source validation, strict ITH/ITL recognition, potential candidates, normalization, and evidence attachment.
- `tests/test_medium_term_structure.py` - focused domain, validation, recognition, structural confirming-source, same-kind, inside, and evidence-boundary tests.
- `tests/test_medium_term_structure_integration.py` - real Chapter 1 -> Lesson 5 -> Lesson 6 composition and cleaned-vertex boundary proof.

Existing Chapter 1 and Chapter 2 production modules remain unchanged. Existing tests remain unchanged.

## Locked Public API

The implementation tasks use this final public surface:

```python
class MediumTermSuppressionReason(Enum):
    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


class CourseRuleMatch(Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MediumTermPoint:
    pivot: ShortTermPoint
    confirmed_by: ShortTermPoint

    @property
    def pivot_index(self) -> int:
        return self.pivot.index

    @property
    def confirmed_by_index(self) -> int:
        return self.confirmed_by.index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


@dataclass(frozen=True)
class PotentialMediumTermPoint:
    previous_same_kind: ShortTermPoint
    pivot: ShortTermPoint

    @property
    def pivot_index(self) -> int:
        return self.pivot.index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


@dataclass(frozen=True)
class SuppressedMediumTermPoint:
    point: MediumTermPoint
    reason: MediumTermSuppressionReason


@dataclass(frozen=True)
class MediumCourseEvidence:
    point: MediumTermPoint
    course_rule_match: CourseRuleMatch


@dataclass(frozen=True)
class MediumTermStructure:
    points: tuple[MediumTermPoint, ...]
    potentials: tuple[PotentialMediumTermPoint, ...]
    vertices: tuple[MediumTermPoint, ...]
    suppressed: tuple[SuppressedMediumTermPoint, ...]
    course_evidence: tuple[MediumCourseEvidence, ...] = ()
```

Exact public function signatures:

```text
build_medium_term_structure(source: ShortTermStructure) -> MediumTermStructure
attach_course_evidence(
    structure: MediumTermStructure,
    evidence: Sequence[MediumCourseEvidence],
) -> MediumTermStructure
```

`build_medium_term_structure()` is the only canonical recognition entry point. Accepting `ShortTermStructure` instead of `Sequence[ShortTermPoint]` makes the cleaned-source boundary explicit and prevents callers from accidentally passing all recognized or suppressed short-term points.

`MediumTermPoint` stores the source pivot and the immediate next same-kind cleaned short-term point that completes the strict comparison. Its properties expose pivot values and `confirmed_by_index` directly from those immutable source objects. The latter is structural provenance, not an actual `known_at_index`.

`PotentialMediumTermPoint` is the minimal current-edge representation. At most one high potential and one low potential may exist for one source snapshot; the returned tuple is ordered by pivot chronology. Failed candidates are not retained as a rejected-history collection.

`MediumCourseEvidence` is externally supplied metadata attached only after canonical structure exists. `attach_course_evidence()` returns a new frozen `MediumTermStructure`; it never reruns or changes recognition/normalization.

Exact validation messages selected by this plan:

```text
confirmed medium points require same-kind pivot and confirmed_by points
confirmed_by index must be after pivot index
potential medium points require same-kind source points
potential medium point indexes must be chronological
potential medium point must be more extreme than previous same-kind point
cleaned short-term vertex indexes must be strictly increasing
cleaned short-term vertices must come from structure points
suppressed short-term points must not be medium-recognition vertices
course evidence requires a confirmed medium point
```

Suppression ordering is deterministic:

1. same-kind suppressions appear in original confirmed-point pivot chronology;
2. inside suppressions follow in left-to-right removal order; and
3. the two points of one suppressed inside pair remain in pivot chronology.

---

### Task 1: Medium Domain Model, Cleaned-Source Validation, Strict Recognition, and Structural Confirmation Provenance

**Files:**
- Create: `trading/definitions/medium_term_structure.py`
- Create: `tests/test_medium_term_structure.py`

**Interfaces:**
- Consumes: `IsolatedPointKind` from `trading.definitions.isolated_points`; `ShortTermPoint`, `ShortTermStructure`, and `SuppressedShortTermPoint` from `trading.definitions.short_term_structure`.
- Produces: all locked domain records and enums; `build_medium_term_structure(source: ShortTermStructure) -> MediumTermStructure` with complete source validation, strict same-kind recognition, explicit `confirmed_by` provenance, and current edge potentials. At this task boundary, confirmed `points` are also the provisional `vertices`, `suppressed == ()`, and `course_evidence == ()`.

- [ ] **Step 1: Write domain, validation, and neutral-input tests first**

Create `tests/test_medium_term_structure.py`:

```python
from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumCourseEvidence,
    MediumTermPoint,
    MediumTermStructure,
    MediumTermSuppressionReason,
    PotentialMediumTermPoint,
    SuppressedMediumTermPoint,
    build_medium_term_structure,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    ShortTermSuppressionReason,
    SuppressedShortTermPoint,
)


def short_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> ShortTermPoint:
    return ShortTermPoint(index, kind, price, None)


def short_structure(
    vertices: list[ShortTermPoint] | tuple[ShortTermPoint, ...],
    *,
    points: list[ShortTermPoint] | tuple[ShortTermPoint, ...] | None = None,
    suppressed: tuple[SuppressedShortTermPoint, ...] = (),
) -> ShortTermStructure:
    vertex_tuple = tuple(vertices)
    return ShortTermStructure(
        points=vertex_tuple if points is None else tuple(points),
        vertices=vertex_tuple,
        suppressed=suppressed,
    )


def alternating_source(
    high_prices: list[float],
    low_prices: list[float],
    *,
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> ShortTermStructure:
    assert len(high_prices) == len(low_prices)
    vertices: list[ShortTermPoint] = []
    for high, low in zip(high_prices, low_prices):
        if first_kind is IsolatedPointKind.HIGH:
            vertices.append(
                short_point(len(vertices), IsolatedPointKind.HIGH, high)
            )
            vertices.append(
                short_point(len(vertices), IsolatedPointKind.LOW, low)
            )
        else:
            vertices.append(
                short_point(len(vertices), IsolatedPointKind.LOW, low)
            )
            vertices.append(
                short_point(len(vertices), IsolatedPointKind.HIGH, high)
            )
    return short_structure(vertices)


def test_enum_values_are_stable() -> None:
    assert {reason.value for reason in MediumTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }
    assert {match.value for match in CourseRuleMatch} == {
        "yes",
        "no",
        "unknown",
    }


def test_medium_records_preserve_provenance_and_are_frozen() -> None:
    pivot = short_point(3, IsolatedPointKind.HIGH, 112.0)
    confirmed_by = short_point(7, IsolatedPointKind.HIGH, 108.0)
    point = MediumTermPoint(pivot, confirmed_by)
    potential = PotentialMediumTermPoint(
        short_point(1, IsolatedPointKind.HIGH, 105.0),
        pivot,
    )
    suppressed = SuppressedMediumTermPoint(
        point,
        MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    evidence = MediumCourseEvidence(point, CourseRuleMatch.UNKNOWN)
    structure = MediumTermStructure(
        points=(point,),
        potentials=(potential,),
        vertices=(point,),
        suppressed=(suppressed,),
        course_evidence=(evidence,),
    )

    assert point.pivot is pivot
    assert point.confirmed_by is confirmed_by
    assert point.pivot_index == 3
    assert point.confirmed_by_index == 7
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 112.0
    assert structure.course_evidence == (evidence,)
    with pytest.raises(FrozenInstanceError):
        point.confirmed_by = short_point(8, IsolatedPointKind.HIGH, 107.0)  # type: ignore[misc]


def test_confirmed_point_requires_same_kind_source_points() -> None:
    pivot = short_point(3, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="same-kind pivot and confirmed_by"):
        MediumTermPoint(
            pivot,
            short_point(5, IsolatedPointKind.LOW, 95.0),
        )


@pytest.mark.parametrize("confirmed_by_index", [2, 3])
def test_confirmed_point_requires_later_confirmed_by(
    confirmed_by_index: int,
) -> None:
    pivot = short_point(3, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="confirmed_by index must be after pivot index"):
        MediumTermPoint(
            pivot,
            short_point(confirmed_by_index, IsolatedPointKind.HIGH, 108.0),
        )


def test_potential_requires_same_kind_chronological_sources() -> None:
    previous = short_point(3, IsolatedPointKind.HIGH, 105.0)

    with pytest.raises(ValueError, match="same-kind source points"):
        PotentialMediumTermPoint(
            previous,
            short_point(5, IsolatedPointKind.LOW, 95.0),
        )
    with pytest.raises(ValueError, match="indexes must be chronological"):
        PotentialMediumTermPoint(
            previous,
            short_point(2, IsolatedPointKind.HIGH, 110.0),
        )


@pytest.mark.parametrize(
    "previous,pivot",
    [
        (
            short_point(1, IsolatedPointKind.HIGH, 110.0),
            short_point(3, IsolatedPointKind.HIGH, 110.0),
        ),
        (
            short_point(1, IsolatedPointKind.LOW, 90.0),
            short_point(3, IsolatedPointKind.LOW, 90.0),
        ),
    ],
)
def test_potential_requires_strictly_more_extreme_edge(
    previous: ShortTermPoint,
    pivot: ShortTermPoint,
) -> None:
    with pytest.raises(ValueError, match="must be more extreme"):
        PotentialMediumTermPoint(previous, pivot)


@pytest.mark.parametrize(
    "vertices",
    [
        [
            short_point(2, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 90.0),
        ],
        [
            short_point(1, IsolatedPointKind.HIGH, 110.0),
            short_point(1, IsolatedPointKind.LOW, 90.0),
        ],
    ],
)
def test_source_rejects_non_increasing_vertex_indexes(
    vertices: list[ShortTermPoint],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_medium_term_structure(short_structure(vertices))


def test_complete_source_chronology_is_validated_before_recognition() -> None:
    vertices = [
        short_point(1, IsolatedPointKind.HIGH, 105.0),
        short_point(4, IsolatedPointKind.HIGH, 112.0),
        short_point(3, IsolatedPointKind.HIGH, 108.0),
    ]

    with pytest.raises(ValueError, match="strictly increasing"):
        build_medium_term_structure(short_structure(vertices))


def test_vertices_must_belong_to_short_term_points() -> None:
    vertex = short_point(3, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="must come from structure points"):
        build_medium_term_structure(
            short_structure([vertex], points=[])
        )


def test_suppressed_short_term_point_cannot_be_a_medium_source_vertex() -> None:
    vertex = short_point(3, IsolatedPointKind.HIGH, 112.0)
    suppression = SuppressedShortTermPoint(
        vertex,
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )

    with pytest.raises(
        ValueError,
        match="must not be medium-recognition vertices",
    ):
        build_medium_term_structure(
            short_structure([vertex], suppressed=(suppression,))
        )


def test_empty_and_one_vertex_sources_are_neutral() -> None:
    empty = build_medium_term_structure(short_structure([]))
    one = build_medium_term_structure(
        short_structure([short_point(1, IsolatedPointKind.HIGH, 105.0)])
    )

    assert empty == MediumTermStructure((), (), (), (), ())
    assert one.points == ()
    assert one.potentials == ()
    assert one.vertices == ()
    assert one.suppressed == ()


def test_two_same_kind_vertices_can_produce_only_a_potential() -> None:
    source = short_structure(
        [
            short_point(1, IsolatedPointKind.HIGH, 105.0),
            short_point(3, IsolatedPointKind.HIGH, 112.0),
        ]
    )

    result = build_medium_term_structure(source)

    assert result.points == ()
    assert result.vertices == ()
    assert result.potentials == (
        PotentialMediumTermPoint(source.vertices[0], source.vertices[1]),
    )
```

- [ ] **Step 2: Run the initial tests and verify RED**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'trading.definitions.medium_term_structure'`. The RED cause must be the absent Lesson 6 module, not malformed test data.

- [ ] **Step 3: Implement the immutable records and source validation**

Create `trading/definitions/medium_term_structure.py` with the initial domain layer:

```python
"""Canonical Chapter 2 medium-term structure from cleaned short-term vertices."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .isolated_points import IsolatedPointKind
from .short_term_structure import ShortTermPoint, ShortTermStructure


class MediumTermSuppressionReason(Enum):
    """Why a confirmed medium point is omitted from the medium line."""

    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


class CourseRuleMatch(Enum):
    """Externally supplied diagnostic match to the course break method."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MediumTermPoint:
    """A canonical medium pivot and its structural right-side confirmer."""

    pivot: ShortTermPoint
    confirmed_by: ShortTermPoint

    def __post_init__(self) -> None:
        if self.pivot.kind is not self.confirmed_by.kind:
            raise ValueError(
                "confirmed medium points require same-kind pivot and confirmed_by points"
            )
        if self.confirmed_by.index <= self.pivot.index:
            raise ValueError("confirmed_by index must be after pivot index")

    @property
    def pivot_index(self) -> int:
        return self.pivot.index

    @property
    def confirmed_by_index(self) -> int:
        """Return structural source location, not actual knowability time."""

        return self.confirmed_by.index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


def _is_strictly_more_extreme(
    candidate: ShortTermPoint,
    previous: ShortTermPoint,
) -> bool:
    if candidate.kind is IsolatedPointKind.HIGH:
        return candidate.price > previous.price
    return candidate.price < previous.price


@dataclass(frozen=True)
class PotentialMediumTermPoint:
    """A right-edge pivot that passes its available left comparison."""

    previous_same_kind: ShortTermPoint
    pivot: ShortTermPoint

    def __post_init__(self) -> None:
        if self.previous_same_kind.kind is not self.pivot.kind:
            raise ValueError(
                "potential medium points require same-kind source points"
            )
        if self.pivot.index <= self.previous_same_kind.index:
            raise ValueError(
                "potential medium point indexes must be chronological"
            )
        if not _is_strictly_more_extreme(
            self.pivot,
            self.previous_same_kind,
        ):
            raise ValueError(
                "potential medium point must be more extreme than "
                "previous same-kind point"
            )

    @property
    def pivot_index(self) -> int:
        return self.pivot.index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


@dataclass(frozen=True)
class SuppressedMediumTermPoint:
    """A confirmed medium point omitted only from normalized vertices."""

    point: MediumTermPoint
    reason: MediumTermSuppressionReason


@dataclass(frozen=True)
class MediumCourseEvidence:
    """Externally supplied evidence that cannot decide canonical output."""

    point: MediumTermPoint
    course_rule_match: CourseRuleMatch


@dataclass(frozen=True)
class MediumTermStructure:
    """Canonical points, edge potentials, vertices, and retained evidence."""

    points: tuple[MediumTermPoint, ...]
    potentials: tuple[PotentialMediumTermPoint, ...]
    vertices: tuple[MediumTermPoint, ...]
    suppressed: tuple[SuppressedMediumTermPoint, ...]
    course_evidence: tuple[MediumCourseEvidence, ...] = ()


def _validate_short_term_source(source: ShortTermStructure) -> None:
    for previous, current in zip(source.vertices, source.vertices[1:]):
        if current.index <= previous.index:
            raise ValueError(
                "cleaned short-term vertex indexes must be strictly increasing"
            )

    if any(vertex not in source.points for vertex in source.vertices):
        raise ValueError(
            "cleaned short-term vertices must come from structure points"
        )

    if any(
        item.point in source.vertices
        for item in source.suppressed
    ):
        raise ValueError(
            "suppressed short-term points must not be "
            "medium-recognition vertices"
        )
```

Add a temporary neutral builder at the end so the initial tests exercise validation:

```python
def build_medium_term_structure(
    source: ShortTermStructure,
) -> MediumTermStructure:
    """Build canonical medium structure from cleaned short-term vertices."""

    _validate_short_term_source(source)
    potentials: tuple[PotentialMediumTermPoint, ...] = ()
    if len(source.vertices) == 2:
        previous, pivot = source.vertices
        if (
            previous.kind is pivot.kind
            and _is_strictly_more_extreme(pivot, previous)
        ):
            potentials = (PotentialMediumTermPoint(previous, pivot),)
    return MediumTermStructure((), potentials, (), (), ())
```

- [ ] **Step 4: Run the domain/validation tests and verify GREEN**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: every test currently in the file passes. No raw-candle or isolated-point recognition import exists in the new production module.

- [ ] **Step 5: Add strict recognition, confirmed-by, same-kind-neighbor, and potential tests**

Append to `tests/test_medium_term_structure.py`:

```python
def test_basic_ith_uses_strict_same_kind_neighbors() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0],
        low_prices=[90.0, 91.0, 92.0],
    )

    result = build_medium_term_structure(source)

    point = result.points[0]
    assert point.pivot is source.vertices[2]
    assert point.confirmed_by is source.vertices[4]
    assert point.pivot_index == 2
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 112.0
    assert point.confirmed_by_index == 4
    assert result.vertices == result.points


def test_basic_itl_uses_strict_same_kind_neighbors() -> None:
    source = alternating_source(
        high_prices=[110.0, 111.0, 112.0],
        low_prices=[100.0, 94.0, 98.0],
    )

    result = build_medium_term_structure(source)

    point = result.points[0]
    assert point.pivot is source.vertices[3]
    assert point.confirmed_by is source.vertices[5]
    assert point.pivot_index == 3
    assert point.kind is IsolatedPointKind.LOW
    assert point.price == 94.0
    assert point.confirmed_by_index == 5


@pytest.mark.parametrize(
    "high_prices",
    [
        [112.0, 112.0, 108.0],
        [105.0, 112.0, 112.0],
    ],
)
def test_ith_equality_on_either_side_rejects_confirmation(
    high_prices: list[float],
) -> None:
    source = alternating_source(
        high_prices=high_prices,
        low_prices=[90.0, 91.0, 92.0],
    )

    result = build_medium_term_structure(source)

    assert all(point.kind is not IsolatedPointKind.HIGH for point in result.points)


@pytest.mark.parametrize(
    "low_prices",
    [
        [94.0, 94.0, 98.0],
        [100.0, 94.0, 94.0],
    ],
)
def test_itl_equality_on_either_side_rejects_confirmation(
    low_prices: list[float],
) -> None:
    source = alternating_source(
        high_prices=[110.0, 111.0, 112.0],
        low_prices=low_prices,
    )

    result = build_medium_term_structure(source)

    assert all(point.kind is not IsolatedPointKind.LOW for point in result.points)


def test_opposite_kind_vertices_are_not_comparison_neighbors() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0],
        low_prices=[100.0, 94.0, 98.0],
    )

    result = build_medium_term_structure(source)

    assert [(point.pivot_index, point.kind) for point in result.points] == [
        (2, IsolatedPointKind.HIGH),
        (3, IsolatedPointKind.LOW),
    ]
    assert result.points[0].confirmed_by is source.vertices[4]
    assert result.points[1].confirmed_by is source.vertices[5]


def test_recognizer_does_not_skip_intervening_same_kind_vertex() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 120.0, 105.0],
        low_prices=[80.0, 81.0, 82.0, 83.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [120.0]
    assert all(point.price != 110.0 for point in result.points)


@pytest.mark.parametrize(
    "kind,prices",
    [
        (IsolatedPointKind.HIGH, [105.0, 112.0]),
        (IsolatedPointKind.LOW, [100.0, 94.0]),
    ],
)
def test_current_edge_candidate_is_separate_from_confirmed_output(
    kind: IsolatedPointKind,
    prices: list[float],
) -> None:
    source = short_structure(
        [
            short_point(1, kind, prices[0]),
            short_point(3, kind, prices[1]),
        ]
    )

    result = build_medium_term_structure(source)

    assert result.points == ()
    assert result.vertices == ()
    assert len(result.potentials) == 1
    assert result.potentials[0].pivot is source.vertices[1]
    assert result.potentials[0].previous_same_kind is source.vertices[0]


def test_potential_becomes_confirmed_only_after_right_high_exists() -> None:
    initial = short_structure(
        [
            short_point(1, IsolatedPointKind.HIGH, 105.0),
            short_point(3, IsolatedPointKind.HIGH, 112.0),
        ]
    )
    extended = short_structure(
        [
            *initial.vertices,
            short_point(5, IsolatedPointKind.HIGH, 108.0),
        ]
    )

    before = build_medium_term_structure(initial)
    after = build_medium_term_structure(extended)

    assert before.points == ()
    assert before.potentials[0].pivot_index == 3
    assert after.potentials == ()
    assert after.points[0].pivot is initial.vertices[1]
    assert after.points[0].confirmed_by is extended.vertices[2]
    assert after.points[0].confirmed_by_index == 5


def test_failed_potential_is_not_promoted() -> None:
    initial = short_structure(
        [
            short_point(1, IsolatedPointKind.HIGH, 105.0),
            short_point(3, IsolatedPointKind.HIGH, 112.0),
        ]
    )
    extended = short_structure(
        [
            *initial.vertices,
            short_point(5, IsolatedPointKind.HIGH, 115.0),
        ]
    )

    before = build_medium_term_structure(initial)
    after = build_medium_term_structure(extended)

    assert before.potentials[0].pivot_index == 3
    assert all(point.pivot_index != 3 for point in after.points)
    assert [potential.pivot_index for potential in after.potentials] == [5]


def test_confirmed_points_use_pivot_order_and_keep_confirming_sources() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0],
        low_prices=[100.0, 94.0, 98.0],
    )

    result = build_medium_term_structure(source)

    assert [point.pivot_index for point in result.points] == [2, 3]
    assert [point.confirmed_by_index for point in result.points] == [4, 5]
    assert all(
        point.confirmed_by.kind is point.pivot.kind
        and point.confirmed_by_index > point.pivot_index
        for point in result.points
    )
```

The final provenance test keeps pivot order and structural confirming-source metadata separate. `confirmed_by_index` must not be described as actual knowability time. Do not fabricate an invalid non-alternating cleaned source merely to force globally inverted source order.

- [ ] **Step 6: Run the recognition tests and verify RED**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: the new ITH/ITL, equality, same-kind-neighbor, promotion, and confirmed-by tests fail because the temporary builder does not yet scan chronological same-kind triples or expose general edge potentials.

- [ ] **Step 7: Implement strict recognition and potential extraction**

Replace the temporary builder with these private helpers and final Task 1 builder:

```python
def _is_strict_medium_pivot(
    previous: ShortTermPoint,
    pivot: ShortTermPoint,
    later: ShortTermPoint,
) -> bool:
    if pivot.kind is IsolatedPointKind.HIGH:
        return previous.price < pivot.price > later.price
    return previous.price > pivot.price < later.price


def _recognize_kind(
    vertices: tuple[ShortTermPoint, ...],
    kind: IsolatedPointKind,
) -> tuple[list[MediumTermPoint], PotentialMediumTermPoint | None]:
    same_kind = tuple(point for point in vertices if point.kind is kind)
    confirmed = [
        MediumTermPoint(pivot, later)
        for previous, pivot, later in zip(
            same_kind,
            same_kind[1:],
            same_kind[2:],
        )
        if _is_strict_medium_pivot(previous, pivot, later)
    ]

    potential: PotentialMediumTermPoint | None = None
    if len(same_kind) >= 2:
        previous, pivot = same_kind[-2:]
        if _is_strictly_more_extreme(pivot, previous):
            potential = PotentialMediumTermPoint(previous, pivot)
    return confirmed, potential


def _recognize_medium_points(
    vertices: tuple[ShortTermPoint, ...],
) -> tuple[
    tuple[MediumTermPoint, ...],
    tuple[PotentialMediumTermPoint, ...],
]:
    high_points, high_potential = _recognize_kind(
        vertices,
        IsolatedPointKind.HIGH,
    )
    low_points, low_potential = _recognize_kind(
        vertices,
        IsolatedPointKind.LOW,
    )

    point_by_index = {
        point.pivot_index: point
        for point in high_points + low_points
    }
    points = tuple(
        point_by_index[vertex.index]
        for vertex in vertices
        if vertex.index in point_by_index
    )

    potential_by_index = {
        potential.pivot_index: potential
        for potential in (high_potential, low_potential)
        if potential is not None
    }
    potentials = tuple(
        potential_by_index[vertex.index]
        for vertex in vertices
        if vertex.index in potential_by_index
    )
    return points, potentials


def build_medium_term_structure(
    source: ShortTermStructure,
) -> MediumTermStructure:
    """Build canonical medium structure from cleaned short-term vertices."""

    _validate_short_term_source(source)
    points, potentials = _recognize_medium_points(source.vertices)
    return MediumTermStructure(
        points=points,
        potentials=potentials,
        vertices=points,
        suppressed=(),
        course_evidence=(),
    )
```

The dictionary merge does not sort caller input. It projects recognized values back through the already validated source vertex chronology. Sliding triples ensure the recognizer cannot skip an intervening same-kind point.

- [ ] **Step 8: Run Task 1 tests and verify GREEN**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: every Task 1 test passes, including strict equality rejection, current potential isolation, failed-potential omission, and structural confirming-source provenance.

- [ ] **Step 9: Run lower-layer regressions and inspect Task 1 scope**

Run:

```bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v
git diff --check
```

Expected: all existing tests pass and the diff check has no output. Confirm the new module imports no candle, isolated-point detector, market-state, BMS, or SMS evaluator.

- [ ] **Step 10: Review and commit Task 1**

Review frozen records, exact enum values, source-only validation, strict same-kind triples, no silent sorting, pivot/confirmed-by separation, explicit real-time timing deferral, potential isolation, and absence of raw recognition logic.

```bash
git add trading/definitions/medium_term_structure.py tests/test_medium_term_structure.py
git commit -m "Add medium-term structure recognition"
```

---

### Task 2: Medium Consecutive Same-Kind Normalization

**Files:**
- Modify: `trading/definitions/medium_term_structure.py`
- Modify: `tests/test_medium_term_structure.py`

**Interfaces:**
- Consumes: Task 1 `MediumTermPoint`, `MediumTermSuppressionReason`, `SuppressedMediumTermPoint`, and the pivot-ordered confirmed tuple returned by `_recognize_medium_points()`.
- Produces: `build_medium_term_structure()` results whose `points` remain complete while `vertices` reduce each consecutive same-kind confirmed run to its objective extreme and `suppressed` records `CONSECUTIVE_SAME_KIND` in pivot chronology. `potentials` remain unchanged and separate.

- [ ] **Step 1: Add consecutive high/low and equal-tie tests**

Append to `tests/test_medium_term_structure.py`:

```python
def test_consecutive_medium_highs_keep_highest_vertex_and_all_points() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0, 86.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0, 115.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [item.point.price for item in result.suppressed] == [110.0, 115.0]
    assert all(
        item.reason is MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND
        for item in result.suppressed
    )


def test_consecutive_medium_lows_keep_lowest_vertex_and_all_points() -> None:
    source = alternating_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0, 135.0, 136.0],
        low_prices=[120.0, 90.0, 100.0, 80.0, 95.0, 85.0, 110.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 80.0, 85.0]
    assert [point.price for point in result.vertices] == [80.0]
    assert [item.point.price for item in result.suppressed] == [90.0, 85.0]


def test_equal_highest_medium_high_keeps_earliest_pivot() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 105.0, 110.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 110.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed == (
        SuppressedMediumTermPoint(
            result.points[1],
            MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
    )


def test_equal_lowest_medium_low_keeps_earliest_pivot() -> None:
    source = alternating_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0],
        low_prices=[120.0, 90.0, 100.0, 90.0, 110.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 90.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed[0].point is result.points[1]


def test_same_kind_normalization_does_not_change_potentials() -> None:
    source = alternating_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 125.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [potential.price for potential in result.potentials] == [125.0]
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: the new normalization tests fail because Task 1 returns every confirmed point as a vertex and records no same-kind suppressions.

- [ ] **Step 3: Implement stable same-kind run reduction**

Add to `trading/definitions/medium_term_structure.py`:

```python
def _is_more_extreme_medium(
    candidate: MediumTermPoint,
    current: MediumTermPoint,
) -> bool:
    if current.kind is IsolatedPointKind.HIGH:
        return candidate.price > current.price
    return candidate.price < current.price


def _normalize_same_kind_runs(
    points: tuple[MediumTermPoint, ...],
) -> tuple[
    list[MediumTermPoint],
    list[SuppressedMediumTermPoint],
]:
    vertices: list[MediumTermPoint] = []
    suppressed: list[SuppressedMediumTermPoint] = []
    run: list[MediumTermPoint] = []

    def flush_run() -> None:
        if not run:
            return
        winner = run[0]
        for candidate in run[1:]:
            if _is_more_extreme_medium(candidate, winner):
                winner = candidate
        vertices.append(winner)
        suppressed.extend(
            SuppressedMediumTermPoint(
                point,
                MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND,
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
```

Update `build_medium_term_structure()` after recognition:

```python
    points, potentials = _recognize_medium_points(source.vertices)
    vertices, suppressed = _normalize_same_kind_runs(points)
    return MediumTermStructure(
        points=points,
        potentials=potentials,
        vertices=tuple(vertices),
        suppressed=tuple(suppressed),
        course_evidence=(),
    )
```

The strict extreme comparison retains the earliest pivot on equality. Every non-winning confirmed point remains in `points` and appears once in suppression evidence.

- [ ] **Step 4: Run Task 2 tests and verify GREEN**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: every Task 1 and Task 2 test passes.

- [ ] **Step 5: Run focused lower-layer regressions and diff checks**

Run:

```bash
pytest tests/test_short_term_structure.py -v
pytest tests/test_market_structure.py -v
git diff --check
```

Expected: existing suites pass and the diff check has no output. Confirm equality changes only the selected vertex, not recognition or point evidence.

- [ ] **Step 6: Review and commit Task 2**

Review high/low mirroring, earliest-on-equality, suppression order, preserved `points`, unchanged potentials, and absence of thresholds.

```bash
git add trading/definitions/medium_term_structure.py tests/test_medium_term_structure.py
git commit -m "Add medium same-kind normalization"
```

---

### Task 3: Provisional Medium Inside-Structure Normalization

**Files:**
- Modify: `trading/definitions/medium_term_structure.py`
- Modify: `tests/test_medium_term_structure.py`

**Interfaces:**
- Consumes: alternating confirmed vertex candidates and same-kind suppressions from Task 2.
- Produces: `build_medium_term_structure()` results with inclusive, mirrored, repeated definite inside normalization; `INSIDE_STRUCTURE` suppression evidence is appended after same-kind suppression evidence.

**Exact pairing representation:** After same-kind normalization, pair current vertices from the beginning as `[0, 1]`, `[2, 3]`, and so on. Each complete pair must contain one medium high and one medium low. Compare each complete later pair with the immediately previous complete pair in the current candidate list. Suppress the entire later pair only when both inclusive containment conditions hold. Preserve an unmatched final vertex. When suppression creates a new adjacency, compare again against the same earlier pair; otherwise advance by two vertices.

- [ ] **Step 1: Add a source helper and inclusive mirrored inside tests**

Append to `tests/test_medium_term_structure.py`:

```python
def paired_medium_source(
    earlier_high: float,
    earlier_low: float,
    later_high: float,
    later_low: float,
    *,
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> ShortTermStructure:
    return alternating_source(
        high_prices=[
            earlier_high - 5.0,
            earlier_high,
            min(earlier_high, later_high) - 6.0,
            later_high,
            later_high - 5.0,
        ],
        low_prices=[
            earlier_low + 5.0,
            earlier_low,
            max(earlier_low, later_low) + 6.0,
            later_low,
            later_low + 5.0,
        ],
        first_kind=first_kind,
    )


@pytest.mark.parametrize(
    "first_kind",
    [IsolatedPointKind.HIGH, IsolatedPointKind.LOW],
)
def test_complete_inside_pair_is_suppressed_in_both_orientations(
    first_kind: IsolatedPointKind,
) -> None:
    source = paired_medium_source(
        110.0,
        100.0,
        108.0,
        102.0,
        first_kind=first_kind,
    )

    result = build_medium_term_structure(source)

    assert len(result.points) == 4
    assert result.vertices == result.points[:2]
    assert result.suppressed == tuple(
        SuppressedMediumTermPoint(
            point,
            MediumTermSuppressionReason.INSIDE_STRUCTURE,
        )
        for point in result.points[2:]
    )


@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (110.0, 102.0),
        (108.0, 100.0),
        (110.0, 100.0),
    ],
)
def test_equality_at_medium_inside_boundary_counts_as_contained(
    later_high: float,
    later_low: float,
) -> None:
    source = paired_medium_source(110.0, 100.0, later_high, later_low)

    result = build_medium_term_structure(source)

    assert result.vertices == result.points[:2]
```

- [ ] **Step 2: Add breakout, incomplete, repeated, and ambiguity-preservation tests**

Append:

```python
@pytest.mark.parametrize(
    "later_high,later_low",
    [
        (111.0, 102.0),
        (108.0, 99.0),
    ],
)
def test_one_side_breakout_preserves_later_medium_pair(
    later_high: float,
    later_low: float,
) -> None:
    source = paired_medium_source(110.0, 100.0, later_high, later_low)

    result = build_medium_term_structure(source)

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_incomplete_later_medium_range_is_preserved() -> None:
    source = alternating_source(
        high_prices=[105.0, 110.0, 104.0, 108.0, 103.0],
        low_prices=[105.0, 100.0, 106.0, 107.0, 108.0],
    )

    result = build_medium_term_structure(source)

    assert [(point.kind, point.price) for point in result.points] == [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 100.0),
        (IsolatedPointKind.HIGH, 108.0),
    ]
    assert result.vertices == result.points
    assert result.suppressed == ()


def test_repeated_inside_medium_pairs_normalize_until_stable() -> None:
    source = alternating_source(
        high_prices=[100.0, 120.0, 99.0, 115.0, 98.0, 110.0, 97.0],
        low_prices=[110.0, 90.0, 111.0, 95.0, 112.0, 100.0, 113.0],
    )

    result = build_medium_term_structure(source)

    assert [point.price for point in result.vertices] == [120.0, 90.0]
    assert [item.point for item in result.suppressed] == list(result.points[2:])
    assert all(
        item.reason is MediumTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.suppressed
    )


def test_non_contained_layout_is_preserved_without_chart_matching() -> None:
    source = paired_medium_source(110.0, 100.0, 115.0, 95.0)

    result = build_medium_term_structure(source)

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_suppression_order_is_phase_then_pivot_chronology() -> None:
    source = alternating_source(
        high_prices=[
            100.0,
            110.0,
            105.0,
            120.0,
            107.0,
            115.0,
            100.0,
            101.0,
        ],
        low_prices=[
            100.0,
            99.0,
            98.0,
            97.0,
            90.0,
            96.0,
            92.0,
            98.0,
        ],
    )

    result = build_medium_term_structure(source)

    reasons = [item.reason for item in result.suppressed]
    assert reasons[0] is MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND
    assert reasons[1:] == [
        MediumTermSuppressionReason.INSIDE_STRUCTURE,
        MediumTermSuppressionReason.INSIDE_STRUCTURE,
    ]
```

The mixed-phase fixture recognizes `HIGH 110`, `HIGH 120`, `LOW 90`, `HIGH 115`, and `LOW 92` in pivot order. Same-kind cleanup suppresses `HIGH 110`; the later `HIGH 115 / LOW 92` range is then objectively inside `HIGH 120 / LOW 90`.

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: inside, equality, and repeated-containment tests fail because Task 2 retains every alternating confirmed medium candidate and records no `INSIDE_STRUCTURE` suppressions. Existing recognition and same-kind tests remain green.

- [ ] **Step 4: Implement the smallest provisional inside helpers**

Add to `trading/definitions/medium_term_structure.py`:

```python
def _pair_bounds(
    first: MediumTermPoint,
    second: MediumTermPoint,
) -> tuple[float, float] | None:
    if first.kind is second.kind:
        return None
    high = first if first.kind is IsolatedPointKind.HIGH else second
    low = first if first.kind is IsolatedPointKind.LOW else second
    return high.price, low.price


def _later_pair_is_inside(
    earlier: tuple[MediumTermPoint, MediumTermPoint],
    later: tuple[MediumTermPoint, MediumTermPoint],
) -> bool:
    earlier_bounds = _pair_bounds(*earlier)
    later_bounds = _pair_bounds(*later)
    if earlier_bounds is None or later_bounds is None:
        return False
    earlier_high, earlier_low = earlier_bounds
    later_high, later_low = later_bounds
    return later_high <= earlier_high and later_low >= earlier_low


def _normalize_inside_structures(
    vertices: list[MediumTermPoint],
) -> tuple[
    list[MediumTermPoint],
    list[SuppressedMediumTermPoint],
]:
    normalized = list(vertices)
    suppressed: list[SuppressedMediumTermPoint] = []
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
                SuppressedMediumTermPoint(
                    point,
                    MediumTermSuppressionReason.INSIDE_STRUCTURE,
                )
                for point in removed
            )
            changed = True

    return normalized, suppressed
```

Update the normalization portion of `build_medium_term_structure()`:

```python
    points, potentials = _recognize_medium_points(source.vertices)
    same_kind_vertices, same_kind_suppressed = _normalize_same_kind_runs(
        points
    )
    vertices, inside_suppressed = _normalize_inside_structures(
        same_kind_vertices
    )
    return MediumTermStructure(
        points=points,
        potentials=potentials,
        vertices=tuple(vertices),
        suppressed=tuple(same_kind_suppressed + inside_suppressed),
        course_evidence=(),
    )
```

This repeats only inclusive complete containment. It does not extend or replace the earlier range, skip a complete pair, infer trend, or synthesize an unmatched boundary.

- [ ] **Step 5: Run Task 3 tests and verify GREEN**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: all medium unit tests pass, including both pair orientations, equality, both one-side breakout directions, unmatched-range preservation, stable repetition, and suppression evidence.

- [ ] **Step 6: Run existing structure regressions and inspect scope**

Run:

```bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
git diff --check
```

Expected: every suite passes and the diff check has no output. Inspect the medium module for only the provisional two-boundary rule and no BMS/SMS, market-state, timeframe, or trend dependency.

- [ ] **Step 7: Review and commit Task 3**

Review inclusive containment, one-side breakout preservation, both orientations, unmatched-point preservation, repeated stability, phase-ordered suppressions, and ambiguous-layout preservation.

```bash
git add trading/definitions/medium_term_structure.py tests/test_medium_term_structure.py
git commit -m "Add medium inside normalization"
```

---

### Task 4: Cross-Layer Integration and Evidence-Only Course Metadata

**Files:**
- Create: `tests/test_medium_term_structure_integration.py`
- Modify: `trading/definitions/medium_term_structure.py`
- Modify: `tests/test_medium_term_structure.py`

**Interfaces:**
- Consumes: existing strict and deformation-aware isolated-point functions; Lesson 5 mapping and `build_short_term_structure()`; Tasks 1-3 `build_medium_term_structure()` and immutable medium records.
- Produces: `attach_course_evidence(structure: MediumTermStructure, evidence: Sequence[MediumCourseEvidence]) -> MediumTermStructure`; focused proof that real Chapter 1 recognition reaches Lesson 6 through cleaned Lesson 5 vertices; proof that suppressed short-term points are not medium neighbors; proof that evidence attachment cannot alter canonical output.

- [ ] **Step 1: Add course-evidence attachment tests first**

Extend the import from `trading.definitions.medium_term_structure` in `tests/test_medium_term_structure.py` with `attach_course_evidence`, then append:

```python
def test_course_evidence_attachment_preserves_all_canonical_output() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0],
        low_prices=[90.0, 91.0, 92.0],
    )
    structure = build_medium_term_structure(source)
    evidence = MediumCourseEvidence(
        structure.points[0],
        CourseRuleMatch.UNKNOWN,
    )

    enriched = attach_course_evidence(structure, [evidence])

    assert enriched.points == structure.points
    assert enriched.potentials == structure.potentials
    assert enriched.vertices == structure.vertices
    assert enriched.suppressed == structure.suppressed
    assert enriched.course_evidence == (evidence,)
    assert structure.course_evidence == ()


def test_course_evidence_requires_an_existing_confirmed_point() -> None:
    source = alternating_source(
        high_prices=[105.0, 112.0, 108.0],
        low_prices=[90.0, 91.0, 92.0],
    )
    structure = build_medium_term_structure(source)
    unrelated = MediumTermPoint(
        short_point(20, IsolatedPointKind.HIGH, 130.0),
        short_point(22, IsolatedPointKind.HIGH, 125.0),
    )

    with pytest.raises(ValueError, match="requires a confirmed medium point"):
        attach_course_evidence(
            structure,
            [MediumCourseEvidence(unrelated, CourseRuleMatch.YES)],
        )
```

- [ ] **Step 2: Run evidence tests and verify RED**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: collection fails with `ImportError` for `attach_course_evidence`, or the new tests fail because the attachment function does not exist. Existing canonical behavior remains green.

- [ ] **Step 3: Implement immutable evidence attachment without inference**

Add to `trading/definitions/medium_term_structure.py`:

```python
def attach_course_evidence(
    structure: MediumTermStructure,
    evidence: Sequence[MediumCourseEvidence],
) -> MediumTermStructure:
    """Attach external diagnostic evidence without changing canonical output."""

    evidence_tuple = tuple(evidence)
    if any(item.point not in structure.points for item in evidence_tuple):
        raise ValueError("course evidence requires a confirmed medium point")
    return MediumTermStructure(
        points=structure.points,
        potentials=structure.potentials,
        vertices=structure.vertices,
        suppressed=structure.suppressed,
        course_evidence=evidence_tuple,
    )
```

Do not add creator fields, candle inputs, BMS/SMS calls, break scanning, or any function that calculates `CourseRuleMatch`. The caller supplies the diagnostic enum explicitly.

- [ ] **Step 4: Run evidence tests and verify GREEN**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: every medium unit test passes, and the original frozen structure remains unchanged after attachment.

- [ ] **Step 5: Verify the integration artifact is absent for RED**

Run before creating the file:

```bash
pytest tests/test_medium_term_structure_integration.py -v
```

Expected: pytest reports `file or directory not found: tests/test_medium_term_structure_integration.py`. This is the integration-artifact RED checkpoint; production behaviors already followed red-to-green cycles in Tasks 1-4.

- [ ] **Step 6: Add strict/deformation composition and cleaned-source boundary tests**

Create `tests/test_medium_term_structure_integration.py`:

```python
from trading.definitions.candles import Candle
from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    confirm_isolated_point_with_deformation,
)
from trading.definitions.isolated_points import (
    IsolatedPointKind,
    detect_confirmed_isolated_point,
    get_potential_isolated_point,
)
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumCourseEvidence,
    attach_course_evidence,
    build_medium_term_structure,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def candle(high: float, low: float) -> Candle:
    midpoint = (high + low) / 2
    return Candle(midpoint, high, low, midpoint)


def require_strict_short_point(
    candles: list[Candle],
    index: int,
) -> ShortTermPoint:
    recognized = detect_confirmed_isolated_point(
        candles[index - 1],
        candles[index],
        candles[index + 1],
        index=index,
    )
    assert recognized is not None
    return short_term_point_from_isolated_point(recognized)


def test_real_strict_and_deformation_paths_reach_medium_structure() -> None:
    candles = [
        candle(100.0, 90.0),
        candle(105.0, 95.0),
        candle(102.0, 92.0),
        candle(112.0, 96.0),
        candle(106.0, 98.0),
        candle(104.0, 94.0),
        candle(108.0, 99.0),
        candle(105.0, 96.0),
    ]
    strict_high_1 = require_strict_short_point(candles, 1)
    strict_low_1 = require_strict_short_point(candles, 2)

    potential = get_potential_isolated_point(
        candles[2],
        candles[3],
        index=3,
    )
    assert potential is not None
    deformation = confirm_isolated_point_with_deformation(
        potential,
        candles[3],
        candles[4],
    )
    assert deformation is not None
    deformation_high = short_term_point_from_recognition(deformation)

    strict_low_2 = require_strict_short_point(candles, 5)
    strict_high_3 = require_strict_short_point(candles, 6)
    short_points = [
        strict_high_1,
        strict_low_1,
        deformation_high,
        strict_low_2,
        strict_high_3,
    ]

    short_structure = build_short_term_structure(short_points)
    medium_structure = build_medium_term_structure(short_structure)

    assert short_structure.vertices == tuple(short_points)
    assert deformation_high.recognition_basis is (
        IsolatedPointBasis.RIGHT_INSIDE_BAR
    )
    assert len(medium_structure.points) == 1
    assert medium_structure.points[0].pivot is deformation_high
    assert medium_structure.points[0].pivot_index == 3
    assert medium_structure.points[0].confirmed_by is strict_high_3
    assert medium_structure.points[0].confirmed_by_index == 6


def test_suppressed_short_term_point_is_not_a_medium_neighbor() -> None:
    short_points = [
        ShortTermPoint(1, IsolatedPointKind.HIGH, 105.0, None),
        ShortTermPoint(2, IsolatedPointKind.LOW, 90.0, None),
        ShortTermPoint(3, IsolatedPointKind.HIGH, 111.0, None),
        ShortTermPoint(4, IsolatedPointKind.HIGH, 112.0, None),
        ShortTermPoint(5, IsolatedPointKind.LOW, 92.0, None),
        ShortTermPoint(6, IsolatedPointKind.HIGH, 108.0, None),
    ]

    short_structure = build_short_term_structure(short_points)
    medium_structure = build_medium_term_structure(short_structure)

    suppressed_short_point = short_points[2]
    assert suppressed_short_point in short_structure.points
    assert suppressed_short_point not in short_structure.vertices
    assert [point.pivot for point in medium_structure.points] == [
        short_points[3]
    ]
    assert all(
        point.pivot is not suppressed_short_point
        for point in medium_structure.points
    )


def test_external_course_evidence_cannot_change_integrated_output() -> None:
    short_points = [
        ShortTermPoint(1, IsolatedPointKind.HIGH, 105.0, None),
        ShortTermPoint(2, IsolatedPointKind.LOW, 90.0, None),
        ShortTermPoint(3, IsolatedPointKind.HIGH, 112.0, None),
        ShortTermPoint(4, IsolatedPointKind.LOW, 92.0, None),
        ShortTermPoint(5, IsolatedPointKind.HIGH, 108.0, None),
    ]
    canonical = build_medium_term_structure(
        build_short_term_structure(short_points)
    )
    evidence = MediumCourseEvidence(
        canonical.points[0],
        CourseRuleMatch.UNKNOWN,
    )

    enriched = attach_course_evidence(canonical, [evidence])

    assert enriched.points == canonical.points
    assert enriched.potentials == canonical.potentials
    assert enriched.vertices == canonical.vertices
    assert enriched.suppressed == canonical.suppressed
    assert enriched.course_evidence == (evidence,)
```

The first test uses real strict and `RIGHT_INSIDE_BAR` recognition. The second intentionally begins from confirmed `ShortTermPoint` values because it is testing Lesson 5 line cleanup as the source boundary, not re-testing candle recognition.

- [ ] **Step 7: Run the focused integration suite and verify GREEN**

Run:

```bash
pytest tests/test_medium_term_structure_integration.py -v
```

Expected: all integration tests pass. The deformation-aware high remains the source pivot, `confirmed_by` is the immediate later cleaned same-kind high at structural pivot index 6, the model does not invent an actual knowability timestamp from the candle at index 7, and the suppressed short-term point never enters medium recognition.

- [ ] **Step 8: Run all Lesson 5 and Lesson 6 tests together**

Run:

```bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
```

Expected: all short-term and medium-term unit/integration tests pass.

- [ ] **Step 9: Run Chapter 1 and existing Chapter 2 regressions**

Run each command separately:

```bash
pytest tests/test_isolated_points.py -v
pytest tests/test_isolated_point_deformations.py -v
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
git diff --check
```

Expected: every existing suite passes and the diff check has no output. Do not record a predicted pass count.

- [ ] **Step 10: Review and commit Task 4**

Review both recognition paths, cleaned-vertex-only input, preserved recognition basis, suppressed-point exclusion, external-only course evidence, and unchanged canonical output after evidence attachment.

```bash
git add trading/definitions/medium_term_structure.py tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py
git commit -m "Add medium structure integration coverage"
```

---

### Task 5: Full Regression, Scope, and Chapter-Continuation Gate

**Files:**
- Verify: `trading/definitions/medium_term_structure.py`
- Verify: `tests/test_medium_term_structure.py`
- Verify: `tests/test_medium_term_structure_integration.py`
- Do not create a verification-only commit.

**Interfaces:**
- Consumes: the complete four-commit Lesson 6 feature branch.
- Produces: fresh test, formatting, scope, and review evidence that the feature is ready for independent GitHub review without merging to `main`.

- [ ] **Step 1: Run the complete Lesson 6 unit suite**

Run:

```bash
pytest tests/test_medium_term_structure.py -v
```

Expected: PASS for domain invariants, strict recognition, equality rejection, same-kind neighbors, edge potentials, structural confirming-source provenance, explicit knowability deferral, same-kind cleanup, provisional inside cleanup, and evidence attachment.

- [ ] **Step 2: Run the complete Lesson 6 integration suite**

Run:

```bash
pytest tests/test_medium_term_structure_integration.py -v
```

Expected: PASS for strict/deformation composition, cleaned-vertex source enforcement, short-term suppression exclusion, and evidence-only behavior.

- [ ] **Step 3: Run Lesson 5 and Chapter 1 regressions**

Run:

```bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v
```

Expected: PASS with no change to isolated-point recognition, recognition basis, short-term points, or Lesson 5 normalization.

- [ ] **Step 4: Run all existing structural-lesson regressions**

Run:

```bash
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
```

Expected: PASS with no change to Lesson 1 market state, Lesson 2 BMS, or Lesson 3 SMS semantics.

- [ ] **Step 5: Run the complete repository verification**

Run:

```bash
pytest -q
git diff --check
python -c "from pathlib import Path; assert not Path('tests/test_course_market_structure_scenarios.py').exists()"
```

Expected: the full repository suite passes, `git diff --check` has no output, and the formal Chapter 2 Level 2 file remains absent.

- [ ] **Step 6: Verify feature scope against the implementation base**

Fetch the current remote reference, then verify that `origin/main` still equals the exact implementation-base SHA recorded in the SDD ledger when the feature branch was created:

```bash
git fetch origin main
git rev-parse origin/main
```

If `origin/main` has moved from the recorded implementation base, STOP and report the divergence. Do not silently compare against a different base, rebase, merge, or redefine the implementation base.

Only after the SHA matches, compare the feature branch against that unchanged base:

```bash
git diff --name-only origin/main...HEAD
git log --oneline origin/main..HEAD
git status --short
```

Expected changed files only:

```text
docs/superpowers/specs/2026-09-02-medium-term-structure-design.md
docs/superpowers/plans/2026-09-02-medium-term-structure.md
trading/definitions/medium_term_structure.py
tests/test_medium_term_structure.py
tests/test_medium_term_structure_integration.py
```

Expected implementation history contains the four task commits, plus only narrowly scoped review-fix commits if a valid finding required them. The feature worktree is clean.

- [ ] **Step 7: Inspect forbidden coupling and deferred concepts**

Run:

```bash
git grep -n -E "Candle|detect_confirmed_isolated_point|confirm_isolated_point|evaluate_bms|evaluate_sms|classify_market_state|timeframe|long.term|strategy|signal|entry|exit|risk|broker|execution|machine.learning" -- trading/definitions/medium_term_structure.py
```

Expected: no raw-candle recognition, BMS/SMS evaluation, market-state inference, timeframe mapping, long-term recognition, or strategy/execution coupling. `CourseRuleMatch` and `attach_course_evidence()` are passive metadata interfaces only.

- [ ] **Step 8: Perform the broad final whole-branch review**

Dispatch the most capable available reviewer against both:

- `docs/superpowers/specs/2026-09-02-medium-term-structure-design.md`
- `docs/superpowers/plans/2026-09-02-medium-term-structure.md`

The review must check:

- `ShortTermStructure.vertices` is the only canonical neighbor source;
- `.points` and short-term suppressions never become hidden medium neighbors;
- strict same-kind comparisons and equality rejection;
- no skipped same-kind point;
- potential/confirmed separation and failed-potential omission;
- pivot provenance and the exact right same-kind `confirmed_by` source;
- `confirmed_by_index` is not represented as actual knowability time and no
  `known_at_index` is invented;
- pivot-ordered canonical output;
- complete confirmed-point evidence despite normalization;
- earliest equal-extreme tie handling;
- provisional inclusive two-boundary inside handling;
- one-side breakout and incomplete-range preservation;
- stable repeated containment without range extension or replacement;
- external diagnostic evidence cannot alter canonical output;
- no course break engine, long-term logic, timeframe mapping, BMS/SMS reinterpretation, market-state inference, or trading behavior; and
- no formal Chapter 2 Level 2 suite.

Fix every valid Critical or Important finding on the feature branch, use red-to-green TDD for behavioral fixes, commit each coherent fix, perform scoped re-review, and rerun the affected tests plus `pytest -q` and `git diff --check`.

- [ ] **Step 9: Push the reviewed feature branch without merging**

After all tests and reviews pass and the worktree is clean:

```bash
git push -u origin feature/medium-term-structure
```

Expected: the feature branch is available for independent GitHub review. Do not push implementation commits directly to `origin/main`, do not merge, do not squash, and do not begin Lesson 7.

---

## Final Review and Execution Handoff

At implementation time:

1. fetch `origin/main`;
2. verify local `main` equals `origin/main` and that `origin/main` is the approved latest Lesson 6 implementation-plan checkpoint named by the user for execution;
3. record that exact `origin/main` SHA as the implementation base, then use `superpowers:using-git-worktrees` to create or verify the isolated `feature/medium-term-structure` branch and worktree from that exact remote checkpoint;
4. create the SDD workspace/ledger for this exact plan and record the implementation-base SHA in it;
5. run the SDD pre-flight consistency scan against the approved spec;
6. use `superpowers:subagent-driven-development` as the recommended executor, with a fresh implementer and task review for Tasks 1-4;
7. use `superpowers:executing-plans` only when subagent-driven execution is unavailable;
8. record RED/GREEN evidence, reviewer verdicts, rulings, and commit SHAs in the ledger;
9. complete Task 5 verification and broad whole-branch review; and
10. push only the reviewed feature branch for independent review.

Do not merge Lesson 6 into `main` until the user explicitly selects the repository's finishing workflow after independent review.
