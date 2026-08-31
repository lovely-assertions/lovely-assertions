"""Assertions for machine numbers, and the tolerance machinery they need.

The ordering half of what a number can be asked is not here. Comparisons, ranges,
``is_positive`` and ``is_zero`` come from
:class:`~lovely_assertions.OrderedExpect`, which answers for anything orderable
at all -- ``Decimal`` and ``Fraction`` included. What this package adds is what
only a machine number needs: a tolerance, and the two values that are not quite
numbers.

Approximation is why this is a package rather than one module. The band a caller
asks for is rarely the band that gets applied -- a relative tolerance is a
fraction of a magnitude, a floor wins near zero, and an integer past every float
has to be compared without ever taking the difference -- and a failure then has
to say which band it used and where that band came from, or the reader is left
holding a number they never typed. None of that is the assertion's work, so it
sits beside the assertion instead of inside it: the defaults and the infinities,
the arithmetic that resolves two optional tolerances into one absolute band and
decides the comparison, the sentences a failed approximation appends to explain
itself, and the subject assembled from the two seams a number adds.

:func:`effective_tolerance`, :func:`within` and :func:`reject_unusable_tolerance`
leave the package because two callers elsewhere have to answer closeness exactly
the way ``is_close_to`` does. The ``close_to`` matcher takes all three: it
resolves its band and reaches its verdict through the first two, and refuses an
unusable tolerance through the third. The approximate sequence comparison takes
that third one alone, so a tolerance no value could satisfy is refused in the
same words wherever it is passed. Borrowed rather than restated -- a rule written
down twice is a rule that will eventually be written down differently.

Nothing here calls into ``math``. A NaN is the one value not equal to itself and
both infinities are bound once as a tuple, so the special-value assertions cost a
comparison and a membership test.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._numeric._subject import NumericExpect as NumericExpect
from lovely_assertions._numeric._tolerance import effective_tolerance as effective_tolerance
from lovely_assertions._numeric._tolerance import (
    reject_unusable_tolerance as reject_unusable_tolerance,
)
from lovely_assertions._numeric._tolerance import within as within

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["NumericExpect", "effective_tolerance", "reject_unusable_tolerance", "within"]
