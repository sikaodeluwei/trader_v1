from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

import pytest

import tools.validation.mnq_5m_inventory as inventory_module
from tools.validation.mnq_5m_inventory import (
    EXCLUSION_REASON_ORDER,
    InventoryBuildResult,
    InventoryFinalizationResult,
    _build_inventory_provenance,
    _load_toolset_manifest_binding,
    _publish_bundle,
    build_inventory,
    build_parser,
    finalize_inventory_bundle,
)
from tools.validation.mnq_5m_inventory_calendar import (
    SessionSegment,
    VerifiedInventoryCalendar,
    VerifiedSession,
)
from tools.validation.mnq_5m_inventory_common import canonical_payload_sha256
from tools.validation.mnq_5m_inventory_evidence import (
    InventoryValidationError,
    LoadedInventoryEvidence,
    ValidatedInventoryEvidence,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
PRODUCING_CHECKPOINT = "1" * 40
TRUSTED_TOOLSET_CHECKPOINT = "2" * 40
CANONICALIZATION_ID = "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1"


def _quality(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "observed_native_five_minute_bar_count": 276,
        "observed_valid_count_from_session_start": 276,
        "first_observed_timestamp": "20260621 170500",
        "two_hundred_fiftieth_native_timestamp": "20260622 135000",
        "last_observed_session_timestamp": "20260622 160000",
        "supplied_order_strictly_increasing": True,
        "duplicate_timestamp_indexes": [],
        "duplicate_timestamp_count": 0,
        "decreasing_timestamp_indexes": [],
        "decreasing_timestamp_count": 0,
        "missing_expected_open_timestamps": [],
        "missing_expected_open_timestamp_count": 0,
        "unexpected_timestamps": [],
        "unexpected_timestamp_count": 0,
        "malformed_or_non_finite_ohlcv_indexes": [],
        "malformed_or_non_finite_ohlcv_count": 0,
        "invalid_ohlc_geometry_indexes": [],
        "invalid_ohlc_geometry_count": 0,
        "negative_volume_indexes": [],
        "negative_volume_count": 0,
        "non_integral_volume_indexes": [],
        "non_integral_volume_count": 0,
        "first_250_source_sha256": SHA_A,
        "complete_session_source_sha256": SHA_B,
        "canonicalization_id": CANONICALIZATION_ID,
    }
    value.update(overrides)
    return value


def _session(
    trading_date: date,
    quality: Mapping[str, object] | None = None,
    *,
    partial_session: bool = False,
    scheduled_breaks: list[dict[str, str]] | None = None,
) -> VerifiedSession:
    begin = datetime.combine(
        trading_date - timedelta(days=1),
        datetime.min.time(),
        timezone(timedelta(hours=-5)),
    ).replace(hour=17)
    end = datetime.combine(
        trading_date,
        datetime.min.time(),
        timezone(timedelta(hours=-5)),
    ).replace(hour=16)
    segment = SessionSegment(begin, end, begin.astimezone(timezone.utc), end.astimezone(timezone.utc))
    schedule = {
        "holiday_name": None,
        "partial_session": partial_session,
        "expected_open_segments": [
            {
                "begin_application": begin.isoformat(),
                "end_application": end.isoformat(),
                "begin_pc": begin.astimezone(timezone.utc).isoformat(),
                "end_pc": end.astimezone(timezone.utc).isoformat(),
            }
        ],
        "scheduled_breaks": scheduled_breaks or [],
        "application_session_begin": begin.isoformat(),
        "application_session_end": end.isoformat(),
        "pc_log_session_begin": begin.astimezone(timezone.utc).isoformat(),
        "pc_log_session_end": end.astimezone(timezone.utc).isoformat(),
        "effective_schedule_source": (
            "SessionIterator using Bars.TradingHours and ActualTradingDayExchange"
        ),
    }
    observation = {
        "civil_date": trading_date.isoformat(),
        "classification": "SESSION",
        "exchange_trading_date": trading_date.isoformat(),
        "schedule_evidence": schedule,
        "quality": dict(quality or _quality()),
    }
    return VerifiedSession(
        civil_date=trading_date,
        trading_date=trading_date,
        holiday_name=None,
        partial_session=partial_session,
        segments=(segment,),
        observation=MappingProxyType(observation),
    )


def _calendar(
    qualities: list[Mapping[str, object]] | None = None,
    *,
    dates: list[date] | None = None,
    partial_indexes: set[int] | None = None,
) -> VerifiedInventoryCalendar:
    values = qualities or [_quality()]
    supplied_dates = dates or [date(2026, 6, 22) + timedelta(days=index) for index in range(len(values))]
    sessions = tuple(
        _session(
            trading_date,
            quality,
            partial_session=index in (partial_indexes or set()),
        )
        for index, (trading_date, quality) in enumerate(zip(supplied_dates, values))
    )
    return VerifiedInventoryCalendar(
        sessions=sessions,
        earliest_session_begin=sessions[0].segments[0].begin_application,
        latest_session_end=sessions[-1].segments[-1].end_application,
        template_sha256=SHA_C,
        calendar_binding_sha256=SHA_D,
    )


def _provider_acquisition() -> dict[str, object]:
    lifecycle = {
        "adapter_connection_initiated_at": "2026-09-16T10:58:00+08:00",
        "connection_ready_at": "2026-09-16T10:59:00+08:00",
        "pre_request_realtime_at": "2026-09-16T11:00:00+08:00",
        "request_observed_at": "2026-09-16T11:01:30+08:00",
        "post_request_initialized_at": "2026-09-16T11:02:00+08:00",
        "post_request_realtime_at": "2026-09-16T11:03:00+08:00",
        "inventory_scan_armed_at": "2026-09-16T11:04:00+08:00",
        "inventory_scan_completed_at": "2026-09-16T11:05:00+08:00",
    }
    return {
        "status": "PROVEN",
        "provider_profile_id": "NINJATRADER_TRADOVATE_PROVIDER31_HDS_V1",
        "runtime_provider_id": "Provider31",
        "trace_adapter": "Tradovate.Adapter",
        "intended_connection_name": "My NinjaTrader",
        "active_connection": {
            "name": "My NinjaTrader",
            "provider": "Provider31",
            "status": "Connected",
            "price_status": "Connected",
            "instrument_types": ["Future"],
        },
        "historical_service": {
            "name": "NinjaTrader HDS",
            "host": "hds-us-nt-007.ninjatrader.com",
            "port": 443,
            "use_ssl": True,
            "connected_at": "2026-09-16T10:59:00+08:00",
        },
        "configuration_binding": {
            "mode": "EXPLICIT_PREFERENCE",
            "preferred_future_connection": "My NinjaTrader",
            "preferred_realtime_future_connection": "My NinjaTrader",
            "saved_connection_matches": 1,
        },
        "acquisition_id": "inventory-acquisition-v1",
        "lifecycle": lifecycle,
        "historical_request": {
            "source_role": "ninjatrader_trace",
            "observed_at": lifecycle["request_observed_at"],
            "instrument": "MNQ SEP26",
            "requested_start": "2026-06-21T17:00:00",
            "requested_end": "2026-07-24T16:00:00",
            "provider_request_period": "1 Minute",
            "covers_verified_inventory_bounds": True,
        },
        "competing_historical_provider_connections": 0,
        "intended_provider_disconnects": 0,
        "log_timezone_id": "Singapore Standard Time",
        "log_utc_offset": "+08:00",
    }


def _loaded(scan: Mapping[str, object]) -> LoadedInventoryEvidence:
    return LoadedInventoryEvidence(
        runtime_capture_path=Path("inventory_runtime_capture.json"),
        runtime_capture=MappingProxyType({"schema_version": "1.0"}),
        inventory_scan_path=Path("inventory_scan.json"),
        inventory_scan=MappingProxyType(dict(scan)),
        acquisition_evidence_path=Path("inventory_acquisition_evidence.json"),
        acquisition_evidence=MappingProxyType({"schema_version": "1.0"}),
        exact_artifact_bytes=MappingProxyType(
            {
                "inventory_runtime_capture": b"runtime",
                "inventory_scan": b"scan",
                "inventory_acquisition_evidence": b"evidence",
            }
        ),
    )


def _evidence(calendar: VerifiedInventoryCalendar) -> ValidatedInventoryEvidence:
    scan = {
        "schema_version": "1.0",
        "acquisition_id": "inventory-acquisition-v1",
        "cohort_id": "mnq-202609-5m-v1",
        "contract": {
            "contract_label": "MNQ SEP26",
            "master_name": "MNQ",
            "full_name": "MNQ SEP26",
            "expiry_month": 9,
            "expiry_year": 2026,
        },
        "bar_series": {"type": "Minute", "value": 5, "native": True},
        "observations": [session.observation for session in calendar.sessions],
    }
    hashes = {
        "inventory_scan": SHA_A,
        "inventory_runtime_capture": SHA_B,
        "inventory_acquisition_evidence": SHA_C,
        "scanner": SHA_D,
        "trading_hours_template": SHA_C,
        "ninjatrader_config": SHA_C,
        "ninjatrader_log": SHA_D,
        "ninjatrader_trace": SHA_E,
    }
    external = (
        MappingProxyType(
            {"role": "ninjatrader_config", "path": "external/config.xml", "sha256": SHA_C, "byte_length": 10}
        ),
        MappingProxyType(
            {"role": "ninjatrader_log", "path": "external/log.txt", "sha256": SHA_D, "byte_length": 11}
        ),
        MappingProxyType(
            {"role": "ninjatrader_trace", "path": "external/trace.txt", "sha256": SHA_E, "byte_length": 12}
        ),
    )
    return ValidatedInventoryEvidence(
        loaded=_loaded(scan),
        provider_acquisition=MappingProxyType(_provider_acquisition()),
        qualifying_request=MappingProxyType(_provider_acquisition()["historical_request"]),
        artifact_hashes=MappingProxyType(hashes),
        external_evidence=external,
        earliest_session_begin=calendar.earliest_session_begin,
        latest_session_end=calendar.latest_session_end,
    )


def _build(qualities: list[Mapping[str, object]]) -> InventoryBuildResult:
    calendar = _calendar(qualities)
    return build_inventory(
        evidence=_evidence(calendar),
        calendar=calendar,
        inventory_provenance_sha256=SHA_E,
        inventory_scan_sha256=SHA_A,
        producing_checkpoint=PRODUCING_CHECKPOINT,
    )


def _toolset_binding() -> dict[str, object]:
    return {
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "stage": "SOURCE_ACQUISITION",
        "schema_version": "2.0",
        "producing_checkpoint": PRODUCING_CHECKPOINT,
        "trusted_checkpoint": TRUSTED_TOOLSET_CHECKPOINT,
        "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856",
        "aggregate_payload_sha256": SHA_A,
    }


def _provenance(calendar: VerifiedInventoryCalendar) -> dict[str, object]:
    return _build_inventory_provenance(
        evidence=_evidence(calendar),
        calendar=calendar,
        trusted_toolset_checkpoint=TRUSTED_TOOLSET_CHECKPOINT,
        producing_checkpoint=PRODUCING_CHECKPOINT,
        toolset_manifest_sha256=SHA_B,
        toolset_binding=_toolset_binding(),
    )


def _exact_json_sha256(value: Mapping[str, object]) -> str:
    encoded = (
        json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_documents() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    calendar = _calendar([_quality()])
    provenance = _provenance(calendar)
    result = build_inventory(
        evidence=_evidence(calendar),
        calendar=calendar,
        inventory_provenance_sha256=_exact_json_sha256(provenance),
        inventory_scan_sha256=SHA_A,
        producing_checkpoint=PRODUCING_CHECKPOINT,
    )
    return provenance, dict(result.source_inventory), dict(result.exclusions)


REASON_FACTORIES: dict[str, Callable[[], dict[str, object]]] = {
    "INCOMPLETE_PROVENANCE": lambda: _quality(first_observed_timestamp=None),
    "FEWER_THAN_250_NATIVE_BARS": lambda: _quality(
        observed_native_five_minute_bar_count=249,
        observed_valid_count_from_session_start=249,
        two_hundred_fiftieth_native_timestamp=None,
        first_250_source_sha256=None,
    ),
    "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS": lambda: _quality(
        observed_valid_count_from_session_start=275,
        supplied_order_strictly_increasing=False,
        duplicate_timestamp_indexes=[275],
        duplicate_timestamp_count=1,
    ),
    "TRADING_HOURS_INCONSISTENCY": lambda: _quality(
        observed_valid_count_from_session_start=250,
        unexpected_timestamps=["20260622 160500"],
        unexpected_timestamp_count=1,
    ),
    "MALFORMED_OR_NON_FINITE_OHLCV": lambda: _quality(
        observed_valid_count_from_session_start=275,
        malformed_or_non_finite_ohlcv_indexes=[275],
        malformed_or_non_finite_ohlcv_count=1,
        complete_session_source_sha256=None,
    ),
    "INVALID_OHLC_GEOMETRY": lambda: _quality(
        observed_valid_count_from_session_start=275,
        invalid_ohlc_geometry_indexes=[275],
        invalid_ohlc_geometry_count=1,
    ),
    "UNEXPECTED_MISSING_BARS": lambda: _quality(
        observed_valid_count_from_session_start=260,
        missing_expected_open_timestamps=["20260622 144500"],
        missing_expected_open_timestamp_count=1,
    ),
    "SOURCE_CORRUPTION": lambda: _quality(complete_session_source_sha256=None),
}


def test_public_contract_has_exact_reason_order_and_frozen_result_types() -> None:
    assert EXCLUSION_REASON_ORDER == (
        "INCOMPLETE_PROVENANCE",
        "FEWER_THAN_250_NATIVE_BARS",
        "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS",
        "TRADING_HOURS_INCONSISTENCY",
        "MALFORMED_OR_NON_FINITE_OHLCV",
        "INVALID_OHLC_GEOMETRY",
        "UNEXPECTED_MISSING_BARS",
        "SOURCE_CORRUPTION",
    )
    build_result = InventoryBuildResult({}, {})
    final_result = InventoryFinalizationResult({}, {}, {})
    with pytest.raises(dataclasses.FrozenInstanceError):
        build_result.source_inventory = {}  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        final_result.exclusions = {}  # type: ignore[misc]


@pytest.mark.parametrize("reason", EXCLUSION_REASON_ORDER)
def test_each_frozen_exclusion_reason_is_mapped_from_an_objective_fact(reason: str) -> None:
    result = _build([REASON_FACTORIES[reason]()])
    entry = result.source_inventory["entries"][0]
    assert reason in entry["exclusion_reasons"]
    assert result.exclusions["entries"][0]["reasons"] == entry["exclusion_reasons"]


def test_simultaneous_reasons_use_frozen_order_not_quality_map_order() -> None:
    quality = _quality()
    quality = {
        "invalid_ohlc_geometry_count": 1,
        "invalid_ohlc_geometry_indexes": [274],
        **quality,
        "supplied_order_strictly_increasing": False,
        "duplicate_timestamp_indexes": [275],
        "duplicate_timestamp_count": 1,
        "observed_valid_count_from_session_start": 274,
    }
    quality["invalid_ohlc_geometry_count"] = 1
    quality["invalid_ohlc_geometry_indexes"] = [274]
    reasons = _build([quality]).source_inventory["entries"][0]["exclusion_reasons"]
    assert reasons == [
        "DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS",
        "INVALID_OHLC_GEOMETRY",
    ]


def test_fewer_than_250_uses_valid_native_prefix_from_session_start() -> None:
    quality = _quality(
        observed_native_five_minute_bar_count=276,
        observed_valid_count_from_session_start=249,
        invalid_ohlc_geometry_indexes=[249],
        invalid_ohlc_geometry_count=1,
    )
    assert _build([quality]).source_inventory["entries"][0]["exclusion_reasons"] == [
        "FEWER_THAN_250_NATIVE_BARS",
        "INVALID_OHLC_GEOMETRY",
    ]


@pytest.mark.parametrize(
    ("fact_name", "indexes_name"),
    [
        ("duplicate_timestamp_count", "duplicate_timestamp_indexes"),
        ("decreasing_timestamp_count", "decreasing_timestamp_indexes"),
    ],
)
def test_duplicate_and_decreasing_supplied_order_facts_are_not_repaired(
    fact_name: str,
    indexes_name: str,
) -> None:
    quality = _quality(
        observed_valid_count_from_session_start=275,
        supplied_order_strictly_increasing=False,
    )
    quality[fact_name] = 1
    quality[indexes_name] = [275]
    reasons = _build([quality]).source_inventory["entries"][0]["exclusion_reasons"]
    assert reasons == ["DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS"]


@pytest.mark.parametrize(
    ("indexes_name", "count_name"),
    [
        ("malformed_or_non_finite_ohlcv_indexes", "malformed_or_non_finite_ohlcv_count"),
        ("negative_volume_indexes", "negative_volume_count"),
        ("non_integral_volume_indexes", "non_integral_volume_count"),
    ],
)
def test_malformed_non_finite_and_invalid_volume_map_to_one_reason(
    indexes_name: str,
    count_name: str,
) -> None:
    quality = _quality(observed_valid_count_from_session_start=275)
    quality[indexes_name] = [275]
    quality[count_name] = 1
    if indexes_name == "malformed_or_non_finite_ohlcv_indexes":
        quality["complete_session_source_sha256"] = None
    reasons = _build([quality]).source_inventory["entries"][0]["exclusion_reasons"]
    assert "MALFORMED_OR_NON_FINITE_OHLCV" in reasons


def test_invalid_ohlc_geometry_has_its_own_reason() -> None:
    quality = _quality(
        observed_valid_count_from_session_start=275,
        invalid_ohlc_geometry_indexes=[275],
        invalid_ohlc_geometry_count=1,
    )
    assert _build([quality]).source_inventory["entries"][0]["exclusion_reasons"] == [
        "INVALID_OHLC_GEOMETRY"
    ]


@pytest.mark.parametrize(
    (
        "indexes_name",
        "count_name",
        "supplied_order_strictly_increasing",
        "complete_hash",
        "expected_reasons",
    ),
    [
        (
            "duplicate_timestamp_indexes",
            "duplicate_timestamp_count",
            False,
            SHA_B,
            ["DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS"],
        ),
        (
            "decreasing_timestamp_indexes",
            "decreasing_timestamp_count",
            False,
            SHA_B,
            ["DUPLICATE_OR_NON_MONOTONIC_TIMESTAMPS"],
        ),
        (
            "malformed_or_non_finite_ohlcv_indexes",
            "malformed_or_non_finite_ohlcv_count",
            True,
            None,
            ["MALFORMED_OR_NON_FINITE_OHLCV", "SOURCE_CORRUPTION"],
        ),
        (
            "invalid_ohlc_geometry_indexes",
            "invalid_ohlc_geometry_count",
            True,
            SHA_B,
            ["INVALID_OHLC_GEOMETRY"],
        ),
        (
            "negative_volume_indexes",
            "negative_volume_count",
            True,
            SHA_B,
            ["MALFORMED_OR_NON_FINITE_OHLCV"],
        ),
        (
            "non_integral_volume_indexes",
            "non_integral_volume_count",
            True,
            SHA_B,
            ["MALFORMED_OR_NON_FINITE_OHLCV"],
        ),
    ],
)
def test_absolute_supplied_order_defect_indexes_are_accepted_and_mapped(
    indexes_name: str,
    count_name: str,
    supplied_order_strictly_increasing: bool,
    complete_hash: str | None,
    expected_reasons: list[str],
) -> None:
    observed_count = 276
    absolute_supplied_index = 500
    quality = _quality(
        observed_native_five_minute_bar_count=observed_count,
        observed_valid_count_from_session_start=275,
        supplied_order_strictly_increasing=supplied_order_strictly_increasing,
        complete_session_source_sha256=complete_hash,
    )
    quality[indexes_name] = [absolute_supplied_index]
    quality[count_name] = 1

    assert absolute_supplied_index > observed_count
    assert _build([quality]).source_inventory["entries"][0]["exclusion_reasons"] == (
        expected_reasons
    )


def test_expected_open_absence_is_missing_but_scheduled_break_is_not() -> None:
    missing = _quality(
        observed_valid_count_from_session_start=260,
        missing_expected_open_timestamps=["20260622 144500"],
        missing_expected_open_timestamp_count=1,
    )
    assert "UNEXPECTED_MISSING_BARS" in _build([missing]).source_inventory["entries"][0][
        "exclusion_reasons"
    ]
    break_segment = {
        "begin_application": "2026-06-22T15:00:00-05:00",
        "end_application": "2026-06-22T15:15:00-05:00",
        "begin_pc": "2026-06-22T20:00:00+00:00",
        "end_pc": "2026-06-22T20:15:00+00:00",
    }
    session = _session(date(2026, 6, 22), _quality(), scheduled_breaks=[break_segment])
    calendar = VerifiedInventoryCalendar(
        sessions=(session,),
        earliest_session_begin=session.segments[0].begin_application,
        latest_session_end=session.segments[-1].end_application,
        template_sha256=SHA_C,
        calendar_binding_sha256=SHA_D,
    )
    result = build_inventory(
        evidence=_evidence(calendar),
        calendar=calendar,
        inventory_provenance_sha256=SHA_E,
        inventory_scan_sha256=SHA_A,
        producing_checkpoint=PRODUCING_CHECKPOINT,
    )
    assert result.source_inventory["entries"][0]["eligible"] is True


@pytest.mark.parametrize(
    "quality",
    [
        _quality(
            observed_native_five_minute_bar_count=0,
            observed_valid_count_from_session_start=0,
            first_observed_timestamp=None,
            two_hundred_fiftieth_native_timestamp=None,
            last_observed_session_timestamp=None,
            first_250_source_sha256=None,
            complete_session_source_sha256=None,
        ),
        _quality(complete_session_source_sha256=None),
    ],
    ids=["date-scoped-read-corruption", "date-scoped-serialization-corruption"],
)
def test_concrete_date_scoped_source_corruption_is_recorded(quality: dict[str, object]) -> None:
    reasons = _build([quality]).source_inventory["entries"][0]["exclusion_reasons"]
    assert "SOURCE_CORRUPTION" in reasons


def test_partial_session_with_short_valid_prefix_is_excluded_normally() -> None:
    quality = REASON_FACTORIES["FEWER_THAN_250_NATIVE_BARS"]()
    calendar = _calendar([quality], partial_indexes={0})
    result = build_inventory(
        evidence=_evidence(calendar),
        calendar=calendar,
        inventory_provenance_sha256=SHA_E,
        inventory_scan_sha256=SHA_A,
        producing_checkpoint=PRODUCING_CHECKPOINT,
    )
    assert result.source_inventory["entries"][0]["exclusion_reasons"] == [
        "FEWER_THAN_250_NATIVE_BARS"
    ]


def test_eligible_session_preserves_both_scanner_hashes_without_raw_bars() -> None:
    entry = _build([_quality()]).source_inventory["entries"][0]
    assert entry["eligible"] is True
    assert entry["first_250_source_sha256"] == SHA_A
    assert entry["complete_session_source_sha256"] == SHA_B
    assert "bars" not in entry


def test_forbidden_compatibility_reasons_are_never_emitted() -> None:
    for factory in REASON_FACTORIES.values():
        reasons = _build([factory()]).source_inventory["entries"][0]["exclusion_reasons"]
        assert "SOURCE_HASH_MISMATCH" not in reasons
        assert "OUTSIDE_POLICY" not in reasons


@pytest.mark.parametrize("failure_stage", ["load", "calendar", "provider"])
def test_global_proof_failure_stops_before_build_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    loaded = _loaded({"scanner_claimed_begin": "1900-01-01T00:00:00+00:00"})
    calendar = _calendar([_quality()])
    calls: list[str] = []

    def fail(label: str) -> None:
        calls.append(label)
        raise InventoryValidationError(label)

    monkeypatch.setattr(
        inventory_module,
        "load_inventory_evidence",
        lambda **_: fail("load") if failure_stage == "load" else loaded,
    )
    monkeypatch.setattr(
        inventory_module,
        "verify_inventory_calendar",
        lambda *_: fail("calendar") if failure_stage == "calendar" else calendar,
    )
    monkeypatch.setattr(
        inventory_module,
        "finalize_inventory_evidence",
        lambda **_: fail("provider") if failure_stage == "provider" else _evidence(calendar),
    )
    monkeypatch.setattr(
        inventory_module,
        "build_inventory",
        lambda **_: (_ for _ in ()).throw(AssertionError("build_inventory was called")),
    )
    template = tmp_path / "template.xml"
    template.write_bytes(b"template")
    with pytest.raises(InventoryValidationError, match=failure_stage):
        finalize_inventory_bundle(**_finalize_kwargs(tmp_path, template))
    assert not (tmp_path / "official").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda quality: quality.__setitem__("eligible", True),
        lambda quality: quality.__setitem__("supplied_order_strictly_increasing", "yes"),
        lambda quality: quality.__setitem__("duplicate_timestamp_count", 1),
    ],
    ids=["unknown-fact", "unknown-state", "unreconciled-count"],
)
def test_unknown_or_unreconciled_quality_state_fails_closed(
    mutation: Callable[[dict[str, object]], None],
) -> None:
    quality = _quality()
    mutation(quality)
    with pytest.raises(InventoryValidationError):
        _build([quality])


