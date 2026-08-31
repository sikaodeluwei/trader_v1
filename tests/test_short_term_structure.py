from dataclasses import FrozenInstanceError

import pytest

from trading.definitions.isolated_point_deformations import (
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from trading.definitions.isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)
from trading.definitions.short_term_structure import (
    ShortTermPoint,
    ShortTermStructure,
    ShortTermSuppressionReason,
    SuppressedShortTermPoint,
    short_term_point_from_isolated_point,
    short_term_point_from_recognition,
)


def isolated_point(
    *,
    index: int = 3,
    kind: IsolatedPointKind = IsolatedPointKind.HIGH,
    status: IsolatedPointStatus = IsolatedPointStatus.CONFIRMED,
    price: float = 110.0,
) -> IsolatedPoint:
    return IsolatedPoint(index, kind, status, price)


def test_suppression_reason_values_are_stable() -> None:
    assert {reason.value for reason in ShortTermSuppressionReason} == {
        "consecutive_same_kind",
        "inside_structure",
    }


def test_short_term_records_preserve_values_and_are_frozen() -> None:
    point = ShortTermPoint(3, IsolatedPointKind.HIGH, 110.0, None)
    suppressed = SuppressedShortTermPoint(
        point,
        ShortTermSuppressionReason.CONSECUTIVE_SAME_KIND,
    )
    structure = ShortTermStructure((point,), (point,), (suppressed,))

    assert structure.points == (point,)
    assert structure.vertices == (point,)
    assert structure.suppressed == (suppressed,)
    with pytest.raises(FrozenInstanceError):
        point.price = 111.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kind", "price"),
    [
        (IsolatedPointKind.HIGH, 110.0),
        (IsolatedPointKind.LOW, 90.0),
    ],
)
def test_bare_confirmed_point_maps_without_recomputed_basis(
    kind: IsolatedPointKind,
    price: float,
) -> None:
    source = isolated_point(kind=kind, price=price)

    result = short_term_point_from_isolated_point(source)

    assert result == ShortTermPoint(
        index=source.index,
        kind=kind,
        price=price,
        recognition_basis=None,
    )


@pytest.mark.parametrize(
    "basis",
    [IsolatedPointBasis.STRICT, IsolatedPointBasis.RIGHT_INSIDE_BAR],
)
def test_recognition_mapping_preserves_exact_basis(
    basis: IsolatedPointBasis,
) -> None:
    source = isolated_point()
    recognition = IsolatedPointRecognition(source, basis)

    result = short_term_point_from_recognition(recognition)

    assert result == ShortTermPoint(
        source.index,
        source.kind,
        source.price,
        basis,
    )
    assert result.recognition_basis is basis


def test_bare_mapping_rejects_potential_point() -> None:
    with pytest.raises(ValueError, match="requires a confirmed isolated point"):
        short_term_point_from_isolated_point(
            isolated_point(status=IsolatedPointStatus.POTENTIAL)
        )


def test_recognition_mapping_rejects_wrapped_potential_point() -> None:
    recognition = IsolatedPointRecognition(
        isolated_point(status=IsolatedPointStatus.POTENTIAL),
        IsolatedPointBasis.RIGHT_INSIDE_BAR,
    )

    with pytest.raises(ValueError, match="requires a confirmed isolated point"):
        short_term_point_from_recognition(recognition)
