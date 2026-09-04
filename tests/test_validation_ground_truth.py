"""Contract tests for source-bound market-structure ground truth."""

import importlib.util
import hashlib
import json
from dataclasses import FrozenInstanceError
from importlib import import_module
from pathlib import Path

import pytest

from trading.analysis.models import EvaluationReason, EvaluationStatus, StructuralLevel
from trading.definitions.extremes import ExtremeOrder
from trading.definitions.isolated_point_deformations import IsolatedPointBasis
from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.market_structure import MarketState
from trading.definitions.movements import MovementSide
from trading.validation.ground_truth import (
    ExpectedExtremePath,
    ExpectedPoint,
    ExpectedStructure,
    GroundTruthCase,
    load_ground_truth,
    sha256_file,
    verify_ground_truth_source,
)


def test_validation_package_is_discoverable() -> None:
    assert importlib.util.find_spec("trading.validation") is not None


def test_ground_truth_module_is_discoverable() -> None:
    assert importlib.util.find_spec("trading.validation.ground_truth") is not None


def test_ground_truth_module_exposes_locked_public_names() -> None:
    module = import_module("trading.validation.ground_truth")
    missing = [
        name
        for name in (
            "GroundTruthSource",
            "ExpectedPoint",
            "ExpectedPotential",
            "ExpectedSuppression",
            "ExpectedStructure",
            "ExpectedGeometry",
            "ExpectedControl",
            "ExpectedPriceLeg",
            "ExpectedMovementSummary",
            "ExpectedExtremePath",
            "ExpectedExtremeEvidence",
            "ExpectedFeatures",
            "ExpectedChapter1Candle",
            "ExpectedMarketState",
            "ExpectedBMS",
            "ExpectedSMS",
            "ExpectedSegment",
            "GroundTruthAmbiguity",
            "GroundTruthCase",
            "sha256_file",
            "load_ground_truth",
            "verify_ground_truth_source",
        )
        if not hasattr(module, name)
    ]
    assert missing == []


def point(
    index: int,
    kind: str,
    price: float,
    *,
    basis: str | None = None,
    confirmed_by_index: int | None = None,
) -> dict[str, object]:
    return {
        "index": index,
        "kind": kind,
        "price": price,
        "recognition_basis": basis,
        "confirmed_by_index": confirmed_by_index,
    }


def structure(*, provenance: bool) -> dict[str, object]:
    item = point(
        3,
        "high",
        110.0,
        basis=None,
        confirmed_by_index=5 if provenance else None,
    )
    return {
        "points": [item],
        "potentials": [
            {"previous_index": 1, "pivot_index": 3, "kind": "high", "price": 110.0}
        ],
        "vertices": [item],
        "suppressed": [
            {
                "point": point(
                    2,
                    "high",
                    108.0,
                    confirmed_by_index=4 if provenance else None,
                ),
                "reason": "consecutive_same_kind",
            }
        ],
    }


def chapter1_candle() -> dict[str, object]:
    return {
        "index": 0,
        "side": "bullish",
        "geometry": {
            "body_ratio": 0.1,
            "upper_wick_ratio": 0.8,
            "lower_wick_ratio": 0.1,
            "open_position": 0.1,
            "close_position": 0.2,
        },
        "control": {
            "buyer_control": 2.0,
            "seller_control": 8.0,
            "buyer_control_ratio": 0.2,
            "seller_control_ratio": 0.8,
            "control_score": -0.6,
        },
        "intrabar_status": "available",
        "intrabar_reason": None,
        "legs": [
            {"side": "seller", "start_price": 100.0, "end_price": 99.0, "distance": 1.0}
        ],
        "movements": {
            "first_side": "seller",
            "first_distance": 1.0,
            "final_side": "buyer",
            "final_distance": 2.0,
            "largest_buyer_move": 2.0,
            "largest_seller_move": 1.0,
            "total_buyer_movement": 2.0,
            "total_seller_movement": 1.0,
            "final_retracement_ratio": 0.5,
        },
        "extreme_path": {"order": "low_then_high", "legs": [
            {"side": "seller", "start_price": 100.0, "end_price": 99.0, "distance": 1.0}
        ]},
        "extreme_evidence": {
            "order": "low_then_high",
            "initial_side": "seller",
            "initial_distance": 1.0,
            "initial_ratio": 0.1,
            "main_side": "buyer",
            "main_distance": 11.0,
            "main_ratio": 1.1,
            "final_side": "seller",
            "final_distance": 9.0,
            "final_ratio": 0.9,
            "signed_displacement": 1.0,
            "displacement_ratio": 0.1,
        },
        "features": {
            "side": "bullish",
            "body_ratio": 0.1,
            "upper_wick_ratio": 0.8,
            "lower_wick_ratio": 0.1,
            "open_position": 0.1,
            "close_position": 0.2,
            "control_score": -0.6,
            "extreme_order": "low_then_high",
            "initial_side": "seller",
            "initial_ratio": 0.1,
            "final_side": "seller",
            "final_ratio": 0.9,
            "displacement_ratio": 0.1,
            "total_buyer_movement_ratio": 0.2,
            "total_seller_movement_ratio": 0.1,
        },
        "candle_type_status": "unavailable",
        "candle_type_reason": "candle_type_uncalibrated",
    }


