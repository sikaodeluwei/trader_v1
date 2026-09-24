from __future__ import annotations

import copy
import hashlib
import inspect
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from tools.validation import mnq_5m_selection
from tools.validation.mnq_5m_selection import (
    SelectionValidationError,
    generate_selection,
)
from tools.validation.mnq_5m_inventory_common import write_json_atomically


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "validation" / "mnq_5m_multiwindow" / "schemas"
TOOLSET_CHECKPOINT = "1" * 40
INVENTORY_CHECKPOINT = "2" * 40
SELECTION_CHECKPOINT = "3" * 40
PINNED_HIERARCHY = "04a73e1401d44688660b211d9db6918113482856"
SHA_A = "a" * 64
SHA_B = "b" * 64


def _canonical_payload_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _canonical_document_bytes(value: object) -> bytes:
    return _canonical_payload_bytes(value) + b"\n"


def _document_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_document_bytes(value)).hexdigest()


def _payload_hash(value: dict[str, object]) -> str:
    payload = dict(value)
    payload.pop("aggregate_payload_sha256", None)
    return hashlib.sha256(_canonical_payload_bytes(payload)).hexdigest()


def _policy() -> dict[str, object]:
    return {
        "contract_label": "MNQ SEP26",
        "full_name": "MNQ SEP26",
        "expiry_month": 9,
        "expiry_year": 2026,
        "candidate_date_start": "2026-06-22",
        "candidate_date_end": "2026-07-24",
    }


def _entry(trading_date: date, *, eligible: bool = True) -> dict[str, object]:
    return {
        "trading_date": trading_date.isoformat(),
        "eligible": eligible,
        "exclusion_reasons": [] if eligible else ["SOURCE_CORRUPTION"],
        "session_begin_application": trading_date.strftime("%Y%m%d 170000"),
        "session_end_application": (trading_date + timedelta(days=1)).strftime(
            "%Y%m%d 160000"
        ),
        "observed_native_bar_count": 276,
        "first_250_source_sha256": SHA_A if eligible else None,
        "complete_session_source_sha256": SHA_B if eligible else None,
    }


def _documents(
    eligible_count: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    entries = [
        _entry(date(2026, 6, 22) + timedelta(days=index))
        for index in range(eligible_count)
    ]
    outcome = "READY_FOR_SELECTION" if eligible_count >= 10 else "COHORT_INCOMPLETE"
    inventory: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_INVENTORY",
        "cohort_outcome": outcome,
        "cohort_id": "mnq-202609-5m-v1",
        "contract_policy": _policy(),
        "inventory_scan": {
            "path": "inventory_scan.json",
            "schema_version": "1.0",
            "sha256": SHA_A,
            "producing_checkpoint": TOOLSET_CHECKPOINT,
        },
        "inventory_provenance": {
            "path": "inventory_provenance.json",
            "schema_version": "1.0",
            "sha256": SHA_B,
            "producing_checkpoint": TOOLSET_CHECKPOINT,
        },
        "producing_checkpoint": TOOLSET_CHECKPOINT,
        "candidate_count": len(entries),
        "eligible_count": eligible_count,
        "entries": entries,
        "aggregate_payload_sha256": "",
    }
    inventory["aggregate_payload_sha256"] = _payload_hash(inventory)
    exclusions: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_INVENTORY",
        "cohort_outcome": outcome,
        "cohort_id": "mnq-202609-5m-v1",
        "source_inventory_sha256": _document_sha256(inventory),
        "producing_checkpoint": TOOLSET_CHECKPOINT,
        "entries": [],
        "aggregate_payload_sha256": "",
    }
    exclusions["aggregate_payload_sha256"] = _payload_hash(exclusions)
    attestation = _attestation(inventory, exclusions)
    return inventory, exclusions, attestation


def _artifact(role: str, path: str, sha256: str) -> dict[str, object]:
    return {
        "role": role,
        "stage": "inventory",
        "repository_path": path,
        "checkpoint": INVENTORY_CHECKPOINT,
        "producing_checkpoint": TOOLSET_CHECKPOINT,
        "git_object_id": "4" * 40,
        "sha256": sha256,
        "bundle_sha256": sha256,
    }


