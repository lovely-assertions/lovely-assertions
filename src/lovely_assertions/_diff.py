"""Rich differences between two values that were supposed to be equal.

pytest's assert rewriting already prints a serviceable diff for ``assert a == b``.
This module exists for the cases where it does not help: a multi-line string
flattened into one escaped ``repr``, a mapping of twenty keys of which one holds
the wrong value, a record of twelve fields of which one holds the wrong value,
two collections with the same items in a different order, two values that render
identically and still are not equal.

One entry point, :func:`describe_difference`, called on the failure path only and
appended to a message that already carries both ``repr``\\ s. It therefore says
only what those reprs cannot: *where* the two values part company.

Three rules shape everything here.

**It never raises.** A subject whose ``repr`` or ``__eq__`` blows up must still
produce an assertion *failure*, not an error inside the assertion library. Every
path degrades to ``""``.

**It is bounded, and the bounds are a scope rather than four constants.** Ten
items, twenty diff lines, a hundred and twenty characters per value, two levels of
nesting -- whatever is left out is counted in the message rather than dropped
silently. Those four numbers live as the defaults on
:class:`~lovely_assertions.FormattingOptions` and are read through
:func:`~lovely_assertions.current_formatting` at each point of use, so the reader
whose failing row is the four hundredth can ask to see it::

    with formatting(max_items=100):
        expect(rows).is_equal_to(expected)

Reading them is a ``ContextVar`` lookup, which a *passing* assertion must never
pay for, so every one of those reads has to stay where the whole of this module
already lives: on the failure path.

**It formats with concatenation, never f-strings.** Nothing here runs on the happy
path, but the package's rule is that a message is never built outside the argument
list of a ``_fail(...)`` call -- Python evaluates arguments eagerly, so an f-string
one line too early costs every passing assertion in every suite -- and a rule with
no exceptions is worth more than the syntax it costs (``_render`` in
``_sequence.py`` does the same).
"""

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Any, Final, TypeIs, cast

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._reflection import (
    attrs_field_names,
    dataclass_field_names,
    instance_dict_names,
    is_float_nan,
    is_mapping,
    is_set,
    named_tuple_field_names,
    qualified,
    slot_names,
)
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["describe_difference", "render_operand"]

# The four *legibility* bounds -- how many items, how many characters, how many
# diff lines, how deep -- are deliberately absent from this block. They are the
# defaults on `_formatting.FormattingOptions` and are read through
# `current_formatting()` at each point of use, so that `formatting(...)` can raise
# one of them for the message somebody is debugging. Keeping a copy here as well
# would be a second source of truth, and the two would drift.
#
# What stays below is of a different kind. These bound what the *engine* may cost
# while a test is already failing, and a caller who could raise them could hang a
# red test run -- so they are not offered.

#: Lines of each text handed to ``difflib`` once the identical head and tail are
#: off. Its matching cost grows with the square of the number of *changed* lines,
#: so two long texts that differ throughout can spend many seconds to yield the
#: handful of lines this prints -- and time spent inside a failing assertion is
#: indistinguishable, to the person waiting on it, from a hung test run. Capping
#: the input caps that cost whatever the two texts hold.
_MAX_DIFF_INPUT: Final = 2000

#: Lines of unchanged text a unified diff prints around a change -- ``difflib``'s
#: own default, named here because the windowing has to leave at least this many
#: identical lines on each side of one or it would change the hunks themselves.
_DIFF_CONTEXT: Final = 3

#: Combined ``repr`` length under which two strings are simply read side by side.
#: The message carrying this block prints both already; under this budget the pair
#: still fits on one terminal line, and pointing at a column of a fourteen-
#: character string is noise, not help.
_TEXT_BUDGET: Final = 40

#: Characters of common prefix quoted back to locate a difference inside a long
#: single-line string. Enough to search for, short enough to sit in a clause.
_CONTEXT_CHARS: Final = 20

#: Unhashable items tolerated before the multiset comparison gives up. Matching
#: them is quadratic and this runs while a test is already failing, so the worst
#: case stays bounded; the positional findings are reported either way.
_MAX_UNHASHABLE: Final = 100

#: One level of the block. The whole thing is indented under a one-line message.
_INDENT: Final = "  "


def describe_difference(actual: object, expected: object, /) -> str:
    """A rendered account of how two unequal values differ.

    Returns "" when a plain repr of both already tells the whole story, so the
    caller can append the result unconditionally. Otherwise returns a block that
    starts with a newline and does not end with one.

    The blanket ``except`` is the contract, not laziness: this runs on the failure
    path of an assertion that has *already* failed, and a hostile ``repr``, a
    ``__eq__`` that raises, or a self-referential structure must cost the reader a
    less detailed message -- never turn their test failure into a library error.
    """
    try:
        lines = _describe(actual, expected, 0)
    except Exception:
        return ""
    if not lines:
        return ""
    return "\n" + "\n".join(lines)


def _describe(actual: object, expected: object, depth: int, /) -> list[str]:
    """The lines describing one pair, without the leading newline."""
    lines = _describe_by_kind(actual, expected, depth)
    if lines:
        return lines
    return _describe_look_alike(actual, expected, depth)


