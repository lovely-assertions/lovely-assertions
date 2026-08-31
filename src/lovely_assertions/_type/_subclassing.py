"""Whether one class counts as another, which is more than inheritance.

``issubclass`` is the operator, and it says yes in three genuinely different
ways: to a class asked about itself, to a class that really does inherit, and to
a virtual subclass -- ``ABCMeta.register``, or a ``__subclasshook__`` matching
structurally -- that inherits nothing at all. Only the first two are visible in
the source. So the check is one line and the work is the sentence after it: what
the class does inherit from when the answer was no, and which of the three ways
the answer held when it was an unwelcome yes. Both explanations live in
:mod:`lovely_assertions._type._hierarchy` and run once an assertion has already
failed.

:meth:`TypeExpect.implements` calls the same ``issubclass``, so the seam here is
vocabulary rather than operator. A failed subclass check is explained in base
classes; a failed conformance check is explained in the members the class never
defined. Neither explanation answers the other question, and one assertion
carrying both would hand the reader the wrong half most of the time.
"""

from typing import Self

from lovely_assertions._callable import CallableExpect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._type._hierarchy import bases_of, why_subclass
from lovely_assertions._type._naming import named
from lovely_assertions._type._protocols import checked_issubclass

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SubclassAssertions(CallableExpect):
    """Whether a class counts as another, and what it inherits when it does not."""

    __slots__ = ()

    # -- inheritance -------------------------------------------------------
    def is_subclass_of(self, other: type[object], /, *, because: str = "") -> Self:
        """Assert the subject is a subclass of ``other``.

        ``issubclass`` semantics exactly, which is to say more than inheritance:
        it is reflexive (a class is a subclass of itself), and it counts virtual
        subclasses registered with ``ABCMeta.register`` as well as structural
        matches made by a ``__subclasshook__``. The failure names what the class
        does inherit from, so the reader is not left to go and look.

        One type per call, never a tuple, which is the one place the signature
        is narrower than the builtin: the checker refuses
        ``expect(C).is_subclass_of((A, B))`` that ``issubclass`` would have
        taken. Two calls say which one failed; a tuple would not. Returns the
        subject, so the call chains.

        Raises ``TypeError``, not a failure, when ``other`` is a protocol nothing
        can be checked against at runtime -- see :meth:`implements`, which
        explains both refusals and names the fix in the message.
        """
        if checked_issubclass(self._subject, other):
            return self
        return self._fail(
            f"to be a subclass of {named(other)}, but it inherits from {bases_of(self._subject)}",
            because,
        )

    def is_not_subclass_of(self, other: type[object], /, *, because: str = "") -> Self:
        """Assert the subject is not a subclass of ``other``.

        The exact complement of :meth:`is_subclass_of`, which means a class fails
        this against itself. The failure says which of the three ways it holds --
        the class itself, an ordinary base class, or a virtual subclass that
        inherits nothing -- because only the first two are visible in the source.
        Returns the subject, so the call chains, and raises ``TypeError`` on an
        uncheckable protocol exactly as :meth:`is_subclass_of` does.
        """
        if not checked_issubclass(self._subject, other):
            return self
        return self._fail(
            f"not to be a subclass of {named(other)}, but {why_subclass(self._subject, other)}",
            because,
        )
