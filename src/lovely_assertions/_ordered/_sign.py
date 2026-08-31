"""Where the subject stands relative to zero -- the bound worth its own name.

``is_positive()`` and ``is_greater_than(0)`` decide the same thing and do not say
the same thing. One is a claim about the value; the other is arithmetic the
reader has to finish, and the failure it produces quotes a number rather than
naming a property. So these four keep their own vocabulary all the way through:
the message reads "to be positive", and ``is_not_zero`` quotes no value at all on
its way out, there being exactly one it could have been.

Zero is also the only bound that can be written as a literal without giving back
what the comparison operand's type was bought with. That operand is ``T`` so a
``Decimal`` subject cannot be measured against a float it does not agree with;
the bare ``0`` here is exact in every type that reaches this subject, so fixing
it costs nothing.

What the parameter does not say is that the subject must compare with zero at
all. :class:`Ordered` asks for the four operators and lets their operands be
``Any``, so ``self._subject > 0`` type-checks for any ``T`` and would raise
``TypeError`` on a value that has no numeric scale. Dispatch is what keeps that
honest rather than the annotation: ``expect()`` sends only numbers to this
subject, and a date -- perfectly ordered, with no sign to speak of -- is given a
subject of its own instead of inheriting a question it cannot answer.

The zero pair is written with ``==`` and ``!=`` rather than with the ordering
operators, and the difference shows wherever the number is strange. A float NaN
passes ``is_not_zero``, being equal to nothing whatever, while every ordering
against it fails. A quiet ``Decimal`` NaN signals ``InvalidOperation`` the moment
an ordering touches it, so the zero pair is the only part of this family it can
answer -- and a signalling ``Decimal("sNaN")`` takes that pair with it, since it
signals on ``==`` as well. Either exception is left to reach the caller rather
than caught and reported, because a comparison that could not be made is not a
verdict about the subject. ``-0.0`` is quieter: no operator here separates it
from ``0.0``, so it is zero, and neither positive nor negative.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered._protocol import Ordered
from lovely_assertions._ordered._rendering import rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SignAssertions[T: Ordered](Expect[T]):
    """Which side of zero the subject falls on, and whether it is zero."""

    __slots__ = ()

    # -- sign and zero ------------------------------------------------------
    def is_positive(self, *, because: str = "") -> Self:
        """Assert ``subject > 0``. Zero is not positive, ``-0.0`` included."""
        if self._subject > 0:
            return self
        return self._fail(f"to be positive, but was {rendered(self._subject)}", because)

    def is_negative(self, *, because: str = "") -> Self:
        """Assert ``subject < 0``. ``-0.0`` is zero with a sign bit, not a negative number."""
        if self._subject < 0:
            return self
        return self._fail(f"to be negative, but was {rendered(self._subject)}", because)

    def is_zero(self, *, because: str = "") -> Self:
        """Assert the subject is zero -- ``0``, ``0.0`` and ``-0.0`` all are."""
        if self._subject == 0:
            return self
        return self._fail(f"to be zero, but was {rendered(self._subject)}", because)

    def is_not_zero(self, *, because: str = "") -> Self:
        """Assert the subject is not zero. A NaN passes: it equals nothing, zero included."""
        if self._subject != 0:
            return self
        return self._fail("not to be zero, but it was", because)
