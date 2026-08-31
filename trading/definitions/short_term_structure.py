"""Course-defined Chapter 2 short-term structure normalization."""

from dataclasses import dataclass
from enum import Enum

from .isolated_point_deformations import (
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from .isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)


class ShortTermSuppressionReason(Enum):
    """Why a valid short-term point is omitted from the line."""

    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


@dataclass(frozen=True)
class ShortTermPoint:
    """One confirmed isolated point represented at short-term level."""

    index: int
    kind: IsolatedPointKind
    price: float
    recognition_basis: IsolatedPointBasis | None = None


@dataclass(frozen=True)
class SuppressedShortTermPoint:
    """A valid point omitted only from normalized line vertices."""

    point: ShortTermPoint
    reason: ShortTermSuppressionReason


@dataclass(frozen=True)
class ShortTermStructure:
    """All valid points, normalized vertices, and suppression evidence."""

    points: tuple[ShortTermPoint, ...]
    vertices: tuple[ShortTermPoint, ...]
    suppressed: tuple[SuppressedShortTermPoint, ...]


def _require_confirmed(point: IsolatedPoint) -> None:
    if point.status is not IsolatedPointStatus.CONFIRMED:
        raise ValueError(
            "short-term point mapping requires a confirmed isolated point"
        )


def short_term_point_from_isolated_point(
    point: IsolatedPoint,
) -> ShortTermPoint:
    """Map a bare confirmed point without recomputing recognition basis."""

    _require_confirmed(point)
    return ShortTermPoint(point.index, point.kind, point.price, None)


def short_term_point_from_recognition(
    recognition: IsolatedPointRecognition,
) -> ShortTermPoint:
    """Map a basis-carrying confirmed recognition exactly."""

    _require_confirmed(recognition.point)
    return ShortTermPoint(
        recognition.point.index,
        recognition.point.kind,
        recognition.point.price,
        recognition.basis,
    )
