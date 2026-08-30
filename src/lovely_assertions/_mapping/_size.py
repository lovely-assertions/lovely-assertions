"""Emptiness and length.

The None-absorbing pair is here for the reason it is on every other container: a
mapping that was never populated and one that came back ``None`` are the same bug
in most tests, and asking twice is a line of noise.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._mapping._previews import (
    entry_count,
    is_none_or_empty,
    preview,
    render_or_none,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sized

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SizeAssertions[K, V](Expect[Mapping[K, V]]):
    """How many entries, and whether there are any."""

    __slots__ = ()

    def is_empty(self, *, because: str = "") -> Self:
        """Assert the mapping has no entries."""
        subject = self._subject
        if not subject:
            return self
        return self._fail(
            f"to be empty, but had {entry_count(len(subject))} with keys {preview(subject.keys())}",
            because,
        )

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the mapping has at least one entry."""
        if self._subject:
            return self
        return self._fail("not to be empty, but it was", because)

    def is_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the mapping is ``None`` or has no entries.

        The subject type excludes ``None``, so a checker will say this can only
        ever be the empty case. The runtime check is real all the same: ``None``
        arrives here through a cast, from untyped code, or from a fixture that
        returned nothing, and absorbing exactly that is what the assertion is for.
        """
        subject = self._subject
        if is_none_or_empty(subject):
            return self
        return self._fail(
            f"to be None or empty, but had {entry_count(len(subject))}"
            f" with keys {preview(subject.keys())}",
            because,
        )

    def is_not_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the mapping is neither ``None`` nor empty."""
        if not is_none_or_empty(self._subject):
            return self
        return self._fail(
            f"not to be None or empty, but was {render_or_none(self._subject)}", because
        )

    def has_length(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the mapping has exactly ``expected`` entries."""
        subject = self._subject
        actual = len(subject)
        if actual == expected:
            return self
        return self._fail(
            f"to have {entry_count(expected)}, but had {entry_count(actual)} "
            f"with keys {preview(subject.keys())}",
            because,
        )

    def does_not_have_length(self, unexpected: int, /, *, because: str = "") -> Self:
        """Assert the mapping has any number of entries other than ``unexpected``."""
        if len(self._subject) != unexpected:
            return self
        return self._fail(f"not to have {entry_count(unexpected)}, but it did", because)

    def has_length_matching(
        self, predicate: "Callable[[int], bool]", /, *, because: str = ""
    ) -> Self:
        """Assert the number of entries satisfies ``predicate``."""
        subject = self._subject
        if predicate(len(subject)):
            return self
        return self._fail(
            f"to have a length matching {describe_predicate(predicate)},"
            f" but had {entry_count(len(subject))} with keys {preview(subject.keys())}",
            because,
        )

    def has_length_greater_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has more than ``other`` entries."""
        subject = self._subject
        if len(subject) > other:
            return self
        return self._fail(
            f"to have more than {entry_count(other)},"
            f" but had {entry_count(len(subject))} with keys {preview(subject.keys())}",
            because,
        )

    def has_length_greater_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has at least ``other`` entries."""
        subject = self._subject
        if len(subject) >= other:
            return self
        return self._fail(
            f"to have at least {entry_count(other)},"
            f" but had {entry_count(len(subject))} with keys {preview(subject.keys())}",
            because,
        )

    def has_length_less_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has fewer than ``other`` entries."""
        subject = self._subject
        if len(subject) < other:
            return self
        return self._fail(
            f"to have fewer than {entry_count(other)},"
            f" but had {entry_count(len(subject))} with keys {preview(subject.keys())}",
            because,
        )

    def has_length_less_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has at most ``other`` entries."""
        subject = self._subject
        if len(subject) <= other:
            return self
        return self._fail(
            f"to have at most {entry_count(other)},"
            f" but had {entry_count(len(subject))} with keys {preview(subject.keys())}",
            because,
        )

    def has_same_length_as(self, other: "Sized", /, *, because: str = "") -> Self:
        """Assert the mapping has as many entries as ``other`` has items.

        ``other`` is anything with a length -- a list, a set, another mapping --
        because comparing an entry count against an item count is a fair
        question and the element types are nobody's business here.
        """
        actual = len(self._subject)
        if actual == len(other):
            return self
        return self._fail(
            f"to have as many entries as {format_value(other)},"
            f" but had {entry_count(actual)} against {len(other)}",
            because,
        )

    def does_not_have_same_length_as(self, other: "Sized", /, *, because: str = "") -> Self:
        """Assert the mapping and ``other`` differ in size.

        The negation of :meth:`has_same_length_as`, and it takes the same
        anything-with-a-length.
        """
        actual = len(self._subject)
        if actual != len(other):
            return self
        return self._fail(
            "not to have as many entries as "
            + format_value(other)
            + ", but both had "
            + entry_count(actual),
            because,
        )
