# Official MNQ Five-Minute Source-Inventory Scanner Design

**Date:** 2026-09-16

**Status:** APPROVED DESIGN — IMPLEMENTATION NOT STARTED

**Design checkpoint base:**
`3a5da982fdd7dbac9bfd98d2c6849c1888a7b427`

**Frozen production hierarchy:**
`04a73e1401d44688660b211d9db6918113482856`

**Scope:** Facts-only discovery, evidence validation, eligibility mapping, and
deterministic selection of official MNQ September 2026 native five-minute
source windows before any hierarchy, oracle, blind-project, or comparator
execution.

## Context and Motivation

The approved multi-window validation protocol requires at least ten disjoint
real MNQ five-minute cases chosen independently of market-structure output.
Before those cases can be acquired, the project needs a reproducible way to
answer two narrower questions:

1. Which actual `CME US Index Futures ETH` trading dates belong to the approved
   `MNQ SEP26` policy window?
2. Which of those dates have sufficiently complete, valid, native five-minute
   source data to enter deterministic selection?

The answer cannot depend on a weekday heuristic, visual chart inspection, or
the hierarchy engine. It must be derived from frozen NinjaTrader session
evidence and objective source-quality facts. This design introduces that
pre-selection subsystem while preserving the production hierarchy and the
already-rehearsed selected-case acquisition path.

The binding data flow is:

```text
facts-only NinjaTrader inventory scanner
    -> metadata plus canonical source hashes
    -> inventory-specific provider/provenance validation
    -> deterministic Python calendar and eligibility mapping
    -> source_inventory.json plus exclusions.json
    -> frozen inventory checkpoint
    -> deterministic ten-stratum selection
    -> frozen selection checkpoint
    -> selected ten official source acquisitions
```

## Current-State Gap

The repository already contains:

- the approved multi-window validation protocol;
- a real-NinjaTrader-rehearsed v1.2 selected-case exporter and finalizer;
- schemas for source inventory, exclusions, selection, provenance, toolset
  manifests, and checkpoint attestations; and
- a checkpoint verifier that protects frozen stage ancestry and hashes.

It does not yet contain an official inventory scanner or an evidence-bound
calendar builder. The current source-inventory validation also assumes
`weekday() < 5`, which cannot represent Trading Hours holidays, partial
sessions, or other template-defined session behavior. The current source
inventory and exclusion schemas do not carry the complete scan/evidence
contract defined here. The source-acquisition toolset manifest requires an
exact ten-component set, and checkpoint attestation treats toolset and
selection as first-class stages but not the intervening inventory freeze.

These are deliberate future implementation changes. They are not corrected by
this documentation-only checkpoint.

## Scope

This design defines:

- the official candidate-date universe;
- a facts-only NinjaTrader component named
  `ScanMnq5mSourceInventory`;
- the inventory-specific provider and acquisition evidence contract;
- objective per-date source observations and canonical hashes;
- independent Python verification of the session calendar;
- deterministic eligibility and exclusion mapping;
- inventory and selection freeze boundaries; and
- the tests and file boundaries expected of a later implementation.

The subsystem is specific to the first multi-window cohort:

- instrument: `MNQ SEP26`;
- expiry: September 2026;
- native NinjaTrader bars: `Minute / 5`;
- Trading Hours template: `CME US Index Futures ETH`;
- candidate trading-date range: 2026-06-22 through 2026-07-24 inclusive;
- connection policy: `My NinjaTrader`;
- provider profile: `NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1`;
- runtime provider ID: `Provider31`;
- trace adapter: `Tradovate.Adapter`; and
- historical service: NinjaTrader HDS.

## Non-Goals

This design does not authorize:

- changes to isolated, SHORT, MEDIUM, or LONG recognition;
- hierarchy execution during inventory or selection;
- oracle, blind-project, comparator, or aggregate-result execution;
- automatic repair, sorting, filling, resampling, interpolation, timezone
  conversion, or back-adjustment of source bars;
- automatic expansion of the date range or mixing of contract expiries;
- selection based on visual cleanliness, hierarchy density, trend behavior,
  volatility, or later agreement;
- Chapter 3;
- strategy, signals, entries, exits, PnL, fees, slippage, risk, sizing,
  backtesting, broker orders, or execution; or
- acquisition of official cohort source cases at this design stage.

## Approved Decisions

### 1. Candidate universe

The official candidate universe is the set of verified template-defined
NinjaTrader Trading Hours sessions whose
`SessionIterator.ActualTradingDayExchange` falls from 2026-06-22 through
2026-07-24 inclusive.

The raw scan covers every civil date in that inclusive range. A civil date
without a session remains present in raw coverage evidence as `NO_SESSION`,
but it is not an official source-inventory entry and is not an exclusion.
Actual partial or shortened sessions remain candidates and may be excluded
only by an objective rule such as having fewer than 250 native bars.

