"""Fixed-time ordered intrabar paths and integration helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from trading.definitions.analysis import CandleAnalysis, analyze_prices
from trading.definitions.candles import Advantage, CandleType
from trading.definitions.dataset import CandleLabelRecord, create_record

from .events import PriceEvent


_UTC_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class IntrabarPricePath:
    """The original ordered prices observed during one fixed-time candle."""

    start_time: datetime
    end_time: datetime
    prices: tuple[float, ...]


def get_interval_start(timestamp: datetime, interval: timedelta) -> datetime:
    """Return the UTC epoch-anchored fixed-window start for a timestamp."""

    if interval <= timedelta(0):
        raise ValueError("interval must be positive")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")

    timestamp_utc = timestamp.astimezone(timezone.utc)
    interval_number = (timestamp_utc - _UTC_EPOCH) // interval
    return _UTC_EPOCH + interval_number * interval


def build_intrabar_paths(
    events: Sequence[PriceEvent],
    interval: timedelta,
) -> list[IntrabarPricePath]:
    """Group chronological events into fixed windows without sorting.

    Windows are anchored at the Unix epoch in UTC and use the half-open rule
    ``start_time <= timestamp < end_time``. Empty windows are omitted, every
    observed price is preserved, and no prices are interpolated.
    """

    if interval <= timedelta(0):
        raise ValueError("interval must be positive")

    paths: list[IntrabarPricePath] = []
    current_start: datetime | None = None
    current_prices: list[float] = []
    previous_timestamp: datetime | None = None

    for event in events:
        if (
            previous_timestamp is not None
            and event.timestamp < previous_timestamp
        ):
            raise ValueError("events must already be chronological")

        window_start = get_interval_start(event.timestamp, interval)
        if current_start is not None and window_start != current_start:
            paths.append(
                IntrabarPricePath(
                    start_time=current_start,
                    end_time=current_start + interval,
                    prices=tuple(current_prices),
                )
            )
            current_prices = []

        current_start = window_start
        current_prices.append(event.price)
        previous_timestamp = event.timestamp

    if current_start is not None:
        paths.append(
            IntrabarPricePath(
                start_time=current_start,
                end_time=current_start + interval,
                prices=tuple(current_prices),
            )
        )

    return paths


def analyze_intrabar_path(path: IntrabarPricePath) -> CandleAnalysis:
    """Analyze a path by reusing the existing ordered-price pipeline."""

    return analyze_prices(path.prices)


def label_intrabar_path(
    path: IntrabarPricePath,
    advantage: Advantage,
    candle_type: CandleType | None = None,
    note: str | None = None,
) -> CandleLabelRecord:
    """Create a dataset record with labels explicitly supplied by the caller."""

    return create_record(
        path.prices,
        advantage,
        candle_type=candle_type,
        note=note,
    )
