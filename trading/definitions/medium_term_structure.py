"""Canonical Chapter 2 medium-term structure from cleaned short-term vertices."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .isolated_points import IsolatedPointKind
from .short_term_structure import ShortTermPoint, ShortTermStructure


class MediumTermSuppressionReason(Enum):
    """Why a confirmed medium point is omitted from the medium line."""

    CONSECUTIVE_SAME_KIND = "consecutive_same_kind"
    INSIDE_STRUCTURE = "inside_structure"


class CourseRuleMatch(Enum):
    """Externally supplied diagnostic match to the course break method."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MediumTermPoint:
    """A canonical medium pivot and when its right evidence existed."""

    pivot: ShortTermPoint
    confirmation_index: int

    def __post_init__(self) -> None:
        if self.confirmation_index <= self.pivot.index:
            raise ValueError("confirmation_index must be after pivot index")

    @property
    def pivot_index(self) -> int:
        return self.pivot.index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


def _is_strictly_more_extreme(candidate: ShortTermPoint, previous: ShortTermPoint) -> bool:
    if candidate.kind is IsolatedPointKind.HIGH:
        return candidate.price > previous.price
    return candidate.price < previous.price


@dataclass(frozen=True)
class PotentialMediumTermPoint:
    """A right-edge pivot that passes its available left comparison."""

    previous_same_kind: ShortTermPoint
    pivot: ShortTermPoint

    def __post_init__(self) -> None:
        if self.previous_same_kind.kind is not self.pivot.kind:
            raise ValueError("potential medium points require same-kind source points")
        if self.pivot.index <= self.previous_same_kind.index:
            raise ValueError("potential medium point indexes must be chronological")
        if not _is_strictly_more_extreme(self.pivot, self.previous_same_kind):
            raise ValueError("potential medium point must be more extreme than previous same-kind point")

    @property
    def pivot_index(self) -> int:
        return self.pivot.index

    @property
    def kind(self) -> IsolatedPointKind:
        return self.pivot.kind

    @property
    def price(self) -> float:
        return self.pivot.price


@dataclass(frozen=True)
class SuppressedMediumTermPoint:
    """A confirmed medium point omitted only from normalized vertices."""

    point: MediumTermPoint
    reason: MediumTermSuppressionReason


@dataclass(frozen=True)
class MediumCourseEvidence:
    """Externally supplied evidence that cannot decide canonical output."""

    point: MediumTermPoint
    course_rule_match: CourseRuleMatch


@dataclass(frozen=True)
class MediumTermStructure:
    """Canonical points, edge potentials, vertices, and retained evidence."""

    points: tuple[MediumTermPoint, ...]
    potentials: tuple[PotentialMediumTermPoint, ...]
    vertices: tuple[MediumTermPoint, ...]
    suppressed: tuple[SuppressedMediumTermPoint, ...]
    course_evidence: tuple[MediumCourseEvidence, ...] = ()


def attach_course_evidence(
    structure: MediumTermStructure,
    evidence: Sequence[MediumCourseEvidence],
) -> MediumTermStructure:
    """Attach external diagnostic evidence without changing canonical output."""

    evidence_tuple = tuple(evidence)
    if any(item.point not in structure.points for item in evidence_tuple):
        raise ValueError("course evidence requires a confirmed medium point")
    return MediumTermStructure(
        points=structure.points,
        potentials=structure.potentials,
        vertices=structure.vertices,
        suppressed=structure.suppressed,
        course_evidence=evidence_tuple,
    )


def _validate_short_term_source(source: ShortTermStructure) -> None:
    for previous, current in zip(source.vertices, source.vertices[1:]):
        if current.index <= previous.index:
            raise ValueError("cleaned short-term vertex indexes must be strictly increasing")

    if any(vertex not in source.points for vertex in source.vertices):
        raise ValueError("cleaned short-term vertices must come from structure points")

    if any(item.point in source.vertices for item in source.suppressed):
        raise ValueError("suppressed short-term points must not be medium-recognition vertices")


def _is_strict_medium_pivot(
    previous: ShortTermPoint,
    pivot: ShortTermPoint,
    later: ShortTermPoint,
) -> bool:
    if pivot.kind is IsolatedPointKind.HIGH:
        return previous.price < pivot.price > later.price
    return previous.price > pivot.price < later.price


def _recognize_kind(
    vertices: tuple[ShortTermPoint, ...],
    kind: IsolatedPointKind,
) -> tuple[list[MediumTermPoint], PotentialMediumTermPoint | None]:
    same_kind = tuple(point for point in vertices if point.kind is kind)
    confirmed = [
        MediumTermPoint(pivot, later.index)
        for previous, pivot, later in zip(
            same_kind,
            same_kind[1:],
            same_kind[2:],
        )
        if _is_strict_medium_pivot(previous, pivot, later)
    ]

    potential: PotentialMediumTermPoint | None = None
    if len(same_kind) >= 2:
        previous, pivot = same_kind[-2:]
        if _is_strictly_more_extreme(pivot, previous):
            potential = PotentialMediumTermPoint(previous, pivot)
    return confirmed, potential


