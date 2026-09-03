# Offline Market-Structure Analysis and Validation Design

**Date:** 2026-09-03

**Status:** Approved architectural checkpoint

**Scope:** Pre-Chapter-3 offline analysis and validation of Chapters 1 and 2

## Purpose

This specification defines the first offline facade that can apply everything
the project legitimately knows from Chapters 1 and 2 to a completed market-data
window. It also defines a validation system that can compare objective output
with deterministic expectations or separately prepared human/course ground
truth.

This is a composition checkpoint, not a new market-structure lesson. Existing
candle measurements, isolated-point rules, structural hierarchy builders,
market-state classification, BMS evaluation, and SMS evaluation remain the
single sources of truth. The new layer validates input, wires those definitions
together, and reports unavailable or invalid outcomes without inventing market
answers.

The validation design keeps six independently diagnosable gates:

1. **Test A:** Chapter 1 exact candle and intrabar analysis;
2. **Test B:** Chapter 1 isolated-point recognition;
3. **Test C:** pure Chapter 2 hierarchy from supplied confirmed points;
4. **Test D:** raw OHLC through the complete objective hierarchy;
5. **Test E:** explicit segment and structural-level evaluation; and
6. **Test F:** later real historical blind validation.

The specification adds no production code, implementation tests, implementation
plan, Chapter 3 behavior, trading strategy, or execution behavior.

## Design-Authority Labels

Every normative statement belongs to one of four categories.

### Course-derived rule

These are Chapter 1 or Chapter 2 rules already represented by the existing
definitions. Examples include candle measurements, confirmed isolated points,
same-level structural connections, trend relationships, strict BMS/SMS breaks,
and OHLC ambiguity.

### Approved user test constraint

These are constraints approved specifically for this validation checkpoint.
The maximum of 250 closed candles and the six separate validation gates are in
this category. They are not market-structure definitions.

### Engineering choice

These choices provide deterministic software boundaries without adding market
meaning. Examples include immutable window records, JSON ground truth, explicit
availability results, exact index resolution, and layer-specific discrepancy
reports.

### Deferred or not yet taught

These include automatic trend-segment selection, automatic structural-level
selection, discretionary BMS/SMS boundary selection, calibrated 16-type candle
classification, realtime knowability, screenshot recognition, and all strategy
or execution behavior.

## Current Repository Assessment

### Existing Chapter 1 functionality to reuse

The following implementation already exists and must not be duplicated:

- `analyze_prices()` derives OHLC from an authoritative ordered intrabar path
  and composes `CandleSide`, `CandleGeometry`, `CandleControl`, raw `PriceLeg`s,
  `MovementSummary`, `ExtremePath`, and `ExtremePathEvidence`;
- `get_features()` flattens those measurements without assigning a label;
- `classify_candle()` deliberately raises `NotImplementedError` because the 16
  fuzzy candle archetypes are uncalibrated;
- explicit human labels and original ordered price paths can be stored through
  the existing candle calibration dataset;
- strict isolated-point detection supports potentials, confirmation, batch
  scanning, and incremental tracking;
- deformation-aware confirmation supports only `STRICT` and
  `RIGHT_INSIDE_BAR` bases;
- `replace_with_more_extreme_point()` supplies the already-defined same-kind
  extremity behavior;
- ordered price-event CSV loading, interval grouping, and intrabar analysis are
  already available; and
- event/path order is authoritative and never silently sorted or interpolated.

### Existing Chapter 2 functionality to reuse

The following implementation also remains authoritative:

- `build_short_term_structure()` consumes confirmed short-term points and
  preserves all points separately from normalized vertices and suppression
  evidence;
- `build_medium_term_structure()` promotes only cleaned short-term vertices;
- `build_long_term_structure()` promotes only cleaned medium-term vertices;
- medium and long structures preserve potentials, confirming provenance,
  canonical vertices, suppressed points, and suppression reasons;
- `classify_market_state()` classifies an explicit `MarketSegment` from
  chronological `StructurePoint`s;
- `PullbackContext` and `evaluate_bms()` implement explicit retrospective BMS
  evaluation over a complete dense observation sequence;
- `SMSContext` and `evaluate_sms()` implement explicit retrospective SMS
  evaluation over a complete dense observation sequence; and
