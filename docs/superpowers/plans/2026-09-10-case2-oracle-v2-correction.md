# Real MNQ Case 2 Oracle V2 Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the Real MNQ Case 2 expected hierarchy under the approved fixed left-anchored pairing engineering rule, preserve all original blind-validation history, and compare the unchanged frozen production result against the corrected versioned oracle.

**Architecture:** Keep the original Case 2 oracle v1 and blind project output immutable. Independently regenerate only the expected hierarchy layers affected by the pair-alignment clarification, bind the corrected artifacts to the same frozen source and explicit design/spec commit, record supersession metadata, then perform a semantic comparison against the already-frozen project output without rerunning or rewriting that output.

**Tech Stack:** Python 3, JSON, hashlib, pytest/project validation utilities only where they do not contaminate oracle independence, Git.

**Spec:** `docs/superpowers/specs/2026-09-10-short-term-pair-alignment-clarification-design.md`

## Global Constraints

- The approved specification is binding. Stop and follow it if any instruction below conflicts with it.
- Fixed left-anchored pair alignment is an approved **engineering choice**, not a teacher/course rule. It remains revisable if later approved course or design evidence establishes a different pairing rule.
- Keep the frozen Case 2 source, all four original Case 2 oracle v1 files, and the original Case 2 blind project output byte-for-byte unchanged.
- Keep every Case 1 frozen artifact byte-for-byte unchanged.
- Generate expected values independently from the production analyzer. The oracle generator must not import `trading`, call `trading.analysis.*`, or call any production hierarchy builder.
- Never read the frozen project output while generating short, medium, or long v2. Project output is comparison input only after all corrected expected layers and their manifest have been frozen.
- Use the existing independently frozen Case 2 isolated oracle as source-bound input evidence. Do not create an isolated v2 file or rerun isolated recognition.
- Promote only confirmed isolated recognitions into short v2. Never promote `unresolved_right_edge_potential`.
- Build medium v2 only from corrected short v2 canonical `vertices`, and long v2 only from corrected medium v2 canonical `vertices`.
- Apply fixed-left inside normalization consistently at short, medium, and long levels because all three approved designs use the same normalization representation.
- Preserve all valid points separately from vertices, including points suppressed for `CONSECUTIVE_SAME_KIND` or `INSIDE_STRUCTURE`.
- Preserve source/provenance fields, exact point order, strict comparisons, earliest-on-equality behavior, and unmatched trailing vertices.
- Do not run or rewrite the project analyzer output. Do not add segment, market-state, BMS, SMS, `trend_start_anchor`, strategy, risk, order, broker, live-data, or Chapter 3 behavior.
- Expected count agreement is a checkpoint, not proof. Completion requires point-by-point semantic equality of the unchanged isolated v1 plus short/medium/long v2 against the frozen project output.
- If semantic comparison reports a mismatch, stop with no PASS report and debug the independent oracle. Do not tune expected values from project output. If evidence indicates a production defect, open a separate systematic-debugging and red-to-green TDD task.
- This is an artifact correction, not a production behavior change. Do not invent a production-code RED/GREEN cycle or restore the rejected sliding-alignment test.

## Locked Files and Ownership

Existing immutable inputs:

- `MNQ_2026-09-03_1601-2010_250bars.txt`
- `MNQ_2026-09-03_1601-2010_isolated_ground_truth.json`
- `MNQ_2026-09-03_1601-2010_short_term_ground_truth.json`
- `MNQ_2026-09-03_1601-2010_medium_term_ground_truth.json`
- `MNQ_2026-09-03_1601-2010_long_term_ground_truth.json`
- `MNQ_2026-09-03_1601-2010_project_blind_result.json`

Create exactly these versioned artifacts:

- `MNQ_2026-09-03_1601-2010_short_term_ground_truth_v2.json`
- `MNQ_2026-09-03_1601-2010_medium_term_ground_truth_v2.json`
- `MNQ_2026-09-03_1601-2010_long_term_ground_truth_v2.json`
- `MNQ_2026-09-03_1601-2010_oracle_v2_manifest.json`
- `MNQ_2026-09-03_1601-2010_case2_comparison_report_v2.json`, only after exact comparison

Use a root-level temporary helper named `_case2_oracle_v2.py`. It is an execution aid, not a repository deliverable: never stage it, remove it before final scope verification, and ensure no generated cache is committed.

The v2 layer files retain the v1 layer schema and therefore retain `schema_version: 1`; `correction_version: 2` belongs in the manifest and comparison report. This distinguishes the unchanged JSON shape from the corrected oracle version.

## Locked Baseline Hashes

Verify these lowercase SHA-256 values before any generation and again during final review:

| File | SHA-256 |
| --- | --- |
| `MNQ_2026-09-03_1601-2010_250bars.txt` | `0e23f45bf44c6772a583ff065f0f873643b7ac08810af2ec1bd92b831f13178e` |
| `MNQ_2026-09-03_1601-2010_isolated_ground_truth.json` | `85278477a104149f4236dfe756994bf8c17133850e92cb7bbe9f36221fa10024` |
| `MNQ_2026-09-03_1601-2010_short_term_ground_truth.json` | `d21ec4175bbfd8535cdc348a1910be5d1b099f892b84e245b6c5f96dc493fca6` |
| `MNQ_2026-09-03_1601-2010_medium_term_ground_truth.json` | `ef6f22ec99da2423d4fcbe8239c395f45d4d42b52a55f7832556221c99ccb0cc` |
| `MNQ_2026-09-03_1601-2010_long_term_ground_truth.json` | `52ece3dec476fffdfeff47e4ee0f87cc7b3ae149f5f11d46689e7fb8d224d4ad` |
| `MNQ_2026-09-03_1601-2010_project_blind_result.json` | `3345facb0d98f3bac7f11e53a1374f136df4f2fdd5a78b135dac6b42b5b4bee4` |

