"""Whether a value falls between two bounds -- and whether the bounds count.

Every other question this subject answers names one bound: a comparison takes a
single operand, and the sign assertions compare against an implicit zero. These
name both ends at once, which is what earns them their place. The chain that
would replace them,
``.is_greater_than_or_equal_to(low).is_less_than_or_equal_to(high)``, fails at
whichever end it reaches first and quotes that bound alone, leaving the reader to
reconstruct the interval that was actually meant. Here the interval is in the
sentence.

Which bounds are included is never left to memory. :meth:`RangeAssertions.is_between`
holds both and says "inclusive" in its message,
:meth:`RangeAssertions.is_strictly_between` holds neither and says "strictly", and
:meth:`RangeAssertions.is_not_between` is the exact complement of the first, bounds
included -- which is why a float NaN subject passes it: a NaN loses every
comparison, so it falls outside every range there is. A ``Decimal`` NaN answers
neither way, signalling ``InvalidOperation`` the moment an ordering touches it.

All three refuse an unusable pair of bounds before they look at the subject, and
refuse it as a ``ValueError`` rather than a failure. Bounds that describe no range
are a bug in the test rather than a fact about the value, and that holds for
``is_not_between`` too, where such a range would otherwise pass and carry the bug
off with it. The one check that cannot be shared is the exclusive form's:
``low == high`` is an ordinary closed range holding exactly one value, so only the
assertion that drops its bounds has grounds to call it empty.

Nothing here appends the note the ordering assertions add when the *operand* was a
NaN. A NaN bound never survives long enough to lose a comparison -- it is refused
first -- so the only NaN a message from here can be quoting is the subject's own,
which the sentence already names.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered._protocol import Ordered
from lovely_assertions._ordered._rendering import rendered
from lovely_assertions._ordered._validation import reject_unusable_range

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class RangeAssertions[T: Ordered](Expect[T]):
    """Whether the subject lies between two bounds, and whether the bounds count."""

    __slots__ = ()

    # -- ranges (`is_between` includes its bounds) ---------------------------
    def is_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert ``low <= subject <= high``, both bounds included.

        Raises ``ValueError`` for an inverted or NaN range. A float NaN *subject*
        merely fails -- it lies outside every range; a ``Decimal`` NaN signals
        ``InvalidOperation``, as it does against any ordering.
        """
        reject_unusable_range(low, high)
        if low <= self._subject <= high:
            return self
        return self._fail(
            f"to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_not_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert the subject is outside ``low..high``, bounds included.

        The exact complement of :meth:`is_between`, so a float NaN subject passes.
        A ``Decimal`` NaN signals ``InvalidOperation`` rather than answering.
        """
        reject_unusable_range(low, high)
        if not low <= self._subject <= high:
            return self
        return self._fail(
            f"not to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_strictly_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert ``low < subject < high``, both bounds excluded.

        ``low == high`` raises ``ValueError`` as an inverted range does: the
        exclusive range between a bound and itself is empty, so no subject could
        ever satisfy it. ``-0.0`` and ``0.0`` are the same bound by that test.
        """
        reject_unusable_range(low, high)
        # Both bounds are named rather than one: `-0.0 == 0.0`, so an empty range
        # can be spelled with two bounds that do not look the same.
        if low == high:
            raise ValueError(
                "exclusive range is empty: low " + rendered(low) + " equals high " + rendered(high)
            )
        if low < self._subject < high:
            return self
        return self._fail(
            f"to be strictly between {rendered(low)} and {rendered(high)}, "
            f"but was {rendered(self._subject)}",
            because,
        )