def test_inventory_provenance_binds_provider_calendar_artifacts_and_checkpoints() -> None:
    calendar = _calendar([_quality(), _quality()])
    evidence = _evidence(calendar)
    provenance = _provenance(calendar)
    assert provenance["provider_acquisition"] == evidence.provider_acquisition
    assert provenance["calendar_binding"] == {
        "status": "VERIFIED",
        "trading_hours_name": "CME US Index Futures ETH",
        "civil_date_start": "2026-06-22",
        "civil_date_end": "2026-07-24",
        "civil_date_count": 33,
        "session_count": 2,
        "earliest_session_begin": calendar.earliest_session_begin.isoformat(),
        "latest_session_end": calendar.latest_session_end.isoformat(),
        "trading_hours_template_sha256": calendar.template_sha256,
        "calendar_binding_sha256": calendar.calendar_binding_sha256,
    }
    assert provenance["artifact_hashes"] == {**dict(evidence.artifact_hashes), "toolset_manifest": SHA_B}
    assert provenance["inventory_scan_binding"]["sha256"] == SHA_A
    assert provenance["toolset_binding"] == _toolset_binding()
    assert provenance["checkpoint_verification"]["trusted_toolset_checkpoint"] == TRUSTED_TOOLSET_CHECKPOINT


def test_only_verified_calendar_bounds_feed_provider_request_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar = _calendar([_quality()])
    loaded = _loaded(
        {
            "earliest_session_begin": "1900-01-01T00:00:00+00:00",
            "latest_session_end": "2100-01-01T00:00:00+00:00",
        }
    )
    observed: dict[str, object] = {}
    monkeypatch.setattr(inventory_module, "load_inventory_evidence", lambda **_: loaded)
    monkeypatch.setattr(inventory_module, "verify_inventory_calendar", lambda *_: calendar)

    def stop_after_provider(**kwargs: object) -> ValidatedInventoryEvidence:
        observed.update(kwargs)
        raise InventoryValidationError("stop after bounds")

    monkeypatch.setattr(inventory_module, "finalize_inventory_evidence", stop_after_provider)
    template = tmp_path / "template.xml"
    template.write_bytes(b"template")
    with pytest.raises(InventoryValidationError, match="stop after bounds"):
        finalize_inventory_bundle(**_finalize_kwargs(tmp_path, template))
    assert observed["earliest_session_begin"] == calendar.earliest_session_begin
    assert observed["latest_session_end"] == calendar.latest_session_end


