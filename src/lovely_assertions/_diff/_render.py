"""The shared rendering: how one disagreeing pair is put on the page.

Every describer ends up here, which is why it holds no opinion about what it was
handed. A pair with structure underneath it is shown nested, by re-entering the
engine one level down; a pair without is shown inline. Membership -- what is
missing, what is surplus -- reads the same whatever kind of container produced it.

The re-entry is the one import in this package that points backwards, and it is
deferred inside the function that needs it. Nesting is a property of the value
being described, not of the module graph, so the alternative is a cycle at import
time to express something that only ever happens at call time.
"""

from lovely_assertions._diff._primitives import clip, indentation
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._reflection import is_float_nan

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def pair_lines(label: str, actual: object, expected: object, depth: int, /) -> list[str]:
    """One differing pair: inline when short, as a nested block when there is more.

    Nesting stops at ``max_depth``. Past it the pair is rendered inline, which is
    also the base case that keeps a self-referential structure from taking the
    stack with it.
    """
    # Deferred because the dispatch imports this module to reach
    # `describe_look_alike`, so naming it at module level here is a cycle. What it
    # costs instead is a `sys.modules` lookup, on a path where a test has already
    # failed.
    from lovely_assertions._diff._dispatch import describe_by_kind  # noqa: PLC0415

    indent = indentation(depth)
    if depth < current_formatting().max_depth:
        # `describe_by_kind`, not `_describe`: a structure is worth descending
        # into even when the two sides render alike, and when it is *not* a
        # structure the look-alike clause below says so on one line rather than
        # opening a block to hold a single sentence.
        nested = describe_by_kind(actual, expected, depth + 1)
        if nested:
            return [indent + label + ":", *nested]
    # Compared unclipped: two values that part company past the clip would
    # otherwise be declared identical-looking, which is a claim, not a truncation.
    rendered = format_value(actual)
    other = format_value(expected)
    if rendered == other:
        return [indent + label + ": " + look_alike_clause(actual, expected, clip(rendered))]
    return [indent + label + ": " + clip(rendered) + " instead of " + clip(other)]


def describe_look_alike(actual: object, expected: object, depth: int, /) -> list[str]:
    """The one thing two reprs cannot say: that they are the same and the values are not.

    This is the failure that reads as a bug in the test runner -- ``to equal
    Point(1, 2), but was Point(1, 2)`` -- and it has a small number of causes worth
    naming outright.
    """
    rendered = format_value(actual)
    if rendered != format_value(expected):
        return []
    return [indentation(depth) + look_alike_clause(actual, expected, clip(rendered))]


def look_alike_clause(actual: object, expected: object, rendered: str, /) -> str:
    """Why two values that render as ``rendered`` are still not equal."""
    if is_float_nan(actual) or is_float_nan(expected):
        return "both are " + rendered + ", and a NaN is equal to nothing, itself included"
    subject_type = type(actual)
    if subject_type is type(expected) and subject_type.__eq__ is object.__eq__:
        return (
            "both render as "
            + rendered
            + ", but "
            + subject_type.__name__
            + " does not define __eq__, so they compare by identity"
        )
    return "both render as " + rendered + ", but they are not equal"


def render_items(items: list[object], /) -> str:
    """Render a computed list of items, truncated like every other collection."""
    max_items = current_formatting().max_items
    shown = [clip(format_value(item)) for item in items[:max_items]]
    elided = len(items) - max_items
    if elided > 0:
        return "[" + ", ".join(shown) + ", ... (" + str(elided) + " more)]"
    return "[" + ", ".join(shown) + "]"


def membership_lines(
    indent: str, missing: list[object], extra: list[object], noun: str, /
) -> list[str]:
    """``missing``/``extra`` in one vocabulary: absent from actual, absent from expected."""
    lines: list[str] = []
    if missing:
        lines.append(indent + "missing " + noun + ": " + render_items(missing))
    if extra:
        lines.append(indent + "extra " + noun + ": " + render_items(extra))
    return lines
