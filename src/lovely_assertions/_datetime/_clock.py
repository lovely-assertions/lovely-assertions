"""The time of day, and whether it is anchored to a timezone.

Shared by the two subjects that carry a clock reading. Awareness is the half
people forget: a naive time and an aware one are different kinds of value, and
comparing them raises rather than answering, so an assertion about which one you
have is worth being able to write.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._datetime._bounds import HOURS, MICROSECONDS, MINUTES, SECONDS
from lovely_assertions._datetime._guards import reject_impossible_component
from lovely_assertions._datetime._render import rendered
from lovely_assertions._datetime._temporal import TemporalExpect
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import datetime, time

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ClockExpect[T: "datetime | time"](TemporalExpect[T]):
    """The time of day, and whether it is anchored to a timezone.

    Private, and shared by :class:`DateTimeExpect` and :class:`TimeExpect`,
    which are the two subjects that have a clock in them. The union bound is
    safe here where it is not on :class:`TemporalExpect`: these assertions read
    attributes both members of the union have, and never compare one against the
    other.
    """

    __slots__ = ()

    def has_hour(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's hour is ``expected``, on a 24-hour clock."""
        reject_impossible_component("hour", expected, HOURS)
        if self._subject.hour == expected:
            return self
        return self._fail(
            f"to have hour {rendered(expected)}, but had {rendered(self._subject.hour)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_minute(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's minute is ``expected``."""
        reject_impossible_component("minute", expected, MINUTES)
        if self._subject.minute == expected:
            return self
        return self._fail(
            f"to have minute {rendered(expected)}, but had {rendered(self._subject.minute)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_second(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's second is ``expected``. ``datetime`` has no leap seconds."""
        reject_impossible_component("second", expected, SECONDS)
        if self._subject.second == expected:
            return self
        return self._fail(
            f"to have second {rendered(expected)}, but had {rendered(self._subject.second)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_microsecond(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's microsecond is ``expected``."""
        reject_impossible_component("microsecond", expected, MICROSECONDS)
        if self._subject.microsecond == expected:
            return self
        return self._fail(
            f"to have microsecond {rendered(expected)},"
            f" but had {rendered(self._subject.microsecond)} ({rendered(self._subject)})",
            because,
        )

    def is_aware(self, *, because: str = "") -> Self:
        """Assert the subject carries a usable timezone.

        A ``tzinfo`` is not enough: one whose ``utcoffset`` answers ``None`` is
        legal, is what ``datetime`` itself treats as naive, and is the reason the
        question is asked of the offset rather than of the attribute.
        """
        if self._subject.utcoffset() is not None:
            return self
        return self._fail(f"to be timezone-aware, but {rendered(self._subject)} is naive", because)

    def is_naive(self, *, because: str = "") -> Self:
        """Assert the subject carries no usable timezone -- :meth:`is_aware`'s complement."""
        offset = self._subject.utcoffset()
        if offset is None:
            return self
        return self._fail(
            f"to be naive, but {rendered(self._subject)} is timezone-aware"
            f" (offset {rendered(offset)})",
            because,
        )
