"""Generate the deterministic MNQ ten-stratum selection registry."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from tools.validation.mnq_5m_inventory_common import (
    _load_schema_validated_json_bytes,
    canonical_payload_sha256,
    sha256_bytes,
    write_json_atomically,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "validation" / "mnq_5m_multiwindow" / "schemas"
SOURCE_INVENTORY_SCHEMA = SCHEMA_DIR / "source_inventory_v2.schema.json"
EXCLUSIONS_SCHEMA = SCHEMA_DIR / "exclusions_v2.schema.json"
SELECTION_REGISTRY_SCHEMA = SCHEMA_DIR / "selection_registry_v2.schema.json"
CHECKPOINT_ATTESTATION_SCHEMA = SCHEMA_DIR / "checkpoint_attestation_v2.schema.json"

SOURCE_INVENTORY_PATH = "source_inventory.json"
EXCLUSIONS_PATH = "exclusions.json"
SELECTION_POLICY = "CHRONOLOGICAL_TEN_STRATA_EARLIEST"
SELECTION_POLICY_VERSION = "1.0"
WINDOW_POLICY = "FIRST_250_NATIVE_5M_SESSION_BARS"


class SelectionValidationError(ValueError):
    """Raised when frozen inventory inputs cannot produce a valid selection."""


def _fail(message: str) -> None:
    raise SelectionValidationError(message)


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"invalid {label}")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail(f"invalid {label}")
    return value


def _validate_document(
    value: Mapping[str, object], schema_path: Path, label: str
) -> None:
    try:
        schema = json.loads(schema_path.read_bytes())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    except Exception as error:
        raise SelectionValidationError(f"invalid {label}") from error


def _document_sha256(value: Mapping[str, object]) -> str:
    return sha256_bytes(_canonical_json_bytes(value))


def _artifact_for_role(
    attestation: Mapping[str, object], role: str
) -> Mapping[str, object]:
    artifacts = _sequence(attestation.get("artifacts"), "inventory attestation artifacts")
    matches: list[Mapping[str, object]] = []
    for raw_artifact in artifacts:
        artifact = _mapping(raw_artifact, "inventory attestation artifact")
        if artifact.get("role") == role:
            matches.append(artifact)
    if len(matches) != 1:
        _fail(f"inventory attestation must bind exactly one {role} artifact")
    return matches[0]


def _verify_artifact_binding(
    *,
    artifact: Mapping[str, object],
    expected_path: str,
    expected_sha256: str,
    trusted_inventory_checkpoint: str,
    trusted_toolset_checkpoint: object,
    label: str,
) -> None:
    if artifact.get("stage") != "inventory":
        _fail(f"{label} attestation stage mismatch")
    if artifact.get("repository_path") != expected_path:
        _fail(f"{label} attestation path mismatch")
    if artifact.get("checkpoint") != trusted_inventory_checkpoint:
        _fail(f"{label} attestation checkpoint mismatch")
    if artifact.get("producing_checkpoint") != trusted_toolset_checkpoint:
        _fail(f"{label} attestation producing checkpoint mismatch")
    if artifact.get("sha256") != expected_sha256:
        _fail(f"{label} attestation hash mismatch")
    if artifact.get("bundle_sha256") != expected_sha256:
        _fail(f"{label} attestation bundle hash mismatch")


def _verify_inventory_attestation(
    *,
    source_inventory: Mapping[str, object],
    exclusions: Mapping[str, object],
    inventory_attestation: Mapping[str, object],
    trusted_inventory_checkpoint: str,
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    _validate_document(
        inventory_attestation,
        CHECKPOINT_ATTESTATION_SCHEMA,
        "inventory attestation",
    )
    if inventory_attestation.get("schema_version") != "2.0":
        _fail("inventory attestation schema version must be 2.0")
    if inventory_attestation.get("status") != "VERIFIED":
        _fail("inventory attestation status must be VERIFIED")
    if inventory_attestation.get("stage") != "INVENTORY":
        _fail("inventory attestation stage must be INVENTORY")
    if (
        inventory_attestation.get("trusted_inventory_checkpoint")
        != trusted_inventory_checkpoint
    ):
        _fail("trusted inventory checkpoint mismatch")

    trusted_toolset_checkpoint = inventory_attestation.get(
        "trusted_toolset_checkpoint"
    )
    if (
        source_inventory.get("producing_checkpoint")
        != trusted_toolset_checkpoint
        or exclusions.get("producing_checkpoint") != trusted_toolset_checkpoint
    ):
        _fail("trusted toolset checkpoint does not bind inventory inputs")

    source_artifact = _artifact_for_role(inventory_attestation, "source_inventory")
    exclusions_artifact = _artifact_for_role(inventory_attestation, "exclusions")
    _verify_artifact_binding(
        artifact=source_artifact,
        expected_path=SOURCE_INVENTORY_PATH,
        expected_sha256=_document_sha256(source_inventory),
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        label="source inventory",
    )
    _verify_artifact_binding(
        artifact=exclusions_artifact,
        expected_path=EXCLUSIONS_PATH,
        expected_sha256=_document_sha256(exclusions),
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        label="exclusions",
    )
    return source_artifact, exclusions_artifact


def _eligible_entries(
    source_inventory: Mapping[str, object], exclusions: Mapping[str, object]
) -> list[Mapping[str, object]]:
    if (
        source_inventory.get("aggregate_payload_sha256")
        != canonical_payload_sha256(source_inventory)
    ):
        _fail("source inventory aggregate hash mismatch")
    if exclusions.get("aggregate_payload_sha256") != canonical_payload_sha256(
        exclusions
    ):
        _fail("exclusions aggregate hash mismatch")
    if exclusions.get("source_inventory_sha256") != _document_sha256(source_inventory):
        _fail("exclusions/source-inventory hash mismatch")
    if (
        exclusions.get("cohort_id") != source_inventory.get("cohort_id")
        or exclusions.get("cohort_outcome")
        != source_inventory.get("cohort_outcome")
        or exclusions.get("producing_checkpoint")
        != source_inventory.get("producing_checkpoint")
    ):
        _fail("inventory/exclusions identity mismatch")

    raw_entries = _sequence(source_inventory.get("entries"), "source inventory entries")
    if source_inventory.get("candidate_count") != len(raw_entries):
        _fail("source inventory candidate count mismatch")

    eligible: list[Mapping[str, object]] = []
    expected_exclusions: list[dict[str, object]] = []
    previous_date: date | None = None
    for raw_entry in raw_entries:
        entry = _mapping(raw_entry, "source inventory entry")
        raw_date = entry.get("trading_date")
        if not isinstance(raw_date, str):
            _fail("source inventory dates are not strictly chronological")
        try:
            trading_date = date.fromisoformat(raw_date)
        except ValueError as error:
            raise SelectionValidationError("invalid source inventory date") from error
        if previous_date is not None and trading_date <= previous_date:
            _fail("source inventory dates are not strictly chronological and unique")
        previous_date = trading_date

        reasons = list(
            _sequence(entry.get("exclusion_reasons"), "inventory exclusion reasons")
        )
        if entry.get("eligible") is True:
            if reasons:
                _fail("eligible inventory entry has exclusion reasons")
            eligible.append(entry)
        elif entry.get("eligible") is False and reasons:
            expected_exclusions.append({"trading_date": raw_date, "reasons": reasons})
        else:
            _fail("inventory disposition does not reconcile")

    if source_inventory.get("eligible_count") != len(eligible):
        _fail("source inventory eligible count mismatch")
    actual_exclusions = list(
        _sequence(exclusions.get("entries"), "exclusions entries")
    )
    if actual_exclusions != expected_exclusions:
        _fail("source inventory and exclusions do not reconcile")
    if source_inventory.get("cohort_outcome") != "READY_FOR_SELECTION":
        _fail("inventory outcome must be READY_FOR_SELECTION")
    if len(eligible) < 10:
        _fail("selection requires at least ten eligible dates")
    return eligible


def _build_selection_records(
    eligible_entries: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    count = len(eligible_entries)
    selections: list[dict[str, object]] = []
    for index in range(10):
        start = index * count // 10
        end = (index + 1) * count // 10 - 1
        trading_date = eligible_entries[start]["trading_date"]
        selections.append(
            {
                "case_id": (
                    f"mnq-202609-5m-td{trading_date}-w{index + 1:02d}"
                ),
                "trading_date": trading_date,
                "stratum_number": index + 1,
                "stratum_start_index": start,
                "stratum_end_index": end,
                "selected_eligible_index": start,
                "window_policy": WINDOW_POLICY,
            }
        )
    return selections


def generate_selection(
    *,
    source_inventory: Mapping[str, object],
    exclusions: Mapping[str, object],
    inventory_attestation: Mapping[str, object],
    trusted_inventory_checkpoint: str,
    producing_checkpoint: str,
) -> dict[str, object]:
    """Verify INVENTORY attestation, then generate without reordering dates."""

    if not isinstance(source_inventory, Mapping):
        _fail("invalid source inventory")
    if not isinstance(exclusions, Mapping):
        _fail("invalid exclusions")
    if not isinstance(inventory_attestation, Mapping):
        _fail("invalid inventory attestation")
    if producing_checkpoint != trusted_inventory_checkpoint:
        _fail("selection producing checkpoint must equal trusted inventory checkpoint")

    source_artifact, exclusions_artifact = _verify_inventory_attestation(
        source_inventory=source_inventory,
        exclusions=exclusions,
        inventory_attestation=inventory_attestation,
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
    )
    _validate_document(source_inventory, SOURCE_INVENTORY_SCHEMA, "source inventory")
    _validate_document(exclusions, EXCLUSIONS_SCHEMA, "exclusions")
    eligible = _eligible_entries(source_inventory, exclusions)

    registry: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": source_inventory["cohort_id"],
        "contract_policy": dict(
            _mapping(source_inventory.get("contract_policy"), "contract policy")
        ),
        "selection_algorithm": {
            "id": SELECTION_POLICY,
            "version": SELECTION_POLICY_VERSION,
            "stratum_count": 10,
        },
        "selection_count": 10,
        "source_inventory": {
            "path": source_artifact["repository_path"],
            "bundle_path": SOURCE_INVENTORY_PATH,
            "schema_version": source_inventory["schema_version"],
            "sha256": source_artifact["sha256"],
            "producing_checkpoint": source_inventory["producing_checkpoint"],
        },
        "exclusion_ledger": {
            "path": exclusions_artifact["repository_path"],
            "bundle_path": EXCLUSIONS_PATH,
            "schema_version": exclusions["schema_version"],
            "sha256": exclusions_artifact["sha256"],
            "producing_checkpoint": exclusions["producing_checkpoint"],
        },
        "trusted_inventory_checkpoint": trusted_inventory_checkpoint,
        "producing_checkpoint": trusted_inventory_checkpoint,
        "selection_influence": {
            "hierarchy_output_used": False,
            "oracle_output_used": False,
            "project_output_used": False,
        },
        "selections": _build_selection_records(eligible),
        "aggregate_payload_sha256": "",
    }
    registry["aggregate_payload_sha256"] = canonical_payload_sha256(registry)
    _validate_document(registry, SELECTION_REGISTRY_SCHEMA, "selection registry")
    return registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-inventory", required=True, type=Path)
    parser.add_argument("--exclusions", required=True, type=Path)
    parser.add_argument("--inventory-attestation", required=True, type=Path)
    parser.add_argument("--trusted-inventory-checkpoint", required=True)
    parser.add_argument("--producing-checkpoint", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--official", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source_inventory_bytes = args.source_inventory.read_bytes()
        exclusions_bytes = args.exclusions.read_bytes()
        inventory_attestation_bytes = args.inventory_attestation.read_bytes()
        inventory_attestation = _load_schema_validated_json_bytes(
            inventory_attestation_bytes,
            CHECKPOINT_ATTESTATION_SCHEMA,
            "inventory attestation",
        )
    except (OSError, ValueError) as error:
        raise SelectionValidationError("invalid selection input") from error
    for role, exact_bytes in (
        ("source_inventory", source_inventory_bytes),
        ("exclusions", exclusions_bytes),
    ):
        artifact = _artifact_for_role(inventory_attestation, role)
        exact_sha256 = sha256_bytes(exact_bytes)
        if (
            artifact.get("sha256") != exact_sha256
            or artifact.get("bundle_sha256") != exact_sha256
        ):
            _fail(f"{role.replace('_', ' ')} exact bytes do not match attestation hash")
    try:
        source_inventory = _load_schema_validated_json_bytes(
            source_inventory_bytes, SOURCE_INVENTORY_SCHEMA, "source inventory"
        )
        exclusions = _load_schema_validated_json_bytes(
            exclusions_bytes, EXCLUSIONS_SCHEMA, "exclusions"
        )
    except ValueError as error:
        raise SelectionValidationError("invalid selection input") from error
    if args.official:
        remote_publication = _mapping(
            inventory_attestation.get("remote_publication"),
            "inventory attestation remote publication",
        )
        if remote_publication.get("status") != "VERIFIED":
            _fail("official selection requires VERIFIED remote publication")

    registry = generate_selection(
        source_inventory=source_inventory,
        exclusions=exclusions,
        inventory_attestation=inventory_attestation,
        trusted_inventory_checkpoint=args.trusted_inventory_checkpoint,
        producing_checkpoint=args.producing_checkpoint,
    )
    write_json_atomically(args.output, registry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
