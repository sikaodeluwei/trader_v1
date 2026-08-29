# SMS Reversal Structure Design

**Date:** 2026-08-30

**Status:** Approved architectural design

**Scope:** Chapter 2, Lesson 3 — Shift in Market Structure (SMS)

## Purpose

This design defines how to evaluate an explicitly supplied Shift in Market Structure relative to one already-established directional market trend.

The intended composition is:

```text
explicit parent MarketSegment + explicit parent StructurePoints
        |
        v
classify_market_state()
        |
        v
explicit SMSContext for that defined trend
        |
        v
complete ordered post-extreme candle observations
        |
        v
PENDING / PULLBACK_ONLY / SMS_CONFIRMED / PARENT_CONTINUED
```

Lesson 2 BMS describes continuation of a defined trend after a valid pullback. Lesson 3 SMS describes a reversal structure that may terminate a defined trend. An SMS is not proof that an actual market reversal has completed, and it does not confirm an opposite trend.

This lesson evaluates explicit structural inputs. It does not discover the trend, select the structural level, choose the creator point, infer a hierarchy, or make trading decisions.

## Course-Derived Rules

This section records rules taught by the course. Engineering representations used to encode those rules are documented separately.

### SMS meaning

SMS means Shift in Market Structure.

An SMS is a reversal structure relative to one defined trend. It represents a potential termination of that trend when the structural point that created the trend's current extreme is broken.

The course distinguishes:

- a reversal structure; and
- an actual completed market reversal.

Only the reversal structure belongs to Lesson 3. `SMS_CONFIRMED` must never be interpreted as confirmation of an opposite trend or proof that the market has completed a reversal.

### Defined parent trend

SMS can be discussed only relative to an explicitly defined directional trend. The caller must identify the exact `MarketSegment` and establish its `MarketState` before constructing an SMS context.

The parent state must be `MarketState.UPTREND` or `MarketState.DOWNTREND`. `MarketState.NON_TREND` cannot form an SMS context in this lesson.

An SMS for one explicitly defined small trend applies only to that trend. It must not automatically become an SMS for a larger trend, another structural level, or another timeframe.

### Trend extreme and creator point

Each SMS context has two explicit structural boundaries:

- `trend_extreme`: the current extreme of the defined parent trend; and
- `creator_point`: the structural point that created that exact extreme.

For an uptrend:

- `trend_extreme` is a `HIGH`;
- `creator_point` is a `LOW`; and
- the creator point is the explicitly supplied low that created the highest extreme of this defined trend.

For a downtrend:

- `trend_extreme` is a `LOW`;
- `creator_point` is a `HIGH`; and
- the creator point is the explicitly supplied high that created the lowest extreme of this defined trend.

The SMS layer must not choose the creator point. In particular, it must not use a nearest-previous-low or nearest-previous-high heuristic. Correct pairing depends on structural level and hierarchy, which are taught later and remain outside this lesson.

### Creator-point break

The creator point must be strictly broken for SMS to be confirmed.

For an uptrend:

```text
candle.low < creator_point.price
```

For a downtrend:

```text
candle.high > creator_point.price
```

The creator-point break requirement is explicitly taught in Lesson 3.

### Parent continuation

If price strictly breaks the parent trend extreme before it breaks the creator point, the defined parent trend has structurally extended. The old SMS context is finished because its extreme and creator pairing are no longer the current boundaries for that extended trend.

For an uptrend, continuation is:

```text
candle.high > trend_extreme.price
```

For a downtrend, continuation is:

```text
candle.low < trend_extreme.price
```

The SMS layer reports this neutrally as `PARENT_CONTINUED`. It does not claim `BMS_CONFIRMED`, because the Lesson 2 BMS module owns BMS semantics and requires its own explicit pullback context.

The evaluator does not construct a replacement context, choose the new trend extreme, or select its creator point.

### Pullback relationship

While later price remains between the creator point and the parent trend extreme, the counter-trend movement can still be treated as a pullback of this defined trend.

The structural resolution is:

```text
creator point breaks first
        -> SMS_CONFIRMED

trend extreme breaks first
        -> PARENT_CONTINUED
        -> old SMS context is finished
```

### Repeated SMS

Repeated or continuous SMS structures are valid when each belongs to its own explicitly defined trend context.

