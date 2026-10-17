# Chapter 3, Lesson 1 — 认识交易区间（1-3-1）

## Scope and source

This lesson adds a small course-knowledge component to Trading System V1.
It does not define a strategy. Development starts at the preserved Chapter 2
checkpoint `164f438ec9339fff483dd9f0f9ceb486982cc963`, on the separate
`codex/chapter3-lesson1` worktree branch.

**Source reconciliation completed on 2026-10-17 for the supplied transcript
and all 17 screenshot slides. The original MP4 frames and audio were not
independently reviewed.** Earlier summary-only and user-reported slide
references are superseded by direct inspection of the following originals in
the user-specified Chapter 3 course folder, outside this repository:

| Actual source | Verification |
| --- | --- |
| `slides/Chapter 3_part1_认识交易区间.pptx` | 24,858,276 bytes; SHA-256 `88ed64c61e6f3a6bc5847f31d5d54e55c5cfdb124aa6438e40fa3e453451c906`; 17 slides in presentation order. All 17 embedded PNG screenshots were visually inspected, including charts and handwritten marks; slide 1 also has a native chapter/part title. |
| `第3章（交易区间）第1讲：认识交易区间（1-3-1） (1).txt` | 20,385 bytes; SHA-256 `6c6b7382ddb6c50a00c83f7eb599d7cc77e5388dfb2ca9422ac1dfd14c3d635b`; complete Chinese text read from opening through closing/homework. It identifies itself as a TurboScribe transcription and supplies one coarse `(0:01 - 19:51)` interval. |

Slide numbers below refer to positions in this actual 17-slide PPTX collection,
not inferred video frame numbers. Screenshots were read directly from their
embedded image bytes; no chart geometry was reconstructed from slide text.
The transcription has recognition errors and some inconsistent wording; it
is not an independently verified record of the MP4 audio. No precise per-slide
audio timestamps or missing video frames are claimed.

This pass changes documentation only. No demonstrated contradiction requires
a production-code or test change. Reconciliation of the supplied evidence is
complete; subjective definitions remain unresolved as stated below.

Chapter 2's published `COHORT_PASS` and 812/812 comparisons are preserved
historical results, read from checkpoint metadata, not new validation claims.
No historical cohort validation is repeated here.

## Verified slide and transcript inventory

| Slide | Visually verified content | Consequence for this component |
| --- | --- | --- |
| 1 | Textbook definition: price oscillates inside a range, with resistance above and support below. | Keep both explicit boundary roles; no OHLC-only automatic selection. |
| 2 | Ordinary-range schematic, including an excursion above resistance, horizontal/no clear inclination description, and the instructor's 80% failure/continuation claim. | Allow externally judged failed penetrations; the percentage is not an approved statistical input. |
| 3 | Two blue-box candle-chart range examples, including later movement outside the boxes. | Examples, not a deterministic box-fitting or forecasting algorithm. |
| 4 | Sloping-range schematic with handwritten emphasis on inclination and slightly stronger side; excessive inclination may be treated as a trend channel. | Retain an external type label; no accepted slope/time threshold. |
| 5 | Sloping candle-chart example inside a tilted blue area. | No automatic channel/range classification or fitted boundary. |
| 6 | Narrow-range schematic, market-dependent 1%–3% wording, high breakout-failure claim and “超过连续3根十字星” wording. | No universal width cutoff or exact doji-count classifier. |
| 7 | Narrow-range candle charts with blue boxes and a hand-circled/arrowed doji cluster. | Confirms the visual illustration; contextual doji and the exact count remain undefined. |
| 8 | Hand-drawn rising-entry example: upper reaction, lower reaction, return to upper, then a circled revisit to the lower boundary. Upper annotations count attempts; other 1/2 labels identify boundaries. Several upper return paths are sketched. | With the transcript, distinguishes three-point potential evidence from the fourth unsuccessful validation; a circled arrival alone is not failure proof. |
| 9 | Hand-drawn falling-entry example with global sequence 1 lower, 2 upper, 3 lower, 4 upper and a circled 5 lower. Point 4 slightly penetrates resistance before returning. | Points 1–3 are potential; 1–4 establish two unsuccessful validations per side. Point 5 has no guaranteed breakout/failure outcome. |
| 10 | Coach's explicit definition: two unsuccessful upward attempts AND two unsuccessful downward attempts. The schematic labels each side 1/2; the second lower reaction is drawn above the support line. | Supports conditional ordinary-range confirmation and externally judged near-misses; exact contact/crossing is not required. |
| 11 | Disagreement explanation, illustrated with higher-high/higher-low and lower-high/lower-low trend diagrams. | Market explanation and existing Chapter 2 context, not a new hierarchy rule. |
| 12 | Turnover/disagreement explanation; round numbers, support/resistance and news are listed as possible locations/causes. | No participant or news inference from this annotation input. |
| 13 | Three proposed turnover pairings: smart money/retail, retail/retail, smart money/smart money, with continuation/termination descriptions. | Explanatory theory; participant identity and future direction are not observable here. |
| 14 | International/domestic institutional-loss anecdotes presented as supporting examples. | Record only their role in the explanation; the anecdotes and numbers were not independently fact-checked or made model inputs. |
| 15 | “加油站” for a trend that has not ended; “产房” for a trend about to end. | Retrospective/contextual explanation, not a prediction or trade signal. |
| 16 | “是底不反弹，反弹不是底”, two candle-chart examples, and stocking/markup-or-markdown/distribution metaphors. | No bottom detection, institutional-position inference or execution logic. |
| 17 | “拥抱交易区间” message with Great Wall beacon-tower and highway-service-area illustrations. | Learning perspective, not executable behavior. |

