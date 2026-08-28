# Market Structure Foundation Design

**Date:** 2026-08-28

**Status:** Approved architectural checkpoint

**Scope:** Chapter 2, Lesson 1 — Trend and Non-Trend

## Purpose

This design defines a small, layered course-definition engine for interpreting market structure inside an explicitly selected market segment. It accepts structural highs and lows that have already been identified by the caller, derives chronological relationships between comparable points, and classifies the supplied segment as an uptrend, downtrend, or non-trend.

The successful flow is:

```text
explicit MarketSegment
        +
ordered, supplied structural highs and lows
        |
        v
same-kind chronological relationships
        |
        v
UPTREND / DOWNTREND / NON_TREND
```

This layer defines course terminology only. It does not create trading decisions or infer structural points from raw candles.

## Scope Boundaries

This checkpoint covers only:

- an explicit index-based market segment;
- explicitly supplied structural high and low points;
- higher-high, lower-high, equal-high, higher-low, lower-low, and equal-low relationships;
- the Chapter 2 definitions of uptrend, downtrend, and non-trend;
- reuse of the existing Chapter 1 inside-bar definition; and
- a strict, two-candle outside-bar definition.

It does not cover:

- automatic swing or structure-point extraction;
- automatic conversion of isolated points into structure points;
- break of market structure (BMS), break of structure (BOS), or change of character (CHOCH);
- timeframe or key-level selection;
- entries, exits, trade signals, strategy rules, or position sizing;
- order execution, broker integration, or live-market connectivity;
- context-dependent candle deformation rules; or
- generalized multi-candle outside-bar or range algorithms.

## Core Design Principles

### Market structure is segment-relative

Market structure is evaluated only inside a `MarketSegment` explicitly supplied by the caller. No API may silently use all available history, choose a segment, expand a segment, or infer boundaries from the supplied points.

Segment boundaries are inclusive. A point belongs to a segment when:

```text
segment.start_index <= point.index <= segment.end_index
```

Index boundaries are the only boundary representation in this checkpoint. Timestamp-based segments may be introduced later through a separate type or adapter without changing the meaning of this API.

### Structural points are supplied, not discovered

A `StructurePoint` represents a structural high or low already selected by an upstream process or a human. This layer does not scan candles, calculate swings, inspect isolated points, or decide which prices deserve structural significance.

In particular, an isolated point and a structure point are different concepts. The existing isolated-point modules remain unchanged, and this design introduces no automatic mapping between them. A single trend candle's internal price path may help explain course terminology, but it is not a hardwired structure-point extraction algorithm. A later lesson, including BMS, may define the missing selection rules.

### Chronology is authoritative

Caller-supplied point order is authoritative. The classifier never sorts points by index or price. Highs are compared only with chronological highs; lows are compared only with chronological lows.

The input sequence must have nondecreasing indexes. The same candle index may contain one `HIGH` and one `LOW`, because a candle can contribute both kinds of point. Duplicate points of the same kind at the same index are invalid. Within each kind-specific subsequence, indexes must therefore be strictly increasing.

Malformed chronology is rejected rather than repaired.

## Proposed Module

The future implementation should live in a focused module:

```text
trading/definitions/market_structure.py
```

It remains separate from the existing isolated-point and isolated-point-deformation modules because structural point selection is not defined as an isolated-point operation.

## Domain Model

### MarketSegment

```python
@dataclass(frozen=True)
class MarketSegment:
    start_index: int
    end_index: int
```

Validation:

- `start_index` and `end_index` are inclusive;
- `start_index` must be less than or equal to `end_index`;
- every supplied structure point must fall inside the segment; and
- points outside the segment cause a `ValueError`; they are not ignored.

Rejecting out-of-segment points makes accidental whole-history classification visible to the caller.

### StructurePointKind

```python
class StructurePointKind(Enum):
    HIGH = "high"
    LOW = "low"
```

### StructurePoint

```python
@dataclass(frozen=True)
class StructurePoint:
    index: int
    kind: StructurePointKind
    price: float
```

`index` establishes chronology inside the explicit segment. `kind` determines which other points are comparable. `price` is the already-selected structural price. The module does not verify that the price equals a candle's raw high or low because candles are not an input to classification.

