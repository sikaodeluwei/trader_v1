"""OFFLINE_TEST_ONLY actual-exporter regression; no live NT or official evidence.

The fixtures redirect the desktop boundary beneath pytest tmp_path and supply
inert data/provider/calendar dependencies. The real exporter source is compiled
unchanged. A manually drained custom-event queue does not validate NT dispatch.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs"
FIXTURE = ROOT / "tests/fixtures/exporter_behavior_offline.cs"
FRAMEWORK = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319")
CSC = FRAMEWORK / "csc.exe"


@pytest.fixture(scope="module")
def executable(tmp_path_factory):
    if not CSC.is_file():
        pytest.skip("installed .NET Framework compiler unavailable")
    path = tmp_path_factory.mktemp("OFFLINE_TEST_ONLY_exporter_compile") / "ExporterBehavior.exe"
    command = [
        str(CSC), "/nologo", "/codepage:65001", f"/out:{path}",
        f"/reference:{FRAMEWORK / 'System.Web.Extensions.dll'}",
        f"/reference:{FRAMEWORK / 'System.ComponentModel.DataAnnotations.dll'}",
        str(EXPORTER), str(FIXTURE),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stdout + result.stderr
    return path


def run(executable, scenario, tmp_path):
    result = subprocess.run(
        [str(executable), scenario, str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def check_normal_bundle(tmp_path):
    root = tmp_path / "desktop/MNQ_5m_Acquisitions/OFFLINE_TEST_ONLY_after_request"
    source = (root / "bars.txt").read_bytes()
    # Hand-defined native fixture chronology: first available closed bar 17:05,
    # 250 bars ending 13:50; Count-2 mapping deliberately preserves old logic.
    start = datetime(2026, 6, 30, 17, 0)
    expected = "".join(
        f"{start + timedelta(minutes=5*i):%Y%m%d %H%M%S};{100+i};{102+i};{99+i};{100+i}.5;{1000+i}\n"
        for i in range(1, 251)
    ).encode("utf-8")
    assert source == expected
    assert len(source.splitlines()) == 250
    assert source.splitlines()[0] == b"20260630 170500;101;103;100;101.5;1001"
    assert source.splitlines()[-1] == b"20260701 135000;350;352;349;350.5;1250"
    assert b"\r" not in source and source.endswith(b"\n") and not source.startswith(b"\xef\xbb\xbf")
    runtime = json.loads((root / "runtime_capture.json").read_bytes())
    assert runtime["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert runtime["bar_series"]["exported_bar_count"] == 250
    assert runtime["connection_snapshot_phase"] == "immediately after operator arm and before export"
    assert runtime["active_connections"] == [{
        "name": "OFFLINE_TEST_ONLY", "provider": "OFFLINE_TEST_ONLY",
        "status": "Connected", "price_status": "Connected", "instrument_types": ["Future"],
    }]
    assert runtime["trading_hours"]["definition_sha256"] == hashlib.sha256(b"<OFFLINE_TEST_ONLY />").hexdigest()
    calendar = runtime["trading_hours"]["session_calendar"][0]
    assert calendar["effective_schedule_source"] == "SessionIterator using Bars.TradingHours"
    segment = calendar["segments"][0]
    assert segment["begin_application"] == "2026-06-30T17:00:00.0000000-05:00"
    assert segment["end_application"] == "2026-07-01T16:00:00.0000000-05:00"
    assert datetime.fromisoformat(segment["begin_pc"]) == datetime.fromisoformat(segment["begin_application"])
    assert runtime["application_timezone"]["source_timestamp_offsets"] == [{
        "first_timestamp": "20260630 170500", "last_timestamp": "20260701 135000", "utc_offset": "-05:00",
    }]


def test_actual_normal_exporter_path_and_canonical_bundle(executable, tmp_path):
    run(executable, "normal", tmp_path)
    check_normal_bundle(tmp_path)


def test_late_arm_exports_without_any_market_callback(executable, tmp_path):
    result = run(executable, "late", tmp_path)
    assert "market_callbacks=0" in result.stdout
    assert " arm poll export completed realtime_bar_callbacks_since_initialized=0 " in result.stdout
    check_normal_bundle(tmp_path)


@pytest.mark.parametrize("scenario", [
    "race", "missing", "stale", "wrong_id", "unreadable", "terminate",
    "existing", "partial", "no_lifecycle", "bounded", "readiness",
    "termination_publication", "termination_dispatch", "historical_pause", "dispatcher_refusal",
    "historical_resume_pending", "poll_after_market",
])
def test_actual_exporter_guards_and_lifecycle(executable, scenario, tmp_path):
    run(executable, scenario, tmp_path)
