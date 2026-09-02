# Long-Term Structure Design

**Date:** 2026-09-03

**Status:** Approved architectural checkpoint

**Scope:** Chapter 2, Lesson 7 - Long-Term Structure

## Purpose

This specification records the approved design for the project's long-term
market-structure layer. Lesson 7 applies the structural-upgrade idea taught in
Lesson 6 one level higher:

```text
short-term structure
        -> medium-term structure
        -> long-term structure
```

The project will recognize canonical long-term points from the cleaned vertices
of an already-built `MediumTermStructure`. It will not rescan candles, consume
suppressed medium points, or generalize the three explicit structural levels
into a generic recursive engine.

This document also preserves an essential distinction:

- the teacher's creator/break method is course context and optional diagnostic
  evidence; while
- the strict same-kind three-point rule is the project's deterministic
  canonical operation.

They must not be presented as the same rule.

## Design-Authority Labels

This specification separates four kinds of statements.

### A. Course concepts retained directly

These statements record what Lesson 7 teaches without assigning additional
software meaning. They include the short/medium/long hierarchy, same-level
connections, potential versus confirmed points, the Russian-doll structural
upgrade idea, the teacher's creator/break discussion, and the practical choice
to view a larger chart timeframe.

### B. Project canonical operational rules

The project has selected the strict same-kind three-point promotion rule as its
deterministic definition of canonical long-term points. The rule repeats the
operation already approved for medium structure, but its input is cleaned
medium vertices.

### C. Neutral engineering choices

These choices make canonical output deterministic without inventing market
meaning. They include immutable provenance, strict chronology validation,
separate potential and confirmed collections, earliest-point tie handling,
and repeated application of an objective complete-pair inside rule until
stable.

### D. Deferred or ambiguous course behavior

The teacher's long-term creator/break method, disputed inside-merging
standards, exact real-time availability, subjective creator selection, and
automatic cross-level hierarchy remain non-canonical, evidence-only, or
deferred.

These labels are normative for the later implementation plan and code review.

## Course Context

### Structural upgrade

Lesson 7 describes long-term structure as the same structural-upgrade idea
used in Lesson 6, applied one level higher. The hierarchy is recursive in the
course's Russian-doll sense:

```text
short-term points form short-term structure
clean short-term structure promotes medium points
clean medium structure promotes long-term points
```

This conceptual repetition does not authorize a generic recursive software
engine in Lesson 7. The project keeps explicit types and boundaries for each
level.

### Teacher creator/break method

The teacher's course method for long-term highs and lows mirrors the Lesson 6
creator/break discussion but operates on medium structure.

In an already-defined upward trend:

- a long-term high is confirmed when the medium low that created a medium high
  is broken downward; and
- a long-term low is confirmed when the most recently confirmed long-term high
  is broken upward.

The downtrend case is mirrored:

- a long-term low is confirmed when the medium high that created a medium low
  is broken upward; and
- a long-term high is confirmed when the most recently confirmed long-term low
  is broken downward.

Lesson 7 does not provide a deterministic software rule for selecting every
creator relationship or trend context. The project therefore records this
method only as optional diagnostic course evidence. It does not control
canonical recognition.

### Potential versus confirmed

Lesson 7 retains a course distinction between potential and confirmed
long-term points. In the teacher's creator/break framework, confirmation is
produced by the specified structural break relationship. For example, in an
already-defined upward trend, a potential long-term low remains potential until
the relevant recently confirmed long-term high is truly broken upward; before
that break, price may continue lower.

The course does not define that confirmation through a strict previous/middle/
next same-kind medium-point comparison. Because exact creator selection and
trend-context selection remain subjective or under-specified for deterministic
software, the teacher's potential/confirmed method remains course context and
optional diagnostic evidence.

The project separately exposes canonical potential and confirmed states. A
canonical right-edge potential exists because only its strict left same-kind
comparison is currently available. It becomes canonically confirmed only when
the immediate next same-kind cleaned medium vertex exists and the strict
three-medium-point comparison passes. This is a project operational rule, not
a claim about the teacher's literal confirmation method.