### 2. Blind metadata and hashes

The scanner may inspect native OHLCV internally to calculate integrity facts
and cryptographic hashes. It does not export raw OHLCV for every candidate
date. Committed inventory evidence contains objective metadata and hashes only,
not price paths or structural descriptors.

### 3. Evidence storage

Metadata-only official inventory evidence and reproduction provenance are
committed. The exact Trading Hours template snapshot may be committed when it
contains no sensitive account information. Full NinjaTrader configuration,
log, and trace files remain immutable external evidence; committed provenance
binds their SHA-256 values and evidence roles. Credentials, tokens, account
identifiers, and sensitive connection configuration must never be committed.

### 4. One broad provider request

Exactly one historical `RequestBars` event must uniquely qualify for the
official inventory acquisition. Segmented requests are not combined. Zero or
multiple qualifying requests fail the inventory stage. Unrelated requests are
permitted only when they fail at least one qualifying condition and therefore
cannot be mistaken for the official acquisition.

## Approved Refinements

Three refinements constrain the implementation:

1. `OUTSIDE_POLICY` is retained only for compatibility. It is not an ordinary
   exclusion for an in-range official inventory entry and is never a catch-all.
2. Calendar authority is evidence-bound. The scanner records raw facts for all
   civil dates, while Python independently verifies those facts against frozen
   Trading Hours evidence before forming the candidate set.
3. The proven selected-case v1.2 path is protected. Implementation reuses its
   semantics and tests without requiring a provider-code refactor; any change
   to that path triggers the frozen real-evidence finalizer regression before
   official inventory execution.

## Candidate-Universe Semantics

The policy begins with the complete civil-date sequence from 2026-06-22
through 2026-07-24. Neither C# nor Python may replace this sequence with a
weekday filter.

For every civil date, the scanner records the session observation produced by
the exact runtime Trading Hours template. Python separately interprets the
frozen template/session evidence and derives the expected session assignment.
The verified candidate set contains one entry for every unique
`ActualTradingDayExchange` in the policy range for which an actual template
session exists.

The following distinctions are binding:

- `SESSION` means the frozen template assigns an actual session and exchange
  trading date.
- `NO_SESSION` means the frozen template assigns no session for that civil
  date.
- A scheduled break or scheduled closure within a session is not missing data.
- A shortened session is still a `SESSION`.
- A civil `NO_SESSION` observation does not become an exclusion-ledger row.
- An actual session may begin on a different civil date from its
  `ActualTradingDayExchange`; exchange trading date, not the session-open civil
  date, controls membership.
- Duplicate or conflicting assignments for one exchange trading date are an
  error, not something Python silently deduplicates.

The official `source_inventory.json` contains exactly the verified actual
trading dates, in strictly increasing exchange-trading-date order. It does not
contain raw `NO_SESSION` civil dates.

The approved range is the first cohort's bounded normal-active-period policy
for `MNQ SEP26`; this design adds no second, hidden rollover filter inside that
range. If authoritative provenance later shows that the range includes a
rollover or liquidity-transition interval that violates the approved cohort
policy, official execution stops for a versioned protocol review before an
inventory is produced. It does not retroactively label those dates with
`OUTSIDE_POLICY`.

## Calendar and Session Evidence Model

The inventory universe is evidence-bound through this flow:

```text
complete civil-date range
    -> frozen Trading Hours template and runtime session observations
    -> scanner SESSION / NO_SESSION facts
    -> independent Python session-calendar verification
    -> verified ActualTradingDayExchange candidate set
    -> official source-inventory entries
```

The scanner is one observer, not the calendar-policy authority. Python must not
accept a scanner-declared `SESSION` merely because C# emitted it.

The frozen evidence must provide enough information to verify:

- the exact Trading Hours template name and immutable snapshot;
- the template timezone and daylight-saving interpretation;
- every expected-open segment and scheduled break for each actual session;
- the session begin and end in application time, including UTC offset;
- the corresponding PC/log-time representation needed to correlate runtime
  evidence;
- the assigned `ActualTradingDayExchange`;
- available holiday and partial-session metadata; and
- all raw `SESSION` and `NO_SESSION` observations across the civil range.

Python derives expected sessions from the frozen template evidence using a
pinned, tested interpretation. A missing, unreadable, sensitive-only, or
internally contradictory global template snapshot is an inventory-stage
failure. A concrete per-date disagreement between otherwise valid scanner and
calendar observations maps to `TRADING_HOURS_INCONSISTENCY`.

## Scanner Responsibilities

`ScanMnq5mSourceInventory` is a NinjaTrader facts collector. It may:

- validate the exact runtime master instrument, contract label, expiry, bar
  type, interval, native status, and Trading Hours name;
- enumerate every civil date and corresponding `SessionIterator` observations;
- emit session, exchange-trading-date, holiday, partial-session, segment, and
  timezone facts available from NinjaTrader;
