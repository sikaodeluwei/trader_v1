from __future__ import annotations

import json
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
    }


def _verify(source: Path, bundle: Path, **overrides):
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
        side_effect=_verified_selection,
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
