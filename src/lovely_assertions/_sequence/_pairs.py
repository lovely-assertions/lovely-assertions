"""Walking two sequences side by side, and the notes only a failure reads.

Position first: two sequences that differ at index three have one useful thing to
say, and the length is not it. The scans here stop at the first disagreement in
each direction, so the cost is the prefix they share rather than the whole of
either.

NaN gets its own note because it is unequal to itself, and a message reporting
that index four differs when both sides print ``nan`` is a message the reader
will not believe.
"""

from typing import TYPE_CHECKING, Any, cast

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered import is_nan
from lovely_assertions._sequence._order_scan import Sortable, sort_key

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence, Sized

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# Rendering helpers -- failure path only.
#
# None of them may use an f-string: an f-string is a message, and a message is
# built in exactly one place, inside `_fail`. They concatenate and join instead,
# so that a helper reached from an argument list cannot format eagerly.
# ---------------------------------------------------------------------------
#: Appended to an approximate-comparison failure a NaN caused, where the two
#: rendered values look identical and the message would otherwise read as though
#: the assertion had misfired.
_NAN_NOTE = " (a NaN is close to nothing, itself included)"


#: Appended to an ordering failure a NaN caused, where the message would
#: otherwise read as though the assertion had misfired. The wording is the one
#: :mod:`lovely_assertions._ordered` uses for the same finding on a scalar
#: subject -- one finding should not have two phrasings depending on which
#: subject reported it -- and is restated here rather than imported because that
#: name is private to its module. The two must be kept in step by hand.
_NAN_ORDERING_NOTE = " (a NaN compares false against every ordering)"


def nan_note(left: object, right: object, /) -> str:
    """Trailing clause for a pair no tolerance could have brought together.

    Without it, an approximate comparison against a NaN reports "differed at
    index 0 (nan instead of nan)", which reads like a bug in the library rather
    than the finding it is.
    """
    if left != left or right != right:  # noqa: PLR0124  (that is what "not a number" means)
        return _NAN_NOTE
    return ""


def nan_ordering_note(
    items: "Sequence[object]", index: int, key: "Callable[[Any], Sortable] | None", /
) -> str:
    """Trailing clause for an ordering failure a NaN caused. Failure path only.

    ``to be sorted, but nan at index 1 came after 3.0`` reads like the library
    misfired -- both values are right there and neither looks out of place. The
    note names the actual reason, in the wording
    :mod:`lovely_assertions._ordered` already uses for the same finding.

    The two keys are recomputed rather than carried out of the scan: carrying
    them would make every *passing* ordering assertion pay for a value only a
    failure ever reads.
    """
    if is_nan(sort_key(items[index], key)) or is_nan(sort_key(items[index - 1], key)):
        return _NAN_ORDERING_NOTE
    return ""


def length_note(left: "Sized", right: "Sized", /) -> str:
    """Trailing clause reporting a length mismatch, or ``""`` when they match."""
    if len(left) == len(right):
        return ""
    return ", and had " + str(len(left)) + " items, not " + str(len(right))


# ---------------------------------------------------------------------------
# Comparison helpers -- these run on the happy path, so they allocate nothing
# beyond what the question itself requires.
# ---------------------------------------------------------------------------
def first_difference(left: "Sequence[object]", right: "Sequence[object]", /) -> int | None:
    """Index of the first item that differs, or ``None`` if the shared part matches.

    Says nothing about length -- the caller decides whether a matching prefix is
    a pass (``starts_with_sequence``) or a failure (``equals_sequence``).

    Two items count as the same when ``item is expected or item == expected``,
    Python's own membership rule (see the module docstring). Spelled inline,
    subscripts and all, rather than through a pair of locals: the identity test
    short-circuits whenever the two sides really are one object, and measured
    against locals it is the cheaper of the two.
    """
    for index in range(min(len(left), len(right))):
        if not (left[index] is right[index] or left[index] == right[index]):
            return index
    return None


def first_difference_from_end(left: "Sequence[object]", right: "Sequence[object]", /) -> int | None:
    """Offset back from the end of the first item that differs, 1 for the last one.

    Same equality rule as :func:`first_difference`, walked from the other end.
    """
    for offset in range(1, min(len(left), len(right)) + 1):
        if not (left[-offset] is right[-offset] or left[-offset] == right[-offset]):
            return offset
    return None


def first_difference_beyond(
    left: "Sequence[object]", right: "Sequence[float]", tol: float, /
) -> int | None:
    """Index of the first pair further apart than ``tol``.

    Equality is tested first, so two infinities count as equal -- their
    difference is a NaN, not zero -- and the tolerance comparison is written as
    ``not (distance <= tol)`` rather than ``distance > tol``, so a NaN distance
    counts as a difference. A NaN is close to nothing, itself included; the
    inverted spelling is what keeps it from passing every comparison instead.

    This is the one comparison in the module that deliberately does *not* apply
    the ``is``-then-``==`` rule. Everywhere else the question is which items a
    sequence holds, and a NaN is held where it sits; here the question is how far
    apart two numbers are, and that is the contract ``is_close_to`` states -- the
    same NaN, compared to itself, is still at no measurable distance from
    anything.

    The cast is where this assertion stops being type-safe and says so: the
    element type of the subject is unconstrained, and the arithmetic below is the
    contract the caller signed up to by asking for an approximate comparison.
    """
    for index in range(min(len(left), len(right))):
        item = cast("float", left[index])
        expected = right[index]
        if item == expected:
            continue
        if not abs(item - expected) <= tol:
            return index
    return None