### Timeframe is not structural level

The teacher notes that traders may move to a larger chart timeframe for a
wider practical view and may use long-term structure less often. This is course
context only, not structural recognition logic.

The existing invariant remains binding:

```text
period/timeframe != structural level
```

A 5-minute, hourly, daily, or other chart may itself contain short-, medium-,
and long-term structural levels. No timeframe is inherently one structural
level.

## Scope

### Approved scope

A later Lesson 7 implementation may:

- consume an explicit `MediumTermStructure`;
- use only its cleaned `vertices` for canonical long-term recognition;
- recognize strict Long-Term Highs and Long-Term Lows;
- represent current edge potentials separately;
- preserve exact medium-point structural provenance;
- normalize confirmed long-term points by same-kind runs;
- apply the currently approved provisional complete-pair inside rule;
- preserve every confirmed point independently from final line vertices;
- attach optional, external course-method evidence without changing canonical
  output; and
- validate caller chronology and structural invariants without silent repair.

### Out-of-scope behavior

Lesson 7 does not add:

- a generic recursive short/medium/long hierarchy engine;
- long-term recognition from raw candles or lower-level point collections;
- fixed timeframe-to-level mappings;
- automatic creator or trend-context selection;
- automatic cross-level parent/child inference beyond explicit medium-to-long
  provenance;
- automatic trend-reversal decisions;
- BMS or SMS reinterpretation;
- trading signals, entries, exits, stops, or targets;
- risk management, position sizing, or leverage;
- broker, order, or execution behavior;
- machine-learning or AI inference; or
- Lesson 8 common-mistake rules or formal whole-Chapter-2 validation.

## Three Explicit Structural Levels

### Course hierarchy

The course recognizes three relative structural levels:

1. short-term;
2. medium-term; and
3. long-term.

Each level is relative to its source structure, not to a fixed chart period.

### Explicit project architecture

Lesson 7 will use dedicated long-term concepts. It must not replace the current
explicit short- and medium-term modules with a parameterized recursive engine.

The explicit dependency is:

```text
ShortTermStructure.vertices
        -> MediumTermStructure
        -> MediumTermStructure.vertices
        -> LongTermStructure
```

This keeps each lesson auditable and prevents a generic abstraction from
silently changing existing semantics.

## Same-Level Connection Invariant

A structure line connects only points of one structural level:

- short-term points connect only with short-term points;
- medium-term points connect only with medium-term points; and
- long-term points connect only with long-term points.

Medium points may provide source provenance for long-term recognition, but
medium and long points do not become mixed vertices in one line.

## Canonical Input Boundary

### Required input

Canonical long-term recognition consumes only:

```text
MediumTermStructure.vertices
```

These vertices are the cleaned output after medium same-kind normalization and
medium provisional inside normalization.

### Forbidden inputs

The long-term layer must not use:

- raw candles;
- isolated points;
- short-term points or short-term vertices directly;
- every `MediumTermStructure.points` value indiscriminately;
- `MediumTermStructure.suppressed` points as hidden neighbors; or
- a rebuilt alternative medium structure line.

A confirmed medium point suppressed from the medium line remains valid medium
evidence, but it is not a canonical long-term-recognition neighbor.

## Canonical Long-Term Point Definition

### Long-Term High

For the chronological subsequence of cleaned medium `HIGH` vertices:

```text
previous medium HIGH < middle medium HIGH > next medium HIGH
```

the middle point is a confirmed Long-Term High.

### Long-Term Low

For the chronological subsequence of cleaned medium `LOW` vertices:

```text
previous medium LOW > middle medium LOW < next medium LOW
```

the middle point is a confirmed Long-Term Low.

### Immediate same-kind neighbors

"Previous" and "next" mean the immediate previous and next cleaned medium
vertices of the same kind. Opposite-kind vertices may occur between them in
overall chronology and are not comparison neighbors for that same-kind triple.

The recognizer must never skip an intervening same-kind medium vertex to
manufacture a long-term pivot.

### Strict comparison

