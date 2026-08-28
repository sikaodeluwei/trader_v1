# BMS Pullback Structure Design

**Date:** 2026-08-29

**Status:** Approved architectural design

**Scope:** Chapter 2, Lesson 2 — BMS Pullback Structure

## Purpose

This design defines how to evaluate an explicitly supplied pullback and subsequent Break in Market Structure (BMS) relative to an already-established directional market state.

The successful composition is:

```text
explicit parent MarketSegment + explicit parent StructurePoints
        |
        v
classify_market_state()
        |
        v
explicit PullbackContext
        |
        v
complete ordered post-pullback candle observations
        |
        v
PULLBACK_ONLY / BMS_CONFIRMED / NOT_A_PULLBACK
```

This lesson adds trend-relative pullback and BMS vocabulary. It does not discover structural points, choose the parent trend, infer a hierarchy, or create trading decisions.

## Course Terminology

### Parent trend

A pullback exists only relative to an already-defined directional trend. The caller must establish the parent state as `MarketState.UPTREND` or `MarketState.DOWNTREND` before constructing the pullback context.

`MarketState.NON_TREND` cannot have a BMS pullback context under this lesson.

### Pullback

A pullback is an opposite-direction movement after the previous trend-direction extreme:

- in an uptrend, the pullback moves downward from the previous high;
- in a downtrend, the pullback moves upward from the previous low.

A pullback and a BMS are different concepts. A valid pullback may exist without a later BMS.

### Trend origin

The trend origin is the parent-trend boundary that the pullback must preserve:

- for an uptrend, it is a `LOW`;
- for a downtrend, it is a `HIGH`.

Touching the origin does not invalidate the pullback. Strictly crossing it means the movement is no longer a pullback of this parent trend and produces `NOT_A_PULLBACK`.

This result is neutral. It must not be described as a reversal, SMS, CHOCH, or any other future-course concept.

### BMS

A BMS occurs only after a valid pullback when a later observed price strictly breaks the previous trend-direction extreme:

- uptrend: candle high is strictly above the previous high;
- downtrend: candle low is strictly below the previous low.

A wick crossing counts because that price traded. Equality is only a touch and does not count as a break.

## Relationship to the Existing Market-Structure Layer

The existing `trading/definitions/market_structure.py` remains the single owner of:

- `MarketSegment`;
- `MarketState`;
- `StructurePoint`;
- `StructurePointKind`;
- `StructureRelationship`;
- `compare_structure_points()`;
- `classify_market_state()`; and
- strict outside-bar recognition.

Lesson 2 must not redesign or duplicate those types or classification rules.

The new module will be:

```text
trading/definitions/pullback_structure.py
```

It receives the already-established `parent_state`. `PullbackContext` does not accept the full parent point sequence and does not call, reimplement, or second-guess `classify_market_state()`.

The mandatory integration scenarios will demonstrate that callers can classify the explicit parent structure first and then pass the resulting directional state into the Lesson 2 layer.

## Index Semantics

Every index in this design is a dense ordinal candle position within one ordered market series and timeframe.

Consequently:

- `index + 1` means the immediately following candle observation in that same series;
- an index does not represent a fixed amount of clock time;
- an index is not an arbitrary external identifier that may naturally contain gaps; and
- observations from different series or timeframes must not be combined in one context.

These semantics make sequence completeness enforceable. Consecutive integer indexes prove that no post-pullback candle position was silently omitted from the supplied evaluation history.

An upstream adapter that uses timestamps, broker identifiers, or sparse source rows must first map the chosen ordered candle series to these dense positional indexes. This design does not perform that mapping.

## Domain Model

All new domain records are immutable.

### PullbackContext

```python
@dataclass(frozen=True)
class PullbackContext:
    parent_segment: MarketSegment
    parent_state: MarketState
    trend_origin: StructurePoint
    previous_extreme: StructurePoint
    pullback_extreme: StructurePoint
```

The context contains only explicit course-defined inputs. It does not contain inferred swings, raw candle history, strategy state, nesting levels, or the full parent point sequence.

### PullbackStructureStatus

```python
class PullbackStructureStatus(Enum):
    PULLBACK_ONLY = "pullback_only"
    BMS_CONFIRMED = "bms_confirmed"
    NOT_A_PULLBACK = "not_a_pullback"
```

These are the only Lesson 2 outcomes. There is no indeterminate market-status value and no reversal status.

### BMSObservation

```python
@dataclass(frozen=True)
class BMSObservation:
    index: int
    candle: Candle
```

