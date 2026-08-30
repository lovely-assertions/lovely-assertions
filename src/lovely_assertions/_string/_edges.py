"""Prefixes and suffixes, cased and not.

The failure shows the end that disagreed rather than the whole string, because a
suffix that is wrong on a two-hundred character line is a fact about the last
twenty characters and nothing else.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped, clipped_end

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EdgeAssertions(Expect[str]):
    """How the string begins and ends."""

    __slots__ = ()

    def starts_with(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string begins with ``prefix``."""
        subject = self._subject
        if subject.startswith(prefix):
            return self
        return self._fail(f"to start with {clipped(prefix)}, but was {clipped(subject)}", because)

    def does_not_start_with(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string does not begin with ``prefix``."""
        subject = self._subject
        if not subject.startswith(prefix):
            return self
        return self._fail(
            f"not to start with {clipped(prefix)}, but was {clipped(subject)}", because
        )

    def starts_with_ignoring_case(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string begins with ``prefix``, whatever the case of either.

        Both sides are casefolded before the comparison, which is why this is not
        simply ``startswith`` on a folded prefix: casefolding can change a
        string's length -- ``"ß"`` folds to ``"ss"`` -- and the prefix has to be
        measured against the folded subject to stay honest.
        """
        subject = self._subject
        if subject.casefold().startswith(prefix.casefold()):
            return self
        return self._fail(
            f"to start with {clipped(prefix)} ignoring case, but was {clipped(subject)}",
            because,
        )

    def does_not_start_with_ignoring_case(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string does not begin with ``prefix`` in any case."""
        subject = self._subject
        if not subject.casefold().startswith(prefix.casefold()):
            return self
        return self._fail(
            f"not to start with {clipped(prefix)} ignoring case, but was {clipped(subject)}",
            because,
        )

    def ends_with(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string ends with ``suffix``."""
        subject = self._subject
        if subject.endswith(suffix):
            return self
        return self._fail(f"to end with {clipped(suffix)}, but was {clipped_end(subject)}", because)

    def does_not_end_with(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string does not end with ``suffix``."""
        subject = self._subject
        if not subject.endswith(suffix):
            return self
        return self._fail(
            f"not to end with {clipped(suffix)}, but was {clipped_end(subject)}", because
        )

    def ends_with_ignoring_case(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string ends with ``suffix``, whatever the case of either."""
        subject = self._subject
        if subject.casefold().endswith(suffix.casefold()):
            return self
        return self._fail(
            f"to end with {clipped(suffix)} ignoring case, but was {clipped_end(subject)}",
            because,
        )

    def does_not_end_with_ignoring_case(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string does not end with ``suffix`` in any case."""
        subject = self._subject
        if not subject.casefold().endswith(suffix.casefold()):
            return self
        return self._fail(
            f"not to end with {clipped(suffix)} ignoring case, but was {clipped_end(subject)}",
            because,
        )
