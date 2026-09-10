# trader_v1

`trader_v1` is a lesson-by-lesson implementation of trading-course definitions and market-analysis foundations. The project translates each approved course concept into explicit, tested Python domain models before any strategy or execution layer is introduced.

This is not yet a complete trading strategy, signal generator, or broker-connected system.

## Architecture

```text
closed candles
      |
      v
confirmed isolated points
      |
      v
canonical short-term structure
      |
      v
canonical medium-term structure
      |
      v
canonical long-term structure
      |
      v
optional explicit segment analysis and offline validation
```

The project follows a course-first, no-guessing philosophy: only objective rules taught by the course or explicitly approved engineering rules are automated. Ambiguous choices remain caller-supplied or are reported explicitly.

## Implemented course content

### Chapter 1 foundation

#### Candles and ordered price movement

- OHLC candle models, candle side, normalized geometry, and close-location control measurements.
- Ordered intrabar price legs, movement summaries, canonical extreme paths, and normalized extreme-path evidence.
- Integrated `CandleAnalysis` and a flat `CandleFeatures` representation.
- Interpretation of an already-known `CandleType` into its course-defined `Advantage` (`BUYER`, `SELLER`, or `NONE`) and `TrendStatus` (`TREND` or `NON_TREND`).
- Candle color/side remains distinct from advantage; for example, a bullish candle can have seller advantage.
- Automatic classification of a raw candle into one of the 16 `CandleType` values remains deliberately unresolved. `classify_candle()` is unimplemented until the fuzzy course rules can be calibrated responsibly.

#### Isolated points and key levels

- Potential and confirmed isolated highs and lows, including stateful tracking that retains the middle candle's full OHLC for confirmation.
- Strict isolated-point recognition and the approved right-inside-bar deformation path, with recognition basis preserved.
- Replacement by a more-extreme isolated point of the same kind.
- Confirmed isolated highs create resistance; confirmed isolated lows create support. Potential points do not create key levels.

#### Data and calibration foundation

- Original ordered price paths flow through `CandleAnalysis` into regenerated `CandleFeatures`.
- Explicit human/course labels can be stored as JSONL calibration records without inferred labels or persisted derived features.
- Generic timezone-aware price events and intrabar paths, deterministic fixed-time grouping, and historical tick CSV loading.
- Historical OHLC CSV loading for offline closed-candle analysis.

### Chapter 2 market structure

Chapter 2 Lessons 1–8 are implemented. The canonical hierarchy is:

```text
candles
  -> confirmed isolated points
  -> canonical short-term vertices
  -> canonical medium-term vertices
  -> canonical long-term vertices
```

- Short-term structure maps confirmed isolated points and applies the taught consecutive same-kind and inclusive inside-structure normalization rules while retaining suppressed points separately.
- Medium-term structure is derived only from canonical short-term vertices; suppressed short-term points are not recognition neighbors.
- Long-term structure is derived only from canonical medium-term vertices; suppressed medium-term points are not promoted.
- Structural level (`SHORT`, `MEDIUM`, or `LONG`) and market segment are selected explicitly. Timeframe and structural level are separate concepts.
- Market-state classification reports `UPTREND`, `DOWNTREND`, or `NON_TREND` from sufficient same-level evidence. Insufficient evidence is reported as unavailable rather than reinterpreted as non-trend.
- Pullback/BMS and SMS evaluation use explicit contexts and dense chronological candle observations. Boundary indexes must resolve uniquely to canonical vertices at the selected level.
- Strict wick crossings count; exact touches do not. When one OHLC candle crosses competing boundaries and cannot prove their intrabar order, the ambiguity is reported instead of guessed.
- Directional `MEDIUM` and `LONG` segment results may include a `trend_start_anchor`: the earliest relevant canonical short-term vertex inside the selected segment (`LOW` for an uptrend, `HIGH` for a downtrend).
- The trend-start anchor is descriptive context only. It does not become a selected structural point, enter or alter the canonical hierarchy, get promoted upward, or affect market state, BMS, SMS, suppression, or potential-point recognition.

## Offline market-structure analyzer

The offline analyzer accepts 1–250 closed candles, preserves their supplied chronological order, and carries generic instrument and timeframe metadata without assigning a structural level from the timeframe.

It builds the complete isolated → short → medium → long hierarchy. A caller may optionally request analysis for one explicit market segment at one explicit structural level, with optional explicit canonical-vertex boundary references for BMS and SMS. The analyzer does not automatically choose a timeframe, structural level, segment, trend origin, pullback extreme, or SMS creator point.

## Validation framework

