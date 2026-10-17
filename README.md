# Trading System V1 — Chapter 3 Lesson 1 development

This development branch starts at preserved Chapter 2 commit
`164f438ec9339fff483dd9f0f9ceb486982cc963`. Chapter 3 Lesson 1 adds explicit
trading-range annotations and conditional formation-evidence checks. See the
[lesson specification and source limitations](docs/lessons/chapter3-lesson1.md).
It does not automatically detect ranges or infer unsuccessful breakouts.

This branch preserves the approved Chapter 1/2 implementation and Chapter 2 scientific-validation methodology. Chapter 2 recognizes frozen market-structure definitions; it does not claim a profitable or predictive trading system.

The scientific result is **COHORT_PASS**: **812/812 comparison groups**, **10/10 windows** and **107/107 explicit contexts** matched, with zero mismatches and independent review C0/I0/M0. The reviewed aggregate report is [here](validation/mnq_5m_successor_v2/scientific_results/comparison_v1/REPORT.md). Identities, source/window hashes and result commitments are in [checkpoint metadata](docs/checkpoints/chapter2-scientific-checkpoint.json). These records preserve the original result without redistributing market data.

## Publication boundary

This is a new independent root snapshot of reviewed publication-safe files from local checkpoint `4d57af458d83b6db7bc8c5fe5f6d543fe6899701`. Its Git history deliberately does not include local dataset commits. Raw NinjaTrader exports, historical bars, data-bearing oracle/production/control payloads, actual numeric contexts, native logs, private paths and backups are omitted. Existing older remote branches are not rewritten. No new redistribution license or market-data rights are asserted.

Project source, synthetic tests, specifications, reusable validation tools and successor protocols/profile/calendar are retained. Original engineering plans and private operational evidence remain local. Code and published scientific documents are copied byte-for-byte; the selected final report is unchanged. The publication file inventory records exact hashes and original paths. New README/ignore/public metadata files describe this publication boundary; they do not change any scientific definition or result.

## Development and reproduction

Use Python 3.12 and install `requirements-validation.txt` plus `validation/mnq_5m_successor_v2/requirements-test.txt` for validation tests. Core unit/integration tests use synthetic fixtures. Historical acquisition/checkpoint/reproduction commands may require deliberately withheld private artifacts; their presence on this branch is not a claim that full-cohort reproduction works without those artifacts. Keep any authorized restored data private and verify it against the original hashes.

The source profile records upstream origin as **UNVERIFIED**. Live streaming, incremental availability/finality/retractions, automatic segment/creator selection, profitability and strategy behavior remain unproven or outside the preserved checkpoint. Chapter 3 additions on this branch are separate from the unchanged scientific artifacts.

See [project overview](docs/PROJECT_OVERVIEW.md) and `docs/superpowers/specs/` for approved definitions. No merge to main or pull request accompanies this checkpoint.
