import pytest

from trading.definitions.candles import (
    Candle,
    CandleControl,
    CandleSide,
    get_control,
    get_side,
)


def test_get_control_when_close_is_at_high() -> None:
    assert get_control(Candle(open=95, high=110, low=90, close=110)) == (
        CandleControl(
            buyer_control=20,
            seller_control=0,
            buyer_control_ratio=1,
            seller_control_ratio=0,
            control_score=1,
        )
    )


def test_get_control_when_close_is_at_low() -> None:
    assert get_control(Candle(open=105, high=110, low=90, close=90)) == (
        CandleControl(
            buyer_control=0,
            seller_control=20,
            buyer_control_ratio=0,
            seller_control_ratio=1,
            control_score=-1,
        )
    )


def test_get_control_when_close_is_at_middle() -> None:
    assert get_control(Candle(open=95, high=110, low=90, close=100)) == (
        CandleControl(
            buyer_control=10,
            seller_control=10,
            buyer_control_ratio=0.5,
            seller_control_ratio=0.5,
            control_score=0,
        )
    )


def test_bullish_candle_can_have_negative_control_score() -> None:
    candle = Candle(open=91, high=110, low=90, close=92)

    assert get_side(candle) is CandleSide.BULLISH
    control = get_control(candle)
    assert control.buyer_control == 2
    assert control.seller_control == 18
    assert control.buyer_control_ratio == pytest.approx(0.1)
    assert control.seller_control_ratio == pytest.approx(0.9)
    assert control.control_score == pytest.approx(-0.8)


def test_bearish_candle_can_have_positive_control_score() -> None:
    candle = Candle(open=109, high=110, low=90, close=108)

    assert get_side(candle) is CandleSide.BEARISH
    control = get_control(candle)
    assert control.buyer_control == 18
    assert control.seller_control == 2
    assert control.buyer_control_ratio == pytest.approx(0.9)
    assert control.seller_control_ratio == pytest.approx(0.1)
    assert control.control_score == pytest.approx(0.8)


def test_get_control_handles_zero_range_candle() -> None:
    assert get_control(Candle(open=100, high=100, low=100, close=100)) == (
        CandleControl(
            buyer_control=0.0,
            seller_control=0.0,
            buyer_control_ratio=0.5,
            seller_control_ratio=0.5,
            control_score=0.0,
        )
    )
