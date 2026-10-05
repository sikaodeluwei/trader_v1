from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

import tools.validation.mnq_5m_checkpoint_verify as checkpoint_verify
import tools.validation.mnq_5m_selection as selection_module
from tools.validation import (
    mnq_5m_acquisition,
    mnq_5m_inventory,
    mnq_5m_inventory_calendar,
    mnq_5m_inventory_common,
    mnq_5m_inventory_evidence,
)
from tools.validation.mnq_5m_checkpoint_verify import (
    CheckpointVerificationError,
    _verify_checkpoints_with_test_pinned_commit,
    main as verifier_main,
)
from tools.validation.mnq_5m_inventory import build_inventory
from tools.validation.mnq_5m_inventory_calendar import (
    SessionSegment,
    VerifiedInventoryCalendar,
    VerifiedSession,
)
from tools.validation.mnq_5m_inventory_evidence import ValidatedInventoryEvidence
from tools.validation.mnq_5m_selection import generate_selection


REPOSITORY_IDENTITY = "https://github.com/sikaodeluwei/trader_v1.git"
TOOLSET_MANIFEST_PATH = "validation/mnq_5m_multiwindow/toolset_manifest.json"
SELECTION_REGISTRY_PATH = (
    "validation/mnq_5m_multiwindow/selection_registry.json"
)
INVENTORY_PATH = "validation/mnq_5m_multiwindow/source_inventory.json"
EXCLUSIONS_PATH = "validation/mnq_5m_multiwindow/exclusions.json"
COMPONENT_PATHS = {
    "protocol_spec": (
        "docs/superpowers/specs/2026-09-13-mnq-5m-multiwindow-validation-design.md"
    ),
    "acquisition_exporter": (
        "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs"
    ),
    "acquisition_finalizer": "tools/validation/mnq_5m_acquisition.py",
    "checkpoint_verifier": "tools/validation/mnq_5m_checkpoint_verify.py",
    "provenance_schema": (
        "validation/mnq_5m_multiwindow/schemas/provenance.schema.json"
    ),
    "checkpoint_attestation_schema": (
        "validation/mnq_5m_multiwindow/schemas/checkpoint_attestation.schema.json"
    ),
    "selection_registry_schema": (
        "validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json"
    ),
    "toolset_manifest_schema": (
        "validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json"
    ),
    "source_inventory_schema": (
        "validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json"
    ),
    "exclusion_ledger_schema": (
        "validation/mnq_5m_multiwindow/schemas/exclusions.schema.json"
    ),
}
EXPECTED_LEGACY_TOOLSET_COMPONENT_PATHS = {
    "protocol_spec": (
        "docs/superpowers/specs/"
        "2026-09-13-mnq-5m-multiwindow-validation-design.md"
    ),
    "acquisition_exporter": (
        "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs"
    ),
    "acquisition_finalizer": "tools/validation/mnq_5m_acquisition.py",
    "checkpoint_verifier": "tools/validation/mnq_5m_checkpoint_verify.py",
    "provenance_schema": (
        "validation/mnq_5m_multiwindow/schemas/provenance.schema.json"
    ),
    "checkpoint_attestation_schema": (
        "validation/mnq_5m_multiwindow/schemas/checkpoint_attestation.schema.json"
    ),
    "selection_registry_schema": (
        "validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json"
    ),
    "toolset_manifest_schema": (
        "validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json"
    ),
    "source_inventory_schema": (
        "validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json"
    ),
    "exclusion_ledger_schema": (
        "validation/mnq_5m_multiwindow/schemas/exclusions.schema.json"
    ),
}
EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS = {
    "protocol_spec": "docs/superpowers/specs/2026-09-13-mnq-5m-multiwindow-validation-design.md",
    "inventory_design_spec": "docs/superpowers/specs/2026-09-16-mnq-5m-official-inventory-scanner-design.md",
    "validation_dependencies": "requirements-validation.txt",
    "acquisition_exporter": "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs",
    "acquisition_finalizer": "tools/validation/mnq_5m_acquisition.py",
    "inventory_scanner": "tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs",
    "inventory_common": "tools/validation/mnq_5m_inventory_common.py",
    "inventory_evidence_finalizer": "tools/validation/mnq_5m_inventory_evidence.py",
    "inventory_calendar_verifier": "tools/validation/mnq_5m_inventory_calendar.py",
    "inventory_builder": "tools/validation/mnq_5m_inventory.py",
    "selection_generator": "tools/validation/mnq_5m_selection.py",
    "selected_source_checker": "tools/validation/mnq_5m_selected_source_check.py",
    "checkpoint_verifier": "tools/validation/mnq_5m_checkpoint_verify.py",
    "provenance_schema": "validation/mnq_5m_multiwindow/schemas/provenance_v1_3.schema.json",
    "inventory_scan_schema": "validation/mnq_5m_multiwindow/schemas/inventory_scan.schema.json",
    "inventory_runtime_capture_schema": "validation/mnq_5m_multiwindow/schemas/inventory_runtime_capture.schema.json",
    "inventory_acquisition_evidence_schema": "validation/mnq_5m_multiwindow/schemas/inventory_acquisition_evidence.schema.json",
    "inventory_provenance_schema": "validation/mnq_5m_multiwindow/schemas/inventory_provenance.schema.json",
    "checkpoint_attestation_schema": "validation/mnq_5m_multiwindow/schemas/checkpoint_attestation_v2.schema.json",
    "selection_registry_schema": "validation/mnq_5m_multiwindow/schemas/selection_registry_v2.schema.json",
    "toolset_manifest_schema": "validation/mnq_5m_multiwindow/schemas/toolset_manifest_v2.schema.json",
    "source_inventory_schema": "validation/mnq_5m_multiwindow/schemas/source_inventory_v2.schema.json",
    "exclusion_ledger_schema": "validation/mnq_5m_multiwindow/schemas/exclusions_v2.schema.json",
}
INVENTORY_ARTIFACT_REPOSITORY_PATHS = {
    "inventory_runtime_capture": "inventory_runtime_capture.json",
    "inventory_scan": "inventory_scan.json",
    "trading_hours_template": "trading_hours_template.xml",
    "inventory_acquisition_evidence": "inventory_acquisition_evidence.json",
    "inventory_provenance": "inventory_provenance.json",
    "source_inventory": "source_inventory.json",
    "exclusions": "exclusions.json",
}
V2_SELECTION_REGISTRY_PATH = "selection_registry.json"
INVENTORY_ACQUISITION_ID = "inventory-acquisition"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _payload_hash(value: dict[str, object]) -> str:
    payload = deepcopy(value)
    payload.pop("aggregate_payload_sha256", None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _attestation_hash(value: dict[str, object]) -> str:
    payload = deepcopy(value)
    payload.pop("attestation_sha256", None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _write_payload(path: Path, value: dict[str, object]) -> None:
    value["aggregate_payload_sha256"] = _payload_hash(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _git(
    repo: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Checkpoint Test",
        "GIT_AUTHOR_EMAIL": "checkpoint@example.invalid",
        "GIT_COMMITTER_NAME": "Checkpoint Test",
        "GIT_COMMITTER_EMAIL": "checkpoint@example.invalid",
        "GIT_AUTHOR_DATE": "2026-09-14T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-09-14T00:00:00+00:00",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "--all")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _git_blob(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        check=True,
        capture_output=True,
    ).stdout


@dataclass
class CheckpointFixture:
    repo: Path
    bundle: Path
    pinned_commit: str
    component_commit: str
    toolset_checkpoint: str
    inventory_checkpoint: str
    selection_checkpoint: str
    manifest: Path
    registry: Path


def _copy_component_sources(repo: Path, *, fake_verifier: bool = False) -> None:
    project_root = Path(__file__).resolve().parents[1]
    for role, relative in COMPONENT_PATHS.items():
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = project_root / relative
        if role == "checkpoint_verifier" and fake_verifier:
            destination.write_text(
                "# frozen but not executing verifier\n", encoding="utf-8"
            )
        else:
            destination.write_bytes(source.read_bytes())


def _refresh_bundle(fixture: CheckpointFixture) -> None:
    for role, relative in COMPONENT_PATHS.items():
        destination = fixture.bundle / f"{role}.artifact"
        destination.write_bytes(
            _git_blob(fixture.repo, fixture.toolset_checkpoint, relative)
        )
    for relative, checkpoint in (
        (TOOLSET_MANIFEST_PATH, fixture.selection_checkpoint),
        (SELECTION_REGISTRY_PATH, fixture.selection_checkpoint),
        (INVENTORY_PATH, fixture.selection_checkpoint),
        (EXCLUSIONS_PATH, fixture.selection_checkpoint),
    ):
        destination = fixture.bundle / Path(relative).name
        destination.write_bytes(_git_blob(fixture.repo, checkpoint, relative))
    fixture.manifest = fixture.bundle / "toolset_manifest.json"
    fixture.registry = fixture.bundle / "selection_registry.json"


def _build_checkpoints(
    tmp_path: Path,
    *,
    fake_verifier: bool = False,
    manifest_mutator=None,
    registry_mutator=None,
) -> CheckpointFixture:
    repo = tmp_path / "repo"
    bundle = tmp_path / "bundle"
    repo.mkdir()
    bundle.mkdir()
    _git(repo, "init")
    _git(repo, "remote", "add", "origin", REPOSITORY_IDENTITY)

    (repo / "PINNED").write_text("production hierarchy\n", encoding="utf-8")
    actual_pinned = _commit(repo, "Pinned production hierarchy")

    _copy_component_sources(repo, fake_verifier=fake_verifier)
    component_commit = _commit(repo, "Freeze tool components")

    components = [
        {
            "role": role,
            "path": relative,
            "bundle_path": f"{role}.artifact",
            "sha256": _sha256_bytes(_git_blob(repo, component_commit, relative)),
            "producing_commit": component_commit,
        }
        for role, relative in COMPONENT_PATHS.items()
    ]
    manifest = {
        "schema_version": "1.0",
        "stage": "SOURCE_ACQUISITION",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": "mnq-202609-5m-v1",
        "producing_checkpoint": component_commit,
        "pinned_production_hierarchy_commit": actual_pinned,
        "runtime": {
            "implementation": "CPython",
            "version": "3.12",
            "dependencies": [
                {"name": "python-standard-library", "version": "3.12"}
            ],
        },
        "canonicalization": (
            "JSON_UTF8_SORTED_KEYS_COMPACT_"
            "EXCLUDE_AGGREGATE_PAYLOAD_SHA256"
        ),
        "components": components,
        "deferred_components": [
            "independent_oracle",
            "blind_project_runner",
            "comparator",
            "cohort_aggregator",
        ],
    }
    if manifest_mutator is not None:
        manifest_mutator(manifest)
    _write_payload(repo / TOOLSET_MANIFEST_PATH, manifest)
    toolset_checkpoint = _commit(repo, "Freeze toolset manifest")

    inventory = {
        "schema_version": "1.0",
        "status": "FROZEN_PRE_EXECUTION",
        "cohort_id": "mnq-202609-5m-v1",
        "contract_policy": {},
        "producing_checkpoint": toolset_checkpoint,
        "entries": [],
    }
    exclusions = {
        "schema_version": "1.0",
        "status": "FROZEN_PRE_EXECUTION",
        "cohort_id": "mnq-202609-5m-v1",
        "producing_checkpoint": toolset_checkpoint,
        "entries": [],
    }
    _write_payload(repo / INVENTORY_PATH, inventory)
    _write_payload(repo / EXCLUSIONS_PATH, exclusions)
    inventory_checkpoint = _commit(repo, "Freeze source inventory")

    registry = {
        "schema_version": "1.0",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": "mnq-202609-5m-v1",
        "producing_checkpoint": inventory_checkpoint,
        "source_inventory": {
            "path": INVENTORY_PATH,
            "bundle_path": "source_inventory.json",
            "schema_version": "1.0",
            "sha256": _sha256_bytes(
                _git_blob(repo, inventory_checkpoint, INVENTORY_PATH)
            ),
            "producing_checkpoint": inventory_checkpoint,
        },
        "exclusion_ledger": {
            "path": EXCLUSIONS_PATH,
            "bundle_path": "exclusions.json",
            "schema_version": "1.0",
            "sha256": _sha256_bytes(
                _git_blob(repo, inventory_checkpoint, EXCLUSIONS_PATH)
            ),
            "producing_checkpoint": inventory_checkpoint,
        },
    }
    if registry_mutator is not None:
        registry_mutator(registry)
    _write_payload(repo / SELECTION_REGISTRY_PATH, registry)
    selection_checkpoint = _commit(repo, "Freeze cohort selection")

    fixture = CheckpointFixture(
        repo=repo,
        bundle=bundle,
        pinned_commit=actual_pinned,
        component_commit=component_commit,
        toolset_checkpoint=toolset_checkpoint,
        inventory_checkpoint=inventory_checkpoint,
        selection_checkpoint=selection_checkpoint,
        manifest=bundle / "toolset_manifest.json",
        registry=bundle / "selection_registry.json",
    )
    _refresh_bundle(fixture)
    return fixture


@dataclass
class InventoryCheckpointFixture:
    repo: Path
    bundle: Path
    pinned_commit: str
    component_commit: str
    toolset_checkpoint: str
    inventory_checkpoint: str
    selection_checkpoint: str
    manifest: Path
    inventory_artifacts: dict[str, Path]
    registry: Path
    external_evidence: dict[str, Path]


def _write_canonical_json(
    path: Path, value: dict[str, object], *, aggregate: bool = False
) -> None:
    if aggregate:
        value["aggregate_payload_sha256"] = _payload_hash(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
    )


def _copy_inventory_component_sources(
    repo: Path, *, fake_verifier: bool = False
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    for role, relative in EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS.items():
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = project_root / relative
        if role == "checkpoint_verifier" and fake_verifier:
            destination.write_bytes(b"# frozen but not executing verifier\n")
        elif source.is_file():
            destination.write_bytes(source.read_bytes())
        else:
            assert role == "selected_source_checker"
            destination.write_bytes(b"# Task 10 placeholder component\n")


def _refresh_inventory_bundle(fixture: InventoryCheckpointFixture) -> None:
    for relative in EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS.values():
        destination = fixture.bundle / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            _git_blob(fixture.repo, fixture.toolset_checkpoint, relative)
        )
    fixture.manifest.write_bytes(
        _git_blob(fixture.repo, fixture.toolset_checkpoint, TOOLSET_MANIFEST_PATH)
    )
    for role, relative in INVENTORY_ARTIFACT_REPOSITORY_PATHS.items():
        fixture.inventory_artifacts[role].write_bytes(
            _git_blob(fixture.repo, fixture.inventory_checkpoint, relative)
        )
    fixture.registry.write_bytes(
        _git_blob(
            fixture.repo,
            fixture.selection_checkpoint,
            V2_SELECTION_REGISTRY_PATH,
        )
    )


def _inventory_transformations() -> dict[str, bool]:
    return {
        "sorted": False,
        "filled": False,
        "interpolated": False,
        "resampled": False,
        "timezone_converted": False,
        "back_adjusted": False,
    }


def _inventory_scanner_transformations() -> dict[str, bool]:
    return {
        **_inventory_transformations(),
        "deduplicated": False,
        "repaired": False,
    }


def _valid_inventory_template() -> bytes:
    weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
    previous = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday")
    sessions = "".join(
        "<Session>"
        f"<BeginDay>{prior}</BeginDay><BeginTime>1700</BeginTime>"
        f"<EndDay>{day}</EndDay><EndTime>1600</EndTime>"
        f"<TradingDay>{day}</TradingDay>"
        "</Session>"
        for prior, day in zip(previous, weekdays)
    )
    return (
        "<NinjaTrader><TradingHours>"
        "<HolidaysSerializable /><PartialHolidaysSerializable />"
        "<Version>1</Version><Name>CME US Index Futures ETH</Name>"
        f"<Sessions>{sessions}</Sessions>"
        "<TimeZone>Central Standard Time</TimeZone>"
        "</TradingHours></NinjaTrader>"
    ).encode("utf-8")


def _inventory_schedule(civil_date: date, *, has_session: bool) -> dict[str, object]:
    previous = civil_date - timedelta(days=1)
    segment = {
        "begin_application": f"{previous.isoformat()}T17:00:00-05:00",
        "end_application": f"{civil_date.isoformat()}T16:00:00-05:00",
        "begin_pc": (datetime.combine(previous, datetime.min.time(), timezone(timedelta(hours=-5))).replace(hour=17).astimezone(timezone(timedelta(hours=8))).isoformat()),
        "end_pc": (datetime.combine(civil_date, datetime.min.time(), timezone(timedelta(hours=-5))).replace(hour=16).astimezone(timezone(timedelta(hours=8))).isoformat()),
    }
    return {
        "holiday_name": None,
        "partial_session": False,
        "expected_open_segments": [segment] if has_session else [],
        "scheduled_breaks": [],
        "application_session_begin": (
            segment["begin_application"] if has_session else None
        ),
        "application_session_end": segment["end_application"] if has_session else None,
        "pc_log_session_begin": segment["begin_pc"] if has_session else None,
        "pc_log_session_end": segment["end_pc"] if has_session else None,
        "effective_schedule_source": (
            "SessionIterator using Bars.TradingHours and ActualTradingDayExchange"
        ),
    }


def _inventory_quality(trading_date: date = date(2026, 6, 22)) -> dict[str, object]:
    previous = trading_date - timedelta(days=1)
    return {
        "observed_native_five_minute_bar_count": 276,
        "observed_valid_count_from_session_start": 276,
        "first_observed_timestamp": previous.strftime("%Y%m%d") + " 170500",
        "two_hundred_fiftieth_native_timestamp": trading_date.strftime("%Y%m%d") + " 135000",
        "last_observed_session_timestamp": trading_date.strftime("%Y%m%d") + " 160000",
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
    }


def _valid_inventory_scan_document() -> dict[str, object]:
    observations = []
    for offset in range(33):
        civil_date = date(2026, 6, 22) + timedelta(days=offset)
        has_session = civil_date.weekday() < 5
        observations.append({
            "civil_date": civil_date.isoformat(),
            "classification": "SESSION" if has_session else "NO_SESSION",
            "exchange_trading_date": civil_date.isoformat() if has_session else None,
            "schedule_evidence": _inventory_schedule(civil_date, has_session=has_session),
            "quality": _inventory_quality(civil_date) if has_session else None,
        })
    return {
        "schema_version": "1.0",
        "acquisition_id": INVENTORY_ACQUISITION_ID,
        "cohort_id": "mnq-202609-5m-v1",
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
        "transformations": _inventory_scanner_transformations(),
        "completed_at": "2026-09-16T12:00:00+08:00",
    }


def _inventory_timezone() -> dict[str, object]:
    return {
        "id": "Singapore Standard Time",
        "display_name": "(UTC+08:00) Kuala Lumpur, Singapore",
        "standard_name": "Singapore Standard Time",
        "daylight_name": "Singapore Standard Time",
        "base_utc_offset": "+08:00",
        "supports_dst": False,
    }


def _valid_inventory_runtime_document(
    *, scan_sha256: str, scanner_sha256: str, template_sha256: str, config_sha256: str
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "acquisition_id": INVENTORY_ACQUISITION_ID,
        "cohort_id": "mnq-202609-5m-v1",
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
            "scanner_sha256": scanner_sha256,
            "scanner_sha256_recording_authority": "operator/finalizer",
        },
        "bar_series": {
            "type": "Minute",
            "value": 5,
            "native": True,
            "calculate": "OnBarClose",
        },
        "application_timezone": _inventory_timezone(),
        "pc_timezone": _inventory_timezone(),
        "trading_hours": {
            "name": "CME US Index Futures ETH",
            "timezone_id": "Central Standard Time",
        },
        "active_connections": [
            {
                "name": "My NinjaTrader",
                "provider": "Provider31",
                "status": "Connected",
                "price_status": "Connected",
                "instrument_types": ["Future"],
            }
        ],
        "connection_snapshot_phase": (
            "immediately after operator arm and before inventory scan"
        ),
        "lifecycle": {
            "initialized_at": "2026-09-16T11:00:00+08:00",
            "realtime_observed_at": "2026-09-16T11:01:00+08:00",
            "armed_at": "2026-09-16T11:02:00+08:00",
            "completed_at": "2026-09-16T12:00:00+08:00",
        },
        "artifact_hashes": {
            "inventory_scan": {
                "file_name": "inventory_scan.json",
                "sha256": scan_sha256,
            },
            "inventory_runtime_capture": {
                "file_name": "inventory_runtime_capture.json",
                "sha256": None,
                "sha256_recording_authority": "operator/finalizer",
            },
            "trading_hours_template": {
                "file_name": "trading_hours_template.xml",
                "sha256": template_sha256,
            },
            "ninjatrader_config": {
                "file_name": "NinjaTrader.Config.xml",
                "sha256": config_sha256,
            },
        },
    }


def _inventory_evidence_records(
    external_evidence: dict[str, Path],
) -> list[dict[str, object]]:
    return [
        {
            "role": role,
            "path": path.parent.name + "/" + path.name,
            "sha256": _sha256(path),
            "byte_length": len(path.read_bytes()),
        }
        for role, path in external_evidence.items()
    ]


def _inventory_provider_lifecycle() -> dict[str, str]:
    return {
        "adapter_connection_initiated_at": "2026-09-16T10:59:00+08:00",
        "connection_ready_at": "2026-09-16T10:59:30+08:00",
        "pre_request_realtime_at": "2026-09-16T11:00:00+08:00",
        "request_observed_at": "2026-09-16T11:01:30+08:00",
        "post_request_initialized_at": "2026-09-16T11:02:00+08:00",
        "post_request_realtime_at": "2026-09-16T11:02:01+08:00",
        "inventory_scan_armed_at": "2026-09-16T11:03:00+08:00",
        "inventory_scan_completed_at": "2026-09-16T12:00:01+08:00",
    }


def _valid_inventory_acquisition_document(
    *, toolset_checkpoint: str, evidence_records: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "acquisition_id": INVENTORY_ACQUISITION_ID,
        "cohort_id": "mnq-202609-5m-v1",
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
            "requested_start": "2026-06-21T17:00:00",
            "requested_end": "2026-07-24T16:00:00",
            "qualifying_request_count": 1,
        },
        "lifecycle": _inventory_provider_lifecycle(),
        "evidence_files": evidence_records,
        "expected_toolset_checkpoint": toolset_checkpoint,
        "transformations": _inventory_transformations(),
    }


def _valid_inventory_provenance_document(
    *,
    toolset_checkpoint: str,
    component_commit: str,
    pinned_commit: str,
    manifest_sha256: str,
    manifest_aggregate_sha256: str,
    scanner_sha256: str,
    scan_sha256: str,
    runtime_sha256: str,
    acquisition_sha256: str,
    template_sha256: str,
    calendar: VerifiedInventoryCalendar,
    evidence_records: list[dict[str, object]],
) -> dict[str, object]:
    evidence_hashes = {
        item["role"]: item["sha256"] for item in evidence_records
    }
    provenance = {
        "schema_version": "1.0",
        "status": "PROVEN",
        "acquisition_id": INVENTORY_ACQUISITION_ID,
        "cohort_id": "mnq-202609-5m-v1",
        "contract": {
            "contract_label": "MNQ SEP26",
            "full_name": "MNQ SEP26",
            "master_name": "MNQ",
            "expiry_month": 9,
            "expiry_year": 2026,
        },
        "bar_series": {"type": "Minute", "value": 5, "native": True},
        "provider_acquisition": {
            "status": "PROVEN",
            "provider_profile_id": "NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1",
            "runtime_provider_id": "Provider31",
            "trace_adapter": "Tradovate.Adapter",
            "intended_connection_name": "My NinjaTrader",
            "active_connection": {
                "name": "My NinjaTrader",
                "provider": "Provider31",
                "status": "Connected",
                "price_status": "Connected",
                "instrument_types": ["Future"],
            },
            "historical_service": {
                "name": "NinjaTrader HDS",
                "host": "hds-us-nt-007.ninjatrader.com",
                "port": 31655,
                "use_ssl": True,
                "connected_at": "2026-09-16T10:59:00+08:00",
            },
            "configuration_binding": {
                "mode": "EXPLICIT_PREFERENCE",
                "preferred_future_connection": "My NinjaTrader",
                "preferred_realtime_future_connection": "My NinjaTrader",
                "saved_connection_matches": 1,
            },
            "acquisition_id": INVENTORY_ACQUISITION_ID,
            "lifecycle": _inventory_provider_lifecycle(),
            "historical_request": {
                "source_role": "ninjatrader_trace",
                "observed_at": "2026-09-16T11:01:30+08:00",
                "instrument": "MNQ SEP26",
                "requested_start": "2026-06-21T17:00:00",
                "requested_end": "2026-07-24T16:00:00",
                "provider_request_period": "1 Minute",
                "covers_verified_inventory_bounds": True,
            },
            "competing_historical_provider_connections": 0,
            "intended_provider_disconnects": 0,
            "log_timezone_id": "Singapore Standard Time",
            "log_utc_offset": "+08:00",
        },
        "calendar_binding": {
            "status": "VERIFIED",
            "trading_hours_name": "CME US Index Futures ETH",
            "civil_date_start": "2026-06-22",
            "civil_date_end": "2026-07-24",
            "civil_date_count": 33,
            "session_count": len(calendar.sessions),
            "earliest_session_begin": calendar.earliest_session_begin.isoformat(),
            "latest_session_end": calendar.latest_session_end.isoformat(),
            "trading_hours_template_sha256": template_sha256,
            "calendar_binding_sha256": calendar.calendar_binding_sha256,
        },
        "artifact_hashes": {
            "inventory_scan": scan_sha256,
            "inventory_runtime_capture": runtime_sha256,
            "inventory_acquisition_evidence": acquisition_sha256,
            "scanner": scanner_sha256,
            "trading_hours_template": template_sha256,
            "ninjatrader_config": evidence_hashes["ninjatrader_config"],
            "ninjatrader_log": evidence_hashes["ninjatrader_log"],
            "ninjatrader_trace": evidence_hashes["ninjatrader_trace"],
            "toolset_manifest": manifest_sha256,
        },
        "external_evidence": evidence_records,
        "inventory_scan_binding": {
            "path": "inventory_scan.json",
            "schema_version": "1.0",
            "sha256": scan_sha256,
        },
        "transformations": _inventory_transformations(),
        "toolset_binding": {
            "status": "FROZEN_FOR_SOURCE_ACQUISITION",
            "stage": "SOURCE_ACQUISITION",
            "schema_version": "2.0",
            "producing_checkpoint": component_commit,
            "trusted_checkpoint": toolset_checkpoint,
            "pinned_production_hierarchy_commit": pinned_commit,
            "aggregate_payload_sha256": manifest_aggregate_sha256,
        },
        "checkpoint_verification": {
            "status": "VERIFIED",
            "trusted_toolset_checkpoint": toolset_checkpoint,
            "pinned_production_hierarchy_commit": pinned_commit,
        },
    }
    if calendar.date_disagreements:
        provenance["calendar_binding"]["date_disagreements"] = [
            dict(witness) for witness in calendar.date_disagreements
        ]
    return provenance


def _task7_inventory_outputs(
    *,
    toolset_checkpoint: str,
    inventory_scan_sha256: str,
    inventory_provenance_sha256: str,
    calendar: VerifiedInventoryCalendar,
) -> tuple[dict[str, object], dict[str, object]]:
    evidence = ValidatedInventoryEvidence(
        loaded=None,  # type: ignore[arg-type]
        provider_acquisition=MappingProxyType({}),
        qualifying_request=MappingProxyType({}),
        artifact_hashes=MappingProxyType(
            {"inventory_scan": inventory_scan_sha256}
        ),
        external_evidence=(),
        earliest_session_begin=calendar.earliest_session_begin,
        latest_session_end=calendar.latest_session_end,
    )
    built = build_inventory(
        evidence=evidence,
        calendar=calendar,
        inventory_provenance_sha256=inventory_provenance_sha256,
        inventory_scan_sha256=inventory_scan_sha256,
        producing_checkpoint=toolset_checkpoint,
    )
    return dict(built.source_inventory), dict(built.exclusions)


def _build_inventory_checkpoints(
    tmp_path: Path,
    *,
    production_pin: bool = False,
    fake_verifier: bool = False,
    manifest_mutator=None,
    artifact_mutators=None,
    calendar_scan_mutator=None,
    provenance_mutator=None,
    inventory_mutator=None,
    exclusions_mutator=None,
    registry_mutator=None,
) -> InventoryCheckpointFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = tmp_path / "inventory-repo"
    bundle = tmp_path / "inventory-bundle"
    repo.mkdir()
    bundle.mkdir()
    _git(repo, "init")
    _git(repo, "remote", "add", "origin", REPOSITORY_IDENTITY)

    if production_pin:
        pinned_commit = checkpoint_verify.DEFAULT_PINNED_PRODUCTION_COMMIT
        _git(repo, "fetch", str(Path(__file__).resolve().parents[1]), pinned_commit)
        _git(repo, "checkout", "--detach", pinned_commit)
    else:
        (repo / "PINNED").write_bytes(b"production hierarchy\n")
        pinned_commit = _commit(repo, "Pinned production hierarchy")

    _copy_inventory_component_sources(repo, fake_verifier=fake_verifier)
    component_commit = _commit(repo, "Freeze inventory tool components")
    components = [
        {
            "role": role,
            "path": relative,
            "bundle_path": relative,
            "sha256": _sha256_bytes(_git_blob(repo, component_commit, relative)),
            "producing_commit": component_commit,
        }
        for role, relative in EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS.items()
    ]
    manifest: dict[str, object] = {
        "schema_version": "2.0",
        "stage": "SOURCE_ACQUISITION",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": "mnq-202609-5m-v1",
        "producing_checkpoint": component_commit,
        "pinned_production_hierarchy_commit": pinned_commit,
        "runtime": {
            "implementation": "CPython",
            "version": "3.12",
            "dependencies": [{"name": "jsonschema", "version": "4.25.1"}],
        },
        "canonicalization": (
            "JSON_UTF8_SORTED_KEYS_COMPACT_"
            "EXCLUDE_AGGREGATE_PAYLOAD_SHA256"
        ),
        "components": components,
        "deferred_components": [
            "independent_oracle",
            "blind_project_runner",
            "comparator",
            "cohort_aggregator",
        ],
        "aggregate_payload_sha256": "",
    }
    if manifest_mutator is not None:
        manifest_mutator(manifest)
    _write_canonical_json(repo / TOOLSET_MANIFEST_PATH, manifest, aggregate=True)
    toolset_checkpoint = _commit(repo, "Freeze inventory toolset manifest")

    external_root = bundle / "external"
    external_root.mkdir()
    external_evidence = {
        "ninjatrader_config": external_root / "NinjaTrader.Config.xml",
        "ninjatrader_log": external_root / "log.txt",
        "ninjatrader_trace": external_root / "trace.txt",
    }
    external_evidence["ninjatrader_config"].write_bytes(b"<Config />\n")
    external_evidence["ninjatrader_log"].write_bytes(b"provider log\n")
    external_evidence["ninjatrader_trace"].write_bytes(b"request trace\n")
    (repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["trading_hours_template"]).write_bytes(
        _valid_inventory_template()
    )

    artifact_mutators = artifact_mutators or {}
    scan = _valid_inventory_scan_document()
    if calendar_scan_mutator is not None:
        calendar_scan_mutator(scan)
    calendar = mnq_5m_inventory_calendar.verify_inventory_calendar(
        scan,
        _valid_inventory_template(),
    )
    if "inventory_scan" in artifact_mutators:
        artifact_mutators["inventory_scan"](scan)
    scan_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["inventory_scan"]
    _write_canonical_json(scan_path, scan)

    scanner_sha256 = _sha256_bytes(
        _git_blob(
            repo,
            component_commit,
            EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS["inventory_scanner"],
        )
    )
    template_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS[
        "trading_hours_template"
    ]
    runtime = _valid_inventory_runtime_document(
        scan_sha256=_sha256(scan_path),
        scanner_sha256=scanner_sha256,
        template_sha256=_sha256(template_path),
        config_sha256=_sha256(external_evidence["ninjatrader_config"]),
    )
    if "inventory_runtime_capture" in artifact_mutators:
        artifact_mutators["inventory_runtime_capture"](runtime)
    runtime_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS[
        "inventory_runtime_capture"
    ]
    _write_canonical_json(runtime_path, runtime)

    evidence_records = _inventory_evidence_records(external_evidence)
    acquisition = _valid_inventory_acquisition_document(
        toolset_checkpoint=toolset_checkpoint,
        evidence_records=evidence_records,
    )
    if "inventory_acquisition_evidence" in artifact_mutators:
        artifact_mutators["inventory_acquisition_evidence"](acquisition)
    acquisition_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS[
        "inventory_acquisition_evidence"
    ]
    _write_canonical_json(acquisition_path, acquisition)

    internal_hashes = {
        "inventory_runtime_capture": _sha256(runtime_path),
        "inventory_scan": _sha256(scan_path),
        "trading_hours_template": _sha256(template_path),
        "inventory_acquisition_evidence": _sha256(acquisition_path),
    }
    provenance = _valid_inventory_provenance_document(
        toolset_checkpoint=toolset_checkpoint,
        component_commit=component_commit,
        pinned_commit=pinned_commit,
        manifest_sha256=_sha256(repo / TOOLSET_MANIFEST_PATH),
        manifest_aggregate_sha256=manifest["aggregate_payload_sha256"],
        scanner_sha256=scanner_sha256,
        scan_sha256=internal_hashes["inventory_scan"],
        runtime_sha256=internal_hashes["inventory_runtime_capture"],
        acquisition_sha256=internal_hashes["inventory_acquisition_evidence"],
        template_sha256=internal_hashes["trading_hours_template"],
        calendar=calendar,
        evidence_records=evidence_records,
    )
    if "inventory_provenance" in artifact_mutators:
        artifact_mutators["inventory_provenance"](provenance)
    if provenance_mutator is not None:
        provenance_mutator(provenance)
    provenance_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["inventory_provenance"]
    _write_canonical_json(provenance_path, provenance)

    inventory, exclusions = _task7_inventory_outputs(
        toolset_checkpoint=toolset_checkpoint,
        inventory_scan_sha256=internal_hashes["inventory_scan"],
        inventory_provenance_sha256=_sha256(provenance_path),
        calendar=calendar,
    )
    policy = inventory["contract_policy"]
    if inventory_mutator is not None:
        inventory_mutator(inventory)
    inventory_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["source_inventory"]
    _write_canonical_json(inventory_path, inventory, aggregate=True)
    exclusions["source_inventory_sha256"] = _sha256(inventory_path)
    if exclusions_mutator is not None:
        exclusions_mutator(exclusions)
    _write_canonical_json(
        repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["exclusions"],
        exclusions,
        aggregate=True,
    )
    inventory_checkpoint = _commit(repo, "Freeze inventory artifacts")

    eligible_dates = [
        entry["trading_date"] for entry in inventory["entries"] if entry["eligible"]
    ]
    registry: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": "mnq-202609-5m-v1",
        "contract_policy": policy,
        "selection_algorithm": {
            "id": "CHRONOLOGICAL_TEN_STRATA_EARLIEST",
            "version": "1.0",
            "stratum_count": 10,
        },
        "selection_count": 10,
        "source_inventory": {
            "path": "source_inventory.json",
            "bundle_path": "source_inventory.json",
            "schema_version": "2.0",
            "sha256": _sha256(inventory_path),
            "producing_checkpoint": toolset_checkpoint,
        },
        "exclusion_ledger": {
            "path": "exclusions.json",
            "bundle_path": "exclusions.json",
            "schema_version": "2.0",
            "sha256": _sha256(
                repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["exclusions"]
            ),
            "producing_checkpoint": toolset_checkpoint,
        },
        "trusted_inventory_checkpoint": inventory_checkpoint,
        "producing_checkpoint": inventory_checkpoint,
        "selection_influence": {
            "hierarchy_output_used": False,
            "oracle_output_used": False,
            "project_output_used": False,
        },
        "selections": [
            {
                "case_id": (
                    f"mnq-202609-5m-td{eligible_dates[(number - 1) * len(eligible_dates) // 10]}"
                    f"-w{number:02d}"
                ),
                "trading_date": eligible_dates[(number - 1) * len(eligible_dates) // 10],
                "stratum_number": number,
                "stratum_start_index": (number - 1) * len(eligible_dates) // 10,
                "stratum_end_index": number * len(eligible_dates) // 10 - 1,
                "selected_eligible_index": (number - 1) * len(eligible_dates) // 10,
                "window_policy": "FIRST_250_NATIVE_5M_SESSION_BARS",
            }
            for number in range(1, 11)
        ],
        "aggregate_payload_sha256": "",
    }
    if registry_mutator is not None:
        registry_mutator(registry)
    _write_canonical_json(
        repo / V2_SELECTION_REGISTRY_PATH,
        registry,
        aggregate=True,
    )
    selection_checkpoint = _commit(repo, "Freeze inventory selection")

    fixture = InventoryCheckpointFixture(
        repo=repo,
        bundle=bundle,
        pinned_commit=pinned_commit,
        component_commit=component_commit,
        toolset_checkpoint=toolset_checkpoint,
        inventory_checkpoint=inventory_checkpoint,
        selection_checkpoint=selection_checkpoint,
        manifest=bundle / "toolset_manifest.json",
        inventory_artifacts={
            role: bundle / relative
            for role, relative in INVENTORY_ARTIFACT_REPOSITORY_PATHS.items()
        },
        registry=bundle / V2_SELECTION_REGISTRY_PATH,
        external_evidence=external_evidence,
    )
    _refresh_inventory_bundle(fixture)
    return fixture


def _verify_inventory(fixture: InventoryCheckpointFixture, **overrides):
    arguments = {
        "repository_path": fixture.repo,
        "bundle_root": fixture.bundle,
        "toolset_manifest_path": fixture.manifest,
        "inventory_artifact_paths": fixture.inventory_artifacts,
        "trusted_toolset_checkpoint": fixture.toolset_checkpoint,
        "trusted_inventory_checkpoint": fixture.inventory_checkpoint,
        "expected_repository_identity": REPOSITORY_IDENTITY,
        "expected_pinned_production_commit": fixture.pinned_commit,
    }
    arguments.update(overrides)
    return checkpoint_verify._verify_inventory_checkpoint_with_test_pinned_commit(
        **arguments
    )


def _verify_selection(fixture: InventoryCheckpointFixture, **overrides):
    arguments = {
        "repository_path": fixture.repo,
        "bundle_root": fixture.bundle,
        "toolset_manifest_path": fixture.manifest,
        "inventory_artifact_paths": fixture.inventory_artifacts,
        "selection_registry_path": fixture.registry,
        "trusted_toolset_checkpoint": fixture.toolset_checkpoint,
        "trusted_inventory_checkpoint": fixture.inventory_checkpoint,
        "trusted_selection_checkpoint": fixture.selection_checkpoint,
        "expected_repository_identity": REPOSITORY_IDENTITY,
        "expected_pinned_production_commit": fixture.pinned_commit,
    }
    arguments.update(overrides)
    return checkpoint_verify._verify_selection_checkpoint_with_test_pinned_commit(
        **arguments
    )


def _verify(fixture: CheckpointFixture, **overrides):
    arguments = {
        "repository_path": fixture.repo,
        "bundle_root": fixture.bundle,
        "toolset_manifest_path": fixture.manifest,
        "selection_registry_path": fixture.registry,
        "trusted_toolset_checkpoint": fixture.toolset_checkpoint,
        "trusted_selection_checkpoint": fixture.selection_checkpoint,
        "expected_repository_identity": REPOSITORY_IDENTITY,
        "expected_pinned_production_commit": fixture.pinned_commit,
    }
    arguments.update(overrides)
    return _verify_checkpoints_with_test_pinned_commit(**arguments)


def test_verifies_committed_bytes_and_toolset_to_selection_ancestry(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)

    result = _verify(fixture)

    assert result["schema_version"] == "1.0"
    assert result["status"] == "VERIFIED"
    assert result["repository"]["identity"] == REPOSITORY_IDENTITY
    assert result["trusted_toolset_checkpoint"] == fixture.toolset_checkpoint
    assert result["trusted_selection_checkpoint"] == fixture.selection_checkpoint
    assert result["pinned_production_hierarchy_commit"] == fixture.pinned_commit
    assert result["ancestry"] == [
        {
            "ancestor": fixture.pinned_commit,
            "descendant": fixture.toolset_checkpoint,
            "verified": True,
        },
        {
            "ancestor": fixture.toolset_checkpoint,
            "descendant": fixture.selection_checkpoint,
            "verified": True,
        },
    ]
    assert {artifact["repository_path"] for artifact in result["artifacts"]} >= {
        TOOLSET_MANIFEST_PATH,
        SELECTION_REGISTRY_PATH,
        INVENTORY_PATH,
        EXCLUSIONS_PATH,
    }
    assert result["attestation_sha256"] == _attestation_hash(result)
    assert _verify(fixture) == result


@pytest.mark.parametrize("checkpoint_name", ["toolset", "selection"])
def test_rejects_nonexistent_checkpoint(
    tmp_path: Path, checkpoint_name: str
) -> None:
    fixture = _build_checkpoints(tmp_path)
    overrides = {f"trusted_{checkpoint_name}_checkpoint": "f" * 40}

    with pytest.raises(CheckpointVerificationError, match="does not exist as a commit"):
        _verify(fixture, **overrides)


def test_rejects_mutable_ref_instead_of_full_checkpoint_sha(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)

    with pytest.raises(
        CheckpointVerificationError,
        match="full immutable Git object ID",
    ):
        _verify(fixture, trusted_toolset_checkpoint="HEAD")


def test_ignores_git_environment_repository_redirection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_checkpoints(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    _git(foreign, "init")
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))

    result = _verify(fixture)

    assert result["trusted_selection_checkpoint"] == fixture.selection_checkpoint


