"""Sampling the current moment in the subject's own shape and timezone.

The one thing in this package that reads a clock, which is why it is on its own:
everything else here is a comparison between two values the caller already holds,
and a test that reads the clock is a test that can fail once a year.

Sampled in the subject's timezone rather than in the local one, so "is in the
past" means the same thing for an aware moment as for a naive one.
"""

from typing import TYPE_CHECKING, cast

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import date, tzinfo

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def zone_of(value: object, /) -> "tzinfo | None":
    """The value's own timezone, or ``None`` when it is naive.

    Naive by the same rule as :meth:`ClockExpect.is_aware`: a ``tzinfo`` whose
    ``utcoffset`` answers ``None`` is not a timezone, and handing it to
    ``datetime.now`` would be asking for the current moment somewhere that
    declines to say where it is.
    """
    utcoffset = getattr(value, "utcoffset", None)
    if utcoffset is None or utcoffset() is None:
        return None
    return cast("tzinfo | None", getattr(value, "tzinfo", None))


def now_like[D: "date"](value: D, /) -> D:
    """The current moment, in the same shape and timezone as ``value``.

    Built from the subject's own type, so a ``date`` gets a date, a ``datetime``
    gets a datetime, and a subclass of either gets one of itself -- and no
    ``datetime`` import is needed to produce any of them.

    Matching the *awareness* is the part that matters: a naive "now" compared
    against an aware subject is precisely the crash this module exists to
    explain, reintroduced inside the assertion meant to prevent it.
    """
    kind = type(value)
    now = getattr(kind, "now", None)
    if now is None:
        return kind.today()
    return cast("D", now(zone_of(value)))
