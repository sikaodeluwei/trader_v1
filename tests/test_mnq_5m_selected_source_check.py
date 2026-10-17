from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.validation.mnq_5m_selected_source_check import (
    INVENTORY_V2_CHECKPOINT_BUNDLE_PATHS,
    SelectedSourceValidationError,
    verify_selected_source_hash,
)


TOOLSET_CHECKPOINT = "1" * 40
INVENTORY_CHECKPOINT = "2" * 40
SELECTION_CHECKPOINT = "3" * 40
CASE_ID = "mnq-202609-5m-td2026-06-22-w01"
SOURCE_SHA256 = "eec12e2501d546e50e5e3e04206f1a13c9471a77d9b846893dfbffdcaaf79695"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_bundle(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    source = tmp_path / "bars.txt"
    source.write_bytes(b"selected bytes\n")
    dates = ["2026-06-22", "2026-06-24", "2026-06-25", "2026-06-26",
             "2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02",
             "2026-07-03", "2026-07-06"]
    inventory = {
        "schema_version": "2.0",
        "entries": [
            {
                "trading_date": trading_date,
                "eligible": True,
                "first_250_source_sha256": SOURCE_SHA256 if index == 1 else "a" * 64,
            }
            for index, trading_date in enumerate(dates, 1)
        ],
    }
    registry = {
        "schema_version": "2.0",
        "trusted_inventory_checkpoint": INVENTORY_CHECKPOINT,
        "selections": [
            {
                "case_id": f"mnq-202609-5m-td{trading_date}-w{index:02d}",
                "trading_date": trading_date,
                "stratum_number": index,
                "stratum_start_index": index - 1,
                "stratum_end_index": index - 1,
                "selected_eligible_index": index - 1,
                "window_policy": "FIRST_250_NATIVE_5M_SESSION_BARS",
            }
            for index, trading_date in enumerate(dates, 1)
        ],
    }
    _write_json(bundle / "source_inventory.json", inventory)
    _write_json(bundle / "selection_registry.json", registry)
    for role, relative in INVENTORY_V2_CHECKPOINT_BUNDLE_PATHS.items():
        path = bundle / relative
        if not path.exists():
            path.write_text("<TradingHours />\n" if path.suffix == ".xml" else "{}\n")
    return source, bundle


def _verified_selection(**kwargs) -> dict[str, object]:
    bundle = Path(kwargs["bundle_root"])
    expected_inventory_paths = {
        role: bundle / INVENTORY_V2_CHECKPOINT_BUNDLE_PATHS[role]
        for role in (
            "inventory_runtime_capture",
            "inventory_scan",
            "trading_hours_template",
            "inventory_acquisition_evidence",
            "inventory_provenance",
            "source_inventory",
            "exclusions",
        )
    }
    if kwargs["toolset_manifest_path"] != bundle / "toolset_manifest.json":
        raise AssertionError("wrong fixed toolset path")
    if kwargs["selection_registry_path"] != bundle / "selection_registry.json":
        raise AssertionError("wrong fixed selection path")
    if kwargs["inventory_artifact_paths"] != expected_inventory_paths:
        raise AssertionError("wrong fixed inventory paths")
    return {
        "schema_version": "2.0",
        "stage": "SELECTION",
        "status": "VERIFIED",
        "trusted_toolset_checkpoint": TOOLSET_CHECKPOINT,
        "trusted_inventory_checkpoint": INVENTORY_CHECKPOINT,
        "trusted_selection_checkpoint": SELECTION_CHECKPOINT,
        "artifacts": [
            {
                "role": "selection_registry",
                "stage": "selection",
                "sha256": _sha256(bundle / "selection_registry.json"),
                "bundle_sha256": _sha256(bundle / "selection_registry.json"),
            },
            {
                "role": "source_inventory",
                "stage": "inventory",
                "sha256": _sha256(bundle / "source_inventory.json"),
                "bundle_sha256": _sha256(bundle / "source_inventory.json"),
            },
        ],
    }


def _verify(source: Path, bundle: Path, *, verifier=_verified_selection, **overrides):
    arguments = {
        "source_path": source,
        "case_id": CASE_ID,
        "repository_path": source.parent,
        "inventory_checkpoint_bundle_root": bundle,
        "trusted_toolset_checkpoint": TOOLSET_CHECKPOINT,
        "trusted_inventory_checkpoint": INVENTORY_CHECKPOINT,
        "trusted_selection_checkpoint": SELECTION_CHECKPOINT,
    }
    arguments.update(overrides)
    with patch(
        "tools.validation.mnq_5m_selected_source_check.verify_selection_checkpoint",
        side_effect=verifier,
    ):
        return verify_selected_source_hash(**arguments)


def test_selected_source_wrapper_returns_exact_frozen_hash_binding(tmp_path: Path) -> None:
    source, bundle = _build_bundle(tmp_path)

    result = _verify(source, bundle)

    assert result.case_id == CASE_ID
    assert result.trading_date == "2026-06-22"
    assert result.expected_sha256 == SOURCE_SHA256
    assert result.observed_sha256 == SOURCE_SHA256
    assert result.trusted_inventory_checkpoint == INVENTORY_CHECKPOINT
    assert result.trusted_selection_checkpoint == SELECTION_CHECKPOINT


def test_selected_source_wrapper_rejects_mismatch_and_is_exact_byte_sensitive(
    tmp_path: Path,
) -> None:
    source, bundle = _build_bundle(tmp_path)
    source.write_bytes(b"selected bytes\r\n")

    with pytest.raises(SelectedSourceValidationError, match="selected source SHA-256 mismatch"):
        _verify(source, bundle)


@pytest.mark.parametrize(
    ("case_id", "mutation", "message"),
    [
        (
            "mnq-202609-5m-td2026-06-24-w01",
            lambda registry: registry["selections"][0].__setitem__(
                "case_id", "mnq-202609-5m-td2026-06-24-w01"
            ),
            "case/date",
        ),
        (
            CASE_ID,
            lambda registry: registry["selections"].append(dict(registry["selections"][0])),
            "exactly once",
        ),
    ],
)
def test_selected_source_wrapper_rejects_wrong_case_date_or_duplicate_selection(
    tmp_path: Path, case_id: str, mutation, message: str
) -> None:
    source, bundle = _build_bundle(tmp_path)
    if mutation is not None:
        path = bundle / "selection_registry.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        mutation(registry)
        _write_json(path, registry)

    with pytest.raises(SelectedSourceValidationError, match=message):
        _verify(source, bundle, case_id=case_id)


def test_selected_source_wrapper_never_substitutes_another_matching_hash(
    tmp_path: Path,
) -> None:
    source, bundle = _build_bundle(tmp_path)
    inventory_path = bundle / "source_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["entries"][0]["first_250_source_sha256"] = "b" * 64
    inventory["entries"][1]["first_250_source_sha256"] = SOURCE_SHA256
    _write_json(inventory_path, inventory)

    with pytest.raises(SelectedSourceValidationError, match="selected source SHA-256 mismatch"):
        _verify(source, bundle)


@pytest.mark.parametrize(
    "role",
    ["selection_registry", "source_inventory"],
)
def test_selected_source_wrapper_rejects_bundle_mutation_after_verification(
    tmp_path: Path, role: str
) -> None:
    source, bundle = _build_bundle(tmp_path)
    if role == "selection_registry":
        registry_path = bundle / "selection_registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["selections"][0]["case_id"] = "unverified-case"
        _write_json(registry_path, registry)
    else:
        inventory_path = bundle / "source_inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory["entries"][0]["first_250_source_sha256"] = "f" * 64
        _write_json(inventory_path, inventory)

    def verifier(**kwargs):
        result = _verified_selection(**kwargs)
        if role == "selection_registry":
            registry = json.loads(
                (bundle / "selection_registry.json").read_text(encoding="utf-8")
            )
            registry["selections"][0]["case_id"] = CASE_ID
            _write_json(bundle / "selection_registry.json", registry)
        else:
            inventory = json.loads(
                (bundle / "source_inventory.json").read_text(encoding="utf-8")
            )
            inventory["entries"][0]["first_250_source_sha256"] = SOURCE_SHA256
            _write_json(bundle / "source_inventory.json", inventory)
        return result

    with pytest.raises(SelectedSourceValidationError, match="verified artifact"):
        _verify(source, bundle, verifier=verifier)


@pytest.mark.parametrize("defect", ["missing", "duplicate", "sha256", "bundle_sha256"])
def test_selected_source_wrapper_requires_unique_matching_verified_artifacts(
    tmp_path: Path, defect: str
) -> None:
    source, bundle = _build_bundle(tmp_path)

    def verifier(**kwargs):
        result = _verified_selection(**kwargs)
        artifacts = result["artifacts"]
        if defect == "missing":
            artifacts.pop()
        elif defect == "duplicate":
            artifacts.append(dict(artifacts[0]))
        else:
            artifacts[0][defect] = "f" * 64
        return result

    with pytest.raises(SelectedSourceValidationError, match="verified artifact"):
        _verify(source, bundle, verifier=verifier)


def test_selected_source_wrapper_accepts_real_task9_immutable_git_verification(
    tmp_path: Path,
) -> None:
    helper_path = Path(__file__).with_name("test_mnq_5m_checkpoint_verify.py")
    spec = importlib.util.spec_from_file_location("_task9_fixture_helpers", helper_path)
    assert spec is not None and spec.loader is not None
    helpers = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helpers
    spec.loader.exec_module(helpers)

    source = tmp_path / "bars.txt"
    source.write_bytes(b"real verified selected bytes\n")
    source_hash = _sha256(source)
    fixture = helpers._build_inventory_checkpoints(
        tmp_path / "task9",
        calendar_scan_mutator=lambda scan: scan["observations"][0]["quality"].__setitem__(
            "first_250_source_sha256", source_hash
        ),
    )

    def real_verifier(**kwargs):
        return helpers.checkpoint_verify._verify_selection_checkpoint_with_test_pinned_commit(
            **kwargs,
            expected_pinned_production_commit=fixture.pinned_commit,
        )

    with patch(
        "tools.validation.mnq_5m_selected_source_check.verify_selection_checkpoint",
        side_effect=real_verifier,
    ):
        result = verify_selected_source_hash(
            source_path=source,
            case_id="mnq-202609-5m-td2026-06-22-w01",
            repository_path=fixture.repo,
            inventory_checkpoint_bundle_root=fixture.bundle,
            trusted_toolset_checkpoint=fixture.toolset_checkpoint,
            trusted_inventory_checkpoint=fixture.inventory_checkpoint,
            trusted_selection_checkpoint=fixture.selection_checkpoint,
            expected_repository_identity=helpers.REPOSITORY_IDENTITY,
        )

    assert result.case_id == "mnq-202609-5m-td2026-06-22-w01"
    assert result.trading_date == "2026-06-22"
    assert result.expected_sha256 == source_hash
    assert result.observed_sha256 == source_hash
