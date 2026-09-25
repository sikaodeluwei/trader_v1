from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest

import tools.validation.mnq_5m_checkpoint_verify as checkpoint_verify
from tools.validation import mnq_5m_acquisition
from tools.validation.mnq_5m_checkpoint_verify import (
    CheckpointVerificationError,
    _verify_checkpoints_with_test_pinned_commit,
    main as verifier_main,
)


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


def _build_inventory_checkpoints(
    tmp_path: Path,
    *,
    fake_verifier: bool = False,
    manifest_mutator=None,
    provenance_mutator=None,
    inventory_mutator=None,
    registry_mutator=None,
) -> InventoryCheckpointFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = tmp_path / "inventory-repo"
    bundle = tmp_path / "inventory-bundle"
    repo.mkdir()
    bundle.mkdir()
    _git(repo, "init")
    _git(repo, "remote", "add", "origin", REPOSITORY_IDENTITY)

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

    raw_documents: dict[str, dict[str, object]] = {
        "inventory_runtime_capture": {
            "schema_version": "1.0",
            "acquisition_id": "inventory-acquisition",
        },
        "inventory_scan": {
            "schema_version": "1.0",
            "acquisition_id": "inventory-acquisition",
        },
        "inventory_acquisition_evidence": {
            "schema_version": "1.0",
            "acquisition_id": "inventory-acquisition",
            "expected_toolset_checkpoint": toolset_checkpoint,
        },
    }
    for role, value in raw_documents.items():
        _write_canonical_json(repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS[role], value)
    (repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["trading_hours_template"]).write_bytes(
        b"<TradingHours name=\"CME US Index Futures ETH\" />\n"
    )

    internal_hashes = {
        role: _sha256(repo / relative)
        for role, relative in INVENTORY_ARTIFACT_REPOSITORY_PATHS.items()
        if role
        in {
            "inventory_runtime_capture",
            "inventory_scan",
            "trading_hours_template",
            "inventory_acquisition_evidence",
        }
    }
    evidence_records = [
        {
            "role": role,
            "path": path.relative_to(bundle).as_posix(),
            "sha256": _sha256(path),
            "byte_length": len(path.read_bytes()),
        }
        for role, path in external_evidence.items()
    ]
    provenance: dict[str, object] = {
        "schema_version": "1.0",
        "status": "PROVEN",
        "artifact_hashes": {
            **internal_hashes,
            "scanner": _sha256_bytes(
                _git_blob(
                    repo,
                    component_commit,
                    EXPECTED_INVENTORY_TOOLSET_COMPONENT_PATHS["inventory_scanner"],
                )
            ),
            **{role: _sha256(path) for role, path in external_evidence.items()},
            "toolset_manifest": _sha256(repo / TOOLSET_MANIFEST_PATH),
        },
        "external_evidence": evidence_records,
        "inventory_scan_binding": {
            "path": "inventory_scan.json",
            "schema_version": "1.0",
            "sha256": internal_hashes["inventory_scan"],
        },
        "toolset_binding": {
            "status": "FROZEN_FOR_SOURCE_ACQUISITION",
            "stage": "SOURCE_ACQUISITION",
            "schema_version": "2.0",
            "producing_checkpoint": component_commit,
            "trusted_checkpoint": toolset_checkpoint,
            "pinned_production_hierarchy_commit": pinned_commit,
            "aggregate_payload_sha256": manifest["aggregate_payload_sha256"],
        },
        "checkpoint_verification": {
            "status": "VERIFIED",
            "trusted_toolset_checkpoint": toolset_checkpoint,
            "pinned_production_hierarchy_commit": pinned_commit,
        },
    }
    if provenance_mutator is not None:
        provenance_mutator(provenance)
    provenance_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["inventory_provenance"]
    _write_canonical_json(provenance_path, provenance)

    entries = []
    for number in range(1, 11):
        trading_date = f"2026-07-{number:02d}"
        entries.append(
            {
                "trading_date": trading_date,
                "eligible": True,
                "exclusion_reasons": [],
                "session_begin_application": f"202607{number:02d} 170000",
                "session_end_application": f"202607{number:02d} 160000",
                "observed_native_bar_count": 276,
                "first_250_source_sha256": "a" * 64,
                "complete_session_source_sha256": "b" * 64,
            }
        )
    policy = {
        "contract_label": "MNQ SEP26",
        "full_name": "MNQ SEP26",
        "expiry_month": 9,
        "expiry_year": 2026,
        "candidate_date_start": "2026-06-22",
        "candidate_date_end": "2026-07-24",
    }
    inventory: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_INVENTORY",
        "cohort_outcome": "READY_FOR_SELECTION",
        "cohort_id": "mnq-202609-5m-v1",
        "contract_policy": policy,
        "inventory_scan": {
            "path": "inventory_scan.json",
            "schema_version": "1.0",
            "sha256": internal_hashes["inventory_scan"],
            "producing_checkpoint": toolset_checkpoint,
        },
        "inventory_provenance": {
            "path": "inventory_provenance.json",
            "schema_version": "1.0",
            "sha256": _sha256(provenance_path),
            "producing_checkpoint": toolset_checkpoint,
        },
        "producing_checkpoint": toolset_checkpoint,
        "candidate_count": 10,
        "eligible_count": 10,
        "entries": entries,
        "aggregate_payload_sha256": "",
    }
    if inventory_mutator is not None:
        inventory_mutator(inventory)
    inventory_path = repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["source_inventory"]
    _write_canonical_json(inventory_path, inventory, aggregate=True)
    exclusions: dict[str, object] = {
        "schema_version": "2.0",
        "status": "FROZEN_INVENTORY",
        "cohort_outcome": "READY_FOR_SELECTION",
        "cohort_id": "mnq-202609-5m-v1",
        "source_inventory_sha256": _sha256(inventory_path),
        "producing_checkpoint": toolset_checkpoint,
        "entries": [],
        "aggregate_payload_sha256": "",
    }
    _write_canonical_json(
        repo / INVENTORY_ARTIFACT_REPOSITORY_PATHS["exclusions"],
        exclusions,
        aggregate=True,
    )
    inventory_checkpoint = _commit(repo, "Freeze inventory artifacts")

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
                "case_id": f"mnq-202609-5m-td2026-07-{number:02d}-w{number:02d}",
                "trading_date": f"2026-07-{number:02d}",
                "stratum_number": number,
                "stratum_start_index": number - 1,
                "stratum_end_index": number - 1,
                "selected_eligible_index": number - 1,
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