def test_finalizer_preserves_required_cross_layer_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar = _calendar([_quality()])
    loaded = _loaded({"scan": "facts"})
    evidence = _evidence(calendar)
    provenance = _provenance(calendar)
    built = build_inventory(
        evidence=evidence,
        calendar=calendar,
        inventory_provenance_sha256=_exact_json_sha256(provenance),
        inventory_scan_sha256=SHA_A,
        producing_checkpoint=PRODUCING_CHECKPOINT,
    )
    events: list[str] = []
    monkeypatch.setattr(inventory_module, "load_inventory_evidence", lambda **_: events.append("load") or loaded)
    monkeypatch.setattr(inventory_module, "verify_inventory_calendar", lambda *_: events.append("calendar") or calendar)
    monkeypatch.setattr(inventory_module, "finalize_inventory_evidence", lambda **_: events.append("provider") or evidence)
    monkeypatch.setattr(
        inventory_module,
        "_load_toolset_manifest_binding",
        lambda **_: events.append("toolset") or (SHA_B, _toolset_binding()),
    )
    monkeypatch.setattr(
        inventory_module,
        "_build_inventory_provenance",
        lambda **_: events.append("provenance") or provenance,
    )

    def validate(_value: object, _schema: Path, label: str) -> None:
        events.append(f"validate:{label}")

    monkeypatch.setattr(inventory_module, "_validate_document", validate)
    monkeypatch.setattr(inventory_module, "build_inventory", lambda **_: events.append("build") or built)
    monkeypatch.setattr(inventory_module, "_cross_reconcile", lambda *_: events.append("reconcile"))
    monkeypatch.setattr(inventory_module, "_publish_bundle", lambda **_: events.append("publish"))
    template = tmp_path / "template.xml"
    template.write_bytes(b"template")
    result = finalize_inventory_bundle(**_finalize_kwargs(tmp_path, template))
    assert isinstance(result, InventoryFinalizationResult)
    assert events == [
        "load",
        "calendar",
        "provider",
        "toolset",
        "provenance",
        "validate:inventory provenance",
        "build",
        "validate:source inventory",
        "validate:exclusions",
        "reconcile",
        "publish",
    ]


