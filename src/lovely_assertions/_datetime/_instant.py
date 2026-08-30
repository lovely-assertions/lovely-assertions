"""A point in time, where the calendar half and the clock half meet.

A ``datetime`` *is* a ``date``, so this subject inherits the calendar catalogue
whole and adds what only a moment can answer: the timezone it carries, whether
it is the same date as another, and closeness within a tolerance.

``is_within(delta).before(other)`` reads as one assertion and is two calls, which
is why the middle of it is its own object rather than a keyword argument.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._datetime._calendar import DateExpect
from lovely_assertions._datetime._clock import ClockExpect
from lovely_assertions._datetime._guards import reject_incomparable, reject_negative_span
from lovely_assertions._datetime._lazy import DateTimeValue
from lovely_assertions._datetime._render import (
    not_utc_reason,
    rendered,
    same_offset_note,
    timezone_of,
)
from lovely_assertions._datetime._within import WithinDelta
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import datetime, timedelta, tzinfo

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class DateTimeExpect(DateExpect[DateTimeValue], ClockExpect[DateTimeValue]):
    """Assertions for a point in time.

    Everything on :class:`DateExpect` and every clock assertion are here as well,
    so one chain can run from the calendar day down to the timezone.
    """

    __slots__ = ()

    def is_same_date_as(self, other: "datetime", /, *, because: str = "") -> Self:
        """Assert the subject falls on the same calendar day as ``other``.

        Wall clock against wall clock: neither side is converted to a common
        timezone first, because the question "was this the same day?" is asked of
        the calendar each value carries. Two aware moments in different zones can
        therefore be the same instant and different dates, which is a fact about
        calendars rather than a defect here.
        """
        if self._subject.date() == other.date():
            return self
        return self._fail(
            f"to fall on the same date as {rendered(other)}, but was {rendered(self._subject)}",
            because,
        )

    def is_close_to(self, other: "datetime", /, *, within: "timedelta", because: str = "") -> Self:
        """Assert the subject is no more than ``within`` away from ``other``.

        The distance is absolute, so the assertion is symmetric in both senses:
        it does not care which of the two came first, and swapping subject and
        operand cannot change the verdict. A negative ``within`` raises
        ``ValueError``; zero is legal and means exact equality.
        """
        reject_negative_span("within", within)
        try:
            distance = abs(self._subject - other)
        except TypeError as error:
            reject_incomparable(self._subject, other, error)
        if distance <= within:
            return self
        return self._fail(
            f"to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)}, {rendered(distance)} away",
            because,
        )

    def is_not_close_to(
        self, other: "datetime", /, *, within: "timedelta", because: str = ""
    ) -> Self:
        """Assert the subject is more than ``within`` away from ``other``.

        The exact complement of :meth:`is_close_to`.
        """
        reject_negative_span("within", within)
        try:
            distance = abs(self._subject - other)
        except TypeError as error:
            reject_incomparable(self._subject, other, error)
        if distance > within:
            return self
        return self._fail(
            f"not to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)}, only {rendered(distance)} away",
            because,
        )

    def is_utc(self, *, because: str = "") -> Self:
        """Assert the subject is anchored to UTC.

        Decided by offset, not by identity: ``timezone.utc``, ``ZoneInfo("UTC")``
        and ``timezone(timedelta(0))`` are three unequal objects that describe the
        same timezone, and an assertion that could tell them apart would be
        asserting which library built the value rather than what the value means.
        :meth:`has_timezone` is the identity question, for when that is what was
        wanted.
        """
        offset = self._subject.utcoffset()
        # A `timedelta` is falsy exactly when it is zero, which is how the offset
        # is compared against zero without a zero to compare it against.
        if offset is not None and not offset:
            return self
        return self._fail(
            f"to be UTC, but {rendered(self._subject)} {not_utc_reason(self._subject)}", because
        )

    def has_timezone(self, zone: "tzinfo", /, *, because: str = "") -> Self:
        """Assert the subject carries exactly the timezone ``zone``.

        Equality of ``tzinfo``, deliberately -- :meth:`is_utc` is the offset
        question. Where the two disagree the failure says so, because a message
        whose two halves print the same offset is otherwise unreadable.
        """
        if self._subject.tzinfo == zone:
            return self
        return self._fail(
            f"to have timezone {rendered(zone)}, but {rendered(self._subject)}"
            f" has {timezone_of(self._subject)}{same_offset_note(self._subject, zone)}",
            because,
        )

    def is_within(self, delta: "timedelta", /) -> "WithinDelta[Self]":
        """Open a difference chain: ``is_within(delta).before(other)`` or ``.after(other)``.

        The Python spelling of FluentAssertions' ``BeLessThan(ts).Before(x)``.
        The assertion is made by the continuation, not by this call: ``is_within``
        on its own asserts nothing, and says so out loud if it is ever left that
        way (see :meth:`WithinDelta.__del__`).

        A negative ``delta`` raises ``ValueError``; a zero one is legal and
        narrows the chain to exact equality with the continuation's operand.
        Takes no ``because``; the reason belongs to the continuation that does
        the asserting.
        """
        reject_negative_span("the delta given to is_within", delta)
        return WithinDelta(self, delta)
