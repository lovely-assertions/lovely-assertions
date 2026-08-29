"""Assertions for numbers.

The subject is ``int | float``. Everything a comparison alone can answer --
``is_greater_than``, the ranges, sign and zero -- lives one level up in
:class:`~lovely_assertions.OrderedExpect`, which is where ``Decimal`` and
``Fraction`` reach it too. What is left here is what a comparison cannot answer:
closeness, which needs subtraction, and the two values that only the float domain
has, NaN and infinity.

Floating point is where numeric assertion libraries are usually wrong, so the
answers below are chosen rather than inherited from whatever the operators happen
to do. ``_ordered.py`` states the rules the comparisons follow; the three this
module adds are:

* **A tolerance nothing could satisfy is a bug in the test**, not a finding about
  the value: a negative or NaN one raises ``ValueError`` rather than reporting a
  failure the subject did not cause. That covers ``rel`` exactly as it covers
  ``tol``. A NaN *target* for :meth:`NumericExpect.is_close_to` is deliberately
  not in that list -- it compares unequal, the way ``pytest.approx`` and
  ``numpy.isclose`` treat one, and the failure message names it.
* **Closeness has two currencies, and the caller picks either or both.** ``tol``
  is an absolute distance and ``rel`` a fraction of the target's magnitude; the
  rules they combine under are ``pytest.approx``'s, and the docstring of
  :meth:`NumericExpect.is_close_to` gives the table. Matching the ecosystem beats
  inventing a third answer for a question every Python developer already has an
  answer to.
* **A distance can exist and still not be representable.** An integer has no
  bound on its size and a float does, so subtracting a float from a large enough
  integer raises ``OverflowError`` rather than yielding a distance. That is
  answered rather than propagated, and answered in exact integer arithmetic --
  every distance goes through :func:`_distance`, every relative band through
  :func:`_relative_band`, and the verdict on a gap no float can hold through
  :func:`_within_exactly`. A failure then says the gap is past measuring, but it
  says so only when the tolerance really does not cover it. An assertion that has
  a verdict to give must give it, and must give the right one.
"""

from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered import OrderedExpect, is_nan, rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

#: ``within`` and the two tolerance helpers carry no leading underscore because
#: ``_matching`` reaches them: ``close_to()`` resolves its band through the very
#: helpers ``NumericExpect.is_close_to`` uses, so the matcher and the assertion
#: cannot answer the same question differently. Naming them privately would buy
#: nothing but a private-usage suppression at every crossing, which says less
#: about the arrangement and hides more.
__all__ = [
    "NumericExpect",
    "effective_tolerance",
    "reject_unusable_tolerance",
    "within",
]

_INFINITY = float("inf")

#: Both infinities, so ``is_infinite`` needs neither ``math`` nor two comparisons.
_INFINITIES: tuple[float, float] = (_INFINITY, -_INFINITY)

#: The relative tolerance ``is_close_to`` applies when the caller names none at
#: all. It is ``pytest.approx``'s, to the digit, because ``pytest.approx(x)`` is
#: the reflex this signature exists to serve: a default that meant something
#: else would be a trap laid for the reader who already knows one answer.
_DEFAULT_REL = 1e-6

#: The absolute floor under a relative tolerance, again ``pytest.approx``'s.
#: A purely relative tolerance is worthless at zero -- ``rel * 0`` is ``0``, so
#: only an exact ``0.0`` would ever be close to one -- and the floor is what
#: keeps ``is_close_to(0.0)`` an assertion rather than an equality test.
_DEFAULT_ABS_FLOOR = 1e-12

#: Appended to a closeness failure a NaN caused: no distance exists to report.
_NAN_DISTANCE_NOTE = " (a NaN is close to nothing, itself included)"

#: Appended when the gap is real but no float can hold it -- a big enough integer
#: against a float. Reporting no distance beats crashing on the subtraction.
_UNMEASURABLE_NOTE = ", further from it than any float can measure"


def _distance(subject: int | float, value: int | float, /) -> int | float | None:
    """``abs(subject - value)``, or ``None`` when no float can hold the answer.

    An integer has no size limit and a float does, so ``10**5000 - 1.0`` does not
    produce a large distance -- it raises ``OverflowError`` on the conversion,
    which would crash an assertion that had a perfectly good verdict to give. The
    real distance is finite, merely past every representable one, and ``None``
    says exactly that: further apart than a float can measure.

    The ``try`` costs nothing when nothing is raised, so the happy path is
    unaffected.
    """
    try:
        return abs(subject - value)
    except OverflowError:
        return None


