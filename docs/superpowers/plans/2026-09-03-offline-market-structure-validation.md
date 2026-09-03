# Offline Market Structure Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic offline facade that validates a closed OHLC window, composes the existing Chapter 1 and Chapter 2 definitions, evaluates only caller-selected structural contexts, and compares results with source-bound ground truth without inventing market labels.

**Architecture:** Add thin `trading.analysis` composition modules around the existing authoritative definitions, a separate timestamped OHLC loader, and separate validation/ground-truth utilities. The analyzer preserves every layer's native records and provenance; it never duplicates recognition rules, chooses a segment/level/boundary, or turns missing evidence into a market conclusion.

**Tech Stack:** Python standard library (`dataclasses`, `datetime`, `enum`, `csv`, `json`, `hashlib`, `pathlib`, `typing`), pytest, and the existing `trading.definitions` and `trading.data` modules.

**Spec:** `docs/superpowers/specs/2026-09-03-offline-market-structure-validation-design.md`

## Global Constraints

- The approved specification is binding. If this plan conflicts with it, stop and follow the specification.
- This is a thin pre-Chapter-3 offline composition and validation layer. Existing Chapter 1 and Chapter 2 functions remain the only market-rule implementations.
- Never duplicate candle geometry, intrabar movement, isolated-point, short/medium/long promotion, market-state, BMS, or SMS algorithms.
- Analyze only caller-supplied closed data in caller chronology. Never sort, truncate, fill, resample, interpolate, or infer an intrabar path.
- Accept 1 through 250 closed observations. Reject zero or more than 250; the limit has no structural meaning.
- Treat `instrument` and `timeframe` as opaque metadata. Never map timeframe to `StructuralLevel`.
- Never call `classify_candle()`. Automatic candle type is `UNAVAILABLE / CANDLE_TYPE_UNCALIBRATED`.
- With no `SegmentAnalysisRequest`, return the objective hierarchy and no implicit whole-window market state.
- Resolve BMS/SMS indexes only against canonical `.vertices` at the explicitly selected level. Never fall back to `.points`, suppressions, another level, raw OHLC, or caller-created `StructurePoint`s.
- Before `classify_market_state()`, require at least two selected-level HIGH vertices and two LOW vertices inside the segment. Insufficient evidence is `UNAVAILABLE / INSUFFICIENT_STRUCTURE`, never `NON_TREND`.
- Preserve dense suffix chronology and the existing exact OHLC ambiguity message. Never infer intrabar boundary order.
- Ground truth is validation input only after analysis and must be SHA-256-bound to the exact numerical source.
- Do not add a generic recursive hierarchy, plugin/registry/DI framework, automatic segment/level/boundary selection, unsupported deformation, candle thresholds, screenshot recognition, live state, prediction, strategy, signals, risk, sizing, execution, broker integration, or Chapter 3 concepts.
- Use red-to-green TDD for every production behavior. A RED must be a collected, executed assertion failure caused by missing behavior, never an import, collection, syntax, or setup error.
- Every implementation task gets spec-compliance and code-quality review; fix valid findings and re-review before recording the task complete.

## Planned File Structure

Create exactly these production files:

- `trading/analysis/__init__.py`
- `trading/analysis/models.py`
- `trading/analysis/candles.py`
- `trading/analysis/isolated.py`
- `trading/analysis/hierarchy.py`
- `trading/analysis/segments.py`
- `trading/analysis/offline.py`
- `trading/data/ohlc_csv_loader.py`
- `trading/validation/__init__.py`
- `trading/validation/ground_truth.py`
- `trading/validation/scoring.py`

Create exactly these focused test files:

- `tests/test_offline_models.py`
- `tests/test_offline_candle_analysis.py`
- `tests/test_offline_isolated.py`
- `tests/test_offline_hierarchy.py`
- `tests/test_offline_analysis.py`
- `tests/test_offline_segments.py`
- `tests/test_ohlc_csv_loader.py`
- `tests/test_validation_ground_truth.py`
- `tests/test_validation_scoring.py`
- `tests/test_offline_market_structure_integration.py`
- `tests/test_blind_validation_workflow.py`

The only refinement from the design's approximate layout is the focused
`trading/analysis/candles.py` module. It keeps Chapter 1 per-candle adaptation
out of immutable models and out of the public facade. Do not modify existing
package exports or any current definition/test file unless a reviewed defect
proves the approved composition impossible.

## Locked Public Interfaces

Use these names consistently across all tasks:

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


@dataclass(frozen=True)
class Evaluation(Generic[T]):
    status: EvaluationStatus
    value: T | None = None
    reason: EvaluationReason | None = None
    message: str | None = None


@dataclass(frozen=True)
class ClosedCandleObservation:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    intrabar_prices: tuple[float, ...] | None = None


@dataclass(frozen=True)
class OfflineMarketWindow:
    instrument: str
    timeframe: str
    start_index: int
    candles: tuple[ClosedCandleObservation, ...]


