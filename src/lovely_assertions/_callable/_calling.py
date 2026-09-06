"""The callable subject: what calling it does.

Two seams, and they are not symmetric. What a call *raises* is the question this
subject exists for; what it *warns* is the same question asked of the warning
machinery, and is spelled the same way so a reader who knows one knows the other.
"""

from collections.abc import Callable
from typing import Self, cast

from lovely_assertions._callable._raising import RaisingAssertions
from lovely_assertions._callable._rendering import rendered
from lovely_assertions._callable._warning_form import WarningFormAssertions
from lovely_assertions._core import Expect, Found
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class CallableExpect[R = object](
    RaisingAssertions,
    WarningFormAssertions,
    Expect[Callable[..., object]],
):
    """Assertions about what calling the subject does.

    The subject is normally a zero-argument thunk -- ``lambda: parse("x")`` --
    because the assertion has to do the calling itself. A callable that needs
    arguments is wrapped in one; a generator function needs draining as well, and
    ``expect(lambda: list(rows()))`` is how: calling a generator function only
    builds a generator, so nothing it would raise has happened yet.

    Every assertion here calls the subject exactly once, so a chain of them calls
    it once per link -- which is what a reader wants from a thunk and what makes a
    callable with side effects worth wrapping in a fresh lambda each time.

    **``R`` is what the subject returns, and it exists for one assertion.** The
    class subject is ``Callable[..., object]`` and stays that way -- a callable
    taking arguments has to be wrapped in a thunk before anything here can call it,
    and the wrapper's parameters are nobody's business. What the parameter carries
    is the *return* type, which ``expect()`` reads off a zero-argument callable and
    which :meth:`returns` then hands on. Without it ``.returns().subject`` would be
    an ``object`` for a thunk whose type is perfectly well known, which is a hole
    in the narrowing this library claims rather than a limitation of it.

    It defaults to ``object``, so every existing spelling of the name means what it
    always did and a callable taking arguments still gets ``CallableExpect``.
    """

    __slots__ = ()

    def returns(self, *, because: str = "") -> "Found[Self, R]":
        """Assert the call returns rather than raising, and continue on the result.

            expect(lambda: parse("3")).returns().which.is_equal_to(3)

        ``.which`` descends into the returned value, ``.and_`` goes back to the
        callable, and ``.subject`` hands the value over raw -- typed as what the
        thunk returns rather than as ``object``, which is the whole of why this
        exists. As an assertion it says little that
        ``expect(parse("3")).is_equal_to(3)`` does not; reach for it where the
        *call* is what the test is about, and for the plain form otherwise.

        Catches ``Exception`` and not ``BaseException``, exactly as
        :meth:`~lovely_assertions._callable._raising.RaisingAssertions.does_not_raise`
        does and for the same reason: a ``KeyboardInterrupt`` crossing the call is
        the interpreter's business.
        """
        try:
            returned = self._subject()
        except Exception as actual:
            return cast(
                "Found[Self, R]",
                self._fail_narrowing(
                    f"to return, but raised {rendered(actual)}", because, cause=actual
                ),
            )
        return Found(self, cast("R", returned))