The complete transcript additionally explicitly identifies ranges with
nontrend in ordinary course language; explains drawing horizontal boundaries
through as many relevant body/wick contacts as practical; distinguishes three
known turning points from the still-awaited fourth; permits a near-miss or
small false penetration in a validation; and cautions that participant turnover
cannot be identified from the chart in advance. Its opening question about
all ranges being pullbacks is described as beyond this lesson, and its closing
assignment requests lesson notes. These passages add no deterministic detector,
trade-entry rule, or approved empirical probability.

## Source-to-implementation reconciliation

| Current contract | Actual evidence | Reconciliation result |
| --- | --- | --- |
| `POTENTIAL`: at least three externally relevant reactions covering both sides | Slides 8–9 and the transcript's explanation that points 1–3 can be treated as potential before point 4 appears. | Matches the illustrated minimum. The diagrams alternate; accepting other externally qualified mixed-side ordering is a minimum-rule API allowance, not an additional illustrated course pattern. Whether/how such events are independent remains discretionary. |
| Ordinary `CONFIRMED`: at least two explicit unsuccessful attempts at each side | Slide 10's written definition, slide 9's points 1–4 and the transcript's repeated two-up/two-down explanation. | Matches conditionally on external event meaning; no entry, continuation or fifth-point outcome follows. |
| Distinct `TOUCH`, `REACTION`, `UNSUCCESSFUL_ATTEMPT` | Slide 10's lower second reaction above support; slides 2/8/9 show failed penetrations; transcript explicitly discusses not quite reaching a level and a small false break. | No demonstrated need for code changes. A bare touch is still not proof of failure; externally annotated near-misses and failed penetrations already fit. |
| Caller-selected body/wick anchors | Transcript's drawing instruction; charts in slides 3/5/7/16. | Keep annotations external. “As many as practical” does not define a fitting algorithm or require isolated-point provenance. |
| `known_at_index`, observation availability indexes, undated default | Transcript describes a provisional line followed by later validation and waiting for the fourth event; slides 8–10 are static examples. | Compatible engineering consistency safeguards, not course-taught index formulas. Neither a contact bar nor a hindsight-drawn boundary proves earlier knowledge; exact failure resolution time is not supplied by the lesson. |
| `SUCCESSFUL_ATTEMPT` makes the supplied context `UNRESOLVED` | Slide 9/transcript warn that point 5 is not guaranteed to break; no complete successful-breakout lifecycle is taught. | Conservative engineering guard, not a taught range-invalidation transition. It must not be interpreted as denying that earlier four-point formation occurred; existing evidence counts remain available. |
| Chapter 2 `NON_TREND` does not automatically populate Chapter 3 | The transcript explicitly treats nontrend/range as the same broad course concept; slide 1 also requires a support/resistance area. | Preserve the conceptual statement in the summary, while retaining the engineering requirement for explicit boundary/event evidence. No Chapter 2 state algorithm is changed. |

No literal price-equality test, obligatory raw-wick crossing, stronger ordering
requirement, probability, lookback, or boundary-fitting rule is justified by
these sources. The component remains an evaluator of externally qualified
annotations, not an independently validated automatic course-pattern detector.

## Knowledge extraction

| Category | Lesson content | Implementation consequence |
| --- | --- | --- |
| Explicit definition | A trading range oscillates between support and resistance without a clear trend. | Record explicit boundaries and labels; OHLC alone does not establish a range. |
| Explicit types | Ordinary/horizontal, sloping and narrow ranges. | Preserve the caller's type label. Do not infer slope or narrowness. |
| Conditional objective rule, slides 8–9 with transcript | Three relevant boundary reactions with evidence at both resistance and support suggest a potential range. | Count externally attested distinct reactions; three single-boundary reactions are insufficient. |
| Conditional objective rule, slide 10 and transcript | Two unsuccessful upward attempts and two unsuccessful downward attempts confirm an ordinary range. | Count explicit unsuccessful-attempt labels separately at resistance and support. |
| Discretionary drawing | Connect as many relevant candle contacts as practical; body or wick contacts may be used. | Accept caller-selected anchors. Do not optimize contacts or require isolated points. |
| Discretionary judgment | Which contacts are relevant, what counts as near, a reaction, a distinct attempt, failure or false breakout. | These meanings remain external annotations, not inferred facts. |
| Description awaiting definitions, slides 6–7 and transcript | The slides say “超过连续3根十字星”; the transcript also refers to “连续三根”. | Do not silently choose >3 or >=3, equate contextual doji with Chapter 1 exact open=close, or build a narrow-range detector. |
| Market theory | Disagreement and turnover between participants explain ranges. | No institutional/retail activity inference from OHLC. |
| Retrospective explanation | A range can precede continuation or reversal. | No forward prediction or continuation/reversal classification. |
| Empirical claims | Instructor's 80% failure and 50/50 direction statements; market-dependent narrowness percentages. | No probability, threshold or quantitative model input is approved. |
| Deferred definitions | Boundary selection, slope, narrowness, breakout success/failure, invalidation and later range lifecycle. | Await later course material and explicit calibration decisions. |

