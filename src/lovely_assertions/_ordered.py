"""Ordering assertions, for anything that compares.

The subject takes any orderable object -- anything answering ``<`` and ``>`` --
and not only ``int`` and ``float``. ``NumericExpect`` is its ``int | float``
specialisation, and ``Decimal`` and ``Fraction`` reach the catalogue here: they
register with ``numbers`` rather than with the built-ins, so no ``isinstance``
against ``int`` or ``float`` will ever claim them.

**Where the line falls.** An assertion belongs here when the comparison
operators answer it, and in ``_numeric.py`` when it needs arithmetic or names a
value from the float domain:

* comparisons and ranges need ``<`` and ``>``, and nothing else;
* :meth:`OrderedExpect.is_positive` and its neighbours need one more thing, the
  literal ``0``. Zero is not a concept every ordered type has -- a ``datetime``
  has none -- and no type system can express "compares against zero", so the
  rule is written down instead: **everything routed to this subject is a
  number**. A date is orderable and is not a number; it takes a vocabulary of
  its own (``is_before``/``is_after``) rather than ``is_greater_than``, so it
  wants its own subject, not this one.
* ``is_close_to`` needs ``-`` and ``abs``, which the :class:`Ordered` protocol
  does not ask for, and its tolerances would have to be typed ``T`` -- a
  ``Decimal`` subject wants a ``Decimal`` tolerance, since refusing to mix the
  two number systems is what a ``Decimal`` is *for*. That is a third signature
  again: ``NumericExpect`` takes ``tol=``/``rel=`` over ``int | float`` while the
  date subjects take ``within=`` over a ``timedelta``. So closeness is not
  shared, and a ``Decimal`` deliberately gets the whole ordering catalogue and no
  approximation at all. ``is_nan`` and ``is_infinite`` name float-domain values.
  All four stay with :class:`~lovely_assertions.NumericExpect`.

Floating point is where numeric assertion libraries are usually wrong, so the
answers below are chosen rather than inherited from whatever ``<`` happens to do:

* **NaN is unordered.** Every comparison involving it is false, ``nan == nan``
  included. A NaN subject therefore fails every positive claim -- ``is_positive``,
  ``is_zero``, ``is_between``, and ``is_equal_to(nan)`` too -- and
  :meth:`~lovely_assertions.NumericExpect.is_nan` is the only way to assert one.
  It passes the negations for the same reason, which is the point: each negation
  stays the exact complement of its assertion. Where that makes a message read
  like the assertion misfired -- ``to be greater than nan, but was 5`` -- the
  failure says so rather than leaving the reader to recall the rule.
* **Signed zero is zero.** ``-0.0 == 0``, so it is neither positive nor negative.
* **A range nothing could satisfy is a bug in the test**, not a finding about the
  value. Inverted or NaN bounds and an empty exclusive range raise ``ValueError``
  rather than reporting a failure the subject did not cause.
* **A ``Decimal`` NaN does not follow the float rule**, because the decimal
  standard says it must not: an ordering against a quiet NaN *signals*, so
  ``expect(Decimal("NaN")).is_positive()`` raises ``decimal.InvalidOperation``
  where the float spelling would fail. ``==`` is the one operator a quiet NaN
  still answers, which is why :meth:`OrderedExpect.is_zero` and its negation
  keep the float meaning there -- and a *signalling* ``Decimal("sNaN")`` takes
  those two with it, along with the NaN guard on a range bound. Every one of
  those exceptions is left to propagate. Catching them would mean catching
  ``ArithmeticError``, which is also what a user's own comparable type raises
  when two values are genuinely incomparable -- a currency mismatch, say -- and
  turning that into "Expected x to be positive, but was ..." would bury a real
  bug under a message about the wrong thing.

**Integers have no bound on their size**, and a float does, which costs this
subject a crash the others cannot have: CPython refuses outright to convert an
integer of more than ``sys.get_int_max_str_digits()`` digits to text, so a bare
``repr`` in a message turns a failing assertion into an unrelated ``ValueError``.
Every value reaching a message goes through :func:`rendered` instead. An
assertion that has a verdict to give must give it.
"""

