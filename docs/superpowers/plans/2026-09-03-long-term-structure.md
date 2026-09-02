# Long-Term Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the explicit Chapter 2 Lesson 7 long-term structure layer that promotes cleaned medium-term vertices into canonical long-term structure.

**Architecture:** Use an explicit long-term module that consumes only `MediumTermStructure.vertices`, applies the approved strict same-kind three-point promotion, preserves medium-point provenance, then performs long-term same-kind and provisional inside normalization. Keep the teacher creator/break method passive as optional diagnostic evidence.

**Tech Stack:** Python, dataclasses, Enum, pytest, existing project market-structure modules.

**Spec:** `docs/superpowers/specs/2026-09-03-long-term-structure-design.md`

## Global Constraints

- The approved specification is binding. If this plan conflicts with it, stop and follow the specification.
- Implement Chapter 2 Lesson 7 only.
- Long-term recognition consumes an explicit `MediumTermStructure` and uses only its cleaned `vertices`.
- Never scan all `MediumTermStructure.points` or use suppressed medium points as hidden recognition neighbors.
- Use immediate previous and next same-kind cleaned medium vertices; never skip an intervening same-kind vertex.
- HIGH confirmation is strict `previous.price < pivot.price > later.price`.
- LOW confirmation is strict `previous.price > pivot.price < later.price`.
- Equality on either side rejects confirmation.
- Keep canonical confirmed points, right-edge potentials, normalized vertices, suppressions, and optional course evidence as separate collections.
- Preserve the exact `MediumTermPoint` objects used as `pivot` and `confirmed_by`.
- `confirmed_by_index` is structural source location only. Do not add `known_at_index`, `confirmed_at_index`, executable timing, or availability timestamps.
- Validate all source chronology and membership invariants before producing canonical output. Do not silently sort or repair input.
- Same-kind normalization retains the most extreme confirmed point, with the earliest pivot winning an exact price tie.
- Provisional inside normalization suppresses a later complete pair only when `later_high <= earlier_high` and `later_low >= earlier_low`, supports both orientations, repeats until stable, and preserves unmatched final points.
- The teacher creator/break method is optional diagnostic evidence only and cannot alter canonical output.
- Reuse `CourseRuleMatch` from `medium_term_structure.py`; its `YES | NO | UNKNOWN` semantics are identical and reuse does not couple evidence to recognition.
- Do not refactor the medium-term module to remove duplication or create a generic recursive hierarchy engine.
- Do not rescan candles, isolated points, short-term points, or lower-level collections inside the long-term production module.
- Do not add timeframe mappings, automatic creator/trend-context selection, BMS/SMS reinterpretation, market-state inference, reversal decisions, strategy, signals, entries, exits, risk, sizing, broker, order, execution, machine-learning, or Lesson 8 behavior.
- Do not create `tests/test_course_market_structure_scenarios.py`; formal Chapter 2 Level-2 validation remains deferred until Lesson 8 is understood.
- Use red-to-green TDD for every production behavior, with a fresh implementer subagent and both spec-compliance and code-quality review after every implementation task.
- Every RED command must collect and execute its test, then report `FAILED`
  because the intended behavior is missing. Import errors, collection errors,
  syntax errors, missing test files, and other setup failures are never RED.

## Planned File Structure

Create exactly:

- `trading/definitions/long_term_structure.py` 鈥?explicit Lesson 7 domain records, source validation, canonical recognition, normalization, and passive evidence attachment.
- `tests/test_long_term_structure.py` 鈥?focused domain, validation, recognition, potential, normalization, and evidence unit tests.
- `tests/test_long_term_structure_integration.py` 鈥?real Chapter 1 through Lesson 7 composition and the cleaned-medium-vertex boundary proof.

Do not modify package export files. Both `trading/__init__.py` and
`trading/definitions/__init__.py` are intentionally docstring-only, and the
current project imports definition modules directly.

## Locked Interfaces

The production module must expose:

~~~python
class LongTermSuppressionReason(Enum):
    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


@dataclass(frozen=True)
class LongTermPoint:
    pivot: MediumTermPoint
    confirmed_by: MediumTermPoint

    @property
    def pivot_index(self) -> int: ...

    @property
    def confirmed_by_index(self) -> int: ...

    @property
    def kind(self) -> IsolatedPointKind: ...

    @property
    def price(self) -> float: ...


@dataclass(frozen=True)
class PotentialLongTermPoint:
    previous_same_kind: MediumTermPoint
    pivot: MediumTermPoint

    @property
    def pivot_index(self) -> int: ...

    @property
    def kind(self) -> IsolatedPointKind: ...

    @property
    def price(self) -> float: ...


@dataclass(frozen=True)
class SuppressedLongTermPoint:
    point: LongTermPoint
    reason: LongTermSuppressionReason


@dataclass(frozen=True)
class LongCourseEvidence:
    point: LongTermPoint
    course_rule_match: CourseRuleMatch


@dataclass(frozen=True)
class LongTermStructure:
    points: tuple[LongTermPoint, ...]
    potentials: tuple[PotentialLongTermPoint, ...]
    vertices: tuple[LongTermPoint, ...]
    suppressed: tuple[SuppressedLongTermPoint, ...]
    course_evidence: tuple[LongCourseEvidence, ...] = ()


def build_long_term_structure(
    source: MediumTermStructure,
) -> LongTermStructure: ...


def attach_course_evidence(
    structure: LongTermStructure,
    evidence: Sequence[LongCourseEvidence],
) -> LongTermStructure: ...
~~~

`LongTermPoint` delegates:

~~~python
pivot_index = pivot.pivot_index
confirmed_by_index = confirmed_by.pivot_index
kind = pivot.kind
price = pivot.price
~~~

It validates same-kind sources and
`confirmed_by.pivot_index > pivot.pivot_index`.

`PotentialLongTermPoint` validates same-kind sources, increasing pivot
chronology, and a strictly more-extreme edge pivot.

---

## Future Execution Protocol

At implementation kickoff:

1. Invoke `superpowers:using-git-worktrees`.
2. Fetch `origin/main`, verify local `main == origin/main`, and verify that
   remote checkpoint is the approved Lesson 7 implementation-plan commit.
3. Record that exact SHA as the implementation base in the SDD ledger.
4. Create `feature/long-term-structure` and its isolated worktree from that
   exact checkpoint; do not implement directly on `main`.
5. Create the SDD workspace/ledger for this exact plan.
6. Read the complete specification and this complete plan, then record the
   pre-flight consistency scan in the ledger.
7. Use `superpowers:subagent-driven-development`, with a fresh implementer
   subagent for Tasks 1-7.
8. For every task, preserve RED and GREEN evidence, run required regressions,
   commit the coherent change, run spec-compliance review, run code-quality
   review, fix every valid finding, re-review fixes, and record verdicts and
   commit SHAs in the ledger.
9. Use the specification as authority over the plan if any discrepancy is
   discovered.
10. Run Task 8 and a broad final whole-branch review.
11. Invoke `superpowers:verification-before-completion` before claiming the
    feature is ready.
12. Push only the reviewed feature branch for independent review.
13. Invoke `superpowers:finishing-a-development-branch` only after the user
    later selects an integration option. Never merge automatically.

---

### Task 1: Domain Records, Source Validation, and Neutral Construction

**Files:**

- Create: `trading/definitions/long_term_structure.py`
- Create: `tests/test_long_term_structure.py`

**Interfaces:**

- Consumes: `IsolatedPointKind`, `CourseRuleMatch`,
  `MediumTermPoint`, `MediumTermStructure`,
  `MediumTermSuppressionReason`, and `SuppressedMediumTermPoint`.
- Produces: all locked immutable records, direct record validation,
  `_validate_medium_term_source()`, and a neutral
  `build_long_term_structure(source: MediumTermStructure) -> LongTermStructure`.

- [ ] **Step 1: Write a collectable module-boundary test**

Create `tests/test_long_term_structure.py` with:

~~~python
from importlib import import_module, util


def test_long_term_module_exists() -> None:
    assert (
        util.find_spec("trading.definitions.long_term_structure")
        is not None
    )
~~~

The test module imports no nonexistent Lesson 7 module or symbol during
collection.

- [ ] **Step 2: Run the module-boundary test and verify behavioral RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_long_term_module_exists -v
~~~

Expected: pytest collects and runs the test, then reports `FAILED` because
`find_spec(...)` returns `None`. This is a normal assertion failure, not a
collection or import error.

- [ ] **Step 3: Add only the module required by the first RED**

Create `trading/definitions/long_term_structure.py` with:

~~~python
"""Canonical Chapter 2 long-term structure from cleaned medium vertices."""
~~~

