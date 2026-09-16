# Official MNQ Five-Minute Inventory Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and rehearse the approved evidence-bound, facts-only MNQ SEP26 inventory acquisition, eligibility, freeze, and deterministic selection tooling without starting the official cohort.

**Architecture:** Use a facts-only NinjaTrader inventory scanner that emits calendar/session/source-quality metadata plus canonical hashes, then validate that evidence in Python, derive eligibility and exclusions deterministically, freeze inventory as a first-class checkpoint, and generate selection with the existing ten-stratum rule. Preserve the proven selected-case v1.2 acquisition path unless a reviewed dependency makes modification unavoidable.

**Tech Stack:** Python 3, pytest, jsonschema Draft 2020-12, NinjaTrader 8 C#, Git/Git object verification, SHA-256.

**Spec:** `docs/superpowers/specs/2026-09-16-mnq-5m-official-inventory-scanner-design.md`

## Global Constraints

- Execution starts from the approved implementation-plan checkpoint on
  `origin/validation/mnq-5m-multiwindow`. Record that SHA as
  `IMPLEMENTATION_BASE`; stop if the remote branch moves before the feature
  branch is created.
- Use an isolated worktree and branch
  `feature/mnq-5m-official-inventory-scanner`; never implement directly on the
  validation branch.
- The exact contract is `MNQ SEP26`, master instrument `MNQ`, expiry month `9`,
  expiry year `2026`.
- The runtime series is native NinjaTrader `Minute / 5` with Trading Hours
  template `CME US Index Futures ETH`.
- The inclusive civil-date and exchange-trading-date policy range is
  `2026-06-22` through `2026-07-24`.
- Candidate membership comes only from independently verified
  `SessionIterator.ActualTradingDayExchange` session evidence.
- Raw scanner evidence represents every civil date in the approved range
  exactly once, including `NO_SESSION` dates.
- Weekday inference is prohibited.
- The scanner records observations only. Python alone assigns eligibility,
  exclusion reasons, and cohort sufficiency.
- The scanner does not export a raw candidate OHLCV corpus.
- The scanner emits `first_250_source_sha256` when available and
  `complete_session_source_sha256` for canonically serializable observed
  sessions using
  `NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1`.
- Inventory-time Python validates scanner hash format and provenance bindings;
  it does not independently recompute hidden candidate OHLCV hashes.
- Exactly one broad qualifying `RequestBars` is required. Its exact instrument
  is `MNQ SEP26`, provider request period is `1 Minute`, and its range covers
  the earliest through latest verified actual candidate-session bounds.
- The provider profile is
  `NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1`; the independent connection policy
  is `My NinjaTrader`; runtime provider is `Provider31`; trace adapter is
  `Tradovate.Adapter`; historical service is NinjaTrader HDS.
- Inventory and selection tooling must not import, execute, inspect, or emit
  hierarchy, oracle, blind-project, comparator, strategy, or profitability
  data.
- Source order is authoritative. No sorting, filling, interpolation,
  resampling, timezone conversion, back-adjustment, deduplication, or repair is
  allowed.
- Inventory freezes before selection. Selection freezes before selected source
  acquisition.
- A later selected official `bars.txt` must match the frozen inventory
  `first_250_source_sha256`; mismatch stops the cohort without exclusion,
  substitution, or reselection.
- Frozen production hierarchy commit
  `04a73e1401d44688660b211d9db6918113482856` never changes.
- Preserve the selected-case v1.2 provider/evidence path and
  `tools/validation/mnq_5m_acquisition.py`. The current exporter SHA-256 is
  `8037c13bbc292984f6f34731b48552c7fd910f80c8aee8a46e6a1ae17beea4d5`.
- No official inventory acquisition, official inventory artifact, official
  selection artifact, hierarchy execution, oracle, blind result, comparator,
  or Chapter 3 work occurs during Tasks 1-11.
- Task 12 is a disposable rehearsal only. Official acquisition requires a
  later, separate authorization.
- Every behavioral task follows RED -> GREEN -> focused regression -> review ->
  bounded commit. Do not batch the twelve task commits into one commit.

---

## Implementation File Map

### New production/validation tools

| Path | Responsibility |
|---|---|
| `tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs` | Facts-only NinjaTrader scanner and metadata/hash emitter |
| `tools/validation/mnq_5m_inventory_common.py` | Inventory constants, strict JSON/schema loading, canonical JSON hashing, atomic writes, and shared error type |
| `tools/validation/mnq_5m_inventory_evidence.py` | Inventory-specific v1.2-style provider/request/lifecycle and external-evidence proof |
| `tools/validation/mnq_5m_inventory_calendar.py` | Independent Trading Hours XML/session verification and candidate derivation |
| `tools/validation/mnq_5m_inventory.py` | Objective date-level eligibility builder and inventory/exclusion CLI |
| `tools/validation/mnq_5m_selection.py` | Deterministic ten-stratum selection generator |
| `tools/validation/mnq_5m_selected_source_check.py` | Later selected `bars.txt` SHA comparison and stop gate |
| `requirements-validation.txt` | Reproducible validation-only dependency pin for Draft 2020-12 schema checks |

### New schemas

| Path | Version |
|---|---|
| `validation/mnq_5m_multiwindow/schemas/inventory_scan.schema.json` | `1.0` |
| `validation/mnq_5m_multiwindow/schemas/inventory_runtime_capture.schema.json` | `1.0` |
| `validation/mnq_5m_multiwindow/schemas/inventory_acquisition_evidence.schema.json` | `1.0` |
| `validation/mnq_5m_multiwindow/schemas/inventory_provenance.schema.json` | `1.0` |

### Modified contracts/checkpoint tooling

| Path | Change |
|---|---|
| `validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json` | Breaking `1.0` -> `2.0` evidence-bound session/hash/outcome contract |
| `validation/mnq_5m_multiwindow/schemas/exclusions.schema.json` | Breaking `1.0` -> `2.0` inventory binding and reserved-reason semantics |
| `validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json` | Breaking `1.0` -> `2.0` first-class inventory checkpoint binding |
| `validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json` | Breaking `1.0` -> `2.0` exact 22-component toolset |
| `validation/mnq_5m_multiwindow/schemas/checkpoint_attestation.schema.json` | Breaking `1.0` -> `2.0` toolset/inventory/selection stages |
| `tools/validation/mnq_5m_checkpoint_verify.py` | `2.0` checkpoint verifier with direct-parent inventory stage |

### Frozen tooling checkpoint artifact

| Path | Responsibility |
|---|---|
| `validation/mnq_5m_multiwindow/toolset_manifest.json` | Task 12 exact 22-component manifest created only after Tasks 1-11 pass review |

`validation/mnq_5m_multiwindow/schemas/provenance.schema.json` remains selected-
case schema `1.2`. `tools/validation/mnq_5m_acquisition.py` and
`tools/validation/ninjatrader/ExportMnq5mCohortSource.cs` remain unchanged.

### Tests

| Path | Coverage |
|---|---|
| `tests/test_mnq_5m_inventory_contracts.py` | Schema versions, strict shapes, enum/reserved semantics |
| `tests/test_ninjatrader_inventory_scanner_compatibility.py` | C# static contract, JSON serializer compatibility, installed-reference compile |
| `tests/test_mnq_5m_inventory_evidence.py` | Provider/request/lifecycle/external evidence |
| `tests/test_mnq_5m_inventory_calendar.py` | XML/session calendar independence and chronology |
| `tests/test_mnq_5m_inventory.py` | Eligibility, exclusions, reconciliation, insufficiency |
| `tests/test_mnq_5m_selection.py` | Ten-stratum generation and freeze preconditions |
| `tests/test_mnq_5m_selected_source_check.py` | Selected-source hash enforcement |
| `tests/test_mnq_5m_checkpoint_verify.py` | Extended first-class inventory checkpoint verification |