def document(source_hash: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_id": "fixture-case",
        "source": {
            "market_data_file": "fixture.csv",
            "sha256": source_hash,
            "instrument": "MNQ",
            "timeframe": "1m",
            "start_index": 0,
            "candle_count": 6,
        },
        "expected": {
            "chapter1": [chapter1_candle()],
            "isolated": [
                point(1, "high", 105.0, basis="strict"),
                point(2, "low", 95.0, basis="right_inside_bar"),
            ],
            "short_term": structure(provenance=False),
            "medium_term": structure(provenance=True),
            "long_term": structure(provenance=True),
            "segment": {
                "start_index": 0,
                "end_index": 5,
                "level": "short",
                "market_state": {"status": "available", "reason": None, "value": "uptrend"},
                "bms_request": {
                    "trend_origin_index": 1,
                    "previous_extreme_index": 3,
                    "pullback_extreme_index": 5,
                },
                "bms": {
                    "status": "available",
                    "reason": None,
                    "value": "bms_confirmed",
                    "broken_point_index": 3,
                    "breakout_index": 6,
                },
                "sms_request": {"trend_extreme_index": 3, "creator_point_index": 2},
                "sms": {
                    "status": "available",
                    "reason": None,
                    "value": "sms_confirmed",
                    "broken_point_index": 2,
                    "event_index": 6,
                },
            },
        },
        "ambiguities": [{"layer": "isolated", "item": "index:4", "note": "reviewed before scoring"}],
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_loads_complete_v1_ground_truth_as_typed_immutable_records(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"timestamp,open,high,low,close\n")
    path = tmp_path / "ground-truth.json"
    write_json(path, document(file_hash(market_data)))

    result = load_ground_truth(path)

    assert isinstance(result, GroundTruthCase)
    assert result.case_id == "fixture-case"
    assert result.source.market_data_file == "fixture.csv"
    assert result.source.instrument == "MNQ"
    assert result.source.timeframe == "1m"
    assert result.source.start_index == 0
    assert result.source.candle_count == 6
    assert result.isolated[0].kind is IsolatedPointKind.HIGH
    assert result.isolated[0].recognition_basis is IsolatedPointBasis.STRICT
    assert result.isolated[1].recognition_basis is IsolatedPointBasis.RIGHT_INSIDE_BAR
    assert result.chapter1[0].intrabar_status is EvaluationStatus.AVAILABLE
    assert result.chapter1[0].legs is not None
    assert result.chapter1[0].legs[0].side is MovementSide.SELLER
    assert result.segment is not None
    assert result.segment.level is StructuralLevel.SHORT
    assert result.segment.market_state.value is MarketState.UPTREND
    assert result.short_term.points == tuple(result.short_term.points)
    assert result.ambiguities[0].note == "reviewed before scoring"
    with pytest.raises(FrozenInstanceError):
        result.case_id = "changed"  # type: ignore[misc]


def test_freezes_source_tolerance_with_a_source_format_justification(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    path = tmp_path / "ground-truth.json"
    payload = document(file_hash(market_data))
    payload["source"].update(  # type: ignore[index]
        price_tolerance=0.25,
        price_tolerance_justification="source CSV prices are rounded to the 0.25 tick",
    )
    write_json(path, payload)

    case = load_ground_truth(path)

    assert case.source.price_tolerance == 0.25
    assert case.source.price_tolerance_justification == "source CSV prices are rounded to the 0.25 tick"

    payload["source"].pop("price_tolerance_justification")  # type: ignore[index]
    write_json(path, payload)
    with pytest.raises(ValueError, match="price_tolerance_justification"):
        load_ground_truth(path)

    payload = document(file_hash(market_data))
    payload["source"]["price_tolerance_justification"] = "not needed"  # type: ignore[index]
    write_json(path, payload)
    with pytest.raises(ValueError, match="price_tolerance_justification"):
        load_ground_truth(path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.__setitem__("schema_version", 2), "schema_version"),
        (lambda payload: payload.pop("case_id"), "case_id"),
        (lambda payload: payload.__setitem__("unexpected", None), "unknown"),
        (lambda payload: payload["expected"].__setitem__("unknown", None), "unknown"),  # type: ignore[index]
        (lambda payload: payload["expected"]["isolated"][0].__setitem__("kind", "peak"), "kind"),  # type: ignore[index]
        (lambda payload: payload["expected"]["isolated"][0].__setitem__("recognition_basis", "inside"), "recognition_basis"),  # type: ignore[index]
        (lambda payload: payload["expected"]["short_term"]["suppressed"][0].__setitem__("reason", "unknown"), "ShortTermSuppressionReason"),  # type: ignore[index]
        (lambda payload: payload["expected"]["segment"].__setitem__("level", "daily"), "StructuralLevel"),  # type: ignore[index]
        (lambda payload: payload["expected"]["segment"]["market_state"].__setitem__("status", "pending"), "EvaluationStatus"),  # type: ignore[index]
        (lambda payload: payload["expected"]["segment"]["market_state"].__setitem__("reason", "not_a_reason"), "EvaluationReason"),  # type: ignore[index]
        (lambda payload: payload["expected"]["isolated"][0].__setitem__("price", float("nan")), "finite"),  # type: ignore[index]
        (lambda payload: payload["ambiguities"][0].pop("note"), "note"),  # type: ignore[index]
    ],
)
def test_rejects_invalid_or_unknown_ground_truth_schema(
    tmp_path: Path,
    mutate: object,
    message: str,
) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    payload = document(file_hash(market_data))
    mutate(payload)  # type: ignore[operator]
    path = tmp_path / "ground-truth.json"
    write_json(path, payload)

    with pytest.raises(ValueError, match=message):
        load_ground_truth(path)


