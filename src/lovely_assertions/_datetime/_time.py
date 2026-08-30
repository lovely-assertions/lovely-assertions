"""A clock reading with no date behind it.

The thinnest subject in the package: everything it can answer is a clock question
or an ordering question, and both arrive from the shared bases. What it declares
is that a ``time`` is what it holds.
"""

from typing import Self

from lovely_assertions._datetime._clock import ClockExpect
from lovely_assertions._datetime._lazy import TimeValue
from lovely_assertions._datetime._render import rendered
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class TimeExpect(ClockExpect[TimeValue]):
    """Assertions for a time of day.

    A ``time`` carries a ``tzinfo`` and no date, so it crashes on a naive/aware
    comparison exactly as a ``datetime`` does and is guarded the same way.
    """

    __slots__ = ()

    def is_midnight(self, *, because: str = "") -> Self:
        """Assert the subject is exactly 00:00:00.000000.

        Asked of the wall clock, so an aware midnight is midnight: it is midnight
        *somewhere*, which is what a ``time`` with a timezone means.
        """
        subject = self._subject
        if not (subject.hour or subject.minute or subject.second or subject.microsecond):
            return self
        return self._fail(f"to be midnight, but was {rendered(subject)}", because)