def _relative_band(relative: int | float, value: int | float, /) -> int | float:
    """``relative * abs(value)`` -- the absolute distance a relative tolerance buys.

    Two kinds of magnitude have no band to offer, and are answered rather than
    multiplied out. An **infinite** ``value`` would make ``rel * abs(value)`` infinite,
    which would quietly turn ``expect(0.0).is_close_to(inf)`` into a pass; a
    **NaN** one would make it a NaN, which is not a neighbourhood either. Both
    come back as zero, so the floor decides and the ordinary rules apply -- only
    ``inf`` ends up close to ``inf``, by the equality that :func:`within` tests
    first.

    An infinite ``relative`` is the opposite case: the caller asked for a
    tolerance that covers everything, and it is answered before the multiplication
    so that ``rel * 0.0`` cannot turn it into a NaN. It is answered before the
    NaN magnitude too, so that a failure against a NaN target still reports the
    infinite band the caller asked for rather than a floor -- the assertion fails
    either way, and "a relative tolerance of inf, floored at 1e-12" would be a
    sentence about nothing.

    ``OverflowError`` is the integer wall again, and it stands on **both** sides:
    ``1e-6 * 10**5000`` overflows on the target's magnitude and
    ``10**5000 * 2.0`` overflows on the tolerance's, because either operand
    converts the other to a float first. Neither is a reason to abandon a band
    that is exactly computable -- ``as_integer_ratio`` is exact for an ``int`` and
    for a ``float`` alike, so the product is taken in integers and an approximate
    band around a number that large is exact or it is nothing.
    """
    magnitude = abs(value)
    if magnitude >= _INFINITY:
        return 0.0
    if relative == _INFINITY:
        return _INFINITY
    if is_nan(magnitude):
        return 0.0
    try:
        return relative * magnitude
    except OverflowError:
        numerator, denominator = relative.as_integer_ratio()
        scale, divisor = magnitude.as_integer_ratio()
        return numerator * scale // (denominator * divisor)


def effective_tolerance(
    value: int | float, tol: int | float | None, rel: int | float | None, /
) -> int | float:
    """The one absolute band ``tol`` and ``rel`` come to at this magnitude.

    The rules are ``pytest.approx``'s, and :meth:`NumericExpect.is_close_to`
    tabulates them. The shape worth noticing is the first line: ``tol`` alone
    short-circuits, so a purely absolute tolerance *is* the band -- no magnitude
    is consulted, and no floor is applied that the caller never asked for.
    """
    if rel is None and tol is not None:
        return tol
    band = _relative_band(_DEFAULT_REL if rel is None else rel, value)
    floor = _DEFAULT_ABS_FLOOR if tol is None else tol
    # `band > floor` rather than `max`: a NaN band has to lose, and `max` would
    # hand back whichever of the two it happened to look at first.
    return band if band > floor else floor


def _floor_note(effective: int | float, /) -> str:
    """Name the absolute floor, but only when the floor is what set the band.

    Near zero the relative part is smaller than the floor and the floor wins, so
    the reader sees ``1e-12`` in a message they never wrote ``1e-12`` in. Away
    from zero the floor never bites and naming it would be noise.
    """
    if effective == _DEFAULT_ABS_FLOOR:
        return ", floored at " + rendered(_DEFAULT_ABS_FLOOR)
    return ""


def _tolerance_note(
    effective: int | float, tol: int | float | None, rel: int | float | None, /
) -> str:
    """Explain where an effective tolerance came from. Failure path only.

    The message always leads with the band that was actually applied, in the same
    units as the distance it is compared against, so the reader can do the
    subtraction by eye. Three of the four argument combinations put a number
    there that the caller never typed, and each says where it came from; a bare
    ``tol`` is the fourth, and needs no gloss because the number in the message
    *is* the number in the call.

    Concatenated rather than interpolated: this library reserves f-strings for
    the arguments of ``_fail``.
    """
    if rel is None and tol is None:
        return (
            " (the default relative tolerance of "
            + rendered(_DEFAULT_REL)
            + _floor_note(effective)
            + ")"
        )
    if rel is None:
        return ""
    if tol is None:
        return " (a relative tolerance of " + rendered(rel) + _floor_note(effective) + ")"
    return " (the wider of an absolute " + rendered(tol) + " and a relative " + rendered(rel) + ")"


def within(subject: int | float, value: int | float, tol: int | float, /) -> bool:
    """``True`` when ``subject`` is within ``tol`` of ``value``: ``abs(subject - value) <= tol``.

    Equality is tested first so that two infinities count as close: their
    difference is NaN, not zero. Shared by ``is_close_to`` and ``is_not_close_to``
    so the two cannot drift apart on the values -- NaN, ``inf``, an integer no
    float can reach -- where a hand-inverted condition would stop being a true
    complement.

    When the subtraction overflows there is still a comparison to make, and
    :func:`_within_exactly` makes it in integers rather than declining.
    """
    if subject == value:
        return True
    distance = _distance(subject, value)
    if distance is None:
        return _within_exactly(subject, value, tol)
    return distance <= tol


