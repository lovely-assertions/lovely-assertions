"""Refusing a range no subject could satisfy.

One rule, and it is not an assertion: bounds describing nothing are a mistake in
the test rather than a finding about the value, so they raise where they were
written instead of being reported through ``_fail``. That distinction is why this
is a module and not three more lines inside the range assertions, which keep the
library's one shape -- compare, then ``self`` or ``_fail`` -- and where a raise
would read as one more verdict. It is not one, and a soft scope agrees: it
collects failures and lets a ``ValueError`` straight out, which is right, because
a later assertion has nothing to add to a range that was never askable.

NaN bounds are the case worth reading twice. Every comparison against a float NaN
is false whichever way it is written, so ``low <= subject <= high`` with one at
either end is false for every subject there could be: ``is_between`` would fail
on everything and ``is_not_between`` pass on everything, neither answer owing
anything to the value. A test that answers the same whatever the code does is
worse than no test, and the check has to come first to catch it -- ``low > high``
is false for a NaN too, so the inversion test alone would wave the pair through.
A ``Decimal`` NaN refuses the question instead, signalling ``InvalidOperation``
at the first ordering, and the same check spares the caller that crash for a
sentence naming the bound: ``!=`` is the one comparison a NaN of either kind
answers. Both bounds then go into the message through the package's renderer, for
the reason any caller's value does: an error raised on the way out of an error
message explains nothing.

Two neighbouring refusals are deliberately elsewhere. An exclusive range between
a bound and itself is empty and raises, but it belongs to
:meth:`OrderedExpect.is_strictly_between` alone -- ``is_between(x, x)`` is a
perfectly good range holding exactly one value, so the rule is that assertion's
and not this one's. Bounds that cannot be compared *with each other* are not
checked at all, because both parameters are typed ``T`` and a mismatched pair is
something the checkers refuse before it can run. The temporal subject cannot lean
on that -- an aware and a naive ``datetime`` are one type and still refuse to
compare -- and so keeps this same rule with a guard of its own that catches the
``TypeError`` and names which side was which.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered._protocol import Ordered
from lovely_assertions._ordered._rendering import is_nan, rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def reject_unusable_range(low: Ordered, high: Ordered, /) -> None:
    """Raise ``ValueError`` for bounds that describe no range at all.

    Checked before the subject is looked at, on purpose: bounds no value could
    satisfy are a bug in the test, and a subject that happened to fail would hide
    it behind a message blaming the value.
    """
    if is_nan(low) or is_nan(high):
        raise ValueError(
            "range bounds must not be NaN, got " + rendered(low) + " to " + rendered(high)
        )
    if low > high:
        raise ValueError(
            "range is inverted: low " + rendered(low) + " exceeds high " + rendered(high)
        )