Historical commits that must remain reachable and unmodified:

- approved clarification spec: `b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5`
- original Case 2 oracle: `2fccf1302be8e695807a3b41ef47b4f0f8cf10d0`
- original blind project output: `3b812f63beb4b54f1cd2628a28b55fce519293fc`

## Independent Helper Interfaces

The temporary standard-library-only helper must expose these commands:

```text
python _case2_oracle_v2.py verify-baseline
python _case2_oracle_v2.py verify-synthetic
python _case2_oracle_v2.py build-short
python _case2_oracle_v2.py build-medium
python _case2_oracle_v2.py build-long
python _case2_oracle_v2.py build-manifest
python _case2_oracle_v2.py compare
python _case2_oracle_v2.py self-check
```

Its import guard and deterministic serializer are mandatory:

```python
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

FORBIDDEN_PREFIXES = ("trading",)


def assert_independent_imports() -> None:
    imported = sorted(
        name for name in sys.modules
        if name == "trading" or name.startswith("trading.")
    )
    if imported:
        raise SystemExit(f"STOP: production modules imported: {imported}")


def stable_json_bytes(value: object) -> bytes:
    text = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


def write_new_json(path: Path, value: object) -> None:
    if path.exists():
        raise SystemExit(f"STOP: refusing to overwrite {path}")
    path.write_bytes(stable_json_bytes(value))
```

Use exact point identities and recursive provenance rather than object identity:

```python
Point = dict[str, object]


def point_key(point: Point) -> tuple[int, str, float]:
    return int(point["index"]), str(point["kind"]), float(point["price"])


def source_ref(point: Point) -> dict[str, object]:
    return {
        "index": point["index"],
        "kind": point["kind"],
        "price": point["price"],
        "timestamp": point["timestamp"],
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
```

The helper must have these exact generation interfaces:

- `normalize_same_kind(points: list[Point], reason: str) -> tuple[list[Point], list[dict[str, object]]]`
- `normalize_fixed_left_inside(points: list[Point], reason: str) -> tuple[list[Point], list[dict[str, object]]]`
- `recognize_next_level(source_vertices: list[Point], *, level: str, source_level: str) -> tuple[list[Point], list[dict[str, object]]]`
- `make_layer(*, level: str, points: list[Point], potentials: list[dict[str, object]], vertices: list[Point], suppressed: list[dict[str, object]]) -> dict[str, object]`

No task may fill these functions by copying production source. Implement them directly from the approved written rules below, and review the helper for forbidden imports before using its output.

## Exact Independent Rules

### Short v2

1. Read `confirmed` from the unchanged isolated v1 oracle in its existing chronology.
2. Verify the isolated oracle points to the locked source filename and SHA, contains 87 confirmed recognitions and one unresolved right-edge potential, and has no duplicate `(index, kind)` identity.
3. Copy each confirmed recognition into `short.points`, preserving index, kind, price, timestamp, `confirmation_basis`, and `confirmed_by` exactly. Do not include the unresolved potential.
4. Collapse each consecutive same-kind run: highest `HIGH`, lowest `LOW`, and earliest occurrence on an equal extreme. Record every omitted valid point with `CONSECUTIVE_SAME_KIND` and the retained vertex.
5. Anchor at the first surviving candidate and form non-overlapping pairs `[P0,P1]`, `[P2,P3]`, `[P4,P5]`.
6. Compare each complete later pair with the immediately preceding complete pair. Resolve orientation by kind, then suppress the later pair only when `later_high <= earlier_high` and `later_low >= earlier_low`.
7. Record both contained points with `INSIDE_STRUCTURE`, the containing pair, and a monotonically increasing suppression event. Retain them in `points`.
8. After any contained-pair suppression, restart fixed-left pairing from the beginning. Stop after a complete pass makes no suppression. Preserve an unmatched trailing vertex.
9. Never inspect shifted pairs such as `[P1,P2]` against `[P3,P4]`.

### Medium and long v2

For each higher level, use only the immediately lower v2 layer's canonical `vertices`. Partition source vertices by kind while preserving chronology. For every three consecutive same-kind source vertices `(previous, pivot, later)`:

```python
is_high = pivot["kind"] == "HIGH"
confirmed = (
    float(previous["price"]) < float(pivot["price"]) > float(later["price"])
    if is_high
    else float(previous["price"]) > float(pivot["price"]) < float(later["price"])
)
```

When confirmed, emit a point at `pivot`, retain the lower-level source vertex, and set `confirmed_by` to the immediate next same-kind source vertex. For the final same-kind source vertex, emit a right-edge potential only when it has a previous same-kind source, lacks a later same-kind source, and is strictly more extreme than that previous source. Record `previous_same_kind`, `source_vertex`, kind, price, index, timestamp, and source level.

Merge confirmed `HIGH` and `LOW` points into pivot chronology without sorting caller-invalid input; assert the generated merge is strictly increasing and contains no duplicate index. Apply the same highest/lowest/earliest same-kind normalization and the same fixed-left stable inside normalization. Medium consumes short v2 vertices only; long consumes medium v2 vertices only.

## Exact Semantic Comparison Contract

Comparison occurs only after short/medium/long v2 and the manifest exist and pass independent self-checks. It may then read the frozen project output but must not write or revise any oracle artifact.

