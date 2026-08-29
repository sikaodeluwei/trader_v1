# Cycle and Level Framework Design

**Date:** 2026-08-30

**Status:** Approved architectural checkpoint

**Scope:** Chapter 2, Lesson 4 — Period/Cycle and Structural Level

## Purpose

This specification preserves the Chapter 2, Lesson 4 course rules about period, cycle, and structural level as binding constraints for future market-structure work. It explains how those concepts relate to the explicit-context architecture established in Lessons 1–3 without inventing the operational hierarchy-identification method that the course only begins teaching in Lesson 5.

This is a documentation-only checkpoint. It introduces no production API, data model, classifier, test suite, strategy rule, or execution behavior.

The intended progression is:

```text
Lesson 4 conceptual framework
        |
        v
period divides market information
level describes structure relative to an analytical reference
        |
        v
Lesson 5+ operational methodology, if sufficiently defined by the course
        |
        v
future design and implementation of explicit cross-level relationships
```

## Scope

### Course-derived scope

This lesson establishes that:

- raw transaction information can be divided into periods for analysis;
- period selection depends on analytical needs rather than a universal mandatory ladder;
- structural level is relative to a chosen reference level;
- period and level are related but are not identical;
- different structural scales can coexist; and
- an event at one scale must not automatically be promoted to another scale.

### Engineering and repository scope

This checkpoint records constraints for future designs while preserving the repository's current explicit-input architecture. It does not change any Lesson 1–3 interfaces or behavior.

The only repository artifact created by Lesson 4 is this specification:

```text
docs/superpowers/specs/2026-08-30-cycle-and-level-framework-design.md
```

## Course Definitions

### Period / cycle — course-derived

A period is an analytical division of market information, normally using time as the measuring scale. Periods make market information usable for human analysis because raw tick-level transaction data is too granular to interpret directly at all times.

The course does not prescribe one universal set of periods. An analyst or institution may choose periods according to analytical needs. Seconds, 20-minute, 1-hour, 4-hour, daily, weekly, monthly, and other custom divisions are examples only.

Consequently:

- no example period is mandatory;
- no example sequence defines a universal timeframe ladder;
- custom periods remain legitimate; and
- period choice by itself does not identify structural importance.

This specification uses “period/cycle” to refer to the lesson's analytical division concept. It does not require future software to treat every possible use of those words as an interchangeable technical type.

### Level — course-derived

Level is a relative structural concept, not an absolute label. A level has meaning only with respect to a chosen analytical reference or base level.

The same timeframe or movement can be described as smaller, base, larger, or further removed when the reference changes. Therefore labels such as “short-term,” “medium-term,” “long-term,” “small,” or “large” cannot be assigned correctly without an explicit reference and an operational identification rule.

Level more often describes the scale of price movement and market structure, including:

- trends;
- rises and declines;
- pullbacks;
- structural breaks; and
- relationships between differently scaled movements.

These descriptions do not yet define how software discovers or relates those structures.

## Period Versus Level

### Course-derived distinction

Period and level are related because periodized market information may be used to observe price structure. They are not the same concept:

| Concept | Course emphasis | What it does not establish by itself |
| --- | --- | --- |
| Period / cycle | How market information is divided, commonly by time | Structural importance, parentage, or trend level |
| Level | The relative scale of price movement and market structure | A mandatory timeframe, fixed duration, or universal hierarchy |

A timeframe label therefore cannot be substituted automatically for a structural-level label. For example, “1-hour” describes a data division; it does not inherently mean “base level,” “medium-term,” “parent,” or “child.”

### Engineering constraint

Future code must keep period selection and structural-level identification as separate responsibilities. A time interval may be an input to a later analysis, but it must not silently determine a structural-level relationship unless a later course rule explicitly defines that mapping.

Lesson 4 authorizes neither a `TimeframeLevel` enum nor a period-to-level lookup table.

## Relative-Level Model

### Course-derived model

A relative-level discussion requires a chosen reference. Once a base level is selected for the analysis, other observed structures may be discussed as smaller, larger, or further removed relative to that base.

The course may illustrate scale with sequences such as:

```text
20m -> 1h -> 4h -> daily -> weekly
```

This sequence demonstrates relative scale only. It is not a universal hierarchy, a required set of periods, or an executable mapping.

Different structural scales can coexist. A movement at one level may later develop into a larger-level movement or into an opposite movement at a comparable level. These are conceptual possibilities, not deterministic transition rules. The lesson does not yet define the observations, pairing rules, or confirmation criteria required to make those conclusions automatically.

### Engineering constraints

Until a later lesson supplies operational rules:

