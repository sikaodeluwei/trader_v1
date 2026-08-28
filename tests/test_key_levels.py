from importlib import import_module
from types import ModuleType

import pytest


def load_isolated_points() -> ModuleType:
    return import_module("trading.definitions.isolated_points")


def load_key_levels() -> ModuleType:
    return import_module("trading.definitions.key_levels")


@pytest.mark.parametrize(
    ("point_kind", "price", "expected_level_kind"),
    [
        ("high", 112.75, "resistance"),
        ("low", 91.25, "support"),
    ],
)
def test_confirmed_isolated_point_becomes_exact_key_level_line(
    point_kind: str,
    price: float,
    expected_level_kind: str,
) -> None:
    isolated_points = load_isolated_points()
    key_levels = load_key_levels()
    point = isolated_points.IsolatedPoint(
        index=7,
        kind=isolated_points.IsolatedPointKind(point_kind),
        status=isolated_points.IsolatedPointStatus.CONFIRMED,
        price=price,
    )

    level = key_levels.key_level_from_isolated_point(point)

    assert level == key_levels.KeyLevel(
        kind=key_levels.KeyLevelKind(expected_level_kind),
        price=price,
        source_index=7,
    )


def test_potential_isolated_point_cannot_create_key_level() -> None:
    isolated_points = load_isolated_points()
    key_levels = load_key_levels()
    point = isolated_points.IsolatedPoint(
        index=3,
        kind=isolated_points.IsolatedPointKind.HIGH,
        status=isolated_points.IsolatedPointStatus.POTENTIAL,
        price=105.0,
    )

    with pytest.raises(ValueError, match="confirmed"):
        key_levels.key_level_from_isolated_point(point)
