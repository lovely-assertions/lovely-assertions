"""The fixed numbers the rest of the package compares against.

Two infinities and the two tolerances :meth:`NumericExpect.is_close_to` falls
back on, and nothing that computes with them. The arithmetic that turns a pair
of tolerances into a band, the sentences that explain where that band came from,
and the assertions for NaN and infinity all read these numbers, and none of the
three has any reason to know about the other two. Housing the constants in
whichever of them happened to be written first would have made the other two
import it -- ``is_infinite`` reaching for a pair of floats through the whole
approximation machinery. A constants module that depends on none of its readers
is the cheaper arrangement and the truer description of what these are.

The tolerances are deliberately not signature defaults. ``is_close_to`` takes
``tol=None`` and ``rel=None`` and resolves them afterwards, because a failure has
to say which of the two set the band it is quoting; a default written into the
signature would erase the difference between a number the caller chose and one
the library supplied before the assertion could ever see it.

``math`` is never imported, here or anywhere below: ``float("inf")`` and its
negation are the whole requirement, and a package whose import cost is a rule
does not pay for a module to obtain a constant it can build itself.
"""

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


INFINITY = float("inf")


#: Both infinities, so ``is_infinite`` needs neither ``math`` nor two comparisons.
INFINITIES: tuple[float, float] = (INFINITY, -INFINITY)


#: The relative tolerance ``is_close_to`` applies when the caller names none at
#: all. It is ``pytest.approx``'s, to the digit, because ``pytest.approx(x)`` is
#: the reflex this signature exists to serve: a default that meant something
#: else would be a trap laid for the reader who already knows one answer.
DEFAULT_REL = 1e-6


#: The absolute floor under a relative tolerance, again ``pytest.approx``'s.
#: A purely relative tolerance is worthless at zero -- ``rel * 0`` is ``0``, so
#: only an exact ``0.0`` would ever be close to one -- and the floor is what
#: keeps ``is_close_to(0.0)`` an assertion rather than an equality test.
DEFAULT_ABS_FLOOR = 1e-12