def _describe_by_kind(actual: object, expected: object, depth: int, /) -> list[str]:
    """Route a pair to the describer for its kind; ``[]`` when the kinds disagree.

    Two values of different kinds have nothing structural in common, so there is
    nothing to say that their reprs do not already show. ``str`` is tested first
    because a string is also a ``Sequence``, and ``bytes`` is excluded for the
    same reason it is excluded from ``SequenceExpect``: iterating it yields
    integers, which is never what the reader meant.

    The position of the last branch is the load-bearing part. Every object is
    asked about *after* the sequence branch, so that a list subclass which happens
    to carry an attribute is still diffed as the list its ``__eq__`` compares it
    as. A NamedTuple is a tuple and so lands in the sequence branch too, which
    reads its names from inside -- see :func:`_describe_sequence_or_record`.
    """
    if isinstance(actual, str) and isinstance(expected, str):
        return _describe_text(actual, expected, depth)
    if is_mapping(actual) and is_mapping(expected):
        return _describe_mapping(actual, expected, depth)
    if is_set(actual) and is_set(expected):
        return _describe_set(actual, expected, depth)
    if _is_plain_sequence(actual) and _is_plain_sequence(expected):
        return _describe_sequence_or_record(actual, expected, depth)
    return _describe_object(actual, expected, depth)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def _describe_text(actual: str, expected: str, depth: int, /) -> list[str]:
    """A unified diff for multi-line strings, a column for single-line ones.

    Multi-line is where ``but was 'line1\\nline2\\n...'`` stops being a message and
    becomes a puzzle, so that is where the diff earns its import. Short strings get
    nothing: the caller already printed both, and two twelve-character reprs on one
    line are read faster than any diff of them.
    """
    if len(format_value(actual)) + len(format_value(expected)) <= _TEXT_BUDGET:
        return []
    actual_lines = actual.splitlines()
    expected_lines = expected.splitlines()
    if len(actual_lines) <= 1 and len(expected_lines) <= 1:
        return [_indent(depth) + _first_text_difference(actual, expected)]
    if actual_lines == expected_lines:
        ending = _line_ending_difference(actual, expected)
        # Nothing to name here means the two texts are the same string, so the
        # difference is in what `__eq__` did with them. Declining hands the pair
        # on to `_describe_look_alike`, which is where that finding is worded.
        return [] if ending is None else [_indent(depth) + ending]
    return _unified_diff(actual_lines, expected_lines, depth)


def _unified_diff(actual_lines: list[str], expected_lines: list[str], depth: int, /) -> list[str]:
    """``difflib``'s unified diff over a bounded window, indented and labelled.

    The ``---``/``+++`` header is dropped and replaced by one line naming the two
    sides, because at 6pm nobody should have to remember which of the two markers
    means which. Hunk headers stay, and stay whole at any bound: in a long text
    they are the line numbers, and :func:`_shift_hunk` puts back the numbers the
    windowing took off.

    ``difflib`` is never handed the whole text -- see :data:`_MAX_DIFF_INPUT`.
    """
    import difflib  # noqa: PLC0415  (importing this package must not import difflib)

    max_diff_lines = current_formatting().max_diff_lines
    start, actual_core, expected_core = _diff_window(actual_lines, expected_lines)
    capped = max(len(actual_core), len(expected_core)) > _MAX_DIFF_INPUT
    if capped:
        actual_core = actual_core[:_MAX_DIFF_INPUT]
        expected_core = expected_core[:_MAX_DIFF_INPUT]
    paired = difflib.unified_diff(expected_core, actual_core, lineterm="", n=_DIFF_CONTEXT)
    body = list(paired)[2:]
    # Insurance for the windowing rather than a case this caller can reach: the
    # first line the two texts disagree on always sits within the context of the
    # window's start and so within the input cap, leaving `difflib` a hunk to emit.
    if not body:
        return []
    indent = _indent(depth)
    inner = indent + _INDENT
    lines = [indent + "the strings differ (- expected, + actual):"]
    lines.extend(
        inner + _shift_hunk(text, start) for text in _clip_diff_lines(body, max_diff_lines)
    )
    if capped:
        # The elided count would be a number about the window, not about the
        # texts, and a precise-looking wrong number is worse than no number.
        lines.append(
            inner + "... (more diff lines; only " + str(_MAX_DIFF_INPUT) + " lines were compared)"
        )
        return lines
    elided = len(body) - max_diff_lines
    if elided > 0:
        lines.append(inner + "... (" + count_of(elided, "more diff line") + ")")
    return lines


def _diff_window(
    actual_lines: list[str], expected_lines: list[str], /
) -> tuple[int, list[str], list[str]]:
    """The slice of both texts the diff has to look at, and the line it starts on.

    Identical lines further out than the context a unified diff prints cannot
    change a hunk -- only how long ``difflib`` spends deciding that they match.
    Dropping them costs one linear scan where the matching is quadratic, and the
    line numbers they carried are restored by :func:`_shift_hunk`.
    """
    head = _common_head(actual_lines, expected_lines)
    tail = _common_tail(actual_lines, expected_lines, head)
    start = max(0, head - _DIFF_CONTEXT)
    return (
        start,
        actual_lines[start : len(actual_lines) - tail + _DIFF_CONTEXT],
        expected_lines[start : len(expected_lines) - tail + _DIFF_CONTEXT],
    )


