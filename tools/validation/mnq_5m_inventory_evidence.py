"""Validate global provider and immutable evidence for one MNQ inventory scan."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping
from xml.etree import ElementTree

from tools.validation.mnq_5m_inventory_common import (
    _load_schema_validated_json_bytes,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "validation" / "mnq_5m_multiwindow" / "schemas"
SCHEMAS = {
    "inventory_runtime_capture": SCHEMA_DIR / "inventory_runtime_capture.schema.json",
    "inventory_scan": SCHEMA_DIR / "inventory_scan.schema.json",
    "inventory_acquisition_evidence": SCHEMA_DIR / "inventory_acquisition_evidence.schema.json",
}
SCANNER_REPOSITORY_PATH = "tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs"
PROVIDER_PROFILE = {
    "provider_profile_id": "NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1",
    "runtime_provider_id": "Provider31",
    "trace_adapter": "Tradovate.Adapter",
    "trace_adapter_name": "Tradovate",
    "historical_service": "NinjaTrader HDS",
}
APPROVED_CONNECTION_NAME = "My NinjaTrader"
APPROVED_CONTRACT = "MNQ SEP26"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
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


class InventoryValidationError(ValueError):
    """Reject invalid inventory evidence without creating official output."""


@dataclass(frozen=True)
class LoadedInventoryEvidence:
    runtime_capture_path: Path
    runtime_capture: Mapping[str, object]
    inventory_scan_path: Path
    inventory_scan: Mapping[str, object]
    acquisition_evidence_path: Path
    acquisition_evidence: Mapping[str, object]
    exact_artifact_bytes: Mapping[str, bytes]


@dataclass(frozen=True)
class ValidatedInventoryEvidence:
    loaded: LoadedInventoryEvidence
    provider_acquisition: Mapping[str, object]
    qualifying_request: Mapping[str, object]
    artifact_hashes: Mapping[str, str]
    external_evidence: tuple[Mapping[str, object], ...]
    earliest_session_begin: datetime
    latest_session_end: datetime


def _fail(message: str) -> None:
    raise InventoryValidationError(message)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"invalid {label}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"invalid {label}")
    return value


def _parse_iso(value: object, label: str) -> datetime:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError) as error:
        raise InventoryValidationError(f"invalid {label}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} must be timezone-aware")
    return parsed


def _parse_offset(value: object, label: str) -> timedelta:
    text = _text(value, label)
    match = re.fullmatch(r"(?P<sign>[+-])(?P<hour>\d{2}):(?P<minute>\d{2})", text)
    if match is None:
        _fail(f"invalid {label}")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23 or minute > 59:
        _fail(f"invalid {label}")
    result = timedelta(hours=hour, minutes=minute)
    return -result if match.group("sign") == "-" else result


def _fixed_timezone(offset: timedelta, label: str) -> timezone:
    try:
        return timezone(offset)
    except (TypeError, ValueError, OverflowError) as error:
        raise InventoryValidationError(f"invalid {label}") from error


def _deep_freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _validate_cross_bindings(
    runtime: Mapping[str, object],
    scan: Mapping[str, object],
    acquisition: Mapping[str, object],
    exact_bytes: Mapping[str, bytes],
) -> None:
    acquisition_id = scan.get("acquisition_id")
    cohort_id = scan.get("cohort_id")
    if any(
        document.get("acquisition_id") != acquisition_id
        or document.get("cohort_id") != cohort_id
        for document in (runtime, acquisition)
    ):
        _fail("inventory acquisition/cohort cross-binding mismatch")
    contract = _mapping(scan.get("contract"), "scan contract")
    instrument = _mapping(runtime.get("instrument"), "runtime instrument")
    for key in ("contract_label", "full_name", "master_name", "expiry_month", "expiry_year"):
        if contract.get(key) != instrument.get(key):
            _fail("inventory scan/runtime contract mismatch")
    scan_series = _mapping(scan.get("bar_series"), "scan bar series")
    runtime_series = _mapping(runtime.get("bar_series"), "runtime bar series")
    for key in ("type", "value", "native"):
        if scan_series.get(key) != runtime_series.get(key):
            _fail("inventory scan/runtime bar-series mismatch")
    scan_hours = _mapping(scan.get("trading_hours"), "scan Trading Hours")
    runtime_hours = _mapping(runtime.get("trading_hours"), "runtime Trading Hours")
    if any(scan_hours.get(key) != runtime_hours.get(key) for key in ("name", "timezone_id")):
        _fail("inventory scan/runtime Trading Hours mismatch")
    runtime_lifecycle = _mapping(runtime.get("lifecycle"), "runtime lifecycle")
    acquisition_lifecycle = _mapping(acquisition.get("lifecycle"), "acquisition lifecycle")
    if (
        runtime_lifecycle.get("initialized_at") != acquisition_lifecycle.get("post_request_initialized_at")
        or runtime_lifecycle.get("realtime_observed_at") != acquisition_lifecycle.get("post_request_realtime_at")
        or runtime_lifecycle.get("armed_at") != acquisition_lifecycle.get("inventory_scan_armed_at")
        or runtime_lifecycle.get("completed_at") != acquisition_lifecycle.get("inventory_scan_completed_at")
        or scan.get("completed_at") != runtime_lifecycle.get("completed_at")
    ):
        _fail("inventory lifecycle cross-binding mismatch")
    trigger = _mapping(acquisition.get("historical_trigger"), "historical trigger")
    if trigger.get("observed_at") != acquisition_lifecycle.get("request_observed_at"):
        _fail("historical trigger/lifecycle cross-binding mismatch")
    hashes = _mapping(runtime.get("artifact_hashes"), "runtime artifact hashes")
    scan_hash = _mapping(hashes.get("inventory_scan"), "runtime scan hash")
    if scan_hash.get("sha256") != sha256_bytes(exact_bytes["inventory_scan"]):
        _fail("inventory scan exact-byte hash mismatch")


def load_inventory_evidence(
    *,
    runtime_capture_path: str | Path,
    inventory_scan_path: str | Path,
    acquisition_evidence_path: str | Path,
) -> LoadedInventoryEvidence:
    """Load exact bytes and validate all three documents against Task 4."""

    paths = {
        "inventory_runtime_capture": Path(runtime_capture_path).resolve(),
        "inventory_scan": Path(inventory_scan_path).resolve(),
        "inventory_acquisition_evidence": Path(acquisition_evidence_path).resolve(),
    }
    try:
        exact = {name: path.read_bytes() for name, path in paths.items()}
        documents = {
            name: _load_schema_validated_json_bytes(
                exact[name], SCHEMAS[name], name.replace("_", " ")
            )
            for name in paths
        }
        _validate_cross_bindings(
            documents["inventory_runtime_capture"],
            documents["inventory_scan"],
            documents["inventory_acquisition_evidence"],
            exact,
        )
    except InventoryValidationError:
        raise
    except (OSError, ValueError) as error:
        raise InventoryValidationError("invalid inventory evidence input") from error
    return LoadedInventoryEvidence(
        runtime_capture_path=paths["inventory_runtime_capture"],
        runtime_capture=_deep_freeze(documents["inventory_runtime_capture"]),
        inventory_scan_path=paths["inventory_scan"],
        inventory_scan=_deep_freeze(documents["inventory_scan"]),
        acquisition_evidence_path=paths["inventory_acquisition_evidence"],
        acquisition_evidence=_deep_freeze(documents["inventory_acquisition_evidence"]),
        exact_artifact_bytes=MappingProxyType(exact),
    )


def _git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _run_git(repository: Path, *arguments: str, text: bool = True) -> subprocess.CompletedProcess[object]:
    options = {"encoding": "utf-8", "errors": "replace"} if text else {}
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            capture_output=True,
            text=text,
            env=_git_environment(),
            **options,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise InventoryValidationError("repository/toolset trust verification failed") from error


def _normalized_identity(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    return normalized[:-4] if normalized.lower().endswith(".git") else normalized


def _verify_repository_and_scanner(
    repository: Path,
    checkpoint: str,
    expected_identity: str,
    scanner_path: Path,
    scanner_bytes: bytes,
) -> None:
    if COMMIT_RE.fullmatch(checkpoint) is None or not repository.is_dir():
        _fail("invalid trusted toolset checkpoint or repository")
    origin = _run_git(repository, "config", "--get", "remote.origin.url").stdout
    assert isinstance(origin, str)
    if _normalized_identity(origin) != _normalized_identity(expected_identity):
        _fail("repository identity does not match the expected repository")
    _run_git(repository, "rev-parse", "--verify", f"{checkpoint}^{{commit}}")
    expected_scanner = (repository / PurePosixPath(SCANNER_REPOSITORY_PATH)).resolve()
    if scanner_path.resolve() != expected_scanner:
        _fail("scanner path does not match the approved repository path")
    committed = _run_git(
        repository,
        "show",
        f"{checkpoint}:{SCANNER_REPOSITORY_PATH}",
        text=False,
    ).stdout
    assert isinstance(committed, bytes)
    if committed != scanner_bytes:
        _fail("scanner bytes do not match the trusted toolset checkpoint")


def _event_time(line: str) -> datetime | None:
    match = LOG_TIMESTAMP_RE.match(line)
    if match is None:
        return None
    fraction = (match.group("fraction") + "000000")[:6]
    try:
        return datetime.strptime(
            f"{match.group('base')}.{fraction}", "%Y-%m-%d %H:%M:%S.%f"
        )
    except ValueError:
        return None


def _marker_times(lines: list[str], needle: str, log_timezone: timezone) -> list[datetime]:
    result: list[datetime] = []
    for line in lines:
        if needle not in line:
            continue
        prefix = _event_time(line)
        marker = MARKER_EVENT_TIME_RE.search(line)
        if prefix is None or marker is None:
            _fail("malformed inventory lifecycle marker")
        embedded = _parse_iso(marker.group(1), "inventory lifecycle marker event_time")
        aware_prefix = prefix.replace(tzinfo=log_timezone)
        if abs(embedded - aware_prefix) > MARKER_LOG_SKEW_LIMIT:
            _fail("inventory lifecycle marker timestamp contradicts line-prefix timestamp")
        result.append(embedded)
    return result


def _request_time(value: str, label: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError) as error:
        raise InventoryValidationError(f"invalid {label}") from error


def _request_events(lines: list[str], log_timezone: timezone) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for line in lines:
        match = REQUEST_BARS_RE.search(line)
        if match is None:
            continue
        prefix = _event_time(line)
        if prefix is None:
            _fail("malformed RequestBars timestamp")
        result.append(
            {
                "timestamp": prefix.replace(tzinfo=log_timezone),
                "instrument": match.group("instrument"),
                "requested_start": _request_time(match.group("start"), "RequestBars start"),
                "requested_end": _request_time(match.group("end"), "RequestBars end"),
                "period": match.group("period"),
            }
        )
    return result


def _event_times(lines: list[str], needle: str, log_timezone: timezone) -> list[datetime]:
    result: list[datetime] = []
    for line in lines:
        if needle not in line:
            continue
        prefix = _event_time(line)
        if prefix is None:
            _fail("malformed provider lifecycle timestamp")
        result.append(prefix.replace(tzinfo=log_timezone))
    return result


def _saved_connection_matches(root: ElementTree.Element, name: str, provider: str) -> int:
    return sum(
        1
        for element in root.iter()
        if {child.tag: child.text for child in element}.get("Name") == name
        and {child.tag: child.text for child in element}.get("Provider") == provider
    )


def _configuration_binding(config_bytes: bytes) -> dict[str, object]:
    try:
        root = ElementTree.fromstring(config_bytes)
    except ElementTree.ParseError as error:
        raise InventoryValidationError("invalid NinjaTrader configuration evidence") from error
    future = root.findtext(".//PreferredFutureConnection")
    realtime = root.findtext(".//PreferredRealtimeFutureConnection")
    matches = _saved_connection_matches(
        root, APPROVED_CONNECTION_NAME, PROVIDER_PROFILE["runtime_provider_id"]
    )
    if future == APPROVED_CONNECTION_NAME and realtime == APPROVED_CONNECTION_NAME:
        mode = "EXPLICIT_PREFERENCE"
    elif future == "Unknown" and realtime == "Unknown" and matches == 1:
        mode = "UNIQUE_AUTO_ROUTE"
    else:
        _fail("preferred historical connection does not match the intended MNQ connection")
    if matches != 1:
        _fail("NinjaTrader configuration does not uniquely bind the intended connection")
    return {
        "mode": mode,
        "preferred_future_connection": future,
        "preferred_realtime_future_connection": realtime,
        "saved_connection_matches": matches,
    }


def _external_evidence(
    loaded: LoadedInventoryEvidence,
    supplied: Mapping[str, Path],
) -> tuple[tuple[Mapping[str, object], ...], dict[str, bytes]]:
    records = loaded.acquisition_evidence.get("evidence_files")
    if not isinstance(records, (list, tuple)):
        _fail("missing external evidence records")
    by_role: dict[str, Mapping[str, object]] = {}
    root = loaded.acquisition_evidence_path.parent.resolve()
    for item in records:
        record = _mapping(item, "external evidence record")
        role = _text(record.get("role"), "external evidence role")
        if role in by_role:
            _fail("duplicate external evidence role")
        by_role[role] = record
    required = set(supplied)
    if set(by_role) != required:
        _fail("external evidence roles do not exactly match supplied evidence")
    exact: dict[str, bytes] = {}
    normalized: list[Mapping[str, object]] = []
    for role in ("ninjatrader_config", "ninjatrader_log", "ninjatrader_trace", "trading_hours_template"):
        record = by_role[role]
        relative_text = _text(record.get("path"), f"{role} evidence path")
        relative = PurePosixPath(relative_text.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            _fail(f"{role} evidence path must be a contained relative path")
        declared = (root / Path(*relative.parts)).resolve()
        supplied_path = supplied[role].resolve()
        try:
            declared.relative_to(root)
        except ValueError:
            _fail(f"{role} evidence path escapes the evidence directory")
        if declared != supplied_path:
            _fail(f"{role} evidence path does not match the supplied immutable file")
        try:
            value = supplied_path.read_bytes()
        except OSError as error:
            raise InventoryValidationError(f"cannot read {role} evidence") from error
        digest = sha256_bytes(value)
        if (
            not value
            or record.get("byte_length") != len(value)
            or record.get("sha256") != digest
            or SHA256_RE.fullmatch(str(record.get("sha256"))) is None
        ):
            _fail(f"{role} immutable evidence binding mismatch")
        exact[role] = value
        normalized.append(dict(record))
    return tuple(normalized), exact


def _validate_provider(
    loaded: LoadedInventoryEvidence,
    exact_external: Mapping[str, bytes],
    earliest: datetime,
    latest: datetime,
) -> tuple[dict[str, object], dict[str, object]]:
    runtime = loaded.runtime_capture
    evidence = loaded.acquisition_evidence
    intended = _mapping(evidence.get("intended_provider"), "intended provider")
    if any(intended.get(key) != value for key, value in PROVIDER_PROFILE.items() if key != "trace_adapter_name"):
        _fail("provider profile is not approved")
    if evidence.get("intended_connection_name") != APPROVED_CONNECTION_NAME:
        _fail("intended connection does not match the approved acquisition connection")
    connections = runtime.get("active_connections")
    if not isinstance(connections, (list, tuple)):
        _fail("missing runtime active connections")
    active_futures = [
        item for item in connections
        if isinstance(item, Mapping)
        and item.get("status") == "Connected"
        and item.get("price_status") == "Connected"
        and isinstance(item.get("instrument_types"), (list, tuple))
        and "Future" in item["instrument_types"]
    ]
    intended_active = [
        item for item in active_futures
        if item.get("name") == APPROVED_CONNECTION_NAME
        and item.get("provider") == PROVIDER_PROFILE["runtime_provider_id"]
    ]
    if len(intended_active) != 1 or len(active_futures) != 1:
        _fail("runtime does not prove one exclusive intended futures provider")

    pc_timezone = _mapping(runtime.get("pc_timezone"), "runtime PC timezone")
    offset = _parse_offset(pc_timezone.get("base_utc_offset"), "PC timezone UTC offset")
    log_timezone = _fixed_timezone(offset, "PC timezone UTC offset")
    try:
        log_lines = exact_external["ninjatrader_log"].decode("utf-8").splitlines()
        trace_lines = exact_external["ninjatrader_trace"].decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise InventoryValidationError("log/trace evidence is not UTF-8") from error
    all_lines = trace_lines + log_lines
    acquisition_id = _text(evidence.get("acquisition_id"), "acquisition id")
    marker = f"acquisition={acquisition_id}"
    lifecycle = _mapping(evidence.get("lifecycle"), "acquisition lifecycle")
    declared = {name: _parse_iso(value, name.replace("_", " ")) for name, value in lifecycle.items()}
    if any(value.utcoffset() != offset for value in declared.values()):
        _fail("lifecycle timestamps do not match the captured PC timezone offset")
    if not (
        declared["adapter_connection_initiated_at"]
        <= declared["connection_ready_at"]
        <= declared["pre_request_realtime_at"]
        < declared["request_observed_at"]
        < declared["post_request_initialized_at"]
        <= declared["post_request_realtime_at"]
        < declared["inventory_scan_armed_at"]
        < declared["inventory_scan_completed_at"]
    ):
        _fail("provider/acquisition lifecycle chronology is invalid")

    pre_post_realtime = _marker_times(
        all_lines, marker + " inventory realtime lifecycle observed", log_timezone
    )
    initialized = _marker_times(
        all_lines, marker + " inventory scanner initialized", log_timezone
    )
    armed = _marker_times(all_lines, marker + " inventory scan armed", log_timezone)
    completed = _marker_times(all_lines, marker + " inventory scan complete", log_timezone)
    if (
        sorted(pre_post_realtime)
        != sorted([declared["pre_request_realtime_at"], declared["post_request_realtime_at"]])
        or initialized != [declared["post_request_initialized_at"]]
        or armed != [declared["inventory_scan_armed_at"]]
        or completed != [declared["inventory_scan_completed_at"]]
    ):
        _fail("provider/acquisition lifecycle marker evidence is incomplete or duplicated")

    adapter_times = _event_times(
        trace_lines,
        f"({APPROVED_CONNECTION_NAME}) {PROVIDER_PROFILE['trace_adapter']}.Connect",
        log_timezone,
    )
    ready_times = _event_times(
        trace_lines,
        f"({APPROVED_CONNECTION_NAME}) Cbi.Connection.ConnectionStatusCallback: status=Connected priceStatus=Connected",
        log_timezone,
    )
    if (
        declared["adapter_connection_initiated_at"] not in adapter_times
        or declared["connection_ready_at"] not in ready_times
    ):
        _fail("provider connection lifecycle evidence is incomplete")
    for line in trace_lines:
        match = PROVIDER_LIFECYCLE_RE.search(line)
        if match is None:
            continue
        timestamp = _event_time(line)
        if timestamp is None:
            _fail("malformed provider lifecycle timestamp")
        aware = timestamp.replace(tzinfo=log_timezone)
        if not declared["adapter_connection_initiated_at"] <= aware <= declared["inventory_scan_completed_at"]:
            continue
        if (
            match.group("connection") != APPROVED_CONNECTION_NAME
            or match.group("provider") != PROVIDER_PROFILE["trace_adapter_name"]
            or match.group("action") == "Disconnect"
        ):
            _fail("competing provider activity or intended-provider disconnect detected")

    hds_events: list[dict[str, object]] = []
    for line in trace_lines:
        match = HDS_CONNECT_RE.search(line)
        if match is None:
            continue
        timestamp = _event_time(line)
        if timestamp is None:
            _fail("malformed HDS timestamp")
        host = match.group("host")
        if HDS_HOST_RE.fullmatch(host) is None or match.group("ssl") != "True":
            _fail("historical data service identity is not approved")
        hds_events.append(
            {"timestamp": timestamp.replace(tzinfo=log_timezone), "host": host, "port": int(match.group("port")), "use_ssl": True}
        )
    matching_hds = [
        item for item in hds_events
        if declared["adapter_connection_initiated_at"] <= item["timestamp"] <= declared["pre_request_realtime_at"]
    ]
    if not matching_hds:
        _fail("NinjaTrader HDS readiness evidence is missing")
    hds = max(matching_hds, key=lambda item: item["timestamp"])

    application_timezone = _mapping(
        runtime.get("application_timezone"), "runtime application timezone"
    )
    if application_timezone.get("supports_dst") is not False:
        _fail("runtime application timezone offset is not independently provable")
    application_offset = _parse_offset(
        application_timezone.get("base_utc_offset"),
        "application timezone UTC offset",
    )
    application_zone = _fixed_timezone(
        application_offset, "application timezone UTC offset"
    )
    try:
        earliest_naive = earliest.astimezone(application_zone).replace(tzinfo=None)
        latest_naive = latest.astimezone(application_zone).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError) as error:
        raise InventoryValidationError(
            "verified session bounds cannot be represented in the application timezone"
        ) from error
    requests = _request_events(trace_lines, log_timezone)
    qualifying = [
        request for request in requests
        if request["instrument"] == APPROVED_CONTRACT
        and request["period"] == "1 Minute"
        and declared["pre_request_realtime_at"] < request["timestamp"] < declared["post_request_initialized_at"]
        and request["timestamp"] < declared["inventory_scan_armed_at"]
        and request["requested_start"] <= earliest_naive
        and request["requested_end"] >= latest_naive
    ]
    if len(qualifying) != 1:
        _fail("historical RequestBars evidence is not uniquely qualifying")
    request = qualifying[0]
    trigger = _mapping(evidence.get("historical_trigger"), "historical trigger")
    expected_trigger = {
        "source_role": "ninjatrader_trace",
        "instrument": request["instrument"],
        "provider_request_period": request["period"],
        "observed_at": request["timestamp"].isoformat(),
        "requested_start": request["requested_start"].isoformat(),
        "requested_end": request["requested_end"].isoformat(),
        "qualifying_request_count": 1,
    }
    if dict(trigger) != expected_trigger or request["timestamp"] != declared["request_observed_at"]:
        _fail("historical trigger does not match the uniquely qualifying request")

    configuration = _configuration_binding(exact_external["ninjatrader_config"])
    provider = {
        "status": "PROVEN",
        "provider_profile_id": PROVIDER_PROFILE["provider_profile_id"],
        "runtime_provider_id": PROVIDER_PROFILE["runtime_provider_id"],
        "trace_adapter": PROVIDER_PROFILE["trace_adapter"],
        "intended_connection_name": APPROVED_CONNECTION_NAME,
        "active_connection": dict(intended_active[0]),
        "historical_service": {
            "name": PROVIDER_PROFILE["historical_service"],
            "host": hds["host"],
            "port": hds["port"],
            "use_ssl": hds["use_ssl"],
            "connected_at": hds["timestamp"].isoformat(),
        },
        "configuration_binding": configuration,
        "acquisition_id": acquisition_id,
        "lifecycle": {name: value.isoformat() for name, value in declared.items()},
        "historical_request": {
            "source_role": "ninjatrader_trace",
            "observed_at": request["timestamp"].isoformat(),
            "instrument": request["instrument"],
            "requested_start": request["requested_start"].isoformat(),
            "requested_end": request["requested_end"].isoformat(),
            "provider_request_period": request["period"],
            "covers_verified_inventory_bounds": True,
        },
        "competing_historical_provider_connections": 0,
        "intended_provider_disconnects": 0,
        "log_timezone_id": pc_timezone.get("id"),
        "log_utc_offset": pc_timezone.get("base_utc_offset"),
    }
    return provider, provider["historical_request"]


def finalize_inventory_evidence(
    *,
    loaded: LoadedInventoryEvidence,
    scanner_path: str | Path,
    trading_hours_template_path: str | Path,
    config_path: str | Path,
    log_path: str | Path,
    trace_path: str | Path,
    trusted_toolset_checkpoint: str,
    repository_path: str | Path,
    expected_repository_identity: str,
    earliest_session_begin: datetime,
    latest_session_end: datetime,
) -> ValidatedInventoryEvidence:
    """Validate immutable evidence and the unique request over supplied bounds."""

    if (
        earliest_session_begin.tzinfo is None
        or earliest_session_begin.utcoffset() is None
        or latest_session_end.tzinfo is None
        or latest_session_end.utcoffset() is None
        or earliest_session_begin >= latest_session_end
    ):
        _fail("verified inventory session bounds must be ordered timezone-aware datetimes")
    scanner = Path(scanner_path).resolve()
    repository = Path(repository_path).resolve()
    try:
        scanner_bytes = scanner.read_bytes()
    except OSError as error:
        raise InventoryValidationError("cannot read inventory scanner") from error
    _verify_repository_and_scanner(
        repository,
        trusted_toolset_checkpoint,
        expected_repository_identity,
        scanner,
        scanner_bytes,
    )
    if loaded.acquisition_evidence.get("expected_toolset_checkpoint") != trusted_toolset_checkpoint:
        _fail("inventory evidence toolset checkpoint mismatch")

    supplied = {
        "ninjatrader_config": Path(config_path),
        "ninjatrader_log": Path(log_path),
        "ninjatrader_trace": Path(trace_path),
        "trading_hours_template": Path(trading_hours_template_path),
    }
    external, exact_external = _external_evidence(loaded, supplied)
    runtime_hashes = _mapping(loaded.runtime_capture.get("artifact_hashes"), "runtime artifact hashes")
    declared_template = _mapping(runtime_hashes.get("trading_hours_template"), "template hash")
    declared_config = _mapping(runtime_hashes.get("ninjatrader_config"), "configuration hash")
    if declared_template.get("sha256") != sha256_bytes(exact_external["trading_hours_template"]):
        _fail("Trading Hours template hash mismatch")
    if declared_config.get("sha256") != sha256_bytes(exact_external["ninjatrader_config"]):
        _fail("NinjaTrader configuration hash mismatch")
    scanner_identity = _mapping(loaded.runtime_capture.get("scanner_identity"), "scanner identity")
    scanner_digest = sha256_bytes(scanner_bytes)
    declared_scanner = scanner_identity.get("scanner_sha256")
    if declared_scanner is not None and declared_scanner != scanner_digest:
        _fail("scanner identity hash mismatch")

    provider, request = _validate_provider(
        loaded,
        exact_external,
        earliest_session_begin,
        latest_session_end,
    )
    artifact_hashes = {
        "inventory_scan": sha256_bytes(loaded.exact_artifact_bytes["inventory_scan"]),
        "inventory_runtime_capture": sha256_bytes(
            loaded.exact_artifact_bytes["inventory_runtime_capture"]
        ),
        "inventory_acquisition_evidence": sha256_bytes(
            loaded.exact_artifact_bytes["inventory_acquisition_evidence"]
        ),
        "scanner": scanner_digest,
        "trading_hours_template": sha256_bytes(exact_external["trading_hours_template"]),
        "ninjatrader_config": sha256_bytes(exact_external["ninjatrader_config"]),
        "ninjatrader_log": sha256_bytes(exact_external["ninjatrader_log"]),
        "ninjatrader_trace": sha256_bytes(exact_external["ninjatrader_trace"]),
    }
    return ValidatedInventoryEvidence(
        loaded=loaded,
        provider_acquisition=MappingProxyType(provider),
        qualifying_request=MappingProxyType(request),
        artifact_hashes=MappingProxyType(artifact_hashes),
        external_evidence=external,
        earliest_session_begin=earliest_session_begin,
        latest_session_end=latest_session_end,
    )
