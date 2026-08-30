# Short-Term Structure Design

**Date:** 2026-08-30

**Status:** Approved architectural checkpoint

**Scope:** Chapter 2, Lesson 5 — Short-Term Market Structure

## Purpose

This specification records the Chapter 2, Lesson 5 operational rules for recognizing short-term structural points and normalizing them into a short-term structure line. Unlike Lesson 4, this lesson authorizes a future production mapping from confirmed isolated points to short-term highs and lows, together with objective line-normalization rules.

The approved flow is:

```text
ordered candles
        |
        v
existing strict and deformation-aware isolated-point recognition
        |
        v
all valid confirmed short-term points
        |
        v
short-term structure-line normalization
        |
        v
final line vertices + explicitly recorded suppressions
```

This is a design-spec checkpoint only. It adds no production API, tests, implementation plan, strategy, or execution behavior.

## Course Context

### Course-derived context

Any explicitly defined candle or candle group can correspond to a price movement that can be discussed. The segment being discussed must remain explicit; the lesson does not make all available chart history one implicit analytical object.

In this course, “走势类型” is used mainly for directional trend movement: an upward trend or a downward trend. The broader market-state vocabulary remains the previously taught distinction between trend and non-trend.

Lesson 5 is still teaching components of market structure. It does not provide a complete reversal model, trading system, or entry/exit framework. In particular:

- BMS remains a pullback-and-continuation structure evaluated inside an explicit Lesson 2 context;
- SMS remains a reversal structure evaluated inside an explicit Lesson 3 context;
- neither BMS nor SMS is a complete trading strategy; and
- neither event alone authorizes entries, exits, or confirmation of a completed reversal.

### Engineering constraint

The short-term structure layer must describe confirmed structural points and a normalized structure line only. It must not classify market state implicitly, construct BMS/SMS contexts, or produce trading decisions.

## Scope

### Course-derived scope

Lesson 5 provides operational rules for:

- treating confirmed isolated highs as short-term highs;
- treating confirmed isolated lows as short-term lows;
- connecting same-level short-term points in chronological order;
- normalizing consecutive same-kind points without deleting their validity;
- suppressing objectively complete inside structures from the line; and
- preserving disputed cases when no precise course rule resolves them.

### Approved engineering scope

A future implementation may add a focused short-term structure layer that:

- reuses existing isolated-point and deformation-aware recognition;
- maps confirmed recognition results into short-term points;
- preserves every valid short-term point separately from the final line vertices;
- records why a valid point was omitted from the normalized line;
- validates strict caller chronology without sorting; and
- applies the definite normalization rules repeatedly until stable.

This checkpoint creates only:

```text
docs/superpowers/specs/2026-08-30-short-term-structure-design.md
```

## Course-Derived Definitions

### Short-term high

A confirmed isolated `HIGH`, including a course-supported isolated-point deformation, is a short-term high.

### Short-term low

A confirmed isolated `LOW`, including a course-supported isolated-point deformation, is a short-term low.

### Short-term structure line

The short-term structure line connects normalized short-term highs and lows in chronological left-to-right order. It preserves the structural movement represented by the course rules while avoiding artificial turns from consecutive same-kind points and omitting objectively complete inside structures.

### Valid point versus visible vertex

A valid short-term point is a confirmed course-recognized point. A structure-line vertex is a valid short-term point retained after line normalization.

These concepts are intentionally different:

```text
valid short-term point
        does not necessarily imply
visible short-term structure-line vertex
```

Suppression from the line does not revoke confirmation, delete the point, or make the original recognition invalid.

## Three Relative Structural Levels

### Course-derived convention

Lesson 5 introduces the practical convention of discussing three structural levels:

- short-term;
- medium-term; and
- long-term.

These are relative and partly subjective structural levels. They are not aliases for fixed chart periods.

Consequently:

- 1-hour is not inherently short-term;
- 4-hour is not inherently medium-term;
- daily is not inherently long-term;
- no timeframe-to-level mapping is authorized; and
- the same period may participate in different relative-level discussions depending on the chosen analytical reference.

Lesson 5 operationally defines only the short-term point and structure-line layer. Lesson 6 is expected to teach medium-term and long-term structure definitions.

