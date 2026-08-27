import pytest

from trading.definitions.movements import (
    MovementSide,
    MovementSummary,
    PriceLeg,
    summarize_movements,
)


def test_summarize_movements_returns_neutral_empty_summary() -> None:
    assert summarize_movements([]) == MovementSummary(
        first_side=None,
        first_distance=0.0,
        final_side=None,
        final_distance=0.0,
        largest_buyer_move=0.0,
        largest_seller_move=0.0,
        total_buyer_movement=0.0,
        total_seller_movement=0.0,
        final_retracement_ratio=None,
    )


def test_summarize_movements_handles_one_buyer_leg() -> None:
    summary = summarize_movements(
        [PriceLeg(MovementSide.BUYER, 100, 110, 10)]
    )

    assert summary == MovementSummary(
        first_side=MovementSide.BUYER,
        first_distance=10,
        final_side=MovementSide.BUYER,
        final_distance=10,
        largest_buyer_move=10,
        largest_seller_move=0.0,
        total_buyer_movement=10,
        total_seller_movement=0.0,
        final_retracement_ratio=None,
    )


def test_summarize_movements_handles_one_seller_leg() -> None:
    summary = summarize_movements(
        [PriceLeg(MovementSide.SELLER, 110, 100, 10)]
    )

    assert summary == MovementSummary(
        first_side=MovementSide.SELLER,
        first_distance=10,
        final_side=MovementSide.SELLER,
        final_distance=10,
        largest_buyer_move=0.0,
        largest_seller_move=10,
        total_buyer_movement=0.0,
        total_seller_movement=10,
        final_retracement_ratio=None,
    )


def test_summarize_movements_handles_seller_buyer_seller() -> None:
    summary = summarize_movements(
        [
            PriceLeg(MovementSide.SELLER, 100, 99, 1),
            PriceLeg(MovementSide.BUYER, 99, 110, 11),
            PriceLeg(MovementSide.SELLER, 110, 101, 9),
        ]
    )

    assert summary.first_side is MovementSide.SELLER
    assert summary.first_distance == 1
    assert summary.final_side is MovementSide.SELLER
    assert summary.final_distance == 9
    assert summary.largest_buyer_move == 11
    assert summary.largest_seller_move == 9
    assert summary.total_buyer_movement == 11
    assert summary.total_seller_movement == 10
    assert summary.final_retracement_ratio == pytest.approx(9 / 11)


def test_summarize_movements_handles_buyer_seller_buyer() -> None:
    summary = summarize_movements(
        [
            PriceLeg(MovementSide.BUYER, 100, 104, 4),
            PriceLeg(MovementSide.SELLER, 104, 99, 5),
            PriceLeg(MovementSide.BUYER, 99, 105, 6),
        ]
    )

    assert summary.first_side is MovementSide.BUYER
    assert summary.first_distance == 4
    assert summary.final_side is MovementSide.BUYER
    assert summary.final_distance == 6
    assert summary.largest_buyer_move == 6
    assert summary.largest_seller_move == 5
    assert summary.total_buyer_movement == 10
    assert summary.total_seller_movement == 5
    assert summary.final_retracement_ratio == pytest.approx(6 / 5)


def test_summarize_movements_calculates_largest_and_total_moves() -> None:
    summary = summarize_movements(
        [
            PriceLeg(MovementSide.BUYER, 100, 102, 2),
            PriceLeg(MovementSide.SELLER, 102, 99, 3),
            PriceLeg(MovementSide.BUYER, 99, 106, 7),
            PriceLeg(MovementSide.SELLER, 106, 101, 5),
        ]
    )

    assert summary.largest_buyer_move == 7
    assert summary.largest_seller_move == 5
    assert summary.total_buyer_movement == 9
    assert summary.total_seller_movement == 8


def test_final_retracement_requires_immediately_opposing_legs() -> None:
    summary = summarize_movements(
        [
            PriceLeg(MovementSide.BUYER, 100, 103, 3),
            PriceLeg(MovementSide.BUYER, 103, 108, 5),
        ]
    )

    assert summary.final_retracement_ratio is None
