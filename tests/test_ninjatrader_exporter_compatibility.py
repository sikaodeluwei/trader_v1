from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORTER = (
    PROJECT_ROOT
    / "tools"
    / "validation"
    / "ninjatrader"
    / "ExportMnq5mCohortSource.cs"
)
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
SYSTEM_WEB_EXTENSIONS = Path(
    r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Web.Extensions.dll"
)
NINJATRADER_INSTALL = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / (
    "NinjaTrader 8"
)


def _ninjatrader_user_data() -> Path | None:
    candidates = (
        Path.home() / "Documents" / "NinjaTrader 8",
        Path.home() / "OneDrive" / "Documents" / "NinjaTrader 8",
        Path.home() / "OneDrive" / "文档" / "NinjaTrader 8",
    )
    return next(
        (
            candidate
            for candidate in candidates
            if (candidate / "bin" / "Custom" / "NinjaTrader.Custom.dll").is_file()
        ),
        None,
    )


def test_exporter_has_no_undeclared_json_dependency() -> None:
    source = EXPORTER.read_text(encoding="utf-8")
    imported_namespaces = re.findall(
        r"^using\s+([A-Za-z_][A-Za-z0-9_.]*);\s*$",
        source,
        flags=re.MULTILINE,
    )

    assert set(imported_namespaces) == {
        "System",
        "System.Collections.Generic",
        "System.ComponentModel.DataAnnotations",
        "System.Globalization",
        "System.IO",
        "System.Linq",
        "System.Security.Cryptography",
        "System.Text",
        "System.Threading",
        "System.Web.Script.Serialization",
        "NinjaTrader.Cbi",
        "NinjaTrader.Data",
        "NinjaTrader.NinjaScript",
    }
    for forbidden in (
        r"\bNewtonsoft(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b",
        r"\bJsonConvert\b",
        r"\bSystem\.Text\.Json\b",
        r"\bDataContractJsonSerializer\b",
    ):
        assert re.search(forbidden, source) is None
    serializer_identifiers = set(
        re.findall(
            r"\b(?:[A-Za-z_][A-Za-z0-9_]*Serializer|JsonConvert)\b",
            source,
        )
    )
    assert serializer_identifiers == {"JavaScriptSerializer"}
    assert "using System.Web.Script.Serialization;" in source
    assert "new JavaScriptSerializer().Serialize(runtimeCapture)" in source


def test_exporter_validates_contract_semantics_not_display_name() -> None:
    source = EXPORTER.read_text(encoding="utf-8")

    assert "ApprovedFullName" not in source
    assert 'masterName != "MNQ"' in source
    assert "expiry.Month != ApprovedExpiryMonth" in source
    assert "expiry.Year != ApprovedExpiryYear" in source
    assert "Instrument.FullName !=" not in source
    assert "full_name = Instrument.FullName" in source
    assert "instrument_id = Instrument.FullName" in source


def test_exporter_emits_only_neutral_v12_lifecycle_markers() -> None:
    source = EXPORTER.read_text(encoding="utf-8")

    assert "realtime lifecycle observed event_time=" in source
    assert '" export armed event_time="' in source
    assert "awaiting operator arm after Reload All Historical Data" not in source
    assert '" export armed after reload event_time="' not in source


def test_windows_crlf_source_bytes_differ_from_literal_lf_canonical_bytes() -> None:
    rows = [
        "20260622 170500;1;2;0.5;1.5;10",
        "20260622 171000;1.5;2.5;1;2;11",
    ]
    canonical_lf = ("\n".join(rows) + "\n").encode("utf-8")
    windows_crlf = ("\r\n".join(rows) + "\r\n").encode("utf-8")

    assert b"\r" not in canonical_lf
    assert b"\r\n" in windows_crlf
    assert hashlib.sha256(canonical_lf).hexdigest() != hashlib.sha256(
        windows_crlf
    ).hexdigest()


def test_exporter_writes_bars_with_literal_lf_not_environment_newline() -> None:
    source = EXPORTER.read_text(encoding="utf-8")

    assert 'File.WriteAllText(sourceTemporary, string.Join("\\n", rows) + "\\n", Utf8NoBom);' in source
    assert (
        'File.WriteAllText(sourceTemporary, string.Join(Environment.NewLine, rows)'
        not in source
    )


