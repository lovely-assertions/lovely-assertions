"""Occurrence constraints -- how many times counts as enough.

The point of use is::

    expect(log).contains("retrying", occurrences=exactly(3))

and the thing it replaces is::

    expect(log.count("retrying")).is_equal_to(3)

The second asserts the same fact and reports almost none of it. Its subject is an
integer, so the failure reads ``Expected log.count('retrying') to equal 3, but
was 2``: the name of the thing under test is gone, the haystack is gone, and the
needle survives only because it happens to sit inside the recovered expression.
The first keeps all three -- ``Expected log to contain 'retrying' exactly 3
times, but found 2.``

That sentence is the whole design brief. :meth:`Occurrence.describe` returns its
middle -- ``"exactly 3 times"`` -- and has to *read* there, which is why these
objects count in English rather than printing an operator, and why ``1`` gets a
singular. "exactly 1 times" is the tell that nobody read the output of the thing
whose entire job is to be read.

**They are values.** Immutable, hashable, ``__slots__``-ed, equal when they were
built the same way, and with a ``repr`` that is the call that made them. A user
is expected to build one at module scope and reuse it across a suite, which only
works if a test cannot quietly change it -- so ``__setattr__`` refuses. Slots
alone would not do: they stop a *new* attribute appearing and do nothing about
the one that is already there.

**A constraint every count satisfies, or one no count satisfies, is a bug in the
test.** Same rule as a variadic assertion given nothing to look for, and the same
reasoning: it either asserts nothing or could never pass, and neither is a
finding about a subject, so it raises :class:`ValueError` where it is written
rather than being reported as a failure. A number of occurrences is a natural
number -- ``str.count`` and ``len`` do not return -1 -- which settles the
boundary cases:

===================  ================================  ==============
call                 accepts                           verdict
===================  ================================  ==============
``exactly(0)``       0 only -- "it never appears"      kept
``at_most(0)``       0 only -- the same claim, softer  kept
``less_than(1)``     0 only -- and again               kept
``more_than(0)``     1, 2, 3, ... -- "it appears"      kept
``at_least(1)``      1, 2, 3, ... -- the same again    kept
``at_least(0)``      every count there is              ``ValueError``
``less_than(0)``     no count there is                 ``ValueError``
any factory, ``-1``  no count there is                 ``ValueError``
===================  ================================  ==============

Three spellings of "it never appears" are kept rather than collapsed into one,
and so are two spellings of "it appears", because the sentence they land in
differs and the caller picked the one that reads best where they wrote it. That
is also why ``at_least(3)`` and ``more_than(2)`` are not equal despite accepting
exactly the same counts: they disagree about :meth:`Occurrence.describe`, which
is observable behaviour, and normalising them would print a phrase the caller did
not write. The message is the product, so nothing quietly rewords it.
"""

from typing import ClassVar, Final, Never, Protocol, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "Occurrence",
    "at_least",
    "at_most",
    "exactly",
    "less_than",
    "more_than",
    "once",
    "twice",
]

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

#: Refused so that ``once`` and ``twice`` -- module-level values a whole suite
#: shares -- cannot be re-pointed by one test that ran first.
_IMMUTABLE: Final = "occurrence constraints are immutable values; cannot change "


class Occurrence(Protocol):
    """How many times something has to appear for an assertion to hold.

    Structural, so a user can add their own by writing two methods::

        class Between:
            __slots__ = ("_high", "_low")

            def __init__(self, low: int, high: int) -> None:
                self._low, self._high = low, high

            def allows(self, count: int, /) -> bool:
                return self._low <= count <= self._high

            def describe(self) -> str:
                return "between " + str(self._low) + " and " + str(self._high) + " times"

    Deliberately **not** ``runtime_checkable``. ``isinstance`` against a protocol
    asks only whether the two *names* exist -- ``_formatters._check`` documents
    the same trap -- so it would accept an object whose ``allows`` is a ``bool``
    and hand back a guarantee it cannot keep. Nothing here needs the check
    either: a constraint is *used* the moment it is passed, so a wrong object
    raises ``TypeError`` at the call site, naming the actual problem in the
    actual place. :class:`~lovely_assertions.ValueFormatter` is checked at
    runtime because its situation is the opposite one -- it is registered now and
    called much later, and a formatter that silently declines everything for the
    life of the process has no other moment at which to be caught.
    """

    __slots__ = ()

    def allows(self, count: int, /) -> bool:
        """Whether ``count`` occurrences satisfy this constraint.

        ``count`` is a number of occurrences and is therefore never negative. The
        shipped constraints do not check that: the check would be paid for on
        every *passing* assertion to catch something that cannot happen, and the
        factories already refuse a negative bound at the point it is written.
        """
        ...

    def describe(self) -> str:
        """This constraint as it appears inside a failure message.

        ``"exactly 3 times"``, ``"at least 2 times"``, ``"at most 1 time"`` -- a
        fragment that has to fit between what was looked for and what was found::

            Expected log to contain 'retrying' <describe()>, but found 2.
        """
        ...


#: Counts that read better as words than as numerals, in the phrases where they
#: do. ``_TAKES_ORDINALS`` excludes ``less than`` on purpose -- see
#: :meth:`_Constraint.describe`.
_ORDINALS = {1: "once", 2: "twice"}
_TAKES_ORDINALS = frozenset({"exactly", "at least", "at most", "more than"})


