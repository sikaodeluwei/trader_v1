# MNQ Five-Minute Multi-Window Hierarchy Validation Design

**Date:** 2026-09-13

**Status:** Approved protocol checkpoint; no cohort execution authorized yet

**Branch base:** `04a73e1401d44688660b211d9db6918113482856`

**Scope:** Broader out-of-sample validation of the existing Chapter 2 market-
structure hierarchy on real, native MNQ five-minute bars

## Purpose

This specification advances the existing frozen single-window MNQ five-minute
result to a predeclared multi-window validation cohort. It tests whether the
unchanged production hierarchy agrees exactly with an independent oracle on at
least ten disjoint real-data windows selected without inspecting hierarchy
output.

The existing branch `validation/mnq-5m-hierarchy` and its frozen commit
`04a73e1401d44688660b211d9db6918113482856` remain historical evidence. They
must not be amended, rebased, or counted as one of the new cohort cases.

This is hierarchy validation only. It does not assess predictive value,
profitability, trade execution, or strategy performance.

## Binding Scope

The validation covers the implemented hierarchy exactly as it exists at the
frozen base:

```text
source candles
    -> isolated confirmed recognitions and unresolved potential
    -> SHORT points, vertices, suppression, and provenance
    -> MEDIUM points, potentials, vertices, suppression, and provenance
    -> LONG points, potentials, vertices, suppression, and provenance
```

Production hierarchy definitions, parameters, alignment rules, and
interpretations remain unchanged throughout the cohort. The protocol must not
be used to introduce Chapter 3, signals, entries, exits, sizing, risk, PnL,
fees, slippage, backtesting, broker integration, or order execution.

## Architectural Decision

Three execution arrangements were considered:

1. process each case through source, oracle, project, and comparison before
   selecting the next case;
2. freeze the whole cohort stage by stage; or
3. place oracle work in a separate external repository.

The second arrangement is selected. It provides stronger cohort-wide blindness
than case-at-a-time execution without the operational overhead of a separate
repository. Isolation is enforced through restricted checkouts and staged
artifacts rather than by relying only on contributor discipline.

The binding stage order is:

```text
protocol and validation tools
    -> source inventory and deterministic selection
    -> all frozen sources and provenance
    -> all frozen independent oracles
    -> all blind production-project results
    -> exact case comparisons
    -> aggregate cohort report
```

No later-stage artifact for the new cohort may be produced, exposed to, or
inspected by an earlier-stage environment. Historical frozen evidence already
present at the branch base is outside the cohort and must also be excluded from
the isolated oracle and project environments.

## Cohort Definition

The first cohort uses one exact MNQ futures contract expiry. Contract months or
years must not be mixed. The cohort contains at least ten valid windows, each:

- associated with a different declared trading date;
- disjoint from every other cohort window;
- composed of exactly 250 native NinjaTrader five-minute bars;
- taken from the first 250 native bars of the declared Trading Hours session;
- bound to complete source provenance; and
- selected without hierarchy, oracle, or production-project output.

The frozen single-window case at the branch base is a compatibility reference,
not a member of this cohort and not part of its pass denominator.

## Contract, Date Range, and Rollover Control

Before inspecting candidate hierarchy output, the cohort manifest must declare:

- the full futures contract identifier, including month and year;
- the exchange/instrument identifier used by NinjaTrader;
- a bounded inclusive trading-date range;
- the objective reason that range is appropriate for the contract;
- the data-provider contract-roll convention, if one exists; and
- an explicit rollover/liquidity-transition exclusion interval.

The date range must be selected from contract availability and validation-
coverage considerations only. It must not be selected, expanded, or shortened
using hierarchy results.

The first cohort excludes every predeclared rollover/liquidity-transition date.
The exclusion interval must be supported by recorded provider or exchange
metadata; it must not be inferred after viewing market structure. Testing a
rollover-transition period is a separate future validation objective requiring
its own predeclared cohort.

If the declared contract and date range yield fewer than ten objectively
eligible trading dates, execution stops with `COHORT_INCOMPLETE`. The process
must not silently expand the range, mix contracts, relax eligibility, or add a
replacement selected after output is known.

## Source Inventory

Before window selection, create and freeze a source inventory covering every
trading date in the declared range. Inventory construction may inspect only
source metadata and source-quality properties. It must not call the hierarchy,
oracle, comparator, or any structural recognition helper.

