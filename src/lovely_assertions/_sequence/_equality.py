"""Sortable equality, and the three weaker forms of it.

Exact, approximate, prefix and suffix. The approximate form exists because a
sequence of floats compared exactly is a test that passes on one machine, and the
prefix and suffix forms because "starts with these three" is a claim about the
order that ``contains_all`` cannot make.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._collection import render_items
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._numeric import reject_unusable_tolerance
from lovely_assertions._sequence._base import SequenceBase
from lovely_assertions._sequence._pairs import (
    first_difference,
    first_difference_beyond,
    first_difference_from_end,
    length_note,
    nan_note,
)
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EqualityAssertions[E](SequenceBase[E]):
    """Item for item, in the order they are in."""

    __slots__ = ()

    def equals_sequence(self, other: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence holds the same items as ``other``, in the same order.

        Compared item by item rather than with ``==`` on the collections, so a
        list equals the tuple with the same contents. The failure names the first
        index that disagrees -- the one thing ``==`` cannot tell you -- and adds
        the lengths when those differ too.

        Two items count as the same when ``item is expected or item == expected``,
        Python's own membership rule, so a sequence holding a NaN equals itself
        while two sequences holding *different* NaNs do not. Lengths must match:
        a subject that merely opens with ``other`` fails here, and
        :meth:`starts_with_sequence` is the assertion for that claim.
        """
        subject = self._subject
        difference = first_difference(subject, other)
        if difference is None:
            if len(subject) == len(other):
                return self
            return self._fail(
                f"to equal {render_items(other)},"
                f" but had {count_of(len(subject), 'item')}, not {len(other)}",
                because,
            )
        return self._fail(
            f"to equal {render_items(other)}, but differed at index {difference}"
            f" ({format_value(subject[difference])} instead of {format_value(other[difference])})"
            + length_note(subject, other),
            because,
        )

    def does_not_equal_sequence(self, other: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence differs from ``other`` in length or in some item.

        The negation of :meth:`equals_sequence`, item comparison included, so the
        two can never both pass. A difference in length satisfies it on its own,
        as does a single item that does not match.
        """
        subject = self._subject
        if len(subject) != len(other) or first_difference(subject, other) is not None:
            return self
        return self._fail(f"not to equal {render_items(other)}, but it did", because)

    def equals_approximately(
        self, other: "Sequence[float]", /, *, tol: float, because: str = ""
    ) -> Self:
        """Assert the sequence matches ``other`` item by item, each within ``tol``.

        The element type is deliberately not constrained: ``SequenceExpect[E]``
        is invariant in ``E``, so a self-type of ``SequenceExpect[float]`` would
        lock out ``SequenceExpect[int]`` -- the common case. The items have to
        support subtraction and ``abs``; anything else raises ``TypeError``,
        which is a bug in the test rather than a finding about the subject.

        ``tol`` is an absolute tolerance and the comparison is inclusive, the
        same contract ``NumericExpect.is_close_to`` states: equal items match at
        any tolerance (so two infinities do), a NaN matches nothing -- itself
        included -- and a negative or NaN ``tol`` raises ``ValueError`` instead
        of quietly making the assertion impossible or vacuous.
        """
        reject_unusable_tolerance(tol, "tolerance")
        subject = self._subject
        difference = first_difference_beyond(subject, other, tol)
        if difference is None:
            if len(subject) == len(other):
                return self
            return self._fail(
                f"to equal {render_items(other)} within {tol},"
                f" but had {count_of(len(subject), 'item')}, not {len(other)}",
                because,
            )
        return self._fail(
            f"to equal {render_items(other)} within {tol}, but differed at index {difference}"
            f" ({format_value(subject[difference])} instead of {format_value(other[difference])})"
            + nan_note(subject[difference], other[difference])
            + length_note(subject, other),
            because,
        )

    def starts_with_sequence(self, prefix: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence opens with ``prefix``, item for item.

        Extra items after the prefix are fine -- that is the whole difference from
        :meth:`equals_sequence`. An empty ``prefix`` passes on any sequence, and a
        ``prefix`` longer than the subject fails even when every item they share
        matches; the message distinguishes the two, naming either the first
        differing index or the length that ran out. Items are compared with the
        same ``item is expected or item == expected`` rule
        :meth:`equals_sequence` uses.
        """
        subject = self._subject
        difference = first_difference(subject, prefix)
        if difference is None:
            if len(prefix) <= len(subject):
                return self
            return self._fail(
                f"to start with {render_items(prefix)},"
                f" but only had {count_of(len(subject), 'item')}: {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to start with {render_items(prefix)}, but differed at index {difference}"
            f" ({format_value(subject[difference])} instead of {format_value(prefix[difference])})",
            because,
        )

    def ends_with_sequence(self, suffix: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence closes with ``suffix``, item for item.

        The mirror of :meth:`starts_with_sequence`, walked from the other end:
        items before the suffix are fine, an empty ``suffix`` passes on any
        sequence, and a ``suffix`` longer than the subject fails. The failure
        reports the index *in the subject* where the two parted company, so it
        can be looked up directly rather than counted back from the end.
        """
        subject = self._subject
        offset = first_difference_from_end(subject, suffix)
        if offset is None:
            if len(suffix) <= len(subject):
                return self
            return self._fail(
                f"to end with {render_items(suffix)},"
                f" but only had {count_of(len(subject), 'item')}: {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to end with {render_items(suffix)}, but differed at index {len(subject) - offset}"
            f" ({format_value(subject[-offset])} instead of {format_value(suffix[-offset])})",
            because,
        )
