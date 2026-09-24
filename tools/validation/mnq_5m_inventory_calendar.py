"""Independent Trading Hours calendar verification for the MNQ inventory scan."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from types import MappingProxyType
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.validation.mnq_5m_inventory_common import (
    canonical_payload_sha256,
    sha256_bytes,
)
from tools.validation.mnq_5m_inventory_evidence import InventoryValidationError


POLICY_START = date(2026, 6, 22)
POLICY_END = date(2026, 7, 24)
TEMPLATE_NAME = "CME US Index Futures ETH"
TEMPLATE_TIMEZONE_ID = "Central Standard Time"
EXCHANGE_DATE_MEMBER = "ActualTradingDayExchange"
SCHEDULE_SOURCE = "SessionIterator using Bars.TradingHours and ActualTradingDayExchange"
DAY_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)


@dataclass(frozen=True)
class SessionSegment:
    begin_application: datetime
    end_application: datetime
    begin_pc: datetime
    end_pc: datetime


@dataclass(frozen=True)
class VerifiedSession:
    civil_date: date
    trading_date: date
    holiday_name: str | None
    partial_session: bool | None
    segments: tuple[SessionSegment, ...]
    observation: Mapping[str, object]


@dataclass(frozen=True)
class VerifiedInventoryCalendar:
    sessions: tuple[VerifiedSession, ...]
    earliest_session_begin: datetime
    latest_session_end: datetime
    template_sha256: str
    calendar_binding_sha256: str


@dataclass(frozen=True)
class _ScheduleDefinition:
    begin_day: str
    begin_time: time
    end_day: str
    end_time: time
    trading_day: str


@dataclass(frozen=True)
class _PartialHoliday:
    description: str
    constraint: _ScheduleDefinition
    early_end: bool
    late_begin: bool


@dataclass(frozen=True)
class _Template:
    sessions: tuple[_ScheduleDefinition, ...]
    holidays: Mapping[date, str]
    partial_holidays: Mapping[date, _PartialHoliday]
    timezone: ZoneInfo


@dataclass(frozen=True)
class _ExpectedDate:
    civil_date: date
    holiday_name: str | None
    partial_session: bool
    segments: tuple[tuple[datetime, datetime], ...]


def _fail(message: str) -> None:
    raise InventoryValidationError(message)


def _children(element: ET.Element, names: Sequence[str], label: str) -> tuple[ET.Element, ...]:
    children = tuple(element)
    if element.attrib or tuple(child.tag for child in children) != tuple(names):
        _fail(f"unknown {label} XML layout")
    return children


def _leaf(element: ET.Element, label: str) -> str:
    if element.attrib or tuple(element):
        _fail(f"unknown {label} XML layout")
    value = element.text or ""
    if not value:
        _fail(f"missing {label}")
    return value


def _parse_xml_date(value: str, label: str) -> date:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise InventoryValidationError(f"malformed {label}") from error
    if parsed.tzinfo is not None or parsed.time() != time.min:
        _fail(f"malformed {label}")
    return parsed.date()


def _parse_clock(value: str, label: str) -> time:
    if not value.isascii() or not value.isdigit() or len(value) > 4:
        _fail(f"malformed {label}")
    numeric = int(value)
    hour, minute = divmod(numeric, 100)
    if hour > 23 or minute > 59:
        _fail(f"malformed {label}")
    return time(hour, minute)


def _parse_bool(value: str, label: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    _fail(f"malformed {label}")
    raise AssertionError("unreachable")


def _parse_schedule(element: ET.Element, label: str) -> _ScheduleDefinition:
    begin_day, begin_time, end_day, end_time, trading_day = _children(
        element,
        ("BeginDay", "BeginTime", "EndDay", "EndTime", "TradingDay"),
        label,
    )
    begin_day_value = _leaf(begin_day, f"{label} BeginDay")
    end_day_value = _leaf(end_day, f"{label} EndDay")
    trading_day_value = _leaf(trading_day, f"{label} TradingDay")
    if (
        begin_day_value not in DAY_NAMES
        or end_day_value not in DAY_NAMES
        or trading_day_value not in DAY_NAMES
    ):
        _fail(f"malformed {label} day")
    return _ScheduleDefinition(
        begin_day_value,
        _parse_clock(_leaf(begin_time, f"{label} BeginTime"), f"{label} BeginTime"),
        end_day_value,
        _parse_clock(_leaf(end_time, f"{label} EndTime"), f"{label} EndTime"),
        trading_day_value,
    )


def _parse_template(exact_bytes: bytes) -> _Template:
    try:
        root = ET.fromstring(exact_bytes)
    except (ET.ParseError, ValueError, TypeError) as error:
        raise InventoryValidationError("invalid Trading Hours XML") from error
    if root.tag != "NinjaTrader":
        _fail("unknown NinjaTrader root XML layout")
    (trading_hours,) = _children(root, ("TradingHours",), "NinjaTrader root")
    holidays_node, partials_node, version_node, name_node, sessions_node, timezone_node = _children(
        trading_hours,
        (
            "HolidaysSerializable",
            "PartialHolidaysSerializable",
            "Version",
            "Name",
            "Sessions",
            "TimeZone",
        ),
        "TradingHours",
    )
    try:
        if int(_leaf(version_node, "Version")) < 1:
            _fail("malformed Version")
    except ValueError as error:
        raise InventoryValidationError("malformed Version") from error
    if _leaf(name_node, "Name") != TEMPLATE_NAME:
        _fail("unexpected Trading Hours template name")
    timezone_id = _leaf(timezone_node, "TimeZone")
    if timezone_id != TEMPLATE_TIMEZONE_ID:
        _fail("unknown Trading Hours timezone")
    try:
        template_timezone = ZoneInfo("America/Chicago")
    except ZoneInfoNotFoundError as error:
        raise InventoryValidationError("Trading Hours timezone unavailable") from error

    if holidays_node.attrib:
        _fail("unknown HolidaysSerializable XML layout")
    holidays: dict[date, str] = {}
    for holiday_node in holidays_node:
        if holiday_node.tag != "Holiday":
            _fail("unknown HolidaysSerializable XML layout")
        date_node, description_node = _children(
            holiday_node,
            ("Date", "Description"),
            "Holiday",
        )
        holiday_date = _parse_xml_date(_leaf(date_node, "Holiday Date"), "Holiday Date")
        description = _leaf(description_node, "Holiday Description")
        if holiday_date in holidays:
            _fail("duplicate holiday date")
        holidays[holiday_date] = description

    if partials_node.attrib:
        _fail("unknown PartialHolidaysSerializable XML layout")
    partials: dict[date, _PartialHoliday] = {}
    for partial_node in partials_node:
        if partial_node.tag != "PartialHoliday":
            _fail("unknown PartialHolidaysSerializable XML layout")
        constraint_node, date_node, description_node, early_node, late_node, custom_node = _children(
            partial_node,
            ("Constraint", "Date", "Description", "IsEarlyEnd", "IsLateBegin", "Sessions"),
            "PartialHoliday",
        )
        if custom_node.attrib or tuple(custom_node):
            _fail("unknown PartialHoliday Sessions XML layout")
        partial_date = _parse_xml_date(
            _leaf(date_node, "PartialHoliday Date"),
            "PartialHoliday Date",
        )
        early_end = _parse_bool(
            _leaf(early_node, "PartialHoliday IsEarlyEnd"),
            "PartialHoliday IsEarlyEnd",
        )
        late_begin = _parse_bool(
            _leaf(late_node, "PartialHoliday IsLateBegin"),
            "PartialHoliday IsLateBegin",
        )
        if not early_end and not late_begin:
            _fail("partial holiday has no schedule override")
        if partial_date in partials or partial_date in holidays:
            _fail("conflicting holiday date")
        partials[partial_date] = _PartialHoliday(
            _leaf(description_node, "PartialHoliday Description"),
            _parse_schedule(constraint_node, "PartialHoliday Constraint"),
            early_end,
            late_begin,
        )

    if sessions_node.attrib:
        _fail("unknown Sessions XML layout")
    schedules: list[_ScheduleDefinition] = []
    for session_node in sessions_node:
        if session_node.tag != "Session":
            _fail("unknown Sessions XML layout")
        schedules.append(_parse_schedule(session_node, "Session"))
    return _Template(
        tuple(schedules),
        MappingProxyType(holidays),
        MappingProxyType(partials),
        template_timezone,
    )


def _policy_dates() -> tuple[date, ...]:
    values: list[date] = []
    current = POLICY_START
    while current <= POLICY_END:
        values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def _relative_date(civil_date: date, source_day: str, trading_day: str, *, begin: bool) -> date:
    offset = DAY_NAMES.index(source_day) - DAY_NAMES.index(trading_day)
    if begin and offset > 0:
        offset -= len(DAY_NAMES)
    if not begin and offset < 0:
        offset += len(DAY_NAMES)
    return civil_date + timedelta(days=offset)


def _scheduled_datetime(
    civil_date: date,
    source_day: str,
    clock: time,
    trading_day: str,
    template_timezone: ZoneInfo,
    *,
    begin: bool,
) -> datetime:
    value = datetime.combine(
        _relative_date(civil_date, source_day, trading_day, begin=begin),
        clock,
        template_timezone,
    )
    if value.astimezone(timezone.utc).astimezone(template_timezone).replace(fold=value.fold) != value:
        _fail("impossible Trading Hours local timestamp")
    return value


def _calendar_for_date(civil_date: date, template: _Template) -> _ExpectedDate:
    if civil_date in template.holidays:
        return _ExpectedDate(civil_date, template.holidays[civil_date], False, ())
    trading_day = civil_date.strftime("%A")
    segments: list[tuple[datetime, datetime]] = []
    for schedule in template.sessions:
        if schedule.trading_day != trading_day:
            continue
        begin = _scheduled_datetime(
            civil_date,
            schedule.begin_day,
            schedule.begin_time,
            schedule.trading_day,
            template.timezone,
            begin=True,
        )
        end = _scheduled_datetime(
            civil_date,
            schedule.end_day,
            schedule.end_time,
            schedule.trading_day,
            template.timezone,
            begin=False,
        )
        if begin >= end:
            _fail("non-chronological template segment")
        segments.append((begin, end))

    holiday_name: str | None = None
    partial_session = False
    partial = template.partial_holidays.get(civil_date)
    if partial is not None:
        if not segments or partial.constraint.trading_day != trading_day:
            _fail("partial holiday does not bind an actual trading session")
        holiday_name = partial.description
        partial_session = True
        if partial.late_begin:
            boundary = _scheduled_datetime(
                civil_date,
                partial.constraint.begin_day,
                partial.constraint.begin_time,
                partial.constraint.trading_day,
                template.timezone,
                begin=True,
            )
            segments = [
                (max(begin, boundary), end)
                for begin, end in segments
                if end > boundary
            ]
        if partial.early_end:
            boundary = _scheduled_datetime(
                civil_date,
                partial.constraint.end_day,
                partial.constraint.end_time,
                partial.constraint.trading_day,
                template.timezone,
                begin=False,
            )
            segments = [
                (begin, min(end, boundary))
                for begin, end in segments
                if begin < boundary
            ]
        if not segments:
            _fail("partial holiday removed its actual session")

    previous_end: datetime | None = None
    for begin, end in segments:
        if begin >= end or (previous_end is not None and begin < previous_end):
            _fail("non-chronological or overlapping template segments")
        previous_end = end
    return _ExpectedDate(civil_date, holiday_name, partial_session, tuple(segments))


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"invalid {label}")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        _fail(f"invalid {label}")
    return value


def _aware_datetime(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        _fail(f"invalid {label}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise InventoryValidationError(f"invalid {label}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"naive {label}")
    return parsed


def _same_instant(left: datetime, right: datetime) -> bool:
    return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _verify_segment(
    value: object,
    expected: tuple[datetime, datetime],
    label: str,
) -> tuple[SessionSegment, dict[str, str]]:
    segment = _mapping(value, label)
    required = ("begin_application", "end_application", "begin_pc", "end_pc")
    if len(segment) != len(required) or any(key not in segment for key in required):
        _fail(f"invalid {label} shape")
    raw = {key: segment[key] for key in required}
    if not all(isinstance(item, str) for item in raw.values()):
        _fail(f"invalid {label} timestamp")
    begin_application = _aware_datetime(raw["begin_application"], f"{label} begin_application")
    end_application = _aware_datetime(raw["end_application"], f"{label} end_application")
    begin_pc = _aware_datetime(raw["begin_pc"], f"{label} begin_pc")
    end_pc = _aware_datetime(raw["end_pc"], f"{label} end_pc")
    expected_begin, expected_end = expected
    if (
        begin_application >= end_application
        or not _same_instant(begin_application, expected_begin)
        or not _same_instant(end_application, expected_end)
        or not _same_instant(begin_pc, expected_begin)
        or not _same_instant(end_pc, expected_end)
        or not _same_instant(begin_application, begin_pc)
        or not _same_instant(end_application, end_pc)
    ):
        _fail(f"{label} timestamp or offset mismatch")
    return (
        SessionSegment(begin_application, end_application, begin_pc, end_pc),
        {key: str(raw[key]) for key in required},
    )


def _verify_breaks(
    value: object,
    raw_segments: Sequence[dict[str, str]],
    label: str,
) -> tuple[dict[str, str], ...]:
    supplied = _sequence(value, label)
    expected_breaks: list[dict[str, str]] = []
    for index in range(1, len(raw_segments)):
        previous_end = _aware_datetime(
            raw_segments[index - 1]["end_application"],
            label,
        )
        current_begin = _aware_datetime(
            raw_segments[index]["begin_application"],
            label,
        )
        if previous_end < current_begin:
            expected_breaks.append(
                {
                    "begin_application": raw_segments[index - 1]["end_application"],
                    "end_application": raw_segments[index]["begin_application"],
                    "begin_pc": raw_segments[index - 1]["end_pc"],
                    "end_pc": raw_segments[index]["begin_pc"],
                }
            )
    if len(supplied) != len(expected_breaks):
        _fail(f"{label} mismatch")
    verified: list[dict[str, str]] = []
    for index, (item, expected) in enumerate(zip(supplied, expected_breaks)):
        current = _mapping(item, f"{label}[{index}]")
        if dict(current) != expected:
            _fail(f"{label} mismatch")
        if _aware_datetime(expected["begin_application"], label) >= _aware_datetime(
            expected["end_application"], label
        ):
            _fail(f"{label} is not a scheduled closure")
        verified.append(expected)
    return tuple(verified)


def _verify_observation(
    value: object,
    expected: _ExpectedDate,
) -> tuple[VerifiedSession | None, dict[str, object], set[timedelta], set[timedelta]]:
    observation = _mapping(value, f"observation {expected.civil_date.isoformat()}")
    if observation.get("civil_date") != expected.civil_date.isoformat():
        _fail("civil-date coverage mismatch")
    has_session = bool(expected.segments)
    expected_classification = "SESSION" if has_session else "NO_SESSION"
    if observation.get("classification") != expected_classification:
        _fail("scanner/template session classification mismatch")
    expected_trading_date = expected.civil_date.isoformat() if has_session else None
    if observation.get("exchange_trading_date") != expected_trading_date:
        _fail("scanner/template exchange trading-date mismatch")
    schedule = _mapping(observation.get("schedule_evidence"), "schedule_evidence")
    if schedule.get("holiday_name") != expected.holiday_name:
        _fail("scanner/template holiday mismatch")
    if schedule.get("partial_session") is not expected.partial_session:
        _fail("scanner/template partial-session mismatch")
    if schedule.get("effective_schedule_source") != SCHEDULE_SOURCE:
        _fail("scanner schedule source mismatch")

    supplied_segments = _sequence(schedule.get("expected_open_segments"), "expected_open_segments")
    if len(supplied_segments) != len(expected.segments):
        _fail("scanner/template segment-count mismatch")
    segments: list[SessionSegment] = []
    raw_segments: list[dict[str, str]] = []
    application_offsets: set[timedelta] = set()
    pc_offsets: set[timedelta] = set()
    previous_end: datetime | None = None
    for index, (supplied, expected_segment) in enumerate(zip(supplied_segments, expected.segments)):
        segment, raw = _verify_segment(supplied, expected_segment, f"segment[{index}]")
        if previous_end is not None and segment.begin_application < previous_end:
            _fail("scanner segments are not chronological")
        previous_end = segment.end_application
        segments.append(segment)
        raw_segments.append(raw)
        application_offsets.update(
            (segment.begin_application.utcoffset(), segment.end_application.utcoffset())
        )
        pc_offsets.update((segment.begin_pc.utcoffset(), segment.end_pc.utcoffset()))

    breaks = _verify_breaks(schedule.get("scheduled_breaks"), raw_segments, "scheduled_breaks")
    expected_summary = {
        "application_session_begin": raw_segments[0]["begin_application"] if raw_segments else None,
        "application_session_end": raw_segments[-1]["end_application"] if raw_segments else None,
        "pc_log_session_begin": raw_segments[0]["begin_pc"] if raw_segments else None,
        "pc_log_session_end": raw_segments[-1]["end_pc"] if raw_segments else None,
    }
    for field, expected_value in expected_summary.items():
        if schedule.get(field) != expected_value:
            _fail(f"scanner {field} mismatch")
    if not has_session and observation.get("quality") is not None:
        _fail("NO_SESSION observation contains session quality")

    binding = {
        "civil_date": expected.civil_date.isoformat(),
        "classification": expected_classification,
        "exchange_trading_date": expected_trading_date,
        "holiday_name": expected.holiday_name,
        "partial_session": expected.partial_session,
        "expected_open_segments": raw_segments,
        "scheduled_breaks": list(breaks),
        **expected_summary,
    }
    if not has_session:
        return None, binding, application_offsets, pc_offsets
    frozen_observation = _freeze(observation)
    assert isinstance(frozen_observation, Mapping)
    return (
        VerifiedSession(
            expected.civil_date,
            expected.civil_date,
            expected.holiday_name,
            expected.partial_session,
            tuple(segments),
            frozen_observation,
        ),
        binding,
        application_offsets,
        pc_offsets,
    )


def verify_inventory_calendar(
    scan: Mapping[str, object],
    trading_hours_template: bytes,
) -> VerifiedInventoryCalendar:
    """Return independently verified sessions, bounds, and calendar hashes."""

    if not isinstance(scan, Mapping) or not isinstance(trading_hours_template, bytes):
        _fail("invalid calendar verification input")
    template = _parse_template(trading_hours_template)
    trading_hours = _mapping(scan.get("trading_hours"), "scan trading_hours")
    if (
        trading_hours.get("name") != TEMPLATE_NAME
        or trading_hours.get("timezone_id") != TEMPLATE_TIMEZONE_ID
        or trading_hours.get("exchange_trading_date_member") != EXCHANGE_DATE_MEMBER
    ):
        _fail("scan/template Trading Hours identity mismatch")
    if (
        scan.get("civil_date_start") != POLICY_START.isoformat()
        or scan.get("civil_date_end") != POLICY_END.isoformat()
    ):
        _fail("scan civil-date policy mismatch")
    transformations = _mapping(scan.get("transformations"), "scanner transformations")
    for key in ("sorted", "deduplicated", "filled", "repaired"):
        if transformations.get(key) is not False:
            _fail("scanner reports calendar repair")

    policy_dates = _policy_dates()
    observations = _sequence(scan.get("observations"), "scan observations")
    if len(observations) != len(policy_dates):
        _fail("scan must contain exactly 33 civil-date observations")
    supplied_dates = tuple(
        _mapping(item, f"observation[{index}]").get("civil_date")
        for index, item in enumerate(observations)
    )
    expected_dates = tuple(value.isoformat() for value in policy_dates)
    if supplied_dates != expected_dates:
        _fail("scan civil-date observations are missing, duplicated, unexpected, or out of order")

    sessions: list[VerifiedSession] = []
    bindings: list[dict[str, object]] = []
    application_offsets: set[timedelta] = set()
    pc_offsets: set[timedelta] = set()
    trading_dates: set[date] = set()
    earliest: datetime | None = None
    latest: datetime | None = None
    previous_session_end: datetime | None = None
    for observation, civil_date in zip(observations, policy_dates):
        expected = _calendar_for_date(civil_date, template)
        verified, binding, observed_application_offsets, observed_pc_offsets = _verify_observation(
            observation,
            expected,
        )
        bindings.append(binding)
        application_offsets.update(observed_application_offsets)
        pc_offsets.update(observed_pc_offsets)
        if verified is None:
            continue
        if verified.trading_date in trading_dates:
            _fail("duplicate exchange trading date")
        if sessions and verified.trading_date <= sessions[-1].trading_date:
            _fail("conflicting exchange trading-date order")
        if (
            previous_session_end is not None
            and verified.segments[0].begin_application < previous_session_end
        ):
            _fail("verified sessions overlap or are not chronological")
        trading_dates.add(verified.trading_date)
        sessions.append(verified)
        previous_session_end = verified.segments[-1].end_application
        for segment in verified.segments:
            if earliest is None or segment.begin_application < earliest:
                earliest = segment.begin_application
            if latest is None or segment.end_application > latest:
                latest = segment.end_application

    if not sessions or earliest is None or latest is None:
        _fail("verified calendar contains no actual session")
    if len(application_offsets) != 1 or len(pc_offsets) != 1:
        _fail("inconsistent application or PC/log UTC offsets")
    binding_payload: Mapping[str, object] = {
        "civil_date_start": POLICY_START.isoformat(),
        "civil_date_end": POLICY_END.isoformat(),
        "trading_hours_name": TEMPLATE_NAME,
        "trading_hours_timezone_id": TEMPLATE_TIMEZONE_ID,
        "dates": bindings,
    }
    return VerifiedInventoryCalendar(
        tuple(sessions),
        earliest,
        latest,
        sha256_bytes(trading_hours_template),
        canonical_payload_sha256(binding_payload, hash_field=""),
    )
