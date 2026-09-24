"""Strict, exact-byte helpers for the MNQ inventory validation pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker


def sha256_bytes(value: bytes) -> str:
    """Return lowercase SHA-256 for exact bytes."""

    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Return lowercase SHA-256 without rewriting the file."""

    return sha256_bytes(path.read_bytes())


def canonical_payload_sha256(
    value: Mapping[str, object],
    hash_field: str = "aggregate_payload_sha256",
) -> str:
    """Hash canonical JSON after excluding the named self-hash field."""

    payload = dict(value)
    payload.pop(hash_field, None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256_bytes(encoded)


def load_schema_validated_json(
    path: Path,
    schema_path: Path,
    label: str,
) -> dict[str, object]:
    """Load JSON and validate it with Draft 2020-12."""

    try:
        exact_bytes = path.read_bytes()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label} JSON") from error
    return _load_schema_validated_json_bytes(exact_bytes, schema_path, label)


def _load_schema_validated_json_bytes(
    exact_bytes: bytes,
    schema_path: Path,
    label: str,
) -> dict[str, object]:
    """Parse and validate one already-retained exact JSON byte sequence."""

    try:
        value = json.loads(exact_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label} JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: top level must be an object")
    try:
        schema = json.loads(schema_path.read_bytes())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label} schema") from error
    except Exception as error:
        raise ValueError(f"invalid {label}") from error
    return value


def write_json_atomically(path: Path, value: Mapping[str, object]) -> None:
    """Refuse overwrite and publish one canonical JSON object atomically."""

    destination = path.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
        temporary.unlink()
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
