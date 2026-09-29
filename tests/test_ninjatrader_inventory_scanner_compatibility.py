from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCANNER = (
    PROJECT_ROOT
    / "tools"
    / "validation"
    / "ninjatrader"
    / "ScanMnq5mSourceInventory.cs"
)
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
SYSTEM_WEB_EXTENSIONS = Path(
    r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Web.Extensions.dll"
)
NINJATRADER_INSTALL = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / (
    "NinjaTrader 8"
)
CANONICALIZATION_ID = "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1"


def _scanner_source() -> str:
    assert SCANNER.is_file(), f"missing scanner source: {SCANNER}"
    return SCANNER.read_text(encoding="utf-8")


def _code_without_comments(source: str) -> str:
    return re.sub(r"//[^\r\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _method_body(source: str, method_name: str) -> str:
    match = re.search(
        rf"(?m)^\s*(?:public|private|protected|internal)\s+"
        rf"(?:(?:static|override|virtual|sealed|async|new)\s+)*"
        rf"[^;{{}}\r\n]+\b{re.escape(method_name)}\s*\([^;{{}}]*\)\s*\{{",
        source,
    )
    assert match is not None, f"missing method body: {method_name}"
    opening = source.find("{", match.start())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"unterminated method body: {method_name}")


def _ninjatrader_user_data() -> Path | None:
    candidates = (
        Path.home() / "Documents" / "NinjaTrader 8",
        Path.home() / "OneDrive" / "Documents" / "NinjaTrader 8",
        Path.home() / "OneDrive" / "文档" / "NinjaTrader 8",
        Path.home() / "OneDrive" / "鏂囨。" / "NinjaTrader 8",
    )
    return next(
        (
            candidate
            for candidate in candidates
            if (candidate / "bin" / "Custom" / "NinjaTrader.Custom.dll").is_file()
        ),
        None,
    )


def _prohibited_surface_findings(source: str) -> set[str]:
    code = _code_without_comments(source)
    findings: set[str] = set()
    checks = {
        "integration": r"\b(?:hierarchy|oracle|project|comparator)\b|\b(?:Run|Execute|Invoke)(?:Hierarchy|Oracle|Project|Comparator)\b",
        "policy-or-selection": r"\b(?:eligible|exclusion_reasons|selector|strata)\b|\b(?:Math\.)?Floor\s*\([^\r\n]*\*[^\r\n]*/\s*10(?:\.0)?\b",
        "structural-summary": r"\b(?:min(?:imum)?Price|max(?:imum)?Price|(?:price|session|bar)Range(?:Summary|Value)?|(?:simple|log)Return(?:Summary|Value)|Volatility(?:Summary|Value)?|Swing(?:Count|Summary)|TrendState|StructureDensity)\b",
    }
    for name, pattern in checks.items():
        if re.search(pattern, code, flags=re.IGNORECASE):
            findings.add(name)
    return findings


def test_scanner_declares_and_validates_the_frozen_ninjatrader_contract() -> None:
    """Catches runtime drift from the exact MNQ September 2026 identity."""
    source = _scanner_source()
    body = _method_body(source, "ValidateRuntimeSeries")

    assert "namespace NinjaTrader.NinjaScript.Indicators" in source
    assert re.search(
        r"public\s+class\s+ScanMnq5mSourceInventory\s*:\s*Indicator\b", source
    )
    for constant in (
        'private const string ApprovedContractLabel = "MNQ SEP26";',
        "private const int ApprovedExpiryMonth = 9;",
        "private const int ApprovedExpiryYear = 2026;",
        'private const string ApprovedRangeStart = "2026-06-22";',
        'private const string ApprovedRangeEnd = "2026-07-24";',
        "private const BarsPeriodType ApprovedBarsPeriodType = BarsPeriodType.Minute;",
        "private const int ApprovedBarsPeriodValue = 5;",
        'private const string ApprovedTradingHoursName = "CME US Index Futures ETH";',
        'private const string ScanFileName = "inventory_scan.json";',
        'private const string RuntimeFileName = "inventory_runtime_capture.json";',
        'private const string TradingHoursFileName = "trading_hours_template.xml";',
        'private const string ConfigFileName = "NinjaTrader.Config.xml";',
        f'"{CANONICALIZATION_ID}";',
    ):
        assert constant in source

    assert 'Instrument.MasterInstrument.Name != "MNQ"' in body
    assert "expiry.Month != ApprovedExpiryMonth" in body
    assert "expiry.Year != ApprovedExpiryYear" in body
    assert "BarsPeriod.BarsPeriodType != ApprovedBarsPeriodType" in body
    assert "BarsPeriod.Value != ApprovedBarsPeriodValue" in body
    assert "appliedTradingHours.Name != ApprovedTradingHoursName" in body
    assert "appliedTradingHours.TimeZoneInfo == null" in body
    assert "Calculate = Calculate.OnBarClose;" in source
    assert re.search(r"\bInstrument\.FullName\s*(?:==|!=)", source) is None

    inventory = _method_body(source, "BuildInventoryScan")
    runtime_capture = _method_body(source, "BuildRuntimeCapture")
    assert "timezone_id = appliedTradingHours.TimeZoneInfo.Id" in inventory
    assert "timezone_id = Bars.TradingHours.TimeZoneInfo.Id" in runtime_capture


