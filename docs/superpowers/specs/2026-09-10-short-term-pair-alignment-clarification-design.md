# Short-Term Inside-Structure Pair Alignment Clarification

**Date:** 2026-09-10

**Status:** Approved design clarification checkpoint

**Scope:** Chapter 2, Lesson 5 short-term inside-structure pair alignment only

## Purpose

This document clarifies how the project deterministically forms comparable
short-term structural ranges before applying the existing inside-structure
containment rule.

It supplements, without rewriting, the approved Lesson 5 design in
`docs/superpowers/specs/2026-08-30-short-term-structure-design.md`. It does not
change the current production algorithm. It makes explicit that fixed
left-anchored pairing is a neutral project engineering choice rather than a
teacher-defined market rule.

## Background

Lesson 5 defines short-term structure from confirmed isolated points. After
consecutive same-kind normalization, the surviving candidates alternate
between `HIGH` and `LOW`. The existing design then permits a later complete
structural range to be suppressed when it is fully contained within an earlier
complete structural range.

Real MNQ Case 1 and Case 2 exposed an interpretation difference before the
containment calculation:

- current production and the validated Case 1 checkpoint use fixed
  left-anchored pairing;
- the original frozen Case 2 oracle v1 silently used sliding/every-alignment
  pairing; and
- both interpretations can identify numerically valid contained ranges, but
  they do not always select the same ranges for comparison.

The systematic root-cause audit therefore classified the mismatch as
`COURSE-RULE / ENGINEERING AMBIGUITY`, not as a proven production defect.

For example, each of these shifted candidates satisfies the numerical
containment rule:

```text
Case 1:
LOW  122 @ 29609.25
HIGH 128 @ 29692
    contains
LOW  131 @ 29654
HIGH 133 @ 29678

Case 2:
HIGH 71 @ 29501.75
LOW  74 @ 29486.5
    contains
HIGH 75 @ 29497.5
LOW  76 @ 29489.25
```

The inequalities alone do not determine whether these shifted ranges belong
to the project's comparable pair set.

## Course-Derived Facts and Their Boundary

### Opposite-kind structural ranges

A comparable complete structural range contains one `HIGH` and one `LOW`.
Chronological orientation may be either:

```text
HIGH -> LOW
LOW  -> HIGH
```

Orientation changes neither the high boundary nor the low boundary used for
the containment calculation.

### Inclusive complete containment

For an earlier complete range and a later complete range, the later range is
inside only when both conditions hold:

```text
later_high <= earlier_high
AND
later_low >= earlier_low
```

Equality at either boundary counts as contained. If either side escapes the
earlier range, the inside rule does not suppress the later range.

### Repeated application

The containment rule is course-derived. Reapplying that definite rule after a
suppression changes adjacency, continuing until the normalized line is stable,
is the already approved engineering application of the same rule. It does not
add a new containment threshold or discretionary market judgment.

### Alignment is not course-specified

Available teacher/course evidence does not objectively define which of the two
possible alternating pair alignments must be used when both are geometrically
available. In particular, it does not establish:

- that both alignments must be evaluated;
- that every four consecutive alternating points form an additional candidate
  comparison;
- that a shifted alignment must take priority; or
- another structural criterion that selects the alignment.

The Lesson 5 ambiguity policy remains binding: behavior not determined by a
precise course rule must not be presented as teacher-defined fact.

## Approved Engineering Decision

For now, short-term inside-structure normalization uses **fixed left-anchored
pairing**.

After same-kind normalization, the candidate sequence is anchored at its first
vertex. Consecutive non-overlapping pairs are formed as:

```text
[P0, P1]
[P2, P3]
[P4, P5]
...
```

The normalization procedure is:

1. Start from the first normalized candidate vertex.
2. Treat `[P0, P1]` as the first complete opposite-kind range and `[P2, P3]`
   as the next complete range.
3. Apply the existing inclusive two-boundary containment rule.
4. If the later range is not contained, advance to the next complete pair:
   compare `[P2, P3]` with `[P4, P5]`, then continue likewise.
5. If the later range is contained, suppress that entire later pair from line
   vertices while retaining both points in the all-points evidence and
   recording their existing suppression reason.
6. Reapply the same left-anchored procedure from the beginning after changed
   adjacency, and continue until a complete pass makes no further definite
   suppression.
7. Preserve any unmatched trailing vertex. Do not create a synthetic partner.

The evaluator does not additionally inspect the shifted alignment merely
because that shifted range would also satisfy the containment inequalities.

For six alternating candidates:

```text
P0 P1 P2 P3 P4 P5
```

evaluate:

```text
[P0, P1] against [P2, P3]
[P2, P3] against [P4, P5]
```

do not additionally evaluate:

```text
[P1, P2] against [P3, P4]
```

unless later approved course or design evidence changes the rule.

## Rationale

Fixed left-anchored pairing is approved because it:

- gives the normalized sequence one deterministic pairing boundary;
- is conservative about additional suppression when the course does not
  define a shifted pairing;
- preserves current production behavior;
- preserves the previously validated Real MNQ Case 1 behavior;
- matches the exact pairing representation already approved in
  `docs/superpowers/plans/2026-08-31-short-term-structure.md`;
- avoids introducing additional point suppression unsupported by explicit
  course evidence; and
- remains mechanically reversible if later course material defines structural
  pairing more precisely.