def _common_head(actual: list[str], expected: list[str], /) -> int:
    """How many leading lines the two texts share."""
    limit = min(len(actual), len(expected))
    index = 0
    while index < limit and actual[index] == expected[index]:
        index += 1
    return index


def _common_tail(actual: list[str], expected: list[str], head: int, /) -> int:
    """How many trailing lines they share, without counting the head twice."""
    limit = min(len(actual), len(expected)) - head
    index = 0
    while index < limit and actual[-1 - index] == expected[-1 - index]:
        index += 1
    return index


def _is_hunk_header(line: str, /) -> bool:
    """Whether a diff line is ``difflib``'s ``@@ -a,b +c,d @@`` position marker."""
    return line.startswith("@@ ")


def _shift_hunk(line: str, offset: int, /) -> str:
    """Put a hunk header's line numbers back where the untrimmed text had them."""
    if offset == 0 or not _is_hunk_header(line):
        return line
    head, _, rest = line.partition(" ")
    removed, _, rest = rest.partition(" ")
    added, _, trailer = rest.partition(" ")
    # Insurance for the windowing rather than a case this caller can reach: a
    # header arrives exactly as `difflib` wrote it, closing `@@` included.
    if not trailer:
        return line
    return " ".join((head, _shift_range(removed, offset), _shift_range(added, offset), trailer))


def _shift_range(field: str, offset: int, /) -> str:
    """``"-1,4"`` moved forward by the number of lines the window dropped."""
    start, comma, length = field[1:].partition(",")
    # Insurance for the windowing rather than a case this caller can reach:
    # `difflib` writes a range as a line number and an optional `,length`, so
    # what precedes the comma is always digits.
    if not start.isdigit():
        return field
    return field[:1] + str(int(start) + offset) + comma + length


def _clip_diff_lines(body: list[str], limit: int, /) -> list[str]:
    """Cut over-long diff lines down around the point where the pair parts company.

    Clipping a minified line from the start renders two *different* lines
    identically, which is the one thing a diff must never do. Only ``limit`` lines
    are kept, but a counterpart is looked for across the whole body: the line that
    says where a kept line was clipped may itself sit past the cut.

    Hunk headers are exempt, as the heading and the elision count around them
    already are. A header carries no text from either subject -- only the line
    numbers a reader searches by -- so a bound meant to keep a *value* readable
    has nothing to cut there, while cutting one leaves the numbers half-written
    and puts the clip's own "N more characters" where the second range belongs,
    for :func:`_shift_hunk` to read back as a line number the text never had.
    """
    max_chars = current_formatting().max_chars
    return [
        line
        if _is_hunk_header(line) or len(line) <= max_chars
        else _clip_around(line, _counterpart(body, index))
        for index, line in enumerate(body[:limit])
    ]


def _counterpart(body: list[str], index: int, /) -> str | None:
    """The added line facing this removed one, or the removed line it replaced.

    A unified diff writes a change as *every* removed line followed by *every*
    added one, so the line facing the k-th removal is the k-th addition -- not the
    neighbour. Pairing by adjacency instead faces most of a multi-line change with
    the wrong counterpart, and :func:`_clip_around` then clips from the start,
    where two different minified lines come out as the same run of characters and
    the same ellipsis.
    """
    marker = body[index][:1]
    if marker == "-":
        removed_start = _run_start(body, index, "-")
        added_start = _run_end(body, index, "-")
        return _facing(body, added_start + index - removed_start, "+")
    if marker == "+":
        added_start = _run_start(body, index, "+")
        if added_start == 0 or not body[added_start - 1].startswith("-"):
            return None
        removed_start = _run_start(body, added_start - 1, "-")
        return _facing(body, removed_start + index - added_start, "-")
    return None


def _run_start(body: list[str], index: int, marker: str, /) -> int:
    """First line of the unbroken run of ``marker`` lines containing ``index``."""
    start = index
    while start > 0 and body[start - 1].startswith(marker):
        start -= 1
    return start


def _run_end(body: list[str], index: int, marker: str, /) -> int:
    """One past the last line of that run."""
    end = index + 1
    while end < len(body) and body[end].startswith(marker):
        end += 1
    return end


def _facing(body: list[str], index: int, marker: str, /) -> str | None:
    """``body[index]`` when it exists and carries ``marker``; ``None`` otherwise."""
    if 0 <= index < len(body) and body[index].startswith(marker):
        return body[index]
    return None


def _clip_around(line: str, counterpart: str | None, /) -> str:
    """Keep the window of an over-long diff line that holds the actual difference."""
    if counterpart is None:
        return _clip(line)
    marker = line[:1]
    text = line[1:]
    start = max(0, _common_prefix_length(text, counterpart[1:]) - _CONTEXT_CHARS)
    if start == 0:
        return _clip(line)
    window = text[start : start + current_formatting().max_chars]
    dropped = len(text) - start - len(window)
    tail = "" if dropped <= 0 else "... (" + str(dropped) + " more characters)"
    return marker + "... (" + str(start) + " earlier characters) " + window + tail