Do not add public records, functions, recognition, or validation in this
bootstrap step.

- [ ] **Step 4: Run the module-boundary test and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_long_term_module_exists -v
~~~

Expected: the one module-boundary test passes.

- [ ] **Step 5: Add a collectable locked-API boundary test**

Append:

~~~python
def test_locked_long_term_api_is_exposed() -> None:
    module = import_module("trading.definitions.long_term_structure")
    expected_names = {
        "LongTermSuppressionReason",
        "LongTermPoint",
        "PotentialLongTermPoint",
        "SuppressedLongTermPoint",
        "LongCourseEvidence",
        "LongTermStructure",
        "build_long_term_structure",
        "attach_course_evidence",
    }

    missing = sorted(
        name for name in expected_names if not hasattr(module, name)
    )

    assert missing == []
~~~

- [ ] **Step 6: Run the locked-API test and verify behavioral RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_locked_long_term_api_is_exposed -v
~~~

Expected: pytest collects and runs the test, then reports `FAILED` with the
missing public names in the assertion diff. The existing module imports
successfully.

- [ ] **Step 7: Add only the public-name scaffold required by the API RED**

Replace the bootstrap module contents with:

~~~python
"""Canonical Chapter 2 long-term structure from cleaned medium vertices."""

from collections.abc import Sequence
from enum import Enum

from .medium_term_structure import (
    MediumTermStructure,
)


class LongTermSuppressionReason(Enum):
    pass


class LongTermPoint:
    pass


class PotentialLongTermPoint:
    pass


class SuppressedLongTermPoint:
    pass


class LongCourseEvidence:
    pass


class LongTermStructure:
    pass


def build_long_term_structure(
    source: MediumTermStructure,
) -> LongTermStructure:
    raise NotImplementedError("long-term structure behavior is not implemented")


def attach_course_evidence(
    structure: LongTermStructure,
    evidence: Sequence[LongCourseEvidence],
) -> LongTermStructure:
    raise NotImplementedError("course evidence attachment is not implemented")
~~~

This scaffold establishes only the locked public names. It does not implement
records, validation, canonical construction, or evidence behavior.

- [ ] **Step 8: Run both boundary tests and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: both boundary tests pass.

- [ ] **Step 9: Append the domain and source-validation behavioral tests**

Append to `tests/test_long_term_structure.py`:

~~~python
from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.long_term_structure import (
    LongCourseEvidence,
    LongTermPoint,
    LongTermStructure,
    LongTermSuppressionReason,
    PotentialLongTermPoint,
    SuppressedLongTermPoint,
    build_long_term_structure,
)
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumTermPoint,
    MediumTermStructure,
    MediumTermSuppressionReason,
    SuppressedMediumTermPoint,
)
from trading.definitions.short_term_structure import ShortTermPoint


def medium_point(
    pivot_index: int,
    kind: IsolatedPointKind,
    price: float,
    *,
    confirmed_by_index: int | None = None,
) -> MediumTermPoint:
    confirmer_index = (
        pivot_index + 1
        if confirmed_by_index is None
        else confirmed_by_index
    )
    return MediumTermPoint(
        ShortTermPoint(pivot_index, kind, price, None),
        ShortTermPoint(confirmer_index, kind, price, None),
    )


def medium_structure(
    vertices: list[MediumTermPoint] | tuple[MediumTermPoint, ...],
    *,
    points: list[MediumTermPoint] | tuple[MediumTermPoint, ...] | None = None,
    suppressed: tuple[SuppressedMediumTermPoint, ...] = (),
) -> MediumTermStructure:
    vertex_tuple = tuple(vertices)
    return MediumTermStructure(
        points=vertex_tuple if points is None else tuple(points),
        potentials=(),
        vertices=vertex_tuple,
        suppressed=suppressed,
        course_evidence=(),
    )


