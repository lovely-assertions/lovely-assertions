"""NaN and the infinities -- what a float can hold that is not quite a number.

These assertions exist because the generic ones cannot ask their questions. A
NaN is equal to nothing at all, itself included, so ``is_equal_to`` handed a NaN
is an assertion that can never pass, whatever the subject is. An infinity does
equal itself, but "infinite" means either sign, and an equality says one sign at
a time. Each assertion here is the exact complement of its partner, which is
worth knowing mainly for the pair that a NaN falls outside of: not being an
infinity, a NaN passes ``is_not_infinite``.

Their own file because they are the numeric assertions with no tolerance
anywhere in them. The approximate half of this subject spends most of its length
keeping exactly these values from corrupting a band -- an infinite magnitude has
no relative neighbourhood, a NaN band has to lose every comparison it enters --
whereas here they are the question being asked rather than the case being worked
around, and each answer is a single comparison.

The two infinities are a module-level pair rather than a call to ``math.isinf``:
one membership test covers both signs, without a second comparison and without
putting ``math`` in the import path of a library that pays for every import its
users do not need.
"""

from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._numeric._bounds import INFINITIES
from lovely_assertions._ordered import OrderedExpect, is_nan, rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SpecialValueAssertions(OrderedExpect[int | float]):
    """The values a float can hold that are not quite numbers."""

    __slots__ = ()

    # -- special values -----------------------------------------------------
    def is_nan(self, *, because: str = "") -> Self:
        """Assert the subject is a NaN.

        ``is_equal_to(float("nan"))`` cannot do this -- a NaN equals nothing, itself
        included -- which is exactly why this assertion exists.
        """
        if is_nan(self._subject):
            return self
        return self._fail(f"to be NaN, but was {rendered(self._subject)}", because)

    def is_not_nan(self, *, because: str = "") -> Self:
        """Assert the subject is not a NaN. Both infinities pass: neither of them is one."""
        if not is_nan(self._subject):
            return self
        return self._fail("not to be NaN, but it was", because)

    def is_infinite(self, *, because: str = "") -> Self:
        """Assert the subject is ``inf`` or ``-inf``."""
        if self._subject in INFINITIES:
            return self
        return self._fail(f"to be infinite, but was {rendered(self._subject)}", because)

    def is_not_infinite(self, *, because: str = "") -> Self:
        """Assert the subject is finite. A NaN passes: it is not an infinity either."""
        if self._subject not in INFINITIES:
            return self
        return self._fail(f"not to be infinite, but was {rendered(self._subject)}", because)