def test_exporter_rows_hash_as_scanner_canonical_lf_bytes() -> None:
    source = EXPORTER.read_text(encoding="utf-8")
    rows = [
        "20260622 170500;1;2;0.5;1.5;10",
        "20260622 171000;1.5;2.5;1;2;11",
    ]
    scanner_canonical = ("\n".join(rows) + "\n").encode("utf-8")

    assert 'string.Join("\\n", rows) + "\\n"' in source
    assert hashlib.sha256(scanner_canonical).hexdigest() == (
        "b7b0410624b07ecddb6a524fb54f898ad999db2f2c3884e06f49faff89ec5dca"
    )


def test_exporter_source_bytes_keep_final_lf_and_utf8_without_bom() -> None:
    source = EXPORTER.read_text(encoding="utf-8")

    assert "new UTF8Encoding(false)" in source
    assert 'string.Join("\\n", rows) + "\\n"' in source
    assert 'new JavaScriptSerializer().Serialize(runtimeCapture) + Environment.NewLine' in source

    rows = ["20260622 170500;1;2;0.5;1.5;10"]
    canonical = ("\n".join(rows) + "\n").encode("utf-8")
    assert canonical.endswith(b"\n")
    assert not canonical.startswith(b"\xef\xbb\xbf")


def test_exporter_session_calendar_uses_trading_hours_timezone_with_offsets() -> None:
    """Catches leaking the configurable application timezone into session evidence."""
    source = EXPORTER.read_text(encoding="utf-8")

    assert (
        "session_calendar = CaptureSessionCalendar(\n"
        "                        tradingDate,\n"
        "                        appliedTradingHours.TimeZoneInfo)"
    ) in source
    assert re.search(
        r"CaptureSessionCalendar\(\s*DateTime tradingDate,\s*"
        r"TimeZoneInfo tradingHoursTimeZone\s*\)",
        source,
    )
    assert re.search(
        r"DateTimeOffset beginTradingHours = TimeZoneInfo\.ConvertTime\(\s*"
        r"beginPc,\s*tradingHoursTimeZone\s*\)",
        source,
    )
    assert re.search(
        r"DateTimeOffset endTradingHours = TimeZoneInfo\.ConvertTime\(\s*"
        r"endPc,\s*tradingHoursTimeZone\s*\)",
        source,
    )
    assert 'begin_application = beginTradingHours.ToString("o", CultureInfo.InvariantCulture)' in source
    assert 'end_application = endTradingHours.ToString("o", CultureInfo.InvariantCulture)' in source
    assert 'begin_pc = beginPc.ToString("o", CultureInfo.InvariantCulture)' in source
    assert 'end_pc = endPc.ToString("o", CultureInfo.InvariantCulture)' in source


