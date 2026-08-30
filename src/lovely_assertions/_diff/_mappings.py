"""Keys first, because a key both sides hold is where the answer usually is.

A mapping that differs almost always differs in a value under a shared key, and
that is the finding a reader wants at the top. Keys nobody expected and keys
nobody wrote come after it: they are real, but they are the shape of the mapping
rather than its contents, and a report that leads with them buries the line the
reader came for.
"""

from collections.abc import Mapping

from lovely_assertions._diff._primitives import clip, equal, indentation
from lovely_assertions._diff._render import membership_lines, pair_lines
from lovely_assertions._diff._type_notes import type_note
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def describe_mapping(
    actual: Mapping[object, object], expected: Mapping[object, object], depth: int, /
) -> list[str]:
    """Values that disagree first, then keys nobody expected and keys nobody wrote.

    The value lines come first because a wrong value under a right key is what a
    mapping comparison usually fails on, and because when it is a key that is
    missing there are no value lines to get in the way.
    """
    indent = indentation(depth)
    differing = [key for key in expected if key in actual and not equal(actual[key], expected[key])]
    max_items = current_formatting().max_items
    lines: list[str] = []
    for key in differing[:max_items]:
        # Clipped like every other rendered value: a mapping keyed by a request
        # body would otherwise put the whole body in the label, and the bound
        # this module advertises would hold for every line except that one.
        lines.extend(
            pair_lines(
                "values differ at key " + clip(format_value(key)),
                actual[key],
                expected[key],
                depth,
            )
        )
    elided = len(differing) - max_items
    if elided > 0:
        lines.append(indent + _more_keys_note(elided))
    missing = [key for key in expected if key not in actual]
    extra = [key for key in actual if key not in expected]
    lines.extend(membership_lines(indent, missing, extra, "keys"))
    if lines:
        return lines
    return type_note(actual, expected, "entries", depth)


def _more_keys_note(elided: int, /) -> str:
    """``"... (5 more keys hold a different value)"``, and the singular of it."""
    if elided == 1:
        return "... (1 more key holds a different value)"
    return "... (" + str(elided) + " more keys hold a different value)"
