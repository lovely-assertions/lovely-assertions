"""Wildcards, and the self-type that keeps them off the wrong subject.

A collection of integers has no business being asked whether anything matches
``"user-*"``, and the type variable *bound* to a string collection is what says
so to the checker rather than to the reader at runtime.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._render import render_items
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._text import wildcard_matcher

if TYPE_CHECKING:
    from collections.abc import Collection


#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class WildcardAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """``*``/``?`` matching, for a collection of strings."""

    __slots__ = ()

    def contains_match[S: "WildcardAssertions[str]"](
        self: S, pattern: str, /, *, because: str = ""
    ) -> S:
        """Assert some item matches the wildcard ``pattern`` (``*`` and ``?``).

        Offered only on collections of strings: the self-type is the constraint, so
        ``expect({1, 2}).contains_match("a*")`` is a type error rather than a
        ``TypeError`` at runtime. ``Self`` cannot be written alongside an explicit
        ``self`` annotation -- both checkers reject that -- so the constraint is
        carried by a type variable *bound* to this seam over ``str`` instead,
        which is the same promise: a subclass gets its own type back, and a
        collection of anything else cannot call the method at all.
        """
        subject = self._subject
        matcher = wildcard_matcher(pattern, ignoring_case=False)
        for item in subject:
            if matcher.fullmatch(item) is not None:
                return self
        return self._fail(
            f"to contain a match for {format_value(pattern)}, but was {render_items(subject)}",
            because,
        )

    def does_not_contain_match[S: "WildcardAssertions[str]"](
        self: S, pattern: str, /, *, because: str = ""
    ) -> S:
        """Assert no item matches the wildcard ``pattern`` (``*`` and ``?``)."""
        subject = self._subject
        matcher = wildcard_matcher(pattern, ignoring_case=False)
        for index, item in enumerate(subject):
            if matcher.fullmatch(item) is not None:
                return self._fail(
                    f"not to contain a match for {format_value(pattern)}, but "
                    f"{self._names(lambda v: matcher.fullmatch(v) is not None, (index, item))}"
                    f" matched",
                    because,
                )
        return self