The SMS layer imposes no maximum SMS count and no one-SMS-per-market rule. Repeated SMS structures may occur even when the broader market is effectively non-trending or range-like, but trading-range classification is not defined in this lesson.

## Engineering Representation Choices

This section describes software choices used to represent the approved course rules. These choices are not teacher quotes or additional market concepts.

### Explicit-input architecture

The new module will be:

```text
trading/definitions/sms_structure.py
```

It reuses:

- `Candle` from `trading/definitions/candles.py`; and
- `MarketSegment`, `MarketState`, `StructurePoint`, and `StructurePointKind` from `trading/definitions/market_structure.py`.

The SMS layer receives an already-established `parent_state`. It does not accept the full parent point sequence, call `classify_market_state()`, or duplicate Lesson 1 classification logic.

It remains separate from `trading/definitions/pullback_structure.py`. It does not call `evaluate_bms()` or reinterpret a `BMSResult`.

### Dense ordinal indexes

Every index is a dense ordinal candle position within one ordered market series and timeframe.

Consequently:

- `index + 1` means the immediately following candle in that series;
- an index is not a fixed amount of clock time;
- an index is not an arbitrary external identifier that may naturally contain gaps; and
- observations from different series or timeframes must not be combined.

The dense-index contract lets the evaluator reject omitted post-extreme candles. An omitted candle could contain the first SMS or parent-continuation event and would make a historical conclusion unreliable.

### Empty observation history

An empty observation sequence returns `PENDING` for a valid context.

`PENDING` is an engineering state meaning that no post-extreme candle has been supplied yet. It is not a teacher-defined market concept, and an empty history must not be described as a pullback.

### OHLC ambiguity handling

One OHLC candle can show that both structural boundaries traded without revealing which boundary was crossed first. Raising `ValueError` for this case is an engineering response to insufficient temporal resolution, not a course-defined market status.

### Result layout

One immutable result object records the status and, for terminal events, the exact supplied structural point and the first event index. The field names `broken_point` and `event_index` are chosen because either the creator point or the trend extreme can be the terminal boundary.

## Relationship to Existing Chapter 2 Layers

The existing `trading/definitions/market_structure.py` remains the single owner of:

- `MarketSegment`;
- `MarketState`;
- `StructurePoint`;
- `StructurePointKind`;
- structural relationships; and
- `classify_market_state()`.

The existing `trading/definitions/pullback_structure.py` remains the single owner of Lesson 2 pullback and BMS evaluation.

Lesson 3 consumes an explicit directional parent state and explicit structural boundaries. It must not modify, duplicate, or weaken Lesson 1 or Lesson 2 semantics unless implementation later proves a real compatibility issue.

The focused Lesson 3 integration check will demonstrate this composition:

```text
explicit parent segment + explicit parent structure points
        |
        v
classify_market_state()
        |
        v
SMSContext with explicit creator/extreme pairing
        |
        v
complete ordered SMSObservation sequence
        |
        v
evaluate_sms()
```

## Domain Model

All new domain records are immutable.

### SMSContext

```python
@dataclass(frozen=True)
class SMSContext:
    parent_segment: MarketSegment
    parent_state: MarketState
    trend_extreme: StructurePoint
    creator_point: StructurePoint
```

The context contains only explicit course-defined inputs. It does not contain inferred swings, raw candle history, hierarchy levels, parent/child identifiers, strategy state, or the full parent point sequence.

### SMSStructureStatus

```python
class SMSStructureStatus(Enum):
    PENDING = "pending"
    PULLBACK_ONLY = "pullback_only"
    SMS_CONFIRMED = "sms_confirmed"
    PARENT_CONTINUED = "parent_continued"
```

Status meanings:

| Status | Meaning |
| --- | --- |
| `PENDING` | Valid context, but no later candle has been supplied. |
| `PULLBACK_ONLY` | At least one later candle exists and neither structural boundary has been strictly broken. |
| `SMS_CONFIRMED` | The creator point was strictly broken first. This confirms a reversal structure only. |
| `PARENT_CONTINUED` | The trend extreme was strictly broken first. The old SMS context is finished. |

### SMSObservation

```python
@dataclass(frozen=True)
class SMSObservation:
    index: int
    candle: Candle
```