- the Chapter 2 Level-2 scenario suite already verifies major cross-lesson
  invariants without creating a general hierarchy engine.

### Genuine composition gaps

The repository does not currently provide:

1. one offline batch helper that collects both strict and right-inside-bar
   recognitions across a complete OHLC sequence;
2. one public facade that maps confirmed recognitions through short, medium,
   and long structure;
3. a timestamped closed-OHLC window contract with the approved 250-candle
   limit;
4. a generic timestamped OHLC CSV adapter;
5. an explicit structural-level selector and adapter from canonical vertices
   to `StructurePoint`;
6. safe index-reference plumbing for selected-segment BMS/SMS evaluation;
7. an explicit high-level distinction between insufficient evidence and a
   classified `NON_TREND` segment; or
8. machine-readable structural ground truth and layer-specific scoring.

These are the only new responsibilities authorized by this design.

## Architecture Alternatives

### Alternative A: one monolithic analyzer

A single module could validate data, analyze candles, recognize isolated
points, build all structural levels, evaluate a selected segment, load ground
truth, and calculate scores.

This would provide one obvious entry point, but it would combine unrelated
responsibilities and make failures difficult to attribute to Tests A through F.
It would also invite duplication of existing definitions.

### Alternative B: thin composition packages — selected

Focused modules surround the existing definitions:

- an offline window and result model;
- a deformation-aware batch recognition adapter;
- a hierarchy composer;
- a selected-segment evaluator;
- a timestamped OHLC CSV adapter; and
- separate validation ground-truth and scoring utilities.

One public facade coordinates these modules. Every component remains directly
testable, and the underlying course definitions stay unchanged. This is the
approved architecture.

### Alternative C: extend existing definition modules

The facade could be distributed across `definitions/analysis.py`, the existing
isolated-point files, and the three structure modules. This minimizes new file
count but mixes orchestration, data loading, validation, and domain definitions.
It would weaken the diagnostic boundary between Chapters 1 and 2.

### Decision

Use Alternative B. Do not build a plugin system, registry, generic recursive
hierarchy abstraction, or dependency-injection framework.

## Proposed Package Layout

Exact filenames may be refined by the later implementation plan, but the
responsibility boundaries are binding:

```text
trading/
    analysis/
        __init__.py
        models.py          # window, availability, requests, results
        isolated.py        # offline deformation-aware recognition adapter
        hierarchy.py       # recognition -> short -> medium -> long
        segments.py        # selected-level adaptation and BMS/SMS plumbing
        offline.py         # public facade
    data/
        ohlc_csv_loader.py # generic timestamped closed-OHLC input
    validation/
        __init__.py
        ground_truth.py    # JSON schema loading and validation
        scoring.py         # layer-specific comparison and metrics
```

These modules call existing functions. They do not copy their algorithms.

## Analysis-Window Contract

### Closed candle observation

The input should use an immutable record conceptually equivalent to:

```python
@dataclass(frozen=True)
class ClosedCandleObservation:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    intrabar_prices: tuple[float, ...] | None = None
```

`timestamp` is the source candle's bar-start timestamp and must be
timezone-aware. Every observation is caller-asserted to be closed/final. The
analyzer does not query a clock or mutate a live candle.

`intrabar_prices` is optional. When present it is the authoritative ordered
price path for that candle. It must never be inferred from OHLC.

The wrapper stores OHLC scalars rather than the repository's mutable `Candle`
object so the captured historical input is genuinely immutable. A thin adapter
constructs a `Candle` value when calling existing definitions; no candle
calculation is duplicated.

### Offline market window

The public window should be immutable and conceptually equivalent to:

```python
@dataclass(frozen=True)
class OfflineMarketWindow:
    instrument: str
    timeframe: str
    start_index: int
    candles: tuple[ClosedCandleObservation, ...]
```

Indexes are derived as `start_index + position`. They are dense ordinal candle
positions in this supplied ordered series. `index + 1` means the immediately
following supplied candle, not a fixed amount of clock time. This matches the
existing BMS/SMS index semantics and prevents duplicate or gapped internal
indexes.

`instrument` and `timeframe` are opaque, non-empty metadata. The analyzer
neither interprets them as structural levels nor switches them automatically.

### Window validation

The analyzer must:

- reject an empty window;
- reject more than 250 candles instead of truncating;
- accept small non-empty windows and return neutral empty structures where the
  existing builders do so;