For each trading date, the inventory records whether the date is eligible and,
if not, one or more objective exclusion reasons. Permitted exclusion reasons
are limited to:

- outside the declared contract/date/rollover policy;
- incomplete or unknown required provenance;
- fewer than 250 native bars available from the session start;
- duplicate or non-monotonic timestamps;
- timestamps inconsistent with the declared Trading Hours calendar;
- malformed or non-finite OHLCV values;
- invalid OHLC geometry;
- unexpected missing bars; or
- source corruption or a source hash mismatch.

Visual cleanliness, trend quality, hierarchy density, point counts, oracle
difficulty, or project agreement are never eligibility criteria.

The complete inventory and exclusion ledger are hashed and frozen before an
oracle or project result is generated.

## Deterministic Window Selection

Let `D` be the strictly chronological list of objectively eligible trading
dates from the frozen inventory, and let `n = len(D)`. Execution requires
`n >= 10`.

Divide `D` into ten chronological strata using zero-based boundaries:

```text
start(i) = floor(i * n / 10)
end(i)   = floor((i + 1) * n / 10) - 1
```

for `i` from 0 through 9. Select `D[start(i)]`, the earliest eligible trading
date in each stratum. This produces ten deterministic dates spread across the
declared range without random sampling or visual selection.

For each selected date, use exactly the first 250 native five-minute bars from
the declared NinjaTrader Trading Hours session. The session calendar, including
scheduled openings, closings, holidays, and breaks, is authoritative:

- a scheduled boundary is not a missing-data defect;
- an unexpected absent bar during an expected open period is a defect;
- bars are never inserted, interpolated, filled, resampled, or duplicated;
- rows are never silently sorted; and
- a timestamp is never shifted to make a window appear valid.

Selection is frozen for the cohort. No case may be excluded, replaced, or
substituted after any oracle or project hierarchy output for the cohort exists.

## Case Naming

Case identifiers use:

```text
mnq-YYYYMM-5m-tdYYYY-MM-DD-wNN
```

where:

- `YYYYMM` is the exact contract expiry;
- `tdYYYY-MM-DD` is the trading date assigned by the declared Trading Hours
  template; and
- `wNN` is the deterministic stratum order from `w01` through `w10`.

Exact source timestamps belong in provenance rather than in the identifier.

## Repository Layout

The cohort uses a contained validation-data tree rather than adding more flat
root-level artifacts:

```text
docs/superpowers/specs/
    2026-09-13-mnq-5m-multiwindow-validation-design.md

validation/mnq_5m_multiwindow/
    cohort_manifest.json
    toolset_manifest.json
    selection_registry.json
    exclusions.json
    schemas/
        cohort_manifest.schema.json
        provenance.schema.json
        hierarchy_oracle.schema.json
        blind_result.schema.json
        comparison_report.schema.json
    cases/
        mnq-YYYYMM-5m-tdYYYY-MM-DD-wNN/
            source/
                bars.txt
                provenance.json
            oracle/
                isolated.json
                short_term.json
                medium_term.json
                long_term.json
                manifest.json
            project/
                blind_result.json
                manifest.json
            comparison/
                report.json
                negative_controls.json
    reports/
        cohort_summary.json
        reproduction_manifest.json
```

Reusable validation programs remain under `tools/validation/`. No production
hierarchy module belongs in the validation-data tree.

## Complete Source Provenance

Every case `provenance.json` must record, without inference or defaults:

- schema version and case identifier;
- instrument root and exchange;
- full contract/expiry identity and NinjaTrader instrument display name;
- source data provider or feed;
- NinjaTrader version;
- NinjaTrader bar type and interval;
- source timezone and daylight-saving semantics;
- exact Trading Hours/session template name and relevant configuration;
- assigned trading date;
- first and last source timestamps;
- exact bar count;
- whether bars are native or resampled;
- original export method and acquisition date;
- original export identity and SHA-256;
- selected row/range derivation;
- frozen case-file SHA-256;
- known missing bars, scheduled exclusions, holidays, or other limitations;
- confirmation that no sorting, interpolation, filling, or timezone conversion
  was performed; and
- the frozen selection-registry and toolset-manifest hashes.

