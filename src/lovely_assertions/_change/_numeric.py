"""The amount half: ``.by(...)``, for probes whose values subtract.

Offered on the scopes whose probe returns something a difference can be taken of
-- a count, a balance, a duration, an instant -- and on nothing else. A ``str``
probe has no ``.by``, for the reason a ``str`` subject has no ``is_positive``.

The delta type is not the value type. Two ``datetime`` samples differ by a
``timedelta``, so the amount a caller passes is the type of ``after - before``
rather than the type of either sample; that is the second type parameter, and it
is why this class carries one more than :class:`~lovely_assertions._change.Change`.
"""

from typing import Any, Never, Self, override

from lovely_assertions._change._scope import NARROWED_BY, Change
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NumericChange[V, D](Change[V]):
    """A change scope that can also be asked *how much*.

    Everything :class:`~lovely_assertions._change.Change` offers, plus
    :meth:`by`. ``expect_change`` hands this back for a probe returning an
    ``int``, ``float``, ``Decimal``, ``Fraction``, ``datetime`` or ``timedelta``,
    and the plain scope for everything else.

    ``bool`` is deliberately not among them, exactly as ``bool`` leads the
    dispatch table ahead of ``int``: a flag that went from ``False`` to ``True``
    did not "increase by 1", and offering the reading would invite it.
    """

    __slots__ = ()

    def by(self, amount: D, /) -> Self:
        """Narrow the claim to how far the value moved.

            with expect_change(lambda: Order.count()).by(1):
                place(order)

        The amount is a *difference*, so for a probe returning instants it is a
        duration. A negative amount reads as a decrease and is a perfectly good
        claim; zero is not refused either, though ``expect_no_change`` says that
        one better.
        """
        self._wanted = amount
        self._narrowed = NARROWED_BY
        return self

    @override
    def _narrowing(self) -> str:
        """``"to increase by 5"`` and its two siblings. **Failure path only.**

        Every scope this library builds at runtime is a ``NumericChange``, whether
        or not the caller was offered ``.by``, so this has to answer for ``.to``
        as well -- and hands that case straight back to the base rather than
        guessing which narrowing it is looking at.
        """
        if self._narrowed == NARROWED_BY:
            return _direction(self._wanted)
        return super()._narrowing()

    @override
    def _satisfied(self, before: V, after: V, /) -> bool:
        """Whether the narrowed claim holds -- a distance for ``by``, a value for ``to``."""
        if self._narrowed == NARROWED_BY:
            moved = _difference(before, after)
            if moved is _NO_DIFFERENCE:
                _refuse_the_probe(after, self._wanted)
            return bool(moved == self._wanted)
        return super()._satisfied(before, after)

    @override
    def _distance(self, before: V, after: V, /) -> str:
        """How far the value went. **Failure path only.**

        "from 3 to 5" leaves the reader subtracting to find out whether the action
        overshot by one or by two, which is exactly the question a failed
        ``by(...)`` is about. Answering it is the whole of what the amount half
        adds to a message.
        """
        moved = _difference(before, after)
        if moved is _NO_DIFFERENCE:
            return ""
        return " (a change of " + format_value(moved) + ")"


class _NoDifference:
    """The answer when two samples will not subtract. Told apart from a real zero."""

    __slots__ = ()

    @override
    def __repr__(self) -> str:
        return "<no difference>"


#: Returned by :func:`_difference` for values that do not subtract. A sentinel and
#: not ``None``, because ``None`` is a difference some type could legitimately
#: define, and because a zero delta is a perfectly ordinary answer.
_NO_DIFFERENCE = _NoDifference()


def _difference(before: Any, after: Any, /) -> Any:  # noqa: ANN401  (the probe's own type, and its delta)
    """``after - before``, or :data:`_NO_DIFFERENCE` where the values do not subtract.

    Reached with values that do not subtract only when a caller went around the
    overloads -- a probe annotated ``Any``, or one that lied about what it
    returns. Never raises here: the two readers want opposite things from that
    case, and each decides for itself.
    """
    try:
        return after - before
    # a probe that does not subtract is a caller's mistake; the readers decide
    except Exception:
        return _NO_DIFFERENCE


def _direction(amount: Any, /) -> str:  # noqa: ANN401  (whatever `by(...)` was given)
    """``"to increase by 5"``, ``"to decrease by 5"``, or a neutral reading.

    The sign is read by comparing the amount with the additive zero of its own
    type -- ``amount - amount`` -- so this needs no table of numeric types and
    works for a ``timedelta`` as readily as for an ``int``. Where any of that
    raises, the neutral wording is still true, which is the safe direction for a
    sentence.
    """
    try:
        zero = amount - amount
        if amount > zero:
            return "to increase by " + format_value(amount)
        if amount < zero:
            return "to decrease by " + format_value(-amount)
    # an amount that will not compare with its own zero still gets a true sentence
    except Exception:
        return "to change by " + format_value(amount)
    return "to change by " + format_value(amount)


def _refuse_the_probe(sample: Any, amount: Any, /) -> Never:  # noqa: ANN401  (whatever the caller had)
    """Refuse a ``by(...)`` over values that will not subtract.

    A caller who reached this went around the overloads, which offer ``by`` only
    for probes returning something a difference can be taken of. Reporting it as
    a *failed assertion* would be a lie about the subject -- the value may have
    changed exactly as intended -- so it is the ``TypeError`` a misuse gets
    everywhere else in this library, naming what arrived and what would work.
    """
    message = (
        "by(...) needs two samples that subtract, and this probe returned "
        + type(sample).__name__
        + ". Use expect_change(...).to("
        + repr(amount)
        + ") for a destination, or a probe that returns a number, a Decimal, a"
        " Fraction, a datetime or a timedelta"
    )
    raise TypeError(message)
