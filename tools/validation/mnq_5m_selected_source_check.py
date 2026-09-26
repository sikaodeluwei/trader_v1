"""Stop unless selected MNQ source bytes match the frozen v2 inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from tools.validation.mnq_5m_checkpoint_verify import (
        DEFAULT_REPOSITORY_IDENTITY,
        CheckpointVerificationError,
        verify_selection_checkpoint,
    )
except ModuleNotFoundError as error:
    if error.name != "tools":
        raise
    from mnq_5m_checkpoint_verify import (  # type: ignore[no-redef]
        DEFAULT_REPOSITORY_IDENTITY,
        CheckpointVerificationError,
        verify_selection_checkpoint,
    )


INVENTORY_V2_CHECKPOINT_BUNDLE_PATHS: Mapping[str, str] = {
    "toolset_manifest": "toolset_manifest.json",
    "inventory_runtime_capture": "inventory_runtime_capture.json",
    "inventory_scan": "inventory_scan.json",
    "trading_hours_template": "trading_hours_template.xml",
    "inventory_acquisition_evidence": "inventory_acquisition_evidence.json",
    "inventory_provenance": "inventory_provenance.json",
    "source_inventory": "source_inventory.json",
    "exclusions": "exclusions.json",
    "selection_registry": "selection_registry.json",
}
_INVENTORY_ARTIFACT_ROLES = (
    "inventory_runtime_capture",
    "inventory_scan",
    "trading_hours_template",
    "inventory_acquisition_evidence",
    "inventory_provenance",
    "source_inventory",
    "exclusions",
)
_CASE_ID_RE = re.compile(
    r"^mnq-202609-5m-td(?P<trading_date>\d{4}-\d{2}-\d{2})-w(?:0[1-9]|10)$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SelectedSourceValidationError(ValueError):
    """Raised when selected bytes are not the uniquely frozen v2 case."""


@dataclass(frozen=True)
class SelectedSourceHashBinding:
    case_id: str
    trading_date: str
    expected_sha256: str
    observed_sha256: str
    trusted_inventory_checkpoint: str
    trusted_selection_checkpoint: str


def _fail(message: str) -> None:
    raise SelectedSourceValidationError(message)


def _contained_paths(root: Path) -> dict[str, Path]:
    resolved_root = root.resolve()
    paths: dict[str, Path] = {}
    for role, relative in INVENTORY_V2_CHECKPOINT_BUNDLE_PATHS.items():
        path = (resolved_root / relative).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError:
            _fail(f"inventory-v2 {role} path is not contained")
        paths[role] = path
    return paths


def _load_object_bytes(contents: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(contents.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SelectedSourceValidationError(f"invalid inventory-v2 {label}") from error
    if not isinstance(value, dict):
        _fail(f"invalid inventory-v2 {label}")
    return value


def _verified_artifact_bytes(
    verification: Mapping[str, Any],
    paths: Mapping[str, Path],
) -> dict[str, bytes]:
    artifacts = verification.get("artifacts")
    if not isinstance(artifacts, list):
        _fail("inventory-v2 verification did not return verified artifacts")
    result: dict[str, bytes] = {}
    for role, stage in (
        ("selection_registry", "selection"),
        ("source_inventory", "inventory"),
    ):
        matches = [
            artifact
            for artifact in artifacts
            if isinstance(artifact, dict)
            and artifact.get("role") == role
            and artifact.get("stage") == stage
        ]
        if len(matches) != 1:
            _fail(f"verified artifact is missing or duplicated: {role}")
        expected = matches[0].get("sha256")
        bundle_expected = matches[0].get("bundle_sha256")
        if (
            not isinstance(expected, str)
            or _SHA256_RE.fullmatch(expected) is None
            or not isinstance(bundle_expected, str)
            or _SHA256_RE.fullmatch(bundle_expected) is None
        ):
            _fail(f"verified artifact hash is invalid: {role}")
        try:
            contents = paths[role].read_bytes()
        except OSError as error:
            raise SelectedSourceValidationError(
                f"cannot read verified artifact: {role}"
            ) from error
        observed = hashlib.sha256(contents).hexdigest()
        if observed != expected or observed != bundle_expected:
            _fail(f"verified artifact bytes do not match verification: {role}")
        result[role] = contents
    return result


def verify_selected_source_hash(
    *,
    source_path: str | Path,
    case_id: str,
    repository_path: str | Path,
    inventory_checkpoint_bundle_root: str | Path,
    trusted_toolset_checkpoint: str,
    trusted_inventory_checkpoint: str,
    trusted_selection_checkpoint: str,
    expected_repository_identity: str = DEFAULT_REPOSITORY_IDENTITY,
    remote_name: str | None = None,
    remote_branch: str | None = None,
) -> SelectedSourceHashBinding:
    """Re-verify v2 checkpoints and stop unless selected bytes match."""

    bundle_root = Path(inventory_checkpoint_bundle_root)
    paths = _contained_paths(bundle_root)
    inventory_paths = {role: paths[role] for role in _INVENTORY_ARTIFACT_ROLES}
    try:
        verification = verify_selection_checkpoint(
            repository_path=repository_path,
            bundle_root=bundle_root,
            toolset_manifest_path=paths["toolset_manifest"],
            inventory_artifact_paths=inventory_paths,
            selection_registry_path=paths["selection_registry"],
            trusted_toolset_checkpoint=trusted_toolset_checkpoint,
            trusted_inventory_checkpoint=trusted_inventory_checkpoint,
            trusted_selection_checkpoint=trusted_selection_checkpoint,
            expected_repository_identity=expected_repository_identity,
            remote_name=remote_name,
            remote_branch=remote_branch,
        )
    except CheckpointVerificationError as error:
        raise SelectedSourceValidationError(
            f"independent inventory-v2 selection verification failed: {error}"
        ) from error
    if (
        verification.get("schema_version") != "2.0"
        or verification.get("stage") != "SELECTION"
        or verification.get("status") != "VERIFIED"
        or verification.get("trusted_toolset_checkpoint") != trusted_toolset_checkpoint
        or verification.get("trusted_inventory_checkpoint")
        != trusted_inventory_checkpoint
        or verification.get("trusted_selection_checkpoint")
        != trusted_selection_checkpoint
    ):
        _fail("inventory-v2 selection verification binding mismatch")

    verified_bytes = _verified_artifact_bytes(verification, paths)
    case_match = _CASE_ID_RE.fullmatch(case_id)
    if case_match is None:
        _fail("selected case/date is invalid")
    registry = _load_object_bytes(
        verified_bytes["selection_registry"], "selection registry"
    )
    inventory = _load_object_bytes(
        verified_bytes["source_inventory"], "source inventory"
    )
    if (
        registry.get("schema_version") != "2.0"
        or inventory.get("schema_version") != "2.0"
        or registry.get("trusted_inventory_checkpoint")
        != trusted_inventory_checkpoint
    ):
        _fail("inventory-v2 schema/checkpoint family mismatch")
    selections = registry.get("selections")
    if not isinstance(selections, list):
        _fail("invalid inventory-v2 selections")
    matches = [
        selection
        for selection in selections
        if isinstance(selection, dict) and selection.get("case_id") == case_id
    ]
    if len(matches) != 1:
        _fail("selected case must occur exactly once")
    selection = matches[0]
    trading_date = selection.get("trading_date")
    if trading_date != case_match.group("trading_date"):
        _fail("selected case/date mismatch")

    entries = inventory.get("entries")
    if not isinstance(entries, list):
        _fail("invalid inventory-v2 source inventory entries")
    inventory_matches = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("trading_date") == trading_date
    ]
    if len(inventory_matches) != 1 or inventory_matches[0].get("eligible") is not True:
        _fail("selected case/date is not uniquely eligible in inventory")
    expected = inventory_matches[0].get("first_250_source_sha256")
    if not isinstance(expected, str) or _SHA256_RE.fullmatch(expected) is None:
        _fail("selected case has no frozen first-250 source SHA-256")
    try:
        observed = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    except OSError as error:
        raise SelectedSourceValidationError("cannot read selected source") from error
    if observed != expected:
        _fail("selected source SHA-256 mismatch")
    return SelectedSourceHashBinding(
        case_id=case_id,
        trading_date=trading_date,
        expected_sha256=expected,
        observed_sha256=observed,
        trusted_inventory_checkpoint=trusted_inventory_checkpoint,
        trusted_selection_checkpoint=trusted_selection_checkpoint,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify selected MNQ bytes against a frozen v2 inventory."
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--inventory-checkpoint-bundle-root", required=True, type=Path)
    parser.add_argument("--trusted-toolset-checkpoint", required=True)
    parser.add_argument("--trusted-inventory-checkpoint", required=True)
    parser.add_argument("--trusted-selection-checkpoint", required=True)
    parser.add_argument("--repository-identity", default=DEFAULT_REPOSITORY_IDENTITY)
    parser.add_argument("--remote-name")
    parser.add_argument("--remote-branch")
    args = parser.parse_args(argv)
    try:
        verify_selected_source_hash(
            source_path=args.source,
            case_id=args.case_id,
            repository_path=args.repository,
            inventory_checkpoint_bundle_root=args.inventory_checkpoint_bundle_root,
            trusted_toolset_checkpoint=args.trusted_toolset_checkpoint,
            trusted_inventory_checkpoint=args.trusted_inventory_checkpoint,
            trusted_selection_checkpoint=args.trusted_selection_checkpoint,
            expected_repository_identity=args.repository_identity,
            remote_name=args.remote_name,
            remote_branch=args.remote_branch,
        )
    except SelectedSourceValidationError as error:
        parser.exit(2, f"STOP: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
