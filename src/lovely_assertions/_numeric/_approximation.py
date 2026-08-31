"""Close enough, and its exact complement.

The two assertions that settle a comparison with a tolerance rather than with
``==``. They live together because they are one claim written twice -- the same
four calling forms, the same effective band, the same refusal of a tolerance no
subject could satisfy -- and because they reach their verdict through the same
call, so the negative form cannot quietly stop being the inverse of the positive
one on the values where being an inverse is hard.

None of the arithmetic is here. Reducing ``tol`` and ``rel`` to the one distance
that was applied, and deciding the comparison itself, belong to the tolerance
helpers; the parenthetical naming where that distance came from belongs to the
notes. What is left, and what this module is for, is choosing *which* failure to
report -- because "too far away" is not the only way an approximate comparison
fails. A NaN on either side leaves no distance to name, and two numbers can be
genuinely finite and still further apart than any float can hold, which arrives
as no distance at all. Each of those gets a sentence saying so, rather than a
number that would misdescribe the bug.

Every message here is assembled below the branch that has already decided the
assertion, so a passing call pays for the two tolerance checks, the band and the
comparison, and never for a sentence.
"""

from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._numeric._notes import NAN_DISTANCE_NOTE, UNMEASURABLE_NOTE, tolerance_note
from lovely_assertions._numeric._tolerance import (
    distance_between,
    effective_tolerance,
    reject_unusable_tolerance,
    within,
)
from lovely_assertions._ordered import OrderedExpect, is_nan, rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ApproximationAssertions(OrderedExpect[int | float]):
    """Near enough, and the four ways of saying how near."""

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

        A ``Decimal`` ``value`` is not ``int | float`` and both checkers say so,
        but the runtime answer is worth knowing: ``==`` crosses the two number
        systems exactly, so an equal ``Decimal`` passes under a bare ``tol``, the
        one calling form that consults no magnitude. Every other form scales a
        relative band first, and that -- like measuring the distance to an
        unequal ``Decimal`` -- meets Python's ``TypeError``. That is left to
        travel: coercing would mean picking between two representations that
        deliberately disagree, which is the one reason to be holding a
        ``Decimal``.
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
                f"{tolerance_note(effective, tol, rel)}, "
                f"but was {rendered(subject)}{NAN_DISTANCE_NOTE}",
                because,
            )
        distance = distance_between(subject, value)
        if distance is None:
            return self._fail(
                f"to be within {rendered(effective)} of {rendered(value)}"
                f"{tolerance_note(effective, tol, rel)}, "
                f"but was {rendered(subject)}{UNMEASURABLE_NOTE}",
                because,
            )
        return self._fail(
            f"to be within {rendered(effective)} of {rendered(value)}"
            f"{tolerance_note(effective, tol, rel)}, "
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
                f"{tolerance_note(effective, tol, rel)}, but was equal to it",
                because,
            )
        # A NaN on either side makes `within` false, so a distance exists here --
        # but it may still be one no float can hold, and then there is none to name.
        distance = distance_between(subject, value)
        if distance is None:
            return self._fail(
                f"not to be within {rendered(effective)} of {rendered(value)}"
                f"{tolerance_note(effective, tol, rel)}, "
                f"but was {rendered(subject)}",
                because,
            )
        return self._fail(
            f"not to be within {rendered(effective)} of {rendered(value)}"
            f"{tolerance_note(effective, tol, rel)}, "
            f"but was {rendered(subject)}, only {rendered(distance)} away",
            because,
        )
