"""Versioned source-bound ground truth for offline market-structure validation."""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from pathlib import Path
from typing import TypeVar

from trading.analysis.models import (
    BMSAnalysisRequest,
    EvaluationReason,
    EvaluationStatus,
    SMSAnalysisRequest,
    StructuralLevel,
)
from trading.definitions.candles import CandleSide
from trading.definitions.extremes import ExtremeOrder
from trading.definitions.isolated_point_deformations import IsolatedPointBasis
from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.long_term_structure import LongTermSuppressionReason
from trading.definitions.market_structure import MarketState
from trading.definitions.medium_term_structure import MediumTermSuppressionReason
from trading.definitions.movements import MovementSide
from trading.definitions.pullback_structure import PullbackStructureStatus
from trading.definitions.short_term_structure import ShortTermSuppressionReason
from trading.definitions.sms_structure import SMSStructureStatus


@dataclass(frozen=True)
class GroundTruthSource:
    market_data_file: str
    sha256: str
    instrument: str
    timeframe: str
    start_index: int
    candle_count: int
    price_tolerance: float = 0.0
    price_tolerance_justification: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.price_tolerance, bool)
            or not isinstance(self.price_tolerance, (int, float))
            or not isfinite(self.price_tolerance)
            or self.price_tolerance < 0
        ):
            raise ValueError(
                "ground truth.source.price_tolerance must be a finite non-negative number"
            )
        tolerance = float(self.price_tolerance)
        object.__setattr__(self, "price_tolerance", tolerance)
        justification = self.price_tolerance_justification
        if tolerance == 0.0:
            if justification is not None:
                raise ValueError(
                    "ground truth.source.price_tolerance_justification is only valid for nonzero price_tolerance"
                )
        elif not isinstance(justification, str) or not justification.strip():
            raise ValueError(
                "ground truth.source.price_tolerance_justification is required for nonzero price_tolerance"
            )


@dataclass(frozen=True)
class ExpectedPoint:
    index: int
    kind: IsolatedPointKind
    price: float
    recognition_basis: IsolatedPointBasis | None = None
    confirmed_by_index: int | None = None


@dataclass(frozen=True)
class ExpectedPotential:
    previous_index: int
    pivot_index: int
    kind: IsolatedPointKind
    price: float


@dataclass(frozen=True)
class ExpectedSuppression:
    point: ExpectedPoint
    reason: (
        ShortTermSuppressionReason
        | MediumTermSuppressionReason
        | LongTermSuppressionReason
    )


@dataclass(frozen=True)
class ExpectedStructure:
    points: tuple[ExpectedPoint, ...]
    potentials: tuple[ExpectedPotential, ...]
    vertices: tuple[ExpectedPoint, ...]
    suppressed: tuple[ExpectedSuppression, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "potentials", tuple(self.potentials))
        object.__setattr__(self, "vertices", tuple(self.vertices))
        object.__setattr__(self, "suppressed", tuple(self.suppressed))


@dataclass(frozen=True)
class ExpectedGeometry:
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    open_position: float
    close_position: float


@dataclass(frozen=True)
class ExpectedControl:
    buyer_control: float
    seller_control: float
    buyer_control_ratio: float
    seller_control_ratio: float
    control_score: float


@dataclass(frozen=True)
class ExpectedPriceLeg:
    side: MovementSide
    start_price: float
    end_price: float
    distance: float


@dataclass(frozen=True)
class ExpectedMovementSummary:
    first_side: MovementSide | None
    first_distance: float
    final_side: MovementSide | None
    final_distance: float
    largest_buyer_move: float
    largest_seller_move: float
    total_buyer_movement: float
    total_seller_movement: float
    final_retracement_ratio: float | None


@dataclass(frozen=True)
class ExpectedExtremePath:
    order: ExtremeOrder
    legs: tuple[ExpectedPriceLeg, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "legs", tuple(self.legs))


@dataclass(frozen=True)
class ExpectedExtremeEvidence:
    order: ExtremeOrder
    initial_side: MovementSide | None
    initial_distance: float
    initial_ratio: float
    main_side: MovementSide | None
    main_distance: float
    main_ratio: float
    final_side: MovementSide | None
    final_distance: float
    final_ratio: float
    signed_displacement: float
    displacement_ratio: float


