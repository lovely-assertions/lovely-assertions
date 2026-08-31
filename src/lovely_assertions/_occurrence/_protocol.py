"""The shape a count constraint has to have, and nothing that has it.

:class:`Occurrence` is all of ``occurrences=`` that is published: ``allows``,
which decides, and ``describe``, which is how the bound reads inside the sentence
a failure prints. It sits apart from everything that satisfies it because it is
the one name in this package a caller refers to rather than calls -- annotating a
helper that passes a constraint along, or as the pair of methods a class of
theirs has to grow -- and a requirement is easiest to read in a file that holds
no implementation to mistake for it. Nothing is imported here past ``typing`` and
the traceback helper every module in the package shares.

The constraints the library ships do not import it either. They satisfy it
structurally, on the same terms a stranger's class does, and the only place those
implementations are held to it is the return annotation on each factory -- so a
protocol asking for something they had stopped providing fails a type check
inside this library rather than in somebody else's test.
"""

from typing import Protocol

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


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
    asks only whether the two *names* exist -- ``_formatters._protocol.check``
    documents the same trap -- so it would accept an object whose ``allows`` is a
    ``bool`` and hand back a guarantee it cannot keep. Nothing here needs the
    check either: a constraint is *used* the moment it is passed, so a wrong
    object raises where it was written, naming the actual problem in the actual
    place -- ``AttributeError`` for a method that is missing, ``TypeError`` for
    one that is there but not callable. :class:`~lovely_assertions.ValueFormatter`
    is checked at runtime because its situation is the opposite one -- it is
    registered now and called much later, and a formatter that silently declines
    everything for the life of the process has no other moment at which to be
    caught.
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

        ``"exactly 3 times"``, ``"at least twice"``, ``"at most once"`` -- a
        fragment that has to fit between what was looked for and what was found::

            Expected log to contain 'retrying' <describe()>, but found 2.
        """
        ...