An observation supplies one complete OHLC candle at its dense ordinal position after the pullback extreme.

### BMSResult

```python
@dataclass(frozen=True)
class BMSResult:
    status: PullbackStructureStatus
    broken_extreme: StructurePoint | None = None
    breakout_index: int | None = None
```

Result invariants:

- `BMS_CONFIRMED` contains the exact supplied `previous_extreme` in `broken_extreme` and the first BMS observation index in `breakout_index`;
- `PULLBACK_ONLY` contains `None` for both optional fields; and
- `NOT_A_PULLBACK` contains `None` for both optional fields.

The result does not prescribe a signal, trade, replacement structure point, or later-course interpretation.

## Parent-Segment and Context Validation

The parent segment is the exact explicit segment on which the parent trend was already established. It ends at the previous trend-direction extreme from which the current pullback begins.

The required chronology is:

```text
parent_segment.start_index
    <= trend_origin.index
    < previous_extreme.index
    == parent_segment.end_index
    < pullback_extreme.index
```

The parent segment may begin before `trend_origin` when earlier structural points are needed to establish the larger parent trend. It must not extend beyond `previous_extreme`, because unexplained post-extreme candles are part of the later pullback/BMS evaluation rather than the already-established parent segment.

For an uptrend:

- `trend_origin.kind` must be `LOW`;
- `previous_extreme.kind` must be `HIGH`;
- `pullback_extreme.kind` must be `LOW`; and
- `trend_origin.price` must be strictly below `previous_extreme.price` so the two boundaries are coherent.

For a downtrend:

- `trend_origin.kind` must be `HIGH`;
- `previous_extreme.kind` must be `LOW`;
- `pullback_extreme.kind` must be `HIGH`; and
- `trend_origin.price` must be strictly above `previous_extreme.price`.

`PullbackContext` rejects:

- `MarketState.NON_TREND`;
- incorrect point kinds;
- a trend origin or previous extreme outside the inclusive parent segment;
- a parent segment that does not end exactly at `previous_extreme.index`;
- non-chronological context indexes; and
- incoherent origin and previous-extreme prices.

It never sorts, repairs, synthesizes, or infers context points.

## Observation-Sequence Contract

The public evaluator is:

```python
def evaluate_bms(
    context: PullbackContext,
    observations: Sequence[BMSObservation],
) -> BMSResult:
    ...
```

The evaluator consumes the complete chronological post-pullback candle sequence through the latest observation the caller wants evaluated.

For a non-empty sequence:

```text
observations[0].index == context.pullback_extreme.index + 1
each later observation.index == previous observation.index + 1
```

Therefore every observation is strictly later than the pullback extreme, indexes strictly increase, and no candle position is skipped. The evaluator preserves caller order and never sorts.

Repeated, decreasing, or gapped indexes raise `ValueError`. A sequence that begins at the pullback candle itself also raises `ValueError`: OHLC cannot prove whether the pullback extreme occurred before a BMS crossing within that same candle.

An empty sequence is valid. For a valid pullback it produces `PULLBACK_ONLY`, meaning that no later boundary observation has yet been supplied.

The result is valid only through the final supplied observation. It makes no claim about later candles that have not yet occurred or have not been included.

## Pullback Evaluation

After validating all structural and sequence inputs, the evaluator applies the context-level course checks before scanning later boundary events.

For an uptrend:

- `pullback_extreme.price >= previous_extreme.price` means no downward pullback occurred and produces `NOT_A_PULLBACK`;
- `pullback_extreme.price < trend_origin.price` means the pullback already broke the parent origin and produces `NOT_A_PULLBACK`; and
- `pullback_extreme.price == trend_origin.price` remains a valid pullback because equality is not a break.

For a downtrend:

- `pullback_extreme.price <= previous_extreme.price` means no upward pullback occurred and produces `NOT_A_PULLBACK`;
- `pullback_extreme.price > trend_origin.price` means the pullback already broke the parent origin and produces `NOT_A_PULLBACK`; and
- `pullback_extreme.price == trend_origin.price` remains valid.

These are valid domain outcomes, not malformed-context errors.

## Chronological BMS Evaluation

For a valid pullback, the evaluator scans observations once in supplied chronological order and stops at the first terminal boundary event.

### Uptrend observation

For each candle:

```text
origin_crossed = candle.low < trend_origin.price
bms_crossed = candle.high > previous_extreme.price
```

### Downtrend observation

For each candle:

```text
origin_crossed = candle.high > trend_origin.price
bms_crossed = candle.low < previous_extreme.price
```