def _attestation(
    inventory: dict[str, object], exclusions: dict[str, object]
) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "stage": "INVENTORY",
        "status": "VERIFIED",
        "repository": {
            "identity": "sikaodeluwei/trader_v1",
            "git_object_format": "sha1",
        },
        "trusted_toolset_checkpoint": TOOLSET_CHECKPOINT,
        "trusted_inventory_checkpoint": INVENTORY_CHECKPOINT,
        "pinned_production_hierarchy_commit": PINNED_HIERARCHY,
        "artifacts": [
            _artifact(
                "source_inventory",
                "source_inventory.json",
                _document_sha256(inventory),
            ),
            _artifact("exclusions", "exclusions.json", _document_sha256(exclusions)),
        ],
        "ancestry": [
            {
                "ancestor": PINNED_HIERARCHY,
                "descendant": TOOLSET_CHECKPOINT,
                "verified": True,
            },
            {
                "ancestor": TOOLSET_CHECKPOINT,
                "descendant": INVENTORY_CHECKPOINT,
                "verified": True,
            },
        ],
        "remote_publication": {"status": "NOT_CHECKED"},
        "verifier": {
            "version": "2.0",
            "repository_path": "tools/validation/mnq_5m_checkpoint_verify.py",
            "producing_commit": TOOLSET_CHECKPOINT,
            "frozen_sha256": SHA_A,
            "executing_sha256": SHA_A,
        },
        "attestation_sha256": SHA_B,
    }


def _refresh_bindings(
    inventory: dict[str, object], exclusions: dict[str, object]
) -> dict[str, object]:
    inventory["aggregate_payload_sha256"] = _payload_hash(inventory)
    exclusions["source_inventory_sha256"] = _document_sha256(inventory)
    exclusions["aggregate_payload_sha256"] = _payload_hash(exclusions)
    return _attestation(inventory, exclusions)


def _generate(
    inventory: dict[str, object],
    exclusions: dict[str, object],
    attestation: dict[str, object],
) -> dict[str, object]:
    return generate_selection(
        source_inventory=inventory,
        exclusions=exclusions,
        inventory_attestation=attestation,
        trusted_inventory_checkpoint=INVENTORY_CHECKPOINT,
        producing_checkpoint=SELECTION_CHECKPOINT,
    )


@pytest.mark.parametrize("eligible_count", [10, 11, 17, 23])
def test_selects_earliest_date_from_each_exact_integer_stratum(
    eligible_count: int,
) -> None:
    inventory, exclusions, attestation = _documents(eligible_count)

    registry = _generate(inventory, exclusions, attestation)

    selections = registry["selections"]
    assert isinstance(selections, list)
    assert len(selections) == 10
    eligible_dates = [entry["trading_date"] for entry in inventory["entries"]]
    for index, selection in enumerate(selections):
        start = index * eligible_count // 10
        end = (index + 1) * eligible_count // 10 - 1
        assert selection["selected_eligible_index"] == start
        assert selection["stratum_start_index"] == start
        assert selection["stratum_end_index"] == end
        assert selection["trading_date"] == eligible_dates[start]
        assert selection["stratum_number"] == index + 1


def test_registry_has_exact_case_names_policy_and_no_duplicate_records() -> None:
    inventory, exclusions, attestation = _documents(17)

    registry = _generate(inventory, exclusions, attestation)
    selections = registry["selections"]

    assert [selection["case_id"].rsplit("-", 1)[-1] for selection in selections] == [
        f"w{number:02d}" for number in range(1, 11)
    ]
    assert len({_canonical_payload_bytes(selection) for selection in selections}) == 10
    assert registry["selection_algorithm"] == {
        "id": "CHRONOLOGICAL_TEN_STRATA_EARLIEST",
        "version": "1.0",
        "stratum_count": 10,
    }
    assert {
        selection["window_policy"] for selection in selections
    } == {"FIRST_250_NATIVE_5M_SESSION_BARS"}