@pytest.mark.parametrize("invalid_name", ["provenance", "inventory", "exclusions"])
def test_any_staged_validation_failure_publishes_none(
    tmp_path: Path,
    invalid_name: str,
) -> None:
    provenance, source_inventory, exclusions = _valid_documents()
    if invalid_name == "provenance":
        provenance["status"] = "FAILED"
    elif invalid_name == "inventory":
        source_inventory["schema_version"] = "1.0"
    else:
        exclusions["entries"] = [{"trading_date": "2026-06-22", "reasons": ["OUTSIDE_POLICY"]}]
    final_dir = tmp_path / "official"
    unrelated = tmp_path / ".official.unrelated"
    unrelated.mkdir()
    with pytest.raises(InventoryValidationError):
        _publish_bundle(
            inventory_provenance_output=final_dir / "inventory_provenance.json",
            source_inventory_output=final_dir / "source_inventory.json",
            exclusions_output=final_dir / "exclusions.json",
            inventory_provenance=provenance,
            source_inventory=source_inventory,
            exclusions=exclusions,
        )
    assert not final_dir.exists()
    assert unrelated.is_dir()
    assert [path for path in tmp_path.iterdir() if path.name.startswith(".official.")] == [unrelated]


def test_inventory_and_exclusion_entries_reconcile_exactly() -> None:
    result = _build([_quality(), REASON_FACTORIES["FEWER_THAN_250_NATIVE_BARS"]()])
    inventory_entries = result.source_inventory["entries"]
    exclusion_by_date = {
        entry["trading_date"]: entry["reasons"] for entry in result.exclusions["entries"]
    }
    assert result.source_inventory["candidate_count"] == len(inventory_entries) == 2
    assert result.source_inventory["eligible_count"] == 1
    for entry in inventory_entries:
        assert exclusion_by_date.get(entry["trading_date"], []) == entry["exclusion_reasons"]