- preserve caller order and never sort;
- require timezone-aware, strictly increasing timestamps;
- reject duplicate timestamps;
- require every OHLC value to be finite;
- require `low <= min(open, close) <= max(open, close) <= high`;
- reject an attached intrabar path containing non-finite values;
- for a path with at least two prices, require its derived OHLC to equal the
  supplied OHLC exactly; and
- treat a missing or shorter-than-two-price path as insufficient for intrabar
  analysis, not as permission to fabricate prices.

The 250-candle maximum is an approved input/test-window constraint. It is not a
short-, medium-, or long-term recognition threshold and cannot influence point
promotion, suppression, or market state.

## Chapter 1 Per-Candle Output

Each candle in the window receives an immutable result containing:

- derived dense index and timestamp;
- the immutable supplied OHLC values and the adapted `Candle` snapshot;
- `CandleSide`, `CandleGeometry`, and `CandleControl`, which are exact from
  OHLC;
- optional `CandleAnalysis` and `CandleFeatures` when at least two ordered
  intrabar prices are available and consistent; and
- explicit capability states for unavailable intrabar evidence and automatic
  candle-type classification.

Use the shared `EvaluationStatus` and `EvaluationReason` types defined below
rather than an ambiguous null alone. The result must distinguish:

```text
AVAILABLE
UNAVAILABLE / INTRABAR_DATA_UNAVAILABLE
UNAVAILABLE / CANDLE_TYPE_UNCALIBRATED
```

Automatic `CandleType` remains unavailable. The facade must not call
`classify_candle()` and must not convert geometry into any of the 16 archetypes.
Known type interpretation remains available only when a human or calibration
record explicitly supplies the type through the existing label layer.

## Offline Isolated-Point Recognition

Add a thin batch adapter around `DeformationAwareIsolatedPointTracker` rather
than reimplementing three-candle rules. Conceptually:

```python
def find_isolated_point_recognitions(
    candles: Sequence[Candle],
    *,
    start_index: int = 0,
) -> IsolatedPointScan:
    ...
```

The scan result should contain:

- confirmed `IsolatedPointRecognition` objects in chronological order; and
- the unresolved right-edge potential, if one exists.

Only confirmations with `IsolatedPointBasis.STRICT` or
`IsolatedPointBasis.RIGHT_INSIDE_BAR` are supported. Rejected potentials may
disappear, consistent with the existing tracker contract. An unresolved
right-edge potential remains diagnostic evidence but is not mapped into short
structure.

The adapter must preserve the window's derived absolute indexes. If reuse of
the current tracker requires offsetting its local indexes, the adapter performs
that mechanical translation without changing kind, status, price, basis, or
chronology.

The standalone `replace_with_more_extreme_point()` behavior remains separately
testable. The batch bridge must not delete confirmed recognitions before the
short-term builder; that builder owns canonical same-kind suppression while
preserving all valid short-term points.

## Structural Hierarchy Composition

The hierarchy composer is conceptually:

```python
@dataclass(frozen=True)
class StructuralHierarchy:
    isolated: IsolatedPointScan
    short_term: ShortTermStructure
    medium_term: MediumTermStructure
    long_term: LongTermStructure

def build_structural_hierarchy(
    isolated: IsolatedPointScan,
) -> StructuralHierarchy:
    ...
```

It performs only this flow:

```text
confirmed isolated recognitions
        -> short_term_point_from_recognition()
        -> build_short_term_structure()
        -> build_medium_term_structure()
        -> build_long_term_structure()
```

The hierarchy composer must preserve:

- every confirmed recognition and its basis;
- all level-specific points separately from vertices;
- potentials at medium and long levels;
- suppression records and reasons;
- medium and long confirming provenance;
- promotion from cleaned lower-level vertices only; and
- exact level-specific point types.

It must not create a generic recursive structural engine or mix levels.

## Public Offline Analyzer

The approved facade is conceptually:

```python
def analyze_market_window(
    window: OfflineMarketWindow,
    segment: SegmentAnalysisRequest | None = None,
) -> OfflineMarketAnalysis:
    ...
```

`OfflineMarketAnalysis` contains:

- the validated window metadata and candle observations;
- per-candle Chapter 1 results;
- the offline isolated-point scan;
- short-, medium-, and long-term structures; and
- an optional selected-segment result.