An observation supplies one complete OHLC candle at its dense ordinal position after the trend extreme.

### SMSResult

```python
@dataclass(frozen=True)
class SMSResult:
    status: SMSStructureStatus
    broken_point: StructurePoint | None = None
    event_index: int | None = None
```

Result invariants:

- `SMS_CONFIRMED` contains the exact supplied `creator_point` in `broken_point` and the first creator-break observation index in `event_index`;
- `PARENT_CONTINUED` contains the exact supplied `trend_extreme` in `broken_point` and the first continuation-break observation index in `event_index`;
- `PENDING` contains `None` for both optional fields; and
- `PULLBACK_ONLY` contains `None` for both optional fields.

A terminal result must contain both event details. A non-terminal result must contain neither. Partially populated event details are invalid.

## Parent-Segment and Context Validation

The parent segment is the exact explicit segment on which the parent trend was already established. It ends at the current trend extreme.

The required chronology is:

```text
parent_segment.start_index
    <= creator_point.index
    < trend_extreme.index
    == parent_segment.end_index
```

The parent segment may begin before the creator point when earlier structural points are needed to establish the parent trend. Both the creator point and trend extreme must belong to the inclusive parent segment.

For an uptrend:

- `creator_point.kind` must be `StructurePointKind.LOW`;
- `trend_extreme.kind` must be `StructurePointKind.HIGH`; and
- `creator_point.price` must be strictly below `trend_extreme.price`.

For a downtrend:

- `creator_point.kind` must be `StructurePointKind.HIGH`;
- `trend_extreme.kind` must be `StructurePointKind.LOW`; and
- `creator_point.price` must be strictly above `trend_extreme.price`.

`SMSContext` rejects:

- `MarketState.NON_TREND`;
- incorrect directional point kinds;
- a creator point or trend extreme outside the inclusive parent segment;
- a parent segment that does not end exactly at `trend_extreme.index`;
- non-chronological context indexes; and
- incoherent directional boundary prices.

Malformed context input raises `ValueError`. The context never sorts, repairs, synthesizes, or infers structural points.

## Observation-Sequence Contract

The public evaluator is:

```python
def evaluate_sms(
    context: SMSContext,
    observations: Sequence[SMSObservation],
) -> SMSResult:
    ...
```

The evaluator consumes the complete chronological candle sequence after the trend extreme through the latest observation the caller wants evaluated.

For a non-empty sequence:

```text
observations[0].index == context.trend_extreme.index + 1
each later observation.index == previous observation.index + 1
```

Therefore every observation is strictly later than the trend extreme, indexes strictly increase, and no candle position is skipped. Caller order is authoritative and is never sorted.

An observation beginning at the trend-extreme candle, a missing first post-extreme candle, a repeated index, a decreasing index, or any later index gap raises `ValueError`.

An empty sequence is valid and returns `PENDING`.

Every result is valid only through the final supplied observation. It makes no claim about later candles that have not occurred or have not been included.

## Chronological SMS Evaluation

For a valid context, the evaluator validates the complete observation sequence, then scans it once in supplied chronological order and stops at the first terminal boundary event.

### Uptrend observation

For each candle:

```text
sms_crossed = candle.low < creator_point.price
continuation_crossed = candle.high > trend_extreme.price
```

### Downtrend observation

For each candle:

```text
sms_crossed = candle.high > creator_point.price
continuation_crossed = candle.low < trend_extreme.price
```

### First-event resolution

For either direction:

| Observation history | Result |
| --- | --- |
| No observations | `PENDING` |
| Creator boundary only is crossed first | `SMS_CONFIRMED` |
| Parent extreme only is crossed first | `PARENT_CONTINUED` |
| Both boundaries are crossed in one first-reached OHLC candle | `ValueError` because intrabar order is unknown |
| Neither boundary is crossed by the end of a non-empty sequence | `PULLBACK_ONLY` |

The first terminal event wins. Once `SMS_CONFIRMED` has occurred, later recovery or parent continuation cannot erase that historical SMS event. Once `PARENT_CONTINUED` has occurred, later creator-point crossing cannot reactivate the stale context.

The evaluator is stateless. The caller must construct a new explicit context if the parent trend extends and a new extreme/creator pairing becomes relevant.

## Wick and Equality Convention

