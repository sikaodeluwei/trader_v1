import pytest

from trading.definitions.candles import Candle
from trading.definitions.extremes import (
    ExtremeOrder,
    ExtremePath,
    ExtremePathEvidence,
    summarize_extreme_path,
)
from trading.definitions.movements import MovementSide, PriceLeg


def test_summarize_low_then_high_with_three_conceptual_moves() -> None:
    candle = Candle(open=100, high=110, low=99, close=101)
    path = ExtremePath(
        order=ExtremeOrder.LOW_THEN_HIGH,
        legs=[
            PriceLeg(MovementSide.SELLER, 100, 99, 1),
            PriceLeg(MovementSide.BUYER, 99, 110, 11),
            PriceLeg(MovementSide.SELLER, 110, 101, 9),
        ],
    )

    evidence = summarize_extreme_path(candle, path)

    assert evidence.order is ExtremeOrder.LOW_THEN_HIGH
    assert evidence.initial_side is MovementSide.SELLER
    assert evidence.initial_distance == 1
    assert evidence.initial_ratio == pytest.approx(1 / 11)
    assert evidence.main_side is MovementSide.BUYER
    assert evidence.main_distance == 11
    assert evidence.main_ratio == 1
    assert evidence.final_side is MovementSide.SELLER
    assert evidence.final_distance == 9
    assert evidence.final_ratio == pytest.approx(9 / 11)
    assert evidence.signed_displacement == 1
    assert evidence.displacement_ratio == pytest.approx(1 / 11)


def test_summarize_high_then_low_with_three_conceptual_moves() -> None:
    candle = Candle(open=109, high=110, low=90, close=108)
    path = ExtremePath(
        order=ExtremeOrder.HIGH_THEN_LOW,
        legs=[
            PriceLeg(MovementSide.BUYER, 109, 110, 1),
            PriceLeg(MovementSide.SELLER, 110, 90, 20),
            PriceLeg(MovementSide.BUYER, 90, 108, 18),
        ],
    )

    evidence = summarize_extreme_path(candle, path)

    assert evidence.order is ExtremeOrder.HIGH_THEN_LOW
    assert evidence.initial_side is MovementSide.BUYER
    assert evidence.initial_distance == 1
    assert evidence.initial_ratio == pytest.approx(1 / 20)
    assert evidence.main_side is MovementSide.SELLER
    assert evidence.main_distance == 20
    assert evidence.main_ratio == 1
    assert evidence.final_side is MovementSide.BUYER
    assert evidence.final_distance == 18
    assert evidence.final_ratio == pytest.approx(18 / 20)
    assert evidence.signed_displacement == -1
    assert evidence.displacement_ratio == pytest.approx(-1 / 20)


def test_summarize_extreme_path_when_open_equals_low() -> None:
    candle = Candle(open=100, high=110, low=100, close=105)
    path = ExtremePath(
        order=ExtremeOrder.LOW_THEN_HIGH,
        legs=[
            PriceLeg(MovementSide.BUYER, 100, 110, 10),
            PriceLeg(MovementSide.SELLER, 110, 105, 5),
        ],
    )

    evidence = summarize_extreme_path(candle, path)

    assert evidence.initial_side is None
    assert evidence.initial_distance == 0
    assert evidence.initial_ratio == 0
    assert evidence.main_side is MovementSide.BUYER
    assert evidence.main_distance == 10
    assert evidence.final_side is MovementSide.SELLER
    assert evidence.final_distance == 5


def test_summarize_extreme_path_when_open_equals_high() -> None:
    candle = Candle(open=110, high=110, low=90, close=100)
    path = ExtremePath(
        order=ExtremeOrder.HIGH_THEN_LOW,
        legs=[
            PriceLeg(MovementSide.SELLER, 110, 90, 20),
            PriceLeg(MovementSide.BUYER, 90, 100, 10),
        ],
    )

    evidence = summarize_extreme_path(candle, path)

    assert evidence.initial_side is None
    assert evidence.initial_distance == 0
    assert evidence.initial_ratio == 0
    assert evidence.main_side is MovementSide.SELLER
    assert evidence.main_distance == 20
    assert evidence.final_side is MovementSide.BUYER
    assert evidence.final_distance == 10


def test_summarize_extreme_path_when_close_equals_high() -> None:
    candle = Candle(open=100, high=110, low=90, close=110)
    path = ExtremePath(order=ExtremeOrder.LOW_THEN_HIGH, legs=[])

    evidence = summarize_extreme_path(candle, path)

    assert evidence.final_side is None
    assert evidence.final_distance == 0
    assert evidence.final_ratio == 0
    assert evidence.main_side is MovementSide.BUYER
    assert evidence.main_distance == 20


def test_summarize_extreme_path_when_close_equals_low() -> None:
    candle = Candle(open=100, high=110, low=90, close=90)
    path = ExtremePath(order=ExtremeOrder.HIGH_THEN_LOW, legs=[])

    evidence = summarize_extreme_path(candle, path)

    assert evidence.final_side is None
    assert evidence.final_distance == 0
    assert evidence.final_ratio == 0
    assert evidence.main_side is MovementSide.SELLER
    assert evidence.main_distance == 20


def test_summarize_extreme_path_when_close_equals_open() -> None:
    candle = Candle(open=100, high=110, low=90, close=100)
    path = ExtremePath(order=ExtremeOrder.LOW_THEN_HIGH, legs=[])

    evidence = summarize_extreme_path(candle, path)

    assert evidence.signed_displacement == 0
    assert evidence.displacement_ratio == 0
    assert evidence.initial_distance == 10
    assert evidence.main_distance == 20
    assert evidence.final_distance == 10


def test_summarize_flat_extreme_path_returns_zero_evidence() -> None:
    candle = Candle(open=100, high=100, low=100, close=100)
    path = ExtremePath(order=ExtremeOrder.FLAT, legs=[])

    assert summarize_extreme_path(candle, path) == ExtremePathEvidence(
        order=ExtremeOrder.FLAT,
        initial_side=None,
        initial_distance=0.0,
        initial_ratio=0.0,
        main_side=None,
        main_distance=0.0,
        main_ratio=0.0,
        final_side=None,
        final_distance=0.0,
        final_ratio=0.0,
        signed_displacement=0.0,
        displacement_ratio=0.0,
    )