@dataclass(frozen=True)
class ExpectedFeatures:
    side: CandleSide
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    open_position: float
    close_position: float
    control_score: float
    extreme_order: ExtremeOrder
    initial_side: MovementSide | None
    initial_ratio: float
    final_side: MovementSide | None
    final_ratio: float
    displacement_ratio: float
    total_buyer_movement_ratio: float
    total_seller_movement_ratio: float


@dataclass(frozen=True)
class ExpectedChapter1Candle:
    index: int
    side: CandleSide
    geometry: ExpectedGeometry
    control: ExpectedControl
    intrabar_status: EvaluationStatus
    intrabar_reason: EvaluationReason | None
    legs: tuple[ExpectedPriceLeg, ...] | None
    movements: ExpectedMovementSummary | None
    extreme_path: ExpectedExtremePath | None
    extreme_evidence: ExpectedExtremeEvidence | None
    features: ExpectedFeatures | None
    candle_type_status: EvaluationStatus
    candle_type_reason: EvaluationReason | None

    def __post_init__(self) -> None:
        if self.legs is not None:
            object.__setattr__(self, "legs", tuple(self.legs))


@dataclass(frozen=True)
class ExpectedMarketState:
    status: EvaluationStatus
    reason: EvaluationReason | None
    value: MarketState | None


@dataclass(frozen=True)
class ExpectedBMS:
    status: EvaluationStatus
    reason: EvaluationReason | None
    value: PullbackStructureStatus | None
    broken_point_index: int | None
    breakout_index: int | None


@dataclass(frozen=True)
class ExpectedSMS:
    status: EvaluationStatus
    reason: EvaluationReason | None
    value: SMSStructureStatus | None
    broken_point_index: int | None
    event_index: int | None


@dataclass(frozen=True)
class ExpectedSegment:
    start_index: int
    end_index: int
    level: StructuralLevel
    market_state: ExpectedMarketState
    bms_request: BMSAnalysisRequest | None
    bms: ExpectedBMS | None
    sms_request: SMSAnalysisRequest | None
    sms: ExpectedSMS | None


@dataclass(frozen=True)
class GroundTruthAmbiguity:
    layer: str
    item: str
    note: str


@dataclass(frozen=True)
class GroundTruthCase:
    schema_version: int
    case_id: str
    source: GroundTruthSource
    chapter1: tuple[ExpectedChapter1Candle, ...]
    isolated: tuple[ExpectedPoint, ...]
    short_term: ExpectedStructure
    medium_term: ExpectedStructure
    long_term: ExpectedStructure
    segment: ExpectedSegment | None
    ambiguities: tuple[GroundTruthAmbiguity, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "chapter1", tuple(self.chapter1))
        object.__setattr__(self, "isolated", tuple(self.isolated))
        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))


E = TypeVar("E", bound=Enum)