def test_scanner_implements_all_task_three_private_units() -> None:
    """Catches omission of a required facts, hashing, publication, or capture unit."""
    source = _scanner_source()
    for method_name in (
        "ValidateRuntimeSeries",
        "TryArmAcquisition",
        "EnumerateCivilDates",
        "CaptureSessionObservation",
        "InspectSessionBars",
        "CanonicalizeBar",
        "Sha256CanonicalRows",
        "WriteBundleAtomically",
        "CaptureActiveConnections",
    ):
        assert re.search(rf"\bprivate\s+[^;\r\n]+\b{method_name}\s*\(", source)


def test_arm_and_output_guards_fail_closed() -> None:
    """Catches stale arms, ambiguous paths, mismatched IDs, and output overwrite."""
    source = _scanner_source()
    arm = _method_body(source, "TryArmAcquisition")
    runtime = _method_body(source, "ValidateRuntimeSeries")

    assert "Path.IsPathRooted(ArmFilePath)" in arm
    assert "Path.GetExtension(ArmFilePath)" in arm
    assert '".arm"' in arm
    assert "File.Exists(ArmFilePath)" in arm
    assert "File.GetLastWriteTimeUtc(ArmFilePath) <= initializedAtPc.UtcDateTime" in arm
    assert "File.ReadAllText(ArmFilePath).Trim() != AcquisitionId" in arm
    assert "Path.IsPathRooted(OutputDirectoryPath)" in runtime
    assert "Directory.Exists(OutputDirectoryPath)" in runtime
    assert "File.Exists(OutputDirectoryPath)" in runtime
    assert "Path.GetFileName" in runtime
    assert "MakeSafeFileName(AcquisitionId)" in runtime


def test_realtime_periodic_arm_poll_can_export_without_a_bar_update() -> None:
    """Catches making a post-Realtime arm depend on a later market bar."""
    source = _scanner_source()
    state_change = _method_body(source, "OnStateChange")
    start = _method_body(source, "StartArmPolling")
    timer_callback = _method_body(source, "PollForArm")
    marshaled_callback = _method_body(source, "ProcessArmPoll")

    assert "private System.Threading.Timer armPollTimer;" in source
    assert state_change.count("StartArmPolling();") == 1
    assert re.search(
        r"else if\s*\(State\s*==\s*State\.Realtime\)\s*\{"
        r"(?:(?!else if\s*\(State\s*==)[\s\S])*?StartArmPolling\(\);\s*\}",
        state_change,
    )
    assert "new System.Threading.Timer(" in start
    assert "PollForArm" in start
    assert "ArmPollIntervalMilliseconds" in start
    assert "TriggerCustomEvent(ProcessArmPoll, null);" in timer_callback
    assert "TryExportArmedAcquisition();" in marshaled_callback
    assert "PollForArm" not in _method_body(source, "OnBarUpdate")


def test_periodic_callback_marshals_before_using_ninjatrader_state() -> None:
    """Catches Bars/session/publication work escaping the NinjaScript context."""
    source = _scanner_source()
    timer_callback = _method_body(source, "PollForArm")

    assert "TriggerCustomEvent(ProcessArmPoll, null);" in timer_callback
    for unsafe_use in (
        "State",
        "Bars",
        "Instrument",
        "TryArmAcquisition",
        "CaptureSessionObservation",
        "WriteBundleAtomically",
        "LogScanComplete",
        "Log(",
        "Print(",
        "Core.",
        "Connection.",
        "File.",
        "Directory.",
    ):
        assert unsafe_use not in timer_callback