With no segment request, the analyzer returns objective candle and hierarchy
results only. It does not classify the entire window implicitly.

The facade delegates every calculation to the relevant existing definition or
thin adapter. It contains no alternate recognition formulas.

## Structural-Level Selection

Introduce an explicit enum conceptually equivalent to:

```python
class StructuralLevel(Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
```

This enum chooses one already-built hierarchy output. It is not derived from
the timeframe. The mapping is exact:

- `SHORT` -> `ShortTermStructure.vertices`;
- `MEDIUM` -> `MediumTermStructure.vertices`; and
- `LONG` -> `LongTermStructure.vertices`.

No point from `.points` but absent from `.vertices`, no suppressed point, and
no point from another structural level may enter the selected-level sequence.

## Selected-Segment Contract

The optional request is conceptually:

```python
@dataclass(frozen=True)
class SegmentAnalysisRequest:
    segment: MarketSegment
    level: StructuralLevel
    bms: BMSAnalysisRequest | None = None
    sms: SMSAnalysisRequest | None = None
```

The `MarketSegment` uses the same inclusive dense indexes as the window. It
must lie wholly inside the window. The analyzer must reject an outside or
inverted request and must not clamp it.

For market-state analysis, select only canonical vertices at the requested
level whose indexes lie inside the segment. Adapt each mechanically to the
existing `StructurePoint` representation:

- the source vertex index becomes `StructurePoint.index`;
- `HIGH` or `LOW` maps directly to `StructurePointKind`; and
- the source vertex price becomes `StructurePoint.price`.

Preserve source-vertex references in the high-level result so provenance is
auditable. Do not silently sort. A medium- or long-term vertex belongs to the
selected segment according to its `pivot_index`; its later confirming-source
index does not relocate the pivot. This is a retrospective inclusion rule and
makes no claim that the point was available before its confirmer existed.

## Market-State Availability

The high-level result must distinguish availability from market state.

Use these exact shared status and reason values:

```python
class EvaluationStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"

class EvaluationReason(Enum):
    INSUFFICIENT_STRUCTURE = "insufficient_structure"
    INTRABAR_DATA_UNAVAILABLE = "intrabar_data_unavailable"
    CANDLE_TYPE_UNCALIBRATED = "candle_type_uncalibrated"
    BOUNDARY_NOT_CANONICAL_VERTEX = "boundary_not_canonical_vertex"
    INVALID_CONTEXT = "invalid_context"
    PARENT_STATE_NOT_DIRECTIONAL = "parent_state_not_directional"
    OHLC_INTRABAR_ORDER_AMBIGUOUS = "ohlc_intrabar_order_ambiguous"
```

Every evaluated capability is wrapped by an immutable object with `status`,
optional `reason`, and optional diagnostic `message`. `AVAILABLE` requires no
reason. `UNAVAILABLE` and `INVALID` require a reason. A value such as
`MarketState`, `BMSResult`, or `SMSResult` is present only for `AVAILABLE`. An
optional BMS/SMS request that was not supplied is represented by `None`, not by
a fabricated evaluation.

Before calling `classify_market_state()`, count selected same-level canonical
vertices inside the segment. If there are fewer than two `HIGH` vertices or
fewer than two `LOW` vertices, return:

```text
UNAVAILABLE / INSUFFICIENT_STRUCTURE
market_state = None
```

Do not call the lower-level classifier in this case, and do not reinterpret
insufficient evidence as `NON_TREND`.

When both counts are sufficient, call the existing classifier unchanged:

- `UPTREND` means all high relationships are higher-high and all low
  relationships are higher-low;
- `DOWNTREND` means all high relationships are lower-high and all low
  relationships are lower-low; and
- `NON_TREND` means sufficient evidence was evaluated but neither directional
  definition holds.

The existing `classify_market_state()` behavior remains unchanged for direct
callers.

## BMS and SMS Request Boundaries

### Caller-supplied index references

The caller chooses every semantically ambiguous boundary. Request types should
be conceptually equivalent to:

```python
@dataclass(frozen=True)
class BMSAnalysisRequest:
    trend_origin_index: int
    previous_extreme_index: int
    pullback_extreme_index: int

@dataclass(frozen=True)
class SMSAnalysisRequest:
    trend_extreme_index: int
    creator_point_index: int
```

