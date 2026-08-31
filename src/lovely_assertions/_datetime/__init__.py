"""Dates, times and durations.

``_ordered`` explains why these are not routed to :class:`OrderedExpect`: a
date is orderable and is not a number, so ``is_positive`` and ``is_zero`` mean
nothing for it, and a value on a calendar wants a vocabulary of its own --
``is_before``/``is_after`` rather than ``is_less_than``/``is_greater_than``.
``expect(deadline).is_before(now)`` is the whole reason the subject exists.

**The stdlib's own Liskov wart.** ``datetime`` subclasses ``date``, so the type
system cannot stop a ``datetime`` operand reaching a ``date`` subject -- and
comparing the two raises ``TypeError`` in CPython. The same is true of a naive
datetime against an aware one, which is the most common way a real suite crashes
on dates. Both are caught here and reported as what they are: a bare
``TypeError: can't compare offset-naive and offset-aware datetimes`` surfacing
from inside an assertion library reads like the library broke, when in fact it
*is* the finding.

The subject is generic over the concrete date type, so a ``date`` subject takes
``date`` bounds and a ``datetime`` subject takes ``datetime`` bounds -- the
checker refuses statically what the runtime would only discover as a crash.

**Both crashes stay ``TypeError``; neither becomes an assertion failure.** The
rule is the one ``_ordered`` applies to a ``Decimal`` NaN: when two values
cannot be compared at all, there is no verdict to report. "Passed" is untrue and
"failed" is worse -- it would blame the subject for a mistake in the test, and a
runner would present it as a finding about production code. So the comparison is
re-raised as a ``TypeError`` that says *which* side is naive and which is aware,
or which is a date and which a datetime, and what both of them were. The
exception type is the same one CPython raised, so a suite that already catches
``TypeError`` keeps working; only the message improves. Where nothing here can
explain the refusal -- a user's own ``__lt__`` saying no for its own reasons --
the original exception is re-raised untouched rather than dressed up as a date
problem it is not.

**A component no calendar has, and a tolerance no pair of values could satisfy,
are ``ValueError``.** ``has_month(13)`` and ``is_close_to(x, within=-1 day)``
could never pass whatever the subject is, which makes them the same kind of
mistake as ``_ordered._validation.reject_unusable_range``'s inverted bounds: a bug in the
test, raised where it was written. A tolerance of *zero* is kept, because it
describes exactly one acceptable value rather than none -- the same reason
``is_between(x, x)`` is legal where ``is_strictly_between(x, x)`` is not.

**Nothing here imports ``datetime``.** The classes are needed for typing and
never at runtime, so they arrive under ``TYPE_CHECKING`` and the module costs an
importing program nothing. ``_subjects.py`` finds the real types through
``sys.modules`` when it has a value to dispatch, on the same argument that
governs ``Decimal``: a program holding a ``datetime`` has already imported one.
Every assertion therefore works through methods on the value it was handed, and
the two facts this module needs about ``datetime`` that no method exposes -- the
calendar's year bounds, and the names of the days -- are written down as
constants rather than imported.

One file per subject, over three shared layers: how a moment is spelled, what a
caller may not ask, and the ordering and clock catalogues the subjects inherit.
The module carries no ``# --`` banners because its seams are its classes, and
this package is those classes made into files.
"""

from lovely_assertions._datetime._calendar import DateExpect
from lovely_assertions._datetime._duration import TimeDeltaExpect
from lovely_assertions._datetime._instant import DateTimeExpect
from lovely_assertions._datetime._time import TimeExpect
from lovely_assertions._datetime._within import WithinDelta
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "DateExpect",
    "DateTimeExpect",
    "TimeDeltaExpect",
    "TimeExpect",
    "WithinDelta",
]
