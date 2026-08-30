"""A set has no position to report, so it reports absence and surplus.

That is the whole difference from a sequence: there is no index to name, no
first disagreement to find, and no order to preserve. What is left is what the
expected side wanted and did not get, and what the actual side had and was not
asked for.

The NaN note exists because a hash-first membership test lists a NaN as both.
``float("nan") != float("nan")``, so the value is absent from the intersection
and present in both differences, and a reader who is not thinking about IEEE 754
at that moment reads it as a contradiction.
"""

from collections.abc import Set as AbstractSet

from lovely_assertions._diff._primitives import indentation, stable_order
from lovely_assertions._diff._render import membership_lines
from lovely_assertions._diff._type_notes import type_note
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import current_formatting
from lovely_assertions._reflection import is_float_nan

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def describe_set(
    actual: AbstractSet[object], expected: AbstractSet[object], depth: int, /
) -> list[str]:
    """What is absent and what is surplus -- a set has no position to report."""
    indent = indentation(depth)
    missing = stable_order([item for item in expected if item not in actual])
    extra = stable_order([item for item in actual if item not in expected])
    lines = membership_lines(indent, missing, extra, "items")
    if lines:
        return lines + _both_sides_nan_note(missing, extra, indent)
    return type_note(actual, expected, "items", depth)


def _both_sides_nan_note(missing: list[object], extra: list[object], indent: str, /) -> list[str]:
    """Account for a NaN a set reports as absent *and* surplus at the same time.

    Set membership hashes before it compares, and two NaNs of separate origin
    hash apart, so each one is listed as missing and as extra. Without this the
    block says a value is both absent and surplus and stops there, which reads as
    a broken report rather than as the finding it is.
    """
    if not _any_nan(missing) or not _any_nan(extra):
        return []
    return [indent + "the nan on both lines is not the same object, and no NaN equals any other"]


def _any_nan(items: list[object], /) -> bool:
    """Whether a NaN is among the items this block actually shows."""
    return any(is_float_nan(item) for item in items[: current_formatting().max_items])
