"""Exact, source-bound offline validation scoring."""

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from math import isfinite

from trading.analysis.offline import OfflineMarketAnalysis
from trading.validation.ground_truth import (
    ExpectedPoint,
    GroundTruthAmbiguity,
    GroundTruthCase,
)


class DiscrepancyClass(Enum):
    ENGINE_FAILURE = "engine_failure"
    GROUND_TRUTH_DISAGREEMENT = "ground_truth_disagreement"
    COURSE_AMBIGUITY = "course_ambiguity"


@dataclass(frozen=True)
class DetectionMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class LayerScore:
    layer: str
    exact_match: bool
    discrepancies: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "discrepancies", tuple(self.discrepancies))


@dataclass(frozen=True)
class ValidationReport:
    case_id: str
    source_sha256: str
    chapter1: LayerScore
    isolated_metrics: DetectionMetrics
    isolated: LayerScore
    short_term: LayerScore
    medium_term: LayerScore
    long_term: LayerScore
    segment: LayerScore | None
    outcomes: tuple[DiscrepancyClass, ...]
    ambiguities: tuple[GroundTruthAmbiguity, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))


def _plain(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return tuple(_plain(item) for item in value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _is_price_path(path: str) -> bool:
    return path.rsplit(".", 1)[-1] in {"price", "start_price", "end_price"}


def _differences(
    actual: object,
    expected: object,
    *,
    path: str,
    price_tolerance: float,
) -> tuple[str, ...]:
    actual = _plain(actual)
    expected = _plain(expected)
    if isinstance(actual, dict) and isinstance(expected, dict):
        result: list[str] = []
        for key in expected:
            child = f"{path}.{key}" if path else key
            if key not in actual:
                result.append(child)
            else:
                result.extend(
                    _differences(
                        actual[key],
                        expected[key],
                        path=child,
                        price_tolerance=price_tolerance,
                    )
                )
        for key in actual:
            if key not in expected:
                result.append(f"{path}.{key}" if path else str(key))
        return tuple(result)
    if isinstance(actual, tuple) and isinstance(expected, tuple):
        result = []
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            result.extend(
                _differences(
                    actual_item,
                    expected_item,
                    path=f"{path}[{index}]",
                    price_tolerance=price_tolerance,
                )
            )
        result.extend(f"{path}[{index}]" for index in range(len(actual), len(expected)))
        result.extend(f"{path}[{index}]" for index in range(len(expected), len(actual)))
        return tuple(result)
    if (
        _is_price_path(path)
        and isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and abs(actual - expected) <= price_tolerance
    ):
        return ()
    return () if actual == expected else (path,)


@dataclass(frozen=True)
class _IsolatedIdentity:
    index: int
    kind: str
    price: float
    recognition_basis: str

    @property
    def anchor(self) -> tuple[int, str, str]:
        return (self.index, self.kind, self.recognition_basis)


@dataclass(frozen=True)
class _IsolatedAmbiguityResolution:
    expected_indices: frozenset[int]
    actual_indices: frozenset[int]
    used: tuple[GroundTruthAmbiguity, ...]


def _expected_identity(point: ExpectedPoint) -> _IsolatedIdentity:
    return _IsolatedIdentity(
        point.index,
        point.kind.value,
        point.price,
        "none" if point.recognition_basis is None else point.recognition_basis.value,
    )


def _native_identity(point: dict[str, object]) -> _IsolatedIdentity:
    kind = point["kind"]
    basis = point["recognition_basis"]
    return _IsolatedIdentity(
        int(point["index"]),
        kind.value,  # type: ignore[union-attr]
        float(point["price"]),
        "none" if basis is None else basis.value,  # type: ignore[union-attr]
    )


def _parse_isolated_identity(value: str) -> _IsolatedIdentity | None:
    parts = value.split("|")
    if len(parts) != 4:
        return None
    fields: dict[str, str] = {}
    for part in parts:
        key, separator, item = part.partition(":")
        if not separator or key in fields:
            return None
        fields[key] = item
    if set(fields) != {"index", "kind", "price", "recognition_basis"}:
        return None
    try:
        index = int(fields["index"])
        price = float(fields["price"])
    except ValueError:
        return None
    if not isfinite(price) or not fields["kind"] or not fields["recognition_basis"]:
        return None
    return _IsolatedIdentity(index, fields["kind"], price, fields["recognition_basis"])


def _resolve_isolated_ambiguities(
    actual: tuple[dict[str, object], ...],
    expected: tuple[ExpectedPoint, ...],
    ambiguities: tuple[GroundTruthAmbiguity, ...],
) -> _IsolatedAmbiguityResolution:
    declared = tuple(
        (ambiguity, identity)
        for ambiguity in ambiguities
        if ambiguity.layer == "isolated"
        for identity in (_parse_isolated_identity(ambiguity.item),)
        if identity is not None
    )
    expected_identities = tuple(_expected_identity(point) for point in expected)
    actual_identities = tuple(_native_identity(point) for point in actual)
    expected_indices = frozenset(
        index
        for index, identity in enumerate(expected_identities)
        if any(identity == declared_identity for _, declared_identity in declared)
    )
    expected_anchors = {
        expected_identities[index].anchor for index in expected_indices
    }
    actual_indices = frozenset(
        index
        for index, identity in enumerate(actual_identities)
        if any(identity == declared_identity for _, declared_identity in declared)
        or identity.anchor in expected_anchors
    )
    used = tuple(
        ambiguity
        for ambiguity, identity in declared
        if identity in expected_identities or identity in actual_identities
    )
    return _IsolatedAmbiguityResolution(expected_indices, actual_indices, used)


def _native_point(point: object, *, recognition_basis: object | None = None) -> dict[str, object]:
    index = getattr(point, "index", getattr(point, "pivot_index", None))
    confirmed = getattr(point, "confirmed_by_index", None)
    return {
        "index": index,
        "kind": getattr(point, "kind"),
        "price": getattr(point, "price"),
        "recognition_basis": recognition_basis,
        "confirmed_by_index": confirmed,
    }


def _native_potential(potential: object) -> dict[str, object]:
    previous = getattr(potential, "previous_same_kind")
    return {
        "previous_index": getattr(previous, "index", getattr(previous, "pivot_index", None)),
        "pivot_index": getattr(potential, "pivot_index"),
        "kind": getattr(potential, "kind"),
        "price": getattr(potential, "price"),
    }


def _native_structure(structure: object, *, short_term: bool) -> dict[str, object]:
    def point(item: object) -> dict[str, object]:
        return _native_point(item, recognition_basis=getattr(item, "recognition_basis", None))

    return {
        "points": tuple(point(item) for item in structure.points),  # type: ignore[attr-defined]
        "potentials": ()
        if short_term
        else tuple(_native_potential(item) for item in structure.potentials),  # type: ignore[attr-defined]
        "vertices": tuple(point(item) for item in structure.vertices),  # type: ignore[attr-defined]
        "suppressed": tuple(
            {"point": point(item.point), "reason": item.reason}
            for item in structure.suppressed  # type: ignore[attr-defined]
        ),
    }


def _native_chapter1(candle: object) -> dict[str, object]:
    intrabar = candle.intrabar_analysis  # type: ignore[attr-defined]
    features = candle.features  # type: ignore[attr-defined]
    candle_type = candle.candle_type  # type: ignore[attr-defined]
    analysis = intrabar.value
    return {
        "index": candle.index,  # type: ignore[attr-defined]
        "side": candle.side,  # type: ignore[attr-defined]
        "geometry": candle.geometry,  # type: ignore[attr-defined]
        "control": candle.control,  # type: ignore[attr-defined]
        "intrabar_status": intrabar.status,
        "intrabar_reason": intrabar.reason,
        "legs": None if analysis is None else tuple(analysis.legs),
        "movements": None if analysis is None else analysis.movements,
        "extreme_path": None if analysis is None else analysis.extreme_path,
        "extreme_evidence": None if analysis is None else analysis.extreme_evidence,
        "features": features.value,
        "candle_type_status": candle_type.status,
        "candle_type_reason": candle_type.reason,
    }


def _native_evaluation(evaluation: object | None, *, event_name: str) -> object:
    if evaluation is None:
        return None
    value = evaluation.value  # type: ignore[attr-defined]
    return {
        "status": evaluation.status,  # type: ignore[attr-defined]
        "reason": evaluation.reason,  # type: ignore[attr-defined]
        "value": None if value is None else value.status,
        "broken_point_index": None
        if value is None or getattr(value, "broken_extreme", None) is None and getattr(value, "broken_point", None) is None
        else getattr(value, "broken_extreme", getattr(value, "broken_point", None)).index,
        event_name: None if value is None else getattr(value, event_name),
    }


def _native_segment(segment: object | None) -> object:
    if segment is None:
        return None
    request = segment.request  # type: ignore[attr-defined]
    return {
        "start_index": request.segment.start_index,
        "end_index": request.segment.end_index,
        "level": request.level,
        "market_state": {
            "status": segment.market_state.status,  # type: ignore[attr-defined]
            "reason": segment.market_state.reason,  # type: ignore[attr-defined]
            "value": segment.market_state.value,  # type: ignore[attr-defined]
        },
        "bms_request": request.bms,
        "bms": _native_evaluation(segment.bms, event_name="breakout_index"),  # type: ignore[attr-defined]
        "sms_request": request.sms,
        "sms": _native_evaluation(segment.sms, event_name="event_index"),  # type: ignore[attr-defined]
    }


def _point_matches(
    actual: dict[str, object], expected: ExpectedPoint, price_tolerance: float
) -> bool:
    return (
        actual["index"] == expected.index
        and actual["kind"] is expected.kind
        and actual["recognition_basis"] is expected.recognition_basis
        and abs(float(actual["price"]) - expected.price) <= price_tolerance
    )


def _isolated_metrics(
    actual: tuple[dict[str, object], ...],
    expected: tuple[ExpectedPoint, ...],
    ambiguities: tuple[GroundTruthAmbiguity, ...],
    price_tolerance: float,
) -> tuple[DetectionMetrics, tuple[GroundTruthAmbiguity, ...]]:
    resolution = _resolve_isolated_ambiguities(actual, expected, ambiguities)
    filtered_expected = tuple(
        point for index, point in enumerate(expected) if index not in resolution.expected_indices
    )
    filtered_actual = tuple(
        point for index, point in enumerate(actual) if index not in resolution.actual_indices
    )
    unmatched_actual = list(filtered_actual)
    true_positives = 0
    for expected_point in filtered_expected:
        for index, actual_point in enumerate(unmatched_actual):
            if _point_matches(actual_point, expected_point, price_tolerance):
                true_positives += 1
                del unmatched_actual[index]
                break
    false_positives = len(unmatched_actual)
    false_negatives = len(filtered_expected) - true_positives
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else (1.0 if false_negatives == 0 else 0.0)
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else (1.0 if false_positives == 0 else 0.0)
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return (
        DetectionMetrics(true_positives, false_positives, false_negatives, precision, recall, f1),
        resolution.used,
    )


def _isolated_difference_is_only_declared_ambiguity(
    actual: tuple[dict[str, object], ...],
    expected: tuple[ExpectedPoint, ...],
    ambiguities: tuple[GroundTruthAmbiguity, ...],
    price_tolerance: float,
) -> bool:
    resolution = _resolve_isolated_ambiguities(actual, expected, ambiguities)
    unmatched_actual = [
        index for index in range(len(actual)) if index not in resolution.actual_indices
    ]
    matched: dict[int, int] = {}
    for expected_index, expected_point in enumerate(expected):
        if expected_index in resolution.expected_indices:
            continue
        for position, actual_index in enumerate(unmatched_actual):
            if _point_matches(actual[actual_index], expected_point, price_tolerance):
                matched[expected_index] = actual_index
                del unmatched_actual[position]
                break
        else:
            return False
    if unmatched_actual:
        return False

    expected_identities = tuple(_expected_identity(point) for point in expected)
    actual_identities = tuple(_native_identity(point) for point in actual)
    shared_ambiguous_anchors = {
        expected_identities[expected_index].anchor
        for expected_index in resolution.expected_indices
        if any(
            actual_identities[actual_index].anchor
            == expected_identities[expected_index].anchor
            for actual_index in resolution.actual_indices
        )
    }
    reverse_matches = {
        actual_index: expected_index
        for expected_index, actual_index in matched.items()
    }
    expected_order: list[tuple[str, object]] = []
    for index, identity in enumerate(expected_identities):
        if index in resolution.expected_indices:
            if identity.anchor in shared_ambiguous_anchors:
                expected_order.append(("ambiguous", identity.anchor))
        elif index in matched:
            expected_order.append(("unambiguous", index))
    actual_order: list[tuple[str, object]] = []
    for index, identity in enumerate(actual_identities):
        if index in resolution.actual_indices:
            if identity.anchor in shared_ambiguous_anchors:
                actual_order.append(("ambiguous", identity.anchor))
        elif index in reverse_matches:
            actual_order.append(("unambiguous", reverse_matches[index]))
    return tuple(expected_order) == tuple(actual_order)


def _validate_analysis_source(
    analysis: OfflineMarketAnalysis,
    expected: GroundTruthCase,
) -> None:
    window = analysis.window
    source = expected.source
    bindings = (
        ("instrument", window.instrument, source.instrument),
        ("timeframe", window.timeframe, source.timeframe),
        ("start_index", window.start_index, source.start_index),
        ("candle_count", len(window.candles), source.candle_count),
    )
    for field, actual, expected_value in bindings:
        if actual != expected_value:
            raise ValueError(
                f"analysis window {field} does not match ground-truth source"
            )


def _layer(layer: str, actual: object, expected: object, price_tolerance: float) -> LayerScore:
    discrepancies = _differences(
        actual, expected, path=layer, price_tolerance=price_tolerance
    )
    return LayerScore(layer, not discrepancies, discrepancies)


def _validate_tolerance(price_tolerance: float) -> None:
    if (
        isinstance(price_tolerance, bool)
        or not isinstance(price_tolerance, (int, float))
        or not isfinite(price_tolerance)
        or price_tolerance < 0
    ):
        raise ValueError("price_tolerance must be a finite non-negative number")


def score_analysis(
    analysis: OfflineMarketAnalysis,
    expected: GroundTruthCase,
    *,
    price_tolerance: float = 0.0,
) -> ValidationReport:
    """Compare completed analysis with independently prepared ground truth only."""

    _validate_tolerance(price_tolerance)
    _validate_analysis_source(analysis, expected)
    if price_tolerance != expected.source.price_tolerance:
        raise ValueError(
            "price_tolerance must match the recorded ground-truth source tolerance"
        )
    expected_chapter1_indexes = {candle.index for candle in expected.chapter1}
    actual_chapter1 = tuple(
        _native_chapter1(candle)
        for candle in analysis.candles
        if candle.index in expected_chapter1_indexes
    )
    chapter1 = _layer("chapter1", actual_chapter1, expected.chapter1, price_tolerance)

    actual_isolated = tuple(
        _native_point(item.point, recognition_basis=item.basis)
        for item in analysis.hierarchy.isolated.recognitions
    )
    isolated = _layer("isolated", actual_isolated, expected.isolated, price_tolerance)
    isolated_metrics, isolated_ambiguities = _isolated_metrics(
        actual_isolated, expected.isolated, expected.ambiguities, price_tolerance
    )
    isolated_difference_is_only_ambiguity = _isolated_difference_is_only_declared_ambiguity(
        actual_isolated, expected.isolated, expected.ambiguities, price_tolerance
    )
    short_term = _layer(
        "short_term",
        _native_structure(analysis.hierarchy.short_term, short_term=True),
        expected.short_term,
        price_tolerance,
    )
    medium_term = _layer(
        "medium_term",
        _native_structure(analysis.hierarchy.medium_term, short_term=False),
        expected.medium_term,
        price_tolerance,
    )
    long_term = _layer(
        "long_term",
        _native_structure(analysis.hierarchy.long_term, short_term=False),
        expected.long_term,
        price_tolerance,
    )
    actual_segment = _native_segment(analysis.segment)
    if actual_segment is None and expected.segment is None:
        segment = None
    else:
        segment = _layer("segment", actual_segment, expected.segment, price_tolerance)

    layers = (chapter1, isolated, short_term, medium_term, long_term)
    if segment is not None:
        layers += (segment,)
    ambiguity_paths = {
        (item.layer, item.item)
        for item in expected.ambiguities
    }
    used_path_ambiguities = tuple(
        item
        for item in expected.ambiguities
        if any(
            item.layer == layer.layer
            and item.item in {discrepancy, discrepancy.removeprefix(f"{layer.layer}.")}
            for layer in layers
            for discrepancy in layer.discrepancies
        )
    )
    unambiguous_differences = [
        discrepancy
        for layer in layers
        for discrepancy in layer.discrepancies
        if not (layer.layer == "isolated" and isolated_difference_is_only_ambiguity)
        if (layer.layer, discrepancy) not in ambiguity_paths
        and (layer.layer, discrepancy.removeprefix(f"{layer.layer}."))
        not in ambiguity_paths
    ]
    outcomes: list[DiscrepancyClass] = []
    if isolated_ambiguities or used_path_ambiguities:
        outcomes.append(DiscrepancyClass.COURSE_AMBIGUITY)
    if (
        unambiguous_differences
        or isolated_metrics.false_positives
        or isolated_metrics.false_negatives
    ):
        outcomes.append(DiscrepancyClass.GROUND_TRUTH_DISAGREEMENT)
    return ValidationReport(
        expected.case_id,
        expected.source.sha256,
        chapter1,
        isolated_metrics,
        isolated,
        short_term,
        medium_term,
        long_term,
        segment,
        tuple(outcomes),
        expected.ambiguities,
    )


def report_engine_failure(
    expected: GroundTruthCase,
    error: BaseException,
) -> ValidationReport:
    """Describe an analyzer or loader failure without scoring it as disagreement."""

    diagnostic = f"engine failure: {type(error).__name__}: {error}"
    failed = lambda layer: LayerScore(layer, False, (diagnostic,))
    return ValidationReport(
        expected.case_id,
        expected.source.sha256,
        failed("chapter1"),
        DetectionMetrics(0, 0, 0, 0.0, 0.0, 0.0),
        failed("isolated"),
        failed("short_term"),
        failed("medium_term"),
        failed("long_term"),
        None if expected.segment is None else failed("segment"),
        (DiscrepancyClass.ENGINE_FAILURE,),
        expected.ambiguities,
    )