## Version and Component Decisions

- New independent artifact families start at `1.0`.
- Existing contracts whose required fields, allowed status values, ancestry, or
  exact component set change move to `2.0`; this avoids interpreting new bytes
  under old semantics.
- Selected-case runtime capture `1.1`, acquisition evidence `1.2`, provenance
  `1.2`, and exporter behavior do not change.
- `jsonschema==4.25.1` is pinned because it supplies
  `Draft202012Validator` without changing runtime production dependencies.
- Toolset manifest `2.0` has exactly these 22 roles:

```text
protocol_spec
inventory_design_spec
validation_dependencies
acquisition_exporter
acquisition_finalizer
inventory_scanner
inventory_common
inventory_evidence_finalizer
inventory_calendar_verifier
inventory_builder
selection_generator
selected_source_checker
checkpoint_verifier
provenance_schema
inventory_scan_schema
inventory_runtime_capture_schema
inventory_acquisition_evidence_schema
inventory_provenance_schema
checkpoint_attestation_schema
selection_registry_schema
source_inventory_schema
exclusion_ledger_schema
```

The exact role-to-path mapping is the one shown in the file map; both schema
and verifier reject missing, duplicate, or additional roles.

### Task 1: Freeze Protocol and Schema Contract Changes

**Files:**
- Create: `requirements-validation.txt`
- Create: `tests/test_mnq_5m_inventory_contracts.py`
- Modify: `validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json`
- Modify: `validation/mnq_5m_multiwindow/schemas/exclusions.schema.json`
- Modify: `validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json`
- Modify: `validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json`
- Modify: `validation/mnq_5m_multiwindow/schemas/checkpoint_attestation.schema.json`
- Test: `tests/test_mnq_5m_inventory_contracts.py`

**Interfaces:**
- Consumes: current `1.0` schemas, the two approved specs, fixed cohort ID
  `mnq-202609-5m-v1`, and frozen hierarchy SHA.
- Produces: Draft 2020-12 version-`2.0` contracts, exact 22-role component
  contract, and dependency pin used by Tasks 4-12.

- [ ] **Step 1: Write the failing schema-contract tests**

  Use `Draft202012Validator.check_schema(schema)` for all five modified
  schemas. Assert the exact versions and required contract changes:

  ```python
  assert inventory["properties"]["schema_version"] == {"const": "2.0"}
  assert inventory["required"] == [
      "schema_version", "status", "cohort_outcome", "cohort_id",
      "contract_policy", "inventory_scan", "inventory_provenance",
      "producing_checkpoint", "candidate_count", "eligible_count",
      "entries", "aggregate_payload_sha256",
  ]
  assert inventory["properties"]["cohort_outcome"]["enum"] == [
      "READY_FOR_SELECTION", "COHORT_INCOMPLETE"
  ]
  assert checkpoint["properties"]["schema_version"] == {"const": "2.0"}
  assert checkpoint["properties"]["artifacts"]["items"]["$ref"] == (
      "#/$defs/artifact"
  )
  assert toolset["properties"]["components"]["minItems"] == 22
  assert toolset["properties"]["components"]["maxItems"] == 22
  ```

  Validate representative `READY_FOR_SELECTION` and `COHORT_INCOMPLETE`
  documents. Validate that `SOURCE_HASH_MISMATCH` and `OUTSIDE_POLICY` remain
  in `$defs.exclusion_reason.enum`, while a schema-level `normally_emitted`
  enum contains only the eight inventory-stage reasons in the design order.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory_contracts.py -v
  ```

  Expected: failures showing version `1.0`, missing `cohort_outcome`, missing
  inventory-stage bindings, missing `inventory` artifact stage, and the old
  ten-role toolset limit.

- [ ] **Step 3: Implement the minimum schema contracts**

  Pin `jsonschema==4.25.1`. Define these exact `source_inventory` entry fields:

  ```json
  {
    "trading_date": "2026-07-01",
    "eligible": true,
    "exclusion_reasons": [],
    "session_begin_application": "20260630 170000",
    "session_end_application": "20260701 160000",
    "observed_native_bar_count": 276,
    "first_250_source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "complete_session_source_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }
  ```

  Permit `first_250_source_sha256: null` only for ineligible sessions with
  fewer than 250 canonically serializable bars. Require
  `complete_session_source_sha256` when the observed session is canonically
  serializable. `candidate_count` equals `len(entries)` and `eligible_count`
  counts `eligible: true`; semantic enforcement belongs to Task 7.

  Define `exclusions 2.0` with `cohort_outcome`, `source_inventory_sha256`,
  `producing_checkpoint`, chronological excluded entries, and aggregate hash.
  Define `selection_registry 2.0` with `trusted_inventory_checkpoint` and bound
  version-`2.0` inventory/exclusion references. Define checkpoint artifacts for
  stages `toolset`, `inventory`, and `selection`.

- [ ] **Step 4: Run focused GREEN verification**

  Run the Task 1 command again. Expected: all contract tests pass and every
  schema passes `Draft202012Validator.check_schema`.

- [ ] **Step 5: Run relevant regression tests**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_acquisition.py -k "semantic_binding_schemas or provenance_schema" -v
  ```

  Expected: selected-case provenance `1.2` assertions remain green; update only
  old inventory/checkpoint-version assertions whose contracts deliberately
  moved to `2.0`.

- [ ] **Step 6: Inspect the diff and invariants**

  Run `git diff --check` and confirm no Python/C#/hierarchy implementation was
  added. Confirm the compatibility enum still contains all ten historical
  values and that only eight are normally emitted by inventory.

- [ ] **Step 7: Commit**

  ```powershell
  git add requirements-validation.txt tests/test_mnq_5m_inventory_contracts.py validation/mnq_5m_multiwindow/schemas
  git commit -m "Define MNQ inventory schema contracts"
  ```

### Task 2: Inventory Scanner Contract and Static Tests

**Files:**
- Create: `tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs`
- Create: `tests/test_ninjatrader_inventory_scanner_compatibility.py`
- Test: `tests/test_ninjatrader_inventory_scanner_compatibility.py`

**Interfaces:**
- Consumes: constants and artifact names fixed by Task 1.
- Produces: compile-shaped C# scanner contract with exact identity, properties,
  constants, lifecycle identifiers, and prohibited-surface guarantees for
  Task 3.

- [ ] **Step 1: Write failing static contract tests**

  Assert the scanner file and class are exactly
  `ScanMnq5mSourceInventory`, with properties `AcquisitionId`, `CohortId`,
  `ArmFilePath`, and `OutputDirectoryPath`. Assert constants for expiry, range,
  bar type/value, Trading Hours name, output filenames, canonicalization ID,
  and these neutral marker fragments:

  ```text
  inventory scanner initialized event_time=
  inventory realtime lifecycle observed event_time=
  inventory scan armed event_time=
  inventory scan complete event_time=
  ```

  Assert the source contains `SessionIterator` and
  `ActualTradingDayExchange`, does not contain `.DayOfWeek`, and does not emit
  fields named `eligible` or `exclusion_reasons`. Assert absence of `bars.txt`,
  raw-row artifact writing, hierarchy/oracle/project/comparator terminology,
  min/max/range/return/volatility/swing summaries, and selection formulas.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_ninjatrader_inventory_scanner_compatibility.py -v
  ```

  Expected: failure because the scanner file does not exist.

- [ ] **Step 3: Add the minimum scanner contract shell**

  Add the class, constants, NinjaScript properties, `SetDefaults`, runtime
  identity guard, and neutral lifecycle logging. Use
  `Calculate.OnBarClose`. The contract shell may remain inert until arm; it
  must compile as an Indicator and must not write any output yet. Define exact
  output names:

  ```csharp
  private const string ScanFileName = "inventory_scan.json";
  private const string RuntimeFileName = "inventory_runtime_capture.json";
  private const string TradingHoursFileName = "trading_hours_template.xml";
  private const string ConfigFileName = "NinjaTrader.Config.xml";
  private const string CanonicalizationId =
      "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1";
  ```

- [ ] **Step 4: Run focused GREEN verification**

  Run the Task 2 command. Expected: all static contract tests pass.

- [ ] **Step 5: Run relevant regression tests**

  Run:

  ```powershell
  python -m pytest tests/test_ninjatrader_exporter_compatibility.py -v
  ```

  Expected: the existing exporter compatibility suite remains green and its
  source hash remains unchanged.

- [ ] **Step 6: Inspect diff and invariant checks**

  Search the new C# file for all forbidden terms and raw candidate file writes.
  Run `git diff --check`. Confirm no installed NinjaTrader file was touched.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs tests/test_ninjatrader_inventory_scanner_compatibility.py
  git commit -m "Define MNQ inventory scanner contract"
  ```