### Engineering constraint

No production `SHORT`/`MEDIUM`/`LONG` enum is authorized by this checkpoint. A later approved implementation design may revisit the representation only after Lesson 6 is understood and only if an explicit type is genuinely required.

The Lesson 4 invariant remains binding:

```text
period != structural level
```

## Same-Level Connection Invariant

### Course-derived rule

A market-structure line may connect only highs and lows belonging to the same structural level.

Therefore:

- short-term highs and lows connect only to short-term highs and lows;
- medium-term points must not be inserted into a short-term line;
- long-term points must not be inserted into a short-term line; and
- one level's line must not automatically propagate an event into another level.

### Engineering constraint

The future short-term builder accepts only confirmed short-term points. It does not accept generic unlabeled structure points and then infer their level. It constructs no parent/child links and makes no claims about medium-term or long-term structure.

## Short-Term Point Definition

### Authorized mapping

Lesson 5 narrows the earlier restriction against automatically equating isolated points with structure points:

- a confirmed isolated `HIGH` may be mapped to a short-term `HIGH`;
- a confirmed isolated `LOW` may be mapped to a short-term `LOW`;
- the index, kind, and price come from the confirmed isolated point; and
- recognition basis or source information is retained when it is available.

This authorization is specific to short-term structure. It does not make the same point medium-term, long-term, or valid at every structural level.

### Reuse of existing recognition

The repository already owns the applicable recognition rules:

- `trading/definitions/isolated_points.py` owns strict potential and confirmed isolated-point recognition;
- `trading/definitions/isolated_point_deformations.py` owns the supported deformation-aware recognition;
- `IsolatedPointStatus.CONFIRMED` distinguishes valid confirmed points from raw potentials;
- `IsolatedPointBasis.STRICT` records strict confirmation; and
- `IsolatedPointBasis.RIGHT_INSIDE_BAR` records the currently supported right-inside-bar deformation.

The short-term layer must reuse these definitions. It must not duplicate their candle comparisons or create a competing raw-candle pattern detector.

Only confirmed points may be mapped. A `POTENTIAL` isolated point is not yet a short-term point and must be rejected or excluded by the future mapping boundary rather than silently promoted.

### Unresolved deformation cases

Lesson 5 does not add a precise algorithm for any context-dependent or disputed isolated-point deformation that the existing deformation module deliberately leaves unresolved. Those cases remain unresolved. The short-term layer must not guess a recognition result that the isolated-point layer did not confirm.

## Architectural Layering

Short-term point recognition and short-term structure-line construction remain separate responsibilities.

### Recognition responsibility

The existing Chapter 1 layer answers:

```text
Is this an objectively confirmed isolated point under a supported rule?
```

### Mapping responsibility

The future short-term mapping boundary answers:

```text
How is this confirmed isolated point represented as a short-term point?
```

It preserves identity fields and any available recognition basis. It does not change confirmation semantics.

### Normalization responsibility

The future structure-line builder answers:

```text
Which valid short-term points appear as vertices after applying the taught
same-kind and definite inside-structure rules?
```

It consumes confirmed short-term points. It does not rescan candles or reinterpret their isolated-point validity.

This separation prevents line-cleaning decisions from erasing upstream recognition evidence.

## Proposed Domain Model

The exact Python names remain an implementation-plan decision, but the later implementation must preserve the following semantics.

### ShortTermPoint

Conceptually:

```python
@dataclass(frozen=True)
class ShortTermPoint:
    index: int
    kind: IsolatedPointKind
    price: float
    recognition_basis: IsolatedPointBasis | None
```

Required meaning:

- `index` is the original confirmed candle index;
- `kind` is `HIGH` or `LOW` from the confirmed isolated point;
- `price` is the confirmed isolated-point price; and
- recognition basis or equivalent source metadata is preserved where the upstream result supplies it.

A strict confirmed point received without a basis-carrying wrapper may be represented through an explicit strict source during mapping or through a documented absence of optional source metadata. The implementation plan must choose one consistent representation without recomputing recognition.

### Suppression reason

The approved design-level suppression meanings are:

```text
CONSECUTIVE_SAME_KIND
INSIDE_STRUCTURE
```

The implementation plan may choose exact Python names while preserving those meanings.

### Suppressed point record

Each valid point omitted from the final line must remain associated with its suppression reason. A conceptual representation is:

```python
@dataclass(frozen=True)
class SuppressedShortTermPoint:
    point: ShortTermPoint
    reason: ShortTermSuppressionReason
```

### ShortTermStructure

Conceptually:

```python
@dataclass(frozen=True)
class ShortTermStructure:
    points: tuple[ShortTermPoint, ...]
    vertices: tuple[ShortTermPoint, ...]
    suppressed: tuple[SuppressedShortTermPoint, ...]
```

Required meaning:

- `points` contains every valid confirmed short-term point in caller chronology;
- `vertices` contains the points used by the normalized structure line, in chronology;
- `suppressed` records valid points omitted from `vertices` and why; and
- normalization never mutates or deletes the all-points evidence.

The implementation plan may use another immutable sequence type or exact field naming if these distinctions and ordering guarantees remain explicit.

## Chronology and Validation

### Input contract

The future structure-line builder receives a sequence of already-confirmed short-term points.

Validation rules:

- indexes must be strictly increasing in caller order;
- duplicate indexes are invalid, regardless of point kind;
- decreasing or repeated indexes raise an explicit error;
- the builder must not silently sort input;
- the builder must not discard malformed inputs to make them usable; and
- the builder must not correct upstream recognition or synthesize missing points.

Chronological ordering is semantic. A different input order can represent a different market movement, so sorting would conceal an upstream error.

### Neutral small-input behavior

Small valid inputs carry no invented trend meaning:

- an empty sequence produces an empty structure with no vertices or suppressions;
- one valid point remains one point and one vertex;
- two opposite-kind points remain two chronological vertices unless an objective later rule applies; and
- two same-kind points are handled by the same-kind normalization rule when it has an objective representative.

The builder must not impose an arbitrary minimum point count. It also must not label a small set as an uptrend, downtrend, or non-trend; Lesson 1 market-state classification remains separate.

### Ambiguous equal extremes

The course rule selects the highest point in a consecutive `HIGH` run and the lowest point in a consecutive `LOW` run. When more than one point shares the same extreme price and the course supplies no rule for choosing between equal candidates, the implementation must not assign discretionary structural importance. The later implementation plan must either preserve the tied candidates or adopt a separately approved deterministic representation that changes no price-level meaning. It must not silently invent a nearest, newest, oldest, or strongest-point market rule.

## Consecutive Same-Kind Normalization

### Course-derived rule

Consecutive valid points of the same kind do not require artificial structure-line turns between them.

For one consecutive `HIGH` run without an intervening short-term `LOW`:

- every confirmed high remains in `ShortTermStructure.points`;
- the highest high contributes the line vertex for the run when it is objectively unique; and
- other highs may appear in `suppressed` with reason `CONSECUTIVE_SAME_KIND`.

For one consecutive `LOW` run without an intervening short-term `HIGH`:

- every confirmed low remains in `points`;
- the lowest low contributes the line vertex for the run when it is objectively unique; and
- other lows may appear in `suppressed` with reason `CONSECUTIVE_SAME_KIND`.

Example:

```text
all valid points:
LOW  100
HIGH 108
HIGH 110
HIGH 109
LOW  103

normalized vertices:
LOW  100
HIGH 110
LOW  103

still-valid suppressed points:
HIGH 108 -> CONSECUTIVE_SAME_KIND
HIGH 109 -> CONSECUTIVE_SAME_KIND
```

### Engineering representation

Same-kind normalization is a stable chronological run reduction over the vertex candidates, not a mutation of `points`. It mirrors the intent of the existing `replace_with_more_extreme_point()` helper, but this design does not require refactoring or reusing that helper. The implementation plan must first assess whether direct reuse preserves the required source metadata and suppression record.

## Inside-Structure Normalization

### Course-derived rule

After same-kind candidate normalization, a later same-level `HIGH`/`LOW` structural pair may be omitted from the line when its complete range is contained inside the earlier same-level structural `HIGH`/`LOW` range.

