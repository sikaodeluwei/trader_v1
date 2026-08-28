from importlib import import_module

import pytest

from trading.definitions.isolated_points import (
    IsolatedPoint,
    IsolatedPointKind,
    IsolatedPointStatus,
)
from trading.definitions.key_levels import KeyLevel, KeyLevelKind


def confirmed_point(
    index: int,
    kind: IsolatedPointKind,
    price: float,
) -> IsolatedPoint:
    return IsolatedPoint(
        index=index,
        kind=kind,
        status=IsolatedPointStatus.CONFIRMED,
        price=price,
    )


@pytest.mark.parametrize(
    ("existing", "new_point", "should_replace"),
    [
        (
            KeyLevel(KeyLevelKind.RESISTANCE, 100.0, 1),
            confirmed_point(5, IsolatedPointKind.HIGH, 110.0),
            True,
        ),
        (
            KeyLevel(KeyLevelKind.RESISTANCE, 100.0, 1),
            confirmed_point(5, IsolatedPointKind.HIGH, 99.0),
            False,
        ),
        (
            KeyLevel(KeyLevelKind.SUPPORT, 90.0, 1),
            confirmed_point(5, IsolatedPointKind.LOW, 80.0),
            True,
        ),
        (
            KeyLevel(KeyLevelKind.SUPPORT, 90.0, 1),
            confirmed_point(5, IsolatedPointKind.LOW, 91.0),
            False,
        ),
    ],
)
def test_key_level_replacement_uses_only_more_extreme_confirmed_point(
    existing: KeyLevel,
    new_point: IsolatedPoint,
    should_replace: bool,
) -> None:
    key_levels = import_module("trading.definitions.key_levels")

    result = key_levels.replace_key_level_from_isolated_point(
        existing,
        new_point,
    )

    if should_replace:
        assert result == KeyLevel(
            kind=existing.kind,
            price=new_point.price,
            source_index=new_point.index,
        )
    else:
        assert result is existing


def test_key_level_replacement_rejects_wrong_point_kind() -> None:
    key_levels = import_module("trading.definitions.key_levels")
    resistance = KeyLevel(KeyLevelKind.RESISTANCE, 100.0, 1)
    low = confirmed_point(5, IsolatedPointKind.LOW, 80.0)

    with pytest.raises(ValueError, match="kind"):
        key_levels.replace_key_level_from_isolated_point(resistance, low)


def test_key_level_replacement_rejects_potential_point() -> None:
    key_levels = import_module("trading.definitions.key_levels")
    resistance = KeyLevel(KeyLevelKind.RESISTANCE, 100.0, 1)
    potential = IsolatedPoint(
        index=5,
        kind=IsolatedPointKind.HIGH,
        status=IsolatedPointStatus.POTENTIAL,
        price=110.0,
    )

    with pytest.raises(ValueError, match="confirmed"):
        key_levels.replace_key_level_from_isolated_point(
            resistance,
            potential,
        )