### Task 3: Implement ScanMnq5mSourceInventory

**Files:**
- Modify: `tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs`
- Modify: `tests/test_ninjatrader_inventory_scanner_compatibility.py`
- Test: `tests/test_ninjatrader_inventory_scanner_compatibility.py`

**Interfaces:**
- Consumes: Task 2 class/property/constants contract and native NinjaTrader
  chart bars.
- Produces: atomic metadata-only `inventory_scan.json`,
  `inventory_runtime_capture.json`, `trading_hours_template.xml`, and
  `NinjaTrader.Config.xml` in a fresh acquisition-specific directory.

- [ ] **Step 1: Extend tests for scanner behavior and output shape**

  Add static/serializer tests for these private units:

  ```text
  ValidateRuntimeSeries
  TryArmAcquisition
  EnumerateCivilDates
  CaptureSessionObservation
  InspectSessionBars
  CanonicalizeBar
  Sha256CanonicalRows
  WriteBundleAtomically
  CaptureActiveConnections
  ```

  Compile a small serializer harness, as the existing exporter test does, and
  assert strict top-level scanner keys:

  ```json
  {
    "schema_version": "1.0",
    "acquisition_id": "dryrun-mnq-202609-5m-inventory-20260622-20260724-v1",
    "cohort_id": "mnq-202609-5m-v1",
    "contract": {},
    "bar_series": {},
    "trading_hours": {},
    "civil_date_start": "2026-06-22",
    "civil_date_end": "2026-07-24",
    "canonicalization_id": "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1",
    "observations": [],
    "transformations": {},
    "completed_at": "2026-09-16T12:00:00+08:00"
  }
  ```

  A `NO_SESSION` observation has only civil date, classification, null exchange
  trading date, schedule evidence, and null quality. A `SESSION` observation
  has exact schedule segments plus the complete quality object listed in the
  design.

- [ ] **Step 2: Run the focused test and verify RED**

  Run Task 2's command. Expected: failures for missing units, incomplete output
  shape, non-atomic output, and missing quality/hash fields.

- [ ] **Step 3: Implement the minimum facts-only scanner**

  Implement:

  - exact runtime identity checks for MNQ September 2026, native Minute/5, and
    `CME US Index Futures ETH`;
  - fresh arm-file check: absolute `.arm` path, modification after
    initialization, trimmed content exactly `AcquisitionId`;
  - fresh absolute output directory whose final name equals a sanitized
    `AcquisitionId`, refusing any existing directory;
  - inclusive enumeration of all 33 civil dates without weekday filtering;
  - `SessionIterator` observations and `ActualTradingDayExchange` capture;
  - expected-open segments in application and PC/log representations;
  - supplied-order native bar inspection with index lists/counts for all facts
    in the design;
  - `Open/High/Low/Close.ToString("R", InvariantCulture)` and invariant volume;
  - UTF-8 no BOM, LF, final-newline canonical hash bytes held only in memory;
  - no raw row array in serialized JSON;
  - copy of exact template and Config evidence;
  - temporary-file writes followed by same-volume atomic rename for JSON; and
  - completion marker only after both JSON documents and evidence copies exist
    and hashes have been computed.

  `inventory_runtime_capture.json` binds scan/template/config hashes, runtime
  identity, timezones, active connections, lifecycle timestamps, output file
  names, and scanner SHA recorded by the operator/finalizer. It does not assert
  provider proof or eligibility.

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 2's command. Expected: all scanner contract, serializer, and static
  behavioral assertions pass.

- [ ] **Step 5: Compile against installed NinjaTrader references**

  Run:

  ```powershell
  python -m pytest tests/test_ninjatrader_inventory_scanner_compatibility.py -k "compile" -v
  ```

  Expected: PASS when the installed compile environment is available; otherwise
  an explicit pytest skip, never a claimed compile success.

