# Chapter 2 successor scientific validation tools — protocol 1.0

Owner-approved extension of the completed coverage audit. Source acceptance remains protocol 2.1 / freeze 2.2, unchanged. Cohort mnq-202609-5m-v2 has ten fixed windows and 2,500 accepted candles. This protocol extends scientific coverage, not market definitions or acquisition.

## Scope and representations

Reuse isolated → SHORT → MEDIUM → LONG rules, including strict promotion, fixed-left normalization and suppressed/potential provenance. Add explicit selected-state/BMS/SMS/anchor comparisons through existing APIs. No automatic segment, timeframe, level, origin, pullback or creator selection. Generic scoring remains unchanged; it has a narrower projection. These tools use the existing rich hierarchy comparator and a complete selected-result projection instead.

The input is the externally pinned frozen snapshot. case_binding derives a unique scientific case ID COHORT-wNN, preserves wNN and its frozen trading date, and binds source and frozen-manifest hashes. The new ID distinguishes successor scientific records without changing any legacy case identity or accepted source bytes. load_case/cohort_bindings reuse the approved source verifier. read_window checks exact CSV header, 250 rows, identity, SHA256, five-minute UTC continuity, OHLC geometry, MNQ quarter ticks and integer volume. Upstream remains UNVERIFIED under the accepted provider profile; no confirmed HDS assertion is introduced.

Frozen UTC timestamps mean bar close. The scientific model continues to use bar start: analysis_time = source_close_utc minus exactly five minutes. Both clocks and mapping version UTC_CLOSE_TO_START_5M_V1 remain explicit. Candle indexes are source-order zero-based, never shifted by one. Comparisons join by identity/index, not formatted local clock. DST conversion is for display only; all arithmetic is UTC. No source file is rewritten. Source Decimal values are retained; conversion to the unchanged float-based analyzer is permitted only when Decimal.from_float(value) equals the original exact value. MNQ quarter ticks satisfy this; loss is rejected.

## Minimal files and API responsibilities

- tools/validation/mnq_5m_scientific_v2.py: stdlib source/context I/O; no production import. Lazy adapters reuse the independent oracle builder and rich comparator. Importing it performs no recognition, context selection or file writes.
- tools/validation/mnq_5m_scientific_project_v2.py: explicit production-only adapter; reads no oracle paths/modules. It validates a numeric blind request document, builds the normal hierarchy once, evaluates requested segments using existing functions, and returns complete serialized hierarchy plus selected results. No model changes.
- tests/test_mnq_5m_scientific*.py: hand-constructed synthetic data only. No frozen cohort candles are recognized.
- CONTEXT_SELECTION_V1.md: independent annotation/eligibility procedure. toolset-manifest.json pins these documents, code and relevant accepted dependencies.

Selected results contain request, selected_points (level, point and complete nested source_vertex), market_state, bms, sms and trend_start_anchor. Each evaluation retains status, exact reason and semantic value. Diagnostic exception prose is excluded; status/reason/event/provenance are never omitted. Ambiguous OHLC remains INVALID / ohlc_intrabar_order_ambiguous, not a guessed crossing order or a new market state. Insufficient structure remains UNAVAILABLE / insufficient_structure at the facade. BMS and SMS terminal events retain the actual broken point and event index. Anchor provenance stays SHORT and separate from selected MEDIUM/LONG points.

## Context checkpoint format and procedure

Future authorized independent annotation supplies a MNQ_CONTEXT_SELECTION_V1 document, complete expected result mapping, externally verified source bindings and the approved selection-policy hash. Strict keys reject embedded expected answers in requests, unknown fields, wrong identities, malformed indexes and duplicate IDs. Selection metadata contains rationale and coverage accounting. freeze_contexts validates membership and expected projections, then writes selection.json, expectations.json, blind-requests.json and a final manifest.json into a new directory. The caller records the returned manifest hash externally. No existing or partial checkpoint can be overwritten or resumed. Missing, extra or changed files fail read-only verify_contexts. No circular hashes are used. This context checkpoint alone is not the all-ten hierarchy-oracle checkpoint.