@pytest.mark.skipif(
    not CSC.is_file(),
    reason="the installed .NET Framework compiler is unavailable",
)
def test_trading_hours_offset_representation_preserves_summer_and_winter_instants(
    tmp_path: Path,
) -> None:
    """The approved Central timezone representation must retain DST and the instant."""
    program = tmp_path / "TradingHoursOffsetContract.cs"
    executable = tmp_path / "TradingHoursOffsetContract.exe"
    program.write_text(
        r'''
using System;
using System.Globalization;

public static class TradingHoursOffsetContract
{
    public static void Main()
    {
        TimeZoneInfo singapore = TimeZoneInfo.FindSystemTimeZoneById("Singapore Standard Time");
        TimeZoneInfo central = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        DateTimeOffset summerPc = new DateTimeOffset(2026, 7, 1, 6, 0, 0, TimeSpan.FromHours(8));
        DateTimeOffset winterPc = new DateTimeOffset(2026, 1, 5, 7, 0, 0, TimeSpan.FromHours(8));
        DateTimeOffset summer = TimeZoneInfo.ConvertTime(summerPc, central);
        DateTimeOffset winter = TimeZoneInfo.ConvertTime(winterPc, central);
        Console.WriteLine(summer.ToString("o", CultureInfo.InvariantCulture));
        Console.WriteLine(winter.ToString("o", CultureInfo.InvariantCulture));
        Console.WriteLine(summer.UtcDateTime == summerPc.UtcDateTime);
        Console.WriteLine(winter.UtcDateTime == winterPc.UtcDateTime);
    }
}
'''.lstrip(),
        encoding="utf-8",
        newline="",
    )

    compiled = subprocess.run(
        [str(CSC), "/nologo", "/codepage:65001", f"/out:{executable}", str(program)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    lines = subprocess.run(
        [str(executable)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=True,
    ).stdout.splitlines()
    assert lines == [
        "2026-06-30T17:00:00.0000000-05:00",
        "2026-01-04T17:00:00.0000000-06:00",
        "True",
        "True",
    ]


@pytest.mark.skipif(
    not (CSC.is_file() and SYSTEM_WEB_EXTENSIONS.is_file()),
    reason="the installed .NET Framework NinjaScript compiler is unavailable",
)
def test_standard_ninjascript_serializer_emits_valid_runtime_capture_json(
    tmp_path: Path,
) -> None:
    program = tmp_path / "SerializeRuntimeCapture.cs"
    executable = tmp_path / "SerializeRuntimeCapture.exe"
    program.write_text(
        r'''
using System;
using System.Collections.Generic;
using System.Text;
using System.Web.Script.Serialization;

public static class SerializeRuntimeCapture
{
    public static void Main()
    {
        object runtimeCapture = new
        {
            schema_version = "1.1",
            acquisition_id = "quote\" backslash\\ control\b\f\n\r\t unicode-\u96ea",
            cohort_id = "mnq-202609-5m-dryrun-v1",
            case_id = "dryrun-mnq-202609-5m-20260701",
            trading_date = "2026-07-01",
            instrument = new
            {
                contract_label = "MNQ SEP26",
                full_name = "MNQ SEP26",
                master_name = "MNQ",
                instrument_id = "MNQ SEP26",
                expiry_month = 9,
                expiry_year = 2026,
                exchange = "Globex"
            },
            ninjatrader_version = "8.1.8.2",
            export_method = "ExportMnq5mCohortSource NinjaTrader indicator",
            original_export_identity = "dryrun/bars.txt",
            bar_series = new
            {
                type = "Minute",
                value = 5,
                native = true,
                exported_bar_count = 250,
                timestamp_semantics = "native close timestamp"
            },
            pc_timezone = new
            {
                id = "Singapore Standard Time",
                base_utc_offset = "+08:00",
                supports_dst = false,
                acquisition_event_offsets = (IList<object>)new List<object>
                {
                    new
                    {
                        @event = "initialized",
                        timestamp = "2026-07-01T20:58:00.0000000+08:00",
                        utc_offset = "+08:00"
                    },
                    new
                    {
                        @event = "armed",
                        timestamp = "2026-07-01T20:59:00.0000000+08:00",
                        utc_offset = "+08:00"
                    },
                    new
                    {
                        @event = "exported",
                        timestamp = "2026-07-01T21:00:00.0000000+08:00",
                        utc_offset = "+08:00"
                    }
                }
            },
            application_timezone = new
            {
                id = "Central Standard Time",
                display_name = "Central Time",
                standard_name = "Central Standard Time",
                daylight_name = "Central Daylight Time",
                base_utc_offset = "-06:00",
                supports_dst = true,
                source_timestamp_offsets = new List<object>
                {
                    new
                    {
                        first_timestamp = "20260701 060000",
                        last_timestamp = "20260701 205500",
                        utc_offset = "-05:00"
                    }
                }
            },
            trading_hours = new
            {
                name = "CME US Index Futures ETH",
                timezone_id = "Central Standard Time",
                definition_sha256 = new string('a', 64),
                holiday_configuration_captured = true,
                session_calendar = new List<object>
                {
                    new
                    {
                        trading_date = "2026-07-01",
                        segments = new List<object>
                        {
                            new
                            {
                                begin_application = "2026-06-30T17:00:00.0000000-05:00",
                                end_application = "2026-07-01T16:00:00.0000000-05:00",
                                begin_pc = "2026-07-01T06:00:00.0000000+08:00",
                                end_pc = "2026-07-02T05:00:00.0000000+08:00"
                            }
                        },
                        holiday_name = (string)null,
                        partial_holiday = (bool?)null,
                        effective_schedule_source = "SessionIterator using Bars.TradingHours"
                    }
                }
            },
            active_connections = (IList<object>)new List<object>
            {
                new
                {
                    name = "Tradovate",
                    provider = "Tradovate",
                    status = "Connected",
                    price_status = "Connected",
                    instrument_types = new[] { "Future" }
                }
            },
            connection_snapshot_phase = "immediately after operator arm and before export",
            exported_at = "2026-07-01T21:00:00.0000000-05:00",
            source_sha256 = new string('b', 64)
        };

        Console.OutputEncoding = new UTF8Encoding(false);
        Console.Write(new JavaScriptSerializer().Serialize(runtimeCapture));
    }
}
'''.lstrip(),
        encoding="utf-8",
        newline="",
    )

    compiled = subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/codepage:65001",
            f"/reference:{SYSTEM_WEB_EXTENSIONS}",
            f"/out:{executable}",
            str(program),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    serialized = subprocess.run(
        [str(executable)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=True,
    ).stdout
    runtime_capture = json.loads(serialized)

    assert set(runtime_capture) == {
        "schema_version",
        "acquisition_id",
        "cohort_id",
        "case_id",
        "trading_date",
        "instrument",
        "ninjatrader_version",
        "export_method",
        "original_export_identity",
        "bar_series",
        "pc_timezone",
        "application_timezone",
        "trading_hours",
        "active_connections",
        "connection_snapshot_phase",
        "exported_at",
        "source_sha256",
    }
    assert runtime_capture["schema_version"] == "1.1"
    assert runtime_capture["acquisition_id"] == (
        'quote" backslash\\ control\b\f\n\r\t unicode-雪'
    )
    assert runtime_capture["instrument"] == {
        "contract_label": "MNQ SEP26",
        "full_name": "MNQ SEP26",
        "master_name": "MNQ",
        "instrument_id": "MNQ SEP26",
        "expiry_month": 9,
        "expiry_year": 2026,
        "exchange": "Globex",
    }
    assert runtime_capture["bar_series"] == {
        "type": "Minute",
        "value": 5,
        "native": True,
        "exported_bar_count": 250,
        "timestamp_semantics": "native close timestamp",
    }
    assert runtime_capture["pc_timezone"]["supports_dst"] is False
    assert runtime_capture["pc_timezone"]["acquisition_event_offsets"] == [
        {
            "event": "initialized",
            "timestamp": "2026-07-01T20:58:00.0000000+08:00",
            "utc_offset": "+08:00",
        },
        {
            "event": "armed",
            "timestamp": "2026-07-01T20:59:00.0000000+08:00",
            "utc_offset": "+08:00",
        },
        {
            "event": "exported",
            "timestamp": "2026-07-01T21:00:00.0000000+08:00",
            "utc_offset": "+08:00",
        },
    ]
    assert runtime_capture["application_timezone"]["source_timestamp_offsets"][
        0
    ]["utc_offset"] == "-05:00"
    assert runtime_capture["trading_hours"]["holiday_configuration_captured"] is True
    assert runtime_capture["trading_hours"]["session_calendar"][0][
        "holiday_name"
    ] is None
    assert runtime_capture["trading_hours"]["session_calendar"][0][
        "partial_holiday"
    ] is None
    assert runtime_capture["trading_hours"]["session_calendar"][0]["segments"][
        0
    ]["begin_application"] == "2026-06-30T17:00:00.0000000-05:00"
    assert runtime_capture["trading_hours"]["session_calendar"][0]["segments"][
        0
    ]["begin_pc"] == "2026-07-01T06:00:00.0000000+08:00"
    assert runtime_capture["active_connections"][0]["instrument_types"] == [
        "Future"
    ]


def test_exporter_compiles_against_installed_ninjatrader_references(
    tmp_path: Path,
) -> None:
    user_data = _ninjatrader_user_data()
    required = (
        CSC,
        SYSTEM_WEB_EXTENSIONS,
        NINJATRADER_INSTALL / "bin" / "NinjaTrader.Core.dll",
        NINJATRADER_INSTALL / "bin" / "NinjaTrader.Gui.dll",
    )
    if user_data is None or not all(path.is_file() for path in required):
        pytest.skip("the installed NinjaTrader compile environment is unavailable")

    framework = CSC.parent
    custom = user_data / "bin" / "Custom" / "NinjaTrader.Custom.dll"
    references = (
        framework / "System.dll",
        framework / "System.Core.dll",
        framework / "System.ComponentModel.DataAnnotations.dll",
        SYSTEM_WEB_EXTENSIONS,
        framework / "WPF" / "WindowsBase.dll",
        framework / "WPF" / "PresentationCore.dll",
        framework / "WPF" / "PresentationFramework.dll",
        NINJATRADER_INSTALL / "bin" / "NinjaTrader.Core.dll",
        NINJATRADER_INSTALL / "bin" / "NinjaTrader.Gui.dll",
        custom,
    )

    compiled = subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/codepage:65001",
            "/target:library",
            f"/out:{tmp_path / 'ExportMnq5mCohortSource.dll'}",
            *(f"/reference:{path}" for path in references),
            str(EXPORTER),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
