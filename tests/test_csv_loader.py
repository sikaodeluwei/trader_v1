from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from trading.data.candles import (
    IntrabarPricePath,
    analyze_intrabar_path,
    analyze_intrabar_paths,
)
from trading.data.csv_loader import (
    load_and_build_intrabar_paths,
    load_price_events_csv,
)
from trading.definitions.analysis import analyze_prices


def write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "ticks.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_price_events_csv_reads_valid_rows(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n"
        "2026-08-28T09:30:00+00:00,100.25\n"
        "2026-08-28T09:30:01+00:00,100.50\n",
    )

    events = load_price_events_csv(path)

    assert [event.price for event in events] == [100.25, 100.50]
    assert events[0].timestamp == datetime(
        2026, 8, 28, 9, 30, tzinfo=timezone.utc
    )


def test_load_price_events_csv_preserves_fractional_seconds(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n"
        "2026-08-28T09:30:00.123456+00:00,100.25\n",
    )

    [event] = load_price_events_csv(path)

    assert event.timestamp.microsecond == 123456


def test_load_price_events_csv_preserves_timezone_offset(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n"
        "2026-08-28T17:30:00+08:00,100.25\n",
    )

    [event] = load_price_events_csv(path)

    assert event.timestamp.utcoffset() == timedelta(hours=8)


def test_duplicate_timestamps_preserve_csv_row_order(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n"
        "2026-08-28T09:30:00+00:00,100.25\n"
        "2026-08-28T09:30:00+00:00,100.00\n"
        "2026-08-28T09:30:00+00:00,100.50\n",
    )

    events = load_price_events_csv(path)

    assert [event.price for event in events] == [100.25, 100.00, 100.50]


def test_non_chronological_csv_rows_are_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n"
        "2026-08-28T09:30:01+00:00,100.25\n"
        "2026-08-28T09:30:00+00:00,100.00\n",
    )

    with pytest.raises(ValueError, match="chronological"):
        load_price_events_csv(path)


def test_missing_timestamp_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "timestamp,price\n,100.25\n")

    with pytest.raises(ValueError, match="missing timestamp"):
        load_price_events_csv(path)


def test_missing_price_is_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n2026-08-28T09:30:00+00:00,\n",
    )

    with pytest.raises(ValueError, match="missing price"):
        load_price_events_csv(path)


def test_malformed_timestamp_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "timestamp,price\nnot-a-timestamp,100.25\n")

    with pytest.raises(ValueError, match="malformed timestamp"):
        load_price_events_csv(path)


def test_non_numeric_price_is_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n2026-08-28T09:30:00+00:00,not-a-price\n",
    )

    with pytest.raises(ValueError, match="non-numeric price"):
        load_price_events_csv(path)


@pytest.mark.parametrize("price", ["NaN", "inf", "-inf"])
def test_non_finite_price_is_rejected(tmp_path: Path, price: str) -> None:
    path = write_csv(
        tmp_path,
        f"timestamp,price\n2026-08-28T09:30:00+00:00,{price}\n",
    )

    with pytest.raises(ValueError, match="finite"):
        load_price_events_csv(path)


def test_csv_builds_one_minute_intrabar_path_in_source_order(
    tmp_path: Path,
) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,price\n"
        "2026-08-28T09:30:00.123456+00:00,100.25\n"
        "2026-08-28T09:30:00.450000+00:00,100.00\n"
        "2026-08-28T09:30:01.000000+00:00,100.50\n",
    )

    paths = load_and_build_intrabar_paths(path, timedelta(minutes=1))

    assert len(paths) == 1
    assert paths[0].prices == (100.25, 100.00, 100.50)
    assert paths[0].start_time == datetime(
        2026, 8, 28, 9, 30, tzinfo=timezone.utc
    )


def test_bulk_analysis_skips_single_price_windows() -> None:
    paths = [
        IntrabarPricePath(
            start_time=datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 28, 9, 31, tzinfo=timezone.utc),
            prices=(100.0,),
        ),
        IntrabarPricePath(
            start_time=datetime(2026, 8, 28, 9, 31, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 28, 9, 32, tzinfo=timezone.utc),
            prices=(100.0, 101.0),
        ),
    ]

    analyses = analyze_intrabar_paths(paths)

    assert analyses == [analyze_prices((100.0, 101.0))]


def test_bulk_analysis_analyzes_every_valid_path() -> None:
    paths = [
        IntrabarPricePath(
            start_time=datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 28, 9, 31, tzinfo=timezone.utc),
            prices=(100.0, 101.0),
        ),
        IntrabarPricePath(
            start_time=datetime(2026, 8, 28, 9, 31, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 28, 9, 32, tzinfo=timezone.utc),
            prices=(101.0, 99.0),
        ),
    ]

    assert analyze_intrabar_paths(paths) == [
        analyze_prices((100.0, 101.0)),
        analyze_prices((101.0, 99.0)),
    ]


def test_strict_analysis_rejects_single_price_path() -> None:
    path = IntrabarPricePath(
        start_time=datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 28, 9, 31, tzinfo=timezone.utc),
        prices=(100.0,),
    )

    with pytest.raises(ValueError, match="at least two"):
        analyze_intrabar_path(path)
