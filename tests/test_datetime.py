"""Dates, times and durations.

Two crashes shape this suite, and most of it exists for them.

The **naive/aware crash**: ``datetime.now() < datetime.now(timezone.utc)`` raises
``TypeError: can't compare offset-naive and offset-aware datetimes``. The
**date/datetime crash**: ``date(2020, 1, 1) < datetime(2020, 1, 1)`` raises one
too -- because ``datetime`` subclasses ``date``, which means no type checker
anywhere can refuse it. Both are the most common ways a real suite blows up on
dates, and both surface from inside the assertion library, where they read like
the library broke. Everything under "the two crashes" pins what is raised
instead.

The rest is the catalogue, and the caller bugs it refuses: an impossible calendar
component, a negative tolerance, an inverted range, and a difference chain that
was opened and never finished.
"""

import gc
import warnings
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from typing import Final, cast
from zoneinfo import ZoneInfo

import pytest

from lovely_assertions import AssertionFailure, expect, soft_assertions
from lovely_assertions._datetime import (
    DateExpect,
    DateTimeExpect,
    _offending_bound,  # pyright: ignore[reportPrivateUsage]
    rendered,
)

PARIS: Final = ZoneInfo("Europe/Paris")
TOKYO: Final = ZoneInfo("Asia/Tokyo")
NEW_YORK: Final = ZoneInfo("America/New_York")


class Anniversary(date):
    """A subclass of ``date``, because people write them and ``T`` must survive."""

    __slots__ = ()


class Blank(tzinfo):
    """A ``tzinfo`` that declines to say what the offset is.

    Legal, and naive by ``datetime``'s own reckoning: a value carrying one has a
    ``tzinfo`` and no timezone. The subject has to agree with ``datetime`` here,
    or every arithmetic assertion downstream reintroduces the naive/aware crash.
    """

    def utcoffset(self, dt: datetime | None, /) -> timedelta | None:
        return None

    def tzname(self, dt: datetime | None, /) -> str | None:
        return None

    def dst(self, dt: datetime | None, /) -> timedelta | None:
        return None


