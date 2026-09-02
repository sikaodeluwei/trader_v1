# Medium-Term Structure Design

**Date:** 2026-09-02

**Status:** Approved architectural checkpoint

**Scope:** Chapter 2, Lesson 6 - Medium-Term / Intermediate Structure

## Purpose

This specification records the approved Chapter 2, Lesson 6 design for a
medium-term structural layer above the cleaned short-term structure. It defines
how the project will recognize canonical Intermediate-Term Highs (`ITH`) and
Intermediate-Term Lows (`ITL`), preserve the later same-kind short-term point
that structurally confirms each pivot, and normalize confirmed medium points
into a medium-level structure line. Exact real-time knowability remains
unavailable until the lower short-term layer carries its own availability
timing.

The approved flow is:

```text
raw candles
        |
        v
confirmed short-term points
        |
        v
short-term consecutive-same-kind normalization
        |
        v
short-term inside-structure normalization
        |
        v
clean short-term vertices
        |
        v
intermediate/medium point recognition
        |
        v
medium consecutive-same-kind normalization
        |
        v
medium inside-structure normalization
        |
        v
final medium structure vertices
```

This is a design-spec checkpoint only. It adds no production API, tests,
implementation plan, market-state decision, strategy, or execution behavior.

## Design-Authority Labels

This specification keeps four kinds of statements separate:

### A. Course concepts retained directly

These are concepts taught by the course and retained without assigning them
additional software meaning. Examples include relative structural levels,
same-level connections, the distinction between a pivot and its later
structural confirming point, and the teacher's break-based medium-structure
discussion.

### B. Project canonical operational definition

The project has intentionally selected the strict ITH/ITL same-kind-neighbor
rule as its deterministic definition of canonical medium points. This is an
approved project decision. It must not be presented as identical to the
teacher's custom break-based method.

### C. Neutral engineering choices

These choices make the deterministic rule representable without inventing
market meaning. They include preserving immutable evidence, ordering confirmed
points by pivot location, retaining the earliest equal extreme during
same-kind cleanup, validating chronology without sorting, and repeatedly
applying an objective inside rule until stable.

### D. Deferred or ambiguous course behavior

The teacher's creator/break method, long-term recognition, cross-level
propagation, and disputed chart interpretations are not precise enough in this
lesson to control deterministic production behavior. They remain explicitly
deferred or evidence-only.

These labels are normative. Future implementation and documentation must not
blur them.

## Course Context

### Course concepts retained directly (A)

Lesson 6 continues the course's relative structural hierarchy above the
short-term structure introduced in Lesson 5. Medium/intermediate structure is a
structural level, not a chart period.

The existing invariant remains binding:

```text
period/timeframe != structural level
```

Consequently:

- no chart period is inherently short-term, medium-term, or long-term;
- no 1-hour/4-hour/daily hierarchy is authorized;
- a medium structure must be derived from the lower-level structural line,
  not from a hard-coded timeframe; and
- Lesson 6 remains a market-structure lesson, not a complete reversal or
  trading system.

BMS and SMS keep their existing explicit context and semantics. Neither is
reinterpreted automatically because a medium layer now exists.

## Scope

### Approved scope

A later implementation may add a focused medium-term layer that:

- consumes the cleaned vertices produced by the existing short-term layer;
- recognizes confirmed ITH/ITL points through the approved strict
  same-kind-neighbor rule;
- optionally exposes the current unconfirmed edge candidate without treating
  it as known history;
- preserves both pivot location and the later same-kind short-term point that
  structurally confirms it;
- preserves all confirmed medium points independently from final line
  vertices;
- records objective same-kind and inside-structure suppressions;
- retains the teacher's break-based method only as optional diagnostic
  evidence; and
- validates semantic chronology without silently sorting or reconstructing
  another short-term line.

### Out-of-scope behavior

This lesson does not add:

- trading signals;
- entries or exits;
- position sizing;
- risk management;
- broker or order execution;
- automatic reversal decisions;
- fixed timeframe-to-level mappings;
- long-term recognition; or
- machine-learning or AI inference.

