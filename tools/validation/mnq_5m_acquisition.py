"""Validate a controlled native MNQ five-minute acquisition bundle.

This module is deliberately independent of the production ``trading`` package.
It validates source and acquisition evidence only; it never runs hierarchy,
oracle, project-result, or comparison code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from xml.etree import ElementTree


SCHEMA_VERSION = "1.0"
APPROVED_CONTRACT = {
    "contract_label": "MNQ SEP26",
    "full_name": "MNQ 09-26",
    "master_name": "MNQ",
    "expiry_month": 9,
    "expiry_year": 2026,
}
APPROVED_INSTRUMENT_IDS = {"MNQ 09-26"}
APPROVED_RANGE_START = date(2026, 6, 22)
APPROVED_RANGE_END = date(2026, 7, 24)
REQUIRED_EVIDENCE_ROLES = {
    "ninjatrader_trace",
    "ninjatrader_log",
    "ninjatrader_config",
    "trading_hours_template",
    "selection_registry",
    "toolset_manifest",
}
PROHIBITED_TRANSFORMATIONS = {
    "sorted",
    "filled",
    "interpolated",
    "resampled",
    "timezone_converted",
    "back_adjusted",
}
SOURCE_TIMESTAMP_FORMAT = "%Y%m%d %H%M%S"
LOG_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
MARKER_EVENT_TIME_RE = re.compile(r"\bevent_time=(\S+)")
PROVIDER_LIFECYCLE_RE = re.compile(
    r"\((?P<connection>[^)]+)\)\s+"
    r"(?P<provider>.+?)\.Adapter\.(?P<action>Connect|Disconnect)\b"
)
CASE_ID_RE = re.compile(
    r"^mnq-202609-5m-td(?P<trading_date>\d{4}-\d{2}-\d{2})-w(?P<stratum>0[1-9]|10)$"
)
COHORT_ID = "mnq-202609-5m-v1"


class AcquisitionValidationError(ValueError):
    """Raised when an acquisition bundle cannot prove its provenance."""


def _fail(message: str) -> None:
    raise AcquisitionValidationError(message)


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise AcquisitionValidationError(f"cannot read required artifact: {path.name}") from error


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AcquisitionValidationError(f"invalid {label}") from error
    if not isinstance(value, dict):
        _fail(f"invalid {label}")
    return value


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"missing or invalid {label}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"missing or invalid {label}")
    return value.strip()


def _parse_iso_timestamp(value: object, label: str) -> datetime:
    text = _text(value, label)
    try:
        result = datetime.fromisoformat(text)
    except ValueError as error:
        raise AcquisitionValidationError(f"invalid {label}") from error
    if result.tzinfo is None or result.utcoffset() is None:
        _fail(f"{label} must be timezone-aware")
    return result


def _verify_hash(path: Path, expected: object, label: str) -> str:
    expected_text = _text(expected, f"{label} SHA-256").lower()
    actual = _sha256(path)
    if actual != expected_text:
        _fail(f"{label} hash mismatch")
    return actual


def _validate_contract(runtime: Mapping[str, Any]) -> dict[str, Any]:
    instrument = _mapping(runtime.get("instrument"), "runtime instrument")
    instrument_id = instrument.get("instrument_id")
    if (
        any(instrument.get(key) != value for key, value in APPROVED_CONTRACT.items())
        or instrument_id not in APPROVED_INSTRUMENT_IDS
    ):
        _fail("runtime instrument is not the approved MNQ SEP26 contract")
    exchange = _text(instrument.get("exchange"), "runtime instrument exchange")
    return {**APPROVED_CONTRACT, "instrument_id": instrument_id, "exchange": exchange}


def _validate_bar_series(runtime: Mapping[str, Any]) -> dict[str, Any]:
    series = _mapping(runtime.get("bar_series"), "runtime bar series")
    if (
        series.get("type") != "Minute"
        or series.get("value") != 5
        or series.get("native") is not True
    ):
        _fail("bar series is not the approved native 5-minute Minute series")
    if series.get("exported_bar_count") != 250:
        _fail("source must contain exactly 250 exported bars")
    semantics = _text(series.get("timestamp_semantics"), "bar timestamp semantics")
    return {
        "type": "Minute",
        "value": 5,
        "native": True,
        "timestamp_semantics": semantics,
    }


def _parse_offset(value: object, label: str) -> timedelta:
    text = _text(value, label)
    match = re.fullmatch(r"(?P<sign>[+-])(?P<hours>\d{2}):(?P<minutes>\d{2})", text)
    if match is None or int(match.group("minutes")) >= 60:
        _fail(f"invalid {label}")
    result = timedelta(
        hours=int(match.group("hours")),
        minutes=int(match.group("minutes")),
    )
    return -result if match.group("sign") == "-" else result


def _validate_timezone(
    runtime: Mapping[str, Any], timestamps: list[datetime]
) -> tuple[dict[str, Any], dict[str, Any]]:
    timezone = _mapping(runtime.get("application_timezone"), "application timezone")
    required = (
        "id",
        "display_name",
        "standard_name",
        "daylight_name",
        "base_utc_offset",
        "supports_dst",
        "source_timestamp_offsets",
    )
    if any(key not in timezone for key in required):
        _fail("missing or invalid application timezone metadata")
    for key in required[:5]:
        _text(timezone[key], f"application timezone {key}")
    _parse_offset(timezone["base_utc_offset"], "application timezone base UTC offset")
    if not isinstance(timezone["supports_dst"], bool):
        _fail("missing or invalid application timezone supports_dst")
    offsets = timezone["source_timestamp_offsets"]
    if not isinstance(offsets, list) or not offsets:
        _fail("missing or invalid application timezone source offsets")
    timestamp_indexes = {timestamp: index for index, timestamp in enumerate(timestamps)}
    next_index = 0
    for offset in offsets:
        entry = _mapping(offset, "application timezone source offset")
        for key in ("first_timestamp", "last_timestamp", "utc_offset"):
            _text(entry.get(key), f"application timezone source offset {key}")
        _parse_offset(entry["utc_offset"], "application timezone source UTC offset")
        try:
            first = datetime.strptime(entry["first_timestamp"], SOURCE_TIMESTAMP_FORMAT)
            last = datetime.strptime(entry["last_timestamp"], SOURCE_TIMESTAMP_FORMAT)
            first_index = timestamp_indexes[first]
            last_index = timestamp_indexes[last]
        except (ValueError, KeyError) as error:
            raise AcquisitionValidationError(
                "application timezone offset coverage does not match the source"
            ) from error
        if first_index != next_index or last_index < first_index:
            _fail("application timezone offset coverage is not contiguous and unique")
        next_index = last_index + 1
    if next_index != len(timestamps):
        _fail("application timezone offset coverage does not match the source")

    pc_timezone = _mapping(runtime.get("pc_timezone"), "PC/log timezone")
    for key in ("id", "base_utc_offset", "supports_dst"):
        if key not in pc_timezone:
            _fail("missing or invalid PC/log timezone metadata")
    _text(pc_timezone["id"], "PC/log timezone id")
    _parse_offset(pc_timezone["base_utc_offset"], "PC/log timezone base UTC offset")
    if not isinstance(pc_timezone["supports_dst"], bool):
        _fail("missing or invalid PC/log timezone supports_dst")
    event_offsets = pc_timezone.get("acquisition_event_offsets")
    if not isinstance(event_offsets, list) or len(event_offsets) != 3:
        _fail("missing or invalid PC/log timezone event offsets")
    expected_events = ("initialized", "armed", "exported")
    for entry_value, expected_event in zip(event_offsets, expected_events, strict=True):
        entry = _mapping(entry_value, "PC/log timezone event offset")
        if entry.get("event") != expected_event:
            _fail("missing or invalid PC/log timezone event offsets")
        event_timestamp = _parse_iso_timestamp(
            entry.get("timestamp"), f"PC/log timezone {expected_event} timestamp"
        )
        declared_offset = _parse_offset(
            entry.get("utc_offset"), f"PC/log timezone {expected_event} UTC offset"
        )
        if event_timestamp.utcoffset() != declared_offset:
            _fail("PC/log timezone offset does not match its captured event timestamp")
    return dict(timezone), dict(pc_timezone)


def _parse_source_timestamp(text: str, row_number: int) -> datetime:
    try:
        return datetime.strptime(text, SOURCE_TIMESTAMP_FORMAT)
    except ValueError as error:
        raise AcquisitionValidationError(
            f"row {row_number}: malformed timestamp"
        ) from error


def _parse_decimal(text: str, row_number: int, field: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise AcquisitionValidationError(
            f"row {row_number}: malformed {field}"
        ) from error
    if not value.is_finite():
        _fail(f"row {row_number}: non-finite {field}")
    return value


def _read_source(path: Path) -> tuple[list[datetime], list[str]]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise AcquisitionValidationError("cannot read source bars") from error
    if any(not line.strip() for line in raw_lines):
        _fail("source contains a malformed empty row")
    lines = raw_lines
    if len(lines) != 250:
        _fail(f"source must contain exactly 250 non-empty rows; found {len(lines)}")

    timestamps: list[datetime] = []
    previous: datetime | None = None
    for row_number, line in enumerate(lines, start=1):
        parts = line.split(";")
        if len(parts) != 6 or any(part == "" for part in parts):
            _fail(f"row {row_number}: malformed row")
        timestamp = _parse_source_timestamp(parts[0], row_number)
        if previous is not None:
            if timestamp == previous:
                _fail(f"row {row_number}: duplicate timestamp")
            if timestamp < previous:
                _fail(f"row {row_number}: non-monotonic timestamp")
        previous = timestamp
        timestamps.append(timestamp)

        open_price, high, low, close = (
            _parse_decimal(text, row_number, field)
            for text, field in zip(parts[1:5], ("open", "high", "low", "close"))
        )
        volume = _parse_decimal(parts[5], row_number, "volume")
        if volume < 0:
            _fail(f"row {row_number}: negative volume")
        if volume != volume.to_integral_value():
            _fail(f"row {row_number}: malformed volume")
        if not (
            high >= open_price
            and high >= close
            and high >= low
            and low <= open_price
            and low <= close
        ):
            _fail(f"row {row_number}: impossible OHLC relationship")
    return timestamps, lines


def _validate_trading_hours(
    runtime: Mapping[str, Any],
    evidence_hashes: Mapping[str, str],
    trading_date: date,
    timestamps: list[datetime],
) -> dict[str, Any]:
    hours = _mapping(runtime.get("trading_hours"), "Trading Hours")
    name = _text(hours.get("name"), "Trading Hours name")
    timezone_id = _text(hours.get("timezone_id"), "Trading Hours timezone")
    definition_hash = _text(
        hours.get("definition_sha256"), "Trading Hours definition SHA-256"
    ).lower()
    if definition_hash != evidence_hashes.get("trading_hours_template"):
        _fail("Trading Hours definition hash mismatch")
    if hours.get("holiday_configuration_captured") is not True:
        _fail("missing Trading Hours holiday/partial-holiday configuration")
    calendar = hours.get("session_calendar")
    if not isinstance(calendar, list) or not calendar:
        _fail("missing Trading Hours session calendar")
    matching = [entry for entry in calendar if entry.get("trading_date") == trading_date.isoformat()]
    if len(matching) != 1:
        _fail("Trading Hours calendar does not uniquely cover the trading date")
    entry = _mapping(matching[0], "Trading Hours session")
    segments = entry.get("segments")
    if not isinstance(segments, list) or not segments:
        _fail("missing Trading Hours session segments")

    expected: list[datetime] = []
    previous_end: datetime | None = None
    for segment in segments:
        item = _mapping(segment, "Trading Hours session segment")
        begin = _parse_source_timestamp(
            _text(item.get("begin_application"), "Trading Hours segment begin"), 0
        )
        end = _parse_source_timestamp(
            _text(item.get("end_application"), "Trading Hours segment end"), 0
        )
        _text(item.get("begin_pc"), "Trading Hours segment PC-local begin")
        _text(item.get("end_pc"), "Trading Hours segment PC-local end")
        if begin >= end or (previous_end is not None and begin < previous_end):
            _fail("Trading Hours session segments are not chronological")
        previous_end = end
        current = begin + timedelta(minutes=5)
        while current < end:
            expected.append(current)
            current += timedelta(minutes=5)
        expected.append(end)

    if timestamps != expected[: len(timestamps)]:
        _fail("unexpected timestamp spacing inside the captured Trading Hours session")
    return {
        "name": name,
        "timezone_id": timezone_id,
        "definition_sha256": definition_hash,
        "holiday_configuration_captured": True,
        "session_calendar": calendar,
    }


def _validate_evidence_files(
    evidence_path: Path, evidence: Mapping[str, Any]
) -> tuple[dict[str, str], dict[str, str]]:
    entries = evidence.get("evidence_files")
    if not isinstance(entries, list):
        _fail("incomplete evidence bundle")
    roles = [entry.get("role") for entry in entries if isinstance(entry, dict)]
    if len(entries) != len(REQUIRED_EVIDENCE_ROLES) or set(roles) != REQUIRED_EVIDENCE_ROLES:
        _fail("incomplete evidence bundle")

    hashes: dict[str, str] = {}
    contents: dict[str, str] = {}
    for entry_object in entries:
        entry = _mapping(entry_object, "evidence file")
        role = _text(entry.get("role"), "evidence role")
        relative = Path(_text(entry.get("path"), f"{role} path"))
        if relative.is_absolute() or ".." in relative.parts:
            _fail("evidence paths must be relative and contained")
        path = evidence_path.parent / relative
        hashes[role] = _verify_hash(path, entry.get("sha256"), role)
        try:
            contents[role] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise AcquisitionValidationError(f"cannot read evidence file {role}") from error
    return hashes, contents


def _event_time(line: str) -> datetime | None:
    match = LOG_TIMESTAMP_RE.match(line)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return None


def _find_event(
    lines: list[str],
    *,
    needle: str,
    start: datetime,
    end: datetime,
    log_timezone: timezone,
) -> datetime | None:
    for line in lines:
        if needle not in line:
            continue
        timestamp = _event_time(line)
        if timestamp is not None:
            aware_timestamp = timestamp.replace(tzinfo=log_timezone)
            if start <= aware_timestamp <= end:
                return aware_timestamp
    return None


def _find_marker_event(
    lines: list[str],
    *,
    needle: str,
    start: datetime,
    end: datetime,
    log_timezone: timezone,
) -> datetime | None:
    for line in lines:
        if needle not in line:
            continue
        log_timestamp = _event_time(line)
        marker_match = MARKER_EVENT_TIME_RE.search(line)
        if log_timestamp is None or marker_match is None:
            continue
        marker_timestamp = _parse_iso_timestamp(
            marker_match.group(1), f"{needle} marker timestamp"
        )
        aware_log_timestamp = log_timestamp.replace(tzinfo=log_timezone)
        if start <= aware_log_timestamp <= end and start <= marker_timestamp <= end:
            return marker_timestamp
    return None


def _reject_competing_provider_activity(
    lines: list[str],
    *,
    provider: str,
    connection_name: str,
    start: datetime,
    end: datetime,
    log_timezone: timezone,
) -> None:
    for line in lines:
        match = PROVIDER_LIFECYCLE_RE.search(line)
        timestamp = _event_time(line)
        if match is None or timestamp is None:
            continue
        aware_timestamp = timestamp.replace(tzinfo=log_timezone)
        if not start <= aware_timestamp <= end:
            continue
        is_intended = (
            match.group("provider") == provider
            and match.group("connection") == connection_name
        )
        if not is_intended or match.group("action") == "Disconnect":
            _fail("competing historical-data provider activity occurred during acquisition")


def _validate_provider_proof(
    runtime: Mapping[str, Any],
    evidence: Mapping[str, Any],
    contents: Mapping[str, str],
    pc_timezone: Mapping[str, Any],
) -> dict[str, Any]:
    acquisition_id = _text(evidence.get("acquisition_id"), "acquisition id")
    if runtime.get("acquisition_id") != acquisition_id:
        _fail("provider/reload evidence does not match the runtime acquisition session")
    provider = _text(evidence.get("intended_provider"), "intended provider")
    connection_name = _text(
        evidence.get("intended_connection_name"), "intended connection name"
    )
    if runtime.get("connection_snapshot_phase") != (
        "immediately after operator arm and before export"
    ):
        _fail("provider connection snapshot is not bound to the acquisition arm event")
    connections = runtime.get("active_connections")
    if not isinstance(connections, list):
        _fail("missing provider/reload evidence")
    connected = [
        item
        for item in connections
        if isinstance(item, dict)
        and item.get("price_status") == "Connected"
        and isinstance(item.get("instrument_types"), list)
        and "Future" in item["instrument_types"]
    ]
    matching = [
        item
        for item in connected
        if item.get("provider") == provider and item.get("name") == connection_name
    ]
    if len(matching) != 1:
        _fail("provider/reload evidence does not prove the intended provider")
    if len(connected) != 1:
        _fail("competing historical-data provider connection is active")

    try:
        config_root = ElementTree.fromstring(contents["ninjatrader_config"])
    except ElementTree.ParseError as error:
        raise AcquisitionValidationError("invalid NinjaTrader configuration evidence") from error
    preferred_future = config_root.findtext(".//PreferredFutureConnection")
    preferred_realtime_future = config_root.findtext(".//PreferredRealtimeFutureConnection")
    if (
        preferred_future != connection_name
        or preferred_realtime_future != connection_name
    ):
        _fail("preferred historical connection does not match the intended MNQ connection")

    started = _parse_iso_timestamp(evidence.get("acquisition_started_at"), "acquisition start")
    reload_declared = _parse_iso_timestamp(
        evidence.get("reload_all_historical_data_initiated_at"),
        "Reload All Historical Data timestamp",
    )
    armed_declared = _parse_iso_timestamp(evidence.get("export_armed_at"), "export arm")
    exported = _parse_iso_timestamp(evidence.get("export_completed_at"), "export completion")
    if not started <= reload_declared <= armed_declared <= exported:
        _fail("provider/reload evidence chronology is invalid")
    log_timezone_id = _text(evidence.get("log_timezone_id"), "log timezone id")
    if log_timezone_id != pc_timezone.get("id"):
        _fail("log timezone does not match the captured PC timezone")
    log_offset = _parse_offset(evidence.get("log_utc_offset"), "log UTC offset")
    runtime_event_offsets = pc_timezone["acquisition_event_offsets"]
    if any(
        _parse_offset(entry["utc_offset"], "PC/log timezone event UTC offset")
        != log_offset
        for entry in runtime_event_offsets
    ):
        _fail("PC/log timezone offset does not match acquisition event offsets")
    if any(
        timestamp.utcoffset() != log_offset
        for timestamp in (started, reload_declared, armed_declared, exported)
    ):
        _fail("PC/log timezone offset does not match acquisition evidence")
    log_tz = timezone(log_offset)
    lines = (contents["ninjatrader_trace"] + "\n" + contents["ninjatrader_log"]).splitlines()
    marker = f"acquisition={acquisition_id}"
    initialized_time = _find_marker_event(
        lines,
        needle=marker + " exporter initialized",
        start=started,
        end=exported,
        log_timezone=log_tz,
    )
    armed_time = _find_marker_event(
        lines,
        needle=marker + " export armed after reload",
        start=started,
        end=exported,
        log_timezone=log_tz,
    )
    completed_time = _find_marker_event(
        lines,
        needle=marker + " export complete",
        start=started,
        end=exported,
        log_timezone=log_tz,
    )
    connection_time = _find_event(
        lines,
        needle=f"({connection_name}) {provider}.Adapter.Connect",
        start=started,
        end=exported,
        log_timezone=log_tz,
    )
    reload_time = _find_event(
        lines,
        needle="Reload All Historical Data initiated",
        start=reload_declared,
        end=exported,
        log_timezone=log_tz,
    )
    request_time = _find_event(
        lines,
        needle="Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26'",
        start=reload_declared,
        end=exported,
        log_timezone=log_tz,
    )
    _reject_competing_provider_activity(
        lines,
        provider=provider,
        connection_name=connection_name,
        start=started,
        end=exported,
        log_timezone=log_tz,
    )
    if (
        initialized_time is None
        or armed_time is None
        or completed_time is None
        or connection_time is None
        or reload_time is None
        or request_time is None
    ):
        _fail("provider/reload evidence chain is incomplete")
    if not (
        started <= connection_time <= request_time
        and started <= initialized_time <= reload_time <= request_time
        and request_time <= armed_time <= completed_time
    ):
        _fail("provider/reload evidence chronology is invalid")
    if reload_time != reload_declared.astimezone(log_tz):
        _fail("Reload All Historical Data evidence does not match its declared time")
    if armed_time != armed_declared or completed_time != exported:
        _fail("export completion evidence does not match its declared time")
    runtime_events = {
        entry["event"]: _parse_iso_timestamp(
            entry["timestamp"], f"PC/log timezone {entry['event']} timestamp"
        )
        for entry in runtime_event_offsets
    }
    if (
        runtime_events["initialized"] != initialized_time
        or runtime_events["armed"] != armed_time
        or runtime_events["exported"] != completed_time
    ):
        _fail("PC/log timezone event timestamps do not match acquisition markers")
    return {
        "status": "PROVEN",
        "intended_provider": provider,
        "intended_connection_name": connection_name,
        "active_connection": matching[0],
        "acquisition_id": acquisition_id,
        "acquisition_started_at": started.isoformat(),
        "reload_all_historical_data_initiated_at": reload_declared.isoformat(),
        "export_armed_at": armed_declared.isoformat(),
        "matching_historical_request_observed": True,
        "export_completed_at": exported.isoformat(),
        "competing_historical_provider_connections": 0,
        "preferred_future_connection": connection_name,
        "log_timezone_id": log_timezone_id,
        "log_utc_offset": _text(evidence.get("log_utc_offset"), "log UTC offset"),
    }


def finalize_provenance(
    *,
    source_path: str | Path,
    runtime_capture_path: str | Path,
    acquisition_evidence_path: str | Path,
    exporter_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, object]:
    """Validate an acquisition bundle and return its frozen provenance."""

    source = Path(source_path)
    runtime_path = Path(runtime_capture_path)
    evidence_path = Path(acquisition_evidence_path)
    exporter = Path(exporter_path)
    runtime = _load_object(runtime_path, "runtime capture")
    evidence = _load_object(evidence_path, "acquisition evidence")
    if runtime.get("schema_version") != SCHEMA_VERSION or evidence.get("schema_version") != SCHEMA_VERSION:
        _fail("unsupported acquisition schema version")

    source_hash = _sha256(source)
    if runtime.get("source_sha256") != source_hash:
        _fail("source hash mismatch against runtime capture")
    runtime_hash = _verify_hash(
        runtime_path, evidence.get("runtime_capture_sha256"), "runtime capture"
    )
    exporter_hash = _verify_hash(
        exporter, evidence.get("exporter_sha256"), "exporter"
    )
    evidence_hashes, evidence_contents = _validate_evidence_files(evidence_path, evidence)
    evidence_hash = _sha256(evidence_path)

    transformations = _mapping(evidence.get("transformations"), "transformation declarations")
    if set(transformations) != PROHIBITED_TRANSFORMATIONS:
        _fail("incomplete transformation declarations")
    if any(transformations[name] is not False for name in PROHIBITED_TRANSFORMATIONS):
        _fail("prohibited transformation was declared")

    try:
        trading_date = date.fromisoformat(_text(evidence.get("trading_date"), "trading date"))
    except ValueError as error:
        raise AcquisitionValidationError("invalid trading date") from error
    if not APPROVED_RANGE_START <= trading_date <= APPROVED_RANGE_END:
        _fail("trading date is outside the approved candidate date range")

    cohort_id = _text(evidence.get("cohort_id"), "cohort id")
    case_id = _text(evidence.get("case_id"), "case id")
    case_match = CASE_ID_RE.fullmatch(case_id)
    if (
        cohort_id != COHORT_ID
        or case_match is None
        or case_match.group("trading_date") != trading_date.isoformat()
    ):
        _fail("case/cohort identity does not match the approved cohort policy")
    if any(
        runtime.get(field) != evidence.get(field)
        for field in ("cohort_id", "case_id", "trading_date")
    ):
        _fail("runtime/evidence identity mismatch")

    contract = _validate_contract(runtime)
    bar_series = _validate_bar_series(runtime)
    timestamps, lines = _read_source(source)
    application_timezone, pc_timezone = _validate_timezone(runtime, timestamps)
    if runtime["bar_series"]["exported_bar_count"] != len(lines):
        _fail("runtime exported bar count does not match the source")
    trading_hours = _validate_trading_hours(
        runtime, evidence_hashes, trading_date, timestamps
    )
    provider = _validate_provider_proof(
        runtime, evidence, evidence_contents, pc_timezone
    )
    ninja_version = _text(runtime.get("ninjatrader_version"), "NinjaTrader version")
    export_method = _text(runtime.get("export_method"), "source export method")
    original_export_identity = _text(
        runtime.get("original_export_identity"), "original export identity"
    )
    exported_at = _parse_iso_timestamp(runtime.get("exported_at"), "runtime export timestamp")
    if exported_at != _parse_iso_timestamp(
        provider["export_completed_at"], "provider export completion"
    ):
        _fail("runtime export timestamp does not match acquisition evidence")

    artifact_hashes = {
        "source": source_hash,
        "runtime_capture": runtime_hash,
        "acquisition_evidence": evidence_hash,
        "exporter": exporter_hash,
        **evidence_hashes,
    }
    quality_findings = evidence.get("source_quality_findings")
    known_missing_bars = evidence.get("known_missing_bars")
    scheduled_exclusions = evidence.get("scheduled_exclusions")
    known_limitations = evidence.get("known_limitations")
    for value, label in (
        (quality_findings, "source quality findings"),
        (known_missing_bars, "known missing bars"),
        (scheduled_exclusions, "scheduled exclusions"),
        (known_limitations, "known limitations"),
    ):
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            _fail(f"missing or invalid {label}")
    selected_row_derivation = _text(
        evidence.get("selected_row_derivation"), "selected row/range derivation"
    )
    if selected_row_derivation != (
        "first 250 native 5-minute bars of the declared Trading Hours session"
    ):
        _fail("selected row/range derivation is not the approved policy")
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "cohort_id": cohort_id,
        "case_id": case_id,
        "contract": contract,
        "ninjatrader_version": ninja_version,
        "provider_acquisition": provider,
        "application_timezone": application_timezone,
        "pc_log_timezone": pc_timezone,
        "trading_hours": trading_hours,
        "bar_series": bar_series,
        "source": {
            "filename": source.name,
            "trading_date": trading_date.isoformat(),
            "first_timestamp": timestamps[0].strftime(SOURCE_TIMESTAMP_FORMAT),
            "last_timestamp": timestamps[-1].strftime(SOURCE_TIMESTAMP_FORMAT),
            "row_count": len(lines),
            "sha256": source_hash,
            "original_source_sha256": _text(
                runtime.get("source_sha256"), "original source SHA-256"
            ),
            "frozen_case_sha256": source_hash,
            "exported_at": exported_at.isoformat(),
            "export_method": export_method,
            "original_export_identity": original_export_identity,
            "selected_row_derivation": selected_row_derivation,
            "known_missing_bars": known_missing_bars,
            "scheduled_exclusions": scheduled_exclusions,
            "known_limitations": known_limitations,
        },
        "artifact_hashes": artifact_hashes,
        "source_quality_findings": quality_findings,
        "transformations": transformations,
        "approved_policy": {
            "contract": "MNQ September 2026",
            "candidate_date_start": APPROVED_RANGE_START.isoformat(),
            "candidate_date_end": APPROVED_RANGE_END.isoformat(),
            "single_expiry_only": True,
            "existing_frozen_5m_case_excluded": True,
            "june_rollover_transition_excluded": True,
        },
    }

    if output_path is not None:
        destination = Path(output_path)
        if destination.resolve() == source.resolve():
            _fail("provenance output must remain distinct from the raw source")
        destination.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="",
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and freeze MNQ five-minute acquisition provenance."
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--runtime-capture", required=True, type=Path)
    parser.add_argument("--acquisition-evidence", required=True, type=Path)
    parser.add_argument("--exporter", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        finalize_provenance(
            source_path=args.source,
            runtime_capture_path=args.runtime_capture,
            acquisition_evidence_path=args.acquisition_evidence,
            exporter_path=args.exporter,
            output_path=args.output,
        )
    except AcquisitionValidationError as error:
        parser.exit(2, f"STOP: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
