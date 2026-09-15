from __future__ import annotations

import json
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
                full_name = "MNQ 09-26",
                master_name = "MNQ",
                instrument_id = "MNQ 09-26",
                expiry_month = 9,
                expiry_year = 2026,
                exchange = "CME"
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
                                begin_application = "20260630 170000",
                                end_application = "20260701 160000",
                                begin_pc = "20260701 060000",
                                end_pc = "20260702 050000"
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
        "full_name": "MNQ 09-26",
        "master_name": "MNQ",
        "instrument_id": "MNQ 09-26",
        "expiry_month": 9,
        "expiry_year": 2026,
        "exchange": "CME",
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
    ]["begin_application"] == "20260630 170000"
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