## Structural Levels and Same-Level Connections

### Course concepts retained directly (A)

Short-term, medium-term, and long-term are relative structural levels. Only
points belonging to one level may form that level's structure line:

- cleaned short-term vertices form the short-term line;
- confirmed medium points form the medium line;
- short-term and medium vertices must not be mixed into one line; and
- long-term structure must not be inferred automatically in Lesson 6.

The medium layer may retain a reference to the short-term vertex from which a
medium point was recognized. That provenance does not make the short-term
vertex and medium point interchangeable in a line.

## Input Boundary

### Project operational boundary (B)

Canonical medium recognition consumes only the cleaned short-term vertices
owned by the Lesson 5 layer. In the existing architecture, this means the
`vertices` of a `ShortTermStructure`, not its complete `points` collection and
not its `suppressed` collection.

The medium recognizer must not:

- rescan raw candles;
- duplicate strict isolated-point recognition;
- duplicate deformation-aware isolated-point recognition;
- promote a suppressed short-term point as though it were a cleaned vertex;
- reconstruct a different short-term line from all recognized points;
- change any Lesson 5 suppression reason; or
- silently apply a competing short-term normalization algorithm.

The existing short-term layer remains the single owner of short-term
recognition and normalization. Its `points` and `suppressed` evidence remain
available to callers for audit, but they are not canonical inputs to medium
recognition.

## Canonical Medium-Point Definition

### Project canonical operational definition (B)

The project's canonical medium-point rule is the deterministic strict
ITH/ITL same-kind-neighbor rule.

For cleaned short-term `HIGH` vertices:

```text
previous STH price < middle STH price > next STH price
```

The middle short-term high is a confirmed Intermediate-Term High (`ITH`) or
medium-term high.

For cleaned short-term `LOW` vertices:

```text
previous STL price > middle STL price < next STL price
```

The middle short-term low is a confirmed Intermediate-Term Low (`ITL`) or
medium-term low.

"Previous" and "next" mean the previous and next cleaned short-term point of
the same kind. They do not mean the immediately adjacent vertex of any kind.
An intervening opposite-kind short-term vertex remains part of the source line
but is not a comparison neighbor for this rule.

### Strict comparison

Both comparisons are strict. Equality on either side prevents confirmation.

Examples:

```text
cleaned STH prices: 105, 112, 108
105 < 112 > 108
=> 112 is a confirmed ITH

cleaned STH prices: 105, 112, 112
105 < 112 but 112 is not greater than 112
=> the middle 112 is not an ITH

cleaned STL prices: 100, 94, 98
100 > 94 < 98
=> 94 is a confirmed ITL

cleaned STL prices: 100, 94, 94
100 > 94 but 94 is not less than 94
=> the middle 94 is not an ITL
```

No percentage, ATR, distance, candle-count, or swing-strength threshold may
modify the strict rule.

## Potential and Confirmed Recognition

### Course concept retained directly (A)

The point at which a structural pivot occurred and the later point at which
enough right-side evidence existed to confirm it are different events.

Example:

```text
STH1 = 105
STH2 = 112
```

Before another cleaned short-term high exists, STH2 cannot be confirmed as an
ITH. It may be represented as the current potential ITH candidate because it
already satisfies the available strict left comparison.

Later:

```text
STH3 = 108

112 > 105
AND
112 > 108
```

STH2 is now a confirmed ITH. The confirmed point remains located at STH2's
original pivot index, while STH3 is retained as the right-side same-kind
short-term point that structurally confirms the comparison. STH3's pivot index
does not reveal when STH3 itself became knowable.

The same rule is mirrored for potential and confirmed ITLs.

### Neutral edge-candidate representation (C)

If the future API exposes potential candidates, the current right-edge
same-kind point may be represented as potential only when:

- a previous cleaned short-term point of the same kind exists;
- the edge point passes the strict available left comparison; and
- no next cleaned short-term point of that kind yet exists.

Such a candidate is not a confirmed medium point and must not enter the
confirmed-points or final-vertices collections. When the next same-kind point
arrives:

- passing the strict right comparison promotes the pivot into a confirmed
  medium point; or
- failing the strict right comparison leaves it unconfirmed and it is not
  added to canonical medium structure.

The exact potential type, status representation, and whether failed candidate
history is retained are implementation-plan decisions. No rejected candidate
may be presented as a confirmed medium point.

### Structural availability boundary and deferred real-time timing

A confirmed ITH/ITL structurally depends on its next same-kind cleaned
short-term point. The medium layer must retain that exact source point and must
not represent the middle pivot as confirmed without it.

The current `ShortTermPoint` model contains a pivot index but no
`known_at_index` or `confirmed_at_index`. Therefore the medium layer cannot
truthfully expose the candle index when its right-side short-term dependency
became knowable. A future backtest must not treat the dependency's pivot index
as an executable knowledge timestamp. Exact real-time availability is deferred
until the lower short-term layer explicitly carries that timing.

## Pivot and Structural Confirmation Chronology

### Required semantics (A and C)

Every confirmed medium point must preserve two structural meanings while
leaving actual real-time knowability explicit as unavailable:

```text
WHERE the structural point is                   = pivot.index
WHICH later same-kind point confirms the triple = confirmed_by.index
WHEN confirmed_by itself became knowable        = unavailable / deferred
```

In general:

```text
pivot_index != confirmed_by_index
confirmed_by_index > pivot_index
```

`confirmed_by` is the next cleaned short-term point of the same kind that
completes the strict three-point comparison. `confirmed_by_index` is that
point's structural pivot index, not the index of an arbitrary adjacent
opposite-kind vertex and not the candle index when `confirmed_by` became
knowable.

In general, `confirmed_by_index != actual known_at_index`. The latter is not
represented by the current lower-layer API and must not be inferred.

Canonical confirmed medium points are ordered in the structure by pivot
location, not by their right-side dependency indexes. Normalization likewise
follows pivot chronology. Structural confirmation provenance must not
reposition a point.

The implementation must not assume that `confirmed_by_index` values across
mixed medium-high and medium-low streams are themselves the line order. Pivot
order is authoritative for the medium structure line.

## Proposed Domain Model

The exact Python names and public function signatures remain implementation-
plan decisions. The future model must preserve the following concepts.

### Confirmed medium point

Conceptually:

```python
@dataclass(frozen=True)
class MediumTermPoint:
    pivot: ShortTermPoint
    confirmed_by: ShortTermPoint

    @property
    def pivot_index(self) -> int: ...

    @property
    def confirmed_by_index(self) -> int: ...

    @property
    def kind(self) -> IsolatedPointKind: ...

    @property
    def price(self) -> float: ...
```

Required meaning:

- `pivot` identifies the cleaned short-term vertex recognized as the medium
  pivot;
- `confirmed_by` identifies the immediate next cleaned short-term vertex of
  the same kind that completes the strict triple;
- `kind` remains `HIGH` or `LOW`;
- `price` is the pivot's price;
- `pivot_index` is the original short-term pivot location; and
- `confirmed_by_index` is `confirmed_by.index`, structural source information
  rather than actual real-time knowability.

Required validation is:

- `pivot.kind is confirmed_by.kind`; and
- `confirmed_by.index > pivot.index`.

No `known_at_index` is invented. `confirmed_by_index` must not be documented or
consumed as the candle time when the medium point became executable knowledge.

An implementation may avoid storing duplicated fields if equivalent immutable
properties preserve all meanings unambiguously.

### Potential medium candidate

A conceptual potential record may retain:

- the current edge pivot;
- its kind and price;
- the previous same-kind cleaned short-term point used for its available left
  comparison; and
- an explicit potential/unconfirmed state.

Potential candidates are separate from confirmed medium points.

### Suppression reason

The medium layer requires suppression meanings equivalent to:

```text
CONSECUTIVE_SAME_KIND
INSIDE_STRUCTURE
```

Exact enum and record names belong to the implementation plan. A suppression
record must identify the confirmed medium point omitted from final vertices
and the objective reason.

