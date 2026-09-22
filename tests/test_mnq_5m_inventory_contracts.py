"""Contract boundaries for the versioned MNQ inventory protocol."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


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
COMPATIBILITY_REASONS = [
    "INCOMPLETE_PROVENANCE", "FEWER_THAN_250_NATIVE_BARS", "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS", "TRADING_HOURS_INCONSISTENCY", "MALFORMED_OR_NON_FINITE_OHLCV", "INVALID_OHLC_GEOMETRY", "UNEXPECTED_MISSING_BARS", "SOURCE_CORRUPTION", "SOURCE_HASH_MISMATCH", "OUTSIDE_POLICY",
]
SHA = "a" * 64
COMMIT = "b" * 40


def _load(name: str) -> dict[str, object]:
    return json.loads((SCHEMA_DIR / SCHEMA_FILES[name]).read_text(encoding="utf-8"))


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
    document = {"schema_version": "2.0", "stage": "INVENTORY_VALIDATION", "status": "FROZEN_FOR_INVENTORY", "cohort_id": "mnq-202609-5m-v1", "producing_checkpoint": COMMIT, "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856", "runtime": {"implementation": "CPython", "version": "3.12", "dependencies": [{"name": "jsonschema", "version": "4.25.1"}]}, "canonicalization": "JSON_UTF8_SORTED_KEYS_COMPACT_EXCLUDE_AGGREGATE_PAYLOAD_SHA256", "components": [{"role": role, "path": f"validation/{role}.txt", "bundle_path": f"validation/{role}.txt", "sha256": SHA, "producing_commit": COMMIT} for role in ROLES], "deferred_components": ["independent_oracle", "blind_project_runner", "comparator", "cohort_aggregator"], "aggregate_payload_sha256": SHA}
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
