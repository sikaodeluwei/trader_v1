"""Strict provider and immutable-evidence validation for the MNQ inventory scan."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
from dataclasses import FrozenInstanceError
from datetime import datetime
from pathlib import Path

import pytest

from tools.validation.mnq_5m_inventory_evidence import (
    InventoryValidationError,
    LoadedInventoryEvidence,
    ValidatedInventoryEvidence,
    finalize_inventory_evidence,
    load_inventory_evidence,
)
from tools.validation.mnq_5m_inventory_common import (
    canonical_payload_sha256,
    load_schema_validated_json,
    sha256_bytes,
    sha256_file,
    write_json_atomically,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "validation" / "mnq_5m_multiwindow" / "schemas"
ACQUISITION_ID = "dryrun-mnq-202609-5m-inventory-20260622-20260724-v1"
COHORT_ID = "mnq-202609-5m-v1"
REPOSITORY_IDENTITY = "https://github.com/sikaodeluwei/trader_v1.git"
EARLIEST = datetime.fromisoformat("2026-06-22T06:00:00+08:00")
LATEST = datetime.fromisoformat("2026-07-25T05:00:00+08:00")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8", newline="\n")


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _timezone() -> dict[str, object]:
    return {
        "id": "Singapore Standard Time",
        "display_name": "(UTC+08:00) Kuala Lumpur, Singapore",
        "standard_name": "Singapore Standard Time",
        "daylight_name": "Singapore Standard Time",
        "base_utc_offset": "+08:00",
        "supports_dst": False,
    }


def _segment() -> dict[str, str]:
    return {
        "begin_application": "2026-06-21T17:00:00-05:00",
        "end_application": "2026-06-22T16:00:00-05:00",
        "begin_pc": "2026-06-22T06:00:00+08:00",
        "end_pc": "2026-06-23T05:00:00+08:00",
    }


def _scan() -> dict[str, object]:
    observations: list[dict[str, object]] = []
    dates = [f"2026-06-{day:02d}" for day in range(22, 31)] + [
        f"2026-07-{day:02d}" for day in range(1, 25)
    ]
    for civil_date in dates:
        observations.append(
            {
                "civil_date": civil_date,
                "classification": "NO_SESSION",
                "exchange_trading_date": None,
                "schedule_evidence": {
                    "holiday_name": None,
                    "partial_session": False,
                    "expected_open_segments": [],
                    "scheduled_breaks": [],
                    "application_session_begin": None,
                    "application_session_end": None,
                    "pc_log_session_begin": None,
                    "pc_log_session_end": None,
                    "effective_schedule_source": (
                        "SessionIterator using Bars.TradingHours and "
                        "ActualTradingDayExchange"
                    ),
                },
                "quality": None,
            }
        )
    segment = _segment()
    observations[0] = {
        "civil_date": "2026-06-22",
        "classification": "SESSION",
        "exchange_trading_date": "2026-06-22",
        "schedule_evidence": {
            "holiday_name": None,
            "partial_session": False,
            "expected_open_segments": [segment],
            "scheduled_breaks": [],
            "application_session_begin": segment["begin_application"],
            "application_session_end": segment["end_application"],
            "pc_log_session_begin": segment["begin_pc"],
            "pc_log_session_end": segment["end_pc"],
            "effective_schedule_source": (
                "SessionIterator using Bars.TradingHours and "
                "ActualTradingDayExchange"
            ),
        },
        "quality": {
            "observed_native_five_minute_bar_count": 276,
            "observed_valid_count_from_session_start": 276,
            "first_observed_timestamp": "20260621 170500",
            "two_hundred_fiftieth_native_timestamp": "20260622 135000",
            "last_observed_session_timestamp": "20260622 160000",
            "supplied_order_strictly_increasing": True,
            "duplicate_timestamp_indexes": [],
            "duplicate_timestamp_count": 0,
            "decreasing_timestamp_indexes": [],
            "decreasing_timestamp_count": 0,
            "missing_expected_open_timestamps": [],
            "missing_expected_open_timestamp_count": 0,
            "unexpected_timestamps": [],
            "unexpected_timestamp_count": 0,
            "malformed_or_non_finite_ohlcv_indexes": [],
            "malformed_or_non_finite_ohlcv_count": 0,
            "invalid_ohlc_geometry_indexes": [],
            "invalid_ohlc_geometry_count": 0,
            "negative_volume_indexes": [],
            "negative_volume_count": 0,
            "non_integral_volume_indexes": [],
            "non_integral_volume_count": 0,
            "first_250_source_sha256": "a" * 64,
            "complete_session_source_sha256": "b" * 64,
            "canonicalization_id": (
                "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1"
            ),
        },
    }
    return {
        "schema_version": "1.0",
        "acquisition_id": ACQUISITION_ID,
        "cohort_id": COHORT_ID,
        "contract": {
            "contract_label": "MNQ SEP26",
            "master_name": "MNQ",
            "full_name": "MNQ SEP26",
            "expiry_month": 9,
            "expiry_year": 2026,
        },
        "bar_series": {
            "type": "Minute",
            "value": 5,
            "native": True,
            "timestamp_semantics": (
                "NinjaTrader native Minute bar close timestamp in application time"
            ),
        },
        "trading_hours": {
            "name": "CME US Index Futures ETH",
            "timezone_id": "Central Standard Time",
            "exchange_trading_date_member": "ActualTradingDayExchange",
        },
        "civil_date_start": "2026-06-22",
        "civil_date_end": "2026-07-24",
        "canonicalization_id": (
            "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1"
        ),
        "observations": observations,
        "transformations": {
            "sorted": False,
            "deduplicated": False,
            "filled": False,
            "interpolated": False,
            "resampled": False,
            "timezone_converted": False,
            "back_adjusted": False,
            "repaired": False,
        },
        "completed_at": "2026-09-16T12:00:01+08:00",
    }


def _runtime(scan_sha: str, scanner_sha: str, template_sha: str, config_sha: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "acquisition_id": ACQUISITION_ID,
        "cohort_id": COHORT_ID,
        "instrument": {
            "contract_label": "MNQ SEP26",
            "full_name": "MNQ SEP26",
            "master_name": "MNQ",
            "expiry_month": 9,
            "expiry_year": 2026,
        },
        "ninjatrader_version": "8.1.6.1",
        "scanner_identity": {
            "name": "ScanMnq5mSourceInventory",
            "scanner_sha256": scanner_sha,
            "scanner_sha256_recording_authority": "operator/finalizer",
        },
        "bar_series": {"type": "Minute", "value": 5, "native": True, "calculate": "OnBarClose"},
        "application_timezone": _timezone(),
        "pc_timezone": _timezone(),
        "trading_hours": {"name": "CME US Index Futures ETH", "timezone_id": "Central Standard Time"},
        "active_connections": [
            {
                "name": "My NinjaTrader",
                "provider": "Provider31",
                "status": "Connected",
                "price_status": "Connected",
                "instrument_types": ["Future"],
            }
        ],
        "connection_snapshot_phase": "immediately after operator arm and before inventory scan",
        "lifecycle": {
            "initialized_at": "2026-09-16T11:02:00+08:00",
            "realtime_observed_at": "2026-09-16T11:02:01+08:00",
            "armed_at": "2026-09-16T11:03:00+08:00",
            "completed_at": "2026-09-16T12:00:01+08:00",
        },
        "artifact_hashes": {
            "inventory_scan": {"file_name": "inventory_scan.json", "sha256": scan_sha},
            "inventory_runtime_capture": {
                "file_name": "inventory_runtime_capture.json",
                "sha256": None,
                "sha256_recording_authority": "operator/finalizer",
            },
            "trading_hours_template": {"file_name": "trading_hours_template.xml", "sha256": template_sha},
            "ninjatrader_config": {"file_name": "NinjaTrader.Config.xml", "sha256": config_sha},
        },
    }


def _trace(request_lines: list[str] | None = None) -> str:
    requests = request_lines or [
        "2026-09-16 11:01:30.000 Cbi.Instrument.RequestBars (to Provider): "
        "instrument='MNQ SEP26' from='2026/06/01 00:00:00' "
        "to='2026/08/01 00:00:00' period='1 Minute'"
    ]
    lines = [
        "2026-09-16 10:59:00.000 (My NinjaTrader) Tradovate.Adapter.Connect status=Connecting",
        "2026-09-16 10:59:30.000 (My NinjaTrader) Cbi.Connection.ConnectionStatusCallback: status=Connected priceStatus=Connected",
        "2026-09-16 10:59:40.000 Server.HdsClient.Connect: type=HDS server='hds-us-nt-007.ninjatrader.com' port=31655 system='' useSsl=True",
        *requests,
    ]
    return "\n".join(lines) + "\n"


def _log() -> str:
    return "\n".join(
        [
            f"2026-09-16 10:59:59.000 acquisition={ACQUISITION_ID} inventory scanner initialized event_time=2026-09-16T10:59:59+08:00",
            f"2026-09-16 11:00:00.000 acquisition={ACQUISITION_ID} inventory realtime lifecycle observed event_time=2026-09-16T11:00:00+08:00",
            f"2026-09-16 11:02:00.000 acquisition={ACQUISITION_ID} inventory scanner initialized event_time=2026-09-16T11:02:00+08:00",
            f"2026-09-16 11:02:01.000 acquisition={ACQUISITION_ID} inventory realtime lifecycle observed event_time=2026-09-16T11:02:01+08:00",
            f"2026-09-16 11:03:00.000 acquisition={ACQUISITION_ID} inventory scan armed event_time=2026-09-16T11:03:00+08:00",
            f"2026-09-16 12:00:02.000 acquisition={ACQUISITION_ID} inventory scan complete event_time=2026-09-16T12:00:02+08:00",
        ]
    ) + "\n"


def _evidence_file(role: str, path: Path) -> dict[str, object]:
    return {"role": role, "path": path.name, "sha256": _sha(path), "byte_length": path.stat().st_size}


def _acquisition(checkpoint: str, config: Path, log: Path, trace: Path, template: Path) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "acquisition_id": ACQUISITION_ID,
        "cohort_id": COHORT_ID,
        "intended_provider": {
            "provider_profile_id": "NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1",
            "runtime_provider_id": "Provider31",
            "trace_adapter": "Tradovate.Adapter",
            "historical_service": "NinjaTrader HDS",
        },
        "intended_connection_name": "My NinjaTrader",
        "historical_trigger": {
            "source_role": "ninjatrader_trace",
            "instrument": "MNQ SEP26",
            "provider_request_period": "1 Minute",
            "observed_at": "2026-09-16T11:01:30+08:00",
            "requested_start": "2026-06-01T00:00:00",
            "requested_end": "2026-08-01T00:00:00",
            "qualifying_request_count": 1,
        },
        "lifecycle": {
            "adapter_connection_initiated_at": "2026-09-16T10:59:00+08:00",
            "connection_ready_at": "2026-09-16T10:59:30+08:00",
            "pre_request_realtime_at": "2026-09-16T11:00:00+08:00",
            "request_observed_at": "2026-09-16T11:01:30+08:00",
            "post_request_initialized_at": "2026-09-16T11:02:00+08:00",
            "post_request_realtime_at": "2026-09-16T11:02:01+08:00",
            "inventory_scan_armed_at": "2026-09-16T11:03:00+08:00",
            "inventory_scan_completed_at": "2026-09-16T12:00:02+08:00",
        },
        "evidence_files": [
            _evidence_file("ninjatrader_config", config),
            _evidence_file("ninjatrader_log", log),
            _evidence_file("ninjatrader_trace", trace),
            _evidence_file("trading_hours_template", template),
        ],
        "expected_toolset_checkpoint": checkpoint,
        "transformations": {
            "sorted": False,
            "filled": False,
            "interpolated": False,
            "resampled": False,
            "timezone_converted": False,
            "back_adjusted": False,
        },
    }


@pytest.fixture
def bundle(tmp_path: Path) -> dict[str, object]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "tests@example.com")
    _git(repository, "config", "user.name", "Tests")
    _git(repository, "remote", "add", "origin", REPOSITORY_IDENTITY)
    scanner = repository / "tools" / "validation" / "ninjatrader" / "ScanMnq5mSourceInventory.cs"
    scanner.parent.mkdir(parents=True)
    scanner.write_bytes(b"// frozen scanner\n")
    _git(repository, "add", scanner.relative_to(repository).as_posix())
    _git(repository, "commit", "-m", "Freeze scanner")
    checkpoint = _git(repository, "rev-parse", "HEAD")

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    scan_path = evidence_dir / "inventory_scan.json"
    runtime_path = evidence_dir / "inventory_runtime_capture.json"
    acquisition_path = evidence_dir / "inventory_acquisition_evidence.json"
    template = evidence_dir / "trading_hours_template.xml"
    config = evidence_dir / "NinjaTrader.Config.xml"
    log = evidence_dir / "log.txt"
    trace = evidence_dir / "trace.txt"
    template.write_bytes(b"<TradingHours name='CME US Index Futures ETH'/>\n")
    config.write_bytes(
        b"<NinjaTrader><PreferredFutureConnection>My NinjaTrader</PreferredFutureConnection>"
        b"<PreferredRealtimeFutureConnection>My NinjaTrader</PreferredRealtimeFutureConnection>"
        b"<Connection><Name>My NinjaTrader</Name><Provider>Provider31</Provider></Connection>"
        b"</NinjaTrader>\n"
    )
    log.write_text(_log(), encoding="utf-8", newline="\n")
    trace.write_text(_trace(), encoding="utf-8", newline="\n")
    _write_json(scan_path, _scan())
    _write_json(runtime_path, _runtime(_sha(scan_path), _sha(scanner), _sha(template), _sha(config)))
    _write_json(acquisition_path, _acquisition(checkpoint, config, log, trace, template))

    def reload() -> LoadedInventoryEvidence:
        return load_inventory_evidence(
            runtime_capture_path=runtime_path,
            inventory_scan_path=scan_path,
            acquisition_evidence_path=acquisition_path,
        )

    return {
        "repository": repository,
        "checkpoint": checkpoint,
        "scanner": scanner,
        "scan_path": scan_path,
        "runtime_path": runtime_path,
        "acquisition_path": acquisition_path,
        "template": template,
        "config": config,
        "log": log,
        "trace": trace,
        "reload": reload,
    }


def _finalize(bundle: dict[str, object], **overrides: object) -> ValidatedInventoryEvidence:
    values: dict[str, object] = {
        "loaded": bundle["reload"](),  # type: ignore[operator]
        "scanner_path": bundle["scanner"],
        "trading_hours_template_path": bundle["template"],
        "config_path": bundle["config"],
        "log_path": bundle["log"],
        "trace_path": bundle["trace"],
        "trusted_toolset_checkpoint": bundle["checkpoint"],
        "repository_path": bundle["repository"],
        "expected_repository_identity": REPOSITORY_IDENTITY,
        "earliest_session_begin": EARLIEST,
        "latest_session_end": LATEST,
    }
    values.update(overrides)
    return finalize_inventory_evidence(**values)  # type: ignore[arg-type]


def _rewrite_json(bundle: dict[str, object], key: str, mutate: object) -> None:
    path = bundle[key]
    assert isinstance(path, Path)
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)  # type: ignore[operator]
    _write_json(path, value)
    if key == "scan_path":
        runtime = json.loads(bundle["runtime_path"].read_text(encoding="utf-8"))  # type: ignore[union-attr]
        runtime["artifact_hashes"]["inventory_scan"]["sha256"] = _sha(path)
        _write_json(bundle["runtime_path"], runtime)  # type: ignore[arg-type]


def _rewrite_external(bundle: dict[str, object], key: str, text: str) -> None:
    path = bundle[key]
    assert isinstance(path, Path)
    path.write_text(text, encoding="utf-8", newline="\n")
    acquisition_path = bundle["acquisition_path"]
    assert isinstance(acquisition_path, Path)
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    role = {
        "config": "ninjatrader_config",
        "log": "ninjatrader_log",
        "trace": "ninjatrader_trace",
        "template": "trading_hours_template",
    }[key]
    record = next(item for item in acquisition["evidence_files"] if item["role"] == role)
    record["sha256"] = _sha(path)
    record["byte_length"] = path.stat().st_size
    _write_json(acquisition_path, acquisition)
    if key in {"config", "template"}:
        runtime_path = bundle["runtime_path"]
        assert isinstance(runtime_path, Path)
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        runtime["artifact_hashes"][
            "ninjatrader_config" if key == "config" else "trading_hours_template"
        ]["sha256"] = _sha(path)
        _write_json(runtime_path, runtime)


def _set_request_range(bundle: dict[str, object], start: str, end: str) -> None:
    trace = Path(bundle["trace"]).read_text(encoding="utf-8")
    trace = trace.replace("from='2026/06/01 00:00:00'", f"from='{start}'")
    trace = trace.replace("to='2026/08/01 00:00:00'", f"to='{end}'")
    _rewrite_external(bundle, "trace", trace)

    def mutate(item: dict[str, object]) -> None:
        trigger = item["historical_trigger"]
        trigger["requested_start"] = datetime.strptime(start, "%Y/%m/%d %H:%M:%S").isoformat()
        trigger["requested_end"] = datetime.strptime(end, "%Y/%m/%d %H:%M:%S").isoformat()

    _rewrite_json(bundle, "acquisition_path", mutate)


def test_public_interfaces_are_exact_and_dataclasses_are_frozen(bundle: dict[str, object]) -> None:
    assert list(inspect.signature(load_inventory_evidence).parameters) == [
        "runtime_capture_path", "inventory_scan_path", "acquisition_evidence_path"
    ]
    assert list(inspect.signature(finalize_inventory_evidence).parameters) == [
        "loaded", "scanner_path", "trading_hours_template_path", "config_path",
        "log_path", "trace_path", "trusted_toolset_checkpoint", "repository_path",
        "expected_repository_identity", "earliest_session_begin", "latest_session_end",
    ]
    loaded = bundle["reload"]()  # type: ignore[operator]
    with pytest.raises(FrozenInstanceError):
        loaded.runtime_capture_path = Path("changed")  # type: ignore[misc]


def test_valid_inventory_evidence_returns_only_in_memory_validation(bundle: dict[str, object]) -> None:
    result = _finalize(bundle)
    assert result.provider_acquisition["status"] == "PROVEN"
    assert result.qualifying_request["instrument"] == "MNQ SEP26"
    assert result.earliest_session_begin == EARLIEST
    assert result.latest_session_end == LATEST
    assert not (Path(bundle["acquisition_path"]).parent / "inventory_provenance.json").exists()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("runtime_provider_id", "Provider99"),
        ("trace_adapter", "Kinetick.Adapter"),
    ],
)
def test_rejects_wrong_provider_or_adapter(bundle: dict[str, object], key: str, value: str) -> None:
    _rewrite_json(bundle, "acquisition_path", lambda item: item["intended_provider"].__setitem__(key, value))
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_rejects_wrong_connection_name(bundle: dict[str, object]) -> None:
    _rewrite_json(bundle, "acquisition_path", lambda item: item.__setitem__("intended_connection_name", "Other"))
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "Provider99"),
        ("name", "Other Connection"),
    ],
)
def test_rejects_wrong_runtime_provider_or_connection(
    bundle: dict[str, object], field: str, value: str
) -> None:
    _rewrite_json(
        bundle,
        "runtime_path",
        lambda item: item["active_connections"][0].__setitem__(field, value),
    )
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_rejects_wrong_trace_adapter(bundle: dict[str, object]) -> None:
    text = Path(bundle["trace"]).read_text(encoding="utf-8").replace(
        "Tradovate.Adapter.Connect", "Kinetick.Adapter.Connect"
    )
    _rewrite_external(bundle, "trace", text)
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


@pytest.mark.parametrize(
    "replacement",
    [
        "server='evil.example.com' port=31655 system='' useSsl=True",
        "server='hds-us-nt-007.ninjatrader.com' port=31655 system='' useSsl=False",
    ],
)
def test_rejects_wrong_hds_host_or_ssl(bundle: dict[str, object], replacement: str) -> None:
    text = Path(bundle["trace"]).read_text(encoding="utf-8")
    text = text.replace("server='hds-us-nt-007.ninjatrader.com' port=31655 system='' useSsl=True", replacement)
    _rewrite_external(bundle, "trace", text)
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_rejects_wrong_config_route(bundle: dict[str, object]) -> None:
    text = Path(bundle["config"]).read_text(encoding="utf-8").replace(
        "<PreferredFutureConnection>My NinjaTrader</PreferredFutureConnection>",
        "<PreferredFutureConnection>Other</PreferredFutureConnection>",
    )
    _rewrite_external(bundle, "config", text)
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


@pytest.mark.parametrize(
    "extra",
    [
        "2026-09-16 11:01:00.000 (Other) Kinetick.Adapter.Connect status=Connecting\n",
        "2026-09-16 11:01:00.000 (My NinjaTrader) Tradovate.Adapter.Disconnect\n",
    ],
)
def test_rejects_competing_provider_or_disconnect(bundle: dict[str, object], extra: str) -> None:
    _rewrite_external(bundle, "trace", Path(bundle["trace"]).read_text(encoding="utf-8") + extra)
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_rejects_marker_prefix_event_time_skew_over_one_second(bundle: dict[str, object]) -> None:
    text = Path(bundle["log"]).read_text(encoding="utf-8").replace(
        "11:03:00.000 acquisition=", "11:03:02.001 acquisition="
    )
    _rewrite_external(bundle, "log", text)
    with pytest.raises(InventoryValidationError, match="marker"):
        _finalize(bundle)


def test_accepts_marker_prefix_event_time_skew_of_exactly_one_second(bundle: dict[str, object]) -> None:
    text = Path(bundle["log"]).read_text(encoding="utf-8").replace(
        "11:03:00.000 acquisition=", "11:03:01.000 acquisition="
    )
    _rewrite_external(bundle, "log", text)
    assert _finalize(bundle).provider_acquisition["status"] == "PROVEN"


@pytest.mark.parametrize("timestamp", ["10:59:59.000", "11:02:00.500", "11:04:00.000"])
def test_rejects_request_outside_required_lifecycle_interval(bundle: dict[str, object], timestamp: str) -> None:
    text = Path(bundle["trace"]).read_text(encoding="utf-8").replace("11:01:30.000", timestamp)
    _rewrite_external(bundle, "trace", text)
    with pytest.raises(InventoryValidationError, match="RequestBars|request"):
        _finalize(bundle)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("earliest_session_begin", datetime.fromisoformat("2026-05-31T23:59:59+08:00")),
        ("latest_session_end", datetime.fromisoformat("2026-08-01T00:00:01+08:00")),
    ],
)
def test_rejects_request_that_does_not_cover_explicit_verified_bound(
    bundle: dict[str, object], name: str, value: datetime
) -> None:
    with pytest.raises(InventoryValidationError, match="RequestBars|request"):
        _finalize(bundle, **{name: value})


def test_request_coverage_preserves_equivalent_instants_across_offsets(
    bundle: dict[str, object],
) -> None:
    _set_request_range(bundle, "2026/06/22 06:00:00", "2026/07/25 05:00:00")
    result = _finalize(
        bundle,
        earliest_session_begin=datetime.fromisoformat("2026-06-21T17:00:00-05:00"),
        latest_session_end=datetime.fromisoformat("2026-07-24T16:00:00-05:00"),
    )
    assert result.qualifying_request["covers_verified_inventory_bounds"] is True


def test_request_coverage_rejects_same_wall_clock_with_different_instant(
    bundle: dict[str, object],
) -> None:
    _set_request_range(bundle, "2026/06/22 06:00:00", "2026/07/25 05:00:00")
    with pytest.raises(InventoryValidationError, match="RequestBars|request"):
        _finalize(
            bundle,
            latest_session_end=datetime.fromisoformat("2026-07-25T05:00:00-05:00"),
        )


def test_request_coverage_rejects_unprovable_dst_application_timezone(
    bundle: dict[str, object],
) -> None:
    _rewrite_json(
        bundle,
        "runtime_path",
        lambda item: item["application_timezone"].__setitem__("supports_dst", True),
    )
    with pytest.raises(InventoryValidationError, match="application timezone"):
        _finalize(bundle)


def test_rejects_zero_qualifying_requests(bundle: dict[str, object]) -> None:
    lines = [line for line in Path(bundle["trace"]).read_text(encoding="utf-8").splitlines() if "RequestBars" not in line]
    _rewrite_external(bundle, "trace", "\n".join(lines) + "\n")
    with pytest.raises(InventoryValidationError, match="RequestBars|request"):
        _finalize(bundle)


def test_rejects_two_qualifying_requests(bundle: dict[str, object]) -> None:
    text = Path(bundle["trace"]).read_text(encoding="utf-8")
    request = next(line for line in text.splitlines() if "RequestBars" in line)
    _rewrite_external(bundle, "trace", text + request.replace("11:01:30.000", "11:01:31.000") + "\n")
    with pytest.raises(InventoryValidationError, match="uniquely|RequestBars"):
        _finalize(bundle)


@pytest.mark.parametrize(
    "request_line",
    [
        "2026-09-16 11:01:20.000 Cbi.Instrument.RequestBars (to Provider): instrument='MNQ DEC26' from='2026/06/01 00:00:00' to='2026/08/01 00:00:00' period='1 Minute'",
        "2026-09-16 11:01:20.000 Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26' from='2026/06/01 00:00:00' to='2026/08/01 00:00:00' period='5 Minute'",
        "2026-09-16 11:01:20.000 Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26' from='2026/07/01 00:00:00' to='2026/07/02 00:00:00' period='1 Minute'",
    ],
)
def test_tolerates_unrelated_contract_period_or_insufficient_range_request(
    bundle: dict[str, object], request_line: str
) -> None:
    _rewrite_external(bundle, "trace", Path(bundle["trace"]).read_text(encoding="utf-8") + request_line + "\n")
    assert _finalize(bundle).qualifying_request["instrument"] == "MNQ SEP26"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: "\n".join(line for line in text.splitlines() if "inventory scan armed" not in line) + "\n",
        lambda text: text.replace("event_time=2026-09-16T11:03:00+08:00", "event_time=malformed"),
    ],
)
def test_rejects_missing_or_malformed_lifecycle_marker(bundle: dict[str, object], mutate: object) -> None:
    _rewrite_external(bundle, "log", mutate(Path(bundle["log"]).read_text(encoding="utf-8")))  # type: ignore[operator]
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_accepts_scanner_shaped_reinitialization_and_post_publication_completion(
    bundle: dict[str, object],
) -> None:
    _rewrite_json(
        bundle,
        "scan_path",
        lambda item: item.__setitem__("completed_at", "2026-09-16T04:00:01+00:00"),
    )

    loaded = bundle["reload"]()  # type: ignore[operator]
    result = _finalize(bundle, loaded=loaded)

    assert result.provider_acquisition["historical_request"]["instrument"] == "MNQ SEP26"


@pytest.mark.parametrize("field", ["sha256", "byte_length"])
def test_rejects_external_evidence_hash_or_byte_length_mismatch(bundle: dict[str, object], field: str) -> None:
    def mutate(item: dict[str, object]) -> None:
        record = next(entry for entry in item["evidence_files"] if entry["role"] == "ninjatrader_log")
        record[field] = "0" * 64 if field == "sha256" else record[field] + 1

    _rewrite_json(bundle, "acquisition_path", mutate)
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_rejects_scan_runtime_cross_binding_mismatch(bundle: dict[str, object]) -> None:
    _rewrite_json(bundle, "runtime_path", lambda item: item.__setitem__("acquisition_id", "different"))
    with pytest.raises(InventoryValidationError):
        bundle["reload"]()  # type: ignore[operator]


def test_rejects_acquisition_cross_binding_mismatch(bundle: dict[str, object]) -> None:
    _rewrite_json(
        bundle,
        "acquisition_path",
        lambda item: item["historical_trigger"].__setitem__("observed_at", "2026-09-16T11:01:31+08:00"),
    )
    with pytest.raises(InventoryValidationError):
        bundle["reload"]()  # type: ignore[operator]


def test_loader_parses_the_single_retained_exact_byte_sequence(
    bundle: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    scan_path = Path(bundle["scan_path"])
    original_bytes = scan_path.read_bytes()
    changed = json.loads(original_bytes)
    changed["observations"][0]["schedule_evidence"]["holiday_name"] = "Changed"
    changed_bytes = json.dumps(changed, sort_keys=True).encode("utf-8")
    real_read_bytes = Path.read_bytes
    calls = 0

    def changing_read_bytes(path: Path) -> bytes:
        nonlocal calls
        if path.resolve() == scan_path.resolve():
            calls += 1
            return original_bytes if calls == 1 else changed_bytes
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", changing_read_bytes)
    loaded = bundle["reload"]()  # type: ignore[operator]
    assert loaded.exact_artifact_bytes["inventory_scan"] == original_bytes
    assert loaded.inventory_scan["observations"][0]["schedule_evidence"]["holiday_name"] is None
    assert calls == 1


def test_loaded_nested_documents_cannot_diverge_from_exact_bytes(
    bundle: dict[str, object],
) -> None:
    loaded = bundle["reload"]()  # type: ignore[operator]
    with pytest.raises(TypeError):
        loaded.runtime_capture["instrument"]["master_name"] = "OTHER"
    with pytest.raises(AttributeError):
        loaded.runtime_capture["active_connections"].append({})


def test_common_exact_hash_and_canonical_payload_hash_helpers(tmp_path: Path) -> None:
    value = b"exact\r\nbytes\n"
    path = tmp_path / "exact.bin"
    path.write_bytes(value)
    assert sha256_bytes(value) == hashlib.sha256(value).hexdigest()
    assert sha256_file(path) == hashlib.sha256(value).hexdigest()
    payload = {"z": 1, "aggregate_payload_sha256": "wrong", "a": "é"}
    expected = hashlib.sha256(
        json.dumps({"a": "é", "z": 1}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert canonical_payload_sha256(payload) == expected


def test_common_schema_loader_rejects_invalid_json_and_schema(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["x"], "additionalProperties": False, "properties": {"x": {"const": 1}}}), encoding="utf-8")
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_schema_validated_json(invalid_json, schema, "sample")
    wrong = tmp_path / "wrong.json"
    wrong.write_text('{"x":2}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_schema_validated_json(wrong, schema, "sample")


def test_atomic_json_writer_refuses_overwrite_and_writes_canonical_bytes(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    value = {"z": 1, "a": "é"}
    write_json_atomically(path, value)
    assert path.read_bytes() == b'{"a":"\xc3\xa9","z":1}\n'
    with pytest.raises(FileExistsError):
        write_json_atomically(path, value)


def test_atomic_json_writer_cannot_overwrite_destination_created_during_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "result.json"
    original_link = os.link

    def create_destination_then_link(source: object, destination: object) -> None:
        path.write_bytes(b"existing\n")
        original_link(source, destination)

    monkeypatch.setattr(os, "link", create_destination_then_link)
    with pytest.raises(FileExistsError):
        write_json_atomically(path, {"a": 1})
    assert path.read_bytes() == b"existing\n"


def test_accepts_unique_automatic_config_route(bundle: dict[str, object]) -> None:
    text = Path(bundle["config"]).read_text(encoding="utf-8")
    text = text.replace(
        "<PreferredFutureConnection>My NinjaTrader</PreferredFutureConnection>",
        "<PreferredFutureConnection>Unknown</PreferredFutureConnection>",
    ).replace(
        "<PreferredRealtimeFutureConnection>My NinjaTrader</PreferredRealtimeFutureConnection>",
        "<PreferredRealtimeFutureConnection>Unknown</PreferredRealtimeFutureConnection>",
    )
    _rewrite_external(bundle, "config", text)
    result = _finalize(bundle)
    assert result.provider_acquisition["configuration_binding"]["mode"] == "UNIQUE_AUTO_ROUTE"


def test_rejects_external_evidence_path_substitution(bundle: dict[str, object]) -> None:
    _rewrite_json(
        bundle,
        "acquisition_path",
        lambda item: item["evidence_files"][0].__setitem__("path", "trace.txt"),
    )
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_rejects_repository_identity_and_toolset_checkpoint_mismatch(bundle: dict[str, object]) -> None:
    with pytest.raises(InventoryValidationError):
        _finalize(bundle, expected_repository_identity="https://example.invalid/other.git")
    with pytest.raises(InventoryValidationError):
        _finalize(bundle, trusted_toolset_checkpoint="f" * 40)


@pytest.mark.parametrize("invalid_offset", ["+08:99", "+99:99"])
def test_rejects_schema_matching_invalid_timezone_offsets_as_inventory_errors(
    bundle: dict[str, object], invalid_offset: str
) -> None:
    def mutate_runtime(item: dict[str, object]) -> None:
        item["pc_timezone"]["base_utc_offset"] = invalid_offset
        if invalid_offset == "+08:99":
            for key in item["lifecycle"]:
                item["lifecycle"][key] = item["lifecycle"][key].replace("+08:00", "+09:39")

    _rewrite_json(bundle, "runtime_path", mutate_runtime)
    if invalid_offset == "+08:99":
        def mutate_acquisition(item: dict[str, object]) -> None:
            for key in item["lifecycle"]:
                item["lifecycle"][key] = item["lifecycle"][key].replace("+08:00", "+09:39")
            item["historical_trigger"]["observed_at"] = item["historical_trigger"]["observed_at"].replace("+08:00", "+09:39")

        _rewrite_json(bundle, "acquisition_path", mutate_acquisition)
        _rewrite_json(
            bundle,
            "scan_path",
            lambda item: item.__setitem__("completed_at", item["completed_at"].replace("+08:00", "+09:39")),
        )
        _rewrite_external(
            bundle,
            "log",
            Path(bundle["log"]).read_text(encoding="utf-8").replace("+08:00", "+09:39"),
        )
    with pytest.raises(InventoryValidationError, match="UTC offset"):
        _finalize(bundle)


def test_rejects_scanner_bytes_not_frozen_at_trusted_checkpoint(bundle: dict[str, object]) -> None:
    Path(bundle["scanner"]).write_bytes(b"// modified scanner\n")
    runtime_path = Path(bundle["runtime_path"])
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["scanner_identity"]["scanner_sha256"] = _sha(Path(bundle["scanner"]))
    _write_json(runtime_path, runtime)
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)


def test_failure_creates_no_result_provenance_or_exclusions(bundle: dict[str, object]) -> None:
    evidence_dir = Path(bundle["acquisition_path"]).parent
    _rewrite_external(bundle, "trace", _trace([]).replace("MNQ SEP26", "MNQ DEC26"))
    before = {path.name for path in evidence_dir.iterdir()}
    with pytest.raises(InventoryValidationError):
        _finalize(bundle)
    assert {path.name for path in evidence_dir.iterdir()} == before
    assert not (evidence_dir / "inventory_provenance.json").exists()
    assert not (evidence_dir / "exclusions.json").exists()
    assert not (evidence_dir / "source_inventory.json").exists()


def test_task4_schemas_are_used_by_loader(bundle: dict[str, object]) -> None:
    loaded = bundle["reload"]()  # type: ignore[operator]
    assert set(loaded.exact_artifact_bytes) == {
        "inventory_runtime_capture", "inventory_scan", "inventory_acquisition_evidence"
    }
    assert loaded.exact_artifact_bytes["inventory_scan"] == Path(bundle["scan_path"]).read_bytes()
    assert (SCHEMA_DIR / "inventory_scan.schema.json").is_file()
