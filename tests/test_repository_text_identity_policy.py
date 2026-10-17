from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "repository_path",
    [
        "tools/validation/mnq_5m_checkpoint_verify.py",
        "tools/validation/mnq_5m_acquisition.py",
        "tools/validation/ninjatrader/ExportMnq5mCohortSource.cs",
        "validation/mnq_5m_multiwindow/schemas/provenance.schema.json",
        (
            "docs/superpowers/specs/"
            "2026-09-16-mnq-5m-official-inventory-scanner-design.md"
        ),
    ],
)
def test_identity_sensitive_text_paths_resolve_to_lf_checkout(
    repository_path: str,
) -> None:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(PROJECT_ROOT),
            "check-attr",
            "eol",
            "--",
            repository_path,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.stdout.strip() == f"{repository_path}: eol: lf"
