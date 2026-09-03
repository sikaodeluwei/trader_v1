import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from importlib import import_module

import trading.data
import pytest

from trading.analysis.models import OfflineMarketWindow
from trading.data.ohlc_csv_loader import load_ohlc_market_window


def test_ohlc_csv_loader_module_is_discoverable() -> None:
    assert importlib.util.find_spec("trading.data.ohlc_csv_loader") is not None


def test_ohlc_csv_loader_exposes_locked_public_name() -> None:
    module = import_module("trading.data.ohlc_csv_loader")
    missing = [
        name
        for name in ("load_ohlc_market_window",)
        if not hasattr(module, name)
    ]
    assert missing == []


def write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "candles.csv"
    path.write_text(content, encoding="utf-8", newline="")
    return path


def call_loader(*args: object, **kwargs: object) -> OfflineMarketWindow:
    try:
        result = load_ohlc_market_window(*args, **kwargs)
    except NotImplementedError as error:
        pytest.fail(f"loader behavior is missing: {error}")
    assert isinstance(result, OfflineMarketWindow)
    return result


DEFAULT_ROWS = (
    "timestamp,open,high,low,close\n"
    "2026-08-28T09:30:00.000000+00:00,100,102,99,101\n"
    "2026-08-28T09:31:00.000000+00:00,101,103,100,102\n"
)


def test_loads_timestamped_ohlc_in_source_order_without_intrabar_fabrication(
    tmp_path: Path,
) -> None:
    path = write_csv(tmp_path, DEFAULT_ROWS)

    window = call_loader(
        path,
        instrument="MNQ",
        timeframe="1m",
        start_index=40,
    )

    assert window.instrument == "MNQ"
    assert window.timeframe == "1m"
    assert window.start_index == 40
    assert [c.open for c in window.candles] == [100.0, 101.0]
    assert [c.close for c in window.candles] == [101.0, 102.0]
    assert [window.start_index + i for i in range(len(window.candles))] == [40, 41]
    assert window.candles[0].timestamp.microsecond == 0
    assert window.candles[0].timestamp.utcoffset() == timedelta(0)
    assert window.candles[0].intrabar_prices is None


def test_preserves_fractional_seconds_and_timezone_offset(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        "2026-08-28T17:30:00.123456+08:00,100,102,99,101\n",
    )

    [candle] = call_loader(
        path,
        instrument="ES",
        timeframe="5m",
    ).candles

    assert candle.timestamp == datetime(
        2026,
        8,
        28,
        17,
        30,
        microsecond=123456,
        tzinfo=timezone(timedelta(hours=8)),
    )


def test_supports_configurable_column_names(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "time,ask,peak,trough,bid\n"
        "2026-08-28T09:30:00+00:00,100,102,99,101\n",
    )

    window = call_loader(
        path,
        instrument="CUSTOM",
        timeframe="opaque",
        timestamp_column="time",
        open_column="ask",
        high_column="peak",
        low_column="trough",
        close_column="bid",
    )

    assert window.candles[0].open == 100.0
    assert window.candles[0].high == 102.0
    assert window.candles[0].low == 99.0
    assert window.candles[0].close == 101.0


@pytest.mark.parametrize(
    ("header", "missing"),
    [
        ("open,high,low,close", "timestamp"),
        ("timestamp,high,low,close", "open"),
        ("timestamp,open,low,close", "high"),
        ("timestamp,open,high,close", "low"),
        ("timestamp,open,high,low", "close"),
    ],
)
def test_rejects_missing_required_headers(
    tmp_path: Path,
    header: str,
    missing: str,
) -> None:
    path = write_csv(tmp_path, f"{header}\n2026-08-28T09:30:00+00:00,100,102,99,101\n")

    with pytest.raises(ValueError, match=rf"missing .*{missing}"):
        call_loader(path, instrument="MNQ", timeframe="1m")


def test_rejects_csv_without_header(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "")

    with pytest.raises(ValueError, match="missing a header"):
        call_loader(path, instrument="MNQ", timeframe="1m")


@pytest.mark.parametrize("column", ["timestamp", "open", "high", "low", "close"])
def test_rejects_missing_cells_with_row_number(tmp_path: Path, column: str) -> None:
    values = {
        "timestamp": "2026-08-28T09:30:00+00:00",
        "open": "100",
        "high": "102",
        "low": "99",
        "close": "101",
    }
    values[column] = ""
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        + ",".join(values[name] for name in ("timestamp", "open", "high", "low", "close"))
        + "\n",
    )

    with pytest.raises(ValueError, match=rf"row 2: missing {column}"):
        call_loader(path, instrument="MNQ", timeframe="1m")


