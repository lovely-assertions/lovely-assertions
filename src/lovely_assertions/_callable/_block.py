"""The context-manager form, whose subject arrives after the block.

``with expect_raises(ValueError) as caught:`` binds a handle to something that
does not exist yet, and every assertion on it before the block ends would be
asserting about nothing. Asking early raises rather than answering.

The soft-scope seam is the other half: once a scope has recorded a failure, an
assertion on a subject that was never bound would report a second failure derived
from the first, and the reader would chase the wrong one.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Never, Self, cast, override

from lovely_assertions._callable._raised import RaisedExpect
from lovely_assertions._callable._rendering import rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from types import TracebackType

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Raised from the handle ``expect_raises`` yields, for as long as the block has
#: not finished. Anything else -- a placeholder subject, a bare ``AttributeError``
#: from the unset slot -- would leave the reader guessing.
_NOT_CAUGHT_YET = (
    "the exception is only available after the `with expect_raises(...)` block has finished"
)


class TooEarlyError(RuntimeError):
    """Raised when the handle is asked for its exception before the block ends.

    A ``RuntimeError`` as promised, and a private subclass so that :meth:`CaughtExpect.__exit__`
    can tell its own guard from a failure of the code under test and let it
    travel unreported -- "the exception is only available afterwards" is already
    the whole finding, and wrapping it in "the wrong exception was raised" would
    bury it.
    """

    __slots__ = ()


class CaughtExpect[E: BaseException](RaisedExpect[E]):
    """The handle :func:`expect_raises` yields: a subject that arrives late.

    It is the context manager *and* the subject, so ``as caught`` binds the object
    the assertions are made on. Its ``_subject`` slot stays unset until
    :meth:`__exit__` fills it, which is what makes an access from inside the block
    an error rather than a lie (see :meth:`__getattr__`).
    """

    #: Three attributes beyond the inherited subject, each of them a piece of
    #: state the subject cannot carry: what the block was asked to raise, the
    #: reason to report if it does not, and whether a soft scope has already
    #: collected that failure -- at which point the rest of the chain has nothing
    #: left to say.
    __slots__ = ("_absorbed", "_because", "_expected")

    def __init__(self, expected: type[E], because: str, /) -> None:
        self._expected: type[E] = expected
        self._because: str = because
        self._absorbed: bool = False

    def __getattr__(self, name: str) -> Never:
        """Explain the one attribute that can legitimately be missing.

        ``_subject`` is an unset slot until the block finishes, so ``.subject``,
        ``__repr__`` and every inherited assertion land here when they are reached
        from *inside* the block. Saying why beats the bare ``AttributeError`` the
        slot would raise, and beats a placeholder even more: a placeholder would
        let the assertion run and report on nothing. Every other name is a typo
        and keeps the ``AttributeError`` it deserves.
        """
        if name == "_subject":
            raise TooEarlyError(_NOT_CAUGHT_YET)
        raise AttributeError(name)

    @override
    def _fail(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Self:
        """As ``Expect._fail``, unless the failure has already been reported.

        In a soft scope, ``__exit__`` collects its failure and execution carries
        on into a chain whose subject never existed. ``_ABSORBING`` solves that
        for a returned subject, but the object bound by ``as caught`` cannot be
        swapped, so the absorbing happens here instead: one root cause, one
        message.
        """
        if self._absorbed:
            return self
        return super()._fail(expectation, because, cause=cause)

    @override
    def _fail_narrowing(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Any:
        """As ``Expect._fail_narrowing``, absorbed once the failure has been reported."""
        if self._absorbed:
            return self._subject
        return super()._fail_narrowing(expectation, because, cause=cause)

    def _absorb(self, stand_in: Any, /) -> None:  # noqa: ANN401  (the stand-in is Any by design)
        """Keep what a soft scope handed back, and stop asserting.

        Only reached when ``_fail_narrowing`` collected instead of raising: the
        stand-in it returns is the same one every other narrowing assertion
        hands back, which is how the rest of the chain gets absorbed rather than
        reporting a second failure derived from the first.
        """
        self._subject = cast("E", stand_in)
        self._absorbed = True

    @override
    def where(self, predicate: Callable[[E], bool], /, *, because: str = "") -> Self:
        """As :meth:`RaisedExpect.where`, unless the failure was already reported.

        These three are the assertions that hand the subject to a callable of the
        user's, and the stand-in cannot survive being handed to one: every
        attribute of it is itself, so ``len(error.args)`` in a predicate written
        for a real exception raises ``TypeError`` from inside the soft block. That
        aborts the scope, which then reports *nothing* -- the collected failures
        included. Absorbed means there is nothing left to ask about, so nothing
        is asked.
        """
        if self._absorbed:
            return self
        return super().where(predicate, because=because)

    @override
    def matches(self, predicate: Callable[[E], bool], /, *, because: str = "") -> Self:
        """As ``Expect.matches``, absorbed once the failure has been reported."""
        if self._absorbed:
            return self
        return super().matches(predicate, because=because)

    @override
    def satisfies(self, inspector: Callable[[E], object], /, *, because: str = "") -> Self:
        """As ``Expect.satisfies``, absorbed once the failure has been reported."""
        if self._absorbed:
            return self
        return super().satisfies(inspector, because=because)

    def __enter__(self) -> "RaisedExpect[E]":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: "TracebackType | None",
        /,
    ) -> bool:
        if isinstance(exc, TooEarlyError):
            # Our own guard, tripped inside the block. It says everything there
            # is to say; reporting it as "the wrong exception" would not.
            return False
        if exc is None:
            self._absorb(
                self._fail_narrowing("to be raised, but nothing was raised", self._because)
            )
            return False
        if isinstance(exc, self._expected):
            self._subject = exc
            return True
        if not isinstance(exc, Exception):
            # A KeyboardInterrupt or a SystemExit is not a finding about the
            # block; it is the run being cut short. Let it travel.
            return False
        self._absorb(
            self._fail_narrowing(
                f"to be raised, but {rendered(exc)} was raised instead", self._because, cause=exc
            )
        )
        # Soft scope only: the failure is collected, so suppress the exception
        # rather than let it out to abort a block that is meant to keep going.
        return True