- [ ] **Step 6: Run regressions and inspect invariants**

  Run both NinjaTrader compatibility test files, `git diff --check`, forbidden-
  term searches, and SHA-256 verification of the unchanged selected-case
  exporter.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs tests/test_ninjatrader_inventory_scanner_compatibility.py
  git commit -m "Add facts-only MNQ inventory scanner"
  ```

### Task 4: Add Inventory Raw-Evidence Schemas

**Files:**
- Create: `validation/mnq_5m_multiwindow/schemas/inventory_scan.schema.json`
- Create: `validation/mnq_5m_multiwindow/schemas/inventory_runtime_capture.schema.json`
- Create: `validation/mnq_5m_multiwindow/schemas/inventory_acquisition_evidence.schema.json`
- Create: `validation/mnq_5m_multiwindow/schemas/inventory_provenance.schema.json`
- Modify: `tests/test_mnq_5m_inventory_contracts.py`
- Test: `tests/test_mnq_5m_inventory_contracts.py`

**Interfaces:**
- Consumes: Task 3 exact scanner output and existing selected-case provider
  schema semantics.
- Produces: four strict Draft 2020-12 schema-`1.0` contracts consumed by Tasks
  5-9.

- [ ] **Step 1: Write failing schema tests with valid and invalid fixtures**

  For each schema call `Draft202012Validator.check_schema`, validate one exact
  minimal document, and reject an unknown property. Add mutation cases for
  wrong cohort/acquisition identity, absent calendar coverage, missing
  provider linkage, invalid hash, missing canonicalization ID, raw OHLCV arrays,
  and forbidden eligibility fields in the scan.

- [ ] **Step 2: Run the focused test and verify RED**

  Run the Task 1 test command. Expected: failures because all four schema files
  are absent.

- [ ] **Step 3: Implement the four strict schemas**

  Use `additionalProperties: false` for every owned object. Required top-level
  fields are:

  ```text
  inventory_scan 1.0:
    schema_version, acquisition_id, cohort_id, contract, bar_series,
    trading_hours, civil_date_start, civil_date_end, canonicalization_id,
    observations, transformations, completed_at

  inventory_runtime_capture 1.0:
    schema_version, acquisition_id, cohort_id, instrument, ninjatrader_version,
    scanner_identity, bar_series, application_timezone, pc_timezone,
    trading_hours, active_connections, connection_snapshot_phase, lifecycle,
    artifact_hashes

  inventory_acquisition_evidence 1.0:
    schema_version, acquisition_id, cohort_id, intended_provider,
    intended_connection_name, historical_trigger, lifecycle, evidence_files,
    expected_toolset_checkpoint, transformations

  inventory_provenance 1.0:
    schema_version, status, acquisition_id, cohort_id, contract, bar_series,
    provider_acquisition, calendar_binding, artifact_hashes, external_evidence,
    inventory_scan_binding, transformations, toolset_binding,
    checkpoint_verification
  ```

  `inventory_scan.observations` must contain the exact per-date facts from the
  design and prohibit raw row arrays. `inventory_provenance.status` is
  `PROVEN`; global evidence failure produces no provenance document.

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 1's command. Expected: all nine schema contracts validate under
  Draft 2020-12.

- [ ] **Step 5: Run relevant regression tests**

  Run schema-focused selected-case acquisition tests. Expected: selected-case
  schema `1.2` remains unchanged and parseable.

- [ ] **Step 6: Inspect diff and invariants**

  Confirm no schema exposes candidate OHLCV, no scanner policy field exists,
  each external evidence item requires role/path/SHA-256/byte length, and
  `git diff --check` passes.

- [ ] **Step 7: Commit**

  ```powershell
  git add validation/mnq_5m_multiwindow/schemas/inventory_*.schema.json tests/test_mnq_5m_inventory_contracts.py
  git commit -m "Add MNQ inventory evidence schemas"
  ```

### Task 5: Add the Inventory Provider and Acquisition Finalizer

**Files:**
- Create: `tools/validation/mnq_5m_inventory_common.py`
- Create: `tools/validation/mnq_5m_inventory_evidence.py`
- Create: `tests/test_mnq_5m_inventory_evidence.py`
- Test: `tests/test_mnq_5m_inventory_evidence.py`

**Interfaces:**
- Consumes: scanner/runtime/evidence artifacts validated against Task 4 schemas,
  immutable template/config/log/trace files, scanner path, trusted toolset
  checkpoint, and repository identity.
- Produces:

  ```python
  class InventoryValidationError(ValueError):
      """Reject invalid inventory evidence without creating official output."""

  @dataclass(frozen=True)
  class ValidatedInventoryEvidence:
      runtime_capture: Mapping[str, object]
      inventory_scan: Mapping[str, object]
      provider_acquisition: Mapping[str, object]
      artifact_hashes: Mapping[str, str]
      external_evidence: tuple[Mapping[str, object], ...]
      earliest_session_begin: datetime
      latest_session_end: datetime

  def finalize_inventory_evidence(
      *,
      runtime_capture_path: str | Path,
      inventory_scan_path: str | Path,
      acquisition_evidence_path: str | Path,
      scanner_path: str | Path,
      trading_hours_template_path: str | Path,
      config_path: str | Path,
      log_path: str | Path,
      trace_path: str | Path,
      trusted_toolset_checkpoint: str,
      repository_path: str | Path,
      expected_repository_identity: str,
      earliest_session_begin: datetime,
      latest_session_end: datetime,
      output_path: str | Path | None = None,
  ) -> ValidatedInventoryEvidence:
      """Validate immutable evidence and the unique request over supplied bounds."""
  ```

- [ ] **Step 1: Write focused failing provider/evidence tests**

  Build a valid fixture with `Provider31`, `Tradovate.Adapter`,
  `My NinjaTrader`, an approved HDS host/port, one broad `MNQ SEP26` `1 Minute`
  request, and lifecycle event times. Add one mutation test per rule:

  - wrong provider, adapter, connection, HDS host/SSL, or Config route;
  - competing futures provider or intended-provider disconnect;
  - marker event time differs from line-prefix time by more than one second;
  - request before pre-Realtime, after post-initialization, or after arm;
  - explicit verified range starts before the request or ends after it;
  - zero or two qualifying requests;
  - unrelated contract/period/insufficient-range requests tolerated;
  - missing/malformed lifecycle marker;
  - external evidence SHA/byte-length mismatch; and
  - malformed scan/runtime cross-binding.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory_evidence.py -v
  ```

  Expected: import failure for `mnq_5m_inventory_evidence`.

- [ ] **Step 3: Implement common strict helpers and evidence finalization**

  In `mnq_5m_inventory_common.py`, implement:

  ```python
  def sha256_bytes(value: bytes) -> str:
      """Return lowercase SHA-256 for exact bytes."""

  def sha256_file(path: Path) -> str:
      """Return lowercase SHA-256 without rewriting the file."""

  def canonical_payload_sha256(
      value: Mapping[str, object],
      hash_field: str = "aggregate_payload_sha256",
  ) -> str:
      """Hash canonical JSON after excluding the named self-hash field."""

  def load_schema_validated_json(
      path: Path, schema_path: Path, label: str
  ) -> dict[str, object]:
      """Load JSON and validate it with Draft 2020-12."""

  def write_json_atomically(path: Path, value: Mapping[str, object]) -> None:
      """Refuse overwrite and publish one canonical JSON object atomically."""
  ```

  Use `jsonschema.Draft202012Validator`, contained relative paths, lowercase
  SHA-256, strict timezone-aware ISO event parsing, and no environment-provided
  Git redirection.

  In the evidence module, reproduce the proven selected-case v1.2 parsing
  semantics without importing or editing `mnq_5m_acquisition.py`. Preserve the
  independent provider profile/connection distinction. Request qualification
  accepts explicit `earliest_session_begin` and `latest_session_end` arguments;
  it must not derive them from scanner claims. Task 5 tests the provider path
  with explicit bounds. Task 7 is the first orchestration step permitted to
  call this function for an inventory result, and must derive those bounds from
  Task 6's independently verified sessions. Require exactly one request that
  covers both supplied bounds.

  Write `inventory_provenance.json` atomically only when `output_path` is
  supplied and every global check passes. A metadata, scan, evidence,
  external-binding, or aggregate-hash mismatch raises
  `InventoryValidationError` and produces no official output; it never becomes
  a date-level exclusion.

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 5's focused command. Expected: all provider, chronology, and evidence
  mutation tests pass.

- [ ] **Step 5: Run selected-case provider regressions**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_acquisition.py -k "provider or historical_request or marker or completion or connection or hds" -v
  ```

  Expected: current selected-case v1.2 semantics remain green and
  `mnq_5m_acquisition.py` has no diff.

- [ ] **Step 6: Inspect diff and invariants**

  Confirm inventory modules do not import `trading`, oracle, blind, or
  comparator modules. Confirm no global proof failure is represented as an
  exclusions list. Run `git diff --check`.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/mnq_5m_inventory_common.py tools/validation/mnq_5m_inventory_evidence.py tests/test_mnq_5m_inventory_evidence.py
  git commit -m "Add MNQ inventory acquisition evidence validation"
  ```

### Task 6: Independently Verify Trading Hours Sessions

**Files:**
- Create: `tools/validation/mnq_5m_inventory_calendar.py`
- Create: `tests/test_mnq_5m_inventory_calendar.py`
- Test: `tests/test_mnq_5m_inventory_calendar.py`

**Interfaces:**
- Consumes: schema-valid `inventory_scan` mapping and exact frozen Trading Hours
  XML bytes.
- Produces:

  ```python
  @dataclass(frozen=True)
  class SessionSegment:
      begin_application: datetime
      end_application: datetime
      begin_pc: datetime
      end_pc: datetime

  @dataclass(frozen=True)
  class VerifiedSession:
      civil_date: date
      trading_date: date
      holiday_name: str | None
      partial_session: bool | None
      segments: tuple[SessionSegment, ...]
      observation: Mapping[str, object]

  def verify_inventory_calendar(
      scan: Mapping[str, object],
      trading_hours_template: bytes,
  ) -> tuple[VerifiedSession, ...]:
      """Verify each civil-date observation against the frozen template."""
  ```