- inspect supplied native bars without changing their order;
- calculate chronology, count, OHLCV-integrity, and session-coverage facts;
- calculate deterministic canonical hashes;
- emit neutral lifecycle markers;
- capture runtime metadata; and
- copy approved evidence snapshots.

It must not:

- declare a date eligible or ineligible;
- assign an exclusion reason;
- perform ten-stratum selection;
- run or import hierarchy, oracle, project, comparator, or strategy logic;
- calculate min/max price, direction, return, range, volatility, swing count,
  trend state, structural density, or another structure-revealing descriptor;
- sort, deduplicate, repair, fill, resample, interpolate, timezone-convert, or
  back-adjust source bars; or
- silently continue after an unknown condition.

The scanner emits observations in supplied chronological order. Invalid order
is recorded as a fact; it is never corrected.

## Inventory Evidence Architecture

The inventory acquisition uses an evidence model derived from the proven v1.2
selected-case semantics but with a separate purpose and artifact contract.
Conceptually it consists of:

1. an inventory runtime capture from NinjaTrader;
2. a raw inventory scan covering all civil dates;
3. the exact Trading Hours template snapshot;
4. hashes and evidence-role records for the exact NinjaTrader configuration,
   log, and trace files;
5. an inventory acquisition-evidence record that validates provider,
   request, lifecycle, and completion chronology;
6. an inventory provenance record binding every input, tool, and output hash;
7. the Python-generated source inventory and exclusion ledger; and
8. checkpoint attestations that freeze and publish the inventory stage before
   selection.

The provider profile describes provider technology only. The exact
`My NinjaTrader` display name remains a separate acquisition-policy binding.
The scanner and finalizer must preserve that separation.

## Broad Provider and RequestBars Proof

Global acquisition evidence is validated before any date-level eligibility
mapping. The qualifying request must:

- name exactly `MNQ SEP26`;
- report provider request period exactly `1 Minute`;
- occur strictly after the selected pre-request Realtime marker;
- occur strictly before the selected post-request initialization marker;
- occur before arm;
- belong to the approved `Provider31` / `Tradovate.Adapter` /
  `My NinjaTrader` / NinjaTrader HDS chain;
- have no intended-provider disconnect in the controlled interval;
- have no competing futures provider activity in that interval;
- start no later than the earliest actual candidate-session begin derived from
  frozen Trading Hours evidence; and
- end no earlier than the latest actual candidate-session end derived from
  frozen Trading Hours evidence.

Coverage is measured against authoritative actual session bounds, not civil
midnights such as `2026-06-22 00:00` and `2026-07-24 23:59`.

Exactly one request must satisfy every condition. Other contract months,
current-day refreshes, insufficient ranges, and unrelated periods may appear
as non-qualifying evidence. Neither first-request nor nearest-request selection
is allowed. If a real official rehearsal proves one broad request impossible,
execution stops for a versioned protocol review; implementation must not
silently combine request segments or weaken uniqueness.

The global proof also binds:

- the exact active connection;
- `Provider31` runtime evidence;
- `Tradovate.Adapter` trace lifecycle;
- the NinjaTrader HDS endpoint;
- the immutable log and trace hashes; and
- the relationship among provider-ready, request, scanner, arm, and completion
  times.

A global provider or provenance failure fails the acquisition. It must never be
converted into `INCOMPLETE_PROVENANCE` for every date.

## Lifecycle Markers and Chronology

The future scanner uses these acquisition-specific, neutral semantic event
identifiers with explicit machine-readable `event_time` values:

```text
inventory scanner initialized
inventory realtime lifecycle observed
inventory scan armed
inventory scan complete
```

The schema and parser must bind each identifier to exactly one meaning and the
log representation must include the acquisition ID. Display punctuation is
not evidence; the parsed event identifier, acquisition ID, and `event_time`
are. A UI action itself does not prove acquisition.

The required chronology is:

```text
approved provider, connection, and HDS ready
    <= selected pre-request Realtime event time
    < exactly one qualifying broad RequestBars event
    < selected post-request initialization event time
    <= selected post-request Realtime event time
    < arm event time
    < scan-complete event time
```

Lifecycle ordering uses the explicit marker event times and parsed provider
event times, not incidental line order alone. Completion is valid only when the
completion marker occurs after the output artifacts have been successfully
written and made durable. Reinitialization, missing markers, duplicate
qualifying lifecycle boundaries, or chronology inversion fails the inventory
stage.

## Objective Per-Date Facts

For every raw civil-date observation, the scan provides a stable identifier
and at least:

- civil date;
- `SESSION` or `NO_SESSION`;
- assigned `ActualTradingDayExchange`, or an explicit null for `NO_SESSION`;
- available schedule, holiday, and partial-session metadata;
- every expected-open segment and scheduled break;
- application-time session bounds with offsets;
- PC/log-time session representations needed for evidence correlation; and
- the exact runtime instrument, native bar, and Trading Hours identity.

