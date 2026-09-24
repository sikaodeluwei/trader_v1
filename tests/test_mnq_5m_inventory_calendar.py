from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Iterable

import pytest

from tools.validation.mnq_5m_inventory_calendar import (
    SessionSegment,
    VerifiedInventoryCalendar,
    VerifiedSession,
    verify_inventory_calendar,
)
from tools.validation.mnq_5m_inventory_evidence import InventoryValidationError


POLICY_START = date(2026, 6, 22)
POLICY_END = date(2026, 7, 24)
APPLICATION_ZONE = timezone(timedelta(hours=-5))
PC_ZONE = timezone(timedelta(hours=8))
SOURCE = "SessionIterator using Bars.TradingHours and ActualTradingDayExchange"

WEEKLY_SESSIONS = (
    ("Sunday", 1700, "Monday", 1600, "Monday"),
    ("Monday", 1700, "Tuesday", 1600, "Tuesday"),
    ("Tuesday", 1700, "Wednesday", 1100, "Wednesday"),
    ("Wednesday", 1200, "Wednesday", 1600, "Wednesday"),
    ("Wednesday", 1700, "Thursday", 1600, "Thursday"),
    ("Thursday", 1700, "Friday", 1600, "Friday"),
)


def _session_xml(session: tuple[str, int, str, int, str]) -> str:
    begin_day, begin_time, end_day, end_time, trading_day = session
    return (
        "<Session>"
        f"<BeginDay>{begin_day}</BeginDay>"
        f"<BeginTime>{begin_time}</BeginTime>"
        f"<EndDay>{end_day}</EndDay>"
        f"<EndTime>{end_time}</EndTime>"
        f"<TradingDay>{trading_day}</TradingDay>"
        "</Session>"
    )


def _template(
    *,
    sessions: Iterable[tuple[str, int, str, int, str]] = WEEKLY_SESSIONS,
    full_holiday_name: str = "Full Holiday",
    partial_holiday_name: str = "Independence Day",
    include_full_holiday: bool = True,
    include_partial_holiday: bool = True,
    timezone_id: str | None = "Central Standard Time",
    extra: str = "",
) -> bytes:
    holidays = (
        "<Holiday><Date>2026-07-06T00:00:00</Date>"
        f"<Description>{full_holiday_name}</Description></Holiday>"
        if include_full_holiday
        else ""
    )
    partials = (
        "<PartialHoliday>"
        "<Constraint><BeginDay>Sunday</BeginDay><BeginTime>0</BeginTime>"
        "<EndDay>Friday</EndDay><EndTime>1200</EndTime>"
        "<TradingDay>Friday</TradingDay></Constraint>"
        "<Date>2026-07-03T00:00:00</Date>"
        f"<Description>{partial_holiday_name}</Description>"
        "<IsEarlyEnd>true</IsEarlyEnd><IsLateBegin>false</IsLateBegin>"
        "<Sessions /></PartialHoliday>"
        if include_partial_holiday
        else ""
    )
    timezone_xml = "" if timezone_id is None else f"<TimeZone>{timezone_id}</TimeZone>"
    session_xml = "".join(_session_xml(session) for session in sessions)
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
        "<NinjaTrader><TradingHours>"
        f"<HolidaysSerializable>{holidays}</HolidaysSerializable>"
        f"<PartialHolidaysSerializable>{partials}</PartialHolidaysSerializable>"
        "<Version>5119</Version>"
        "<Name>CME US Index Futures ETH</Name>"
        f"<Sessions>{session_xml}</Sessions>"
        f"{timezone_xml}{extra}"
        "</TradingHours></NinjaTrader>"
    ).encode("utf-8")


BASE_TEMPLATE = _template()


def _policy_dates() -> tuple[date, ...]:
    result: list[date] = []
    current = POLICY_START
    while current <= POLICY_END:
        result.append(current)
        current += timedelta(days=1)
    return tuple(result)


def _clock(value: int) -> tuple[int, int]:
    return divmod(value, 100)


def _day_offset(source: str, target: str, *, begin: bool) -> int:
    names = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
    offset = names.index(source) - names.index(target)
    if begin and offset > 0:
        offset -= 7
    if not begin and offset < 0:
        offset += 7
    return offset