def _within_exactly(subject: int | float, value: int | float, tol: int | float, /) -> bool:
    """Decide the comparison in exact integers when no float can hold the distance.

    Only reached from :func:`within` once the subtraction has overflowed, which
    takes an integer past every float on one side. Declining there -- calling the
    pair close only when the tolerance is infinite -- is not an option, because
    ``rel`` can *derive* a band from a target that large: the failure would print
    a band wider than the gap and still call the value too far away, a message
    that contradicts itself, which is the one thing a failure message must never
    do.

    The three answers ahead of the arithmetic are the ones the measurable path
    already gives, restated where no distance exists to give them: a NaN is close
    to nothing however infinite the tolerance (``nan <= inf`` is false), an
    infinite tolerance covers every real gap, and an infinite operand is not a
    real gap -- an unequal infinity is beyond every finite tolerance.

    The rest is ``abs(a/b - c/d) <= t/u`` rearranged to ``abs(a*d - c*b) * u <=
    t * b * d``. Every denominator from ``as_integer_ratio`` is positive, so the
    multiplication cannot turn the comparison around.
    """
    if is_nan(subject) or is_nan(value):
        return False
    if tol == _INFINITY:
        return True
    if subject in _INFINITIES or value in _INFINITIES:
        return False
    subject_numerator, subject_denominator = subject.as_integer_ratio()
    value_numerator, value_denominator = value.as_integer_ratio()
    tolerance_numerator, tolerance_denominator = tol.as_integer_ratio()
    gap = abs(subject_numerator * value_denominator - value_numerator * subject_denominator)
    return gap * tolerance_denominator <= (
        tolerance_numerator * subject_denominator * value_denominator
    )


def reject_unusable_tolerance(tol: int | float | None, name: str, /) -> None:
    """Raise ``ValueError`` for a tolerance no subject could satisfy.

    ``None`` is not one of those: it means the caller named this tolerance no
    value at all, which :func:`effective_tolerance` reads as a default rather
    than as a claim. The name is threaded through because there are now two
    tolerances and "tolerance must not be negative" would not say which.
    """
    if tol is None:
        return
    if is_nan(tol):
        raise ValueError(name + " must not be NaN")
    if tol < 0:
        raise ValueError(name + " must not be negative, got " + rendered(tol))