### Medium-term structure

Conceptually:

```python
@dataclass(frozen=True)
class MediumTermStructure:
    points: tuple[MediumTermPoint, ...]
    potentials: tuple[PotentialMediumTermPoint, ...]
    vertices: tuple[MediumTermPoint, ...]
    suppressed: tuple[SuppressedMediumTermPoint, ...]
    course_evidence: tuple[MediumCourseEvidence, ...]
```

Required semantic distinctions:

- `points` contains all confirmed canonical medium points in pivot chronology;
- `potentials`, if exposed, contains only current unconfirmed edge candidates;
- `vertices` contains confirmed medium points retained after normalization;
- `suppressed` records confirmed points omitted from the line and why;
- `course_evidence`, if implemented, is diagnostic metadata only; and
- no normalization step deletes confirmed evidence from `points`.

Optional concepts need not become empty public fields if the implementation
plan determines a smaller API is clearer. Their semantics must not be folded
into confirmed canonical output in a misleading way.

## Recognition Algorithm Boundary

### Project canonical operation (B)

For each point kind independently:

1. Read cleaned short-term vertices in caller chronology.
2. Select the subsequence of vertices with that kind without reordering it.
3. Evaluate each chronological triple of same-kind points.
4. Confirm the middle point only when both strict comparisons pass.
5. Record the middle point as `pivot` and the immediate later same-kind neighbor
   as `confirmed_by`.
6. Merge confirmed highs and lows back into one sequence ordered by pivot
   chronology.
7. Preserve any eligible current right-edge potential separately from
   confirmed points.

The recognizer must not skip a same-kind neighbor to manufacture a pivot. If
the immediately previous or next cleaned short-term point of that kind causes
the strict test to fail, that middle point is not canonically confirmed.

## Chronology and Validation

### Input validation (C)

The future medium recognizer must treat caller chronology as semantic:

- source short-term vertex indexes must be strictly increasing;
- duplicate vertex indexes are invalid;
- decreasing or repeated indexes raise an explicit error;
- the recognizer must not silently sort;
- the recognizer must not silently remove a vertex to make a triple pass;
- source vertices must come from the cleaned short-term structure boundary;
  and
- the complete input must be validated before recognition or terminal output.

If the future public API accepts a `ShortTermStructure`, it may validate the
relevant structure invariants directly. If it accepts a dedicated cleaned-
vertices value, that value must still make its Lesson 5 origin explicit. A
bare unlabeled sequence that could be raw isolated points must not blur the
boundary.

### Confirmed-point validation (C)

For every confirmed medium point:

- `pivot` and `confirmed_by` must refer to supplied cleaned short-term vertices;
- `pivot.kind` and `confirmed_by.kind` must match;
- `confirmed_by` must be the next same-kind source vertex;
- `confirmed_by.index` must be later than `pivot.index`; and
- confirmed points must be stored in strictly increasing pivot chronology.

No silent repair, synthetic point, or alternative source chronology is
authorized.

### Neutral small-input behavior

Small valid inputs do not acquire invented market meaning:

- fewer than three cleaned short-term highs cannot confirm an ITH;
- fewer than three cleaned short-term lows cannot confirm an ITL;
- an eligible right-edge point may remain potential if the API exposes
  potentials;
- no confirmed medium points produce an empty medium line; and
- small outputs must not be labeled trend, non-trend, or reversal by this
  lesson.

## Medium Consecutive Same-Kind Normalization

### Course-compatible structure rule (A)

After canonical confirmed medium points are merged into pivot chronology,
consecutive points of the same kind do not require artificial line turns.

For consecutive confirmed medium `HIGH` points without an intervening retained
medium `LOW`:

- preserve every confirmed high in the all-points collection;
- retain the highest high as the line representative; and
- suppress the other highs only from final vertices with reason
  `CONSECUTIVE_SAME_KIND`.

For consecutive confirmed medium `LOW` points:

- preserve every confirmed low;
- retain the lowest low as the line representative; and
- suppress the other lows only from final vertices with the same reason.

