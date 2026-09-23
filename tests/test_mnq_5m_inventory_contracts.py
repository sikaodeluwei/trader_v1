"""Contract boundaries for the versioned MNQ inventory protocol."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "validation" / "mnq_5m_multiwindow" / "schemas"
SCHEMA_FILES = {
    "inventory": "source_inventory_v2.schema.json",
    "exclusions": "exclusions_v2.schema.json",
    "selection": "selection_registry_v2.schema.json",
    "toolset": "toolset_manifest_v2.schema.json",
    "checkpoint": "checkpoint_attestation_v2.schema.json",
    "provenance": "provenance_v1_3.schema.json",
}
INVENTORY_EVIDENCE_SCHEMA_FILES = {
    "scan": "inventory_scan.schema.json",
    "runtime": "inventory_runtime_capture.schema.json",
    "acquisition": "inventory_acquisition_evidence.schema.json",
    "provenance": "inventory_provenance.schema.json",
}
LEGACY_HASHES = {
    "source_inventory.schema.json": "76665617a84f3250adbdafc4d80c509a0640ab39f5c397daaa17b69de1352f6e",
    "exclusions.schema.json": "6e66d0eb32aadbaf722dc36bdb2c826e64d0d7186353647a0793fb2f2fe0d776",
    "selection_registry.schema.json": "720fc56f5091b783efd8a2702daf606f4865aefd7e88a0ec33f903d009fd2bd5",
    "toolset_manifest.schema.json": "047d8a2116b74939f0191aedcb696915ddc10f689f2ea1d19e9e793353e7456b",
    "checkpoint_attestation.schema.json": "e7f3d4de4c9b4035b7d318a6e2cb02d563b834c67695da3570a153d4d4e8335d",
    "provenance.schema.json": "35b795e60d41de11ff48fa575039c7d4f8c6284b3e37b27c0b16b9eee054cc2b",
}
ROLES = [
    "protocol_spec", "inventory_design_spec", "validation_dependencies", "acquisition_exporter", "acquisition_finalizer", "inventory_scanner", "inventory_common", "inventory_evidence_finalizer", "inventory_calendar_verifier", "inventory_builder", "selection_generator", "selected_source_checker", "checkpoint_verifier", "provenance_schema", "inventory_scan_schema", "inventory_runtime_capture_schema", "inventory_acquisition_evidence_schema", "inventory_provenance_schema", "checkpoint_attestation_schema", "selection_registry_schema", "toolset_manifest_schema", "source_inventory_schema", "exclusion_ledger_schema",
]
ROLE_PATHS = {
    "protocol_spec": "docs/superpowers/specs/2026-09-13-mnq-5m-multiwindow-validation-design.md", "inventory_design_spec": "docs/superpowers/specs/2026-09-16-mnq-5m-official-inventory-scanner-design.md", "validation_dependencies": "requirements-validation.txt", "acquisition_exporter": "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs", "acquisition_finalizer": "tools/validation/mnq_5m_acquisition.py", "inventory_scanner": "tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs", "inventory_common": "tools/validation/mnq_5m_inventory_common.py", "inventory_evidence_finalizer": "tools/validation/mnq_5m_inventory_evidence.py", "inventory_calendar_verifier": "tools/validation/mnq_5m_inventory_calendar.py", "inventory_builder": "tools/validation/mnq_5m_inventory.py", "selection_generator": "tools/validation/mnq_5m_selection.py", "selected_source_checker": "tools/validation/mnq_5m_selected_source_check.py", "checkpoint_verifier": "tools/validation/mnq_5m_checkpoint_verify.py", "provenance_schema": "validation/mnq_5m_multiwindow/schemas/provenance_v1_3.schema.json", "inventory_scan_schema": "validation/mnq_5m_multiwindow/schemas/inventory_scan.schema.json", "inventory_runtime_capture_schema": "validation/mnq_5m_multiwindow/schemas/inventory_runtime_capture.schema.json", "inventory_acquisition_evidence_schema": "validation/mnq_5m_multiwindow/schemas/inventory_acquisition_evidence.schema.json", "inventory_provenance_schema": "validation/mnq_5m_multiwindow/schemas/inventory_provenance.schema.json", "checkpoint_attestation_schema": "validation/mnq_5m_multiwindow/schemas/checkpoint_attestation_v2.schema.json", "selection_registry_schema": "validation/mnq_5m_multiwindow/schemas/selection_registry_v2.schema.json", "toolset_manifest_schema": "validation/mnq_5m_multiwindow/schemas/toolset_manifest_v2.schema.json", "source_inventory_schema": "validation/mnq_5m_multiwindow/schemas/source_inventory_v2.schema.json", "exclusion_ledger_schema": "validation/mnq_5m_multiwindow/schemas/exclusions_v2.schema.json",
}
COMPATIBILITY_REASONS = [
    "INCOMPLETE_PROVENANCE", "FEWER_THAN_250_NATIVE_BARS", "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS", "TRADING_HOURS_INCONSISTENCY", "MALFORMED_OR_NON_FINITE_OHLCV", "INVALID_OHLC_GEOMETRY", "UNEXPECTED_MISSING_BARS", "SOURCE_CORRUPTION", "SOURCE_HASH_MISMATCH", "OUTSIDE_POLICY",
]
SHA = "a" * 64
COMMIT = "b" * 40
ACQUISITION_ID = "dryrun-mnq-202609-5m-inventory-20260622-20260724-v1"
CANONICALIZATION_ID = "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1"


def _load(name: str) -> dict[str, object]:
    return json.loads((SCHEMA_DIR / SCHEMA_FILES[name]).read_text(encoding="utf-8"))


def _load_inventory_evidence(name: str) -> dict[str, object]:
    return json.loads(
        (SCHEMA_DIR / INVENTORY_EVIDENCE_SCHEMA_FILES[name]).read_text(
            encoding="utf-8"
        )
    )


def _transformations() -> dict[str, bool]:
    return {
        "sorted": False,
        "filled": False,
        "interpolated": False,
        "resampled": False,
        "timezone_converted": False,
        "back_adjusted": False,
    }


def _scanner_transformations() -> dict[str, bool]:
    return {
        "sorted": False,
        "deduplicated": False,
        "filled": False,
        "interpolated": False,
        "resampled": False,
        "timezone_converted": False,
        "back_adjusted": False,
        "repaired": False,
    }


def _segment() -> dict[str, str]:
    return {
        "begin_application": "2026-06-21T17:00:00-05:00",
        "end_application": "2026-06-22T16:00:00-05:00",
        "begin_pc": "2026-06-22T06:00:00+08:00",
        "end_pc": "2026-06-23T05:00:00+08:00",
    }


def _schedule(*, has_session: bool) -> dict[str, object]:
    segment = _segment()
    return {
        "holiday_name": None,
        "partial_session": False,
        "expected_open_segments": [segment] if has_session else [],
        "scheduled_breaks": [],
        "application_session_begin": segment["begin_application"] if has_session else None,
        "application_session_end": segment["end_application"] if has_session else None,
        "pc_log_session_begin": segment["begin_pc"] if has_session else None,
        "pc_log_session_end": segment["end_pc"] if has_session else None,
        "effective_schedule_source": (
            "SessionIterator using Bars.TradingHours and ActualTradingDayExchange"
        ),
    }


def _quality() -> dict[str, object]:
    return {
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
        "first_250_source_sha256": SHA,
        "complete_session_source_sha256": "c" * 64,
        "canonicalization_id": CANONICALIZATION_ID,
    }


def _valid_inventory_scan() -> dict[str, object]:
    observations: list[dict[str, object]] = []
    for day in range(22, 31):
        observations.append(
            {
                "civil_date": f"2026-06-{day:02d}",
                "classification": "NO_SESSION",
                "exchange_trading_date": None,
                "schedule_evidence": _schedule(has_session=False),
                "quality": None,
            }
        )
    for day in range(1, 25):
        observations.append(
            {
                "civil_date": f"2026-07-{day:02d}",
                "classification": "NO_SESSION",
                "exchange_trading_date": None,
                "schedule_evidence": _schedule(has_session=False),
                "quality": None,
            }
        )
    observations[0] = {
        "civil_date": "2026-06-22",
        "classification": "SESSION",
        "exchange_trading_date": "2026-06-22",
        "schedule_evidence": _schedule(has_session=True),
        "quality": _quality(),
    }
    return {
        "schema_version": "1.0",
        "acquisition_id": ACQUISITION_ID,
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
        "canonicalization_id": CANONICALIZATION_ID,
        "observations": observations,
        "transformations": _scanner_transformations(),
        "completed_at": "2026-09-16T12:00:00+08:00",
    }


def _timezone() -> dict[str, object]:
    return {
        "id": "Singapore Standard Time",
        "display_name": "(UTC+08:00) Kuala Lumpur, Singapore",
        "standard_name": "Singapore Standard Time",
        "daylight_name": "Singapore Standard Time",
        "base_utc_offset": "+08:00",
        "supports_dst": False,
    }


def _valid_inventory_runtime_capture() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "acquisition_id": ACQUISITION_ID,
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
            "scanner_sha256": None,
            "scanner_sha256_recording_authority": "operator/finalizer",
        },
        "bar_series": {
            "type": "Minute",
            "value": 5,
            "native": True,
            "calculate": "OnBarClose",
        },
        "application_timezone": _timezone(),
        "pc_timezone": _timezone(),
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
                "sha256": SHA,
            },
            "inventory_runtime_capture": {
                "file_name": "inventory_runtime_capture.json",
                "sha256": None,
                "sha256_recording_authority": "operator/finalizer",
            },
            "trading_hours_template": {
                "file_name": "trading_hours_template.xml",
                "sha256": "c" * 64,
            },
            "ninjatrader_config": {
                "file_name": "NinjaTrader.Config.xml",
                "sha256": "d" * 64,
            },
        },
    }


def _evidence_file(role: str, path: str, digest: str) -> dict[str, object]:
    return {"role": role, "path": path, "sha256": digest, "byte_length": 1234}


def _valid_inventory_acquisition_evidence() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "acquisition_id": ACQUISITION_ID,
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
        "lifecycle": {
            "adapter_connection_initiated_at": "2026-09-16T10:59:00+08:00",
            "connection_ready_at": "2026-09-16T10:59:30+08:00",
            "pre_request_realtime_at": "2026-09-16T11:00:00+08:00",
            "request_observed_at": "2026-09-16T11:01:30+08:00",
            "post_request_initialized_at": "2026-09-16T11:02:00+08:00",
            "post_request_realtime_at": "2026-09-16T11:02:01+08:00",
            "inventory_scan_armed_at": "2026-09-16T11:03:00+08:00",
            "inventory_scan_completed_at": "2026-09-16T12:00:01+08:00",
        },
        "evidence_files": [
            _evidence_file("ninjatrader_config", "external/NinjaTrader.Config.xml", "c" * 64),
            _evidence_file("ninjatrader_log", "external/log.txt", "d" * 64),
            _evidence_file("ninjatrader_trace", "external/trace.txt", "e" * 64),
        ],
        "expected_toolset_checkpoint": COMMIT,
        "transformations": _transformations(),
    }


def _valid_inventory_provenance() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "status": "PROVEN",
        "acquisition_id": ACQUISITION_ID,
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
            "acquisition_id": ACQUISITION_ID,
            "lifecycle": _valid_inventory_acquisition_evidence()["lifecycle"],
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
            "session_count": 24,
            "earliest_session_begin": "2026-06-21T17:00:00-05:00",
            "latest_session_end": "2026-07-24T16:00:00-05:00",
            "trading_hours_template_sha256": "c" * 64,
            "calendar_binding_sha256": "9" * 64,
        },
        "artifact_hashes": {
            "inventory_scan": SHA,
            "inventory_runtime_capture": "b" * 64,
            "inventory_acquisition_evidence": "f" * 64,
            "scanner": "8" * 64,
            "trading_hours_template": "c" * 64,
            "ninjatrader_config": "c" * 64,
            "ninjatrader_log": "d" * 64,
            "ninjatrader_trace": "e" * 64,
            "toolset_manifest": "7" * 64,
        },
        "external_evidence": [
            _evidence_file("ninjatrader_config", "external/NinjaTrader.Config.xml", "c" * 64),
            _evidence_file("ninjatrader_log", "external/log.txt", "d" * 64),
            _evidence_file("ninjatrader_trace", "external/trace.txt", "e" * 64),
        ],
        "inventory_scan_binding": {
            "path": "inventory_scan.json",
            "schema_version": "1.0",
            "sha256": SHA,
        },
        "transformations": _transformations(),
        "toolset_binding": {
            "status": "FROZEN_FOR_SOURCE_ACQUISITION",
            "stage": "SOURCE_ACQUISITION",
            "schema_version": "2.0",
            "producing_checkpoint": COMMIT,
            "trusted_checkpoint": COMMIT,
            "pinned_production_hierarchy_commit": (
                "04a73e1401d44688660b211d9db6918113482856"
            ),
            "aggregate_payload_sha256": "a" * 64,
        },
        "checkpoint_verification": {
            "status": "VERIFIED",
            "trusted_toolset_checkpoint": COMMIT,
            "pinned_production_hierarchy_commit": (
                "04a73e1401d44688660b211d9db6918113482856"
            ),
        },
    }


def _require_contracts() -> None:
    if not all((SCHEMA_DIR / filename).is_file() for filename in SCHEMA_FILES.values()):
        pytest.skip("versioned contracts are intentionally absent during RED")


def _policy() -> dict[str, object]:
    return {"contract_label": "MNQ SEP26", "full_name": "MNQ SEP26", "expiry_month": 9, "expiry_year": 2026, "candidate_date_start": "2026-06-22", "candidate_date_end": "2026-07-24"}


def _valid_inventory(*, incomplete: bool = False) -> dict[str, object]:
    return {
        "schema_version": "2.0", "status": "FROZEN_INVENTORY", "cohort_outcome": "COHORT_INCOMPLETE" if incomplete else "READY_FOR_SELECTION", "cohort_id": "mnq-202609-5m-v1", "contract_policy": _policy(),
        "inventory_scan": {"path": "inventory_scan.json", "schema_version": "1.0", "sha256": SHA, "producing_checkpoint": COMMIT}, "inventory_provenance": {"path": "inventory_provenance.json", "schema_version": "1.0", "sha256": SHA, "producing_checkpoint": COMMIT}, "producing_checkpoint": COMMIT, "candidate_count": 1, "eligible_count": 0 if incomplete else 1,
        "entries": [{"trading_date": "2026-07-01", "eligible": not incomplete, "exclusion_reasons": [] if not incomplete else ["FEWER_THAN_250_NATIVE_BARS"], "session_begin_application": "20260630 170000", "session_end_application": "20260701 160000", "observed_native_bar_count": 100 if incomplete else 276, "first_250_source_sha256": None if incomplete else SHA, "complete_session_source_sha256": "b" * 64}], "aggregate_payload_sha256": SHA,
    }


def _bound_artifact(path: str) -> dict[str, str]:
    return {"path": path, "bundle_path": path, "schema_version": "2.0", "sha256": SHA, "producing_checkpoint": COMMIT}


def _toolset_document() -> dict[str, object]:
    return {"schema_version": "2.0", "stage": "SOURCE_ACQUISITION", "status": "FROZEN_FOR_SOURCE_ACQUISITION", "cohort_id": "mnq-202609-5m-v1", "producing_checkpoint": COMMIT, "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856", "runtime": {"implementation": "CPython", "version": "3.12", "dependencies": [{"name": "jsonschema", "version": "4.25.1"}]}, "canonicalization": "JSON_UTF8_SORTED_KEYS_COMPACT_EXCLUDE_AGGREGATE_PAYLOAD_SHA256", "components": [{"role": role, "path": ROLE_PATHS[role], "bundle_path": ROLE_PATHS[role], "sha256": SHA, "producing_commit": COMMIT} for role in ROLES], "deferred_components": ["independent_oracle", "blind_project_runner", "comparator", "cohort_aggregator"], "aggregate_payload_sha256": SHA}


@pytest.mark.parametrize("filename", SCHEMA_FILES.values())
def test_versioned_schema_file_is_present_before_contract_assertions(filename: str) -> None:
    """Removing a versioned contract must fail its contract test."""
    schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_versioned_schemas_have_unique_draft_2020_12_ids_and_versions() -> None:
    _require_contracts()
    schemas = {name: _load(name) for name in SCHEMA_FILES}
    assert {schema["$schema"] for schema in schemas.values()} == {"https://json-schema.org/draft/2020-12/schema"}
    assert [schemas[name]["properties"]["schema_version"] for name in SCHEMA_FILES] == [{"const": "2.0"}] * 5 + [{"const": "1.3"}]
    ids = [schema["$id"] for schema in schemas.values()]
    assert len(ids) == len(set(ids)) == 6
    for filename, schema_id in zip(SCHEMA_FILES.values(), ids):
        assert schema_id.endswith(filename)
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)


def test_source_inventory_v2_accepts_ready_and_short_incomplete_cohorts() -> None:
    _require_contracts()
    inventory = _load("inventory")
    assert inventory["required"] == ["schema_version", "status", "cohort_outcome", "cohort_id", "contract_policy", "inventory_scan", "inventory_provenance", "producing_checkpoint", "candidate_count", "eligible_count", "entries", "aggregate_payload_sha256"]
    assert inventory["properties"]["cohort_outcome"]["enum"] == ["READY_FOR_SELECTION", "COHORT_INCOMPLETE"]
    assert "minItems" not in inventory["properties"]["entries"]
    validator = Draft202012Validator(inventory)
    assert not list(validator.iter_errors(_valid_inventory()))
    incomplete = _valid_inventory(incomplete=True)
    assert len(incomplete["entries"]) < 10
    assert not list(validator.iter_errors(incomplete))
    assert inventory["$defs"]["entry"]["required"] == ["trading_date", "eligible", "exclusion_reasons", "session_begin_application", "session_end_application", "observed_native_bar_count", "first_250_source_sha256", "complete_session_source_sha256"]


def test_exclusions_v2_preserves_compatibility_and_limits_normal_emission() -> None:
    _require_contracts()
    exclusions = _load("exclusions")
    assert exclusions["properties"]["schema_version"] == {"const": "2.0"}
    assert exclusions["$defs"]["exclusion_reason"]["enum"] == COMPATIBILITY_REASONS
    assert exclusions["$defs"]["normally_emitted_exclusion_reason"]["enum"] == COMPATIBILITY_REASONS[:8]
    document = {"schema_version": "2.0", "status": "FROZEN_INVENTORY", "cohort_outcome": "COHORT_INCOMPLETE", "cohort_id": "mnq-202609-5m-v1", "source_inventory_sha256": SHA, "producing_checkpoint": COMMIT, "entries": [{"trading_date": "2026-07-01", "reasons": ["FEWER_THAN_250_NATIVE_BARS"]}], "aggregate_payload_sha256": SHA}
    assert not list(Draft202012Validator(exclusions).iter_errors(document))


def test_selection_registry_v2_binds_v2_inventory_and_exclusions_to_inventory_checkpoint() -> None:
    _require_contracts()
    selection = _load("selection")
    assert selection["properties"]["schema_version"] == {"const": "2.0"}
    assert "trusted_inventory_checkpoint" in selection["required"]
    document = {"schema_version": "2.0", "status": "FROZEN_FOR_SOURCE_ACQUISITION", "cohort_id": "mnq-202609-5m-v1", "contract_policy": _policy(), "selection_algorithm": {"id": "CHRONOLOGICAL_TEN_STRATA_EARLIEST", "version": "1.0", "stratum_count": 10}, "selection_count": 10, "source_inventory": _bound_artifact("source_inventory.json"), "exclusion_ledger": _bound_artifact("exclusions.json"), "trusted_inventory_checkpoint": COMMIT, "producing_checkpoint": COMMIT, "selection_influence": {"hierarchy_output_used": False, "oracle_output_used": False, "project_output_used": False}, "selections": [{"case_id": "mnq-202609-5m-td2026-07-01-w01", "trading_date": "2026-07-01", "stratum_number": number, "stratum_start_index": number - 1, "stratum_end_index": number - 1, "selected_eligible_index": number - 1, "window_policy": "FIRST_250_NATIVE_5M_SESSION_BARS"} for number in range(1, 11)], "aggregate_payload_sha256": SHA}
    assert not list(Draft202012Validator(selection).iter_errors(document))


def test_toolset_manifest_v2_has_only_the_approved_23_roles() -> None:
    _require_contracts()
    toolset = _load("toolset")
    components = toolset["properties"]["components"]
    assert components["minItems"] == components["maxItems"] == 23
    assert toolset["$defs"]["component"]["properties"]["role"]["enum"] == ROLES
    document = _toolset_document()
    validator = Draft202012Validator(toolset)
    assert not list(validator.iter_errors(document))
    for count in (22, 24):
        altered = copy.deepcopy(document)
        altered["components"] = altered["components"][:count]
        if count == 24:
            altered["components"].append(copy.deepcopy(altered["components"][0]))
        assert list(validator.iter_errors(altered))


def _checkpoint(stage: str) -> dict[str, object]:
    document: dict[str, object] = {"schema_version": "2.0", "stage": stage, "status": "VERIFIED", "repository": {"identity": "sikaodeluwei/trader_v1", "git_object_format": "sha1"}, "trusted_toolset_checkpoint": COMMIT, "trusted_inventory_checkpoint": COMMIT, "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856", "artifacts": [{"role": "inventory", "stage": "inventory", "repository_path": "inventory.json", "checkpoint": COMMIT, "git_object_id": COMMIT, "sha256": SHA, "bundle_sha256": SHA}], "ancestry": [{"ancestor": COMMIT, "descendant": COMMIT, "verified": True}, {"ancestor": COMMIT, "descendant": COMMIT, "verified": True}], "remote_publication": {"status": "NOT_CHECKED"}, "verifier": {"version": "2.0", "repository_path": "tools/validation/mnq_5m_checkpoint_verify.py", "producing_commit": COMMIT, "frozen_sha256": SHA, "executing_sha256": SHA}, "attestation_sha256": SHA}
    if stage == "SELECTION":
        document["trusted_selection_checkpoint"] = COMMIT
    return document


def test_checkpoint_attestation_v2_has_inventory_selection_trust_conditions() -> None:
    _require_contracts()
    checkpoint = _load("checkpoint")
    assert checkpoint["properties"]["stage"]["enum"] == ["INVENTORY", "SELECTION"]
    assert checkpoint["properties"]["artifacts"]["items"]["$ref"] == "#/$defs/artifact"
    assert checkpoint["$defs"]["artifact"]["properties"]["stage"]["enum"] == ["toolset", "inventory", "selection"]
    validator = Draft202012Validator(checkpoint)
    assert not list(validator.iter_errors(_checkpoint("INVENTORY")))
    assert not list(validator.iter_errors(_checkpoint("SELECTION")))
    bad_inventory = _checkpoint("INVENTORY")
    bad_inventory["trusted_selection_checkpoint"] = COMMIT
    assert list(validator.iter_errors(bad_inventory))
    bad_selection = _checkpoint("SELECTION")
    del bad_selection["trusted_selection_checkpoint"]
    assert list(validator.iter_errors(bad_selection))


def test_provenance_v1_3_preserves_selected_case_semantics_and_v2_bindings() -> None:
    _require_contracts()
    provenance = _load("provenance")
    assert provenance["properties"]["schema_version"] == {"const": "1.3"}
    assert "trusted_inventory_checkpoint" in provenance["required"]
    assert "selected_source_binding" in provenance["required"]
    selected = provenance["properties"]["selected_source_binding"]
    assert selected["required"] == ["expected_sha256", "observed_sha256"]
    assert selected["properties"]["expected_sha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert selected["properties"]["observed_sha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert provenance["properties"]["checkpoint_verification"]["$ref"] == "checkpoint_attestation_v2.schema.json"
    assert provenance["properties"]["provider_acquisition"] == {"$ref": "provenance.schema.json#/properties/provider_acquisition"}
    legacy = json.loads((SCHEMA_DIR / "provenance.schema.json").read_text(encoding="utf-8"))
    provider = legacy["properties"]["provider_acquisition"]["properties"]
    assert provider["runtime_provider_id"] == {"const": "Provider31"}
    assert provider["trace_adapter"] == {"const": "Tradovate.Adapter"}
    assert provider["intended_connection_name"] == {"const": "My NinjaTrader"}
    assert legacy["properties"]["bar_series"]["properties"]["type"] == {"const": "Minute"}
    assert legacy["properties"]["bar_series"]["properties"]["value"] == {"const": 5}
    assert legacy["properties"]["source"]["properties"]["row_count"] == {"const": 250}


def test_legacy_schema_bytes_are_frozen_and_v1_documents_do_not_cross_v2_boundary() -> None:
    _require_contracts()
    for filename, expected_hash in LEGACY_HASHES.items():
        assert hashlib.sha256((SCHEMA_DIR / filename).read_bytes()).hexdigest() == expected_hash
    for name in SCHEMA_FILES:
        legacy_version = "1.2" if name == "provenance" else "1.0"
        assert list(Draft202012Validator(_load(name)).iter_errors({"schema_version": legacy_version}))


def test_toolset_v2_enforces_exact_ordered_roles_and_repository_paths() -> None:
    toolset = _load("toolset")
    validator = Draft202012Validator(toolset)
    valid = _toolset_document()
    assert not list(validator.iter_errors(valid))
    duplicate = copy.deepcopy(valid)
    duplicate["components"][1] = copy.deepcopy(duplicate["components"][0])
    assert list(validator.iter_errors(duplicate))
    reordered = copy.deepcopy(valid)
    reordered["components"][0], reordered["components"][1] = reordered["components"][1], reordered["components"][0]
    assert list(validator.iter_errors(reordered))
    legacy_path = copy.deepcopy(valid)
    legacy_path["components"][13]["path"] = "validation/mnq_5m_multiwindow/schemas/provenance.schema.json"
    assert list(validator.iter_errors(legacy_path))
    plan_path = copy.deepcopy(valid)
    plan_path["components"][0]["path"] = "docs/superpowers/plans/2026-09-16-mnq-5m-official-inventory-scanner-implementation-plan.md"
    assert list(validator.iter_errors(plan_path))
    for invalid_component in ({}, "not-a-component"):
        malformed = copy.deepcopy(valid)
        malformed["components"][0] = invalid_component
        assert list(validator.iter_errors(malformed))
    for missing_field in ("sha256", "producing_commit"):
        malformed = copy.deepcopy(valid)
        del malformed["components"][0][missing_field]
        assert list(validator.iter_errors(malformed))


def test_source_inventory_hash_nullability_tracks_serializability_and_defects() -> None:
    validator = Draft202012Validator(_load("inventory"))
    nonserializable = _valid_inventory(incomplete=True)
    entry = nonserializable["entries"][0]
    entry["observed_native_bar_count"] = 276
    entry["complete_session_source_sha256"] = None
    entry["exclusion_reasons"] = ["SOURCE_CORRUPTION"]
    assert not list(validator.iter_errors(nonserializable))
    impossible_first_hash = copy.deepcopy(nonserializable)
    impossible_first_hash["entries"][0]["observed_native_bar_count"] = 100
    impossible_first_hash["entries"][0]["first_250_source_sha256"] = SHA
    assert list(validator.iter_errors(impossible_first_hash))
    invalid_complete_null = _valid_inventory(incomplete=True)
    invalid_complete_null["entries"][0]["complete_session_source_sha256"] = None
    assert list(validator.iter_errors(invalid_complete_null))
    impossible_missing_first_hash = _valid_inventory(incomplete=True)
    entry = impossible_missing_first_hash["entries"][0]
    entry["observed_native_bar_count"] = 276
    entry["exclusion_reasons"] = ["INVALID_OHLC_GEOMETRY"]
    assert list(validator.iter_errors(impossible_missing_first_hash))


def test_toolset_and_provenance_keep_selected_source_stage_status() -> None:
    toolset = _load("toolset")
    provenance = _load("provenance")
    assert toolset["properties"]["stage"] == {"const": "SOURCE_ACQUISITION"}
    assert toolset["properties"]["status"] == {"const": "FROZEN_FOR_SOURCE_ACQUISITION"}
    binding = provenance["$defs"]["toolset_binding"]["properties"]
    assert binding["stage"] == {"const": "SOURCE_ACQUISITION"}
    assert binding["status"] == {"const": "FROZEN_FOR_SOURCE_ACQUISITION"}


def _legacy_documents() -> dict[str, dict[str, object]]:
    policy = _policy()
    legacy_components = [
        ("protocol_spec", "docs/superpowers/specs/2026-09-13-mnq-5m-multiwindow-validation-design.md"), ("acquisition_exporter", "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs"), ("acquisition_finalizer", "tools/validation/mnq_5m_acquisition.py"), ("checkpoint_verifier", "tools/validation/mnq_5m_checkpoint_verify.py"), ("provenance_schema", "validation/mnq_5m_multiwindow/schemas/provenance.schema.json"), ("checkpoint_attestation_schema", "validation/mnq_5m_multiwindow/schemas/checkpoint_attestation.schema.json"), ("selection_registry_schema", "validation/mnq_5m_multiwindow/schemas/selection_registry.schema.json"), ("toolset_manifest_schema", "validation/mnq_5m_multiwindow/schemas/toolset_manifest.schema.json"), ("source_inventory_schema", "validation/mnq_5m_multiwindow/schemas/source_inventory.schema.json"), ("exclusion_ledger_schema", "validation/mnq_5m_multiwindow/schemas/exclusions.schema.json"),
    ]
    inventory = {"schema_version": "1.0", "status": "FROZEN_PRE_EXECUTION", "cohort_id": "mnq-202609-5m-v1", "contract_policy": policy, "producing_checkpoint": COMMIT, "entries": [{"trading_date": f"2026-07-{day:02d}", "eligible": True, "exclusion_reasons": []} for day in range(1, 11)], "aggregate_payload_sha256": SHA}
    exclusions = {"schema_version": "1.0", "status": "FROZEN_PRE_EXECUTION", "cohort_id": "mnq-202609-5m-v1", "producing_checkpoint": COMMIT, "entries": [], "aggregate_payload_sha256": SHA}
    selection = {"schema_version": "1.0", "status": "FROZEN_FOR_SOURCE_ACQUISITION", "cohort_id": "mnq-202609-5m-v1", "contract_policy": policy, "selection_algorithm": {"id": "CHRONOLOGICAL_TEN_STRATA_EARLIEST", "version": "1.0", "stratum_count": 10}, "selection_count": 10, "source_inventory": {"path": "source_inventory.json", "bundle_path": "source_inventory.json", "schema_version": "1.0", "sha256": SHA, "producing_checkpoint": COMMIT}, "exclusion_ledger": {"path": "exclusions.json", "bundle_path": "exclusions.json", "schema_version": "1.0", "sha256": SHA, "producing_checkpoint": COMMIT}, "producing_checkpoint": COMMIT, "selection_influence": {"hierarchy_output_used": False, "oracle_output_used": False, "project_output_used": False}, "selections": [{"case_id": f"mnq-202609-5m-td2026-07-{day:02d}-w{day:02d}", "trading_date": f"2026-07-{day:02d}", "stratum_number": day, "stratum_start_index": day - 1, "stratum_end_index": day - 1, "selected_eligible_index": day - 1, "window_policy": "FIRST_250_NATIVE_5M_SESSION_BARS"} for day in range(1, 11)], "aggregate_payload_sha256": SHA}
    toolset = {"schema_version": "1.0", "stage": "SOURCE_ACQUISITION", "status": "FROZEN_FOR_SOURCE_ACQUISITION", "cohort_id": "mnq-202609-5m-v1", "producing_checkpoint": COMMIT, "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856", "runtime": {"implementation": "CPython", "version": "3.12", "dependencies": [{"name": "jsonschema", "version": "4.25.1"}]}, "canonicalization": "JSON_UTF8_SORTED_KEYS_COMPACT_EXCLUDE_AGGREGATE_PAYLOAD_SHA256", "components": [{"role": role, "path": path, "bundle_path": path, "sha256": SHA, "producing_commit": COMMIT} for role, path in legacy_components], "deferred_components": ["independent_oracle", "blind_project_runner", "comparator", "cohort_aggregator"], "aggregate_payload_sha256": SHA}
    checkpoint = {"schema_version": "1.0", "status": "VERIFIED", "repository": {"identity": "sikaodeluwei/trader_v1", "git_object_format": "sha1"}, "trusted_toolset_checkpoint": COMMIT, "trusted_selection_checkpoint": COMMIT, "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856", "artifacts": [{"role": "toolset", "stage": "toolset", "repository_path": "toolset.json", "checkpoint": COMMIT, "git_object_id": COMMIT, "sha256": SHA, "bundle_sha256": SHA}], "ancestry": [{"ancestor": COMMIT, "descendant": COMMIT, "verified": True}, {"ancestor": COMMIT, "descendant": COMMIT, "verified": True}], "remote_publication": {"status": "NOT_CHECKED"}, "verifier": {"version": "1.0", "repository_path": "tools/validation/mnq_5m_checkpoint_verify.py", "producing_commit": COMMIT, "frozen_sha256": SHA, "executing_sha256": SHA}, "attestation_sha256": SHA}
    provenance = {"schema_version": "1.2", "cohort_id": "mnq-202609-5m-v1", "case_id": "mnq-202609-5m-td2026-07-01-w01", "contract": {"full_name": "MNQ SEP26", "contract_label": "MNQ SEP26", "master_name": "MNQ", "instrument_id": "MNQ SEP26", "expiry_month": 9, "expiry_year": 2026, "exchange": "CME"}, "ninjatrader_version": "8", "provider_acquisition": {"status": "PROVEN", "provider_profile_id": "NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1", "runtime_provider_id": "Provider31", "trace_adapter": "Tradovate.Adapter", "intended_connection_name": "My NinjaTrader", "active_connection": {"name": "My NinjaTrader", "provider": "Provider31", "status": "Connected", "price_status": "Connected", "instrument_types": ["Future"]}, "historical_service": {"name": "NinjaTrader HDS", "host": "hds-us-nt-1.ninjatrader.com", "port": 443, "use_ssl": True, "connected_at": "2026-07-01T00:00:00Z"}, "configuration_binding": {"mode": "EXPLICIT_PREFERENCE", "preferred_future_connection": "My NinjaTrader", "preferred_realtime_future_connection": "My NinjaTrader", "saved_connection_matches": 1}, "acquisition_id": "acq", "lifecycle": {key: "2026-07-01T00:00:00Z" for key in ["adapter_connection_initiated_at", "connection_ready_at", "pre_request_realtime_at", "post_request_initialized_at", "post_request_realtime_at", "export_armed_at", "export_completed_at"]}, "historical_request": {"source_role": "ninjatrader_trace", "observed_at": "2026-07-01T00:00:00Z", "instrument": "MNQ SEP26", "requested_start": "2026-06-30T17:00:00", "requested_end": "2026-07-01T16:00:00", "provider_request_period": "1 Minute", "covers_declared_session": True}, "competing_historical_provider_connections": 0, "intended_provider_disconnects": 0, "log_timezone_id": "UTC", "log_utc_offset": "+00:00"}, "application_timezone": {"id": "UTC", "display_name": "UTC", "standard_name": "UTC", "daylight_name": "UTC", "base_utc_offset": "+00:00", "supports_dst": False, "source_timestamp_offsets": [{"first_timestamp": "a", "last_timestamp": "b", "utc_offset": "+00:00"}]}, "pc_log_timezone": {"id": "UTC", "base_utc_offset": "+00:00", "supports_dst": False, "acquisition_event_offsets": [{"event": event, "timestamp": "2026-07-01T00:00:00Z", "utc_offset": "+00:00"} for event in ["initialized", "armed", "exported"]]}, "trading_hours": {"name": "CME US Index Futures ETH", "timezone_id": "UTC", "definition_sha256": SHA, "holiday_configuration_captured": True, "session_calendar": [{"trading_date": "2026-07-01", "segments": [{"begin_application": "a", "end_application": "b", "begin_pc": "a", "end_pc": "b"}], "holiday_name": None, "partial_holiday": None}]}, "bar_series": {"type": "Minute", "value": 5, "native": True, "timestamp_semantics": "session"}, "source": {"filename": "bars.txt", "trading_date": "2026-07-01", "first_timestamp": "a", "last_timestamp": "b", "row_count": 250, "sha256": SHA, "original_source_sha256": SHA, "frozen_case_sha256": SHA, "exported_at": "2026-07-01T00:00:00Z", "export_method": "export", "original_export_identity": "id", "selected_row_derivation": "first 250 native 5-minute bars of the declared Trading Hours session", "known_missing_bars": [], "scheduled_exclusions": [], "known_limitations": []}, "artifact_hashes": {key: SHA for key in ["source", "runtime_capture", "acquisition_evidence", "exporter", "ninjatrader_trace", "ninjatrader_log", "ninjatrader_config", "trading_hours_template", "selection_registry", "toolset_manifest"]}, "selection_binding": {"status": "FROZEN_FOR_SOURCE_ACQUISITION", "producing_checkpoint": COMMIT, "trusted_checkpoint": COMMIT, "aggregate_payload_sha256": SHA, "selection": selection["selections"][0], "inventory": {"path": "source_inventory.json", "schema_version": "1.0", "sha256": SHA, "producing_checkpoint": COMMIT}, "exclusion_ledger": {"path": "exclusions.json", "schema_version": "1.0", "sha256": SHA, "producing_checkpoint": COMMIT}}, "toolset_binding": {"status": "FROZEN_FOR_SOURCE_ACQUISITION", "stage": "SOURCE_ACQUISITION", "producing_checkpoint": COMMIT, "trusted_checkpoint": COMMIT, "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856", "aggregate_payload_sha256": SHA}, "checkpoint_verification": checkpoint, "source_quality_findings": [], "transformations": {"sorted": False, "filled": False, "interpolated": False, "resampled": False, "timezone_converted": False, "back_adjusted": False}, "approved_policy": {"contract": "MNQ September 2026", "candidate_date_start": "2026-06-22", "candidate_date_end": "2026-07-24", "single_expiry_only": True, "existing_frozen_5m_case_excluded": True, "june_rollover_transition_excluded": True}}
    return {"inventory": inventory, "exclusions": exclusions, "selection": selection, "toolset": toolset, "checkpoint": checkpoint, "provenance": provenance}


def test_representative_documents_respect_legacy_v2_boundaries_and_local_provenance_resolution() -> None:
    legacy = _legacy_documents()
    legacy_names = {"inventory": "source_inventory.schema.json", "exclusions": "exclusions.schema.json", "selection": "selection_registry.schema.json", "toolset": "toolset_manifest.schema.json", "checkpoint": "checkpoint_attestation.schema.json", "provenance": "provenance.schema.json"}
    registry = Registry().with_resources([(json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))["$id"], Resource.from_contents(json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8")))) for name in legacy_names.values()] + [(_load("checkpoint")["$id"], Resource.from_contents(_load("checkpoint")))])
    for name, filename in legacy_names.items():
        assert not list(Draft202012Validator(json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8")), registry=registry).iter_errors(legacy[name]))
        assert list(Draft202012Validator(_load(name), registry=registry).iter_errors(legacy[name]))
    v2_provenance = copy.deepcopy(legacy["provenance"])
    v2_provenance.update({"schema_version": "1.3", "inventory_binding": _bound_artifact("source_inventory.json"), "exclusion_binding": _bound_artifact("exclusions.json"), "trusted_inventory_checkpoint": COMMIT, "selected_source_binding": {"expected_sha256": SHA, "observed_sha256": SHA}})
    v2_provenance["selection_binding"]["inventory"] = _bound_artifact("source_inventory.json")
    v2_provenance["selection_binding"]["exclusion_ledger"] = _bound_artifact("exclusions.json")
    for binding in (v2_provenance["inventory_binding"], v2_provenance["exclusion_binding"], v2_provenance["selection_binding"]["inventory"], v2_provenance["selection_binding"]["exclusion_ledger"]):
        binding.pop("bundle_path")
    v2_provenance["toolset_binding"]["schema_version"] = "2.0"
    v2_provenance["checkpoint_verification"] = _checkpoint("SELECTION")
    assert not list(Draft202012Validator(_load("provenance"), registry=registry).iter_errors(v2_provenance))
    assert list(Draft202012Validator(json.loads((SCHEMA_DIR / "provenance.schema.json").read_text(encoding="utf-8")), registry=registry).iter_errors(v2_provenance))


def test_representative_v2_documents_are_valid_only_for_versioned_contracts() -> None:
    legacy_names = {
        "inventory": "source_inventory.schema.json",
        "exclusions": "exclusions.schema.json",
        "selection": "selection_registry.schema.json",
        "toolset": "toolset_manifest.schema.json",
        "checkpoint": "checkpoint_attestation.schema.json",
    }
    selection = copy.deepcopy(_legacy_documents()["selection"])
    selection.update({
        "schema_version": "2.0",
        "source_inventory": _bound_artifact("source_inventory.json"),
        "exclusion_ledger": _bound_artifact("exclusions.json"),
        "trusted_inventory_checkpoint": COMMIT,
    })
    documents = {
        "inventory": _valid_inventory(),
        "exclusions": {
            "schema_version": "2.0", "status": "FROZEN_INVENTORY",
            "cohort_outcome": "COHORT_INCOMPLETE", "cohort_id": "mnq-202609-5m-v1",
            "source_inventory_sha256": SHA, "producing_checkpoint": COMMIT,
            "entries": [{"trading_date": "2026-07-01", "reasons": ["FEWER_THAN_250_NATIVE_BARS"]}],
            "aggregate_payload_sha256": SHA,
        },
        "selection": selection,
        "toolset": _toolset_document(),
        "checkpoint": _checkpoint("INVENTORY"),
    }
    for name, document in documents.items():
        assert not list(Draft202012Validator(_load(name)).iter_errors(document))
        legacy_schema = json.loads((SCHEMA_DIR / legacy_names[name]).read_text(encoding="utf-8"))
        assert list(Draft202012Validator(legacy_schema).iter_errors(document))


@pytest.mark.parametrize("filename", INVENTORY_EVIDENCE_SCHEMA_FILES.values())
def test_inventory_evidence_schema_file_is_present(filename: str) -> None:
    schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_inventory_evidence_schemas_are_strict_unique_draft_2020_12_contracts() -> None:
    schemas = {
        name: _load_inventory_evidence(name)
        for name in INVENTORY_EVIDENCE_SCHEMA_FILES
    }
    assert [schema["properties"]["schema_version"] for schema in schemas.values()] == [
        {"const": "1.0"}
    ] * 4
    schema_ids = [schema["$id"] for schema in schemas.values()]
    assert len(schema_ids) == len(set(schema_ids)) == 4
    repository_schema_ids = [
        json.loads(path.read_text(encoding="utf-8"))["$id"]
        for path in SCHEMA_DIR.glob("*.schema.json")
    ]
    assert len(repository_schema_ids) == len(set(repository_schema_ids))
    for filename, schema_id in zip(INVENTORY_EVIDENCE_SCHEMA_FILES.values(), schema_ids):
        assert schema_id.endswith(filename)
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)


def test_every_owned_inventory_evidence_object_rejects_additional_properties() -> None:
    def assert_strict_objects(node: object, path: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, path
            for key, value in node.items():
                assert_strict_objects(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                assert_strict_objects(value, f"{path}/{index}")

    for name in INVENTORY_EVIDENCE_SCHEMA_FILES:
        assert_strict_objects(_load_inventory_evidence(name), name)


@pytest.mark.parametrize(
    ("schema_name", "document_factory"),
    [
        ("scan", _valid_inventory_scan),
        ("runtime", _valid_inventory_runtime_capture),
        ("acquisition", _valid_inventory_acquisition_evidence),
        ("provenance", _valid_inventory_provenance),
    ],
)
def test_inventory_evidence_schemas_accept_exact_documents_and_reject_unknown_fields(
    schema_name: str, document_factory: object
) -> None:
    schema = _load_inventory_evidence(schema_name)
    validator = Draft202012Validator(schema)
    document = document_factory()
    assert not list(validator.iter_errors(document))
    document["unknown_field"] = "not allowed"
    assert list(validator.iter_errors(document))


def test_inventory_scan_contract_matches_scanner_and_rejects_policy_or_raw_rows() -> None:
    schema = _load_inventory_evidence("scan")
    validator = Draft202012Validator(schema)
    valid = _valid_inventory_scan()
    assert schema["required"] == [
        "schema_version",
        "acquisition_id",
        "cohort_id",
        "contract",
        "bar_series",
        "trading_hours",
        "civil_date_start",
        "civil_date_end",
        "canonicalization_id",
        "observations",
        "transformations",
        "completed_at",
    ]
    assert not list(validator.iter_errors(valid))

    for forbidden_field in (
        "raw_ohlcv",
        "bars",
        "eligible",
        "exclusion_reasons",
        "hierarchy_output",
        "oracle_output",
        "project_output",
        "comparator_output",
        "trend_state",
        "strategy_output",
        "pnl",
        "selection_result",
    ):
        altered = copy.deepcopy(valid)
        altered[forbidden_field] = []
        assert list(validator.iter_errors(altered)), forbidden_field

    absent_coverage = copy.deepcopy(valid)
    absent_coverage["observations"].pop()
    assert list(validator.iter_errors(absent_coverage))

    missing_canonicalization = copy.deepcopy(valid)
    del missing_canonicalization["canonicalization_id"]
    assert list(validator.iter_errors(missing_canonicalization))

    raw_rows_nested = copy.deepcopy(valid)
    raw_rows_nested["observations"][0]["raw_ohlcv"] = [[1, 2, 3, 4, 5]]
    assert list(validator.iter_errors(raw_rows_nested))


def test_inventory_scan_distinguishes_no_session_and_session_quality_shapes() -> None:
    validator = Draft202012Validator(_load_inventory_evidence("scan"))
    valid = _valid_inventory_scan()
    assert not list(validator.iter_errors(valid))

    bad_no_session = copy.deepcopy(valid)
    bad_no_session["observations"][1]["quality"] = _quality()
    assert list(validator.iter_errors(bad_no_session))

    bad_session = copy.deepcopy(valid)
    bad_session["observations"][0]["quality"] = None
    assert list(validator.iter_errors(bad_session))

    bad_quality_hash = copy.deepcopy(valid)
    bad_quality_hash["observations"][0]["quality"]["first_250_source_sha256"] = "A" * 64
    assert list(validator.iter_errors(bad_quality_hash))


def test_inventory_runtime_capture_is_facts_only_and_uses_strict_hashes() -> None:
    validator = Draft202012Validator(_load_inventory_evidence("runtime"))
    valid = _valid_inventory_runtime_capture()
    assert not list(validator.iter_errors(valid))

    invalid_hash = copy.deepcopy(valid)
    invalid_hash["artifact_hashes"]["inventory_scan"]["sha256"] = "not-a-sha"
    assert list(validator.iter_errors(invalid_hash))

    provider_claim = copy.deepcopy(valid)
    provider_claim["provider_proven"] = True
    assert list(validator.iter_errors(provider_claim))

    provider_claim_nested = copy.deepcopy(valid)
    provider_claim_nested["active_connections"][0]["historical_service"] = "NinjaTrader HDS"
    assert list(validator.iter_errors(provider_claim_nested))


def test_acquisition_evidence_requires_exact_provider_linkage_and_external_evidence() -> None:
    validator = Draft202012Validator(_load_inventory_evidence("acquisition"))
    valid = _valid_inventory_acquisition_evidence()
    assert not list(validator.iter_errors(valid))

    for missing in ("intended_provider", "intended_connection_name", "historical_trigger"):
        altered = copy.deepcopy(valid)
        del altered[missing]
        assert list(validator.iter_errors(altered)), missing

    for missing in ("role", "path", "sha256", "byte_length"):
        altered = copy.deepcopy(valid)
        del altered["evidence_files"][0][missing]
        assert list(validator.iter_errors(altered)), missing

    invalid_sha = copy.deepcopy(valid)
    invalid_sha["evidence_files"][0]["sha256"] = "C" * 64
    assert list(validator.iter_errors(invalid_sha))


@pytest.mark.parametrize(
    ("schema_name", "document_factory", "evidence_field"),
    [
        ("acquisition", _valid_inventory_acquisition_evidence, "evidence_files"),
        ("provenance", _valid_inventory_provenance, "external_evidence"),
    ],
)
@pytest.mark.parametrize(
    "required_role",
    ["ninjatrader_config", "ninjatrader_log", "ninjatrader_trace"],
)
def test_required_external_evidence_role_cardinality_is_exactly_one(
    schema_name: str,
    document_factory: object,
    evidence_field: str,
    required_role: str,
) -> None:
    validator = Draft202012Validator(_load_inventory_evidence(schema_name))
    valid = document_factory()
    assert not list(validator.iter_errors(valid))

    omitted = copy.deepcopy(valid)
    omitted[evidence_field] = [
        item for item in omitted[evidence_field] if item["role"] != required_role
    ]
    assert list(validator.iter_errors(omitted))

    duplicate_substitution = copy.deepcopy(valid)
    items = duplicate_substitution[evidence_field]
    missing_index = next(
        index for index, item in enumerate(items) if item["role"] == required_role
    )
    replacement_index = 0 if missing_index != 0 else 1
    items[missing_index] = copy.deepcopy(items[replacement_index])
    assert list(validator.iter_errors(duplicate_substitution))


def test_inventory_provenance_is_proven_only_and_has_no_selected_case_binding() -> None:
    schema = _load_inventory_evidence("provenance")
    validator = Draft202012Validator(schema)
    valid = _valid_inventory_provenance()
    assert schema["properties"]["status"] == {"const": "PROVEN"}
    assert not list(validator.iter_errors(valid))

    failed = copy.deepcopy(valid)
    failed["status"] = "FAILED"
    assert list(validator.iter_errors(failed))

    selected_source = copy.deepcopy(valid)
    selected_source["selected_source_binding"] = {
        "expected_sha256": SHA,
        "observed_sha256": SHA,
    }
    assert list(validator.iter_errors(selected_source))

    selection = copy.deepcopy(valid)
    selection["selection_binding"] = {"status": "FROZEN_FOR_SOURCE_ACQUISITION"}
    assert list(validator.iter_errors(selection))

    missing_calendar_hash = copy.deepcopy(valid)
    del missing_calendar_hash["calendar_binding"]["calendar_binding_sha256"]
    assert list(validator.iter_errors(missing_calendar_hash))

    missing_provider_link = copy.deepcopy(valid)
    del missing_provider_link["provider_acquisition"]["historical_request"]
    assert list(validator.iter_errors(missing_provider_link))


def test_inventory_contract_identities_and_immutable_transformations_are_enforced() -> None:
    fixtures = {
        "scan": _valid_inventory_scan(),
        "runtime": _valid_inventory_runtime_capture(),
        "acquisition": _valid_inventory_acquisition_evidence(),
        "provenance": _valid_inventory_provenance(),
    }
    for name, document in fixtures.items():
        validator = Draft202012Validator(_load_inventory_evidence(name))
        assert not list(validator.iter_errors(document))

        wrong_cohort = copy.deepcopy(document)
        wrong_cohort["cohort_id"] = "mnq-wrong-cohort"
        assert list(validator.iter_errors(wrong_cohort)), name

        wrong_acquisition = copy.deepcopy(document)
        wrong_acquisition["acquisition_id"] = ""
        assert list(validator.iter_errors(wrong_acquisition)), name

        if "transformations" in document:
            transformed = copy.deepcopy(document)
            transformed["transformations"]["sorted"] = True
            assert list(validator.iter_errors(transformed)), name