def test_bar_and_periodic_paths_share_one_single_shot_export_path() -> None:
    """Catches duplicate publication logic or a race between callback paths."""
    source = _scanner_source()
    update = _method_body(source, "OnBarUpdate")
    marshaled_callback = _method_body(source, "ProcessArmPoll")
    export = _method_body(source, "TryExportArmedAcquisition")

    assert "TryExportArmedAcquisition();" in update
    assert "TryExportArmedAcquisition();" in marshaled_callback
    for duplicated_call in (
        "TryArmAcquisition",
        "CaptureActiveConnections",
        "CaptureSessionObservation",
        "WriteBundleAtomically",
        "LogScanComplete",
    ):
        assert duplicated_call not in update
        assert duplicated_call not in marshaled_callback
        assert duplicated_call in export
    assert re.search(
        r"Interlocked\.CompareExchange\(ref exportStarted, 1, 0\)\s*!=\s*0",
        export,
    )
    no_arm = export[export.index("if (!armAccepted)") :]
    assert "Interlocked.Exchange(ref exportStarted, 0);" in no_arm


def test_arm_validation_exception_releases_gate_for_a_corrected_later_arm() -> None:
    """Catches an invalid arm permanently blocking a later valid arm export."""
    export = _method_body(_scanner_source(), "TryExportArmedAcquisition")

    assert export.count("TryArmAcquisition()") == 1
    guarded_validation = re.search(
        r"bool\s+armAccepted\s*;\s*"
        r"try\s*\{\s*armAccepted\s*=\s*TryArmAcquisition\(\)\s*;\s*\}\s*"
        r"catch\s*\{\s*"
        r"Interlocked\.Exchange\(ref\s+exportStarted,\s*0\)\s*;\s*"
        r"throw\s*;\s*\}",
        export,
    )
    assert guarded_validation is not None
    assert guarded_validation.end() < export.index("if (!armAccepted)")


def test_arm_poll_timer_is_published_disabled_before_it_can_fire() -> None:
    """Catches a zero-due timer escaping disposal before field publication."""
    source = _scanner_source()
    start = _method_body(source, "StartArmPolling")
    stop = _method_body(source, "StopArmPolling")

    assert "private readonly object armPollLifecycleLock = new object();" in source
    assert "lock (armPollLifecycleLock)" in start
    assert "lock (armPollLifecycleLock)" in stop
    assert re.search(
        r"new\s+System\.Threading\.Timer\(\s*"
        r"PollForArm,\s*null,\s*Timeout\.Infinite,\s*Timeout\.Infinite\s*\)",
        start,
    )
    assert start.index("armPollTimer = timer;") < start.index(
        "timer.Change(0, ArmPollIntervalMilliseconds);"
    )
    assert "Interlocked.Exchange(ref armPollTimer, null)" in stop
    assert "timer.Dispose();" in stop


def test_arm_polling_is_disposed_after_export_and_on_termination() -> None:
    """Catches a polling leak after publication or NinjaScript termination."""
    source = _scanner_source()
    state_change = _method_body(source, "OnStateChange")
    stop = _method_body(source, "StopArmPolling")
    export = _method_body(source, "TryExportArmedAcquisition")

    assert re.search(
        r"State\s*==\s*State\.Terminated[\s\S]*?StopArmPolling\(\);",
        state_change,
    )
    assert "Interlocked.Exchange(ref armPollActive, 0);" in stop
    assert "Interlocked.Exchange(ref armPollTimer, null)" in stop
    assert "timer.Dispose();" in stop
    assert export.index("LogScanComplete();") < export.index("StopArmPolling();")


def test_civil_date_enumeration_is_inclusive_and_has_no_weekday_filter() -> None:
    """Catches skipped weekends or either missing policy boundary."""
    source = _scanner_source()
    body = _method_body(source, "EnumerateCivilDates")

    assert "ApprovedRangeStart" in body
    assert "ApprovedRangeEnd" in body
    assert "date <= end" in body
    assert "date.AddDays(1)" in body
    assert ".DayOfWeek" not in source
    assert '(end - start).Days + 1 != 33' in body