import sys
from typing import Any, Protocol, Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._text import length_note

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["Ordered", "OrderedExpect", "is_nan", "rendered"]

#: Longest value rendered in full in a failure message, matching the string
#: subject's budget: roughly one terminal line, which is what a reader takes in at
#: a glance. Past it the digits stop informing and start dumping.
_MAX_RENDERED = 120

#: ``log10(2)``, scaled to five decimals so the digit count of a huge integer can
#: be estimated from ``int.bit_length()`` in integer arithmetic. Needed because on
#: the far side of CPython's conversion limit the digits cannot be produced at all,
#: and the size is the only thing left to report.
_LOG10_OF_2_SCALED = 30103

#: Appended to an ordering failure whose operand was a NaN, where the message
#: would otherwise read as though the assertion had misfired.
_NAN_OPERAND_NOTE = " (a NaN compares false against every ordering)"


class Ordered(Protocol):
    """Anything the comparison operators accept -- the requirement this subject has.

    ``_typeshed.SupportsRichComparison`` is the obvious candidate and does not
    work: it is a *union* of two half-protocols, and neither checker will compare
    one member of that union against the other. This is the protocol written to
    solve that, and it is shared: ``_sequence`` asks for the same thing of the
    ``key=`` callables its ordering assertions take.

    All four operators are named, rather than the ``__lt__`` that sorting alone
    would need, because a NaN makes them genuinely independent: ``a >= b`` is
    *not* ``not (a < b)`` when either side is unordered, so
    :meth:`OrderedExpect.is_greater_than_or_equal_to` cannot be spelled with
    ``<`` and stay a true complement of :meth:`OrderedExpect.is_less_than`.
    """

    __slots__ = ()

    def __lt__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's business)
        ...

    def __le__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's)
        ...

    def __gt__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's)
        ...

    def __ge__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's)
        ...


def is_nan(value: object, /) -> bool:
    """``True`` when ``value`` is a NaN.

    A NaN is the only value not equal to itself, so the self-comparison *is* the
    definition rather than an accident -- and it answers the question without
    importing ``math``, for a ``Decimal`` NaN as readily as for a float one.
    """
    return value != value  # noqa: PLR0124  (that is what "not a number" means)


def rendered(value: object, /) -> str:
    """Render a value for a failure message. Failure path only.

    An integer has no size limit, and two thresholds sit above it. The lower one
    is legibility: past :data:`_MAX_RENDERED` characters the digits are a wall,
    so the value is clipped and its real length reported, exactly as the string
    subject elides a long haystack. The upper one is hard -- CPython raises
    ``ValueError`` rather than convert an integer of more than
    ``sys.get_int_max_str_digits()`` digits to text -- so past it the digits are
    never asked for at all, and the size is reported from ``bit_length`` instead.
    Without that, a failing assertion on a big integer would not report at all:
    it would blow up inside its own message with an error about string
    conversion.

    Everything else goes through the formatter registry, so a domain type with a
    registered formatter reads as itself here rather than as its address.

    Assembled by concatenation rather than an f-string, which this library
    reserves for the arguments of ``_fail``.
    """
    if isinstance(value, int):
        digits = value.bit_length() * _LOG10_OF_2_SCALED // 100000 + 1
        # `sys.get_int_max_str_digits()` answers 0 when the limit is disabled.
        limit = sys.get_int_max_str_digits()
        if limit and digits >= limit:
            sign = "-" if value < 0 else ""
            return sign + "<integer of about " + str(digits) + " digits>"
    text = format_value(value)
    if len(text) <= _MAX_RENDERED:
        return text
    return text[:_MAX_RENDERED] + "..." + length_note(len(text))