The pair orientation may be `HIGH -> LOW` or `LOW -> HIGH`. For comparison, each chronological opposite-kind pair defines:

```text
pair_high = the pair's HIGH price
pair_low  = the pair's LOW price
```

Inclusive complete containment is:

```text
later_high <= earlier_high
AND
later_low >= earlier_low
```

Both conditions are required. Equality at either boundary counts as contained, consistent with the course language and the repository's existing inclusive inside-bar convention.

When complete containment holds:

- the inner high and low remain in `ShortTermStructure.points`;
- they may be omitted from `vertices`; and
- each omitted point is recorded with reason `INSIDE_STRUCTURE`.

Example:

```text
earlier range: HIGH 110 / LOW 100
later range:   HIGH 108 / LOW 102

108 <= 110 and 102 >= 100
=> complete inside structure
=> later pair may be suppressed from the line
```

### One-side breakout prevents suppression

If either later boundary escapes the earlier range, the later pair is not completely inside:

```text
later_high > earlier_high
OR
later_low < earlier_low
```

The inside-structure rule must not suppress that pair.

Example:

```text
earlier range: HIGH 110 / LOW 100
later range:   HIGH 108 / LOW 98

108 <= 110 but 98 < 100
=> not completely inside
=> keep the later structure
```

The same rule applies in mirrored chronological orientation. Candle color, body, close, elapsed time, and subjective visual importance do not alter the two-boundary containment test.

### Pairing boundary

Inside suppression applies only when the current normalized candidate line presents an objective earlier opposite-kind range and an objective later opposite-kind range in chronology. If the available points do not define those comparable ranges unambiguously, the builder preserves them. It must not manufacture pairs, skip intervening points, or choose a preferred outer range through a nearest-point heuristic.

## Repeated and Nested Normalization

### Approved engineering application

Apply the teacher's definite inside-structure rule repeatedly from left to right until the normalized vertex sequence is stable.

Conceptually:

1. Begin with the chronologically validated points after same-kind candidate normalization.
2. Compare objectively adjacent earlier and later same-level ranges.
3. Suppress a later pair only when both inclusive containment conditions hold.
4. Continue left to right.
5. If suppression makes a new pair comparison adjacent, evaluate that comparison with the same rule.
6. Stop when a complete pass produces no further definite inside suppression.

This is not a new market rule. It is repeated application of the same explicit containment rule to the changed adjacency created by an earlier objective suppression.

Every suppressed point remains in `points`, and every suppression remains recorded. Repeated processing must be deterministic for the same valid chronological input.

## Ambiguity Policy

### Course-derived boundary

The teacher acknowledges that real charts may contain disputed or fuzzy short-term points and structure drawings. The course mentions that a human may inspect internal price behavior, new highs and lows, BMS, or SMS when reasoning about such cases.

Lesson 5 does not provide a complete deterministic algorithm for software to resolve every dispute from that evidence.

### Approved engineering policy

Automate only cases that objectively satisfy a taught rule. Otherwise preserve the valid point or candidate vertex rather than guessing.

The future implementation must not:

- suppress a point merely because it looks less important;
- introduce swing-strength scoring;
- choose a nearest point;
- introduce minimum movement, percentage, ATR, candle-count, or distance thresholds;
- invoke BMS or SMS automatically to delete or reclassify disputed points;
- infer a discretionary internal price path from OHLC; or
- create a fallback hierarchy rule.

Preserving an ambiguous case is intentional conservative behavior, not a failed classification. Later course material may authorize a separate deterministic resolution rule.

## Relationship to Existing Lessons

### Chapter 1 isolated points

Existing strict and supported deformation-aware recognition remain the single source of truth. Lesson 5 consumes confirmed results and does not alter Chapter 1 potential, confirmation, tracking, inside-bar, deformation, or recognition-basis behavior.

Lesson 5 changes only the architectural interpretation of a confirmed isolated point: it can now serve as a short-term structural point.

### Lesson 1 market state

`MarketSegment`, `StructurePoint`, and `classify_market_state()` remain explicit. Short-term recognition does not make the entire chart one implicit segment and does not automatically classify a trend.