def alternating_medium_source(
    high_prices: list[float],
    low_prices: list[float],
    *,
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> MediumTermStructure:
    assert len(high_prices) == len(low_prices)
    vertices: list[MediumTermPoint] = []
    for position, (high, low) in enumerate(zip(high_prices, low_prices)):
        first_index = position * 20 + 1
        if first_kind is IsolatedPointKind.HIGH:
            high_index, low_index = first_index, first_index + 10
        else:
            low_index, high_index = first_index, first_index + 10
        high_point = medium_point(
            high_index,
            IsolatedPointKind.HIGH,
            high,
        )
        low_point = medium_point(
            low_index,
            IsolatedPointKind.LOW,
            low,
        )
        vertices.extend(
            (high_point, low_point)
            if first_kind is IsolatedPointKind.HIGH
            else (low_point, high_point)
        )
    return medium_structure(vertices)


def test_long_term_domain_values_are_stable_and_frozen() -> None:
    pivot = medium_point(30, IsolatedPointKind.HIGH, 120.0)
    confirmed_by = medium_point(50, IsolatedPointKind.HIGH, 115.0)
    point = LongTermPoint(pivot, confirmed_by)
    potential = PotentialLongTermPoint(
        medium_point(10, IsolatedPointKind.HIGH, 110.0),
        pivot,
    )
    suppressed = SuppressedLongTermPoint(
        point,
        LongTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    evidence = LongCourseEvidence(point, CourseRuleMatch.UNKNOWN)
    structure = LongTermStructure(
        points=(point,),
        potentials=(potential,),
        vertices=(point,),
        suppressed=(suppressed,),
        course_evidence=(evidence,),
    )

    assert {reason.value for reason in LongTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }
    assert point.pivot is pivot
    assert point.confirmed_by is confirmed_by
    assert point.pivot_index == 30
    assert point.confirmed_by_index == 50
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 120.0
    assert not hasattr(point, "known_at_index")
    assert not hasattr(point, "confirmed_at_index")
    assert structure.course_evidence == (evidence,)
    with pytest.raises(FrozenInstanceError):
        point.confirmed_by = pivot  # type: ignore[misc]


def test_confirmed_long_point_requires_same_kind_sources() -> None:
    with pytest.raises(ValueError, match="same-kind pivot and confirmed_by"):
        LongTermPoint(
            medium_point(30, IsolatedPointKind.HIGH, 120.0),
            medium_point(50, IsolatedPointKind.LOW, 90.0),
        )


@pytest.mark.parametrize("confirmed_by_index", [20, 30])
def test_confirmed_long_point_requires_later_source(
    confirmed_by_index: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="confirmed_by pivot index must be after pivot index",
    ):
        LongTermPoint(
            medium_point(30, IsolatedPointKind.HIGH, 120.0),
            medium_point(
                confirmed_by_index,
                IsolatedPointKind.HIGH,
                115.0,
            ),
        )


def test_potential_long_point_validates_kind_chronology_and_extremity() -> None:
    previous_high = medium_point(10, IsolatedPointKind.HIGH, 110.0)

    with pytest.raises(ValueError, match="same-kind source points"):
        PotentialLongTermPoint(
            previous_high,
            medium_point(30, IsolatedPointKind.LOW, 90.0),
        )
    with pytest.raises(ValueError, match="indexes must be chronological"):
        PotentialLongTermPoint(
            previous_high,
            medium_point(5, IsolatedPointKind.HIGH, 120.0),
        )
    with pytest.raises(ValueError, match="must be more extreme"):
        PotentialLongTermPoint(
            previous_high,
            medium_point(30, IsolatedPointKind.HIGH, 110.0),
        )


@pytest.mark.parametrize(
    "vertices",
    [
        [
            medium_point(20, IsolatedPointKind.HIGH, 110.0),
            medium_point(10, IsolatedPointKind.LOW, 90.0),
        ],
        [
            medium_point(10, IsolatedPointKind.HIGH, 110.0),
            medium_point(10, IsolatedPointKind.LOW, 90.0),
        ],
    ],
)
def test_source_rejects_non_increasing_pivot_indexes(
    vertices: list[MediumTermPoint],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_long_term_structure(medium_structure(vertices))


def test_complete_source_chronology_is_validated_before_output() -> None:
    vertices = [
        medium_point(10, IsolatedPointKind.HIGH, 105.0),
        medium_point(40, IsolatedPointKind.HIGH, 112.0),
        medium_point(30, IsolatedPointKind.HIGH, 108.0),
    ]

    with pytest.raises(ValueError, match="strictly increasing"):
        build_long_term_structure(medium_structure(vertices))


def test_source_vertices_must_belong_to_medium_points() -> None:
    vertex = medium_point(30, IsolatedPointKind.HIGH, 112.0)

    with pytest.raises(ValueError, match="must come from structure points"):
        build_long_term_structure(medium_structure([vertex], points=[]))


def test_suppressed_medium_point_cannot_be_a_long_source_vertex() -> None:
    vertex = medium_point(30, IsolatedPointKind.HIGH, 112.0)
    suppression = SuppressedMediumTermPoint(
        vertex,
        MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )

    with pytest.raises(
        ValueError,
        match="must not be long-term recognition vertices",
    ):
        build_long_term_structure(
            medium_structure([vertex], suppressed=(suppression,))
        )


def test_empty_and_one_vertex_sources_are_neutral() -> None:
    empty = build_long_term_structure(medium_structure([]))
    one = build_long_term_structure(
        medium_structure(
            [medium_point(10, IsolatedPointKind.HIGH, 105.0)]
        )
    )

    assert empty == LongTermStructure((), (), (), (), ())
    assert one == LongTermStructure((), (), (), (), ())
~~~

- [ ] **Step 10: Run the domain and validation tests and verify behavioral RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: pytest collects and executes every test. The two boundary tests pass,
while the new domain and validation tests report `FAILED` because the scaffold
has no dataclass construction, enum values, delegated properties, validation,
or neutral builder behavior. There must be no collection/import/syntax error.

- [ ] **Step 11: Implement the immutable records and validation boundary**

Replace the public-name scaffold in
`trading/definitions/long_term_structure.py` with:

~~~python
"""Canonical Chapter 2 long-term structure from cleaned medium vertices."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .isolated_points import IsolatedPointKind
from .medium_term_structure import (
    CourseRuleMatch,
    MediumTermPoint,
    MediumTermStructure,
)


class LongTermSuppressionReason(Enum):
    """Why a confirmed long point is omitted from the long line."""

    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


@dataclass(frozen=True)
class LongTermPoint:
    """A canonical long pivot and its structural right-side confirmer."""

    pivot: MediumTermPoint
    confirmed_by: MediumTermPoint

    def __post_init__(self) -> None:
        if self.pivot.kind is not self.confirmed_by.kind:
            raise ValueError(
                "confirmed long-term points require same-kind pivot "
                "and confirmed_by points"
            )
        if self.confirmed_by.pivot_index <= self.pivot.pivot_index:
            raise ValueError(
                "confirmed_by pivot index must be after pivot index"
            )

    @property
    def pivot_index(self) -> int:
        return self.pivot.pivot_index

    @property
    def confirmed_by_index(self) -> int:
        """Return structural source location, not knowability time."""

        return self.confirmed_by.pivot_index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


def _is_strictly_more_extreme(
    candidate: MediumTermPoint,
    previous: MediumTermPoint,
) -> bool:
    if candidate.kind is IsolatedPointKind.HIGH:
        return candidate.price > previous.price
    return candidate.price < previous.price


@dataclass(frozen=True)
class PotentialLongTermPoint:
    """A right-edge pivot that passes its available left comparison."""

    previous_same_kind: MediumTermPoint
    pivot: MediumTermPoint

    def __post_init__(self) -> None:
        if self.previous_same_kind.kind is not self.pivot.kind:
            raise ValueError(
                "potential long-term points require same-kind source points"
            )
        if self.pivot.pivot_index <= self.previous_same_kind.pivot_index:
            raise ValueError(
                "potential long-term point indexes must be chronological"
            )
        if not _is_strictly_more_extreme(
            self.pivot,
            self.previous_same_kind,
        ):
            raise ValueError(
                "potential long-term point must be more extreme "
                "than previous same-kind point"
            )

    @property
    def pivot_index(self) -> int:
        return self.pivot.pivot_index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


@dataclass(frozen=True)
class SuppressedLongTermPoint:
    """A confirmed long point omitted only from normalized vertices."""

    point: LongTermPoint
    reason: LongTermSuppressionReason


@dataclass(frozen=True)
class LongCourseEvidence:
    """Externally supplied evidence that cannot decide canonical output."""

    point: LongTermPoint
    course_rule_match: CourseRuleMatch


@dataclass(frozen=True)
class LongTermStructure:
    """Canonical points, edge potentials, vertices, and retained evidence."""

    points: tuple[LongTermPoint, ...]
    potentials: tuple[PotentialLongTermPoint, ...]
    vertices: tuple[LongTermPoint, ...]
    suppressed: tuple[SuppressedLongTermPoint, ...]
    course_evidence: tuple[LongCourseEvidence, ...] = ()


def attach_course_evidence(
    structure: LongTermStructure,
    evidence: Sequence[LongCourseEvidence],
) -> LongTermStructure:
    """Remain intentionally unimplemented until Task 6's behavioral RED."""

    raise NotImplementedError("course evidence attachment is not implemented")


def _validate_medium_term_source(source: MediumTermStructure) -> None:
    for previous, current in zip(source.vertices, source.vertices[1:]):
        if current.pivot_index <= previous.pivot_index:
            raise ValueError(
                "cleaned medium vertex pivot indexes must be strictly increasing"
            )

    if any(vertex not in source.points for vertex in source.vertices):
        raise ValueError(
            "cleaned medium vertices must come from structure points"
        )

    if any(item.point in source.vertices for item in source.suppressed):
        raise ValueError(
            "suppressed medium points must not be long-term "
            "recognition vertices"
        )


def build_long_term_structure(
    source: MediumTermStructure,
) -> LongTermStructure:
    """Build canonical long structure from cleaned medium vertices."""

    _validate_medium_term_source(source)
    return LongTermStructure((), (), (), (), ())
~~~

`Sequence` is imported now because Task 6 adds the locked evidence
attachment behavior. Its public callable remains an explicit
`NotImplementedError` stub until Task 6. Do not add recognition, potentials,
normalization, or final evidence behavior in this task.

- [ ] **Step 12: Run Task 1 tests and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: all Task 1 tests pass.

- [ ] **Step 13: Run lower-layer regressions**

Run:

~~~bash
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
git diff --check
~~~

Expected: all existing Lesson 5 and Lesson 6 tests pass; the diff check emits
no errors.

- [ ] **Step 14: Review and commit Task 1**

Review frozen records, exact delegated properties, timing deferral, all direct
invariants, complete source validation before output, neutral small input,
direct-module imports, and absence of generic hierarchy logic.

~~~bash
git add trading/definitions/long_term_structure.py tests/test_long_term_structure.py
git commit -m "Add long-term structure domain model"
~~~

---

### Task 2: Strict Long-Term Recognition and Provenance

**Files:**

- Modify: `trading/definitions/long_term_structure.py`
- Modify: `tests/test_long_term_structure.py`

**Interfaces:**

- Consumes: validated `MediumTermStructure.vertices`.
- Produces: strict immediate-same-kind long HIGH/LOW recognition, pivot-ordered
  `LongTermStructure.points`, exact `pivot` and `confirmed_by`
  provenance, and initial `vertices == points`.

- [ ] **Step 1: Append strict recognition tests**

Append to `tests/test_long_term_structure.py`:

~~~python
def test_basic_long_high_uses_strict_same_kind_medium_neighbors() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 120.0, 115.0],
        low_prices=[90.0, 91.0, 92.0],
    )

    result = build_long_term_structure(source)

    assert len(result.points) == 1
    point = result.points[0]
    assert point.pivot is source.vertices[2]
    assert point.confirmed_by is source.vertices[4]
    assert point.pivot_index == source.vertices[2].pivot_index
    assert point.confirmed_by_index == source.vertices[4].pivot_index
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 120.0
    assert result.vertices == result.points
    assert result.potentials == ()


def test_basic_long_low_uses_strict_same_kind_medium_neighbors() -> None:
    source = alternating_medium_source(
        high_prices=[110.0, 111.0, 112.0],
        low_prices=[100.0, 80.0, 90.0],
    )

    result = build_long_term_structure(source)

    point = result.points[0]
    assert point.pivot is source.vertices[3]
    assert point.confirmed_by is source.vertices[5]
    assert point.kind is IsolatedPointKind.LOW
    assert point.price == 80.0


@pytest.mark.parametrize(
    "high_prices",
    [[120.0, 120.0, 115.0], [105.0, 120.0, 120.0]],
)
def test_long_high_equality_on_either_side_rejects_confirmation(
    high_prices: list[float],
) -> None:
    source = alternating_medium_source(
        high_prices=high_prices,
        low_prices=[90.0, 91.0, 92.0],
    )

    result = build_long_term_structure(source)

    assert all(
        point.kind is not IsolatedPointKind.HIGH
        for point in result.points
    )


@pytest.mark.parametrize(
    "low_prices",
    [[80.0, 80.0, 90.0], [100.0, 80.0, 80.0]],
)
def test_long_low_equality_on_either_side_rejects_confirmation(
    low_prices: list[float],
) -> None:
    source = alternating_medium_source(
        high_prices=[110.0, 111.0, 112.0],
        low_prices=low_prices,
    )

    result = build_long_term_structure(source)

    assert all(
        point.kind is not IsolatedPointKind.LOW
        for point in result.points
    )


def test_opposite_kind_vertices_are_not_same_kind_neighbors() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 120.0, 115.0],
        low_prices=[100.0, 80.0, 90.0],
    )

    result = build_long_term_structure(source)

    assert [(point.pivot_index, point.kind) for point in result.points] == [
        (source.vertices[2].pivot_index, IsolatedPointKind.HIGH),
        (source.vertices[3].pivot_index, IsolatedPointKind.LOW),
    ]
    assert result.points[0].confirmed_by is source.vertices[4]
    assert result.points[1].confirmed_by is source.vertices[5]