@pytest.mark.parametrize(
    ("count", "expected"),
    [(9, "COHORT_INCOMPLETE"), (10, "READY_FOR_SELECTION")],
)
def test_cohort_outcome_threshold_keeps_fixed_range_and_expiry(count: int, expected: str) -> None:
    result = _build([_quality() for _ in range(count)])
    assert result.source_inventory["cohort_outcome"] == expected
    assert result.exclusions["cohort_outcome"] == expected
    assert result.source_inventory["contract_policy"] == {
        "contract_label": "MNQ SEP26",
        "full_name": "MNQ SEP26",
        "expiry_month": 9,
        "expiry_year": 2026,
        "candidate_date_start": "2026-06-22",
        "candidate_date_end": "2026-07-24",
    }


def test_reversed_sessions_fail_instead_of_being_sorted() -> None:
    first = _session(date(2026, 6, 23), _quality())
    second = _session(date(2026, 6, 22), _quality())
    calendar = VerifiedInventoryCalendar(
        sessions=(first, second),
        earliest_session_begin=second.segments[0].begin_application,
        latest_session_end=first.segments[-1].end_application,
        template_sha256=SHA_C,
        calendar_binding_sha256=SHA_D,
    )
    with pytest.raises(InventoryValidationError, match="chronological"):
        build_inventory(
            evidence=_evidence(calendar),
            calendar=calendar,
            inventory_provenance_sha256=SHA_E,
            inventory_scan_sha256=SHA_A,
            producing_checkpoint=PRODUCING_CHECKPOINT,
        )