This choice preserves the existing distinction between valid points and line
vertices. A point omitted by a definite fixed-left comparison remains valid in
`ShortTermStructure.points`. A shifted candidate not inspected under this rule
also remains preserved rather than being suppressed through an unstated
alignment assumption.

## Explicit Non-Claims

This clarification does **not** claim that:

- fixed-left pairing is a newly discovered teacher/course rule;
- fixed-left pairing is universally correct market theory;
- sliding/every-alignment pairing is inherently invalid;
- the Case 2 production analyzer was proven wrong;
- all visually plausible inside structures must be suppressed; or
- the decision can never be revised.

It records only the current deterministic project representation needed while
the course evidence remains incomplete.

## Validation Consequences

### Real MNQ Case 1

The existing Case 1 checkpoint remains valid under the fixed-left engineering
rule. Its canonical hierarchy and recorded validation result are not changed
by this clarification.

### Real MNQ Case 2

The original frozen Case 2 oracle v1 used a different, unstated sliding
interpretation. It must remain preserved in Git history as evidence of the
original blind-validation process and mismatch.

A later, separately approved correction task must:

- produce a corrected, versioned Case 2 short-term oracle under fixed-left
  pairing;
- regenerate dependent medium-term and long-term expected outputs from that
  corrected canonical short-term input;
- retain clear supersession metadata connecting the corrected artifacts to
  the original oracle version and commits; and
- leave the frozen blind project output unchanged.

The isolated-point oracle and frozen source are not changed by a short-term
pair-alignment correction.

## Frozen Artifact Policy

A frozen oracle or result used in a blind comparison must never be silently
overwritten to make a later comparison pass.

Corrections must:

- use distinct versioned artifacts or an equally explicit immutable version
  boundary;
- identify which earlier artifact is superseded and why;
- preserve original filenames, hashes, and commits in Git history;
- distinguish corrected expected results from the already frozen project
  output; and
- regenerate downstream expected layers only from the corrected canonical
  upstream oracle.

The exact artifact filenames and metadata schema belong to the future
oracle-correction checkpoint. Whatever representation is selected must make
the original and corrected versions independently retrievable and must not
rewrite either historical blob.

## Existing Diagnostic RED Test

The diagnostic worktree contains an uncommitted test asserting that a shifted
alignment is suppressed. That test represents the investigated sliding
hypothesis. Under the current fixed-left engineering decision, it is not an
approved production requirement and is expected to remain RED against current
production.

The test must not be altered as part of this design checkpoint. It should be
removed later in the separately approved implementation/oracle-correction task
after its diagnostic provenance has been recorded. Its presence must not be
used to characterize current production as defective.

## Future-Change Trigger

Fixed-left pairing may be revisited only when at least one of the following is
available and the resulting change is explicitly approved:

- a direct teacher explanation of structural-range pairing;
- a course diagram or transcript establishing shifted/every-alignment
  comparison;
- a later course lesson defining structural pairing differently; or
- an explicit user-approved engineering redesign supported by new validation
  consequences.

Any revision must address backward compatibility, Case 1 and Case 2 oracle
versioning, downstream medium/long expectations, and the distinction between
course rules and project engineering rules before production changes.

## Relationship to Existing Documents and Artifacts

This clarification should be read with:

- `docs/superpowers/specs/2026-08-30-short-term-structure-design.md`, which
  defines short-term point mapping, containment, evidence preservation, and
  the general ambiguity policy;
- `docs/superpowers/plans/2026-08-31-short-term-structure.md`, which already
  specifies the fixed-left implementation representation;
- the frozen Real MNQ Case 1 source, validation counts, and hierarchy digest;
- the frozen Real MNQ Case 2 source and hierarchy oracle v1; and
- the frozen Real MNQ Case 2 blind project output.

This document clarifies only the pairing boundary. It does not revise isolated
recognition, same-kind normalization, inclusive containment, medium-term or
long-term recognition, market-state analysis, BMS, SMS, or any strategy,
risk, execution, or Chapter 3 behavior.

## Decision Summary

The project currently applies this deterministic rule:

```text
same-kind-normalized candidates
        -> anchor at the first vertex
        -> form non-overlapping pairs from the left
        -> compare each complete later pair with the preceding pair
        -> suppress only definite inclusive containment
        -> restart/reapply after changed adjacency until stable
        -> preserve unmatched or shifted candidates not selected by this rule
```

Fixed-left alignment is an approved, conservative, and revisable engineering
choice. It is not attributed to the teacher.

## Design Invariants

1. Course-derived containment remains inclusive on both boundaries.
2. Both `HIGH -> LOW` and `LOW -> HIGH` pair orientations remain valid.
3. Pair alignment itself is not attributed to available teacher/course
   evidence.
4. The normalized candidate sequence is anchored at its first vertex.
5. Comparable pairs are consecutive and non-overlapping from that anchor.
6. Shifted alternative alignment is not additionally evaluated.
7. Definite suppression is reapplied from the left until stable.
8. An unmatched trailing vertex is preserved.
9. All valid short-term points remain preserved separately from vertices.
10. Current production and Case 1 behavior remain unchanged.
11. The original Case 2 oracle and blind output remain immutable historical
    artifacts.
12. Corrected Case 2 expectations must be versioned and auditable.
13. Fixed-left pairing may be revised only through new evidence and explicit
    approval.
14. This clarification adds no production, test, oracle, implementation-plan,
    strategy, execution, or Chapter 3 behavior.
