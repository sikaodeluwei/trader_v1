"""Basic support and resistance lines from confirmed isolated points."""

from dataclasses import dataclass
from enum import Enum

from .isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)


class KeyLevelKind(Enum):
    """The market role of a key price line."""

    RESISTANCE = "resistance"
    SUPPORT = "support"


@dataclass(frozen=True)
class KeyLevel:
    """A support or resistance line sourced from an isolated point."""

    kind: KeyLevelKind
    price: float
    source_index: int


def key_level_from_isolated_point(point: IsolatedPoint) -> KeyLevel:
    """Map a confirmed isolated point to its exact key-level line."""

    if point.status is not IsolatedPointStatus.CONFIRMED:
        raise ValueError("key levels require a confirmed isolated point")

    kind = (
        KeyLevelKind.RESISTANCE
        if point.kind is IsolatedPointKind.HIGH
        else KeyLevelKind.SUPPORT
    )
    return KeyLevel(
        kind=kind,
        price=point.price,
        source_index=point.index,
    )
