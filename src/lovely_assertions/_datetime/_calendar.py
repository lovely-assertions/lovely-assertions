"""The calendar subject: a year, a month, a day and what they add up to.

Weekday and weekend are here rather than as a predicate the caller writes,
because the answer depends on a convention -- Saturday and Sunday -- that a test
should not have to restate, and because the failure names the day it landed on.

The three that compare against today are the only assertions in this package
that read a clock, and they read it in the subject's own timezone.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._datetime._bounds import DAYS, MAX_YEAR, MIN_YEAR, MONTHS, SATURDAY
from lovely_assertions._datetime._guards import reject_impossible_component
from lovely_assertions._datetime._now import now_like
from lovely_assertions._datetime._render import day_name, rendered
from lovely_assertions._datetime._temporal import TemporalExpect
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import date

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# The public subjects
# ---------------------------------------------------------------------------
class DateExpect[T: "date"](TemporalExpect[T]):
    """Assertions for a calendar date.

    :class:`DateTimeExpect` extends this with everything that needs a time of
    day, mirroring ``datetime``'s own inheritance from ``date``.

    The operand of a comparison is ``T`` rather than ``date``, which is what
    buys the static half of the Liskov wart: on a ``DateTimeExpect`` it resolves
    to ``datetime``, so a ``date`` bound is refused by the checker instead of
    crashing at runtime. The other direction cannot be refused by anybody --
    a ``datetime`` *is* a ``date`` -- which is why the runtime half exists.
    """

    __slots__ = ()

    def has_year(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject falls in year ``expected``."""
        reject_impossible_component("year", expected, (MIN_YEAR, MAX_YEAR))
        if self._subject.year == expected:
            return self
        return self._fail(
            f"to have year {rendered(expected)}, but had {rendered(self._subject.year)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_month(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject falls in month ``expected``, January being 1."""
        reject_impossible_component("month", expected, MONTHS)
        if self._subject.month == expected:
            return self
        return self._fail(
            f"to have month {rendered(expected)}, but had {rendered(self._subject.month)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_day(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject falls on day ``expected`` of its month.

        Day 31 of a February is a claim that fails; day 32 is a claim no calendar
        has room for, and raises ``ValueError``.
        """
        reject_impossible_component("day of the month", expected, DAYS)
        if self._subject.day == expected:
            return self
        return self._fail(
            f"to have day {rendered(expected)}, but had {rendered(self._subject.day)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def is_weekday(self, *, because: str = "") -> Self:
        """Assert the subject falls Monday through Friday."""
        if self._subject.weekday() < SATURDAY:
            return self
        return self._fail(
            f"to fall on a weekday, but {rendered(self._subject)} is a {day_name(self._subject)}",
            because,
        )

    def is_weekend(self, *, because: str = "") -> Self:
        """Assert the subject falls on a Saturday or a Sunday."""
        if self._subject.weekday() >= SATURDAY:
            return self
        return self._fail(
            f"to fall on a weekend, but {rendered(self._subject)} is a {day_name(self._subject)}",
            because,
        )

    def is_today(self, *, because: str = "") -> Self:
        """Assert the subject falls on today's calendar date.

        Compared by calendar day rather than by equality, so a ``datetime``
        subject passes at any hour of the day -- ``date`` and ``datetime`` never
        compare equal to each other, and a subject narrowed to a moment would
        otherwise be able to pass only in the microsecond it was created.

        For an aware subject "today" is today *in the subject's own timezone*,
        which is the only reading that does not compare a wall clock against a
        different one.
        """
        now = now_like(self._subject)
        if self._subject.toordinal() == now.toordinal():
            return self
        return self._fail(
            f"to be today, but was {rendered(self._subject)} and today is {rendered(now)}", because
        )

    def is_in_the_past(self, *, because: str = "") -> Self:
        """Assert the subject is earlier than the moment the assertion runs.

        "Now" is sampled in the subject's own shape and timezone, so an aware
        subject is compared against an aware now and a naive one against a naive
        now. Anything else would raise the very ``TypeError`` this module is here
        to explain. A ``date`` subject is compared by day, so *today* is neither
        past nor future.
        """
        now = now_like(self._subject)
        if self._subject < now:
            return self
        return self._fail(
            f"to be in the past, but was {rendered(self._subject)} and now is {rendered(now)}",
            because,
        )

    def is_in_the_future(self, *, because: str = "") -> Self:
        """Assert the subject is later than the moment the assertion runs."""
        now = now_like(self._subject)
        if self._subject > now:
            return self
        return self._fail(
            f"to be in the future, but was {rendered(self._subject)} and now is {rendered(now)}",
            because,
        )