def test_first_250_hash_is_null_exactly_when_canonical_prefix_is_unavailable() -> None:
    short = REASON_FACTORIES["FEWER_THAN_250_NATIVE_BARS"]()
    malformed_prefix = _quality(
        observed_valid_count_from_session_start=249,
        malformed_or_non_finite_ohlcv_indexes=[249],
        malformed_or_non_finite_ohlcv_count=1,
        first_250_source_sha256=None,
        complete_session_source_sha256=None,
    )
    finite_invalid_geometry = _quality(
        observed_valid_count_from_session_start=249,
        invalid_ohlc_geometry_indexes=[249],
        invalid_ohlc_geometry_count=1,
    )
    entries = _build([short, malformed_prefix, finite_invalid_geometry]).source_inventory[
        "entries"
    ]
    assert [entry["first_250_source_sha256"] for entry in entries] == [
        None,
        None,
        SHA_A,
    ]
    assert entries[2]["exclusion_reasons"] == [
        "FEWER_THAN_250_NATIVE_BARS",
        "INVALID_OHLC_GEOMETRY",
    ]
    impossible = copy.deepcopy(short)
    impossible["first_250_source_sha256"] = SHA_A
    with pytest.raises(InventoryValidationError, match="first-250"):
        _build([impossible])


def test_no_session_observations_never_become_inventory_or_exclusion_entries() -> None:
    calendar = _calendar([_quality()])
    evidence = _evidence(calendar)
    evidence.loaded.inventory_scan["observations"].append(  # type: ignore[union-attr]
        {"civil_date": "2026-06-27", "classification": "NO_SESSION", "quality": None}
    )
    result = build_inventory(
        evidence=evidence,
        calendar=calendar,
        inventory_provenance_sha256=SHA_E,
        inventory_scan_sha256=SHA_A,
        producing_checkpoint=PRODUCING_CHECKPOINT,
    )
    assert [entry["trading_date"] for entry in result.source_inventory["entries"]] == ["2026-06-22"]
    assert result.exclusions["entries"] == []