A future caller may explicitly adapt selected short-term points into Lesson 1 `StructurePoint`s for an explicit segment only when the implementation design defines that composition. Lesson 5 does not silently run market-state classification as part of line normalization.

### Lesson 2 BMS

`PullbackContext` and `evaluate_bms()` remain unchanged and explicit. Lesson 5 does not derive a BMS context from every short-term line, select BMS boundaries automatically, or propagate a BMS across structural levels.

### Lesson 3 SMS

`SMSContext` and `evaluate_sms()` remain unchanged and explicit. Lesson 5 does not choose creator points or trend extremes from the short-term line. A short-term SMS does not automatically become medium-term or long-term SMS.

### Lesson 4 period and level

Period remains distinct from structural level. Short-term, medium-term, and long-term remain relative scale descriptions rather than fixed timeframe assignments. No timeframe ladder is introduced.

## Data Flow

### Recognition-to-structure composition

The future focused integration path is:

```text
ordered candles
        |
        +--> existing strict recognition
        |        -> confirmed IsolatedPoint
        |
        +--> existing deformation-aware recognition
                 -> IsolatedPointRecognition with basis
        |
        v
short-term point mapping
        -> preserves index, kind, price, and available basis/source
        |
        v
strict chronology validation
        |
        v
same-kind candidate normalization
        |
        v
repeated definite inside-structure normalization
        |
        v
ShortTermStructure
        - points: all confirmed short-term points
        - vertices: normalized line points
        - suppressed: omitted valid points and reasons
```

Potential isolated points and unconfirmed deformation candidates do not enter this flow as short-term points.

## Error Handling

The future implementation must distinguish malformed input from neutral or unresolved structure:

| Condition | Required behavior |
| --- | --- |
| Mapping receives an unconfirmed potential | Reject or exclude through an explicit confirmed-only boundary; never promote silently |
| Point indexes decrease | Raise an explicit chronology error |
| Point indexes repeat | Raise an explicit duplicate-index error |
| Input is empty | Return an empty neutral structure |
| Input contains one valid point | Preserve it as one point and one vertex |
| Input contains a definite same-kind run | Apply objective more-extreme normalization and record suppressions |
| Later pair is completely inside on both boundaries | Suppress it from vertices and record `INSIDE_STRUCTURE` |
| Either later boundary breaks outside | Preserve the later structure |
| Case lacks a precise operational rule | Preserve it; do not guess |

The builder must validate before normalization. It must not silently sort, repair, synthesize, or relabel input.

Exact exception classes, messages, and public function names belong to the later implementation plan, but malformed chronology must be observable to callers.

## Testing Strategy

No tests are created during this design-only task. The later implementation plan must use red-to-green test-driven development.

### Unit tests

The plan must cover at least:

1. strict isolated `HIGH` mapping to short-term `HIGH`;
2. strict isolated `LOW` mapping to short-term `LOW`;
3. supported deformation recognition mapping to a valid short-term point;
4. recognition basis or source retained where available;
5. a potential isolated point not being promoted;
6. chronological alternating points remaining unchanged;
7. a consecutive `HIGH` run retaining the highest high as the objective vertex;
8. a consecutive `LOW` run retaining the lowest low as the objective vertex;
9. same-kind suppressed points remaining in the all-points collection;
10. a complete inside `HIGH`/`LOW` range being suppressed from vertices;
11. equality at either inside boundary counting as contained;
12. contained high with a lower-low breakout being preserved;
13. contained low with a higher-high breakout being preserved;
14. mirrored `HIGH -> LOW` and `LOW -> HIGH` inside cases;
15. repeated or nested definite inside structures normalizing until stable;
16. ambiguous or non-rule cases being preserved;
17. decreasing chronology raising an error;
18. duplicate indexes raising an error;
19. proof that input is not silently sorted;
20. neutral empty input;
21. neutral one-point input;
22. neutral two-point input with same-kind normalization as objectively applicable; and
23. no implicit trend classification or cross-level propagation.

Equal-price same-kind runs must receive an explicit test consistent with the conservative ambiguity policy or with a separately approved deterministic representation chosen in the implementation plan.

### Focused cross-layer integration

The implementation plan must include focused tests proving:

```text
candles
        -> existing strict/deformation-aware recognition
        -> short-term points
        -> short-term structure
```

These tests verify that the Chapter 1 isolated-point layer composes with the Lesson 5 layer without duplicate candle-pattern logic. They must include strict recognition and the already-supported right-inside-bar deformation.

Integration tests must not infer medium-term or long-term structure, automatically build BMS/SMS contexts, or claim a trend solely from the normalized short-term line.

## Formal Chapter 2 Validation Status

Formal Chapter 2 Level 2 course-scenario validation remains deferred until all Chapter 2 lessons are complete. Lesson 5 must not create:

```text
tests/test_course_market_structure_scenarios.py
```

Lesson 6 still needs to define medium-term and long-term structure, so the hierarchy is incomplete. The formal suite must not be used to freeze guessed hierarchy behavior before that lesson is understood.

## Deferred Behavior and Non-Goals

Lesson 5 does not implement or authorize by assumption:

- medium-term structure identification;
- long-term structure identification;
- a generic cross-level hierarchy;
- timeframe-to-level mapping;
- fixed 1-hour/4-hour/daily structural assignments;
- automatic parent/child structure discovery;
- a production short/medium/long enum;
- automatic creator-point selection by structural level;
- automatic trend-extreme selection by structural level;
- automatic BMS or SMS propagation between levels;
- BMS/SMS-based ambiguity resolution without a taught algorithm;
- new context-dependent isolated-point deformation rules;
- discretionary swing-strength scoring;
- arbitrary movement, ATR, percentage, candle-count, or distance thresholds;
- confirmation of a completed trend reversal;
- trading ranges beyond already-taught concepts;
- trading signals;
- entries or exits;
- stop losses;
- risk management;
- position sizing;
- leverage;
- broker, order, or execution logic; or
- trader-profile logic.

The design also does not require refactoring any existing Chapter 1 or Chapter 2 module.

## Future Lesson 6 Handoff

Lesson 6 is expected to teach the definitions of medium-term and long-term structure. That material is the next permitted source for cross-level identification and hierarchy rules.

Before any medium-term or long-term implementation is approved, a future specification must determine from course evidence:

- how short-term points or structures contribute to a medium-term structure;
- how medium-term structures contribute to a long-term structure;
- how relative levels are anchored without fixed timeframe assignments;
- how same-level connection is verified;
- how ambiguous cross-level candidates are preserved or resolved; and
- whether any explicit production level representation is then necessary.

Lesson 6 must not retroactively turn every short-term point into a higher-level point without an operational course rule.

## Design Invariants

Future implementation and later Chapter 2 designs must preserve these invariants:

1. Any discussed candle segment remains explicitly defined.
2. Trend and non-trend remain the broad market states; Lesson 5 line normalization does not classify them.
3. Structural levels are relative and are not fixed chart periods.
4. Only same-level highs and lows connect in one structure line.
5. A confirmed isolated `HIGH` may map to a short-term `HIGH`.
6. A confirmed isolated `LOW` may map to a short-term `LOW`.
7. Isolated points do not automatically become medium-term or long-term points.
8. Existing strict and supported deformation recognition remain the single source of truth.
9. Potential or unresolved isolated points are not silently promoted.
10. Every valid short-term point remains preserved in the all-points collection.
11. A valid short-term point need not be a final structure-line vertex.
12. Suppression from the line never deletes or invalidates the confirmed point.
13. A consecutive same-kind run uses its objectively most extreme point as the line vertex and records other definite suppressions.
14. Inside suppression requires both later boundaries to be inclusively contained.
15. A breakout on either side prevents inside suppression.
16. Repeated/nested processing is repeated application of the same definite inside rule until stable.
17. Caller chronology is authoritative, strictly increasing, and never silently sorted.
18. Ambiguous cases remain preserved when no precise course rule resolves them.
19. BMS/SMS are not automatically invoked to resolve ambiguity or propagated across levels.
20. No medium-term or long-term identification rule is invented before Lesson 6.
21. Strategy, risk, and execution behavior remain outside this layer.
22. Formal Chapter 2 Level 2 validation remains deferred until all Chapter 2 lessons are complete.