### Equal-extreme tie-break (C)

The course does not define temporal precedence for exact equal extremes. The
approved neutral engineering tie-break mirrors Lesson 5:

- equal highest medium highs retain the earliest pivot as the vertex;
- equal lowest medium lows retain the earliest pivot as the vertex;
- later tied points remain confirmed in the all-points collection; and
- later tied points are suppressed only from vertices with reason
  `CONSECUTIVE_SAME_KIND`.

This is an engineering tie-break, not a market-course rule.

## Provisional Medium Inside-Structure Normalization

### Provisional course-compatible rule (D)

After same-kind normalization, compare an earlier complete medium high/low
range with a later complete medium high/low range.

For each complete opposite-kind pair, define:

```text
pair_high = the pair's medium HIGH price
pair_low  = the pair's medium LOW price
```

The later range is inside only when both inclusive conditions hold:

```text
later_high <= earlier_high
AND
later_low >= earlier_low
```

Equality counts as contained.

When complete containment holds:

- the later high and low remain valid confirmed medium points;
- both may be omitted from final medium vertices; and
- both suppressions are recorded with reason `INSIDE_STRUCTURE`.

If either boundary breaks outside:

```text
later_high > earlier_high
OR
later_low < earlier_low
```

the later complete range is not inside, and this rule must not suppress it.

The rule applies in both chronological pair orientations: `HIGH -> LOW` and
`LOW -> HIGH`. An incomplete later range is preserved because it does not
provide both boundaries required for objective containment.

This rule is explicitly provisional and subject to revision if later course
material supplies a clearer operational definition.

### Repeated and nested application (C)

Apply only the definite two-boundary rule repeatedly from left to right until
the normalized vertex sequence is stable:

1. Start with medium points after same-kind normalization.
2. Compare objectively adjacent complete ranges.
3. Suppress a later pair only when both inclusive conditions hold.
4. Continue left to right.
5. If suppression creates a new objective adjacency, apply the same rule.
6. Stop when a full pass produces no further definite suppression.

This is repeated application of one approved provisional rule, not a recursive
trend rule. It does not authorize range extension, boundary replacement,
nearest-pair selection, or discretionary suppression to reproduce every line
in a teacher illustration.

## Recognized Points Versus Final Vertices

### Architectural invariant (C)

The Lesson 5 separation remains mandatory at medium level:

```text
confirmed medium point
        does not necessarily imply
final medium structure-line vertex
```

The model must keep distinct:

- all confirmed canonical medium points;
- current potential edge candidates where the chosen API exposes them;
- normalized final medium vertices;
- suppressed confirmed points and suppression reasons;
- pivot and structural confirming-source information; and
- optional course-method evidence.

Suppression from the medium line never revokes canonical confirmation, deletes
the source short-term pivot, or changes its `confirmed_by` source.

## Course Break Method as Evidence

### Course concepts retained directly (A)

The teacher describes creator/break relationships such as:

- in a defined uptrend, a short-term low associated with creation of a
  short-term high may become relevant when that low is broken;
- medium points may later receive evidence from breaks of established medium
  boundaries; and
- mirrored reasoning applies in a downtrend.

This material must not be silently discarded. However, Lesson 6 does not
define creator selection, applicable context, break sequencing, and every
mirrored case precisely enough for this custom method to determine canonical
software output.

### Evidence-only boundary (D)

The future architecture may record optional diagnostic metadata such as:

- creator point;
- creator-boundary break occurrence or index;
- previous-medium-boundary break occurrence or index; and
- `course_rule_match = YES | NO | UNKNOWN` or equivalent.

Exact fields and whether this evidence belongs in the first medium-layer
implementation are implementation-plan decisions.

The critical invariant is:

```text
course evidence must not promote, demote, create, remove, or reposition a
canonical ITH/ITL
```

Canonical medium structure is determined only by the strict same-kind-neighbor
rule. Course evidence is diagnostic metadata for later comparison. It must not
change confirmed points, vertices, suppressions, pivot indexes, or
`confirmed_by` sources.

## Ambiguity Policy