blind_requests projects only context ID, exact source binding, explicit segment/level and numerical BMS/SMS references. It strips rationale and coverage/expected labels. load_blind_requests verifies the externally pinned request-file hash and strict numeric schema without opening expectations. The production worker must receive a separate source/request/code allowlist. Hashes detect changed bytes; they do not prevent edits, prove annotator independence or enforce OS isolation.

## Mandatory scientific stage ordering

1. Source cohort is already accepted/frozen; verify external manifest hash and source bindings.
2. Independently annotate all ten source windows under CONTEXT_SELECTION_V1.md. Keep production code/results, this implementation audit and old project overlays outside the annotator allowlist. Complete hierarchy oracles and all selected contexts, ambiguities and absent-case records. Context utilities may be used; they do not select answers. Independent review resolves eligibility before production. Freeze all oracle/context files with exact hashes and record one cohort inventory before any production run.
3. Prepare a source + numeric request + approved production-code workspace. It must have no expected-result files or oracle module access. All-oracle-first and blinded workspace creation are procedural scientific gates, not a new ROOT-style authorization service. analyze_case is a library function, not an enforcement sandbox. Run all ten and freeze all outputs before comparison. No selected source may be run as an early smoke test.
4. Only afterward compare complete ordered hierarchy using compare_hierarchy and every frozen selected context using compare_selected. Read expected bytes from their preserved checkpoint. Require identical case and request membership; never score only a convenient subset. Preserve per-field mismatch paths, controls and source bindings. Reproduce oracle and production outputs independently twice and compare hashes. Aggregate only after all ten have explained outcomes.

These steps are prepared, not executed by this implementation authorization. The read-only CLI exposes verify-source and verify-contexts only. No convenience CLI creates oracles or runs production.

## Acceptance and defects

Retain approved exact synthetic Test A–E and ten-window hierarchy criteria, ordered provenance/potentials/suppression, applicable negative controls, independent stage separation and deterministic reproduction. Add exact agreement on all predeclared unambiguous selected-result fields and explicit negative/ambiguity/unavailable behavior. Coverage accounting must distinguish observed real-data coverage, synthetic-only coverage, unresolved course definitions and absent natural events. No arbitrary percentage threshold or profitability criterion is added. A 9/10 pass with an engine defect is incomplete, not a 90% scientific acceptance.

Classify mismatches as PROJECT_DEFECT, SOURCE_PROVENANCE_DEFECT, ORACLE_DEFECT, SPECIFICATION_AMBIGUITY or COMPARATOR_DEFECT. Stop on unexplained mismatches. Preserve original artifacts and version corrections; never tune definitions/dates/contexts to production results. Raw sixteen-type classification, inferred intrabar paths, automatic selectors and unresolved course creator rules remain outside claims.

## Causality and remaining execution boundary

This is retrospective offline correctness. Pivot indexes, later structural confirmers and full-window suffix evaluations are not a live known-at contract. Anchors are descriptive, never signals. Streaming finality, corrections/retractions and prefix availability remain a separate future interface task. No additional historical acquisition is justified by present coverage. Next authorization is independent source-only annotation/oracle preparation under this protocol; all-oracle-first and blind production ordering remains mandatory.

## Safe read-only command

From the repository root, use PowerShell with the existing Python installation:

    D:/python/python.exe -B -m tools.validation.mnq_5m_scientific_v2 verify-source --snapshot "validation/mnq_5m_successor_v2/frozen/mnq-202609-5m-v2" --manifest-sha256 ce048e298e2eb0eb5f82cec2cb34ac14f5db277997b3399e27f910d4581dc6ac

This verifies source inputs and emits hashes/counts; it never calls the analyzer. Later context verification uses verify-contexts --directory <frozen-context-directory> --manifest-sha256 <external-context-manifest-hash>. Do not run oracle or production APIs under the tools-only authorization.