Local absolute paths are not provenance and must not be required for
reproduction. Unknown contract identity, provider, source timezone, or Trading
Hours template makes the source ineligible. No inferred or assumed value may
fill these fields.

## Source Integrity and Chronology

Source validation occurs before selection and again before every downstream
stage. It must enforce:

- exactly 250 non-empty source rows per selected case;
- the declared native five-minute bar schema;
- timestamps parseable under the declared timezone;
- strict chronological increase in supplied order;
- no duplicate timestamps;
- spacing consistent with expected bar starts from the declared session
  calendar;
- finite OHLCV values;
- `low <= min(open, close) <= max(open, close) <= high`;
- non-negative integral volume when volume is supplied; and
- exact agreement with the recorded source hash.

Validation rejects defects. It never sorts, truncates, fills, repairs,
interpolates, or converts timezones silently.

## Validation Toolset Freeze

Before the first cohort oracle is generated, freeze and hash:

- this approved protocol specification;
- every source and artifact schema;
- the independent oracle implementation;
- the blind production-result runner;
- the exact comparator;
- the complete representation-only normalization rules;
- every negative mutation-control definition; and
- the cohort aggregation implementation.

The `toolset_manifest.json` records each path, SHA-256, producing commit,
runtime version, dependencies, and an aggregate manifest hash. It also pins the
production hierarchy commit under test.

The toolset is immutable for the full cohort. If a semantic tool, schema,
normalization, negative control, or aggregation correction becomes necessary
after cohort execution begins, stop the cohort. Record the defect
classification, version the corrected component and protocol checkpoint, and
start a new cohort version. Never patch a running cohort silently.

## Oracle Independence

All ten oracles must be frozen before any cohort project result is generated or
inspected.

Oracle execution uses an isolated directory or checkout whose allowlist
contains only:

- the frozen source and provenance for the current case;
- the frozen approved protocol and schemas;
- the frozen independent oracle program; and
- the standard runtime dependencies recorded in the toolset manifest.

It must not contain or access:

- production `trading` modules;
- the production hierarchy runner;
- project blind results;
- comparison reports; or
- aggregate project output.

Static import inspection must show no production import. Execution uses Python
isolated mode or an equivalently documented restricted runtime. A reproduction
manifest records the allowlisted files and hashes. Every oracle layer is
serialized, hashed, reviewed, and committed before project execution begins.

## Blind Production Execution

Project results use the pinned, unchanged production hierarchy commit. Each
result is generated in an isolated checkout/environment containing production
code, frozen source/provenance, and the blind runner, but no oracle,
comparison, or aggregate-report artifacts.

Where the repository history already contains the oracle commit, the project
runner must execute from the earlier frozen source-stage tree or an equivalent
allowlisted export that excludes every oracle path. The resulting artifact may
be transferred by verified hash into the later project-result commit only
after all oracles are frozen.

The project stage runs all ten cases before any comparison is revealed. Its
manifest records the production commit, runner hash, input hashes, runtime, and
output hash for every case.

## Stage Ancestry and Hash Chain

Separate commits or otherwise immutable checkpoints must prove this order:

```text
protocol/toolset freeze
    < source inventory and selection freeze
    < all source/provenance freeze
    < all oracle freeze
    < all project-result freeze
    < comparisons
    < aggregate report
```

Manifests record both Git ancestry and SHA-256. A downstream stage refuses to
run when its expected upstream commit or hash differs. Generated caches,
untracked helpers, machine-specific paths, or deleted local-only tools cannot
be required for reproduction.

## Exact Hierarchy Comparison

Every case comparison validates the full implemented hierarchy, including:

### Source and isolated layer

- exact ordered source candles and OHLCV geometry;
- confirmed isolated point index, kind, price, basis, and confirmer;
- unresolved isolated potential identity and provenance; and
- exact counts and ordering.

### SHORT layer

- every valid point;
- canonical vertices;
- suppressed points;
- suppression reason;
- retained vertex, containing pair, and suppression-event provenance where
  applicable;
- recognition basis and structural source geometry;
- unresolved potential representation where the schema provides it; and
- exact counts and ordering.

### MEDIUM and LONG layers

- points and canonical vertices;
- potential points;
- suppressed points and reasons;
- pivot and confirming-source indexes;
- lower-level canonical source vertices and structural source geometry;
- suppression provenance; and
- exact counts and ordering.

