"""Canonical Chapter 2 long-term structure from cleaned medium vertices."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .isolated_points import IsolatedPointKind
from .medium_term_structure import CourseRuleMatch, MediumTermPoint, MediumTermStructure


class LongTermSuppressionReason(Enum):
    """Why a confirmed long point is omitted from the long line."""
    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


@dataclass(frozen=True)
class LongTermPoint:
    """A canonical long pivot and its structural right-side confirmer."""
    pivot: MediumTermPoint
    confirmed_by: MediumTermPoint

    def __post_init__(self) -> None:
        if self.pivot.kind is not self.confirmed_by.kind:
            raise ValueError("confirmed long-term points require same-kind pivot and confirmed_by points")
        if self.confirmed_by.pivot_index <= self.pivot.pivot_index:
            raise ValueError("confirmed_by pivot index must be after pivot index")

    @property
    def pivot_index(self) -> int:
        return self.pivot.pivot_index

    @property
    def confirmed_by_index(self) -> int:
        """Return structural source location, not knowability time."""
        return self.confirmed_by.pivot_index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


def _is_strictly_more_extreme(candidate: MediumTermPoint, previous: MediumTermPoint) -> bool:
    if candidate.kind is IsolatedPointKind.HIGH:
        return candidate.price > previous.price
    return candidate.price < previous.price


@dataclass(frozen=True)
class PotentialLongTermPoint:
    """A right-edge pivot that passes its available left comparison."""
    previous_same_kind: MediumTermPoint
    pivot: MediumTermPoint

    def __post_init__(self) -> None:
        if self.previous_same_kind.kind is not self.pivot.kind:
            raise ValueError("potential long-term points require same-kind source points")
        if self.pivot.pivot_index <= self.previous_same_kind.pivot_index:
            raise ValueError("potential long-term point indexes must be chronological")
        if not _is_strictly_more_extreme(self.pivot, self.previous_same_kind):
            raise ValueError("potential long-term point must be more extreme than previous same-kind point")

    @property
    def pivot_index(self) -> int:
        return self.pivot.pivot_index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


@dataclass(frozen=True)
class SuppressedLongTermPoint:
    """A confirmed long point omitted only from normalized vertices."""
    point: LongTermPoint
    reason: LongTermSuppressionReason


@dataclass(frozen=True)
class LongCourseEvidence:
    """Externally supplied evidence that cannot decide canonical output."""
    point: LongTermPoint
    course_rule_match: CourseRuleMatch


@dataclass(frozen=True)
class LongTermStructure:
    """Canonical points, edge potentials, vertices, and retained evidence."""
    points: tuple[LongTermPoint, ...]
    potentials: tuple[PotentialLongTermPoint, ...]
    vertices: tuple[LongTermPoint, ...]
    suppressed: tuple[SuppressedLongTermPoint, ...]
    course_evidence: tuple[LongCourseEvidence, ...] = ()


def attach_course_evidence(structure: LongTermStructure, evidence: Sequence[LongCourseEvidence]) -> LongTermStructure:
    """Remain intentionally unimplemented until Task 6's behavioral RED."""
    raise NotImplementedError("course evidence attachment is not implemented")


def _validate_medium_term_source(source: MediumTermStructure) -> None:
    for previous, current in zip(source.vertices, source.vertices[1:]):
        if current.pivot_index <= previous.pivot_index:
            raise ValueError("cleaned medium vertex pivot indexes must be strictly increasing")
    if any(vertex not in source.points for vertex in source.vertices):
        raise ValueError("cleaned medium vertices must come from structure points")
    if any(item.point in source.vertices for item in source.suppressed):
        raise ValueError("suppressed medium points must not be long-term recognition vertices")


def _is_strict_long_pivot(
    previous: MediumTermPoint,
    pivot: MediumTermPoint,
    later: MediumTermPoint,
) -> bool:
    if pivot.kind is IsolatedPointKind.HIGH:
        return previous.price < pivot.price > later.price
    return previous.price > pivot.price < later.price


def _recognize_kind(
    vertices: tuple[MediumTermPoint, ...],
    kind: IsolatedPointKind,
) -> tuple[list[LongTermPoint], PotentialLongTermPoint | None]:
    same_kind = tuple(point for point in vertices if point.kind is kind)
    confirmed = [
        LongTermPoint(pivot, later)
        for previous, pivot, later in zip(
            same_kind,
            same_kind[1:],
            same_kind[2:],
        )
        if _is_strict_long_pivot(previous, pivot, later)
    ]

    potential: PotentialLongTermPoint | None = None
    if len(same_kind) >= 2:
        previous, pivot = same_kind[-2:]
        if _is_strictly_more_extreme(pivot, previous):
            potential = PotentialLongTermPoint(previous, pivot)
    return confirmed, potential


def _recognize_long_points(
    vertices: tuple[MediumTermPoint, ...],
) -> tuple[tuple[LongTermPoint, ...], tuple[PotentialLongTermPoint, ...]]:
    high_points, high_potential = _recognize_kind(
        vertices,
        IsolatedPointKind.HIGH,
    )
    low_points, low_potential = _recognize_kind(
        vertices,
        IsolatedPointKind.LOW,
    )
    point_by_index = {
        point.pivot_index: point for point in high_points + low_points
    }
    points = tuple(
        point_by_index[vertex.pivot_index]
        for vertex in vertices
        if vertex.pivot_index in point_by_index
    )

    potential_by_index = {
        potential.pivot_index: potential
        for potential in (high_potential, low_potential)
        if potential is not None
    }
    potentials = tuple(
        potential_by_index[vertex.pivot_index]
        for vertex in vertices
        if vertex.pivot_index in potential_by_index
    )
    return points, potentials


def build_long_term_structure(source: MediumTermStructure) -> LongTermStructure:
    """Build canonical long structure from cleaned medium vertices."""
    _validate_medium_term_source(source)
    points, potentials = _recognize_long_points(source.vertices)
    return LongTermStructure(
        points=points,
        potentials=potentials,
        vertices=points,
        suppressed=(),
        course_evidence=(),
    )
