# trader_v1

`trader_v1` is a lesson-by-lesson implementation of trading-course definitions and market-analysis foundations. The project translates each approved course concept into explicit, tested Python domain models before any strategy or execution layer is introduced.

This is not yet a complete trading strategy, signal generator, or broker-connected system.

## Architecture

```text
market / price data
        |
        v
candle definitions and interpretation
        |
        v
isolated points and key levels
        |
        v
market structure
        |
        v
future course-defined strategy/execution layers (not implemented)
```

## Implemented course content

### Chapter 1 foundation

#### Candles and ordered price movement

- OHLC candle models, candle side, normalized geometry, and close-location control measurements.
- Ordered intrabar price legs, movement summaries, canonical extreme paths, and normalized extreme-path evidence.
- Integrated `CandleAnalysis` and a flat `CandleFeatures` representation.
- Interpretation of an already-known `CandleType` into its course-defined `Advantage` (`BUYER`, `SELLER`, or `NONE`) and `TrendStatus` (`TREND` or `NON_TREND`).
- The mapping deliberately distinguishes candle color/side from advantage; for example, a bullish candle can have seller advantage.
- Automatic classification of a raw candle into one of the 16 `CandleType` values is deliberately unresolved. `classify_candle()` remains unimplemented until the course rules are sufficiently defined.

#### Isolated points and key levels

- Potential and confirmed isolated highs and lows, including stateful tracking that retains the middle candle's full OHLC for confirmation.
- Strict three-candle recognition plus a separate deformation-aware tracker for right-side inside-bar confirmation.
- Replacement by a more-extreme isolated point of the same kind.
- Confirmed isolated highs create resistance; confirmed isolated lows create support.
- Potential points do not create key levels, and more-extreme confirmed points can replace an existing same-kind level.

#### Data and calibration foundation

- Original ordered price paths flow through `CandleAnalysis` into regenerated `CandleFeatures`.
- Explicit human/course labels can be stored as calibration records and persisted as JSONL without inferring labels or saving derived features.
- Generic timezone-aware `PriceEvent` and `IntrabarPricePath` models, fixed-time grouping, and historical tick CSV loading.
- Bulk historical analysis skips single-price windows without fabricating prices; strict single-path analysis retains its validation.

### Chapter 2, Lesson 1: market structure foundation

- Every market-state decision requires an explicit `MarketSegment` and caller-supplied chronological `StructurePoint` values.
- Structural points distinguish `HIGH` and `LOW` and support six same-kind relationships: higher high, lower high, equal high, higher low, lower low, and equal low.
- Market state is one of `UPTREND`, `DOWNTREND`, or `SIDEWAYS`.
- The minimum uptrend is two highs where the later high is higher and two lows where the later low is higher.
- The minimum downtrend is two highs where the later high is lower and two lows where the later low is lower.
- In longer segments, every adjacent same-kind relationship must continue the claimed direction. Chronology is preserved: points are not sorted, contradictory intermediate points are not skipped, and equality breaks directional continuity.
- Points outside the explicit segment are rejected.
- Strict two-candle outside-bar recognition is implemented. Existing inside-bar logic is reused rather than duplicated.

## Current boundaries

The following are intentionally not implemented because their course definitions belong to later lessons or still require calibration:

- automatic extraction of structure points from candles;
- automatic mapping from isolated points to structure points;
- automatic segment, timeframe, or structure-level selection;
- Break in Market Structure (BMS), Break of Structure (BOS), or Change of Character (CHOCH);
- automatic classification of raw candles into the 16 candle types;
- automatic `BUYER` / `SELLER` / `NONE` advantage classification, thresholds, or model training;
- strategy rules, signals, entries, exits, position management, or execution;
- live market feeds and broker-specific integration.

These boundaries are deliberate: the repository records only approved course behavior and avoids guessing rules that have not yet been defined.

## Repository structure

| Path | Purpose |
| --- | --- |
| `trading/definitions/candles.py` | Candle models, geometry, control, known-type interpretation, and the unresolved classifier boundary |
| `trading/definitions/movements.py` | Detailed ordered price legs and movement summaries |
| `trading/definitions/extremes.py` | Canonical extreme paths and normalized evidence |
| `trading/definitions/analysis.py` | Integrated analysis built from ordered intrabar prices |
| `trading/definitions/features.py` | Flat feature vectors and explicitly labelled samples |
| `trading/definitions/dataset.py` | Original-path calibration records and JSONL persistence |
| `trading/definitions/isolated_points.py` | Strict isolated-point detection and tracking |
| `trading/definitions/isolated_point_deformations.py` | Approved inside-bar deformation handling |
| `trading/definitions/key_levels.py` | Support and resistance derived from confirmed isolated points |
| `trading/definitions/market_structure.py` | Explicit segments, structure-point relationships, market states, and outside bars |
| `trading/data/` | Generic intrabar market-data models, time windows, analysis integration, and CSV loading |
| `tests/` | Unit and integration tests for the implemented definitions |
| `docs/superpowers/specs/` | Approved design specifications |
| `docs/superpowers/plans/` | Approved implementation plans |

## Development principles

- Follow the course lesson by lesson; do not infer future behavior.
- Keep raw observations, derived measurements, human labels, and interpretations distinct.
- Preserve chronological input order and reject invalid input instead of silently sorting or fabricating data.
- Reuse existing domain calculations instead of duplicating them across layers.
- Introduce behavior through red-to-green test-driven development and run the full regression suite before completion.
- Keep production changes narrowly scoped to the approved lesson.

## Progress checkpoint

| Course area | Status |
| --- | --- |
| Chapter 1 definition foundation | Implemented |
| Chapter 2, Lesson 1 market structure foundation | Implemented |
| Chapter 2, Lesson 2 BMS Pullback Structure | Next |
| Strategy and execution layers | Not implemented |

Chapter 2 is not complete. The next planned course unit is Lesson 2: BMS Pullback Structure.

## Testing

Run the complete test suite from the repository root:

```bash
pytest
```
