"""Ordering and ranges, for anything on a calendar or a clock.

The shared base of every temporal subject, bound by ``Ordered`` rather than by
``date`` -- what these assertions need is that two values compare, not that they
carry a year. That is what lets one catalogue serve a date, a datetime and a
time without any of them inheriting an assertion that makes no sense for it.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._datetime._guards import (
    offending_bound,
    reject_incomparable,
    reject_unusable_range,
)
from lovely_assertions._datetime._render import rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from lovely_assertions._ordered import Ordered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# The shared halves
# ---------------------------------------------------------------------------
class TemporalExpect[T: "Ordered"](Expect[T]):
    """Ordering and ranges, for anything on a calendar or a clock.

    Private, and shared rather than written twice, because ``date`` and ``time``
    answer the comparison operators identically and crash on a naive/aware mix
    identically. What separates them -- a date has no hour, a time has no year --
    is what the public subjects add.

    The bound is ``Ordered`` -- ``_ordered``'s protocol, reused exactly as its
    own docstring says it is meant to be -- and **not** ``date | time``, which is
    what it looks like it should be and does not work: a type parameter bounded
    by a union has to satisfy the checker for *every* pairing of that union's
    members, so ``subject < other`` would be asked to prove that a ``date``
    compares against a ``time``. It does not, and the code would be rejected for
    a combination no subclass of this class can produce. The public subjects
    below re-bind ``T`` to a single concrete type, so nothing is loosened where
    a caller can see it.
    """

    __slots__ = ()

    def is_before(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls strictly before ``other``.

        ``other`` has to be comparable with the subject: a ``date`` mixed with a
        ``datetime``, or a naive value with an aware one, raises ``TypeError``
        naming both sides rather than reporting a failure the subject did not
        cause. Equal moments fail; :meth:`is_on_or_before` is the inclusive form.
        """
        try:
            ordered = self._subject < other
        except TypeError as error:
            reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be before {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_after(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls strictly after ``other``.

        Equal moments fail; :meth:`is_on_or_after` is the inclusive form. An
        operand that cannot be compared with the subject raises ``TypeError``,
        on the same terms as :meth:`is_before`.
        """
        try:
            ordered = self._subject > other
        except TypeError as error:
            reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be after {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_on_or_before(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls at or before ``other``.

        :meth:`is_before` is the strict form. An operand that cannot be compared
        with the subject raises ``TypeError``.
        """
        try:
            ordered = self._subject <= other
        except TypeError as error:
            reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be on or before {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_on_or_after(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls at or after ``other``.

        :meth:`is_after` is the strict form. An operand that cannot be compared
        with the subject raises ``TypeError``.
        """
        try:
            ordered = self._subject >= other
        except TypeError as error:
            reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be on or after {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert ``low <= subject <= high``, both bounds included.

        Raises ``ValueError`` for an inverted range, and ``TypeError`` for bounds
        that cannot be compared with each other or with the subject.
        """
        reject_unusable_range(low, high)
        try:
            inside = low <= self._subject <= high
        except TypeError as error:
            reject_incomparable(self._subject, offending_bound(self._subject, low, high), error)
        if inside:
            return self
        return self._fail(
            f"to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_not_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert the subject falls outside ``low..high``, bounds included.

        The exact complement of :meth:`is_between`.
        """
        reject_unusable_range(low, high)
        try:
            inside = low <= self._subject <= high
        except TypeError as error:
            reject_incomparable(self._subject, offending_bound(self._subject, low, high), error)
        if not inside:
            return self
        return self._fail(
            f"not to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_strictly_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert ``low < subject < high``, both bounds excluded.

        ``low == high`` raises ``ValueError`` as an inverted range does: the
        exclusive range between a moment and itself is empty, so no subject could
        ever satisfy it.
        """
        reject_unusable_range(low, high)
        if low == high:
            raise ValueError(
                "exclusive range is empty: low " + rendered(low) + " equals high " + rendered(high)
            )
        try:
            inside = low < self._subject < high
        except TypeError as error:
            reject_incomparable(self._subject, offending_bound(self._subject, low, high), error)
        if inside:
            return self
        return self._fail(
            f"to be strictly between {rendered(low)} and {rendered(high)}, "
            f"but was {rendered(self._subject)}",
            because,
        )