“Potential” does not mean confirmed. Insufficient evidence does not mean a
range is absent. Chapter 2 `NON_TREND` is a separate structural classification,
and neither a range label nor a single doji proves Chapter 3 formation.

## Reused architecture

The existing course-first pattern separates observations, labels, measurements
and interpretation. Chapter 3 follows it in
`trading/definitions/trading_ranges.py`:

- Reuse `MarketSegment` and its inclusive index bounds from Chapter 2.
- Reuse `KeyLevelKind.SUPPORT` and `RESISTANCE` for boundary roles.
- Keep existing `KeyLevel` unchanged: its documented provenance is a confirmed
  isolated point. Lesson 1 body/wick anchors need not have that provenance, so
  a `RangeBoundary` holds explicit `BoundaryAnchor` values instead.
- Leave `Candle`, geometry, `get_side`, raw candle classification and the
  canonical isolated → short → medium → long hierarchy unchanged. These remain
  useful upstream context; none supplies automatic range confirmation.
- Leave the offline analyzer, market-state outputs, BMS/SMS, validation payloads
  and all frozen scientific artifacts unchanged. The new function is an
  independently importable domain companion, not a new analyzer output field.

## Explicit input contract

`TradingRangeContext` supplies a segment, a `TradingRangeType`, an upper
resistance boundary, a lower support boundary and chronological observations.
Every boundary contains at least one finite price anchor. Anchors are caller
choices, not measurements generated by this component.

`BoundaryAnchor.index` locates the candle contact. It is **not** the time at
which the analyst selected that boundary. The optional
`TradingRangeContext.known_at_index` records when the entire supplied annotation
was actually known, including boundary selection and every supplied outcome.
It must be an integer at least as late as every anchor and observation index.
It may be later than the analyzed segment's end for retrospective annotation.

For example, anchors at candle 0 and reaction evidence known by candle 4 do
not prove that boundaries selected at candle 9 were available at candle 4.
The complete annotation must instead carry `known_at_index=9` (or a later true
knowledge time). An anchor at 9 cannot be included in an annotation claimed
known at 3. An unsuccessful attempt known at 4 likewise cannot belong to an
annotation claimed known at 3.

When omitted, `known_at_index=None` explicitly leaves historical availability
unknown; neither the first anchor, third reaction nor last attempt is silently
substituted as a boundary-selection time. The result retains this metadata in
`result.context.known_at_index`. It provides no `formed_at` timestamp. These
are caller-supplied offline annotations with lower-bound consistency checks,
not independent proof of the caller's actual knowledge time. No streaming
state, historical prefix query or automatic as-of filtering is introduced.

Ordinary boundaries must be horizontal and upper must exceed lower. Sloping
and narrow labels may retain multiple anchors; the module does not fit,
interpolate, extrapolate or certify their shape. It only rejects inverted
upper/lower anchors at shared indexes. No slope or width acceptance threshold
is introduced. A supplied label remains a supplied label after evaluation.

`BoundaryObservation` represents one distinct relevant event against these
particular boundaries. Its `index` is when the stated evidence is known,
inside the selected segment. The caller must not backdate a resolved result
to its initial touch, split one prolonged attempt into repeated events, or
reuse evidence after changing boundaries without reassessing it.

| External outcome | Counts as a relevant reaction? | Counts as an unsuccessful attempt? |
| --- | --- | --- |
| `TOUCH` | No | No |
| `REACTION` | Yes | No |
| `UNSUCCESSFUL_ATTEMPT` | Yes | Yes, on the specified boundary |
| `UNRESOLVED` | No | No |
| `SUCCESSFUL_ATTEMPT` | No | No; overall lifecycle judgment is unresolved |

A reaction is not proof of failure. A touch, wick crossing, return inside,
close or Chapter 2 BMS/SMS result is not automatically relabeled as an
unsuccessful Chapter 3 attempt. The course summary supplies no independent
mathematical failure test. **The evaluator verifies annotation counts, not the
truth of the externally supplied failure judgments.**