- [ ] **Step 1: Write failing calendar tests**

  Freeze small XML fixtures using the exact element/attribute names observed in
  the NinjaTrader template. Cover:

  - every civil date appears exactly once;
  - Saturday/Sunday and a full holiday are `NO_SESSION` and absent from the
    returned sessions;
  - a partial/shortened session remains returned;
  - a session begins on the prior civil date but uses the next
    `ActualTradingDayExchange`;
  - multiple expected-open segments preserve the scheduled break;
  - duplicate or conflicting exchange trading dates fail;
  - scanner/template classification, segment, holiday, or trading-date
    mismatch fails;
  - application/PC timestamps and UTC offsets are internally consistent;
  - unknown XML layout, missing timezone, and non-chronological segments fail;
  - no deduplication, weekday inference, or session repair occurs.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory_calendar.py -v
  ```

  Expected: import failure for `mnq_5m_inventory_calendar`.

- [ ] **Step 3: Implement the independent parser and verifier**

  Parse the frozen XML with `xml.etree.ElementTree`; accept only the exact
  NinjaTrader element/attribute vocabulary pinned by the fixtures. Derive the
  complete civil-date sequence from constants, apply weekly sessions plus exact
  holiday/partial-holiday overrides, and construct expected application-time
  segments. Compare, field by field, with scanner observations. Use scanner
  PC/log representations only as values to verify against captured offsets;
  never use them to invent an absent session.

  Return strictly chronological unique actual sessions. Raise
  `InventoryValidationError` on an unknown template form or any mismatch.

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 6's command. Expected: all calendar fixtures pass.

- [ ] **Step 5: Run evidence and selected-case calendar regressions**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory_evidence.py tests/test_mnq_5m_acquisition.py -k "trading_hours or session or timezone" -v
  ```

  Expected: both independent inventory calendar rules and selected-case
  session validation pass.

- [ ] **Step 6: Inspect diff and invariant checks**

  Search the new module for `weekday(` and sorting calls; neither may be used
  to form or repair the universe. Confirm `NO_SESSION` observations are checked
  but not returned as candidate sessions. Run `git diff --check`.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/mnq_5m_inventory_calendar.py tests/test_mnq_5m_inventory_calendar.py
  git commit -m "Verify MNQ Trading Hours inventory calendar"
  ```

### Task 7: Build Objective Inventory and Exclusion Artifacts

**Files:**
- Create: `tools/validation/mnq_5m_inventory.py`
- Create: `tests/test_mnq_5m_inventory.py`
- Test: `tests/test_mnq_5m_inventory.py`

**Interfaces:**
- Consumes: scanner/runtime/evidence paths, verified sessions from Task 6,
  inventory provenance, and producing toolset checkpoint.
- Produces:

  ```python
  EXCLUSION_REASON_ORDER: tuple[str, ...] = (
      "INCOMPLETE_PROVENANCE",
      "FEWER_THAN_250_NATIVE_BARS",
      "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS",
      "TRADING_HOURS_INCONSISTENCY",
      "MALFORMED_OR_NON_FINITE_OHLCV",
      "INVALID_OHLC_GEOMETRY",
      "UNEXPECTED_MISSING_BARS",
      "SOURCE_CORRUPTION",
  )

  @dataclass(frozen=True)
  class InventoryBuildResult:
      source_inventory: Mapping[str, object]
      exclusions: Mapping[str, object]

  def build_inventory(
      *,
      evidence: ValidatedInventoryEvidence,
      sessions: Sequence[VerifiedSession],
      inventory_provenance_sha256: str,
      inventory_scan_sha256: str,
      producing_checkpoint: str,
  ) -> InventoryBuildResult:
      """Map verified facts to reconciled inventory and exclusion artifacts."""
  ```

- [ ] **Step 1: Write failing eligibility/reconciliation tests**

  Add one fixture for every reason in `EXCLUSION_REASON_ORDER`, plus:

  - two simultaneous reasons retain that exact order regardless of input map
    order;
  - fewer than 250 native valid bars from session start;
  - duplicate and decreasing supplied-order timestamps;
  - malformed/non-finite OHLC and negative/non-integral volume;
  - invalid OHLC geometry;
  - expected-open absence while scheduled breaks remain valid;
  - concrete date-scoped source read/serialization corruption;
  - partial session with fewer than 250 bars;
  - eligible session with both scanner hashes;
  - `SOURCE_HASH_MISMATCH` and `OUTSIDE_POLICY` are never emitted;
  - global proof failure stops before `build_inventory`;
  - an unknown fact key/state raises instead of becoming an exclusion;
  - `source_inventory.entries` and `exclusions.entries` reconcile exactly;
  - fewer than ten eligible dates yields `cohort_outcome = COHORT_INCOMPLETE`;
  - ten or more yields `READY_FOR_SELECTION`; and
  - candidate range and expiry remain fixed in both outcomes.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory.py -v
  ```

  Expected: import failure for `mnq_5m_inventory`.

- [ ] **Step 3: Implement deterministic mapping and atomic paired output**

  First derive `earliest_session_begin` and `latest_session_end` from the
  strictly ordered Task 6 sessions, then call `finalize_inventory_evidence`
  with those exact bounds and its output path. Stop globally if finalization
  fails. Pass the returned `ValidatedInventoryEvidence` into `build_inventory`.
  Build entries only from verified actual sessions. Treat all scanner quality
  fields as observations, not policy declarations. Require null first-250 hash
  exactly when canonical first-250 bytes are unavailable; never recompute the
  hidden bytes. Sort reasons by `EXCLUSION_REASON_ORDER`, but never sort dates
  or source observations: validate that sessions already arrive strictly
  chronological.

  CLI signature:

  ```text
  python tools/validation/mnq_5m_inventory.py
      --runtime-capture PATH
      --inventory-scan PATH
      --acquisition-evidence PATH
      --inventory-provenance PATH
      --trading-hours-template PATH
      --trusted-toolset-checkpoint SHA
      --producing-checkpoint SHA
      --source-inventory-output PATH
      --exclusions-output PATH
  ```

  Write both outputs to temporary files, validate both against schema `2.0`,
  verify reconciliation and aggregate hashes, then rename both. If either
  write/validation fails, neither final output may exist.

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 7's command. Expected: all mapping, ordering, reconciliation, and
  sufficiency tests pass.

- [ ] **Step 5: Run cross-layer inventory regressions**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory_contracts.py tests/test_mnq_5m_inventory_evidence.py tests/test_mnq_5m_inventory_calendar.py tests/test_mnq_5m_inventory.py -v
  ```

- [ ] **Step 6: Inspect diff and invariants**

  Confirm the builder has no hierarchy imports, no weekday rule, no raw bars,
  and no selection logic. Confirm `SOURCE_HASH_MISMATCH` appears only in enum-
  compatibility checks. Run `git diff --check`.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/mnq_5m_inventory.py tests/test_mnq_5m_inventory.py
  git commit -m "Build objective MNQ source inventory"
  ```

### Task 8: Generate Deterministic Ten-Stratum Selection

**Files:**
- Create: `tools/validation/mnq_5m_selection.py`
- Create: `tests/test_mnq_5m_selection.py`
- Test: `tests/test_mnq_5m_selection.py`

**Interfaces:**
- Consumes: schema-`2.0` frozen source inventory, exclusions, their hashes, and
  a verified inventory-checkpoint attestation.
- Produces:

  ```python
  def generate_selection(
      *,
      source_inventory: Mapping[str, object],
      exclusions: Mapping[str, object],
      trusted_inventory_checkpoint: str,
      producing_checkpoint: str,
  ) -> dict[str, object]:
      """Generate the frozen ten-stratum selection without reordering dates."""
  ```

  Output is selection registry `2.0` using
  `CHRONOLOGICAL_TEN_STRATA_EARLIEST` version `1.0`.

