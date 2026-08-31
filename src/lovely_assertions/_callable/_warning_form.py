"""What calling the subject warns.

The callable spelling of the warning family, kept next to the raising one because
a reader who knows ``raises`` should be able to guess ``warns`` and be right. The
capture semantics live in the warning package; what is here is the shape.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Self, cast

from lovely_assertions._callable._async_guard import reject_awaitable
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._warnings import (
    WarnedExpect,
    allowed,
    issued_report,
    matching,
    reissue_unmatched,
    warned_report,
)

if TYPE_CHECKING:
    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class WarningFormAssertions(Expect[Callable[..., object]]):
    """What calling the subject warns."""

    __slots__ = ()

    def warns[W: Warning](
        self,
        category: type[W],
        /,
        *,
        occurrences: "Occurrence | None" = None,
        because: str = "",
    ) -> "WarnedExpect[W]":
        """Assert the call issues a warning of ``category``; continue on the warnings.

            expect(legacy).warns(DeprecationWarning).with_message_containing("removed in 3.0")

        The callable-form twin of ``expect_warns``, which is the primary spelling;
        everything about what is captured, what is restored, and what happens to
        warnings of other categories is argued in :mod:`lovely_assertions._warnings`.

        A subclass counts, and ``occurrences`` takes a count constraint
        (``exactly(2)``, ``at_least(1)``) over the warnings of ``category`` alone.
        Without one, the assertion means "at least one".

        The subject becomes the warnings that were issued -- a tuple, because a
        call may issue several where it can raise only one -- typed as
        ``category``, so a warning class that carries fields gets them checked in
        ``.where(...)`` with the type the checker knows.

        **One thing the context-manager form does better**, said here because it is
        visible in the failure message and would otherwise look like a bug.
        ``warnings.warn(..., stacklevel=2)`` reports the *caller* of the function
        that warned, and in this form that caller is the thunk's invocation --
        inside this method. So a failure lists the location as ``_callable.py``
        rather than as the test's own line. ``expect_warns`` has no such frame in
        between and reports the block. This is not fixable from here: the frame the
        warning names is chosen by the code that issued it, and a thunk really is
        called from a different place than a ``with`` body.
        """
        import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

        with warnings.catch_warnings(record=True, action="always") as records:
            returned = self._subject()
        reject_awaitable(returned)
        found = matching(records, category)
        reissue_unmatched(records, category)
        if allowed(len(found), occurrences):
            return WarnedExpect(found)
        return cast(
            "WarnedExpect[W]",
            self._fail_narrowing(
                f"to warn {category.__name__}{warned_report(records, len(found), occurrences)}",
                because,
            ),
        )

    def does_not_warn(self, category: type[Warning] | None = None, /, *, because: str = "") -> Self:
        """Assert the call issues no warning, or none of type ``category``.

        The assertion ``pytest.warns`` has no spelling for at all: it can only say
        that something *did* warn, so "this call must stop deprecating" otherwise
        gets written by hand around a ``catch_warnings`` block.

        The optional argument is a default rather than an overload pair, for the
        reason :meth:`does_not_raise` gives: both forms take the same subject and
        return the same ``Self``. Passing ``None`` explicitly means what it reads
        as -- no filter, so nothing at all may be issued.

        With an argument, warnings of *other* categories are re-issued to the
        project's own filters on the way out rather than swallowed, which is the
        warning-shaped version of ``does_not_raise``'s "exceptions of other types
        travel on untouched". Under ``-W error`` that re-issue raises, at the end
        of the assertion rather than in the middle of the call -- the module
        docstring in :mod:`lovely_assertions._warnings` argues why that is the
        faithful answer rather than the convenient one.
        """
        import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

        unwanted: type[Warning] = Warning if category is None else category
        with warnings.catch_warnings(record=True, action="always") as records:
            returned = self._subject()
        reject_awaitable(returned)
        found = matching(records, unwanted)
        reissue_unmatched(records, unwanted)
        if not found:
            return self
        if category is None:
            return self._fail(f"not to warn, but {issued_report(records, unwanted)}", because)
        return self._fail(
            f"not to warn {category.__name__}, but {issued_report(records, unwanted)}", because
        )
