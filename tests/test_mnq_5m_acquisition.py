from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.validation import mnq_5m_acquisition
from tools.validation.mnq_5m_acquisition import (
    AcquisitionValidationError,
    finalize_provenance as _finalize_provenance,
)


PINNED_PRODUCTION_COMMIT = "04a73e1401d44688660b211d9db6918113482856"
COHORT_ID = "mnq-202609-5m-v1"
PROVIDER_PROFILE_ID = "NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1"
SELECTION_CHECKPOINT = "2" * 40
INVENTORY_CHECKPOINT = "3" * 40
TOOLSET_CHECKPOINT = "4" * 40
COMPONENT_PATHS = {
    "protocol_spec": (
        "docs/superpowers/specs/2026-09-13-mnq-5m-multiwindow-validation-design.md"
    ),
    "acquisition_exporter": (
        "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs"
    ),
    "acquisition_finalizer": "tools/validation/mnq_5m_acquisition.py",
    "checkpoint_verifier": "tools/validation/mnq_5m_checkpoint_verify.py",
    "provenance_schema": "validation/mnq_5m_multiwindow/schemas/provenance.schema.json",
    "checkpoint_attestation_schema": (
        "validation/mnq_5m_multiwindow/schemas/checkpoint_attestation.schema.json"
    ),
    "selection_registry_schema": (
        "validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json"
    ),
    "toolset_manifest_schema": "validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json",
    "source_inventory_schema": "validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json",
    "exclusion_ledger_schema": "validation/mnq_5m_multiwindow/schemas/exclusions.schema.json",
}


def test_provider_profile_excludes_acquisition_connection_binding() -> None:
    assert "connection_name" not in mnq_5m_acquisition.PROVIDER_PROFILE
    assert mnq_5m_acquisition.APPROVED_CONNECTION_NAME == "My NinjaTrader"


def _verified_checkpoint_attestation(evidence_path: Path) -> dict[str, object]:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_entries = {
        entry["role"]: evidence_path.parent / entry["path"]
        for entry in evidence["evidence_files"]
    }
    registry_path = evidence_entries.get("selection_registry")
    registry = (
        json.loads(registry_path.read_text(encoding="utf-8"))
        if registry_path is not None
        else {}
    )

    def evidence_hash(role: str) -> str:
        path = evidence_entries.get(role)
        return _sha256(path) if path is not None else "0" * 64

    def registry_reference(name: str) -> dict[str, str]:
        value = registry.get(name)
        return value if isinstance(value, dict) else {
            "path": f"validation/mnq_5m_multiwindow/{name}.json",
            "sha256": "0" * 64,
        }

    def artifact(
        role: str, stage: str, repository_path: str, checkpoint: str, sha256: str
    ) -> dict[str, object]:
        return {
            "role": role,
            "stage": stage,
            "repository_path": repository_path,
            "checkpoint": checkpoint,
            "git_object_id": "5" * 40,
            "sha256": sha256,
            "bundle_sha256": sha256,
        }

    artifacts = [
        artifact(
            "toolset_manifest",
            "toolset",
            "validation/mnq_5m_multiwindow/toolset_manifest.json",
            TOOLSET_CHECKPOINT,
            evidence_hash("toolset_manifest"),
        ),
        artifact(
            "selection_registry",
            "selection",
            "validation/mnq_5m_multiwindow/selection_registry.json",
            SELECTION_CHECKPOINT,
            evidence_hash("selection_registry"),
        ),
        artifact(
            "source_inventory",
            "selection",
            registry_reference("source_inventory")["path"],
            SELECTION_CHECKPOINT,
            registry_reference("source_inventory")["sha256"],
        ),
        artifact(
            "exclusion_ledger",
            "selection",
            registry_reference("exclusion_ledger")["path"],
            SELECTION_CHECKPOINT,
            registry_reference("exclusion_ledger")["sha256"],
        ),
    ]
    attestation = {
        "schema_version": "1.0",
        "status": "VERIFIED",
        "repository": {
            "identity": "https://github.com/sikaodeluwei/trader_v1.git",
            "git_object_format": "sha1",
        },
        "trusted_toolset_checkpoint": TOOLSET_CHECKPOINT,
        "trusted_selection_checkpoint": SELECTION_CHECKPOINT,
        "pinned_production_hierarchy_commit": PINNED_PRODUCTION_COMMIT,
        "artifacts": artifacts,
        "ancestry": [
            {
                "ancestor": PINNED_PRODUCTION_COMMIT,
                "descendant": TOOLSET_CHECKPOINT,
                "verified": True,
            },
            {
                "ancestor": TOOLSET_CHECKPOINT,
                "descendant": SELECTION_CHECKPOINT,
                "verified": True,
            },
        ],
        "remote_publication": {"status": "NOT_CHECKED"},
        "verifier": {
            "version": "1.0",
            "repository_path": "tools/validation/mnq_5m_checkpoint_verify.py",
            "producing_commit": TOOLSET_CHECKPOINT,
            "frozen_sha256": "7" * 64,
            "executing_sha256": "7" * 64,
        },
        "attestation_sha256": "8" * 64,
    }
    return attestation