def test_recognizer_does_not_skip_intervening_same_kind_medium_vertex() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 120.0, 105.0],
        low_prices=[80.0, 81.0, 82.0, 83.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [120.0]
    assert all(point.price != 110.0 for point in result.points)


def test_confirmed_long_points_use_pivot_order_and_exact_sources() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 120.0, 115.0],
        low_prices=[100.0, 80.0, 90.0],
    )

    result = build_long_term_structure(source)

    assert [point.pivot_index for point in result.points] == [
        source.vertices[2].pivot_index,
        source.vertices[3].pivot_index,
    ]
    assert [point.confirmed_by for point in result.points] == [
        source.vertices[4],
        source.vertices[5],
    ]
    assert all(not hasattr(point, "known_at_index") for point in result.points)
~~~

- [ ] **Step 2: Run recognition tests and verify RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_basic_long_high_uses_strict_same_kind_medium_neighbors -v
~~~

Expected: pytest collects and runs the test, then reports `FAILED` at
`assert len(result.points) == 1` because the neutral builder returns no
confirmed points. There is no collection or setup error.

- [ ] **Step 3: Implement strict recognition**

Add before `build_long_term_structure()`:

~~~python
def _is_strict_long_pivot(
    previous: MediumTermPoint,
    pivot: MediumTermPoint,
    later: MediumTermPoint,
) -> bool:
    if pivot.kind is IsolatedPointKind.HIGH:
        return previous.price < pivot.price > later.price
    return previous.price > pivot.price < later.price


def _recognize_kind(
    vertices: tuple[MediumTermPoint, ...],
    kind: IsolatedPointKind,
) -> list[LongTermPoint]:
    same_kind = tuple(point for point in vertices if point.kind is kind)
    return [
        LongTermPoint(pivot, later)
        for previous, pivot, later in zip(
            same_kind,
            same_kind[1:],
            same_kind[2:],
        )
        if _is_strict_long_pivot(previous, pivot, later)
    ]


def _recognize_long_points(
    vertices: tuple[MediumTermPoint, ...],
) -> tuple[LongTermPoint, ...]:
    high_points = _recognize_kind(vertices, IsolatedPointKind.HIGH)
    low_points = _recognize_kind(vertices, IsolatedPointKind.LOW)
    point_by_index = {
        point.pivot_index: point for point in high_points + low_points
    }
    return tuple(
        point_by_index[vertex.pivot_index]
        for vertex in vertices
        if vertex.pivot_index in point_by_index
    )
~~~

Replace the neutral builder body after validation with:

~~~python
    points = _recognize_long_points(source.vertices)
    return LongTermStructure(
        points=points,
        potentials=(),
        vertices=points,
        suppressed=(),
        course_evidence=(),
    )
~~~

The algorithm filters each kind without sorting, evaluates consecutive triples,
uses the immediate later same-kind source as `confirmed_by`, and merges
confirmed kinds by original pivot chronology.

- [ ] **Step 4: Run Task 2 tests and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: all Task 1-2 tests pass.

- [ ] **Step 5: Run Lesson 6 regressions and diff check**

Run:

~~~bash
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
git diff --check
~~~

Expected: all Lesson 6 tests pass and the diff check emits no errors.

- [ ] **Step 6: Review and commit Task 2**

Review strict inequalities for both kinds, equality rejection, complete source
validation before recognition, immediate same-kind neighbors, refusal to skip,
pivot ordering, exact medium-object provenance, and absence of invented
knowability timing.

~~~bash
git add trading/definitions/long_term_structure.py tests/test_long_term_structure.py
git commit -m "Add strict long-term point recognition"
~~~

---

### Task 3: Right-Edge Long-Term Potentials

**Files:**

- Modify: `trading/definitions/long_term_structure.py`
- Modify: `tests/test_long_term_structure.py`

**Interfaces:**

- Consumes: the final two same-kind cleaned medium vertices.
- Produces: at most one HIGH and one LOW
  `PotentialLongTermPoint`, merged by pivot chronology and kept separate
  from confirmed points and vertices.

- [ ] **Step 1: Append potential lifecycle tests**

Append:

~~~python
@pytest.mark.parametrize(
    "kind,prices",
    [
        (IsolatedPointKind.HIGH, [105.0, 120.0]),
        (IsolatedPointKind.LOW, [100.0, 80.0]),
    ],
)
def test_current_edge_candidate_is_only_a_potential(
    kind: IsolatedPointKind,
    prices: list[float],
) -> None:
    source = medium_structure(
        [
            medium_point(10, kind, prices[0]),
            medium_point(30, kind, prices[1]),
        ]
    )

    result = build_long_term_structure(source)

    assert result.points == ()
    assert result.vertices == ()
    assert result.suppressed == ()
    assert len(result.potentials) == 1
    assert result.potentials[0].previous_same_kind is source.vertices[0]
    assert result.potentials[0].pivot is source.vertices[1]


def test_potential_becomes_confirmed_after_passing_later_high() -> None:
    previous = medium_point(10, IsolatedPointKind.HIGH, 105.0)
    pivot = medium_point(30, IsolatedPointKind.HIGH, 120.0)
    later = medium_point(50, IsolatedPointKind.HIGH, 115.0)

    before = build_long_term_structure(medium_structure([previous, pivot]))
    after = build_long_term_structure(
        medium_structure([previous, pivot, later])
    )

    assert before.points == ()
    assert before.potentials[0].pivot is pivot
    assert after.potentials == ()
    assert after.points == (LongTermPoint(pivot, later),)


def test_failed_potential_is_not_promoted() -> None:
    previous = medium_point(10, IsolatedPointKind.HIGH, 105.0)
    pivot = medium_point(30, IsolatedPointKind.HIGH, 120.0)
    later = medium_point(50, IsolatedPointKind.HIGH, 125.0)

    before = build_long_term_structure(medium_structure([previous, pivot]))
    after = build_long_term_structure(
        medium_structure([previous, pivot, later])
    )

    assert before.potentials[0].pivot is pivot
    assert all(point.pivot is not pivot for point in after.points)
    assert after.potentials == (
        PotentialLongTermPoint(pivot, later),
    )


def test_non_extreme_right_edge_is_not_a_potential() -> None:
    source = medium_structure(
        [
            medium_point(10, IsolatedPointKind.LOW, 80.0),
            medium_point(30, IsolatedPointKind.LOW, 90.0),
        ]
    )

    result = build_long_term_structure(source)

    assert result.potentials == ()
~~~

- [ ] **Step 2: Run potential tests and verify RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_current_edge_candidate_is_only_a_potential -v
~~~

Expected: pytest collects and runs both parameter cases, then reports `FAILED`
at `assert len(result.potentials) == 1` because the builder still returns an
empty `potentials` collection. There is no collection or setup error.

- [ ] **Step 3: Extend recognition to return edge potentials**

Replace `_recognize_kind()` with:

~~~python
def _recognize_kind(
    vertices: tuple[MediumTermPoint, ...],
    kind: IsolatedPointKind,
) -> tuple[list[LongTermPoint], PotentialLongTermPoint | None]:
    same_kind = tuple(point for point in vertices if point.kind is kind)
    confirmed = [
        LongTermPoint(pivot, later)
        for previous, pivot, later in zip(
            same_kind,
            same_kind[1:],
            same_kind[2:],
        )
        if _is_strict_long_pivot(previous, pivot, later)
    ]

    potential: PotentialLongTermPoint | None = None
    if len(same_kind) >= 2:
        previous, pivot = same_kind[-2:]
        if _is_strictly_more_extreme(pivot, previous):
            potential = PotentialLongTermPoint(previous, pivot)
    return confirmed, potential
~~~

Replace `_recognize_long_points()` with:

