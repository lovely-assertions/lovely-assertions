"""Several values in one call, and the refusal of none at all.

``contains_all()`` with no arguments is an assertion that cannot fail, which is
the one kind of test worse than a wrong one -- so it is refused where it is
written rather than passing quietly forever.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped, preview
from lovely_assertions._text import holds_any, holds_every

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Guard message for the multi-value assertions. ``contains_all()`` with nothing
#: to look for would pass whatever the subject is, and ``contains_any()`` could
#: never pass. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported.
_NEEDS_VALUES = "at least one value to look for is required"


class MultipleContainmentAssertions(Expect[str]):
    """Several values at once."""

    __slots__ = ()

    def contains_all(self, *values: str, because: str = "") -> Self:
        """Assert every one of ``values`` appears in the string.

        The failure names the values that were missing rather than reporting
        only that some were. Called with no values at all this raises
        ``ValueError``: an assertion that looks for nothing would pass whatever
        the subject is, which is a bug where it was written rather than a
        finding about the subject. :meth:`contains_any` asks for one of them
        instead of all.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if holds_every(subject, values):
            return self
        missing = [value for value in values if value not in subject]
        return self._fail(
            f"to contain all of {preview(values)}, "
            f"but {clipped(subject)} is missing {preview(missing)}",
            because,
        )

    def does_not_contain_all(self, *values: str, because: str = "") -> Self:
        """Assert at least one of ``values`` is absent from the string.

        The negation of :meth:`contains_all`, so it is satisfied by one missing
        value; :meth:`does_not_contain_any` is the one that demands all of them
        be absent. Raises ``ValueError`` when called with no values, for the
        reason :meth:`contains_all` gives.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not holds_every(subject, values):
            return self
        return self._fail(
            f"not to contain all of {preview(values)}, "
            f"but {clipped(subject)} contains every one of them",
            because,
        )

    def contains_any(self, *values: str, because: str = "") -> Self:
        """Assert at least one of ``values`` appears in the string.

        :meth:`contains_all` is the one that demands every value. The failure
        reports that none of them were found, and echoes the values it looked
        for. Raises ``ValueError`` when called with no values: a choice between
        nothing could never be satisfied by any subject.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if holds_any(subject, values):
            return self
        return self._fail(
            f"to contain at least one of {preview(values)}, "
            f"but {clipped(subject)} contains none of them",
            because,
        )

    def does_not_contain_any(self, *values: str, because: str = "") -> Self:
        """Assert none of ``values`` appears in the string.

        Every one of them has to be absent, where :meth:`does_not_contain_all`
        is satisfied by a single missing value. The failure names the ones that
        were found. Raises ``ValueError`` when called with no values.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not holds_any(subject, values):
            return self
        present = [value for value in values if value in subject]
        return self._fail(
            f"not to contain any of {preview(values)}, "
            f"but {clipped(subject)} contains {preview(present)}",
            because,
        )