def _run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _toolset_manifest(producing_checkpoint: str) -> dict[str, object]:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "validation"
        / "mnq_5m_multiwindow"
        / "schemas"
        / "toolset_manifest_v2.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    components = []
    for item in schema["properties"]["components"]["prefixItems"]:
        properties = item["allOf"][1]["properties"]
        components.append(
            {
                "role": properties["role"]["const"],
                "path": properties["path"]["const"],
                "bundle_path": properties["bundle_path"]["const"],
                "sha256": SHA_A,
                "producing_commit": producing_checkpoint,
            }
        )
    manifest: dict[str, object] = {
        "schema_version": "2.0",
        "stage": "SOURCE_ACQUISITION",
        "status": "FROZEN_FOR_SOURCE_ACQUISITION",
        "cohort_id": "mnq-202609-5m-v1",
        "producing_checkpoint": producing_checkpoint,
        "pinned_production_hierarchy_commit": "04a73e1401d44688660b211d9db6918113482856",
        "runtime": {
            "implementation": "CPython",
            "version": "3.12",
            "dependencies": [{"name": "jsonschema", "version": "4.25.1"}],
        },
        "canonicalization": "JSON_UTF8_SORTED_KEYS_COMPACT_EXCLUDE_AGGREGATE_PAYLOAD_SHA256",
        "components": components,
        "deferred_components": [
            "independent_oracle",
            "blind_project_runner",
            "comparator",
            "cohort_aggregator",
        ],
        "aggregate_payload_sha256": "",
    }
    manifest["aggregate_payload_sha256"] = canonical_payload_sha256(manifest)
    return manifest