Both comparisons are strict. Equality on either side rejects confirmation.
No ATR, percentage, candle count, distance, movement, timeframe, trend-strength,
or discretionary swing threshold modifies the rule.

## Structural Provenance and Timing

### Required meanings

Every confirmed long-term point preserves:

```text
WHERE the long-term pivot occurred
    = pivot.pivot_index

WHICH later same-kind cleaned medium point completes the strict triple
    = confirmed_by

STRUCTURAL location of that confirming medium pivot
    = confirmed_by.pivot_index
```

An equivalent `confirmed_by_index` property may expose
`confirmed_by.pivot_index`.

### Structural provenance only

The confirming medium pivot's structural index is not necessarily the candle
index at which that medium point itself became knowable. In general:

```text
confirmed_by_index != actual known_at_index
```

`MediumTermPoint` carries its medium pivot and structural confirmer, but it does
not carry a true executable availability time. Consequently, Lesson 7 must not
invent:

- `known_at_index`;
- `confirmed_at_index`; or
- any executable real-time availability timestamp.

Actual real-time availability remains deferred until the lower layers carry
explicit confirmation/availability timing. A future backtest must not treat a
confirming medium pivot's structural index as an executable knowledge time.

### Conceptual validation

For every `LongTermPoint`:

```text
pivot.kind is confirmed_by.kind
confirmed_by.pivot_index > pivot.pivot_index
```

The later implementation must reject invalid directly constructed values
rather than silently repairing them.

## Proposed Domain Model

Exact Python names and validation messages will be locked by the implementation
plan. The preferred model mirrors Lesson 6 explicitly.

### Confirmed long-term point

```python
@dataclass(frozen=True)
class LongTermPoint:
    pivot: MediumTermPoint
    confirmed_by: MediumTermPoint

    @property
    def pivot_index(self) -> int:
        return self.pivot.pivot_index

    @property
    def confirmed_by_index(self) -> int:
        return self.confirmed_by.pivot_index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price
```

This model retains medium-level source objects instead of copying only prices
or integer indexes.

### Potential long-term point

```python
@dataclass(frozen=True)
class PotentialLongTermPoint:
    previous_same_kind: MediumTermPoint
    pivot: MediumTermPoint
```

The potential retains the current edge pivot and the immediate previous
same-kind cleaned medium vertex used for its strict left comparison.

### Suppression

The design prefers explicit concepts equivalent to:

```python
class LongTermSuppressionReason(Enum):
    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


@dataclass(frozen=True)
class SuppressedLongTermPoint:
    point: LongTermPoint
    reason: LongTermSuppressionReason
```

Suppression removes a point only from final line vertices. It never deletes
canonical confirmed evidence.

### Course evidence

The preferred explicit record is conceptually:

```python
class LongCourseRuleMatch(Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LongCourseEvidence:
    point: LongTermPoint
    course_rule_match: LongCourseRuleMatch
```

The implementation plan may reuse an existing evidence-status enum if doing so
preserves the same semantics without coupling canonical output to evidence.

### Long-term structure

```python
@dataclass(frozen=True)
class LongTermStructure:
    points: tuple[LongTermPoint, ...]
    potentials: tuple[PotentialLongTermPoint, ...]
    vertices: tuple[LongTermPoint, ...]
    suppressed: tuple[SuppressedLongTermPoint, ...]
    course_evidence: tuple[LongCourseEvidence, ...] = ()
```

The collections remain distinct:

- `points` contains every confirmed canonical long-term point in pivot
  chronology;
- `potentials` contains only eligible current-edge candidates;
- `vertices` contains confirmed points retained by long-term normalization;
- `suppressed` records confirmed points omitted from the line and why; and
- `course_evidence` contains optional external diagnostic metadata.

## Potential Long-Term Points

### Potential Long-Term High

At the current right edge, a cleaned medium `HIGH` may be a potential
Long-Term High only when:

- an immediately previous cleaned medium `HIGH` exists;
- the current high is strictly higher than that previous high; and
- no next cleaned medium `HIGH` exists yet.

### Potential Long-Term Low

The mirrored potential low requires:

- an immediately previous cleaned medium `LOW` exists;
- the current low is strictly lower than that previous low; and
- no next cleaned medium `LOW` exists yet.

### Potential boundary

Potential points:

- are separate from confirmed long-term points;
- do not enter `LongTermStructure.points`;
- do not enter `LongTermStructure.vertices`;
- become confirmed only if the later same-kind medium point completes the
  strict three-point comparison; and
- otherwise remain unconfirmed and are not promoted.

No rejected-potential market status is required by this design.

## Recognition Algorithm Boundary

For each point kind independently, the later implementation will:

1. Validate the complete cleaned medium source before producing output.
2. Read `MediumTermStructure.vertices` in caller chronology.
3. Select the subsequence of vertices with the requested kind without sorting.
4. Evaluate every consecutive triple in that same-kind subsequence.
5. Confirm the middle point only when both strict comparisons pass.
6. Store the middle medium point as `pivot` and the immediate later same-kind
   medium point as `confirmed_by`.
7. Merge confirmed long-term highs and lows back into pivot chronology.
8. Preserve eligible current-edge potentials separately.
9. Normalize only the confirmed long-term points.

The long-term module depends on the medium layer and must not reconstruct any
lower-level recognition.

## Chronology and Validation

### Source validation

Caller chronology is semantic. The future builder must:

- require cleaned medium vertex pivot indexes to be strictly increasing;
- reject duplicate or decreasing pivot indexes;
- never silently sort;
- require each medium vertex to belong to `MediumTermStructure.points`;
- reject any source value represented simultaneously as both suppressed and a
  cleaned vertex; and
- validate the complete input before recognition or output.

The builder's responsibility is long-term recognition, not repair of malformed
medium structure.

### Confirmed-point validation

A directly constructed confirmed point must satisfy:

- `pivot.kind is confirmed_by.kind`; and
- `confirmed_by.pivot_index > pivot.pivot_index`.

Canonical recognition additionally guarantees that `confirmed_by` is the
immediate next cleaned medium vertex of the same kind.

### Potential validation

A potential must use same-kind medium points in increasing pivot chronology,
and its edge pivot must be strictly more extreme than its previous same-kind
source.

### Neutral small inputs

Small valid inputs do not acquire invented market meaning:

- no cleaned medium vertices produce an empty long-term structure;
- fewer than three cleaned medium highs cannot confirm a Long-Term High;
- fewer than three cleaned medium lows cannot confirm a Long-Term Low;
- two eligible same-kind edge vertices may produce a potential only; and
- no confirmed long-term points produce empty confirmed and vertex collections.

## Long-Term Consecutive Same-Kind Normalization

After canonical recognition, consecutive confirmed points of the same kind are
normalized before inside processing.

### Consecutive highs

For one run of confirmed long-term `HIGH` points:

- retain the highest high as the line vertex;
- preserve every confirmed high in `LongTermStructure.points`; and
- record each omitted point with `CONSECUTIVE_SAME_KIND`.

### Consecutive lows

For one run of confirmed long-term `LOW` points:

- retain the lowest low as the line vertex;
- preserve every confirmed low in `LongTermStructure.points`; and
- record each omitted point with `CONSECUTIVE_SAME_KIND`.

### Equal-extreme tie

When multiple points share the exact winning price, retain the earliest pivot
as a neutral deterministic tie-break. Later tied points remain confirmed
evidence and are suppressed only from final vertices.

## Provisional Long-Term Inside Handling

### Same-level complete pairs

Inside handling operates only on long-term points after same-kind
normalization. Compare complete high-low structural pairs from left to right.
The rule works for either orientation:

- `HIGH -> LOW`; or
- `LOW -> HIGH`.

### Inclusive complete containment

A later complete pair is inside the earlier complete pair only when both
conditions hold:

```text
later_high <= earlier_high
AND
later_low >= earlier_low
```

If both conditions hold:

- the later points remain confirmed canonical evidence;
- the later pair is omitted from final long-term vertices; and
- both removed points receive `INSIDE_STRUCTURE` suppression evidence.

Equality at either boundary counts as contained. Exact touch is not a breakout.

