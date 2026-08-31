"""The five constraints the shipped factories return -- one class per comparison.

An instance holds one number and nothing else; its class holds the comparison,
the factory name the ``repr`` spells, and the phrase :meth:`_Constraint.describe`
opens with. One class per comparison rather than one class parameterised by one:
a subclass here is a comparison and two class-level strings, so parameterising
would save nothing and would move the kind of a constraint out of the type and
into the instance, where equality would have to compare stored callables instead
of asking ``type(other) is type(self)``.

Which is what equality means here: how a constraint was written, not what it
accepts. ``at_least(3)`` and ``more_than(2)`` admit exactly the same counts and
are still different values, and comparing them by those counts is not an option
that was weighed and dropped -- there is nothing to compare, since the accepted
counts are unbounded and a constraint answers one at a time. What can be compared
is how the two say themselves, and that phrase is read by a human in a failure
message, so treating the pair as one value would print words the caller never
wrote.

Nothing here names :class:`~lovely_assertions.Occurrence`, and that is not an
oversight. The protocol is structural, so these classes satisfy it exactly the
way a caller's own class does, by having the two methods; an import edge would
suggest they were the implementation it was written around rather than the five
that happen to ship. Refusals are absent for a related reason: a constructor
takes the count it is handed and asks nothing about it, because a constraint is
built through a factory, and a bound that could not describe any subject is
turned away there -- once, where a reader typed it.

Callers ask ``allows`` first and reach for ``describe`` only once the answer has
gone against the subject, so the counting in English, and the pluralisation it
borrows from :mod:`lovely_assertions._text`, cost a passing assertion nothing.
The class names carry no leading underscore because
:mod:`lovely_assertions._occurrence._factories` reads them across a file
boundary; the package exports the protocol and the factories, and neither these
nor this module.
"""

from typing import ClassVar, Final, Never, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Refused so that ``once`` and ``twice`` -- module-level values a whole suite
#: shares -- cannot be re-pointed by one test that ran first.
_IMMUTABLE: Final = "occurrence constraints are immutable values; cannot change "


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


class Exactly(_Constraint):
    """``count == n``."""

    __slots__ = ()
    _factory = "exactly"
    _phrase = "exactly"

    def allows(self, count: int, /) -> bool:
        return count == self._count


class AtLeast(_Constraint):
    """``count >= n``."""

    __slots__ = ()
    _factory = "at_least"
    _phrase = "at least"

    def allows(self, count: int, /) -> bool:
        return count >= self._count


class AtMost(_Constraint):
    """``count <= n``."""

    __slots__ = ()
    _factory = "at_most"
    _phrase = "at most"

    def allows(self, count: int, /) -> bool:
        return count <= self._count


class MoreThan(_Constraint):
    """``count > n``."""

    __slots__ = ()
    _factory = "more_than"
    _phrase = "more than"

    def allows(self, count: int, /) -> bool:
        return count > self._count


class LessThan(_Constraint):
    """``count < n``."""

    __slots__ = ()
    _factory = "less_than"
    _phrase = "less than"

    def allows(self, count: int, /) -> bool:
        return count < self._count