def test_session_observation_uses_exchange_date_and_exact_schedule_evidence() -> None:
    """Catches weekday inference or loss of objective session representations."""
    source = _scanner_source()
    body = _method_body(source, "CaptureSessionObservation")

    assert "new SessionIterator(Bars)" in body
    assert "ActualTradingDayExchange.Date" in body
    assert "ActualSessionBegin" in body
    assert "ActualSessionEnd" in body
    for key in (
        '"civil_date"',
        '"classification"',
        '"exchange_trading_date"',
        '"schedule_evidence"',
        '"quality"',
        "expected_open_segments",
        "scheduled_breaks",
        "application_session_begin",
        "application_session_end",
        "pc_log_session_begin",
        "pc_log_session_end",
        "holiday_name",
        "partial_session",
    ):
        assert key in body
    assert '"NO_SESSION"' in body
    assert '"SESSION"' in body


def test_session_observation_reads_full_and_partial_holiday_runtime_facts() -> None:
    """Catches fabricated null holiday/shortened-session schedule evidence."""
    source = _scanner_source()
    observation = _method_body(source, "CaptureSessionObservation")
    resolver = _method_body(source, "ResolveScheduleMetadata")

    assert re.search(
        r"ResolveScheduleMetadata\(\s*appliedTradingHours,\s*civilDate\.Date\s*\)",
        observation,
    )
    assert "holiday_name = scheduleMetadata.HolidayName" in observation
    assert "partial_session = scheduleMetadata.PartialSession" in observation
    assert "appliedTradingHours.Holidays" in resolver
    assert "appliedTradingHours.PartialHolidays" in resolver
    assert "TryGetValue" in resolver
    assert "partialHoliday.Description" in resolver
    assert "holiday_name = (string)null" not in observation
    assert "partial_session = (bool?)null" not in observation


@pytest.mark.skipif(
    shutil.which("powershell.exe") is None,
    reason="Windows PowerShell is unavailable",
)
def test_runtime_schedule_metadata_resolver_reports_full_and_partial_holidays(
    tmp_path: Path,
) -> None:
    """Exercises the production resolver with installed NinjaTrader schedule types."""
    user_data = _ninjatrader_user_data()
    core = NINJATRADER_INSTALL / "bin" / "NinjaTrader.Core.dll"
    gui = NINJATRADER_INSTALL / "bin" / "NinjaTrader.Gui.dll"
    required = (CSC, SYSTEM_WEB_EXTENSIONS, core, gui)
    if user_data is None or not all(path.is_file() for path in required):
        pytest.skip("the installed NinjaTrader compile environment is unavailable")

    scanner_dll = tmp_path / "ScanMnq5mSourceInventory.dll"
    framework = CSC.parent
    references = (
        framework / "System.dll",
        framework / "System.Core.dll",
        framework / "System.ComponentModel.DataAnnotations.dll",
        SYSTEM_WEB_EXTENSIONS,
        framework / "WPF" / "WindowsBase.dll",
        framework / "WPF" / "PresentationCore.dll",
        framework / "WPF" / "PresentationFramework.dll",
        core,
        gui,
        user_data / "bin" / "Custom" / "NinjaTrader.Custom.dll",
    )
    compiled = subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/codepage:65001",
            "/target:library",
            f"/out:{scanner_dll}",
            *(f"/reference:{path}" for path in references),
            str(SCANNER),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    custom = user_data / "bin" / "Custom" / "NinjaTrader.Custom.dll"
    script = rf'''
$ErrorActionPreference = "Stop"
[Reflection.Assembly]::LoadFrom("{core}") | Out-Null
[Reflection.Assembly]::LoadFrom("{gui}") | Out-Null
[Reflection.Assembly]::LoadFrom("{custom}") | Out-Null
$scannerAssembly = [Reflection.Assembly]::LoadFrom("{scanner_dll}")
$scannerType = $scannerAssembly.GetType("NinjaTrader.NinjaScript.Indicators.ScanMnq5mSourceInventory", $true)
$method = $scannerType.GetMethod("ResolveScheduleMetadata", [Reflection.BindingFlags] "NonPublic,Static")
if ($null -eq $method) {{ throw "missing ResolveScheduleMetadata" }}

$fullDate = [DateTime] "2026-07-03"
$fullHours = [NinjaTrader.Data.TradingHours]::new()
$fullHours.Holidays.Add($fullDate, "Full Holiday")
$fullResult = $method.Invoke($null, [object[]] @($fullHours, $fullDate))
Write-Output ("FULL|" + $fullResult.HolidayName + "|" + $fullResult.PartialSession)

$partialDate = [DateTime] "2026-07-02"
$partialHours = [NinjaTrader.Data.TradingHours]::new()
$partial = [NinjaTrader.Data.PartialHoliday]::new()
$partial.Date = $partialDate
$partial.Description = "Shortened Session"
$partial.IsEarlyEnd = $true
$partialHours.PartialHolidays.Add($partialDate, $partial)
$partialResult = $method.Invoke($null, [object[]] @($partialHours, $partialDate))
Write-Output ("PARTIAL|" + $partialResult.HolidayName + "|" + $partialResult.PartialSession)
'''
    executed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert executed.returncode == 0, executed.stdout + executed.stderr
    assert executed.stdout.splitlines() == [
        "FULL|Full Holiday|False",
        "PARTIAL|Shortened Session|True",
    ]


