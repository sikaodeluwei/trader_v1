"""Explicit course-defined deformations of strict isolated points.

Inside-bar confirmation is the only automatically recognized deformation.
Context-dependent structures remain unresolved until later course material
defines market background; this module deliberately does not guess it.
"""

from dataclasses import dataclass
from enum import Enum

from .candles import Candle
from .isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
    confirm_isolated_point,
    get_potential_isolated_point,
)


class IsolatedPointBasis(Enum):
    """How an isolated point passed right-side confirmation."""

    STRICT = "strict"
    RIGHT_INSIDE_BAR = "right_inside_bar"


@dataclass(frozen=True)
class IsolatedPointRecognition:
    """A confirmed isolated point together with its recognition basis."""

    point: IsolatedPoint
    basis: IsolatedPointBasis


def is_inside_bar(outer: Candle, inner: Candle) -> bool:
    """Return whether one candle is geometrically contained by another."""

    return inner.high <= outer.high and inner.low >= outer.low


def confirm_isolated_point_with_deformation(
    point: IsolatedPoint,
    middle: Candle,
    right: Candle,
) -> IsolatedPointRecognition | None:
    """Confirm strictly first, then allow the right-inside-bar deformation."""

    strict_point = confirm_isolated_point(point, middle, right)
    if strict_point is not None:
        return IsolatedPointRecognition(
            point=strict_point,
            basis=IsolatedPointBasis.STRICT,
        )

    if not is_inside_bar(middle, right):
        return None

    price = (
        middle.high
        if point.kind is IsolatedPointKind.HIGH
        else middle.low
    )
    return IsolatedPointRecognition(
        point=IsolatedPoint(
            index=point.index,
            kind=point.kind,
            status=IsolatedPointStatus.CONFIRMED,
            price=price,
        ),
        basis=IsolatedPointBasis.RIGHT_INSIDE_BAR,
    )


def replace_with_more_extreme_point(
    existing: IsolatedPoint,
    new_point: IsolatedPoint,
) -> IsolatedPoint:
    """Select a newer point only when it is more extreme in the same kind."""

    if existing.kind is not new_point.kind:
        raise ValueError("isolated point replacement requires the same kind")

    if existing.kind is IsolatedPointKind.HIGH:
        return new_point if new_point.price > existing.price else existing
    return new_point if new_point.price < existing.price else existing


class DeformationAwareIsolatedPointTracker:
    """Incrementally confirm strict and right-inside-bar isolated points."""

    def __init__(self) -> None:
        self._previous_candle: Candle | None = None
        self._pending_point: IsolatedPoint | None = None
        self._next_index = 0

    def add_candle(
        self,
        candle: Candle,
    ) -> list[IsolatedPoint | IsolatedPointRecognition]:
        """Return raw potentials and basis-carrying confirmed recognitions."""

        index = self._next_index
        self._next_index += 1

        if self._previous_candle is None:
            self._previous_candle = candle
            return []

        changes: list[IsolatedPoint | IsolatedPointRecognition] = []
        if self._pending_point is not None:
            recognition = confirm_isolated_point_with_deformation(
                self._pending_point,
                self._previous_candle,
                candle,
            )
            if recognition is not None:
                changes.append(recognition)

        self._pending_point = get_potential_isolated_point(
            self._previous_candle,
            candle,
            index,
        )
        if self._pending_point is not None:
            changes.append(self._pending_point)

        self._previous_candle = candle
        return changes