def _first_text_difference(actual: str, expected: str, /) -> str:
    """Where two single-line strings part company, and on what.

    The index is quoted with the tail of the common prefix rather than a caret
    under the text: the message renders strings through ``repr``, where an escape
    sequence occupies several columns, so a caret would point at the wrong one for
    exactly the strings -- tabs, newlines, non-ASCII -- that need it most.
    """
    shared = _common_prefix_length(actual, expected)
    if shared == len(actual):
        return (
            "the first "
            + str(shared)
            + " characters match; actual ends there, expected continues with "
            + _clip(repr(expected[shared:]))
        )
    if shared == len(expected):
        return (
            "the first "
            + str(shared)
            + " characters match; expected ends there, actual continues with "
            + _clip(repr(actual[shared:]))
        )
    return (
        "first difference at index "
        + str(shared)
        + ": "
        + format_value(actual[shared])
        + " instead of "
        + format_value(expected[shared])
        + _after_clause(actual, shared)
    )


def _line_ending_difference(actual: str, expected: str, /) -> str | None:
    """Name the line whose terminator differs, or ``None`` when none of them does.

    A diff of two texts with identical lines is empty, so without this the reader
    would be told the strings differ and shown no difference at all -- the worst
    possible message for the one bug that is invisible in a terminal.

    ``None`` is the other half of that promise. Falling out of the loop means
    every line matched its counterpart down to the terminator, so the two texts
    are the same string and their line endings are precisely what does *not*
    differ -- a ``str`` subclass whose ``__eq__`` answers no is how a pair gets
    here. The caller has a clause for that; this function must not invent one.
    """
    actual_lines = actual.splitlines(keepends=True)
    expected_lines = expected.splitlines(keepends=True)
    for number, (left, right) in enumerate(zip(actual_lines, expected_lines, strict=False), 1):
        if left != right:
            return (
                "the lines are identical; line "
                + str(number)
                + " ends with "
                + _terminator(left)
                + ", not "
                + _terminator(right)
            )
    return None


def _terminator(line: str, /) -> str:
    """``"'\\r\\n'"`` or ``"no newline"`` -- how one line of text ends.

    The terminator is whatever ``splitlines`` broke on, not just ``\\r`` and
    ``\\n``: Python also breaks a string on a form feed, a vertical tab, U+2028
    and four more. Stripping a fixed set of characters instead would call every
    one of those "no newline", which is the one claim this message exists to make
    and the one it must never get wrong.
    """
    content = line.splitlines()[0] if line else ""
    if len(content) == len(line):
        return "no newline"
    return repr(line[len(content) :])


def _after_clause(text: str, index: int, /) -> str:
    """Quote the tail of the common prefix, so the reader can search for it."""
    if index == 0:
        return ""
    start = max(0, index - _CONTEXT_CHARS)
    leader = "..." if start > 0 else ""
    return ", after " + leader + repr(text[start:index])


def _common_prefix_length(actual: str, expected: str, /) -> int:
    """How many leading characters the two strings share."""
    limit = min(len(actual), len(expected))
    for index in range(limit):
        if actual[index] != expected[index]:
            return index
    return limit


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------
def _describe_sequence_or_record(
    actual: Sequence[object], expected: Sequence[object], depth: int, /
) -> list[str]:
    """Field names when both tuples agree on them, indices otherwise.

    A NamedTuple **is** a tuple, so the sequence describer claims it happily and
    reports "index 0" for a field the reader calls ``x`` and has never indexed by
    hand. The names are the better label -- but only while *both* sides declare
    the same ones.

    That condition is not fussiness. ``tuple.__eq__`` ignores the class, so
    ``Point(1, 2) == Coord(1, 2)`` is true: for two tuples with different names,
    or with none on one side, the values are what parted company and the indices
    are the only label both sides share. Naming the two *types* instead would be
    an account of the failure that is not true, and labelling one side's values
    with the other side's names would be worse. The names are also dropped when
    reading them yields nothing -- a tuple subclass is free to declare a
    ``_fields`` it does not carry, and an index diff beats an empty block.
    """
    names = named_tuple_field_names(actual)
    if names and names == named_tuple_field_names(expected):
        lines = _field_lines(actual, expected, names, names, depth)
        if lines:
            return lines
    return _describe_sequence(actual, expected, depth)


def _describe_sequence(
    actual: Sequence[object], expected: Sequence[object], depth: int, /
) -> list[str]:
    """Position first, then length, then what is surplus and what is absent.

    Order is what a sequence *is*, so the first line names an index. The set
    arithmetic comes after it and only when it adds something: for two lists that
    differ in one slot, "missing" and "extra" would just repeat the position line
    in a form that no longer says where.
    """
    indent = _indent(depth)
    index = _first_difference(actual, expected)
    lines: list[str] = []
    if index is not None:
        lines.extend(
            _pair_lines(
                "first difference at index " + str(index), actual[index], expected[index], depth
            )
        )
    if len(actual) != len(expected):
        lines.append(
            indent
            + "lengths differ: "
            + count_of(len(actual), "item")
            + ", expected "
            + str(len(expected))
        )
    lines.extend(_sequence_membership(actual, expected, index, indent))
    if lines:
        return lines
    return _type_note(actual, expected, "items", depth)