### StructureRelationship

```python
class StructureRelationship(Enum):
    HIGHER_HIGH = "higher_high"
    LOWER_HIGH = "lower_high"
    EQUAL_HIGH = "equal_high"
    HIGHER_LOW = "higher_low"
    LOWER_LOW = "lower_low"
    EQUAL_LOW = "equal_low"
```

Equality is explicit and non-directional. It never counts as either a higher or lower relationship, and it breaks directional continuity.

### MarketState

```python
class MarketState(Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    NON_TREND = "non_trend"
```

`NON_TREND` means that the explicit segment does not satisfy either complete trend definition. It is not a trading signal and does not imply a specific market regime beyond this lesson's definition.

## Relationship Rules

A comparison accepts two chronological points of the same kind:

```python
def compare_structure_points(
    previous: StructurePoint,
    later: StructurePoint,
) -> StructureRelationship:
    ...
```

For two highs:

- later price greater than previous price → `HIGHER_HIGH`;
- later price less than previous price → `LOWER_HIGH`;
- equal prices → `EQUAL_HIGH`.

For two lows:

- later price greater than previous price → `HIGHER_LOW`;
- later price less than previous price → `LOWER_LOW`;
- equal prices → `EQUAL_LOW`.

The comparison rejects points of different kinds and non-increasing same-kind indexes. It does not reorder its arguments.

## Consecutive Trend Definition

The course requirement counts structural points, not repeated relationships:

- **UPTREND:** at least two chronological `HIGH` points where the later high is higher than the immediately previous high, and at least two chronological `LOW` points where the later low is higher than the immediately previous low;
- **DOWNTREND:** at least two chronological `HIGH` points where the later high is lower than the immediately previous high, and at least two chronological `LOW` points where the later low is lower than the immediately previous low;
- **NON_TREND:** neither complete definition is satisfied.

The minimum trend structure therefore contains two highs and two lows. Two same-kind points create one relationship, which is sufficient for that kind at the minimum.

Minimum uptrend:

```text
H1 -> H2 = HIGHER_HIGH
L1 -> L2 = HIGHER_LOW
```

Minimum downtrend:

```text
H1 -> H2 = LOWER_HIGH
L1 -> L2 = LOWER_LOW
```

To preserve chronology while comparing like with like:

1. Validate the explicit segment and the complete ordered point sequence.
2. Split the sequence into a high subsequence and a low subsequence without reordering either one.
3. Compare adjacent points inside each kind-specific subsequence.
4. Evaluate the resulting relationships across the whole explicit segment.

An uptrend requires both of the following across the selected segment:

```text
at least one HIGHER_HIGH relationship
at least one HIGHER_LOW relationship
```

A downtrend requires both of the following across the selected segment:

```text
at least one LOWER_HIGH relationship
at least one LOWER_LOW relationship
```

When the segment contains more than two highs or more than two lows, every adjacent same-kind relationship in that subsequence must continue the claimed direction. For an uptrend, all additional high relationships must remain `HIGHER_HIGH` and all additional low relationships must remain `HIGHER_LOW`. For a downtrend, all additional high relationships must remain `LOWER_HIGH` and all additional low relationships must remain `LOWER_LOW`.

“Consecutive” means that each point is compared with the immediately previous point of the same kind in chronological order. An equality or an opposite relationship means that the segment as supplied does not satisfy that directional definition. The classifier never skips an intervening same-kind point to construct a preferred relationship.

This whole-segment rule prevents the classifier from cherry-picking an earlier high run and an unrelated later low run. If a broader segment contains a reversal but a smaller subsegment has continuing structure, the caller must explicitly supply that smaller segment and only its in-segment structure points. The classifier does not choose the subsegment.

The public classifier is conceptually:

```python
def classify_market_state(
    segment: MarketSegment,
    points: Sequence[StructurePoint],
) -> MarketState:
    ...
```

Classification behavior:

- if only the uptrend definition is satisfied, return `UPTREND`;
- if only the downtrend definition is satisfied, return `DOWNTREND`;
- if neither is satisfied, including insufficient points, return `NON_TREND`;
- if malformed data or violated invariants somehow make both directional definitions true, raise `ValueError` instead of guessing which state dominates.