For every actual session, the scan additionally provides:

- observed native five-minute bar count;
- observed valid count beginning at the declared session start;
- first observed timestamp;
- 250th native timestamp when present;
- last observed session timestamp;
- supplied-order strictly-increasing status;
- duplicate timestamp/index list and count;
- decreasing timestamp/index list and count;
- missing expected-open timestamp list and count;
- unexpected timestamp list and count outside expected-open segments;
- malformed or non-finite OHLCV index list and count;
- invalid OHLC-geometry index list and count;
- negative-volume index list and count;
- non-integral-volume index list and count;
- first-250 canonical source SHA-256 when canonical serialization is possible;
- complete-observed-session SHA-256 when canonical serialization is possible;
  and
- the canonicalization identifier.

Indexes identify supplied scan order. Counts and index lists must reconcile.
The scan must distinguish scheduled non-open timestamps from unexpected missing
timestamps. It must not add price-derived summaries beyond what is necessary
to identify malformed geometry and compute hashes.

## Canonical Source Hashing

The scanner computes SHA-256 over canonical source bytes. Each serialized bar
uses the selected-case representation:

```text
yyyyMMdd HHmmss;Open;High;Low;Close;Volume
```

Canonicalization is:

- supplied chronological order, with no sorting;
- invariant culture;
- the same round-trip numeric representation as the existing selected-case
  exporter;
- UTF-8 without BOM;
- line feed (`LF`) as the newline convention; and
- one final newline after the last record.

The canonicalization identifier must be versioned and recorded. The first-250
hash covers exactly the first 250 observed native five-minute records beginning
at the declared session start. It is emitted only when 250 records and valid
canonical bytes are available. The complete-session hash covers all observed
native records assigned to the session in supplied order, including
canonically serializable defect-bearing records. This makes the hash an
identity control rather than a statement that the session is eligible.

The scanner records these values as `first_250_source_sha256` and
`complete_session_source_sha256`. Inventory-time Python validates their schema,
presence where required, provenance binding, and consistency across metadata
artifacts. It does not independently recompute either value from candidate
OHLCV because raw candidate OHLCV is intentionally not exported to Python.
At this stage each value is a provenance-bound scanner identity claim, not an
independently reproduced price-source digest.

Hash presence does not make a date eligible. Python evaluates the accompanying
chronology, count, calendar, and data-integrity facts. After deterministic
selection, the selected-case acquisition produces the actual official
`bars.txt`; that file's canonical SHA-256 is independently recomputed and must
equal the selected date's frozen `first_250_source_sha256` byte-for-byte.

## Blindness Model

Inventory and selection are blind to market structure. Their processes,
artifacts, tests, and execution environments must not access or emit:

- isolated recognition or unresolved potential;
- SHORT, MEDIUM, or LONG points, vertices, suppression, or provenance;
- trend state, BMS, SMS, support, resistance, or structural density;
- swing counts or subjective chart quality;
- oracle results;
- blind-project results;
- comparator or aggregate-result output; or
- signals, trades, or profitability data.

The raw scan contains no OHLCV rows. Hashes are one-way identity controls, not
a source of selection features. The selector receives only the frozen eligible
date sequence and required checkpoint identities.

## Artifact Contract

The proposed official acquisition output contains these conceptual artifacts:

```text
inventory_runtime_capture.json
inventory_scan.json
trading_hours_template.xml
inventory_acquisition_evidence.json
inventory_provenance.json
source_inventory.json
exclusions.json
```

External immutable evidence additionally includes:

```text
NinjaTrader.Config.xml
NinjaTrader log
NinjaTrader trace
```

`inventory_scan.json` is raw scanner evidence for all civil dates.
`source_inventory.json` is the Python-verified actual-trading-date inventory.
`exclusions.json` contains only excluded actual candidate dates. These three
concepts must not be collapsed.

All committed JSON artifacts use schemas that reject unknown fields. Every
artifact records its schema version, cohort/acquisition identity, producing
tool checkpoint, direct input hashes, and aggregate payload hash where
applicable. Cross-artifact dates, counts, hashes, and status fields must
reconcile exactly.

## Sensitive Evidence Handling

The following may be committed:

- the metadata-only raw scan;
- inventory acquisition evidence and provenance;
- source inventory and exclusion ledger;
- checkpoint attestations;
- selection registry after selection; and
- the exact Trading Hours snapshot after a sensitivity review.

The following remain outside Git as read-only evidence:

- full NinjaTrader configuration;
- full NinjaTrader logs;
- full NinjaTrader traces; and
- any artifact containing credentials, tokens, account information, or
  sensitive local configuration.

Committed provenance records each external evidence artifact's exact SHA-256,
byte length, role, acquisition ID, and documented external storage location or
retrieval procedure. Local paths alone are not provenance. Evidence files are
copied without trimming, normalization, or rewriting.