### Breakout preservation

If either condition holds:

```text
later_high > earlier_high
OR
later_low < earlier_low
```

the later structure is not completely inside and must remain in the long-term
line under this rule. One contained side is insufficient for suppression.

### Repeated stabilization

Apply the same definite rule repeatedly from left to right until a complete
pass makes no further suppression. If one removal makes another complete pair
adjacent and that pair objectively satisfies the same containment rule, it may
also be suppressed.

Preserve any unmatched final point. Do not invent a partner or discard an
incomplete range.

### Provisional status

This rule is provisional. The course acknowledges disputed or alternative
inside-merging standards, and Lesson 7 supplies no new deterministic rule that
replaces the currently approved complete-pair operation.

The implementation must not add:

- recursive boundary replacement or range extension;
- nearest-pair matching;
- subjective chart fitting;
- trend-dependent inside handling; or
- ATR, percentage, distance, movement, or candle-count thresholds.

## Confirmed Points Versus Final Vertices

The following distinction remains mandatory:

```text
confirmed canonical long-term point
        does not necessarily imply
final long-term structure-line vertex
```

Every confirmed point stays in `LongTermStructure.points`, even when same-kind
or inside normalization omits it from `vertices`. Suppression never revokes
confirmation, deletes medium provenance, or changes `confirmed_by`.

## Teacher Creator/Break Method as Evidence

### Evidence-only boundary

The teacher's long-term creator/break method may be attached after canonical
long-term structure exists as optional diagnostic evidence with a status
equivalent to:

```text
YES | NO | UNKNOWN
```

Evidence may record whether a human-reviewed course relationship appears to
match one confirmed long-term point. It must not:

- create or remove canonical long-term points;
- promote or demote points;
- alter potentials;
- alter suppressions;
- alter final vertices;
- automatically choose creator points;
- automatically choose trend context; or
- infer a trading or reversal decision.

Attaching evidence should return an immutable result preserving every canonical
collection exactly.

## Relationship to Existing Lessons

### Chapter 1 and Lesson 5

Existing candle, isolated-point, deformation, and short-term behavior remain
unchanged. Lesson 7 does not rescan those layers.

### Lesson 1 market state

Explicit `MarketSegment` and market-state classification remain separate.
Long-term recognition does not automatically classify a market state or infer
an implicit all-history segment.

### Lesson 2 BMS and Lesson 3 SMS

Existing BMS and SMS contexts and semantics remain unchanged. Lesson 7 does not
automatically derive those contexts from long-term vertices or propagate their
results across levels.

### Lesson 4 period and level

Period remains distinct from structural level. Moving to a larger timeframe is
a viewing choice, not the definition of a long-term point.

### Lesson 6 medium structure

`MediumTermStructure.vertices` is the sole canonical lower-level boundary.
Lesson 7 consumes it without changing medium points, potentials, suppressions,
course evidence, normalization, or structural provenance.

## Data Flow

The complete approved hierarchy is:

```text
raw candles
        |
        v
existing strict/deformation-aware isolated-point recognition
        |
        v
confirmed short-term points
        |
        v
short-term same-kind and inside normalization
        |
        v
ShortTermStructure.vertices
        |
        v
strict same-kind three-point promotion
        |
        v
confirmed medium points + separate medium potentials
        |
        v
medium same-kind normalization
        |
        v
medium provisional inside normalization
        |
        v
MediumTermStructure.vertices
        |
        v
strict same-kind three-point promotion again
        |
        +--> confirmed long-term points with pivot + confirmed_by provenance
        +--> separate long-term edge potentials
        +--> optional evidence-only course metadata
        |
        v
long-term same-kind normalization
        |
        v
long-term provisional inside normalization
        |
        v
LongTermStructure
        - points: all confirmed canonical long-term points
        - vertices: normalized long-term line
        - suppressed: omitted confirmed points and reasons
        - potentials/evidence: separate non-canonical information
```

No arrow bypasses cleaned `MediumTermStructure.vertices` to rescan lower-level
data.

## Error Handling

The future implementation should fail explicitly for malformed semantic input:

