"""The clauses a failed approximation adds to explain itself.

Failure path only, all of it. Every constant and function here is reached from
inside a failure branch, after the comparison has already returned its verdict,
so a passing assertion builds none of these sentences.

A tolerance reaches the comparison as one number, which is the right shape for
deciding and the wrong one for explaining: by then a floor nobody asked for and a
tolerance the caller typed look identical. So the arguments are read a second
time here, against the band they came to, rather than being carried through the
arithmetic as provenance it would have no use for. What the message ends up with
is the band that actually applied *and* where it came from -- the two questions a
surprising closeness failure raises, and the second is the one a bare number
cannot answer.

The two constants are the failures with no distance to report: a NaN, which is
close to nothing and so has no gap to measure, and a gap that is real but past
every float. They are named rather than written into the message that uses them,
because a clause buried inside a nested f-string is one nobody rereads, and the
wording is the part of a failure that has to be right.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._numeric._bounds import DEFAULT_ABS_FLOOR, DEFAULT_REL
from lovely_assertions._ordered import rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Appended to a closeness failure a NaN caused: no distance exists to report.
NAN_DISTANCE_NOTE = " (a NaN is close to nothing, itself included)"


#: Appended when the gap is real but no float can hold it -- a big enough integer
#: against a float. Reporting no distance beats crashing on the subtraction.
UNMEASURABLE_NOTE = ", further from it than any float can measure"


def _floor_note(effective: int | float, /) -> str:
    """Name the absolute floor, but only when the floor is what set the band.

    Whenever the relative part comes out under the floor -- near zero, for any
    ordinary ``rel`` -- the floor wins, and the reader sees ``1e-12`` in a message
    they never wrote ``1e-12`` in. When the relative part is the wider of the two
    it is the number in the message already, and naming a floor that never bit
    would be noise.
    """
    if effective == DEFAULT_ABS_FLOOR:
        return ", floored at " + rendered(DEFAULT_ABS_FLOOR)
    return ""


def tolerance_note(
    effective: int | float, tol: int | float | None, rel: int | float | None, /
) -> str:
    """Explain where an effective tolerance came from. Failure path only.

    The message always leads with the band that was actually applied, in the same
    units as the distance it is compared against, so the reader can do the
    subtraction by eye. Three of the four argument combinations can put a number
    there that the caller never typed, and each says where it came from; a bare
    ``tol`` is the fourth, and needs no gloss because the number in the message
    *is* the number in the call.

    Concatenated rather than interpolated: every piece is a string already, and
    the result goes straight into the f-string ``_fail`` is handed.
    """
    if rel is None and tol is None:
        return (
            " (the default relative tolerance of "
            + rendered(DEFAULT_REL)
            + _floor_note(effective)
            + ")"
        )
    if rel is None:
        return ""
    if tol is None:
        return " (a relative tolerance of " + rendered(rel) + _floor_note(effective) + ")"
    return " (the wider of an absolute " + rendered(tol) + " and a relative " + rendered(rel) + ")"