def _expected_instants(
    civil_date: date,
    *,
    sessions: Iterable[tuple[str, int, str, int, str]] = WEEKLY_SESSIONS,
    include_full_holiday: bool = True,
    include_partial_holiday: bool = True,
) -> list[tuple[datetime, datetime]]:
    if include_full_holiday and civil_date == date(2026, 7, 6):
        return []
    day_name = civil_date.strftime("%A")
    result: list[tuple[datetime, datetime]] = []
    for begin_day, begin_time, end_day, end_time, trading_day in sessions:
        if trading_day != day_name:
            continue
        begin_hour, begin_minute = _clock(begin_time)
        end_hour, end_minute = _clock(end_time)
        begin_date = civil_date + timedelta(days=_day_offset(begin_day, trading_day, begin=True))
        end_date = civil_date + timedelta(days=_day_offset(end_day, trading_day, begin=False))
        begin = datetime.combine(begin_date, datetime.min.time(), APPLICATION_ZONE).replace(
            hour=begin_hour, minute=begin_minute
        )
        end = datetime.combine(end_date, datetime.min.time(), APPLICATION_ZONE).replace(
            hour=end_hour, minute=end_minute
        )
        if include_partial_holiday and civil_date == date(2026, 7, 3):
            end = min(
                end,
                datetime(2026, 7, 3, 12, 0, tzinfo=APPLICATION_ZONE),
            )
        if begin < end:
            result.append((begin, end))
    return result


def _segment(begin: datetime, end: datetime, *, pc_zone: timezone = PC_ZONE) -> dict[str, str]:
    return {
        "begin_application": begin.isoformat(),
        "end_application": end.isoformat(),
        "begin_pc": begin.astimezone(pc_zone).isoformat(),
        "end_pc": end.astimezone(pc_zone).isoformat(),
    }


def _quality() -> dict[str, object]:
    return {
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
        "first_250_source_sha256": "a" * 64,
        "complete_session_source_sha256": "b" * 64,
        "canonicalization_id": "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1",
    }


def _scan(
    *,
    sessions: Iterable[tuple[str, int, str, int, str]] = WEEKLY_SESSIONS,
    full_holiday_name: str = "Full Holiday",
    partial_holiday_name: str = "Independence Day",
    include_full_holiday: bool = True,
    include_partial_holiday: bool = True,
    pc_zone: timezone = PC_ZONE,
) -> dict[str, object]:
    observations: list[dict[str, object]] = []
    for civil_date in _policy_dates():
        instants = _expected_instants(
            civil_date,
            sessions=sessions,
            include_full_holiday=include_full_holiday,
            include_partial_holiday=include_partial_holiday,
        )
        segments = [_segment(begin, end, pc_zone=pc_zone) for begin, end in instants]
        breaks = [
            {
                "begin_application": segments[index - 1]["end_application"],
                "end_application": segments[index]["begin_application"],
                "begin_pc": segments[index - 1]["end_pc"],
                "end_pc": segments[index]["begin_pc"],
            }
            for index in range(1, len(segments))
            if datetime.fromisoformat(segments[index - 1]["end_application"])
            < datetime.fromisoformat(segments[index]["begin_application"])
        ]
        holiday_name: str | None = None
        partial = False
        if include_full_holiday and civil_date == date(2026, 7, 6):
            holiday_name = full_holiday_name
        if include_partial_holiday and civil_date == date(2026, 7, 3):
            holiday_name = partial_holiday_name
            partial = True
        schedule = {
            "holiday_name": holiday_name,
            "partial_session": partial,
            "expected_open_segments": segments,
            "scheduled_breaks": breaks,
            "application_session_begin": segments[0]["begin_application"] if segments else None,
            "application_session_end": segments[-1]["end_application"] if segments else None,
            "pc_log_session_begin": segments[0]["begin_pc"] if segments else None,
            "pc_log_session_end": segments[-1]["end_pc"] if segments else None,
            "effective_schedule_source": SOURCE,
        }
        observations.append(
            {
                "civil_date": civil_date.isoformat(),
                "classification": "SESSION" if segments else "NO_SESSION",
                "exchange_trading_date": civil_date.isoformat() if segments else None,
                "schedule_evidence": schedule,
                "quality": _quality() if segments else None,
            }
        )
    return {
        "schema_version": "1.0",
        "acquisition_id": "20260916T120000Z-abcdef12",
        "cohort_id": "mnq-202609-5m-v1",
        "contract": {
            "contract_label": "MNQ SEP26",
            "master_name": "MNQ",
            "full_name": "MNQ SEP26",
            "expiry_month": 9,
            "expiry_year": 2026,
        },
        "bar_series": {
            "type": "Minute",
            "value": 5,
            "native": True,
            "timestamp_semantics": "NinjaTrader native Minute bar close timestamp in application time",
        },
        "trading_hours": {
            "name": "CME US Index Futures ETH",
            "timezone_id": "Central Standard Time",
            "exchange_trading_date_member": "ActualTradingDayExchange",
        },
        "civil_date_start": "2026-06-22",
        "civil_date_end": "2026-07-24",
        "canonicalization_id": "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1",
        "observations": observations,
        "transformations": {
            "sorted": False,
            "deduplicated": False,
            "filled": False,
            "interpolated": False,
            "resampled": False,
            "timezone_converted": False,
            "back_adjusted": False,
            "repaired": False,
        },
        "completed_at": "2026-09-16T12:00:00+08:00",
    }


