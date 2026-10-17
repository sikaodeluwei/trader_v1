# Trading System V1 — Chapter 2 final scientific comparison

Scientific acceptance: **PASS — COHORT_PASS**, under the existing frozen criteria for the fixed successor cohort mnq-202609-5m-v2. Stage integrity PASS. All10windows and107explicit contexts match; no required comparison is incomplete. No recognition or independent oracle was regenerated, and no source, expected result, production result, context, definition or comparison semantics changed.

## Exact results and denominators

**812/812 exact comparison groups matched (100%):170complete hierarchy groups +642selected-field groups.** A group compares a complete semantic object or ordered collection, recursively, using the approved comparator. This is not a count of primitive scalar fields or independent market observations. Each context has six named groups: request, selected_points, market_state, BMS, SMS and trend_start_anchor. Whole-window and whole-context outcomes are aggregates and are not added again to812. Unrequested/null BMS/SMS fields are checked, but only41/45are counted as requested evaluations.

| Capability | Exact matches | Coverage and interpretation |
|---|---:|---|
| Source candles / structural geometry | 20/20 groups | All2,500source candles and source-bound geometry; original OHLCV bytes separately verified. Analyzer consumes OHLC; volume remains source-integrity-bound. UTC close -> UTC analysis start minus5minutes is explicitly preserved. |
| Isolated confirmed / right-edge potential | 20/20 groups | All719recognitions, including502strict and217deformation recognitions;9right-edge potentials and1null case. Basis, status, source clock, confirmer and ordering retained. |
| SHORT | 40/40 groups |719points,441canonical vertices,278suppressed; complete point/vertex/potential/suppression projections, fixed-left normalization and provenance. |
| MEDIUM | 40/40 groups |88points,63vertices,25suppressed,11potentials; promotion/pivot/previous/confirmer/source geometry. |
| LONG | 40/40 groups |5points,5vertices,0suppressed,12potentials; exact empty collections are also checked. Positive natural LONG suppression is not claimed. |
| Hierarchy counts | 10/10 groups | All13count fields per window. |
| Explicit request parameters | 107/107 contexts | Structural level, segment and caller-supplied creator/origin/pullback boundaries unchanged. |
| Selected points and provenance | 107/107 contexts | Full ordered nested source vertices, level and point fields. |
| Market state | 107/107 contexts |29uptrend,17downtrend,18nontrend and43unavailable; unavailable is not relabelled nontrend. |
| Requested BMS | 41/41 requests |19confirmed,11not-a-pullback,8invalid,3unavailable. Other66null/unrequested fields also match. |
| Requested SMS | 45/45 requests |16confirmed,15parent-continued,3pullback-only,8invalid,3unavailable. Other62null/unrequested fields also match. |
| Trend-start anchor | 107/107 contexts |20nonnull MEDIUM-context anchors with complete SHORT provenance;87null outcomes. Counts are contexts, not unique anchor pivots. |

All nonzero-denominator rates above are100%. Some rows overlap within the same recursive group; they must not be summed as additional independent comparisons. The six selected-field groups total642, of which BMS/SMS requested subsets are reported separately. SHORT48/48,MEDIUM38/38,LONG21/21selected contexts match. Provenance/confirmation mismatches:0.

## Per-window completeness

| Window | Hierarchy groups matched | Contexts matched | Mismatches |
|---|---:|---:|---:|
| w01 | 17/17 | 20/20 | 0 |
| w02 | 17/17 | 8/8 | 0 |
| w03 | 17/17 | 9/9 | 0 |
| w04 | 17/17 | 9/9 | 0 |
| w05 | 17/17 | 10/10 | 0 |
| w06 | 17/17 | 11/11 | 0 |
| w07 | 17/17 | 10/10 | 0 |
| w08 | 17/17 | 9/9 | 0 |
| w09 | 17/17 | 10/10 | 0 |
| w10 | 17/17 | 11/11 | 0 |

## Discrepancies and controls

Actual mismatch count: **0**. PROJECT_DEFECT0;SOURCE_PROVENANCE_DEFECT0;ORACLE_DEFECT0;SPECIFICATION_AMBIGUITY0;COMPARATOR_DEFECT0;UNRESOLVED0. There is no earliest divergence, causal-timing discrepancy or corrective change justified by this comparison. Invalid/unavailable cases remain included with their exact reasons and values.