When teacher material is ambiguous:

- do not invent hidden rules;
- do not infer trading meaning;
- do not force deterministic output to match an illustrative chart when that
  would contradict the explicit canonical rule;
- preserve ambiguity or label a small neutral engineering choice;
- do not use BMS/SMS as an unapproved ambiguity resolver;
- do not introduce thresholds or discretionary swing-strength heuristics; and
- allow later lessons to revise explicitly provisional behavior.

An unresolved course-evidence result should remain `UNKNOWN` or absent rather
than altering canonical ITH/ITL recognition.

## Relationship to Existing Lessons

### Chapter 1 isolated points

Strict and supported deformation-aware isolated-point recognition remain
unchanged. Medium recognition never consumes or rescans candles and never maps
isolated points directly to medium points.

### Lesson 1 market state

`MarketSegment`, `StructurePoint`, and `classify_market_state()` remain
explicit. Medium recognition does not infer market state or make the entire
history one implicit segment.

### Lesson 2 BMS

`PullbackContext` and `evaluate_bms()` remain unchanged. The medium layer does
not automatically choose BMS boundaries, build pullback contexts, or propagate
BMS between levels.

### Lesson 3 SMS

`SMSContext` and `evaluate_sms()` remain unchanged. The medium layer does not
automatically select creator points or trend extremes, confirm an opposite
trend, or propagate SMS between levels.

### Lesson 4 period and level

Period remains distinct from structural level. No fixed timeframe ladder is
introduced.

### Lesson 5 short-term structure

`ShortTermStructure.vertices` is the canonical lower-level input. Lesson 6
does not modify short-term recognition, normalization, suppression evidence,
or recognition basis.

## Data Flow

The future integration path is:

```text
ordered candles
        |
        v
existing strict/deformation-aware isolated-point recognition
        |
        v
confirmed ShortTermPoint values
        |
        v
build_short_term_structure(...)
        |
        +--> points and suppressed evidence remain owned by Lesson 5
        |
        v
ShortTermStructure.vertices
        |
        v
strict same-kind-neighbor ITH/ITL recognition
        |
        +--> potential edge candidate(s), if exposed
        +--> confirmed points with pivot + confirmed_by source points
        +--> optional evidence-only course metadata
        |
        v
medium same-kind normalization
        |
        v
repeated definite provisional inside normalization
        |
        v
MediumTermStructure
        - points: all confirmed canonical medium points
        - vertices: normalized medium line
        - suppressed: omitted confirmed points and reasons
        - potentials/evidence: separate non-canonical information
```

No arrow bypasses the cleaned short-term vertices to rescan raw candles or
suppressed short-term points.

## Error Handling

The later implementation must distinguish invalid input from neutral or
unconfirmed structure:

| Condition | Required behavior |
| --- | --- |
| Source vertex indexes decrease | Raise an explicit chronology error |
| Source vertex indexes repeat | Raise an explicit duplicate-index error |
| Input is not an explicit cleaned short-term source | Reject the boundary or require an explicit adapter; do not guess |
| Fewer than three same-kind source vertices exist | Confirm no point of that kind |
| Edge point passes only the available left comparison | Keep separate as potential if the API exposes potentials |
| Candidate fails the later strict comparison | Do not promote it to a confirmed medium point |
| Equality occurs on either ITH/ITL comparison | Do not confirm the middle point |
| Definite consecutive same-kind medium run exists | Retain the objective extreme vertex and record suppressions |
| Later complete range is contained on both boundaries | Suppress the pair only from vertices and record `INSIDE_STRUCTURE` |
| Either later boundary breaks outside | Preserve the later range |
| Course break evidence is absent or ambiguous | Record `UNKNOWN`/absence if modeled; do not change canonical output |
| No confirmed medium points exist | Return neutral empty confirmed/vertex collections |

The recognizer must validate the complete source before returning recognized
or normalized output. It must not silently sort, repair, synthesize, or
relabel source points.

Exact exception classes, messages, data types, and public API names belong to
the implementation plan.

## Testing Strategy