Normalize only representation differences that are known and lossless:

```python
def canonical_kind(value: str) -> str:
    return value.upper()


def canonical_reason(value: str) -> str:
    return value.upper()


def expected_short_point(point: Point) -> tuple[object, ...]:
    return (
        point["index"], canonical_kind(str(point["kind"])), float(point["price"]),
        str(point["confirmation_basis"]).upper(),
    )


def actual_short_point(point: Point) -> tuple[object, ...]:
    return (
        point["index"], canonical_kind(str(point["kind"])), float(point["price"]),
        str(point["recognition_basis"]).upper(),
    )


def expected_higher_point(point: Point) -> tuple[object, ...]:
    return (
        point["index"], canonical_kind(str(point["kind"])), float(point["price"]),
        point["confirmed_by"]["index"],
    )
```

Add corresponding actual adapters that unwrap medium `pivot` / `confirmed_by` and long nested `pivot` / `confirmed_by` records to the same `(index, kind, price, confirmed_by_index)` identity. Normalize potentials to `(previous_index, pivot_index, kind, price)`. Normalize suppressions to `(normalized_point, reason)`. Compare sequence order as well as content for:

- unchanged isolated v1 confirmed points and unresolved potential against `analysis.hierarchy.isolated`;
- short v2 `points`, `vertices`, and `suppressed`;
- medium v2 `points`, `potentials`, `vertices`, and `suppressed`;
- long v2 `points`, `potentials`, `vertices`, and `suppressed`.

The expected artifacts retain richer timestamps, containing-pair records, and short confirmer timestamps. Independently validate those fields against the source and upstream layer. Do not pretend they exist in the frozen project serialization when they do not. Every shared semantic field and all available recognition/confirmation provenance must match exactly.

The comparison status is exactly one of `EXACT_MATCH`, `MISMATCH`, or `BLOCKED`. `EXACT_MATCH` requires empty mismatches and these counts:

```text
isolated: 87 confirmed / 1 unresolved
short:    87 points / 51 vertices / 36 suppressed
medium:   11 points / 0 potentials / 8 vertices / 3 suppressed
long:     2 points / 1 potential / 2 vertices / 0 suppressed
```

Counts are assertions in addition to, never substitutes for, ordered semantic comparisons.

## Exact Manifest Schema

Build the manifest with code so every hash is computed from final bytes:

```python
manifest = {
    "schema_version": 1,
    "case_id": "real-mnq-case-2",
    "correction_version": 2,
    "status": "FROZEN_AWAITING_COMPARISON",
    "source": {
        "filename": "MNQ_2026-09-03_1601-2010_250bars.txt",
        "sha256": "0e23f45bf44c6772a583ff065f0f873643b7ac08810af2ec1bd92b831f13178e",
    },
    "alignment_rule": {
        "identifier": "fixed_left_anchored_pairs_v1",
        "classification": "engineering_choice",
        "revisable_with_future_approved_evidence": True,
    },
    "approved_clarification": {
        "spec_path": "docs/superpowers/specs/2026-09-10-short-term-pair-alignment-clarification-design.md",
        "commit_sha": "b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5",
    },
    "history": {
        "original_oracle_commit": "2fccf1302be8e695807a3b41ef47b4f0f8cf10d0",
        "original_blind_project_output_commit": "3b812f63beb4b54f1cd2628a28b55fce519293fc",
        "supersedes": [
            "MNQ_2026-09-03_1601-2010_short_term_ground_truth.json",
            "MNQ_2026-09-03_1601-2010_medium_term_ground_truth.json",
            "MNQ_2026-09-03_1601-2010_long_term_ground_truth.json",
        ],
        "supersession_reason": (
            "original v1 silently applied sliding/every-alignment pairing "
            "despite the course leaving alignment unspecified"
        ),
        "original_v1_artifacts_remain_immutable_historical_evidence": True,
    },
    "layers": {
        "isolated": {
            "status": "UNCHANGED_V1_SOURCE",
            "filename": "MNQ_2026-09-03_1601-2010_isolated_ground_truth.json",
            "sha256": "85278477a104149f4236dfe756994bf8c17133850e92cb7bbe9f36221fa10024",
        },
        "short": {"filename": SHORT_V2.name, "sha256": sha256_file(SHORT_V2)},
        "medium": {"filename": MEDIUM_V2.name, "sha256": sha256_file(MEDIUM_V2)},
        "long": {"filename": LONG_V2.name, "sha256": sha256_file(LONG_V2)},
    },
    "future_revision_policy": (
        "Fixed-left pairing may be revisited only with future approved "
        "course or design evidence and a new immutable oracle version."
    ),
}
```

Do not mutate this manifest after it is committed. The comparison report references its hash and records the later comparison outcome.

## Exact Comparison Report Schema

Write this report only when every semantic comparison returns an empty mismatch list:

```python
report = {
    "schema_version": 1,
    "case_id": "real-mnq-case-2",
    "correction_version": 2,
    "status": "EXACT_MATCH",
    "oracle_manifest": {
        "filename": MANIFEST.name,
        "sha256": sha256_file(MANIFEST),
    },
    "frozen_project_output": {
        "filename": PROJECT_RESULT.name,
        "sha256": "3345facb0d98f3bac7f11e53a1374f136df4f2fdd5a78b135dac6b42b5b4bee4",
        "commit_sha": "3b812f63beb4b54f1cd2628a28b55fce519293fc",
        "rerun": False,
    },
    "layers": {
        "isolated": {"status": "EXACT_MATCH", "mismatches": []},
        "short": {"status": "EXACT_MATCH", "mismatches": []},
        "medium": {"status": "EXACT_MATCH", "mismatches": []},
        "long": {"status": "EXACT_MATCH", "mismatches": []},
    },
    "counts": EXPECTED_CASE2_COUNTS,
    "mismatches": [],
}
```