class Stamped:
    """A scoped formatter, to prove the date messages reach the registry."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, date)

    def format(self, value: object, /) -> str:
        return "<" + value.isoformat() + ">" if isinstance(value, date) else repr(value)


def _message(call: Callable[[], object], /) -> str:
    """The message a failing assertion produced."""
    with pytest.raises(AssertionFailure) as caught:
        call()
    return str(caught.value)


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------
def test_a_date_gets_the_ordering_catalogue() -> None:
    subject = expect(date(2020, 5, 4))
    assert subject.is_before(date(2020, 6, 1)) is subject
    assert subject.is_after(date(2020, 1, 1)) is subject
    assert subject.is_on_or_before(date(2020, 5, 4)) is subject
    assert subject.is_on_or_after(date(2020, 5, 4)) is subject


def test_the_ordering_failures_name_both_sides() -> None:
    hired_on = date(2020, 5, 4)
    assert _message(lambda: expect(hired_on).is_before(date(2019, 1, 1))) == (
        "Expected hired_on to be before 2019-01-01, but was 2020-05-04."
    )
    assert _message(lambda: expect(hired_on).is_after(date(2021, 1, 1))) == (
        "Expected hired_on to be after 2021-01-01, but was 2020-05-04."
    )
    assert _message(lambda: expect(hired_on).is_on_or_before(date(2019, 1, 1))) == (
        "Expected hired_on to be on or before 2019-01-01, but was 2020-05-04."
    )
    assert _message(lambda: expect(hired_on).is_on_or_after(date(2021, 1, 1))) == (
        "Expected hired_on to be on or after 2021-01-01, but was 2020-05-04."
    )


def test_the_strict_orderings_reject_the_boundary_and_the_loose_ones_take_it() -> None:
    """The one-character difference between the four, pinned at the boundary."""
    same = date(2020, 5, 4)
    expect(same).is_on_or_before(same).and_.is_on_or_after(same)
    with pytest.raises(AssertionFailure):
        expect(same).is_before(same)
    with pytest.raises(AssertionFailure):
        expect(same).is_after(same)


def test_a_datetime_orders_to_the_microsecond() -> None:
    subject = expect(datetime(2020, 1, 1, 12, 0, 0, 1))
    assert subject.is_after(datetime(2020, 1, 1, 12, 0, 0, 0)) is subject
    assert subject.is_before(datetime(2020, 1, 1, 12, 0, 0, 2)) is subject


def test_a_time_orders_too() -> None:
    lunch = expect(time(12, 30))
    assert lunch.is_after(time(9, 0)) is lunch
    assert lunch.is_before(time(13, 0)) is lunch
    assert lunch.is_on_or_after(time(12, 30)) is lunch
    assert lunch.is_on_or_before(time(12, 30)) is lunch


# ---------------------------------------------------------------------------
# Ranges: `is_between` includes its bounds
# ---------------------------------------------------------------------------
def test_is_between_includes_both_bounds() -> None:
    low, high = date(2020, 1, 1), date(2020, 12, 31)
    expect(low).is_between(low, high)
    expect(high).is_between(low, high)
    expect(date(2020, 6, 1)).is_between(low, high)


def test_is_strictly_between_excludes_them() -> None:
    low, high = date(2020, 1, 1), date(2020, 12, 31)
    expect(date(2020, 6, 1)).is_strictly_between(low, high)
    with pytest.raises(AssertionFailure):
        expect(low).is_strictly_between(low, high)
    with pytest.raises(AssertionFailure):
        expect(high).is_strictly_between(low, high)


def test_is_not_between_is_the_exact_complement() -> None:
    low, high = date(2020, 1, 1), date(2020, 12, 31)
    expect(date(2019, 12, 31)).is_not_between(low, high)
    expect(date(2021, 1, 1)).is_not_between(low, high)
    with pytest.raises(AssertionFailure):
        expect(low).is_not_between(low, high)


def test_the_range_failures_name_both_bounds() -> None:
    hired_on = date(2020, 5, 4)
    assert _message(lambda: expect(hired_on).is_between(date(2021, 1, 1), date(2021, 12, 31))) == (
        "Expected hired_on to be between 2021-01-01 and 2021-12-31 inclusive, but was 2020-05-04."
    )
    assert _message(
        lambda: expect(hired_on).is_not_between(date(2020, 1, 1), date(2020, 12, 31))
    ) == (
        "Expected hired_on not to be between 2020-01-01 and 2020-12-31 inclusive,"
        " but was 2020-05-04."
    )
    assert _message(
        lambda: expect(hired_on).is_strictly_between(date(2020, 6, 1), date(2020, 12, 31))
    ) == ("Expected hired_on to be strictly between 2020-06-01 and 2020-12-31, but was 2020-05-04.")


def test_a_time_range_works_the_same() -> None:
    expect(time(12, 30)).is_between(time(9, 0), time(17, 0))
    expect(time(3, 0)).is_not_between(time(9, 0), time(17, 0))
    expect(time(12, 30)).is_strictly_between(time(9, 0), time(17, 0))


def test_an_inverted_range_is_a_caller_bug() -> None:
    """A range nothing could satisfy is a bug in the test, not a finding."""
    with pytest.raises(ValueError, match="range is inverted") as caught:
        expect(date(2020, 5, 4)).is_between(date(2021, 1, 1), date(2020, 1, 1))
    assert not isinstance(caught.value, AssertionFailure)
    assert str(caught.value) == "range is inverted: low 2021-01-01 exceeds high 2020-01-01"


def test_an_empty_exclusive_range_is_a_caller_bug() -> None:
    bound = datetime(2020, 1, 1)
    with pytest.raises(ValueError, match="exclusive range is empty"):
        expect(datetime(2020, 6, 1)).is_strictly_between(bound, bound)
    # ... and the same two bounds are a legal *inclusive* range of one moment.
    expect(bound).is_between(bound, bound)


def test_the_range_guard_runs_before_the_subject_is_looked_at() -> None:
    """A subject that would fail anyway must not hide the bug in the bounds."""
    with pytest.raises(ValueError, match="range is inverted"):
        expect(date(1999, 1, 1)).is_between(date(2021, 1, 1), date(2020, 1, 1))


# ---------------------------------------------------------------------------
# Calendar components
# ---------------------------------------------------------------------------
def test_the_date_components() -> None:
    subject = expect(date(2020, 2, 29))
    assert subject.has_year(2020) is subject
    assert subject.has_month(2) is subject
    assert subject.has_day(29) is subject


def test_a_component_failure_names_the_value_and_shows_the_whole_date() -> None:
    hired_on = date(2020, 5, 4)
    assert _message(lambda: expect(hired_on).has_year(2021)) == (
        "Expected hired_on to have year 2021, but had 2020 (2020-05-04)."
    )
    assert _message(lambda: expect(hired_on).has_month(6)) == (
        "Expected hired_on to have month 6, but had 5 (2020-05-04)."
    )
    assert _message(lambda: expect(hired_on).has_day(5)) == (
        "Expected hired_on to have day 5, but had 4 (2020-05-04)."
    )


def test_a_day_the_month_does_not_have_merely_fails() -> None:
    """Day 31 of a February is a possible claim about a date. It is just wrong."""
    with pytest.raises(AssertionFailure):
        expect(date(2021, 2, 28)).has_day(31)


#: Components no calendar has room for, with the assertion each belongs to.
_IMPOSSIBLE: list[tuple[str, Callable[[], object], str]] = [
    ("has_year(0)", lambda: expect(date(2020, 1, 1)).has_year(0), "year 0"),
    ("has_year(10000)", lambda: expect(date(2020, 1, 1)).has_year(10000), "year 10000"),
    ("has_month(13)", lambda: expect(date(2020, 1, 1)).has_month(13), "month 13"),
    ("has_month(0)", lambda: expect(date(2020, 1, 1)).has_month(0), "month 0"),
    ("has_day(0)", lambda: expect(date(2020, 1, 1)).has_day(0), "day of the month 0"),
    ("has_day(32)", lambda: expect(date(2020, 1, 1)).has_day(32), "day of the month 32"),
    ("has_hour(24)", lambda: expect(datetime(2020, 1, 1)).has_hour(24), "hour 24"),
    ("has_minute(60)", lambda: expect(datetime(2020, 1, 1)).has_minute(60), "minute 60"),
    ("has_second(60)", lambda: expect(datetime(2020, 1, 1)).has_second(60), "second 60"),
    (
        "has_microsecond(1000000)",
        lambda: expect(datetime(2020, 1, 1)).has_microsecond(1000000),
        "microsecond 1000000",
    ),
    ("time.has_hour(-1)", lambda: expect(time(0, 0)).has_hour(-1), "hour -1"),
]


@pytest.mark.parametrize(
    ("label", "call", "fragment"), _IMPOSSIBLE, ids=[label for label, _, _ in _IMPOSSIBLE]
)
def test_an_impossible_component_is_a_caller_bug(
    label: str, call: Callable[[], object], fragment: str
) -> None:
    """``ValueError``, not a failure: no subject could ever disprove the claim.

    ``has_month(13)`` is the same kind of mistake as an inverted range -- it
    describes nothing the calendar has room for -- so it is raised where it was
    written rather than reported as a finding about the value.
    """
    with pytest.raises(ValueError, match="there is no") as caught:
        call()
    assert not isinstance(caught.value, AssertionFailure), label
    assert fragment in str(caught.value)


def test_the_second_bound_says_datetime_has_no_leap_seconds() -> None:
    """23:59:60 exists in UTC and not in ``datetime``, so 60 is out of range."""
    with pytest.raises(ValueError, match="second 60: it must be between 0 and 59"):
        expect(datetime(2016, 12, 31, 23, 59, 59)).has_second(60)


def test_the_clock_components() -> None:
    subject = expect(datetime(2020, 1, 1, 23, 59, 58, 123456))
    assert subject.has_hour(23) is subject
    assert subject.has_minute(59) is subject
    assert subject.has_second(58) is subject
    assert subject.has_microsecond(123456) is subject


def test_a_clock_component_failure_shows_the_whole_moment() -> None:
    """All four failure messages, because a branch no test renders is not covered.

    An assertion exercised only where it passes never builds its message, so
    ``has_minute`` and ``has_second`` could be neutered to ``return self`` and a
    suite that never watched them fail would stay green.
    """
    started_at = datetime(2020, 1, 1, 9, 30, 15, 500000)
    assert _message(lambda: expect(started_at).has_hour(10)) == (
        "Expected started_at to have hour 10, but had 9 (2020-01-01T09:30:15.500000)."
    )
    assert _message(lambda: expect(started_at).has_minute(0)) == (
        "Expected started_at to have minute 0, but had 30 (2020-01-01T09:30:15.500000)."
    )
    assert _message(lambda: expect(started_at).has_second(0)) == (
        "Expected started_at to have second 0, but had 15 (2020-01-01T09:30:15.500000)."
    )
    assert _message(lambda: expect(started_at).has_microsecond(0)) == (
        "Expected started_at to have microsecond 0, but had 500000 (2020-01-01T09:30:15.500000)."
    )


def test_the_clock_components_are_on_a_time_too() -> None:
    lunch = expect(time(12, 30, 5, 7))
    assert lunch.has_hour(12) is lunch
    assert lunch.has_minute(30) is lunch
    assert lunch.has_second(5) is lunch
    assert lunch.has_microsecond(7) is lunch


# ---------------------------------------------------------------------------
# Weekday, weekend, and the day names
# ---------------------------------------------------------------------------
def test_the_week_splits_where_the_calendar_says() -> None:
    monday = date(2020, 5, 4)
    friday = date(2020, 5, 8)
    saturday = date(2020, 5, 9)
    sunday = date(2020, 5, 10)
    expect(monday).is_weekday()
    expect(friday).is_weekday()
    expect(saturday).is_weekend()
    expect(sunday).is_weekend()


def test_a_weekday_failure_names_the_day() -> None:
    """The day name is the entire content of the failure; a bare date is not."""
    shipped_on = date(2020, 5, 9)
    assert _message(lambda: expect(shipped_on).is_weekday()) == (
        "Expected shipped_on to fall on a weekday, but 2020-05-09 is a Saturday."
    )
    hired_on = date(2020, 5, 4)
    assert _message(lambda: expect(hired_on).is_weekend()) == (
        "Expected hired_on to fall on a weekend, but 2020-05-04 is a Monday."
    )


def test_every_day_name_is_the_right_one() -> None:
    """A hand-written table drifts by one, silently, and only once."""
    names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    # 2020-05-04 was a Monday.
    for offset, name in enumerate(names):
        day = date(2020, 5, 4) + timedelta(days=offset)
        assertion = expect(day).is_weekend if offset < 5 else expect(day).is_weekday
        assert name in _message(assertion)


def test_a_datetime_has_the_weekday_assertions_too() -> None:
    expect(datetime(2020, 5, 9, 12, 0)).is_weekend()
    expect(datetime(2020, 5, 4, 12, 0)).is_weekday()


# ---------------------------------------------------------------------------
# Today, the past, the future
# ---------------------------------------------------------------------------
def test_is_today_on_a_date() -> None:
    today = date.today()
    expect(today).is_today()
    with pytest.raises(AssertionFailure):
        expect(today - timedelta(days=1)).is_today()


def test_is_today_on_a_datetime_compares_the_calendar_day_not_the_moment() -> None:
    """A datetime is never equal to a date, so equality would be unusable here.

    Without the calendar-day comparison the assertion could only pass in the
    microsecond the subject was created, which is a test nobody can write.
    """
    expect(datetime.now()).is_today()
    expect(datetime.now().replace(hour=0, minute=0, second=0)).is_today()
    expect(datetime.now().replace(hour=23, minute=59, second=59)).is_today()


def test_is_today_on_an_aware_datetime_means_today_where_the_subject_is() -> None:
    """The only reading that does not compare one wall clock against another."""
    expect(datetime.now(TOKYO)).is_today()
    expect(datetime.now(NEW_YORK)).is_today()
    expect(datetime.now(UTC)).is_today()


def test_an_is_today_failure_says_what_today_is() -> None:
    message = _message(lambda: expect(date(2020, 5, 4)).is_today())
    assert message.startswith("Expected date(2020, 5, 4) to be today, but was 2020-05-04")
    assert "and today is " + date.today().isoformat() in message


def test_the_past_and_the_future() -> None:
    expect(date(1999, 1, 1)).is_in_the_past()
    expect(date(2999, 1, 1)).is_in_the_future()
    expect(datetime(1999, 1, 1)).is_in_the_past()
    expect(datetime(2999, 1, 1)).is_in_the_future()


def test_today_is_neither_past_nor_future_for_a_date_subject() -> None:
    """A ``date`` has no time of day, so today can only be compared by day."""
    today = date.today()

    past = _message(lambda: expect(today).is_in_the_past())
    future = _message(lambda: expect(today).is_in_the_future())

    both_moments = " but was " + today.isoformat() + " and now is " + today.isoformat() + "."
    assert past == "Expected today to be in the past," + both_moments
    assert future == "Expected today to be in the future," + both_moments


def test_the_past_and_future_on_an_aware_subject_do_not_crash() -> None:
    """The edge that would reintroduce the naive/aware crash inside the assertion.

    A naive "now" against an aware subject raises ``TypeError``. "Now" is
    therefore built in the subject's own shape and timezone.
    """
    expect(datetime(1999, 1, 1, tzinfo=UTC)).is_in_the_past()
    expect(datetime(2999, 1, 1, tzinfo=PARIS)).is_in_the_future()
    expect(datetime(1999, 1, 1, tzinfo=timezone(timedelta(hours=-11)))).is_in_the_past()


def test_the_past_and_future_on_a_tzinfo_that_declines_to_answer() -> None:
    """A ``tzinfo`` whose ``utcoffset`` is ``None`` is naive, so "now" must be too."""
    subject = datetime(1999, 1, 1, tzinfo=Blank())
    expect(subject).is_in_the_past()
    expect(datetime(2999, 1, 1, tzinfo=Blank())).is_in_the_future()


def test_the_calendar_boundaries_are_reachable() -> None:
    """``date.min``, ``date.max`` and ``datetime.max`` all have to answer."""
    expect(date.min).is_in_the_past().and_.is_before(date.max)
    expect(date.max).is_in_the_future().and_.is_after(date.min)
    expect(datetime.max).is_in_the_future()
    expect(datetime.min).is_in_the_past()
    expect(date.min).has_year(1).and_.has_month(1).and_.has_day(1)
    expect(date.max).has_year(9999).and_.has_month(12).and_.has_day(31)


def test_a_past_failure_reports_both_moments() -> None:
    message = _message(lambda: expect(date(2999, 1, 1)).is_in_the_past())
    assert message.startswith("Expected date(2999, 1, 1) to be in the past, but was 2999-01-01")
    assert " and now is " in message


def test_a_future_failure_reports_both_moments() -> None:
    """The mirror of the past failure: "now" is what the reader is missing."""
    message = _message(lambda: expect(date(1999, 1, 1)).is_in_the_future())

    assert message.startswith("Expected date(1999, 1, 1) to be in the future, but was 1999-01-01")
    assert " and now is " + date.today().isoformat() in message


# ---------------------------------------------------------------------------
# The same calendar day
# ---------------------------------------------------------------------------
def test_is_same_date_as_ignores_the_time_of_day() -> None:
    subject = expect(datetime(2020, 1, 1, 0, 0))
    assert subject.is_same_date_as(datetime(2020, 1, 1, 23, 59, 59, 999999)) is subject
    with pytest.raises(AssertionFailure):
        expect(datetime(2020, 1, 1, 23, 59)).is_same_date_as(datetime(2020, 1, 2, 0, 1))


def test_is_same_date_as_across_a_leap_day() -> None:
    expect(datetime(2020, 2, 29, 8, 0)).is_same_date_as(datetime(2020, 2, 29, 20, 0))
    with pytest.raises(AssertionFailure):
        expect(datetime(2020, 2, 29, 23, 0)).is_same_date_as(datetime(2020, 3, 1, 1, 0))


def test_is_same_date_as_across_a_dst_transition() -> None:
    """Spring forward: 2020-03-08 lost an hour in New York and is still one day."""
    before = datetime(2020, 3, 8, 1, 59, tzinfo=NEW_YORK)
    after = datetime(2020, 3, 8, 3, 1, tzinfo=NEW_YORK)
    expect(before).is_same_date_as(after)
    # And the pair really is only 62 minutes apart, not 122.
    expect(after - before).is_equal_to(timedelta(minutes=62))


def test_is_same_date_as_compares_wall_clocks_not_instants() -> None:
    """Two names for one instant can be two different dates. That is calendars."""
    utc_moment = datetime(2020, 1, 1, 23, 0, tzinfo=UTC)
    tokyo_moment = utc_moment.astimezone(TOKYO)
    expect(tokyo_moment).is_equal_to(utc_moment)  # the same instant
    assert _message(lambda: expect(utc_moment).is_same_date_as(tokyo_moment)) == (
        "Expected utc_moment to fall on the same date as 2020-01-02T08:00:00+09:00,"
        " but was 2020-01-01T23:00:00+00:00."
    )


# ---------------------------------------------------------------------------
# Closeness
# ---------------------------------------------------------------------------
def test_is_close_to_takes_the_boundary() -> None:
    subject = expect(datetime(2020, 1, 1, 12, 0))
    assert subject.is_close_to(datetime(2020, 1, 1, 12, 5), within=timedelta(minutes=5)) is subject


def test_is_close_to_is_symmetric_in_both_senses() -> None:
    """``within`` is an absolute distance: neither the order nor the sign matters."""
    early = datetime(2020, 1, 1, 12, 0)
    late = datetime(2020, 1, 1, 12, 3)
    expect(early).is_close_to(late, within=timedelta(minutes=5))
    expect(late).is_close_to(early, within=timedelta(minutes=5))
    with pytest.raises(AssertionFailure):
        expect(early).is_close_to(late, within=timedelta(minutes=1))
    with pytest.raises(AssertionFailure):
        expect(late).is_close_to(early, within=timedelta(minutes=1))


def test_is_not_close_to_is_the_exact_complement() -> None:
    early = datetime(2020, 1, 1, 12, 0)
    late = datetime(2020, 1, 1, 12, 3)
    expect(early).is_not_close_to(late, within=timedelta(minutes=1))
    with pytest.raises(AssertionFailure):
        expect(early).is_not_close_to(late, within=timedelta(minutes=5))


def test_a_closeness_failure_reports_the_distance() -> None:
    started_at = datetime(2020, 1, 1, 12, 0)
    assert _message(
        lambda: expect(started_at).is_close_to(
            datetime(2020, 1, 1, 12, 3), within=timedelta(minutes=1)
        )
    ) == (
        "Expected started_at to be within 0:01:00 of 2020-01-01T12:03:00,"
        " but was 2020-01-01T12:00:00, 0:03:00 away."
    )
    assert _message(
        lambda: expect(started_at).is_not_close_to(
            datetime(2020, 1, 1, 12, 3), within=timedelta(minutes=5)
        )
    ) == (
        "Expected started_at not to be within 0:05:00 of 2020-01-01T12:03:00,"
        " but was 2020-01-01T12:00:00, only 0:03:00 away."
    )


def test_a_zero_tolerance_means_exact_equality() -> None:
    """A range of one point is satisfiable, so it is kept rather than refused."""
    moment = datetime(2020, 1, 1, 12, 0)
    expect(moment).is_close_to(moment, within=timedelta(0))
    with pytest.raises(AssertionFailure):
        expect(moment).is_close_to(moment + timedelta(microseconds=1), within=timedelta(0))


def test_the_tolerance_boundary_falls_inside_the_range() -> None:
    """A subject exactly ``within`` away is close, and therefore not *not* close.

    This is the only input that can tell the pair apart from a pair spelled with
    each other's operator. ``is_close_to`` includes both ends of
    ``other - within .. other + within``, so a value sitting on an end passes it
    and has to fail its complement; everywhere else in this file the two are
    tested well clear of the line they draw.
    """
    moment = datetime(2020, 1, 1, 12, 0)
    tolerance = timedelta(minutes=5)
    for other in (moment + tolerance, moment - tolerance):
        expect(moment).is_close_to(other, within=tolerance)
        with pytest.raises(AssertionFailure):
            expect(moment).is_not_close_to(other, within=tolerance)
    # One microsecond further out and both verdicts swap.
    beyond = moment + tolerance + timedelta(microseconds=1)
    expect(moment).is_not_close_to(beyond, within=tolerance)
    with pytest.raises(AssertionFailure):
        expect(moment).is_close_to(beyond, within=tolerance)


def test_a_negative_tolerance_is_a_caller_bug() -> None:
    """A range no pair of values could satisfy -- the inverted-range rule again."""
    moment = datetime(2020, 1, 1, 12, 0)
    with pytest.raises(ValueError, match="within must not be negative") as caught:
        expect(moment).is_close_to(moment, within=timedelta(microseconds=-1))
    assert not isinstance(caught.value, AssertionFailure)
    with pytest.raises(ValueError, match="within must not be negative"):
        expect(moment).is_not_close_to(moment, within=timedelta(days=-1))
    with pytest.raises(ValueError, match="within must not be negative"):
        expect(timedelta(0)).is_close_to(timedelta(0), within=timedelta(seconds=-1))


def test_the_tolerance_guard_reads_the_sign_of_a_normalised_timedelta() -> None:
    """``timedelta(microseconds=-1)`` normalises to ``days=-1``; only ``days`` is signed."""
    assert timedelta(microseconds=-1).days == -1
    assert timedelta(microseconds=-1).seconds > 0
    with pytest.raises(ValueError, match="must not be negative"):
        expect(datetime(2020, 1, 1)).is_close_to(datetime(2020, 1, 1), within=timedelta(hours=-1))


# ---------------------------------------------------------------------------
# Timezones
# ---------------------------------------------------------------------------
def test_is_aware_and_is_naive() -> None:
    aware = expect(datetime(2020, 1, 1, tzinfo=UTC))
    assert aware.is_aware() is aware
    naive = expect(datetime(2020, 1, 1))
    assert naive.is_naive() is naive
    with pytest.raises(AssertionFailure):
        expect(datetime(2020, 1, 1)).is_aware()
    with pytest.raises(AssertionFailure):
        expect(datetime(2020, 1, 1, tzinfo=UTC)).is_naive()


def test_a_tzinfo_whose_offset_is_none_is_naive_despite_being_set() -> None:
    """``datetime`` says so, and an assertion that disagreed would be lying."""
    subject = datetime(2020, 1, 1, tzinfo=Blank())
    assert subject.tzinfo is not None
    expect(subject).is_naive()
    with pytest.raises(AssertionFailure):
        expect(subject).is_aware()


def test_the_awareness_failures() -> None:
    started_at = datetime(2020, 1, 1, 9, 0)
    assert _message(lambda: expect(started_at).is_aware()) == (
        "Expected started_at to be timezone-aware, but 2020-01-01T09:00:00 is naive."
    )
    stamped = datetime(2020, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=2)))
    assert _message(lambda: expect(stamped).is_naive()) == (
        "Expected stamped to be naive, but 2020-01-01T09:00:00+02:00"
        " is timezone-aware (offset 2:00:00)."
    )


def test_a_time_is_aware_or_naive_by_the_same_rule() -> None:
    expect(time(12, 0, tzinfo=UTC)).is_aware()
    expect(time(12, 0)).is_naive()
    expect(time(12, 0, tzinfo=Blank())).is_naive()


#: Four objects that all describe UTC, of which three are genuinely distinct --
#: ``timezone(timedelta(0))`` is interned and really *is* ``timezone.utc``.
#: ``is_utc`` decides by offset, because deciding by identity would be asserting
#: which library built the value rather than what the value means.
_UTC_SPELLINGS: list[tuple[str, tzinfo]] = [
    ("timezone.utc", UTC),
    ("zoneinfo UTC", ZoneInfo("UTC")),
    ("fixed +00:00", timezone(timedelta(0))),
    ("named +00:00", timezone(timedelta(0), "Zulu")),
]


@pytest.mark.parametrize(("label", "zone"), _UTC_SPELLINGS, ids=[n for n, _ in _UTC_SPELLINGS])
def test_every_spelling_of_utc_is_utc(label: str, zone: tzinfo) -> None:
    subject = expect(datetime(2020, 1, 1, tzinfo=zone))
    assert subject.is_utc() is subject, label


def test_the_spellings_really_are_different_objects() -> None:
    """Otherwise the parametrised test above proves nothing.

    Three of the four are distinct; the fourth is the trap. CPython interns the
    zero offset, so ``timezone(timedelta(0)) is timezone.utc`` -- which is
    exactly why a test that only tried that spelling would look like it had
    proved something about offsets and have proved something about identity.
    """
    zones = [zone for _, zone in _UTC_SPELLINGS]
    assert len({id(zone) for zone in zones}) == 3
    assert timezone(timedelta(0)) is UTC
    assert ZoneInfo("UTC") != UTC
    # And a second trap, in the opposite direction: `timezone.__eq__` compares
    # offsets and ignores the name, so a *named* zero offset is `timezone.utc`
    # by equality while being a different object. `has_timezone` inherits that.
    assert timezone(timedelta(0), "Zulu") is not UTC
    assert timezone(timedelta(0), "Zulu") == UTC


def test_has_timezone_inherits_the_stdlibs_own_notion_of_equal_timezones() -> None:
    """``timezone`` compares by offset and ignores its name; this does not second-guess it."""
    expect(datetime(2020, 1, 1, tzinfo=timezone(timedelta(0), "Zulu"))).has_timezone(UTC)
    with pytest.raises(AssertionFailure):
        expect(datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))).has_timezone(UTC)


def test_a_zoneinfo_that_is_at_zero_offset_today_is_not_utc() -> None:
    """London is +00:00 in January and +01:00 in July; the offset is asked *of the value*."""
    expect(datetime(2020, 1, 1, tzinfo=ZoneInfo("Europe/London"))).is_utc()
    with pytest.raises(AssertionFailure):
        expect(datetime(2020, 7, 1, tzinfo=ZoneInfo("Europe/London"))).is_utc()


def test_the_utc_failures_say_which_kind_of_not_utc() -> None:
    naive = datetime(2020, 1, 1, 9, 0)
    assert _message(lambda: expect(naive).is_utc()) == (
        "Expected naive to be UTC, but 2020-01-01T09:00:00 is naive."
    )
    elsewhere = datetime(2020, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert _message(lambda: expect(elsewhere).is_utc()) == (
        "Expected elsewhere to be UTC, but 2020-01-01T09:00:00-05:00 is offset -5:00:00 from UTC."
    )


def test_has_timezone_is_the_identity_question() -> None:
    subject = expect(datetime(2020, 1, 1, tzinfo=PARIS))
    assert subject.has_timezone(PARIS) is subject
    with pytest.raises(AssertionFailure):
        expect(datetime(2020, 1, 1, tzinfo=PARIS)).has_timezone(UTC)


def test_has_timezone_says_so_when_only_the_objects_differ() -> None:
    """The confusing failure: two halves that print the same offset."""
    stamped = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
    message = _message(lambda: expect(stamped).has_timezone(UTC))
    assert message == (
        "Expected stamped to have timezone datetime.timezone.utc,"
        " but 2020-01-01T00:00:00+00:00 has zoneinfo.ZoneInfo(key='UTC')"
        " (the two agree on the offset and are still not the same timezone)."
    )


def test_has_timezone_on_a_naive_subject_says_there_is_none() -> None:
    started_at = datetime(2020, 1, 1)
    assert _message(lambda: expect(started_at).has_timezone(UTC)) == (
        "Expected started_at to have timezone datetime.timezone.utc,"
        " but 2020-01-01T00:00:00 has no timezone at all."
    )


# ---------------------------------------------------------------------------
# The difference chain: is_within(delta).before(other) / .after(other)
# ---------------------------------------------------------------------------
def test_the_difference_chain_holds_inside_the_delta() -> None:
    deadline = datetime(2020, 1, 1, 12, 0)
    subject = expect(datetime(2020, 1, 1, 11, 57))
    assert subject.is_within(timedelta(minutes=5)).before(deadline) is subject
    later = expect(datetime(2020, 1, 1, 12, 3))
    assert later.is_within(timedelta(minutes=5)).after(deadline) is later


def test_the_difference_chain_is_inclusive_at_both_ends() -> None:
    deadline = datetime(2020, 1, 1, 12, 0)
    expect(deadline - timedelta(minutes=5)).is_within(timedelta(minutes=5)).before(deadline)
    expect(deadline).is_within(timedelta(minutes=5)).before(deadline)
    expect(deadline).is_within(timedelta(minutes=5)).after(deadline)
    expect(deadline + timedelta(minutes=5)).is_within(timedelta(minutes=5)).after(deadline)


def test_the_direction_is_part_of_the_claim() -> None:
    """A subject one second on the wrong side fails, however close it is."""
    deadline = datetime(2020, 1, 1, 12, 0)
    with pytest.raises(AssertionFailure):
        expect(deadline + timedelta(seconds=1)).is_within(timedelta(hours=1)).before(deadline)
    with pytest.raises(AssertionFailure):
        expect(deadline - timedelta(seconds=1)).is_within(timedelta(hours=1)).after(deadline)


def test_the_difference_chain_failures_say_which_side_and_how_far() -> None:
    deadline = datetime(2020, 1, 1, 12, 0)
    submitted_at = datetime(2020, 1, 1, 11, 40)
    assert _message(
        lambda: expect(submitted_at).is_within(timedelta(minutes=5)).before(deadline)
    ) == (
        "Expected submitted_at to be within 0:05:00 before 2020-01-01T12:00:00,"
        " but was 2020-01-01T11:40:00, 0:20:00 before it."
    )
    assert _message(
        lambda: expect(submitted_at).is_within(timedelta(minutes=5)).after(deadline)
    ) == (
        "Expected submitted_at to be within 0:05:00 after 2020-01-01T12:00:00,"
        " but was 2020-01-01T11:40:00, 0:20:00 before it."
    )


def test_the_difference_chain_takes_because() -> None:
    deadline = datetime(2020, 1, 1, 12, 0)
    submitted_at = datetime(2020, 1, 1, 13, 0)
    assert _message(
        lambda: (
            expect(submitted_at)
            .is_within(timedelta(minutes=5))
            .before(deadline, because="the form closes on the hour")
        )
    ) == (
        "Expected submitted_at to be within 0:05:00 before 2020-01-01T12:00:00,"
        " but was 2020-01-01T13:00:00, 1:00:00 after it"
        " because the form closes on the hour."
    )


def test_the_chain_keeps_flowing_after_the_continuation() -> None:
    deadline = datetime(2020, 1, 1, 12, 0)
    subject = expect(datetime(2020, 1, 1, 11, 57))
    assert subject.is_within(timedelta(minutes=5)).before(deadline).and_.is_naive() is subject


def test_a_negative_delta_is_a_caller_bug() -> None:
    with pytest.raises(ValueError, match="is_within must not be negative") as caught:
        expect(datetime(2020, 1, 1)).is_within(timedelta(minutes=-5))
    assert not isinstance(caught.value, AssertionFailure)


def test_a_zero_delta_means_exactly_that_moment() -> None:
    deadline = datetime(2020, 1, 1, 12, 0)
    expect(deadline).is_within(timedelta(0)).before(deadline)
    with pytest.raises(AssertionFailure):
        expect(deadline - timedelta(microseconds=1)).is_within(timedelta(0)).before(deadline)


def test_the_bound_that_falls_off_the_calendar_does_not_become_an_overflow() -> None:
    """``datetime.max + delta`` does not exist, and nothing can be past it anyway."""
    expect(datetime.max).is_within(timedelta(days=1)).after(datetime.max)
    expect(datetime.min).is_within(timedelta(days=1)).before(datetime.min)
    with pytest.raises(AssertionFailure):
        expect(datetime.min).is_within(timedelta(days=1)).after(datetime.max)


def test_an_unfinished_chain_says_it_asserted_nothing() -> None:
    """``is_within(...)`` alone is a test that asserts nothing.

    It cannot be raised on at the call, because at that moment it is still a good
    half of a chain -- so it is reported the way CPython reports the identical
    mistake with an un-awaited coroutine: a ``RuntimeWarning`` from the finaliser.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        expect(datetime(2020, 1, 1)).is_within(timedelta(minutes=5))
        gc.collect()
    assert [type(warning.message) for warning in caught] == [RuntimeWarning]
    assert str(caught[0].message) == (
        "is_within(...) asserted nothing: continue it with .before(...) or .after(...)."
        " The delta was 0:05:00"
    )


