"""Generic timestamped closed-OHLC CSV adapter."""

import csv
from datetime import datetime
from pathlib import Path

from trading.analysis.models import ClosedCandleObservation, OfflineMarketWindow


def _cell(row: dict[str, str | None], column: str, row_number: int) -> str:
    value = row.get(column)
    if value is None or not value.strip():
        raise ValueError(f"row {row_number}: missing {column}")
    return value.strip()


def load_ohlc_market_window(
    path: str | Path,
    *,
    instrument: str,
    timeframe: str,
    start_index: int = 0,
    timestamp_column: str = "timestamp",
    open_column: str = "open",
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
) -> OfflineMarketWindow:
    """Load ordered, completed timezone-aware OHLC rows into a market window.

    Rows are consumed in their source order.  The adapter performs no sorting,
    filling, resampling, interpolation, or intrabar-path fabrication; the
    immutable analysis models validate each observation and the final window.
    """

    observations: list[ClosedCandleObservation] = []
    row_numbers: list[int] = []

    required_columns = (
        timestamp_column,
        open_column,
        high_column,
        low_column,
        close_column,
    )

    with Path(path).open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError("CSV is missing a header row")

        for column in required_columns:
            if column not in fieldnames:
                raise ValueError(f"CSV is missing required column {column!r}")

        for row_number, row in enumerate(reader, start=2):
            timestamp_text = _cell(row, timestamp_column, row_number)
            try:
                timestamp = datetime.fromisoformat(timestamp_text)
            except ValueError as error:
                raise ValueError(
                    f"row {row_number}: malformed timestamp"
                ) from error

            values: dict[str, float] = {}
            for column in (open_column, high_column, low_column, close_column):
                value_text = _cell(row, column, row_number)
                try:
                    values[column] = float(value_text)
                except (TypeError, ValueError, OverflowError) as error:
                    raise ValueError(
                        f"row {row_number}: non-numeric {column}"
                    ) from error

            try:
                observation = ClosedCandleObservation(
                    timestamp=timestamp,
                    open=values[open_column],
                    high=values[high_column],
                    low=values[low_column],
                    close=values[close_column],
                )
            except ValueError as error:
                raise ValueError(f"row {row_number}: {error}") from error

            observations.append(observation)
            row_numbers.append(row_number)

    try:
        return OfflineMarketWindow(
            instrument=instrument,
            timeframe=timeframe,
            start_index=start_index,
            candles=tuple(observations),
        )
    except ValueError as error:
        message = str(error)
        if "strictly increasing" in message and len(observations) >= 2:
            offending_row = next(
                row
                for row, previous, current in zip(
                    row_numbers[1:], observations, observations[1:]
                )
                if not previous.timestamp < current.timestamp
            )
            raise ValueError(f"row {offending_row}: {message}") from error
        if "1 through 250" in message and row_numbers:
            raise ValueError(f"row {row_numbers[-1]}: {message}") from error
        raise
