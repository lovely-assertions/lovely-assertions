"""Turning what the walk collected into the block a failure message carries.

The split from the walk is what makes this a file of its own. A difference record
holds *values*, and every step from a value to a line of text -- formatting it,
clipping it, counting what was left out -- reads a ``ContextVar``, which the walk
must not pay for: ``is_not_equivalent_to`` passes by finding differences, so the
walk is a path a passing assertion takes. Turning the findings into prose happens
here instead, once, after the verdict is already settled.

The case that earns the file its awkward parts is the pair whose two renderings
come out the same. A block reporting that a value differs from itself reads as a
bug in the test runner rather than in the test, so the causes worth naming are
named outright instead of leaving the reader with one ``repr`` printed twice.

One difference record is built here rather than beside the others: a leaf pair
carries a sentence when ``==`` refused to answer, and a sentence is prose. It is
made of a constant and an exception's type name, which is the only kind of note
the walk can afford to compose.
"""

from lovely_assertions._equivalence._findings import (
    SHOWS_ITEMS,
    SHOWS_NOTE,
    SHOWS_TYPES,
    Difference,
    Findings,
    pair_difference,
)
from lovely_assertions._equivalence._labels import INDENT, clip, render_items
from lovely_assertions._equivalence._options import Equivalency, configuration
from lovely_assertions._equivalence._paths import ROOT
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._reflection import is_float_nan, qualified
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# Rendering. Everything below here runs on the reporting path only, which is what
# licenses it to read `current_formatting()`.
# ---------------------------------------------------------------------------
def render(findings: Findings, options: Equivalency, /) -> str:
    """The block: the differences, what was left out, and what was in force."""
    max_items = current_formatting().max_items
    lines = [INDENT + _render_difference(difference) for difference in findings.items[:max_items]]
    elided = len(findings.items) - max_items
    if elided > 0:
        lines.append(INDENT + "... (" + count_of(elided, "more difference") + ")")
    if findings.full:
        # Said as well as the count, not instead of it: the count is how many
        # findings are being held back, and this is the separate fact that the
        # walk stopped looking. Two mismatched graphs of ten thousand nodes have
        # both to report, and neither says the other.
        lines.append(
            INDENT
            + "... (the comparison stopped at "
            + count_of(findings.limit, "difference")
            + ")"
        )
    lines.append(INDENT + "(compared with " + configuration(options) + ")")
    return "\n" + "\n".join(lines)


def _render_difference(difference: Difference, /) -> str:
    """One finding as one line: where it is, then what is wrong there."""
    where = clip(difference.path or ROOT)
    shows = difference.shows
    if shows == SHOWS_NOTE:
        return where + ": " + difference.note
    if shows == SHOWS_ITEMS:
        return where + ": " + difference.note + " " + render_items(difference.items)
    pair = difference.pair
    if pair is None:
        # Unreachable: the two remaining shapes are built with a pair. Kept so
        # that the narrowing is done by the code rather than by a cast.
        return where + ": " + difference.note
    if shows == SHOWS_TYPES:
        return where + ": " + _different_types_note(pair[0], pair[1])
    return where + ": " + _values_note(pair[0], pair[1], difference.note)


def _values_note(actual: object, expected: object, note: str, /) -> str:
    """``actual instead of expected``, and the one case where that says nothing.

    Compared unclipped: two values that part company past the clip would otherwise
    be declared identical-looking, which is a claim rather than a truncation.
    """
    rendered = format_value(actual)
    other = format_value(expected)
    if rendered == other:
        body = _look_alike_note(actual, expected, clip(rendered))
    else:
        body = clip(rendered) + " instead of " + clip(other)
    if note:
        return body + " " + note
    return body


def _look_alike_note(actual: object, expected: object, rendered: str, /) -> str:
    """Why two values that render the same are still not equivalent.

    This is the failure that reads as a bug in the test runner, and it has a small
    number of causes worth naming outright. The last of them is particular to this
    assertion: a type with neither an ``__eq__`` nor any readable member gives the
    engine nothing at all to compare, and saying so is more use than repeating the
    ``repr`` twice.
    """
    if is_float_nan(actual) or is_float_nan(expected):
        return "both are " + rendered + ", and a NaN is equal to nothing, itself included"
    subject_type = type(actual)
    if subject_type is type(expected) and subject_type.__eq__ is object.__eq__:
        return (
            "both render as "
            + rendered
            + ", but "
            + subject_type.__name__
            + " has no __eq__ and no members to compare, so they compare by identity"
        )
    return "both render as " + rendered + ", but they are not equivalent"


def _different_types_note(actual: object, expected: object, /) -> str:
    """Name both types, in the vocabulary the rest of the block uses."""
    actual_type = type(actual)
    expected_type = type(expected)
    actual_name = actual_type.__name__
    expected_name = expected_type.__name__
    if actual_name == expected_name:
        # Two classes of one name is the case where the two reprs are of no help
        # whatsoever, so it is the one worth spelling out in full.
        actual_name = qualified(actual_type)
        expected_name = qualified(expected_type)
    if actual_name == expected_name:
        return (
            "types differ: both are called "
            + actual_name
            + ", but they are not the same class object"
        )
    return "types differ: " + actual_name + " instead of " + expected_name


def leaf_difference(
    path: str, actual: object, expected: object, settled: bool | None, /
) -> Difference:
    """A pair with no members to take apart, and the note when ``==`` would not answer."""
    if settled is None:
        return pair_difference(
            path,
            actual,
            expected,
            "(comparing them raised " + _comparison_error(actual, expected) + ")",
        )
    return pair_difference(path, actual, expected)


def _comparison_error(actual: object, expected: object, /) -> str:
    """Name the exception ``==`` raised, by asking it again on the reporting path.

    Asked a second time rather than carried out of the walk: an exception held in
    a difference record keeps a traceback, and with it every frame and local of
    the failing comparison, alive until the message is built. The second call
    costs one more failed comparison on a path that is already reporting.
    """
    try:
        _ = actual == expected
    # naming it is the whole point
    except Exception as error:
        return type(error).__name__
    return "an exception"