def finalize_provenance(**kwargs):
    attestation = _verified_checkpoint_attestation(Path(kwargs["acquisition_evidence_path"]))
    with patch(
        "tools.validation.mnq_5m_acquisition.verify_checkpoints",
        return_value=attestation,
    ):
        return _finalize_provenance(
            **kwargs,
            trusted_selection_checkpoint=SELECTION_CHECKPOINT,
            trusted_toolset_checkpoint=TOOLSET_CHECKPOINT,
            repository_path=Path(kwargs["source_path"]).parent,
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


def _payload_sha256(value: dict[str, object], hash_field: str) -> str:
    payload = deepcopy(value)
    payload.pop(hash_field, None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_payload(path: Path, value: dict[str, object], hash_field: str) -> None:
    value[hash_field] = _payload_sha256(value, hash_field)
    _write_json(path, value)


def _build_selection_evidence(tmp_path: Path) -> dict[str, Path]:
    inventory_path = tmp_path / "source_inventory.json"
    exclusions_path = tmp_path / "exclusions.json"
    registry_path = tmp_path / "selection_registry.json"

    entries: list[dict[str, object]] = []
    current = date(2026, 6, 22)
    while current <= date(2026, 7, 24):
        if current.weekday() < 5:
            excluded = current == date(2026, 6, 23)
            entries.append(
                {
                    "trading_date": current.isoformat(),
                    "eligible": not excluded,
                    "exclusion_reasons": (
                        ["UNEXPECTED_MISSING_BARS"] if excluded else []
                    ),
                }
            )
        current += timedelta(days=1)

    inventory = {
        "schema_version": "1.0",
        "status": "FROZEN_PRE_EXECUTION",
        "cohort_id": COHORT_ID,
        "contract_policy": {
            "contract_label": "MNQ SEP26",
            "full_name": "MNQ SEP26",
            "expiry_month": 9,
            "expiry_year": 2026,
            "candidate_date_start": "2026-06-22",
            "candidate_date_end": "2026-07-24",
        },
        "producing_checkpoint": TOOLSET_CHECKPOINT,
        "entries": entries,
    }
    _write_payload(inventory_path, inventory, "aggregate_payload_sha256")

    exclusions = {
        "schema_version": "1.0",
        "status": "FROZEN_PRE_EXECUTION",
        "cohort_id": COHORT_ID,
        "producing_checkpoint": TOOLSET_CHECKPOINT,
        "entries": [
            {
                "trading_date": "2026-06-23",
                "reasons": ["UNEXPECTED_MISSING_BARS"],
            }
        ],
    }
    _write_payload(exclusions_path, exclusions, "aggregate_payload_sha256")

    eligible_dates = [entry["trading_date"] for entry in entries if entry["eligible"]]
    selections = []
    count = len(eligible_dates)
    for index in range(10):
        start = index * count // 10
        end = (index + 1) * count // 10 - 1
        trading_date = eligible_dates[start]
        stratum = index + 1
        selections.append(
            {
                "case_id": f"mnq-202609-5m-td{trading_date}-w{stratum:02d}",
                "trading_date": trading_date,
                "stratum_number": stratum,
                "stratum_start_index": start,
                "stratum_end_index": end,
                "selected_eligible_index": start,
                "window_policy": "FIRST_250_NATIVE_5M_SESSION_BARS",
            }
        )

    registry = {
        "schema_version": "1.0",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": COHORT_ID,
        "contract_policy": inventory["contract_policy"],
        "selection_algorithm": {
            "id": "CHRONOLOGICAL_TEN_STRATA_EARLIEST",
            "version": "1.0",
            "stratum_count": 10,
        },
        "selection_count": 10,
        "source_inventory": {
            "path": "validation/mnq_5m_multiwindow/source_inventory.json",
            "bundle_path": inventory_path.name,
            "schema_version": "1.0",
            "sha256": _sha256(inventory_path),
            "producing_checkpoint": INVENTORY_CHECKPOINT,
        },
        "exclusion_ledger": {
            "path": "validation/mnq_5m_multiwindow/exclusions.json",
            "bundle_path": exclusions_path.name,
            "schema_version": "1.0",
            "sha256": _sha256(exclusions_path),
            "producing_checkpoint": INVENTORY_CHECKPOINT,
        },
        "producing_checkpoint": INVENTORY_CHECKPOINT,
        "selection_influence": {
            "hierarchy_output_used": False,
            "oracle_output_used": False,
            "project_output_used": False,
        },
        "selections": selections,
    }
    _write_payload(registry_path, registry, "aggregate_payload_sha256")
    return {
        "source_inventory": inventory_path,
        "exclusion_ledger": exclusions_path,
        "selection_registry": registry_path,
    }


def _build_toolset_evidence(tmp_path: Path, exporter: Path) -> dict[str, Path]:
    root = Path(__file__).resolve().parents[1]
    artifact_sources = {
        role: root / relative_path for role, relative_path in COMPONENT_PATHS.items()
    }
    artifact_sources["acquisition_exporter"] = exporter
    evidence_paths: dict[str, Path] = {}
    for role in COMPONENT_PATHS:
        source = artifact_sources.get(role)
        destination = tmp_path / f"{role}.artifact"
        assert source is not None and source.exists()
        destination.write_bytes(source.read_bytes())
        evidence_paths[role] = destination

    components = [
        {
            "role": role,
            "path": COMPONENT_PATHS[role],
            "bundle_path": evidence_paths[role].name,
            "sha256": _sha256(evidence_paths[role]),
            "producing_commit": TOOLSET_CHECKPOINT,
        }
        for role in COMPONENT_PATHS
    ]
    manifest = {
        "schema_version": "1.0",
        "stage": "SOURCE_ACQUISITION",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": COHORT_ID,
        "producing_checkpoint": TOOLSET_CHECKPOINT,
        "pinned_production_hierarchy_commit": PINNED_PRODUCTION_COMMIT,
        "runtime": {
            "implementation": "CPython",
            "version": "3.12",
            "dependencies": [{"name": "python-standard-library", "version": "3.12"}],
        },
        "canonicalization": "JSON_UTF8_SORTED_KEYS_COMPACT_EXCLUDE_AGGREGATE_PAYLOAD_SHA256",
        "components": components,
        "deferred_components": [
            "independent_oracle",
            "blind_project_runner",
            "comparator",
            "cohort_aggregator",
        ],
    }
    manifest_path = tmp_path / "toolset_manifest.json"
    _write_payload(manifest_path, manifest, "aggregate_payload_sha256")
    evidence_paths["toolset_manifest"] = manifest_path
    return evidence_paths


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
        "2026-06-21 23:45:00.000 (My NinjaTrader) "
        "Tradovate.Adapter.Connect status=Connecting\n"
        "2026-06-21 23:45:01.000 (My NinjaTrader) "
        "Cbi.Connection.ConnectionStatusCallback: status=Connected "
        "priceStatus=Connected previousStatus=Connecting\n"
        "2026-06-21 23:45:02.000 Server.HdsClient.Connect: type=HDS "
        "server='hds-us-nt-007.ninjatrader.com' port=31655 system='' useSsl=True\n"
        "2026-06-21 23:46:00.000 acquisition=acq-001 exporter initialized "
        "event_time=2026-06-21T23:46:00+08:00\n"
        "2026-06-21 23:46:01.000 acquisition=acq-001 realtime lifecycle observed "
        "event_time=2026-06-21T23:46:01+08:00\n"
        "2026-06-21 23:56:00.000 "
        "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26' "
        "from='2026/6/21 23:00:00' to='2026/6/23 0:00:00' period='1 Minute'\n"
        "2026-06-21 23:56:30.000 acquisition=acq-001 exporter initialized "
        "event_time=2026-06-21T23:56:30+08:00\n"
        "2026-06-21 23:56:31.000 acquisition=acq-001 realtime lifecycle observed "
        "event_time=2026-06-21T23:56:31+08:00\n"
        "2026-06-22 21:30:59.000 acquisition=acq-001 export armed "
        "event_time=2026-06-22T21:30:59+08:00\n"
        "2026-06-22 21:31:00.000 acquisition=acq-001 export complete "
        "event_time=2026-06-22T21:31:00+08:00\n",
        encoding="utf-8",
    )
    log = tmp_path / "log.txt"
    log.write_text(
        "2026-06-21 23:50:00.000 acquisition=acq-001 "
        "provider=Provider31 connection=My NinjaTrader status=Connected\n",
        encoding="utf-8",
    )
    config = tmp_path / "Config.xml"
    config.write_text(
        "<NinjaTrader><PreferredFutureConnection>My NinjaTrader</PreferredFutureConnection>"
        "<PreferredRealtimeFutureConnection>My NinjaTrader</PreferredRealtimeFutureConnection>"
        "<TradovateOptions><Name>My NinjaTrader</Name><Provider>Provider31</Provider>"
        "</TradovateOptions>"
        "</NinjaTrader>\n",
        encoding="utf-8",
    )
    hours = tmp_path / "CME US Index Futures ETH.xml"
    hours.write_text("<TradingHours name='CME US Index Futures ETH' />\n", encoding="utf-8")
    selection_paths = _build_selection_evidence(tmp_path)
    toolset_paths = _build_toolset_evidence(tmp_path, exporter)
    selection_registry = selection_paths["selection_registry"]
    toolset_manifest = toolset_paths["toolset_manifest"]

    runtime = {
        "schema_version": "1.1",
        "acquisition_id": "acq-001",
        "cohort_id": "mnq-202609-5m-v1",
        "case_id": "mnq-202609-5m-td2026-06-22-w01",
        "trading_date": "2026-06-22",
        "instrument": {
            "contract_label": "MNQ SEP26",
            "full_name": "MNQ SEP26",
            "master_name": "MNQ",
            "instrument_id": "MNQ SEP26",
            "expiry_month": 9,
            "expiry_year": 2026,
            "exchange": "Globex",
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
                    "timestamp": "2026-06-21T23:56:30+08:00",
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
                "name": "My NinjaTrader",
                "provider": "Provider31",
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

    evidence_files = [
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
    ]
    evidence = {
        "schema_version": "1.2",
        "acquisition_id": "acq-001",
        "cohort_id": "mnq-202609-5m-v1",
        "case_id": "mnq-202609-5m-td2026-06-22-w01",
        "trading_date": "2026-06-22",
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "intended_connection_name": "My NinjaTrader",
        "log_timezone_id": "Singapore Standard Time",
        "log_utc_offset": "+08:00",
        "historical_request_trigger": {
            "method": "NINJATRADER_REQUEST_BARS_TRACE",
            "request_source_role": "ninjatrader_trace",
            "adapter_connection_initiated_at": "2026-06-21T23:45:00+08:00",
            "connection_ready_at": "2026-06-21T23:45:01+08:00",
            "hds_connected_at": "2026-06-21T23:45:02+08:00",
            "pre_request_realtime_at": "2026-06-21T23:46:01+08:00",
            "request_observed_at": "2026-06-21T23:56:00+08:00",
            "post_request_initialized_at": "2026-06-21T23:56:30+08:00",
            "post_request_realtime_at": "2026-06-21T23:56:31+08:00",
        },
        "export_armed_at": "2026-06-22T21:30:59+08:00",
        "export_completed_at": "2026-06-22T21:31:00+08:00",
        "runtime_capture_sha256": _sha256(runtime_path),
        "exporter_sha256": _sha256(exporter),
        "expected_selection_checkpoint": SELECTION_CHECKPOINT,
        "expected_toolset_checkpoint": TOOLSET_CHECKPOINT,
        "evidence_files": evidence_files,
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


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "--all")
    _git(
        repo,
        "-c",
        "user.name=Acquisition Test",
        "-c",
        "user.email=acquisition@example.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


def _git_bytes(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        check=True,
        capture_output=True,
    ).stdout


def _freeze_bundle_in_real_git_history(
    tmp_path: Path, evidence_path: Path
) -> tuple[Path, str, str]:
    project_root = Path(__file__).resolve().parents[1]
    repository = tmp_path / "checkpoint-repository"
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--no-hardlinks",
            str(project_root),
            str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _git(
        repository,
        "remote",
        "set-url",
        "origin",
        "https://github.com/sikaodeluwei/trader_v1.git",
    )
    _git(repository, "config", "core.autocrlf", "false")

    manifest_path = _evidence_role_path(evidence_path, "toolset_manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for component in manifest["components"]:
        source = evidence_path.parent / component["bundle_path"]
        destination = repository / component["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    component_commit = _commit(repository, "Freeze acquisition components")

    manifest["producing_checkpoint"] = component_commit
    for component in manifest["components"]:
        committed_bytes = _git_bytes(
            repository, component_commit, component["path"]
        )
        (evidence_path.parent / component["bundle_path"]).write_bytes(
            committed_bytes
        )
        component["producing_commit"] = component_commit
        component["sha256"] = hashlib.sha256(committed_bytes).hexdigest()
    _write_payload(manifest_path, manifest, "aggregate_payload_sha256")
    _refresh_evidence_role_hash(evidence_path, "toolset_manifest")
    repository_manifest = (
        repository / "validation/mnq_5m_multiwindow/toolset_manifest.json"
    )
    repository_manifest.parent.mkdir(parents=True, exist_ok=True)
    repository_manifest.write_bytes(manifest_path.read_bytes())
    toolset_checkpoint = _commit(repository, "Freeze acquisition toolset")
    manifest_path.write_bytes(
        _git_bytes(
            repository,
            toolset_checkpoint,
            "validation/mnq_5m_multiwindow/toolset_manifest.json",
        )
    )
    _refresh_evidence_role_hash(evidence_path, "toolset_manifest")

    inventory_path = evidence_path.parent / "source_inventory.json"
    exclusions_path = evidence_path.parent / "exclusions.json"
    for path in (inventory_path, exclusions_path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["producing_checkpoint"] = toolset_checkpoint
        _write_payload(path, payload, "aggregate_payload_sha256")
        repository_path = repository / (
            "validation/mnq_5m_multiwindow/" + path.name
        )
        repository_path.write_bytes(path.read_bytes())
    inventory_checkpoint = _commit(repository, "Freeze source inventory")
    for path in (inventory_path, exclusions_path):
        path.write_bytes(
            _git_bytes(
                repository,
                inventory_checkpoint,
                "validation/mnq_5m_multiwindow/" + path.name,
            )
        )

    registry_path = _evidence_role_path(evidence_path, "selection_registry")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["producing_checkpoint"] = inventory_checkpoint
    for key, path in (
        ("source_inventory", inventory_path),
        ("exclusion_ledger", exclusions_path),
    ):
        registry[key]["producing_checkpoint"] = inventory_checkpoint
        registry[key]["sha256"] = _sha256(path)
    _write_payload(registry_path, registry, "aggregate_payload_sha256")
    _refresh_evidence_role_hash(evidence_path, "selection_registry")
    repository_registry = (
        repository / "validation/mnq_5m_multiwindow/selection_registry.json"
    )
    repository_registry.write_bytes(registry_path.read_bytes())
    selection_checkpoint = _commit(repository, "Freeze cohort selection")
    registry_path.write_bytes(
        _git_bytes(
            repository,
            selection_checkpoint,
            "validation/mnq_5m_multiwindow/selection_registry.json",
        )
    )
    _refresh_evidence_role_hash(evidence_path, "selection_registry")

    _rewrite_json(
        evidence_path,
        lambda value: value.update(
            {
                "expected_toolset_checkpoint": toolset_checkpoint,
                "expected_selection_checkpoint": selection_checkpoint,
            }
        ),
    )
    return repository, toolset_checkpoint, selection_checkpoint


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


def _evidence_role_path(evidence: Path, role: str) -> Path:
    value = json.loads(evidence.read_text(encoding="utf-8"))
    entry = next(item for item in value["evidence_files"] if item["role"] == role)
    return evidence.parent / entry["path"]


def _refresh_evidence_role_hash(evidence: Path, role: str) -> None:
    role_path = _evidence_role_path(evidence, role)

    def update(value: dict[str, object]) -> None:
        entry = next(
            item for item in value["evidence_files"] if item["role"] == role
        )
        entry["sha256"] = _sha256(role_path)

    _rewrite_json(evidence, update)


def _rewrite_evidence_role_text(evidence: Path, role: str, transform) -> Path:
    path = _evidence_role_path(evidence, role)
    path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")
    _refresh_evidence_role_hash(evidence, role)
    return path


def _rewrite_bound_payload(
    evidence: Path,
    role: str,
    hash_field: str,
    mutator,
) -> Path:
    path = _evidence_role_path(evidence, role)
    value = json.loads(path.read_text(encoding="utf-8"))
    mutator(value)
    _write_payload(path, value, hash_field)
    _refresh_evidence_role_hash(evidence, role)
    return path


def _bind_registry_reference(
    evidence: Path, reference_name: str, referenced_path: Path
) -> None:
    _rewrite_bound_payload(
        evidence,
        "selection_registry",
        "aggregate_payload_sha256",
        lambda value: value[reference_name].__setitem__(
            "sha256", _sha256(referenced_path)
        ),
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

    assert result["schema_version"] == "1.2"
    assert result["cohort_id"] == "mnq-202609-5m-v1"
    assert result["case_id"] == "mnq-202609-5m-td2026-06-22-w01"
    assert result["contract"]["contract_label"] == "MNQ SEP26"
    assert result["contract"]["full_name"] == "MNQ SEP26"
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
    assert result["provider_acquisition"] == {
        "status": "PROVEN",
        "provider_profile_id": PROVIDER_PROFILE_ID,
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
            "connected_at": "2026-06-21T23:45:02+08:00",
        },
        "configuration_binding": {
            "mode": "EXPLICIT_PREFERENCE",
            "preferred_future_connection": "My NinjaTrader",
            "preferred_realtime_future_connection": "My NinjaTrader",
            "saved_connection_matches": 1,
        },
        "acquisition_id": "acq-001",
        "lifecycle": {
            "adapter_connection_initiated_at": "2026-06-21T23:45:00+08:00",
            "connection_ready_at": "2026-06-21T23:45:01+08:00",
            "pre_request_realtime_at": "2026-06-21T23:46:01+08:00",
            "post_request_initialized_at": "2026-06-21T23:56:30+08:00",
            "post_request_realtime_at": "2026-06-21T23:56:31+08:00",
            "export_armed_at": "2026-06-22T21:30:59+08:00",
            "export_completed_at": "2026-06-22T21:31:00+08:00",
        },
        "historical_request": {
            "source_role": "ninjatrader_trace",
            "observed_at": "2026-06-21T23:56:00+08:00",
            "instrument": "MNQ SEP26",
            "requested_start": "2026-06-21T23:00:00",
            "requested_end": "2026-06-23T00:00:00",
            "provider_request_period": "1 Minute",
            "covers_declared_session": True,
        },
        "competing_historical_provider_connections": 0,
        "intended_provider_disconnects": 0,
        "log_timezone_id": "Singapore Standard Time",
        "log_utc_offset": "+08:00",
    }
    assert result["selection_binding"]["status"] == "FROZEN_FOR_SOURCE_ACQUISITION"
    assert result["selection_binding"]["trusted_checkpoint"] == SELECTION_CHECKPOINT
    assert result["selection_binding"]["selection"]["case_id"] == (
        "mnq-202609-5m-td2026-06-22-w01"
    )
    assert result["selection_binding"]["inventory"]["producing_checkpoint"] == (
        INVENTORY_CHECKPOINT
    )
    assert result["toolset_binding"] == {
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "stage": "SOURCE_ACQUISITION",
        "producing_checkpoint": TOOLSET_CHECKPOINT,
        "trusted_checkpoint": TOOLSET_CHECKPOINT,
        "pinned_production_hierarchy_commit": PINNED_PRODUCTION_COMMIT,
        "aggregate_payload_sha256": json.loads(
            _evidence_role_path(evidence, "toolset_manifest").read_text(encoding="utf-8")
        )["aggregate_payload_sha256"],
    }
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


def test_accepts_confirmed_runtime_name_without_normalizing_it(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        runtime,
        lambda value: (
            value["instrument"].__setitem__("full_name", "MNQ SEP26"),
            value["instrument"].__setitem__("instrument_id", "MNQ SEP26"),
        ),
    )
    _refresh_runtime_hash(runtime, evidence)

    result = finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
    )

    assert result["contract"]["full_name"] == "MNQ SEP26"
    assert result["contract"]["instrument_id"] == "MNQ SEP26"


def test_rejects_disagreeing_raw_runtime_identity_fields(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        runtime,
        lambda value: value["instrument"].__setitem__(
            "instrument_id", "MNQ 09-26"
        ),
    )
    _refresh_runtime_hash(runtime, evidence)

    with pytest.raises(AcquisitionValidationError, match="identity fields disagree"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_semantic_validation_uses_the_same_manifest_bytes_that_were_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    manifest_path = _evidence_role_path(evidence, "toolset_manifest")
    substituted = json.loads(manifest_path.read_text(encoding="utf-8"))
    substituted["producing_checkpoint"] = "5" * 40
    substituted["aggregate_payload_sha256"] = _payload_sha256(
        substituted, "aggregate_payload_sha256"
    )
    substituted_bytes = json.dumps(substituted, indent=2).encode("utf-8")
    attestation = _verified_checkpoint_attestation(evidence)
    original_read_bytes = Path.read_bytes
    reads = 0

    def swapped_read_bytes(path: Path) -> bytes:
        nonlocal reads
        if path.resolve() == manifest_path.resolve():
            reads += 1
            if reads > 1:
                return substituted_bytes
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", swapped_read_bytes)

    with patch(
        "tools.validation.mnq_5m_acquisition.verify_checkpoints",
        return_value=attestation,
    ):
        result = _finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
            trusted_selection_checkpoint=SELECTION_CHECKPOINT,
            trusted_toolset_checkpoint=TOOLSET_CHECKPOINT,
            repository_path=tmp_path,
        )

    assert result["toolset_binding"]["producing_checkpoint"] == TOOLSET_CHECKPOINT
    assert reads == 1


def test_bound_documents_are_not_reread_after_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    inventory_path = evidence.parent / "source_inventory.json"
    expected_hash = _sha256(inventory_path)
    original_read_bytes = Path.read_bytes
    reads = 0

    def reject_inventory_reread(path: Path) -> bytes:
        nonlocal reads
        if path.resolve() == inventory_path.resolve():
            reads += 1
            if reads > 1:
                raise AssertionError("inventory was reread after hashing")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_inventory_reread)

    result = finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
    )

    assert result["selection_binding"]["inventory"]["sha256"] == expected_hash
    assert reads == 1


def test_finalizer_rejects_attestation_for_different_bundle_snapshot(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    attestation = _verified_checkpoint_attestation(evidence)
    manifest_artifact = next(
        item
        for item in attestation["artifacts"]
        if item["role"] == "toolset_manifest"
    )
    manifest_artifact["sha256"] = "0" * 64
    manifest_artifact["bundle_sha256"] = "0" * 64

    with patch(
        "tools.validation.mnq_5m_acquisition.verify_checkpoints",
        return_value=attestation,
    ):
        with pytest.raises(
            AcquisitionValidationError,
            match="verified checkpoint artifact.*toolset_manifest",
        ):
            _finalize_provenance(
                source_path=source,
                runtime_capture_path=runtime,
                acquisition_evidence_path=evidence,
                exporter_path=exporter,
                trusted_selection_checkpoint=SELECTION_CHECKPOINT,
                trusted_toolset_checkpoint=TOOLSET_CHECKPOINT,
                repository_path=tmp_path,
            )


def test_official_finalization_requires_independent_git_checkpoint_verification(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)

    with pytest.raises(
        AcquisitionValidationError,
        match="independent Git checkpoint verification is required",
    ):
        _finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
            trusted_selection_checkpoint=SELECTION_CHECKPOINT,
            trusted_toolset_checkpoint=TOOLSET_CHECKPOINT,
        )


def test_official_finalizer_embeds_attestation_from_real_git_objects(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    repository, toolset_checkpoint, selection_checkpoint = (
        _freeze_bundle_in_real_git_history(tmp_path, evidence)
    )

    result = _finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
        trusted_selection_checkpoint=selection_checkpoint,
        trusted_toolset_checkpoint=toolset_checkpoint,
        repository_path=repository,
    )

    assert result["checkpoint_verification"]["status"] == "VERIFIED"
    assert (
        result["checkpoint_verification"]["trusted_selection_checkpoint"]
        == selection_checkpoint
    )


def test_public_finalizer_has_no_unverified_synthetic_bypass(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)

    with pytest.raises(TypeError, match="allow_unverified_synthetic"):
        _finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
            trusted_selection_checkpoint=SELECTION_CHECKPOINT,
            trusted_toolset_checkpoint=TOOLSET_CHECKPOINT,
            allow_unverified_synthetic=True,
        )


def test_acquisition_cli_can_run_directly_from_repository_root() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/validation/mnq_5m_acquisition.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert completed.returncode == 0, completed.stderr
    assert "--repository" in completed.stdout


def test_finalizer_rejects_user_supplied_checkpoint_attestation(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)

    with pytest.raises(
        AcquisitionValidationError,
        match="user-supplied checkpoint attestation is not accepted",
    ):
        _finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
            trusted_selection_checkpoint=SELECTION_CHECKPOINT,
            trusted_toolset_checkpoint=TOOLSET_CHECKPOINT,
            checkpoint_attestation={"status": "VERIFIED"},
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["selections"][0].__setitem__(
            "trading_date", "2026-06-24"
        ),
        lambda value: value["selections"][0].__setitem__("stratum_number", 2),
        lambda value: value["selections"][0].__setitem__(
            "case_id", "mnq-202609-5m-td2026-06-22-w02"
        ),
        lambda value: value["selections"].pop(0),
        lambda value: value["selections"][1].__setitem__(
            "case_id", value["selections"][0]["case_id"]
        ),
        lambda value: (
            value["selections"][1].__setitem__("trading_date", "2026-06-22"),
            value["selections"][1].__setitem__(
                "case_id", "mnq-202609-5m-td2026-06-22-w02"
            ),
        ),
        lambda value: value.__setitem__("cohort_id", "other-cohort"),
        lambda value: value.__setitem__("status", "PREPARATION_INCOMPLETE"),
        lambda value: value["selection_influence"].__setitem__(
            "hierarchy_output_used", True
        ),
        lambda value: value.__setitem__("unexpected", True),
        lambda value: value["contract_policy"].__setitem__(
            "full_name", "MNQ 12-26"
        ),
        lambda value: value["contract_policy"].__setitem__(
            "candidate_date_end", "2026-07-25"
        ),
        lambda value: (
            value["selections"][1].__setitem__("trading_date", "2026-06-26"),
            value["selections"][1].__setitem__(
                "case_id", "mnq-202609-5m-td2026-06-26-w02"
            ),
        ),
    ],
    ids=[
        "case-date",
        "stratum",
        "case-suffix",
        "missing-current-case",
        "duplicate-case",
        "duplicate-trading-date",
        "cohort",
        "status",
        "hierarchy-influence",
        "extra-field",
        "contract",
        "date-policy",
        "not-deterministically-selected",
    ],
)
def test_rejects_semantically_invalid_selection_registry(
    tmp_path: Path, mutation
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_bound_payload(
        evidence, "selection_registry", "aggregate_payload_sha256", mutation
    )

    with pytest.raises(AcquisitionValidationError, match="selection registry"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_placeholder_selection_registry(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    registry = _evidence_role_path(evidence, "selection_registry")
    _write_json(registry, {"status": "synthetic-fixture"})
    _refresh_evidence_role_hash(evidence, "selection_registry")

    with pytest.raises(AcquisitionValidationError, match="selection registry"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize("defect", ["non-chronological", "eligibility"])
def test_rejects_semantically_invalid_source_inventory(
    tmp_path: Path, defect: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    inventory = tmp_path / "source_inventory.json"
    value = json.loads(inventory.read_text(encoding="utf-8"))
    if defect == "non-chronological":
        value["entries"][0], value["entries"][1] = (
            value["entries"][1],
            value["entries"][0],
        )
    else:
        value["entries"][1]["eligible"] = True
    _write_payload(inventory, value, "aggregate_payload_sha256")
    _bind_registry_reference(evidence, "source_inventory", inventory)

    with pytest.raises(AcquisitionValidationError, match="source inventory"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["entries"][1].__setitem__(
            "trading_date", value["entries"][0]["trading_date"]
        ),
        lambda value: value["entries"][0].__setitem__(
            "trading_date", "2026-06-21"
        ),
        lambda value: value["entries"][1].__setitem__(
            "exclusion_reasons", ["NOT_AN_APPROVED_REASON"]
        ),
    ],
    ids=["duplicate-date", "outside-policy", "malformed-reason"],
)
def test_rejects_additional_invalid_source_inventory_semantics(
    tmp_path: Path, mutation
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    inventory = tmp_path / "source_inventory.json"
    value = json.loads(inventory.read_text(encoding="utf-8"))
    mutation(value)
    _write_payload(inventory, value, "aggregate_payload_sha256")
    _bind_registry_reference(evidence, "source_inventory", inventory)

    with pytest.raises(AcquisitionValidationError, match="source inventory"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_undeclared_inventory_exclusion(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    inventory = tmp_path / "source_inventory.json"
    value = json.loads(inventory.read_text(encoding="utf-8"))
    value["entries"][2]["eligible"] = False
    value["entries"][2]["exclusion_reasons"] = ["UNEXPECTED_MISSING_BARS"]
    _write_payload(inventory, value, "aggregate_payload_sha256")
    _bind_registry_reference(evidence, "source_inventory", inventory)

    with pytest.raises(AcquisitionValidationError, match="exclusion ledger"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_inventory_missing_a_candidate_trading_date(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    inventory = tmp_path / "source_inventory.json"
    value = json.loads(inventory.read_text(encoding="utf-8"))
    value["entries"].pop(2)
    _write_payload(inventory, value, "aggregate_payload_sha256")
    _bind_registry_reference(evidence, "source_inventory", inventory)

    with pytest.raises(AcquisitionValidationError, match="every candidate trading date"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_coordinated_selection_checkpoint_tampering(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        evidence,
        lambda value: value.__setitem__("expected_selection_checkpoint", "5" * 40),
    )
    _rewrite_bound_payload(
        evidence,
        "selection_registry",
        "aggregate_payload_sha256",
        lambda value: value.__setitem__(
            "producing_checkpoint", "not-a-checkpoint"
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="selection registry"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_selection_reference_path_traversal(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_bound_payload(
        evidence,
        "selection_registry",
        "aggregate_payload_sha256",
        lambda value: value["source_inventory"].__setitem__(
            "bundle_path", "../source_inventory.json"
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="relative and contained"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_inventory_hash_disagreement(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    inventory = tmp_path / "source_inventory.json"
    value = json.loads(inventory.read_text(encoding="utf-8"))
    value["entries"][-1]["eligible"] = False
    value["entries"][-1]["exclusion_reasons"] = ["SOURCE_HASH_MISMATCH"]
    _write_payload(inventory, value, "aggregate_payload_sha256")

    with pytest.raises(AcquisitionValidationError, match="inventory hash"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_exclusion_ledger_hash_disagreement(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    exclusions = tmp_path / "exclusions.json"
    value = json.loads(exclusions.read_text(encoding="utf-8"))
    value["entries"][0]["reasons"] = ["SOURCE_HASH_MISMATCH"]
    _write_payload(exclusions, value, "aggregate_payload_sha256")

    with pytest.raises(AcquisitionValidationError, match="exclusion ledger hash"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_exclusion_ledger_semantic_disagreement(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    exclusions = tmp_path / "exclusions.json"
    value = json.loads(exclusions.read_text(encoding="utf-8"))
    value["entries"][0]["reasons"] = ["SOURCE_HASH_MISMATCH"]
    _write_payload(exclusions, value, "aggregate_payload_sha256")
    _bind_registry_reference(evidence, "exclusion_ledger", exclusions)

    with pytest.raises(AcquisitionValidationError, match="exclusion ledger"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "role",
    [
        "acquisition_exporter",
        "acquisition_finalizer",
        "checkpoint_verifier",
        "protocol_spec",
        "provenance_schema",
        "checkpoint_attestation_schema",
        "selection_registry_schema",
        "toolset_manifest_schema",
        "source_inventory_schema",
        "exclusion_ledger_schema",
    ],
)
def test_rejects_toolset_component_hash_disagreement(
    tmp_path: Path, role: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)

    def mutate(value: dict[str, object]) -> None:
        component = next(item for item in value["components"] if item["role"] == role)
        component["sha256"] = "0" * 64

    _rewrite_bound_payload(
        evidence, "toolset_manifest", "aggregate_payload_sha256", mutate
    )

    with pytest.raises(AcquisitionValidationError, match="toolset manifest"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.__setitem__(
            "pinned_production_hierarchy_commit", "0" * 40
        ),
        lambda value: value.__setitem__(
            "producing_checkpoint", "not-a-checkpoint"
        ),
        lambda value: value["components"].append(deepcopy(value["components"][0])),
        lambda value: value["components"].pop(),
        lambda value: value.__setitem__("status", "PREPARATION_INCOMPLETE"),
        lambda value: value["components"][0].__setitem__(
            "producing_commit", "not-a-commit"
        ),
        lambda value: value["components"][0].__setitem__(
            "path", "tools/validation/wrong.py"
        ),
        lambda value: value.__setitem__("unexpected", True),
    ],
    ids=[
        "production-commit",
        "producing-checkpoint",
        "duplicate-role",
        "missing-role",
        "incomplete-status",
        "component-producing-commit",
        "component-path",
        "extra-field",
    ],
)
def test_rejects_semantically_invalid_toolset_manifest(
    tmp_path: Path, mutation
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_bound_payload(
        evidence, "toolset_manifest", "aggregate_payload_sha256", mutation
    )

    with pytest.raises(AcquisitionValidationError, match="toolset manifest"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_invalid_toolset_aggregate_hash(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    manifest = _evidence_role_path(evidence, "toolset_manifest")
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["aggregate_payload_sha256"] = "0" * 64
    _write_json(manifest, value)
    _refresh_evidence_role_hash(evidence, "toolset_manifest")

    with pytest.raises(AcquisitionValidationError, match="toolset manifest"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_coordinated_toolset_checkpoint_tampering(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        evidence,
        lambda value: value.__setitem__("expected_toolset_checkpoint", "5" * 40),
    )

    def mutate(value: dict[str, object]) -> None:
        value["producing_checkpoint"] = "5" * 40
        for component in value["components"]:
            component["producing_commit"] = "5" * 40

    _rewrite_bound_payload(
        evidence, "toolset_manifest", "aggregate_payload_sha256", mutate
    )

    with pytest.raises(AcquisitionValidationError, match="toolset manifest"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_placeholder_toolset_manifest(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    manifest = _evidence_role_path(evidence, "toolset_manifest")
    _write_json(manifest, {"status": "synthetic-fixture"})
    _refresh_evidence_role_hash(evidence, "toolset_manifest")

    with pytest.raises(AcquisitionValidationError, match="toolset manifest"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_toolset_component_path_traversal(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)

    def mutate(value: dict[str, object]) -> None:
        component = next(
            item
            for item in value["components"]
            if item["role"] == "protocol_spec"
        )
        component["bundle_path"] = "../protocol.md"

    _rewrite_bound_payload(
        evidence, "toolset_manifest", "aggregate_payload_sha256", mutate
    )

    with pytest.raises(AcquisitionValidationError, match="relative and contained"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    ("filename", "title_fragment"),
    [
        ("provenance.schema.json", "source provenance"),
        ("checkpoint_attestation.schema.json", "checkpoint verification"),
        ("selection_registry.schema.json", "selection registry"),
        ("toolset_manifest.schema.json", "toolset manifest"),
        ("source_inventory.schema.json", "source inventory"),
        ("exclusions.schema.json", "exclusion ledger"),
    ],
)
def test_semantic_binding_schemas_are_parseable_and_versioned(
    filename: str, title_fragment: str
) -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "validation"
        / "mnq_5m_multiwindow"
        / "schemas"
        / filename
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert title_fragment in schema["title"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_provenance_schema_requires_semantic_bindings() -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "validation"
        / "mnq_5m_multiwindow"
        / "schemas"
        / "provenance.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"] == {"const": "1.2"}
    assert "selection_binding" in schema["required"]
    assert "toolset_binding" in schema["required"]
    provider = schema["properties"]["provider_acquisition"]
    assert provider["additionalProperties"] is False
    assert set(provider["required"]) == {
        "status",
        "provider_profile_id",
        "runtime_provider_id",
        "trace_adapter",
        "intended_connection_name",
        "active_connection",
        "historical_service",
        "configuration_binding",
        "acquisition_id",
        "lifecycle",
        "historical_request",
        "competing_historical_provider_connections",
        "intended_provider_disconnects",
        "log_timezone_id",
        "log_utc_offset",
    }
    assert "reload_all_historical_data_initiated_at" not in provider["properties"]
    assert "matching_historical_request_observed" not in provider["properties"]
    assert provider["properties"]["provider_profile_id"] == {
        "const": PROVIDER_PROFILE_ID
    }
    assert provider["properties"]["historical_service"]["additionalProperties"] is False
    assert provider["properties"]["configuration_binding"]["properties"]["mode"] == {
        "enum": ["EXPLICIT_PREFERENCE", "UNIQUE_AUTO_ROUTE"]
    }
    assert provider["properties"]["lifecycle"]["additionalProperties"] is False
    historical_request = provider["properties"]["historical_request"]
    assert historical_request["additionalProperties"] is False
    local_request_timestamp = {
        "type": "string",
        "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",
    }
    assert historical_request["properties"]["requested_start"] == (
        local_request_timestamp
    )
    assert historical_request["properties"]["requested_end"] == (
        local_request_timestamp
    )
    instrument = schema["properties"]["contract"]["properties"]
    assert instrument["full_name"] == {
        "type": "string",
        "minLength": 1,
        "pattern": r"^\S(?:.*\S)?$",
    }
    assert instrument["instrument_id"] == {
        "type": "string",
        "minLength": 1,
        "pattern": r"^\S(?:.*\S)?$",
    }


def _matches_routing_schema(value: dict[str, object], schema: dict[str, object]) -> bool:
    variants = schema["oneOf"]
    return (
        sum(
            all(
                value.get(name) == constraint["const"]
                for name, constraint in variant["properties"].items()
            )
            for variant in variants
        )
        == 1
    )


@pytest.mark.parametrize(
    "configuration_binding",
    [
        {
            "mode": "EXPLICIT_PREFERENCE",
            "preferred_future_connection": "Other",
            "preferred_realtime_future_connection": "My NinjaTrader",
            "saved_connection_matches": 1,
        },
        {
            "mode": "UNIQUE_AUTO_ROUTE",
            "preferred_future_connection": "My NinjaTrader",
            "preferred_realtime_future_connection": "My NinjaTrader",
            "saved_connection_matches": 1,
        },
        {
            "mode": "UNIQUE_AUTO_ROUTE",
            "preferred_future_connection": "Unknown",
            "preferred_realtime_future_connection": "Unknown",
            "saved_connection_matches": 0,
        },
    ],
)
def test_provenance_schema_rejects_invalid_routing_mode_bindings(
    configuration_binding: dict[str, object],
) -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "validation"
        / "mnq_5m_multiwindow"
        / "schemas"
        / "provenance.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    routing_schema = schema["properties"]["provider_acquisition"]["properties"][
        "configuration_binding"
    ]

    assert not _matches_routing_schema(configuration_binding, routing_schema)


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


def test_rejects_nearby_december_contract(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        runtime,
        lambda value: (
            value["instrument"].__setitem__("full_name", "MNQ DEC26"),
            value["instrument"].__setitem__("instrument_id", "MNQ DEC26"),
            value["instrument"].__setitem__("expiry_month", 12),
        ),
    )
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
        "Cbi.Connection.ConnectionStatusCallback: status=Connected",
        "Server.HdsClient.Connect",
        "realtime lifecycle observed",
        "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26'",
        "export armed event_time=",
        "exporter initialized",
        "export complete",
    ],
)
def test_rejects_missing_provider_historical_request_chain(
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

    with pytest.raises(
        AcquisitionValidationError,
        match="provider/historical-request|historical RequestBars",
    ):
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
            "2026-06-21 23:56:00.000 "
            "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26' "
            "from='2026/6/21 23:00:00' to='2026/6/23 0:00:00' "
            "period='1 Minute'\n",
            "2026-06-21 23:54:00.000 (Other) Kinetick.Adapter.Connect "
            "status=Connected\n"
            "2026-06-21 23:54:30.000 (Other) Kinetick.Adapter.Disconnect\n"
            "2026-06-21 23:56:00.000 "
            "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26' "
            "from='2026/6/21 23:00:00' to='2026/6/23 0:00:00' "
            "period='1 Minute'\n",
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


def test_accepts_colon_millisecond_timestamps_and_unique_auto_route(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: re.sub(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.(\d+)",
            r"\1:\2",
            text,
            flags=re.MULTILINE,
        ),
    )
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_config",
        lambda text: text.replace(
            "<PreferredFutureConnection>My NinjaTrader</PreferredFutureConnection>",
            "<PreferredFutureConnection>Unknown</PreferredFutureConnection>",
        ).replace(
            "<PreferredRealtimeFutureConnection>My NinjaTrader"
            "</PreferredRealtimeFutureConnection>",
            "<PreferredRealtimeFutureConnection>Unknown"
            "</PreferredRealtimeFutureConnection>",
        ),
    )

    result = finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
    )

    assert result["provider_acquisition"]["configuration_binding"]["mode"] == (
        "UNIQUE_AUTO_ROUTE"
    )
    assert result["provider_acquisition"]["historical_request"][
        "provider_request_period"
    ] == "1 Minute"
    assert result["bar_series"]["value"] == 5


def test_accepts_varying_approved_hds_node_and_unrelated_requests(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)

    def add_unrelated(text: str) -> str:
        return text.replace(
            "hds-us-nt-007.ninjatrader.com",
            "hds-us-nt-123.ninjatrader.com",
        ).replace(
            "2026-06-21 23:56:00.000 ",
            "2026-06-21 23:55:58.000 "
            "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ DEC26' "
            "from='2026/6/21 23:00:00' to='2026/6/23 0:00:00' "
            "period='1 Minute'\n"
            "2026-06-21 23:55:59.000 "
            "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26' "
            "from='2026/6/22 0:00:00' to='2026/6/22 0:00:00' "
            "period='1 Minute'\n"
            "2026-06-21 23:56:00.000 ",
            1,
        )

    _rewrite_evidence_role_text(evidence, "ninjatrader_trace", add_unrelated)

    result = finalize_provenance(
        source_path=source,
        runtime_capture_path=runtime,
        acquisition_evidence_path=evidence,
        exporter_path=exporter,
    )

    assert result["provider_acquisition"]["historical_service"]["host"] == (
        "hds-us-nt-123.ninjatrader.com"
    )
    assert result["provider_acquisition"]["historical_request"]["instrument"] == (
        "MNQ SEP26"
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "2026-06-21 23:56:00.000",
            "2026-06-21 23:45:30.000",
        ),
        (
            "2026-06-21 23:56:00.000",
            "2026-06-22 21:30:59.500",
        ),
        ("instrument='MNQ SEP26'", "instrument='MNQ DEC26'"),
        (
            "from='2026/6/21 23:00:00' to='2026/6/23 0:00:00'",
            "from='2026/6/22 1:00:00' to='2026/6/22 22:00:00'",
        ),
        ("period='1 Minute'", "period='Daily'"),
    ],
)
def test_rejects_nonqualifying_historical_requests(
    tmp_path: Path, old: str, new: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(old, new, 1),
    )

    with pytest.raises(AcquisitionValidationError, match="RequestBars"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_multiple_qualifying_historical_requests(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(
            "2026-06-21 23:56:00.000 ",
            "2026-06-21 23:55:59.000 "
            "Cbi.Instrument.RequestBars (to Provider): instrument='MNQ SEP26' "
            "from='2026/6/21 23:00:00' to='2026/6/23 0:00:00' "
            "period='1 Minute'\n"
            "2026-06-21 23:56:00.000 ",
            1,
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="uniquely qualifying"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    ("target", "replacement", "error"),
    [
        ("Provider31", "Provider99", "intended provider"),
        ("Tradovate.Adapter", "Kinetick.Adapter", "competing historical"),
        (
            "hds-us-nt-007.ninjatrader.com",
            "history.example.invalid",
            "service identity",
        ),
    ],
)
def test_rejects_wrong_provider_profile_evidence(
    tmp_path: Path, target: str, replacement: str, error: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    if target == "Provider31":
        _rewrite_json(
            runtime,
            lambda value: value["active_connections"][0].__setitem__(
                "provider", replacement
            ),
        )
        _refresh_runtime_hash(runtime, evidence)
    else:
        _rewrite_evidence_role_text(
            evidence,
            "ninjatrader_trace",
            lambda text: text.replace(target, replacement),
        )

    with pytest.raises(AcquisitionValidationError, match=error):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_unknown_provider_profile_and_wrong_connection_name(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        evidence,
        lambda value: value.__setitem__("provider_profile_id", "GENERIC_PROVIDER"),
    )
    with pytest.raises(AcquisitionValidationError, match="profile is not approved"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )

    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        evidence,
        lambda value: value.__setitem__("intended_connection_name", "Other"),
    )
    with pytest.raises(
        AcquisitionValidationError, match="approved acquisition connection"
    ):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_intended_provider_disconnect_during_request_cycle(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(
            "2026-06-21 23:56:00.000 ",
            "2026-06-21 23:55:00.000 (My NinjaTrader) "
            "Tradovate.Adapter.Disconnect\n"
            "2026-06-21 23:56:00.000 ",
            1,
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="competing historical"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_ambiguous_unique_auto_route(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)

    def make_ambiguous(text: str) -> str:
        return text.replace(
            "<PreferredFutureConnection>My NinjaTrader</PreferredFutureConnection>",
            "<PreferredFutureConnection>Unknown</PreferredFutureConnection>",
        ).replace(
            "<PreferredRealtimeFutureConnection>My NinjaTrader"
            "</PreferredRealtimeFutureConnection>",
            "<PreferredRealtimeFutureConnection>Unknown"
            "</PreferredRealtimeFutureConnection>",
        ).replace(
            "</NinjaTrader>",
            "<TradovateOptions><Name>My NinjaTrader</Name>"
            "<Provider>Provider31</Provider></TradovateOptions></NinjaTrader>",
        )

    _rewrite_evidence_role_text(evidence, "ninjatrader_config", make_ambiguous)

    with pytest.raises(AcquisitionValidationError, match="ambiguous unique"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_multiple_active_futures_feeds_for_unknown_auto_route(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_config",
        lambda text: text.replace(
            "<PreferredFutureConnection>My NinjaTrader</PreferredFutureConnection>",
            "<PreferredFutureConnection>Unknown</PreferredFutureConnection>",
        ).replace(
            "<PreferredRealtimeFutureConnection>My NinjaTrader"
            "</PreferredRealtimeFutureConnection>",
            "<PreferredRealtimeFutureConnection>Unknown"
            "</PreferredRealtimeFutureConnection>",
        ),
    )
    _rewrite_json(
        runtime,
        lambda value: value["active_connections"].append(
            {
                "name": "Other",
                "provider": "Provider99",
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


def test_rejects_malformed_ninjatrader_timestamp(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(
            "2026-06-21 23:56:00.000 Cbi.Instrument.RequestBars",
            "2026-06-21 23:56:00.BAD Cbi.Instrument.RequestBars",
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="RequestBars timestamp"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


@pytest.mark.parametrize(
    "provider_event",
    [
        "(Other) Kinetick.Adapter.Connect status=Connected",
        "(My NinjaTrader) Tradovate.Adapter.Disconnect",
    ],
)
def test_rejects_malformed_provider_lifecycle_timestamp(
    tmp_path: Path, provider_event: str
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(
            "2026-06-21 23:56:00.000 ",
            f"2026-06-21 23:55:00.BAD {provider_event}\n"
            "2026-06-21 23:56:00.000 ",
            1,
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="provider lifecycle timestamp"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_marker_when_log_and_embedded_chronology_disagree(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(
            "2026-06-21 23:56:30.000 acquisition=acq-001 exporter initialized",
            "2026-06-21 23:47:00.000 acquisition=acq-001 exporter initialized",
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="marker timestamp"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_legacy_arm_marker_alone_for_official_v12(tmp_path: Path) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(
            "export armed event_time=",
            "export armed after reload event_time=",
        ),
    )

    with pytest.raises(AcquisitionValidationError, match="historical-request evidence"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )


def test_rejects_legacy_reload_evidence_and_markers_for_official_v12(
    tmp_path: Path,
) -> None:
    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_json(
        evidence,
        lambda value: value.__setitem__(
            "reload_all_historical_data_initiated_at",
            "2026-06-21T23:55:00+08:00",
        ),
    )
    with pytest.raises(AcquisitionValidationError, match="legacy reload evidence"):
        finalize_provenance(
            source_path=source,
            runtime_capture_path=runtime,
            acquisition_evidence_path=evidence,
            exporter_path=exporter,
        )

    source, runtime, evidence, exporter = _build_bundle(tmp_path)
    _rewrite_evidence_role_text(
        evidence,
        "ninjatrader_trace",
        lambda text: text.replace(
            "realtime lifecycle observed event_time=",
            "awaiting operator arm after Reload All Historical Data event_time=",
        ).replace(
            "export armed event_time=",
            "export armed after reload event_time=",
        ),
    )
    with pytest.raises(AcquisitionValidationError, match="historical-request evidence"):
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