The caller does not supply arbitrary `StructurePoint` objects. It also does not
ask the analyzer to choose a boundary.

### Exact canonical resolution

Each index must resolve uniquely against the canonical vertices of the
explicitly selected `StructuralLevel` in the already-built hierarchy.

The resolver must not fall back to:

- a suppressed point;
- a level-specific `.points` member absent from `.vertices`;
- a vertex at another structural level;
- a raw OHLC high or low; or
- an arbitrary caller-created point.

Zero or multiple matches produce an explicit `INVALID` boundary-evaluation
result with a machine-readable reason such as
`BOUNDARY_NOT_CANONICAL_VERTEX`. The analyzer must not guess.

### Safe automated plumbing

After successful resolution, the analyzer may only:

1. adapt exact selected-level vertices into `StructurePoint`s;
2. validate kinds, chronology, and selected parent segment;
3. construct the existing `PullbackContext` or `SMSContext`;
4. derive every dense OHLC observation after the relevant boundary through the
   end of the supplied window; and
5. call `evaluate_bms()` or `evaluate_sms()` unchanged.

For BMS:

- `trend_origin` and `previous_extreme` must be inside the selected parent
  segment;
- `previous_extreme.index == segment.end_index`;
- `pullback_extreme` must be a later canonical vertex at the same level and
  inside the analysis window; and
- observations cover every window candle from
  `pullback_extreme.index + 1` through the window end.

For SMS:

- `creator_point` and `trend_extreme` must be inside the selected parent
  segment;
- `trend_extreme.index == segment.end_index`; and
- observations cover every window candle from
  `trend_extreme.index + 1` through the window end.

The derived observation indexes are the window's dense ordinal indexes. No
post-boundary candle may be skipped. Empty suffixes remain valid inputs to the
existing evaluators.

### Directional and invalid contexts

BMS and SMS require an available directional parent state. If selected-segment
market state is unavailable or `NON_TREND`, a requested BMS/SMS evaluation
returns an explicit unavailable result such as
`PARENT_STATE_NOT_DIRECTIONAL`; it does not fabricate a context.

If resolved boundaries violate the existing point-kind, price, chronology, or
segment invariants, report an explicit `INVALID / INVALID_CONTEXT` result and
retain the underlying validation message. Do not weaken existing context
validation.

### OHLC ambiguity

The existing strict wick-crossing, equality, dense chronology, and first-event
rules remain unchanged. When a candle crosses both relevant boundaries and
OHLC cannot determine intrabar order, the high-level evaluation reports:

```text
INVALID / OHLC_INTRABAR_ORDER_AMBIGUOUS
```

It retains the exact existing evaluator message. It must not infer intrabar
order. Ordered intrabar resolution is deferred to a separate future design.

`SMS_CONFIRMED` remains a retrospective structural event, never a prediction,
opposite-trend confirmation, or trading signal.

## Retrospective Timing Boundary

This analyzer interprets one completed historical window. It does not claim
when each retrospectively normalized result was knowable in realtime.

Do not add:

- `known_at_index`;
- `confirmed_at_index`;
- fake streaming availability;
- a live state machine;
- look-ahead trading claims; or
- broker/execution behavior.

Existing pivot and confirming-source provenance remains intact. A future
candle-by-candle replay design may add real availability semantics only after
they are explicitly specified and tested.

## Timestamped OHLC CSV Adapter

Add a generic loader separate from the existing tick/trade loader. The default
schema is:

```text
timestamp,open,high,low,close
```

The loader must:

- parse ISO-8601 timezone-aware timestamps;
- preserve row order;
- reject missing, malformed, non-numeric, or non-finite values;
- reject duplicate or decreasing timestamps;
- validate OHLC geometry;
- never sort, fill, resample, or interpolate; and
- combine explicit caller-supplied `instrument`, `timeframe`, and
  `start_index` metadata into an `OfflineMarketWindow`.

The CSV adapter accepts only completed OHLC rows. It does not download data or
connect to NinjaTrader, TradingView, or a broker.

## Validation Boundaries

### Test A — Chapter 1 candle analysis

Input: ordered intrabar price paths when available.

Validate exact OHLC, side, geometry, wick/body ratios, open/close positions,
control, movement legs, movement summaries, extreme order/path/evidence, and
features. Validate explicit unavailability when intrabar paths or calibrated
candle types are absent.