- [ ] **Step 1: Write failing selection tests**

  Cover `n = 10`, `n = 11`, `n = 17`, and another uneven case. Assert for each
  `i = 0..9`:

  ```python
  start = i * n // 10
  end = (i + 1) * n // 10 - 1
  assert selection["selected_eligible_index"] == start
  assert selection["stratum_start_index"] == start
  assert selection["stratum_end_index"] == end
  ```

  Assert exact `w01` through `w10` case names, stable repeated bytes, source-
  inventory/exclusion hashes, no forbidden influence, refusal of
  `COHORT_INCOMPLETE`, refusal of fewer than ten eligible dates, invalid/missing
  inventory attestation, and input order that is not strictly chronological.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_selection.py -v
  ```

  Expected: import failure for `mnq_5m_selection`.

- [ ] **Step 3: Implement minimum selection generator and CLI**

  Preserve eligible input order after validating it; do not sort. Emit exactly
  ten records with window policy `FIRST_250_NATIVE_5M_SESSION_BARS`. Bind
  inventory and exclusion paths, schema versions, hashes, and producing
  inventory checkpoint. Require attestation stage `INVENTORY` and remote
  publication `VERIFIED` when the official-mode CLI flag is used.

  CLI signature:

  ```text
  python tools/validation/mnq_5m_selection.py
      --source-inventory PATH
      --exclusions PATH
      --inventory-attestation PATH
      --trusted-inventory-checkpoint SHA
      --producing-checkpoint SHA
      --output PATH
  ```

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 8's command. Expected: all deterministic and refusal tests pass.

- [ ] **Step 5: Run inventory/selection regressions**

  Run Task 7's cross-layer command plus `tests/test_mnq_5m_selection.py`.

- [ ] **Step 6: Inspect diff and invariant checks**

  Confirm no imports from `trading`, oracle, project, or comparator code and no
  access to scanner hash bytes other than bound strings. Run generator twice
  against one fixture and compare output bytes. Run `git diff --check`.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/mnq_5m_selection.py tests/test_mnq_5m_selection.py
  git commit -m "Add deterministic MNQ inventory selection"
  ```

### Task 9: Make Inventory a First-Class Checkpoint

**Files:**
- Modify: `tools/validation/mnq_5m_checkpoint_verify.py`
- Modify: `tests/test_mnq_5m_checkpoint_verify.py`
- Test: `tests/test_mnq_5m_checkpoint_verify.py`

**Interfaces:**
- Consumes: schema-`2.0` toolset manifest, inventory artifacts, selection
  registry, immutable Git objects, bundle bytes, and optional remote identity.
- Produces:

  ```python
  def verify_inventory_checkpoint(
      *,
      repository_path: str | Path,
      bundle_root: str | Path,
      toolset_manifest_path: str | Path,
      inventory_artifact_paths: Mapping[str, str | Path],
      trusted_toolset_checkpoint: str,
      trusted_inventory_checkpoint: str,
      expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
      remote_name: str | None = None,
      remote_branch: str | None = None,
  ) -> dict[str, Any]:
      """Verify a first-class inventory checkpoint from immutable bytes."""

  def verify_selection_checkpoint(
      *,
      repository_path: str | Path,
      bundle_root: str | Path,
      toolset_manifest_path: str | Path,
      inventory_artifact_paths: Mapping[str, str | Path],
      selection_registry_path: str | Path,
      trusted_toolset_checkpoint: str,
      trusted_inventory_checkpoint: str,
      trusted_selection_checkpoint: str,
      expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
      remote_name: str | None = None,
      remote_branch: str | None = None,
  ) -> dict[str, Any]:
      """Verify selection as the direct child of a trusted inventory stage."""
  ```

  Keep the existing `verify_checkpoints` public function for selected-case v1.2
  regression compatibility; do not reinterpret its old artifacts as v2.

- [ ] **Step 1: Write failing checkpoint tests**

  Extend the synthetic Git fixture to create four direct stages:

  ```text
  component/tooling checkpoint
      -> toolset checkpoint
      -> inventory checkpoint
      -> selection checkpoint
  ```

  Inventory checkpoint must commit exact bytes for runtime capture, scan,
  Trading Hours snapshot, acquisition evidence, inventory provenance, source
  inventory, and exclusions. Its provenance binds external Config/log/trace
  hashes. Test:

  - exact 22 toolset components and executing-tool hash checks;
  - direct-parent enforcement for all three edges;
  - inventory artifact producing commits, Git object IDs, committed bytes,
    bundle hashes, aggregate hashes, and schema versions;
  - `trusted_inventory_checkpoint` in attestation `2.0`;
  - artifact stages `toolset`, `inventory`, and `selection`;
  - remote publication verification for inventory and selection modes;
  - rejection of dirty-bundle substitutions, later commits preserving only
    filenames, reversed ancestry, missing inventory artifacts, and external
    evidence hash mismatch; and
  - old `verify_checkpoints` v1.2 fixture remains green.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_checkpoint_verify.py -v
  ```

  Expected: failures for missing inventory APIs, verifier version `1.0`, old
  ten-role component contract, and absent inventory-stage attestation.

- [ ] **Step 3: Implement verifier `2.0` without weakening v1.2**

  Add exact repository paths for the seven committed inventory artifacts and
  exact 22 component roles. Reuse immutable-object, raw-parent, bundle
  containment, Git-blob, SHA-256, aggregate-hash, no-graft, and remote-query
  helpers. Snapshot each bundle file once before semantic parsing.

  The inventory attestation has `stage = "INVENTORY"`, required toolset and
  inventory checkpoints, no selection checkpoint, and two ancestry edges
  including frozen hierarchy -> toolset. The selection attestation has
  `stage = "SELECTION"`, all three trusted checkpoints, and three ancestry
  edges. Both use schema/version `2.0` and bind the executing verifier hash.

  CLI uses subcommands:

  ```text
  mnq_5m_checkpoint_verify.py inventory --repository-path PATH --bundle-root PATH --toolset-manifest PATH --runtime-capture PATH --inventory-scan PATH --trading-hours-template PATH --acquisition-evidence PATH --inventory-provenance PATH --source-inventory PATH --exclusions PATH --trusted-toolset-checkpoint SHA --trusted-inventory-checkpoint SHA --expected-repository-identity OWNER/REPO
  mnq_5m_checkpoint_verify.py selection --repository-path PATH --bundle-root PATH --toolset-manifest PATH --runtime-capture PATH --inventory-scan PATH --trading-hours-template PATH --acquisition-evidence PATH --inventory-provenance PATH --source-inventory PATH --exclusions PATH --selection-registry PATH --trusted-toolset-checkpoint SHA --trusted-inventory-checkpoint SHA --trusted-selection-checkpoint SHA --expected-repository-identity OWNER/REPO
  ```

  Preserve the existing argument path as `legacy-selected-case` or the current
  no-subcommand behavior so frozen v1.2 tests still execute unchanged.

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 9's command. Expected: all legacy and new checkpoint tests pass.

- [ ] **Step 5: Run schema, inventory, and selection regressions**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory_contracts.py tests/test_mnq_5m_inventory.py tests/test_mnq_5m_selection.py tests/test_mnq_5m_checkpoint_verify.py -v
  ```