## Python Eligibility Authority

Python is the sole policy authority. Its inventory finalizer executes in this
order:

1. validate the frozen toolset and pinned production hierarchy commit;
2. validate global runtime, provider, connection, HDS, RequestBars, lifecycle,
   artifact-hash, and provenance evidence;
3. verify that the raw scan covers every civil date exactly once;
4. independently derive the expected session calendar from frozen Trading
   Hours evidence;
5. compare scanner `SESSION` / `NO_SESSION`, segments, and exchange trading
   dates against that independent derivation;
6. form the strictly chronological actual candidate-date set;
7. validate all objective facts plus the format, required presence,
   provenance binding, and cross-artifact consistency of scanner-reported
   canonical hashes for each candidate, without recomputing hidden candidate
   OHLCV hashes;
8. map every applicable date-scoped condition to the frozen exclusion enum and
   ordering;
9. write `source_inventory.json` and `exclusions.json` together as one atomic
   logical result; and
10. report whether at least ten eligible dates exist.

The finalizer does not repair input and does not delegate eligibility back to
the scanner. If a condition cannot be mapped to an approved rule, it stops
instead of inventing a catch-all reason.

## Exclusion Mapping

The compatibility enum retains this frozen order:

1. `INCOMPLETE_PROVENANCE`
2. `FEWER_THAN_250_NATIVE_BARS`
3. `DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS`
4. `TRADING_HOURS_INCONSISTENCY`
5. `MALFORMED_OR_NON_FINITE_OHLCV`
6. `INVALID_OHLC_GEOMETRY`
7. `UNEXPECTED_MISSING_BARS`
8. `SOURCE_CORRUPTION`
9. `SOURCE_HASH_MISMATCH`
10. `OUTSIDE_POLICY`

During official inventory construction, `SOURCE_HASH_MISMATCH` and
`OUTSIDE_POLICY` are not emitted as ordinary date-level exclusions. The other
applicable date-scoped reasons are recorded in the relative order shown above.
The mapping is deterministic:

- `INCOMPLETE_PROVENANCE` means a concrete date-scoped required fact or
  evidence item is absent. It never substitutes for a failed global provider
  or acquisition proof.
- `FEWER_THAN_250_NATIVE_BARS` means fewer than 250 valid observed native bars
  are available beginning at the declared session start.
- `DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS` means one or more duplicate or
  decreasing supplied-order timestamps exist.
- `TRADING_HOURS_INCONSISTENCY` means the otherwise valid scanner/session
  observation conflicts with independently verified frozen Trading Hours
  evidence.
- `MALFORMED_OR_NON_FINITE_OHLCV` means a required value cannot be parsed or is
  non-finite, or a volume value violates the required non-negative integral
  representation.
- `INVALID_OHLC_GEOMETRY` means a parsed bar violates the frozen source
  geometry invariants, including `low <= open/close <= high` and `low <= high`.
- `UNEXPECTED_MISSING_BARS` means an expected-open native timestamp is absent
  after excluding scheduled closures and breaks.
- `SOURCE_CORRUPTION` means a concrete date-scoped read or serialization
  corruption prevents trustworthy use. Corruption of a global artifact fails
  the entire inventory stage.
- `SOURCE_HASH_MISMATCH` is reserved for compatibility and for the later
  selected-case comparison. Inventory-time Python cannot recompute hidden
  candidate OHLCV. A SHA mismatch affecting committed scanner metadata, scan
  JSON, acquisition evidence, provenance, or an external evidence binding is
  an inventory-stage integrity/provenance failure, not a date-level exclusion.
  After selection, Python independently hashes the acquired official
  `bars.txt` and compares it with the frozen inventory
  `first_250_source_sha256`. A mismatch stops the cohort for discrepancy
  classification and review; it does not exclude or replace the selected date,
  rerun selection, or choose a substitute.
- `OUTSIDE_POLICY` remains in the enum only for schema compatibility. Under
  normal official v1 execution, an out-of-range date is not a source-inventory
  entry and therefore does not receive this reason. It is not a catch-all.

When date-scoped corruption makes a downstream check impossible, the finalizer
records the concrete corruption/provenance reason and does not manufacture
additional inferred defects. Unknown or unmapped conditions stop inventory
processing for review.

## Inventory Sufficiency and COHORT_INCOMPLETE

An inventory is structurally valid only when global proof passes and every
actual candidate date is deterministically classified. Let `D` be its strictly
chronological eligible date list.

If `len(D) < 10`, the inventory checkpoint records `COHORT_INCOMPLETE` and
selection does not run. Execution must not:

- expand the date range;
- include `NO_SESSION` civil dates;
- relax quality rules;
- mix a different expiry;
- substitute an excluded date; or
- inspect hierarchy output to seek a more favorable cohort.

`COHORT_INCOMPLETE` is a valid protocol outcome, not permission to adapt the
cohort.