As verified in slides 8–10 and the transcript, a near-miss or a false penetration
may be explicitly annotated `UNSUCCESSFUL_ATTEMPT` by an external observer.
This does not require exact contact, and does not approve any automatic
near-miss distance, crossing/return rule or false-breakout classifier. Raw
price geometry is not an input to this component. The transcript describes
these as validations, without defining a numerical acceptance distance or a
complete mathematical false-break criterion.

The caller is responsible for establishing relevance and independence. The
minimum two-boundary requirement is supported by the directly inspected
examples in slides 8–9. These illustrations do not establish an exhaustive
algorithm for mandatory alternation, contact tolerance, lookback or unique
three-event ordering. Nonalternating inputs still require external relevance
and independence judgments; they are not claimed to appear in the slides.

Engineering input restrictions, not additional course discoveries:

- Anchor and observation indexes must lie inside the segment.
- Anchors and observations must be strictly chronological; input is never sorted.
- Only one distinct event per observation index is supported. Duplicate events,
  contradictory labels at the same index and same-candle upper/lower events
  are rejected. This conservative API cannot encode intrabar event order.
- Known enum values are required. Empty boundaries and nonfinite prices are invalid.
- Inputs are immutable snapshots; sequences are copied to tuples.
- A dated annotation cannot precede any supplied anchor or known outcome.
  Omitting the date leaves availability unknown; it does not date the result
  at the analyzed segment's start, end or third reaction.

## Formation evaluation

`evaluate_range_formation(context)` returns its exact input context, status,
reaction count, unsuccessful upward-attempt count and unsuccessful
downward-attempt count. Its rules, in order, are:

1. A supplied successful attempt returns `UNRESOLVED`. Lesson 1 does not provide
   the lifecycle rules needed to decide whether the range ended, changed or
   reformed. This conservative engineering status makes no invalidation claim.
2. For `ORDINARY` only, at least two explicit unsuccessful resistance attempts
   and at least two explicit unsuccessful support attempts yield `CONFIRMED`.
3. Otherwise, at least three explicit relevant reactions, including at least
   one resistance reaction and one support reaction, yield `POTENTIAL`.
4. Otherwise return `INSUFFICIENT_EVIDENCE`, never “not a range.”

Three reactions at resistance alone, or support alone, are insufficient even
if every event is externally labeled an unsuccessful attempt. A `TOUCH` on the
other side does not supply the missing reaction. Both alternating examples
verified in slides 8–9 and nonalternating upper–upper–lower / lower–lower–upper
annotations meet this minimum; the latter are permitted by the limited rule,
not presented as additional diagrams seen in the deck.

Sloping and narrow contexts cannot receive `CONFIRMED` through the ordinary
two-plus-two rule. A sufficient reaction count may support `POTENTIAL`,
conditional on the supplied label and evidence; it does not validate that label.

An unknown extra event does not erase already known formation evidence and
cannot add a failure. `CONFIRMED` means the ordinary formation counts are met
conditionally; it does not certify that a range is still active or predict
what an unresolved later event will do. There is no automatic event resolution,
live readiness, retraction, range-boundary discovery or trading decision.

Example, using only externally established failed-attempt outcomes:

```python
from trading.definitions.key_levels import KeyLevelKind as Side
from trading.definitions.market_structure import MarketSegment
from trading.definitions.trading_ranges import (
    BoundaryAnchor, BoundaryObservation, BoundaryOutcome, RangeBoundary,
    TradingRangeContext, TradingRangeType, evaluate_range_formation,
)

failed = BoundaryOutcome.UNSUCCESSFUL_ATTEMPT
context = TradingRangeContext(
    segment=MarketSegment(0, 9),
    range_type=TradingRangeType.ORDINARY,
    upper=RangeBoundary(Side.RESISTANCE, (BoundaryAnchor(0, 110),)),
    lower=RangeBoundary(Side.SUPPORT, (BoundaryAnchor(0, 100),)),
    observations=(
        BoundaryObservation(1, Side.RESISTANCE, failed),
        BoundaryObservation(2, Side.SUPPORT, failed),
        BoundaryObservation(3, Side.RESISTANCE, failed),
        BoundaryObservation(4, Side.SUPPORT, failed),
    ),
    known_at_index=4,  # Caller attests boundaries and all outcomes were known then.
)
result = evaluate_range_formation(context)
# CONFIRMED is conditional on the four supplied distinct failed-attempt labels.
```

## Verification and changed files

New synthetic tests cover the three-reaction candidate, two-plus-two ordinary
confirmation, asymmetric attempt counts, touches, unknown outcomes, supplied
labels/anchors, deferred successful-breakout lifecycle, Chapter 2 non-trend
separation, chronology, duplicate events and malformed boundaries.

### Source-only reconciliation verification (current)

- The entire specified Chinese transcript and all 17 PPTX screenshot images
  were inspected. Actual slide references and source identities are recorded
  above; the previous missing-source status is superseded.
