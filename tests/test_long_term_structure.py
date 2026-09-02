from importlib import import_module, util
from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_points import IsolatedPointKind
from trading.definitions.long_term_structure import (
    LongCourseEvidence,
    LongTermPoint,
    LongTermStructure,
    LongTermSuppressionReason,
    PotentialLongTermPoint,
    SuppressedLongTermPoint,
    build_long_term_structure,
)
from trading.definitions.medium_term_structure import (
    CourseRuleMatch,
    MediumTermPoint,
    MediumTermStructure,
    MediumTermSuppressionReason,
    SuppressedMediumTermPoint,
)
from trading.definitions.short_term_structure import ShortTermPoint


def test_long_term_module_exists() -> None:
    assert (
        util.find_spec("trading.definitions.long_term_structure")
        is not None
    )


def test_locked_long_term_api_is_exposed() -> None:
    module = import_module("trading.definitions.long_term_structure")
    expected_names = {
        "LongTermSuppressionReason",
        "LongTermPoint",
        "PotentialLongTermPoint",
        "SuppressedLongTermPoint",
        "LongCourseEvidence",
        "LongTermStructure",
        "build_long_term_structure",
        "attach_course_evidence",
    }

    missing = sorted(
        name for name in expected_names if not hasattr(module, name)
    )

    assert missing == []


def medium_point(
    pivot_index: int,
    kind: IsolatedPointKind,
    price: float,
    *,
    confirmed_by_index: int | None = None,
) -> MediumTermPoint:
    confirmer_index = (
        pivot_index + 1
        if confirmed_by_index is None
        else confirmed_by_index
    )
    return MediumTermPoint(
        ShortTermPoint(pivot_index, kind, price, None),
        ShortTermPoint(confirmer_index, kind, price, None),
    )


def medium_structure(
    vertices: list[MediumTermPoint] | tuple[MediumTermPoint, ...],
    *,
    points: list[MediumTermPoint] | tuple[MediumTermPoint, ...] | None = None,
    suppressed: tuple[SuppressedMediumTermPoint, ...] = (),
) -> MediumTermStructure:
    vertex_tuple = tuple(vertices)
    return MediumTermStructure(
        points=vertex_tuple if points is None else tuple(points),
        potentials=(),
        vertices=vertex_tuple,
        suppressed=suppressed,
        course_evidence=(),
    )


def test_long_term_domain_values_are_stable_and_frozen() -> None:
    pivot = medium_point(30, IsolatedPointKind.HIGH, 120.0)
    confirmed_by = medium_point(50, IsolatedPointKind.HIGH, 115.0)
    point = LongTermPoint(pivot, confirmed_by)
    potential = PotentialLongTermPoint(
        medium_point(10, IsolatedPointKind.HIGH, 110.0),
        pivot,
    )
    suppressed = SuppressedLongTermPoint(
        point,
        LongTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    evidence = LongCourseEvidence(point, CourseRuleMatch.UNKNOWN)
    structure = LongTermStructure(
        points=(point,),
        potentials=(potential,),
        vertices=(point,),
        suppressed=(suppressed,),
        course_evidence=(evidence,),
    )

    assert {reason.value for reason in LongTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }
    assert point.pivot is pivot
    assert point.confirmed_by is confirmed_by
    assert point.pivot_index == 30
    assert point.confirmed_by_index == 50
    assert point.kind is IsolatedPointKind.HIGH
    assert point.price == 120.0
    assert not hasattr(point, "known_at_index")
    assert not hasattr(point, "confirmed_at_index")
    assert structure.course_evidence == (evidence,)
    with pytest.raises(FrozenInstanceError):
        point.confirmed_by = pivot  # type: ignore[misc]


def test_confirmed_long_point_requires_same_kind_sources() -> None:
    with pytest.raises(ValueError, match="same-kind pivot and confirmed_by"):
        LongTermPoint(
            medium_point(30, IsolatedPointKind.HIGH, 120.0),
            medium_point(50, IsolatedPointKind.LOW, 90.0),
        )


@pytest.mark.parametrize("confirmed_by_index", [20, 30])
def test_confirmed_long_point_requires_later_source(confirmed_by_index: int) -> None:
    with pytest.raises(ValueError, match="confirmed_by pivot index must be after pivot index"):
        LongTermPoint(
            medium_point(30, IsolatedPointKind.HIGH, 120.0),
            medium_point(confirmed_by_index, IsolatedPointKind.HIGH, 115.0),
        )


def test_potential_long_point_validates_kind_chronology_and_extremity() -> None:
    previous_high = medium_point(10, IsolatedPointKind.HIGH, 110.0)
    with pytest.raises(ValueError, match="same-kind source points"):
        PotentialLongTermPoint(previous_high, medium_point(30, IsolatedPointKind.LOW, 90.0))
    with pytest.raises(ValueError, match="indexes must be chronological"):
        PotentialLongTermPoint(previous_high, medium_point(5, IsolatedPointKind.HIGH, 120.0))
    with pytest.raises(ValueError, match="must be more extreme"):
        PotentialLongTermPoint(previous_high, medium_point(30, IsolatedPointKind.HIGH, 110.0))


@pytest.mark.parametrize("vertices", [
    [medium_point(20, IsolatedPointKind.HIGH, 110.0), medium_point(10, IsolatedPointKind.LOW, 90.0)],
    [medium_point(10, IsolatedPointKind.HIGH, 110.0), medium_point(10, IsolatedPointKind.LOW, 90.0)],
])
def test_source_rejects_non_increasing_pivot_indexes(vertices: list[MediumTermPoint]) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_long_term_structure(medium_structure(vertices))


def test_complete_source_chronology_is_validated_before_output() -> None:
    vertices = [medium_point(10, IsolatedPointKind.HIGH, 105.0), medium_point(40, IsolatedPointKind.HIGH, 112.0), medium_point(30, IsolatedPointKind.HIGH, 108.0)]
    with pytest.raises(ValueError, match="strictly increasing"):
        build_long_term_structure(medium_structure(vertices))


def test_source_vertices_must_belong_to_medium_points() -> None:
    vertex = medium_point(30, IsolatedPointKind.HIGH, 112.0)
    with pytest.raises(ValueError, match="must come from structure points"):
        build_long_term_structure(medium_structure([vertex], points=[]))


def test_suppressed_medium_point_cannot_be_a_long_source_vertex() -> None:
    vertex = medium_point(30, IsolatedPointKind.HIGH, 112.0)
    suppression = SuppressedMediumTermPoint(vertex, MediumTermSuppressionReason.CONSECUTIVE_SAME_KIND)
    with pytest.raises(ValueError, match="must not be long-term recognition vertices"):
        build_long_term_structure(medium_structure([vertex], suppressed=(suppression,)))


def test_empty_and_one_vertex_sources_are_neutral() -> None:
    empty = build_long_term_structure(medium_structure([]))
    one = build_long_term_structure(medium_structure([medium_point(10, IsolatedPointKind.HIGH, 105.0)]))
    assert empty == LongTermStructure((), (), (), (), ())
    assert one == LongTermStructure((), (), (), (), ())