def test_native_bar_inspection_records_complete_supplied_order_quality() -> None:
    """Catches silent repair or omission of a design-required quality fact."""
    source = _scanner_source()
    body = _method_body(source, "InspectSessionBars")

    for read in (
        "Bars.GetTime(index)",
        "Bars.GetOpen(index)",
        "Bars.GetHigh(index)",
        "Bars.GetLow(index)",
        "Bars.GetClose(index)",
        "Bars.GetVolume(index)",
    ):
        assert read in body
    assert "for (int index = 0; index < Bars.Count; index++)" in body
    assert "if (!IsWithinSessionBounds(timestamp, segments))" in body
    assert "IsExpectedSessionTimestamp(timestamp, segments)" not in body
    assert (
        "bars[validFromSessionStart].Timestamp\n"
        "                    != expectedTimestamps[validFromSessionStart]"
    ) in body
    assert not re.search(r"\.(?:Sort|OrderBy|OrderByDescending|Distinct)\s*\(", body)
    assert "TimeZoneInfo.ConvertTime" not in body
    for key in (
        "observed_native_five_minute_bar_count",
        "observed_valid_count_from_session_start",
        "first_observed_timestamp",
        "two_hundred_fiftieth_native_timestamp",
        "last_observed_session_timestamp",
        "supplied_order_strictly_increasing",
        "duplicate_timestamp_indexes",
        "duplicate_timestamp_count",
        "decreasing_timestamp_indexes",
        "decreasing_timestamp_count",
        "missing_expected_open_timestamps",
        "missing_expected_open_timestamp_count",
        "unexpected_timestamps",
        "unexpected_timestamp_count",
        "malformed_or_non_finite_ohlcv_indexes",
        "malformed_or_non_finite_ohlcv_count",
        "invalid_ohlc_geometry_indexes",
        "invalid_ohlc_geometry_count",
        "negative_volume_indexes",
        "negative_volume_count",
        "non_integral_volume_indexes",
        "non_integral_volume_count",
        "first_250_source_sha256",
        "complete_session_source_sha256",
        "canonicalization_id",
    ):
        assert key in body


def test_canonicalization_and_hashing_match_the_selected_case_bytes() -> None:
    """Catches culture, newline, BOM, ordering, or final-newline drift."""
    source = _scanner_source()
    canonicalize = _method_body(source, "CanonicalizeBar")
    hashing = _method_body(source, "Sha256CanonicalRows")

    assert 'ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture)' in canonicalize
    assert canonicalize.count('ToString("R", CultureInfo.InvariantCulture)') == 4
    assert "Volume.ToString(CultureInfo.InvariantCulture)" in canonicalize
    assert re.search(r'string\.Join\(\s*";",', canonicalize)
    assert 'string.Join("\\n", rows) + "\\n"' in hashing
    assert "new UTF8Encoding(false)" in hashing
    assert "SHA256.Create()" in hashing
    assert ".OrderBy" not in hashing and ".Sort(" not in hashing

    rows = [
        "20260622 170500;1;2;0.5;1.5;10",
        "20260622 171000;1.5;2.5;1;2;11",
    ]
    canonical = ("\n".join(rows) + "\n").encode("utf-8")
    assert canonical[:3] != b"\xef\xbb\xbf"
    assert b"\r" not in canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "b7b0410624b07ecddb6a524fb54f898ad999db2f2c3884e06f49faff89ec5dca"
    )


def test_first_250_hash_uses_canonical_rows_not_eligibility_valid_prefix() -> None:
    """Catches suppressing an available identity hash for finite defect rows."""
    body = _method_body(_scanner_source(), "InspectSessionBars")

    assert re.search(
        r"if\s*\(bar\.HasFiniteOhlcv\)\s*"
        r"bar\.CanonicalRow\s*=\s*CanonicalizeBar\(bar\);",
        body,
    )
    assert "bar.HasFiniteOhlcv\n                    && (bar.Low > bar.High" in body

    first_hash = body[
        body.index("string first250Hash = null;") : body.index("string completeHash = null;")
    ]
    assert re.search(r"if\s*\(bars\.Count\s*>=\s*250\)", first_hash)
    assert re.search(
        r"bars\.Take\(250\)\.Select\(value\s*=>\s*value\.CanonicalRow\)",
        first_hash,
    )
    assert "validFromSessionStart" not in first_hash


