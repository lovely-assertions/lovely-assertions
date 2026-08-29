"""Every marked line here must be rejected by pyright and mypy.

What this rules out: a bound of the wrong temporal kind, a tolerance that is not
a duration, the clock assertions leaking onto a subject that has no clock, the
number assertions leaking onto a subject that is not a number, and a date subject
that forgot which date type it was holding.

The one thing it deliberately does **not** rule out is a ``datetime`` bound on a
``date`` subject. ``datetime`` subclasses ``date``, so that call typechecks and
nothing here could make it stop -- it is pinned as an accepted call in
``positive/datetime_subject.py``, and the runtime raises the ``TypeError`` that
names the mismatch instead.
"""

from datetime import date, datetime, time, timedelta
from typing import assert_type

from lovely_assertions import DateExpect, DateTimeExpect, TimeDeltaExpect, TimeExpect, expect
from lovely_assertions._datetime import WithinDelta


class BillingDate(date):
    """A ``date`` subclass, of the kind people actually write."""

    __slots__ = ()


def a_bound_has_to_be_the_temporal_kind_being_compared(
    started_at: datetime, hired_on: date, opens_at: time, elapsed: timedelta
) -> None:
    """The half of the Liskov wart a checker *can* refuse: a date on a datetime."""
    expect(started_at).is_before(hired_on)  # expect-error: a `date` bound on a `datetime`
    expect(started_at).is_after(hired_on)  # expect-error
    expect(started_at).is_between(hired_on, hired_on)  # expect-error
    expect(started_at).is_same_date_as(hired_on)  # expect-error
    expect(opens_at).is_before(started_at)  # expect-error: a `datetime` is not a `time`
    expect(opens_at).is_after(hired_on)  # expect-error
    expect(started_at).is_before(opens_at)  # expect-error
    expect(hired_on).is_before(opens_at)  # expect-error
    expect(elapsed).is_longer_than(started_at)  # expect-error: a moment is not a duration


def a_string_is_never_a_date(
    started_at: datetime, hired_on: date, opens_at: time, elapsed: timedelta
) -> None:
    """The operand people actually reach for, and the one that must never land."""
    expect(hired_on).is_before("2020-01-01")  # expect-error
    expect(started_at).is_after("2020-01-01T00:00:00")  # expect-error
    expect(opens_at).is_between("09:00", "17:00")  # expect-error
    expect(elapsed).is_at_most("PT1H")  # expect-error
    expect(hired_on).has_year("2020")  # expect-error: a component is an int
    expect(started_at).has_hour("09")  # expect-error


def a_number_is_never_a_duration(started_at: datetime, elapsed: timedelta) -> None:
    """``within=60`` is the mistake this signature exists to catch."""
    expect(started_at).is_close_to(started_at, within=60)  # expect-error: not a `timedelta`
    expect(started_at).is_not_close_to(started_at, within=60.0)  # expect-error
    expect(started_at).is_within(300)  # expect-error
    expect(elapsed).is_close_to(elapsed, within=1)  # expect-error
    expect(elapsed).is_longer_than(60)  # expect-error
    expect(elapsed).has_total_seconds("90")  # expect-error: that one really is a float


def a_tolerance_is_not_optional(started_at: datetime, elapsed: timedelta) -> None:
    """``within=`` is keyword-only and required: closeness with no tolerance is not a claim."""
    expect(started_at).is_close_to(started_at)  # expect-error: no `within=`
    expect(started_at).is_not_close_to(started_at)  # expect-error
    expect(elapsed).is_close_to(elapsed)  # expect-error
    expect(started_at).is_close_to(started_at, timedelta(0))  # expect-error: keyword-only


def the_clock_assertions_do_not_leak_onto_a_date(hired_on: date) -> None:
    """A ``date`` has no time of day; these live on the two subjects that do."""
    expect(hired_on).has_hour(9)  # expect-error
    expect(hired_on).has_minute(30)  # expect-error
    expect(hired_on).has_second(0)  # expect-error
    expect(hired_on).has_microsecond(0)  # expect-error
    expect(hired_on).is_aware()  # expect-error
    expect(hired_on).is_naive()  # expect-error
    expect(hired_on).is_utc()  # expect-error
    expect(hired_on).is_same_date_as(hired_on)  # expect-error
    expect(hired_on).is_close_to(hired_on, within=timedelta(0))  # expect-error
    expect(hired_on).is_within(timedelta(0))  # expect-error
    expect(hired_on).is_midnight()  # expect-error


def the_calendar_assertions_do_not_leak_onto_a_time(opens_at: time) -> None:
    """A ``time`` has no date in it, so it has no year, no weekday and no today."""
    expect(opens_at).has_year(2020)  # expect-error
    expect(opens_at).has_month(5)  # expect-error
    expect(opens_at).has_day(4)  # expect-error
    expect(opens_at).is_weekday()  # expect-error
    expect(opens_at).is_weekend()  # expect-error
    expect(opens_at).is_today()  # expect-error
    expect(opens_at).is_in_the_past()  # expect-error
    expect(opens_at).is_in_the_future()  # expect-error


