"""Pure composition of confirmed isolated recognitions into structures."""

from dataclasses import dataclass

from trading.analysis.isolated import IsolatedPointScan
from trading.definitions.long_term_structure import (
    LongTermStructure,
    build_long_term_structure,
)
from trading.definitions.medium_term_structure import (
    MediumTermStructure,
    build_medium_term_structure,
)
from trading.definitions.short_term_structure import (
    ShortTermStructure,
    build_short_term_structure,
    short_term_point_from_recognition,
)


@dataclass(frozen=True)
class StructuralHierarchy:
    """The isolated scan and its composed structural levels."""

    isolated: IsolatedPointScan
    short_term: ShortTermStructure
    medium_term: MediumTermStructure
    long_term: LongTermStructure


def build_structural_hierarchy(
    isolated: IsolatedPointScan,
) -> StructuralHierarchy:
    """Build all structural levels from confirmed isolated recognitions."""

    short_points = tuple(
        short_term_point_from_recognition(item)
        for item in isolated.recognitions
    )
    short_term = build_short_term_structure(short_points)
    medium_term = build_medium_term_structure(short_term)
    long_term = build_long_term_structure(medium_term)
    return StructuralHierarchy(isolated, short_term, medium_term, long_term)
