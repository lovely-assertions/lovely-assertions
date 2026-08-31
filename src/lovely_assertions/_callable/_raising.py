"""What calling the subject raises.

The question this subject exists for. Both directions are here, and they are not
each other's negation in the message: "raised nothing" and "raised the wrong
thing" are different findings, and one of them names what it got instead.
"""

from collections.abc import Callable
from typing import Self, cast

from lovely_assertions._callable._async_guard import reject_awaitable
from lovely_assertions._callable._raised import RaisedExpect
from lovely_assertions._callable._rendering import rendered
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class RaisingAssertions(Expect[Callable[..., object]]):
    """What calling the subject raises."""

    __slots__ = ()

    def raises[E: BaseException](
        self, exception_type: type[E], /, *, because: str = ""
    ) -> "RaisedExpect[E]":
        """Assert the call raises ``exception_type`` or a subclass; continue on the exception.

        The exception becomes the new subject, so ``.which``, ``.and_`` and every
        generic assertion apply to it. When the call raises something else, the
        failure is raised *from* that exception: its traceback is what will
        actually explain the test, and losing it would be the expensive half of
        the report.

        A ``KeyboardInterrupt`` or a ``SystemExit`` that was not asked for is left
        to travel; name one as ``exception_type`` and it is caught like anything
        else, because then it is the subject of the test rather than the run being
        cut short. Handing over an ``async def`` raises :class:`TypeError` instead
        of reporting a failure -- calling one returns a coroutine without running a
        line of its body, so there was never anything to raise.

        :meth:`raises_exactly` is the same assertion with subclasses excluded.
        """
        try:
            returned = self._subject()
        except (exception_type, Exception) as actual:
            # The tuple is "what was asked for" plus "what an ordinary bug looks
            # like". Everything outside it -- KeyboardInterrupt, SystemExit --
            # is the interpreter talking and is left to travel.
            if isinstance(actual, exception_type):
                return RaisedExpect(actual)
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise {exception_type.__name__}, but raised {rendered(actual)}",
                    because,
                    cause=actual,
                ),
            )
        else:
            reject_awaitable(returned)
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise {exception_type.__name__}, but nothing was raised"
                    f" (the call returned {rendered(returned)})",
                    because,
                ),
            )

    def raises_exactly[E: BaseException](
        self, exception_type: type[E], /, *, because: str = ""
    ) -> "RaisedExpect[E]":
        """Assert the call raises ``exception_type`` itself -- a subclass does not count.

        The test is on the type object, so ``raises_exactly(Exception)`` is not
        satisfied by a ``ValueError``. Reach for :meth:`raises` unless the point of
        the test is *which* exception the code chose; everything else is the same,
        including the exception becoming the new subject and a wrong-type failure
        being raised from the real exception so its traceback survives.
        """
        try:
            returned = self._subject()
        except (exception_type, Exception) as actual:
            # The type is read into a name first, as `is_exactly_instance_of`
            # does: comparing the type object is what "exactly" means, and it
            # leaves the cast below stating what neither checker can derive.
            actual_type = type(actual)
            if actual_type is exception_type:
                return RaisedExpect(cast("E", actual))
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise exactly {exception_type.__name__}, but raised {rendered(actual)}",
                    because,
                    cause=actual,
                ),
            )
        else:
            reject_awaitable(returned)
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise exactly {exception_type.__name__}, but nothing was raised"
                    f" (the call returned {rendered(returned)})",
                    because,
                ),
            )

    def does_not_raise(
        self, exception_type: type[BaseException] | None = None, /, *, because: str = ""
    ) -> Self:
        """Assert the call raises nothing, or nothing of type ``exception_type``.

        The optional argument is a default rather than an overload pair: both
        forms take the same subject and return the same ``Self``, so overloads
        would buy one thing only -- rejecting a literal ``None`` -- at the price
        of a doubled signature. Passing ``None`` explicitly means what it reads
        as: no filter, so nothing may escape.

        With no argument the assertion catches ``Exception``, not
        ``BaseException``: a ``KeyboardInterrupt`` or a ``SystemExit`` crossing
        the call is the interpreter's business, and reporting "it raised" for a
        Ctrl-C would swallow the interruption. Name one to test for it.

        With an argument, exceptions of *other* types travel on untouched -- the
        assertion is about that type, and burying an unrelated error under it
        would hide the more interesting failure.
        """
        unwanted: type[BaseException] = Exception if exception_type is None else exception_type
        try:
            returned = self._subject()
        except unwanted as actual:
            if exception_type is None:
                return self._fail(
                    f"not to raise, but raised {rendered(actual)}", because, cause=actual
                )
            return self._fail(
                f"not to raise {exception_type.__name__}, but raised {rendered(actual)}",
                because,
                cause=actual,
            )
        else:
            reject_awaitable(returned)
            return self