def _observation(scan: dict[str, object], civil_date: str) -> dict[str, object]:
    observations = scan["observations"]
    assert isinstance(observations, list)
    return next(item for item in observations if item["civil_date"] == civil_date)


def _schedule_evidence(observation: dict[str, object]) -> dict[str, object]:
    value = observation["schedule_evidence"]
    assert isinstance(value, dict)
    return value


def test_verifies_complete_calendar_and_exact_public_interfaces() -> None:
    calendar = verify_inventory_calendar(_scan(), BASE_TEMPLATE)

    assert isinstance(calendar, VerifiedInventoryCalendar)
    assert len(calendar.sessions) == 24
    assert all(isinstance(session, VerifiedSession) for session in calendar.sessions)
    assert all(isinstance(segment, SessionSegment) for session in calendar.sessions for segment in session.segments)
    assert tuple(session.trading_date for session in calendar.sessions) == tuple(
        value
        for value in _policy_dates()
        if _expected_instants(value)
    )


def test_accepts_schema_valid_segment_mapping_member_order() -> None:
    scan = _scan()
    schedule = _schedule_evidence(_observation(scan, "2026-06-22"))
    original = schedule["expected_open_segments"][0]
    schedule["expected_open_segments"][0] = {
        "end_pc": original["end_pc"],
        "begin_pc": original["begin_pc"],
        "end_application": original["end_application"],
        "begin_application": original["begin_application"],
    }

    assert verify_inventory_calendar(scan, BASE_TEMPLATE).sessions


@pytest.mark.parametrize("defect", ["missing", "duplicate", "unexpected", "out_of_order"])
def test_rejects_any_defect_in_the_exact_33_date_civil_universe(defect: str) -> None:
    scan = _scan()
    observations = scan["observations"]
    assert isinstance(observations, list)
    if defect == "missing":
        observations.pop()
    elif defect == "duplicate":
        observations[-1] = deepcopy(observations[-2])
    elif defect == "unexpected":
        observations[-1]["civil_date"] = "2026-07-25"
    else:
        observations[0], observations[1] = observations[1], observations[0]

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(scan, BASE_TEMPLATE)


def test_weekends_and_full_holiday_are_checked_no_session_and_not_returned() -> None:
    scan = _scan()
    calendar = verify_inventory_calendar(scan, BASE_TEMPLATE)

    for closed_date in (date(2026, 6, 27), date(2026, 6, 28), date(2026, 7, 6)):
        observation = _observation(scan, closed_date.isoformat())
        assert observation["classification"] == "NO_SESSION"
        assert closed_date not in {session.civil_date for session in calendar.sessions}
    assert _schedule_evidence(_observation(scan, "2026-07-06"))["holiday_name"] == "Full Holiday"


def test_partial_session_prior_date_open_and_scheduled_break_are_preserved() -> None:
    calendar = verify_inventory_calendar(_scan(), BASE_TEMPLATE)
    partial = next(session for session in calendar.sessions if session.civil_date == date(2026, 7, 3))
    wednesday = next(session for session in calendar.sessions if session.civil_date == date(2026, 6, 24))

    assert partial.partial_session is True
    assert partial.holiday_name == "Independence Day"
    assert partial.segments[0].end_application == datetime(2026, 7, 3, 12, 0, tzinfo=APPLICATION_ZONE)
    assert wednesday.trading_date == date(2026, 6, 24)
    assert wednesday.segments[0].begin_application.date() == date(2026, 6, 23)
    assert len(wednesday.segments) == 2
    assert wednesday.segments[0].end_application == datetime(2026, 6, 24, 11, 0, tzinfo=APPLICATION_ZONE)
    assert wednesday.segments[1].begin_application == datetime(2026, 6, 24, 12, 0, tzinfo=APPLICATION_ZONE)