class StructuralLevel(Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


@dataclass(frozen=True)
class BMSAnalysisRequest:
    trend_origin_index: int
    previous_extreme_index: int
    pullback_extreme_index: int


@dataclass(frozen=True)
class SMSAnalysisRequest:
    trend_extreme_index: int
    creator_point_index: int


@dataclass(frozen=True)
class SegmentAnalysisRequest:
    segment: MarketSegment
    level: StructuralLevel
    bms: BMSAnalysisRequest | None = None
    sms: SMSAnalysisRequest | None = None


StructuralVertex = ShortTermPoint | MediumTermPoint | LongTermPoint


@dataclass(frozen=True)
class ResolvedStructurePoint:
    level: StructuralLevel
    source_vertex: StructuralVertex
    point: StructurePoint


@dataclass(frozen=True)
class SegmentAnalysisResult:
    request: SegmentAnalysisRequest
    selected_points: tuple[ResolvedStructurePoint, ...]
    market_state: Evaluation[MarketState]
    bms: Evaluation[BMSResult] | None
    sms: Evaluation[SMSResult] | None


def analyze_market_window(
    window: OfflineMarketWindow,
    segment: SegmentAnalysisRequest | None = None,
) -> OfflineMarketAnalysis: ...
```

`Evaluation` enforces: `AVAILABLE` has a value and no reason;
`UNAVAILABLE`/`INVALID` have no value and require a reason. Optional BMS/SMS
requests not supplied remain `None`. Specialized immutable result records are
defined in the relevant task below and preserve source objects rather than
flattening away provenance.

## New-Module RED Bootstrap Rule

For every production module that does not exist at the start of its task,
perform this exact prelude before importing its public symbols in the test
module:

1. write a test that calls `importlib.util.find_spec("exact.module.name")` and
   asserts the result is not `None`;
2. run only that test and confirm a collected assertion `FAILED` (for a nested
   module, its parent package must already exist);
3. create only the target module with its docstring;
4. rerun the discovery test to PASS;
5. add an `import_module()`/`hasattr()` locked-public-name test;
6. run it and confirm a collected assertion `FAILED` listing missing names;
7. add only collectable public-name scaffolds that raise `NotImplementedError`
   from callable behavior; and
8. rerun the boundary tests to PASS before appending normal imports and
   behavioral tests.

For Task 1, bootstrap `trading.analysis` first, then
`trading.analysis.models`. For Task 10, bootstrap `trading.validation` first,
then `trading.validation.ground_truth`. Import/collection errors do not count
as RED at any point. The task-specific RED below always occurs after this
prelude and must be an executed behavioral failure.

---

## Future Execution Protocol

Before Task 1, the executor must:

- [ ] Invoke `superpowers:using-git-worktrees`.
- [ ] Fetch `origin/main`; verify local `main == origin/main`; record the approved implementation-plan SHA as the immutable implementation base in the SDD ledger.
- [ ] Create `feature/offline-market-analysis` and an isolated worktree from that exact checkpoint. Do not implement on `main`.
- [ ] Create the SDD workspace/ledger for this exact plan.
- [ ] Read the complete approved spec and this complete plan, run the SDD pre-flight consistency scan, and record any binding ruling in the ledger.
- [ ] Run `pytest -q` and `git diff --check` before edits; record the actual fresh baseline count rather than assuming the previously reported 464.
- [ ] Use `superpowers:subagent-driven-development`, `superpowers:test-driven-development`, and a fresh implementer for each Task 1-13.
- [ ] After each task, run the listed regressions, commit the coherent change, request spec-compliance and code-quality review, fix valid findings, re-review, and record all SHAs/verdicts.
- [ ] Use `superpowers:systematic-debugging` for unexpected failures and `superpowers:verification-before-completion` before completion claims.
- [ ] Push only the reviewed feature branch. Use `superpowers:finishing-a-development-branch` only after the user later chooses an integration option.

---

### Task 1: Immutable Offline Models and Window Validation

**Files:**

- Create: `trading/analysis/__init__.py`
- Create: `trading/analysis/models.py`
- Create: `tests/test_offline_models.py`

**Interfaces:** Produces `EvaluationStatus`, `EvaluationReason`, generic
`Evaluation[T]`, `ClosedCandleObservation`, `OfflineMarketWindow`,
`StructuralLevel`, `BMSAnalysisRequest`, `SMSAnalysisRequest`,
`SegmentAnalysisRequest`, `ResolvedStructurePoint`, and
`SegmentAnalysisResult`. The last two records carry existing
`StructurePoint`/BMS/SMS values and a source-vertex union but contain no
evaluation logic.

- [ ] **Step 1: Bootstrap the package/module, then add model behavior tests**

Apply the New-Module RED Bootstrap Rule first. After both modules and their
locked-name scaffolds exist, append normal imports and exact tests such as:

```python
def observation(index: int, **overrides: object) -> ClosedCandleObservation:
    values = dict(
        timestamp=datetime(2026, 8, 28, 9, 30, index, tzinfo=timezone.utc),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        intrabar_prices=None,
    )
    values.update(overrides)
    return ClosedCandleObservation(**values)


def test_window_preserves_dense_input_metadata_without_sorting() -> None:
    first = observation(0)
    second = observation(1)
    window = OfflineMarketWindow("MNQ", "1m", 40, (first, second))
    assert window.candles == (first, second)
    assert [window.start_index + i for i in range(len(window.candles))] == [40, 41]


@pytest.mark.parametrize("count", [0, 251])
def test_window_rejects_outside_approved_size(count: int) -> None:
    candles = tuple(observation(i) for i in range(count))
    with pytest.raises(ValueError, match="1 through 250"):
        OfflineMarketWindow("MNQ", "1m", 0, candles)
```

Also test frozen records, empty `instrument`/`timeframe`, naive timestamps,
duplicate/decreasing timestamps, non-finite OHLC/intrabar values, each invalid
OHLC geometry ordering, exact 250 acceptance, no truncation, and exact
intrabar/OHLC agreement. Explicitly test `None`, `()`, and `(100.0,)` as valid
but intrabar-insufficient inputs; for length at least two, use
`(100.0, 99.0, 102.0, 101.0)` and require exact `100/102/99/101` agreement.

Test `Evaluation` invariants:

```python
assert Evaluation(EvaluationStatus.AVAILABLE, value=MarketState.UPTREND)
with pytest.raises(ValueError):
    Evaluation(EvaluationStatus.AVAILABLE, reason=EvaluationReason.INVALID_CONTEXT)
with pytest.raises(ValueError):
    Evaluation(EvaluationStatus.UNAVAILABLE)
with pytest.raises(ValueError):
    Evaluation(EvaluationStatus.INVALID, value=MarketState.NON_TREND,
               reason=EvaluationReason.INVALID_CONTEXT)
```

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
pytest tests/test_offline_models.py -v
```

Expected: collected assertions fail because the discovered module lacks the
locked records/validation; no import or collection error is accepted.

- [ ] **Step 3: Implement the minimum immutable validation model**

Use `math.isfinite`, timezone-awareness via `utcoffset()`, caller-order `zip`,
and exact tuple preservation. Validate all observations in their own
`__post_init__`; validate metadata, count, and strictly increasing timestamps
in `OfflineMarketWindow.__post_init__`. For an intrabar path with at least two
prices, compare `(first, max, min, last)` exactly to supplied OHLC.

```python
if prices is not None and len(prices) >= 2:
    derived = (prices[0], max(prices), min(prices), prices[-1])
    supplied = (self.open, self.high, self.low, self.close)
    if derived != supplied:
        raise ValueError("intrabar prices must derive the supplied OHLC exactly")
```

- [ ] **Step 4: Run GREEN and adjacent model regressions**

```bash
pytest tests/test_offline_models.py -v
pytest tests/test_market_data.py tests/test_csv_loader.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

Review immutability, exact enum values, the 1-250 boundary, no sorting, no
timeframe interpretation, no path fabrication, and generic evaluation
invariants.

```bash
git add trading/analysis/__init__.py trading/analysis/models.py tests/test_offline_models.py
git commit -m "Add offline market window models"
```

---

### Task 2: Chapter 1 Per-Candle Analysis Adapter (Test A)

**Files:**

- Create: `trading/analysis/candles.py`
- Create: `tests/test_offline_candle_analysis.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class OfflineCandleResult:
    index: int
    timestamp: datetime
    observation: ClosedCandleObservation
    candle: Candle
    side: CandleSide
    geometry: CandleGeometry
    control: CandleControl
    intrabar_analysis: Evaluation[CandleAnalysis]
    features: Evaluation[CandleFeatures]
    candle_type: Evaluation[CandleType]


def analyze_closed_candle(
    observation: ClosedCandleObservation,
    *,
    index: int,
) -> OfflineCandleResult: ...
```

- [ ] **Step 1: Write exact Test A failures**

Use the canonical path
`(100.0, 99.0, 102.0, 106.0, 110.0, 107.0, 103.0, 101.0)`
at index 40. Assert the adapter reuses the existing output: bullish side,
OHLC `100/110/99/101`, geometry ratios, control score, three detailed legs,
`LOW_THEN_HIGH`, final retracement `9/11`, extreme evidence, and features.
Assert object identity/value agreement with direct `analyze_prices(path)` and
`get_features(...)`.

Add OHLC-only tests asserting `get_side()`, `get_geometry()`, and
`get_control()` remain available while both `intrabar_analysis` and `features`
are `UNAVAILABLE / INTRABAR_DATA_UNAVAILABLE`. Assert `candle_type` is always
`UNAVAILABLE / CANDLE_TYPE_UNCALIBRATED`, including when intrabar exists, and
monkeypatch `trading.definitions.candles.classify_candle` to raise if called.
Cover bearish, doji, and zero-range OHLC; never involve isolated points.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_offline_candle_analysis.py -v
```

Expected: collected assertions fail because `analyze_closed_candle` behavior
is absent, not because imports or fixtures fail.

- [ ] **Step 3: Implement by composition only**

Construct `Candle(observation.open, observation.high, observation.low,
observation.close)`, then call existing `get_side`, `get_geometry`, and
`get_control`. Only when `intrabar_prices is not None` and length is at least
two call `analyze_prices` and `get_features`. Create unavailable wrappers
otherwise. Never call `classify_candle`.

```python
if observation.intrabar_prices is None or len(observation.intrabar_prices) < 2:
    intrabar = Evaluation(
        EvaluationStatus.UNAVAILABLE,
        reason=EvaluationReason.INTRABAR_DATA_UNAVAILABLE,
    )
else:
    analysis = analyze_prices(observation.intrabar_prices)
    intrabar = Evaluation(EvaluationStatus.AVAILABLE, value=analysis)
```

- [ ] **Step 4: Run GREEN and Chapter 1 regressions**

```bash
pytest tests/test_offline_candle_analysis.py -v
pytest tests/test_analysis.py tests/test_candles.py tests/test_controls.py tests/test_extremes.py tests/test_extreme_evidence.py tests/test_movements.py tests/test_movement_summaries.py tests/test_features.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/analysis/candles.py tests/test_offline_candle_analysis.py
git commit -m "Add offline Chapter 1 candle analysis"
```

---

### Task 3: Deformation-Aware Offline Isolated Scan (Test B)

**Files:**

- Create: `trading/analysis/isolated.py`
- Create: `tests/test_offline_isolated.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class IsolatedPointScan:
    recognitions: tuple[IsolatedPointRecognition, ...]
    unresolved_potential: IsolatedPoint | None


def find_isolated_point_recognitions(
    candles: Sequence[Candle],
    *,
    start_index: int = 0,
) -> IsolatedPointScan: ...
```

- [ ] **Step 1: Write the exact batch-scanner tests**

Use midpoint-body candles with `(high, low)` pairs:

```python
[(10, 5), (12, 7), (11, 6), (13, 8), (13, 9),
 (15, 10), (15, 8), (12, 7)]
```

This sequence must produce strict HIGH index 1, strict LOW index 2,
`RIGHT_INSIDE_BAR` HIGH index 3, reject the equal-high/non-inside candidate at
index 5, and retain the right-edge LOW potential at index 7. With
`start_index=100`, assert recognitions at 101/102/103 and unresolved potential
at 107 with all kind/status/price/basis values translated exactly. Assert
chronological output, no pre-suppression, empty/one-candle neutral scans, and
that `replace_with_more_extreme_point()` still has its existing separate
equality behavior.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_offline_isolated.py -v
```

Expected: normal failures because the batch scan is missing.

- [ ] **Step 3: Implement as a tracker adapter**

Feed each candle to one existing `DeformationAwareIsolatedPointTracker`.
Collect only emitted `IsolatedPointRecognition` objects. Track the latest raw
`POTENTIAL`; clear it when its next-candle confirmation/rejection is processed,
then replace it with any new potential emitted on that candle. Translate local
indexes by `start_index` using new immutable `IsolatedPoint`/
`IsolatedPointRecognition` values without changing other fields. Do not copy
strict or deformation formulas.

```python
for candle in candles:
    changes = tracker.add_candle(candle)
    pending = None
    for change in changes:
        if isinstance(change, IsolatedPointRecognition):
            recognitions.append(_offset_recognition(change, start_index))
        else:
            pending = _offset_point(change, start_index)
```

- [ ] **Step 4: Run GREEN and recognition regressions**

```bash
pytest tests/test_offline_isolated.py -v
pytest tests/test_isolated_points.py tests/test_isolated_point_deformations.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/analysis/isolated.py tests/test_offline_isolated.py
git commit -m "Add offline deformation-aware isolated scan"
```

---

### Task 4: Pure Structural Hierarchy Composition (Test C)

**Files:**

- Create: `trading/analysis/hierarchy.py`
- Create: `tests/test_offline_hierarchy.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class StructuralHierarchy:
    isolated: IsolatedPointScan
    short_term: ShortTermStructure
    medium_term: MediumTermStructure
    long_term: LongTermStructure


def build_structural_hierarchy(
    isolated: IsolatedPointScan,
) -> StructuralHierarchy: ...
```

- [ ] **Step 1: Write pure supplied-recognition tests**

Build `IsolatedPointRecognition` fixtures directly; do not run raw candle
recognition. Reuse the proven alternating high/low prices:

```python
high_prices = [100, 110, 105, 120, 107, 115, 100]
low_prices = [90, 95, 80, 96, 85, 97, 70]
```

Assign consecutive absolute indexes, mark one high `RIGHT_INSIDE_BAR`, and the
rest `STRICT`. Assert all recognitions map through
`short_term_point_from_recognition`, medium vertices have prices
`[110, 80, 120, 85, 115]`, the long HIGH pivots at 120 and is confirmed by
115, and exact recognition/pivot/confirmer object provenance survives.

Add reviewed subcases:

- `LOW 90@1, HIGH 108@2, HIGH 110@3, HIGH 109@4, LOW 95@5` keeps all short points, uses HIGH 110, and suppresses 108/109 as consecutive same-kind;
- `HIGH 110@1, LOW 100@2, HIGH 108@3, LOW 102@4` suppresses the later inclusive inside pair;
- exact equal-extreme ties keep the earliest vertex;
- right-edge high/low candidates remain medium/long potentials where the existing builders produce them;
- suppressed lower points never become promotion neighbors.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_offline_hierarchy.py -v
```

Expected: collected failures because `StructuralHierarchy` composition is
missing.

- [ ] **Step 3: Implement the four-call pipeline**

```python
short_points = tuple(
    short_term_point_from_recognition(item)
    for item in isolated.recognitions
)
short_term = build_short_term_structure(short_points)
medium_term = build_medium_term_structure(short_term)
long_term = build_long_term_structure(medium_term)
return StructuralHierarchy(isolated, short_term, medium_term, long_term)
```

Do not create a generic recursive abstraction and do not feed potentials or
suppressed points upward.

- [ ] **Step 4: Run GREEN and hierarchy regressions**

```bash
pytest tests/test_offline_hierarchy.py -v
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
pytest tests/test_long_term_structure.py tests/test_long_term_structure_integration.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/analysis/hierarchy.py tests/test_offline_hierarchy.py
git commit -m "Add offline structural hierarchy composition"
```

---

### Task 5: Objective Public Offline Facade (Test D)

**Files:**

- Create: `trading/analysis/offline.py`
- Create: `tests/test_offline_analysis.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class OfflineMarketAnalysis:
    window: OfflineMarketWindow
    candles: tuple[OfflineCandleResult, ...]
    hierarchy: StructuralHierarchy
    segment: SegmentAnalysisResult | None


def analyze_market_window(
    window: OfflineMarketWindow,
    segment: SegmentAnalysisRequest | None = None,
) -> OfflineMarketAnalysis: ...
```

`SegmentAnalysisResult` is introduced in Task 6. During Task 5, accept only
`segment=None` and raise `NotImplementedError` for a supplied request so no
partial market semantics are invented.

- [ ] **Step 1: Write the objective bridge tests**

Create the exact raw OHLC bridge with midpoint open/close bodies:

```python
HIGH_LOW = [
    (96, 95), (100, 99), (91, 90), (110, 109), (96, 95),
    (105, 104), (81, 80), (120, 119), (120, 119.2),
    (97, 96), (107, 106), (86, 85), (115, 114),
    (98, 97), (100, 99), (71, 70), (80, 79),
]
```

Use UTC minute timestamps, `start_index=40`, `instrument="MNQ"`, and
`timeframe="1m"`. Assert dense per-candle indexes 40-56, objective OHLC-only
analysis for every candle, a deformation-aware confirmation at local index 7
(absolute 47), the exact short point prices from Task 4, medium prices
`[110, 80, 120, 85, 115]`, and the long 120 HIGH with nested provenance.
Assert `analysis.segment is None`; patch `classify_market_state`,
`evaluate_bms`, and `evaluate_sms` to fail if called.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_offline_analysis.py -v
```

Expected: normal failure because the facade is missing.

- [ ] **Step 3: Implement objective orchestration only**

Adapt every observation with `analyze_closed_candle`, pass the resulting
`Candle` sequence to `find_isolated_point_recognitions(start_index=...)`, then
call `build_structural_hierarchy`. Preserve the original validated window.
Do not infer a segment or classify the full window.

```python
candles = tuple(
    analyze_closed_candle(item, index=window.start_index + offset)
    for offset, item in enumerate(window.candles)
)
scan = find_isolated_point_recognitions(
    tuple(item.candle for item in candles),
    start_index=window.start_index,
)
hierarchy = build_structural_hierarchy(scan)
```

- [ ] **Step 4: Run GREEN and bridge regressions**

```bash
pytest tests/test_offline_analysis.py -v
pytest tests/test_offline_candle_analysis.py tests/test_offline_isolated.py tests/test_offline_hierarchy.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/analysis/offline.py tests/test_offline_analysis.py
git commit -m "Add objective offline market analysis facade"
```

---

### Task 6: Selected-Level Resolution and Market-State Availability (Test E)

**Files:**

- Create: `trading/analysis/segments.py`
- Create: `tests/test_offline_segments.py`
- Modify: `trading/analysis/offline.py`

**Interfaces:**

```python
def select_canonical_vertices(
    hierarchy: StructuralHierarchy,
    level: StructuralLevel,
) -> tuple[ResolvedStructurePoint, ...]: ...


def evaluate_selected_segment(
    window: OfflineMarketWindow,
    hierarchy: StructuralHierarchy,
    request: SegmentAnalysisRequest,
) -> SegmentAnalysisResult: ...
```

`ResolvedStructurePoint` and `SegmentAnalysisResult` are the immutable records
created in Task 1; Task 6 implements their population in `segments.py`.

- [ ] **Step 1: Write selected-level and sufficiency tests**

Construct small hierarchy records directly. For SHORT use canonical vertices:

```python
[
    ShortTermPoint(0, HIGH, 100.0, STRICT),
    ShortTermPoint(1, LOW, 90.0, STRICT),
    ShortTermPoint(2, HIGH, 110.0, STRICT),
    ShortTermPoint(3, LOW, 95.0, STRICT),
    ShortTermPoint(4, HIGH, 120.0, STRICT),
]
```

Assert `MarketSegment(0, 4)` is `UPTREND`, a mirrored
`HIGH 120, LOW 100, HIGH 110, LOW 90` sequence is `DOWNTREND`, and
`HIGH 110, LOW 90, HIGH 105, LOW 95` is `NON_TREND`. A sequence with two
HIGHs but one LOW must return `UNAVAILABLE / INSUFFICIENT_STRUCTURE` and a
monkeypatched `classify_market_state` must remain uncalled.

For SHORT, MEDIUM, and LONG, assert exact mapping to `.vertices`, using
`pivot_index` for medium/long and retaining the exact source object. Add a
suppressed/non-vertex point with a tempting matching index and prove it is not
selected. Verify caller order is retained, not sorted.

Assert a segment outside `window.start_index .. start_index + len(candles)-1`
raises `ValueError` and is never clamped. Assert an in-window request with no
BMS/SMS returns both optional fields as `None`.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_offline_segments.py -k "level or market_state or insufficient or segment" -v
```

Expected: collected assertions fail because level resolution and high-level
availability are missing.

- [ ] **Step 3: Implement canonical selection and market-state gating**

Map `SHORT -> short_term.vertices`, `MEDIUM -> medium_term.vertices`, and
`LONG -> long_term.vertices`. Convert kinds mechanically to
`StructurePointKind`, include only pivot indexes within the inclusive segment,
and preserve `ResolvedStructurePoint.source_vertex`. Count kinds before
calling `classify_market_state`; return unavailable if either count is below
two. Otherwise call the existing classifier with the selected chronological
`StructurePoint`s.

```python
vertices = {
    StructuralLevel.SHORT: hierarchy.short_term.vertices,
    StructuralLevel.MEDIUM: hierarchy.medium_term.vertices,
    StructuralLevel.LONG: hierarchy.long_term.vertices,
}[request.level]
if high_count < 2 or low_count < 2:
    market_state = Evaluation(
        EvaluationStatus.UNAVAILABLE,
        reason=EvaluationReason.INSUFFICIENT_STRUCTURE,
    )
```

Wire `analyze_market_window(..., segment=request)` to call
`evaluate_selected_segment` after objective hierarchy construction.
If `request.bms` or `request.sms` is supplied during Task 6, leave a deliberate
`NotImplementedError` boundary so Tasks 7 and 8 receive normal behavioral RED
without fabricating an interim result.

- [ ] **Step 4: Run GREEN and Lesson 1 regressions**

```bash
pytest tests/test_offline_segments.py -k "level or market_state or insufficient or segment" -v
pytest tests/test_market_structure.py -v
pytest tests/test_course_market_structure_scenarios.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

Review explicit level/segment boundaries, selected-level `.vertices` only,
pivot inclusion, source preservation, sufficient `NON_TREND`, unavailable
insufficiency, and unchanged lower-level semantics.

```bash
git add trading/analysis/segments.py trading/analysis/offline.py tests/test_offline_segments.py
git commit -m "Add selected segment market-state analysis"
```

---

### Task 7: Selected-Level BMS Index Plumbing

**Files:**

- Modify: `trading/analysis/segments.py`
- Modify: `tests/test_offline_segments.py`

**Interfaces:** Consumes `BMSAnalysisRequest`; produces
`Evaluation[BMSResult]` through `SegmentAnalysisResult.bms`.

- [ ] **Step 1: Write BMS resolution and chronology tests**

Use the uptrend SHORT vertices from Task 6 plus a same-level pullback LOW
`105.0@6`. The parent segment is `MarketSegment(0, 4)` and request indexes are
`trend_origin=3`, `previous_extreme=4`, `pullback_extreme=6`. Provide dense
window candles through index 8.

Assert:

- high 120 touch at index 7 remains `PULLBACK_ONLY`;
- high 121 at index 8 confirms BMS at the first strict event and returns the
  exact resolved previous-extreme `StructurePoint` and event index 8;
- every candle from index 7 through the window end is passed as a dense
  `BMSObservation`, even when the terminal event is earlier;
- high 121/low 94 in one observation returns
  `INVALID / OHLC_INTRABAR_ORDER_AMBIGUOUS` and exact message
  `"OHLC cannot determine the intrabar boundary order"`;
- missing index, suppressed-only index, non-vertex `.points` index, and an
  index available only at another level each return
  `INVALID / BOUNDARY_NOT_CANONICAL_VERTEX`;
- wrong kind, invalid chronology, or parent-segment mismatch returns
  `INVALID / INVALID_CONTEXT` with the original validation message;
- insufficient or `NON_TREND` parent returns
  `UNAVAILABLE / PARENT_STATE_NOT_DIRECTIONAL` without constructing a
  `PullbackContext`;
- the mirrored downtrend case resolves and evaluates identically.

- [ ] **Step 2: Run BMS RED**

```bash
pytest tests/test_offline_segments.py -k bms -v
```

Expected: normal failures because BMS request plumbing is absent.

- [ ] **Step 3: Implement exact resolution and existing evaluator reuse**

Build an index-to-list lookup only from all selected-level canonical vertices
(not only parent-segment vertices, because the pullback is later). Require
exactly one match for each requested index. Adapt those same source vertices
to `StructurePoint`, construct `PullbackContext` with the already evaluated
directional parent state, build `BMSObservation`s from every window candle at
`pullback_extreme.index + 1` through the final dense index, and call
`evaluate_bms` unchanged.

```python
observations = tuple(
    BMSObservation(index, _candle_at(window, index))
    for index in range(pullback.point.index + 1, window_end + 1)
)
result = evaluate_bms(context, observations)
```

Catch only expected context/evaluator `ValueError`s. Map the exact dual-boundary
message to `OHLC_INTRABAR_ORDER_AMBIGUOUS`; map other context failures to
`INVALID_CONTEXT`. Do not catch programming errors broadly.
Leave the Task 6 `NotImplementedError` boundary for a supplied SMS request in
place until Task 8.

- [ ] **Step 4: Run GREEN and BMS regressions**

```bash
pytest tests/test_offline_segments.py -k bms -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_market_structure.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/analysis/segments.py tests/test_offline_segments.py
git commit -m "Add canonical BMS analysis plumbing"
```

---

### Task 8: Selected-Level SMS Index Plumbing

**Files:**

- Modify: `trading/analysis/segments.py`
- Modify: `tests/test_offline_segments.py`

**Interfaces:** Consumes `SMSAnalysisRequest`; produces
`Evaluation[SMSResult]` through `SegmentAnalysisResult.sms`.

- [ ] **Step 1: Write SMS resolution and chronology tests**

For the Task 6 uptrend segment, request `trend_extreme=4` and
`creator_point=3`. Assert:

- empty suffix returns available `PENDING`;
- low 95/high 120 exact touches do not break;
- a later low 94 confirms SMS and returns the exact resolved creator point and
  first event index;
- high 121 first returns `PARENT_CONTINUED` with the exact trend extreme;
- if later candles cross the opposite boundary, the first terminal event still
  wins;
- all suffix observations are built before evaluation so a later chronology
  defect cannot be hidden (the validated window normally makes this invariant
  automatic; spy on the evaluator to assert the complete tuple);
- high 121/low 94 in one candle maps to
  `INVALID / OHLC_INTRABAR_ORDER_AMBIGUOUS` with the exact existing message;
- suppressed/non-vertex/other-level/missing indexes map to
  `BOUNDARY_NOT_CANONICAL_VERTEX`;
- invalid kind/chronology/segment maps to `INVALID_CONTEXT`;
- unavailable/`NON_TREND` parent maps to `PARENT_STATE_NOT_DIRECTIONAL`;
- the downtrend behavior mirrors the uptrend behavior.

- [ ] **Step 2: Run SMS RED**

```bash
pytest tests/test_offline_segments.py -k sms -v
```

Expected: normal failures because SMS plumbing is absent.

- [ ] **Step 3: Implement through the existing SMS types**

Resolve both indexes uniquely from the selected-level canonical lookup,
construct `SMSContext`, derive every `SMSObservation` from
`trend_extreme.index + 1` through the final window candle, and call
`evaluate_sms`. Use the same narrow error mapping as Task 7. Do not select a
creator, infer a larger reversal, or treat `SMS_CONFIRMED` as predictive.

```python
observations = tuple(
    SMSObservation(index, _candle_at(window, index))
    for index in range(trend_extreme.point.index + 1, window_end + 1)
)
result = evaluate_sms(context, observations)
```

- [ ] **Step 4: Run GREEN and SMS/BMS regressions**

```bash
pytest tests/test_offline_segments.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/analysis/segments.py tests/test_offline_segments.py
git commit -m "Add canonical SMS analysis plumbing"
```

---

### Task 9: Timestamped Closed-OHLC CSV Adapter

**Files:**

- Create: `trading/data/ohlc_csv_loader.py`
- Create: `tests/test_ohlc_csv_loader.py`

**Interfaces:**

```python
def load_ohlc_market_window(
    path: str | Path,
    *,
    instrument: str,
    timeframe: str,
    start_index: int = 0,
    timestamp_column: str = "timestamp",
    open_column: str = "open",
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
) -> OfflineMarketWindow: ...
```

- [ ] **Step 1: Write loader tests using `tmp_path`**

Use exact rows:

```text
timestamp,open,high,low,close
2026-08-28T09:30:00.000000+00:00,100,102,99,101
2026-08-28T09:31:00.000000+00:00,101,103,100,102
```

Assert source order, timezone offsets/fractional seconds, metadata, dense start
index, and no intrabar fabrication. Test configurable columns. Reject missing
headers/cells, malformed or naive timestamps, nonnumeric/nonfinite values,
invalid OHLC geometry, duplicate/decreasing timestamps, empty data, and 251
rows with row-aware messages. Patch `sorted` or compare exact input order to
prove no sorting. Do not fill missing wall-clock minutes.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_ohlc_csv_loader.py -v
```

Expected: collected failures because the loader is absent.

- [ ] **Step 3: Implement a standard-library adapter**

Mirror the row-aware style of `trading/data/csv_loader.py`: `csv.DictReader`,
`datetime.fromisoformat`, `float`, then `ClosedCandleObservation` and finally
`OfflineMarketWindow`. Preserve rows exactly and let model validation enforce
chronology/geometry/limits. Wrap validation errors with the row number without
weakening their messages.

```python
observation = ClosedCandleObservation(
    timestamp=datetime.fromisoformat(timestamp_text.strip()),
    open=float(row[open_column]),
    high=float(row[high_column]),
    low=float(row[low_column]),
    close=float(row[close_column]),
)
observations.append(observation)
```

- [ ] **Step 4: Run GREEN and data regressions**

```bash
pytest tests/test_ohlc_csv_loader.py -v
pytest tests/test_csv_loader.py tests/test_market_data.py tests/test_offline_models.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/data/ohlc_csv_loader.py tests/test_ohlc_csv_loader.py
git commit -m "Add timestamped OHLC CSV loader"
```

---

### Task 10: Versioned Ground Truth and SHA-256 Source Binding

**Files:**

- Create: `trading/validation/__init__.py`
- Create: `trading/validation/ground_truth.py`
- Create: `tests/test_validation_ground_truth.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class GroundTruthSource:
    market_data_file: str
    sha256: str
    instrument: str
    timeframe: str
    start_index: int
    candle_count: int


@dataclass(frozen=True)
class ExpectedPoint:
    index: int
    kind: IsolatedPointKind
    price: float
    recognition_basis: IsolatedPointBasis | None = None
    confirmed_by_index: int | None = None


@dataclass(frozen=True)
class ExpectedPotential:
    previous_index: int
    pivot_index: int
    kind: IsolatedPointKind
    price: float


@dataclass(frozen=True)
class ExpectedSuppression:
    point: ExpectedPoint
    reason: (
        ShortTermSuppressionReason
        | MediumTermSuppressionReason
        | LongTermSuppressionReason
    )


@dataclass(frozen=True)
class ExpectedStructure:
    points: tuple[ExpectedPoint, ...]
    potentials: tuple[ExpectedPotential, ...]
    vertices: tuple[ExpectedPoint, ...]
    suppressed: tuple[ExpectedSuppression, ...]


@dataclass(frozen=True)
class ExpectedGeometry:
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    open_position: float
    close_position: float


@dataclass(frozen=True)
class ExpectedControl:
    buyer_control: float
    seller_control: float
    buyer_control_ratio: float
    seller_control_ratio: float
    control_score: float


@dataclass(frozen=True)
class ExpectedPriceLeg:
    side: MovementSide
    start_price: float
    end_price: float
    distance: float


@dataclass(frozen=True)
class ExpectedMovementSummary:
    first_side: MovementSide | None
    first_distance: float
    final_side: MovementSide | None
    final_distance: float
    largest_buyer_move: float
    largest_seller_move: float
    total_buyer_movement: float
    total_seller_movement: float
    final_retracement_ratio: float | None


@dataclass(frozen=True)
class ExpectedExtremePath:
    order: ExtremeOrder
    legs: tuple[ExpectedPriceLeg, ...]


@dataclass(frozen=True)
class ExpectedExtremeEvidence:
    order: ExtremeOrder
    initial_side: MovementSide | None
    initial_distance: float
    initial_ratio: float
    main_side: MovementSide | None
    main_distance: float
    main_ratio: float
    final_side: MovementSide | None
    final_distance: float
    final_ratio: float
    signed_displacement: float
    displacement_ratio: float


@dataclass(frozen=True)
class ExpectedFeatures:
    side: CandleSide
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    open_position: float
    close_position: float
    control_score: float
    extreme_order: ExtremeOrder
    initial_side: MovementSide | None
    initial_ratio: float
    final_side: MovementSide | None
    final_ratio: float
    displacement_ratio: float
    total_buyer_movement_ratio: float
    total_seller_movement_ratio: float


@dataclass(frozen=True)
class ExpectedChapter1Candle:
    index: int
    side: CandleSide
    geometry: ExpectedGeometry
    control: ExpectedControl
    intrabar_status: EvaluationStatus
    intrabar_reason: EvaluationReason | None
    legs: tuple[ExpectedPriceLeg, ...] | None
    movements: ExpectedMovementSummary | None
    extreme_path: ExpectedExtremePath | None
    extreme_evidence: ExpectedExtremeEvidence | None
    features: ExpectedFeatures | None
    candle_type_status: EvaluationStatus
    candle_type_reason: EvaluationReason | None


@dataclass(frozen=True)
class ExpectedMarketState:
    status: EvaluationStatus
    reason: EvaluationReason | None
    value: MarketState | None


@dataclass(frozen=True)
class ExpectedBMS:
    status: EvaluationStatus
    reason: EvaluationReason | None
    value: PullbackStructureStatus | None
    broken_point_index: int | None
    breakout_index: int | None


@dataclass(frozen=True)
class ExpectedSMS:
    status: EvaluationStatus
    reason: EvaluationReason | None
    value: SMSStructureStatus | None
    broken_point_index: int | None
    event_index: int | None


@dataclass(frozen=True)
class ExpectedSegment:
    start_index: int
    end_index: int
    level: StructuralLevel
    market_state: ExpectedMarketState
    bms_request: BMSAnalysisRequest | None
    bms: ExpectedBMS | None
    sms_request: SMSAnalysisRequest | None
    sms: ExpectedSMS | None


@dataclass(frozen=True)
class GroundTruthAmbiguity:
    layer: str
    item: str
    note: str


@dataclass(frozen=True)
class GroundTruthCase:
    schema_version: int
    case_id: str
    source: GroundTruthSource
    chapter1: tuple[ExpectedChapter1Candle, ...]
    isolated: tuple[ExpectedPoint, ...]
    short_term: ExpectedStructure
    medium_term: ExpectedStructure
    long_term: ExpectedStructure
    segment: ExpectedSegment | None
    ambiguities: tuple[GroundTruthAmbiguity, ...]


def sha256_file(path: str | Path) -> str: ...
def load_ground_truth(path: str | Path) -> GroundTruthCase: ...
def verify_ground_truth_source(
    case: GroundTruthCase,
    market_data_path: str | Path,
) -> None: ...
```

- [ ] **Step 1: Write schema and binding tests**

Use a complete version-1 JSON in `tmp_path` with all nested collections,
one exact Chapter 1 candle record (geometry/control plus intrabar legs,
movement/extreme evidence/features and uncalibrated candle-type capability),
STRICT and RIGHT_INSIDE_BAR isolated bases, short suppressions, medium/long
potentials and confirmer provenance, optional typed segment requests/results,
and a predeclared ambiguity. Assert typed immutable parsing and stable tuple
order.

Assert rejection before scoring for schema version other than 1, missing keys,
unknown structural level/kind/basis/suppression/status/reason values,
non-finite price, duplicate case identity fields where relevant, malformed
provenance, and malformed ambiguity. Hash exact CSV bytes, verify a matching
source, then change one byte and require a clear SHA-256 mismatch. Also verify
filename, instrument, timeframe, start index, and candle count are retained;
the analyzer must not be called anywhere in these parser tests.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_validation_ground_truth.py -v
```

Expected: normal assertion failures because schema loading/binding is absent.

- [ ] **Step 3: Implement strict JSON decoding and hashing**

Use explicit parsing helpers per nested record, reject booleans where integer
indexes are expected, validate finite prices and enum strings against existing
enums, and preserve document order. Do not deserialize labels into analyzer
requests except the explicitly allowed segment/level/BMS/SMS request fields.
Use streaming `hashlib.sha256()` chunks for source files.

```python
def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

- [ ] **Step 4: Run GREEN and validation-model regressions**

```bash
pytest tests/test_validation_ground_truth.py -v
pytest tests/test_offline_models.py tests/test_offline_segments.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

```bash
git add trading/validation/__init__.py trading/validation/ground_truth.py tests/test_validation_ground_truth.py
git commit -m "Add source-bound market structure ground truth"
```

---

### Task 11: Layer-Specific Exact Scoring and Real-Case Metrics

**Files:**

- Create: `trading/validation/scoring.py`
- Create: `tests/test_validation_scoring.py`

**Interfaces:**

```python
class DiscrepancyClass(Enum):
    ENGINE_FAILURE = "engine_failure"
    GROUND_TRUTH_DISAGREEMENT = "ground_truth_disagreement"
    COURSE_AMBIGUITY = "course_ambiguity"


@dataclass(frozen=True)
class DetectionMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class LayerScore:
    layer: str
    exact_match: bool
    discrepancies: tuple[str, ...]


@dataclass(frozen=True)
class ValidationReport:
    case_id: str
    source_sha256: str
    chapter1: LayerScore
    isolated_metrics: DetectionMetrics
    isolated: LayerScore
    short_term: LayerScore
    medium_term: LayerScore
    long_term: LayerScore
    segment: LayerScore | None
    outcomes: tuple[DiscrepancyClass, ...]
    ambiguities: tuple[GroundTruthAmbiguity, ...]


def score_analysis(
    analysis: OfflineMarketAnalysis,
    expected: GroundTruthCase,
    *,
    price_tolerance: float = 0.0,
) -> ValidationReport: ...


def report_engine_failure(
    expected: GroundTruthCase,
    error: BaseException,
) -> ValidationReport: ...
```

- [ ] **Step 1: Write exact deterministic and metric tests**

Create actual/expected records directly. Assert a perfect case returns exact
matches and `TP=3, FP=0, FN=0, precision=recall=F1=1.0`. Assert one missing,
one extra, and one correct point returns `TP=1, FP=1, FN=1` and all metrics
`0.5`. Point identity must include index, kind, price, and recognition basis;
a mismatch in any field is one FP plus one FN.

Assert exact ordered comparisons for:

- optional Chapter 1 expected candle measurements and capability states;
- isolated recognitions;
- short points/vertices/suppressions and exact reasons;
- medium/long points, potentials, vertices, suppressions, pivot and
  `confirmed_by_index` provenance;
- segment status/reason/state; and
- BMS/SMS status, exact broken point, and first event index.

Assert default price equality is exact. A nonzero `price_tolerance` must be
explicit, nonnegative, and applied only to price fields; order/index/kind/basis
remain exact. Include zero-denominator metric cases with deterministic 0.0 or
1.0 semantics documented by the implementation (both empty = 1.0; expected
empty/actual nonempty precision 0.0; actual empty/expected nonempty recall
0.0).

Test discrepancy classification separately:

- `report_engine_failure(expected, error)` returns `ENGINE_FAILURE` with the
  case/source identity and diagnostic error without pretending layer matches;
- valid differences are `GROUND_TRUTH_DISAGREEMENT`;
- only exact predeclared ambiguity items are reported as `COURSE_AMBIGUITY`
  and excluded from detection denominators;
- ambiguity cannot be manufactured after seeing output, and unrelated
  differences remain disagreements.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_validation_scoring.py -v
```

Expected: collected assertions fail because scoring behavior is absent.

- [ ] **Step 3: Implement transparent comparisons**

Normalize actual native records into private immutable comparison keys while
retaining exact ordered sequences for reports. Match isolated detections as a
multiset only after removing predeclared exact ambiguity identities; compute
TP/FP/FN and metrics from those remaining identities. Compare structure and
segment layers field-by-field and emit human-readable discrepancy paths such
as `medium_term.vertices[1].confirmed_by_index`. Do not invent a pass threshold
or mutate either input. `report_engine_failure` is the explicit boundary for
an analyzer/loader crash; `score_analysis` accepts only a completed
`OfflineMarketAnalysis` and must not hide exceptions as disagreements.

```python
precision = tp / (tp + fp) if tp + fp else (1.0 if fn == 0 else 0.0)
recall = tp / (tp + fn) if tp + fn else (1.0 if fp == 0 else 0.0)
f1 = (
    2 * precision * recall / (precision + recall)
    if precision + recall
    else 0.0
)
```

- [ ] **Step 4: Run GREEN and ground-truth regressions**

```bash
pytest tests/test_validation_scoring.py -v
pytest tests/test_validation_ground_truth.py -v
git diff --check
```

- [ ] **Step 5: Review and commit**

Review exactness, zero denominators, declared-before-run ambiguity isolation,
no label leakage, no hidden success threshold, and complete provenance/status
comparison.

```bash
git add trading/validation/scoring.py tests/test_validation_scoring.py
git commit -m "Add layer-specific market structure scoring"
```

---

### Task 12: Formal Deterministic Tests A-E Integration Checkpoint

**Files:**

- Create: `tests/test_offline_market_structure_integration.py`

**Interfaces:** Exercises public APIs only; adds no new production interface.

- [ ] **Step 1: Add independently named Test A-E scenarios**

Create five clearly separated test classes or named tests:

1. **Test A:** use `(100, 99, 102, 106, 110, 107, 103, 101)` to assert exact
   side, geometry, control, movements, extreme path/evidence, and features;
   also assert missing intrabar and uncalibrated candle type are explicitly
   unavailable. Do not inspect hierarchy.
2. **Test B:** use Task 3's eight-candle `(high, low)` sequence to assert
   strict confirmation, equality rejection, RIGHT_INSIDE_BAR, absolute offset,
   chronology, and the unresolved right-edge potential. Do not build medium or
   long structure.
3. **Test C:** inject the Task 4 supplied confirmed-recognition family directly
   and assert short/medium/long points, potentials, vertices, suppressions,
   cleaned promotion, and provenance without raw recognition.
4. **Test D:** run Task 5's exact 17-candle OHLC bridge through
   `analyze_market_window(window)` and assert raw OHLC -> isolated -> short ->
   medium -> long output, including the RIGHT_INSIDE_BAR source nested under
   the long point.
5. **Test E:** use explicit hand-built hierarchy/window cases from Tasks 6-8
   for uptrend, downtrend, sufficient `NON_TREND`, insufficient unavailable,
   invalid segment, noncanonical cross-level boundaries, BMS strict/touch,
   SMS strict/touch/first event, and dual-crossing ambiguity.

Keep each gate independently runnable with markers or exact names; do not use
one giant fixture whose setup couples all gates.

- [ ] **Step 2: Run the new integration checkpoint**

```bash
pytest tests/test_offline_market_structure_integration.py -v
```

Expected: all tests pass against Tasks 1-11. This task is integration
verification, not a fabricated RED step. If it exposes a genuine approved
production defect, preserve the failing test as RED, make the minimum fix in
the owning module, rerun focused and adjacent suites, create a narrow fix
commit, and record review/re-review in the ledger.

- [ ] **Step 3: Run each gate independently**

```bash
pytest tests/test_offline_market_structure_integration.py -k test_a -v
pytest tests/test_offline_market_structure_integration.py -k test_b -v
pytest tests/test_offline_market_structure_integration.py -k test_c -v
pytest tests/test_offline_market_structure_integration.py -k test_d -v
pytest tests/test_offline_market_structure_integration.py -k test_e -v
git diff --check
```

- [ ] **Step 4: Review and commit**

Review diagnostic independence, exact fixture expectations, absence of
automatic context selection, and that this is not a replacement for existing
Chapter 1/2 unit tests.

```bash
git add tests/test_offline_market_structure_integration.py
git commit -m "Add deterministic offline validation checkpoint"
```

---

### Task 13: Blind Real-Historical Validation Workflow Support (Test F)

**Files:**

- Create: `tests/test_blind_validation_workflow.py`

**Interfaces:** Demonstrates the existing loader, analyzer, ground-truth
loader/source verifier, and scorer in the approved blind order; adds no market
algorithm or downloader.

- [ ] **Step 1: Write a reproducible workflow test with temporary files**

The test must make the separation mechanically visible:

```python
window = load_ohlc_market_window(
    market_path,
    instrument="MNQ",
    timeframe="1m",
    start_index=0,
)
analysis = analyze_market_window(window, explicit_request)

# Expected labels are loaded only after analyzer output exists.
truth = load_ground_truth(ground_truth_path)
verify_ground_truth_source(truth, market_path)
report = score_analysis(analysis, truth)
```

Use a deterministic small test CSV only to validate tooling and call order;
name the case `workflow-fixture`, not a real MNQ result. Assert changing one
market-data byte invalidates the label binding. Spy on `analyze_market_window`
arguments to prove no expected label, expected point sequence, or ambiguity is
passed into it. Assert a reproducible report contains case ID, source hash,
layer scores, raw metrics, and predeclared ambiguities.

The test and module docstring must record the first actual checkpoint procedure:

- multiple independently selected MNQ 1-minute windows, then 5-minute windows;
- no more than 250 completed timezone-aware OHLC candles per window;
- freeze and SHA-256 hash the source before annotation/scoring;
- human review of the exact same range in TradingView;
- analyzer input limited to market data, metadata, explicit segment/level,
  and explicit BMS/SMS indexes;
- ground truth loaded only after analysis;
- no cherry-picking successful windows;
- separate ordered NinjaTrader tick/trade export through the existing Chapter
  1 path when intrabar validation is required; and
- no broker/order integration.

- [ ] **Step 2: Run Test F tooling**

```bash
pytest tests/test_blind_validation_workflow.py -v
```

Expected: PASS. This verifies tooling, not actual market accuracy and not a
claim that real MNQ data was acquired.

- [ ] **Step 3: Run the entire new validation surface**

```bash
pytest tests/test_offline_models.py tests/test_offline_candle_analysis.py tests/test_offline_isolated.py tests/test_offline_hierarchy.py tests/test_offline_analysis.py tests/test_offline_segments.py tests/test_ohlc_csv_loader.py tests/test_validation_ground_truth.py tests/test_validation_scoring.py tests/test_offline_market_structure_integration.py tests/test_blind_validation_workflow.py -v
git diff --check
```

- [ ] **Step 4: Review and commit**

Review label isolation, source binding, no real-data claims, no network/data
download, no TradingView/NinjaTrader scraping or execution, and the explicit
MNQ 1m -> 5m handoff.

```bash
git add tests/test_blind_validation_workflow.py
git commit -m "Add blind historical validation workflow coverage"
```

---

### Task 14: Full Regression, Scope, and Completion Gate

**Files:** Verify all eleven planned production files and eleven planned test
files. Do not create a verification-only commit.

- [ ] **Step 1: Run all new focused tests**

```bash
pytest tests/test_offline_models.py tests/test_offline_candle_analysis.py tests/test_offline_isolated.py tests/test_offline_hierarchy.py tests/test_offline_analysis.py tests/test_offline_segments.py tests/test_ohlc_csv_loader.py tests/test_validation_ground_truth.py tests/test_validation_scoring.py tests/test_offline_market_structure_integration.py tests/test_blind_validation_workflow.py -v
```

- [ ] **Step 2: Run Chapter 1 regressions**

```bash
pytest tests/test_candles.py tests/test_controls.py tests/test_analysis.py tests/test_movements.py tests/test_movement_summaries.py tests/test_extremes.py tests/test_extreme_evidence.py tests/test_features.py tests/test_dataset.py tests/test_market_data.py tests/test_csv_loader.py tests/test_isolated_points.py tests/test_isolated_point_deformations.py tests/test_key_levels.py tests/test_key_level_replacement.py -v
```

- [ ] **Step 3: Run Chapter 2 level regressions**

```bash
pytest tests/test_short_term_structure.py tests/test_short_term_structure_integration.py -v
pytest tests/test_medium_term_structure.py tests/test_medium_term_structure_integration.py -v
pytest tests/test_long_term_structure.py tests/test_long_term_structure_integration.py -v
```

- [ ] **Step 4: Run market-state, BMS, SMS, and formal Level-2 regressions**

```bash
pytest tests/test_market_structure.py -v
pytest tests/test_pullback_structure.py tests/test_pullback_structure_integration.py -v
pytest tests/test_sms_structure.py tests/test_sms_structure_integration.py -v
pytest tests/test_course_market_structure_scenarios.py -v
```

- [ ] **Step 5: Run complete repository verification**

```bash
pytest -q
git diff --check
```

Record the actual final count. Do not compare it to a hard-coded 464 or any
other predicted number.

- [ ] **Step 6: Verify scope against the immutable implementation base**

```bash
git fetch origin main
git rev-parse origin/main
git diff --name-only origin/main...HEAD
git log --oneline origin/main..HEAD
git status --short
```

If `origin/main` moved from the base recorded at kickoff, stop and report the
divergence. Do not silently redefine the base, rebase, merge, or force. The
expected diff is exactly the eleven production files and eleven test files
listed in Planned File Structure.

- [ ] **Step 7: Inspect forbidden behavior and duplication**

```bash
git grep -n -E "classify_candle|known_at_index|confirmed_at_index|timeframe.*StructuralLevel|auto.*segment|auto.*level|auto.*creator|auto.*extreme|strategy|signal|entry|exit|stop.loss|risk|position.siz|leverage|broker|order|execution|Chapter 3" -- trading/analysis trading/data/ohlc_csv_loader.py trading/validation
git grep -n -E "def (get_geometry|get_control|get_price_legs|get_extreme_path|classify_market_state|evaluate_bms|evaluate_sms|build_short_term_structure|build_medium_term_structure|build_long_term_structure)" -- trading/analysis trading/validation trading/data/ohlc_csv_loader.py
```

Expected: no copied algorithm definitions, classifier call, automatic context
selection, timeframe mapping, realtime timing, strategy/execution, or Chapter
3 behavior. Legitimate imports/calls to authoritative functions are expected.

- [ ] **Step 8: Perform the broad final whole-branch review**

Dispatch the most capable reviewer against the approved spec, this plan, and
the complete feature diff. Require explicit review of:

- immutable window/evaluation invariants and exact status/reason contract;
- no sorting/truncation/path fabrication;
- OHLC-only availability and intrabar/candle-type unavailability;
- tracker reuse, absolute indexes, bases, and unresolved edge potential;
- exact recognition -> short -> medium -> long composition and provenance;
- no implicit segment/level selection;
- canonical selected-level vertices only and pivot-index inclusion;
- insufficiency versus sufficient `NON_TREND`;
- unique BMS/SMS canonical index resolution and complete dense suffixes;
- existing strict/touch/first-event/OHLC ambiguity behavior;
- strict OHLC CSV parsing without fill/resample/interpolation;
- versioned JSON, source hash, and no label leakage;
- exact deterministic scoring and separated failure/disagreement/ambiguity;
- independently diagnosable Tests A-F; and
- absence of live, predictive, strategy, execution, and Chapter 3 scope.

Fix every valid Critical or Important finding with RED -> GREEN TDD, create a
coherent fix commit, run scoped re-review, rerun affected suites and
`pytest -q`, then repeat `git diff --check`.

- [ ] **Step 9: Push the reviewed feature branch only**

```bash
git push -u origin feature/offline-market-analysis
```

Do not merge, squash, push implementation commits to `origin/main`, acquire
real data, or start Chapter 3.

---

## Deterministic Fixture Register

| Fixture | Exact input | Responsibility |
| --- | --- | --- |
| A | intrabar `(100, 99, 102, 106, 110, 107, 103, 101)` plus bearish/doji/flat subcases | Exact Chapter 1 OHLC, side, geometry, control, movement, extremes, features, and unavailable capabilities |
| B | `(high, low)` sequence `[(10,5),(12,7),(11,6),(13,8),(13,9),(15,10),(15,8),(12,7)]` | Strict HIGH/LOW, RIGHT_INSIDE_BAR HIGH, equality rejection, chronology, absolute offset, right-edge potential |
| C1 | supplied highs `[100,110,105,120,107,115,100]`, lows `[90,95,80,96,85,97,70]` | Pure short -> medium `[110,80,120,85,115]` -> long HIGH 120 composition and provenance |
| C2 | `LOW 90@1, HIGH 108@2, HIGH 110@3, HIGH 109@4, LOW 95@5` | Same-kind suppression, earliest ties in variants, all-points preservation |
| C3 | `HIGH 110@1, LOW 100@2, HIGH 108@3, LOW 102@4` and one-side-break variants | Inclusive inside suppression versus preservation |
| D | 17 OHLC ranges from Task 5 | Raw OHLC through deformation-aware isolated recognition and all three structural levels |
| E-up | `H100@0,L90@1,H110@2,L95@3,H120@4`, optional pullback `L105@6` | UPTREND, BMS/SMS canonical boundaries, touch/strict/first-event/ambiguity |
| E-down | `H120@0,L100@1,H110@2,L90@3` | Mirrored DOWNTREND and boundary evaluation |
| E-non | `H110@0,L90@1,H105@2,L95@3` | Sufficient NON_TREND |
| E-insufficient | `H100@0,L90@1,H110@2` | UNAVAILABLE / INSUFFICIENT_STRUCTURE without lower classifier call |

All fixture expectations must be authored before running the corresponding
facade/scorer. If an exact numeric fixture does not produce the documented
existing-definition output, treat that as a fixture review finding and correct
the plan fixture/test before changing authoritative market rules.

## Spec Coverage Map

| Approved responsibility | Planned coverage |
| --- | --- |
| Immutable 1-250 closed window, OHLC/intrabar validation, dense indexes | Task 1 |
| OHLC-only Chapter 1 output and intrabar feature composition | Task 2 / Test A |
| Explicit uncalibrated candle type without classifier call | Task 2 / Test A |
| Strict + RIGHT_INSIDE_BAR batch scan, offset, edge potential | Task 3 / Test B |
| Confirmed recognition -> short -> medium -> long | Task 4 / Test C |
| Points/vertices/suppressions/potentials/provenance preserved | Tasks 4, 10, 11, 12 |
| Raw OHLC objective facade and no implicit segment | Task 5 / Test D |
| Explicit SHORT/MEDIUM/LONG canonical vertex selection | Task 6 / Test E |
| Segment bounds and pivot-index retrospective inclusion | Task 6 |
| Insufficient unavailable versus sufficient NON_TREND | Task 6 / Test E |
| Caller-supplied BMS indexes and dense existing evaluation | Task 7 / Test E |
| Caller-supplied SMS indexes and dense existing evaluation | Task 8 / Test E |
| Exact OHLC ambiguity propagation | Tasks 7-8 / Test E |
| Generic timestamped OHLC CSV | Task 9 |
| Versioned JSON and SHA-256 source binding | Task 10 |
| Exact layer scoring and TP/FP/FN/precision/recall/F1 | Task 11 |
| Engine failure / disagreement / predeclared ambiguity separation | Task 11 |
| Independently diagnosable A-E checkpoint | Task 12 |
| Real blind Test F tooling and MNQ handoff | Task 13 |
| Existing Chapter 1/2 semantics and Level-2 suite preserved | Task 14 |
| No automatic context, live timing, strategy, execution, or Chapter 3 | Global constraints and Task 14 |

## Final Review and Execution Handoff

The future implementation is ready for independent review only when:

1. the feature worktree was created from the approved plan checkpoint and its
   SHA is recorded in the SDD ledger;
2. Tasks 1-13 each have complete TDD/review evidence and focused commits;
3. Tests A-F tooling remain independently runnable and real Test F is not
   misrepresented as completed market validation;
4. every existing Chapter 1/2 suite, including
   `tests/test_course_market_structure_scenarios.py`, and full `pytest -q`
   pass with a fresh recorded count;
5. `git diff --check`, scope inspection, and the forbidden-behavior scan pass;
6. final whole-branch review has no unresolved Critical or Important finding;
7. the worktree is clean and only the reviewed feature branch is pushed; and
8. execution stops without merging, acquiring/cherry-picking real results, or
   starting Chapter 3.