The following behavior carries forward the Chapter 2 strict-break convention established in Lesson 2. It is not presented as a separately re-taught SMS transcript rule:

- a wick strictly beyond the creator point confirms SMS;
- a wick strictly beyond the trend extreme confirms parent continuation;
- exact contact with either boundary is not a break;
- a close beyond the boundary is not required;
- a candle body beyond the boundary is not required;
- candle color is irrelevant; and
- no penetration percentage, confirmation candle, tick buffer, or tolerance is added.

The creator-point break itself is the Lesson 3 course rule. Wick and equality handling specify how the existing Chapter 2 break convention measures that rule in OHLC data.

## Same-Candle Dual-Boundary Ambiguity

If one observation candle strictly crosses both the creator-point boundary and the parent trend extreme, the evaluator raises:

```python
ValueError("OHLC cannot determine the intrabar boundary order")
```

The evaluator must not infer precedence from candle color, assume an OHLC path, or guess whether SMS or continuation occurred first.

This is an OHLC resolution limitation rather than a market-structure status. A future ordered intrabar or tick evaluator may resolve the case only when actual event order is available. That evaluator is not part of Lesson 3.

## Parent Continuation and Context Lifetime

`PARENT_CONTINUED` is terminal for the supplied `SMSContext`.

It means only that the parent trend extreme was strictly broken before the creator point in the complete supplied history. It does not invoke the BMS evaluator, claim a valid Lesson 2 pullback, create a new context, or identify the creator point of the extended trend.

Leaving the old context active after parent continuation would compare later candles against stale boundaries. The caller must explicitly construct a replacement context when sufficient course-defined inputs are available.

## Repeated and Multi-Scale Contexts

The evaluator supports repeated SMS structures by evaluating separate explicit contexts. It adds no global SMS counter, maximum count, one-SMS rule, or persistent registry.

Likewise, a small trend and a larger trend may each have an independently supplied context. A result for one context has no automatic effect on the other.

The design adds no hierarchy fields, recursive discovery, importance ranking, structural level, or timeframe relationship. Those relationships remain caller-owned until later course lessons define them.

## Error Contract

| Condition | Result |
| --- | --- |
| Parent state is `NON_TREND` | `ValueError` |
| Directional point kinds do not match | `ValueError` |
| Creator point or trend extreme is outside the parent segment | `ValueError` |
| Parent segment does not end at the trend extreme | `ValueError` |
| Context indexes violate chronology | `ValueError` |
| Directional creator/extreme prices are incoherent | `ValueError` |
| First observation is not the immediately following dense candle index | `ValueError` |
| Observation indexes repeat, decrease, or skip | `ValueError` |
| One observation crosses both boundaries | `ValueError` explaining OHLC order ambiguity |
| Valid context with no observations | `PENDING` |
| Non-empty history with neither boundary crossed | `PULLBACK_ONLY` |
| Creator point is strictly broken first | `SMS_CONFIRMED` |
| Parent trend extreme is strictly broken first | `PARENT_CONTINUED` |

Malformed inputs raise errors. Well-formed histories return one of the four SMS-layer statuses.

## Testing Strategy

No tests are created during this design-only task. The later implementation plan must use red-to-green test-driven development.

### Level 1 — Unit tests

The implementation plan should cover at least:

1. valid uptrend `SMSContext` construction;
2. valid downtrend `SMSContext` construction;
3. rejection of `MarketState.NON_TREND`;
4. rejection of incorrect structure-point kinds;
5. rejection of invalid context chronology;
6. exact parent-segment ending at `trend_extreme`;
7. directional creator/extreme price validation;
8. empty observations producing `PENDING`;
9. one or multiple inside-boundary candles producing `PULLBACK_ONLY`;
10. a strict wick creator break producing `SMS_CONFIRMED`;
11. exact creator-point contact not confirming SMS;
12. a strict parent-extreme break producing `PARENT_CONTINUED`;
13. exact parent-extreme contact not confirming continuation;
14. first-terminal-event precedence;
15. later recovery not erasing an earlier SMS;
16. complete dense chronology enforcement;
17. rejection of a missing observation;
18. rejection of repeated or decreasing observation indexes;
19. same-candle dual-boundary ambiguity with the approved `ValueError`;
20. `SMSResult` field invariants;
21. independence from candle color, body, and close;
22. mirrored uptrend/downtrend behavior;
23. independent repeated explicit SMS contexts;
24. a small-trend SMS not inferring a large-trend SMS; and
25. absence of future hierarchy behavior.

