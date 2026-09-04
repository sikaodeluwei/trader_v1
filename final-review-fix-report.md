# Final Review Fix Round 1

Date: 2026-09-05
Branch: `feature/offline-market-analysis`
Base before fix: `a63d324766b5abe90d5f3fb5db0a8b7fe0ec29b7`

## Findings addressed

- Ground-truth source metadata now freezes an optional non-negative
  `price_tolerance` and optional `price_tolerance_justification`. Existing
  zero-tolerance JSON remains backward-compatible; nonzero tolerance requires
  a non-empty justification, and zero tolerance forbids one. Scoring rejects
  an explicit tolerance that does not exactly match the recorded source value.
- The timestamped OHLC CSV adapter rejects duplicate headers before a later
  value can overwrite an earlier one, and rejects surplus row cells with the
  source row number.
- Ground-truth segment validation enforces the exact capability-specific
  status/reason mappings used by market-state, BMS, and SMS evaluation.

## RED

The recovered RED stage ran:

```text
python -m pytest tests/test_ohlc_csv_loader.py tests/test_validation_ground_truth.py tests/test_validation_scoring.py -q
```

Result: 5 expected failures and 73 passes. The failures demonstrated duplicate
header acceptance, surplus-cell acceptance, missing source tolerance metadata,
unrecorded scorer tolerance acceptance, and capability-impossible segment
status/reason acceptance.

## GREEN

After the minimum production changes:

```text
python -m pytest tests/test_ohlc_csv_loader.py tests/test_validation_ground_truth.py tests/test_validation_scoring.py -q
```

Result: 78 passed.

```text
python -m pytest -q
```

Result: 673 passed.

`git diff --check` also passed. No ledger, push, or merge was performed.