def _object(
    value: object,
    path: str,
    keys: set[str],
    *,
    optional_keys: set[str] | None = None,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    actual = set(value)
    missing = keys - actual
    unknown = actual - (keys | (optional_keys or set()))
    if missing:
        raise ValueError(f"{path} is missing required keys: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{path} has unknown keys: {', '.join(sorted(unknown))}")
    return value


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    return value


def _string(value: object, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path} must be an integer")
    return value


def _number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a finite number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{path} must be finite")
    return result


def _optional_integer(value: object, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _optional_number(value: object, path: str) -> float | None:
    return None if value is None else _number(value, path)


def _enum(enum_type: type[E], value: object, path: str) -> E:
    raw = _string(value, path)
    try:
        return enum_type(raw)
    except ValueError as error:
        raise ValueError(f"{path} has unknown {enum_type.__name__} value: {raw}") from error


def _optional_enum(enum_type: type[E], value: object, path: str) -> E | None:
    return None if value is None else _enum(enum_type, value, path)


def _status_value(
    value: object,
    path: str,
    enum_type: type[E],
    *,
    keys: set[str] | None = None,
) -> tuple[EvaluationStatus, EvaluationReason | None, E | None]:
    item = _object(value, path, keys or {"status", "reason", "value"})
    status = _enum(EvaluationStatus, item["status"], f"{path}.status")
    reason = _optional_enum(EvaluationReason, item["reason"], f"{path}.reason")
    result = _optional_enum(enum_type, item["value"], f"{path}.value")
    if status is EvaluationStatus.AVAILABLE:
        if reason is not None or result is None:
            raise ValueError(f"{path} AVAILABLE status requires value and no reason")
    elif reason is None or result is not None:
        raise ValueError(f"{path} unavailable or invalid status requires reason and no value")
    return status, reason, result


def _validate_capability_pair(
    status: EvaluationStatus,
    reason: EvaluationReason | None,
    path: str,
    allowed: set[tuple[EvaluationStatus, EvaluationReason | None]],
    *,
    label: str | None = None,
) -> None:
    if (status, reason) not in allowed:
        suffix = "" if label is None else f" ({label})"
        raise ValueError(f"{path}{suffix} has an invalid status/reason combination")


def _validate_parent_child_capability(
    *,
    market_status: EvaluationStatus,
    market_value: MarketState | None,
    child: ExpectedBMS | ExpectedSMS | None,
    path: str,
    label: str,
) -> None:
    if child is None:
        return
    parent_is_nondirectional = (
        market_status is EvaluationStatus.UNAVAILABLE
        or market_value is MarketState.NON_TREND
    )
    child_is_parent_blocked = (
        child.status is EvaluationStatus.UNAVAILABLE
        and child.reason is EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL
    )
    if parent_is_nondirectional and not child_is_parent_blocked:
        raise ValueError(
            f"{path} {label} must be unavailable with "
            "PARENT_STATE_NOT_DIRECTIONAL when market state is not directional"
        )
    if not parent_is_nondirectional and child_is_parent_blocked:
        raise ValueError(
            f"{path} {label} cannot be unavailable with "
            "PARENT_STATE_NOT_DIRECTIONAL for a directional market state"
        )


def _parse_point(
    value: object,
    path: str,
    *,
    require_provenance: bool,
    require_recognition_basis: bool = False,
    forbid_recognition_basis: bool = False,
) -> ExpectedPoint:
    item = _object(
        value,
        path,
        {"index", "kind", "price", "recognition_basis", "confirmed_by_index"},
    )
    index = _integer(item["index"], f"{path}.index")
    confirmed_by_index = _optional_integer(
        item["confirmed_by_index"], f"{path}.confirmed_by_index"
    )
    recognition_basis = _optional_enum(
        IsolatedPointBasis,
        item["recognition_basis"],
        f"{path}.recognition_basis",
    )
    if require_recognition_basis and recognition_basis is None:
        raise ValueError(f"{path}.recognition_basis is required for confirmed isolated points")
    if forbid_recognition_basis and recognition_basis is not None:
        raise ValueError(f"{path}.recognition_basis is not valid above short term")
    if require_provenance:
        if confirmed_by_index is None:
            raise ValueError(f"{path}.confirmed_by_index is required")
        if confirmed_by_index <= index:
            raise ValueError(f"{path}.confirmed_by_index must be after index")
    elif confirmed_by_index is not None:
        raise ValueError(f"{path}.confirmed_by_index is not allowed at short term")
    return ExpectedPoint(
        index=index,
        kind=_enum(IsolatedPointKind, item["kind"], f"{path}.kind"),
        price=_number(item["price"], f"{path}.price"),
        recognition_basis=recognition_basis,
        confirmed_by_index=confirmed_by_index,
    )


def _parse_potential(value: object, path: str) -> ExpectedPotential:
    item = _object(value, path, {"previous_index", "pivot_index", "kind", "price"})
    previous_index = _integer(item["previous_index"], f"{path}.previous_index")
    pivot_index = _integer(item["pivot_index"], f"{path}.pivot_index")
    if previous_index >= pivot_index:
        raise ValueError(f"{path}.previous_index must be before pivot_index")
    return ExpectedPotential(
        previous_index=previous_index,
        pivot_index=pivot_index,
        kind=_enum(IsolatedPointKind, item["kind"], f"{path}.kind"),
        price=_number(item["price"], f"{path}.price"),
    )


def _parse_structure(
    value: object,
    path: str,
    *,
    require_provenance: bool,
    suppression_enum: type[E],
) -> ExpectedStructure:
    item = _object(value, path, {"points", "potentials", "vertices", "suppressed"})
    points = tuple(
        _parse_point(
            member,
            f"{path}.points[{index}]",
            require_provenance=require_provenance,
            forbid_recognition_basis=require_provenance,
        )
        for index, member in enumerate(_list(item["points"], f"{path}.points"))
    )
    vertices = tuple(
        _parse_point(
            member,
            f"{path}.vertices[{index}]",
            require_provenance=require_provenance,
            forbid_recognition_basis=require_provenance,
        )
        for index, member in enumerate(_list(item["vertices"], f"{path}.vertices"))
    )
    potentials = tuple(
        _parse_potential(member, f"{path}.potentials[{index}]")
        for index, member in enumerate(_list(item["potentials"], f"{path}.potentials"))
    )
    suppressed: list[ExpectedSuppression] = []
    for index, member in enumerate(_list(item["suppressed"], f"{path}.suppressed")):
        suppression = _object(member, f"{path}.suppressed[{index}]", {"point", "reason"})
        suppressed.append(
            ExpectedSuppression(
                point=_parse_point(
                    suppression["point"],
                    f"{path}.suppressed[{index}].point",
                    require_provenance=require_provenance,
                    forbid_recognition_basis=require_provenance,
                ),
                reason=_enum(
                    suppression_enum,
                    suppression["reason"],
                    f"{path}.suppressed[{index}].reason",
                ),
            )
        )
    _require_unique_points(points, f"{path}.points")
    _require_unique_points(vertices, f"{path}.vertices")
    _require_unique_potentials(potentials, f"{path}.potentials")
    _require_unique_suppressions(tuple(suppressed), f"{path}.suppressed")
    return ExpectedStructure(points, potentials, vertices, tuple(suppressed))


def _require_unique_points(points: tuple[ExpectedPoint, ...], path: str) -> None:
    identities = [(point.index, point.kind) for point in points]
    if len(set(identities)) != len(identities):
        raise ValueError(f"{path} contains duplicate point identities")


def _require_unique_chapter1_indexes(
    candles: tuple[ExpectedChapter1Candle, ...],
    path: str,
) -> None:
    indexes = [candle.index for candle in candles]
    if len(set(indexes)) != len(indexes):
        raise ValueError(f"{path} contains duplicate candle indexes")


def _require_unique_potentials(
    potentials: tuple[ExpectedPotential, ...],
    path: str,
) -> None:
    identities = [
        (item.previous_index, item.pivot_index, item.kind)
        for item in potentials
    ]
    if len(set(identities)) != len(identities):
        raise ValueError(f"{path} contains duplicate potential identities")


def _require_unique_suppressions(
    suppressions: tuple[ExpectedSuppression, ...],
    path: str,
) -> None:
    identities = [
        (item.point.index, item.point.kind)
        for item in suppressions
    ]
    if len(set(identities)) != len(identities):
        raise ValueError(f"{path} contains duplicate suppression identities")


def _parse_geometry(value: object, path: str) -> ExpectedGeometry:
    item = _object(value, path, {"body_ratio", "upper_wick_ratio", "lower_wick_ratio", "open_position", "close_position"})
    return ExpectedGeometry(*(_number(item[key], f"{path}.{key}") for key in (
        "body_ratio", "upper_wick_ratio", "lower_wick_ratio", "open_position", "close_position"
    )))


def _parse_control(value: object, path: str) -> ExpectedControl:
    item = _object(value, path, {"buyer_control", "seller_control", "buyer_control_ratio", "seller_control_ratio", "control_score"})
    return ExpectedControl(*(_number(item[key], f"{path}.{key}") for key in (
        "buyer_control", "seller_control", "buyer_control_ratio", "seller_control_ratio", "control_score"
    )))


def _parse_leg(value: object, path: str) -> ExpectedPriceLeg:
    item = _object(value, path, {"side", "start_price", "end_price", "distance"})
    return ExpectedPriceLeg(
        side=_enum(MovementSide, item["side"], f"{path}.side"),
        start_price=_number(item["start_price"], f"{path}.start_price"),
        end_price=_number(item["end_price"], f"{path}.end_price"),
        distance=_number(item["distance"], f"{path}.distance"),
    )


def _parse_movements(value: object, path: str) -> ExpectedMovementSummary:
    item = _object(value, path, {
        "first_side", "first_distance", "final_side", "final_distance", "largest_buyer_move",
        "largest_seller_move", "total_buyer_movement", "total_seller_movement", "final_retracement_ratio",
    })
    return ExpectedMovementSummary(
        _optional_enum(MovementSide, item["first_side"], f"{path}.first_side"),
        _number(item["first_distance"], f"{path}.first_distance"),
        _optional_enum(MovementSide, item["final_side"], f"{path}.final_side"),
        _number(item["final_distance"], f"{path}.final_distance"),
        _number(item["largest_buyer_move"], f"{path}.largest_buyer_move"),
        _number(item["largest_seller_move"], f"{path}.largest_seller_move"),
        _number(item["total_buyer_movement"], f"{path}.total_buyer_movement"),
        _number(item["total_seller_movement"], f"{path}.total_seller_movement"),
        _optional_number(item["final_retracement_ratio"], f"{path}.final_retracement_ratio"),
    )


def _parse_extreme_path(value: object, path: str) -> ExpectedExtremePath:
    item = _object(value, path, {"order", "legs"})
    return ExpectedExtremePath(
        order=_enum(ExtremeOrder, item["order"], f"{path}.order"),
        legs=tuple(_parse_leg(member, f"{path}.legs[{index}]") for index, member in enumerate(_list(item["legs"], f"{path}.legs"))),
    )


def _parse_extreme_evidence(value: object, path: str) -> ExpectedExtremeEvidence:
    item = _object(value, path, {
        "order", "initial_side", "initial_distance", "initial_ratio", "main_side", "main_distance",
        "main_ratio", "final_side", "final_distance", "final_ratio", "signed_displacement", "displacement_ratio",
    })
    return ExpectedExtremeEvidence(
        _enum(ExtremeOrder, item["order"], f"{path}.order"),
        _optional_enum(MovementSide, item["initial_side"], f"{path}.initial_side"),
        _number(item["initial_distance"], f"{path}.initial_distance"),
        _number(item["initial_ratio"], f"{path}.initial_ratio"),
        _optional_enum(MovementSide, item["main_side"], f"{path}.main_side"),
        _number(item["main_distance"], f"{path}.main_distance"),
        _number(item["main_ratio"], f"{path}.main_ratio"),
        _optional_enum(MovementSide, item["final_side"], f"{path}.final_side"),
        _number(item["final_distance"], f"{path}.final_distance"),
        _number(item["final_ratio"], f"{path}.final_ratio"),
        _number(item["signed_displacement"], f"{path}.signed_displacement"),
        _number(item["displacement_ratio"], f"{path}.displacement_ratio"),
    )


def _parse_features(value: object, path: str) -> ExpectedFeatures:
    item = _object(value, path, {
        "side", "body_ratio", "upper_wick_ratio", "lower_wick_ratio", "open_position", "close_position",
        "control_score", "extreme_order", "initial_side", "initial_ratio", "final_side", "final_ratio",
        "displacement_ratio", "total_buyer_movement_ratio", "total_seller_movement_ratio",
    })
    return ExpectedFeatures(
        _enum(CandleSide, item["side"], f"{path}.side"),
        *(_number(item[key], f"{path}.{key}") for key in (
            "body_ratio", "upper_wick_ratio", "lower_wick_ratio", "open_position", "close_position", "control_score"
        )),
        _enum(ExtremeOrder, item["extreme_order"], f"{path}.extreme_order"),
        _optional_enum(MovementSide, item["initial_side"], f"{path}.initial_side"),
        _number(item["initial_ratio"], f"{path}.initial_ratio"),
        _optional_enum(MovementSide, item["final_side"], f"{path}.final_side"),
        _number(item["final_ratio"], f"{path}.final_ratio"),
        _number(item["displacement_ratio"], f"{path}.displacement_ratio"),
        _number(item["total_buyer_movement_ratio"], f"{path}.total_buyer_movement_ratio"),
        _number(item["total_seller_movement_ratio"], f"{path}.total_seller_movement_ratio"),
    )


def _parse_chapter1(value: object, path: str) -> ExpectedChapter1Candle:
    item = _object(value, path, {
        "index", "side", "geometry", "control", "intrabar_status", "intrabar_reason", "legs", "movements",
        "extreme_path", "extreme_evidence", "features", "candle_type_status", "candle_type_reason",
    })
    intrabar_status = _enum(EvaluationStatus, item["intrabar_status"], f"{path}.intrabar_status")
    intrabar_reason = _optional_enum(EvaluationReason, item["intrabar_reason"], f"{path}.intrabar_reason")
    intrabar_values = (item["legs"], item["movements"], item["extreme_path"], item["extreme_evidence"], item["features"])
    if intrabar_status is EvaluationStatus.AVAILABLE:
        if intrabar_reason is not None or any(member is None for member in intrabar_values):
            raise ValueError(f"{path} available intrabar output requires all values and no reason")
    elif (
        intrabar_status is not EvaluationStatus.UNAVAILABLE
        or intrabar_reason is not EvaluationReason.INTRABAR_DATA_UNAVAILABLE
        or any(member is not None for member in intrabar_values)
    ):
        raise ValueError(f"{path} intrabar output must be available or unavailable for missing data")
    candle_type_status = _enum(EvaluationStatus, item["candle_type_status"], f"{path}.candle_type_status")
    candle_type_reason = _optional_enum(EvaluationReason, item["candle_type_reason"], f"{path}.candle_type_reason")
    if (
        candle_type_status is not EvaluationStatus.UNAVAILABLE
        or candle_type_reason is not EvaluationReason.CANDLE_TYPE_UNCALIBRATED
    ):
        raise ValueError(f"{path} candle type must be unavailable and uncalibrated")
    return ExpectedChapter1Candle(
        index=_integer(item["index"], f"{path}.index"),
        side=_enum(CandleSide, item["side"], f"{path}.side"),
        geometry=_parse_geometry(item["geometry"], f"{path}.geometry"),
        control=_parse_control(item["control"], f"{path}.control"),
        intrabar_status=intrabar_status,
        intrabar_reason=intrabar_reason,
        legs=(None if item["legs"] is None else tuple(_parse_leg(member, f"{path}.legs[{index}]") for index, member in enumerate(_list(item["legs"], f"{path}.legs")))),
        movements=(None if item["movements"] is None else _parse_movements(item["movements"], f"{path}.movements")),
        extreme_path=(None if item["extreme_path"] is None else _parse_extreme_path(item["extreme_path"], f"{path}.extreme_path")),
        extreme_evidence=(None if item["extreme_evidence"] is None else _parse_extreme_evidence(item["extreme_evidence"], f"{path}.extreme_evidence")),
        features=(None if item["features"] is None else _parse_features(item["features"], f"{path}.features")),
        candle_type_status=candle_type_status,
        candle_type_reason=candle_type_reason,
    )


def _parse_request(value: object, path: str, fields: tuple[str, ...]) -> tuple[int, ...] | None:
    if value is None:
        return None
    item = _object(value, path, set(fields))
    return tuple(_integer(item[field], f"{path}.{field}") for field in fields)


def _parse_bms(value: object, path: str) -> ExpectedBMS | None:
    if value is None:
        return None
    item = _object(value, path, {"status", "reason", "value", "broken_point_index", "breakout_index"})
    status, reason, result = _status_value(
        item,
        path,
        PullbackStructureStatus,
        keys={"status", "reason", "value", "broken_point_index", "breakout_index"},
    )
    _validate_capability_pair(
        status,
        reason,
        path,
        {
            (EvaluationStatus.AVAILABLE, None),
            (EvaluationStatus.UNAVAILABLE, EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL),
            (EvaluationStatus.INVALID, EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX),
            (EvaluationStatus.INVALID, EvaluationReason.INVALID_CONTEXT),
            (EvaluationStatus.INVALID, EvaluationReason.OHLC_INTRABAR_ORDER_AMBIGUOUS),
        },
        label="BMS",
    )
    broken_point_index = _optional_integer(item["broken_point_index"], f"{path}.broken_point_index")
    breakout_index = _optional_integer(item["breakout_index"], f"{path}.breakout_index")
    has_event = broken_point_index is not None and breakout_index is not None
    if (broken_point_index is None) != (breakout_index is None):
        raise ValueError(f"{path} BMS event details must be both present or absent")
    if status is not EvaluationStatus.AVAILABLE and has_event:
        raise ValueError(f"{path} unavailable or invalid BMS result cannot contain event details")
    if result is PullbackStructureStatus.BMS_CONFIRMED and not has_event:
        raise ValueError(f"{path} confirmed BMS requires broken point and breakout index")
    if result is not PullbackStructureStatus.BMS_CONFIRMED and has_event:
        raise ValueError(f"{path} nonterminal BMS result cannot contain event details")
    return ExpectedBMS(status, reason, result, broken_point_index, breakout_index)


def _parse_sms(value: object, path: str) -> ExpectedSMS | None:
    if value is None:
        return None
    item = _object(value, path, {"status", "reason", "value", "broken_point_index", "event_index"})
    status, reason, result = _status_value(
        item,
        path,
        SMSStructureStatus,
        keys={"status", "reason", "value", "broken_point_index", "event_index"},
    )
    _validate_capability_pair(
        status,
        reason,
        path,
        {
            (EvaluationStatus.AVAILABLE, None),
            (EvaluationStatus.UNAVAILABLE, EvaluationReason.PARENT_STATE_NOT_DIRECTIONAL),
            (EvaluationStatus.INVALID, EvaluationReason.BOUNDARY_NOT_CANONICAL_VERTEX),
            (EvaluationStatus.INVALID, EvaluationReason.INVALID_CONTEXT),
            (EvaluationStatus.INVALID, EvaluationReason.OHLC_INTRABAR_ORDER_AMBIGUOUS),
        },
        label="SMS",
    )
    broken_point_index = _optional_integer(item["broken_point_index"], f"{path}.broken_point_index")
    event_index = _optional_integer(item["event_index"], f"{path}.event_index")
    has_event = broken_point_index is not None and event_index is not None
    if (broken_point_index is None) != (event_index is None):
        raise ValueError(f"{path} SMS event details must be both present or absent")
    if status is not EvaluationStatus.AVAILABLE and has_event:
        raise ValueError(f"{path} unavailable or invalid SMS result cannot contain event details")
    if result in {SMSStructureStatus.SMS_CONFIRMED, SMSStructureStatus.PARENT_CONTINUED}:
        if not has_event:
            raise ValueError(f"{path} terminal SMS result requires broken point and event index")
    elif has_event:
        raise ValueError(f"{path} nonterminal SMS result cannot contain event details")
    return ExpectedSMS(status, reason, result, broken_point_index, event_index)


def _parse_segment(value: object, path: str) -> ExpectedSegment | None:
    if value is None:
        return None
    item = _object(value, path, {"start_index", "end_index", "level", "market_state", "bms_request", "bms", "sms_request", "sms"})
    start_index = _integer(item["start_index"], f"{path}.start_index")
    end_index = _integer(item["end_index"], f"{path}.end_index")
    if start_index > end_index:
        raise ValueError(f"{path}.start_index must not be after end_index")
    market_status, market_reason, market_value = _status_value(item["market_state"], f"{path}.market_state", MarketState)
    _validate_capability_pair(
        market_status,
        market_reason,
        f"{path}.market_state",
        {
            (EvaluationStatus.AVAILABLE, None),
            (EvaluationStatus.UNAVAILABLE, EvaluationReason.INSUFFICIENT_STRUCTURE),
        },
    )
    bms_request = _parse_request(item["bms_request"], f"{path}.bms_request", ("trend_origin_index", "previous_extreme_index", "pullback_extreme_index"))
    sms_request = _parse_request(item["sms_request"], f"{path}.sms_request", ("trend_extreme_index", "creator_point_index"))
    bms = _parse_bms(item["bms"], f"{path}.bms")
    sms = _parse_sms(item["sms"], f"{path}.sms")
    if (bms_request is None) != (bms is None) or (sms_request is None) != (sms is None):
        raise ValueError(f"{path} request and expected result presence must match")
    _validate_parent_child_capability(
        market_status=market_status,
        market_value=market_value,
        child=bms,
        path=path,
        label="BMS",
    )
    _validate_parent_child_capability(
        market_status=market_status,
        market_value=market_value,
        child=sms,
        path=path,
        label="SMS",
    )
    return ExpectedSegment(
        start_index=start_index,
        end_index=end_index,
        level=_enum(StructuralLevel, item["level"], f"{path}.level"),
        market_state=ExpectedMarketState(market_status, market_reason, market_value),
        bms_request=None if bms_request is None else BMSAnalysisRequest(*bms_request),
        bms=bms,
        sms_request=None if sms_request is None else SMSAnalysisRequest(*sms_request),
        sms=sms,
    )


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of the exact source bytes at *path*."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"ground truth JSON has duplicate key: {key}")
        result[key] = value
    return result


def load_ground_truth(path: str | Path) -> GroundTruthCase:
    """Load one strictly versioned, immutable ground-truth JSON document."""

    try:
        with Path(path).open("r", encoding="utf-8") as source:
            payload = json.load(source, object_pairs_hook=_reject_duplicate_members)
    except json.JSONDecodeError as error:
        raise ValueError(f"ground truth JSON is malformed: {error.msg}") from error
    document = _object(payload, "ground truth", {"schema_version", "case_id", "source", "expected", "ambiguities"})
    schema_version = _integer(document["schema_version"], "ground truth.schema_version")
    if schema_version != 1:
        raise ValueError("ground truth.schema_version must be 1")
    case_id = _string(document["case_id"], "ground truth.case_id")
    source_value = _object(
        document["source"],
        "ground truth.source",
        {"market_data_file", "sha256", "instrument", "timeframe", "start_index", "candle_count"},
        optional_keys={"price_tolerance", "price_tolerance_justification"},
    )
    source_hash = _string(source_value["sha256"], "ground truth.source.sha256")
    if len(source_hash) != 64 or any(character not in "0123456789abcdef" for character in source_hash):
        raise ValueError("ground truth.source.sha256 must be a lowercase SHA-256 digest")
    candle_count = _integer(source_value["candle_count"], "ground truth.source.candle_count")
    if not 1 <= candle_count <= 250:
        raise ValueError("ground truth.source.candle_count must be 1 through 250")
    source = GroundTruthSource(
        market_data_file=_string(source_value["market_data_file"], "ground truth.source.market_data_file"),
        sha256=source_hash,
        instrument=_string(source_value["instrument"], "ground truth.source.instrument"),
        timeframe=_string(source_value["timeframe"], "ground truth.source.timeframe"),
        start_index=_integer(source_value["start_index"], "ground truth.source.start_index"),
        candle_count=candle_count,
        price_tolerance=_number(
            source_value.get("price_tolerance", 0.0),
            "ground truth.source.price_tolerance",
        ),
        price_tolerance_justification=(
            None
            if source_value.get("price_tolerance_justification") is None
            else _string(
                source_value["price_tolerance_justification"],
                "ground truth.source.price_tolerance_justification",
            )
        ),
    )
    expected = _object(document["expected"], "ground truth.expected", {"chapter1", "isolated", "short_term", "medium_term", "long_term", "segment"})
    chapter1 = tuple(_parse_chapter1(member, f"ground truth.expected.chapter1[{index}]") for index, member in enumerate(_list(expected["chapter1"], "ground truth.expected.chapter1")))
    isolated = tuple(
        _parse_point(
            member,
            f"ground truth.expected.isolated[{index}]",
            require_provenance=False,
            require_recognition_basis=True,
        )
        for index, member in enumerate(
            _list(expected["isolated"], "ground truth.expected.isolated")
        )
    )
    _require_unique_points(isolated, "ground truth.expected.isolated")
    _require_unique_chapter1_indexes(chapter1, "ground truth.expected.chapter1")
    ambiguities = tuple(
        GroundTruthAmbiguity(
            layer=_string(item["layer"], f"ground truth.ambiguities[{index}].layer"),
            item=_string(item["item"], f"ground truth.ambiguities[{index}].item"),
            note=_string(item["note"], f"ground truth.ambiguities[{index}].note"),
        )
        for index, raw in enumerate(_list(document["ambiguities"], "ground truth.ambiguities"))
        for item in [_object(raw, f"ground truth.ambiguities[{index}]", {"layer", "item", "note"})]
    )
    if len({(item.layer, item.item) for item in ambiguities}) != len(ambiguities):
        raise ValueError("ground truth.ambiguities contains duplicate layer/item identities")
    return GroundTruthCase(
        schema_version=schema_version,
        case_id=case_id,
        source=source,
        chapter1=chapter1,
        isolated=isolated,
        short_term=_parse_structure(expected["short_term"], "ground truth.expected.short_term", require_provenance=False, suppression_enum=ShortTermSuppressionReason),
        medium_term=_parse_structure(expected["medium_term"], "ground truth.expected.medium_term", require_provenance=True, suppression_enum=MediumTermSuppressionReason),
        long_term=_parse_structure(expected["long_term"], "ground truth.expected.long_term", require_provenance=True, suppression_enum=LongTermSuppressionReason),
        segment=_parse_segment(expected["segment"], "ground truth.expected.segment"),
        ambiguities=ambiguities,
    )


def verify_ground_truth_source(
    case: GroundTruthCase,
    market_data_path: str | Path,
) -> None:
    """Verify that a label document still names and hashes its source bytes."""

    source_path = Path(market_data_path)
    if source_path.name != case.source.market_data_file:
        raise ValueError("market data filename does not match ground truth source")
    actual = sha256_file(source_path)
    if actual != case.source.sha256:
        raise ValueError("SHA-256 mismatch for ground truth source")