### First-event resolution

For either direction:

| Observation | Result |
| --- | --- |
| Origin crossing only | `NOT_A_PULLBACK` |
| BMS crossing only | `BMS_CONFIRMED` |
| Both boundaries crossed | `ValueError` because OHLC cannot determine intrabar boundary order |
| Neither boundary crossed | Continue scanning |
| End of sequence without a crossing | `PULLBACK_ONLY` |

The first terminal event wins. Later observations cannot overwrite it.

For example, if an earlier candle breaks the BMS level and a later candle crosses the origin, the result remains the earlier `BMS_CONFIRMED`. A caller cannot evaluate only the later candle because the completeness contract rejects skipped post-pullback indexes.

If the pullback was already invalidated at `pullback_extreme`, the known earlier invalidation produces `NOT_A_PULLBACK`; a later candle cannot create a BMS for that parent context.

## Wick and Equality Rules

- An uptrend BMS requires `candle.high > previous_extreme.price`.
- A downtrend BMS requires `candle.low < previous_extreme.price`.
- A wick strictly beyond the BMS level is sufficient.
- A close beyond the level is not required.
- A candle body beyond the level is not required.
- Candle color is irrelevant.
- No confirmation candle, percentage penetration, tick buffer, or tolerance is added.
- Exact contact with the BMS level is not a break.
- Exact contact with the trend origin is not invalidation.

## OHLC Ambiguity

If one later OHLC candle strictly crosses both the trend-origin boundary and the BMS boundary, the evaluator raises `ValueError` with the message:

```text
OHLC cannot determine the intrabar boundary order
```

It must not guess BMS-first, invalidation-first, candle-color order, or an assumed open-high-low-close path. It must not convert the ambiguity into `NOT_A_PULLBACK`, `BMS_CONFIRMED`, a new market state, or a reversal label.

The same uncertainty explains why an observation at `pullback_extreme.index` is not allowed. A future ordered intrabar evaluator may allow events within one candle only when actual timestamps prove:

```text
pullback_extreme_timestamp < bms_crossing_timestamp
```

That ordered-intrabar extension is not part of Lesson 2.

## Repeated BMS and Nested Pullbacks

The evaluator is stateless and imposes no maximum BMS count, one-BMS-per-trend rule, or channel restriction.

Repeated events are represented by separate explicitly supplied contexts, each evaluated against its own complete post-pullback observation sequence.

A pullback may contain a smaller explicitly supplied parent trend with its own pullback and BMS. The caller represents this by constructing a second independent `PullbackContext` and calling the same evaluator. The design adds no parent identifier, child collection, level number, recursive discovery, automatic nesting, or importance ranking.

This preserves composability without inventing the level relationships deferred to later Chapter 2 lessons.

## Error Contract

| Condition | Result |
| --- | --- |
| Parent state is `NON_TREND` | `ValueError` |
| Directional point kinds do not match | `ValueError` |
| Origin or previous extreme is outside the parent segment | `ValueError` |
| Parent segment does not end at the previous extreme | `ValueError` |
| Context indexes violate strict chronology | `ValueError` |
| Directional origin and previous-extreme prices are incoherent | `ValueError` |
| First observation is not the immediately following dense candle index | `ValueError` |
| Observation indexes repeat, decrease, or skip | `ValueError` |
| One observation crosses both boundaries | `ValueError` explaining OHLC order ambiguity |
| No opposite-direction pullback occurred | `NOT_A_PULLBACK` |
| Pullback strictly crossed its parent origin | `NOT_A_PULLBACK` |
| A later origin-only crossing occurs first | `NOT_A_PULLBACK` |
| A later BMS-only crossing occurs first | `BMS_CONFIRMED` |
| No supplied observation crosses either boundary | `PULLBACK_ONLY` |

Malformed inputs raise errors. Well-formed inputs that do not meet the course definition return one of the three course statuses.

## Testing Strategy

### Level 1 — Unit tests

Implementation must follow red-to-green test-driven development in a focused future file such as:

```text
tests/test_pullback_structure.py
```

Unit coverage must include:

1. immutable domain objects and stable enum values;
2. directional point-kind validation;
3. rejection of `NON_TREND`;
4. exact parent-segment ending boundary;
5. strict context chronology and segment inclusion;
6. coherent directional boundary prices;
7. uptrend and downtrend pullback rules;
8. origin equality remaining valid;
9. strict origin invalidation;
10. exact BMS touches not breaking;
11. wick-based strict BMS breaks;
12. independence from candle close, body, and color;
13. empty observation sequences;
14. immediate and multi-candle BMS;
15. first-terminal-event precedence;
16. repeated, decreasing, same-index, and skipped observations;
17. same-candle dual-boundary ambiguity;
18. `BMSResult` field invariants; and
19. separate repeated and nested contexts.