With well-formed price comparisons, both definitions cannot be true at once. The final rule is a defensive invariant: contradictory caller data must never be resolved by recency, counts, or arbitrary precedence that the course has not defined. A broad, valid segment containing reversals is `NON_TREND`; the caller may explicitly select a narrower segment when that is the segment under discussion.

## Inside-Bar Compatibility

The existing Chapter 1 `is_inside_bar(left, right)` definition remains the single source of truth and must be reused unchanged.

Multiple later candles may each be evaluated independently against the same mother candle. For example, `is_inside_bar(mother, child_1)` and `is_inside_bar(mother, child_2)` may both be true. This observation does not introduce a multi-candle structure tracker, mother-bar state machine, or grouping algorithm in this checkpoint.

## Outside-Bar Definition

The future module should expose a focused helper:

```python
def is_outside_bar(left: Candle, right: Candle) -> bool:
    return right.high > left.high and right.low < left.low
```

The definition is:

- strictly higher high on the right candle;
- strictly lower low on the right candle;
- candle color and open/close direction are irrelevant; and
- equality at either boundary is not an outside bar.

This is a strict comparison between exactly two candles. It must not be generalized into a range, group, nested-bar, or multi-candle algorithm.

## Validation and Error Contract

The future implementation should reject invalid inputs explicitly:

| Condition | Result |
| --- | --- |
| `start_index > end_index` | `ValueError` |
| Any point outside the inclusive segment | `ValueError` |
| Point indexes decrease in caller order | `ValueError` |
| Same-kind points repeat the same index | `ValueError` |
| A direct relationship compares different kinds | `ValueError` |
| A direct relationship is not chronological | `ValueError` |
| Both complete uptrend and downtrend definitions are satisfied | `ValueError` |
| Too few points to establish a trend | `MarketState.NON_TREND` |

The classifier must not silently sort, discard, synthesize, or infer points to make invalid input usable.

## Future Implementation Test Plan

Implementation will follow red-to-green test-driven development, but this architectural checkpoint adds no tests. The later implementation plan must cover at least:

1. valid and invalid `MarketSegment` boundaries;
2. each higher-high, lower-high, equal-high, higher-low, lower-low, and equal-low relationship;
3. equality breaking directional continuity;
4. a minimum valid uptrend using exactly two highs and two lows;
5. a minimum valid downtrend using exactly two highs and two lows;
6. extended uptrend and downtrend segments whose additional same-kind points continue the claimed direction;
7. non-trend cases, including fewer than two points of either required kind, equality, and a contradictory intermediate same-kind point;
8. proof that an intervening same-kind point cannot be skipped to manufacture a trend;
9. explicit segment enforcement;
10. rejection of points outside the segment;
11. preservation and validation of chronological input order;
12. rejection of contradictory complete directional structures;
13. strict two-candle outside-bar behavior, including equality boundaries and color independence; and
14. regression coverage proving the existing Chapter 1 inside-bar behavior remains unchanged, including multiple later candles checked against the same mother candle.

Tests must use explicitly supplied structure points. They must not invent an automatic candle-to-structure-point mapping.

## Deferred Work

The following decisions are intentionally deferred until the corresponding course material defines them:

- automatic swing-high and swing-low extraction;
- mapping confirmed isolated points to structure points;
- BMS and any role it plays in structure-point selection;
- timeframe, level, or segment selection;
- BOS and CHOCH terminology;
- resolving or subdividing contradictory real-world structures;
- strategy, signal, entry, exit, and position-management rules;
- execution and broker integrations; and
- generalized multi-candle outside-bar behavior.

Deferral means these behaviors must not be inferred during implementation of this checkpoint.

## Success Criteria

The foundation is correctly implemented when a caller can provide:

1. one explicit inclusive `MarketSegment`; and
2. one chronological sequence of already-identified structural highs and lows inside that segment;

and receive deterministic same-kind relationships followed by exactly one valid `MarketState`, without raw-candle scanning, isolated-point conversion, strategy logic, or future-lesson assumptions.