| Condition | Required behavior |
| --- | --- |
| Medium vertex pivot indexes decrease or repeat | Raise `ValueError`; do not sort |
| A medium vertex is absent from medium `points` | Raise `ValueError` |
| A suppressed medium point is also a source vertex | Raise `ValueError` |
| `LongTermPoint` source kinds differ | Raise `ValueError` |
| `confirmed_by` is not later than `pivot` | Raise `ValueError` |
| Potential sources differ in kind | Raise `ValueError` |
| Potential chronology is invalid | Raise `ValueError` |
| Potential edge is not strictly more extreme | Raise `ValueError` |
| Fewer than three same-kind vertices exist | Confirm no point of that kind |
| A strict comparison contains equality | Do not confirm the middle point |
| A potential fails its later comparison | Do not promote it |
| Optional evidence references no confirmed point | Raise an explicit error |
| No confirmed long-term points exist | Return neutral empty canonical collections |

No error path may fabricate a point, reorder caller input, or reinterpret an
ambiguous course example.

## Testing Strategy for the Future Plan

No tests are created during this design checkpoint. The later implementation
plan must use red-to-green test-driven development.

### Focused unit coverage

Future tests must cover at least:

1. strict Long-Term High recognition;
2. strict Long-Term Low recognition;
3. equality rejection on either side for both kinds;
4. immediate previous and next cleaned medium neighbors of the same kind;
5. refusal to skip an intervening same-kind medium point;
6. potential Long-Term High;
7. potential Long-Term Low;
8. potential becoming confirmed only after a passing later comparison;
9. failed potential not being promoted;
10. confirmed output ordered by pivot chronology;
11. exact `pivot` and `confirmed_by` medium-point provenance;
12. `confirmed_by_index` exposing structural location only;
13. no `known_at_index` or executable availability time being invented;
14. invalid confirming-source kind;
15. invalid confirming-source order;
16. invalid or duplicate input chronology and proof that input is not sorted;
17. consecutive long-term highs retaining the highest;
18. consecutive long-term lows retaining the lowest;
19. equal winning extremes retaining the earliest pivot;
20. all confirmed points remaining in `points` after same-kind suppression;
21. complete-pair inclusive inside handling in both orientations;
22. equality at either inside boundary counting as contained;
23. one-side breakout preserving the later structure;
24. repeated inside handling stabilizing;
25. unmatched final points being preserved; and
26. course evidence leaving every canonical collection unchanged.

### Focused cross-layer integration

Integration tests must use real outputs to prove:

```text
raw candles
        -> existing isolated/deformation recognition
        -> ShortTermStructure
        -> cleaned ShortTermStructure.vertices
        -> MediumTermStructure
        -> cleaned MediumTermStructure.vertices
        -> LongTermStructure
```

At least one scenario must demonstrate that:

- real medium outputs, rather than a hand-waved generic point sequence, reach
  the long-term layer;
- a confirmed medium point suppressed from `MediumTermStructure.vertices`
  remains in medium `points` but is not a long-term-recognition neighbor;
- exact medium `pivot` and `confirmed_by` provenance survives long-term
  promotion as source objects; and
- external course evidence remains passive.

Fixtures must be discriminating: a prohibited implementation that scans all
medium points must produce a different result and fail the integration test.

### Regression coverage

The future plan must run all existing Chapter 1 and Chapter 2 Lessons 1-6
tests, plus the complete repository suite.

## Formal Chapter 2 Validation Status

Do not create:

```text
tests/test_course_market_structure_scenarios.py
```

Formal Chapter 2 Level-2 course-scenario validation remains deferred. Lesson 8
explicitly covers common mistakes across Lessons 5-7, so whole-Chapter-2
validation must wait until Lesson 8 is understood and incorporated.

This deferral does not weaken focused Lesson 7 unit, integration, or regression
requirements.

## Ambiguity Policy

When course material is disputed or not operationally precise:

- preserve the ambiguity;
- use `UNKNOWN` or absent diagnostic evidence where appropriate;
- do not alter canonical output to match a subjective drawing;
- do not invent creator selection, hierarchy, timing, or thresholds; and
- document any later approved engineering choice explicitly.

