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

try:
    from tools.validation.mnq_5m_checkpoint_verify import (
        DEFAULT_REPOSITORY_IDENTITY,
        REQUIRED_TOOLSET_COMPONENT_PATHS,
        CheckpointVerificationError,
        verify_checkpoints,
    )
except ModuleNotFoundError as error:
    if error.name != "tools":
        raise
    from mnq_5m_checkpoint_verify import (  # type: ignore[no-redef]
        DEFAULT_REPOSITORY_IDENTITY,
        REQUIRED_TOOLSET_COMPONENT_PATHS,
        CheckpointVerificationError,
        verify_checkpoints,
    )


RUNTIME_CAPTURE_SCHEMA_VERSION = "1.1"
ACQUISITION_EVIDENCE_SCHEMA_VERSION = "1.2"
PROVENANCE_SCHEMA_VERSION = "1.2"
BOUND_ARTIFACT_SCHEMA_VERSION = "1.0"
PINNED_PRODUCTION_HIERARCHY_COMMIT = (
    "04a73e1401d44688660b211d9db6918113482856"
)
APPROVED_CONTRACT = {
    "contract_label": "MNQ SEP26",
    "master_name": "MNQ",
    "expiry_month": 9,
    "expiry_year": 2026,
}
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
LOG_TIMESTAMP_RE = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[.:](?P<fraction>\d+)"
)
MARKER_EVENT_TIME_RE = re.compile(r"\bevent_time=(\S+)")
PROVIDER_LIFECYCLE_RE = re.compile(
    r"\((?P<connection>[^)]+)\)\s+"
    r"(?P<provider>.+?)\.Adapter\.(?P<action>Connect|Disconnect)\b"
)
REQUEST_BARS_RE = re.compile(
    r"Cbi\.Instrument\.RequestBars \(to Provider\): "
    r"instrument='(?P<instrument>[^']+)' "
    r"from='(?P<start>[^']+)' to='(?P<end>[^']+)' "
    r"period='(?P<period>[^']+)'"
)
HDS_CONNECT_RE = re.compile(
    r"Server\.HdsClient\.Connect: type=HDS "
    r"server='(?P<host>[^']+)' port=(?P<port>\d+) .*\buseSsl=(?P<ssl>True|False)\b"
)
HDS_HOST_RE = re.compile(r"^hds-us-nt-\d+\.ninjatrader\.com$")
MARKER_LOG_SKEW_LIMIT = timedelta(seconds=1)
CASE_ID_RE = re.compile(
    r"^mnq-202609-5m-td(?P<trading_date>\d{4}-\d{2}-\d{2})-w(?P<stratum>0[1-9]|10)$"
)
COHORT_ID = "mnq-202609-5m-v1"
APPROVED_CONTRACT_POLICY = {
    "contract_label": "MNQ SEP26",
    "full_name": "MNQ SEP26",
    "expiry_month": 9,
    "expiry_year": 2026,
    "candidate_date_start": APPROVED_RANGE_START.isoformat(),
    "candidate_date_end": APPROVED_RANGE_END.isoformat(),
}
APPROVED_SELECTION_ALGORITHM = {
    "id": "CHRONOLOGICAL_TEN_STRATA_EARLIEST",
    "version": "1.0",
    "stratum_count": 10,
}
APPROVED_WINDOW_POLICY = "FIRST_250_NATIVE_5M_SESSION_BARS"
APPROVED_CANONICALIZATION = (
    "JSON_UTF8_SORTED_KEYS_COMPACT_EXCLUDE_AGGREGATE_PAYLOAD_SHA256"
)
APPROVED_TOOLSET_STAGE = "SOURCE_ACQUISITION"
APPROVED_FROZEN_STATUS = "FROZEN_FOR_SOURCE_ACQUISITION"
APPROVED_INVENTORY_STATUS = "FROZEN_PRE_EXECUTION"
APPROVED_DEFERRED_COMPONENTS = {
    "independent_oracle",
    "blind_project_runner",
    "comparator",
    "cohort_aggregator",
}
APPROVED_EXCLUSION_REASONS = {
    "OUTSIDE_POLICY",
    "INCOMPLETE_PROVENANCE",
    "FEWER_THAN_250_NATIVE_BARS",
    "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS",
    "TRADING_HOURS_INCONSISTENCY",
    "MALFORMED_OR_NON_FINITE_OHLCV",
    "INVALID_OHLC_GEOMETRY",
    "UNEXPECTED_MISSING_BARS",
    "SOURCE_CORRUPTION",
    "SOURCE_HASH_MISMATCH",
}
SELECTION_REFERENCE_PATHS = {
    "source_inventory": "validation/mnq_5m_multiwindow/source_inventory.json",
    "exclusion_ledger": "validation/mnq_5m_multiwindow/exclusions.json",
}
TOOLSET_COMPONENT_PATHS = dict(REQUIRED_TOOLSET_COMPONENT_PATHS)