def test_toolset_binding_comes_from_exact_manifest_committed_at_trusted_checkpoint(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _run_git(repository, "init", "-q")
    _run_git(repository, "config", "user.email", "inventory@example.invalid")
    _run_git(repository, "config", "user.name", "Inventory Test")
    (repository / "component.txt").write_bytes(b"component\n")
    _run_git(repository, "add", "component.txt")
    _run_git(repository, "commit", "-q", "-m", "components")
    producing = _run_git(repository, "rev-parse", "HEAD")
    manifest = _toolset_manifest(producing)
    manifest_path = repository / "validation" / "mnq_5m_multiwindow" / "toolset_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(
        (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )
    _run_git(repository, "add", "validation/mnq_5m_multiwindow/toolset_manifest.json")
    _run_git(repository, "commit", "-q", "-m", "toolset")
    trusted = _run_git(repository, "rev-parse", "HEAD")
    digest, binding = _load_toolset_manifest_binding(
        repository_path=repository,
        trusted_toolset_checkpoint=trusted,
        producing_checkpoint=producing,
    )
    assert digest == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert binding["producing_checkpoint"] == producing
    assert binding["trusted_checkpoint"] == trusted
    manifest_path.write_bytes(b"{}\n")
    with pytest.raises(InventoryValidationError, match="committed"):
        _load_toolset_manifest_binding(
            repository_path=repository,
            trusted_toolset_checkpoint=trusted,
            producing_checkpoint=producing,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda paths: paths.__setitem__(0, paths[0].with_name("wrong.json")),
        lambda paths: paths.__setitem__(1, paths[1].parent.parent / "other" / paths[1].name),
    ],
    ids=["wrong-basename", "different-final-directory"],
)
def test_publication_requires_exact_names_in_one_absent_directory(
    tmp_path: Path,
    mutation: Callable[[list[Path]], None],
) -> None:
    provenance, source_inventory, exclusions = _valid_documents()
    final_dir = tmp_path / "official"
    paths = [
        final_dir / "inventory_provenance.json",
        final_dir / "source_inventory.json",
        final_dir / "exclusions.json",
    ]
    mutation(paths)
    with pytest.raises(InventoryValidationError):
        _publish_bundle(
            inventory_provenance_output=paths[0],
            source_inventory_output=paths[1],
            exclusions_output=paths[2],
            inventory_provenance=provenance,
            source_inventory=source_inventory,
            exclusions=exclusions,
        )


def test_publication_refuses_an_existing_final_directory(tmp_path: Path) -> None:
    provenance, source_inventory, exclusions = _valid_documents()
    final_dir = tmp_path / "official"
    final_dir.mkdir()
    marker = final_dir / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(InventoryValidationError, match="absent"):
        _publish_bundle(
            inventory_provenance_output=final_dir / "inventory_provenance.json",
            source_inventory_output=final_dir / "source_inventory.json",
            exclusions_output=final_dir / "exclusions.json",
            inventory_provenance=provenance,
            source_inventory=source_inventory,
            exclusions=exclusions,
        )
    assert marker.read_text(encoding="utf-8") == "keep"


def test_successful_publication_exposes_all_three_files_together(tmp_path: Path) -> None:
    provenance, source_inventory, exclusions = _valid_documents()
    final_dir = tmp_path / "official"
    _publish_bundle(
        inventory_provenance_output=final_dir / "inventory_provenance.json",
        source_inventory_output=final_dir / "source_inventory.json",
        exclusions_output=final_dir / "exclusions.json",
        inventory_provenance=provenance,
        source_inventory=source_inventory,
        exclusions=exclusions,
    )
    assert {path.name for path in final_dir.iterdir()} == {
        "inventory_provenance.json",
        "source_inventory.json",
        "exclusions.json",
    }
    assert not [path for path in tmp_path.iterdir() if path.name.startswith(".official.")]


def test_cli_exposes_only_the_documented_required_paths_and_identifiers() -> None:
    parser = build_parser()
    options = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }
    assert options == {
        "--help",
        "--runtime-capture",
        "--inventory-scan",
        "--acquisition-evidence",
        "--scanner",
        "--trading-hours-template",
        "--config",
        "--log",
        "--trace",
        "--repository-path",
        "--expected-repository-identity",
        "--trusted-toolset-checkpoint",
        "--producing-checkpoint",
        "--inventory-provenance-output",
        "--source-inventory-output",
        "--exclusions-output",
    }
    assert all(action.required for action in parser._actions if action.option_strings and "--help" not in action.option_strings)


def _finalize_kwargs(tmp_path: Path, template: Path) -> dict[str, object]:
    final_dir = tmp_path / "official"
    return {
        "runtime_capture_path": tmp_path / "runtime.json",
        "inventory_scan_path": tmp_path / "scan.json",
        "acquisition_evidence_path": tmp_path / "evidence.json",
        "scanner_path": tmp_path / "scanner.cs",
        "trading_hours_template_path": template,
        "config_path": tmp_path / "config.xml",
        "log_path": tmp_path / "log.txt",
        "trace_path": tmp_path / "trace.txt",
        "repository_path": tmp_path / "repository",
        "expected_repository_identity": "owner/repository",
        "trusted_toolset_checkpoint": TRUSTED_TOOLSET_CHECKPOINT,
        "producing_checkpoint": PRODUCING_CHECKPOINT,
        "inventory_provenance_output": final_dir / "inventory_provenance.json",
        "source_inventory_output": final_dir / "source_inventory.json",
        "exclusions_output": final_dir / "exclusions.json",
    }
