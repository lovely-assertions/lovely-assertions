"""Containment once case is set aside on both sides.

Its own seam rather than an argument on the cased form: a flag that changes what
an assertion means is a flag a reader has to look up, and the name says it.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped

if TYPE_CHECKING:
    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class CaselessContainmentAssertions(Expect[str]):
    """Containment with both sides casefolded."""

    __slots__ = ()

    def contains_ignoring_case(
        self, value: str, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert ``value`` appears in the string, whatever the case of either.

        ``occurrences`` counts the casefolded needle in the casefolded subject,
        non-overlapping as everywhere else (:meth:`contains`). Both sides are
        folded before counting because casefolding can change a string's length --
        ``"ß"`` folds to ``"ss"`` -- so ``"ßß"`` contains ``"ss"`` twice, and
        counting against the unfolded text would answer about a string nobody
        wrote.
        """
        subject = self._subject
        if occurrences is None:
            if value.casefold() in subject.casefold():
                return self
            return self._fail(
                f"to contain {clipped(value)} ignoring case, but was {clipped(subject)}", because
            )
        found = subject.casefold().count(value.casefold())
        if occurrences.allows(found):
            return self
        return self._fail(
            f"to contain {clipped(value)} ignoring case {occurrences.describe()},"
            f" but found {found}",
            because,
        )

    def does_not_contain_ignoring_case(self, unexpected: str, /, *, because: str = "") -> Self:
        """Assert ``unexpected`` appears nowhere in the string, in any case."""
        subject = self._subject
        if unexpected.casefold() not in subject.casefold():
            return self
        return self._fail(
            f"not to contain {clipped(unexpected)} ignoring case, but {clipped(subject)} does",
            because,
        )