def test_rejects_boolean_indexes_and_malformed_optional_provenance(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    payload = document(file_hash(market_data))
    payload["source"]["start_index"] = True  # type: ignore[index]
    path = tmp_path / "ground-truth.json"
    write_json(path, payload)

    with pytest.raises(ValueError, match="start_index"):
        load_ground_truth(path)

    payload = document(file_hash(market_data))
    payload["expected"]["medium_term"]["points"][0]["confirmed_by_index"] = None  # type: ignore[index]
    write_json(path, payload)
    with pytest.raises(ValueError, match="confirmed_by_index"):
        load_ground_truth(path)


def test_rejects_noncanonical_chapter1_intrabar_availability(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    payload = document(file_hash(market_data))
    candle = payload["expected"]["chapter1"][0]  # type: ignore[index]
    candle["intrabar_status"] = "invalid"
    candle["intrabar_reason"] = "invalid_context"
    candle["legs"] = None
    candle["movements"] = None
    candle["extreme_path"] = None
    candle["extreme_evidence"] = None
    candle["features"] = None
    path = tmp_path / "ground-truth.json"
    write_json(path, payload)

    with pytest.raises(ValueError, match="intrabar"):
        load_ground_truth(path)


def test_verifies_exact_source_bytes_and_reports_sha256_mismatch(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"original bytes\n")
    assert sha256_file(market_data) == file_hash(market_data)
    path = tmp_path / "ground-truth.json"
    write_json(path, document(file_hash(market_data)))
    case = load_ground_truth(path)

    assert verify_ground_truth_source(case, market_data) is None

    market_data.write_bytes(b"changed bytes\n")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_ground_truth_source(case, market_data)


def test_rejects_source_filename_mismatch_without_loading_analyzer(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    path = tmp_path / "ground-truth.json"
    write_json(path, document(file_hash(market_data)))
    case = load_ground_truth(path)

    other = tmp_path / "other.csv"
    other.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="filename"):
        verify_ground_truth_source(case, other)


def test_rejects_nonterminal_bms_and_sms_event_details(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    path = tmp_path / "ground-truth.json"

    payload = document(file_hash(market_data))
    payload["expected"]["segment"]["bms"]["value"] = "pullback_only"  # type: ignore[index]
    write_json(path, payload)
    with pytest.raises(ValueError, match="BMS"):
        load_ground_truth(path)

    payload = document(file_hash(market_data))
    payload["expected"]["segment"]["sms"]["value"] = "pending"  # type: ignore[index]
    write_json(path, payload)
    with pytest.raises(ValueError, match="SMS"):
        load_ground_truth(path)


def test_rejects_capability_impossible_segment_status_reason_pairs(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    path = tmp_path / "ground-truth.json"

    payload = document(file_hash(market_data))
    payload["expected"]["segment"]["market_state"] = {  # type: ignore[index]
        "status": "unavailable",
        "reason": "parent_state_not_directional",
        "value": None,
    }
    write_json(path, payload)
    with pytest.raises(ValueError, match="market_state"):
        load_ground_truth(path)

    payload = document(file_hash(market_data))
    payload["expected"]["segment"]["bms"].update(  # type: ignore[index]
        status="unavailable",
        reason="insufficient_structure",
        value=None,
        broken_point_index=None,
        breakout_index=None,
    )
    write_json(path, payload)
    with pytest.raises(ValueError, match="BMS"):
        load_ground_truth(path)

    payload = document(file_hash(market_data))
    payload["expected"]["segment"]["sms"].update(  # type: ignore[index]
        status="invalid",
        reason="insufficient_structure",
        value=None,
        broken_point_index=None,
        event_index=None,
    )
    write_json(path, payload)
    with pytest.raises(ValueError, match="SMS"):
        load_ground_truth(path)


def test_public_sequence_records_snapshot_mutable_inputs(tmp_path: Path) -> None:
    point_value = ExpectedPoint(1, IsolatedPointKind.HIGH, 110.0)
    points = [point_value]
    structure_value = ExpectedStructure(points, [], points, [])  # type: ignore[arg-type]
    legs = []
    path_value = ExpectedExtremePath(ExtremeOrder.LOW_THEN_HIGH, legs)  # type: ignore[arg-type]

    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    case = load_ground_truth(write_case(tmp_path, document(file_hash(market_data))))
    chapter1 = list(case.chapter1)
    isolated = list(case.isolated)
    ambiguities = list(case.ambiguities)
    copied_case = GroundTruthCase(
        case.schema_version,
        case.case_id,
        case.source,
        chapter1,  # type: ignore[arg-type]
        isolated,  # type: ignore[arg-type]
        case.short_term,
        case.medium_term,
        case.long_term,
        case.segment,
        ambiguities,  # type: ignore[arg-type]
    )
    points.clear()
    legs.append(object())
    chapter1.clear()
    isolated.clear()
    ambiguities.clear()

    assert structure_value.points == (point_value,)
    assert path_value.legs == ()
    assert copied_case.chapter1 == case.chapter1
    assert copied_case.isolated == case.isolated
    assert copied_case.ambiguities == case.ambiguities


def test_rejects_invalid_isolated_and_higher_level_provenance(tmp_path: Path) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    path = tmp_path / "ground-truth.json"

    payload = document(file_hash(market_data))
    payload["expected"]["isolated"][0]["recognition_basis"] = None  # type: ignore[index]
    write_json(path, payload)
    with pytest.raises(ValueError, match="recognition_basis"):
        load_ground_truth(path)

    payload = document(file_hash(market_data))
    payload["expected"]["medium_term"]["points"][0]["recognition_basis"] = "strict"  # type: ignore[index]
    write_json(path, payload)
    with pytest.raises(ValueError, match="recognition_basis"):
        load_ground_truth(path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["expected"]["chapter1"].append(chapter1_candle()),  # type: ignore[index]
            "chapter1.*duplicate",
        ),
        (
            lambda payload: payload["expected"]["short_term"]["potentials"].append(  # type: ignore[index]
                payload["expected"]["short_term"]["potentials"][0]
            ),
            "potentials.*duplicate",
        ),
        (
            lambda payload: payload["expected"]["short_term"]["suppressed"].append(  # type: ignore[index]
                payload["expected"]["short_term"]["suppressed"][0]
            ),
            "suppressed.*duplicate",
        ),
    ],
)
def test_rejects_duplicate_expected_identities(
    tmp_path: Path,
    mutate: object,
    message: str,
) -> None:
    market_data = tmp_path / "fixture.csv"
    market_data.write_bytes(b"fixture")
    payload = document(file_hash(market_data))
    mutate(payload)  # type: ignore[operator]

    with pytest.raises(ValueError, match=message):
        load_ground_truth(write_case(tmp_path, payload))


def test_rejects_duplicate_raw_json_member_names(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate key"):
        load_ground_truth(path)


def write_case(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "ground-truth.json"
    write_json(path, payload)
    return path