def test_rejects_unrelated_checkpoint(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)
    tree = _git(
        fixture.repo, "rev-parse", f"{fixture.pinned_commit}^{{tree}}"
    ).stdout.strip()
    unrelated = _git(
        fixture.repo, "commit-tree", tree, "-m", "Unrelated root"
    ).stdout.strip()

    with pytest.raises(CheckpointVerificationError, match="not an ancestor"):
        _verify(fixture, trusted_selection_checkpoint=unrelated)


def test_rejects_unrelated_checkpoint_hidden_by_local_replace_ref(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)
    tree = _git(
        fixture.repo, "rev-parse", f"{fixture.pinned_commit}^{{tree}}"
    ).stdout.strip()
    unrelated = _git(
        fixture.repo, "commit-tree", tree, "-m", "Unrelated root"
    ).stdout.strip()
    _git(fixture.repo, "replace", unrelated, fixture.selection_checkpoint)

    with pytest.raises(CheckpointVerificationError, match="not an ancestor"):
        _verify(fixture, trusted_selection_checkpoint=unrelated)


def test_rejects_unrelated_checkpoint_hidden_by_local_graft(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)
    tree = _git(
        fixture.repo, "rev-parse", f"{fixture.selection_checkpoint}^{{tree}}"
    ).stdout.strip()
    unrelated = _git(
        fixture.repo, "commit-tree", tree, "-m", "Unrelated selection root"
    ).stdout.strip()
    grafts = fixture.repo / ".git" / "info" / "grafts"
    grafts.parent.mkdir(parents=True, exist_ok=True)
    grafts.write_text(
        f"{unrelated} {fixture.inventory_checkpoint}\n", encoding="ascii"
    )

    with pytest.raises(CheckpointVerificationError, match="graft"):
        _verify(fixture, trusted_selection_checkpoint=unrelated)