On `MISMATCH`, print a deterministic path/value diff and exit nonzero without creating this file. On malformed, missing, hash-mismatched, or source-unbound input, classify `BLOCKED`, print the exact blocker, and exit nonzero without creating this file.

---

### Task 1: Establish the Immutable Correction Baseline

**Files:**
- Read: all six immutable Case 2 files listed above
- Read: `docs/superpowers/specs/2026-09-10-short-term-pair-alignment-clarification-design.md`
- Temporary: `_case2_oracle_v2.py` (never stage)
- Modify: none

**Interfaces:**
- Consumes: design branch at `b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5`, locked files and hashes.
- Produces: a verified immutable baseline and a standard-library-only helper skeleton that refuses overwrite or production imports.

- [ ] **Step 1: Verify branch, worktrees, and immutable Git history**

Run:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git worktree list --porcelain
git cat-file -e 2fccf1302be8e695807a3b41ef47b4f0f8cf10d0^{commit}
git cat-file -e 3b812f63beb4b54f1cd2628a28b55fce519293fc^{commit}
```

Expected: branch is `design/short-pair-alignment-clarification`, HEAD is the approved plan checkpoint descended from `b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5`, the design worktree is clean, both historical commits exist, and the separate `fix/short-inside-pair-alignment` worktree is present but untouched.

- [ ] **Step 2: Verify every immutable input hash and original blob**

Run a standard-library hash assertion from the repository root:

```powershell
python -c "from pathlib import Path; import hashlib; expected={'MNQ_2026-09-03_1601-2010_250bars.txt':'0e23f45bf44c6772a583ff065f0f873643b7ac08810af2ec1bd92b831f13178e','MNQ_2026-09-03_1601-2010_isolated_ground_truth.json':'85278477a104149f4236dfe756994bf8c17133850e92cb7bbe9f36221fa10024','MNQ_2026-09-03_1601-2010_short_term_ground_truth.json':'d21ec4175bbfd8535cdc348a1910be5d1b099f892b84e245b6c5f96dc493fca6','MNQ_2026-09-03_1601-2010_medium_term_ground_truth.json':'ef6f22ec99da2423d4fcbe8239c395f45d4d42b52a55f7832556221c99ccb0cc','MNQ_2026-09-03_1601-2010_long_term_ground_truth.json':'52ece3dec476fffdfeff47e4ee0f87cc7b3ae149f5f11d46689e7fb8d224d4ad','MNQ_2026-09-03_1601-2010_project_blind_result.json':'3345facb0d98f3bac7f11e53a1374f136df4f2fdd5a78b135dac6b42b5b4bee4'}; actual={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in expected}; assert actual==expected, (actual, expected); print(actual)"
git diff --exit-code 2fccf1302be8e695807a3b41ef47b4f0f8cf10d0 -- MNQ_2026-09-03_1601-2010_isolated_ground_truth.json MNQ_2026-09-03_1601-2010_short_term_ground_truth.json MNQ_2026-09-03_1601-2010_medium_term_ground_truth.json MNQ_2026-09-03_1601-2010_long_term_ground_truth.json
git diff --exit-code 3b812f63beb4b54f1cd2628a28b55fce519293fc -- MNQ_2026-09-03_1601-2010_project_blind_result.json
```

Expected: all hashes match and both diffs are empty. Any mismatch is a hard stop.

- [ ] **Step 3: Create the temporary independent helper skeleton**

Create `_case2_oracle_v2.py` with the constants, import guard, serializer, hash function, overwrite guard, command dispatcher, and function signatures defined above. Its `verify-baseline` command must parse every JSON file, assert the source binding, assert the immutable hashes, assert 87 confirmed isolated recognitions and one unresolved potential, and reject any unexpected key or duplicate point identity.

- [ ] **Step 4: Run the baseline and independence checks**

Run:

```powershell
python _case2_oracle_v2.py verify-baseline
python -c "from pathlib import Path; text=Path('_case2_oracle_v2.py').read_text(encoding='utf-8'); forbidden=('import trading','from trading'); assert not any(token in text for token in forbidden)"
git status --short
```

Expected: `BASELINE VERIFIED`, no forbidden import, and only `_case2_oracle_v2.py` is untracked. Do not commit Task 1.

### Task 2: Build the Independent Short V2 Oracle

**Files:**
- Temporary: `_case2_oracle_v2.py` (never stage)
- Create: `MNQ_2026-09-03_1601-2010_short_term_ground_truth_v2.json`
- Read: frozen source and unchanged isolated v1 oracle

**Interfaces:**
- Consumes: `normalize_same_kind()`, `normalize_fixed_left_inside()`, unchanged isolated v1 `confirmed` evidence.
- Produces: short v2 in v1 layer schema with all 87 valid points, fixed-left canonical vertices, suppression evidence, and no potentials.

- [ ] **Step 1: Add and execute the synthetic alignment proof**

Encode this alternating fixture in `verify-synthetic`:

```python
candidates = [
    {"index": 0, "kind": "HIGH", "price": 105.0},
    {"index": 1, "kind": "LOW", "price": 90.0},
    {"index": 2, "kind": "HIGH", "price": 110.0},
    {"index": 3, "kind": "LOW", "price": 95.0},
    {"index": 4, "kind": "HIGH", "price": 108.0},
    {"index": 5, "kind": "LOW", "price": 85.0},
]
vertices, suppressed = normalize_fixed_left_inside(
    candidates, "INSIDE_STRUCTURE"
)
assert [point["index"] for point in vertices] == [0, 1, 2, 3, 4, 5]
assert suppressed == []

