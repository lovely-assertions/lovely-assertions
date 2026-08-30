"""The pattern a reader means nine times in ten.

``*`` and ``?``, not a regex -- so a full stop is a full stop. The translation
and its bound live in ``_text``, because the collection subject matches the same
way and one answer is worth more than two.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped
from lovely_assertions._text import matches_wildcard

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class WildcardAssertions(Expect[str]):
    """``*`` and ``?`` matching."""

    __slots__ = ()

    def matches_wildcard(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the whole string matches the wildcard ``pattern``.

        ``*`` matches any run of characters and ``?`` exactly one; everything
        else, punctuation included, is literal. Unlike :meth:`matches` this is a
        full match, which is what makes the wildcard form worth having.
        """
        subject = self._subject
        if matches_wildcard(subject, pattern, ignoring_case=False):
            return self
        return self._fail(
            f"to match the wildcard pattern {pattern!r}, but was {clipped(subject)}", because
        )

    def does_not_match_wildcard(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the string does not match the wildcard ``pattern`` in full."""
        subject = self._subject
        if not matches_wildcard(subject, pattern, ignoring_case=False):
            return self
        return self._fail(
            f"not to match the wildcard pattern {pattern!r}, but was {clipped(subject)}", because
        )

    def matches_wildcard_ignoring_case(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the whole string matches the wildcard ``pattern``, ignoring case."""
        subject = self._subject
        if matches_wildcard(subject, pattern, ignoring_case=True):
            return self
        return self._fail(
            f"to match the wildcard pattern {pattern!r} ignoring case, but was {clipped(subject)}",
            because,
        )

    def does_not_match_wildcard_ignoring_case(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the string does not match the wildcard ``pattern``, in any case."""
        subject = self._subject
        if not matches_wildcard(subject, pattern, ignoring_case=True):
            return self
        return self._fail(
            f"not to match the wildcard pattern {pattern!r} ignoring case, "
            f"but was {clipped(subject)}",
            because,
        )