PROVIDER_PROFILE = {
    "id": "NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1",
    "runtime_provider_id": "Provider31",
    "trace_adapter": "Tradovate.Adapter",
    "trace_adapter_name": "Tradovate",
    "historical_service": "NinjaTrader HDS",
    "contract_label": "MNQ SEP26",
}
APPROVED_CONNECTION_NAME = "My NinjaTrader"
HISTORICAL_TRIGGER_KEYS = {
    "method",
    "request_source_role",
    "adapter_connection_initiated_at",
    "connection_ready_at",
    "hds_connected_at",
    "pre_request_realtime_at",
    "request_observed_at",
    "post_request_initialized_at",
    "post_request_realtime_at",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


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


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], label: str
) -> None:
    if set(value) != expected:
        _fail(f"missing or invalid {label} fields")


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
    if any(instrument.get(key) != value for key, value in APPROVED_CONTRACT.items()):
        _fail("runtime instrument is not the approved MNQ SEP26 contract")
    full_name = instrument.get("full_name")
    instrument_id = instrument.get("instrument_id")
    if (
        not isinstance(full_name, str)
        or not full_name
        or full_name != full_name.strip()
        or not isinstance(instrument_id, str)
        or not instrument_id
        or instrument_id != instrument_id.strip()
    ):
        _fail("missing or invalid exact runtime instrument identity")
    if full_name != instrument_id:
        _fail(
            "runtime instrument identity fields disagree for approved MNQ SEP26 contract"
        )
    exchange = _text(instrument.get("exchange"), "runtime instrument exchange")
    return {
        "contract_label": APPROVED_CONTRACT["contract_label"],
        "full_name": full_name,
        "master_name": APPROVED_CONTRACT["master_name"],
        "instrument_id": instrument_id,
        "expiry_month": APPROVED_CONTRACT["expiry_month"],
        "expiry_year": APPROVED_CONTRACT["expiry_year"],
        "exchange": exchange,
    }


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
) -> tuple[dict[str, str], dict[str, str], dict[str, Path]]:
    entries = evidence.get("evidence_files")
    if not isinstance(entries, list):
        _fail("incomplete evidence bundle")
    roles = [entry.get("role") for entry in entries if isinstance(entry, dict)]
    if len(entries) != len(REQUIRED_EVIDENCE_ROLES) or set(roles) != REQUIRED_EVIDENCE_ROLES:
        _fail("incomplete evidence bundle")

    hashes: dict[str, str] = {}
    contents: dict[str, str] = {}
    paths: dict[str, Path] = {}
    for entry_object in entries:
        entry = _mapping(entry_object, "evidence file")
        role = _text(entry.get("role"), "evidence role")
        relative = Path(_text(entry.get("path"), f"{role} path"))
        if relative.is_absolute() or ".." in relative.parts:
            _fail("evidence paths must be relative and contained")
        path = _contained_artifact_path(
            evidence_path.parent, relative.as_posix(), f"evidence {role}"
        )
        paths[role] = path
        try:
            artifact_bytes = path.read_bytes()
            contents[role] = artifact_bytes.decode("utf-8")
        except (OSError, UnicodeError) as error:
            raise AcquisitionValidationError(f"cannot read evidence file {role}") from error
        actual_hash = hashlib.sha256(artifact_bytes).hexdigest()
        if entry.get("sha256") != actual_hash:
            _fail(f"{role} hash mismatch")
        hashes[role] = actual_hash
    return hashes, contents, paths


def _verified_bundle_hashes(attestation: Mapping[str, Any]) -> dict[str, str]:
    required = {
        "toolset_manifest": "toolset",
        "selection_registry": "selection",
        "source_inventory": "selection",
        "exclusion_ledger": "selection",
    }
    artifacts = attestation.get("artifacts")
    if not isinstance(artifacts, list):
        _fail("checkpoint verification did not return artifact identities")
    result: dict[str, str] = {}
    for role, stage in required.items():
        matches = [
            item
            for item in artifacts
            if isinstance(item, dict)
            and item.get("role") == role
            and item.get("stage") == stage
        ]
        if len(matches) != 1:
            _fail(f"verified checkpoint artifact is missing or duplicated: {role}")
        artifact_hash = matches[0].get("sha256")
        if (
            not isinstance(artifact_hash, str)
            or SHA256_RE.fullmatch(artifact_hash) is None
            or matches[0].get("bundle_sha256") != artifact_hash
        ):
            _fail(f"verified checkpoint artifact hash is invalid: {role}")
        result[role] = artifact_hash
    return result


