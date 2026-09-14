from __future__ import annotations

import hashlib
import json
import os
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest

import tools.validation.mnq_5m_checkpoint_verify as checkpoint_verify
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
