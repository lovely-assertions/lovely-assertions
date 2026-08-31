"""Satisfying a protocol, and what a class was short of.

Both assertions run the same ``issubclass`` the inheritance seam runs -- there is
only the one structural check to run -- so the line between the two families is
drawn by the question rather than by the machinery underneath. It earns the line
in the failures: conformance names the members, inheritance names the base
classes, and one message written to serve both would name neither well.

Neither assertion here reports a failure when the protocol cannot be checked at
runtime at all. The shared check raises ``TypeError`` instead, and letting it
through is the point -- nothing was established about the class, so a reported
"does not implement" would be a finding no check ever made. The protocol helpers
hold both refusals and the fix each one names.
"""

from typing import Self

from lovely_assertions._callable import CallableExpect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._type._naming import named
from lovely_assertions._type._protocols import checked_issubclass, provided, shortfall

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ConformanceAssertions(CallableExpect):
    """Whether a class satisfies a protocol, and which members decide it."""

    __slots__ = ()

    # -- protocols ---------------------------------------------------------
    def implements(self, protocol: type[object], /, *, because: str = "") -> Self:
        """Assert the class satisfies ``protocol``.

            @runtime_checkable
            class Closeable(Protocol):
                def close(self) -> None: ...

            expect(Session).implements(Closeable)

        The runtime question is ``issubclass``, the same one
        :meth:`is_subclass_of` asks -- Python has one structural-conformance
        operator and this is it. The two are separate names because they read
        differently and fail differently: this one lists the members the class
        does not define, which is what a reader of a conformance failure needs
        and what an inheritance failure has nothing to say about. An abstract
        base class works here too, and lists its abstract methods the same way.

        Two protocols cannot be checked at all, and both raise ``TypeError``
        rather than reporting a failure, because nothing about the subject was
        established: one that is not ``@runtime_checkable``, and a *data*
        protocol -- one with non-method members -- which cannot be checked
        against a class because its members live on instances. Each refusal
        names the fix.

        What ``issubclass`` checks for a method protocol is that the members
        exist, not that their signatures match. A checker is what verifies
        signatures; this verifies that the object in front of you at runtime is
        the one the checker was looking at. Returns the subject, so the call
        chains.
        """
        if checked_issubclass(self._subject, protocol):
            return self
        return self._fail(
            f"to implement {named(protocol)}, but {shortfall(self._subject, protocol)}",
            because,
        )

    def does_not_implement(self, protocol: type[object], /, *, because: str = "") -> Self:
        """Assert the class does not satisfy ``protocol``.

        The complement of :meth:`implements`, and the one an accidental
        conformance wants: a class that grew a ``__len__`` and quietly became a
        ``Sized`` is a change no signature records. The failure lists the members
        it turned out to provide, since the reader's next move is to find where
        one of them came from; where it provides none -- a class registered with
        ``ABCMeta.register`` defines nothing and still conforms -- the message
        says that instead of listing members that were never written.

        Raises ``TypeError`` on the two protocols that cannot be checked at all,
        for the reason :meth:`implements` gives. Returns the subject, so the call
        chains.
        """
        if not checked_issubclass(self._subject, protocol):
            return self
        return self._fail(
            f"not to implement {named(protocol)}, but {provided(self._subject, protocol)}",
            because,
        )
