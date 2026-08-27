"""Historical tick/trade CSV adapter for ordered price events."""

import csv
from datetime import datetime, timedelta
from pathlib import Path

from .candles import IntrabarPricePath, build_intrabar_paths
from .events import PriceEvent


def load_price_events_csv(
    path: str | Path,
    timestamp_column: str = "timestamp",
    price_column: str = "price",
) -> list[PriceEvent]:
    """Load chronological ISO-8601 price events without reordering rows."""

    events: list[PriceEvent] = []
    previous_timestamp: datetime | None = None

    with Path(path).open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError("CSV is missing a header row")
        if timestamp_column not in fieldnames:
            raise ValueError(f"CSV is missing timestamp column {timestamp_column!r}")
        if price_column not in fieldnames:
            raise ValueError(f"CSV is missing price column {price_column!r}")

        for row_number, row in enumerate(reader, start=2):
            timestamp_text = row.get(timestamp_column)
            if timestamp_text is None or not timestamp_text.strip():
                raise ValueError(f"row {row_number}: missing timestamp")

            price_text = row.get(price_column)
            if price_text is None or not price_text.strip():
                raise ValueError(f"row {row_number}: missing price")

            try:
                timestamp = datetime.fromisoformat(timestamp_text.strip())
            except ValueError as error:
                raise ValueError(
                    f"row {row_number}: malformed timestamp"
                ) from error

            try:
                price = float(price_text.strip())
            except ValueError as error:
                raise ValueError(
                    f"row {row_number}: non-numeric price"
                ) from error

            try:
                event = PriceEvent(timestamp=timestamp, price=price)
            except ValueError as error:
                raise ValueError(f"row {row_number}: {error}") from error

            if (
                previous_timestamp is not None
                and event.timestamp < previous_timestamp
            ):
                raise ValueError(f"row {row_number}: events must be chronological")

            events.append(event)
            previous_timestamp = event.timestamp

    return events


def load_and_build_intrabar_paths(
    path: str | Path,
    interval: timedelta,
) -> list[IntrabarPricePath]:
    """Load CSV events and group them using the existing interval builder."""

    return build_intrabar_paths(load_price_events_csv(path), interval)
