"""Verify frozen MNQ validation checkpoints from immutable Git objects.

This module validates acquisition tooling and selection inputs only. It never
imports or executes hierarchy, oracle, project-result, or comparison code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

try:
    from tools.validation.mnq_5m_inventory_common import reconcile_inventory_entries
except ModuleNotFoundError:  # pragma: no cover - direct-script import path
    from mnq_5m_inventory_common import (  # type: ignore[no-redef]
        reconcile_inventory_entries,
    )


VERIFIER_VERSION = "2.0"
LEGACY_VERIFIER_VERSION = "1.0"
ATTESTATION_SCHEMA_VERSION = "1.0"
INVENTORY_ATTESTATION_SCHEMA_VERSION = "2.0"
DEFAULT_REPOSITORY_IDENTITY = "https://github.com/sikaodeluwei/trader_v1.git"
DEFAULT_PINNED_PRODUCTION_COMMIT = "04a73e1401d44688660b211d9db6918113482856"
TOOLSET_MANIFEST_REPOSITORY_PATH = (
    "validation/mnq_5m_multiwindow/toolset_manifest.json"
)
SELECTION_REGISTRY_REPOSITORY_PATH = (
    "validation/mnq_5m_multiwindow/selection_registry.json"
)
REQUIRED_SELECTION_PATHS = {
    "source_inventory": "validation/mnq_5m_multiwindow/source_inventory.json",
    "exclusion_ledger": "validation/mnq_5m_multiwindow/exclusions.json",
}
REQUIRED_TOOLSET_COMPONENT_PATHS = {
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
REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS = {
    "protocol_spec": (
        "docs/superpowers/specs/"
        "2026-09-13-mnq-5m-multiwindow-validation-design.md"
    ),
    "inventory_design_spec": (
        "docs/superpowers/specs/"
        "2026-09-16-mnq-5m-official-inventory-scanner-design.md"
    ),
    "validation_dependencies": "requirements-validation.txt",
    "acquisition_exporter": (
        "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs"
    ),
    "acquisition_finalizer": "tools/validation/mnq_5m_acquisition.py",
    "inventory_scanner": (
        "tools/validation/ninjatrader/ScanMnq5mSourceInventory.cs"
    ),
    "inventory_common": "tools/validation/mnq_5m_inventory_common.py",
    "inventory_evidence_finalizer": (
        "tools/validation/mnq_5m_inventory_evidence.py"
    ),
    "inventory_calendar_verifier": (
        "tools/validation/mnq_5m_inventory_calendar.py"
    ),
    "inventory_builder": "tools/validation/mnq_5m_inventory.py",
    "selection_generator": "tools/validation/mnq_5m_selection.py",
    "selected_source_checker": (
        "tools/validation/mnq_5m_selected_source_check.py"
    ),
    "checkpoint_verifier": "tools/validation/mnq_5m_checkpoint_verify.py",
    "provenance_schema": (
        "validation/mnq_5m_multiwindow/schemas/provenance_v1_3.schema.json"
    ),
    "inventory_scan_schema": (
        "validation/mnq_5m_multiwindow/schemas/inventory_scan.schema.json"
    ),
    "inventory_runtime_capture_schema": (
        "validation/mnq_5m_multiwindow/schemas/"
        "inventory_runtime_capture.schema.json"
    ),
    "inventory_acquisition_evidence_schema": (
        "validation/mnq_5m_multiwindow/schemas/"
        "inventory_acquisition_evidence.schema.json"
    ),
    "inventory_provenance_schema": (
        "validation/mnq_5m_multiwindow/schemas/inventory_provenance.schema.json"
    ),
    "checkpoint_attestation_schema": (
        "validation/mnq_5m_multiwindow/schemas/"
        "checkpoint_attestation_v2.schema.json"
    ),
    "selection_registry_schema": (
        "validation/mnq_5m_multiwindow/schemas/"
        "selection_registry_v2.schema.json"
    ),
    "toolset_manifest_schema": (
        "validation/mnq_5m_multiwindow/schemas/toolset_manifest_v2.schema.json"
    ),
    "source_inventory_schema": (
        "validation/mnq_5m_multiwindow/schemas/source_inventory_v2.schema.json"
    ),
    "exclusion_ledger_schema": (
        "validation/mnq_5m_multiwindow/schemas/exclusions_v2.schema.json"
    ),
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
INVENTORY_ARTIFACT_SCHEMA_VERSIONS = {
    "inventory_runtime_capture": "1.0",
    "inventory_scan": "1.0",
    "inventory_acquisition_evidence": "1.0",
    "inventory_provenance": "1.0",
    "source_inventory": "2.0",
    "exclusions": "2.0",
}
INVENTORY_SELECTION_REGISTRY_REPOSITORY_PATH = "selection_registry.json"


class CheckpointVerificationError(ValueError):
    """Raised when immutable Git objects cannot prove a frozen checkpoint."""


def _fail(message: str) -> None:
    raise CheckpointVerificationError(message)


def _immutable_object_id(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9a-f]{40}|[0-9a-f]{64}", value
    ) is None:
        _fail(f"{label} must be a full immutable Git object ID")
    return value


def _git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _run_git(
    repository: Path,
    *arguments: str,
    text: bool = True,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[Any]:
    text_options = {"encoding": "utf-8", "errors": "replace"} if text else {}
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=check,
            capture_output=True,
            text=text,
            timeout=timeout,
            env=_git_environment(),
            **text_options,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise CheckpointVerificationError(
            f"Git verification failed: {' '.join(arguments)}"
        ) from error


def _commit_exists(repository: Path, commit: str, label: str) -> None:
    try:
        _run_git(repository, "cat-file", "-e", f"{commit}^{{commit}}")
    except CheckpointVerificationError as error:
        raise CheckpointVerificationError(
            f"{label} {commit} does not exist as a commit"
        ) from error


def _assert_no_grafts(repository: Path) -> None:
    common_directory = Path(
        _run_git(
            repository,
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ).stdout.strip()
    )
    if (common_directory / "info" / "grafts").exists():
        _fail("Git graft metadata is not permitted during checkpoint verification")


def _assert_ancestor(
    repository: Path, ancestor: str, descendant: str, label: str
) -> None:
    pending = [descendant]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == ancestor:
            return
        if current in visited:
            continue
        visited.add(current)
        pending.extend(_raw_commit_parents(repository, current))
    _fail(f"{label}: {ancestor} is not an ancestor of {descendant}")


def _assert_strict_ancestor(
    repository: Path, ancestor: str, descendant: str, label: str
) -> None:
    if ancestor == descendant:
        _fail(f"{label}: stages must strictly precede one another")
    _assert_ancestor(repository, ancestor, descendant, label)


def _assert_direct_parent(
    repository: Path, parent: str, child: str, label: str
) -> None:
    if _raw_commit_parents(repository, child) != [parent]:
        _fail(f"{label}: producing checkpoint must be the direct parent")


def _raw_commit_parents(repository: Path, commit: str) -> list[str]:
    parents: list[str] = []
    for line in _run_git(repository, "cat-file", "-p", commit).stdout.splitlines():
        if not line:
            break
        if line.startswith("parent "):
            parents.append(
                _immutable_object_id(line.removeprefix("parent "), "commit parent")
            )
    return parents


def _repository_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"missing or invalid {label}")
    if "\\" in value:
        _fail(f"{label} must use repository-relative POSIX syntax")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        _fail(f"{label} must be repository-relative and contained")
    return path.as_posix()


def _bundle_path(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        _fail(f"missing or invalid {label}")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        _fail(f"{label} must be relative and contained")
    root_resolved = root.resolve()
    result = (root / relative).resolve()
    try:
        result.relative_to(root_resolved)
    except ValueError:
        _fail(f"{label} must be relative and contained")
    return result


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise CheckpointVerificationError(f"cannot read {label}") from error


def _git_bytes(repository: Path, commit: str, path: str, label: str) -> bytes:
    try:
        return _run_git(
            repository, "show", f"{commit}:{path}", text=False
        ).stdout
    except CheckpointVerificationError as error:
        raise CheckpointVerificationError(
            f"{label} is missing from checkpoint {commit}"
        ) from error


def _git_object_id(repository: Path, commit: str, path: str) -> str:
    return _run_git(repository, "rev-parse", f"{commit}:{path}").stdout.strip()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json_bytes(value: bytes, label: str) -> dict[str, Any]:
    try:
        result = json.loads(value.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CheckpointVerificationError(f"invalid {label}") from error
    if not isinstance(result, dict):
        _fail(f"invalid {label}")
    return result


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("attestation_sha256", None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _sha256(encoded)


def _aggregate_payload_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("aggregate_payload_sha256", None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _sha256(encoded)


def _normalized_identity(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    return normalized[:-4] if normalized.lower().endswith(".git") else normalized


def _verify_exact_artifact(
    *,
    repository: Path,
    checkpoint: str,
    repository_path: str,
    bundle_bytes: bytes,
    role: str,
    stage: str,
) -> dict[str, Any]:
    committed = _git_bytes(
        repository, checkpoint, repository_path, f"{role} committed artifact"
    )
    if committed != bundle_bytes:
        _fail(f"{role} bundle bytes do not match committed bytes")
    return {
        "role": role,
        "stage": stage,
        "repository_path": repository_path,
        "checkpoint": checkpoint,
        "git_object_id": _git_object_id(repository, checkpoint, repository_path),
        "sha256": _sha256(committed),
        "bundle_sha256": _sha256(bundle_bytes),
    }


def _verify_remote(
    *,
    repository: Path,
    remote_name: str | None,
    remote_branch: str | None,
    expected_checkpoint: str,
) -> dict[str, Any]:
    if remote_name is None and remote_branch is None:
        return {"status": "NOT_CHECKED"}
    if not remote_name or not remote_branch:
        _fail("remote name and branch must be supplied together")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", remote_name) is None:
        _fail("remote name contains unsafe Git syntax")
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", remote_branch) is None
        or ".." in remote_branch
        or remote_branch.endswith(("/", ".", ".lock"))
    ):
        _fail("remote branch contains unsafe Git ref syntax")
    reference = f"refs/heads/{remote_branch}"
    try:
        completed = _run_git(
            repository,
            "ls-remote",
            "--heads",
            remote_name,
            reference,
            timeout=15,
        )
    except CheckpointVerificationError:
        return {
            "status": "UNAVAILABLE",
            "remote": remote_name,
            "branch": remote_branch,
            "expected_checkpoint": expected_checkpoint,
            "reason": "REMOTE_QUERY_FAILED",
        }
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    observed = lines[0].split()[0] if len(lines) == 1 else None
    if observed != expected_checkpoint:
        _fail(
            "remote branch mismatch: "
            f"expected {expected_checkpoint}, observed {observed or 'MISSING'}"
        )
    return {
        "status": "VERIFIED",
        "remote": remote_name,
        "branch": remote_branch,
        "expected_checkpoint": expected_checkpoint,
        "observed_checkpoint": observed,
    }


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"invalid {label}")
    return value


def _sequence(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"invalid {label}")
    return value


def _contained_bundle_input(
    bundle: Path, value: str | Path, label: str
) -> Path:
    candidate = Path(value)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (bundle / candidate).resolve()
    )
    try:
        resolved.relative_to(bundle)
    except ValueError:
        _fail(f"{label} must be contained in the bundle")
    return resolved


def _snapshot_path(
    snapshots: dict[Path, bytes], path: Path, label: str
) -> bytes:
    resolved = path.resolve()
    if resolved not in snapshots:
        snapshots[resolved] = _read_bytes(resolved, label)
    return snapshots[resolved]


def _validate_against_schema(
    document: Mapping[str, Any],
    schema_bytes: bytes,
    label: str,
    *,
    expected_pinned_production_commit: str,
) -> None:
    schema = _load_json_bytes(schema_bytes, f"{label} schema")
    if expected_pinned_production_commit != DEFAULT_PINNED_PRODUCTION_COMMIT:
        pending: list[object] = [schema]
        while pending:
            current = pending.pop()
            if isinstance(current, dict):
                properties = current.get("properties")
                if isinstance(properties, dict):
                    pinned = properties.get("pinned_production_hierarchy_commit")
                    if isinstance(pinned, dict) and "const" in pinned:
                        pinned["const"] = expected_pinned_production_commit
                pending.extend(current.values())
            elif isinstance(current, list):
                pending.extend(current)
    try:
        errors = sorted(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(dict(document)),
            key=lambda error: list(error.absolute_path),
        )
    except Exception as error:  # pragma: no cover - frozen schema defect
        raise CheckpointVerificationError(f"invalid frozen {label} schema") from error
    if errors:
        _fail(f"{label} schema validation failed: {errors[0].message}")


def _verify_inventory_toolset(
    *,
    repository: Path,
    bundle: Path,
    snapshots: dict[Path, bytes],
    manifest_bundle: Path,
    trusted_toolset_checkpoint: str,
    expected_pinned_production_commit: str,
) -> tuple[
    dict[str, Any],
    bytes,
    str,
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, bytes],
    str,
]:
    manifest_bytes = _snapshot_path(
        snapshots, manifest_bundle, "inventory toolset manifest"
    )
    manifest_record = _verify_exact_artifact(
        repository=repository,
        checkpoint=trusted_toolset_checkpoint,
        repository_path=TOOLSET_MANIFEST_REPOSITORY_PATH,
        bundle_bytes=manifest_bytes,
        role="toolset_manifest",
        stage="toolset",
    )
    manifest = _load_json_bytes(manifest_bytes, "inventory toolset manifest")
    if manifest.get("aggregate_payload_sha256") != _aggregate_payload_hash(manifest):
        _fail("inventory toolset manifest aggregate hash mismatch")
    if (
        manifest.get("pinned_production_hierarchy_commit")
        != expected_pinned_production_commit
    ):
        _fail("wrong pinned production hierarchy commit")

    manifest_producer = _immutable_object_id(
        manifest.get("producing_checkpoint"),
        "inventory toolset manifest producing checkpoint",
    )
    _commit_exists(
        repository,
        manifest_producer,
        "inventory toolset manifest producing checkpoint",
    )
    _assert_direct_parent(
        repository,
        manifest_producer,
        trusted_toolset_checkpoint,
        "inventory toolset manifest production ancestry",
    )
    manifest_record["producing_commit"] = manifest_producer

    components = _sequence(manifest.get("components"), "inventory toolset components")
    roles = [
        component.get("role") if isinstance(component, dict) else None
        for component in components
    ]
    if roles != list(REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS):
        _fail("inventory toolset manifest must contain the exact 23 component roles")

    artifacts = [manifest_record]
    by_role: dict[str, dict[str, Any]] = {}
    for component_value in components:
        component = _mapping(component_value, "inventory toolset component")
        role = component.get("role")
        if not isinstance(role, str) or role not in REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS:
            _fail("invalid inventory toolset component role")
        repository_relative = _repository_path(
            component.get("path"), f"inventory toolset component {role} path"
        )
        if repository_relative != REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS[role]:
            _fail(f"inventory toolset component {role} path mismatch")
        producer = _immutable_object_id(
            component.get("producing_commit"),
            f"inventory toolset component {role} producing commit",
        )
        if producer != manifest_producer:
            _fail(f"inventory toolset component {role} producing commit mismatch")
        produced_bytes = _git_bytes(
            repository,
            producer,
            repository_relative,
            f"inventory toolset component {role}",
        )
        frozen_bytes = _git_bytes(
            repository,
            trusted_toolset_checkpoint,
            repository_relative,
            f"inventory toolset component {role}",
        )
        declared_hash = component.get("sha256")
        if (
            not isinstance(declared_hash, str)
            or _sha256(produced_bytes) != declared_hash
            or _sha256(frozen_bytes) != declared_hash
        ):
            _fail(f"inventory toolset component {role} hash mismatch")
        bundle_path = _bundle_path(
            bundle,
            component.get("bundle_path"),
            f"inventory toolset component {role} bundle path",
        )
        bundled_bytes = _snapshot_path(
            snapshots, bundle_path, f"inventory toolset component {role}"
        )
        if bundled_bytes != frozen_bytes:
            _fail(
                f"inventory toolset component {role} bundle bytes "
                "do not match committed bytes"
            )
        record = {
            "role": role,
            "stage": "toolset",
            "repository_path": repository_relative,
            "checkpoint": trusted_toolset_checkpoint,
            "producing_commit": producer,
            "git_object_id": _git_object_id(
                repository, trusted_toolset_checkpoint, repository_relative
            ),
            "sha256": declared_hash,
            "bundle_sha256": _sha256(bundled_bytes),
        }
        artifacts.append(record)
        by_role[role] = record

    schema_bytes = {
        role: _git_bytes(
            repository,
            trusted_toolset_checkpoint,
            REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS[role],
            f"frozen {role}",
        )
        for role in (
            "toolset_manifest_schema",
            "inventory_scan_schema",
            "inventory_runtime_capture_schema",
            "inventory_acquisition_evidence_schema",
            "inventory_provenance_schema",
            "source_inventory_schema",
            "exclusion_ledger_schema",
            "selection_registry_schema",
            "checkpoint_attestation_schema",
        )
    }
    _validate_against_schema(
        manifest,
        schema_bytes["toolset_manifest_schema"],
        "inventory toolset manifest",
        expected_pinned_production_commit=expected_pinned_production_commit,
    )

    verifier_component = by_role.get("checkpoint_verifier")
    if verifier_component is None:
        _fail("inventory toolset is missing checkpoint_verifier")
    executing_verifier_hash = _sha256(Path(__file__).read_bytes())
    if executing_verifier_hash != verifier_component["sha256"]:
        _fail("executing verifier differs from frozen tool identity")
    return (
        manifest,
        manifest_bytes,
        manifest_producer,
        artifacts,
        by_role,
        schema_bytes,
        executing_verifier_hash,
    )


def verify_inventory_toolset_checkpoint(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    trusted_toolset_checkpoint: str,
    expected_repository_identity: str,
    expected_pinned_production_commit: str,
) -> dict[str, Any]:
    """Verify the frozen inventory policy toolset before Task 7 executes."""

    repository = Path(repository_path).resolve()
    bundle = Path(bundle_root).resolve()
    if not repository.is_dir() or not bundle.is_dir():
        _fail("repository and bundle roots must exist")
    _assert_no_grafts(repository)
    trusted = _immutable_object_id(
        trusted_toolset_checkpoint, "trusted toolset checkpoint"
    )
    pinned = _immutable_object_id(
        expected_pinned_production_commit, "pinned production checkpoint"
    )
    actual_identity = _run_git(
        repository, "config", "--get", "remote.origin.url"
    ).stdout.strip()
    if _normalized_identity(actual_identity) != _normalized_identity(
        expected_repository_identity
    ):
        _fail("repository identity does not match the expected trader_v1 repository")
    _commit_exists(repository, pinned, "pinned production checkpoint")
    _commit_exists(repository, trusted, "trusted toolset checkpoint")
    _assert_strict_ancestor(
        repository,
        pinned,
        trusted,
        "pinned production/toolset ancestry",
    )

    manifest_bundle = _contained_bundle_input(
        bundle, toolset_manifest_path, "toolset manifest path"
    )
    snapshots: dict[Path, bytes] = {}
    (
        _manifest,
        manifest_bytes,
        manifest_producer,
        artifacts,
        component_records,
        _schema_bytes,
        executing_verifier_hash,
    ) = _verify_inventory_toolset(
        repository=repository,
        bundle=bundle,
        snapshots=snapshots,
        manifest_bundle=manifest_bundle,
        trusted_toolset_checkpoint=trusted,
        expected_pinned_production_commit=pinned,
    )

    executing_modules = {
        "inventory_builder": "tools.validation.mnq_5m_inventory",
        "inventory_calendar_verifier": "tools.validation.mnq_5m_inventory_calendar",
        "inventory_evidence_finalizer": "tools.validation.mnq_5m_inventory_evidence",
        "inventory_common": "tools.validation.mnq_5m_inventory_common",
        "checkpoint_verifier": __name__,
    }
    for role, module_name in executing_modules.items():
        module = sys.modules.get(module_name)
        module_path_value = getattr(module, "__file__", None) if module is not None else None
        expected_path = (
            repository / REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS[role]
        ).resolve()
        if not isinstance(module_path_value, str) or Path(module_path_value).resolve() != expected_path:
            _fail(f"executing {role} path differs from frozen tool identity")
        if _sha256(_snapshot_path(snapshots, expected_path, f"executing {role}")) != component_records[role]["sha256"]:
            _fail(f"executing {role} differs from frozen tool identity")

    executing_root = Path(__file__).resolve().parents[2]
    for role in (
        "toolset_manifest_schema",
        "inventory_scan_schema",
        "inventory_runtime_capture_schema",
        "inventory_acquisition_evidence_schema",
        "inventory_provenance_schema",
        "source_inventory_schema",
        "exclusion_ledger_schema",
        "selection_registry_schema",
        "checkpoint_attestation_schema",
    ):
        expected_path = (
            repository / REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS[role]
        ).resolve()
        executing_path = (
            executing_root / REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS[role]
        ).resolve()
        if executing_path != expected_path:
            _fail(f"executing {role} path differs from frozen tool identity")
        if _sha256(_snapshot_path(snapshots, executing_path, f"executing {role}")) != component_records[role]["sha256"]:
            _fail(f"executing {role} differs from frozen tool identity")

    return {
        "status": "VERIFIED",
        "trusted_toolset_checkpoint": trusted,
        "producing_checkpoint": manifest_producer,
        "manifest_sha256": _sha256(manifest_bytes),
        "component_count": len(component_records),
        "artifacts": artifacts,
        "executing_verifier_sha256": executing_verifier_hash,
    }


def _verify_inventory_documents(
    *,
    repository: Path,
    bundle: Path,
    snapshots: dict[Path, bytes],
    inventory_artifact_paths: Mapping[str, str | Path],
    trusted_toolset_checkpoint: str,
    trusted_inventory_checkpoint: str,
    trusted_selection_checkpoint: str | None,
    manifest: Mapping[str, Any],
    manifest_bytes: bytes,
    manifest_producer: str,
    component_records: Mapping[str, Mapping[str, Any]],
    schema_bytes: Mapping[str, bytes],
    expected_pinned_production_commit: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, bytes]]:
    if set(inventory_artifact_paths) != set(INVENTORY_ARTIFACT_REPOSITORY_PATHS):
        _fail("inventory checkpoint requires the exact inventory artifact roles")

    bundle_paths = {
        role: _contained_bundle_input(
            bundle, inventory_artifact_paths[role], f"{role} bundle path"
        )
        for role in INVENTORY_ARTIFACT_REPOSITORY_PATHS
    }
    artifact_bytes = {
        role: _snapshot_path(snapshots, path, role)
        for role, path in bundle_paths.items()
    }
    records: list[dict[str, Any]] = []
    for role, repository_path in INVENTORY_ARTIFACT_REPOSITORY_PATHS.items():
        record = _verify_exact_artifact(
            repository=repository,
            checkpoint=trusted_inventory_checkpoint,
            repository_path=repository_path,
            bundle_bytes=artifact_bytes[role],
            role=role,
            stage="inventory",
        )
        record["producing_checkpoint"] = trusted_toolset_checkpoint
        records.append(record)
        if trusted_selection_checkpoint is not None:
            selection_bytes = _git_bytes(
                repository,
                trusted_selection_checkpoint,
                repository_path,
                f"{role} at selection checkpoint",
            )
            if selection_bytes != artifact_bytes[role]:
                _fail(f"{role} changed after the inventory checkpoint")

    documents: dict[str, dict[str, Any]] = {}
    for role in INVENTORY_ARTIFACT_SCHEMA_VERSIONS:
        documents[role] = _load_json_bytes(artifact_bytes[role], role)

    for role, schema_role, label in (
        (
            "inventory_runtime_capture",
            "inventory_runtime_capture_schema",
            "inventory runtime capture",
        ),
        ("inventory_scan", "inventory_scan_schema", "inventory scan"),
        (
            "inventory_acquisition_evidence",
            "inventory_acquisition_evidence_schema",
            "inventory acquisition evidence",
        ),
        (
            "inventory_provenance",
            "inventory_provenance_schema",
            "inventory provenance",
        ),
    ):
        _validate_against_schema(
            documents[role],
            schema_bytes[schema_role],
            label,
            expected_pinned_production_commit=expected_pinned_production_commit,
        )

    evidence_roles = (
        "inventory_runtime_capture",
        "inventory_scan",
        "inventory_acquisition_evidence",
        "inventory_provenance",
    )
    acquisition_ids = [documents[role].get("acquisition_id") for role in evidence_roles]
    cohort_ids = [documents[role].get("cohort_id") for role in evidence_roles]
    provenance = documents["inventory_provenance"]
    provider_acquisition = _mapping(
        provenance.get("provider_acquisition"),
        "inventory provenance provider acquisition",
    )
    if (
        not all(value == acquisition_ids[0] for value in acquisition_ids)
        or provider_acquisition.get("acquisition_id") != acquisition_ids[0]
    ):
        _fail("inventory evidence acquisition identity mismatch")
    if not all(value == cohort_ids[0] for value in cohort_ids):
        _fail("inventory evidence cohort identity mismatch")

    source_inventory = documents["source_inventory"]
    exclusions = documents["exclusions"]
    _validate_against_schema(
        source_inventory,
        schema_bytes["source_inventory_schema"],
        "source inventory",
        expected_pinned_production_commit=expected_pinned_production_commit,
    )
    _validate_against_schema(
        exclusions,
        schema_bytes["exclusion_ledger_schema"],
        "exclusions",
        expected_pinned_production_commit=expected_pinned_production_commit,
    )
    for label, document in (
        ("source inventory", source_inventory),
        ("exclusions", exclusions),
    ):
        if document.get("aggregate_payload_sha256") != _aggregate_payload_hash(
            document
        ):
            _fail(f"{label} aggregate hash mismatch")
        if document.get("producing_checkpoint") != trusted_toolset_checkpoint:
            _fail(f"{label} producing checkpoint mismatch")
    entries = _sequence(source_inventory.get("entries"), "source inventory entries")
    eligible_count = sum(
        1
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("eligible") is True
    )
    if (
        source_inventory.get("candidate_count") != len(entries)
        or source_inventory.get("eligible_count") != eligible_count
    ):
        _fail("source inventory count mismatch")
    if exclusions.get("source_inventory_sha256") != _sha256(
        artifact_bytes["source_inventory"]
    ):
        _fail("exclusions/source inventory exact-byte hash mismatch")
    if (
        exclusions.get("cohort_id") != source_inventory.get("cohort_id")
        or exclusions.get("cohort_outcome")
        != source_inventory.get("cohort_outcome")
    ):
        _fail("inventory/exclusions identity mismatch")
    try:
        reconcile_inventory_entries(source_inventory, exclusions)
    except ValueError as error:
        _fail(str(error))

    for reference_name, role in (
        ("inventory_scan", "inventory_scan"),
        ("inventory_provenance", "inventory_provenance"),
    ):
        reference = _mapping(
            source_inventory.get(reference_name),
            f"source inventory {reference_name}",
        )
        if (
            reference.get("path") != INVENTORY_ARTIFACT_REPOSITORY_PATHS[role]
            or reference.get("schema_version") != "1.0"
            or reference.get("sha256") != _sha256(artifact_bytes[role])
            or reference.get("producing_checkpoint")
            != trusted_toolset_checkpoint
        ):
            _fail(f"source inventory {reference_name} binding mismatch")

    provenance = documents["inventory_provenance"]
    hashes = _mapping(provenance.get("artifact_hashes"), "provenance artifact hashes")
    expected_hash_keys = {
        "inventory_scan",
        "inventory_runtime_capture",
        "inventory_acquisition_evidence",
        "scanner",
        "trading_hours_template",
        "ninjatrader_config",
        "ninjatrader_log",
        "ninjatrader_trace",
        "toolset_manifest",
    }
    if set(hashes) != expected_hash_keys:
        _fail("inventory provenance artifact hashes are incomplete")
    runtime = documents["inventory_runtime_capture"]
    runtime_hashes = _mapping(runtime.get("artifact_hashes"), "runtime artifact hashes")
    for role in (
        "inventory_scan",
        "inventory_runtime_capture",
        "inventory_acquisition_evidence",
        "trading_hours_template",
    ):
        if hashes.get(role) != _sha256(artifact_bytes[role]):
            _fail(f"inventory provenance {role} hash mismatch")
        if role in {"inventory_scan", "trading_hours_template"}:
            embedded = _mapping(runtime_hashes.get(role), f"runtime {role} hash")
            if embedded.get("sha256") != _sha256(artifact_bytes[role]):
                _fail(f"inventory runtime {role} hash mismatch")
    if hashes.get("toolset_manifest") != _sha256(manifest_bytes):
        _fail("inventory provenance toolset manifest hash mismatch")
    scanner = component_records.get("inventory_scanner")
    if scanner is None or hashes.get("scanner") != scanner.get("sha256"):
        _fail("inventory provenance scanner hash mismatch")
    scanner_identity = _mapping(runtime.get("scanner_identity"), "runtime scanner identity")
    embedded_scanner_hash = scanner_identity.get("scanner_sha256")
    if embedded_scanner_hash is not None and embedded_scanner_hash != scanner.get("sha256"):
        _fail("inventory runtime scanner hash mismatch")

    evidence = _sequence(
        provenance.get("external_evidence"), "inventory external evidence"
    )
    observed_roles: set[str] = set()
    for evidence_value in evidence:
        record = _mapping(evidence_value, "inventory external evidence record")
        role = record.get("role")
        if role not in {
            "ninjatrader_config",
            "ninjatrader_log",
            "ninjatrader_trace",
            "trading_hours_template",
        } or not isinstance(role, str):
            _fail("invalid inventory external evidence role")
        if role in observed_roles:
            _fail("duplicate inventory external evidence role")
        observed_roles.add(role)
        evidence_path = _contained_bundle_input(
            bundle,
            record.get("path"),
            f"external evidence {role} path",
        )
        evidence_bytes = _snapshot_path(
            snapshots, evidence_path, f"external evidence {role}"
        )
        if (
            record.get("sha256") != _sha256(evidence_bytes)
            or record.get("byte_length") != len(evidence_bytes)
            or hashes.get(role) != _sha256(evidence_bytes)
        ):
            _fail(f"external evidence {role} hash/length mismatch")
        if role == "ninjatrader_config":
            embedded = _mapping(runtime_hashes.get(role), f"runtime {role} hash")
            if embedded.get("sha256") != _sha256(evidence_bytes):
                _fail(f"inventory runtime {role} hash mismatch")
        if (
            role == "trading_hours_template"
            and evidence_bytes != artifact_bytes["trading_hours_template"]
        ):
            _fail("external Trading Hours evidence differs from committed artifact")
    if not {
        "ninjatrader_config",
        "ninjatrader_log",
        "ninjatrader_trace",
    }.issubset(observed_roles):
        _fail("inventory external evidence roles are incomplete")

    scan_binding = _mapping(
        provenance.get("inventory_scan_binding"),
        "inventory provenance scan binding",
    )
    if (
        scan_binding.get("path") != "inventory_scan.json"
        or scan_binding.get("schema_version") != "1.0"
        or scan_binding.get("sha256") != _sha256(artifact_bytes["inventory_scan"])
    ):
        _fail("inventory provenance scan binding mismatch")
    toolset_binding = _mapping(
        provenance.get("toolset_binding"), "inventory provenance toolset binding"
    )
    if (
        toolset_binding.get("schema_version") != "2.0"
        or toolset_binding.get("producing_checkpoint") != manifest_producer
        or toolset_binding.get("trusted_checkpoint") != trusted_toolset_checkpoint
        or toolset_binding.get("pinned_production_hierarchy_commit")
        != expected_pinned_production_commit
        or toolset_binding.get("aggregate_payload_sha256")
        != manifest.get("aggregate_payload_sha256")
    ):
        _fail("inventory provenance toolset binding mismatch")
    checkpoint_binding = _mapping(
        provenance.get("checkpoint_verification"),
        "inventory provenance checkpoint binding",
    )
    if (
        checkpoint_binding.get("status") != "VERIFIED"
        or checkpoint_binding.get("trusted_toolset_checkpoint")
        != trusted_toolset_checkpoint
        or checkpoint_binding.get("pinned_production_hierarchy_commit")
        != expected_pinned_production_commit
    ):
        _fail("inventory provenance checkpoint binding mismatch")
    acquisition = documents["inventory_acquisition_evidence"]
    if acquisition.get("expected_toolset_checkpoint") != trusted_toolset_checkpoint:
        _fail("inventory acquisition evidence toolset checkpoint mismatch")

    try:
        from tools.validation.mnq_5m_inventory import _session_entry
        from tools.validation.mnq_5m_inventory_calendar import verify_inventory_calendar
        from tools.validation.mnq_5m_inventory_evidence import InventoryValidationError
    except ModuleNotFoundError as error:  # pragma: no cover - direct-script invocation
        if error.name != "tools":
            raise
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from tools.validation.mnq_5m_inventory import _session_entry
        from tools.validation.mnq_5m_inventory_calendar import verify_inventory_calendar
        from tools.validation.mnq_5m_inventory_evidence import InventoryValidationError

    for role, module_name in (
        ("inventory_builder", "tools.validation.mnq_5m_inventory"),
        (
            "inventory_calendar_verifier",
            "tools.validation.mnq_5m_inventory_calendar",
        ),
    ):
        module = sys.modules.get(module_name)
        module_path_value = getattr(module, "__file__", None) if module is not None else None
        expected_path = (
            Path(__file__).resolve().parents[2]
            / REQUIRED_INVENTORY_TOOLSET_COMPONENT_PATHS[role]
        ).resolve()
        if not isinstance(module_path_value, str) or Path(module_path_value).resolve() != expected_path:
            _fail(f"executing {role} path differs from frozen tool identity")
        if _sha256(_snapshot_path(snapshots, expected_path, f"executing {role}")) != component_records[role]["sha256"]:
            _fail(f"executing {role} differs from frozen tool identity")

    try:
        calendar = verify_inventory_calendar(
            documents["inventory_scan"], artifact_bytes["trading_hours_template"]
        )
        expected_entries = [_session_entry(session) for session in calendar.sessions]
    except InventoryValidationError as error:
        _fail(f"inventory candidate calendar/quality binding invalid: {error}")
    calendar_binding = _mapping(
        provenance.get("calendar_binding"), "inventory provenance calendar binding"
    )
    expected_calendar_binding = {
        "status": "VERIFIED",
        "trading_hours_name": "CME US Index Futures ETH",
        "civil_date_start": "2026-06-22",
        "civil_date_end": "2026-07-24",
        "civil_date_count": 33,
        "session_count": len(calendar.sessions),
        "earliest_session_begin": calendar.earliest_session_begin.isoformat(),
        "latest_session_end": calendar.latest_session_end.isoformat(),
        "trading_hours_template_sha256": calendar.template_sha256,
        "calendar_binding_sha256": calendar.calendar_binding_sha256,
    }
    if calendar.date_disagreements:
        expected_calendar_binding["date_disagreements"] = [
            dict(witness) for witness in calendar.date_disagreements
        ]
    if dict(calendar_binding) != expected_calendar_binding:
        _fail("inventory provenance calendar binding contradicts verified calendar")
    if list(entries) != expected_entries:
        _fail("source inventory candidate facts contradict bound scan/calendar")
    return records, documents, artifact_bytes


def _verify_inventory_or_selection_checkpoint(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    inventory_artifact_paths: Mapping[str, str | Path],
    trusted_toolset_checkpoint: str,
    trusted_inventory_checkpoint: str,
    expected_repository_identity: str,
    expected_pinned_production_commit: str,
    selection_registry_path: str | Path | None = None,
    trusted_selection_checkpoint: str | None = None,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> dict[str, Any]:
    repository = Path(repository_path).resolve()
    bundle = Path(bundle_root).resolve()
    if not repository.is_dir() or not bundle.is_dir():
        _fail("repository and bundle roots must exist")
    _assert_no_grafts(repository)
    expected_pinned_production_commit = _immutable_object_id(
        expected_pinned_production_commit, "pinned production checkpoint"
    )
    trusted_toolset_checkpoint = _immutable_object_id(
        trusted_toolset_checkpoint, "trusted toolset checkpoint"
    )
    trusted_inventory_checkpoint = _immutable_object_id(
        trusted_inventory_checkpoint, "trusted inventory checkpoint"
    )
    selection_mode = trusted_selection_checkpoint is not None
    if selection_mode != (selection_registry_path is not None):
        _fail("selection registry and checkpoint must be supplied together")
    if trusted_selection_checkpoint is not None:
        trusted_selection_checkpoint = _immutable_object_id(
            trusted_selection_checkpoint, "trusted selection checkpoint"
        )

    actual_identity = _run_git(
        repository, "config", "--get", "remote.origin.url"
    ).stdout.strip()
    if _normalized_identity(actual_identity) != _normalized_identity(
        expected_repository_identity
    ):
        _fail("repository identity does not match the expected trader_v1 repository")
    for commit, label in (
        (expected_pinned_production_commit, "pinned production checkpoint"),
        (trusted_toolset_checkpoint, "trusted toolset checkpoint"),
        (trusted_inventory_checkpoint, "trusted inventory checkpoint"),
    ):
        _commit_exists(repository, commit, label)
    _assert_strict_ancestor(
        repository,
        expected_pinned_production_commit,
        trusted_toolset_checkpoint,
        "pinned production/toolset ancestry",
    )
    _assert_direct_parent(
        repository,
        trusted_toolset_checkpoint,
        trusted_inventory_checkpoint,
        "toolset/inventory ancestry",
    )
    if trusted_selection_checkpoint is not None:
        _commit_exists(
            repository, trusted_selection_checkpoint, "trusted selection checkpoint"
        )
        _assert_direct_parent(
            repository,
            trusted_inventory_checkpoint,
            trusted_selection_checkpoint,
            "inventory/selection ancestry",
        )

    manifest_bundle = _contained_bundle_input(
        bundle, toolset_manifest_path, "toolset manifest path"
    )
    snapshots: dict[Path, bytes] = {}
    (
        manifest,
        manifest_bytes,
        manifest_producer,
        artifacts,
        component_records,
        schema_bytes,
        executing_verifier_hash,
    ) = _verify_inventory_toolset(
        repository=repository,
        bundle=bundle,
        snapshots=snapshots,
        manifest_bundle=manifest_bundle,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        expected_pinned_production_commit=expected_pinned_production_commit,
    )
    for checkpoint, label in (
        (trusted_inventory_checkpoint, "inventory"),
        (trusted_selection_checkpoint, "selection"),
    ):
        if checkpoint is not None and _git_bytes(
            repository,
            checkpoint,
            TOOLSET_MANIFEST_REPOSITORY_PATH,
            f"toolset manifest at {label} checkpoint",
        ) != manifest_bytes:
            _fail(f"toolset manifest changed at {label} checkpoint")

    inventory_records, documents, inventory_bytes = _verify_inventory_documents(
        repository=repository,
        bundle=bundle,
        snapshots=snapshots,
        inventory_artifact_paths=inventory_artifact_paths,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        trusted_selection_checkpoint=trusted_selection_checkpoint,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        manifest_producer=manifest_producer,
        component_records=component_records,
        schema_bytes=schema_bytes,
        expected_pinned_production_commit=expected_pinned_production_commit,
    )
    artifacts.extend(inventory_records)

    if trusted_selection_checkpoint is not None and selection_registry_path is not None:
        registry_bundle = _contained_bundle_input(
            bundle, selection_registry_path, "selection registry path"
        )
        registry_bytes = _snapshot_path(
            snapshots, registry_bundle, "selection registry"
        )
        registry_record = _verify_exact_artifact(
            repository=repository,
            checkpoint=trusted_selection_checkpoint,
            repository_path=INVENTORY_SELECTION_REGISTRY_REPOSITORY_PATH,
            bundle_bytes=registry_bytes,
            role="selection_registry",
            stage="selection",
        )
        registry_record["producing_checkpoint"] = trusted_inventory_checkpoint
        registry = _load_json_bytes(registry_bytes, "selection registry")
        _validate_against_schema(
            registry,
            schema_bytes["selection_registry_schema"],
            "selection registry",
            expected_pinned_production_commit=expected_pinned_production_commit,
        )
        if registry.get("aggregate_payload_sha256") != _aggregate_payload_hash(
            registry
        ):
            _fail("selection registry aggregate hash mismatch")
        if (
            registry.get("trusted_inventory_checkpoint")
            != trusted_inventory_checkpoint
            or registry.get("producing_checkpoint") != trusted_inventory_checkpoint
        ):
            _fail("selection registry checkpoint binding mismatch")
        for reference_name, role in (
            ("source_inventory", "source_inventory"),
            ("exclusion_ledger", "exclusions"),
        ):
            reference = _mapping(
                registry.get(reference_name), f"selection registry {reference_name}"
            )
            if (
                reference.get("path") != INVENTORY_ARTIFACT_REPOSITORY_PATHS[role]
                or reference.get("bundle_path")
                != INVENTORY_ARTIFACT_REPOSITORY_PATHS[role]
                or reference.get("schema_version") != "2.0"
                or reference.get("sha256") != _sha256(inventory_bytes[role])
                or reference.get("producing_checkpoint")
                != trusted_toolset_checkpoint
            ):
                _fail(f"selection registry {reference_name} binding mismatch")
        artifacts.append(registry_record)

    expected_remote_checkpoint = (
        trusted_selection_checkpoint
        if trusted_selection_checkpoint is not None
        else trusted_inventory_checkpoint
    )
    remote = _verify_remote(
        repository=repository,
        remote_name=remote_name,
        remote_branch=remote_branch,
        expected_checkpoint=expected_remote_checkpoint,
    )
    object_format = _run_git(
        repository, "rev-parse", "--show-object-format"
    ).stdout.strip()
    ancestry = [
        {
            "ancestor": expected_pinned_production_commit,
            "descendant": trusted_toolset_checkpoint,
            "verified": True,
        },
        {
            "ancestor": trusted_toolset_checkpoint,
            "descendant": trusted_inventory_checkpoint,
            "verified": True,
        },
    ]
    if trusted_selection_checkpoint is not None:
        ancestry.append(
            {
                "ancestor": trusted_inventory_checkpoint,
                "descendant": trusted_selection_checkpoint,
                "verified": True,
            }
        )
    verifier_component = component_records["checkpoint_verifier"]
    result: dict[str, Any] = {
        "schema_version": INVENTORY_ATTESTATION_SCHEMA_VERSION,
        "stage": "SELECTION" if selection_mode else "INVENTORY",
        "status": "VERIFIED",
        "repository": {
            "identity": expected_repository_identity,
            "git_object_format": object_format,
        },
        "trusted_toolset_checkpoint": trusted_toolset_checkpoint,
        "trusted_inventory_checkpoint": trusted_inventory_checkpoint,
        "pinned_production_hierarchy_commit": expected_pinned_production_commit,
        "artifacts": sorted(
            artifacts, key=lambda item: (item["stage"], item["role"])
        ),
        "ancestry": ancestry,
        "remote_publication": remote,
        "verifier": {
            "version": VERIFIER_VERSION,
            "repository_path": verifier_component["repository_path"],
            "producing_commit": verifier_component["producing_commit"],
            "frozen_sha256": verifier_component["sha256"],
            "executing_sha256": executing_verifier_hash,
        },
    }
    if trusted_selection_checkpoint is not None:
        result["trusted_selection_checkpoint"] = trusted_selection_checkpoint
    if result["verifier"]["frozen_sha256"] != result["verifier"]["executing_sha256"]:
        _fail("executing verifier differs from frozen tool identity")
    result["attestation_sha256"] = _canonical_hash(result)
    _validate_against_schema(
        result,
        schema_bytes["checkpoint_attestation_schema"],
        "checkpoint attestation",
        expected_pinned_production_commit=expected_pinned_production_commit,
    )
    return result


def _verify_inventory_checkpoint_with_test_pinned_commit(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    inventory_artifact_paths: Mapping[str, str | Path],
    trusted_toolset_checkpoint: str,
    trusted_inventory_checkpoint: str,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    expected_pinned_production_commit: str,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> dict[str, Any]:
    return _verify_inventory_or_selection_checkpoint(
        repository_path=repository_path,
        bundle_root=bundle_root,
        toolset_manifest_path=toolset_manifest_path,
        inventory_artifact_paths=inventory_artifact_paths,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        expected_repository_identity=expected_repository_identity,
        expected_pinned_production_commit=expected_pinned_production_commit,
        remote_name=remote_name,
        remote_branch=remote_branch,
    )


def _verify_selection_checkpoint_with_test_pinned_commit(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    inventory_artifact_paths: Mapping[str, str | Path],
    selection_registry_path: str | Path,
    trusted_toolset_checkpoint: str,
    trusted_inventory_checkpoint: str,
    trusted_selection_checkpoint: str,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    expected_pinned_production_commit: str,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> dict[str, Any]:
    return _verify_inventory_or_selection_checkpoint(
        repository_path=repository_path,
        bundle_root=bundle_root,
        toolset_manifest_path=toolset_manifest_path,
        inventory_artifact_paths=inventory_artifact_paths,
        selection_registry_path=selection_registry_path,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        trusted_selection_checkpoint=trusted_selection_checkpoint,
        expected_repository_identity=expected_repository_identity,
        expected_pinned_production_commit=expected_pinned_production_commit,
        remote_name=remote_name,
        remote_branch=remote_branch,
    )


def verify_inventory_checkpoint(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    inventory_artifact_paths: Mapping[str, str | Path],
    trusted_toolset_checkpoint: str,
    trusted_inventory_checkpoint: str,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> dict[str, Any]:
    """Verify a first-class inventory checkpoint from immutable bytes."""

    return _verify_inventory_checkpoint_with_test_pinned_commit(
        repository_path=repository_path,
        bundle_root=bundle_root,
        toolset_manifest_path=toolset_manifest_path,
        inventory_artifact_paths=inventory_artifact_paths,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        expected_repository_identity=expected_repository_identity,
        expected_pinned_production_commit=DEFAULT_PINNED_PRODUCTION_COMMIT,
        remote_name=remote_name,
        remote_branch=remote_branch,
    )


def verify_selection_checkpoint(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    inventory_artifact_paths: Mapping[str, str | Path],
    selection_registry_path: str | Path,
    trusted_toolset_checkpoint: str,
    trusted_inventory_checkpoint: str,
    trusted_selection_checkpoint: str,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> dict[str, Any]:
    """Verify selection as the direct child of a trusted inventory stage."""

    return _verify_selection_checkpoint_with_test_pinned_commit(
        repository_path=repository_path,
        bundle_root=bundle_root,
        toolset_manifest_path=toolset_manifest_path,
        inventory_artifact_paths=inventory_artifact_paths,
        selection_registry_path=selection_registry_path,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        trusted_selection_checkpoint=trusted_selection_checkpoint,
        expected_repository_identity=expected_repository_identity,
        expected_pinned_production_commit=DEFAULT_PINNED_PRODUCTION_COMMIT,
        remote_name=remote_name,
        remote_branch=remote_branch,
    )


def _verify_checkpoints_with_test_pinned_commit(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    selection_registry_path: str | Path,
    trusted_toolset_checkpoint: str,
    trusted_selection_checkpoint: str,
    trusted_acquisition_checkpoint: str | None = None,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    expected_pinned_production_commit: str,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> dict[str, Any]:
    """Verify frozen artifacts directly from trusted immutable Git commits."""

    repository = Path(repository_path).resolve()
    bundle = Path(bundle_root).resolve()
    if not repository.is_dir() or not bundle.is_dir():
        _fail("repository and bundle roots must exist")
    _assert_no_grafts(repository)
    expected_pinned_production_commit = _immutable_object_id(
        expected_pinned_production_commit, "pinned production checkpoint"
    )
    trusted_toolset_checkpoint = _immutable_object_id(
        trusted_toolset_checkpoint, "trusted toolset checkpoint"
    )
    trusted_selection_checkpoint = _immutable_object_id(
        trusted_selection_checkpoint, "trusted selection checkpoint"
    )
    if trusted_acquisition_checkpoint is not None:
        trusted_acquisition_checkpoint = _immutable_object_id(
            trusted_acquisition_checkpoint, "trusted acquisition checkpoint"
        )
    actual_identity = _run_git(
        repository, "config", "--get", "remote.origin.url"
    ).stdout.strip()
    if _normalized_identity(actual_identity) != _normalized_identity(
        expected_repository_identity
    ):
        _fail("repository identity does not match the expected trader_v1 repository")

    for commit, label in (
        (expected_pinned_production_commit, "pinned production checkpoint"),
        (trusted_toolset_checkpoint, "trusted toolset checkpoint"),
        (trusted_selection_checkpoint, "trusted selection checkpoint"),
    ):
        _commit_exists(repository, commit, label)
    _assert_strict_ancestor(
        repository,
        expected_pinned_production_commit,
        trusted_toolset_checkpoint,
        "pinned production/toolset ancestry",
    )
    _assert_strict_ancestor(
        repository,
        trusted_toolset_checkpoint,
        trusted_selection_checkpoint,
        "toolset/selection ancestry",
    )
    if trusted_acquisition_checkpoint is not None:
        _commit_exists(
            repository,
            trusted_acquisition_checkpoint,
            "trusted acquisition checkpoint",
        )
        _assert_strict_ancestor(
            repository,
            trusted_selection_checkpoint,
            trusted_acquisition_checkpoint,
            "selection/acquisition ancestry",
        )

    manifest_bundle = Path(toolset_manifest_path).resolve()
    registry_bundle = Path(selection_registry_path).resolve()
    try:
        manifest_bundle.relative_to(bundle)
        registry_bundle.relative_to(bundle)
    except ValueError:
        _fail("manifest and registry paths must be contained in the bundle")

    artifacts: list[dict[str, Any]] = []
    manifest_bytes = _read_bytes(manifest_bundle, "toolset manifest")
    manifest_record = _verify_exact_artifact(
        repository=repository,
        checkpoint=trusted_toolset_checkpoint,
        repository_path=TOOLSET_MANIFEST_REPOSITORY_PATH,
        bundle_bytes=manifest_bytes,
        role="toolset_manifest",
        stage="toolset",
    )
    manifest = _load_json_bytes(manifest_bytes, "toolset manifest")
    if manifest.get("aggregate_payload_sha256") != _aggregate_payload_hash(manifest):
        _fail("toolset manifest aggregate hash mismatch")
    if (
        manifest.get("pinned_production_hierarchy_commit")
        != expected_pinned_production_commit
    ):
        _fail("wrong pinned production hierarchy commit")
    manifest_producer = _immutable_object_id(
        manifest.get("producing_checkpoint"),
        "toolset manifest producing checkpoint",
    )
    # A self-describing Git commit cannot embed its own object ID. This field
    # therefore anchors the completed component stage immediately preceding
    # the trusted commit that contains the manifest itself.
    _commit_exists(
        repository, manifest_producer, "toolset manifest producing checkpoint"
    )
    _assert_direct_parent(
        repository,
        manifest_producer,
        trusted_toolset_checkpoint,
        "toolset manifest production ancestry",
    )
    artifacts.append(manifest_record)

    components = manifest.get("components")
    if not isinstance(components, list):
        _fail("invalid toolset manifest components")
    component_roles = [
        component.get("role") if isinstance(component, dict) else None
        for component in components
    ]
    if (
        len(component_roles) != len(REQUIRED_TOOLSET_COMPONENT_PATHS)
        or len(set(component_roles)) != len(component_roles)
        or set(component_roles) != set(REQUIRED_TOOLSET_COMPONENT_PATHS)
    ):
        _fail("toolset manifest must contain the exact required component roles")
    verifier_component: dict[str, Any] | None = None
    for component_value in components:
        if not isinstance(component_value, dict):
            _fail("invalid toolset manifest component")
        role = component_value.get("role")
        if not isinstance(role, str) or not role:
            _fail("invalid toolset manifest component role")
        repository_relative = _repository_path(
            component_value.get("path"), f"toolset component {role} path"
        )
        if repository_relative != REQUIRED_TOOLSET_COMPONENT_PATHS[role]:
            _fail(f"toolset component {role} path mismatch")
        producer = _immutable_object_id(
            component_value.get("producing_commit"),
            f"toolset component {role} producing commit",
        )
        _commit_exists(
            repository, producer, f"toolset component {role} producing commit"
        )
        _assert_ancestor(
            repository,
            producer,
            trusted_toolset_checkpoint,
            f"toolset component {role} ancestry",
        )
        produced_bytes = _git_bytes(
            repository, producer, repository_relative, f"toolset component {role}"
        )
        frozen_bytes = _git_bytes(
            repository,
            trusted_toolset_checkpoint,
            repository_relative,
            f"toolset component {role}",
        )
        declared_hash = component_value.get("sha256")
        if (
            not isinstance(declared_hash, str)
            or _sha256(produced_bytes) != declared_hash
            or _sha256(frozen_bytes) != declared_hash
        ):
            _fail(f"toolset component {role} hash/producing commit mismatch")
        component_bundle = _bundle_path(
            bundle,
            component_value.get("bundle_path"),
            f"toolset component {role} bundle path",
        )
        bundled_bytes = _read_bytes(component_bundle, f"toolset component {role}")
        if bundled_bytes != frozen_bytes:
            _fail(f"toolset component {role} bundle bytes do not match committed bytes")
        record = {
            "role": role,
            "stage": "toolset",
            "repository_path": repository_relative,
            "checkpoint": trusted_toolset_checkpoint,
            "producing_commit": producer,
            "git_object_id": _git_object_id(
                repository, trusted_toolset_checkpoint, repository_relative
            ),
            "sha256": declared_hash,
            "bundle_sha256": _sha256(bundled_bytes),
        }
        artifacts.append(record)
        if role == "checkpoint_verifier":
            verifier_component = record

    if verifier_component is None:
        _fail("toolset manifest is missing checkpoint_verifier")
    executing_verifier_hash = _sha256(Path(__file__).read_bytes())
    if executing_verifier_hash != verifier_component["sha256"]:
        _fail("executing verifier differs from frozen tool identity")
    finalizer_components = [
        item for item in artifacts if item.get("role") == "acquisition_finalizer"
    ]
    executing_finalizer = Path(__file__).with_name("mnq_5m_acquisition.py")
    if (
        len(finalizer_components) != 1
        or _sha256(executing_finalizer.read_bytes())
        != finalizer_components[0]["sha256"]
    ):
        _fail("executing finalizer differs from frozen tool identity")

    artifacts.append(
        _verify_exact_artifact(
            repository=repository,
            checkpoint=trusted_selection_checkpoint,
            repository_path=TOOLSET_MANIFEST_REPOSITORY_PATH,
            bundle_bytes=manifest_bytes,
            role="toolset_manifest_at_selection",
            stage="selection",
        )
    )
    registry_bytes = _read_bytes(registry_bundle, "selection registry")
    registry_record = _verify_exact_artifact(
        repository=repository,
        checkpoint=trusted_selection_checkpoint,
        repository_path=SELECTION_REGISTRY_REPOSITORY_PATH,
        bundle_bytes=registry_bytes,
        role="selection_registry",
        stage="selection",
    )
    artifacts.append(registry_record)
    registry = _load_json_bytes(registry_bytes, "selection registry")
    if registry.get("aggregate_payload_sha256") != _aggregate_payload_hash(registry):
        _fail("selection registry aggregate hash mismatch")
    registry_producer = _immutable_object_id(
        registry.get("producing_checkpoint"),
        "selection registry producing checkpoint",
    )
    # Likewise, the registry producer is the predecessor checkpoint containing
    # the inventory and exclusions; the trusted selection commit contains the
    # registry itself.
    _commit_exists(
        repository, registry_producer, "selection registry producing checkpoint"
    )
    _assert_direct_parent(
        repository,
        registry_producer,
        trusted_selection_checkpoint,
        "selection registry production ancestry",
    )

    for reference_name, expected_path in REQUIRED_SELECTION_PATHS.items():
        reference = registry.get(reference_name)
        if not isinstance(reference, dict):
            _fail(f"missing selection registry {reference_name}")
        repository_relative = _repository_path(
            reference.get("path"), f"selection registry {reference_name} path"
        )
        if repository_relative != expected_path:
            _fail(f"selection registry {reference_name} path mismatch")
        producer = _immutable_object_id(
            reference.get("producing_checkpoint"),
            f"selection registry {reference_name} checkpoint",
        )
        if producer != registry_producer:
            _fail(
                f"selection registry {reference_name} producing checkpoint mismatch"
            )
        _commit_exists(
            repository,
            producer,
            f"selection registry {reference_name} checkpoint",
        )
        _assert_ancestor(
            repository,
            producer,
            trusted_selection_checkpoint,
            f"selection registry {reference_name} ancestry",
        )
        produced_bytes = _git_bytes(
            repository,
            producer,
            repository_relative,
            f"selection registry {reference_name} producing checkpoint artifact",
        )
        reference_bundle = _bundle_path(
            bundle,
            reference.get("bundle_path"),
            f"selection registry {reference_name} bundle path",
        )
        reference_bytes = _read_bytes(
            reference_bundle, f"selection registry {reference_name} bundle artifact"
        )
        record = _verify_exact_artifact(
            repository=repository,
            checkpoint=trusted_selection_checkpoint,
            repository_path=repository_relative,
            bundle_bytes=reference_bytes,
            role=reference_name,
            stage="selection",
        )
        declared_hash = reference.get("sha256")
        if (
            declared_hash != record["sha256"]
            or _sha256(produced_bytes) != declared_hash
        ):
            _fail(
                f"selection registry {reference_name} "
                "producing checkpoint/hash mismatch"
            )
        record["producing_checkpoint"] = producer
        artifacts.append(record)

    remote = _verify_remote(
        repository=repository,
        remote_name=remote_name,
        remote_branch=remote_branch,
        expected_checkpoint=trusted_selection_checkpoint,
    )
    object_format = _run_git(
        repository, "rev-parse", "--show-object-format"
    ).stdout.strip()
    ancestry = [
        {
            "ancestor": expected_pinned_production_commit,
            "descendant": trusted_toolset_checkpoint,
            "verified": True,
        },
        {
            "ancestor": trusted_toolset_checkpoint,
            "descendant": trusted_selection_checkpoint,
            "verified": True,
        },
    ]
    if trusted_acquisition_checkpoint is not None:
        ancestry.append(
            {
                "ancestor": trusted_selection_checkpoint,
                "descendant": trusted_acquisition_checkpoint,
                "verified": True,
            }
        )
    result: dict[str, Any] = {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "status": "VERIFIED",
        "repository": {
            "identity": expected_repository_identity,
            "git_object_format": object_format,
        },
        "trusted_toolset_checkpoint": trusted_toolset_checkpoint,
        "trusted_selection_checkpoint": trusted_selection_checkpoint,
        "pinned_production_hierarchy_commit": expected_pinned_production_commit,
        "artifacts": sorted(
            artifacts, key=lambda item: (item["stage"], item["role"])
        ),
        "ancestry": ancestry,
        "remote_publication": remote,
        "verifier": {
            "version": LEGACY_VERIFIER_VERSION,
            "repository_path": verifier_component["repository_path"],
            "producing_commit": verifier_component["producing_commit"],
            "frozen_sha256": verifier_component["sha256"],
            "executing_sha256": executing_verifier_hash,
        },
    }
    if trusted_acquisition_checkpoint is not None:
        result["trusted_acquisition_checkpoint"] = trusted_acquisition_checkpoint
    result["attestation_sha256"] = _canonical_hash(result)
    return result


def verify_checkpoints(
    *,
    repository_path: str | Path,
    bundle_root: str | Path,
    toolset_manifest_path: str | Path,
    selection_registry_path: str | Path,
    trusted_toolset_checkpoint: str,
    trusted_selection_checkpoint: str,
    trusted_acquisition_checkpoint: str | None = None,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> dict[str, Any]:
    """Verify official checkpoints against the fixed production hierarchy."""

    return _verify_checkpoints_with_test_pinned_commit(
        repository_path=repository_path,
        bundle_root=bundle_root,
        toolset_manifest_path=toolset_manifest_path,
        selection_registry_path=selection_registry_path,
        trusted_toolset_checkpoint=trusted_toolset_checkpoint,
        trusted_selection_checkpoint=trusted_selection_checkpoint,
        trusted_acquisition_checkpoint=trusted_acquisition_checkpoint,
        expected_repository_identity=expected_repository_identity,
        expected_pinned_production_commit=DEFAULT_PINNED_PRODUCTION_COMMIT,
        remote_name=remote_name,
        remote_branch=remote_branch,
    )


def _write_attestation(path: Path, result: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )


def _legacy_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify immutable MNQ validation Git checkpoints."
    )
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--toolset-manifest", required=True, type=Path)
    parser.add_argument("--selection-registry", required=True, type=Path)
    parser.add_argument("--trusted-toolset-checkpoint", required=True)
    parser.add_argument("--trusted-selection-checkpoint", required=True)
    parser.add_argument("--trusted-acquisition-checkpoint")
    parser.add_argument("--repository-identity", default=DEFAULT_REPOSITORY_IDENTITY)
    parser.add_argument("--remote-name")
    parser.add_argument("--remote-branch")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_checkpoints(
            repository_path=args.repository,
            bundle_root=args.bundle_root,
            toolset_manifest_path=args.toolset_manifest,
            selection_registry_path=args.selection_registry,
            trusted_toolset_checkpoint=args.trusted_toolset_checkpoint,
            trusted_selection_checkpoint=args.trusted_selection_checkpoint,
            trusted_acquisition_checkpoint=args.trusted_acquisition_checkpoint,
            expected_repository_identity=args.repository_identity,
            remote_name=args.remote_name,
            remote_branch=args.remote_branch,
        )
    except CheckpointVerificationError as error:
        parser.exit(2, f"STOP: {error}\n")
    _write_attestation(args.output, result)
    return 0


def _v2_main(mode: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=f"mnq_5m_checkpoint_verify.py {mode}",
        description=f"Verify the immutable MNQ {mode} checkpoint.",
    )
    parser.add_argument("--repository-path", required=True, type=Path)
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--toolset-manifest", required=True, type=Path)
    parser.add_argument("--runtime-capture", required=True, type=Path)
    parser.add_argument("--inventory-scan", required=True, type=Path)
    parser.add_argument("--trading-hours-template", required=True, type=Path)
    parser.add_argument("--acquisition-evidence", required=True, type=Path)
    parser.add_argument("--inventory-provenance-input", required=True, type=Path)
    parser.add_argument("--source-inventory", required=True, type=Path)
    parser.add_argument("--exclusions", required=True, type=Path)
    parser.add_argument("--trusted-toolset-checkpoint", required=True)
    parser.add_argument("--trusted-inventory-checkpoint", required=True)
    if mode == "selection":
        parser.add_argument("--selection-registry", required=True, type=Path)
        parser.add_argument("--trusted-selection-checkpoint", required=True)
    parser.add_argument(
        "--expected-repository-identity",
        default=DEFAULT_REPOSITORY_IDENTITY,
    )
    parser.add_argument("--remote-name")
    parser.add_argument("--remote-branch")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    inventory_artifacts = {
        "inventory_runtime_capture": args.runtime_capture,
        "inventory_scan": args.inventory_scan,
        "trading_hours_template": args.trading_hours_template,
        "inventory_acquisition_evidence": args.acquisition_evidence,
        "inventory_provenance": args.inventory_provenance_input,
        "source_inventory": args.source_inventory,
        "exclusions": args.exclusions,
    }
    common = {
        "repository_path": args.repository_path,
        "bundle_root": args.bundle_root,
        "toolset_manifest_path": args.toolset_manifest,
        "inventory_artifact_paths": inventory_artifacts,
        "trusted_toolset_checkpoint": args.trusted_toolset_checkpoint,
        "trusted_inventory_checkpoint": args.trusted_inventory_checkpoint,
        "expected_repository_identity": args.expected_repository_identity,
        "remote_name": args.remote_name,
        "remote_branch": args.remote_branch,
    }
    try:
        if mode == "inventory":
            result = verify_inventory_checkpoint(**common)
        else:
            result = verify_selection_checkpoint(
                **common,
                selection_registry_path=args.selection_registry,
                trusted_selection_checkpoint=args.trusted_selection_checkpoint,
            )
    except CheckpointVerificationError as error:
        parser.exit(2, f"STOP: {error}\n")
    _write_attestation(args.output, result)
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in {"inventory", "selection"}:
        return _v2_main(arguments[0], arguments[1:])
    return _legacy_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