def _sequence_membership(
    actual: Sequence[object], expected: Sequence[object], index: int | None, indent: str, /
) -> list[str]:
    """Which items are surplus and which are absent, duplicates counted.

    Silent in the two cases where it would mislead: when the answer only echoes
    the differing position, and when the items cannot be matched cheaply -- see
    :func:`_unmatched`, which would rather say nothing than hang.
    """
    missing = _unmatched(expected, actual)
    extra = _unmatched(actual, expected)
    if missing is None or extra is None:
        return []
    if not missing and not extra:
        if index is None or len(actual) != len(expected):
            return []
        return [indent + "the same items, in a different order"]
    if index is not None and missing == [expected[index]] and extra == [actual[index]]:
        return []
    return _membership_lines(indent, missing, extra, "items")


def _first_difference(actual: Sequence[object], expected: Sequence[object], /) -> int | None:
    """Index of the first item that differs, ignoring any length mismatch."""
    for index in range(min(len(actual), len(expected))):
        if not _equal(actual[index], expected[index]):
            return index
    return None


def _unmatched(items: Sequence[object], against: Sequence[object], /) -> list[object] | None:
    """Items of ``items`` that ``against`` has no counterpart for, duplicates counted.

    ``None`` when the answer would cost more than it is worth. Hashable items are
    matched through a tally; unhashable ones -- a list of dicts is an ordinary
    subject -- fall back to a linear scan, which is quadratic overall, so past
    :data:`_MAX_UNHASHABLE` of them this declines to answer instead of hanging a
    test run that is already red.
    """
    tally = _tally(against)
    if tally is None:
        return None
    counts, unhashable = tally
    # The filter consumes as it goes: `_take` removes the counterpart it matched,
    # so three copies of an item in `items` only match three copies in `against`.
    return [item for item in items if not _take(item, counts, unhashable)]


def _tally(items: Sequence[object], /) -> tuple[dict[object, int], list[object]] | None:
    """Count the hashable items, list the rest; ``None`` past the unhashable cap."""
    counts: dict[object, int] = {}
    unhashable: list[object] = []
    for item in items:
        try:
            counts[item] = counts.get(item, 0) + 1
        except TypeError:
            if len(unhashable) == _MAX_UNHASHABLE:
                return None
            unhashable.append(item)
    return counts, unhashable


def _take(item: object, counts: dict[object, int], unhashable: list[object], /) -> bool:
    """Consume one occurrence of ``item``; ``False`` when there is none left."""
    try:
        remaining = counts.get(item, 0)
    except TypeError:
        for index, candidate in enumerate(unhashable):
            if _equal(candidate, item):
                del unhashable[index]
                return True
        return False
    if remaining == 0:
        return False
    counts[item] = remaining - 1
    return True


# ---------------------------------------------------------------------------
# Sets and mappings
# ---------------------------------------------------------------------------
def _describe_set(
    actual: AbstractSet[object], expected: AbstractSet[object], depth: int, /
) -> list[str]:
    """What is absent and what is surplus -- a set has no position to report."""
    indent = _indent(depth)
    missing = stable_order([item for item in expected if item not in actual])
    extra = stable_order([item for item in actual if item not in expected])
    lines = _membership_lines(indent, missing, extra, "items")
    if lines:
        return lines + _both_sides_nan_note(missing, extra, indent)
    return _type_note(actual, expected, "items", depth)


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


