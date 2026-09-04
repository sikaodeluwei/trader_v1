"""Tooling-only Test F coverage for the later real-historical checkpoint.

The first actual checkpoint procedure is deliberately documented here without
claiming that this deterministic fixture is real-market validation:

* select multiple independent MNQ 1-minute windows, then MNQ 5-minute windows;
* use no more than 250 completed timezone-aware OHLC candles per window;
* freeze and SHA-256 hash each source before annotation and scoring;
* have a human review the exact same range in TradingView;
* pass the analyzer only market data, metadata, explicit segment/level, and
  explicit BMS/SMS indexes;
* load ground truth only after analysis;
* do not cherry-pick successful windows;
* use a separate ordered NinjaTrader tick/trade export through the existing
  Chapter 1 path when intrabar validation is required; and
* do not add broker or order integration.

The tests below use a small ``workflow-fixture`` solely to prove this order,
source binding, and report shape. They do not acquire MNQ data or make a
real-market accuracy claim.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

import trading.analysis.offline as offline_module
import trading.data.ohlc_csv_loader as loader_module
import trading.validation.ground_truth as ground_truth_module
import trading.validation.scoring as scoring_module
from trading.validation.scoring import DiscrepancyClass


MARKET_CSV = (
    "timestamp,open,high,low,close\n"
    "2026-09-03T09:30:00+00:00,100,102,99,101\n"
)


def write_market_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "market.csv"
    path.write_text(MARKET_CSV, encoding="utf-8", newline="")
    return path


def write_ground_truth_fixture(tmp_path: Path, market_path: Path) -> Path:
    """Write labels independently, after the frozen source hash exists."""

    source_hash = hashlib.sha256(market_path.read_bytes()).hexdigest()
    payload = {
        "schema_version": 1,
        "case_id": "workflow-fixture",
        "source": {
            "market_data_file": market_path.name,
            "sha256": source_hash,
            "instrument": "MNQ",
            "timeframe": "1m",
            "start_index": 0,
            "candle_count": 1,
        },
        "expected": {
            "chapter1": [],
            "isolated": [
                {
                    "index": 1,
                    "kind": "high",
                    "price": 102.0,
                    "recognition_basis": "strict",
                    "confirmed_by_index": None,
                }
            ],
            "short_term": {
                "points": [],
                "potentials": [],
                "vertices": [],
                "suppressed": [],
            },
            "medium_term": {
                "points": [],
                "potentials": [],
                "vertices": [],
                "suppressed": [],
            },
            "long_term": {
                "points": [],
                "potentials": [],
                "vertices": [],
                "suppressed": [],
            },
            "segment": None,
        },
        "ambiguities": [
            {
                "layer": "isolated",
                "item": "workflow-fixture-review",
                "note": "Tooling-only fixture; not a real-market accuracy claim.",
            }
        ],
    }
    path = tmp_path / "ground-truth.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def run_blind_workflow(
    market_path: Path,
    ground_truth_path: Path,
    *,
    before_verify: Callable[[], None] | None = None,
) -> object:
    """Run the real public blind sequence, with one verification hook."""

    window = loader_module.load_ohlc_market_window(
        market_path,
        instrument="MNQ",
        timeframe="1m",
        start_index=0,
    )
    analysis = offline_module.analyze_market_window(window, None)

    # Expected labels are loaded only after analyzer output exists.
    truth = ground_truth_module.load_ground_truth(ground_truth_path)
    if before_verify is not None:
        before_verify()
    ground_truth_module.verify_ground_truth_source(truth, market_path)
    return scoring_module.score_analysis(analysis, truth)


def test_blind_workflow_keeps_labels_out_of_analysis_and_scores_after_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market_path = write_market_fixture(tmp_path)
    ground_truth_path = write_ground_truth_fixture(tmp_path, market_path)
    events: list[str] = []
    truth_loaded = False
    analyzer_arguments: list[tuple[object, object | None]] = []

    real_loader = loader_module.load_ohlc_market_window
    real_analyzer = offline_module.analyze_market_window
    real_truth_loader = ground_truth_module.load_ground_truth
    real_source_verifier = ground_truth_module.verify_ground_truth_source
    real_scorer = scoring_module.score_analysis

    def load_market(*args: object, **kwargs: object) -> object:
        events.append("load_market")
        return real_loader(*args, **kwargs)

    def analyze(*args: object, **kwargs: object) -> object:
        nonlocal truth_loaded
        assert not truth_loaded
        window = args[0] if args else kwargs["window"]
        segment = args[1] if len(args) > 1 else kwargs.get("segment")
        analyzer_arguments.append((window, segment))
        events.append("analyze")
        return real_analyzer(*args, **kwargs)

    def load_truth(*args: object, **kwargs: object) -> object:
        nonlocal truth_loaded
        events.append("load_ground_truth")
        truth_loaded = True
        return real_truth_loader(*args, **kwargs)

    def verify_source(*args: object, **kwargs: object) -> None:
        events.append("verify_source")
        return real_source_verifier(*args, **kwargs)

    def score(*args: object, **kwargs: object) -> object:
        events.append("score")
        return real_scorer(*args, **kwargs)

    monkeypatch.setattr(loader_module, "load_ohlc_market_window", load_market)
    monkeypatch.setattr(offline_module, "analyze_market_window", analyze)
    monkeypatch.setattr(ground_truth_module, "load_ground_truth", load_truth)
    monkeypatch.setattr(ground_truth_module, "verify_ground_truth_source", verify_source)
    monkeypatch.setattr(scoring_module, "score_analysis", score)

    report = run_blind_workflow(market_path, ground_truth_path)

    assert events == [
        "load_market",
        "analyze",
        "load_ground_truth",
        "verify_source",
        "score",
    ]
    assert len(analyzer_arguments) == 1
    assert analyzer_arguments[0][0].instrument == "MNQ"
    assert analyzer_arguments[0][1] is None
    assert truth_loaded

    assert report.case_id == "workflow-fixture"
    assert report.source_sha256 == hashlib.sha256(market_path.read_bytes()).hexdigest()
    assert report.isolated_metrics.true_positives == 0
    assert report.isolated_metrics.false_positives == 0
    assert report.isolated_metrics.false_negatives == 1
    assert report.isolated_metrics.precision == 0.0
    assert report.isolated_metrics.recall == 0.0
    assert report.isolated_metrics.f1 == 0.0
    assert report.chapter1.exact_match
    assert report.short_term.exact_match
    assert report.medium_term.exact_match
    assert report.long_term.exact_match
    assert report.segment is None
    assert len(report.ambiguities) == 1
    assert report.ambiguities[0].layer == "isolated"
    assert report.ambiguities[0].item == "workflow-fixture-review"
    assert DiscrepancyClass.GROUND_TRUTH_DISAGREEMENT in report.outcomes


def test_blind_workflow_rejects_one_byte_source_change_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market_path = write_market_fixture(tmp_path)
    ground_truth_path = write_ground_truth_fixture(tmp_path, market_path)
    score_called = False

    def unexpected_score(*args: object, **kwargs: object) -> object:
        nonlocal score_called
        score_called = True
        pytest.fail("source mismatch must reject before scoring")

    monkeypatch.setattr(scoring_module, "score_analysis", unexpected_score)

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        run_blind_workflow(
            market_path,
            ground_truth_path,
            before_verify=lambda: market_path.write_bytes(
                market_path.read_bytes().replace(b",101\n", b",101.1\n")
            ),
        )
    assert not score_called


def test_workflow_fixture_is_explicitly_tooling_only() -> None:
    assert "workflow-fixture" in (__doc__ or "")
    assert "real-market accuracy claim" in (__doc__ or "")
    assert "broker or order integration" in (__doc__ or "")