- This pass modifies only this lesson document relative to the existing
  uncommitted worktree. Production code and tests are unchanged: no demonstrated
  source contradiction requires an executable correction. Therefore regression
  tests are not rerun for this documentation-only pass.
- The prior **50 focused / 747 course-domain passes** below are retained as
  historical verification, not represented as new test executions. The earlier
  **1461 passed / 83 failed full-suite result**, all 83 failed node IDs, and its
  raw log remain preserved. The complete suite is not claimed green.
- Reconciliation is complete for the supplied text/screenshots while the
  explicitly listed subjective definitions remain open. MP4 frames/audio
  remain independently unverified.

### Prior scoped code reconciliation (historical)

- **50 focused tests passed** in `tests/test_trading_ranges.py`.
- **747 course-domain tests passed**, including the 50 focused cases and the
  Chapter 1/2, offline-analysis, data and course-validation regressions. The
  selected file set matches the earlier 725-test scope; 22 focused cases were
  added. Legacy `mnq_`/`ninjatrader_` tool files and the repository text-policy
  file remain outside this scoped run.
- Before the production change, new tests exposed the single-boundary bug and
  missing annotation-knowledge contract (11 failures, 35 passes); four added
  malformed-knowledge-index cases also failed before implementation.
- Coverage includes three resistance-only/support-only reactions, explicitly
  failed single-side attempts, mixed-side alternating and nonalternating
  reactions, a touch on the missing side, contact versus reaction versus failed
  attempt, future-anchor/failed-evidence backdating, late boundary selection,
  exact knowledge-time bounds and explicitly undated annotations.
- The first course run reached 100% but stalled while cleaning old temporary
  repositories and was interrupted. The completed **747-pass** run used a
  fresh task-owned system-temp directory. That completed run supplies the
  result above; no success is claimed for the interrupted process.
- The earlier **1461-pass / 83-failure full-suite result is historical and
  unchanged**, with all 83 node IDs preserved below. The full suite was not
  rerun for this reconciliation and is not claimed green. The retained raw log
  SHA-256 is `101b88759ebdb26ab36a39d85f034c4e4f7f77b9eafaa029d91ebf92b8b20faa`.
- At the time of that code pass, actual source files were unavailable in the
  workspace/attachments. The subsequent source-only pass above inspected the
  user-specified originals and supersedes that earlier limitation. MP4
  frames/audio remain independently unreviewed.

Focused/course-domain reproduction from this worktree:

```powershell
$python = '../chapter3-test-env/Scripts/python.exe'
& $python -m pytest tests/test_trading_ranges.py -q
$courseTemp = Join-Path ([IO.Path]::GetTempPath()) ('tsv1-c3-reconcile-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
if (Test-Path -LiteralPath $courseTemp) { throw 'Expected a new test directory' }
$courseTestFiles = Get-ChildItem tests/test_*.py |
    Where-Object { $_.Name -notmatch '^test_(mnq_|ninjatrader_|repository_text_identity_policy)' } |
    ForEach-Object { $_.FullName }
& $python -m pytest -q @courseTestFiles --basetemp $courseTemp
```

That earlier code reconciliation edited only `trading/definitions/trading_ranges.py`,
`tests/test_trading_ranges.py` and this lesson document relative to the existing
uncommitted worktree. Earlier README/project-overview edits remain in place.
There is no Chapter 2 algorithm or frozen-artifact change, commit, merge or push.

### Original implementation verification (historical)

Original implementation verification, retained as historical results, used an
isolated CPython 3.12.14 environment and the repository's pinned
`pytest==9.1.1`, `jsonschema==4.25.1` and `tzdata==2026.2` dependencies:

- Before implementation, the new test module failed because the Chapter 3
  module did not exist; the initial focused Chapter 1/2 baseline passed 79 tests.
- Final focused Chapter 3 run: **28 passed**.
- Course-domain regression set: **725 passed**, including those 28 Chapter 3
  tests. This selects every `test_*.py` except legacy `mnq_`/`ninjatrader_` tool
  files and the separately checked repository text-policy test file.
- Independent read-only review found no actionable correctness or course
  faithfulness issues. An additional assertion checks positive evidence counts
  and preserves known formation when a later observation is unresolved.
- Byte comparison with the preserved checkout confirms **157 unchanged tracked
  files**. Only README and the project overview differ among pre-existing
  tracked files. All original code, tests and scientific artifacts are intact.
- `git -c core.whitespace=cr-at-eol diff --check` passes, honoring the two
  existing documents' CRLF convention; the preserved Chapter 2 checkout is clean.

Reproduction from this development worktree in PowerShell:

```powershell
$python = '../chapter3-test-env/Scripts/python.exe'
$env:PYTEST_DEBUG_TEMPROOT = (Resolve-Path '../chapter3-test-temp').Path
$env:PYTHONIOENCODING = 'utf-8'
# Process-local Windows Git setting; no repository/global config is changed.
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'core.longpaths'
$env:GIT_CONFIG_VALUE_0 = 'true'

& $python -m pytest tests/test_trading_ranges.py -q
$coreTestFiles = Get-ChildItem tests/test_*.py |
    Where-Object { $_.Name -notmatch '^test_(mnq_|ninjatrader_|repository_text_identity_policy)' } |
    ForEach-Object { $_.FullName }
& $python -m pytest -q @coreTestFiles
# For the legacy Git-tooling suite, use a NEW short temporary directory.
# pytest may clear --basetemp; never point it at an existing artifact directory.
$fullToolTemp = Join-Path ([IO.Path]::GetTempPath()) ('tsv1-c3-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
if (Test-Path -LiteralPath $fullToolTemp) { throw 'Expected a new test directory' }
& $python -m pytest -q --tb=short --basetemp $fullToolTemp
```

The new task-owned temporary root avoids a permission error on an old system
pytest directory, without deleting or reusing existing local artifacts. Git's
process-local long-path setting avoids some Windows `git show` filename-length
errors. The old checkpoint verifier intentionally strips `GIT_*` variables
from its subprocess environment, so that setting does not reach its internal
Git calls. Deep workspace-local fixtures can therefore fail with a misleading
"component missing from checkpoint" error caused by Windows filename length.
The representative
`test_verifies_first_class_inventory_checkpoint_from_immutable_bytes` failed
on the untouched checkpoint in the long fixture path and **passed** in a newly
generated short system-temp directory (1 passed). No verifier code or system
Git settings were changed. Use the short `--basetemp` form above when rerunning
the legacy Git-tooling suite; the original complete run used the longer path.

Known publication-checkpoint limitations were also checked directly on the
untouched Chapter 2 checkout, with bytecode and pytest cache writes disabled:

- `tests/test_mnq_5m_acquisition.py::test_official_finalizer_embeds_attestation_from_real_git_objects`
  fails because pinned production commit
  `04a73e1401d44688660b211d9db6918113482856` is absent from the independent public
  root snapshot. No old history or private artifacts were restored to bypass it.
- All five parameters of
  `tests/test_repository_text_identity_policy.py::test_identity_sensitive_text_paths_resolve_to_lf_checkout`
  fail: the snapshot's `.gitattributes` contains `* -text`, while the tests expect
  `eol: lf` for the checkpoint verifier, acquisition finalizer, C# exporter,
  provenance schema and official-inventory design specification. This existing
  mismatch is not changed as part of Chapter 3.

The full suite uses synthetic/tooling fixtures; it is not a new 812-group
historical validation campaign. No source, oracle, production or frozen report
artifact is edited. The complete tooling-suite run finished with **1461 passed,
83 failed** in 1234.83 seconds. This run collected the initial 27 Chapter 3 cases;
the supplemental known-evidence/unknown-event case is included in the later
**28-pass focused** and **725-pass course-domain** runs reported above. The full
suite is **not green**. Its failure groups are:

| Count | Failure group | Evidence and disposition |
| --- | --- | --- |
| 52 | Windows long paths in old Git-verifier calls (51 checkpoint-verifier cases and one selected-source wrapper) | Full log reports failed `git show` / component missing, including downstream expected-error mismatches. The representative inventory case was reproduced on the untouched checkpoint and passed in short system temp. This verifies the representative cause; the entire 52-case group was not rerun. |
| 19 | Exporter fixture requires output beneath system temp | All failed at the fixture's system-temp guard before exercising the exporter. **All 19 passed** on the untouched checkpoint when rerun under a new short system-temp root. |
| 7 | Missing pinned production commit | One acquisition case and six public-inventory cases require/fetch `04a73e1401d44688660b211d9db6918113482856`, absent from this independent publication root. The acquisition case was also reproduced on the preserved checkpoint. |
| 5 | Existing text-attribute expectation mismatch | All five were reproduced on the preserved checkpoint; no attribute or frozen-file policy is changed here. |

The full raw log is retained locally as `../chapter3-regression-results.txt`.
All failed node IDs are preserved in the appendix below. No original tests were
removed, marked skipped, weakened or changed. The 19 exporter retests and the
short-path inventory retest correct test-environment placement only. A clean
full tool-suite rerun with the short path was not performed; the known missing
history and text-policy failures remain outside this lesson's change scope.

Files changed for this lesson:

1. `trading/definitions/trading_ranges.py` — new annotation models and conditional formation evaluator.
2. `tests/test_trading_ranges.py` — focused synthetic behavior tests.
3. `docs/lessons/chapter3-lesson1.md` — source limitations, knowledge specification, decisions and results.
4. `README.md` — link this lesson's scope from the development branch.
5. `docs/PROJECT_OVERVIEW.md` — describe the new companion component and current chapter progress.

## Questions for Lesson 2 and next step