def test_a_finished_chain_warns_about_nothing() -> None:
    """A guard that fired on the good path would be worse than no guard."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        expect(datetime(2020, 1, 1)).is_within(timedelta(minutes=5)).before(datetime(2020, 1, 1))
        gc.collect()
    assert [str(warning.message) for warning in caught] == []


def test_a_chain_finished_by_a_failing_continuation_warns_about_nothing() -> None:
    """The continuation ran. That it reported a failure is a different matter."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(AssertionFailure):
            expect(datetime(2020, 1, 2)).is_within(timedelta(minutes=5)).before(
                datetime(2020, 1, 1)
            )
        gc.collect()
    assert [str(warning.message) for warning in caught] == []


# ---------------------------------------------------------------------------
# Time of day
# ---------------------------------------------------------------------------
def test_is_midnight() -> None:
    subject = expect(time(0, 0))
    assert subject.is_midnight() is subject
    expect(time(0, 0, 0, 0)).is_midnight()
    for not_midnight in (time(0, 0, 0, 1), time(0, 0, 1), time(0, 1), time(1, 0)):
        with pytest.raises(AssertionFailure):
            expect(not_midnight).is_midnight()


def test_an_aware_midnight_is_midnight() -> None:
    """It is midnight *somewhere*, which is what a ``time`` with a timezone means."""
    expect(time(0, 0, tzinfo=TOKYO)).is_midnight()


