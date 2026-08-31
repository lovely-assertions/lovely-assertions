"""How far apart two numbers are, and whether that is close enough.

The arithmetic of an approximate comparison and none of its prose: the distance
between two numbers, the absolute band a relative tolerance buys at a given
magnitude, the one band ``tol`` and ``rel`` come to together, the inclusive test
that decides, and the refusal of a tolerance no subject could satisfy. Nothing
here builds a failure message. :func:`effective_tolerance` and :func:`within`
run on every *passing* approximate assertion, so they cost a comparison and an
answer; the sentences that explain a failed one are assembled elsewhere, on the
failure path.

Separate from the assertions because the numeric subject is not the only caller.
The ``close_to`` matcher settles the same question inside a larger value, and a
sequence compared item by item within a tolerance refuses the same unusable
tolerances. Re-derived in each place, the rules would agree everywhere except
where an approximate comparison actually goes wrong -- a NaN, the two
infinities, an integer no float can represent -- so there is one implementation
and the callers import it.

``OverflowError`` is the recurring shape, because an ``int`` has no size limit
and a ``float`` does: a large enough integer overflows on the subtraction, and
again on scaling a relative band. Neither is an answer to the question that was
asked. Where the result is a number the reader will be shown, it comes back as
``None`` and the message says no float can measure the gap; where the result is
the verdict itself, the work is redone in exact integers rather than declined,
so that a failure can never print a band wider than the gap it calls too large.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._numeric._bounds import DEFAULT_ABS_FLOOR, DEFAULT_REL, INFINITIES, INFINITY
from lovely_assertions._ordered import is_nan, rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def distance_between(subject: int | float, value: int | float, /) -> int | float | None:
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
    come back as zero, so the floor decides and the ordinary rules apply --
    nothing but ``inf`` falls inside a finite band around ``inf``, and ``inf``
    itself is close by the equality that :func:`within` tests first.

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
    that is still computable -- ``as_integer_ratio`` is exact for an ``int`` and
    for a ``float`` alike, so the product is taken in integers and floored. What
    that floor discards is under one unit, at a magnitude no float can name at
    all.
    """
    magnitude = abs(value)
    if magnitude >= INFINITY:
        return 0.0
    if relative == INFINITY:
        return INFINITY
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
    band = _relative_band(DEFAULT_REL if rel is None else rel, value)
    floor = DEFAULT_ABS_FLOOR if tol is None else tol
    # `band > floor` rather than `max`: a NaN band has to lose, and `max` would
    # hand back whichever of the two it happened to look at first.
    return band if band > floor else floor


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
    distance = distance_between(subject, value)
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
    if tol == INFINITY:
        return True
    if subject in INFINITIES or value in INFINITIES:
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
    than as a claim. The name is threaded through because there are two
    tolerances and "tolerance must not be negative" would not say which.
    """
    if tol is None:
        return
    if is_nan(tol):
        raise ValueError(name + " must not be NaN")
    if tol < 0:
        raise ValueError(name + " must not be negative, got " + rendered(tol))