1. What precisely establishes one relevant reaction or distinct unsuccessful
   attempt? Can its evidence and resolution time be specified independently?
2. With slides 8–10 and the full transcript now inspected, what stronger
   ordering/independence rules, if any, should govern reactions beyond the
   illustrated alternating examples and apply to sloping/narrow types?
3. How should multiple body/wick contacts determine or revise boundaries?
4. How are false breakout, successful breakout and range invalidation distinguished?
5. How are contextual doji, “铁丝网”, narrowness and acceptable slope defined
   for each market? In particular, does “超过连续3根” mean strictly more than
   three, despite the transcript also discussing three consecutive doji?
6. What future causal availability, retraction and boundary-version rules are
   needed before these observations can be produced from a live stream?

Recommended next step: read Lesson 2's actual source material, refine these
semantics and add only newly justified objective behavior. Keep boundary
selection and attempt-outcome judgment external until deterministic course
rules or explicit calibration approval exist. Chapter 2 is complete and is
not restarted.


## Appendix: full-suite failed test IDs

<details>
<summary>83 failures from the complete tooling-suite run</summary>

```text
tests/test_mnq_5m_acquisition.py::test_official_finalizer_embeds_attestation_from_real_git_objects
tests/test_mnq_5m_checkpoint_verify.py::test_verifies_first_class_inventory_checkpoint_from_immutable_bytes
tests/test_mnq_5m_checkpoint_verify.py::test_public_inventory_rejects_contradictory_runtime_scan_hash
tests/test_mnq_5m_checkpoint_verify.py::test_public_inventory_rejects_adjacent_runtime_hash_contradictions[trading_hours_template]
tests/test_mnq_5m_checkpoint_verify.py::test_public_inventory_rejects_adjacent_runtime_hash_contradictions[ninjatrader_config]
tests/test_mnq_5m_checkpoint_verify.py::test_public_inventory_rejects_adjacent_runtime_hash_contradictions[scanner]
tests/test_mnq_5m_checkpoint_verify.py::test_public_inventory_verifies_matching_runtime_hashes[False]
tests/test_mnq_5m_checkpoint_verify.py::test_public_inventory_verifies_matching_runtime_hashes[True]
tests/test_mnq_5m_checkpoint_verify.py::test_noncandidate_calendar_disagreement_is_bound_without_a_phantom_entry
tests/test_mnq_5m_checkpoint_verify.py::test_closed_scan_on_actual_date_verifies_as_excluded_unknown_candidate
tests/test_mnq_5m_checkpoint_verify.py::test_inventory_checkpoint_rejects_contradictory_bound_bar_count
tests/test_mnq_5m_checkpoint_verify.py::test_candidate_replay_rejects_noncanonical_executing_module[inventory_builder-tools.validation.mnq_5m_inventory]
tests/test_mnq_5m_checkpoint_verify.py::test_candidate_replay_rejects_noncanonical_executing_module[inventory_calendar_verifier-tools.validation.mnq_5m_inventory_calendar]
tests/test_mnq_5m_checkpoint_verify.py::test_inventory_checkpoint_rejects_missing_exclusion_row
tests/test_mnq_5m_checkpoint_verify.py::test_inventory_checkpoint_rejects_extra_exclusion_row
tests/test_mnq_5m_checkpoint_verify.py::test_inventory_checkpoint_rejects_changed_exclusion_row
tests/test_mnq_5m_checkpoint_verify.py::test_inventory_checkpoint_rejects_exclusion_reason_order_mutation
tests/test_mnq_5m_checkpoint_verify.py::test_inventory_checkpoint_rejects_outcome_threshold_mutation[false-ready]
tests/test_mnq_5m_checkpoint_verify.py::test_inventory_checkpoint_rejects_outcome_threshold_mutation[false-incomplete]
tests/test_mnq_5m_checkpoint_verify.py::test_toolset_only_gate_verifies_exact_frozen_23_role_policy_toolset
tests/test_mnq_5m_checkpoint_verify.py::test_toolset_only_gate_rejects_executing_policy_or_schema_mutation[inventory_builder]
tests/test_mnq_5m_checkpoint_verify.py::test_toolset_only_gate_rejects_executing_policy_or_schema_mutation[inventory_calendar_verifier]
tests/test_mnq_5m_checkpoint_verify.py::test_toolset_only_gate_rejects_executing_policy_or_schema_mutation[inventory_evidence_finalizer]
tests/test_mnq_5m_checkpoint_verify.py::test_toolset_only_gate_rejects_executing_policy_or_schema_mutation[inventory_common]
tests/test_mnq_5m_checkpoint_verify.py::test_toolset_only_gate_rejects_executing_policy_or_schema_mutation[source_inventory_schema]
tests/test_mnq_5m_checkpoint_verify.py::test_verifies_selection_as_direct_child_of_inventory_checkpoint
tests/test_mnq_5m_checkpoint_verify.py::test_real_task7_outputs_flow_through_component_toolset_inventory_selection_chain
tests/test_mnq_5m_checkpoint_verify.py::test_rejects_inventory_toolset_with_wrong_executing_verifier_hash
tests/test_mnq_5m_checkpoint_verify.py::test_v2_rejects_dirty_bundle_later_filename_only_commit_and_missing_artifact
tests/test_mnq_5m_checkpoint_verify.py::test_v2_rejects_external_evidence_hash_mismatch
tests/test_mnq_5m_checkpoint_verify.py::test_v2_uses_fixed_schemas_instead_of_self_declared_version
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_missing_required_fields[inventory_runtime_capture-instrument-inventory runtime capture]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_missing_required_fields[inventory_scan-observations-inventory scan]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_missing_required_fields[inventory_acquisition_evidence-historical_trigger-inventory acquisition evidence]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_missing_required_fields[inventory_provenance-provider_acquisition-inventory provenance]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_unknown_fields[inventory_runtime_capture-inventory runtime capture]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_unknown_fields[inventory_scan-inventory scan]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_unknown_fields[inventory_acquisition_evidence-inventory acquisition evidence]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_unknown_fields[inventory_provenance-inventory provenance]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_invalid_fixed_values[inventory_runtime_capture-connection_snapshot_phase-after inventory scan-inventory runtime capture]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_invalid_fixed_values[inventory_scan-civil_date_start-2026-06-23-inventory scan]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_invalid_fixed_values[inventory_acquisition_evidence-intended_connection_name-Replay Connection-inventory acquisition evidence]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_applies_each_frozen_evidence_schema_to_invalid_fixed_values[inventory_provenance-status-UNVERIFIED-inventory provenance]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_reconciles_acquisition_identity_across_every_evidence_document[inventory_runtime_capture]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_reconciles_acquisition_identity_across_every_evidence_document[inventory_scan]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_reconciles_acquisition_identity_across_every_evidence_document[inventory_acquisition_evidence]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_reconciles_acquisition_identity_across_every_evidence_document[inventory_provenance]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_rejects_mismatched_fixed_cohort_identity_in_every_evidence_document[inventory_runtime_capture-inventory runtime capture]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_rejects_mismatched_fixed_cohort_identity_in_every_evidence_document[inventory_scan-inventory scan]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_rejects_mismatched_fixed_cohort_identity_in_every_evidence_document[inventory_acquisition_evidence-inventory acquisition evidence]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_rejects_mismatched_fixed_cohort_identity_in_every_evidence_document[inventory_provenance-inventory provenance]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_reconciles_provenance_provider_acquisition_identity
tests/test_mnq_5m_checkpoint_verify.py::test_v2_reads_and_checks_the_executing_verifier_exactly_once
tests/test_mnq_5m_checkpoint_verify.py::test_v2_snapshots_every_supplied_bundle_file_once
tests/test_mnq_5m_checkpoint_verify.py::test_v2_remote_publication_verifies_the_mode_checkpoint[inventory]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_remote_publication_verifies_the_mode_checkpoint[selection]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_remote_publication_rejects_wrong_mode_checkpoint[inventory]
tests/test_mnq_5m_checkpoint_verify.py::test_v2_remote_publication_rejects_wrong_mode_checkpoint[selection]
tests/test_mnq_5m_selected_source_check.py::test_selected_source_wrapper_accepts_real_task9_immutable_git_verification
tests/test_ninjatrader_exporter_behavior.py::test_actual_normal_exporter_path_and_canonical_bundle
tests/test_ninjatrader_exporter_behavior.py::test_late_arm_exports_without_any_market_callback
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[race]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[missing]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[stale]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[wrong_id]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[unreadable]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[terminate]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[existing]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[partial]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[no_lifecycle]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[bounded]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[readiness]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[termination_publication]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[termination_dispatch]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[historical_pause]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[dispatcher_refusal]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[historical_resume_pending]
tests/test_ninjatrader_exporter_behavior.py::test_actual_exporter_guards_and_lifecycle[poll_after_market]
tests/test_repository_text_identity_policy.py::test_identity_sensitive_text_paths_resolve_to_lf_checkout[tools/validation/mnq_5m_checkpoint_verify.py]
tests/test_repository_text_identity_policy.py::test_identity_sensitive_text_paths_resolve_to_lf_checkout[tools/validation/mnq_5m_acquisition.py]
tests/test_repository_text_identity_policy.py::test_identity_sensitive_text_paths_resolve_to_lf_checkout[tools/validation/ninjatrader/ExportMnq5mCohortSource.cs]
tests/test_repository_text_identity_policy.py::test_identity_sensitive_text_paths_resolve_to_lf_checkout[validation/mnq_5m_multiwindow/schemas/provenance.schema.json]
tests/test_repository_text_identity_policy.py::test_identity_sensitive_text_paths_resolve_to_lf_checkout[docs/superpowers/specs/2026-09-16-mnq-5m-official-inventory-scanner-design.md]
```

</details>