def test_raw_commit_ancestry_ignores_graft_created_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_checkpoints(tmp_path)
    tree = _git(
        fixture.repo, "rev-parse", f"{fixture.selection_checkpoint}^{{tree}}"
    ).stdout.strip()
    unrelated = _git(
        fixture.repo, "commit-tree", tree, "-m", "Unrelated selection root"
    ).stdout.strip()
    original_preflight = checkpoint_verify._assert_no_grafts

    def create_graft_after_preflight(repository: Path) -> None:
        original_preflight(repository)
        grafts = fixture.repo / ".git" / "info" / "grafts"
        grafts.parent.mkdir(parents=True, exist_ok=True)
        grafts.write_text(
            f"{unrelated} {fixture.inventory_checkpoint}\n", encoding="ascii"
        )

    monkeypatch.setattr(
        checkpoint_verify, "_assert_no_grafts", create_graft_after_preflight
    )

    with pytest.raises(CheckpointVerificationError, match="not an ancestor"):
        _verify(fixture, trusted_selection_checkpoint=unrelated)


def test_rejects_reversed_stage_ancestry(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)

    with pytest.raises(CheckpointVerificationError, match="not an ancestor"):
        _verify(
            fixture,
            trusted_toolset_checkpoint=fixture.selection_checkpoint,
            trusted_selection_checkpoint=fixture.toolset_checkpoint,
        )