def test_rejects_malformed_timestamp_with_row_number(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        "not-a-timestamp,100,102,99,101\n",
    )

    with pytest.raises(ValueError, match="row 2: malformed timestamp"):
        call_loader(path, instrument="MNQ", timeframe="1m")


def test_rejects_naive_timestamp_with_row_number(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        "2026-08-28T09:30:00,100,102,99,101\n",
    )

    with pytest.raises(ValueError, match="row 2: .*timezone-aware"):
        call_loader(path, instrument="MNQ", timeframe="1m")


@pytest.mark.parametrize("column", ["open", "high", "low", "close"])
def test_rejects_nonnumeric_ohlc_with_row_number(tmp_path: Path, column: str) -> None:
    values = {
        "timestamp": "2026-08-28T09:30:00+00:00",
        "open": "100",
        "high": "102",
        "low": "99",
        "close": "101",
    }
    values[column] = "not-a-number"
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        + ",".join(values[name] for name in ("timestamp", "open", "high", "low", "close"))
        + "\n",
    )

    with pytest.raises(ValueError, match=rf"row 2: non-numeric {column}"):
        call_loader(path, instrument="MNQ", timeframe="1m")


@pytest.mark.parametrize("value", ["NaN", "inf", "-inf"])
def test_rejects_nonfinite_ohlc_with_row_number(tmp_path: Path, value: str) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        f"2026-08-28T09:30:00+00:00,{value},102,99,101\n",
    )

    with pytest.raises(ValueError, match="row 2: .*finite"):
        call_loader(path, instrument="MNQ", timeframe="1m")


@pytest.mark.parametrize(
    "values",
    [
        (100, 99, 99, 101),
        (100, 102, 103, 101),
        (100, 102, 99, 103),
        (100, 99, 102, 101),
    ],
)
def test_rejects_invalid_ohlc_geometry_with_row_number(
    tmp_path: Path,
    values: tuple[int, int, int, int],
) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        f"2026-08-28T09:30:00+00:00,{values[0]},{values[1]},{values[2]},{values[3]}\n",
    )

    with pytest.raises(ValueError, match=r"row 2: .*low <= min\(open, close\)"):
        call_loader(path, instrument="MNQ", timeframe="1m")


@pytest.mark.parametrize(
    "rows",
    [
        (
            "2026-08-28T09:30:00+00:00,100,102,99,101\n"
            "2026-08-28T09:30:00+00:00,101,103,100,102\n"
        ),
        (
            "2026-08-28T09:31:00+00:00,100,102,99,101\n"
            "2026-08-28T09:30:00+00:00,101,103,100,102\n"
        ),
    ],
)
def test_rejects_duplicate_or_decreasing_timestamps_with_row_number(
    tmp_path: Path,
    rows: str,
) -> None:
    path = write_csv(tmp_path, "timestamp,open,high,low,close\n" + rows)

    with pytest.raises(ValueError, match=r"row 3: .*strictly increasing"):
        call_loader(path, instrument="MNQ", timeframe="1m")


def test_rejects_empty_data(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "timestamp,open,high,low,close\n")

    with pytest.raises(ValueError, match="1 through 250"):
        call_loader(path, instrument="MNQ", timeframe="1m")


def test_rejects_251_rows_with_row_number_without_truncating(tmp_path: Path) -> None:
    rows = ["timestamp,open,high,low,close"]
    for index in range(251):
        timestamp = datetime(2026, 8, 28, tzinfo=timezone.utc) + timedelta(minutes=index)
        rows.append(f"{timestamp.isoformat()},100,102,99,101")
    path = write_csv(tmp_path, "\n".join(rows) + "\n")

    with pytest.raises(ValueError, match=r"row 252: .*1 through 250"):
        call_loader(path, instrument="MNQ", timeframe="1m")


def test_preserves_nonminute_gaps_and_does_not_sort_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,open,high,low,close\n"
        "2026-08-28T09:30:00+00:00,100,102,99,101\n"
        "2026-08-28T09:32:00+00:00,101,103,100,102\n",
    )

    monkeypatch.setattr(
        "builtins.sorted",
        lambda *args, **kwargs: pytest.fail("loader must not sort rows"),
    )

    window = call_loader(path, instrument="MNQ", timeframe="1m")

    assert [c.timestamp.minute for c in window.candles] == [30, 32]
    assert len(window.candles) == 2
