"""Strict, exact-byte helpers for the MNQ inventory validation pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker


EXCLUSION_REASON_ORDER: tuple[str, ...] = (
    "INCOMPLETE_PROVENANCE",
    "FEWER_THAN_250_NATIVE_BARS",
    "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS",
    "TRADING_HOURS_INCONSISTENCY",
    "MALFORMED_OR_NON_FINITE_OHLCV",
    "INVALID_OHLC_GEOMETRY",
    "UNEXPECTED_MISSING_BARS",
    "SOURCE_CORRUPTION",
)


def reconcile_inventory_entries(
    source_inventory: Mapping[str, object], exclusions: Mapping[str, object]
) -> list[Mapping[str, object]]:
    """Cross-reconcile frozen inventory dispositions, exclusions, and outcome."""

    raw_entries = source_inventory.get("entries")
    if not isinstance(raw_entries, Sequence) or isinstance(
        raw_entries, (str, bytes, bytearray)
    ):
        raise ValueError("invalid source inventory entries")
    if source_inventory.get("candidate_count") != len(raw_entries):
        raise ValueError("source inventory candidate count mismatch")

    eligible: list[Mapping[str, object]] = []
    expected_exclusions: list[dict[str, object]] = []
    previous_date: date | None = None
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            raise ValueError("invalid source inventory entry")
        raw_date = raw_entry.get("trading_date")
        if not isinstance(raw_date, str):
            raise ValueError("source inventory dates are not strictly chronological")
        try:
            trading_date = date.fromisoformat(raw_date)
        except ValueError as error:
            raise ValueError("invalid source inventory date") from error
        if previous_date is not None and trading_date <= previous_date:
            raise ValueError(
                "source inventory dates are not strictly chronological and unique"
            )
        previous_date = trading_date

        raw_reasons = raw_entry.get("exclusion_reasons")
        if not isinstance(raw_reasons, Sequence) or isinstance(
            raw_reasons, (str, bytes, bytearray)
        ):
            raise ValueError("invalid inventory exclusion reasons")
        reasons = list(raw_reasons)
        if any(not isinstance(reason, str) for reason in reasons) or any(
            reason not in EXCLUSION_REASON_ORDER for reason in reasons
        ):
            raise ValueError("inventory contains a forbidden exclusion reason")
        if reasons != [reason for reason in EXCLUSION_REASON_ORDER if reason in reasons]:
            raise ValueError("inventory exclusion reason order is not frozen")
        if raw_entry.get("eligible") is True:
            if reasons:
                raise ValueError("eligible inventory entry has exclusion reasons")
            eligible.append(raw_entry)
        elif raw_entry.get("eligible") is False and reasons:
            expected_exclusions.append(
                {"trading_date": raw_date, "reasons": reasons}
            )
        else:
            raise ValueError("inventory disposition does not reconcile")

    if source_inventory.get("eligible_count") != len(eligible):
        raise ValueError("source inventory eligible count mismatch")
    raw_exclusions = exclusions.get("entries")
    if not isinstance(raw_exclusions, Sequence) or isinstance(
        raw_exclusions, (str, bytes, bytearray)
    ):
        raise ValueError("invalid exclusions entries")
    if list(raw_exclusions) != expected_exclusions:
        raise ValueError("source inventory and exclusions do not reconcile")
    expected_outcome = (
        "READY_FOR_SELECTION" if len(eligible) >= 10 else "COHORT_INCOMPLETE"
    )
    if source_inventory.get("cohort_outcome") != expected_outcome:
        raise ValueError("inventory cohort outcome mismatch")
    return eligible


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