@pytest.mark.skipif(
    not (CSC.is_file() and SYSTEM_WEB_EXTENSIONS.is_file()),
    reason="the installed .NET Framework serializer compiler is unavailable",
)
def test_standard_serializer_emits_strict_inventory_shapes(tmp_path: Path) -> None:
    """Catches accidental extra keys and SESSION/NO_SESSION shape conflation."""
    program = tmp_path / "SerializeInventoryScan.cs"
    executable = tmp_path / "SerializeInventoryScan.exe"
    program.write_text(
        r'''
using System;
using System.Collections.Generic;
using System.Text;
using System.Web.Script.Serialization;

public static class SerializeInventoryScan
{
    public static void Main()
    {
        object schedule = new
        {
            holiday_name = (string)null,
            partial_session = (bool?)null,
            expected_open_segments = new object[0],
            scheduled_breaks = new object[0],
            application_session_begin = (string)null,
            application_session_end = (string)null,
            pc_log_session_begin = (string)null,
            pc_log_session_end = (string)null,
            effective_schedule_source = "SessionIterator using Bars.TradingHours"
        };
        object quality = new
        {
            observed_native_five_minute_bar_count = 0,
            observed_valid_count_from_session_start = 0,
            first_observed_timestamp = (string)null,
            two_hundred_fiftieth_native_timestamp = (string)null,
            last_observed_session_timestamp = (string)null,
            supplied_order_strictly_increasing = true,
            duplicate_timestamp_indexes = new int[0],
            duplicate_timestamp_count = 0,
            decreasing_timestamp_indexes = new int[0],
            decreasing_timestamp_count = 0,
            missing_expected_open_timestamps = new string[0],
            missing_expected_open_timestamp_count = 0,
            unexpected_timestamps = new string[0],
            unexpected_timestamp_count = 0,
            malformed_or_non_finite_ohlcv_indexes = new int[0],
            malformed_or_non_finite_ohlcv_count = 0,
            invalid_ohlc_geometry_indexes = new int[0],
            invalid_ohlc_geometry_count = 0,
            negative_volume_indexes = new int[0],
            negative_volume_count = 0,
            non_integral_volume_indexes = new int[0],
            non_integral_volume_count = 0,
            first_250_source_sha256 = (string)null,
            complete_session_source_sha256 = (string)null,
            canonicalization_id = "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1"
        };
        object scan = new
        {
            schema_version = "1.0",
            acquisition_id = "dryrun-mnq-202609-5m-inventory-20260622-20260724-v1",
            cohort_id = "mnq-202609-5m-v1",
            contract = new { },
            bar_series = new { },
            trading_hours = new { },
            civil_date_start = "2026-06-22",
            civil_date_end = "2026-07-24",
            canonicalization_id = "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1",
            observations = new object[]
            {
                new Dictionary<string, object>
                {
                    { "civil_date", "2026-06-27" },
                    { "classification", "NO_SESSION" },
                    { "exchange_trading_date", null },
                    { "schedule_evidence", schedule },
                    { "quality", null }
                },
                new Dictionary<string, object>
                {
                    { "civil_date", "2026-06-22" },
                    { "classification", "SESSION" },
                    { "exchange_trading_date", "2026-06-22" },
                    { "schedule_evidence", schedule },
                    { "quality", quality }
                }
            },
            transformations = new { },
            completed_at = "2026-09-16T12:00:00+08:00"
        };
        Console.OutputEncoding = new UTF8Encoding(false);
        Console.Write(new JavaScriptSerializer().Serialize(scan));
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
    payload = json.loads(
        subprocess.run(
            [str(executable)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        ).stdout
    )

    assert set(payload) == {
        "schema_version",
        "acquisition_id",
        "cohort_id",
        "contract",
        "bar_series",
        "trading_hours",
        "civil_date_start",
        "civil_date_end",
        "canonicalization_id",
        "observations",
        "transformations",
        "completed_at",
    }
    assert payload["canonicalization_id"] == CANONICALIZATION_ID
    assert set(payload["observations"][0]) == {
        "civil_date",
        "classification",
        "exchange_trading_date",
        "schedule_evidence",
        "quality",
    }
    assert payload["observations"][0]["exchange_trading_date"] is None
    assert payload["observations"][0]["quality"] is None
    assert payload["observations"][1]["classification"] == "SESSION"
    assert set(payload["observations"][1]["quality"]) == {
        "observed_native_five_minute_bar_count",
        "observed_valid_count_from_session_start",
        "first_observed_timestamp",
        "two_hundred_fiftieth_native_timestamp",
        "last_observed_session_timestamp",
        "supplied_order_strictly_increasing",
        "duplicate_timestamp_indexes",
        "duplicate_timestamp_count",
        "decreasing_timestamp_indexes",
        "decreasing_timestamp_count",
        "missing_expected_open_timestamps",
        "missing_expected_open_timestamp_count",
        "unexpected_timestamps",
        "unexpected_timestamp_count",
        "malformed_or_non_finite_ohlcv_indexes",
        "malformed_or_non_finite_ohlcv_count",
        "invalid_ohlc_geometry_indexes",
        "invalid_ohlc_geometry_count",
        "negative_volume_indexes",
        "negative_volume_count",
        "non_integral_volume_indexes",
        "non_integral_volume_count",
        "first_250_source_sha256",
        "complete_session_source_sha256",
        "canonicalization_id",
    }


def test_scanner_source_builds_the_strict_inventory_document_shape() -> None:
    """Catches production serialization drifting from the strict harness shape."""
    source = _scanner_source()
    body = _method_body(source, "BuildInventoryScan")
    for key in (
        "schema_version",
        "acquisition_id",
        "cohort_id",
        "contract",
        "bar_series",
        "trading_hours",
        "civil_date_start",
        "civil_date_end",
        "canonicalization_id",
        "observations",
        "transformations",
        "completed_at",
    ):
        assert re.search(rf"\b{key}\s*=", body)
    assert "new JavaScriptSerializer().Serialize" in source
    assert "canonical_rows" not in body
    assert "raw_ohlcv" not in body


def test_atomic_bundle_publication_precedes_completion_marker() -> None:
    """Catches direct JSON writes, partial final publication, or early completion."""
    source = _scanner_source()
    write = _method_body(source, "WriteBundleAtomically")
    export = _method_body(source, "TryExportArmedAcquisition")

    assert "Directory.Exists(OutputDirectoryPath)" in write
    assert "Directory.CreateDirectory(stagingDirectory)" in write
    assert "WriteJsonAtomically" in write
    assert "File.Copy(tradingHoursSource, tradingHoursDestination, false)" in write
    assert "File.Copy(configSource, configDestination, false)" in write
    assert "Directory.Move(stagingDirectory, OutputDirectoryPath)" in write
    for file_name in (
        "ScanFileName",
        "RuntimeFileName",
        "TradingHoursFileName",
        "ConfigFileName",
    ):
        assert file_name in write
    assert "File.Move(temporaryPath, finalPath)" in _method_body(
        source, "WriteJsonAtomically"
    )
    assert export.index("WriteBundleAtomically") < export.index("LogScanComplete")
    assert "LogScanComplete();" in export
    assert "LogScanComplete(completedAtPc)" not in export

    completion = _method_body(source, "LogScanComplete")
    assert "DateTimeOffset completedAtPc = DateTimeOffset.Now;" in completion
    assert re.search(r"private\s+void\s+LogScanComplete\s*\(\s*\)", source)

    move_index = write.index("Directory.Move(stagingDirectory, OutputDirectoryPath)")
    assert write.index("VerifyPublishedBundle(OutputDirectoryPath)") > move_index


def test_failed_atomic_publication_removes_only_its_staging_directory() -> None:
    """Catches abandoned partial evidence without weakening final-path refusal."""
    write = _method_body(_scanner_source(), "WriteBundleAtomically")

    assert "bool published = false;" in write
    assert "try" in write and "finally" in write
    assert "published = true;" in write
    assert "if (!published && Directory.Exists(stagingDirectory))" in write
    assert "Directory.Delete(stagingDirectory, true);" in write


def test_runtime_capture_is_objective_and_binds_all_task_three_outputs() -> None:
    """Catches missing hashes/connections or an improper provider/policy assertion."""
    source = _scanner_source()
    runtime = _method_body(source, "BuildRuntimeCapture")
    connections = _method_body(source, "CaptureActiveConnections")
    export = _method_body(source, "TryExportArmedAcquisition")

    top_level_keys = set(
        re.findall(r"(?m)^ {16}([a-z][a-z0-9_]*)\s*=", runtime)
    )
    assert top_level_keys == {
        "schema_version",
        "acquisition_id",
        "cohort_id",
        "instrument",
        "ninjatrader_version",
        "scanner_identity",
        "bar_series",
        "application_timezone",
        "pc_timezone",
        "trading_hours",
        "active_connections",
        "connection_snapshot_phase",
        "lifecycle",
        "artifact_hashes",
    }
    for key in (
        "instrument",
        "scanner_identity",
        "bar_series",
        "application_timezone",
        "pc_timezone",
        "active_connections",
        "lifecycle",
        "artifact_hashes",
        "inventory_scan",
        "inventory_runtime_capture",
        "trading_hours_template",
        "ninjatrader_config",
        "file_name",
        "sha256",
        "scanner_sha256",
        "scanner_sha256_recording_authority",
        "connection_snapshot_phase",
    ):
        assert key in runtime
    assert export.index("CaptureActiveConnections") < export.index(
        "CaptureSessionObservation"
    )
    assert "Connection.Connections" in connections
    assert "ConnectionStatus.Connected" in connections
    assert "provider_proven" not in runtime
    assert "eligib" not in runtime.lower()
    assert "exclusion" not in runtime.lower()


def test_scanner_remains_blind_and_does_not_export_candidate_rows() -> None:
    """Catches policy, market-structure, selected-source, or raw-row leakage."""
    source = _scanner_source()
    code = _code_without_comments(source)
    assert "bars.txt" not in code
    assert _prohibited_surface_findings(source) == set()
    assert not re.search(
        r"\b(?:canonical|raw)_rows\s*=", _method_body(source, "BuildInventoryScan")
    )


@pytest.mark.parametrize(
    ("source", "expected_finding"),
    (
        ("RunOracle();", "integration"),
        ("int start = (int)Math.Floor(index * dates.Count / 10.0);", "policy-or-selection"),
        ("bool eligible = true;", "policy-or-selection"),
        ("string[] exclusion_reasons = reasons;", "policy-or-selection"),
        ("double minPrice = Low[0];", "structural-summary"),
        ("double maxPrice = High[0];", "structural-summary"),
        ("double priceRange = highest - lowest;", "structural-summary"),
        ("double volatilityValue = variance;", "structural-summary"),
        ("int swingCount = 0;", "structural-summary"),
        ("string trendState = state;", "structural-summary"),
    ),
)
def test_prohibited_surface_checks_reject_realistic_mutations(
    source: str, expected_finding: str
) -> None:
    """Proves forbidden behavior checks fail on realistic mutations."""
    assert expected_finding in _prohibited_surface_findings(source)


def test_prohibited_surface_checks_ignore_comments_and_partial_words() -> None:
    """Keeps word-boundary checks from rejecting comments or benign identifiers."""
    assert _prohibited_surface_findings(
        "// RunOracle(); hierarchy comparator\nstring projected = \"projected\";"
    ) == set()


def test_property_annotations_remain_contiguous_with_their_declarations() -> None:
    """Catches a later property borrowing a preceding NinjaScript attribute."""
    source = _scanner_source()
    for property_name, display_name in (
        ("AcquisitionId", "Acquisition ID"),
        ("CohortId", "Cohort ID"),
        ("ArmFilePath", "Operator arm file"),
        ("OutputDirectoryPath", "Output directory"),
    ):
        declaration = rf"public string {property_name} {{ get; set; }}"
        pattern = rf"\[NinjaScriptProperty\]\s*\[Display\([^\]]*\)\]\s*{re.escape(declaration)}"
        assert re.search(pattern, source)
        mutated = source.replace(
            "[NinjaScriptProperty]\n" + f'        [Display(Name = "{display_name}",',
            f'[Display(Name = "{display_name}",',
            1,
        )
        assert re.search(pattern, mutated) is None


def test_scanner_compiles_against_installed_ninjatrader_references(
    tmp_path: Path,
) -> None:
    """Catches API or language constructs unsupported by installed NinjaTrader."""
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
        user_data / "bin" / "Custom" / "NinjaTrader.Custom.dll",
    )
    compiled = subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/codepage:65001",
            "/target:library",
            f"/out:{tmp_path / 'ScanMnq5mSourceInventory.dll'}",
            *(f"/reference:{path}" for path in references),
            str(SCANNER),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