def test_registry_binds_exact_inventory_exclusions_and_checkpoints() -> None:
    inventory, exclusions, attestation = _documents(10)

    registry = _generate(inventory, exclusions, attestation)

    assert registry["source_inventory"] == {
        "path": "source_inventory.json",
        "bundle_path": "source_inventory.json",
        "schema_version": "2.0",
        "sha256": _document_sha256(inventory),
        "producing_checkpoint": TOOLSET_CHECKPOINT,
    }
    assert registry["exclusion_ledger"] == {
        "path": "exclusions.json",
        "bundle_path": "exclusions.json",
        "schema_version": "2.0",
        "sha256": _document_sha256(exclusions),
        "producing_checkpoint": TOOLSET_CHECKPOINT,
    }
    assert registry["trusted_inventory_checkpoint"] == INVENTORY_CHECKPOINT
    assert registry["producing_checkpoint"] == SELECTION_CHECKPOINT
    assert registry["contract_policy"] == inventory["contract_policy"]
    assert registry["selection_influence"] == {
        "hierarchy_output_used": False,
        "oracle_output_used": False,
        "project_output_used": False,
    }


def test_registry_is_schema_valid_and_repeated_results_have_stable_bytes() -> None:
    inventory, exclusions, attestation = _documents(17)

    first = _generate(inventory, exclusions, attestation)
    second = _generate(inventory, exclusions, attestation)

    assert _canonical_document_bytes(first) == _canonical_document_bytes(second)
    schema = json.loads(
        (SCHEMA_DIR / "selection_registry_v2.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(first)


def test_public_interface_has_no_forbidden_selection_influence_inputs() -> None:
    signature = inspect.signature(generate_selection)
    assert list(signature.parameters) == [
        "source_inventory",
        "exclusions",
        "inventory_attestation",
        "trusted_inventory_checkpoint",
        "producing_checkpoint",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    inventory, exclusions, attestation = _documents(10)
    with pytest.raises(TypeError):
        generate_selection(
            source_inventory=inventory,
            exclusions=exclusions,
            inventory_attestation=attestation,
            trusted_inventory_checkpoint=INVENTORY_CHECKPOINT,
            producing_checkpoint=SELECTION_CHECKPOINT,
            hierarchy_output={"preferred_date": "2026-06-30"},  # type: ignore[call-arg]
        )


def test_refuses_cohort_incomplete_even_with_ten_eligible_dates() -> None:
    inventory, exclusions, _ = _documents(10)
    inventory["cohort_outcome"] = "COHORT_INCOMPLETE"
    exclusions["cohort_outcome"] = "COHORT_INCOMPLETE"
    attestation = _refresh_bindings(inventory, exclusions)

    with pytest.raises(SelectionValidationError, match="READY_FOR_SELECTION"):
        _generate(inventory, exclusions, attestation)


def test_refuses_fewer_than_ten_eligible_dates_independently_of_outcome() -> None:
    inventory, exclusions, _ = _documents(9)
    inventory["cohort_outcome"] = "READY_FOR_SELECTION"
    exclusions["cohort_outcome"] = "READY_FOR_SELECTION"
    attestation = _refresh_bindings(inventory, exclusions)

    with pytest.raises(SelectionValidationError, match="at least ten"):
        _generate(inventory, exclusions, attestation)


@pytest.mark.parametrize("mutation", ["reordered", "duplicate"])
def test_refuses_non_chronological_or_duplicate_inventory_dates(mutation: str) -> None:
    inventory, exclusions, _ = _documents(11)
    entries = inventory["entries"]
    if mutation == "reordered":
        entries[3], entries[4] = entries[4], entries[3]
    else:
        entries[4]["trading_date"] = entries[3]["trading_date"]
    attestation = _refresh_bindings(inventory, exclusions)

    with pytest.raises(SelectionValidationError, match="strictly chronological"):
        _generate(inventory, exclusions, attestation)


def test_refuses_inventory_exclusion_reconciliation_mismatch() -> None:
    inventory, exclusions, _ = _documents(10)
    exclusions["entries"] = [
        {"trading_date": inventory["entries"][0]["trading_date"], "reasons": ["SOURCE_CORRUPTION"]}
    ]
    attestation = _refresh_bindings(inventory, exclusions)

    with pytest.raises(SelectionValidationError, match="reconcile"):
        _generate(inventory, exclusions, attestation)


def _mutate_attestation(
    attestation: dict[str, object], mutation: str
) -> dict[str, object]:
    invalid = copy.deepcopy(attestation)
    artifacts = invalid["artifacts"]
    if mutation == "schema_version":
        invalid["schema_version"] = "1.0"
    elif mutation == "status":
        invalid["status"] = "UNVERIFIED"
    elif mutation == "stage":
        invalid["stage"] = "SELECTION"
        invalid["trusted_selection_checkpoint"] = SELECTION_CHECKPOINT
    elif mutation == "trusted_toolset_checkpoint":
        invalid["trusted_toolset_checkpoint"] = "5" * 40
    elif mutation == "trusted_inventory_checkpoint":
        invalid["trusted_inventory_checkpoint"] = "5" * 40
    elif mutation == "source_path":
        artifacts[0]["repository_path"] = "other/source_inventory.json"
    elif mutation == "source_hash":
        artifacts[0]["sha256"] = "5" * 64
    elif mutation == "exclusions_path":
        artifacts[1]["repository_path"] = "other/exclusions.json"
    elif mutation == "exclusions_hash":
        artifacts[1]["sha256"] = "5" * 64
    elif mutation == "missing_fact":
        del artifacts[0]["producing_checkpoint"]
    else:  # pragma: no cover - test table owns the values
        raise AssertionError(mutation)
    return invalid


@pytest.mark.parametrize(
    "mutation",
    [
        "schema_version",
        "status",
        "stage",
        "trusted_toolset_checkpoint",
        "trusted_inventory_checkpoint",
        "source_path",
        "source_hash",
        "exclusions_path",
        "exclusions_hash",
        "missing_fact",
    ],
)
def test_each_invalid_inventory_attestation_fact_fails_before_record_building(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    inventory, exclusions, attestation = _documents(10)
    invalid = _mutate_attestation(attestation, mutation)

    def fail_if_called(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise AssertionError("selection records were built before attestation rejection")

    monkeypatch.setattr(mnq_5m_selection, "_build_selection_records", fail_if_called)
    with pytest.raises(SelectionValidationError):
        _generate(inventory, exclusions, invalid)


def test_refuses_missing_inventory_attestation() -> None:
    inventory, exclusions, _ = _documents(10)
    with pytest.raises(SelectionValidationError, match="attestation"):
        generate_selection(
            source_inventory=inventory,
            exclusions=exclusions,
            inventory_attestation=None,  # type: ignore[arg-type]
            trusted_inventory_checkpoint=INVENTORY_CHECKPOINT,
            producing_checkpoint=SELECTION_CHECKPOINT,
        )


def _write_cli_inputs(
    directory: Path,
    *,
    eligible_count: int = 17,
    remote_status: str = "NOT_CHECKED",
) -> tuple[Path, Path, Path]:
    inventory, exclusions, attestation = _documents(eligible_count)
    attestation["remote_publication"] = {"status": remote_status}
    paths = (
        directory / "source_inventory.json",
        directory / "exclusions.json",
        directory / "inventory_attestation.json",
    )
    for path, value in zip(paths, (inventory, exclusions, attestation)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_canonical_document_bytes(value))
    return paths


def _cli_args(inputs: tuple[Path, Path, Path], output: Path) -> list[str]:
    inventory, exclusions, attestation = inputs
    return [
        "--source-inventory",
        str(inventory),
        "--exclusions",
        str(exclusions),
        "--inventory-attestation",
        str(attestation),
        "--trusted-inventory-checkpoint",
        INVENTORY_CHECKPOINT,
        "--producing-checkpoint",
        SELECTION_CHECKPOINT,
        "--output",
        str(output),
    ]


def _write_task7_exact_inputs(
    directory: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    tuple[Path, Path, Path],
]:
    inventory, exclusions, attestation = _documents(17)
    inventory_path = directory / "source_inventory.json"
    exclusions_path = directory / "exclusions.json"
    attestation_path = directory / "inventory_attestation.json"
    write_json_atomically(inventory_path, inventory)
    write_json_atomically(exclusions_path, exclusions)

    exact_hashes = {
        "source_inventory": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        "exclusions": hashlib.sha256(exclusions_path.read_bytes()).hexdigest(),
    }
    for artifact in attestation["artifacts"]:
        exact_hash = exact_hashes[artifact["role"]]
        artifact["sha256"] = exact_hash
        artifact["bundle_sha256"] = exact_hash
    write_json_atomically(attestation_path, attestation)
    return (
        inventory,
        exclusions,
        attestation,
        (inventory_path, exclusions_path, attestation_path),
    )


def test_task7_exact_document_bytes_are_accepted_by_public_and_cli_paths(
    tmp_path: Path,
) -> None:
    inventory, exclusions, attestation, inputs = _write_task7_exact_inputs(tmp_path)
    inventory_bytes = inputs[0].read_bytes()
    exclusions_bytes = inputs[1].read_bytes()

    assert inventory_bytes == _canonical_document_bytes(inventory)
    assert exclusions_bytes == _canonical_document_bytes(exclusions)
    assert inventory_bytes.endswith(b"\n") and not inventory_bytes.endswith(b"\n\n")
    assert exclusions_bytes.endswith(b"\n") and not exclusions_bytes.endswith(b"\n\n")
    registry = _generate(inventory, exclusions, attestation)

    output = tmp_path / "selection_registry.json"
    assert mnq_5m_selection.main(_cli_args(inputs, output)) == 0
    assert json.loads(output.read_bytes()) == registry


def test_one_byte_final_lf_hash_mutation_is_rejected_before_selection_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory, exclusions, attestation, inputs = _write_task7_exact_inputs(tmp_path)
    source_bytes = inputs[0].read_bytes()
    assert source_bytes.endswith(b"\n")
    without_final_lf_hash = hashlib.sha256(source_bytes[:-1]).hexdigest()
    source_artifact = attestation["artifacts"][0]
    source_artifact["sha256"] = without_final_lf_hash
    source_artifact["bundle_sha256"] = without_final_lf_hash
    exclusions_artifact = attestation["artifacts"][1]
    current_no_lf_exclusions_hash = hashlib.sha256(
        _canonical_payload_bytes(exclusions)
    ).hexdigest()
    exclusions_artifact["sha256"] = current_no_lf_exclusions_hash
    exclusions_artifact["bundle_sha256"] = current_no_lf_exclusions_hash

    def fail_if_called(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise AssertionError("selection records were built before newline rejection")

    monkeypatch.setattr(mnq_5m_selection, "_build_selection_records", fail_if_called)
    with pytest.raises(
        SelectionValidationError,
        match="source inventory attestation hash mismatch",
    ):
        _generate(inventory, exclusions, attestation)


def test_cli_writes_byte_identical_canonical_output_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    first_inputs = _write_cli_inputs(tmp_path / "first")
    second_inputs = _write_cli_inputs(tmp_path / "second")
    first_output = tmp_path / "first" / "selection_registry.json"
    second_output = tmp_path / "second" / "selection_registry.json"

    assert mnq_5m_selection.main(_cli_args(first_inputs, first_output)) == 0
    assert mnq_5m_selection.main(_cli_args(second_inputs, second_output)) == 0
    assert first_output.read_bytes() == second_output.read_bytes()
    assert first_output.read_bytes().endswith(b"\n")
    with pytest.raises(FileExistsError):
        mnq_5m_selection.main(_cli_args(first_inputs, first_output))


def test_official_cli_requires_verified_remote_publication(tmp_path: Path) -> None:
    inputs = _write_cli_inputs(tmp_path)
    output = tmp_path / "selection_registry.json"

    with pytest.raises(SelectionValidationError, match="remote publication"):
        mnq_5m_selection.main([*_cli_args(inputs, output), "--official"])
    assert not output.exists()


def test_official_cli_uses_same_verified_generate_selection_path(tmp_path: Path) -> None:
    inputs = _write_cli_inputs(tmp_path, remote_status="VERIFIED")
    attestation = json.loads(inputs[2].read_text(encoding="utf-8"))
    attestation["stage"] = "SELECTION"
    attestation["trusted_selection_checkpoint"] = SELECTION_CHECKPOINT
    inputs[2].write_bytes(_canonical_document_bytes(attestation))

    with pytest.raises(SelectionValidationError, match="INVENTORY"):
        mnq_5m_selection.main(
            [*_cli_args(inputs, tmp_path / "selection_registry.json"), "--official"]
        )