def _recognize_medium_points(
    vertices: tuple[ShortTermPoint, ...],
) -> tuple[tuple[MediumTermPoint, ...], tuple[PotentialMediumTermPoint, ...]]:
    high_points, high_potential = _recognize_kind(vertices, IsolatedPointKind.HIGH)
    low_points, low_potential = _recognize_kind(vertices, IsolatedPointKind.LOW)

    point_by_index = {point.pivot_index: point for point in high_points + low_points}
    points = tuple(
        point_by_index[vertex.index]
        for vertex in vertices
        if vertex.index in point_by_index
    )

    potential_by_index = {
        potential.pivot_index: potential
        for potential in (high_potential, low_potential)
        if potential is not None
    }
    potentials = tuple(
        potential_by_index[vertex.index]
        for vertex in vertices
        if vertex.index in potential_by_index
    )
    return points, potentials


def _is_more_extreme_medium(
    candidate: MediumTermPoint,
    current: MediumTermPoint,
) -> bool:
    if current.kind is IsolatedPointKind.HIGH:
        return candidate.price > current.price
    return candidate.price < current.price


def _normalize_same_kind_runs(
    points: tuple[MediumTermPoint, ...],
) -> tuple[
    list[MediumTermPoint],
    list[SuppressedMediumTermPoint],
]:
    vertices: list[MediumTermPoint] = []
    suppressed: list[SuppressedMediumTermPoint] = []
    run: list[MediumTermPoint] = []

    def flush_run() -> None:
        if not run:
            return
        winner = run[0]
        for candidate in run[1:]:
            if _is_more_extreme_medium(candidate, winner):
                winner = candidate
        vertices.append(winner)
        suppressed.extend(
            SuppressedMediumTermPoint(
                point,
                MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND,
            )
            for point in run
            if point is not winner
        )

    for point in points:
        if run and point.kind is not run[-1].kind:
            flush_run()
            run = []
        run.append(point)
    flush_run()
    return vertices, suppressed


def _pair_bounds(
    first: MediumTermPoint,
    second: MediumTermPoint,
) -> tuple[float, float] | None:
    if first.kind is second.kind:
        return None
    high = first if first.kind is IsolatedPointKind.HIGH else second
    low = first if first.kind is IsolatedPointKind.LOW else second
    return high.price, low.price


def _later_pair_is_inside(
    earlier: tuple[MediumTermPoint, MediumTermPoint],
    later: tuple[MediumTermPoint, MediumTermPoint],
) -> bool:
    earlier_bounds = _pair_bounds(*earlier)
    later_bounds = _pair_bounds(*later)
    if earlier_bounds is None or later_bounds is None:
        return False
    earlier_high, earlier_low = earlier_bounds
    later_high, later_low = later_bounds
    return later_high <= earlier_high and later_low >= earlier_low


def _normalize_inside_structures(
    vertices: list[MediumTermPoint],
) -> tuple[
    list[MediumTermPoint],
    list[SuppressedMediumTermPoint],
]:
    normalized = list(vertices)
    suppressed: list[SuppressedMediumTermPoint] = []
    changed = True

    while changed:
        changed = False
        pair_start = 0
        while pair_start + 3 < len(normalized):
            earlier = (
                normalized[pair_start],
                normalized[pair_start + 1],
            )
            later = (
                normalized[pair_start + 2],
                normalized[pair_start + 3],
            )
            if not _later_pair_is_inside(earlier, later):
                pair_start += 2
                continue

            removed = normalized[pair_start + 2 : pair_start + 4]
            del normalized[pair_start + 2 : pair_start + 4]
            suppressed.extend(
                SuppressedMediumTermPoint(
                    point,
                    MediumTermSuppressionReason.INSIDE_STRUCTURE,
                )
                for point in removed
            )
            changed = True

    return normalized, suppressed


def build_medium_term_structure(source: ShortTermStructure) -> MediumTermStructure:
    """Build canonical medium structure from cleaned short-term vertices."""

    _validate_short_term_source(source)
    points, potentials = _recognize_medium_points(source.vertices)
    same_kind_vertices, same_kind_suppressed = _normalize_same_kind_runs(points)
    vertices, inside_suppressed = _normalize_inside_structures(same_kind_vertices)
    return MediumTermStructure(
        points=points,
        potentials=potentials,
        vertices=tuple(vertices),
        suppressed=tuple(same_kind_suppressed + inside_suppressed),
        course_evidence=(),
    )
