"""The date subjects' static surface: what survives a chain.

Three properties are pinned here.

``T`` survives every assertion, so ``.subject`` comes back as the type that went
in -- and a ``date`` **subclass** stays that subclass rather than widening to
``date``. That is the reason :class:`DateExpect` is generic at all.

The operand of a comparison is ``T`` as well, which is what keeps a ``date``
bound out of a ``datetime`` subject. ``datetime_negative.py`` holds that half,
and also holds the direction that cannot be refused: a ``datetime`` **is** a
``date``, so a ``datetime`` bound on a ``date`` subject typechecks and is pinned
*here*, as the accepted call it is. The runtime raises the ``TypeError`` no
checker could.

And the difference chain ``is_within(delta).before(other)`` keeps flowing: its
continuations hand back the subject that opened it, not a new one, so a
subclassed subject stays subclassed all the way through.

``expect()``'s dispatch table is pinned in ``dispatch.py``; nothing here repeats
it beyond what a chain needs to start.
"""

from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import assert_type

from lovely_assertions import DateExpect, DateTimeExpect, TimeDeltaExpect, TimeExpect, expect
from lovely_assertions._datetime import WithinDelta


class BillingDate(date):
    """A ``date`` subclass, of the kind people actually write."""

    __slots__ = ()


class Stamp(datetime):
    """A ``datetime`` subclass. It dispatches to the datetime subject, not the date one."""

    __slots__ = ()


def chaining_keeps_the_date_subject(hired_on: date, other: date) -> None:
    subject = expect(hired_on)
    assert_type(subject, DateExpect[date])
    assert_type(subject.is_before(other), DateExpect[date])
    assert_type(subject.is_after(other), DateExpect[date])
    assert_type(subject.is_on_or_before(other), DateExpect[date])
    assert_type(subject.is_on_or_after(other), DateExpect[date])
    assert_type(subject.is_between(other, other), DateExpect[date])
    assert_type(subject.is_not_between(other, other), DateExpect[date])
    assert_type(subject.is_strictly_between(other, other), DateExpect[date])
    assert_type(subject.has_year(2020), DateExpect[date])
    assert_type(subject.has_month(5), DateExpect[date])
    assert_type(subject.has_day(4), DateExpect[date])
    assert_type(subject.is_weekday(), DateExpect[date])
    assert_type(subject.is_weekend(), DateExpect[date])
    assert_type(subject.is_today(), DateExpect[date])
    assert_type(subject.is_in_the_past(), DateExpect[date])
    assert_type(subject.is_in_the_future(), DateExpect[date])
    assert_type(subject.is_before(other).and_.is_weekday(), DateExpect[date])


def the_date_subject_keeps_its_own_type(hired_on: date) -> None:
    assert_type(expect(hired_on).is_before(hired_on).subject, date)


def a_date_subclass_survives_the_whole_chain(cycle: BillingDate) -> None:
    """The reason the subject is generic: ``.subject`` must not widen to ``date``."""
    assert_type(expect(cycle), DateExpect[BillingDate])
    assert_type(expect(cycle).is_before(cycle), DateExpect[BillingDate])
    assert_type(expect(cycle).is_weekend().and_.is_in_the_past(), DateExpect[BillingDate])
    assert_type(expect(cycle).has_year(2020).subject, BillingDate)


def a_datetime_operand_on_a_date_subject_is_accepted(hired_on: date, moment: datetime) -> None:
    """The Liskov wart, pinned as an *accepted* call because that is what it is.

    ``datetime`` subclasses ``date``, so this satisfies ``T = date`` and no
    checker anywhere can refuse it. The runtime raises a ``TypeError`` naming the
    mismatch, which is the whole reason that half of the module exists.
    """
    assert_type(expect(hired_on).is_before(moment), DateExpect[date])
    assert_type(expect(hired_on).is_between(hired_on, moment), DateExpect[date])


def chaining_keeps_the_datetime_subject(started_at: datetime, other: datetime) -> None:
    subject = expect(started_at)
    assert_type(subject, DateTimeExpect)
    assert_type(subject.is_before(other), DateTimeExpect)
    assert_type(subject.is_between(other, other), DateTimeExpect)
    assert_type(subject.has_year(2020), DateTimeExpect)
    assert_type(subject.has_hour(9), DateTimeExpect)
    assert_type(subject.has_minute(30), DateTimeExpect)
    assert_type(subject.has_second(0), DateTimeExpect)
    assert_type(subject.has_microsecond(0), DateTimeExpect)
    assert_type(subject.is_same_date_as(other), DateTimeExpect)
    assert_type(subject.is_aware(), DateTimeExpect)
    assert_type(subject.is_naive(), DateTimeExpect)
    assert_type(subject.is_utc(), DateTimeExpect)
    assert_type(subject.is_weekday().and_.is_in_the_past(), DateTimeExpect)
    assert_type(subject.subject, datetime)


def the_datetime_subject_takes_datetime_bounds(started_at: datetime, other: datetime) -> None:
    """The half of the wart a checker *can* refuse; the refusal is in the negative file."""
    assert_type(expect(started_at).is_after(other), DateTimeExpect)
    assert_type(expect(started_at).is_strictly_between(other, other), DateTimeExpect)


