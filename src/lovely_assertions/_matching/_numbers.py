"""The numeric placeholder, and where its tolerance comes from.

``close_to`` has to mean exactly what ``NumericExpect.is_close_to`` means. A
library that answers one question two ways is worse than one that answers it
badly, so the tolerance machinery is borrowed from the assertion rather than
restated here, and the band is resolved once at construction.
"""

from typing import Final, cast, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._matching._base import Matcher
from lovely_assertions._matching._rendering import tolerance_phrase
from lovely_assertions._numeric import effective_tolerance, reject_unusable_tolerance, within
from lovely_assertions._ordered import rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: The three membership tests below, hoisted out of the calls that make them.
#:
#: ``isinstance(value, int | float)`` builds the union object afresh on every
#: call -- an allocation whose size grows with the interpreter version -- where
#: the same test against a name bound once allocates nothing at all.
#: :meth:`CloseTo.matches` runs inside ``==`` on an assertion that is about to
#: pass, and a passing assertion is meant to allocate nothing, so the union is
#: built once, here.
#:
#: Written as tuples rather than as ``Final`` unions for the reason :data:`_TEXTUAL`
#: already is one: both checkers narrow through a tuple of types, and a tuple has
#: no runtime construction left to hoist.
_NUMERIC: Final = (int, float)


class CloseTo(Matcher):
    """A number within a tolerance of another.

    The tolerance is resolved once, at construction, into the single absolute
    band ``NumericExpect.is_close_to`` would have applied -- through that
    assertion's own helpers, so the two cannot answer the same question
    differently. A comparison then costs one ``isinstance`` and one subtraction.
    """

    __slots__ = ("_band_", "_rel_", "_tol_", "_value_")

    _value_: int | float
    _band_: int | float
    _tol_: int | float | None
    _rel_: int | float | None

    def __init__(
        self,
        value: int | float,
        band: int | float,
        tol: int | float | None,
        rel: int | float | None,
        /,
    ) -> None:
        object.__setattr__(self, "_value_", value)
        object.__setattr__(self, "_band_", band)
        object.__setattr__(self, "_tol_", tol)
        object.__setattr__(self, "_rel_", rel)

    @override
    def matches(self, value: object, /) -> bool:
        # `bool` is an `int` and passes: `True` really is within a whisker of 1.0,
        # and refusing it would mean this matcher disagreed with `==` about a
        # value `is_close_to` accepts. A `Decimal` is neither, so it does not
        # match -- the same boundary `NumericExpect.is_close_to` documents.
        if not isinstance(value, _NUMERIC):
            return False
        return within(value, self._value_, self._band_)

    @override
    def _spec_key(self) -> tuple[object, ...]:
        # The tolerances as the caller wrote them rather than the band they
        # resolved to, which loses nothing -- the band is a function of these
        # three -- and keeps `==` from contradicting the `repr` below. Around 60,
        # `tol=1` and `rel=1/60` admit exactly the same numbers and print as two
        # different phrases, and the phrase is what a reader meets in a failure
        # message, so the two are not one expectation. `_occurrence._Constraint`
        # draws the line in the same place, between `at_least(3)` and
        # `more_than(2)`.
        return (self._value_, self._tol_, self._rel_)

    @override
    def __repr__(self) -> str:
        return f"<close to {rendered(self._value_)}{tolerance_phrase(self._tol_, self._rel_)}>"


def close_to(
    value: int | float, /, *, tol: int | float | None = None, rel: int | float | None = None
) -> float:
    """A placeholder for any number within a tolerance of ``value``.

        >>> expect({"ttl": 59.7}).is_equal_to({"ttl": close_to(60, tol=1)})
        MappingExpect({'ttl': 59.7})

    ``tol`` is an absolute distance and ``rel`` a fraction of ``value``'s
    magnitude, and the four ways of calling this are the four
    ``NumericExpect.is_close_to`` documents -- the same helpers decide it, so the
    matcher and the assertion cannot drift apart on a NaN, an infinity, or an
    integer no float can hold. Neither tolerance means ``pytest.approx(x)``: one
    part in a million, floored near zero.

    Declared ``float`` rather than ``int | float``. The two are one slot in
    practice, because a ``float`` annotation accepts an ``int`` under the numeric
    tower every checker implements, and returning the union would fail in the
    direction that matters: ``dict[str, float]`` would refuse it.

    A negative or NaN tolerance raises ``ValueError``, exactly as it does on the
    assertion. A NaN **value** is refused here as well, and that one *is* a
    departure: ``expect(x).is_close_to(nan)`` is allowed to run and to fail, which
    is a true finding about ``x``. A matcher has no subject to make a finding
    about -- it would simply never match, anywhere it was placed, and report the
    mismatch as though the value were at fault. That is a bug in the test, and a
    bug in the test is raised where it was written rather than reported as a
    failure somewhere else.
    """
    reject_unusable_tolerance(tol, "tolerance")
    reject_unusable_tolerance(rel, "relative tolerance")
    if value != value:  # noqa: PLR0124  (that is what "not a number" means)
        raise ValueError("close_to(nan) matches nothing, itself included")
    band = effective_tolerance(value, tol, rel)
    return cast("float", CloseTo(value, band, tol, rel))