class _Constraint:
    """Everything the five shipped constraints share -- which is not the comparison.

    ``allows`` lives on each subclass, because the comparison *is* the subclass.
    What is shared is what makes these objects values: construction, equality,
    hashing, the ``repr`` that spells the call that built them, and the
    counting-in-English behind :meth:`describe`.

    Immutability is enforced rather than merely intended. ``object.__setattr__``
    still gets through, as it does for a frozen dataclass, but nobody reaches for
    that by accident -- and the accident this guards against is a test mutating
    the module-level ``once`` that every other test is reading.
    """

    __slots__ = ("_count",)

    #: Declared, never assigned here: a class variable of this name would collide
    #: with the slot of the same name.
    _count: int

    #: The factory that builds this constraint, so ``repr`` can spell the call.
    _factory: ClassVar[str]

    #: The words :meth:`describe` opens with. Kept as its own string rather than
    #: derived from ``_factory`` by swapping underscores for spaces: the
    #: identifier is a name and the phrase is prose, and the day one wants to
    #: change without the other, the derivation would have to be unpicked first.
    _phrase: ClassVar[str]

    def __init__(self, count: int, /) -> None:
        # Through `object`, because this class's own `__setattr__` refuses.
        object.__setattr__(self, "_count", count)

    @override
    def __repr__(self) -> str:
        return f"{self._factory}({self._count})"

    @override
    def __eq__(self, other: object) -> bool:
        """Equal when built the same way: same factory, same count.

        ``at_least(3) == more_than(2)`` is **False**, though the two accept
        exactly the same counts. They disagree about :meth:`describe`, which is
        behaviour a caller can observe in a failure message, so they are not the
        same value (see the module docstring).
        """
        if not isinstance(other, _Constraint):
            return NotImplemented
        return type(other) is type(self) and self._count == other._count

    @override
    def __hash__(self) -> int:
        return hash((type(self), self._count))

    @override
    def __setattr__(self, name: str, _value: object, /) -> Never:
        raise AttributeError(_IMMUTABLE + type(self).__name__ + "." + name)

    @override
    def __delattr__(self, name: str, /) -> Never:
        raise AttributeError(_IMMUTABLE + type(self).__name__ + "." + name)

    def describe(self) -> str:
        """The constraint as a fragment of a failure message. Failure path only.

        Counts of one and two read as words -- "exactly once", "at least twice" --
        because that is how the phrases are said, and "at least 1 time" is stilted
        in the one place this text appears. Everything else goes through
        ``count_of``, the library's single answer to "1 item" against "4 items"
        (``_text``), so occurrences pluralise the way every other message does.

        ``less_than`` is left numeric: "less than once" is not English, and the
        alternative of rendering it "never" produces "Expected log to contain 'x'
        never, but found 2", which is not a sentence either. A count constraint
        that means "never" is better spelled ``does_not_contain``.
        """
        word = _ORDINALS.get(self._count) if self._phrase in _TAKES_ORDINALS else None
        return self._phrase + " " + (word or count_of(self._count, "time"))


class _Exactly(_Constraint):
    """``count == n``."""

    __slots__ = ()
    _factory = "exactly"
    _phrase = "exactly"

    def allows(self, count: int, /) -> bool:
        return count == self._count


class _AtLeast(_Constraint):
    """``count >= n``."""

    __slots__ = ()
    _factory = "at_least"
    _phrase = "at least"

    def allows(self, count: int, /) -> bool:
        return count >= self._count


class _AtMost(_Constraint):
    """``count <= n``."""

    __slots__ = ()
    _factory = "at_most"
    _phrase = "at most"

    def allows(self, count: int, /) -> bool:
        return count <= self._count


class _MoreThan(_Constraint):
    """``count > n``."""

    __slots__ = ()
    _factory = "more_than"
    _phrase = "more than"

    def allows(self, count: int, /) -> bool:
        return count > self._count


class _LessThan(_Constraint):
    """``count < n``."""

    __slots__ = ()
    _factory = "less_than"
    _phrase = "less than"

    def allows(self, count: int, /) -> bool:
        return count < self._count


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
    return _Exactly(count)


def at_least(count: int, /) -> Occurrence:
    """Require ``count`` occurrences or more.

    ``at_least(0)`` raises :class:`ValueError`. Every possible count is zero or
    more, so the constraint holds unconditionally and the assertion carrying it
    could never fail. ``more_than(0)`` is what "it appears" is spelled. A
    negative ``count`` raises :class:`ValueError` too.
    """
    _reject_negative(count)
    if count == 0:
        raise ValueError(_VACUOUS_AT_LEAST)
    return _AtLeast(count)


def at_most(count: int, /) -> Occurrence:
    """Require ``count`` occurrences or fewer.

    ``at_most(0)`` is kept: only zero occurrences are zero or fewer, so it is
    another way of writing "it never appears". A negative ``count`` raises
    :class:`ValueError`.
    """
    _reject_negative(count)
    return _AtMost(count)


def more_than(count: int, /) -> Occurrence:
    """Require strictly more than ``count`` occurrences.

    ``more_than(0)`` is kept, and is the useful lower bound with no upper limit:
    "it appears". It accepts exactly what ``at_least(1)`` accepts and is not
    equal to it, because the two describe themselves differently. A negative
    ``count`` raises :class:`ValueError`.
    """
    _reject_negative(count)
    return _MoreThan(count)


def less_than(count: int, /) -> Occurrence:
    """Require strictly fewer than ``count`` occurrences.

    ``less_than(1)`` is kept -- only zero is fewer than one, so it is the third
    spelling of "it never appears". ``less_than(0)`` raises
    :class:`ValueError`: no count is below zero, so nothing could satisfy it,
    and a negative ``count`` is refused for the same reason.
    """
    _reject_negative(count)
    if count == 0:
        raise ValueError(_IMPOSSIBLE_LESS_THAN)
    return _LessThan(count)


#: ``exactly(1)``, for the reading. Built here so a suite that wants it shares
#: one object rather than allocating a fresh one per assertion.
once: Occurrence = exactly(1)

#: ``exactly(2)``, likewise.
twice: Occurrence = exactly(2)