def test_a_midnight_failure_shows_the_time() -> None:
    opens_at = time(9, 30)
    assert _message(lambda: expect(opens_at).is_midnight()) == (
        "Expected opens_at to be midnight, but was 09:30:00."
    )


# ---------------------------------------------------------------------------
# Durations
# ---------------------------------------------------------------------------
def test_the_duration_comparisons() -> None:
    subject = expect(timedelta(minutes=3))
    assert subject.is_longer_than(timedelta(minutes=1)) is subject
    assert subject.is_shorter_than(timedelta(minutes=5)) is subject
    assert subject.is_at_least(timedelta(minutes=3)) is subject
    assert subject.is_at_most(timedelta(minutes=3)) is subject


def test_the_duration_comparison_failures() -> None:
    elapsed = timedelta(seconds=90)
    assert _message(lambda: expect(elapsed).is_longer_than(timedelta(minutes=5))) == (
        "Expected elapsed to be longer than 0:05:00, but was 0:01:30."
    )
    assert _message(lambda: expect(elapsed).is_shorter_than(timedelta(seconds=1))) == (
        "Expected elapsed to be shorter than 0:00:01, but was 0:01:30."
    )
    assert _message(lambda: expect(elapsed).is_at_least(timedelta(minutes=5))) == (
        "Expected elapsed to be at least 0:05:00, but was 0:01:30."
    )
    assert _message(lambda: expect(elapsed).is_at_most(timedelta(seconds=1))) == (
        "Expected elapsed to be at most 0:00:01, but was 0:01:30."
    )