**103/103 controls passed in both clean comparison runs:**80existing controls(eight per window) plus23supplementary controls.93semantic mutations produced MISMATCH at relevant fields, and10enum-casing-only representation controls retained EXACT_MATCH. Supplemental controls exercise isolated identity/confirmer, unresolved addition/deletion/change, suppression, MEDIUM/LONG points/potentials/confirmers, every selected result field, type/order, events and anchor provenance. Mutations use temporary deep copies only; frozen artifacts were never edited and no new legitimate oracle answers were generated. Supplemental targets are the first eligible existing frozen case/context, not newly selected scientific contexts.

The approved comparator normalizes only its frozen documented representations, with exact Decimal prices, known enum casing and explicit clock/provenance adapters. Lists remain ordered; types/keys/nulls remain significant. No tolerance, price rounding, value substitution, case exclusion or passing percentage was introduced. Every check records its adapter; raw stage hashes bind original representations.

## Natural versus synthetic coverage

The frozen coverage register has69records:42covered,26absent and1conceptual creator-uniqueness ambiguity. All26absent records resolve to already passed synthetic fixture IDs. All accepted LONG windows have too few canonical vertices for a directional LONG parent; natural directional LONG state/events/anchors are absent. Natural BMS pullback-only, SMS pending, exact equality touch and competing-OHLC ambiguity are absent from these fixed107contexts. Natural ambiguity outcome denominator is0: no0/0success rate is claimed. Synthetic fixtures support these rules; LONG suppression/normalization branches also rely on the existing supplied-structure synthetic coverage where natural positive cases are absent. Other absence claims are limited to the frozen annotation scope, not all possible segments or markets.

The65independent course-rule fixtures and their independent rerun/review remain accepted and hash-bound.69new scientific-tool synthetics,165relevant regression results(including96existing tests) and26aggregation tests are reused for unchanged code. This task does not rerun recognition/oracle-generating tests, as prohibited. Exact accepted logs/reviews, unchanged52toolset dependencies and supplemental components are bound in reproduction-and-evidence-reuse.json. Test A-E responsibilities remain supported by the approved prior synthetic/regression evidence; this comparison is the real-data hierarchy/explicit-context extension, not a claim to calibrate unavailable intrabar capabilities.

Creator/origin choices are explicit conditional analytical inputs and preserved alternatives. A unique automatic segment/creator selector remains intentionally undefined and outside the scored API. That conceptual ambiguity does not make any of these frozen numeric requests ambiguous. No event horizon or context was changed after observing outcomes.

## Integrity, reproduction and acceptance

Source, oracle, context and production manifest SHA256pins all verify. All10fixed dates, exact case/source identities,107request identities, timeframe/structural-level distinction and close/start clock bindings are compatible. Production scientific base04a73e1401d44688660b211d9db6918113482856 and every copied module match. Oraclecheckpointf1fa4136 precedes blindproductionaa33390; both complete stages were frozen before this comparison.

Two fresh comparison processes produced byte-identical comparison.json, controls.json and result-hashes.json, using unchanged approved comparison functions. compare_frozen.py is a version1reporting/control orchestrator, not a recognizer. Its import/call guards record0recognition/oracle-generation calls. Original comparison/aggregation tools retain their exact pinned hashes. acceptance.json records evidence for every existing gate; aggregate.json uses the approved pure reducer and yields COHORT_PASS for all ten disjoint valid cases. No source acceptance or original historical disposition is rewritten.

The one focused independent comparison review, its scope and exact bindings are recorded in independent-comparison-review.json in this report package. The final continuation handoff pins its decision alongside the report hashes. This report's scientific judgment is limited to the stated frozen cohort and implemented definitions.

## Validated scope and remaining limits

Validated: exact retrospective implementation of isolated/deformation and SHORT/MEDIUM/LONG structure, normalization/promotion/suppression/provenance where supplied, plus the fixed explicit market-state/BMS/SMS/anchor requests, including negative/unavailable outcomes, deterministic output and input/clock integrity. This is foundational recognition validation, not a trading-edge evaluation.

Unproven: unrestricted unseen-market generalization; automatic segment/creator choice; unique unresolved course interpretations outside the explicit API; raw sixteen-type/intrabar calibration or inferred OHLC crossing order; live/prefix known-at semantics, streaming finality/retractions/late corrections; prediction, profitability or execution behavior. Later structural confirmers and suffix events are retrospective evidence, not signals available at pivot time. Upstream historical provider origin remains UNVERIFIED under the approved temporary source profile; byte integrity is not exchange authentication.

No correction, new oracle, new context or additional acquisition is justified by these zero-mismatch results. Future streaming-interface work remains a separately scoped task if the owner chooses it. No correction, Chapter3implementation, strategy, live API, merge or push begins automatically. Final scientific records are preserved by the existing hash/write-once/local-checkpoint mechanism; hashes detect edits rather than preventing them.