~~~python
def _recognize_long_points(
    vertices: tuple[MediumTermPoint, ...],
) -> tuple[tuple[LongTermPoint, ...], tuple[PotentialLongTermPoint, ...]]:
    high_points, high_potential = _recognize_kind(
        vertices,
        IsolatedPointKind.HIGH,
    )
    low_points, low_potential = _recognize_kind(
        vertices,
        IsolatedPointKind.LOW,
    )

    point_by_index = {
        point.pivot_index: point for point in high_points + low_points
    }
    points = tuple(
        point_by_index[vertex.pivot_index]
        for vertex in vertices
        if vertex.pivot_index in point_by_index
    )

    potential_by_index = {
        potential.pivot_index: potential
        for potential in (high_potential, low_potential)
        if potential is not None
    }
    potentials = tuple(
        potential_by_index[vertex.pivot_index]
        for vertex in vertices
        if vertex.pivot_index in potential_by_index
    )
    return points, potentials
~~~

Update the builder:

~~~python
    points, potentials = _recognize_long_points(source.vertices)
    return LongTermStructure(
        points=points,
        potentials=potentials,
        vertices=points,
        suppressed=(),
        course_evidence=(),
    )
~~~

- [ ] **Step 4: Run Task 3 tests and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: all domain, recognition, and potential tests pass.

- [ ] **Step 5: Run lower-layer regressions**

Run:

~~~bash
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
git diff --check
~~~

Expected: all suites pass and the diff check emits no errors.

- [ ] **Step 6: Review and commit Task 3**

Review strict edge extremity for both kinds, absence with fewer than two
same-kind vertices, separation from confirmed output and normalization,
successful promotion only after a passing immediate later comparison, failed
promotion omission, and chronological potential ordering.

~~~bash
git add trading/definitions/long_term_structure.py tests/test_long_term_structure.py
git commit -m "Add long-term edge potentials"
~~~

---

### Task 4: Consecutive Same-Kind Long-Term Normalization

**Files:**

- Modify: `trading/definitions/long_term_structure.py`
- Modify: `tests/test_long_term_structure.py`

**Interfaces:**

- Consumes: all pivot-ordered confirmed long-term points.
- Produces: most-extreme line vertices per consecutive same-kind run,
  earliest-winner tie behavior, complete `points` preservation, and
  `CONSECUTIVE_SAME_KIND` suppression evidence.

- [ ] **Step 1: Append same-kind normalization tests**

Append:

~~~python
def test_consecutive_long_highs_keep_highest_vertex_and_all_points() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0, 86.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0, 115.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [item.point.price for item in result.suppressed] == [
        110.0,
        115.0,
    ]
    assert all(
        item.reason is LongTermSuppressionReason.CONSECUTIVE_SAME_KIND
        for item in result.suppressed
    )


def test_consecutive_long_lows_keep_lowest_vertex_and_all_points() -> None:
    source = alternating_medium_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0, 135.0, 136.0],
        low_prices=[120.0, 90.0, 100.0, 80.0, 95.0, 85.0, 110.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 80.0, 85.0]
    assert [point.price for point in result.vertices] == [80.0]
    assert [item.point.price for item in result.suppressed] == [90.0, 85.0]


def test_equal_highest_long_high_keeps_earliest_pivot() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 105.0, 110.0, 100.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 110.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed == (
        SuppressedLongTermPoint(
            result.points[1],
            LongTermSuppressionReason.CONSECUTIVE_SAME_KIND,
        ),
    )