## Deterministic Selection Stage

Selection occurs only after the inventory and exclusions are committed,
published, and checkpoint-verified. It uses
`CHRONOLOGICAL_TEN_STRATA_EARLIEST` version `1.0`.

For chronological eligible dates `D` with `n = len(D)` and `n >= 10`:

```text
start(i) = floor(i * n / 10)
end(i)   = floor((i + 1) * n / 10) - 1
select D[start(i)]
```

for `i = 0..9`.

A dedicated deterministic Python selector creates the selection registry. The
registry is not hand-authored. The selector receives the verified inventory,
exclusion ledger, checkpoint attestations, and hashes; it has no hierarchy,
oracle, blind-project, comparator, or price-path input. The frozen selection
checkpoint precedes acquisition of the ten selected official `bars.txt` files.

## Checkpoint and Freeze Chronology

The binding chronology is:

```text
frozen production hierarchy
    -> inventory scanner/builder/schema tooling commit
    -> frozen and published source-acquisition toolset checkpoint
    -> official broad inventory scan
    -> inventory evidence and provenance
    -> official inventory/exclusions checkpoint
    -> deterministic selection
    -> frozen selection checkpoint
    -> ten selected official source acquisitions
    -> all ten independent oracles
    -> all ten blind project results
    -> exact comparisons
    -> aggregate report
```

Every component needed to interpret the inventory scan, calendar evidence,
hashes, eligibility mapping, exclusions, and selection must be frozen before
the official scan. A downstream stage refuses to run if its expected upstream
commit, artifact hash, schema, or ancestry differs.

## Toolset-Manifest Implications

The current source-acquisition toolset manifest has an exact ten-component
contract. The later implementation must deliberately version and extend that
contract to include, at minimum, the inventory scanner, inventory finalizer,
inventory-specific schemas, and deterministic selector required before the
official scan. It must not insert untracked helpers around the exact-count
validation.

The current checkpoint attestation recognizes toolset and selection artifacts,
but inventory evidence is not fully first-class. The later implementation must
version the attestation schema and verifier so the inventory checkpoint:

- attests the committed raw scan/evidence/provenance/inventory/exclusion
  artifacts;
- binds external template/config/log/trace evidence hashes;
- verifies producing commits and Git object IDs;
- verifies toolset -> inventory -> selection ancestry;
- records remote publication status; and
- refuses selection when inventory attestation is missing or invalid.

Exact schema version numbers and final component paths belong in the later
implementation plan. The semantic requirement to make inventory first-class
is fixed here.

## Existing V1.2 Selected-Case Regression Protection

The existing selected-case acquisition and provenance path has passed a real
NinjaTrader end-to-end rehearsal. Architectural neatness is not sufficient
reason to refactor `tools/validation/mnq_5m_acquisition.py` into a shared
provider module.

Implementation should reuse proven semantics, parsing rules, and regression
fixtures without unnecessarily changing that finalizer. A shared helper is
acceptable only if implementation analysis demonstrates that duplication
creates a greater correctness risk and the change is explicitly reviewed.

If inventory implementation changes selected-case acquisition behavior or its
provider-proof code, the frozen v2 real-evidence finalizer regression must pass
again before any official inventory acquisition begins. The official scan is
blocked until that regression is green.

## Operational NinjaTrader Workflow

The intended operator workflow is:

1. freeze and publish the exact inventory toolset;
2. install the exact scanner and verify its SHA-256;
3. open one `MNQ SEP26` native `Minute / 5` chart;
4. select `CME US Index Futures ETH`;
5. load enough history to cover the earliest actual candidate-session begin
   through the latest actual candidate-session end;
6. connect through `My NinjaTrader`;
7. capture `Provider31`, `Tradovate.Adapter`, and NinjaTrader HDS readiness;
8. conduct one controlled historical acquisition cycle;
9. freeze evidence showing exactly one qualifying broad `RequestBars` event;
10. arm the scanner once with a fresh acquisition identity and output path;
11. let the scanner inspect all civil dates and sessions in one pass;
12. freeze runtime, scan, template, config, log, and trace evidence without
    editing it;
13. run the inventory Python finalizer;
14. freeze and publish the inventory/exclusions checkpoint;
15. run the deterministic selector;
16. freeze and publish the selection checkpoint; and
17. acquire only the selected ten official 250-bar cases through the proven
    selected-case v1.2 path.

Manual acquisition of every candidate date is neither required nor permitted
as a substitute for the one-pass inventory scan.

## Failure and Restart Semantics

- Scanner compile failure is a pre-execution tool defect. Fix, version, and
  rehearse the tool before an official scan.
- Incomplete global provider proof fails the inventory stage and produces no
  official inventory.
