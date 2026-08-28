"""Explicit, segment-relative Chapter 2 market-structure definitions."""

from dataclasses import dataclass
from enum import Enum


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