def test_contiguous_template_segments_remain_distinct_without_an_invented_break() -> None:
    sessions = (
        ("Sunday", 1700, "Monday", 1100, "Monday"),
        ("Monday", 1100, "Monday", 1600, "Monday"),
        *WEEKLY_SESSIONS[1:],
    )
    scan = _scan(sessions=sessions)

    calendar = verify_inventory_calendar(scan, _template(sessions=sessions))
    monday = next(session for session in calendar.sessions if session.civil_date == date(2026, 6, 22))

    assert len(monday.segments) == 2
    assert _schedule_evidence(_observation(scan, "2026-06-22"))["scheduled_breaks"] == []


@pytest.mark.parametrize("kind", ["duplicate", "conflict"])
def test_rejects_duplicate_or_conflicting_exchange_trading_dates(kind: str) -> None:
    scan = _scan()
    current = _observation(scan, "2026-06-23")
    current["exchange_trading_date"] = "2026-06-22" if kind == "duplicate" else "2026-06-24"

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(scan, BASE_TEMPLATE)


@pytest.mark.parametrize("field", ["classification", "segment", "holiday", "trading_date"])
def test_rejects_scanner_template_calendar_mismatches(field: str) -> None:
    scan = _scan()
    if field == "classification":
        _observation(scan, "2026-06-27")["classification"] = "SESSION"
    elif field == "segment":
        schedule = _schedule_evidence(_observation(scan, "2026-06-22"))
        schedule["expected_open_segments"][0]["end_application"] = "2026-06-22T15:55:00-05:00"
    elif field == "holiday":
        _schedule_evidence(_observation(scan, "2026-07-03"))["holiday_name"] = "Wrong Holiday"
    else:
        _observation(scan, "2026-06-22")["exchange_trading_date"] = "2026-06-23"

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(scan, BASE_TEMPLATE)


@pytest.mark.parametrize(
    "field,value",
    [
        ("end_application", "2026-06-22T16:00:00-04:00"),
        ("begin_pc", "2026-06-22T07:00:00+08:00"),
        ("begin_application", "2026-06-21T17:00:00"),
        ("end_pc", "2026-06-23T05:00:00"),
    ],
)
def test_rejects_application_or_pc_timestamp_and_offset_inconsistency(field: str, value: str) -> None:
    scan = _scan()
    schedule = _schedule_evidence(_observation(scan, "2026-06-22"))
    schedule["expected_open_segments"][0][field] = value

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(scan, BASE_TEMPLATE)


def test_pc_values_cannot_invent_an_absent_session() -> None:
    scan = _scan()
    saturday = _observation(scan, "2026-06-27")
    invented = _segment(
        datetime(2026, 6, 26, 17, 0, tzinfo=APPLICATION_ZONE),
        datetime(2026, 6, 27, 16, 0, tzinfo=APPLICATION_ZONE),
    )
    saturday["classification"] = "SESSION"
    saturday["exchange_trading_date"] = "2026-06-27"
    schedule = _schedule_evidence(saturday)
    schedule["expected_open_segments"] = [invented]
    schedule["application_session_begin"] = invented["begin_application"]
    schedule["application_session_end"] = invented["end_application"]
    schedule["pc_log_session_begin"] = invented["begin_pc"]
    schedule["pc_log_session_end"] = invented["end_pc"]
    saturday["quality"] = _quality()

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(scan, BASE_TEMPLATE)


@pytest.mark.parametrize(
    "template",
    [
        _template(extra="<UnknownSchedule />"),
        _template(timezone_id=None),
        _template(timezone_id="Mars Standard Time"),
        b"<NinjaTrader><NotTradingHours /></NinjaTrader>",
        _template().replace(b"<NinjaTrader>", b"<WrongRoot>").replace(
            b"</NinjaTrader>", b"</WrongRoot>"
        ),
        _template().replace(b"<Session>", b'<Session unknown="true">', 1),
        _template().replace(b"<EndTime>1600</EndTime>", b"<EndTime>2460</EndTime>", 1),
    ],
)
def test_rejects_unknown_xml_layout_or_missing_malformed_timezone(template: bytes) -> None:
    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(_scan(), template)