def test_optional_acquisition_checkpoint_extends_stage_ancestry(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)
    (fixture.repo / "SOURCE_CHECKPOINT").write_text(
        "acquired source\n", encoding="utf-8"
    )
    acquisition_checkpoint = _commit(fixture.repo, "Freeze acquired source")

    result = _verify(
        fixture, trusted_acquisition_checkpoint=acquisition_checkpoint
    )

    assert result["trusted_acquisition_checkpoint"] == acquisition_checkpoint
    assert result["ancestry"][-1] == {
        "ancestor": fixture.selection_checkpoint,
        "descendant": acquisition_checkpoint,
        "verified": True,
    }


def test_rejects_optional_acquisition_checkpoint_equal_to_selection(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)

    with pytest.raises(CheckpointVerificationError, match="strictly precede"):
        _verify(
            fixture,
            trusted_acquisition_checkpoint=fixture.selection_checkpoint,
        )


def test_rejects_reversed_optional_acquisition_checkpoint(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)

    with pytest.raises(CheckpointVerificationError, match="not an ancestor"):
        _verify(
            fixture,
            trusted_acquisition_checkpoint=fixture.toolset_checkpoint,
        )


def test_reads_committed_bytes_when_working_tree_is_dirty(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)
    (fixture.repo / COMPONENT_PATHS["protocol_spec"]).write_text(
        "mutated working tree\n", encoding="utf-8"
    )

    result = _verify(fixture)

    protocol = next(
        artifact
        for artifact in result["artifacts"]
        if artifact["role"] == "protocol_spec"
    )
    assert protocol["sha256"] == _sha256(fixture.bundle / "protocol_spec.artifact")