# Shifted [1,2] contains [3,4], but shifted alignment is not evaluated.
assert 108.0 <= 110.0 and 95.0 >= 90.0
```

Also add synthetic assertions for highest `HIGH`, lowest `LOW`, earliest equal extreme, contained fixed-left pair suppression, restart-to-stability, both pair orientations, inclusive boundary equality, one-side breakout preservation, and unmatched trailing preservation.

Run:

```powershell
python _case2_oracle_v2.py verify-synthetic
```

Expected: `SYNTHETIC FIXED-LEFT CHECKS PASSED`. Any failure must be fixed from the written rules, not by consulting project output.

- [ ] **Step 2: Generate short v2 without reading project output**

Implement `build-short` from the exact Short v2 rules. The command must fail if the project-output file has been opened by the generation path, refuse overwrite, and write stable JSON.

Run:

```powershell
python _case2_oracle_v2.py build-short
```

Expected: one new short v2 file. It is acceptable to assert the locked 87 input points; do not use production result counts to alter the normalization.

- [ ] **Step 3: Validate short semantics and determinism**

Add short self-checks that assert:

```python
assert payload["schema_version"] == 1
assert payload["case_id"] == "real-mnq-case-2"
assert payload["level"] == "SHORT"
assert payload["source"]["sha256"] == SOURCE_SHA256
assert len(payload["points"]) == 87
assert payload["potentials"] == []
assert {75, 76}.issubset({point["index"] for point in payload["vertices"]})
assert not ({75, 76} & {item["point"]["index"] for item in payload["suppressed"]})
```

Validate strict chronological point/vertex order, unique identities, exact upstream point preservation, recognition basis and confirmer preservation, legal suppression reasons, suppression membership in `points`, vertex/suppressed partition after same-kind and inside normalization, and source timestamps at every referenced index.

Also assert the independently generated checkpoint counts are 87 points, zero potentials, 51 vertices, and 36 suppressions. These counts are necessary but remain insufficient without Task 6's ordered semantic comparison.

Run:

```powershell
python _case2_oracle_v2.py self-check --through short
python -c "from pathlib import Path; import json; p=Path('MNQ_2026-09-03_1601-2010_short_term_ground_truth_v2.json'); v=json.loads(p.read_text(encoding='utf-8')); assert p.read_bytes()==(__import__('json').dumps(v,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')"
```

Expected: all assertions pass. Record the short v2 SHA in the task review notes.

- [ ] **Step 4: Review and commit only short v2**

Inspect the full file and verify `_case2_oracle_v2.py` remains untracked:

```powershell
git diff --check
git status --short
git add MNQ_2026-09-03_1601-2010_short_term_ground_truth_v2.json
git diff --cached --name-only
git commit -m "Freeze MNQ Case 2 short oracle v2"
```

Expected staged file: short v2 only.

### Task 3: Build the Independent Medium V2 Oracle

**Files:**
- Temporary: `_case2_oracle_v2.py` (never stage)
- Read: `MNQ_2026-09-03_1601-2010_short_term_ground_truth_v2.json`
- Create: `MNQ_2026-09-03_1601-2010_medium_term_ground_truth_v2.json`

**Interfaces:**
- Consumes: corrected short v2 canonical `vertices` only and the higher-level rules above.
- Produces: medium v2 with strict triple provenance, right-edge potentials, same-kind evidence, and fixed-left normalization.

- [ ] **Step 1: Add medium-level synthetic self-checks**

Use source-vertex fixtures that prove strict high/low triples, equality rejection, immediate same-kind confirmer selection, right-edge potential creation/rejection, mixed-kind chronological merge, earliest equal-extreme behavior, fixed-left containment, stable restart, and upstream-vertex-only membership.

Run:

```powershell
python _case2_oracle_v2.py verify-synthetic --level medium
```

Expected: `SYNTHETIC MEDIUM CHECKS PASSED` without importing production modules.

- [ ] **Step 2: Generate medium v2 from short v2 vertices only**

Implement `build-medium` so it verifies short v2 deterministic bytes and source binding before consuming exactly `short_payload["vertices"]`.

Run:

```powershell
python _case2_oracle_v2.py build-medium
```

Expected: one new medium v2 file; no original or short v2 file changes.

- [ ] **Step 3: Validate medium semantics and determinism**

Assert every medium point's `source_vertex` and `confirmed_by` are members of short v2 vertices of the same kind, are immediate adjacent same-kind vertices around the pivot, satisfy the strict triple, and retain index/price/timestamp. Assert every potential is the final eligible same-kind short vertex. Validate all collection order, uniqueness, suppression membership/reasons, fixed-left pairing, stable normalization, and deterministic bytes.

Run:

```powershell
python _case2_oracle_v2.py self-check --through medium
```

Expected: independent semantic checks pass. The expected checkpoint is 11 points, zero potentials, eight vertices, and three suppressions; any count difference requires rule-level debugging before comparison.

- [ ] **Step 4: Review and commit only medium v2**

Run:

```powershell
git diff --check
git add MNQ_2026-09-03_1601-2010_medium_term_ground_truth_v2.json
git diff --cached --name-only
git commit -m "Freeze MNQ Case 2 medium oracle v2"
```

Expected staged file: medium v2 only.

### Task 4: Build the Independent Long V2 Oracle

**Files:**
- Temporary: `_case2_oracle_v2.py` (never stage)
- Read: `MNQ_2026-09-03_1601-2010_medium_term_ground_truth_v2.json`
- Create: `MNQ_2026-09-03_1601-2010_long_term_ground_truth_v2.json`

**Interfaces:**
- Consumes: corrected medium v2 canonical `vertices` only and the higher-level rules above.
- Produces: long v2 with immutable medium provenance and fixed-left normalization.

- [ ] **Step 1: Add long-level synthetic self-checks**

Create independent medium-shaped source fixtures and assert strict high/low triple confirmation, equality rejection, immediate same-kind `confirmed_by`, eligible/ineligible right-edge potential, same-kind normalization, fixed-left containment, stable restart, and provenance retention.

Run:

```powershell
python _case2_oracle_v2.py verify-synthetic --level long
```

Expected: `SYNTHETIC LONG CHECKS PASSED`.

- [ ] **Step 2: Generate long v2 from medium v2 vertices only**

Implement `build-long` so it verifies medium v2 deterministic bytes and source binding, then consumes exactly `medium_payload["vertices"]`.

Run:

```powershell
python _case2_oracle_v2.py build-long
```

Expected: one new long v2 file; all upstream files unchanged.

- [ ] **Step 3: Validate long semantics and determinism**

Assert every long point/potential recursively resolves to canonical medium v2 vertices, all strict comparisons and immediate same-kind relationships hold, collections remain chronological and unique, suppression evidence is legal, and bytes are deterministic.

Run:

```powershell
python _case2_oracle_v2.py self-check --through long
```

Expected checkpoint: two points, one potential, two vertices, and zero suppressions. Exact semantic validation remains mandatory.

- [ ] **Step 4: Review and commit only long v2**

Run:

```powershell
git diff --check
git add MNQ_2026-09-03_1601-2010_long_term_ground_truth_v2.json
git diff --cached --name-only
git commit -m "Freeze MNQ Case 2 long oracle v2"
```

Expected staged file: long v2 only.

### Task 5: Create the Oracle V2 Manifest

**Files:**
- Temporary: `_case2_oracle_v2.py` (never stage)
- Read: all immutable inputs and all three v2 layers
- Create: `MNQ_2026-09-03_1601-2010_oracle_v2_manifest.json`

**Interfaces:**
- Consumes: final byte hashes for source, unchanged isolated v1, and short/medium/long v2.
- Produces: the exact manifest schema above, with auditable supersession and revision policy.

- [ ] **Step 1: Reverify the complete source-bound chain**

Run:

```powershell
python _case2_oracle_v2.py verify-baseline
python _case2_oracle_v2.py self-check --through long
```

Expected: all immutable hashes, JSON schemas, source bindings, and cross-level provenance pass before manifest creation.

- [ ] **Step 2: Build the manifest deterministically**

Implement `build-manifest` using the exact schema above. Compute v2 hashes from bytes; do not paste calculated values by hand. The status remains `FROZEN_AWAITING_COMPARISON` because the manifest is an immutable pre-comparison checkpoint.

Run:

```powershell
python _case2_oracle_v2.py build-manifest
python _case2_oracle_v2.py self-check --through manifest
```

Expected: the manifest parses, hashes all referenced files exactly, names only the three superseded v1 layers, references isolated v1 as unchanged, labels fixed-left `engineering_choice`, and explicitly permits a future approved v3.

- [ ] **Step 3: Review and commit only the manifest**

Run:

```powershell
git diff --check
git add MNQ_2026-09-03_1601-2010_oracle_v2_manifest.json
git diff --cached --name-only
git commit -m "Record MNQ Case 2 oracle v2 manifest"
```

Expected staged file: manifest only.

### Task 6: Compare V2 Semantics with the Frozen Blind Output

**Files:**
- Temporary: `_case2_oracle_v2.py` (never stage)
- Read: unchanged isolated v1, short/medium/long v2, manifest, frozen project output
- Create on exact match only: `MNQ_2026-09-03_1601-2010_case2_comparison_report_v2.json`

**Interfaces:**
- Consumes: independently frozen expected chain and unchanged blind output.
- Produces: deterministic `EXACT_MATCH` report, or a nonzero mismatch/blocker diagnostic with no PASS artifact.

- [ ] **Step 1: Put a hard phase boundary before loading project output**

The `compare` command must first run all baseline, manifest-hash, deterministic-byte, source-binding, and oracle self-checks. Only after they pass may it open `MNQ_2026-09-03_1601-2010_project_blind_result.json`. Verify the frozen result hash and metadata source SHA before reading hierarchy collections.

- [ ] **Step 2: Compare every ordered semantic collection**

Implement the adapters and comparison contract above. Each difference must include a stable JSON path plus expected and actual values, for example:

```python
{
    "path": "short.vertices[17]",
    "expected": [75, "HIGH", 29497.5, "STRICT"],
    "actual": [76, "LOW", 29489.25, "STRICT"],
}
```

Compare isolated confirmations/unresolved potential; short points/vertices/suppressions; medium and long points/potentials/vertices/suppressions; provenance; order; and all summary counts. Do not compare raw JSON formatting or fields absent from one representation.

- [ ] **Step 3: Execute comparison and enforce stop behavior**

Run:

```powershell
python _case2_oracle_v2.py compare
```

Expected: `EXACT_MATCH`, zero mismatches, and one new comparison report matching the exact schema above. If status would be `MISMATCH` or `BLOCKED`, ensure no report file exists, leave all oracle artifacts unchanged, record diagnostics, and stop this plan before commit.

- [ ] **Step 4: Independently parse and verify the report**

Run:

```powershell
python -c "from pathlib import Path; import json; p=Path('MNQ_2026-09-03_1601-2010_case2_comparison_report_v2.json'); r=json.loads(p.read_text(encoding='utf-8')); assert r['status']=='EXACT_MATCH'; assert r['mismatches']==[]; assert all(x['status']=='EXACT_MATCH' and x['mismatches']==[] for x in r['layers'].values()); assert r['frozen_project_output']['rerun'] is False; print(r['status'])"
git diff --check
```

Expected: `EXACT_MATCH` and a clean diff check.

- [ ] **Step 5: Review and commit only the exact-match report**

Run:

```powershell
git add MNQ_2026-09-03_1601-2010_case2_comparison_report_v2.json
git diff --cached --name-only
git commit -m "Record MNQ Case 2 v2 exact comparison"
```

Expected staged file: comparison report only. Do not commit any mismatch report.

### Task 7: Protect Case 1 and Run Repository Regressions

**Files:**
- Read: Case 1 frozen source and existing Case 1 validation runner/checkpoint
- Read: all Case 2 v1/v2 artifacts and report
- Modify: none

**Interfaces:**
- Consumes: completed v2 artifact commits and unchanged production tree.
- Produces: fresh Case 1 checkpoint evidence, regression results, immutable-file proof, and a clean artifact-only scope.

- [ ] **Step 1: Verify Case 1 with the established hierarchy serialization**

Use the repository's known-good Case 1 hierarchy procedure with `MNQ_2026-09-04_1151-1600_250bars.txt`. Run the analyzer for Case 1 only; do not rerun Case 2. Serialize only the hierarchy with the same established dataclass/enum encoder and canonical JSON byte representation used to produce the checkpoint digest.

Assert:

```python
assert counts == {
    "isolated_recognitions": 73,
    "isolated_unresolved_potential": 1,
    "short_points": 73,
    "short_vertices": 47,
    "short_suppressed": 26,
    "medium_points": 9,
    "medium_potentials": 1,
    "medium_vertices": 8,
    "medium_suppressed": 1,
    "long_points": 1,
    "long_potentials": 2,
    "long_vertices": 1,
    "long_suppressed": 0,
}
assert hierarchy_digest == "860a5d148bae81264e2ca8c09f11ae6ee09bd5d105a850a038444e8e67427a60"
```

Expected: exact counts and digest. Do not modify or regenerate any Case 1 artifact.

- [ ] **Step 2: Run focused validation regressions**

Run:

```powershell
python -m pytest tests/test_short_term_structure.py tests/test_medium_term_structure.py tests/test_long_term_structure.py -q
python -m pytest tests/test_offline_hierarchy.py tests/test_offline_market_structure_integration.py -q
python -m pytest tests/test_validation_ground_truth.py tests/test_validation_scoring.py tests/test_blind_validation_workflow.py -q
```

Expected: every focused suite passes. No test should depend on or mutate the new temporary helper.

- [ ] **Step 3: Run the full repository verification**

Run:

```powershell
python -m pytest -q
git diff --check
```

Expected: full suite passes and diff check produces no output.

- [ ] **Step 4: Prove historical artifacts and production files did not change**

Run:

```powershell
python _case2_oracle_v2.py verify-baseline
git diff --exit-code b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5 -- trading tests MNQ_2026-09-03_1601-2010_250bars.txt MNQ_2026-09-03_1601-2010_isolated_ground_truth.json MNQ_2026-09-03_1601-2010_short_term_ground_truth.json MNQ_2026-09-03_1601-2010_medium_term_ground_truth.json MNQ_2026-09-03_1601-2010_long_term_ground_truth.json MNQ_2026-09-03_1601-2010_project_blind_result.json MNQ_2026-09-04_1151-1600_250bars.txt
git diff --name-only b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5..HEAD
```

Expected diff contains exactly the three v2 layer files, manifest, and exact-match report. `_case2_oracle_v2.py` remains untracked at this point. Do not create a Task 7 commit.

### Task 8: Clean Up the Rejected Diagnostic Worktree Only After Success

**Files:**
- Inspect then restore only: `tests/test_short_term_structure.py` in the separate `fix/short-inside-pair-alignment` worktree
- Modify in design worktree: none

**Interfaces:**
- Consumes: successful Task 6 exact comparison and successful Task 7 verification.
- Produces: removal of the rejected uncommitted sliding-hypothesis test, with diagnostic production baseline unchanged.

- [ ] **Step 1: Reconfirm the success gate**

Run in the design worktree:

```powershell
python _case2_oracle_v2.py self-check
python -m pytest -q
git diff --check
```

Expected: v2 remains exact and all tests pass. Do not enter the diagnostic worktree otherwise.

- [ ] **Step 2: Inspect the diagnostic worktree without changing it**

Run using its exact path from `git worktree list --porcelain`:

```powershell
$diagnosticWorktree = 'C:\Users\曹朕语\Documents\Codex\2026-08-28\inspect-the-latest-main-branch-first\work\trader_v1-short-inside-pair-alignment'
git -C $diagnosticWorktree branch --show-current
git -C $diagnosticWorktree rev-parse HEAD
git -C $diagnosticWorktree status --short
git -C $diagnosticWorktree diff -- tests/test_short_term_structure.py
```

Expected: branch `fix/short-inside-pair-alignment`, baseline `3b812f63beb4b54f1cd2628a28b55fce519293fc`, and the sole change is the rejected sliding-alignment RED test in `tests/test_short_term_structure.py`. Any additional change is a hard stop.

- [ ] **Step 3: Discard exactly the approved diagnostic test change**

Only after Step 2 proves the exact target, run:

```powershell
$diagnosticWorktree = 'C:\Users\曹朕语\Documents\Codex\2026-08-28\inspect-the-latest-main-branch-first\work\trader_v1-short-inside-pair-alignment'
git -C $diagnosticWorktree restore -- tests/test_short_term_structure.py
git -C $diagnosticWorktree status --short
git -C $diagnosticWorktree diff --exit-code
git -C $diagnosticWorktree rev-parse HEAD
```

Expected: diagnostic worktree clean and HEAD unchanged at `3b812f...`. This operation removes only the explicitly rejected uncommitted test; it does not modify production or preserve that hypothesis in main.

- [ ] **Step 4: Leave branch/worktree lifecycle to the finishing workflow**

Do not silently delete the diagnostic branch or worktree. Record its clean state. Any later removal must follow `superpowers:finishing-a-development-branch` and respect host-managed worktree ownership.

### Task 9: Final Review and Branch Handoff

**Files:**
- Review: all five new v2 artifacts
- Remove before final scope check: `_case2_oracle_v2.py` and only its generated untracked cache, if any
- Modify: no production, test, source, v1, blind-output, or Case 1 file

**Interfaces:**
- Consumes: complete artifact chain, exact comparison, regression evidence, clean diagnostic worktree.
- Produces: reviewed, pushed design feature branch ready for an explicit integration decision.

- [ ] **Step 1: Request a fresh whole-branch review**

Use `superpowers:requesting-code-review`. Give the reviewer the approved spec, this plan, base commit `b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5`, all artifact hashes, and verification results. Require review of independence, fixed-left semantics, cross-level provenance, immutable history, manifest/report schema, mismatch stop behavior, absence of production changes, and future-revision wording.

Expected: no Critical or Important findings. Fix valid artifact findings without overwriting committed artifacts: add a new corrective commit and repeat scoped review. A finding that changes the approved rule requires stopping for design approval.

- [ ] **Step 2: Remove the temporary helper and verify exact scope**

Delete only the untracked `_case2_oracle_v2.py` after preserving its commands/results in the task ledger. Then run:

```powershell
git status --short
git diff --check
git diff --name-only b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5..HEAD
git log --oneline b6d6eca1cc112fcccf8c6f4db24f2f67c2ec69a5..HEAD
```

Expected changed files, exactly:

```text
MNQ_2026-09-03_1601-2010_short_term_ground_truth_v2.json
MNQ_2026-09-03_1601-2010_medium_term_ground_truth_v2.json
MNQ_2026-09-03_1601-2010_long_term_ground_truth_v2.json
MNQ_2026-09-03_1601-2010_oracle_v2_manifest.json
MNQ_2026-09-03_1601-2010_case2_comparison_report_v2.json
```

Working tree must be clean. No original artifact, production file, test, helper, cache, or Case 1 file may appear.

- [ ] **Step 3: Run fresh completion verification**

Run:

```powershell
python -m pytest -q
git diff --check
git status --short
```

Recompute and verify immutable hashes with the Task 1 assertion. Parse all v2 JSON. Recompute each manifest/report hash reference. Re-run the semantic comparator from a temporary copy outside the repository or reconstruct the helper temporarily without staging it, then remove it and reconfirm clean status.

Expected: full suite green, deterministic artifacts valid, comparison `EXACT_MATCH`, historical hashes unchanged, and clean working tree.

- [ ] **Step 4: Push the branch normally**

Run:

```powershell
git push -u origin design/short-pair-alignment-clarification
git rev-parse HEAD
git rev-parse origin/design/short-pair-alignment-clarification
```

Expected: local and remote branch SHAs match. Do not force-push and do not merge automatically.

- [ ] **Step 5: Use the finishing workflow for the integration decision**

Invoke `superpowers:finishing-a-development-branch`, present its integration menu, and stop for the user's choice. Do not merge, create a pull request, retain/delete a branch, or remove a host-managed worktree without the chosen finishing action.

## Execution Review Checklist

- Fixed-left pairing is labeled an engineering choice everywhere and future approved revision remains possible.
- Source, isolated v1, short/medium/long v1, blind output, and Case 1 bytes match their locked baselines.
- The independent helper imports only Python standard-library modules and never calls production builders.
- Isolated v1 remains the sole isolated source; no isolated v2 exists and unresolved potential is not promoted.
- Short v2 starts from confirmed isolated evidence, applies highest/lowest/earliest same-kind rules, uses only fixed-left pairs, restarts after suppression, and preserves trailing vertices.
- Medium v2 consumes only short v2 vertices; long v2 consumes only medium v2 vertices.
- All points, suppressions, potentials, source vertices, and confirmers are independently checked.
- Manifest supersession, hashes, commits, classification, immutability, and revision policy match the exact schema.
- Comparison reads project output only after the oracle is frozen and never feeds actual values back into expected generation.
- Exact ordered semantics pass; counts alone are not accepted.
- Case 1 counts and digest remain exact.
- The rejected diagnostic test is removed only after successful v2 comparison and regression verification.
- No production, test, original artifact, strategy, risk, execution, broker, live-data, or Chapter 3 change exists.
