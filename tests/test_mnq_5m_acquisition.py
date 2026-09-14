from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from tools.validation.mnq_5m_acquisition import (
    AcquisitionValidationError,
    finalize_provenance as _finalize_provenance,
)


PINNED_PRODUCTION_COMMIT = "04a73e1401d44688660b211d9db6918113482856"
COHORT_ID = "mnq-202609-5m-v1"
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
    "provenance_schema": "validation/mnq_5m_multiwindow/schemas/provenance.schema.json",
    "selection_registry_schema": (
        "validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json"
    ),
    "toolset_manifest_schema": "validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json",
    "source_inventory_schema": "validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json",
    "exclusion_ledger_schema": "validation/mnq_5m_multiwindow/schemas/exclusions.schema.json",
}


def finalize_provenance(**kwargs):
    return _finalize_provenance(
        **kwargs,
        trusted_selection_checkpoint=SELECTION_CHECKPOINT,
        trusted_toolset_checkpoint=TOOLSET_CHECKPOINT,
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
            "full_name": "MNQ 09-26",
            "expiry_month": 9,
            "expiry_year": 2026,
            "candidate_date_start": "2026-06-22",
            "candidate_date_end": "2026-07-24",
        },
        "producing_checkpoint": INVENTORY_CHECKPOINT,
        "entries": entries,
    }
    _write_payload(inventory_path, inventory, "aggregate_payload_sha256")

    exclusions = {
        "schema_version": "1.0",
        "status": "FROZEN_PRE_EXECUTION",
        "cohort_id": COHORT_ID,
        "producing_checkpoint": INVENTORY_CHECKPOINT,
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
        "producing_checkpoint": SELECTION_CHECKPOINT,
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
        "schema_version": "1.1",
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

    assert result["schema_version"] == "1.1"
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
    assert result["selection_binding"]["status"] == "FROZEN_FOR_SOURCE_ACQUISITION"
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
        lambda value: value.__setitem__("producing_checkpoint", "5" * 40),
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
        "protocol_spec",
        "provenance_schema",
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
        lambda value: value.__setitem__("producing_checkpoint", "5" * 40),
        lambda value: value["components"].append(deepcopy(value["components"][0])),
        lambda value: value["components"].pop(),
        lambda value: value.__setitem__("status", "PREPARATION_INCOMPLETE"),
        lambda value: value["components"][0].__setitem__(
            "producing_commit", "not-a-commit"
        ),
        lambda value: value["components"][0].__setitem__(
            "producing_commit", "5" * 40
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
        "component-wrong-producing-commit",
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

    assert schema["properties"]["schema_version"] == {"const": "1.1"}
    assert "selection_binding" in schema["required"]
    assert "toolset_binding" in schema["required"]


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
