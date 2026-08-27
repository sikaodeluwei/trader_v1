from datetime import datetime, timedelta, timezone

import pytest

from trading.data.candles import (
    IntrabarPricePath,
    analyze_intrabar_path,
    build_intrabar_paths,
    label_intrabar_path,
)
from trading.data.events import PriceEvent
from trading.definitions.analysis import analyze_prices
from trading.definitions.candles import Advantage, CandleType


def utc_time(
    hour: int,
    minute: int,
    second: int = 0,
    microsecond: int = 0,
) -> datetime:
    return datetime(
        2026,
        8,
        28,
        hour,
        minute,
        second,
        microsecond,
        tzinfo=timezone.utc,
    )


def test_price_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PriceEvent(datetime(2026, 8, 28, 9, 30), 100)


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_price_event_requires_finite_price(price: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        PriceEvent(utc_time(9, 30), price)


def test_build_intrabar_paths_groups_ordered_events_in_one_interval() -> None:
    events = [
        PriceEvent(utc_time(9, 30), 100),
        PriceEvent(utc_time(9, 30, 15), 99),
        PriceEvent(utc_time(9, 30, 59, 999999), 102),
    ]

    assert build_intrabar_paths(events, timedelta(minutes=1)) == [
        IntrabarPricePath(
            start_time=utc_time(9, 30),
            end_time=utc_time(9, 31),
            prices=(100, 99, 102),
        )
    ]


def test_build_intrabar_paths_splits_intervals_and_omits_empty_windows() -> None:
    events = [
        PriceEvent(utc_time(9, 30, 10), 100),
        PriceEvent(utc_time(9, 32, 5), 103),
    ]

    paths = build_intrabar_paths(events, timedelta(minutes=1))

    assert [(path.start_time, path.prices) for path in paths] == [
        (utc_time(9, 30), (100,)),
        (utc_time(9, 32), (103,)),
    ]


def test_event_on_exact_boundary_belongs_to_new_interval() -> None:
    events = [
        PriceEvent(utc_time(9, 30, 59), 100),
        PriceEvent(utc_time(9, 31), 101),
    ]

    paths = build_intrabar_paths(events, timedelta(minutes=1))

    assert [path.prices for path in paths] == [(100,), (101,)]
    assert paths[1].start_time == utc_time(9, 31)


def test_build_intrabar_paths_preserves_original_price_order() -> None:
    events = [
        PriceEvent(utc_time(9, 30, 1), 100),
        PriceEvent(utc_time(9, 30, 2), 99),
        PriceEvent(utc_time(9, 30, 3), 105),
        PriceEvent(utc_time(9, 30, 4), 101),
    ]

    [path] = build_intrabar_paths(events, timedelta(minutes=1))

    assert path.prices == (100, 99, 105, 101)


def test_duplicate_timestamps_preserve_input_order() -> None:
    timestamp = utc_time(9, 30, 10)
    events = [
        PriceEvent(timestamp, 100),
        PriceEvent(timestamp, 99),
        PriceEvent(timestamp, 101),
    ]

    [path] = build_intrabar_paths(events, timedelta(minutes=1))

    assert path.prices == (100, 99, 101)


def test_build_intrabar_paths_rejects_non_chronological_events() -> None:
    events = [
        PriceEvent(utc_time(9, 30, 10), 100),
        PriceEvent(utc_time(9, 30, 9), 99),
    ]

    with pytest.raises(ValueError, match="chronological"):
        build_intrabar_paths(events, timedelta(minutes=1))


@pytest.mark.parametrize("interval", [timedelta(0), timedelta(seconds=-1)])
def test_build_intrabar_paths_rejects_non_positive_interval(
    interval: timedelta,
) -> None:
    with pytest.raises(ValueError, match="positive"):
        build_intrabar_paths([], interval)


def test_analyze_intrabar_path_matches_analyze_prices() -> None:
    path = IntrabarPricePath(
        start_time=utc_time(9, 30),
        end_time=utc_time(9, 31),
        prices=(100, 99, 105, 101),
    )

    assert analyze_intrabar_path(path) == analyze_prices(path.prices)


@pytest.mark.parametrize(
    "advantage",
    [Advantage.BUYER, Advantage.SELLER, Advantage.NONE],
)
def test_label_intrabar_path_preserves_explicit_advantage(
    advantage: Advantage,
) -> None:
    path = IntrabarPricePath(
        start_time=utc_time(9, 30),
        end_time=utc_time(9, 31),
        prices=(100, 99, 105, 101),
    )

    record = label_intrabar_path(path, advantage)

    assert record.prices == path.prices
    assert record.advantage is advantage


def test_label_intrabar_path_preserves_optional_metadata() -> None:
    path = IntrabarPricePath(
        start_time=utc_time(9, 30),
        end_time=utc_time(9, 31),
        prices=(100, 99, 105, 101),
    )

    record = label_intrabar_path(
        path,
        Advantage.SELLER,
        candle_type=CandleType.BULL_4,
        note="manual review",
    )

    assert record.candle_type is CandleType.BULL_4
    assert record.note == "manual review"