def test_rejects_later_toolset_checkpoint_that_only_preserves_manifest(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)

    with pytest.raises(CheckpointVerificationError, match="direct parent"):
        _verify(fixture, trusted_toolset_checkpoint=fixture.inventory_checkpoint)


def test_rejects_later_selection_checkpoint_that_only_preserves_registry(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)
    (fixture.repo / "UNRELATED_LATER_FILE").write_text("later\n", encoding="utf-8")
    later_checkpoint = _commit(fixture.repo, "Later unrelated change")

    with pytest.raises(CheckpointVerificationError, match="direct parent"):
        _verify(fixture, trusted_selection_checkpoint=later_checkpoint)


def test_manifest_and_registry_bundle_bytes_are_snapshotted_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_checkpoints(tmp_path)
    original_read_bytes = Path.read_bytes
    reads = {fixture.manifest.resolve(): 0, fixture.registry.resolve(): 0}

    def counted_read_bytes(path: Path) -> bytes:
        resolved = path.resolve()
        if resolved in reads:
            reads[resolved] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)

    _verify(fixture)

    assert reads == {fixture.manifest.resolve(): 1, fixture.registry.resolve(): 1}


def test_rejects_bundle_file_that_differs_from_committed_bytes(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)
    (fixture.bundle / "source_inventory.json").write_text(
        "{\"mutated\": true}\n", encoding="utf-8"
    )

    with pytest.raises(CheckpointVerificationError, match="committed bytes"):
        _verify(fixture)


def test_rejects_wrong_manifest_component_producing_commit(tmp_path: Path) -> None:
    fixture = _build_checkpoints(
        tmp_path,
        manifest_mutator=lambda value: value["components"][0].__setitem__(
            "producing_commit", "f" * 40
        ),
    )

    with pytest.raises(CheckpointVerificationError, match="does not exist as a commit"):
        _verify(fixture)


def test_rejects_incomplete_toolset_manifest(tmp_path: Path) -> None:
    fixture = _build_checkpoints(
        tmp_path,
        manifest_mutator=lambda value: value["components"].pop(),
    )

    with pytest.raises(
        CheckpointVerificationError,
        match="exact required component roles",
    ):
        _verify(fixture)


def test_rejects_wrong_pinned_hierarchy_commit(tmp_path: Path) -> None:
    fixture = _build_checkpoints(
        tmp_path,
        manifest_mutator=lambda value: value.__setitem__(
            "pinned_production_hierarchy_commit", "f" * 40
        ),
    )

    with pytest.raises(CheckpointVerificationError, match="pinned production"):
        _verify(fixture)


def test_rejects_wrong_registry_inventory_checkpoint(tmp_path: Path) -> None:
    fixture = _build_checkpoints(
        tmp_path,
        registry_mutator=lambda value: value["source_inventory"].__setitem__(
            "producing_checkpoint", "f" * 40
        ),
    )

    with pytest.raises(
        CheckpointVerificationError,
        match="source_inventory.*producing checkpoint",
    ):
        _verify(fixture)


def test_rejects_frozen_verifier_that_differs_from_executing_verifier(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path, fake_verifier=True)

    with pytest.raises(CheckpointVerificationError, match="executing verifier"):
        _verify(fixture)


def test_rejects_remote_branch_mismatch_when_enabled(tmp_path: Path) -> None:
    fixture = _build_checkpoints(tmp_path)
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _git(fixture.repo, "remote", "set-url", "origin", str(remote))
    _git(
        fixture.repo,
        "push",
        "origin",
        f"{fixture.toolset_checkpoint}:refs/heads/validation/mnq-5m-multiwindow",
    )

    with pytest.raises(CheckpointVerificationError, match="remote branch mismatch"):
        _verify(
            fixture,
            expected_repository_identity=str(remote),
            remote_name="origin",
            remote_branch="validation/mnq-5m-multiwindow",
        )


def test_rejects_remote_name_that_can_be_parsed_as_git_option(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)

    with pytest.raises(CheckpointVerificationError, match="remote name"):
        _verify(
            fixture,
            remote_name="--upload-pack=malicious-command",
            remote_branch="validation/mnq-5m-multiwindow",
        )


def test_reports_remote_verification_unavailable_without_claiming_pass(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)
    _git(fixture.repo, "remote", "set-url", "origin", str(tmp_path / "missing.git"))

    result = _verify(
        fixture,
        expected_repository_identity=str(tmp_path / "missing.git"),
        remote_name="origin",
        remote_branch="validation/mnq-5m-multiwindow",
    )

    assert result["remote_publication"]["status"] == "UNAVAILABLE"


def test_fixture_does_not_require_network_or_mutable_branch_identity(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)
    _git(fixture.repo, "checkout", "-b", "renamed-local-branch")

    result = _verify(fixture)

    assert result["status"] == "VERIFIED"


def test_cli_does_not_allow_pinned_production_checkpoint_override(
    tmp_path: Path,
) -> None:
    fixture = _build_checkpoints(tmp_path)

    with pytest.raises(SystemExit) as error:
        verifier_main(
            [
                "--repository",
                str(fixture.repo),
                "--bundle-root",
                str(fixture.bundle),
                "--toolset-manifest",
                str(fixture.manifest),
                "--selection-registry",
                str(fixture.registry),
                "--trusted-toolset-checkpoint",
                fixture.toolset_checkpoint,
                "--trusted-selection-checkpoint",
                fixture.selection_checkpoint,
                "--pinned-production-commit",
                fixture.pinned_commit,
                "--output",
                str(tmp_path / "attestation.json"),
            ]
        )

    assert error.value.code == 2


def test_attestation_schema_fixes_the_production_hierarchy_checkpoint() -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "validation"
        / "mnq_5m_multiwindow"
        / "schemas"
        / "checkpoint_attestation.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["properties"]["pinned_production_hierarchy_commit"] == {
        "const": "04a73e1401d44688660b211d9db6918113482856"
    }


def test_legacy_and_inventory_toolset_mappings_are_exact_and_independent() -> None:
    assert checkpoint_verify.REQUIRED_TOOLSET_COMPONENT_PATHS == (
        EXPECTED_LEGACY_TOOLSET_COMPONENT_PATHS
    )
    assert mnq_5m_acquisition.TOOLSET_COMPONENT_PATHS == (
        EXPECTED_LEGACY_TOOLSET_COMPONENT_PATHS
    )
    assert checkpoint_verify.REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS == (
        EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS
    )
    assert len(checkpoint_verify.REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS) == 23
    assert checkpoint_verify.VERIFIER_VERSION == "2.0"

    versioned_roles = {
        "provenance_schema": "provenance_v1_3.schema.json",
        "checkpoint_attestation_schema": "checkpoint_attestation_v2.schema.json",
        "selection_registry_schema": "selection_registry_v2.schema.json",
        "toolset_manifest_schema": "toolset_manifest_v2.schema.json",
        "source_inventory_schema": "source_inventory_v2.schema.json",
        "exclusion_ledger_schema": "exclusions_v2.schema.json",
    }
    for role, filename in versioned_roles.items():
        assert checkpoint_verify.REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS[
            role
        ].endswith(filename)


def test_public_inventory_checkpoint_interfaces_match_the_plan() -> None:
    assert list(inspect.signature(checkpoint_verify.verify_inventory_checkpoint).parameters) == [
        "repository_path",
        "bundle_root",
        "toolset_manifest_path",
        "inventory_artifact_paths",
        "trusted_toolset_checkpoint",
        "trusted_inventory_checkpoint",
        "expected_repository_identity",
        "remote_name",
        "remote_branch",
    ]
    assert list(inspect.signature(checkpoint_verify.verify_selection_checkpoint).parameters) == [
        "repository_path",
        "bundle_root",
        "toolset_manifest_path",
        "inventory_artifact_paths",
        "selection_registry_path",
        "trusted_toolset_checkpoint",
        "trusted_inventory_checkpoint",
        "trusted_selection_checkpoint",
        "expected_repository_identity",
        "remote_name",
        "remote_branch",
    ]


