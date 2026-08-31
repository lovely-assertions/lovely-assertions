"""What each component of a date or a time is allowed to be.

Stated once, because the same nine numbers are the difference between an
assertion that cannot hold and one that merely does not. A month of 13 is a
mistake in the test; a month of 12 that is not December is a finding.
"""

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: The years the proleptic Gregorian calendar ``datetime`` implements admits --
#: ``datetime.MINYEAR`` and ``datetime.MAXYEAR``, written out because importing
#: them would put the ``datetime`` module on the bill of every program that
#: imports this library. They are fixed by the stdlib, not configuration.
MIN_YEAR = 1


MAX_YEAR = 9999


#: The remaining calendar and clock components, as ``low, high`` pairs. ``day``
#: is bounded by the longest month rather than by the subject's own month: day 31
#: of a February is a claim that *fails*, where day 32 is a claim nobody could
#: ever make.
MONTHS = (1, 12)


DAYS = (1, 31)


HOURS = (0, 23)


MINUTES = (0, 59)


#: 59, not 60: ``datetime`` has no leap seconds, so there is no 23:59:60.
SECONDS = (0, 59)


MICROSECONDS = (0, 999999)


#: ``date.weekday()`` numbers Monday 0 through Sunday 6, so the weekend starts
#: here. Named rather than spelled ``>= 5`` at three call sites.
SATURDAY = 5