Do not invoke isolated-point or Chapter 2 logic.

### Test B — isolated-point recognition

Input: chronological OHLC candles.

Validate potentials, strict confirmation, equality rejection,
`RIGHT_INSIDE_BAR`, basis provenance, chronological batch output, unresolved
right-edge potential handling, and existing same-kind replacement behavior.

Do not build market structure in this gate.

### Test C — pure Chapter 2 hierarchy

Input: deterministic or human-labelled confirmed isolated recognitions,
bypassing candle recognition.

Validate all points, potentials, canonical vertices, suppression reasons,
provenance, same-level-only connections, cleaned lower-level promotion sources,
and short-to-medium-to-long recursion.

### Test D — complete objective bridge

Input: raw chronological OHLC candles.

Validate:

```text
OHLC
 -> strict/deformation recognition
 -> ShortTermStructure
 -> MediumTermStructure
 -> LongTermStructure
```

This is the main facade integration test, but Tests A through C remain separate
so failures are attributable.

### Test E — selected-segment analysis

Input: one explicit segment, one explicit structural level, and optional
caller-chosen BMS/SMS boundary indexes.

Validate sufficiency, `UPTREND`/`DOWNTREND`/`NON_TREND`, exact canonical
boundary resolution, dense observation derivation, strict breaks, equality
touches, first events, invalid contexts, and OHLC ambiguity.

### Test F — real historical blind validation

Input to the analyzer: numerical market data plus only permitted metadata and
explicit context selections. Human expected labels are stored independently
and are never passed to the analyzer.

This gate begins only after deterministic Tests A through E pass.

## Machine-Readable Ground Truth

Use one versioned JSON document per validation case. JSON matches the nested
structure and enum values better than CSV, while separate files make reviews
and disagreements auditable. A directory of case files forms a dataset; a
manifest may list them without embedding labels into market-data input.

Conceptual schema:

```json
{
  "schema_version": 1,
  "case_id": "mnq-1m-2026-08-28-a",
  "source": {
    "market_data_file": "mnq-1m-2026-08-28-a.csv",
    "sha256": "...",
    "instrument": "MNQ",
    "timeframe": "1m",
    "start_index": 0,
    "candle_count": 200
  },
  "expected": {
    "isolated": [],
    "short_term": {
      "points": [],
      "vertices": [],
      "suppressed": []
    },
    "medium_term": {
      "points": [],
      "potentials": [],
      "vertices": [],
      "suppressed": []
    },
    "long_term": {
      "points": [],
      "potentials": [],
      "vertices": [],
      "suppressed": []
    },
    "segment": null
  },
  "ambiguities": []
}
```

Point records carry index, kind, price, and recognition basis when applicable.
Medium/long records also carry pivot and confirming-source indexes. Potential
records carry previous and pivot indexes. Suppression records carry point
identity and exact reason. Optional segment records carry boundaries, selected
level, market-state availability/state, caller-supplied boundary requests, and
expected BMS/SMS status and event details where legitimately labelable.

`sha256` binds labels to exact market data. The visual TradingView chart is
supporting evidence and may be referenced by metadata, but pixels are never the
analyzer's numerical input.

Ambiguity entries must be written before scoring and identify the exact layer
and disputed item. They cannot be added after seeing a poor score merely to
hide disagreement.

## Correctness Scoring

### Deterministic cases

Tests A through E require exact equality wherever existing rules are exact.
Sequence order, enum identity, indexes, point membership, suppression reason,
and provenance must match exactly.

### Real labelled cases

Point detection reports:

- true positives, false positives, and false negatives;
- precision, recall, and F1;
- exact index and kind agreement;
- exact recognition-basis agreement; and
- exact price agreement.

Because expected structural prices come from the same numerical market data,
price comparison is exact by default. A non-zero tolerance is allowed only when
the source format supplies an explicit tick-size/rounding justification; the
tolerance must be recorded in the case before execution.

Each structural level reports:

- exact ordered point-sequence match;
- exact potential-sequence match where applicable;
- exact canonical vertex-sequence match;
- exact suppressed-point and suppression-reason match; and
- exact pivot/confirming-source provenance match.

Selected-segment scoring reports exact availability reason, market state, BMS
status/broken boundary/event index, and SMS status/broken boundary/event index.