- Versioned, frozen ground truth is bound to its exact source data by SHA-256.
- Blind/offline workflows keep expected results separate from analyzer execution.
- Deterministic structural comparison and scoring cover Chapter 1 evidence, isolated recognition, hierarchy layers, and optional selected-segment results.
- Reports distinguish analyzer/engine failure, ground-truth disagreement, and declared course ambiguity.

### Real historical checkpoint: MNQ Case 1

The first real-data hierarchy checkpoint uses:

- Instrument: `MNQ 09-26`
- Timeframe: `1 minute`
- Window: 250 closed candles, 2026-09-04 11:51 through 16:00
- Source SHA-256: `78eabcf5b2d753311a89a2412e2c277fa51af6f57fe29424ee3363fcb1188e03`
- Isolated recognitions / unresolved potential: `73 / 1`
- Short points / vertices / suppressed: `73 / 47 / 26`
- Medium points / potentials / vertices / suppressed: `9 / 1 / 8 / 1`
- Long points / potentials / vertices / suppressed: `1 / 2 / 1 / 0`
- Hierarchy digest: `860a5d148bae81264e2ca8c09f11ae6ee09bd5d105a850a038444e8e67427a60`

All Chapter 2 hierarchy layers matched the independently prepared course-rule oracle exactly for this case. This single checkpoint does not establish universal correctness. Its hierarchy-only run did not request selected-segment analysis, so market state, BMS, SMS, and `trend_start_anchor` were not exercised; its OHLC-only input also did not validate Chapter 1 ordered-intrabar behavior.

## Current boundaries

The following remain intentionally outside the implemented scope:

- automatic market-segment selection;
- automatic structural-level selection;
- automatic timeframe selection or timeframe-to-level mapping;
- automatic classification of raw candles into the 16 fuzzy candle types;
- automatic `BUYER` / `SELLER` / `NONE` advantage classification, thresholds, or model training;
- strategy rules or entry/exit signals;
- position sizing, risk management, or leverage decisions;
- broker/order execution and live broker integration.

These boundaries are deliberate: the repository records approved course behavior and does not advertise unresolved or future behavior as implemented.

## Repository structure

| Path | Purpose |
| --- | --- |
| `trading/definitions/candles.py` | Candle models, measurements, known-type interpretation, and the unresolved raw classifier boundary |
| `trading/definitions/isolated_points.py` | Strict isolated-point detection and stateful tracking |
| `trading/definitions/isolated_point_deformations.py` | Approved right-inside-bar deformation recognition |
| `trading/definitions/short_term_structure.py` | Confirmed isolated points and canonical short-term normalization |
| `trading/definitions/medium_term_structure.py` | Medium-term recognition from canonical short-term vertices |
| `trading/definitions/long_term_structure.py` | Long-term recognition from canonical medium-term vertices |
| `trading/definitions/market_structure.py` | Explicit segments, structure-point relationships, and market-state classification |
| `trading/definitions/pullback_structure.py` | Explicit pullback and BMS evaluation |
| `trading/definitions/sms_structure.py` | Explicit SMS evaluation |
| `trading/analysis/` | Offline candle, isolated-point, hierarchy, selected-segment, BMS/SMS, and trend-anchor composition |
| `trading/validation/` | Frozen ground-truth models, deterministic comparison, scoring, and diagnostics |
| `trading/data/` | Generic market-data models, intrabar grouping, tick CSV loading, and OHLC CSV loading |
| `tests/` | Unit, cross-layer integration, course-scenario, offline, and blind-validation tests |
| `docs/superpowers/specs/` | Approved design specifications |
| `docs/superpowers/plans/` | Approved implementation plans |

## Development principles

- Follow the course lesson by lesson; do not infer future behavior.
- Keep raw observations, derived measurements, human labels, and interpretations distinct.
- Preserve chronological input order and reject invalid input instead of silently sorting or fabricating data.
- Keep canonical structural levels separate and compose each higher level only from the preceding level's canonical vertices.
- Reuse existing domain calculations instead of duplicating them across layers.
- Introduce behavior through red-to-green test-driven development and run the full regression suite before completion.

## Progress checkpoint

| Project area | Status |
| --- | --- |
| Chapter 1 definition foundation | Implemented |
| Chapter 2 Lessons 1–8 | Implemented |
| Offline analyzer and validation foundation | Implemented |
| Real MNQ Case 1 hierarchy validation | Exact match with the independent oracle |
| Additional real-data validation | Next checkpoint |
| Chapter 3 | After the validation checkpoint |
| Strategy and execution | Not implemented |

Chapter 2 implementation is complete. Additional real-data validation continues before Chapter 3 begins.

## Testing

Run the complete test suite from the repository root:

```bash
pytest
```