def test_a_duration_is_signed_so_shorter_means_shorter_not_smaller() -> None:
    """``timedelta(days=-2)`` really is shorter than nothing at all."""
    expect(timedelta(days=-2)).is_shorter_than(timedelta(0))
    expect(timedelta(days=-2)).is_shorter_than(timedelta(days=-1))
    expect(timedelta(days=-1)).is_longer_than(timedelta(days=-2))
    with pytest.raises(AssertionFailure):
        expect(timedelta(days=-2)).is_longer_than(timedelta(days=-1))


def test_the_strict_duration_comparisons_refuse_an_equal_operand() -> None:
    """``is_longer_than`` is strict exactly where ``is_at_least`` is not.

    Equality is the single input that separates the two pairs, so it is the only
    one that can catch either of them being spelled with the other's operator.
    """
    same = timedelta(minutes=3)
    subject = expect(same)
    assert subject.is_at_least(same) is subject
    assert subject.is_at_most(same) is subject
    with pytest.raises(AssertionFailure):
        expect(same).is_longer_than(same)
    with pytest.raises(AssertionFailure):
        expect(same).is_shorter_than(same)


def test_the_duration_ranges() -> None:
    subject = expect(timedelta(minutes=3))
    assert subject.is_between(timedelta(minutes=1), timedelta(minutes=5)) is subject
    assert subject.is_not_between(timedelta(minutes=10), timedelta(minutes=20)) is subject
    expect(timedelta(minutes=1)).is_between(timedelta(minutes=1), timedelta(minutes=5))
    with pytest.raises(ValueError, match="range is inverted"):
        expect(timedelta(minutes=3)).is_between(timedelta(minutes=5), timedelta(minutes=1))