No tests are created during this design-only checkpoint. The later
implementation plan must use red-to-green test-driven development.

### Canonical recognition tests

The plan must cover at least:

1. basic strict ITH recognition;
2. basic strict ITL recognition;
3. equality on the left ITH comparison preventing confirmation;
4. equality on the right ITH comparison preventing confirmation;
5. mirrored equality rejection for ITL;
6. use of previous and next cleaned short-term points of the same kind rather
   than immediately adjacent opposite-kind vertices;
7. refusal to skip an intervening same-kind point to manufacture a pivot;
8. an eligible potential ITH before the right-side same-kind point exists;
9. an eligible potential ITL before the right-side same-kind point exists;
10. a potential becoming confirmed only when its right-side comparison passes;
11. a potential failing its right-side comparison and not entering confirmed
    output;
12. the confirmed point retaining the middle pivot's index;
13. the immediate later same-kind point being preserved as `confirmed_by`;
14. `confirmed_by_index` exposing structural source location without claiming
    actual knowability timing;
15. confirmed points ordered by pivot chronology rather than confirming-source
    chronology; and
16. no `known_at_index` being inferred from unavailable lower-layer data.

### Medium normalization tests

The plan must cover at least:

1. a consecutive medium-high run retaining the highest high;
2. a consecutive medium-low run retaining the lowest low;
3. equal highest medium highs retaining the earliest pivot;
4. equal lowest medium lows retaining the earliest pivot;
5. later equal-extreme points remaining confirmed but suppressed only from the
   line;
6. all other same-kind suppressed points remaining in the all-points
   collection;
7. complete inside medium structure suppression;
8. equality at either inside boundary counting as contained;
9. a high-side breakout preventing inside suppression;
10. a low-side breakout preventing inside suppression;
11. both `HIGH -> LOW` and `LOW -> HIGH` pair orientations;
12. an incomplete range being preserved;
13. nested or repeated definite inside ranges normalizing until stable; and
14. ambiguous layouts being preserved rather than guessed.

### Validation tests

The plan must cover:

- decreasing source chronology;
- duplicate source indexes;
- proof that source input is not silently sorted;
- neutral small inputs;
- pivot/confirmed-by invariant failures in directly constructed domain values;
  and
- separation of potential, confirmed, vertex, and suppressed collections.

### Focused cross-layer integration

The plan must prove:

```text
candles
        -> existing isolated/deformation recognition
        -> confirmed short-term points
        -> ShortTermStructure
        -> cleaned ShortTermStructure.vertices
        -> canonical medium recognition
        -> MediumTermStructure
```

At least one integration scenario must demonstrate that a valid short-term
point suppressed by Lesson 5 normalization remains in
`ShortTermStructure.points` but is not used as a canonical medium-recognition
neighbor.

Another scenario must prove that optional course-method evidence does not
change canonical ITH/ITL points, pivot locations, `confirmed_by` sources, or
normalized vertices.

## Formal Chapter 2 Validation Status

Formal Chapter 2 Level 2 course-scenario validation remains deferred until all
Chapter 2 lessons are complete. Lesson 6 must not create:

```text
tests/test_course_market_structure_scenarios.py
```

Lesson 7 still needs to define long-term structure, so the hierarchy is not
complete enough to freeze a formal cross-lesson scenario suite.

## Deferred Behavior and Non-Goals

Lesson 6 does not implement or authorize by assumption:

- long-term point recognition;
- automatic recursive long-term promotion;
- a generic automatic parent/child hierarchy;
- fixed 1-hour/4-hour/daily structural assignments;
- timeframe-to-level inference;
- direct isolated-point-to-medium-point mapping;
- rescanning candles for medium pivots;
- use of suppressed short-term points as canonical medium neighbors;
- creator-point selection from ambiguous course material;
- canonical promotion or demotion from the course break method;
- automatic BMS/SMS reinterpretation or propagation;
- market-state inference;
- trend-reversal confirmation;
- discretionary swing-strength, distance, ATR, percentage, or candle-count
  thresholds;