@pytest.mark.parametrize(
    "sessions",
    [
        (("Sunday", 1700, "Sunday", 1600, "Monday"),),
        (
            ("Sunday", 1700, "Monday", 1200, "Monday"),
            ("Monday", 1100, "Monday", 1600, "Monday"),
        ),
        (
            ("Monday", 1200, "Monday", 1600, "Monday"),
            ("Sunday", 1700, "Monday", 1100, "Monday"),
        ),
    ],
)
def test_rejects_non_chronological_overlapping_or_unsorted_template_segments(
    sessions: tuple[tuple[str, int, str, int, str], ...],
) -> None:
    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(_scan(sessions=sessions), _template(sessions=sessions))


def test_rejects_unsorted_scanner_segments_instead_of_repairing_them() -> None:
    scan = _scan()
    schedule = _schedule_evidence(_observation(scan, "2026-06-24"))
    schedule["expected_open_segments"].reverse()

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(scan, BASE_TEMPLATE)


def test_rejects_cross_trading_date_session_overlap_instead_of_repairing_it() -> None:
    sessions = (
        ("Sunday", 1700, "Tuesday", 1800, "Monday"),
        *WEEKLY_SESSIONS[1:],
    )

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(
            _scan(sessions=sessions),
            _template(sessions=sessions),
        )


def test_bounds_come_only_from_verified_segments_and_ignore_scanner_summary_claims() -> None:
    scan = _scan()
    scan["earliest_session_begin"] = "1900-01-01T00:00:00+00:00"
    scan["latest_session_end"] = "2999-12-31T23:59:59+00:00"
    calendar = verify_inventory_calendar(scan, BASE_TEMPLATE)

    assert calendar.earliest_session_begin == datetime(2026, 6, 21, 17, 0, tzinfo=APPLICATION_ZONE)
    assert calendar.latest_session_end == datetime(2026, 7, 24, 16, 0, tzinfo=APPLICATION_ZONE)


def test_exact_template_bytes_and_verified_calendar_facts_bind_separate_hashes() -> None:
    scan = _scan()
    original = verify_inventory_calendar(scan, BASE_TEMPLATE)
    whitespace_template = BASE_TEMPLATE + b"\n"
    whitespace = verify_inventory_calendar(scan, whitespace_template)
    changed_scan = _scan(pc_zone=timezone(timedelta(hours=9)))
    changed_calendar = verify_inventory_calendar(changed_scan, BASE_TEMPLATE)

    assert original.template_sha256 == sha256(BASE_TEMPLATE).hexdigest()
    assert whitespace.template_sha256 == sha256(whitespace_template).hexdigest()
    assert whitespace.template_sha256 != original.template_sha256
    assert whitespace.calendar_binding_sha256 == original.calendar_binding_sha256
    assert changed_calendar.template_sha256 == original.template_sha256
    assert changed_calendar.calendar_binding_sha256 != original.calendar_binding_sha256


@pytest.mark.parametrize("mutation", ["existence", "holiday", "partial", "segment"])
def test_calendar_binding_hash_changes_for_every_independently_bound_calendar_fact(mutation: str) -> None:
    original = verify_inventory_calendar(_scan(), BASE_TEMPLATE)
    if mutation == "existence":
        template = _template(include_full_holiday=False)
        scan = _scan(include_full_holiday=False)
    elif mutation == "holiday":
        template = _template(full_holiday_name="Renamed Full Holiday")
        scan = _scan(full_holiday_name="Renamed Full Holiday")
    elif mutation == "partial":
        template = _template(partial_holiday_name="Renamed Partial Holiday")
        scan = _scan(partial_holiday_name="Renamed Partial Holiday")
    else:
        sessions = tuple(
            (begin_day, begin_time, end_day, 1555 if trading_day == "Thursday" else end_time, trading_day)
            for begin_day, begin_time, end_day, end_time, trading_day in WEEKLY_SESSIONS
        )
        template = _template(sessions=sessions)
        scan = _scan(sessions=sessions)

    changed = verify_inventory_calendar(scan, template)
    assert changed.calendar_binding_sha256 != original.calendar_binding_sha256


def test_no_actual_session_calendar_fails_globally_with_approved_error() -> None:
    template = _template(sessions=(), include_full_holiday=False, include_partial_holiday=False)
    scan = _scan(sessions=(), include_full_holiday=False, include_partial_holiday=False)

    with pytest.raises(InventoryValidationError):
        verify_inventory_calendar(scan, template)