The scorer returns raw metrics and exact-match booleans. This design does not
invent a pass threshold for imperfect real data.

### Outcome classification

Every discrepancy is classified as one of:

- **ENGINE_FAILURE:** the analyzer crashes, violates an invariant, produces an
  invalid shape, or fails an exact deterministic rule;
- **GROUND_TRUTH_DISAGREEMENT:** valid deterministic output differs from a
  human-labelled expectation; or
- **COURSE_AMBIGUITY:** the case was explicitly marked as not operationally
  determined by the taught rules.

Course ambiguities are reported separately and excluded from precision/recall
denominators only when declared before execution. They are never silently
converted into passes or engine failures.

## Validation Data Strategy

### First deterministic simulated dataset

Use a small, reviewed collection rather than one giant scenario:

1. ordered intrabar paths covering bullish, bearish, doji, flat, reversals,
   repeated prices, and zero-range behavior for Test A;
2. OHLC sequences covering strict high/low, equality rejection,
   right-inside-bar confirmation, rejected candidates, and right-edge potential
   for Test B;
3. supplied confirmed points covering same-kind runs, equal ties, inside
   suppression, one-side breakouts, potentials, medium promotion, and long
   promotion for Test C;
4. at least one rich OHLC bridge sequence containing both strict and
   right-inside-bar recognitions and enough objective structure for medium and
   long outputs for Test D; and
5. explicit uptrend, downtrend, non-trend, insufficient, BMS touch/break, SMS
   touch/break, first-event, invalid-boundary, and dual-crossing ambiguity cases
   for Test E.

Every dataset is at most 250 closed candles. Expected outputs are authored
before running the facade.

### First real historical MNQ dataset

Start with multiple MNQ one-minute windows, then add MNQ five-minute windows.
Each window contains at most 250 completed candles in a generic timezone-aware
OHLC CSV:

```text
timestamp,open,high,low,close
```

Include several independently selected windows across clear directional,
non-trending, same-kind replacement, inside-structure, and naturally occurring
deformation conditions. Some windows should support medium promotion and, when
naturally present, long promotion. No single window must contain every case.

For Chapter 1 intrabar validation, use separately exported ordered MNQ
tick/trade data in the existing `timestamp,price` format, preferably from
NinjaTrader historical/replay export. Preserve original event order and use the
existing interval builder. Do not infer an intrabar path from OHLC.

TradingView is initially a human annotation and visual cross-check tool for the
exact same timestamp range. Do not scrape it or use screenshots as numerical
input. After MNQ one- and five-minute validation, add ES or MES to assess
instrument independence.

### Blind procedure

For every real case:

1. freeze and hash the numerical source data;
2. prepare and review human/course ground truth independently;
3. run the analyzer using only market data and allowed explicit context inputs;
4. load ground truth only in the validation layer;
5. compare and classify discrepancies by layer; and
6. retain the report and source hash for reproducibility.

Do not select only charts already known to match the implementation.

## Error Handling

| Condition | High-level behavior |
| --- | --- |
| Empty window | `ValueError` |
| More than 250 candles | `ValueError`; never truncate |
| One or two valid candles | Return available OHLC measurements and neutral hierarchy output |
| Invalid or non-finite OHLC | `ValueError` |
| Naive, duplicate, or decreasing timestamps | `ValueError`; never sort |
| Missing/one-price intrabar path | OHLC analysis remains available; intrabar result explicitly unavailable |
| Intrabar path disagrees with supplied OHLC | `ValueError` |
| Uncalibrated 16-type classification | Explicit unavailable capability; no classifier call |
| Selected segment outside the window | `ValueError`; never clamp |
| Fewer than two selected-level highs or lows | `UNAVAILABLE / INSUFFICIENT_STRUCTURE` |
| Boundary index has no unique selected-level canonical vertex | `INVALID / BOUNDARY_NOT_CANONICAL_VERTEX` |
| Boundary kind, price, chronology, or segment is invalid | `INVALID / INVALID_CONTEXT` with message |
| Parent state is unavailable or non-directional | BMS/SMS unavailable; no context fabricated |
| Same OHLC candle crosses both relevant BMS/SMS boundaries | `INVALID / OHLC_INTRABAR_ORDER_AMBIGUOUS` with existing message |
| Malformed ground-truth schema | Validation error before scoring |
| Predeclared course ambiguity | Report separately; do not guess |

