"""Which side of a given value the subject falls on.

The four comparison operators, one assertion each, against a bound the caller
supplies. It is the plainest family this subject has, and the one the other two
are variations of: the sign assertions fix the bound at zero and drop it from the
signature, the range assertions take two of them and name the interval between.

Each assertion is written against the operator it names, never as the negation of
its opposite. The economy is tempting and it is wrong.
``not (subject < other)`` agrees with ``subject >= other`` for every pair of
numbers a reader is likely to picture, and parts from it against a float NaN,
where all four operators answer ``False``: spelled as a negation,
:meth:`OrderingAssertions.is_greater_than_or_equal_to` would report success on a
comparison that never happened. :class:`Ordered` names all four operators for
that reason rather than for sorting's sake.

Every failure here carries the note that explains a NaN *operand*, and only the
operand. A NaN subject is quoted on the "but was" side, where the sentence is
already pointing at it; a NaN bound leaves a message whose subject looks
perfectly sound, which reads as the library having misfired rather than as a
finding.

Nothing is refused before the comparison, which is where this family parts from
the ranges. A float NaN bound can be satisfied by no subject, just as an inverted
range cannot, but it fails in the direction that shows: all four assertions fail
against it, so the mistake arrives as a red test carrying a sentence that names
its cause, and never as a green one that carries it away. A ``Decimal`` NaN bound
is louder still: the comparison signals ``InvalidOperation`` before there is a
verdict to report, and nothing here catches it.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered._protocol import Ordered
from lovely_assertions._ordered._rendering import nan_operand_note, rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class OrderingAssertions[T: Ordered](Expect[T]):
    """Which side of a single supplied bound the subject falls on."""

    __slots__ = ()

    # -- ordering ----------------------------------------------------------
    def is_greater_than(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject > other``. A NaN on either side fails: NaN is unordered."""
        if self._subject > other:
            return self
        return self._fail(
            f"to be greater than {rendered(other)}, but was {rendered(self._subject)}"
            f"{nan_operand_note(other)}",
            because,
        )

    def is_greater_than_or_equal_to(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject >= other``."""
        if self._subject >= other:
            return self
        return self._fail(
            f"to be greater than or equal to {rendered(other)}, "
            f"but was {rendered(self._subject)}{nan_operand_note(other)}",
            because,
        )

    def is_less_than(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject < other``. A NaN on either side fails: NaN is unordered."""
        if self._subject < other:
            return self
        return self._fail(
            f"to be less than {rendered(other)}, but was {rendered(self._subject)}"
            f"{nan_operand_note(other)}",
            because,
        )

    def is_less_than_or_equal_to(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject <= other``."""
        if self._subject <= other:
            return self
        return self._fail(
            f"to be less than or equal to {rendered(other)}, "
            f"but was {rendered(self._subject)}{nan_operand_note(other)}",
            because,
        )