### Level 2 — Mandatory course-scenario integration gate

Immediately after BMS implementation and before Chapter 2 Lesson 3, the project must add and pass:

```text
tests/test_course_market_structure_scenarios.py
```

Each scenario must demonstrate the intended cross-layer composition:

```text
explicit parent segment + explicit parent structure points
        |
        v
classify_market_state()
        |
        v
PullbackContext
        |
        v
complete ordered BMSObservation sequence
        |
        v
evaluate_bms()
```

Required scenarios are:

1. minimum valid uptrend, valid pullback, and no previous-high break producing `PULLBACK_ONLY`;
2. minimum valid uptrend and a wick breaking the previous high producing `BMS_CONFIRMED`;
3. the minimum valid downtrend mirror producing `BMS_CONFIRMED`;
4. exact contact with the BMS level producing no BMS;
5. an uptrend pullback breaking below its parent origin producing `NOT_A_PULLBACK`;
6. the mirrored downtrend invalidation;
7. an extended continuing trend with repeated explicit contexts whose valid BMS events remain independently valid;
8. separate outer and nested explicit contexts evaluated without automatic hierarchy inference;
9. parent state proven through `classify_market_state()` before each pullback/BMS evaluation;
10. a dual-boundary OHLC candle rejected instead of guessed;
11. first-event precedence across multiple later candles; and
12. rejection of an observation sequence that omits an earlier post-pullback candle.

The Level 2 checkpoint answers whether the implemented course layers reach the same conclusion as complete hand-defined lesson scenarios. Passing isolated unit tests is not sufficient to begin Lesson 3. The Level 2 scenarios and the full regression suite must pass first.

These scenarios still use explicitly supplied segments and structure points. They are not raw-chart recognition tests.

### Level 3 — Future raw-chart end-to-end validation

Only after the course defines legitimate automatic structure-point and zig-zag extraction rules will development pause for a higher-level validation phase:

```text
raw historical candles
        |
        v
automatic structure extraction
        |
        v
trend -> pullback -> BMS and later structures
        |
        v
comparison with manually labelled teacher/course examples
```

This future milestone must verify connected behavior rather than merely accumulating individually correct helper tests. It is documented now but must not be approximated with invented swing logic, direct isolated-point mapping, or guessed hierarchy rules.

## Explicitly Deferred Work

This design does not implement or define:

- automatic swing or zig-zag extraction;
- automatic structural high/low discovery;
- automatic pullback discovery from raw candles;
- automatic trend, segment, timeframe, or parent-level selection;
- automatic mapping from Chapter 1 isolated points to Chapter 2 structure points;
- automatic nesting or level hierarchy;
- ordered-intrabar resolution of same-candle event order;
- SMS or any reversal structure;
- BOS or CHOCH;
- reversal confirmation or trend-reversal labels;
- strategy rules or signals;
- entries, exits, stop losses, take profits, or position sizing; or
- broker execution and live-trading integration.

The next lesson's reversal material remains separate.

## Design Invariants

The implementation plan and later code must preserve these invariants:

1. Parent trend context is mandatory and already classified.
2. `market_structure.py` remains the single source for parent-state classification.
3. Pullback and BMS remain distinct outcomes.
4. The parent segment ends exactly at the previous trend extreme.
5. The pullback extreme and every evaluated observation occur strictly later.
6. Indexes are dense positional candle indexes in one ordered series/timeframe.
7. The complete post-pullback sequence is required and never sorted.
8. The first terminal boundary event determines the result.
9. Wick crossings count, while equality does not.
10. OHLC dual-boundary order is rejected as ambiguous.
11. Repeated and nested structures remain explicitly composable without inferred hierarchy.
12. No future-course or strategy behavior is introduced.
13. The Level 2 course-scenario gate is mandatory before Lesson 3.

## Remaining Course Ambiguity

OHLC data cannot determine event order when one candle crosses both the trend-origin and BMS boundaries, or when a pullback extreme and possible BMS crossing occur in the same candle. This design deliberately rejects both cases rather than inventing precedence.

Ordered intrabar or tick data could resolve these cases in the future when it proves the actual event timestamps. The course has not yet defined that extension, so it remains deferred and does not create an additional Lesson 2 status.