def test_inventory_v2_mapping_mutation_cannot_change_legacy_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_verifier = checkpoint_verify.REQUIRED_TOOLSET_COMPONENT_PATHS
    original_acquisition = mnq_5m_acquisition.TOOLSET_COMPONENT_PATHS
    monkeypatch.setitem(
        checkpoint_verify.REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS,
        "inventory_builder",
        "changed-only-for-this-test.py",
    )
    monkeypatch.setitem(
        checkpoint_verify.REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS,
        "future_inventory_only_role",
        "future.py",
    )

    assert checkpoint_verify.REQUIRED_TOOLSET_COMPONENT_PATHS is original_verifier
    assert mnq_5m_acquisition.TOOLSET_COMPONENT_PATHS is original_acquisition
    assert checkpoint_verify.REQUIRED_TOOLSET_COMPONENT_PATHS == (
        EXPECTED_LEGACY_TOOLSET_COMPONENT_PATHS
    )
    assert mnq_5m_acquisition.TOOLSET_COMPONENT_PATHS == (
        EXPECTED_LEGACY_TOOLSET_COMPONENT_PATHS
    )
    assert _verify(_build_checkpoints(tmp_path))["schema_version"] == "1.0"


def test_verifies_first_class_inventory_checkpoint_from_immutable_bytes(
    tmp_path: Path,
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)

    result = _verify_inventory(fixture)

    assert result["schema_version"] == "2.0"
    assert result["stage"] == "INVENTORY"
    assert result["status"] == "VERIFIED"
    assert result["trusted_toolset_checkpoint"] == fixture.toolset_checkpoint
    assert result["trusted_inventory_checkpoint"] == fixture.inventory_checkpoint
    assert "trusted_selection_checkpoint" not in result
    assert result["ancestry"] == [
        {
            "ancestor": fixture.pinned_commit,
            "descendant": fixture.toolset_checkpoint,
            "verified": True,
        },
        {
            "ancestor": fixture.toolset_checkpoint,
            "descendant": fixture.inventory_checkpoint,
            "verified": True,
        },
    ]
    assert {item["stage"] for item in result["artifacts"]} == {
        "toolset",
        "inventory",
    }
    assert {item["role"] for item in result["artifacts"]} >= set(
        INVENTORY_ARTIFACT_REPOSITORY_PATHS
    )
    for role, expected_path in INVENTORY_ARTIFACT_REPOSITORY_PATHS.items():
        artifact = next(item for item in result["artifacts"] if item["role"] == role)
        assert artifact["repository_path"] == expected_path
        assert artifact["checkpoint"] == fixture.inventory_checkpoint
        assert artifact["producing_checkpoint"] == fixture.toolset_checkpoint
        assert artifact["sha256"] == artifact["bundle_sha256"]
    assert result["verifier"]["version"] == "2.0"
    assert result["verifier"]["frozen_sha256"] == result["verifier"][
        "executing_sha256"
    ]
    assert result["attestation_sha256"] == _attestation_hash(result)


def _verify_public_inventory(fixture: InventoryCheckpointFixture) -> dict[str, object]:
    return checkpoint_verify.verify_inventory_checkpoint(
        repository_path=fixture.repo,
        bundle_root=fixture.bundle,
        toolset_manifest_path=fixture.manifest,
        inventory_artifact_paths=fixture.inventory_artifacts,
        trusted_toolset_checkpoint=fixture.toolset_checkpoint,
        trusted_inventory_checkpoint=fixture.inventory_checkpoint,
        expected_repository_identity=REPOSITORY_IDENTITY,
    )


def test_public_inventory_rejects_contradictory_runtime_scan_hash(
    tmp_path: Path,
) -> None:
    def contradict_scan_hash(runtime: dict[str, object]) -> None:
        runtime["artifact_hashes"]["inventory_scan"]["sha256"] = "0" * 64

    fixture = _build_inventory_checkpoints(
        tmp_path,
        production_pin=True,
        artifact_mutators={"inventory_runtime_capture": contradict_scan_hash},
    )

    with pytest.raises(CheckpointVerificationError, match="runtime.*inventory_scan"):
        _verify_public_inventory(fixture)


@pytest.mark.parametrize("role", ["trading_hours_template", "ninjatrader_config", "scanner"])
def test_public_inventory_rejects_adjacent_runtime_hash_contradictions(
    tmp_path: Path, role: str
) -> None:
    def contradict_runtime_hash(runtime: dict[str, object]) -> None:
        if role == "scanner":
            runtime["scanner_identity"]["scanner_sha256"] = "0" * 64
        else:
            runtime["artifact_hashes"][role]["sha256"] = "0" * 64

    fixture = _build_inventory_checkpoints(
        tmp_path,
        production_pin=True,
        artifact_mutators={"inventory_runtime_capture": contradict_runtime_hash},
    )

    with pytest.raises(CheckpointVerificationError, match=f"runtime.*{role}"):
        _verify_public_inventory(fixture)


@pytest.mark.parametrize("deferred_scanner_hash", [False, True])
def test_public_inventory_verifies_matching_runtime_hashes(
    tmp_path: Path, deferred_scanner_hash: bool
) -> None:
    def defer_scanner_hash(runtime: dict[str, object]) -> None:
        if deferred_scanner_hash:
            runtime["scanner_identity"]["scanner_sha256"] = None

    fixture = _build_inventory_checkpoints(
        tmp_path,
        production_pin=True,
        artifact_mutators={"inventory_runtime_capture": defer_scanner_hash},
    )

    assert _verify_public_inventory(fixture)["status"] == "VERIFIED"


def test_noncandidate_calendar_disagreement_is_bound_without_a_phantom_entry(
    tmp_path: Path,
) -> None:
    def add_scanner_only_session(scan: dict[str, object]) -> None:
        saturday = next(
            observation for observation in scan["observations"]
            if observation["civil_date"] == "2026-06-27"
        )
        saturday["classification"] = "SESSION"
        saturday["exchange_trading_date"] = "2026-06-27"
        saturday["schedule_evidence"] = _inventory_schedule(
            date(2026, 6, 27), has_session=True
        )
        saturday["quality"] = _inventory_quality(date(2026, 6, 27))

    fixture = _build_inventory_checkpoints(
        tmp_path,
        calendar_scan_mutator=add_scanner_only_session,
    )
    result = _verify_inventory(fixture)
    provenance = json.loads(
        fixture.inventory_artifacts["inventory_provenance"].read_bytes()
    )
    inventory = json.loads(fixture.inventory_artifacts["source_inventory"].read_bytes())

    assert result["status"] == "VERIFIED"
    assert inventory["candidate_count"] == 25
    assert "2026-06-27" not in {entry["trading_date"] for entry in inventory["entries"]}
    assert provenance["calendar_binding"]["date_disagreements"] == [{
        "civil_date": "2026-06-27",
        "reason": "TRADING_HOURS_INCONSISTENCY",
        "scanner_classification": "SESSION",
        "template_classification": "NO_SESSION",
    }]


def test_closed_scan_on_actual_date_verifies_as_excluded_unknown_candidate(
    tmp_path: Path,
) -> None:
    def close_actual_session(scan: dict[str, object]) -> None:
        friday = next(
            observation for observation in scan["observations"]
            if observation["civil_date"] == "2026-07-03"
        )
        friday["classification"] = "NO_SESSION"
        friday["exchange_trading_date"] = None
        friday["schedule_evidence"] = _inventory_schedule(
            date(2026, 7, 3), has_session=False
        )
        friday["quality"] = None

    fixture = _build_inventory_checkpoints(
        tmp_path,
        calendar_scan_mutator=close_actual_session,
    )
    result = _verify_inventory(fixture)
    inventory = json.loads(fixture.inventory_artifacts["source_inventory"].read_bytes())
    entry = next(
        item for item in inventory["entries"]
        if item["trading_date"] == "2026-07-03"
    )

    assert result["status"] == "VERIFIED"
    assert inventory["candidate_count"] == 25
    assert inventory["eligible_count"] == 24
    assert entry["eligible"] is False
    assert entry["exclusion_reasons"] == ["TRADING_HOURS_INCONSISTENCY"]
    assert entry["observed_native_bar_count"] is None


def test_inventory_checkpoint_rejects_contradictory_bound_bar_count(tmp_path: Path) -> None:
    def contradict_inventory(inventory: dict[str, object]) -> None:
        inventory["entries"][0]["observed_native_bar_count"] = 277

    fixture = _build_inventory_checkpoints(
        tmp_path,
        inventory_mutator=contradict_inventory,
    )

    with pytest.raises(CheckpointVerificationError, match="candidate"):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    "role,module",
    [
        ("inventory_builder", mnq_5m_inventory),
        ("inventory_calendar_verifier", mnq_5m_inventory_calendar),
    ],
)
def test_candidate_replay_rejects_noncanonical_executing_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    module: object,
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    alternative = tmp_path / f"modified-{role}.py"
    alternative.write_bytes(Path(module.__file__).read_bytes() + b"\n# modified\n")
    monkeypatch.setattr(module, "__file__", str(alternative))

    with pytest.raises(CheckpointVerificationError, match=f"executing {role}"):
        _verify_inventory(fixture)


def _make_first_inventory_entry_ineligible(
    inventory: dict[str, object], reasons: list[str]
) -> None:
    first = inventory["entries"][0]
    first["eligible"] = False
    first["exclusion_reasons"] = reasons
    inventory["eligible_count"] = inventory["eligible_count"] - 1
    inventory["cohort_outcome"] = "COHORT_INCOMPLETE"


def _set_incomplete_exclusions(
    exclusions: dict[str, object], entries: list[dict[str, object]]
) -> None:
    exclusions["cohort_outcome"] = "COHORT_INCOMPLETE"
    exclusions["entries"] = entries


def test_inventory_checkpoint_rejects_missing_exclusion_row(tmp_path: Path) -> None:
    fixture = _build_inventory_checkpoints(
        tmp_path,
        inventory_mutator=lambda value: _make_first_inventory_entry_ineligible(
            value, ["SOURCE_CORRUPTION"]
        ),
        exclusions_mutator=lambda value: _set_incomplete_exclusions(value, []),
    )

    with pytest.raises(CheckpointVerificationError, match="reconcile"):
        _verify_inventory(fixture)


def test_inventory_checkpoint_rejects_extra_exclusion_row(tmp_path: Path) -> None:
    fixture = _build_inventory_checkpoints(
        tmp_path,
        exclusions_mutator=lambda value: value.__setitem__(
            "entries",
            [{"trading_date": "2026-06-22", "reasons": ["SOURCE_CORRUPTION"]}],
        ),
    )

    with pytest.raises(CheckpointVerificationError, match="reconcile"):
        _verify_inventory(fixture)


def test_inventory_checkpoint_rejects_changed_exclusion_row(tmp_path: Path) -> None:
    fixture = _build_inventory_checkpoints(
        tmp_path,
        inventory_mutator=lambda value: _make_first_inventory_entry_ineligible(
            value, ["SOURCE_CORRUPTION"]
        ),
        exclusions_mutator=lambda value: _set_incomplete_exclusions(
            value,
            [
                {
                    "trading_date": "2026-06-22",
                    "reasons": ["UNEXPECTED_MISSING_BARS"],
                }
            ],
        ),
    )

    with pytest.raises(CheckpointVerificationError, match="reconcile"):
        _verify_inventory(fixture)