Lists are compared positionally. Prices and other numeric structural values use
exact decimal semantics. No tolerance-based acceptance is permitted for values
that should be exact.

## Representation-Only Normalization

The complete normalization table is frozen before cohort execution. It may
normalize only representation with identical semantics, such as:

- JSON object key order and insignificant whitespace;
- explicitly enumerated case differences for known enum spellings; and
- numeric lexical forms that parse to the same exact decimal value.

Normalization must not reorder semantic lists, round prices, alter timestamps,
substitute enum meanings, add defaults, infer missing fields, or remove
provenance. Any unlisted difference is a comparison difference. The comparator
report records both raw hashes and the exact normalization rule applied.

## Negative Mutation Controls

The frozen comparator must retain the existing mutation controls and extend
coverage where needed so the cohort toolset proves detection of:

- an isolated point identity or confirmer mutation;
- unresolved-potential addition, deletion, or mutation;
- SHORT vertex reordering or source-index mutation;
- SHORT suppression reason or provenance mutation;
- MEDIUM point, potential, or confirmer mutation;
- LONG point, potential, or confirmer mutation;
- a one-tick source or structural-geometry mutation;
- deletion of a required field or status; and
- a representation-only enum-case mutation that must remain semantically
  equal under the frozen normalization table.

Every semantic mutation must produce `MISMATCH` at its expected path. The sole
representation-only control must produce `EXACT_MATCH`. A missing or
unexpected control result invalidates the comparator evidence.

## Mismatch Investigation Gate

Comparison stops at the first unexplained mismatch. Before changing any
semantic code, reviewers must assign one of these classifications with
evidence:

1. `PROJECT_DEFECT`;
2. `SOURCE_PROVENANCE_DEFECT`;
3. `ORACLE_DEFECT`;
4. `SPECIFICATION_AMBIGUITY`; or
5. `COMPARATOR_DEFECT`.

No production hierarchy rule, parameter, alignment rule, or interpretation may
change between cases. An oracle rule may not be altered merely because it
disagrees with production. No failed or difficult case may be removed or
replaced after its output is known.

Corrections occur only in a new versioned checkpoint. The affected cohort and
its evidence remain preserved with their terminal status.

## Aggregate Status Model

The aggregate report uses exactly one terminal status:

- `COHORT_PASS`: at least ten valid, disjoint, different-trading-date cases
  completed and all cases are exact matches with every control passing;
- `ENGINE_VALIDATION_FAIL`: at least one valid case contains a proven
  `PROJECT_DEFECT`;
- `COHORT_INVALID_SOURCE`: evidence contains a proven source or provenance
  defect discovered after the cohort was frozen;
- `COHORT_INVALID_ORACLE`: evidence contains a proven oracle defect;
- `COHORT_INVALID_SPECIFICATION`: evidence depends on a specification
  ambiguity that prevents a valid engine conclusion;
- `COHORT_INVALID_COMPARATOR`: evidence contains a proven comparator defect;
  or
- `COHORT_INCOMPLETE`: fewer than ten valid selected cases complete, a stage
  is interrupted, a required artifact/control is absent, or a mismatch remains
  unresolved.

Invalid-source, invalid-oracle, invalid-specification, and invalid-comparator
cases do not count as production-engine passes or failures. They invalidate the
cohort evidence and require a new versioned checkpoint. They must not be
silently discarded and replaced.

If evidence supports more than one invalid category, preserve all case-level
classifications and use `COHORT_INCOMPLETE` until a reviewed primary terminal
classification is assigned. Status assignment itself must not hide secondary
findings.

## Predeclared Completion Criteria

The multi-window stage succeeds only when all of the following are true:

1. one exact contract, bounded date range, session template, timezone, provider,
   and rollover policy were declared before selection;
2. the inventory, exclusions, and deterministic ten-stratum selection were
   frozen before hierarchy output;
3. at least ten disjoint windows on different trading dates pass all source and
   provenance requirements;
4. all tools, schemas, normalization rules, controls, and aggregation logic
   remained unchanged for the cohort;
5. every oracle was frozen before any project result existed or was inspected;
6. every project result was produced without oracle access;
7. all cases report exact agreement across every hierarchy layer, value,
   sequence, count, and provenance field;
