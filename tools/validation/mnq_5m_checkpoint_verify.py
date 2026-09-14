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
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


VERIFIER_VERSION = "1.0"
ATTESTATION_SCHEMA_VERSION = "1.0"
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
            "version": VERIFIER_VERSION,
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


def main(argv: list[str] | None = None) -> int:
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
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
