"""How a count is written, and which counts are refused.

Everything this package hands a caller except the protocol itself: the five
factories a test calls, and the two constraints named for the counts that read
better as words than as numerals. The classes underneath are values -- a
comparison, an equality, a ``repr``, a phrase -- and none of them has an opinion
about whether the bound it was handed made sense. That question belongs at the
entrance, because the entrance is where a reader typed the number.

Two bounds are refused although nothing about them is ill-formed.
``at_least(0)`` accepts every count there is, so an assertion carrying it could
never fail; ``less_than(0)`` accepts none, so one carrying it could never pass.
Neither states anything about a subject, so neither is reported as a failure:
:class:`ValueError` is raised where the bound was written, and it names the
spelling that was meant, since somebody who typed one of those meant something.
A negative count is refused by every factory for the same reason -- ``str.count``
and ``len`` do not return -1, so a negative bound is a typo rather than a claim.
Every other spelling is kept, the three that say "it never appears" and the two
that say "it appears" included: which of them reads best depends on the sentence
it lands in, and collapsing them would print a phrase the caller did not write.

Refusing here is what lets the comparison never check. A constraint is asked
``allows`` once per comparison, on the passing path, and looks only at the count
in front of it -- affordable because no count reaches a constraint except through
a call in this file, ``once`` and ``twice`` included, being ``exactly(1)`` and
``exactly(2)`` rather than a sixth kind of constraint. Constructing one of the
classes directly would walk past the guard, which is one reason they stay behind
the factories.

The return type is :class:`Occurrence` throughout and never the class actually
built. The five classes are an implementation detail that a return annotation
would promote to surface, and the protocol is also what a caller's own constraint
satisfies, so a shipped bound and a hand-written one are one type to a checker.
"""

from typing import Final

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._occurrence._constraint import AtLeast, AtMost, Exactly, LessThan, MoreThan
from lovely_assertions._occurrence._protocol import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: A count below zero cannot describe any subject, so a constraint written
#: against one is a typo, not a claim.
_NEGATIVE_COUNT: Final = "an occurrence count cannot be negative, but was "


#: ``at_least(0)`` is the assertion that cannot fail: every count is zero or
#: more. The suggestion matters as much as the refusal -- somebody who wrote it
#: meant something, and it was almost certainly this.
_VACUOUS_AT_LEAST: Final = (
    "at_least(0) holds for every count, so it asserts nothing;"
    " use more_than(0) for 'it appears', or drop the constraint entirely"
)


#: ``less_than(0)`` is its mirror: no count is below zero, so no subject could
#: ever satisfy it.
_IMPOSSIBLE_LESS_THAN: Final = (
    "less_than(0) holds for no count, so it can never pass;"
    " use exactly(0), at_most(0) or less_than(1) for 'it never appears'"
)


def _reject_negative(count: int, /) -> None:
    """Refuse a count that could not have come from counting anything."""
    if count < 0:
        raise ValueError(_NEGATIVE_COUNT + str(count))


def exactly(count: int, /) -> Occurrence:
    """Require exactly ``count`` occurrences.

    ``exactly(0)`` is kept: only zero occurrences equal zero, so it says "it
    never appears", which is something a test genuinely wants to say.
    ``at_most(0)`` and ``less_than(1)`` say it too, and all three survive --
    which of them reads best depends on the sentence around it.

    A negative ``count`` raises :class:`ValueError`, here and in every other
    factory: nothing is counted a negative number of times, so such a bound is a
    typo rather than a claim.
    """
    _reject_negative(count)
    return Exactly(count)


def at_least(count: int, /) -> Occurrence:
    """Require ``count`` occurrences or more.

    ``at_least(0)`` raises :class:`ValueError`. Every possible count is zero or
    more, so the constraint holds unconditionally and the assertion carrying it
    could never fail. ``more_than(0)`` is how "it appears" is spelled. A
    negative ``count`` raises :class:`ValueError` too.
    """
    _reject_negative(count)
    if count == 0:
        raise ValueError(_VACUOUS_AT_LEAST)
    return AtLeast(count)


def at_most(count: int, /) -> Occurrence:
    """Require ``count`` occurrences or fewer.

    ``at_most(0)`` is kept: only zero occurrences are zero or fewer, so it is
    another way of writing "it never appears". A negative ``count`` raises
    :class:`ValueError`.
    """
    _reject_negative(count)
    return AtMost(count)


def more_than(count: int, /) -> Occurrence:
    """Require strictly more than ``count`` occurrences.

    ``more_than(0)`` is kept, and is the useful lower bound with no upper limit:
    "it appears". It accepts exactly what ``at_least(1)`` accepts and is not
    equal to it, because the two describe themselves differently. A negative
    ``count`` raises :class:`ValueError`.
    """
    _reject_negative(count)
    return MoreThan(count)


def less_than(count: int, /) -> Occurrence:
    """Require strictly fewer than ``count`` occurrences.

    ``less_than(1)`` is kept -- only zero is fewer than one, so it is the third
    spelling of "it never appears". ``less_than(0)`` raises
    :class:`ValueError`: no count is below zero, so nothing could satisfy it. A
    negative ``count`` raises :class:`ValueError` too, and is caught first, so
    ``less_than(-1)`` is reported as the typo it is rather than as a bound
    nothing could meet.
    """
    _reject_negative(count)
    if count == 0:
        raise ValueError(_IMPOSSIBLE_LESS_THAN)
    return LessThan(count)


#: ``exactly(1)``, for the reading. Built here so a suite that wants it shares
#: one object rather than allocating a fresh one per assertion.
once: Occurrence = exactly(1)


#: ``exactly(2)``, likewise.
twice: Occurrence = exactly(2)