- trading ranges not already operationally defined;
- trading signals;
- entries or exits;
- stop losses;
- position sizing;
- leverage;
- risk management;
- strategy rules;
- execution;
- broker or API integration;
- machine-learning or AI inference; or
- trader-profile logic.

The design does not require refactoring any existing Chapter 1 or Chapter 2
module.

## Future Lesson 7 Handoff

Lesson 7 is expected to define long-term structure. Before long-term
implementation is approved, its design must determine from course evidence:

- the canonical source level for long-term recognition;
- whether the same-kind-neighbor operation repeats from cleaned medium
  vertices or whether the course supplies another deterministic rule;
- how structural confirming-point provenance carries across another level;
- how actual knowability timing should propagate once lower layers represent
  it explicitly;
- how same-level connection remains explicit;
- whether provisional inside handling remains valid; and
- whether any course break evidence becomes operationally precise.

Lesson 7 must not retroactively change canonical Lesson 6 output without an
explicitly approved design revision.

## Known Deferred Ambiguities

The following details intentionally remain unresolved at this checkpoint:

1. The exact public type and API for exposing current potential edge
   candidates.
2. Whether failed potential history is retained or simply omitted after it
   fails the strict right comparison.
3. The exact representation and collection point for optional course
   creator/break evidence.
4. A deterministic algorithm for selecting creator points and interpreting
   every teacher break-based illustration.
5. Whether later lessons revise the provisional medium inside-structure rule.
6. The long-term recognition rule and any permitted cross-level hierarchy
   representation.

These ambiguities do not affect canonical confirmed ITH/ITL recognition, which
is fully determined by the strict same-kind-neighbor rule.

## Design Invariants

Future implementation and later designs must preserve these invariants:

1. Period/timeframe remains different from structural level.
2. Medium recognition consumes cleaned short-term vertices, not raw candles.
3. Suppressed short-term points are not canonical medium-recognition inputs.
4. Existing isolated-point and short-term logic remain the single source of
   truth for their respective layers.
5. Only same-level points connect in one structure line.
6. Canonical ITH/ITL output is determined only by the strict same-kind-neighbor
   rule.
7. Previous and next mean previous and next cleaned short-term points of the
   same kind.
8. The recognizer never skips a same-kind neighbor to manufacture a pivot.
9. Equality on either side prevents canonical ITH/ITL confirmation.
10. A potential medium candidate is not a confirmed medium point.
11. A confirmed point is not exposed before its right-side same-kind evidence
    exists.
12. Every confirmed point preserves both `pivot` and `confirmed_by` structural
    provenance.
13. The pivot index determines where a medium point belongs in the line.
14. `confirmed_by_index` records the structural pivot index of the immediate
    right-side same-kind confirming point, not actual knowability time.
15. Actual `known_at_index` remains unavailable and must not be inferred until
    the short-term layer explicitly supplies it.
16. Confirmed medium points are ordered by pivot chronology.
17. Every confirmed medium point remains preserved independently from final
    vertices.
18. Suppression from the line never revokes canonical recognition.
19. Consecutive medium highs retain the highest high as line representative.
20. Consecutive medium lows retain the lowest low as line representative.
21. Equal-extreme same-kind ties retain the earliest pivot as a neutral
    engineering tie-break.
22. Medium inside suppression requires both later boundaries to be inclusively
    contained.
23. A breakout on either boundary prevents inside suppression.
24. Repeated inside handling applies only the same definite provisional rule
    until stable.
25. Course creator/break evidence is optional diagnostic metadata only.
26. Course evidence cannot change canonical points, vertices, suppressions,
    pivot indexes, or `confirmed_by` sources.
27. Caller chronology is authoritative and is never silently sorted.
28. Ambiguous course behavior is preserved or labeled, never converted into a
    hidden rule.
29. Long-term recognition remains deferred to Lesson 7.
30. No BMS/SMS reinterpretation, market-state inference, strategy, risk, or
    execution behavior is introduced.
31. Formal Chapter 2 Level 2 validation remains deferred until all Chapter 2
    lessons are complete.