def test_inventory_checkpoint_rejects_exclusion_reason_order_mutation(
    tmp_path: Path,
) -> None:
    reasons = ["SOURCE_CORRUPTION", "FEWER_THAN_250_NATIVE_BARS"]
    fixture = _build_inventory_checkpoints(
        tmp_path,
        inventory_mutator=lambda value: _make_first_inventory_entry_ineligible(
            value, reasons
        ),
        exclusions_mutator=lambda value: _set_incomplete_exclusions(
            value,
            [{"trading_date": "2026-06-22", "reasons": reasons}],
        ),
    )

    with pytest.raises(CheckpointVerificationError, match="reason order"):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    "outcome",
    ["READY_FOR_SELECTION", "COHORT_INCOMPLETE"],
    ids=["false-ready", "false-incomplete"],
)
def test_inventory_checkpoint_rejects_outcome_threshold_mutation(
    tmp_path: Path, outcome: str
) -> None:
    if outcome == "READY_FOR_SELECTION":
        excluded_dates: list[str] = []

        def below_threshold(inventory: dict[str, object]) -> None:
            entries = inventory["entries"]
            for entry in entries[:-9]:
                entry["eligible"] = False
                entry["exclusion_reasons"] = ["SOURCE_CORRUPTION"]
                excluded_dates.append(entry["trading_date"])
            inventory["eligible_count"] = 9
            inventory["cohort_outcome"] = outcome

        def exclude_same_dates(exclusions: dict[str, object]) -> None:
            exclusions["entries"] = [
                {"trading_date": trading_date, "reasons": ["SOURCE_CORRUPTION"]}
                for trading_date in excluded_dates
            ]

        fixture = _build_inventory_checkpoints(
            tmp_path,
            inventory_mutator=below_threshold,
            exclusions_mutator=exclude_same_dates,
        )
    else:
        fixture = _build_inventory_checkpoints(
            tmp_path,
            inventory_mutator=lambda value: value.__setitem__(
                "cohort_outcome", outcome
            ),
            exclusions_mutator=lambda value: value.__setitem__(
                "cohort_outcome", outcome
            ),
        )

    with pytest.raises(CheckpointVerificationError, match="outcome"):
        _verify_inventory(fixture)


def _bind_executing_inventory_modules_to_fixture(
    fixture: InventoryCheckpointFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    for relative in EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS.values():
        (fixture.repo / relative).write_bytes(
            _git_blob(fixture.repo, fixture.toolset_checkpoint, relative)
        )
    (fixture.repo / TOOLSET_MANIFEST_PATH).write_bytes(
        _git_blob(fixture.repo, fixture.toolset_checkpoint, TOOLSET_MANIFEST_PATH)
    )
    modules = {
        "inventory_builder": mnq_5m_inventory,
        "inventory_calendar_verifier": mnq_5m_inventory_calendar,
        "inventory_evidence_finalizer": mnq_5m_inventory_evidence,
        "inventory_common": mnq_5m_inventory_common,
        "checkpoint_verifier": checkpoint_verify,
    }
    for role, module in modules.items():
        monkeypatch.setattr(
            module,
            "__file__",
            str(fixture.repo / EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS[role]),
        )


def _verify_inventory_toolset_only(fixture: InventoryCheckpointFixture) -> dict[str, object]:
    return checkpoint_verify.verify_inventory_toolset_checkpoint(
        repository_path=fixture.repo,
        bundle_root=fixture.repo,
        toolset_manifest_path=TOOLSET_MANIFEST_PATH,
        trusted_toolset_checkpoint=fixture.toolset_checkpoint,
        expected_repository_identity=REPOSITORY_IDENTITY,
        expected_pinned_production_commit=fixture.pinned_commit,
    )


def test_toolset_only_gate_verifies_exact_frozen_23_role_policy_toolset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    _bind_executing_inventory_modules_to_fixture(fixture, monkeypatch)

    result = _verify_inventory_toolset_only(fixture)

    assert result["status"] == "VERIFIED"
    assert result["producing_checkpoint"] == fixture.component_commit
    assert result["trusted_toolset_checkpoint"] == fixture.toolset_checkpoint
    assert result["component_count"] == 23


@pytest.mark.parametrize(
    "role",
    [
        "inventory_builder",
        "inventory_calendar_verifier",
        "inventory_evidence_finalizer",
        "inventory_common",
        "source_inventory_schema",
    ],
)
def test_toolset_only_gate_rejects_executing_policy_or_schema_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    _bind_executing_inventory_modules_to_fixture(fixture, monkeypatch)
    path = fixture.repo / EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS[role]
    path.write_bytes(path.read_bytes() + b"\nreview mutation\n")

    with pytest.raises(CheckpointVerificationError, match=role):
        _verify_inventory_toolset_only(fixture)


def test_verifies_selection_as_direct_child_of_inventory_checkpoint(
    tmp_path: Path,
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)

    result = _verify_selection(fixture)

    assert result["schema_version"] == "2.0"
    assert result["stage"] == "SELECTION"
    assert result["trusted_inventory_checkpoint"] == fixture.inventory_checkpoint
    assert result["trusted_selection_checkpoint"] == fixture.selection_checkpoint
    assert result["ancestry"][-1] == {
        "ancestor": fixture.inventory_checkpoint,
        "descendant": fixture.selection_checkpoint,
        "verified": True,
    }
    assert {item["stage"] for item in result["artifacts"]} == {
        "toolset",
        "inventory",
        "selection",
    }
    registry = next(
        item for item in result["artifacts"] if item["role"] == "selection_registry"
    )
    assert registry["repository_path"] == V2_SELECTION_REGISTRY_PATH
    assert registry["checkpoint"] == fixture.selection_checkpoint
    assert registry["producing_checkpoint"] == fixture.inventory_checkpoint
    assert result["attestation_sha256"] == _attestation_hash(result)


def test_real_task7_outputs_flow_through_component_toolset_inventory_selection_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    inventory_attestation = _verify_inventory(fixture)
    schema = json.loads(
        selection_module.CHECKPOINT_ATTESTATION_SCHEMA.read_bytes()
    )
    pending: list[object] = [schema]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            properties = current.get("properties")
            if isinstance(properties, dict):
                pinned = properties.get("pinned_production_hierarchy_commit")
                if isinstance(pinned, dict) and "const" in pinned:
                    pinned["const"] = fixture.pinned_commit
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    synthetic_attestation_schema = tmp_path / "checkpoint_attestation_v2.schema.json"
    synthetic_attestation_schema.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(
        selection_module,
        "CHECKPOINT_ATTESTATION_SCHEMA",
        synthetic_attestation_schema,
    )
    inventory = json.loads(
        fixture.inventory_artifacts["source_inventory"].read_bytes()
    )
    exclusions = json.loads(fixture.inventory_artifacts["exclusions"].read_bytes())
    registry = generate_selection(
        source_inventory=inventory,
        exclusions=exclusions,
        inventory_attestation=inventory_attestation,
        trusted_inventory_checkpoint=fixture.inventory_checkpoint,
        producing_checkpoint=fixture.inventory_checkpoint,
    )

    _git(fixture.repo, "checkout", "--detach", fixture.inventory_checkpoint)
    _write_canonical_json(
        fixture.repo / V2_SELECTION_REGISTRY_PATH,
        registry,
    )
    fixture.selection_checkpoint = _commit(
        fixture.repo, "Freeze generated inventory selection"
    )
    fixture.registry.write_bytes(
        _git_blob(
            fixture.repo,
            fixture.selection_checkpoint,
            V2_SELECTION_REGISTRY_PATH,
        )
    )

    result = _verify_selection(fixture)

    assert _git(
        fixture.repo,
        "rev-parse",
        f"{fixture.toolset_checkpoint}^",
    ).stdout.strip() == fixture.component_commit
    assert _git(
        fixture.repo,
        "rev-parse",
        f"{fixture.inventory_checkpoint}^",
    ).stdout.strip() == fixture.toolset_checkpoint
    assert _git(
        fixture.repo,
        "rev-parse",
        f"{fixture.selection_checkpoint}^",
    ).stdout.strip() == fixture.inventory_checkpoint
    assert inventory["producing_checkpoint"] == fixture.toolset_checkpoint
    assert exclusions["producing_checkpoint"] == fixture.toolset_checkpoint
    assert registry["producing_checkpoint"] == fixture.inventory_checkpoint
    assert result["stage"] == "SELECTION"
    assert result["status"] == "VERIFIED"


def test_rejects_inventory_toolset_with_wrong_executing_verifier_hash(
    tmp_path: Path,
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path, fake_verifier=True)

    with pytest.raises(CheckpointVerificationError, match="executing verifier"):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    ("edge", "mode"),
    [
        ("component/toolset", "inventory"),
        ("toolset/inventory", "inventory"),
        ("inventory/selection", "selection"),
    ],
)
def test_v2_enforces_every_direct_parent_edge(
    tmp_path: Path, edge: str, mode: str
) -> None:
    if edge == "component/toolset":
        fixture = _build_inventory_checkpoints(
            tmp_path,
            manifest_mutator=lambda value: value.__setitem__(
                "producing_checkpoint", value["pinned_production_hierarchy_commit"]
            ),
        )
        call = lambda: _verify_inventory(fixture)
    else:
        fixture = _build_inventory_checkpoints(tmp_path)
        if edge == "toolset/inventory":
            call = lambda: _verify_inventory(
                fixture,
                trusted_inventory_checkpoint=fixture.selection_checkpoint,
            )
        else:
            (fixture.repo / "LATER").write_bytes(b"later\n")
            later = _commit(fixture.repo, "Later commit preserving selection")
            call = lambda: _verify_selection(
                fixture,
                trusted_selection_checkpoint=later,
            )

    with pytest.raises(CheckpointVerificationError, match="direct parent"):
        call()


def test_v2_rejects_reversed_ancestry_and_graft_metadata(tmp_path: Path) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    with pytest.raises(CheckpointVerificationError, match="direct parent|ancestor"):
        _verify_inventory(
            fixture,
            trusted_toolset_checkpoint=fixture.inventory_checkpoint,
            trusted_inventory_checkpoint=fixture.toolset_checkpoint,
        )

    grafts = fixture.repo / ".git" / "info" / "grafts"
    grafts.parent.mkdir(parents=True, exist_ok=True)
    grafts.write_text(
        f"{fixture.selection_checkpoint} {fixture.pinned_commit}\n",
        encoding="ascii",
    )
    with pytest.raises(CheckpointVerificationError, match="graft"):
        _verify_selection(fixture)


def test_v2_rejects_dirty_bundle_later_filename_only_commit_and_missing_artifact(
    tmp_path: Path,
) -> None:
    dirty = _build_inventory_checkpoints(tmp_path / "dirty")
    dirty.inventory_artifacts["source_inventory"].write_bytes(b"{}\n")
    with pytest.raises(CheckpointVerificationError, match="committed bytes"):
        _verify_inventory(dirty)

    later = _build_inventory_checkpoints(tmp_path / "later")
    with pytest.raises(CheckpointVerificationError, match="direct parent"):
        _verify_inventory(
            later,
            trusted_inventory_checkpoint=later.selection_checkpoint,
        )

    missing = _build_inventory_checkpoints(tmp_path / "missing")
    paths = dict(missing.inventory_artifacts)
    paths.pop("inventory_scan")
    with pytest.raises(CheckpointVerificationError, match="exact inventory artifact roles"):
        _verify_inventory(missing, inventory_artifact_paths=paths)