- the caller remains responsible for the analytical reference;
- no repository component may infer parent, child, peer, or distant levels;
- no result at one explicit context may mutate or propagate into another context;
- no structural event may be promoted solely because it occurred on a named timeframe; and
- structures that appear to have different scales must remain separately and explicitly supplied.

The repository must not encode an absolute ranking whose meaning survives every change of analytical reference.

## Relationship to Lessons 1–3

### Lesson 1 — market state

`MarketSegment` remains explicitly selected by the caller, and `StructurePoint` remains explicitly supplied. `classify_market_state()` continues to classify only the provided points inside the provided segment.

Lesson 4 does not authorize Lesson 1 to:

- select a period or segment automatically;
- infer a structural level;
- extract structure points from candles;
- assign parent/child relationships; or
- reinterpret an isolated high or low as a level-specific structure point.

Market state therefore remains segment-relative rather than globally or hierarchically absolute.

### Lesson 2 — pullback and BMS

Lesson 2 BMS remains relative to an explicitly supplied directional parent state and `PullbackContext`. The trend origin, previous extreme, pullback extreme, parent segment, and observation chronology remain explicit.

Lesson 4 establishes that a future BMS discussion may need a structural-level reference, but it does not authorize:

- automatic selection of that level;
- propagation of BMS into another level;
- replacement of the caller's explicit context; or
- reinterpretation of one context's BMS as a larger-scale BMS.

### Lesson 3 — SMS

Lesson 3 SMS remains relative to an explicitly supplied parent trend, trend extreme, creator point, parent segment, and complete observation sequence.

Lesson 4 establishes that differently scaled SMS contexts may coexist, but it does not authorize:

- automatic creator-point or trend-extreme selection by level;
- automatic hierarchy inference;
- propagation of SMS into another level;
- construction of a replacement context; or
- treating a smaller-scale SMS as a confirmed larger-scale event.

`SMS_CONFIRMED` continues to mean reversal structure only. It does not confirm an opposite trend at the same level or at any larger level.

### Architectural continuity

The existing Chapter 2 composition remains valid:

```text
caller selects explicit segment and structural points
        |
        v
Lesson 1 classifies that segment
        |
        +--> Lesson 2 evaluates an explicit pullback/BMS context
        |
        +--> Lesson 3 evaluates an explicit SMS context
```

Lesson 4 adds no hidden hierarchy around this flow. Any future level-aware composition must extend it through explicit, separately designed inputs rather than retrofitting automatic inference into the existing APIs.

## Architectural Implications

The following are engineering and repository constraints derived from the course rules:

1. **No fixed ladder:** example periods must remain examples in documentation and fixtures; they must not become a canonical enum order or required sequence.
2. **Explicit reference:** any future statement that one structure is smaller, larger, parent, child, or peer must identify the reference that gives that statement meaning.
3. **Separate responsibilities:** periodization, structure identification, and cross-level relationship analysis must not be collapsed into one implicit operation.
4. **No automatic promotion:** a structural event proven inside one context carries no automatic meaning in another context.
5. **No historical retrofit:** the explicit segment, point, BMS, and SMS contracts from Lessons 1–3 remain unchanged until a later approved design demonstrates a course-derived need for extension.
6. **No premature domain types:** Lesson 4 introduces no production level enum, hierarchy node, timeframe registry, parent/child link, or automatic context builder.
7. **Original observations remain authoritative:** future level-aware analysis must not justify fabricating, reordering, or silently omitting market observations.

These constraints preserve room for later methodology without making the current architecture pretend to know more than the course has taught.

## Course Motivation Versus Executable Rules

### Course-derived motivation

The teacher uses period and level to explain why analysts may need to:

- filter market noise;
- define an analytical identity or intended holding horizon;
- compare market forces across different scales;
- understand that different scales can exert different structural influence; and
- reason about illustrative risk, stop, and position consequences.

These examples explain why the concepts matter. They are not algorithms or trading instructions.

### Engineering constraint

Lesson 4 motivation must not be translated into executable rules for:

- trader profiling;
- directional bias;
- trade selection;
- entries or exits;
- stop-loss placement;
- risk limits;
- position sizing;
- portfolio allocation; or
- order execution.

No numerical threshold, holding period, stop distance, risk percentage, or position formula may be inferred from the motivational examples.

## Explicitly Deferred Behavior

Lesson 4 does not authorize implementation or design-by-assumption of:

- automatic timeframe-to-level mapping;
- a fixed 20-minute/1-hour/4-hour/daily/weekly hierarchy;
- automatic short-term, medium-term, or long-term structure classification;
- automatic parent/child structure discovery;
- automatic structural hierarchy inference;
- automatic structure-point extraction by level;
- automatic creator-point selection by level;
- automatic trend-extreme selection by level;
- automatic BMS propagation across levels;
- automatic SMS propagation across levels;
- automatic replacement contexts across levels;
- multi-timeframe directional bias;
- trading-range logic;
- strategy or signal logic;
- entries or exits;
- stop-loss logic;
- risk management;
- position sizing; or
- broker, order, or execution logic.

The existing isolated-point definitions also remain separate. A confirmed isolated high or low must not automatically become a structure point at any level.

## Implementation Gate

No production hierarchy or level-identification logic may be added until a later course lesson supplies sufficiently operational rules for identifying, pairing, and relating structures across levels.

At minimum, a future approved design must be able to state from course evidence:

- how candidate structures are identified;
- how large and small structures are distinguished relative to a stated base;
- how structural points are paired into one continuous structure;
- how structures at different levels are related without skipping contradictory observations;
- when a structure changes level or contributes to a larger structure; and
- which inputs remain explicit when automatic identification is not justified.

If the course does not answer one of these questions operationally, the corresponding behavior must remain caller-supplied or deferred. Plausible swing, zig-zag, timeframe, or nearest-point heuristics are not substitutes for course rules.

This gate applies to production code, tests that imply unsupported behavior, and documentation that presents an example as a rule.

## Testing and Validation Policy

### Lesson 4 checkpoint

This documentation-only checkpoint adds no production tests because it adds no executable behavior. Validation consists of reviewing the specification for course fidelity, internal consistency, scope, and compatibility with Lessons 1–3.

No implementation plan is created at this checkpoint.

### Future level-aware work

If a later lesson passes the implementation gate, its design and implementation plan must define tests from the operational rules actually taught. Those tests must distinguish, at minimum:

- data period from structural level;
- relative level from absolute timeframe labels;
- explicit context behavior from automatic inference;
- events confined to one level from course-justified cross-level relationships; and
- valid continuous structure from cherry-picked or contradictory observations.

Tests must not encode the course's illustrative timeframe sequence as a universal ladder.

### Formal Chapter 2 validation

Formal Chapter 2 Level 2 course-scenario validation remains deferred until all Chapter 2 lessons are complete. Lesson 4 must not create:

```text
tests/test_course_market_structure_scenarios.py
```

At the Chapter 2 completion checkpoint, the repository may design comprehensive human-labelled scenarios across the complete taught model. Raw-chart automation remains conditional on the course eventually providing legitimate operational extraction and hierarchy rules.

## Future-Course Handoff

The teacher states that the next lesson begins the methodology for:

- identifying large and small structures; and
- drawing or identifying short-term structure.

Lesson 5 and later material are therefore the next permitted source for hierarchy methodology. Their content must be evaluated for operational completeness before any production design is approved.

Passing from this framework to implementation requires a separate sequence:

```text
later course rule
        |
        v
course-faithful architectural design
        |
        v
user approval
        |
        v
implementation plan and red-to-green development
```

This specification does not pre-approve any Lesson 5 API, algorithm, data structure, or extraction rule.

## Non-Goals

This specification is not:

- an implementation plan;
- a proposal for production code;
- a timeframe configuration system;
- a multi-timeframe analysis engine;
- a structural hierarchy model;
- a structure-extraction algorithm;
- a definition of short-, medium-, or long-term structure;
- a BMS or SMS propagation mechanism;
- a trading-range model;
- a risk-management design;
- a strategy or signal specification; or
- an execution architecture.

It preserves the conceptual boundary needed for later course work: period divides information, level describes structure relative to a reference, and neither concept authorizes automatic hierarchy inference before the course teaches an operational method.

## Design Invariants

Future Chapter 2 work must preserve these invariants unless a later approved course-derived specification explicitly replaces one:

1. Period choice is analyst-dependent and not limited to a universal mandatory set.
2. Example timeframe sequences illustrate relative scale only.
3. Period and structural level remain related but distinct concepts.
4. Level has meaning only relative to a chosen analytical reference.
5. A timeframe does not automatically determine structural level.
6. Different structural scales may coexist without automatic propagation between them.
7. A smaller-scale event does not automatically become a larger-scale event.
8. Lessons 1–3 remain explicit-context systems.
9. Isolated points do not automatically become level-specific structure points.
10. Risk, stop, position, and trader-identity examples remain motivation rather than executable rules.
11. No hierarchy logic is implemented before a later lesson provides operational identification, pairing, and relationship rules.
12. Formal Chapter 2 Level 2 validation remains deferred until all Chapter 2 lessons are complete.
