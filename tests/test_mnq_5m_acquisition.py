from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tools.validation.mnq_5m_acquisition import (
    AcquisitionValidationError,
    finalize_provenance,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp_text(value: datetime) -> str:
    return value.strftime("%Y%m%d %H%M%S")


def _expected_timestamps() -> list[datetime]:
    first_begin = datetime(2026, 6, 22, 0, 0)
    first_end = datetime(2026, 6, 22, 10, 0)
    second_begin = datetime(2026, 6, 22, 10, 30)
    second_end = datetime(2026, 6, 22, 21, 30)
    result: list[datetime] = []
    for begin, end in (
        (first_begin, first_end),
        (second_begin, second_end),
    ):
        current = begin + timedelta(minutes=5)
        while current <= end:
            result.append(current)
            current += timedelta(minutes=5)
    return result[:250]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _build_bundle(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    timestamps = _expected_timestamps()
    source = tmp_path / "bars.txt"
    rows = []
    for index, timestamp in enumerate(timestamps):
        volume = "0" if index == 0 else str(100 + index)
        rows.append(
            f"{_timestamp_text(timestamp)};100.00;101.25;99.50;100.75;{volume}"
        )
    source.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")

    exporter = tmp_path / "ExportMnq5mCohortSource.cs"
    exporter.write_text("// frozen exporter fixture\n", encoding="utf-8")
    trace = tmp_path / "trace.txt"
    trace.write_text(
        "2026-06-21 23:46:00.000 acquisition=acq-001 exporter initialized "
        "event_time=2026-06-21T23:46:00+08:00\n"
        "2026-06-21 23:50:00.000 (Live) "
        "Tradovate.Adapter.Connect status=Connected\n"
        "2026-06-21 23:55:00.000 Reload All Historical Data initiated\n"
        "2026-06-21 23:56:00.000 "
        "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26'\n"
        "2026-06-22 21:30:59.000 acquisition=acq-001 export armed after reload "
        "event_time=2026-06-22T21:30:59+08:00\n"
        "2026-06-22 21:31:00.000 acquisition=acq-001 export complete "
        "event_time=2026-06-22T21:31:00+08:00\n",
        encoding="utf-8",
    )
    log = tmp_path / "log.txt"
    log.write_text(
        "2026-06-21 23:50:00.000 acquisition=acq-001 "
        "provider=Tradovate connection=Live status=Connected\n",
        encoding="utf-8",
    )
    config = tmp_path / "Config.xml"
    config.write_text(
        "<NinjaTrader><PreferredFutureConnection>Live</PreferredFutureConnection>"
        "<PreferredRealtimeFutureConnection>Live</PreferredRealtimeFutureConnection>"
        "</NinjaTrader>\n",
        encoding="utf-8",
    )
    hours = tmp_path / "CME US Index Futures ETH.xml"
    hours.write_text("<TradingHours name='CME US Index Futures ETH' />\n", encoding="utf-8")
    selection_registry = tmp_path / "selection_registry.json"
    selection_registry.write_text("{\"status\": \"synthetic-fixture\"}\n", encoding="utf-8")
    toolset_manifest = tmp_path / "toolset_manifest.json"
    toolset_manifest.write_text("{\"status\": \"synthetic-fixture\"}\n", encoding="utf-8")

    runtime = {
        "schema_version": "1.0",
        "acquisition_id": "acq-001",
        "cohort_id": "mnq-202609-5m-v1",
        "case_id": "mnq-202609-5m-td2026-06-22-w01",
        "trading_date": "2026-06-22",
        "instrument": {
            "contract_label": "MNQ SEP26",
            "full_name": "MNQ 09-26",
            "master_name": "MNQ",
            "instrument_id": "MNQ 09-26",
            "expiry_month": 9,
            "expiry_year": 2026,
            "exchange": "CME",
        },
        "ninjatrader_version": "8.1.5.2",
        "export_method": "ExportMnq5mCohortSource NinjaTrader indicator",
        "original_export_identity": "acq-001/bars.txt",
        "bar_series": {
            "type": "Minute",
            "value": 5,
            "native": True,
            "exported_bar_count": 250,
            "timestamp_semantics": (
                "Time[0] clock values displayed in the NinjaTrader application timezone"
            ),
        },
        "application_timezone": {
            "id": "Singapore Standard Time",
            "display_name": "(UTC+08:00) Kuala Lumpur, Singapore",
            "standard_name": "Singapore Standard Time",
            "daylight_name": "Singapore Daylight Time",
            "base_utc_offset": "+08:00",
            "supports_dst": False,
            "source_timestamp_offsets": [
                {
                    "first_timestamp": _timestamp_text(timestamps[0]),
                    "last_timestamp": _timestamp_text(timestamps[-1]),
                    "utc_offset": "+08:00",
                }
            ],
        },
        "pc_timezone": {
            "id": "Singapore Standard Time",
            "base_utc_offset": "+08:00",
            "supports_dst": False,
            "acquisition_event_offsets": [
                {
                    "event": "initialized",
                    "timestamp": "2026-06-21T23:46:00+08:00",
                    "utc_offset": "+08:00",
                },
                {
                    "event": "armed",
                    "timestamp": "2026-06-22T21:30:59+08:00",
                    "utc_offset": "+08:00",
                },
                {
                    "event": "exported",
                    "timestamp": "2026-06-22T21:31:00+08:00",
                    "utc_offset": "+08:00",
                },
            ],
        },
        "trading_hours": {
            "name": "CME US Index Futures ETH",
            "timezone_id": "Central Standard Time",
            "definition_sha256": _sha256(hours),
            "holiday_configuration_captured": True,
            "session_calendar": [
                {
                    "trading_date": "2026-06-22",
                    "segments": [
                        {
                            "begin_application": "20260622 000000",
                            "end_application": "20260622 100000",
                            "begin_pc": "20260622 000000",
                            "end_pc": "20260622 100000",
                        },
                        {
                            "begin_application": "20260622 103000",
                            "end_application": "20260622 213000",
                            "begin_pc": "20260622 103000",
                            "end_pc": "20260622 213000",
                        },
                    ],
                    "holiday_name": None,
                    "partial_holiday": False,
                }
            ],
        },
        "active_connections": [
            {
                "name": "Live",
                "provider": "Tradovate",
                "status": "Connected",
                "price_status": "Connected",
                "instrument_types": ["Future"],
            }
        ],
        "connection_snapshot_phase": "immediately after operator arm and before export",
        "exported_at": "2026-06-22T21:31:00+08:00",
        "source_sha256": _sha256(source),
    }
    runtime_path = tmp_path / "runtime_capture.json"
    _write_json(runtime_path, runtime)

    evidence = {
        "schema_version": "1.0",
        "acquisition_id": "acq-001",
        "cohort_id": "mnq-202609-5m-v1",
        "case_id": "mnq-202609-5m-td2026-06-22-w01",
        "trading_date": "2026-06-22",
        "intended_provider": "Tradovate",
        "intended_connection_name": "Live",
        "log_timezone_id": "Singapore Standard Time",
        "log_utc_offset": "+08:00",
        "acquisition_started_at": "2026-06-21T23:45:00+08:00",
        "reload_all_historical_data_initiated_at": "2026-06-21T23:55:00+08:00",
        "export_armed_at": "2026-06-22T21:30:59+08:00",
        "export_completed_at": "2026-06-22T21:31:00+08:00",
        "runtime_capture_sha256": _sha256(runtime_path),
        "exporter_sha256": _sha256(exporter),
        "evidence_files": [
            {
                "role": "ninjatrader_trace",
                "path": trace.name,
                "sha256": _sha256(trace),
            },
            {
                "role": "ninjatrader_log",
                "path": log.name,
                "sha256": _sha256(log),
            },
            {
                "role": "ninjatrader_config",
                "path": config.name,
                "sha256": _sha256(config),
            },
            {
                "role": "trading_hours_template",
                "path": hours.name,
                "sha256": _sha256(hours),
            },
            {
                "role": "selection_registry",
                "path": selection_registry.name,
                "sha256": _sha256(selection_registry),
            },
            {
                "role": "toolset_manifest",
                "path": toolset_manifest.name,
                "sha256": _sha256(toolset_manifest),
            },
        ],
        "selected_row_derivation": (
            "first 250 native 5-minute bars of the declared Trading Hours session"
        ),
        "source_quality_findings": [],
        "known_missing_bars": [],
        "scheduled_exclusions": ["captured Trading Hours session breaks"],
        "known_limitations": [],
        "transformations": {
            "sorted": False,
            "filled": False,
            "interpolated": False,
            "resampled": False,
            "timezone_converted": False,
            "back_adjusted": False,
        },
    }
    evidence_path = tmp_path / "acquisition_evidence.json"
    _write_json(evidence_path, evidence)
    return source, runtime_path, evidence_path, exporter


def _finalize(tmp_path: Path) -> dict[str, object]:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    return finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
    )


def _rewrite_json(path: Path, mutator) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutator(value)
    _write_json(path, value)


def _refresh_runtime_hash(runtime: Path, evidence: Path) -> None:
    _rewrite_json(
        evidence,
        lambda value: value.__setitem__("runtime_capture_sha256", _sha256(runtime)),
    )


def test_valid_bundle_captures_provenance_and_accepts_zero_volume(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    original_source = source.read_bytes()

    result = finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
    )

    assert result["schema_version"] == "1.0"
    assert result["cohort_id"] == "mnq-202609-5m-v1"
    assert result["case_id"] == "mnq-202609-5m-td2026-06-22-w01"
    assert result["contract"]["contract_label"] == "MNQ SEP26"
    assert result["contract"]["full_name"] == "MNQ 09-26"
    assert result["bar_series"] == {
        "type": "Minute",
        "value": 5,
        "native": True,
        "timestamp_semantics": (
            "Time[0] clock values displayed in the NinjaTrader application timezone"
        ),
    }
    assert result["source"]["row_count"] == 250
    assert result["source"]["first_timestamp"] == "20260622 000500"
    assert result["source"]["sha256"] == _sha256(source)
    assert result["source"]["original_source_sha256"] == _sha256(source)
    assert result["source"]["frozen_case_sha256"] == _sha256(source)
    assert result["application_timezone"]["id"] == "Singapore Standard Time"
    assert result["trading_hours"]["name"] == "CME US Index Futures ETH"
    assert result["provider_acquisition"]["status"] == "PROVEN"
    assert result["source_quality_findings"] == []
    assert result["source"]["selected_row_derivation"].startswith("first 250")
    assert result["source"]["known_missing_bars"] == []
    assert result["source"]["scheduled_exclusions"] == [
        "captured Trading Hours session breaks"
    ]
    assert result["source"]["known_limitations"] == []
    assert result["source"]["export_method"].startswith("ExportMnq5m")
    assert set(result["artifact_hashes"]) == {
        "source",
        "runtime_capture",
        "acquisition_evidence",
        "exporter",
        "ninjatrader_trace",
        "ninjatrader_log",
        "ninjatrader_config",
        "trading_hours_template",
        "selection_registry",
        "toolset_manifest",
    }
    assert source.read_bytes() == original_source


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["instrument"].__setitem__("full_name", "MNQ 12-26"),
        lambda value: value["instrument"].__setitem__("master_name", "ES"),
        lambda value: value["instrument"].__setitem__("instrument_id", "MNQ 12-26"),
        lambda value: value["instrument"].__setitem__("expiry_month", 12),
        lambda value: value["instrument"].__setitem__("expiry_year", 2025),
    ],
)
def test_rejects_wrong_runtime_contract(tmp_path: Path, mutation) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(runtime, mutation)
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="approved MNQ SEP26"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "field,value",
    [("type", "Second"), ("value", 1), ("native", False)],
)
def test_rejects_non_native_five_minute_series(
    tmp_path: Path, field: str, value: object
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(runtime, lambda data: data["bar_series"].__setitem__(field, value))
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="native 5-minute"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "replacement,error",
    [
        ("20260622 000500", "duplicate timestamp"),
        ("20260621 235500", "non-monotonic timestamp"),
        ("not-a-time", "malformed timestamp"),
    ],
)
def test_rejects_invalid_timestamp_order(
    tmp_path: Path, replacement: str, error: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    rows = source.read_text(encoding="utf-8").splitlines()
    rows[1] = replacement + ";100;101;99;100;1"
    source.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")
    _rewrite_json(runtime, lambda value: value.__setitem__("source_sha256", _sha256(source)))
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match=error):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "row,error",
    [
        ("20260622 000000;100;99;98;100;1", "impossible OHLC"),
        ("20260622 000000;NaN;101;99;100;1", "non-finite"),
        ("20260622 000000;100;101;99;100;-1", "negative volume"),
        ("20260622 000000;100;101;99;100", "malformed row"),
    ],
)
def test_rejects_invalid_ohlcv(tmp_path: Path, row: str, error: str) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    rows = source.read_text(encoding="utf-8").splitlines()
    rows[0] = row
    source.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")
    _rewrite_json(runtime, lambda value: value.__setitem__("source_sha256", _sha256(source)))
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match=error):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_accepts_captured_scheduled_break_but_rejects_unexpected_gap(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    valid = finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
    )
    assert valid["source"]["row_count"] == 250

    rows = source.read_text(encoding="utf-8").splitlines()
    rows[1] = "20260622 000600;100;101;99;100;1"
    source.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")
    _rewrite_json(runtime, lambda value: value.__setitem__("source_sha256", _sha256(source)))
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="unexpected timestamp spacing"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "field,error",
    [
        ("application_timezone", "application timezone"),
        ("trading_hours", "Trading Hours"),
    ],
)
def test_rejects_missing_runtime_metadata(
    tmp_path: Path, field: str, error: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(runtime, lambda value: value.pop(field))
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match=error):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "missing_text",
    [
        "Tradovate.Adapter.Connect",
        "Reload All Historical Data initiated",
        "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26'",
        "export armed after reload",
        "exporter initialized",
        "export complete",
    ],
)
def test_rejects_missing_provider_reload_chain(
    tmp_path: Path, missing_text: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    trace = tmp_path / "trace.txt"
    log = tmp_path / "log.txt"
    for path in (trace, log):
        path.write_text(
            path.read_text(encoding="utf-8").replace(missing_text, "REMOVED"),
            encoding="utf-8",
        )
    _rewrite_json(
        evidence,
        lambda value: [
            item.__setitem__("sha256", _sha256(tmp_path / item["path"]))
            for item in value["evidence_files"]
            if item["role"] in {"ninjatrader_trace", "ninjatrader_log"}
        ],
    )

    with pytest.raises(AcquisitionValidationError, match="provider/reload evidence"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_incorrect_or_competing_provider(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        runtime,
        lambda value: value["active_connections"].append(
            {
                "name": "Other",
                "provider": "Kinetick",
                "status": "Connected",
                "price_status": "Connected",
                "instrument_types": ["Future"],
            }
        ),
    )
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="competing historical"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_intended_provider_with_disconnected_price_feed(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        runtime,
        lambda value: value["active_connections"][0].__setitem__(
            "price_status", "Disconnected"
        ),
    )
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="intended provider"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_competing_provider_activity_during_acquisition(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    trace = tmp_path / "trace.txt"
    trace.write_text(
        trace.read_text(encoding="utf-8").replace(
            "2026-06-21 23:55:00.000 Reload All Historical Data initiated\n",
            "2026-06-21 23:54:00.000 (Other) Kinetick.Adapter.Connect "
            "status=Connected\n"
            "2026-06-21 23:54:30.000 (Other) Kinetick.Adapter.Disconnect\n"
            "2026-06-21 23:55:00.000 Reload All Historical Data initiated\n",
        ),
        encoding="utf-8",
    )
    _rewrite_json(
        evidence,
        lambda value: next(
            item
            for item in value["evidence_files"]
            if item["role"] == "ninjatrader_trace"
        ).__setitem__("sha256", _sha256(trace)),
    )

    with pytest.raises(AcquisitionValidationError, match="competing historical"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_provider_when_preferred_future_connection_does_not_match(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    config = tmp_path / "Config.xml"
    config.write_text(
        "<NinjaTrader><PreferredFutureConnection>Other</PreferredFutureConnection>"
        "<PreferredRealtimeFutureConnection>Other</PreferredRealtimeFutureConnection>"
        "</NinjaTrader>\n",
        encoding="utf-8",
    )
    _rewrite_json(
        evidence,
        lambda value: next(
            item
            for item in value["evidence_files"]
            if item["role"] == "ninjatrader_config"
        ).__setitem__("sha256", _sha256(config)),
    )

    with pytest.raises(AcquisitionValidationError, match="preferred historical connection"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize("field", ["cohort_id", "case_id", "trading_date"])
def test_rejects_runtime_identity_relabeling(tmp_path: Path, field: str) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(runtime, lambda value: value.__setitem__(field, "different"))
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="runtime/evidence identity"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_timezone_offset_coverage_not_bound_to_source(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        runtime,
        lambda value: value["application_timezone"]["source_timestamp_offsets"][0].__setitem__(
            "first_timestamp", "20260622 000000"
        ),
    )
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="timezone offset coverage"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize("defect", ["gap", "overlap", "reverse"])
def test_rejects_noncontiguous_timezone_offset_coverage(
    tmp_path: Path, defect: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    timestamps = _expected_timestamps()

    def corrupt(value: dict[str, object]) -> None:
        if defect == "gap":
            second_first = timestamps[101]
        elif defect == "overlap":
            second_first = timestamps[99]
        else:
            second_first = timestamps[100]
        first_last = timestamps[100] if defect == "reverse" else timestamps[99]
        value["application_timezone"]["source_timestamp_offsets"] = [
            {
                "first_timestamp": _timestamp_text(timestamps[0]),
                "last_timestamp": _timestamp_text(first_last),
                "utc_offset": "+08:00",
            },
            {
                "first_timestamp": _timestamp_text(second_first),
                "last_timestamp": _timestamp_text(timestamps[-1]),
                "utc_offset": "+08:00",
            },
        ]

    _rewrite_json(runtime, corrupt)
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="timezone offset coverage"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_log_offset_not_bound_to_runtime_pc_timezone(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        runtime,
        lambda value: value["pc_timezone"]["acquisition_event_offsets"][1].__setitem__(
            "utc_offset", "+09:00"
        ),
    )
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="PC/log timezone offset"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_incomplete_or_hash_mismatched_evidence(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        evidence,
        lambda value: value["evidence_files"].pop(),
    )

    with pytest.raises(AcquisitionValidationError, match="incomplete evidence bundle"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )

    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    (tmp_path / "trace.txt").write_text("mutated", encoding="utf-8")
    with pytest.raises(AcquisitionValidationError, match="hash mismatch"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_source_mutation_against_runtime_hash(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    source.write_text(
        source.read_text(encoding="utf-8").replace("100.75", "100.50", 1),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(AcquisitionValidationError, match="source hash mismatch"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "field",
    ["sorted", "filled", "interpolated", "resampled", "timezone_converted", "back_adjusted"],
)
def test_rejects_any_prohibited_transformation(tmp_path: Path, field: str) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        evidence,
        lambda value: value["transformations"].__setitem__(field, True),
    )

    with pytest.raises(AcquisitionValidationError, match="prohibited transformation"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize("trading_date", ["2026-06-21", "2026-07-25"])
def test_rejects_trading_date_outside_approved_range(
    tmp_path: Path, trading_date: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(evidence, lambda value: value.__setitem__("trading_date", trading_date))

    with pytest.raises(AcquisitionValidationError, match="approved candidate date range"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_fewer_than_250_rows(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    rows = source.read_text(encoding="utf-8").splitlines()[:-1]
    source.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")
    _rewrite_json(runtime, lambda value: value.__setitem__("source_sha256", _sha256(source)))
    _rewrite_json(runtime, lambda value: value["bar_series"].__setitem__("exported_bar_count", 249))
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="exactly 250"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_module_does_not_import_production_hierarchy() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import tools.validation.mnq_5m_acquisition; "
                "print(any(name == 'trading' or name.startswith('trading.') "
                "for name in sys.modules))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "False"