def _canonical_payload_sha256(
    value: Mapping[str, Any], hash_field: str = "aggregate_payload_sha256"
) -> str:
    payload = dict(value)
    payload.pop(hash_field, None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_payload_hash(value: Mapping[str, Any], label: str) -> str:
    declared = _text(value.get("aggregate_payload_sha256"), f"{label} aggregate hash")
    if SHA256_RE.fullmatch(declared) is None:
        _fail(f"invalid {label} aggregate hash")
    actual = _canonical_payload_sha256(value)
    if declared != actual:
        _fail(f"{label} aggregate hash mismatch")
    return declared


def _parse_json_text(value: str, label: str) -> dict[str, Any]:
    try:
        result = json.loads(value)
    except json.JSONDecodeError as error:
        raise AcquisitionValidationError(f"invalid {label}") from error
    if not isinstance(result, dict):
        _fail(f"invalid {label}")
    return result


def _contained_artifact_path(root: Path, value: object, label: str) -> Path:
    relative = Path(_text(value, f"{label} bundle path"))
    if relative.is_absolute() or ".." in relative.parts:
        _fail(f"{label} bundle path must be relative and contained")
    root_resolved = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError:
        _fail(f"{label} bundle path must be relative and contained")
    return path


def _validate_commit(value: object, label: str) -> str:
    commit = _text(value, label)
    if COMMIT_RE.fullmatch(commit) is None:
        _fail(f"invalid {label}")
    return commit


def _parse_policy_date(value: object, label: str) -> date:
    try:
        return date.fromisoformat(_text(value, label))
    except ValueError as error:
        raise AcquisitionValidationError(f"invalid {label}") from error


def _validate_contract_policy(value: object, label: str) -> dict[str, Any]:
    policy = _mapping(value, label)
    if policy != APPROVED_CONTRACT_POLICY:
        _fail(f"{label} does not match the approved contract/date policy")
    return dict(policy)


def _load_bound_reference(
    *,
    bundle_root: Path,
    reference_value: object,
    reference_name: str,
    verified_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    label = reference_name.replace("_", " ")
    reference = _mapping(reference_value, f"selection registry {label} reference")
    _require_exact_keys(
        reference,
        {"path", "bundle_path", "schema_version", "sha256", "producing_checkpoint"},
        f"selection registry {label} reference",
    )
    if reference.get("path") != SELECTION_REFERENCE_PATHS[reference_name]:
        _fail(f"selection registry {label} path is not approved")
    if reference.get("schema_version") != BOUND_ARTIFACT_SCHEMA_VERSION:
        _fail(f"selection registry {label} schema version is not supported")
    checkpoint = _validate_commit(
        reference.get("producing_checkpoint"),
        f"selection registry {label} producing checkpoint",
    )
    path = _contained_artifact_path(
        bundle_root, reference.get("bundle_path"), f"selection registry {label}"
    )
    declared_hash = _text(
        reference.get("sha256"), f"selection registry {label} SHA-256"
    )
    try:
        document_bytes = path.read_bytes()
        document_text = document_bytes.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise AcquisitionValidationError(f"cannot read {label}") from error
    if (
        SHA256_RE.fullmatch(declared_hash) is None
        or hashlib.sha256(document_bytes).hexdigest() != declared_hash
        or declared_hash != verified_sha256
    ):
        _fail(f"{label} hash mismatch")
    document = _parse_json_text(document_text, label)
    return document, {
        "path": reference["path"],
        "schema_version": reference["schema_version"],
        "sha256": declared_hash,
        "producing_checkpoint": checkpoint,
    }


def _validate_inventory(
    value: Mapping[str, Any], *, expected_predecessor_checkpoint: str
) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    label = "source inventory"
    _require_exact_keys(
        value,
        {
            "schema_version",
            "status",
            "cohort_id",
            "contract_policy",
            "producing_checkpoint",
            "entries",
            "aggregate_payload_sha256",
        },
        label,
    )
    if (
        value.get("schema_version") != BOUND_ARTIFACT_SCHEMA_VERSION
        or value.get("status") != APPROVED_INVENTORY_STATUS
        or value.get("cohort_id") != COHORT_ID
    ):
        _fail(f"invalid {label}")
    _validate_contract_policy(value.get("contract_policy"), label)
    if value.get("producing_checkpoint") != expected_predecessor_checkpoint:
        _fail(f"{label} producing checkpoint mismatch")
    _validate_payload_hash(value, label)

    entries = value.get("entries")
    if not isinstance(entries, list):
        _fail(f"invalid {label} entries")
    eligible_dates: list[str] = []
    observed_dates: list[date] = []
    exclusions: dict[str, tuple[str, ...]] = {}
    previous: date | None = None
    seen: set[date] = set()
    for entry_value in entries:
        entry = _mapping(entry_value, f"{label} entry")
        _require_exact_keys(
            entry,
            {"trading_date", "eligible", "exclusion_reasons"},
            f"{label} entry",
        )
        trading_date = _parse_policy_date(
            entry.get("trading_date"), f"{label} trading date"
        )
        if trading_date in seen or (previous is not None and trading_date <= previous):
            _fail(f"{label} dates must be strictly chronological and unique")
        if not APPROVED_RANGE_START <= trading_date <= APPROVED_RANGE_END:
            _fail(f"{label} date is outside the approved policy")
        seen.add(trading_date)
        observed_dates.append(trading_date)
        previous = trading_date
        eligible = entry.get("eligible")
        reasons = entry.get("exclusion_reasons")
        if not isinstance(eligible, bool) or not isinstance(reasons, list):
            _fail(f"invalid {label} eligibility")
        if (
            any(
                not isinstance(reason, str)
                or reason not in APPROVED_EXCLUSION_REASONS
                for reason in reasons
            )
            or len(reasons) != len(set(reasons))
            or (eligible and reasons)
            or (not eligible and not reasons)
        ):
            _fail(f"invalid {label} eligibility")
        iso_date = trading_date.isoformat()
        if eligible:
            eligible_dates.append(iso_date)
        else:
            exclusions[iso_date] = tuple(reasons)
    expected_dates: list[date] = []
    candidate = APPROVED_RANGE_START
    while candidate <= APPROVED_RANGE_END:
        if candidate.weekday() < 5:
            expected_dates.append(candidate)
        candidate += timedelta(days=1)
    if observed_dates != expected_dates:
        _fail(f"{label} must cover every candidate trading date")
    if len(eligible_dates) < 10:
        _fail(f"{label} has fewer than ten eligible dates")
    return eligible_dates, exclusions


def _validate_exclusion_ledger(
    value: Mapping[str, Any],
    *,
    expected_predecessor_checkpoint: str,
    inventory_exclusions: Mapping[str, tuple[str, ...]],
) -> None:
    label = "exclusion ledger"
    _require_exact_keys(
        value,
        {
            "schema_version",
            "status",
            "cohort_id",
            "producing_checkpoint",
            "entries",
            "aggregate_payload_sha256",
        },
        label,
    )
    if (
        value.get("schema_version") != BOUND_ARTIFACT_SCHEMA_VERSION
        or value.get("status") != APPROVED_INVENTORY_STATUS
        or value.get("cohort_id") != COHORT_ID
        or value.get("producing_checkpoint") != expected_predecessor_checkpoint
    ):
        _fail(f"invalid {label}")
    _validate_payload_hash(value, label)
    entries = value.get("entries")
    if not isinstance(entries, list):
        _fail(f"invalid {label} entries")
    observed: dict[str, tuple[str, ...]] = {}
    previous: date | None = None
    for entry_value in entries:
        entry = _mapping(entry_value, f"{label} entry")
        _require_exact_keys(
            entry, {"trading_date", "reasons"}, f"{label} entry"
        )
        trading_date = _parse_policy_date(
            entry.get("trading_date"), f"{label} trading date"
        )
        if previous is not None and trading_date <= previous:
            _fail(f"{label} dates must be strictly chronological and unique")
        if not APPROVED_RANGE_START <= trading_date <= APPROVED_RANGE_END:
            _fail(f"{label} date is outside the approved policy")
        previous = trading_date
        reasons = entry.get("reasons")
        if (
            not isinstance(reasons, list)
            or not reasons
            or len(reasons) != len(set(reasons))
            or any(
                not isinstance(reason, str) or reason not in APPROVED_EXCLUSION_REASONS
                for reason in reasons
            )
        ):
            _fail(f"invalid {label} reasons")
        observed[trading_date.isoformat()] = tuple(reasons)
    if observed != dict(inventory_exclusions):
        _fail(f"{label} does not exactly match source inventory exclusions")


def _validate_selection_registry(
    *,
    evidence_path: Path,
    evidence: Mapping[str, Any],
    registry_text: str,
    cohort_id: str,
    case_id: str,
    trading_date: date,
    trusted_checkpoint: str,
    trusted_toolset_checkpoint: str,
    verified_bundle_hashes: Mapping[str, str],
) -> dict[str, Any]:
    label = "selection registry"
    registry = _parse_json_text(registry_text, label)
    _require_exact_keys(
        registry,
        {
            "schema_version",
            "status",
            "cohort_id",
            "contract_policy",
            "selection_algorithm",
            "selection_count",
            "source_inventory",
            "exclusion_ledger",
            "producing_checkpoint",
            "selection_influence",
            "selections",
            "aggregate_payload_sha256",
        },
        label,
    )
    if (
        registry.get("schema_version") != BOUND_ARTIFACT_SCHEMA_VERSION
        or registry.get("status") != APPROVED_FROZEN_STATUS
        or registry.get("cohort_id") != cohort_id
        or registry.get("selection_algorithm") != APPROVED_SELECTION_ALGORITHM
        or registry.get("selection_count") != 10
    ):
        _fail(f"invalid {label}")
    _validate_contract_policy(registry.get("contract_policy"), label)
    checkpoint = _validate_commit(
        registry.get("producing_checkpoint"), f"{label} producing checkpoint"
    )
    if evidence.get("expected_selection_checkpoint") != trusted_checkpoint:
        _fail(f"{label} producing checkpoint mismatch")
    influence = _mapping(registry.get("selection_influence"), f"{label} influence")
    if influence != {
        "hierarchy_output_used": False,
        "oracle_output_used": False,
        "project_output_used": False,
    }:
        _fail(f"{label} must explicitly exclude hierarchy/oracle/project influence")
    aggregate_hash = _validate_payload_hash(registry, label)

    inventory, inventory_binding = _load_bound_reference(
        bundle_root=evidence_path.parent,
        reference_value=registry.get("source_inventory"),
        reference_name="source_inventory",
        verified_sha256=verified_bundle_hashes["source_inventory"],
    )
    exclusions, exclusions_binding = _load_bound_reference(
        bundle_root=evidence_path.parent,
        reference_value=registry.get("exclusion_ledger"),
        reference_name="exclusion_ledger",
        verified_sha256=verified_bundle_hashes["exclusion_ledger"],
    )
    eligible_dates, inventory_exclusions = _validate_inventory(
        inventory,
        expected_predecessor_checkpoint=trusted_toolset_checkpoint,
    )
    _validate_exclusion_ledger(
        exclusions,
        expected_predecessor_checkpoint=trusted_toolset_checkpoint,
        inventory_exclusions=inventory_exclusions,
    )
    if inventory_binding["producing_checkpoint"] != exclusions_binding["producing_checkpoint"]:
        _fail(f"{label} inventory/exclusion checkpoints disagree")
    if checkpoint != inventory_binding["producing_checkpoint"]:
        _fail(f"{label} producing checkpoint mismatch")

    selections = registry.get("selections")
    if not isinstance(selections, list) or len(selections) != 10:
        _fail(f"invalid {label} selections")
    selected_case_ids: set[str] = set()
    selected_dates: set[str] = set()
    count = len(eligible_dates)
    normalized: list[dict[str, Any]] = []
    for zero_index, selection_value in enumerate(selections):
        selection = _mapping(selection_value, f"{label} selection")
        stratum = zero_index + 1
        start = zero_index * count // 10
        end = (zero_index + 1) * count // 10 - 1
        expected_date = eligible_dates[start]
        expected_case = f"mnq-202609-5m-td{expected_date}-w{stratum:02d}"
        expected = {
            "case_id": expected_case,
            "trading_date": expected_date,
            "stratum_number": stratum,
            "stratum_start_index": start,
            "stratum_end_index": end,
            "selected_eligible_index": start,
            "window_policy": APPROVED_WINDOW_POLICY,
        }
        if selection != expected:
            _fail(f"{label} selection does not match deterministic ten-stratum policy")
        if expected_case in selected_case_ids or expected_date in selected_dates:
            _fail(f"{label} selections must have unique case IDs and dates")
        selected_case_ids.add(expected_case)
        selected_dates.add(expected_date)
        normalized.append(dict(selection))
    matches = [item for item in normalized if item["case_id"] == case_id]
    if (
        len(matches) != 1
        or matches[0]["trading_date"] != trading_date.isoformat()
    ):
        _fail(f"{label} does not contain the current case/date exactly once")
    return {
        "status": APPROVED_FROZEN_STATUS,
        "producing_checkpoint": checkpoint,
        "trusted_checkpoint": trusted_checkpoint,
        "aggregate_payload_sha256": aggregate_hash,
        "selection": matches[0],
        "inventory": inventory_binding,
        "exclusion_ledger": exclusions_binding,
    }


def _validate_toolset_manifest(
    *,
    evidence_path: Path,
    evidence: Mapping[str, Any],
    manifest_text: str,
    exporter_hash: str,
    trusted_checkpoint: str,
) -> dict[str, Any]:
    label = "toolset manifest"
    manifest = _parse_json_text(manifest_text, label)
    _require_exact_keys(
        manifest,
        {
            "schema_version",
            "stage",
            "status",
            "cohort_id",
            "producing_checkpoint",
            "pinned_production_hierarchy_commit",
            "runtime",
            "canonicalization",
            "components",
            "deferred_components",
            "aggregate_payload_sha256",
        },
        label,
    )
    if (
        manifest.get("schema_version") != BOUND_ARTIFACT_SCHEMA_VERSION
        or manifest.get("stage") != APPROVED_TOOLSET_STAGE
        or manifest.get("status") != APPROVED_FROZEN_STATUS
        or manifest.get("cohort_id") != COHORT_ID
        or manifest.get("pinned_production_hierarchy_commit")
        != PINNED_PRODUCTION_HIERARCHY_COMMIT
        or manifest.get("canonicalization") != APPROVED_CANONICALIZATION
    ):
        _fail(f"invalid {label}")
    checkpoint = _validate_commit(
        manifest.get("producing_checkpoint"), f"{label} producing checkpoint"
    )
    if evidence.get("expected_toolset_checkpoint") != trusted_checkpoint:
        _fail(f"{label} producing checkpoint mismatch")
    runtime = _mapping(manifest.get("runtime"), f"{label} runtime")
    _require_exact_keys(
        runtime, {"implementation", "version", "dependencies"}, f"{label} runtime"
    )
    _text(runtime.get("implementation"), f"{label} runtime implementation")
    _text(runtime.get("version"), f"{label} runtime version")
    dependencies = runtime.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        _fail(f"invalid {label} runtime dependencies")
    dependency_names: set[str] = set()
    for dependency_value in dependencies:
        dependency = _mapping(dependency_value, f"{label} runtime dependency")
        _require_exact_keys(
            dependency, {"name", "version"}, f"{label} runtime dependency"
        )
        dependency_name = _text(
            dependency.get("name"), f"{label} dependency name"
        )
        if dependency_name in dependency_names:
            _fail(f"duplicate {label} runtime dependency")
        dependency_names.add(dependency_name)
        _text(dependency.get("version"), f"{label} dependency version")
    deferred = manifest.get("deferred_components")
    if (
        not isinstance(deferred, list)
        or len(deferred) != len(set(deferred))
        or set(deferred) != APPROVED_DEFERRED_COMPONENTS
    ):
        _fail(f"invalid {label} deferred components")
    aggregate_hash = _validate_payload_hash(manifest, label)

    components = manifest.get("components")
    if not isinstance(components, list):
        _fail(f"invalid {label} components")
    roles = [
        component.get("role") for component in components if isinstance(component, dict)
    ]
    if (
        len(components) != len(TOOLSET_COMPONENT_PATHS)
        or len(roles) != len(set(roles))
        or set(roles) != set(TOOLSET_COMPONENT_PATHS)
    ):
        _fail(f"{label} component roles are missing or duplicated")
    for component_value in components:
        component = _mapping(component_value, f"{label} component")
        _require_exact_keys(
            component,
            {"role", "path", "bundle_path", "sha256", "producing_commit"},
            f"{label} component",
        )
        role = _text(component.get("role"), f"{label} component role")
        if component.get("path") != TOOLSET_COMPONENT_PATHS[role]:
            _fail(f"{label} component path mismatch for {role}")
        _validate_commit(
            component.get("producing_commit"),
            f"{label} component producing commit for {role}",
        )
        path = _contained_artifact_path(
            evidence_path.parent,
            component.get("bundle_path"),
            f"{label} component {role}",
        )
        declared_hash = _text(
            component.get("sha256"), f"{label} component {role} SHA-256"
        )
        if SHA256_RE.fullmatch(declared_hash) is None or _sha256(path) != declared_hash:
            _fail(f"{label} component hash mismatch for {role}")
        if role == "acquisition_exporter" and declared_hash != exporter_hash:
            _fail(f"{label} acquisition exporter is not the supplied exporter")
        if role == "acquisition_finalizer" and declared_hash != _sha256(Path(__file__)):
            _fail(f"{label} acquisition finalizer is not the executing finalizer")
    return {
        "status": APPROVED_FROZEN_STATUS,
        "stage": APPROVED_TOOLSET_STAGE,
        "producing_checkpoint": checkpoint,
        "trusted_checkpoint": trusted_checkpoint,
        "pinned_production_hierarchy_commit": PINNED_PRODUCTION_HIERARCHY_COMMIT,
        "aggregate_payload_sha256": aggregate_hash,
    }


def _event_time(line: str) -> datetime | None:
    match = LOG_TIMESTAMP_RE.match(line)
    if match is None:
        return None
    try:
        return datetime.strptime(
            f"{match.group('base')}.{match.group('fraction')}",
            "%Y-%m-%d %H:%M:%S.%f",
        )
    except ValueError:
        return None


def _event_times(
    lines: list[str],
    *,
    needle: str,
    start: datetime,
    end: datetime,
    log_timezone: timezone,
) -> list[datetime]:
    result: list[datetime] = []
    for line in lines:
        if needle not in line:
            continue
        timestamp = _event_time(line)
        if timestamp is None:
            continue
        aware_timestamp = timestamp.replace(tzinfo=log_timezone)
        if start <= aware_timestamp <= end:
            result.append(aware_timestamp)
    return result


def _marker_event_times(
    lines: list[str],
    *,
    needle: str,
    start: datetime,
    end: datetime,
    log_timezone: timezone,
) -> list[datetime]:
    result: list[datetime] = []
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
        if abs(marker_timestamp - aware_log_timestamp) >= MARKER_LOG_SKEW_LIMIT:
            _fail("NinjaTrader marker timestamp contradicts its log timestamp")
        if start <= marker_timestamp <= end:
            result.append(marker_timestamp)
    return result


def _parse_request_time(value: str, label: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
    except ValueError as error:
        raise AcquisitionValidationError(f"invalid {label}") from error


def _request_events(
    lines: list[str], *, log_timezone: timezone
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for line in lines:
        match = REQUEST_BARS_RE.search(line)
        if match is None:
            continue
        timestamp = _event_time(line)
        if timestamp is None:
            _fail("malformed NinjaTrader RequestBars timestamp")
        result.append(
            {
                "timestamp": timestamp.replace(tzinfo=log_timezone),
                "instrument": match.group("instrument"),
                "requested_start": _parse_request_time(
                    match.group("start"), "RequestBars start"
                ),
                "requested_end": _parse_request_time(
                    match.group("end"), "RequestBars end"
                ),
                "period": match.group("period"),
            }
        )
    return result


def _hds_events(
    lines: list[str], *, log_timezone: timezone
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for line in lines:
        match = HDS_CONNECT_RE.search(line)
        if match is None:
            continue
        timestamp = _event_time(line)
        if timestamp is None:
            _fail("malformed NinjaTrader HDS timestamp")
        host = match.group("host")
        if HDS_HOST_RE.fullmatch(host) is None or match.group("ssl") != "True":
            _fail("historical-data service identity is not approved")
        result.append(
            {
                "timestamp": timestamp.replace(tzinfo=log_timezone),
                "host": host,
                "port": int(match.group("port")),
                "use_ssl": True,
            }
        )
    return result


def _session_bounds(
    runtime: Mapping[str, Any], trading_date: date
) -> tuple[datetime, datetime]:
    hours = _mapping(runtime.get("trading_hours"), "Trading Hours")
    calendar = hours.get("session_calendar")
    if not isinstance(calendar, list):
        _fail("missing Trading Hours session calendar")
    matching = [
        entry
        for entry in calendar
        if isinstance(entry, dict)
        and entry.get("trading_date") == trading_date.isoformat()
    ]
    if len(matching) != 1:
        _fail("Trading Hours calendar does not uniquely cover the trading date")
    segments = matching[0].get("segments")
    if not isinstance(segments, list) or not segments:
        _fail("missing Trading Hours session segments")
    starts: list[datetime] = []
    ends: list[datetime] = []
    for segment in segments:
        item = _mapping(segment, "Trading Hours session segment")
        starts.append(
            _parse_source_timestamp(
                _text(item.get("begin_application"), "Trading Hours segment begin"),
                0,
            )
        )
        ends.append(
            _parse_source_timestamp(
                _text(item.get("end_application"), "Trading Hours segment end"),
                0,
            )
        )
    return min(starts), max(ends)


def _saved_connection_matches(
    config_root: ElementTree.Element, *, connection_name: str, provider_id: str
) -> int:
    matches = 0
    for element in config_root.iter():
        children = {child.tag: child.text for child in element}
        if (
            children.get("Name") == connection_name
            and children.get("Provider") == provider_id
        ):
            matches += 1
    return matches


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
        if match is None:
            continue
        timestamp = _event_time(line)
        if timestamp is None:
            _fail("malformed NinjaTrader provider lifecycle timestamp")
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
    trading_date: date,
) -> dict[str, Any]:
    if "reload_all_historical_data_initiated_at" in evidence:
        _fail("legacy reload evidence is not valid for acquisition evidence v1.2")
    acquisition_id = _text(evidence.get("acquisition_id"), "acquisition id")
    if runtime.get("acquisition_id") != acquisition_id:
        _fail(
            "provider/historical-request evidence does not match the runtime acquisition session"
        )
    profile_id = _text(evidence.get("provider_profile_id"), "provider profile id")
    if profile_id != PROVIDER_PROFILE["id"]:
        _fail("provider profile is not approved")
    connection_name = _text(
        evidence.get("intended_connection_name"), "intended connection name"
    )
    if connection_name != APPROVED_CONNECTION_NAME:
        _fail("intended connection does not match the approved acquisition connection")
    trigger = _mapping(
        evidence.get("historical_request_trigger"), "historical request trigger"
    )
    _require_exact_keys(trigger, HISTORICAL_TRIGGER_KEYS, "historical request trigger")
    if (
        trigger.get("method") != "NINJATRADER_REQUEST_BARS_TRACE"
        or trigger.get("request_source_role") != "ninjatrader_trace"
    ):
        _fail("historical request trigger method is not approved")
    if runtime.get("connection_snapshot_phase") != (
        "immediately after operator arm and before export"
    ):
        _fail("provider connection snapshot is not bound to the acquisition arm event")
    connections = runtime.get("active_connections")
    if not isinstance(connections, list):
        _fail("missing provider/historical-request evidence")
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
        if item.get("provider") == PROVIDER_PROFILE["runtime_provider_id"]
        and item.get("name") == connection_name
    ]
    if len(matching) != 1:
        _fail("provider/historical-request evidence does not prove the intended provider")
    if len(connected) != 1:
        _fail("competing historical-data provider connection is active")

    try:
        config_root = ElementTree.fromstring(contents["ninjatrader_config"])
    except ElementTree.ParseError as error:
        raise AcquisitionValidationError("invalid NinjaTrader configuration evidence") from error
    preferred_future = config_root.findtext(".//PreferredFutureConnection")
    preferred_realtime_future = config_root.findtext(
        ".//PreferredRealtimeFutureConnection"
    )
    saved_connection_matches = _saved_connection_matches(
        config_root,
        connection_name=connection_name,
        provider_id=PROVIDER_PROFILE["runtime_provider_id"],
    )
    if (
        preferred_future == connection_name
        and preferred_realtime_future == connection_name
    ):
        configuration_mode = "EXPLICIT_PREFERENCE"
    elif preferred_future == "Unknown" and preferred_realtime_future == "Unknown":
        if saved_connection_matches != 1:
            _fail("ambiguous unique automatic futures routing")
        configuration_mode = "UNIQUE_AUTO_ROUTE"
    else:
        _fail("preferred historical connection does not match the intended MNQ connection")

    declared = {
        name: _parse_iso_timestamp(trigger.get(name), name.replace("_", " "))
        for name in HISTORICAL_TRIGGER_KEYS
        if name not in {"method", "request_source_role"}
    }
    armed_declared = _parse_iso_timestamp(evidence.get("export_armed_at"), "export arm")
    exported = _parse_iso_timestamp(evidence.get("export_completed_at"), "export completion")
    if not (
        declared["adapter_connection_initiated_at"]
        <= declared["connection_ready_at"]
        and declared["hds_connected_at"]
        <= declared["pre_request_realtime_at"]
        and declared["connection_ready_at"]
        <= declared["pre_request_realtime_at"]
        < declared["request_observed_at"]
        < declared["post_request_initialized_at"]
        <= declared["post_request_realtime_at"]
        < armed_declared
        <= exported
    ):
        _fail("provider/historical-request evidence chronology is invalid")
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
        for timestamp in (*declared.values(), armed_declared, exported)
    ):
        _fail("PC/log timezone offset does not match acquisition evidence")
    log_tz = timezone(log_offset)
    trace_lines = contents["ninjatrader_trace"].splitlines()
    lines = (
        contents["ninjatrader_trace"] + "\n" + contents["ninjatrader_log"]
    ).splitlines()
    marker = f"acquisition={acquisition_id}"
    search_start = declared["adapter_connection_initiated_at"]
    initialized_times = _marker_event_times(
        lines,
        needle=marker + " exporter initialized",
        start=search_start,
        end=exported,
        log_timezone=log_tz,
    )
    realtime_times = _marker_event_times(
        lines,
        needle=marker + " realtime lifecycle observed",
        start=search_start,
        end=exported,
        log_timezone=log_tz,
    )
    armed_times = _marker_event_times(
        lines,
        needle=marker + " export armed event_time=",
        start=search_start,
        end=exported,
        log_timezone=log_tz,
    )
    completed_times = _marker_event_times(
        lines,
        needle=marker + " export complete",
        start=search_start,
        end=exported,
        log_timezone=log_tz,
    )
    adapter_times = _event_times(
        trace_lines,
        needle=f"({connection_name}) {PROVIDER_PROFILE['trace_adapter']}.Connect",
        start=search_start,
        end=exported,
        log_timezone=log_tz,
    )
    connection_ready_times = _event_times(
        trace_lines,
        needle=(
            f"({connection_name}) Cbi.Connection.ConnectionStatusCallback: "
            "status=Connected priceStatus=Connected"
        ),
        start=search_start,
        end=exported,
        log_timezone=log_tz,
    )
    hds_events = _hds_events(trace_lines, log_timezone=log_tz)
    request_events = _request_events(trace_lines, log_timezone=log_tz)
    session_start, session_end = _session_bounds(runtime, trading_date)

    qualifying_requests = [
        request
        for request in request_events
        if request["instrument"] == PROVIDER_PROFILE["contract_label"]
        and request["period"] == "1 Minute"
        and declared["pre_request_realtime_at"]
        < request["timestamp"]
        < declared["post_request_initialized_at"]
        and request["timestamp"] < armed_declared
        and request["requested_start"] <= session_start
        and request["requested_end"] >= session_end
    ]
    if len(qualifying_requests) != 1:
        _fail("historical RequestBars evidence is not uniquely qualifying")
    request = qualifying_requests[0]
    request_time = request["timestamp"]

    pre_realtime_candidates = [time for time in realtime_times if time < request_time]
    post_initialized_candidates = [
        time for time in initialized_times if request_time < time < armed_declared
    ]
    if not pre_realtime_candidates or not post_initialized_candidates:
        _fail("provider/historical-request evidence chain is incomplete")
    pre_realtime_time = max(pre_realtime_candidates)
    post_initialized_time = min(post_initialized_candidates)
    post_realtime_candidates = [
        time
        for time in realtime_times
        if post_initialized_time <= time < armed_declared
    ]
    if not post_realtime_candidates:
        _fail("provider/historical-request evidence chain is incomplete")
    post_realtime_time = min(post_realtime_candidates)

    matching_hds = [
        event
        for event in hds_events
        if declared["adapter_connection_initiated_at"]
        <= event["timestamp"]
        <= pre_realtime_time
    ]
    if not matching_hds:
        _fail("provider/historical-request evidence chain is incomplete")
    hds = max(matching_hds, key=lambda event: event["timestamp"])

    _reject_competing_provider_activity(
        trace_lines,
        provider=PROVIDER_PROFILE["trace_adapter_name"],
        connection_name=connection_name,
        start=declared["adapter_connection_initiated_at"],
        end=exported,
        log_timezone=log_tz,
    )
    if (
        declared["adapter_connection_initiated_at"] not in adapter_times
        or declared["connection_ready_at"] not in connection_ready_times
        or declared["hds_connected_at"] != hds["timestamp"]
        or declared["pre_request_realtime_at"] != pre_realtime_time
        or declared["request_observed_at"] != request_time
        or declared["post_request_initialized_at"] != post_initialized_time
        or declared["post_request_realtime_at"] != post_realtime_time
        or armed_declared not in armed_times
        or exported not in completed_times
    ):
        _fail("provider/historical-request evidence chain is incomplete")
    runtime_events = {
        entry["event"]: _parse_iso_timestamp(
            entry["timestamp"], f"PC/log timezone {entry['event']} timestamp"
        )
        for entry in runtime_event_offsets
    }
    if (
        runtime_events["initialized"] != post_initialized_time
        or runtime_events["armed"] != armed_declared
        or runtime_events["exported"] != exported
    ):
        _fail("PC/log timezone event timestamps do not match acquisition markers")
    return {
        "status": "PROVEN",
        "provider_profile_id": profile_id,
        "runtime_provider_id": PROVIDER_PROFILE["runtime_provider_id"],
        "trace_adapter": PROVIDER_PROFILE["trace_adapter"],
        "intended_connection_name": connection_name,
        "active_connection": matching[0],
        "historical_service": {
            "name": PROVIDER_PROFILE["historical_service"],
            "host": hds["host"],
            "port": hds["port"],
            "use_ssl": hds["use_ssl"],
            "connected_at": hds["timestamp"].isoformat(),
        },
        "configuration_binding": {
            "mode": configuration_mode,
            "preferred_future_connection": preferred_future,
            "preferred_realtime_future_connection": preferred_realtime_future,
            "saved_connection_matches": saved_connection_matches,
        },
        "acquisition_id": acquisition_id,
        "lifecycle": {
            "adapter_connection_initiated_at": declared[
                "adapter_connection_initiated_at"
            ].isoformat(),
            "connection_ready_at": declared["connection_ready_at"].isoformat(),
            "pre_request_realtime_at": pre_realtime_time.isoformat(),
            "post_request_initialized_at": post_initialized_time.isoformat(),
            "post_request_realtime_at": post_realtime_time.isoformat(),
            "export_armed_at": armed_declared.isoformat(),
            "export_completed_at": exported.isoformat(),
        },
        "historical_request": {
            "source_role": trigger["request_source_role"],
            "observed_at": request_time.isoformat(),
            "instrument": request["instrument"],
            "requested_start": request["requested_start"].isoformat(),
            "requested_end": request["requested_end"].isoformat(),
            "provider_request_period": request["period"],
            "covers_declared_session": True,
        },
        "competing_historical_provider_connections": 0,
        "intended_provider_disconnects": 0,
        "log_timezone_id": log_timezone_id,
        "log_utc_offset": _text(evidence.get("log_utc_offset"), "log UTC offset"),
    }


def finalize_provenance(
    *,
    source_path: str | Path,
    runtime_capture_path: str | Path,
    acquisition_evidence_path: str | Path,
    exporter_path: str | Path,
    trusted_selection_checkpoint: str,
    trusted_toolset_checkpoint: str,
    trusted_acquisition_checkpoint: str | None = None,
    repository_path: str | Path | None = None,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    remote_name: str | None = None,
    remote_branch: str | None = None,
    checkpoint_attestation: Mapping[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, object]:
    """Validate an acquisition bundle and return its frozen provenance."""

    if checkpoint_attestation is not None:
        _fail("user-supplied checkpoint attestation is not accepted")

    source = Path(source_path)
    runtime_path = Path(runtime_capture_path)
    evidence_path = Path(acquisition_evidence_path)
    exporter = Path(exporter_path)
    trusted_selection_checkpoint = _validate_commit(
        trusted_selection_checkpoint, "trusted selection checkpoint"
    )
    trusted_toolset_checkpoint = _validate_commit(
        trusted_toolset_checkpoint, "trusted toolset checkpoint"
    )
    runtime = _load_object(runtime_path, "runtime capture")
    evidence = _load_object(evidence_path, "acquisition evidence")
    if (
        runtime.get("schema_version") != RUNTIME_CAPTURE_SCHEMA_VERSION
        or evidence.get("schema_version") != ACQUISITION_EVIDENCE_SCHEMA_VERSION
    ):
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
    evidence_hashes, evidence_contents, evidence_paths = _validate_evidence_files(
        evidence_path, evidence
    )
    evidence_hash = _sha256(evidence_path)

    if repository_path is None:
        _fail("independent Git checkpoint verification is required")
    try:
        checkpoint_verification = verify_checkpoints(
            repository_path=repository_path,
            bundle_root=evidence_path.parent,
            toolset_manifest_path=evidence_paths["toolset_manifest"],
            selection_registry_path=evidence_paths["selection_registry"],
            trusted_toolset_checkpoint=trusted_toolset_checkpoint,
            trusted_selection_checkpoint=trusted_selection_checkpoint,
            trusted_acquisition_checkpoint=trusted_acquisition_checkpoint,
            expected_repository_identity=expected_repository_identity,
            remote_name=remote_name,
            remote_branch=remote_branch,
        )
    except CheckpointVerificationError as error:
        raise AcquisitionValidationError(
            f"independent Git checkpoint verification failed: {error}"
        ) from error

    verified_bundle_hashes = _verified_bundle_hashes(checkpoint_verification)
    for role in ("toolset_manifest", "selection_registry"):
        if evidence_hashes[role] != verified_bundle_hashes[role]:
            _fail(f"verified checkpoint artifact differs from bundle snapshot: {role}")

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

    selection_binding = _validate_selection_registry(
        evidence_path=evidence_path,
        evidence=evidence,
        registry_text=evidence_contents["selection_registry"],
        cohort_id=cohort_id,
        case_id=case_id,
        trading_date=trading_date,
        trusted_checkpoint=trusted_selection_checkpoint,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        verified_bundle_hashes=verified_bundle_hashes,
    )
    toolset_binding = _validate_toolset_manifest(
        evidence_path=evidence_path,
        evidence=evidence,
        manifest_text=evidence_contents["toolset_manifest"],
        exporter_hash=exporter_hash,
        trusted_checkpoint=trusted_toolset_checkpoint,
    )

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
        runtime, evidence, evidence_contents, pc_timezone, trading_date
    )
    ninja_version = _text(runtime.get("ninjatrader_version"), "NinjaTrader version")
    export_method = _text(runtime.get("export_method"), "source export method")
    original_export_identity = _text(
        runtime.get("original_export_identity"), "original export identity"
    )
    exported_at = _parse_iso_timestamp(runtime.get("exported_at"), "runtime export timestamp")
    if exported_at != _parse_iso_timestamp(
        provider["lifecycle"]["export_completed_at"], "provider export completion"
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
    try:
        final_checkpoint_verification = verify_checkpoints(
            repository_path=repository_path,
            bundle_root=evidence_path.parent,
            toolset_manifest_path=evidence_paths["toolset_manifest"],
            selection_registry_path=evidence_paths["selection_registry"],
            trusted_toolset_checkpoint=trusted_toolset_checkpoint,
            trusted_selection_checkpoint=trusted_selection_checkpoint,
            trusted_acquisition_checkpoint=trusted_acquisition_checkpoint,
            expected_repository_identity=expected_repository_identity,
            remote_name=remote_name,
            remote_branch=remote_branch,
        )
    except CheckpointVerificationError as error:
        raise AcquisitionValidationError(
            f"independent Git checkpoint re-verification failed: {error}"
        ) from error
    for field in (
        "trusted_toolset_checkpoint",
        "trusted_selection_checkpoint",
        "trusted_acquisition_checkpoint",
        "pinned_production_hierarchy_commit",
        "artifacts",
        "ancestry",
        "verifier",
    ):
        if checkpoint_verification.get(field) != final_checkpoint_verification.get(
            field
        ):
            _fail("checkpoint artifacts changed during provenance finalization")
    checkpoint_verification = final_checkpoint_verification
    result: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
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
        "selection_binding": selection_binding,
        "toolset_binding": toolset_binding,
        "checkpoint_verification": checkpoint_verification,
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
    parser.add_argument("--trusted-selection-checkpoint", required=True)
    parser.add_argument("--trusted-toolset-checkpoint", required=True)
    parser.add_argument("--trusted-acquisition-checkpoint")
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--repository-identity", default=DEFAULT_REPOSITORY_IDENTITY)
    parser.add_argument("--remote-name")
    parser.add_argument("--remote-branch")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        finalize_provenance(
            source_path=args.source,
            runtime_capture_path=args.runtime_capture,
            acquisition_evidence_path=args.acquisition_evidence,
            exporter_path=args.exporter,
            trusted_selection_checkpoint=args.trusted_selection_checkpoint,
            trusted_toolset_checkpoint=args.trusted_toolset_checkpoint,
            trusted_acquisition_checkpoint=args.trusted_acquisition_checkpoint,
            repository_path=args.repository,
            expected_repository_identity=args.repository_identity,
            remote_name=args.remote_name,
            remote_branch=args.remote_branch,
            output_path=args.output,
        )
    except AcquisitionValidationError as error:
        parser.exit(2, f"STOP: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