The strict same-kind three-point rule remains deterministic even when optional
creator/break evidence is unknown.

## Deferred Behavior and Non-Goals

Lesson 7 must not implement or authorize by assumption:

- a generic recursive hierarchy abstraction;
- arbitrary levels beyond explicit short, medium, and long concepts;
- timeframe-to-structural-level mapping;
- recursive parent/child inference;
- automatic creator-point or trend-context selection;
- automatic BMS/SMS propagation or reinterpretation;
- automatic trend or reversal decisions;
- non-provisional subjective inside merging;
- long-term trading signals;
- entries or exits;
- stop losses or profit targets;
- risk management;
- position sizing or leverage;
- broker, order, or execution logic;
- machine-learning or AI inference;
- trader-profile logic;
- Lesson 8 common-mistake behavior; or
- formal whole-Chapter-2 Level-2 validation.

## Future Lesson 8 Handoff

Lesson 8 is expected to address common mistakes across the short-, medium-, and
long-term structure lessons. Before formal Chapter 2 validation, Lesson 8 must
clarify whether any taught mistake changes:

- same-level connection interpretation;
- lower-level source boundaries;
- potential versus confirmed handling;
- disputed inside-merging practices;
- structural provenance presentation; or
- the distinction between structural level and chart timeframe.

Lesson 8 must not retroactively change canonical Lessons 5-7 output without an
explicitly approved design revision.

## Design Invariants

Future implementation, plans, and reviews must preserve these invariants:

1. Period/timeframe remains different from structural level.
2. Short-, medium-, and long-term remain explicit project concepts.
3. Lesson 7 does not introduce a generic recursive hierarchy engine.
4. Long-term recognition consumes an explicit `MediumTermStructure`.
5. Only `MediumTermStructure.vertices` are canonical recognition neighbors.
6. Medium `points` and suppressed medium points are not hidden long-term
   neighbors.
7. Canonical Long-Term Highs use strict `previous < middle > next` comparisons
   among immediate same-kind cleaned medium vertices.
8. Canonical Long-Term Lows use strict `previous > middle < next` comparisons
   among immediate same-kind cleaned medium vertices.
9. The recognizer never skips an intervening same-kind medium vertex.
10. Equality on either side rejects confirmation.
11. A potential long-term point is not confirmed canonical output.
12. Every confirmed point preserves exact `pivot` and `confirmed_by`
    `MediumTermPoint` objects.
13. `pivot_index` identifies the medium pivot's structural location.
14. `confirmed_by_index` identifies the confirming medium pivot's structural
    location only.
15. `confirmed_by_index` is not an executable knowledge timestamp.
16. Actual `known_at_index` remains unavailable and must not be inferred.
17. Confirmed long-term points are ordered by pivot chronology.
18. Every confirmed point remains in `LongTermStructure.points` independently
    from final vertices.
19. Suppression from vertices never revokes canonical confirmation.
20. Consecutive long-term highs retain the highest high.
21. Consecutive long-term lows retain the lowest low.
22. Equal-extreme ties retain the earliest pivot.
23. Long-term inside handling compares same-level complete pairs only.
24. Inside suppression requires both later boundaries to be inclusively
    contained.
25. A breakout on either boundary prevents inside suppression.
26. Exact boundary contact remains contained rather than being a breakout.
27. Repeated inside handling applies only the same definite provisional rule
    until stable.
28. Unmatched final points are preserved.
29. The teacher's creator/break method remains optional diagnostic evidence.
30. Course evidence cannot change points, potentials, vertices, suppressions,
    or structural provenance.
31. Caller chronology is authoritative and is never silently sorted.
32. No raw-candle or lower-level rescan bypasses the medium boundary.
33. No timeframe mapping, BMS/SMS reinterpretation, market-state inference,
    strategy, risk, or execution behavior is introduced.
34. Lesson 8 is not implemented by this design.
35. Formal Chapter 2 Level-2 validation remains deferred until Lesson 8 is
    understood and incorporated.