def test_equal_lowest_long_low_keeps_earliest_pivot() -> None:
    source = alternating_medium_source(
        high_prices=[130.0, 131.0, 132.0, 133.0, 134.0],
        low_prices=[120.0, 90.0, 100.0, 90.0, 110.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [90.0, 90.0]
    assert result.vertices == (result.points[0],)
    assert result.suppressed[0].point is result.points[1]


def test_same_kind_normalization_does_not_change_potentials() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 125.0],
        low_prices=[80.0, 81.0, 82.0, 83.0, 84.0, 85.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.points] == [110.0, 120.0]
    assert [point.price for point in result.vertices] == [120.0]
    assert [potential.price for potential in result.potentials] == [125.0]
~~~

- [ ] **Step 2: Run same-kind tests and verify RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_consecutive_long_highs_keep_highest_vertex_and_all_points -v
~~~

Expected: pytest collects and runs the test, then reports `FAILED` because
every confirmed high is still returned as a vertex instead of only the
highest high. There is no collection or setup error.

- [ ] **Step 3: Implement same-kind run normalization**

Add:

~~~python
def _is_more_extreme_long(
    candidate: LongTermPoint,
    current: LongTermPoint,
) -> bool:
    if current.kind is IsolatedPointKind.HIGH:
        return candidate.price > current.price
    return candidate.price < current.price


def _normalize_same_kind_runs(
    points: tuple[LongTermPoint, ...],
) -> tuple[list[LongTermPoint], list[SuppressedLongTermPoint]]:
    vertices: list[LongTermPoint] = []
    suppressed: list[SuppressedLongTermPoint] = []
    run: list[LongTermPoint] = []

    def flush_run() -> None:
        if not run:
            return
        winner = run[0]
        for candidate in run[1:]:
            if _is_more_extreme_long(candidate, winner):
                winner = candidate
        vertices.append(winner)
        suppressed.extend(
            SuppressedLongTermPoint(
                point,
                LongTermSuppressionReason.CONSECUTIVE_SAME_KIND,
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
~~~

Update the builder:

~~~python
    points, potentials = _recognize_long_points(source.vertices)
    vertices, suppressed = _normalize_same_kind_runs(points)
    return LongTermStructure(
        points=points,
        potentials=potentials,
        vertices=tuple(vertices),
        suppressed=tuple(suppressed),
        course_evidence=(),
    )
~~~

The comparison is strict, so the first point retains an exact price tie.

- [ ] **Step 4: Run Task 4 tests and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: all unit tests pass, including earliest equal-extreme winners and
preservation of every confirmed point.

- [ ] **Step 5: Run Lessons 5-6 regressions**

Run:

~~~bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
git diff --check
~~~

Expected: all suites pass and the diff check emits no errors.

- [ ] **Step 6: Review and commit Task 4**

Review run boundaries, HIGH/LOW mirroring, strict winner replacement,
earliest-tie behavior, preservation of every confirmed point and its
provenance, suppression reasons, phase ordering, and potential independence.

~~~bash
git add trading/definitions/long_term_structure.py tests/test_long_term_structure.py
git commit -m "Add long-term same-kind normalization"
~~~

---

### Task 5: Provisional Complete-Pair Inside Normalization

**Files:**

- Modify: `trading/definitions/long_term_structure.py`
- Modify: `tests/test_long_term_structure.py`

**Interfaces:**

- Consumes: vertices after same-kind normalization.
- Produces: inclusive complete-pair inside suppression in either orientation,
  breakout preservation, repeated stabilization, unmatched-point
  preservation, and `INSIDE_STRUCTURE` evidence.

- [ ] **Step 1: Append the source helper and inside tests**

Append:

~~~python
def paired_long_source(
    earlier_high: float,
    earlier_low: float,
    later_high: float,
    later_low: float,
    *,
    first_kind: IsolatedPointKind = IsolatedPointKind.HIGH,
) -> MediumTermStructure:
    return alternating_medium_source(
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
def test_complete_inside_long_pair_is_suppressed_in_both_orientations(
    first_kind: IsolatedPointKind,
) -> None:
    source = paired_long_source(
        110.0,
        100.0,
        108.0,
        102.0,
        first_kind=first_kind,
    )

    result = build_long_term_structure(source)

    assert len(result.points) == 4
    assert result.vertices == result.points[:2]
    assert result.suppressed == tuple(
        SuppressedLongTermPoint(
            point,
            LongTermSuppressionReason.INSIDE_STRUCTURE,
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
def test_equality_at_long_inside_boundary_counts_as_contained(
    later_high: float,
    later_low: float,
) -> None:
    result = build_long_term_structure(
        paired_long_source(110.0, 100.0, later_high, later_low)
    )

    assert result.vertices == result.points[:2]


@pytest.mark.parametrize(
    "later_high,later_low",
    [(111.0, 102.0), (108.0, 99.0)],
)
def test_one_side_breakout_preserves_later_long_pair(
    later_high: float,
    later_low: float,
) -> None:
    result = build_long_term_structure(
        paired_long_source(110.0, 100.0, later_high, later_low)
    )

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_incomplete_later_long_range_is_preserved() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 110.0, 104.0, 108.0, 103.0],
        low_prices=[105.0, 100.0, 106.0, 107.0, 108.0],
    )

    result = build_long_term_structure(source)

    assert [(point.kind, point.price) for point in result.points] == [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 100.0),
        (IsolatedPointKind.HIGH, 108.0),
    ]
    assert result.vertices == result.points
    assert result.suppressed == ()


def test_repeated_inside_long_pairs_normalize_until_stable() -> None:
    source = alternating_medium_source(
        high_prices=[100.0, 120.0, 99.0, 115.0, 98.0, 110.0, 97.0],
        low_prices=[110.0, 90.0, 111.0, 95.0, 112.0, 100.0, 113.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.vertices] == [120.0, 90.0]
    assert [item.point for item in result.suppressed] == list(
        result.points[2:]
    )
    assert all(
        item.reason is LongTermSuppressionReason.INSIDE_STRUCTURE
        for item in result.suppressed
    )


def test_inside_pair_uses_immediately_previous_complete_pair() -> None:
    source = alternating_medium_source(
        high_prices=[105.0, 110.0, 104.0, 120.0, 103.0, 115.0, 102.0],
        low_prices=[105.0, 100.0, 106.0, 90.0, 107.0, 95.0, 108.0],
    )

    result = build_long_term_structure(source)

    assert [point.price for point in result.vertices] == [
        110.0,
        100.0,
        120.0,
        90.0,
    ]
    assert [item.point.price for item in result.suppressed] == [115.0, 95.0]


def test_non_contained_long_layout_is_preserved_without_guessing() -> None:
    result = build_long_term_structure(
        paired_long_source(110.0, 100.0, 115.0, 95.0)
    )

    assert result.vertices == result.points
    assert result.suppressed == ()


def test_suppression_order_is_phase_then_pivot_chronology() -> None:
    source = alternating_medium_source(
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

    result = build_long_term_structure(source)

    reasons = [item.reason for item in result.suppressed]
    assert reasons[0] is LongTermSuppressionReason.CONSECUTIVE_SAME_KIND
    assert reasons[1:] == [
        LongTermSuppressionReason.INSIDE_STRUCTURE,
        LongTermSuppressionReason.INSIDE_STRUCTURE,
    ]
~~~

- [ ] **Step 2: Run inside tests and verify RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_complete_inside_long_pair_is_suppressed_in_both_orientations -v
~~~

Expected: pytest collects and runs both orientation cases, then reports
`FAILED` because the contained later pair remains in `vertices`. There is no
collection or setup error. Breakout-preservation tests document
already-preserved layouts and are verified after GREEN.

- [ ] **Step 3: Implement the provisional complete-pair rule**

Add:

~~~python
def _pair_bounds(
    first: LongTermPoint,
    second: LongTermPoint,
) -> tuple[float, float] | None:
    if first.kind is second.kind:
        return None
    high = first if first.kind is IsolatedPointKind.HIGH else second
    low = first if first.kind is IsolatedPointKind.LOW else second
    return high.price, low.price


def _later_pair_is_inside(
    earlier: tuple[LongTermPoint, LongTermPoint],
    later: tuple[LongTermPoint, LongTermPoint],
) -> bool:
    earlier_bounds = _pair_bounds(*earlier)
    later_bounds = _pair_bounds(*later)
    if earlier_bounds is None or later_bounds is None:
        return False
    earlier_high, earlier_low = earlier_bounds
    later_high, later_low = later_bounds
    return later_high <= earlier_high and later_low >= earlier_low


def _normalize_inside_structures(
    vertices: list[LongTermPoint],
) -> tuple[list[LongTermPoint], list[SuppressedLongTermPoint]]:
    normalized = list(vertices)
    suppressed: list[SuppressedLongTermPoint] = []
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
                SuppressedLongTermPoint(
                    point,
                    LongTermSuppressionReason.INSIDE_STRUCTURE,
                )
                for point in removed
            )
            changed = True

    return normalized, suppressed
~~~

Update the builder:

~~~python
    points, potentials = _recognize_long_points(source.vertices)
    same_kind_vertices, same_kind_suppressed = (
        _normalize_same_kind_runs(points)
    )
    vertices, inside_suppressed = _normalize_inside_structures(
        same_kind_vertices
    )
    return LongTermStructure(
        points=points,
        potentials=potentials,
        vertices=tuple(vertices),
        suppressed=tuple(
            same_kind_suppressed + inside_suppressed
        ),
        course_evidence=(),
    )
~~~

Do not extend earlier ranges, replace boundaries, search for nearest pairs, or
use BMS/SMS, trend, timeframe, price-distance, or candle-count rules.

- [ ] **Step 4: Run Task 5 tests and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: every unit test passes, including both orientations, inclusive
boundaries, both one-side breakouts, incomplete range preservation, repeated
stability, suppression phase order, and ambiguous layout preservation.

- [ ] **Step 5: Run structural regressions**

Run:

~~~bash
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
git diff --check
~~~

Expected: all suites pass and the diff check emits no errors.

- [ ] **Step 6: Review and commit Task 5**

Review same-level complete pairs only, inclusive two-boundary containment,
one-side breakout preservation, HIGH-to-LOW and LOW-to-HIGH orientations,
stable repeated application, unmatched final points, preservation of all
confirmed evidence, phase-ordered suppressions, and absence of alternative
inside algorithms.

~~~bash
git add trading/definitions/long_term_structure.py tests/test_long_term_structure.py
git commit -m "Add long-term inside normalization"
~~~

---

### Task 6: Passive Teacher Creator/Break Evidence

**Files:**

- Modify: `trading/definitions/long_term_structure.py`
- Modify: `tests/test_long_term_structure.py`

**Interfaces:**

- Consumes: caller-supplied `Sequence[LongCourseEvidence]` using the existing
  `CourseRuleMatch` enum.
- Produces:
  `attach_course_evidence(structure, evidence) -> LongTermStructure`, which
  validates point membership and changes only `course_evidence`.

- [ ] **Step 1: Add evidence attachment tests**

Extend the long-term import with `attach_course_evidence`, then append:

~~~python
def test_course_evidence_attachment_preserves_canonical_output() -> None:
    canonical = build_long_term_structure(
        alternating_medium_source(
            high_prices=[105.0, 120.0, 115.0],
            low_prices=[90.0, 91.0, 92.0],
        )
    )
    evidence = LongCourseEvidence(
        canonical.points[0],
        CourseRuleMatch.UNKNOWN,
    )

    enriched = attach_course_evidence(canonical, [evidence])

    assert enriched.points == canonical.points
    assert enriched.potentials == canonical.potentials
    assert enriched.vertices == canonical.vertices
    assert enriched.suppressed == canonical.suppressed
    assert enriched.course_evidence == (evidence,)
    assert canonical.course_evidence == ()
    assert enriched.points[0].pivot is canonical.points[0].pivot
    assert enriched.points[0].confirmed_by is canonical.points[0].confirmed_by


def test_course_evidence_requires_a_confirmed_long_point() -> None:
    canonical = build_long_term_structure(
        alternating_medium_source(
            high_prices=[105.0, 120.0, 115.0],
            low_prices=[90.0, 91.0, 92.0],
        )
    )
    unrelated = LongTermPoint(
        medium_point(200, IsolatedPointKind.HIGH, 130.0),
        medium_point(220, IsolatedPointKind.HIGH, 125.0),
    )

    with pytest.raises(
        ValueError,
        match="requires a confirmed long-term point",
    ):
        attach_course_evidence(
            canonical,
            [LongCourseEvidence(unrelated, CourseRuleMatch.YES)],
        )
~~~

- [ ] **Step 2: Run evidence tests and verify RED**

Run:

~~~bash
pytest tests/test_long_term_structure.py::test_course_evidence_attachment_preserves_canonical_output tests/test_long_term_structure.py::test_course_evidence_requires_a_confirmed_long_point -v
~~~

Expected: pytest collects and runs both tests, then reports two `FAILED` tests
because the Task 1 public callable still raises
`NotImplementedError("course evidence attachment is not implemented")`.
This is the intended missing evidence behavior, not an import, collection, or
setup failure.

- [ ] **Step 3: Implement immutable evidence attachment**

Replace the Task 1 `attach_course_evidence()` stub with:

~~~python
def attach_course_evidence(
    structure: LongTermStructure,
    evidence: Sequence[LongCourseEvidence],
) -> LongTermStructure:
    """Attach external diagnostic evidence without changing canonical output."""

    evidence_tuple = tuple(evidence)
    if any(item.point not in structure.points for item in evidence_tuple):
        raise ValueError(
            "course evidence requires a confirmed long-term point"
        )
    return LongTermStructure(
        points=structure.points,
        potentials=structure.potentials,
        vertices=structure.vertices,
        suppressed=structure.suppressed,
        course_evidence=evidence_tuple,
    )
~~~

Do not calculate `CourseRuleMatch`, choose creator points, choose trend
context, scan breaks, or invoke BMS/SMS. Evidence is supplied explicitly after
canonical construction.

- [ ] **Step 4: Run Task 6 tests and verify GREEN**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: every unit test passes and attachment preserves the exact canonical
objects and collections.

- [ ] **Step 5: Run Lesson 6 and structural regressions**

Run:

~~~bash
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
git diff --check
~~~

Expected: every suite passes and the diff check emits no errors.

- [ ] **Step 6: Review and commit Task 6**

Review enum reuse, explicit caller-supplied status, confirmed-point membership,
immutability, exact canonical/provenance preservation, and absence of
creator-selection, break-evaluation, hierarchy, or market-decision behavior.

~~~bash
git add trading/definitions/long_term_structure.py tests/test_long_term_structure.py
git commit -m "Add long-term course evidence"
~~~

---

### Task 7: Real Chapter 1 Through Lesson 7 Integration

**Files:**

- Create: `tests/test_long_term_structure_integration.py`

**Interfaces:**

- Consumes: raw `Candle` inputs; strict and `RIGHT_INSIDE_BAR` Chapter 1
  recognition; Lesson 5 mapping and normalization; Lesson 6 construction; and
  the complete Lesson 7 API.
- Produces: a real lower-layer composition proof, nested provenance proof,
  a discriminating cleaned-medium-vertices-only test, and passive-evidence
  integration coverage.

- [ ] **Step 1: Create exact raw-recognition integration fixtures and tests**

Create `tests/test_long_term_structure_integration.py`:

~~~python
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
from trading.definitions.long_term_structure import (
    LongCourseEvidence,
    LongTermStructure,
    attach_course_evidence,
    build_long_term_structure,
)
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumTermStructure,
    build_medium_term_structure,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    build_short_term_structure,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def candle(high: float, low: float) -> Candle:
    midpoint = (high + low) / 2
    return Candle(midpoint, high, low, midpoint)


def strict_short_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> ShortTermPoint:
    if kind is IsolatedPointKind.HIGH:
        left = candle(price - 2.0, price - 10.0)
        middle = candle(price, price - 8.0)
        right = candle(price - 1.0, price - 9.0)
    else:
        left = candle(price + 10.0, price + 2.0)
        middle = candle(price + 8.0, price)
        right = candle(price + 9.0, price + 1.0)

    recognized = detect_confirmed_isolated_point(
        left,
        middle,
        right,
        index=index,
    )
    assert recognized is not None
    return short_term_point_from_isolated_point(recognized)


def right_inside_high(index: int, price: float) -> ShortTermPoint:
    left = candle(price - 2.0, price - 10.0)
    middle = candle(price, price - 8.0)
    potential = get_potential_isolated_point(left, middle, index=index)
    assert potential is not None

    recognition = confirm_isolated_point_with_deformation(
        potential,
        middle,
        candle(price, price - 7.0),
    )
    assert recognition is not None
    assert recognition.basis is IsolatedPointBasis.RIGHT_INSIDE_BAR
    return short_term_point_from_recognition(recognition)


def recognized_short_points(
    high_prices: list[float],
    low_prices: list[float],
    *,
    deformation_high_position: int | None = None,
) -> list[ShortTermPoint]:
    assert len(high_prices) == len(low_prices)
    points: list[ShortTermPoint] = []
    for position, (high, low) in enumerate(zip(high_prices, low_prices)):
        high_index = position * 2 + 1
        if position == deformation_high_position:
            high_point = right_inside_high(high_index, high)
        else:
            high_point = strict_short_point(
                high_index,
                IsolatedPointKind.HIGH,
                high,
            )
        low_point = strict_short_point(
            high_index + 1,
            IsolatedPointKind.LOW,
            low,
        )
        points.extend((high_point, low_point))
    return points


def build_real_hierarchy() -> tuple[
    list[ShortTermPoint],
    ShortTermStructure,
    MediumTermStructure,
    LongTermStructure,
]:
    points = recognized_short_points(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[90.0, 95.0, 80.0, 96.0, 85.0, 97.0, 70.0],
        deformation_high_position=3,
    )
    short_structure = build_short_term_structure(points)
    medium_structure = build_medium_term_structure(short_structure)
    long_structure = build_long_term_structure(medium_structure)
    return points, short_structure, medium_structure, long_structure


def test_real_strict_and_deformation_hierarchy_reaches_long_structure() -> None:
    points, short_structure, medium_structure, long_structure = (
        build_real_hierarchy()
    )
    deformation_high = points[6]

    assert short_structure.vertices == tuple(points)
    assert deformation_high.recognition_basis is (
        IsolatedPointBasis.RIGHT_INSIDE_BAR
    )
    assert [point.price for point in medium_structure.vertices] == [
        110.0,
        80.0,
        120.0,
        85.0,
        115.0,
    ]
    assert len(long_structure.points) == 1
    long_high = long_structure.points[0]
    assert long_high.pivot is medium_structure.vertices[2]
    assert long_high.confirmed_by is medium_structure.vertices[4]
    assert long_high.pivot.pivot is deformation_high
    assert long_high.pivot.pivot.recognition_basis is (
        IsolatedPointBasis.RIGHT_INSIDE_BAR
    )
    assert long_high.confirmed_by.pivot is points[10]
    assert not hasattr(long_high, "known_at_index")


def test_suppressed_medium_points_are_not_long_recognition_neighbors() -> None:
    points = recognized_short_points(
        high_prices=[100.0, 110.0, 105.0, 120.0, 107.0, 115.0, 100.0],
        low_prices=[90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0],
    )
    short_structure = build_short_term_structure(points)
    medium_structure = build_medium_term_structure(short_structure)
    long_structure = build_long_term_structure(medium_structure)

    assert [point.price for point in medium_structure.points] == [
        110.0,
        120.0,
        115.0,
    ]
    assert [point.price for point in medium_structure.vertices] == [120.0]
    assert [item.point.price for item in medium_structure.suppressed] == [
        110.0,
        115.0,
    ]
    assert all(
        item.point in medium_structure.points
        and item.point not in medium_structure.vertices
        for item in medium_structure.suppressed
    )
    assert long_structure.points == ()
    assert long_structure.vertices == ()


def test_external_evidence_cannot_change_integrated_long_output() -> None:
    _, _, _, canonical = build_real_hierarchy()
    evidence = LongCourseEvidence(
        canonical.points[0],
        CourseRuleMatch.UNKNOWN,
    )

    enriched = attach_course_evidence(canonical, [evidence])

    assert enriched.points == canonical.points
    assert enriched.potentials == canonical.potentials
    assert enriched.vertices == canonical.vertices
    assert enriched.suppressed == canonical.suppressed
    assert enriched.course_evidence == (evidence,)
    assert enriched.points[0].pivot is canonical.points[0].pivot
    assert (
        enriched.points[0].confirmed_by
        is canonical.points[0].confirmed_by
    )
~~~

The second test is deliberately discriminating: scanning all medium
`points` would see `110 < 120 > 115` and incorrectly confirm a long high,
while the approved cleaned `vertices` boundary contains only `120` and
therefore confirms nothing.

- [ ] **Step 2: Run the integration verification suite**

Run:

~~~bash
pytest tests/test_long_term_structure_integration.py -v
~~~

Expected: all three integration tests pass against the already completed
Tasks 1-6 production behavior. Both Chapter 1 recognition paths reach
`LongTermStructure`; nested medium-to-short provenance is retained; suppressed
medium points cannot affect long recognition; and evidence is passive. This is
integration verification, not a RED step.

- [ ] **Step 3: Handle a real integration-discovered production defect with TDD**

If Step 2 fails because an approved Tasks 1-6 production behavior is defective:

1. Preserve the failing integration test as the behavioral RED evidence.
2. Confirm pytest collected and ran it and that the failure is caused by the
   production defect rather than fixture, import, collection, or setup error.
3. Make the minimum production correction in
   `trading/definitions/long_term_structure.py`.
4. Rerun the exact failing integration test to GREEN.
5. Rerun `pytest tests/test_long_term_structure.py -v` and the complete
   integration file.
6. Commit the correction as a narrowly scoped review/fix commit and record it
   in the SDD ledger.

If Step 2 passes, make no production change and create no fix commit.

- [ ] **Step 4: Run all Lessons 5-7 tests together**

Run:

~~~bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py tests/test_long_term_structure.py tests/test_long_term_structure_integration.py -v
~~~

Expected: every short-, medium-, and long-term unit/integration test passes.

- [ ] **Step 5: Run Chapter 1 and earlier Chapter 2 regressions**

Run each command separately:

~~~bash
pytest tests/test_isolated_points.py -v
pytest tests/test_isolated_point_deformations.py -v
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
git diff --check
~~~

Expected: every existing suite passes and the diff check emits no errors. Do
not record a predicted pass count.

- [ ] **Step 6: Review and commit Task 7**

Review the real raw-candle recognition boundary, strict and
`RIGHT_INSIDE_BAR` composition, exact nested provenance, exclusive use of
`MediumTermStructure.vertices`, the discriminating prohibited-path failure,
passive evidence, and absence of lower-layer recognition in production.

~~~bash
git add tests/test_long_term_structure_integration.py
git commit -m "Add long-term structure integration coverage"
~~~

---

### Task 8: Full Regression, Scope, and Lesson 8 Gate

**Files:**

- Verify: `trading/definitions/long_term_structure.py`
- Verify: `tests/test_long_term_structure.py`
- Verify: `tests/test_long_term_structure_integration.py`
- Do not create a verification-only commit.

**Interfaces:**

- Consumes: the complete seven-commit Lesson 7 feature branch plus any
  narrowly scoped review-fix commits.
- Produces: fresh verification, scope evidence, ledger completion, and broad
  final review suitable for independent GitHub review without merging.

- [ ] **Step 1: Run the focused long-term unit suite**

Run:

~~~bash
pytest tests/test_long_term_structure.py -v
~~~

Expected: PASS for records, validation, neutral inputs, strict recognition,
equality rejection, immediate same-kind neighbors, provenance, timing
deferral, potentials, both normalization phases, and course evidence.

- [ ] **Step 2: Run the focused long-term integration suite**

Run:

~~~bash
pytest tests/test_long_term_structure_integration.py -v
~~~

Expected: PASS for real strict/deformation composition, nested provenance,
cleaned-medium-vertex-only recognition, suppressed-medium exclusion, and
passive evidence.

- [ ] **Step 3: Run Lesson 6 regression suites**

Run:

~~~bash
pytest tests/test_medium_term_structure.py -v
pytest tests/test_medium_term_structure_integration.py -v
~~~

Expected: both Lesson 6 suites pass with unchanged medium recognition,
potentials, provenance, normalization, and evidence behavior.

- [ ] **Step 4: Run Lesson 5 and Chapter 1 regression suites**

Run:

~~~bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v
~~~

Expected: all suites pass with unchanged isolated/deformation recognition and
short-term normalization.

- [ ] **Step 5: Run Lessons 1-3 regression suites**

Run:

~~~bash
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
~~~

Expected: all suites pass with unchanged market-state, BMS, and SMS semantics.

- [ ] **Step 6: Run complete repository verification**

Run:

~~~bash
pytest -q
git diff --check
python -c "from pathlib import Path; assert not Path('tests/test_course_market_structure_scenarios.py').exists()"
~~~

Expected: the full suite passes, the diff check emits no errors, and the
formal Chapter 2 Level-2 suite remains absent.

- [ ] **Step 7: Verify implementation scope against the recorded base**

Fetch the current remote reference and compare it with the exact implementation
base recorded in the SDD ledger:

~~~bash
git fetch origin main
git rev-parse origin/main
~~~

If `origin/main` moved after feature creation, stop and report the divergence.
Do not silently redefine the base, rebase, merge, or continue scope
verification against a different checkpoint.

When the SHA still matches:

~~~bash
git diff --name-only origin/main...HEAD
git log --oneline origin/main..HEAD
git status --short
~~~

Expected changed files only:

~~~text
trading/definitions/long_term_structure.py
tests/test_long_term_structure.py
tests/test_long_term_structure_integration.py
~~~

Expected history contains the seven task commits plus only coherent
review-fix commits. The feature worktree is clean.

- [ ] **Step 8: Inspect forbidden coupling and deferred concepts**

Run:

~~~bash
git grep -n -E "Candle|detect_confirmed_isolated_point|confirm_isolated_point|build_short_term_structure|evaluate_bms|evaluate_sms|classify_market_state|timeframe|generic|recursive|strategy|signal|entry|exit|risk|broker|execution|machine.learning|known_at_index|confirmed_at_index" -- trading/definitions/long_term_structure.py
~~~

Expected: no raw-candle or lower-level rescan, BMS/SMS evaluation,
market-state inference, timeframe mapping, generic recursive engine,
strategy/execution coupling, machine learning, or invented timing. The
`confirmed_by_index` property is structural provenance only.

- [ ] **Step 9: Perform the broad final whole-branch review**

Dispatch the most capable available reviewer against:

- `docs/superpowers/specs/2026-09-03-long-term-structure-design.md`
- `docs/superpowers/plans/2026-09-03-long-term-structure.md`
- the complete feature diff from the recorded implementation base

The review must verify:

- only cleaned `MediumTermStructure.vertices` are recognition neighbors;
- medium `points` and suppressions never become hidden neighbors;
- source validation completes before output;
- strict immediate-same-kind HIGH/LOW comparisons and equality rejection;
- no skipped intervening same-kind medium point;
- potential/confirmed separation, passing promotion, and failed omission;
- exact `MediumTermPoint` pivot and confirming-source provenance;
- `confirmed_by_index` is not represented as actual knowability time;
- no executable timing property exists;
- pivot-ordered output;
- all confirmed points survive normalization;
- most-extreme same-kind cleanup and earliest exact-price tie behavior;
- provisional inclusive two-boundary inside handling in both orientations;
- one-side breakout, incomplete range, ambiguous layout, and unmatched final
  point preservation;
- stable repeated containment without boundary extension or replacement;
- course evidence cannot alter canonical output or choose creators/context;
- no generic hierarchy, lower-level rescan, timeframe mapping, BMS/SMS
  reinterpretation, market-state inference, Lesson 8 behavior, strategy, risk,
  or execution; and
- no formal Chapter 2 Level-2 suite.

Fix every valid Critical or Important finding on the feature branch. Use
red-to-green TDD for behavioral fixes, create a coherent fix commit, perform
scoped re-review, and rerun affected tests plus `pytest -q` and
`git diff --check`.

- [ ] **Step 10: Push the reviewed feature branch without merging**

After all tests and reviews pass and the worktree is clean:

~~~bash
git push -u origin feature/long-term-structure
~~~

Expected: the reviewed feature branch is available for independent GitHub
review. Do not push implementation commits directly to `origin/main`, do not
merge, do not squash, and do not begin Lesson 8.

---

## Spec Coverage Map

| Approved requirement | Planned coverage |
| --- | --- |
| Explicit medium-to-long boundary | Tasks 1, 2, and 7 |
| Cleaned medium vertices only | Tasks 1, 2, 7, and 8 |
| Strict HIGH/LOW three-point promotion | Task 2 |
| Immediate same-kind neighbors and no skipping | Task 2 |
| Equality rejection | Task 2 |
| Pivot and confirming-source provenance | Tasks 1, 2, and 7 |
| No invented knowability timing | Tasks 1, 2, 7, and 8 |
| Right-edge potentials and lifecycle | Task 3 |
| Confirmed/potential separation | Tasks 2 and 3 |
| Source chronology, membership, and suppression validation | Task 1 |
| Same-kind cleanup and earliest ties | Task 4 |
| Provisional complete-pair inside cleanup | Task 5 |
| Both orientations and inclusive boundaries | Task 5 |
| One-side breakout and unmatched-point preservation | Task 5 |
| Repeated stable normalization | Task 5 |
| Confirmed points independent from vertices | Tasks 4 and 5 |
| Teacher creator/break as passive evidence | Task 6 |
| Raw recognition through the full explicit hierarchy | Task 7 |
| Suppressed medium point discrimination | Task 7 |
| Existing Lessons 1-6 unchanged | Tasks 1-8 regressions |
| No generic engine, timeframe mapping, or trading behavior | Global constraints and Task 8 |
| Formal Chapter 2 Level-2 suite deferred | Global constraints and Task 8 |
| Lesson 8 not started | Global constraints and Task 8 |

## Final Review and Execution Handoff

The implementation plan is complete only when its executor:

1. starts from the approved implementation-plan checkpoint on
   `origin/main`;
2. records that immutable implementation base in the SDD ledger;
3. creates `feature/long-term-structure` in an isolated worktree;
4. completes Tasks 1-7 with fresh implementers, RED/GREEN evidence, commits,
   spec-compliance reviews, code-quality reviews, fixes, and re-reviews;
5. completes Task 8 fresh verification and broad whole-branch review;
6. confirms the implementation diff contains only the three planned files;
7. pushes only the feature branch for independent review; and
8. stops without merging or beginning Lesson 8.

No package export change, medium-term refactor, production dependency, or
formal Chapter 2 Level-2 suite is planned.