def test_the_duration_range_failures() -> None:
    elapsed = timedelta(seconds=90)
    assert _message(
        lambda: expect(elapsed).is_between(timedelta(minutes=5), timedelta(minutes=10))
    ) == ("Expected elapsed to be between 0:05:00 and 0:10:00 inclusive, but was 0:01:30.")
    assert _message(
        lambda: expect(elapsed).is_not_between(timedelta(minutes=1), timedelta(minutes=10))
    ) == ("Expected elapsed not to be between 0:01:00 and 0:10:00 inclusive, but was 0:01:30.")


def test_the_sign_of_a_duration() -> None:
    expect(timedelta(seconds=1)).is_positive()
    expect(timedelta(microseconds=1)).is_positive()
    expect(timedelta(microseconds=-1)).is_negative()
    expect(timedelta(days=-1)).is_negative()
    expect(timedelta(0)).is_zero()
    expect(timedelta(seconds=1)).is_not_zero()
    expect(timedelta(seconds=-1)).is_not_zero()


def test_zero_is_neither_positive_nor_negative() -> None:
    with pytest.raises(AssertionFailure):
        expect(timedelta(0)).is_positive()
    with pytest.raises(AssertionFailure):
        expect(timedelta(0)).is_negative()
    with pytest.raises(AssertionFailure):
        expect(timedelta(0)).is_not_zero()


def test_the_smallest_representable_duration_still_has_a_sign() -> None:
    """One microsecond either way, where a coarser test would call both zero."""
    expect(timedelta(microseconds=1)).is_positive().and_.is_not_zero()
    expect(timedelta(microseconds=-1)).is_negative().and_.is_not_zero()


def test_the_sign_failures() -> None:
    drift = timedelta(seconds=-5)
    assert _message(lambda: expect(drift).is_positive()) == (
        "Expected drift to be a positive duration, but was -0:00:05."
    )
    elapsed = timedelta(seconds=5)
    assert _message(lambda: expect(elapsed).is_negative()) == (
        "Expected elapsed to be a negative duration, but was 0:00:05."
    )
    assert _message(lambda: expect(elapsed).is_zero()) == (
        "Expected elapsed to be zero, but was 0:00:05."
    )
    empty = timedelta(0)
    assert _message(lambda: expect(empty).is_not_zero()) == (
        "Expected empty not to be zero, but it was."
    )


def test_duration_closeness() -> None:
    subject = expect(timedelta(seconds=10))
    assert subject.is_close_to(timedelta(seconds=11), within=timedelta(seconds=1)) is subject
    assert subject.is_not_close_to(timedelta(seconds=20), within=timedelta(seconds=1)) is subject
    expect(timedelta(seconds=11)).is_close_to(timedelta(seconds=10), within=timedelta(seconds=1))


def test_duration_closeness_failures() -> None:
    elapsed = timedelta(seconds=10)
    assert _message(
        lambda: expect(elapsed).is_close_to(timedelta(seconds=20), within=timedelta(seconds=1))
    ) == ("Expected elapsed to be within 0:00:01 of 0:00:20, but was 0:00:10, 0:00:10 away.")
    assert _message(
        lambda: expect(elapsed).is_not_close_to(timedelta(seconds=10), within=timedelta(seconds=1))
    ) == (
        "Expected elapsed not to be within 0:00:01 of 0:00:10, but was 0:00:10, only 0:00:00 away."
    )


def test_the_duration_tolerance_boundary_falls_inside_the_range() -> None:
    """``TimeDeltaExpect``'s pair draws the line in the same place its ``datetime`` twin does."""
    elapsed = timedelta(seconds=10)
    tolerance = timedelta(seconds=1)
    for other in (timedelta(seconds=11), timedelta(seconds=9)):
        expect(elapsed).is_close_to(other, within=tolerance)
        with pytest.raises(AssertionFailure):
            expect(elapsed).is_not_close_to(other, within=tolerance)
    beyond = timedelta(seconds=11, microseconds=1)
    expect(elapsed).is_not_close_to(beyond, within=tolerance)
    with pytest.raises(AssertionFailure):
        expect(elapsed).is_close_to(beyond, within=tolerance)


def test_has_total_seconds() -> None:
    subject = expect(timedelta(seconds=90))
    assert subject.has_total_seconds(90.0) is subject
    expect(timedelta(milliseconds=1500)).has_total_seconds(1.5)
    expect(timedelta(0)).has_total_seconds(0.0)
    expect(timedelta(seconds=-1)).has_total_seconds(-1.0)


def test_has_total_seconds_is_exact() -> None:
    """A component that is nearly right is wrong; ``is_close_to`` is the other one."""
    elapsed = timedelta(microseconds=1)
    expect(elapsed).has_total_seconds(1e-06)
    with pytest.raises(AssertionFailure):
        expect(elapsed).has_total_seconds(0.0)
    assert _message(lambda: expect(elapsed).has_total_seconds(0.0)) == (
        "Expected elapsed to have total seconds 0.0, but had 1e-06 (0:00:00.000001)."
    )


# ---------------------------------------------------------------------------
# The two crashes
# ---------------------------------------------------------------------------
def test_a_naive_subject_against_an_aware_operand_names_both_sides() -> None:
    """The naive/aware crash. The stdlib says only "can't compare"; this says which is which."""
    started_at = datetime(2020, 1, 1, 9, 0)
    with pytest.raises(TypeError) as caught:
        expect(started_at).is_before(datetime(2020, 1, 1, 10, 0, tzinfo=UTC))
    assert str(caught.value) == (
        "can't compare a timezone-aware datetime with a naive one:"
        " 2020-01-01T09:00:00 is naive and 2020-01-01T10:00:00+00:00 is aware;"
        " give both a timezone, or neither"
    )


def test_the_naive_aware_crash_is_a_type_error_and_not_a_failure() -> None:
    """The decision: two values that cannot be compared produce no verdict."""
    with pytest.raises(TypeError) as caught:
        expect(datetime(2020, 1, 1, tzinfo=UTC)).is_after(datetime(2020, 1, 1))
    assert not isinstance(caught.value, AssertionFailure)
    assert "is aware and " in str(caught.value)
    assert "is naive" in str(caught.value)


def test_the_original_type_error_is_kept_as_the_cause() -> None:
    """A suite that already catches ``TypeError`` keeps working; only the message improves."""
    with pytest.raises(TypeError) as caught:
        expect(datetime(2020, 1, 1)).is_before(datetime(2020, 1, 1, tzinfo=UTC))
    cause = caught.value.__cause__
    assert isinstance(cause, TypeError)
    assert "offset-naive and offset-aware" in str(cause)


def test_the_crash_message_calls_a_tzinfo_that_declines_an_offset_naive() -> None:
    """A subject carrying ``Blank()`` is naive, and the message has to say so.

    ``datetime`` decides awareness by ``utcoffset()`` and never by whether
    ``tzinfo`` is set, and this is the one place that distinction shows up in
    prose. Reading the attribute instead would call both sides "aware", the
    mismatch would look like agreement, and the explanation would be dropped in
    favour of the bare stdlib message -- on the very value that most needs it.
    """
    blank = datetime(2020, 1, 1, 12, 0, tzinfo=Blank())
    assert blank.tzinfo is not None
    with pytest.raises(TypeError) as caught:
        expect(blank).is_before(datetime(2020, 1, 1, 13, 0, tzinfo=UTC))
    assert str(caught.value) == (
        "can't compare a timezone-aware datetime with a naive one:"
        " 2020-01-01T12:00:00 is naive and 2020-01-01T13:00:00+00:00 is aware;"
        " give both a timezone, or neither"
    )