def _nan_operand_note(other: object, /) -> str:
    """Explain an ordering failure the *operand* caused. Failure path only.

    ``Expected 5 to be greater than nan, but was 5`` reads like a bug in the
    library; the subject is right there and nothing looks wrong with it. The note
    names the actual reason so the reader does not have to recall that every
    ordering against a NaN is false.
    """
    return _NAN_OPERAND_NOTE if is_nan(other) else ""


def _reject_unusable_range(low: Ordered, high: Ordered, /) -> None:
    """Raise ``ValueError`` for bounds that describe no range at all.

    Checked before the subject is looked at, on purpose: bounds no value could
    satisfy are a bug in the test, and a subject that happened to fail would hide
    it behind a message blaming the value.
    """
    if is_nan(low) or is_nan(high):
        raise ValueError(
            "range bounds must not be NaN, got " + rendered(low) + " to " + rendered(high)
        )
    if low > high:
        raise ValueError(
            "range is inverted: low " + rendered(low) + " exceeds high " + rendered(high)
        )


class OrderedExpect[T: Ordered](Expect[T]):
    """Assertions for ordered values.

    ``expect()`` routes ``int``, ``float`` and their subclasses to
    :class:`~lovely_assertions.NumericExpect`, which is this class specialised to
    ``int | float`` and extended with the float-domain assertions; ``Decimal`` and
    ``Fraction`` land here directly, as ``OrderedExpect[Decimal]`` and
    ``OrderedExpect[Fraction]``.

    The operand of a comparison is typed ``T``, not "any number". On
    ``NumericExpect`` that resolves to ``int | float`` and reads as an ordinary
    numeric bound; on ``OrderedExpect[Decimal]`` it means a bound has to be a
    ``Decimal`` too. That is deliberate rather than incidental:
    ``Decimal("0.1") == 0.1`` is false, and an assertion library that let a float
    bound slip into a ``Decimal`` comparison would be undermining the reason the
    value is a ``Decimal``. Where a bound of zero is what was wanted,
    :meth:`is_positive` and its neighbours take no operand at all.
    """

    __slots__ = ()

    # -- ordering ----------------------------------------------------------
    def is_greater_than(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject > other``. A NaN on either side fails: NaN is unordered."""
        if self._subject > other:
            return self
        return self._fail(
            f"to be greater than {rendered(other)}, but was {rendered(self._subject)}"
            f"{_nan_operand_note(other)}",
            because,
        )

    def is_greater_than_or_equal_to(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject >= other``."""
        if self._subject >= other:
            return self
        return self._fail(
            f"to be greater than or equal to {rendered(other)}, "
            f"but was {rendered(self._subject)}{_nan_operand_note(other)}",
            because,
        )

    def is_less_than(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject < other``. A NaN on either side fails: NaN is unordered."""
        if self._subject < other:
            return self
        return self._fail(
            f"to be less than {rendered(other)}, but was {rendered(self._subject)}"
            f"{_nan_operand_note(other)}",
            because,
        )

    def is_less_than_or_equal_to(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``subject <= other``."""
        if self._subject <= other:
            return self
        return self._fail(
            f"to be less than or equal to {rendered(other)}, "
            f"but was {rendered(self._subject)}{_nan_operand_note(other)}",
            because,
        )

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

    # -- ranges (`is_between` includes its bounds) ---------------------------
    def is_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert ``low <= subject <= high``, both bounds included.

        Raises ``ValueError`` for an inverted or NaN range. A NaN *subject* merely
        fails -- it lies outside every range.
        """
        _reject_unusable_range(low, high)
        if low <= self._subject <= high:
            return self
        return self._fail(
            f"to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_not_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert the subject is outside ``low..high``, bounds included.

        The exact complement of :meth:`is_between`, so a NaN subject passes.
        """
        _reject_unusable_range(low, high)
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
        _reject_unusable_range(low, high)
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