- [ ] **Step 6: Inspect diff and invariant checks**

  Confirm exact direct-parent semantics and no mutable-ref trust. Confirm v1.2
  selected-case tests use their unchanged public verifier path. Run
  `git diff --check`.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/mnq_5m_checkpoint_verify.py tests/test_mnq_5m_checkpoint_verify.py
  git commit -m "Make MNQ inventory a first-class checkpoint"
  ```

### Task 10: Enforce the Frozen Hash for Selected Sources

**Files:**
- Create: `tools/validation/mnq_5m_selected_source_check.py`
- Create: `tests/test_mnq_5m_selected_source_check.py`
- Test: `tests/test_mnq_5m_selected_source_check.py`
- Review-only unless the stop gate is triggered: `tools/validation/mnq_5m_acquisition.py`

**Interfaces:**
- Consumes: acquired selected `bars.txt`, case ID, source inventory `2.0`,
  selection registry `2.0`, and a freshly verified selection checkpoint.
- Produces:

  ```python
  @dataclass(frozen=True)
  class SelectedSourceHashBinding:
      case_id: str
      trading_date: str
      expected_sha256: str
      observed_sha256: str
      trusted_inventory_checkpoint: str
      trusted_selection_checkpoint: str

  def verify_selected_source_hash(
      *,
      source_path: str | Path,
      case_id: str,
      source_inventory_path: str | Path,
      selection_registry_path: str | Path,
      checkpoint_attestation: Mapping[str, object],
  ) -> SelectedSourceHashBinding:
      """Stop unless selected source bytes match the frozen inventory hash."""
  ```

- [ ] **Step 1: Write failing selected-source tests**

  Test an exact 250-line canonical file whose SHA matches the chosen inventory
  entry. Reject wrong case/date mapping, unselected case, missing/null frozen
  hash, malformed selection attestation, wrong inventory/selection checkpoint,
  mutated source byte, CRLF-for-LF change, missing final newline, substitution,
  and any request to rerun selection. Assert mismatch raises
  `InventoryValidationError` with a stop message and writes no exclusion or
  replacement artifact.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:

  ```powershell
  python -m pytest tests/test_mnq_5m_selected_source_check.py -v
  ```

  Expected: import failure for `mnq_5m_selected_source_check`.

- [ ] **Step 3: Implement the external pre-finalizer stop gate**

  Validate bound v2 artifacts and the `SELECTION` attestation, locate the exact
  selected case/date, hash the supplied bytes without normalization, compare to
  frozen `first_250_source_sha256`, and return the binding only on equality.
  CLI exits `2` with `STOP:` on mismatch and emits a JSON binding only on
  success.

  This checker runs immediately after selected official acquisition and before
  the existing selected-case finalizer. It does not change provider proof,
  source parsing, or provenance schema `1.2`.

- [ ] **Step 4: Run focused GREEN verification**

  Run Task 10's command. Expected: all exact-byte and stop-behavior tests pass.

- [ ] **Step 5: Run selected-case safety regression and reviewer gate**

  Run the complete `tests/test_mnq_5m_acquisition.py` suite and verify
  `git diff -- tools/validation/mnq_5m_acquisition.py` is empty.

  If execution discovers that the wrapper cannot be placed before the existing
  finalizer without changing selected-case provider/proof semantics, stop this
  task before editing that file. Record the dependency and obtain explicit
  review approval. An approved change must start with a failing regression,
  touch only selection-binding integration, preserve the legacy v1.2 path, run
  the full selected-case suite, and rerun the immutable real v2 finalizer
  evidence rehearsal. No official inventory work proceeds if that rehearsal
  differs or fails.

- [ ] **Step 6: Inspect diff and invariant checks**

  Confirm the normal path modified only the new checker and test, no source
  normalization exists, and no hash mismatch can call the selector. Run
  `git diff --check`.

- [ ] **Step 7: Commit**

  ```powershell
  git add tools/validation/mnq_5m_selected_source_check.py tests/test_mnq_5m_selected_source_check.py
  git commit -m "Enforce selected MNQ inventory source hashes"
  ```

### Task 11: Run Full Regression, Scope, and Cleanliness Gates

**Files:**
- Modify only when a failing test proves an in-scope defect: files introduced
  or deliberately modified by Tasks 1-10
- Test: all focused MNQ validation tests and the full repository suite

**Interfaces:**
- Consumes: all Task 1-10 commits.
- Produces: a reviewed, clean component/tooling checkpoint ready for toolset
  manifest generation and disposable rehearsal.

- [ ] **Step 1: Run focused scanner tests**

  ```powershell
  python -m pytest tests/test_ninjatrader_inventory_scanner_compatibility.py -v
  ```

- [ ] **Step 2: Run schema, provider, calendar, eligibility, and selection tests**

  ```powershell
  python -m pytest tests/test_mnq_5m_inventory_contracts.py tests/test_mnq_5m_inventory_evidence.py tests/test_mnq_5m_inventory_calendar.py tests/test_mnq_5m_inventory.py tests/test_mnq_5m_selection.py tests/test_mnq_5m_selected_source_check.py -v
  ```

- [ ] **Step 3: Run checkpoint and selected-case regressions**

  ```powershell
  python -m pytest tests/test_mnq_5m_checkpoint_verify.py tests/test_mnq_5m_acquisition.py tests/test_ninjatrader_exporter_compatibility.py -v
  ```

- [ ] **Step 4: Run all related MNQ validation tests**

  ```powershell
  python -m pytest tests/test_validation_ground_truth.py tests/test_validation_scoring.py tests/test_blind_validation_workflow.py -v
  ```

- [ ] **Step 5: Run full repository and schema verification**

  ```powershell
  python -m pytest -q
  python -c "from pathlib import Path; import json; from jsonschema import Draft202012Validator; [Draft202012Validator.check_schema(json.loads(p.read_text(encoding='utf-8'))) for p in Path('validation/mnq_5m_multiwindow/schemas').glob('*.schema.json')]"
  git diff --check
  ```

  Expected: zero failures; do not quote an old pass count.

- [ ] **Step 6: Verify frozen boundaries and exact scope**

  ```powershell
  git diff --exit-code 04a73e1401d44688660b211d9db6918113482856 -- trading
  (Get-FileHash -Algorithm SHA256 tools/validation/ninjatrader/ExportMnq5mCohortSource.cs).Hash.ToLowerInvariant()
  git status --short
  git diff --name-only $env:IMPLEMENTATION_BASE...HEAD
  ```

  Expected exporter SHA:
  `8037c13bbc292984f6f34731b48552c7fd910f80c8aee8a46e6a1ae17beea4d5`.
  Confirm no official inventory, exclusions, selection, source, oracle, project,
  or comparison artifact exists.

- [ ] **Step 7: Request fresh whole-branch review**

  Review against both specs. Fix every valid Critical/Important finding with a
  failing test first, rerun affected suites plus `pytest -q`, and obtain scoped
  re-review. Record accepted Minor findings without unrelated cleanup.

- [ ] **Step 8: Commit only if review fixes were required**

  ```powershell
  git add -- requirements-validation.txt tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs tools/validation/mnq_5m_inventory_common.py tools/validation/mnq_5m_inventory_evidence.py tools/validation/mnq_5m_inventory_calendar.py tools/validation/mnq_5m_inventory.py tools/validation/mnq_5m_selection.py tools/validation/mnq_5m_selected_source_check.py tools/validation/mnq_5m_checkpoint_verify.py validation/mnq_5m_multiwindow/schemas tests/test_mnq_5m_inventory_contracts.py tests/test_ninjatrader_inventory_scanner_compatibility.py tests/test_mnq_5m_inventory_evidence.py tests/test_mnq_5m_inventory_calendar.py tests/test_mnq_5m_inventory.py tests/test_mnq_5m_selection.py tests/test_mnq_5m_checkpoint_verify.py tests/test_mnq_5m_selected_source_check.py
  git commit -m "Fix MNQ inventory tooling review findings"
  ```

  If no fix is required, do not create a verification-only commit. The current
  `HEAD` becomes the component/tooling checkpoint for Task 12.

### Task 12: Freeze Tooling and Run a Disposable Inventory Rehearsal

**Files:**
- Create: `validation/mnq_5m_multiwindow/toolset_manifest.json`
- Test: all Task 11 suites plus real disposable rehearsal evidence outside the
  repository

**Interfaces:**
- Consumes: reviewed component/tooling checkpoint, all 22 frozen components,
  NinjaTrader runtime, and a fresh rehearsal identity.
- Produces: published toolset checkpoint plus external disposable rehearsal
  evidence proving scan -> inventory -> inventory checkpoint -> selection ->
  selection checkpoint. It produces no official cohort artifact.

- [ ] **Step 1: Generate the exact toolset manifest from committed bytes**

  Use the Task 11 `HEAD` as `producing_checkpoint`. Generate the 22 components
  in the fixed role order, with repository path, bundle path, lowercase SHA-256,
  and producing commit. Set schema `2.0`, stage `SOURCE_ACQUISITION`, status
  `FROZEN_FOR_SOURCE_ACQUISITION`, cohort ID, frozen hierarchy SHA, runtime and
  pinned dependency versions, JSON canonicalization, deferred downstream
  components, and aggregate hash.

- [ ] **Step 2: Verify RED against an uncommitted manifest, then commit the toolset checkpoint**

  First run the verifier with the future trusted toolset SHA absent and confirm
  it rejects a mutable/uncommitted manifest. Validate schema and hashes, then:

  ```powershell
  git add validation/mnq_5m_multiwindow/toolset_manifest.json
  git commit -m "Freeze MNQ inventory acquisition toolset"
  ```

  The toolset checkpoint must be the direct child of the Task 11 component
  checkpoint. Push the feature branch normally and verify the remote SHA.

- [ ] **Step 3: Prepare a unique rehearsal without touching official paths**

  Use exactly:

  ```text
  acquisition_id = dryrun-mnq-202609-5m-inventory-20260622-20260724-v1
  cohort_id      = mnq-202609-5m-dryrun-inventory-v1
  arm file       = C:\Users\曹朕语\OneDrive\文档\NinjaTrader 8\dryrun\dryrun-mnq-202609-5m-inventory-20260622-20260724-v1.arm
  output         = C:\Users\曹朕语\OneDrive\Desktop\MNQ_5m_Acquisitions\_INVENTORY_REHEARSAL_ONLY\dryrun-mnq-202609-5m-inventory-20260622-20260724-v1
  ```

  Confirm arm/output paths do not exist. Install the scanner only after
  repository and installed SHA-256 equality. Do not overwrite prior evidence.

- [ ] **Step 4: Conduct one controlled broad NinjaTrader rehearsal**

  Open one `MNQ SEP26` native Minute/5 chart using
  `CME US Index Futures ETH`, connect through `My NinjaTrader`, load sufficient
  history, capture provider/HDS readiness, perform one controlled history
  cycle, prove exactly one qualifying broad request, then arm once. Freeze
  unmodified scanner outputs, template, Config, full log, and full trace in the
  rehearsal-only directory with hashes.

- [ ] **Step 5: Run the inventory finalizer and builder in rehearsal mode**

  Run evidence, calendar, and inventory CLIs against copied immutable evidence.
  Validate both output schemas and reconciliation. A failure ends the rehearsal
  without changing code or relaxing rules; classify the defect before any new
  implementation commit.

- [ ] **Step 6: Prove inventory and selection checkpoint flows in an external clone**

  Create a fresh temporary clone at the toolset checkpoint. Commit rehearsal-
  labeled inventory artifacts there as a direct child, run
  `verify_inventory_checkpoint`, generate deterministic selection, commit it as
  the next direct child, and run `verify_selection_checkpoint`. Do not push
  these disposable inventory/selection commits and do not copy them into the
  project worktree.

- [ ] **Step 7: Run final verification and publish only tooling**

  Rerun Task 11's full commands on the feature branch, `git diff --check`,
  scanner/exporter hashes, frozen hierarchy diff, and clean status. Publish the
  feature branch/toolset checkpoint only. Preserve external rehearsal evidence
  read-only.

- [ ] **Step 8: Stop at the authorization boundary**

  Report the toolset checkpoint, hashes, rehearsal status, test counts,
  checkpoint ancestry, and external evidence paths. Do not run the official
  scan, create official inventory/exclusions/selection, acquire a selected
  source, or begin hierarchy/oracle/project/comparison work.

## Implementation Commit Sequence

1. `Define MNQ inventory schema contracts`
2. `Define MNQ inventory scanner contract`
3. `Add facts-only MNQ inventory scanner`
4. `Add MNQ inventory evidence schemas`
5. `Add MNQ inventory acquisition evidence validation`
6. `Verify MNQ Trading Hours inventory calendar`
7. `Build objective MNQ source inventory`
8. `Add deterministic MNQ inventory selection`
9. `Make MNQ inventory a first-class checkpoint`
10. `Enforce selected MNQ inventory source hashes`
11. `Fix MNQ inventory tooling review findings` only when review produces an
    in-scope fix
12. `Freeze MNQ inventory acquisition toolset`

Do not squash these commits and do not merge the feature branch during plan
execution.

## Spec-Coverage Map

| Design section | Implemented by task(s) |
|---|---|
| Context and Motivation | Global constraints; 1; 11 |
| Current-State Gap | 1; 2; 6; 9 |
| Scope | Global constraints; 1-12 |
| Non-Goals | Global constraints; 2; 7; 10; 11; 12 |
| Approved Decisions | 1; 3; 5; 6; 7; 8; 9; 10 |
| Approved Refinements | 1; 5; 6; 7; 9; 10 |
| Candidate-Universe Semantics | 3; 6; 7 |
| Calendar and Session Evidence Model | 3; 6; 7 |
| Scanner Responsibilities | 2; 3 |
| Inventory Evidence Architecture | 4; 5; 9; 12 |
| Broad Provider and RequestBars Proof | 3; 5; 12 |
| Lifecycle Markers and Chronology | 2; 3; 5; 12 |
| Objective Per-Date Facts | 3; 4; 7 |
| Canonical Source Hashing | 3; 4; 7; 10 |
| Blindness Model | Global constraints; 2-8; 10; 11 |
| Artifact Contract | 1; 3; 4; 7; 8; 9 |
| Sensitive Evidence Handling | 4; 5; 9; 12 |
| Python Eligibility Authority | 5; 6; 7 |
| Exclusion Mapping | 1; 7 |
| Inventory Sufficiency and COHORT_INCOMPLETE | 1; 7; 8 |
| Deterministic Selection Stage | 8 |
| Checkpoint and Freeze Chronology | 9; 12 |
| Toolset-Manifest Implications | 1; 9; 12 |
| Existing V1.2 Selected-Case Regression Protection | 5; 10; 11 |
| Operational NinjaTrader Workflow | 3; 5; 9; 12 |
| Failure and Restart Semantics | 3; 5; 7; 9; 10; 12 |
| Testing Strategy | Every task, especially 11 |
| Proposed Implementation File Scope | Implementation File Map; 1-12 |
| Compatibility with the 2026-09-13 Protocol | 1; 8; 9; 10; 11 |
| Explicit Invariants | Global constraints; 2-12 |
| Explicit Prohibited Behaviors | Global constraints; 2; 7; 10; 11; 12 |
| Future Implementation Notes | Execution Handoff; 12 |
| Approval Status | Execution Handoff |

## Execution and Review Gates

- Each task receives a fresh spec-compliance and code-quality review before the
  next task begins. Fix Critical/Important findings and re-review the scoped
  fix.
- If exact NinjaTrader XML vocabulary differs from the Task 6 frozen fixture,
  stop and update the plan/spec through review; do not accept unknown elements
  or infer session meaning.
- If one broad request is impossible in a real rehearsal, stop for protocol
  versioning; do not combine requests.
- If selected-case finalizer integration would require changing provider proof,
  stop at Task 10's explicit reviewer gate.
- If origin validation branch moves after implementation starts, stop and
  report divergence; do not silently change `IMPLEMENTATION_BASE`.
- A usage-limit interruption must leave the plan-specific progress ledger
  current with RED/GREEN/review/commit state and the next incomplete step.

## Execution Handoff

At implementation kickoff:

1. fetch origin and verify the approved plan commit is the current
   `origin/validation/mnq-5m-multiwindow`;
2. create `feature/mnq-5m-official-inventory-scanner` from that exact commit in
   an isolated worktree;
3. record `IMPLEMENTATION_BASE`, worktree path, and preflight scan in the SDD
   ledger;
4. execute Tasks 1-12 continuously with TDD and per-task review; and
5. stop after the published tooling checkpoint and successful disposable
   rehearsal.

The execution must not merge to `validation/mnq-5m-multiwindow` or `main`, and
must not start the official inventory scan.