#: Every comparison that can meet the naive/aware mix, and the call that does it.
_NAIVE_AWARE: list[tuple[str, Callable[[], object]]] = [
    ("is_before", lambda: expect(datetime(2020, 1, 1)).is_before(datetime(2020, 1, 2, tzinfo=UTC))),
    ("is_after", lambda: expect(datetime(2020, 1, 1)).is_after(datetime(2019, 1, 1, tzinfo=UTC))),
    (
        "is_on_or_before",
        lambda: expect(datetime(2020, 1, 1)).is_on_or_before(datetime(2020, 1, 2, tzinfo=UTC)),
    ),
    (
        "is_on_or_after",
        lambda: expect(datetime(2020, 1, 1)).is_on_or_after(datetime(2019, 1, 1, tzinfo=UTC)),
    ),
    (
        "is_between (subject)",
        lambda: expect(datetime(2020, 1, 1)).is_between(
            datetime(2019, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC)
        ),
    ),
    (
        "is_not_between (subject)",
        lambda: expect(datetime(2020, 1, 1)).is_not_between(
            datetime(2019, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC)
        ),
    ),
    (
        "is_strictly_between (subject)",
        lambda: expect(datetime(2020, 1, 1)).is_strictly_between(
            datetime(2019, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC)
        ),
    ),
    (
        "is_between (bounds disagree)",
        lambda: expect(datetime(2020, 1, 1)).is_between(
            datetime(2019, 1, 1), datetime(2021, 1, 1, tzinfo=UTC)
        ),
    ),
    (
        "is_close_to",
        lambda: expect(datetime(2020, 1, 1)).is_close_to(
            datetime(2020, 1, 1, tzinfo=UTC), within=timedelta(minutes=1)
        ),
    ),
    (
        "is_not_close_to",
        lambda: expect(datetime(2020, 1, 1)).is_not_close_to(
            datetime(2020, 1, 1, tzinfo=UTC), within=timedelta(minutes=1)
        ),
    ),
    (
        "is_within(...).before",
        lambda: (
            expect(datetime(2020, 1, 1))
            .is_within(timedelta(minutes=1))
            .before(datetime(2020, 1, 1, tzinfo=UTC))
        ),
    ),
    (
        "is_within(...).after",
        lambda: (
            expect(datetime(2020, 1, 1))
            .is_within(timedelta(minutes=1))
            .after(datetime(2020, 1, 1, tzinfo=UTC))
        ),
    ),
    ("time.is_before", lambda: expect(time(9, 0)).is_before(time(10, 0, tzinfo=UTC))),
    (
        "time.is_between",
        lambda: expect(time(9, 0)).is_between(time(8, 0, tzinfo=UTC), time(10, 0, tzinfo=UTC)),
    ),
]


@pytest.mark.parametrize(("label", "call"), _NAIVE_AWARE, ids=[label for label, _ in _NAIVE_AWARE])
def test_no_comparison_lets_the_bare_stdlib_crash_escape(
    label: str, call: Callable[[], object]
) -> None:
    """Every route into a comparison, because one unguarded route is the whole bug."""
    with pytest.raises(TypeError) as caught:
        call()
    message = str(caught.value)
    assert "offset-naive" not in message, label
    assert "is naive" in message, label
    assert "is aware" in message, label


def test_a_date_subject_against_a_datetime_operand_names_the_mismatch() -> None:
    """The date/datetime crash: no type checker can refuse this call, and the message says so."""
    hired_on = date(2020, 5, 4)
    with pytest.raises(TypeError) as caught:
        # No `type: ignore` here, and that is the finding: both checkers accept
        # this call, because a `datetime` really is a `date`.
        expect(hired_on).is_before(datetime(2021, 1, 1))
    assert str(caught.value) == (
        "can't compare a date with a datetime:"
        " 2020-05-04 is a date and 2021-01-01T00:00:00 is a datetime;"
        " datetime subclasses date, so no type checker can refuse the mix"
    )


def test_the_date_datetime_mismatch_really_is_invisible_to_the_type_system() -> None:
    """The reason the runtime half has to exist at all."""
    assert issubclass(datetime, date)
    assert isinstance(datetime(2020, 1, 1), date)


def test_a_range_whose_bounds_are_a_date_and_a_datetime() -> None:
    with pytest.raises(TypeError, match="can't compare a date with a datetime"):
        expect(date(2020, 5, 4)).is_between(date(2020, 1, 1), datetime(2021, 1, 1))


def test_bounds_that_disagree_with_each_other_are_caught_before_the_subject() -> None:
    """The range guard runs first, so the two bounds are reported against each other."""
    with pytest.raises(TypeError) as caught:
        expect(datetime(2020, 6, 1)).is_between(
            datetime(2020, 1, 1), datetime(2021, 1, 1, tzinfo=UTC)
        )
    assert str(caught.value) == (
        "can't compare a timezone-aware datetime with a naive one:"
        " 2020-01-01T00:00:00 is naive and 2021-01-01T00:00:00+00:00 is aware;"
        " give both a timezone, or neither"
    )


def test_a_range_names_the_bound_that_actually_refused() -> None:
    """One ``TypeError`` covers two comparisons; naming the wrong bound misdirects.

    ``low <= subject <= high`` short-circuits, so which bound raised depends on
    how far the chain got. The stdlib types make the second case unreachable
    through the public assertion -- two bounds that disagree with each other are
    rejected by the range guard above, and two that agree cannot then disagree
    with the same subject -- so the helper is asked directly rather than left
    untested on the strength of an argument.
    """
    naive = datetime(2020, 6, 1)
    assert _offending_bound(naive, date(2020, 1, 1), datetime(2021, 1, 1)) == date(2020, 1, 1)
    assert _offending_bound(
        naive, datetime(2020, 1, 1), datetime(2021, 1, 1, tzinfo=UTC)
    ) == datetime(2021, 1, 1, tzinfo=UTC)


def test_a_time_against_a_datetime_is_a_kind_mismatch_too() -> None:
    with pytest.raises(TypeError, match="can't compare a time with a datetime") as caught:
        expect(time(9, 0)).is_before(datetime(2020, 1, 1))  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    assert "datetime subclasses date" not in str(caught.value), "the Liskov note is for date only"


def test_a_type_error_this_module_cannot_explain_propagates_untouched() -> None:
    """A user's own ``__lt__`` saying no is not this module's to reinterpret."""

    class Picky(date):
        __slots__ = ()

        def __lt__(self, other: object, /) -> bool:
            raise TypeError("currencies do not mix")

    with pytest.raises(TypeError) as caught:
        expect(Picky(2020, 1, 1)).is_before(Picky(2021, 1, 1))
    assert str(caught.value) == "currencies do not mix"
    assert caught.value.__cause__ is None