### Focused Chapter 2 cross-layer integration

Lesson 3 should receive a small integration smoke test proving only that already-taught APIs compose:

```text
explicit parent segment + explicit parent points
        -> classify_market_state()
        -> SMSContext
        -> complete SMSObservation sequence
        -> evaluate_sms()
```

Representative cases should remain few and focused: directional parent classification followed by SMS confirmation, parent continuation, or unresolved pullback history. The integration test must not invent hierarchy or later-course behavior.

### Formal Level 2 validation after Chapter 2 completion

The formal Chapter 2 course-scenario suite remains deferred until every Chapter 2 market-structure lesson has been implemented.

The Lesson 3 implementation must not create:

```text
tests/test_course_market_structure_scenarios.py
```

At the Chapter 2 completion checkpoint, the project will review the complete taught model, design comprehensive hand-labelled scenarios, exercise all relevant structure layers together, and run the full regression suite.

### Conditional Level 3 raw-chart validation

Raw-chart automatic validation remains conditional on whether the completed course eventually provides legitimate rules for structural-point extraction, trend levels, cycles, and hierarchy. It must not be approximated with invented swing or zig-zag rules.

## Explicitly Deferred Work

This design does not implement or define:

- automatic short-, medium-, or long-term structure;
- cycle or timeframe hierarchy;
- structure-level hierarchy;
- automatic parent/child trend detection;
- automatic trend-segment selection;
- automatic trend-extreme discovery;
- automatic creator-point selection;
- automatic swing or zig-zag extraction;
- automatic structure-point extraction;
- automatic mapping from isolated points to structure points;
- confirmation of an actual market reversal;
- confirmation of an opposite trend;
- trading-range or channel logic;
- divergence or momentum rules;
- multi-timeframe analysis or bias;
- strategy, signal, entry, exit, stop-loss, take-profit, or position-sizing logic; or
- broker, order, or execution integration.

The design uses only the course terminology already approved for this stage: trend/non-trend, pullback, BMS, and SMS.

## Design Invariants

The implementation plan and later code must preserve these invariants:

1. SMS is a reversal structure, not confirmation of an actual reversal or opposite trend.
2. One already-defined directional parent trend is mandatory.
3. The caller explicitly supplies the exact parent segment, trend extreme, and creator point.
4. Creator-point selection is never automatic and never uses a nearest-point heuristic.
5. The parent segment ends exactly at the supplied trend extreme.
6. Creator and trend-extreme kinds, chronology, membership, and prices match the parent direction.
7. Observations use complete dense ordinal chronology after the trend extreme and are never sorted.
8. Empty history is the engineering state `PENDING`, not a pullback.
9. A non-empty unresolved history is `PULLBACK_ONLY`.
10. The first strict creator-point break produces `SMS_CONFIRMED`.
11. The first strict trend-extreme break produces terminal `PARENT_CONTINUED` for the old context.
12. Strict wick crossings count, while equality does not.
13. One OHLC candle crossing both boundaries is rejected as temporally ambiguous.
14. Terminal results contain the exact supplied broken point and first event index.
15. Repeated and differently scaled contexts remain explicit and independent.
16. The SMS layer neither claims BMS nor constructs a replacement context after continuation.
17. No later-course hierarchy, extraction, reversal-confirmation, strategy, or execution logic is introduced.
18. Formal Chapter 2 Level 2 validation remains deferred until all Chapter 2 lessons are complete.

## Remaining Course Ambiguities

The course identifies the creator point conceptually but has not yet supplied general automatic rules for selecting the correct creator point across short-, medium-, and long-term structures. This design therefore requires the creator point to be explicit.

OHLC data cannot determine event order when one candle strictly crosses both the creator point and parent trend extreme. This design rejects that case rather than inventing precedence. Ordered intrabar data may resolve it in a future lesson or adapter, but no such evaluator is defined here.

The course has not yet defined how repeated SMS structures relate across trading ranges, structural levels, or timeframes. Separate explicit contexts preserve the taught behavior without inferring those future relationships.