def test_v2_rejects_external_evidence_hash_mismatch(tmp_path: Path) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    fixture.external_evidence["ninjatrader_log"].write_bytes(b"mutated log\n")

    with pytest.raises(CheckpointVerificationError, match="external evidence.*hash"):
        _verify_inventory(fixture)


def test_v2_uses_fixed_schemas_instead_of_self_declared_version(tmp_path: Path) -> None:
    fixture = _build_inventory_checkpoints(
        tmp_path,
        inventory_mutator=lambda value: value.__setitem__("schema_version", "1.0"),
    )

    with pytest.raises(CheckpointVerificationError, match="source inventory schema"):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    ("role", "required_field", "schema_label"),
    [
        ("inventory_runtime_capture", "instrument", "inventory runtime capture"),
        ("inventory_scan", "observations", "inventory scan"),
        (
            "inventory_acquisition_evidence",
            "historical_trigger",
            "inventory acquisition evidence",
        ),
        ("inventory_provenance", "provider_acquisition", "inventory provenance"),
    ],
)
def test_v2_applies_each_frozen_evidence_schema_to_missing_required_fields(
    tmp_path: Path, role: str, required_field: str, schema_label: str
) -> None:
    def remove_required(document: dict[str, object]) -> None:
        document.pop(required_field)

    fixture = _build_inventory_checkpoints(
        tmp_path, artifact_mutators={role: remove_required}
    )

    with pytest.raises(
        CheckpointVerificationError,
        match=rf"{schema_label} schema validation failed.*required property",
    ):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    ("role", "schema_label"),
    [
        ("inventory_runtime_capture", "inventory runtime capture"),
        ("inventory_scan", "inventory scan"),
        ("inventory_acquisition_evidence", "inventory acquisition evidence"),
        ("inventory_provenance", "inventory provenance"),
    ],
)
def test_v2_applies_each_frozen_evidence_schema_to_unknown_fields(
    tmp_path: Path, role: str, schema_label: str
) -> None:
    def add_unknown(document: dict[str, object]) -> None:
        document["review_probe_unknown_field"] = True

    fixture = _build_inventory_checkpoints(
        tmp_path, artifact_mutators={role: add_unknown}
    )

    with pytest.raises(
        CheckpointVerificationError,
        match=rf"{schema_label} schema validation failed.*Additional properties",
    ):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    ("role", "fixed_field", "invalid_value", "schema_label"),
    [
        (
            "inventory_runtime_capture",
            "connection_snapshot_phase",
            "after inventory scan",
            "inventory runtime capture",
        ),
        ("inventory_scan", "civil_date_start", "2026-06-23", "inventory scan"),
        (
            "inventory_acquisition_evidence",
            "intended_connection_name",
            "Replay Connection",
            "inventory acquisition evidence",
        ),
        ("inventory_provenance", "status", "UNVERIFIED", "inventory provenance"),
    ],
)
def test_v2_applies_each_frozen_evidence_schema_to_invalid_fixed_values(
    tmp_path: Path,
    role: str,
    fixed_field: str,
    invalid_value: str,
    schema_label: str,
) -> None:
    def replace_fixed_value(document: dict[str, object]) -> None:
        document[fixed_field] = invalid_value

    fixture = _build_inventory_checkpoints(
        tmp_path, artifact_mutators={role: replace_fixed_value}
    )

    with pytest.raises(
        CheckpointVerificationError,
        match=rf"{schema_label} schema validation failed",
    ):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    "role",
    [
        "inventory_runtime_capture",
        "inventory_scan",
        "inventory_acquisition_evidence",
        "inventory_provenance",
    ],
)
def test_v2_reconciles_acquisition_identity_across_every_evidence_document(
    tmp_path: Path, role: str
) -> None:
    def change_acquisition(document: dict[str, object]) -> None:
        document["acquisition_id"] = "different-inventory-acquisition"

    fixture = _build_inventory_checkpoints(
        tmp_path, artifact_mutators={role: change_acquisition}
    )

    with pytest.raises(
        CheckpointVerificationError,
        match="inventory evidence acquisition identity mismatch",
    ):
        _verify_inventory(fixture)


@pytest.mark.parametrize(
    ("role", "schema_label"),
    [
        ("inventory_runtime_capture", "inventory runtime capture"),
        ("inventory_scan", "inventory scan"),
        ("inventory_acquisition_evidence", "inventory acquisition evidence"),
        ("inventory_provenance", "inventory provenance"),
    ],
)
def test_v2_rejects_mismatched_fixed_cohort_identity_in_every_evidence_document(
    tmp_path: Path, role: str, schema_label: str
) -> None:
    def change_cohort(document: dict[str, object]) -> None:
        document["cohort_id"] = "mnq-wrong-cohort"

    fixture = _build_inventory_checkpoints(
        tmp_path, artifact_mutators={role: change_cohort}
    )

    with pytest.raises(
        CheckpointVerificationError,
        match=rf"{schema_label} schema validation failed",
    ):
        _verify_inventory(fixture)


def test_v2_reconciles_provenance_provider_acquisition_identity(
    tmp_path: Path,
) -> None:
    def change_nested_acquisition(document: dict[str, object]) -> None:
        provider = document["provider_acquisition"]
        assert isinstance(provider, dict)
        provider["acquisition_id"] = "different-inventory-acquisition"

    fixture = _build_inventory_checkpoints(
        tmp_path,
        artifact_mutators={"inventory_provenance": change_nested_acquisition},
    )

    with pytest.raises(
        CheckpointVerificationError,
        match="inventory evidence acquisition identity mismatch",
    ):
        _verify_inventory(fixture)


def test_v2_reads_and_checks_the_executing_verifier_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    executing_path = Path(checkpoint_verify.__file__).resolve()
    original_read_bytes = Path.read_bytes
    reads = 0

    def changing_read_bytes(path: Path) -> bytes:
        nonlocal reads
        if path.resolve() == executing_path:
            reads += 1
            if reads > 1:
                return b"mutated verifier after identity check\n"
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", changing_read_bytes)

    result = _verify_inventory(fixture)

    assert reads == 1
    assert result["verifier"]["executing_sha256"] == result["verifier"][
        "frozen_sha256"
    ]


def test_v2_snapshots_every_supplied_bundle_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    original_read_bytes = Path.read_bytes
    expected_paths = {
        fixture.manifest.resolve(),
        fixture.registry.resolve(),
        *(path.resolve() for path in fixture.inventory_artifacts.values()),
        *(path.resolve() for path in fixture.external_evidence.values()),
        *(
            (fixture.bundle / relative).resolve()
            for relative in EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS.values()
        ),
    }
    reads = {path: 0 for path in expected_paths}

    def counted_read_bytes(path: Path) -> bytes:
        resolved = path.resolve()
        if resolved in reads:
            reads[resolved] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)

    _verify_selection(fixture)

    assert set(reads.values()) == {1}


@pytest.mark.parametrize("mode", ["inventory", "selection"])
def test_v2_remote_publication_verifies_the_mode_checkpoint(
    tmp_path: Path, mode: str
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    remote = tmp_path / "published.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _git(fixture.repo, "remote", "set-url", "origin", str(remote))
    expected = (
        fixture.inventory_checkpoint
        if mode == "inventory"
        else fixture.selection_checkpoint
    )
    _git(
        fixture.repo,
        "push",
        "origin",
        f"{expected}:refs/heads/validation/mnq-5m-inventory",
    )
    verifier = _verify_inventory if mode == "inventory" else _verify_selection

    result = verifier(
        fixture,
        expected_repository_identity=str(remote),
        remote_name="origin",
        remote_branch="validation/mnq-5m-inventory",
    )

    assert result["remote_publication"] == {
        "status": "VERIFIED",
        "remote": "origin",
        "branch": "validation/mnq-5m-inventory",
        "expected_checkpoint": expected,
        "observed_checkpoint": expected,
    }


@pytest.mark.parametrize("mode", ["inventory", "selection"])
def test_v2_remote_publication_rejects_wrong_mode_checkpoint(
    tmp_path: Path, mode: str
) -> None:
    fixture = _build_inventory_checkpoints(tmp_path)
    remote = tmp_path / "wrong.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _git(fixture.repo, "remote", "set-url", "origin", str(remote))
    wrong = (
        fixture.selection_checkpoint
        if mode == "inventory"
        else fixture.inventory_checkpoint
    )
    _git(
        fixture.repo,
        "push",
        "origin",
        f"{wrong}:refs/heads/validation/mnq-5m-inventory",
    )
    verifier = _verify_inventory if mode == "inventory" else _verify_selection

    with pytest.raises(CheckpointVerificationError, match="remote branch mismatch"):
        verifier(
            fixture,
            expected_repository_identity=str(remote),
            remote_name="origin",
            remote_branch="validation/mnq-5m-inventory",
        )


@pytest.mark.parametrize("mode", ["inventory", "selection"])
def test_cli_subcommands_dispatch_exact_v2_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    captured: dict[str, object] = {}

    def fake_verify(**arguments):
        captured.update(arguments)
        return {"mode": mode}

    monkeypatch.setattr(
        checkpoint_verify,
        f"verify_{mode}_checkpoint",
        fake_verify,
    )
    output = tmp_path / f"{mode}-attestation.json"
    arguments = [
        mode,
        "--repository-path",
        str(tmp_path),
        "--bundle-root",
        str(tmp_path),
        "--toolset-manifest",
        str(tmp_path / "toolset_manifest.json"),
        "--runtime-capture",
        str(tmp_path / "inventory_runtime_capture.json"),
        "--inventory-scan",
        str(tmp_path / "inventory_scan.json"),
        "--trading-hours-template",
        str(tmp_path / "trading_hours_template.xml"),
        "--acquisition-evidence",
        str(tmp_path / "inventory_acquisition_evidence.json"),
        "--inventory-provenance-input",
        str(tmp_path / "inventory_provenance.json"),
        "--source-inventory",
        str(tmp_path / "source_inventory.json"),
        "--exclusions",
        str(tmp_path / "exclusions.json"),
        "--trusted-toolset-checkpoint",
        "1" * 40,
        "--trusted-inventory-checkpoint",
        "2" * 40,
        "--expected-repository-identity",
        REPOSITORY_IDENTITY,
        "--output",
        str(output),
    ]
    if mode == "selection":
        arguments.extend(
            [
                "--selection-registry",
                str(tmp_path / "selection_registry.json"),
                "--trusted-selection-checkpoint",
                "3" * 40,
            ]
        )

    assert verifier_main(arguments) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {"mode": mode}
    assert captured["inventory_artifact_paths"] == {
        role: tmp_path / relative
        for role, relative in INVENTORY_ARTIFACT_REPOSITORY_PATHS.items()
    }
    assert captured["expected_repository_identity"] == REPOSITORY_IDENTITY