8. every negative mutation control has the expected outcome;
9. independent clean reproduction yields identical semantic artifacts and
   hashes;
10. the cohort report has no unexplained mismatch or unresolved classification;
11. repository regression tests and validation-tool checks pass at the pinned
    checkpoint; and
12. the aggregate status is `COHORT_PASS`.

There is no partial-pass percentage. Nine matches and one valid project defect
is `ENGINE_VALIDATION_FAIL`, not 90% success.

## Reproduction Requirements

A reviewer must be able to reproduce the source validation, selection,
oracles, blind outputs, comparisons, controls, and aggregate report using only
tracked files and documented external source inputs. Reproduction must not
depend on caches, untracked scripts, deleted helpers, workstation-specific
paths, or unstated environment state.

Expected deterministic stages are run twice in clean temporary locations. The
reproduction manifest records commands, runtime versions, input/output hashes,
and equality results. Temporary generated files are not accepted as evidence
unless their finalized equivalents and producing tools are tracked and hashed.

## Risks and Limitations

Even `COHORT_PASS` establishes rule-implementation agreement, not trading
profitability or market prediction. Remaining limitations include:

- ten windows are broader than one but still a modest sample;
- windows from one expiry and provider may be correlated;
- provider and NinjaTrader bar construction may differ from another feed;
- session-template or timezone metadata can be recorded incorrectly at source;
- native OHLC bars do not establish intrabar price order; and
- the independent oracle and production implementation can share the same
  misunderstood written rule despite implementation separation.

These limitations must appear in the aggregate report. They are not reasons to
tune rules or remove unfavorable cases.

## Deferred Behavior and Non-Goals

This protocol does not authorize:

- mixed-expiry or rollover-transition validation in the first cohort;
- automatic contract, date-range, window, session, or provider selection;
- changes to isolated, SHORT, MEDIUM, or LONG recognition;
- tolerance-based structural acceptance;
- parameter optimization or rule tuning;
- Chapter 3 concepts;
- trading signals, entries, exits, stops, risk, sizing, or leverage;
- PnL, fee, slippage, drawdown, or trade-count calculations;
- backtesting or performance claims;
- live trading or future-data execution claims; or
- broker, order, or execution integration.

## Execution Gate

No new source window may be selected and no cohort oracle, project result, or
comparison may be generated until:

1. this specification is reviewed and approved;
2. the exact contract, provider, bounded date range, source timezone, Trading
   Hours template, and rollover exclusion interval are explicitly supplied and
   approved; and
3. a separate implementation/execution plan freezes the schemas and toolset
   before cohort work begins.

## Design Invariants

1. The frozen single-window branch and commit remain unchanged.
2. The existing frozen case does not count toward the new ten-case cohort.
3. One exact contract expiry is used; expiries are never mixed.
4. Rollover-transition testing is excluded unless separately predeclared.
5. Window selection depends only on frozen source inventory and quality.
6. Ten chronological strata select the earliest eligible date in each stratum.
7. Each case contains the first 250 native bars from its declared session.
8. Scheduled session boundaries are respected; unexpected gaps are rejected.
9. No source value, timestamp, or row order is silently repaired.
10. Unknown contract, provider, timezone, or session metadata is ineligible.
11. The complete validation toolset is frozen before the first oracle.
12. All cohort sources are frozen before all cohort oracles.
13. All cohort oracles are frozen before any cohort project result.
14. Oracle execution cannot access production modules or project results.
15. Project execution cannot access oracle or comparison artifacts.
16. Production and oracle semantic rules do not adapt to case results.
17. Every hierarchy layer, order, count, geometry, and provenance is compared.
18. Exact values remain exact; normalization is representation-only and
    exhaustively declared.
19. Negative controls prove that semantic corruption is detected.
20. The first unexplained mismatch stops comparison for classification.
21. A valid project defect produces `ENGINE_VALIDATION_FAIL`.
22. Non-project evidence defects invalidate the cohort rather than count as an
    engine pass or failure.
23. No post-result case exclusion or substitution is allowed.
24. `COHORT_PASS` requires at least ten valid cases and 10/10 exact matches.
25. No strategy, performance, execution, or Chapter 3 behavior enters this
    validation stage.