- Zero or multiple qualifying broad requests fail the inventory stage.
- Fewer than 250 valid native bars is a date-level exclusion.
- An unexpected missing expected-open bar is a date-level exclusion.
- Fewer than ten eligible dates yields `COHORT_INCOMPLETE`; the range and
  contract remain unchanged.
- A malformed inventory artifact, or any SHA mismatch involving committed
  scanner metadata, scan JSON, acquisition evidence, provenance, or external
  evidence bindings, fails the inventory stage. It is not converted into a
  date-level `SOURCE_HASH_MISMATCH` exclusion.
- A semantic scanner, builder, schema, or verifier correction after inventory
  freeze preserves the old evidence, versions the corrected tool/protocol, and
  restarts official inventory and selection from a fresh acquisition. No
  frozen artifact is silently patched.
- After deterministic selection and official selected-case acquisition, the
  selected `bars.txt` canonical SHA-256 is independently recomputed. A mismatch
  with the frozen inventory `first_250_source_sha256` stops the cohort for
  classification as project, oracle, source/provenance, specification, or
  comparator defect. The date is not excluded or replaced, and selection is
  not rerun.
- An interrupted scan is abandoned with its acquisition identity and output
  path intact. A rerun uses a fresh identity and a new non-existing output
  path.
- Any unknown condition stops execution for explicit review.

## Testing Strategy

The future implementation requires tests that remain independent of hierarchy
output.

### Scanner contract and compatibility

Tests must verify:

- exact `MNQ SEP26`, September 2026, native `Minute / 5`, and Trading Hours
  validation;
- full civil-date coverage including weekends, holidays, and partial sessions;
- stable `SESSION` / `NO_SESSION` and `ActualTradingDayExchange` facts;
- no eligibility or exclusion fields in scanner output;
- no forbidden price-derived or hierarchy fields;
- chronology and defect indexes reflect supplied order without sorting;
- expected-open gaps exclude scheduled breaks;
- canonical first-250 and complete-session hashes use exact bytes; and
- the NinjaTrader source compiles under the supported NinjaTrader environment.

### Calendar and eligibility

Tests must cover:

- independent Python calendar derivation and exact scanner agreement;
- weekend and holiday `NO_SESSION` observations omitted from the official
  inventory without exclusion rows;
- partial sessions retained as candidates;
- every approved exclusion mapping and its frozen ordering;
- global proof failure never expanded into per-date exclusions;
- inventory-time metadata/evidence hash mismatches fail the stage rather than
  becoming `SOURCE_HASH_MISMATCH` exclusions;
- Python validates scanner hash bindings without receiving or recomputing raw
  candidate OHLCV;
- `OUTSIDE_POLICY` retained for compatibility but absent from normal in-range
  v1 output;
- unknown conditions stop instead of mapping to a catch-all;
- inventory and exclusions are written as one reconciling result; and
- `COHORT_INCOMPLETE` does not alter the range or contract.

### Provider and lifecycle evidence

Fixtures must test:

- exactly one qualifying broad request;
- zero and multiple qualifying requests;
- actual-session-bound coverage at both ends;
- rejection of segmented-request combination;
- unrelated non-qualifying requests;
- connection/provider/adapter/HDS mismatches;
- intended-provider disconnect and competing-provider activity;
- marker event-time chronology; and
- completion only after durable artifact write.

### Selection and checkpointing

Tests must verify:

- exact ten-stratum boundaries for varying `n >= 10`;
- earliest eligible date in each stratum;
- deterministic repeated output;
- no price/hierarchy input to the selector;
- toolset -> inventory -> selection ancestry and hashes;
- inventory artifacts as first-class checkpoint evidence;
- later selected-case `bars.txt` canonical SHA-256 comparison against the
  frozen `first_250_source_sha256`, including mismatch stop behavior;
- refusal on remote/checkpoint/hash/schema mismatch; and
- absence of generated/cache/local-only dependencies.

### Regression protection

The full selected-case v1.2 acquisition suite, exporter compatibility suite,
checkpoint-verifier suite, related MNQ validation tests, and full repository
test suite must remain green. If selected-case provider proof changes, the
frozen v2 real-evidence finalizer regression is mandatory before official use.
The frozen hierarchy diff must remain empty.

## Proposed Implementation File Scope

Exact names may be finalized by an approved implementation plan, but expected
scope is limited to:

```text
tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs
tools/validation/mnq_5m_inventory.py
tools/validation/mnq_5m_selection.py
tools/validation/mnq_5m_checkpoint_verify.py
validation/mnq_5m_multiwindow/schemas/<inventory-specific schemas>
validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json
validation/mnq_5m_multiwindow/schemas/exclusions.schema.json
validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json
validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json
validation/mnq_5m_multiwindow/schemas/checkpoint_attestation.schema.json
tests/<focused inventory, scanner, selection, and checkpoint tests>
```

`tools/validation/mnq_5m_acquisition.py` and its tests should remain unchanged
unless a later implementation analysis proves a required dependency. No
production file under `trading/` is in scope. This section declares boundaries,
not an implementation plan or task sequence.

