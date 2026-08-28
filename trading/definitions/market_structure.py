"""Explicit, segment-relative Chapter 2 market-structure definitions."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .candles import Candle


@dataclass(frozen=True)
class MarketSegment:
    """Inclusive candle-index boundaries selected by the caller."""

    start_index: int
    end_index: int

    def __post_init__(self) -> None:
        if self.start_index > self.end_index:
            raise ValueError("start_index must not be after end_index")


class StructurePointKind(Enum):
    """Whether an explicitly supplied structural point is a high or low."""

    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True)
class StructurePoint:
    """A structural price point already identified by the caller."""

    index: int
    kind: StructurePointKind
    price: float


class StructureRelationship(Enum):
    """The directional relationship between chronological same-kind points."""

    HIGHER_HIGH = "higher_high"
    LOWER_HIGH = "lower_high"
    EQUAL_HIGH = "equal_high"
    HIGHER_LOW = "higher_low"
    LOWER_LOW = "lower_low"
    EQUAL_LOW = "equal_low"


class MarketState(Enum):
    """The course-defined state of one explicit market segment."""

    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    NON_TREND = "non_trend"


def compare_structure_points(
    previous: StructurePoint,
    later: StructurePoint,
) -> StructureRelationship:
    """Compare chronological structural points of the same kind."""

    if previous.kind is not later.kind:
        raise ValueError("structure-point comparison requires the same kind")
    if later.index <= previous.index:
        raise ValueError("same-kind structure points must be chronological")

    if previous.kind is StructurePointKind.HIGH:
        if later.price > previous.price:
            return StructureRelationship.HIGHER_HIGH
        if later.price < previous.price:
            return StructureRelationship.LOWER_HIGH
        return StructureRelationship.EQUAL_HIGH

    if later.price > previous.price:
        return StructureRelationship.HIGHER_LOW
    if later.price < previous.price:
        return StructureRelationship.LOWER_LOW
    return StructureRelationship.EQUAL_LOW


def _validate_segment_points(
    segment: MarketSegment,
    points: Sequence[StructurePoint],
) -> None:
    previous_index: int | None = None
    seen_same_kind_indexes: set[tuple[int, StructurePointKind]] = set()

    for point in points:
        if not segment.start_index <= point.index <= segment.end_index:
            raise ValueError("structure point is outside segment")
        if previous_index is not None and point.index < previous_index:
            raise ValueError("structure points must be chronological")

        point_identity = (point.index, point.kind)
        if point_identity in seen_same_kind_indexes:
            raise ValueError("duplicate same-kind structure-point index")
        seen_same_kind_indexes.add(point_identity)
        previous_index = point.index


def _relationships_for_kind(
    points: Sequence[StructurePoint],
    kind: StructurePointKind,
) -> list[StructureRelationship]:
    same_kind_points = [point for point in points if point.kind is kind]
    return [
        compare_structure_points(previous, later)
        for previous, later in zip(same_kind_points, same_kind_points[1:])
    ]


def _all_relationships_are(
    relationships: Sequence[StructureRelationship],
    expected: StructureRelationship,
) -> bool:
    return bool(relationships) and all(
        relationship is expected for relationship in relationships
    )


def _resolve_market_state(uptrend: bool, downtrend: bool) -> MarketState:
    if uptrend and downtrend:
        raise ValueError("contradictory market-state candidates")
    if uptrend:
        return MarketState.UPTREND
    if downtrend:
        return MarketState.DOWNTREND
    return MarketState.NON_TREND


def classify_market_state(
    segment: MarketSegment,
    points: Sequence[StructurePoint],
) -> MarketState:
    """Classify one explicit segment from supplied chronological points."""

    _validate_segment_points(segment, points)
    high_relationships = _relationships_for_kind(points, StructurePointKind.HIGH)
    low_relationships = _relationships_for_kind(points, StructurePointKind.LOW)

    uptrend = _all_relationships_are(
        high_relationships,
        StructureRelationship.HIGHER_HIGH,
    ) and _all_relationships_are(
        low_relationships,
        StructureRelationship.HIGHER_LOW,
    )
    downtrend = _all_relationships_are(
        high_relationships,
        StructureRelationship.LOWER_HIGH,
    ) and _all_relationships_are(
        low_relationships,
        StructureRelationship.LOWER_LOW,
    )
    return _resolve_market_state(uptrend, downtrend)


def is_outside_bar(left: Candle, right: Candle) -> bool:
    """Return whether the right candle strictly contains the left range."""

    return right.high > left.high and right.low < left.low