def closeness_takes_a_timedelta(started_at: datetime, other: datetime, span: timedelta) -> None:
    assert_type(expect(started_at).is_close_to(other, within=span), DateTimeExpect)
    assert_type(expect(started_at).is_not_close_to(other, within=span), DateTimeExpect)


def timezones(started_at: datetime, zone: tzinfo) -> None:
    assert_type(expect(started_at).has_timezone(zone), DateTimeExpect)
    assert_type(expect(started_at).has_timezone(UTC), DateTimeExpect)


def the_difference_chain_flows(started_at: datetime, other: datetime, span: timedelta) -> None:
    """``is_within(delta)`` is a step, and both continuations return the subject."""
    opened = expect(started_at).is_within(span)
    assert_type(opened, WithinDelta[DateTimeExpect])
    assert_type(opened.before(other), DateTimeExpect)
    assert_type(opened.after(other), DateTimeExpect)
    assert_type(expect(started_at).is_within(span).before(other).and_.is_utc(), DateTimeExpect)


def the_difference_chain_keeps_a_subclassed_subject(other: datetime, span: timedelta) -> None:
    """``WithinDelta`` is generic over the subject, so an extension survives it."""

    class Deadline(DateTimeExpect):
        __slots__ = ()

        def is_business_hours(self) -> "Deadline":
            return self

    subject = Deadline(other)
    assert_type(subject.is_within(span), WithinDelta[Deadline])
    assert_type(subject.is_within(span).before(other), Deadline)
    assert_type(subject.is_within(span).after(other).is_business_hours(), Deadline)


def a_datetime_subclass_reaches_the_datetime_subject(stamp: Stamp) -> None:
    """``datetime`` comes before ``date`` in the overload table, and stays there."""
    assert_type(expect(stamp), DateTimeExpect)
    assert_type(expect(stamp).has_hour(9), DateTimeExpect)


def chaining_keeps_the_time_subject(opens_at: time, other: time) -> None:
    subject = expect(opens_at)
    assert_type(subject, TimeExpect)
    assert_type(subject.is_before(other), TimeExpect)
    assert_type(subject.is_after(other), TimeExpect)
    assert_type(subject.is_on_or_before(other), TimeExpect)
    assert_type(subject.is_on_or_after(other), TimeExpect)
    assert_type(subject.is_between(other, other), TimeExpect)
    assert_type(subject.is_not_between(other, other), TimeExpect)
    assert_type(subject.is_strictly_between(other, other), TimeExpect)
    assert_type(subject.has_hour(9), TimeExpect)
    assert_type(subject.has_minute(30), TimeExpect)
    assert_type(subject.has_second(0), TimeExpect)
    assert_type(subject.has_microsecond(0), TimeExpect)
    assert_type(subject.is_aware(), TimeExpect)
    assert_type(subject.is_naive(), TimeExpect)
    assert_type(subject.is_midnight(), TimeExpect)
    assert_type(subject.is_midnight().and_.is_naive().subject, time)


def chaining_keeps_the_duration_subject(elapsed: timedelta, other: timedelta) -> None:
    subject = expect(elapsed)
    assert_type(subject, TimeDeltaExpect)
    assert_type(subject.is_longer_than(other), TimeDeltaExpect)
    assert_type(subject.is_shorter_than(other), TimeDeltaExpect)
    assert_type(subject.is_at_least(other), TimeDeltaExpect)
    assert_type(subject.is_at_most(other), TimeDeltaExpect)
    assert_type(subject.is_between(other, other), TimeDeltaExpect)
    assert_type(subject.is_not_between(other, other), TimeDeltaExpect)
    assert_type(subject.is_positive(), TimeDeltaExpect)
    assert_type(subject.is_negative(), TimeDeltaExpect)
    assert_type(subject.is_zero(), TimeDeltaExpect)
    assert_type(subject.is_not_zero(), TimeDeltaExpect)
    assert_type(subject.is_close_to(other, within=other), TimeDeltaExpect)
    assert_type(subject.is_not_close_to(other, within=other), TimeDeltaExpect)
    assert_type(subject.has_total_seconds(1.5), TimeDeltaExpect)
    assert_type(subject.has_total_seconds(90), TimeDeltaExpect)
    assert_type(subject.is_positive().and_.is_not_zero().subject, timedelta)


def because_reaches_every_date_assertion(
    hired_on: date, started_at: datetime, opens_at: time, elapsed: timedelta, span: timedelta
) -> None:
    """Every assertion takes a reason, and ``because`` is keyword-only throughout."""
    expect(hired_on).is_before(hired_on, because="the contract predates it")
    expect(hired_on).is_weekday(because="payroll runs on working days")
    expect(started_at).is_close_to(started_at, within=span, because="the clock drifts")
    expect(started_at).is_within(span).before(started_at, because="the form closes")
    expect(opens_at).is_midnight(because="the batch starts the day")
    expect(elapsed).is_positive(because="time does not run backwards here")


def the_explicit_subject_form_is_typed(hired_on: date, started_at: datetime) -> None:
    """``as_=`` is the fully typed way to ask for a subject by name."""
    assert_type(expect(hired_on, as_=DateExpect[date]), DateExpect[date])
    assert_type(expect(started_at, as_=DateTimeExpect), DateTimeExpect)
    assert_type(expect(started_at, as_=DateTimeExpect).is_utc(), DateTimeExpect)