## Compatibility with the 2026-09-13 Protocol

This specification refines, rather than silently replaces, the approved
multi-window protocol. A later implementation must deliberately version or
clarify these existing contracts:

1. The protocol's phrase “every trading date” is resolved through verified
   template sessions, while raw evidence covers every civil date.
2. Weekday-based candidate validation is replaced by
   `ActualTradingDayExchange` derived from frozen Trading Hours evidence.
3. `OUTSIDE_POLICY` remains schema-compatible but is not an ordinary in-range
   candidate exclusion.
4. Inventory schemas gain the evidence, scan-completeness, and canonical-hash
   fields needed by this design.
5. The inventory schema must represent a valid `COHORT_INCOMPLETE` result and
   therefore must not enforce ten entries or ten eligible dates as a schema
   precondition.
6. Selected-case RequestBars coverage remains one session; the inventory
   variant requires one broad request covering all actual candidate sessions.
7. The exact-count toolset manifest is versioned to include inventory scanner,
   builder, schema, and selector components.
8. Checkpoint attestation is extended so inventory is first-class between
   toolset and selection.

No implementation may exploit an older schema's narrower shape to bypass these
requirements.

## Explicit Invariants

1. The frozen hierarchy commit remains
   `04a73e1401d44688660b211d9db6918113482856`.
2. Inventory and selection never execute or inspect hierarchy output.
3. One exact contract expiry is used: `MNQ SEP26`.
4. Candidate membership comes from verified
   `SessionIterator.ActualTradingDayExchange`, never weekday heuristics.
5. Raw scan coverage includes every civil date in the policy range.
6. Official inventory entries include actual sessions only.
7. `NO_SESSION` is raw coverage evidence, not a date-level exclusion.
8. Partial sessions remain candidates and face the same objective rules.
9. The scanner records facts; Python alone assigns eligibility and exclusions.
10. Global proof failure cannot be converted into date-level exclusions.
11. Exactly one broad qualifying RequestBars event is required.
12. Actual session bounds, not civil midnights, define request coverage.
13. Source bars retain supplied order and native timestamps.
14. No raw candidate OHLCV corpus is exported by the inventory scanner.
15. First-250 hashes use the selected-case canonical source representation.
16. Inventory-time Python provenance-binds scanner-computed candidate hashes;
    it does not recompute them from hidden raw candidate bars.
17. `SOURCE_HASH_MISMATCH` is reserved for later selected-source comparison,
    not inventory-time date exclusion.
18. `OUTSIDE_POLICY` is not a normal in-range official exclusion.
19. Inventory and exclusions freeze before deterministic selection.
20. Selection freezes before selected official source acquisition.
21. Selected-case source bytes must match their inventory-stage frozen hashes.
22. The proven selected-case v1.2 path is protected from unnecessary refactor.

## Explicit Prohibited Behaviors

The inventory subsystem must never:

- infer candidate sessions from weekdays;
- trust scanner session declarations without independent evidence validation;
- emit raw price paths for all candidate dates;
- use structure, trend, volatility, returns, or profitability in eligibility;
- accept zero, multiple, or combined segmented broad requests;
- silently sort, repair, fill, interpolate, resample, or convert source bars;
- treat scheduled breaks as unexpected missing bars;
- use `OUTSIDE_POLICY` or another enum as an unknown-error catch-all;
- independently recompute hidden candidate OHLCV hashes during inventory;
- map inventory artifact or evidence-binding hash failures to a normal
  date-level `SOURCE_HASH_MISMATCH` exclusion;
- replace a selected date after a source-hash mismatch;
- rerun selection after a selected-source hash mismatch;
- change the range or mix contracts after `COHORT_INCOMPLETE`;
- patch a frozen official scan in place;
- commit sensitive NinjaTrader environment evidence;
- require refactoring the proven selected-case finalizer for convenience; or
- begin oracle, blind-project, comparison, strategy, or Chapter 3 work.

## Future Implementation Notes

The later implementation plan must resolve exact schema versions, artifact
field names, component-list changes, test fixtures, and command-level freeze
procedure without changing this design's semantics. It must use test-driven
development and rehearse the complete inventory path before the official scan.

The official scan is not authorized until:

- inventory code and schemas are implemented and reviewed;
- the extended toolset manifest and checkpoint verifier pass;
- scanner installation is hash-verified;
- provider and lifecycle evidence rules pass a disposable rehearsal;
- the selected-case v1.2 regression remains proven; and
- the exact source-acquisition toolset checkpoint is published.

## Approval Status

The architecture in this document is approved. Implementation has not started.
This checkpoint authorizes only future planning against the fixed design; it
does not authorize code, schema, NinjaTrader, data-acquisition, cohort,
hierarchy, oracle, blind-project, comparator, or Chapter 3 execution.
