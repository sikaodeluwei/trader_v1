"""Course-defined Chapter 2 short-term structure normalization."""

from dataclasses import dataclass
from enum import Enum
from collections.abc import Sequence

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


def _validate_chronology(points: Sequence[ShortTermPoint]) -> None:
    for previous, current in zip(points, points[1:]):
        if current.index <= previous.index:
            raise ValueError(
                "short-term point indexes must be strictly increasing"
            )


def _is_more_extreme(
    candidate: ShortTermPoint,
    current: ShortTermPoint,
) -> bool:
    if current.kind is IsolatedPointKind.HIGH:
        return candidate.price > current.price
    return candidate.price < current.price


def _normalize_same_kind_runs(
    points: tuple[ShortTermPoint, ...],
) -> tuple[
    list[ShortTermPoint],
    list[SuppressedShortTermPoint],
]:
    vertices: list[ShortTermPoint] = []
    suppressed: list[SuppressedShortTermPoint] = []
    run: list[ShortTermPoint] = []

    def flush_run() -> None:
        if not run:
            return
        winner = run[0]
        for candidate in run[1:]:
            if _is_more_extreme(candidate, winner):
                winner = candidate
        vertices.append(winner)
        suppressed.extend(
            SuppressedShortTermPoint(
                point,
                ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
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
    first: ShortTermPoint,
    second: ShortTermPoint,
) -> tuple[float, float] | None:
    if first.kind is second.kind:
        return None
    high = first if first.kind is IsolatedPointKind.HIGH else second
    low = first if first.kind is IsolatedPointKind.LOW else second
    return high.price, low.price


def _later_pair_is_inside(
    earlier: tuple[ShortTermPoint, ShortTermPoint],
    later: tuple[ShortTermPoint, ShortTermPoint],
) -> bool:
    earlier_bounds = _pair_bounds(*earlier)
    later_bounds = _pair_bounds(*later)
    if earlier_bounds is None or later_bounds is None:
        return False
    earlier_high, earlier_low = earlier_bounds
    later_high, later_low = later_bounds
    return later_high <= earlier_high and later_low >= earlier_low


def _normalize_inside_structures(
    vertices: list[ShortTermPoint],
) -> tuple[
    list[ShortTermPoint],
    list[SuppressedShortTermPoint],
]:
    normalized = list(vertices)
    suppressed: list[SuppressedShortTermPoint] = []
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
                SuppressedShortTermPoint(
                    point,
                    ShortTermSuppressionReason.INSIDE_STRUCTURE,
                )
                for point in removed
            )
            changed = True

    return normalized, suppressed


def build_short_term_structure(
    points: Sequence[ShortTermPoint],
) -> ShortTermStructure:
    """Normalize confirmed short-term points without losing evidence."""

    all_points = tuple(points)
    _validate_chronology(all_points)
    same_kind_vertices, same_kind_suppressed = _normalize_same_kind_runs(
        all_points
    )
    vertices, inside_suppressed = _normalize_inside_structures(
        same_kind_vertices
    )
    return ShortTermStructure(
        points=all_points,
        vertices=tuple(vertices),
        suppressed=tuple(same_kind_suppressed + inside_suppressed),
    )


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