## Test Strategy

The later implementation plan must preserve red-to-green TDD and keep each gate
in its own focused test module. A failure in Test A or B must not require the
Chapter 2 hierarchy to diagnose it; Test C must bypass Chapter 1 recognition;
and Test D must prove their real composition.

Required test families include:

- window limits, OHLC validity, timestamp chronology, no sorting, and metadata;
- per-candle OHLC-only versus intrabar-available results;
- explicit uncalibrated candle-type availability;
- offline strict and right-inside-bar batch recognition with basis/index
  preservation and unresolved edge potential;
- exact hierarchy composition and provenance;
- explicit structural-level selection and same-level canonical resolution;
- insufficient structure versus evaluated `NON_TREND`;
- BMS/SMS index resolution, context validation, dense suffix observations,
  strict break/touch behavior, first-event behavior, and OHLC ambiguity;
- OHLC CSV loading without interpolation or reordering;
- JSON ground-truth schema validation;
- exact deterministic comparisons and real-data metrics; and
- complete repository regression coverage.

No implementation test may assert an untaught deformation, automatic segment,
automatic level, automatic boundary, candle-type threshold, or trading result.

## Explicitly Deferred Behavior and Non-Goals

This checkpoint does not authorize:

- automatic trend-segment selection;
- automatic structural-level selection;
- automatic BMS trend-origin, previous-extreme, or pullback-extreme selection;
- automatic SMS creator-point or trend-extreme selection;
- automatic timeframe selection or switching;
- timeframe-to-level mapping or a fixed timeframe hierarchy;
- use of the 250-candle limit as a structural rule;
- unsupported isolated-point deformations;
- a generic recursive hierarchy engine;
- calibrated or learned classification of the 16 candle archetypes;
- AI/ML classification;
- TradingView scraping or screenshot computer vision;
- live streaming or realtime knowability fields;
- `known_at_index` or `confirmed_at_index`;
- automatic intrabar resolution of OHLC ambiguity;
- future-price prediction;
- trading signals, entries, exits, stops, risk, sizing, leverage, or
  profitability backtesting;
- broker APIs, NinjaTrader order placement, or execution logic; or
- Chapter 3 concepts.

## Future Live/Replay Handoff

After deterministic offline correctness and real blind historical validation
are established, a separate specification may define candle-by-candle replay.
That future work must distinguish retrospective pivot provenance from when a
result first became knowable, prove that no later candle is used early, and
use ordered intrabar timestamps when resolving same-candle boundary order.

Offline results from this checkpoint must not be retroactively described as
live-safe signals.

## Design Invariants

1. Existing Chapter 1 and Chapter 2 algorithms remain authoritative.
2. The new layer composes definitions; it does not redefine them.
3. Tests A through F remain independently diagnosable.
4. No analysis window contains more than 250 closed candles.
5. The 250-candle maximum has no structural meaning.
6. Caller chronology is preserved; no input is silently sorted.
7. Timeframe metadata is never interpreted as structural level.
8. Missing intrabar data never causes an inferred price path.
9. Automatic candle-type classification remains explicitly uncalibrated.
10. Only confirmed strict or right-inside-bar recognitions enter short-term
    structure.
11. All confirmed point evidence remains distinct from canonical vertices.
12. Medium promotion consumes only short-term canonical vertices.
13. Long promotion consumes only medium-term canonical vertices.
14. Selected-segment analysis uses one explicit structural level.
15. Fewer than two highs or lows produces unavailable, not `NON_TREND`.
16. `NON_TREND` is returned only after sufficient evidence is evaluated.
17. BMS/SMS references resolve uniquely against selected-level canonical
    vertices only.
18. Every ambiguous semantic BMS/SMS boundary remains caller-supplied.
19. BMS/SMS observations form a complete dense window suffix.
20. Existing strict break, equality, first-event, and OHLC ambiguity rules are
    preserved.
21. `SMS_CONFIRMED` remains structural and non-predictive.
22. Human labels are never analyzer input during blind validation.
23. Ground truth is bound to exact source data and scored layer by layer.
24. Course ambiguities are explicit and cannot be added after scoring to hide
    disagreement.
25. No strategy, risk, execution, or Chapter 3 behavior enters this design.