def _describe_mapping(
    actual: Mapping[object, object], expected: Mapping[object, object], depth: int, /
) -> list[str]:
    """Values that disagree first, then keys nobody expected and keys nobody wrote.

    The value lines come first because a wrong value under a right key is what a
    mapping comparison usually fails on, and because when it is a key that is
    missing there are no value lines to get in the way.
    """
    indent = _indent(depth)
    differing = [
        key for key in expected if key in actual and not _equal(actual[key], expected[key])
    ]
    max_items = current_formatting().max_items
    lines: list[str] = []
    for key in differing[:max_items]:
        # Clipped like every other rendered value: a mapping keyed by a request
        # body would otherwise put the whole body in the label, and the bound
        # this module advertises would hold for every line except that one.
        lines.extend(
            _pair_lines(
                "values differ at key " + _clip(format_value(key)),
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
    lines.extend(_membership_lines(indent, missing, extra, "keys"))
    if lines:
        return lines
    return _type_note(actual, expected, "entries", depth)


def _more_keys_note(elided: int, /) -> str:
    """``"... (5 more keys hold a different value)"``, and the singular of it."""
    if elided == 1:
        return "... (1 more key holds a different value)"
    return "... (" + str(elided) + " more keys hold a different value)"


def _membership_lines(
    indent: str, missing: list[object], extra: list[object], noun: str, /
) -> list[str]:
    """``missing``/``extra`` in one vocabulary: absent from actual, absent from expected."""
    lines: list[str] = []
    if missing:
        lines.append(indent + "missing " + noun + ": " + _render_items(missing))
    if extra:
        lines.append(indent + "extra " + noun + ": " + _render_items(extra))
    return lines


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------
def _describe_object(actual: object, expected: object, depth: int, /) -> list[str]:
    """Field by field, for the composite type Python actually has most of.

    Reached for anything the container describers did not claim: a dataclass, a
    ``__slots__`` class, a plain object with a ``__dict__``, and -- with nothing
    imported to recognise them -- an attrs class or a pydantic model. This is the
    one place pytest's rewriting still wins on the common case, because
    ``User(name='ann', age=30)`` against ``User(name='ann', age=31)`` is two
    reprs the reader has to diff by eye. (A NamedTuple is a record too, but it
    reaches its field names through the sequence branch, which is where being a
    tuple lands it; it arrives here only when the other side is not a sequence
    at all.)

    Silent for anything that resolves no fields at all, which is how ``3``, a
    function and a bare ``object()`` fall straight through to the look-alike
    clause below.
    """
    actual_fields = _field_names(actual)
    expected_fields = _field_names(expected)
    if not actual_fields or not expected_fields:
        return []
    actual_type = type(actual)
    expected_type = type(expected)
    if actual_type is not expected_type:
        return _cross_type_lines(actual, expected, actual_fields, expected_fields, depth)
    if actual_type.__eq__ is object.__eq__:
        # The fields are not why this failed and never could be: the type compares
        # by identity, so two instances are unequal however their fields read.
        # Returning nothing hands the pair to `_describe_look_alike`, which says
        # the thing that is actually wrong -- the type has no `__eq__`.
        return []
    return _field_lines(actual, expected, actual_fields, expected_fields, depth)


def _cross_type_lines(
    actual: object,
    expected: object,
    actual_fields: tuple[str, ...],
    expected_fields: tuple[str, ...],
    depth: int,
    /,
) -> list[str]:
    """Name both types, and add the fields only when the types leave room for them.

    Two *unrelated* types are the whole finding. Every generated ``__eq__`` in
    the ecosystem -- ``dataclass``, ``NamedTuple``, attrs, pydantic -- refuses a
    different class outright, so no arrangement of the fields would have made
    these two equal, and a field-by-field diff between them would bury the one
    finding there is under differences that are beside the point.

    When one type *derives* from the other the note is still worth its line and
    is no longer the whole answer: the ``__eq__`` they share is very often the
    hand-written ``isinstance`` kind, which compares a ``Cash`` to a ``Money``
    happily. Left alone, "types differ" would send the reader hunting for a
    construction bug when the amount is what is wrong. The membership half stays
    out -- a subclass declaring a field its base does not is what subclassing
    *is*, not a finding.
    """
    actual_type = type(actual)
    expected_type = type(expected)
    lines = [_indent(depth) + _different_types_note(actual_type, expected_type)]
    if not _is_related(actual_type, expected_type):
        return lines
    on_actual = frozenset(actual_fields)
    shared = [name for name in expected_fields if name in on_actual]
    lines.extend(_differing_field_lines(actual, expected, shared, depth))
    return lines


def _is_related(actual_type: type, expected_type: type, /) -> bool:
    """Whether one of the two types derives from the other.

    ``issubclass`` runs the metaclass's ``__subclasscheck__``, which is somebody
    else's code and is under no obligation to answer. Unrelated is the safe
    assumption when it will not: the note above stands on its own, where letting
    the exception out would cost the reader the whole block.
    """
    try:
        return issubclass(actual_type, expected_type) or issubclass(expected_type, actual_type)
    except Exception:
        return False


def _field_lines(
    actual: object,
    expected: object,
    actual_fields: tuple[str, ...],
    expected_fields: tuple[str, ...],
    depth: int,
    /,
) -> list[str]:
    """Fields that disagree first, then fields only one side carries.

    The same order, and the same vocabulary, as the mapping describer: a wrong
    value under a right name is what an object comparison usually fails on. The
    membership half only ever has anything to say for two objects read through
    their ``__dict__``, where the field set belongs to the instance rather than
    to the class.
    """
    on_actual = frozenset(actual_fields)
    on_expected = frozenset(expected_fields)
    shared = [name for name in expected_fields if name in on_actual]
    lines = _differing_field_lines(actual, expected, shared, depth)
    missing: list[object] = [name for name in expected_fields if name not in on_actual]
    extra: list[object] = [name for name in actual_fields if name not in on_expected]
    lines.extend(_membership_lines(_indent(depth), missing, extra, "fields"))
    return lines


def _differing_field_lines(
    actual: object, expected: object, names: list[str], depth: int, /
) -> list[str]:
    """The shared fields that hold different values, capped and counted."""
    differing = _differing_fields(actual, expected, names)
    max_items = current_formatting().max_items
    lines: list[str] = []
    for name, actual_value, expected_value in differing[:max_items]:
        # Clipped like every other rendered label, for the same reason a mapping
        # key is: a name read off an instance dictionary is not always short.
        lines.extend(_pair_lines("field " + _clip(name), actual_value, expected_value, depth))
    elided = len(differing) - max_items
    if elided > 0:
        lines.append(_indent(depth) + _more_fields_note(elided))
    return lines


def _differing_fields(
    actual: object, expected: object, names: list[str], /
) -> list[tuple[str, object, object]]:
    """The fields that hold different values, with both values already read."""
    found: list[tuple[str, object, object]] = []
    for name in names:
        pair = _field_pair(actual, expected, name)
        if pair is not None:
            found.append((name, *pair))
    return found


def _field_pair(actual: object, expected: object, name: str, /) -> tuple[object, object] | None:
    """Both sides of one field, or ``None`` when there is nothing to report.

    ``None`` covers the equal case and every case this cannot answer: a property
    that raises, a ``__slots__`` entry that was never assigned, an ``__eq__``
    that blows up. Guarded per field rather than around the loop on purpose -- one
    hostile member of a twelve-field record must cost the reader that field, not
    the other eleven.
    """
    try:
        actual_value = getattr(actual, name)
        expected_value = getattr(expected, name)
        if _equal(actual_value, expected_value):
            return None
    except Exception:
        return None
    return actual_value, expected_value


def _more_fields_note(elided: int, /) -> str:
    """``"... (5 more fields hold a different value)"``, and the singular of it."""
    if elided == 1:
        return "... (1 more field holds a different value)"
    return "... (" + str(elided) + " more fields hold a different value)"


def _different_types_note(actual_type: type, expected_type: type, /) -> str:
    """Name both types, in the vocabulary the rest of the block uses."""
    actual_name = actual_type.__name__
    expected_name = expected_type.__name__
    if actual_name == expected_name:
        # Two classes of one name is the case where the two reprs above are of no
        # help whatsoever, so it is the one worth spelling out in full.
        actual_name = qualified(actual_type)
        expected_name = qualified(expected_type)
    if actual_name == expected_name:
        return (
            "types differ: both are called "
            + actual_name
            + ", but they are not the same class object"
        )
    # "actual instead of expected", the order every other line of the block uses.
    # An article would have to go in front of each name, and no rule on a first
    # letter gets both "a Admin" and "an User" right.
    return "types differ: " + actual_name + " instead of " + expected_name


def _field_names(value: object, /) -> tuple[str, ...]:
    """The names that make this object what it is; the first to answer wins.

    ``dataclasses.fields`` leads because it is the only resolver that knows which
    fields the generated ``__eq__`` actually reads, and it is terminal for the
    same reason: fall through from it and a ``field(compare=False)`` comes back
    in through ``vars`` -- on the one type this was written for. Then a
    NamedTuple's own ``_fields``; then ``__attrs_attrs__``, for exactly the
    reason ``dataclasses.fields`` leads, since ``attrs`` spells the same
    exclusion ``eq=False``; then ``__slots__`` *together with* the instance
    dictionary, which is what answers for a plain class and for pydantic v2,
    neither of which is imported to be recognised.

    Skipping the ``attrs`` step is the mistake the order exists to prevent: an
    ``eq=False`` field would reach ``vars`` and be reported as a difference under
    a heading saying the objects are unequal, when the ``__eq__`` that said so
    never looked at it. Every resolver in the package reads its leaves from
    ``_reflection.py``, so no two of them can answer this differently.

    The last two are added rather than raced. An object has both storages more
    often than it looks: a ``__slots__`` base whose subclass does not repeat the
    declaration keeps the base's fields in slots and every one the subclass adds
    in a ``__dict__``, and reading only the winner would report the two fields it
    found and stay silent about the two it did not -- an incomplete answer that
    reads exactly like a complete one.
    """
    if isinstance(value, type):
        # A class's own ``__dict__`` holds the methods it defines, not the state
        # an instance carries; read as fields it would have two classes differ in
        # ``encode``. A class is not a record.
        return ()
    subject_type = type(value)
    if hasattr(subject_type, "__dataclass_fields__"):
        return dataclass_field_names(value)
    named = named_tuple_field_names(value)
    if named:
        return named
    attributes = attrs_field_names(value)
    if attributes:
        return attributes
    slots = slot_names(subject_type)
    members = instance_dict_names(value)
    if not slots:
        return members
    return slots + tuple(name for name in members if name not in slots)


# ---------------------------------------------------------------------------
# Pairs, notes and rendering
# ---------------------------------------------------------------------------
def _pair_lines(label: str, actual: object, expected: object, depth: int, /) -> list[str]:
    """One differing pair: inline when short, as a nested block when there is more.

    Nesting stops at ``max_depth``. Past it the pair is rendered inline, which is
    also the base case that keeps a self-referential structure from taking the
    stack with it.
    """
    indent = _indent(depth)
    if depth < current_formatting().max_depth:
        # `_describe_by_kind`, not `_describe`: a structure is worth descending
        # into even when the two sides render alike, and when it is *not* a
        # structure the look-alike clause below says so on one line rather than
        # opening a block to hold a single sentence.
        nested = _describe_by_kind(actual, expected, depth + 1)
        if nested:
            return [indent + label + ":", *nested]
    # Compared unclipped: two values that part company past the clip would
    # otherwise be declared identical-looking, which is a claim, not a truncation.
    rendered = format_value(actual)
    other = format_value(expected)
    if rendered == other:
        return [indent + label + ": " + _look_alike_clause(actual, expected, _clip(rendered))]
    return [indent + label + ": " + _clip(rendered) + " instead of " + _clip(other)]


def _describe_look_alike(actual: object, expected: object, depth: int, /) -> list[str]:
    """The one thing two reprs cannot say: that they are the same and the values are not.

    This is the failure that reads as a bug in the test runner -- ``to equal
    Point(1, 2), but was Point(1, 2)`` -- and it has a small number of causes worth
    naming outright.
    """
    rendered = format_value(actual)
    if rendered != format_value(expected):
        return []
    return [_indent(depth) + _look_alike_clause(actual, expected, _clip(rendered))]


def _look_alike_clause(actual: object, expected: object, rendered: str, /) -> str:
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


def _type_note(actual: object, expected: object, noun: str, depth: int, /) -> list[str]:
    """The note for two containers holding the same ``noun`` that are still unequal.

    ``[1, 2] == (1, 2)`` is false and the reprs differ by two characters. Saying
    which two saves a reader the minute they would otherwise spend re-reading them.
    """
    actual_type = type(actual)
    expected_type = type(expected)
    if actual_type is expected_type:
        return []
    return [
        _indent(depth)
        + "the same "
        + noun
        + ", but actual is a "
        + actual_type.__name__
        + " and expected is a "
        + expected_type.__name__
    ]


def _render_items(items: list[object], /) -> str:
    """Render a computed list of items, truncated like every other collection."""
    max_items = current_formatting().max_items
    shown = [_clip(format_value(item)) for item in items[:max_items]]
    elided = len(items) - max_items
    if elided > 0:
        return "[" + ", ".join(shown) + ", ... (" + str(elided) + " more)]"
    return "[" + ", ".join(shown) + "]"


def render_operand(value: object, /) -> str:
    """Render one side of an equality failure, clipped to the same budget as a diff.

    ``is_equal_to`` prints both operands before the difference block. A bare
    ``repr`` there undoes everything this module does about size: two large
    collections print in full, and the reader scrolls past both of them to reach
    the few lines that say where they part company. Clipped, the operands stay a
    sanity check on *what* was compared, and the block explains how they differ.

    Rendering goes through the formatter registry, so a domain type with a
    registered formatter reads as itself here rather than as its address. Clipping
    stays outside it: the budget belongs to this message, not to the formatter.
    """
    return _clip(format_value(value))


def _clip(text: str, /) -> str:
    """Cut an over-long rendering down, saying how much was cut.

    The bound is read here rather than passed in, at every single place a value is
    rendered. That is a ``ContextVar`` lookup per rendered value, which is
    affordable precisely because none of it happens until an assertion has already
    failed -- and it is what lets one ``formatting(...)`` block widen every value
    in a message without threading an options record through every function in the
    module.
    """
    max_chars = current_formatting().max_chars
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (" + str(len(text) - max_chars) + " more characters)"


def _indent(depth: int, /) -> str:
    """The block sits under a one-line message, and nests with the structure."""
    return _INDENT * (depth + 1)


def stable_order[T](items: list[T], /) -> list[T]:
    """Impose an order on items that have none, so two runs read the same.

    Sets are unordered and CPython's iteration order for strings depends on the
    hash seed, which would make a failure message differ between runs of the same
    test. Mixed or unorderable items keep iteration order -- an arbitrary order
    beats an exception raised while rendering somebody else's failure.

    No leading underscore: ``_collection`` renders the same kind of container in
    the same kind of message and needs the same answer, and two implementations
    free to drift would eventually give a reader two different orders for one
    collection.

    ``Exception`` rather than ``TypeError``, matching the twin in
    ``_equivalence.py``, because a ``__lt__`` is somebody else's code and may
    raise whatever it likes. Narrowed to ``TypeError``, a set of hostile members
    costs the reader the *entire* difference block: the exception escapes to the
    guard in :func:`describe_difference`, which degrades to ``""``, and the
    message is two reprs and nothing else. Giving up on the order must not mean
    giving up on the items.
    """
    try:
        return sorted(cast("list[Any]", items))
    # Unorderable items keep the order they came in.
    except Exception:
        return items


def _equal(actual: object, expected: object, /) -> bool:
    """Python's own containment rule: identity first, then equality.

    Identity first is what makes a ``float("nan")`` compare equal to itself, the
    same rule ``list.__eq__`` and ``dict.__eq__`` apply internally, and the one
    ``_mapping.py`` spells out at each of its comparison sites.
    """
    return actual is expected or bool(actual == expected)


def _is_plain_sequence(value: object, /) -> TypeIs[Sequence[object]]:
    """A sequence whose items are what the reader means by items.

    ``str`` has its own describer, and iterating ``bytes`` yields integers -- a
    diff of those would report positions in a value nobody indexed by hand.
    """
    return isinstance(value, Sequence) and not isinstance(
        value, str | bytes | bytearray | memoryview
    )