class NumericExpect(OrderedExpect[int | float]):
    """Assertions for numbers.

    ``expect()`` routes ``int``, ``float`` and their subclasses here; ``bool``
    goes to :class:`~lovely_assertions.BoolExpect`, which is the narrower
    overload and so is matched first. Because the subject is a union rather than
    a type parameter, everything inherited from ``Expect[T]`` sees
    ``int | float`` -- a predicate passed to ``matches`` has to accept both.
    ``is_equal_to``, ``is_one_of`` and ``matches`` are those inherited generic
    assertions, as are the comparisons and ranges inherited from
    :class:`~lovely_assertions.OrderedExpect`.

    The class stays **non-generic** on purpose. ``expect(3)`` is a
    ``NumericExpect`` and not a ``NumericExpect[int]``, which keeps the subject
    the union that the built-ins really form -- an ``int`` bound on a ``float``
    subject and the reverse are both ordinary -- and keeps every chained
    assertion's static type one word long.
    """

    __slots__ = ()

    # -- approximation ------------------------------------------------------
    def is_close_to(
        self,
        value: int | float,
        /,
        *,
        tol: int | float | None = None,
        rel: int | float | None = None,
        because: str = "",
    ) -> Self:
        """Assert the subject is close to ``value``, absolutely or relatively.

        ``tol`` is an absolute distance and ``rel`` a fraction of ``value``'s
        magnitude. Both are optional, and the four ways of calling this are
        ``pytest.approx``'s four, deliberately:

        ==================== ==========================================
        call                 the subject has to be within
        ==================== ==========================================
        ``tol=t``            ``t``
        ``rel=r``            ``max(r * abs(value), 1e-12)``
        ``tol=t, rel=r``     ``max(r * abs(value), t)`` -- *either* one
        neither              ``max(1e-6 * abs(value), 1e-12)``
        ==================== ==========================================

        **Neither** means what ``pytest.approx(x)`` means: a relative tolerance of
        one part in a million, floored at ``1e-12`` so that the answer next to
        zero is an approximation rather than an equality test. Requiring an
        explicit tolerance would make the commonest assertion in numeric testing
        the one you have to look up.

        **Both** means *within either*, not within both. Within both would be the
        narrower of the two, which the caller could always have written as a
        single ``tol``; within either is the combination that earns its place --
        a relative band for large values with an absolute floor for small ones,
        which is exactly why ``rel`` needs a floor at all. Spell a pure relative
        tolerance with no floor as ``rel=r, tol=0``.

        The comparison is inclusive: ``abs(subject - value) <= tolerance``. Equal
        values are close at any tolerance, which is what makes two infinities
        close -- their difference is NaN, not zero. A NaN is close to nothing,
        itself included, on either side. An **infinite** ``value`` has no relative
        neighbourhood, so nothing but ``inf`` itself is close to it however large
        ``rel`` is; ``tol=inf`` remains the way to say that everything is close.
        A negative or NaN ``tol`` or ``rel`` raises ``ValueError``.

        A ``Decimal`` is not ``int | float`` and both checkers say so, but the
        runtime answer is worth knowing: ``==`` crosses the two number systems
        exactly, so an equal ``Decimal`` never reaches a subtraction and passes,
        while anything that measures a distance or scales a relative band meets
        Python's ``TypeError``. That is left to travel -- coercing would mean
        picking between two representations that deliberately disagree, which is
        the one reason to be holding a ``Decimal``.
        """
        reject_unusable_tolerance(tol, "tolerance")
        reject_unusable_tolerance(rel, "relative tolerance")
        subject = self._subject
        effective = effective_tolerance(value, tol, rel)
        if within(subject, value, effective):
            return self
        if is_nan(subject) or is_nan(value):
            # `abs(subject - value)` is a NaN here, and "was nan away" tells the
            # reader nothing. Name the reason instead of reporting a non-distance.
            return self._fail(
                f"to be within {rendered(effective)} of {rendered(value)}"
                f"{_tolerance_note(effective, tol, rel)}, "
                f"but was {rendered(subject)}{_NAN_DISTANCE_NOTE}",
                because,
            )
        distance = _distance(subject, value)
        if distance is None:
            return self._fail(
                f"to be within {rendered(effective)} of {rendered(value)}"
                f"{_tolerance_note(effective, tol, rel)}, "
                f"but was {rendered(subject)}{_UNMEASURABLE_NOTE}",
                because,
            )
        return self._fail(
            f"to be within {rendered(effective)} of {rendered(value)}"
            f"{_tolerance_note(effective, tol, rel)}, "
            f"but {rendered(subject)} was {rendered(distance)} away",
            because,
        )

    def is_not_close_to(
        self,
        value: int | float,
        /,
        *,
        tol: int | float | None = None,
        rel: int | float | None = None,
        because: str = "",
    ) -> Self:
        """Assert the subject is further from ``value`` than the tolerance allows.

        The exact complement of :meth:`is_close_to`, argument for argument: the
        same four calling forms, the same effective band, the same ``ValueError``
        for a tolerance nothing could satisfy. Two equal infinities fail, and a
        NaN on either side passes -- which does mean that a NaN ``value`` makes
        this assertion vacuous, the same way ``!= pytest.approx(nan)`` is.
        """
        reject_unusable_tolerance(tol, "tolerance")
        reject_unusable_tolerance(rel, "relative tolerance")
        subject = self._subject
        effective = effective_tolerance(value, tol, rel)
        if not within(subject, value, effective):
            return self
        if subject == value:
            # There is no gap to measure, and for two infinities there is no
            # subtraction either: `inf - inf` is a NaN, not a distance of zero.
            return self._fail(
                f"not to be within {rendered(effective)} of {rendered(value)}"
                f"{_tolerance_note(effective, tol, rel)}, but was equal to it",
                because,
            )
        # A NaN on either side makes `within` false, so a distance exists here --
        # but it may still be one no float can hold, and then there is none to name.
        distance = _distance(subject, value)
        if distance is None:
            return self._fail(
                f"not to be within {rendered(effective)} of {rendered(value)}"
                f"{_tolerance_note(effective, tol, rel)}, "
                f"but was {rendered(subject)}",
                because,
            )
        return self._fail(
            f"not to be within {rendered(effective)} of {rendered(value)}"
            f"{_tolerance_note(effective, tol, rel)}, "
            f"but was {rendered(subject)}, only {rendered(distance)} away",
            because,
        )

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
        """Assert the subject is a real number rather than a NaN."""
        if not is_nan(self._subject):
            return self
        return self._fail("not to be NaN, but it was", because)

    def is_infinite(self, *, because: str = "") -> Self:
        """Assert the subject is ``inf`` or ``-inf``."""
        if self._subject in _INFINITIES:
            return self
        return self._fail(f"to be infinite, but was {rendered(self._subject)}", because)

    def is_not_infinite(self, *, because: str = "") -> Self:
        """Assert the subject is finite. A NaN passes: it is not an infinity either."""
        if self._subject not in _INFINITIES:
            return self
        return self._fail(f"not to be infinite, but was {rendered(self._subject)}", because)