def test_two_aware_datetimes_in_different_zones_compare_perfectly_well() -> None:
    """The guard must not have made anything legal illegal."""
    expect(datetime(2020, 1, 1, 0, 0, tzinfo=UTC)).is_before(
        datetime(2020, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    )


# ---------------------------------------------------------------------------
# The type survives, and so does the subclass
# ---------------------------------------------------------------------------
def test_a_date_subclass_stays_that_subclass() -> None:
    """People write ``class Anniversary(date)``, and ``T`` has to survive it."""
    leap_day = Anniversary(2020, 2, 29)
    subject = expect(leap_day)
    assert type(subject) is DateExpect
    assert subject.is_before(Anniversary(2021, 1, 1)) is subject
    assert type(subject.subject) is Anniversary


def test_a_date_subclass_gets_a_now_of_its_own_kind() -> None:
    """``_now_like`` builds from the subject's own type, so ``today()`` is a subclass."""
    expect(Anniversary(1999, 1, 1)).is_in_the_past()
    expect(Anniversary(2999, 1, 1)).is_in_the_future()
    with pytest.raises(AssertionFailure):
        expect(Anniversary(1999, 1, 1)).is_today()


def test_a_datetime_subclass_still_reaches_the_datetime_subject() -> None:
    class Stamp(datetime):
        __slots__ = ()

    subject = expect(Stamp(2020, 1, 1, 12, 0))
    assert type(subject) is DateTimeExpect
    assert subject.has_hour(12) is subject
    assert subject.is_naive() is subject


def test_the_two_subjects_are_the_ones_expect_hands_back() -> None:
    assert type(expect(date(2020, 1, 1))) is DateExpect
    assert type(expect(datetime(2020, 1, 1))) is DateTimeExpect
    assert type(expect(time(12, 0))).__name__ == "TimeExpect"
    assert type(expect(timedelta(0))).__name__ == "TimeDeltaExpect"


def test_a_datetime_subject_has_the_whole_date_catalogue() -> None:
    """``DateTimeExpect`` inherits ``DateExpect``, so everything there must work."""
    subject = expect(datetime(2020, 2, 29, 12, 0))
    assert subject.has_year(2020) is subject
    assert subject.has_month(2) is subject
    assert subject.has_day(29) is subject
    assert subject.is_weekend() is subject
    assert subject.is_in_the_past() is subject
    assert subject.is_between(datetime(2020, 1, 1), datetime(2021, 1, 1)) is subject


# ---------------------------------------------------------------------------
# Chaining, `because`, soft scopes and the formatter registry
# ---------------------------------------------------------------------------
def test_every_assertion_returns_the_subject_it_was_called_on() -> None:
    """The chain is the API; one assertion returning something else breaks it."""
    day = expect(date(2020, 5, 4))
    assert (
        day.is_before(date(2021, 1, 1))
        .and_.is_after(date(2019, 1, 1))
        .and_.is_on_or_before(date(2020, 5, 4))
        .and_.is_on_or_after(date(2020, 5, 4))
        .and_.is_between(date(2020, 1, 1), date(2020, 12, 31))
        .and_.is_not_between(date(2021, 1, 1), date(2021, 12, 31))
        .and_.is_strictly_between(date(2020, 1, 1), date(2020, 12, 31))
        .and_.has_year(2020)
        .and_.has_month(5)
        .and_.has_day(4)
        .and_.is_weekday()
        .and_.is_in_the_past()
        is day
    )


def test_the_datetime_chain_flows_too() -> None:
    moment = datetime(2020, 5, 4, 9, 30, tzinfo=UTC)
    subject = expect(moment)
    assert (
        subject.has_hour(9)
        .and_.has_minute(30)
        .and_.has_second(0)
        .and_.has_microsecond(0)
        .and_.is_aware()
        .and_.is_utc()
        .and_.has_timezone(UTC)
        .and_.is_same_date_as(datetime(2020, 5, 4, 23, 0, tzinfo=UTC))
        .and_.is_close_to(moment, within=timedelta(0))
        .and_.is_within(timedelta(minutes=1))
        .before(moment)
        is subject
    )


def test_the_duration_chain_flows_too() -> None:
    subject = expect(timedelta(minutes=3))
    assert (
        subject.is_longer_than(timedelta(minutes=1))
        .and_.is_shorter_than(timedelta(minutes=5))
        .and_.is_at_least(timedelta(minutes=3))
        .and_.is_at_most(timedelta(minutes=3))
        .and_.is_between(timedelta(0), timedelta(hours=1))
        .and_.is_not_between(timedelta(hours=1), timedelta(hours=2))
        .and_.is_positive()
        .and_.is_not_zero()
        .and_.is_close_to(timedelta(minutes=3), within=timedelta(0))
        .and_.has_total_seconds(180.0)
        is subject
    )


def test_because_reaches_the_date_assertions() -> None:
    shipped_on = date(2020, 5, 9)
    assert _message(
        lambda: expect(shipped_on).is_weekday(because="the warehouse is closed at weekends")
    ) == (
        "Expected shipped_on to fall on a weekday, but 2020-05-09 is a Saturday"
        " because the warehouse is closed at weekends."
    )


def test_a_soft_scope_collects_every_date_failure() -> None:
    with soft_assertions() as scope:
        hired_on = date(2020, 5, 4)
        expect(hired_on).has_year(2021)
        expect(hired_on).is_weekend()
        collected = scope.discard()
    assert collected == [
        "Expected hired_on to have year 2021, but had 2020 (2020-05-04).",
        "Expected hired_on to fall on a weekend, but 2020-05-04 is a Monday.",
    ]


def test_a_scoped_formatter_reaches_the_date_messages() -> None:
    with soft_assertions(formatters=(Stamped(),)) as scope:
        hired_on = date(2020, 5, 4)
        expect(hired_on).is_before(date(2019, 1, 1))
        collected = scope.discard()
    assert collected == ["Expected hired_on to be before <2019-01-01>, but was <2020-05-04>."]


def test_rendered_prefers_iso_over_the_stdlib_repr() -> None:
    """``datetime.datetime(2020, 1, 1, 0, 0)`` is noise beside ``2020-01-01T00:00:00``."""
    assert rendered(datetime(2020, 1, 1)) == "2020-01-01T00:00:00"
    assert rendered(date(2020, 1, 1)) == "2020-01-01"
    assert rendered(time(9, 30)) == "09:30:00"
    assert rendered(timedelta(minutes=90)) == "1:30:00"
    assert rendered(7) == "7"


def test_rendered_prints_a_backwards_duration_as_a_negative_one() -> None:
    """``str(timedelta(seconds=-5))`` is ``'-1 day, 23:59:55'``, and nobody means that.

    Only ``days`` carries the sign once a ``timedelta`` normalises, so the stdlib
    spelling makes a reader do subtraction in the middle of a failure message.
    """
    assert str(timedelta(seconds=-5)) == "-1 day, 23:59:55"
    assert rendered(timedelta(seconds=-5)) == "-0:00:05"
    assert rendered(timedelta(hours=-5)) == "-5:00:00"
    assert rendered(timedelta(days=-1)) == "-1 day, 0:00:00"
    assert rendered(timedelta(microseconds=-1)) == "-0:00:00.000001"
    # Positive durations are left exactly as they were.
    assert rendered(timedelta(seconds=5)) == "0:00:05"
    assert rendered(timedelta(0)) == "0:00:00"


# ---------------------------------------------------------------------------
# Two corners of the failure path: an operand of no calendar kind at all, and
# what an open difference chain shows a debugger
# ---------------------------------------------------------------------------
def test_an_operand_of_no_calendar_kind_is_named_by_its_own_type() -> None:
    """``_kind`` reads the MRO, and a domain value names none of the four kinds.

    The fallback is what keeps the sentence complete. Without it the message
    would have to leave one side unnamed -- and the side it cannot name is
    precisely the one the reader has not understood yet.
    """

    class Stardate:
        """Comparable with nothing in the calendar, and a plausible operand anyway."""

        __slots__ = ()

        def __repr__(self) -> str:
            return "Stardate(41153.7)"

    hired_on = date(2020, 5, 4)

    with pytest.raises(TypeError) as caught:
        expect(hired_on).is_before(cast("date", Stardate()))

    assert str(caught.value) == (
        "can't compare a date with a Stardate:"
        " 2020-05-04 is a date and Stardate(41153.7) is a Stardate"
    )


def test_an_operand_named_with_a_vowel_gets_an_rather_than_a() -> None:
    """The article follows the kind. "a Instant" is a sentence nobody writes."""

    class Instant:
        """A domain moment, named so the article has to move."""

        __slots__ = ()

        def __repr__(self) -> str:
            return "Instant(0)"

    hired_on = date(2020, 5, 4)

    with pytest.raises(TypeError) as caught:
        expect(hired_on).is_before(cast("date", Instant()))

    assert str(caught.value) == (
        "can't compare a date with an Instant: 2020-05-04 is a date and Instant(0) is an Instant"
    )


def test_an_open_difference_chain_reprs_as_the_delta_it_holds() -> None:
    """What a debugger stopped between ``is_within`` and its continuation shows.

    The default ``<...WithinDelta object at 0x...>`` names neither half of the
    chain, and the delta is the only thing the object is carrying -- the same
    thing :meth:`WithinDelta.__del__` reaches for when the chain is abandoned.
    """
    deadline = datetime(2020, 1, 1, 12, 0)

    chain = expect(deadline).is_within(timedelta(minutes=5))
    rendering = repr(chain)
    chain.before(deadline)  # finish it, so the finaliser has nothing to warn about

    assert rendering == "WithinDelta(datetime.timedelta(seconds=300))"