def is_midnight_belongs_to_the_time_subject(started_at: datetime) -> None:
    """A ``datetime`` at midnight is a moment, not a time of day; ``.time()`` narrows it."""
    expect(started_at).is_midnight()  # expect-error


def the_number_assertions_are_not_here(
    hired_on: date, started_at: datetime, opens_at: time
) -> None:
    """``_ordered.py`` explains the split: a date is orderable and is not a number.

    Zero is not a concept a calendar has, so ``is_positive`` and its neighbours
    stay with the subjects that do have one -- ``timedelta`` among them.
    """
    expect(hired_on).is_positive()  # expect-error
    expect(hired_on).is_negative()  # expect-error
    expect(hired_on).is_zero()  # expect-error
    expect(started_at).is_positive()  # expect-error
    expect(opens_at).is_zero()  # expect-error
    expect(hired_on).is_greater_than(hired_on)  # expect-error: dates say `is_after`
    expect(hired_on).is_less_than(hired_on)  # expect-error


def the_duration_assertions_are_not_on_a_moment(started_at: datetime, elapsed: timedelta) -> None:
    expect(started_at).has_total_seconds(90.0)  # expect-error
    expect(started_at).is_longer_than(elapsed)  # expect-error
    expect(elapsed).has_year(2020)  # expect-error: a duration is not on a calendar
    expect(elapsed).is_before(elapsed)  # expect-error: durations say shorter, not before
    expect(elapsed).is_weekday()  # expect-error
    expect(elapsed).is_aware()  # expect-error


def a_range_needs_two_bounds(hired_on: date, elapsed: timedelta) -> None:
    expect(hired_on).is_between(hired_on)  # expect-error: one bound is not a range
    expect(hired_on).is_strictly_between(hired_on)  # expect-error
    expect(hired_on).is_not_between()  # expect-error
    expect(elapsed).is_between(elapsed)  # expect-error


def because_is_keyword_only(hired_on: date, started_at: datetime, elapsed: timedelta) -> None:
    expect(hired_on).is_weekday("a reason")  # expect-error: `because` is keyword-only
    expect(hired_on).is_before(hired_on, "a reason")  # expect-error
    expect(elapsed).is_positive("a reason")  # expect-error
    expect(started_at).is_within(timedelta(0), because="a reason")  # expect-error: not an assertion


def the_no_operand_assertions_take_no_operand(hired_on: date, elapsed: timedelta) -> None:
    expect(hired_on).is_today(hired_on)  # expect-error
    expect(hired_on).is_weekend(5)  # expect-error
    expect(elapsed).is_zero(timedelta(0))  # expect-error


def the_difference_chain_is_typed(started_at: datetime, hired_on: date) -> None:
    """The continuations are the assertion, and they take a moment like any other."""
    expect(started_at).is_within(timedelta(0)).before(hired_on)  # expect-error: a `date`
    expect(started_at).is_within(timedelta(0)).after("noon")  # expect-error
    expect(started_at).is_within(timedelta(0)).during(started_at)  # expect-error: no such step
    expect(started_at).is_within(timedelta(0)).before()  # expect-error: it needs the other moment
    WithinDelta(expect(hired_on), timedelta(0))  # expect-error: a date subject cannot open one


def a_date_subclass_does_not_widen(cycle: BillingDate, hired_on: date) -> None:
    """``T`` is the concrete date type, and the bound is ``T`` -- as on ``OrderedExpect``.

    A plain ``date`` bound on a ``BillingDate`` subject compares perfectly well at
    runtime; refusing it is the price of the ``T`` bound that refuses a ``date``
    on a ``datetime``, and the price is paid knowingly.
    """
    assert_type(expect(cycle), DateExpect[date])  # expect-error: it is a `BillingDate`
    assert_type(expect(cycle).subject, date)  # expect-error
    expect(cycle).is_before(hired_on)  # expect-error: the bound is `T`, not `date`


def the_subjects_are_not_interchangeable(
    started_at: datetime, hired_on: date, opens_at: time, elapsed: timedelta
) -> None:
    assert_type(expect(started_at), DateExpect[date])  # expect-error: it is a `DateTimeExpect`
    assert_type(expect(hired_on), DateTimeExpect)  # expect-error
    assert_type(expect(opens_at), DateExpect[time])  # expect-error
    assert_type(expect(elapsed), TimeExpect)  # expect-error
    assert_type(expect(started_at).subject, date)  # expect-error
    assert_type(expect(elapsed).subject, float)  # expect-error


def the_parameter_has_to_be_a_date() -> None:
    DateExpect("2020-01-01")  # expect-error: a string is not a date
    DateExpect(3)  # expect-error
    DateTimeExpect(date(2020, 1, 1))  # expect-error: a `date` is not a `datetime`
    TimeExpect(datetime(2020, 1, 1))  # expect-error
    TimeDeltaExpect(datetime(2020, 1, 1))  # expect-error
