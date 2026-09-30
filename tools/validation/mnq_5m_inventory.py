"""Build and atomically publish the objective MNQ five-minute inventory."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Mapping, Sequence

from tools.validation.mnq_5m_inventory_calendar import (
    TEMPLATE_NAME,
    VerifiedInventoryCalendar,
    VerifiedSession,
    verify_inventory_calendar,
)
from tools.validation.mnq_5m_inventory_common import (
    EXCLUSION_REASON_ORDER,
    _load_schema_validated_json_bytes,
    canonical_payload_sha256,
    load_schema_validated_json,
    reconcile_inventory_entries,
    sha256_bytes,
    write_json_atomically,
)
from tools.validation.mnq_5m_inventory_evidence import (
    InventoryValidationError,
    ValidatedInventoryEvidence,
    finalize_inventory_evidence,
    load_inventory_evidence,
)
from tools.validation.mnq_5m_checkpoint_verify import (
    CheckpointVerificationError,
    verify_inventory_toolset_checkpoint,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "validation" / "mnq_5m_multiwindow" / "schemas"
INVENTORY_PROVENANCE_SCHEMA = SCHEMA_DIR / "inventory_provenance.schema.json"
SOURCE_INVENTORY_SCHEMA = SCHEMA_DIR / "source_inventory_v2.schema.json"
EXCLUSIONS_SCHEMA = SCHEMA_DIR / "exclusions_v2.schema.json"
TOOLSET_MANIFEST_SCHEMA = SCHEMA_DIR / "toolset_manifest_v2.schema.json"
TOOLSET_MANIFEST_REPOSITORY_PATH = "validation/mnq_5m_multiwindow/toolset_manifest.json"
PINNED_HIERARCHY_COMMIT = "04a73e1401d44688660b211d9db6918113482856"
COHORT_ID = "mnq-202609-5m-v1"
CANONICALIZATION_ID = "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
BAR_TIMESTAMP_RE = re.compile(r"^[0-9]{8} [0-9]{6}$")

QUALITY_KEYS = frozenset(
    {
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
)


@dataclass(frozen=True)
class InventoryBuildResult:
    source_inventory: Mapping[str, object]
    exclusions: Mapping[str, object]


@dataclass(frozen=True)
class InventoryFinalizationResult:
    inventory_provenance: Mapping[str, object]
    source_inventory: Mapping[str, object]
    exclusions: Mapping[str, object]


def _fail(message: str) -> None:
    raise InventoryValidationError(message)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"invalid {label}")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        _fail(f"invalid {label}")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail(f"invalid {label}")
    return value


def _hash_or_none(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(f"invalid {label}")
    return value


def _commit(value: object, label: str) -> str:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        _fail(f"invalid {label}")
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            _thaw(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _validate_document(
    value: Mapping[str, object],
    schema_path: Path,
    label: str,
) -> None:
    try:
        _load_schema_validated_json_bytes(_canonical_json_bytes(value), schema_path, label)
    except InventoryValidationError:
        raise
    except ValueError as error:
        raise InventoryValidationError(f"invalid {label}") from error


def _strict_indexes(
    quality: Mapping[str, object],
    *,
    indexes_key: str,
    count_key: str,
) -> int:
    indexes = _sequence(quality.get(indexes_key), indexes_key)
    count = _integer(quality.get(count_key), count_key)
    if count != len(indexes):
        _fail(f"{count_key} does not reconcile with {indexes_key}")
    previous = -1
    for value in indexes:
        index = _integer(value, indexes_key)
        if index <= previous:
            _fail(f"invalid supplied-order {indexes_key}")
        previous = index
    return count


def _strict_timestamps(
    quality: Mapping[str, object],
    *,
    values_key: str,
    count_key: str,
    require_unique: bool = True,
) -> int:
    values = _sequence(quality.get(values_key), values_key)
    count = _integer(quality.get(count_key), count_key)
    if count != len(values) or (require_unique and len(set(values)) != len(values)):
        _fail(f"{count_key} does not reconcile with {values_key}")
    for value in values:
        if not isinstance(value, str) or BAR_TIMESTAMP_RE.fullmatch(value) is None:
            _fail(f"invalid {values_key}")
    return count


def _timestamp_or_none(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or BAR_TIMESTAMP_RE.fullmatch(value) is None:
        _fail(f"invalid {label}")
    return value


def _quality_reasons(quality: Mapping[str, object]) -> tuple[list[str], int, str | None, str | None]:
    if set(quality) != QUALITY_KEYS:
        _fail("unknown or missing inventory quality fact")
    observed_count = _integer(
        quality.get("observed_native_five_minute_bar_count"),
        "observed native five-minute bar count",
    )
    valid_from_start = _integer(
        quality.get("observed_valid_count_from_session_start"),
        "observed valid count from session start",
    )
    if valid_from_start > observed_count:
        _fail("valid native prefix exceeds observed native bar count")

    duplicate_count = _strict_indexes(
        quality,
        indexes_key="duplicate_timestamp_indexes",
        count_key="duplicate_timestamp_count",
    )
    decreasing_count = _strict_indexes(
        quality,
        indexes_key="decreasing_timestamp_indexes",
        count_key="decreasing_timestamp_count",
    )
    malformed_count = _strict_indexes(
        quality,
        indexes_key="malformed_or_non_finite_ohlcv_indexes",
        count_key="malformed_or_non_finite_ohlcv_count",
    )
    invalid_geometry_count = _strict_indexes(
        quality,
        indexes_key="invalid_ohlc_geometry_indexes",
        count_key="invalid_ohlc_geometry_count",
    )
    negative_volume_count = _strict_indexes(
        quality,
        indexes_key="negative_volume_indexes",
        count_key="negative_volume_count",
    )
    non_integral_volume_count = _strict_indexes(
        quality,
        indexes_key="non_integral_volume_indexes",
        count_key="non_integral_volume_count",
    )
    missing_count = _strict_timestamps(
        quality,
        values_key="missing_expected_open_timestamps",
        count_key="missing_expected_open_timestamp_count",
    )
    unexpected_count = _strict_timestamps(
        quality,
        values_key="unexpected_timestamps",
        count_key="unexpected_timestamp_count",
        require_unique=False,
    )

    increasing = quality.get("supplied_order_strictly_increasing")
    if not isinstance(increasing, bool):
        _fail("invalid supplied-order chronology state")
    if increasing != (duplicate_count == 0 and decreasing_count == 0):
        _fail("supplied-order chronology facts do not reconcile")
    if quality.get("canonicalization_id") != CANONICALIZATION_ID:
        _fail("unknown inventory canonicalization")

    first_timestamp = _timestamp_or_none(
        quality.get("first_observed_timestamp"), "first observed timestamp"
    )
    two_hundred_fiftieth = _timestamp_or_none(
        quality.get("two_hundred_fiftieth_native_timestamp"),
        "two hundred fiftieth native timestamp",
    )
    last_timestamp = _timestamp_or_none(
        quality.get("last_observed_session_timestamp"),
        "last observed session timestamp",
    )
    if observed_count == 0 and any(
        value is not None for value in (first_timestamp, two_hundred_fiftieth, last_timestamp)
    ):
        _fail("zero-bar session contains observed timestamps")
    if observed_count < 250 and two_hundred_fiftieth is not None:
        _fail("short session contains a 250th native timestamp")

    first_hash = _hash_or_none(
        quality.get("first_250_source_sha256"), "first-250 source hash"
    )
    complete_hash = _hash_or_none(
        quality.get("complete_session_source_sha256"), "complete-session source hash"
    )
    if observed_count < 250 and first_hash is not None:
        _fail("first-250 source hash cannot cover fewer than 250 observed records")
    if observed_count >= 250 and complete_hash is not None and first_hash is None:
        _fail("first-250 source hash is missing despite available canonical rows")
    if observed_count == 0 and complete_hash is not None:
        _fail("zero-bar session contains a complete-session hash")
    if malformed_count and complete_hash is not None:
        _fail("non-finite session cannot have canonical complete-session bytes")

    applicable: set[str] = set()
    if (
        (observed_count > 0 and (first_timestamp is None or last_timestamp is None))
        or (observed_count >= 250 and two_hundred_fiftieth is None)
    ):
        applicable.add("INCOMPLETE_PROVENANCE")
    if valid_from_start < 250:
        applicable.add("FEWER_THAN_250_NATIVE_BARS")
    if duplicate_count or decreasing_count:
        applicable.add("DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS")
    if unexpected_count:
        applicable.add("TRADING_HOURS_INCONSISTENCY")
    if malformed_count or negative_volume_count or non_integral_volume_count:
        applicable.add("MALFORMED_OR_NON_FINITE_OHLCV")
    if invalid_geometry_count:
        applicable.add("INVALID_OHLC_GEOMETRY")
    if missing_count:
        applicable.add("UNEXPECTED_MISSING_BARS")
    if complete_hash is None:
        applicable.add("SOURCE_CORRUPTION")
    return (
        [reason for reason in EXCLUSION_REASON_ORDER if reason in applicable],
        observed_count,
        first_hash,
        complete_hash,
    )


def _session_entry(session: VerifiedSession) -> dict[str, object]:
    observation = _mapping(session.observation, "verified session observation")
    if (
        observation.get("classification") != "SESSION"
        or observation.get("exchange_trading_date") != session.trading_date.isoformat()
        or not session.segments
    ):
        _fail("verified session identity mismatch")
    previous_end: datetime | None = None
    for segment in session.segments:
        if (
            segment.begin_application.tzinfo is None
            or segment.begin_application.utcoffset() is None
            or segment.end_application.tzinfo is None
            or segment.end_application.utcoffset() is None
            or segment.begin_application >= segment.end_application
            or (previous_end is not None and segment.begin_application < previous_end)
        ):
            _fail("invalid verified session segment order")
        previous_end = segment.end_application
    quality = _mapping(observation.get("quality"), "verified session quality")
    reasons, observed_count, first_hash, complete_hash = _quality_reasons(quality)
    return {
        "trading_date": session.trading_date.isoformat(),
        "eligible": not reasons,
        "exclusion_reasons": reasons,
        "session_begin_application": session.segments[0].begin_application.strftime(
            "%Y%m%d %H%M%S"
        ),
        "session_end_application": session.segments[-1].end_application.strftime(
            "%Y%m%d %H%M%S"
        ),
        "observed_native_bar_count": observed_count,
        "first_250_source_sha256": first_hash,
        "complete_session_source_sha256": complete_hash,
    }


def build_inventory(
    *,
    evidence: ValidatedInventoryEvidence,
    calendar: VerifiedInventoryCalendar,
    inventory_provenance_sha256: str,
    inventory_scan_sha256: str,
    producing_checkpoint: str,
) -> InventoryBuildResult:
    """Map verified facts to reconciled inventory and exclusion artifacts."""

    if SHA256_RE.fullmatch(inventory_provenance_sha256) is None:
        _fail("invalid inventory provenance hash")
    if SHA256_RE.fullmatch(inventory_scan_sha256) is None:
        _fail("invalid inventory scan hash")
    producing_checkpoint = _commit(producing_checkpoint, "producing checkpoint")
    if evidence.artifact_hashes.get("inventory_scan") != inventory_scan_sha256:
        _fail("inventory scan hash does not match validated evidence")
    if (
        evidence.earliest_session_begin != calendar.earliest_session_begin
        or evidence.latest_session_end != calendar.latest_session_end
    ):
        _fail("validated provider bounds do not match verified calendar bounds")
    if not calendar.sessions:
        _fail("verified calendar contains no actual session")

    entries: list[dict[str, object]] = []
    previous_date: date | None = None
    previous_end: datetime | None = None
    for session in calendar.sessions:
        if previous_date is not None and session.trading_date <= previous_date:
            _fail("verified sessions are not strictly chronological and unique")
        if (
            previous_end is not None
            and session.segments
            and session.segments[0].begin_application < previous_end
        ):
            _fail("verified sessions are not chronological")
        entry = _session_entry(session)
        entries.append(entry)
        previous_date = session.trading_date
        previous_end = session.segments[-1].end_application

    if (
        calendar.earliest_session_begin != calendar.sessions[0].segments[0].begin_application
        or calendar.latest_session_end != calendar.sessions[-1].segments[-1].end_application
    ):
        _fail("verified calendar bounds do not reconcile with sessions")

    eligible_count = sum(1 for entry in entries if entry["eligible"] is True)
    outcome = "READY_FOR_SELECTION" if eligible_count >= 10 else "COHORT_INCOMPLETE"
    source_inventory: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_INVENTORY",
        "cohort_outcome": outcome,
        "cohort_id": COHORT_ID,
        "contract_policy": {
            "contract_label": "MNQ SEP26",
            "full_name": "MNQ SEP26",
            "expiry_month": 9,
            "expiry_year": 2026,
            "candidate_date_start": "2026-06-22",
            "candidate_date_end": "2026-07-24",
        },
        "inventory_scan": {
            "path": "inventory_scan.json",
            "schema_version": "1.0",
            "sha256": inventory_scan_sha256,
            "producing_checkpoint": producing_checkpoint,
        },
        "inventory_provenance": {
            "path": "inventory_provenance.json",
            "schema_version": "1.0",
            "sha256": inventory_provenance_sha256,
            "producing_checkpoint": producing_checkpoint,
        },
        "producing_checkpoint": producing_checkpoint,
        "candidate_count": len(entries),
        "eligible_count": eligible_count,
        "entries": entries,
        "aggregate_payload_sha256": "",
    }
    source_inventory["aggregate_payload_sha256"] = canonical_payload_sha256(source_inventory)

    exclusions: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_INVENTORY",
        "cohort_outcome": outcome,
        "cohort_id": COHORT_ID,
        "source_inventory_sha256": sha256_bytes(_canonical_json_bytes(source_inventory)),
        "producing_checkpoint": producing_checkpoint,
        "entries": [
            {"trading_date": entry["trading_date"], "reasons": list(entry["exclusion_reasons"])}
            for entry in entries
            if entry["eligible"] is False
        ],
        "aggregate_payload_sha256": "",
    }
    exclusions["aggregate_payload_sha256"] = canonical_payload_sha256(exclusions)
    _validate_document(source_inventory, SOURCE_INVENTORY_SCHEMA, "source inventory")
    _validate_document(exclusions, EXCLUSIONS_SCHEMA, "exclusions")
    _cross_reconcile({}, source_inventory, exclusions, require_provenance=False)
    return InventoryBuildResult(source_inventory, exclusions)


def _git_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        environment.pop(name, None)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return environment


def _run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _load_toolset_manifest_binding(
    *,
    repository_path: str | Path,
    trusted_toolset_checkpoint: str,
    producing_checkpoint: str,
) -> tuple[str, dict[str, object]]:
    repository = Path(repository_path).resolve()
    trusted = _commit(trusted_toolset_checkpoint, "trusted toolset checkpoint")
    producing = _commit(producing_checkpoint, "producing checkpoint")
    manifest_path = repository / Path(TOOLSET_MANIFEST_REPOSITORY_PATH)
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as error:
        raise InventoryValidationError("cannot read committed toolset manifest") from error
    committed = _run_git(repository, "show", f"{trusted}:{TOOLSET_MANIFEST_REPOSITORY_PATH}")
    ancestry = _run_git(repository, "merge-base", "--is-ancestor", producing, trusted)
    if committed.returncode != 0 or ancestry.returncode != 0 or committed.stdout != manifest_bytes:
        _fail("toolset manifest does not match committed trusted-checkpoint bytes")
    try:
        manifest = _load_schema_validated_json_bytes(
            manifest_bytes,
            TOOLSET_MANIFEST_SCHEMA,
            "toolset manifest",
        )
    except ValueError as error:
        raise InventoryValidationError("invalid toolset manifest") from error
    if (
        manifest.get("producing_checkpoint") != producing
        or manifest.get("pinned_production_hierarchy_commit") != PINNED_HIERARCHY_COMMIT
        or manifest.get("aggregate_payload_sha256") != canonical_payload_sha256(manifest)
    ):
        _fail("toolset manifest binding mismatch")
    binding = {
        "status": manifest["status"],
        "stage": manifest["stage"],
        "schema_version": manifest["schema_version"],
        "producing_checkpoint": producing,
        "trusted_checkpoint": trusted,
        "pinned_production_hierarchy_commit": PINNED_HIERARCHY_COMMIT,
        "aggregate_payload_sha256": manifest["aggregate_payload_sha256"],
    }
    return sha256_bytes(manifest_bytes), binding


def _build_inventory_provenance(
    *,
    evidence: ValidatedInventoryEvidence,
    calendar: VerifiedInventoryCalendar,
    trusted_toolset_checkpoint: str,
    producing_checkpoint: str,
    toolset_manifest_sha256: str,
    toolset_binding: Mapping[str, object],
) -> dict[str, object]:
    trusted = _commit(trusted_toolset_checkpoint, "trusted toolset checkpoint")
    producing = _commit(producing_checkpoint, "producing checkpoint")
    if SHA256_RE.fullmatch(toolset_manifest_sha256) is None:
        _fail("invalid toolset manifest hash")
    scan = _mapping(evidence.loaded.inventory_scan, "validated inventory scan")
    contract = _mapping(scan.get("contract"), "inventory scan contract")
    bar_series = _mapping(scan.get("bar_series"), "inventory scan bar series")
    artifact_hashes = dict(evidence.artifact_hashes)
    if set(artifact_hashes) != {
        "inventory_scan",
        "inventory_runtime_capture",
        "inventory_acquisition_evidence",
        "scanner",
        "trading_hours_template",
        "ninjatrader_config",
        "ninjatrader_log",
        "ninjatrader_trace",
    }:
        _fail("validated inventory artifact hashes are incomplete")
    if artifact_hashes["trading_hours_template"] != calendar.template_sha256:
        _fail("validated template hash does not match verified calendar")
    artifact_hashes["toolset_manifest"] = toolset_manifest_sha256
    provenance = {
        "schema_version": "1.0",
        "status": "PROVEN",
        "acquisition_id": scan.get("acquisition_id"),
        "cohort_id": COHORT_ID,
        "contract": {
            "contract_label": contract.get("contract_label"),
            "full_name": contract.get("full_name"),
            "master_name": contract.get("master_name"),
            "expiry_month": contract.get("expiry_month"),
            "expiry_year": contract.get("expiry_year"),
        },
        "bar_series": {
            "type": bar_series.get("type"),
            "value": bar_series.get("value"),
            "native": bar_series.get("native"),
        },
        "provider_acquisition": _thaw(evidence.provider_acquisition),
        "calendar_binding": {
            "status": "VERIFIED",
            "trading_hours_name": TEMPLATE_NAME,
            "civil_date_start": "2026-06-22",
            "civil_date_end": "2026-07-24",
            "civil_date_count": 33,
            "session_count": len(calendar.sessions),
            "earliest_session_begin": calendar.earliest_session_begin.isoformat(),
            "latest_session_end": calendar.latest_session_end.isoformat(),
            "trading_hours_template_sha256": calendar.template_sha256,
            "calendar_binding_sha256": calendar.calendar_binding_sha256,
        },
        "artifact_hashes": artifact_hashes,
        "external_evidence": _thaw(evidence.external_evidence),
        "inventory_scan_binding": {
            "path": "inventory_scan.json",
            "schema_version": "1.0",
            "sha256": artifact_hashes["inventory_scan"],
        },
        "transformations": {
            "sorted": False,
            "filled": False,
            "interpolated": False,
            "resampled": False,
            "timezone_converted": False,
            "back_adjusted": False,
        },
        "toolset_binding": _thaw(toolset_binding),
        "checkpoint_verification": {
            "status": "VERIFIED",
            "trusted_toolset_checkpoint": trusted,
            "pinned_production_hierarchy_commit": PINNED_HIERARCHY_COMMIT,
        },
    }
    binding = _mapping(provenance["toolset_binding"], "toolset binding")
    if (
        binding.get("producing_checkpoint") != producing
        or binding.get("trusted_checkpoint") != trusted
        or binding.get("pinned_production_hierarchy_commit") != PINNED_HIERARCHY_COMMIT
    ):
        _fail("toolset/checkpoint binding mismatch")
    return provenance


def _cross_reconcile(
    inventory_provenance: Mapping[str, object],
    source_inventory: Mapping[str, object],
    exclusions: Mapping[str, object],
    *,
    require_provenance: bool = True,
) -> None:
    if source_inventory.get("aggregate_payload_sha256") != canonical_payload_sha256(
        source_inventory
    ):
        _fail("source inventory aggregate hash mismatch")
    if exclusions.get("aggregate_payload_sha256") != canonical_payload_sha256(exclusions):
        _fail("exclusions aggregate hash mismatch")
    if exclusions.get("source_inventory_sha256") != sha256_bytes(
        _canonical_json_bytes(source_inventory)
    ):
        _fail("exclusions/source-inventory hash mismatch")
    if (
        exclusions.get("cohort_outcome") != source_inventory.get("cohort_outcome")
        or exclusions.get("cohort_id") != source_inventory.get("cohort_id")
        or exclusions.get("producing_checkpoint") != source_inventory.get("producing_checkpoint")
    ):
        _fail("inventory/exclusions identity mismatch")

    try:
        reconcile_inventory_entries(source_inventory, exclusions)
    except ValueError as error:
        _fail(str(error))

    if not require_provenance:
        return
    scan_binding = _mapping(source_inventory.get("inventory_scan"), "inventory scan binding")
    provenance_binding = _mapping(
        source_inventory.get("inventory_provenance"), "inventory provenance binding"
    )
    provenance_scan = _mapping(
        inventory_provenance.get("inventory_scan_binding"), "provenance scan binding"
    )
    artifact_hashes = _mapping(
        inventory_provenance.get("artifact_hashes"), "provenance artifact hashes"
    )
    if (
        scan_binding.get("sha256") != provenance_scan.get("sha256")
        or scan_binding.get("sha256") != artifact_hashes.get("inventory_scan")
        or provenance_binding.get("sha256")
        != sha256_bytes(_canonical_json_bytes(inventory_provenance))
    ):
        _fail("inventory provenance/scan cross-binding mismatch")


def _validate_staged_bundle(
    staging_directory: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    try:
        provenance = load_schema_validated_json(
            staging_directory / "inventory_provenance.json",
            INVENTORY_PROVENANCE_SCHEMA,
            "inventory provenance",
        )
        source_inventory = load_schema_validated_json(
            staging_directory / "source_inventory.json",
            SOURCE_INVENTORY_SCHEMA,
            "source inventory",
        )
        exclusions = load_schema_validated_json(
            staging_directory / "exclusions.json",
            EXCLUSIONS_SCHEMA,
            "exclusions",
        )
    except ValueError as error:
        raise InventoryValidationError("invalid staged inventory bundle") from error
    _cross_reconcile(provenance, source_inventory, exclusions)
    return provenance, source_inventory, exclusions


def _publish_bundle(
    *,
    inventory_provenance_output: str | Path,
    source_inventory_output: str | Path,
    exclusions_output: str | Path,
    inventory_provenance: Mapping[str, object],
    source_inventory: Mapping[str, object],
    exclusions: Mapping[str, object],
) -> None:
    paths = (
        Path(inventory_provenance_output).resolve(),
        Path(source_inventory_output).resolve(),
        Path(exclusions_output).resolve(),
    )
    if tuple(path.name for path in paths) != (
        "inventory_provenance.json",
        "source_inventory.json",
        "exclusions.json",
    ):
        _fail("inventory output basenames must be exact")
    final_directory = paths[0].parent
    if any(path.parent != final_directory for path in paths):
        _fail("inventory outputs must share one final directory")
    if final_directory.exists():
        _fail("inventory final directory must be absent")
    if not final_directory.parent.is_dir():
        _fail("inventory final-directory parent must exist")

    staging_directory = Path(
        tempfile.mkdtemp(
            prefix=f".{final_directory.name}.",
            suffix=".staging",
            dir=final_directory.parent,
        )
    )
    try:
        write_json_atomically(
            staging_directory / "inventory_provenance.json", inventory_provenance
        )
        write_json_atomically(staging_directory / "source_inventory.json", source_inventory)
        write_json_atomically(staging_directory / "exclusions.json", exclusions)
        _validate_staged_bundle(staging_directory)
        staging_directory.rename(final_directory)
    except BaseException:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
        raise


def finalize_inventory_bundle(
    *,
    runtime_capture_path: str | Path,
    inventory_scan_path: str | Path,
    acquisition_evidence_path: str | Path,
    scanner_path: str | Path,
    trading_hours_template_path: str | Path,
    config_path: str | Path,
    log_path: str | Path,
    trace_path: str | Path,
    repository_path: str | Path,
    expected_repository_identity: str,
    trusted_toolset_checkpoint: str,
    producing_checkpoint: str,
    inventory_provenance_output: str | Path,
    source_inventory_output: str | Path,
    exclusions_output: str | Path,
) -> InventoryFinalizationResult:
    """Verify both evidence domains and atomically publish all three results."""

    try:
        verify_inventory_toolset_checkpoint(
            repository_path=repository_path,
            bundle_root=repository_path,
            toolset_manifest_path=TOOLSET_MANIFEST_REPOSITORY_PATH,
            trusted_toolset_checkpoint=trusted_toolset_checkpoint,
            expected_repository_identity=expected_repository_identity,
            expected_pinned_production_commit=PINNED_HIERARCHY_COMMIT,
        )
    except CheckpointVerificationError as error:
        raise InventoryValidationError(
            "inventory policy toolset checkpoint verification failed"
        ) from error

    loaded = load_inventory_evidence(
        runtime_capture_path=runtime_capture_path,
        inventory_scan_path=inventory_scan_path,
        acquisition_evidence_path=acquisition_evidence_path,
    )
    try:
        template_bytes = Path(trading_hours_template_path).resolve().read_bytes()
    except OSError as error:
        raise InventoryValidationError("cannot read Trading Hours template") from error
    calendar = verify_inventory_calendar(loaded.inventory_scan, template_bytes)
    evidence = finalize_inventory_evidence(
        loaded=loaded,
        scanner_path=scanner_path,
        trading_hours_template_path=trading_hours_template_path,
        config_path=config_path,
        log_path=log_path,
        trace_path=trace_path,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        repository_path=repository_path,
        expected_repository_identity=expected_repository_identity,
        earliest_session_begin=calendar.earliest_session_begin,
        latest_session_end=calendar.latest_session_end,
    )
    toolset_manifest_sha256, toolset_binding = _load_toolset_manifest_binding(
        repository_path=repository_path,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        producing_checkpoint=producing_checkpoint,
    )
    provenance = _build_inventory_provenance(
        evidence=evidence,
        calendar=calendar,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        producing_checkpoint=producing_checkpoint,
        toolset_manifest_sha256=toolset_manifest_sha256,
        toolset_binding=toolset_binding,
    )
    _validate_document(provenance, INVENTORY_PROVENANCE_SCHEMA, "inventory provenance")
    provenance_sha256 = sha256_bytes(_canonical_json_bytes(provenance))
    inventory_scan_sha256 = evidence.artifact_hashes["inventory_scan"]
    built = build_inventory(
        evidence=evidence,
        calendar=calendar,
        inventory_provenance_sha256=provenance_sha256,
        inventory_scan_sha256=inventory_scan_sha256,
        producing_checkpoint=trusted_toolset_checkpoint,
    )
    _validate_document(built.source_inventory, SOURCE_INVENTORY_SCHEMA, "source inventory")
    _validate_document(built.exclusions, EXCLUSIONS_SCHEMA, "exclusions")
    _cross_reconcile(provenance, built.source_inventory, built.exclusions)
    _publish_bundle(
        inventory_provenance_output=inventory_provenance_output,
        source_inventory_output=source_inventory_output,
        exclusions_output=exclusions_output,
        inventory_provenance=provenance,
        source_inventory=built.source_inventory,
        exclusions=built.exclusions,
    )
    return InventoryFinalizationResult(provenance, built.source_inventory, built.exclusions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-capture", required=True, type=Path)
    parser.add_argument("--inventory-scan", required=True, type=Path)
    parser.add_argument("--acquisition-evidence", required=True, type=Path)
    parser.add_argument("--scanner", required=True, type=Path)
    parser.add_argument("--trading-hours-template", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--repository-path", required=True, type=Path)
    parser.add_argument("--expected-repository-identity", required=True)
    parser.add_argument("--trusted-toolset-checkpoint", required=True)
    parser.add_argument("--producing-checkpoint", required=True)
    parser.add_argument("--inventory-provenance-output", required=True, type=Path)
    parser.add_argument("--source-inventory-output", required=True, type=Path)
    parser.add_argument("--exclusions-output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    finalize_inventory_bundle(
        runtime_capture_path=args.runtime_capture,
        inventory_scan_path=args.inventory_scan,
        acquisition_evidence_path=args.acquisition_evidence,
        scanner_path=args.scanner,
        trading_hours_template_path=args.trading_hours_template,
        config_path=args.config,
        log_path=args.log,
        trace_path=args.trace,
        repository_path=args.repository_path,
        expected_repository_identity=args.expected_repository_identity,
        trusted_toolset_checkpoint=args.trusted_toolset_checkpoint,
        producing_checkpoint=args.producing_checkpoint,
        inventory_provenance_output=args.inventory_provenance_output,
        source_inventory_output=args.source_inventory_output,
        exclusions_output=args.exclusions_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
