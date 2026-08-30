"""The rich-difference engine: ``describe_difference``.

The block this produces is read by somebody whose test has just gone red, so the
tests pin the *rendered text*, not the fact that something came back. A diff test
that only asserts truthiness would pass on a block that points at the wrong index.

Three properties get their own attention, because each of them is a promise the
caller relies on:

*It says nothing when there is nothing to add* -- the message that carries this
block already prints both ``repr``\\ s.

*It stays bounded* -- ten items, twenty diff lines, and a count of whatever was
left out. Those numbers are not constants in ``_diff``: they are the defaults
on ``FormattingOptions``, read from the formatting scope at the point of use.
Both halves get their own section below -- the defaults are what a caller who
sets no scope gets, and a ``formatting(...)`` block really does move them.

*It never raises* -- a hostile subject costs the reader detail, never an error in
place of their assertion failure.
"""

import time
from importlib import import_module
from pathlib import Path
from typing import Any, Final

import pytest

# `formatting` comes from its private module because the package root does not
# re-export it.
import lovely_assertions
from _package import module_name, sources
from conftest import Detonator
from lovely_assertions import AssertionFailure, _diff, expect
from lovely_assertions._diff import describe_difference
from lovely_assertions._formatting import _scope, current_formatting, formatting

#: Long enough to blow the budget for reading two reprs side by side on one line.
LEFT: Final = "the quick brown fox jumps over the lazy dog"
RIGHT: Final = "the quick brown fox jumped over the lazy dog"


class Point:
    """A value type that forgot ``__eq__`` -- the classic look-alike failure."""

    __slots__ = ("x",)

    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return "Point(" + str(self.x) + ")"


class Contrary(str):
    """A string that is equal to nothing -- the look-alike failure, in text.

    It is the only way two texts reach the engine with the same characters, the
    same lines and the same terminators: every other route out of ``is_equal_to``
    has already established that the bytes differ somewhere.
    """

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return 0


class Hostile:
    """Everything a difference might touch, wired to explode."""

    __slots__ = ()

    def __repr__(self) -> str:
        raise RuntimeError("repr exploded")

    def __eq__(self, other: object) -> bool:
        raise RuntimeError("eq exploded")

    def __hash__(self) -> int:
        raise RuntimeError("hash exploded")


def block(actual: object, expected: object, /) -> list[str]:
    """The rendered lines, with the leading newline stripped."""
    rendered = describe_difference(actual, expected)
    assert rendered.startswith("\n")
    return rendered[1:].split("\n")


# ---------------------------------------------------------------------------
# The contract: silence, and the shape of what is not silence
# ---------------------------------------------------------------------------
def test_says_nothing_when_two_short_strings_are_read_side_by_side() -> None:
    assert describe_difference("hello", "hallo") == ""


def test_says_nothing_about_values_that_are_not_composite() -> None:
    assert describe_difference(3, 4) == ""
    assert describe_difference(None, 4) == ""


def test_says_nothing_when_the_two_kinds_disagree() -> None:
    """A dict and a list have no shared structure to point into."""
    assert describe_difference({"a": 1}, [1]) == ""
    assert describe_difference("abcdefghijklmnopqrstuvwxyz", list("abcdefghijklmnop")) == ""
    assert describe_difference({1, 2, 3}, [1, 2, 3]) == ""


def test_says_nothing_when_the_reprs_carry_the_whole_finding() -> None:
    """``[1]`` and ``[True]`` hold equal items; only the reprs tell them apart."""
    assert describe_difference([1], [True]) == ""


def test_bytes_are_not_treated_as_a_sequence_of_integers() -> None:
    assert describe_difference(b"abcdef", b"abcdeg") == ""


def test_the_block_starts_with_a_newline_and_does_not_end_with_one() -> None:
    rendered = describe_difference([1, 2, 3], [1, 9, 3])
    assert rendered.startswith("\n")
    assert not rendered.endswith("\n")


def test_every_line_of_the_block_is_indented_under_the_message() -> None:
    lines = block({"a": 1, "b": 2}, {"a": 9, "c": 2})
    assert lines
    assert all(line.startswith("  ") for line in lines)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def test_multi_line_strings_get_a_unified_diff() -> None:
    actual = "alpha\nbeta\ngamma\ndelta"
    expected = "alpha\nbeta the second\ngamma\ndelta"
    assert block(actual, expected) == [
        "  the strings differ (- expected, + actual):",
        "    @@ -1,4 +1,4 @@",
        "     alpha",
        "    -beta the second",
        "    +beta",
        "     gamma",
        "     delta",
    ]


def test_the_unified_diff_is_truncated_and_counts_what_it_left_out() -> None:
    actual = "\n".join("line " + str(number) for number in range(200))
    expected = "\n".join("line " + str(number) + "!" for number in range(200))
    lines = block(actual, expected)
    assert len(lines) == 22  # heading, twenty diff lines, and the count
    assert lines[0] == "  the strings differ (- expected, + actual):"
    assert lines[1] == "    @@ -1,200 +1,200 @@"
    assert lines[-1] == "    ... (381 more diff lines)"


def test_a_difference_in_line_endings_is_named_outright() -> None:
    """The diff of two texts with identical lines is empty; this is what is left."""
    assert block("a\r\nb\r\nc\r\nand a tail long enough", "a\nb\nc\nand a tail long enough") == [
        "  the lines are identical; line 1 ends with '\\r\\n', not '\\n'"
    ]


def test_a_missing_trailing_newline_is_named_outright() -> None:
    assert block("first line\nsecond line", "first line\nsecond line\n") == [
        "  the lines are identical; line 2 ends with no newline, not '\\n'"
    ]


def test_two_texts_with_the_same_line_endings_are_not_blamed_on_their_line_endings() -> None:
    """The line-ending clause is reached whenever the lines match, and may find nothing.

    Every terminator matching too means the two texts are the same string, so what
    differs is ``__eq__`` and not the text. "the strings differ only in their line
    endings" would then be a confident sentence about the one thing that provably
    does not differ, and the look-alike clause is the one that answers.
    """
    text = "alpha\nbeta\ngamma\ndelta"

    assert block(Contrary(text), text) == [
        "  both render as 'alpha\\nbeta\\ngamma\\ndelta', but they are not equal"
    ]


def test_a_line_ending_difference_is_still_named_when_the_subject_is_never_equal() -> None:
    """The clause declines only when there is nothing to name, not on every odd subject."""
    assert block(
        Contrary("a\r\nb\r\nc\r\nand a tail long enough"), "a\nb\nc\nand a tail long enough"
    ) == ["  the lines are identical; line 1 ends with '\\r\\n', not '\\n'"]


def test_the_budget_for_reading_two_reprs_side_by_side_is_forty_characters() -> None:
    """The gate between "the reprs are the comparison" and "point at a column"."""
    assert len(repr("0123456789abcdefgh")) + len(repr("0123456789abcdefgi")) == 40
    assert describe_difference("0123456789abcdefgh", "0123456789abcdefgi") == ""
    assert len(repr("0123456789abcdefgh")) + len(repr("0123456789abcdefghi")) == 41
    assert block("0123456789abcdefgh", "0123456789abcdefghi") == [
        "  the first 18 characters match; actual ends there, expected continues with 'i'"
    ]


def test_a_line_terminator_that_is_not_a_newline_is_named_as_itself() -> None:
    """``splitlines`` breaks on seven characters; ``rstrip`` knows two of them.

    Reporting a form feed as "no newline" is the one claim this message exists
    to make, made wrongly -- and invisibly, because neither one shows in a
    terminal.
    """
    assert block(
        "a form feed ends this line\x0cand this one trails",
        "a form feed ends this line\rand this one trails",
    ) == ["  the lines are identical; line 1 ends with '\\x0c', not '\\r'"]
    assert block(
        "a paragraph break here\u2028and a tail long enough",
        "a paragraph break here\nand a tail long enough",
    ) == ["  the lines are identical; line 1 ends with '\\u2028', not '\\n'"]


def test_a_trailing_newline_on_a_single_line_is_reported_by_column() -> None:
    """Both text branches match here; the column one is the one that answers.

    "the lines are identical" is a strange thing to tell somebody about a string
    that has one line, so the single-line test is asked first.
    """
    assert block(LEFT + "\n", LEFT) == [
        "  the first 43 characters match; expected ends there, actual continues with '\\n'"
    ]


def test_a_long_single_line_string_is_pointed_at_by_column() -> None:
    assert block(LEFT, RIGHT) == [
        "  first difference at index 24: 's' instead of 'e', after ...'quick brown fox jump'"
    ]


def test_the_context_clause_is_dropped_when_the_strings_differ_at_the_start() -> None:
    assert block("z" + LEFT[1:], LEFT) == ["  first difference at index 0: 'z' instead of 't'"]


def test_a_string_that_is_a_prefix_of_the_other_is_reported_as_one() -> None:
    assert block(LEFT[:30], LEFT) == [
        (
            "  the first 30 characters match; actual ends there,"
            " expected continues with ' the lazy dog'"
        )
    ]
    assert block(LEFT, LEFT[:30]) == [
        (
            "  the first 30 characters match; expected ends there,"
            " actual continues with ' the lazy dog'"
        )
    ]


def test_an_over_long_diff_line_is_clipped_around_the_difference() -> None:
    """Clipped from the start, two different minified lines render identically."""
    lines = block("x" * 400 + "a\ntail", "x" * 400 + "b\ntail")
    assert lines[2] == "    -... (380 earlier characters) " + "x" * 20 + "b"
    assert lines[3] == "    +... (380 earlier characters) " + "x" * 20 + "a"


def test_a_diff_line_without_a_counterpart_is_clipped_from_the_start() -> None:
    lines = block("kept\n" + "x" * 300, "kept")
    assert lines[-1] == "    +" + "x" * 119 + "... (181 more characters)"


def test_a_removed_line_with_nothing_facing_it_is_clipped_from_the_start() -> None:
    """A deletion the diff answers with no addition at all has nothing to clip against.

    The counterpart of the k-th removal is the k-th addition, so a hunk that
    removes a line and adds none is asked for an addition past the end of the
    body. Reading whatever sits at that index instead would pair the removed line
    with itself, and a line clipped around its difference from itself is clipped
    around its own end.
    """
    lines = block("kept", "kept\n" + "x" * 300)

    assert lines[-1] == "    -" + "x" * 119 + "... (181 more characters)"


def test_an_over_long_unchanged_line_is_clipped_from_the_start() -> None:
    """A context line is nobody's counterpart, and has no difference to be clipped around.

    It is printed because it locates the change, not because it is part of it, so
    the readable half is its beginning -- the same treatment a line with no
    counterpart gets.
    """
    lines = block("x" * 300 + "\nalpha", "x" * 300 + "\nbeta")

    assert lines[2] == "     " + "x" * 119 + "... (181 more characters)"


def test_each_line_of_a_change_is_clipped_against_the_line_it_replaced() -> None:
    """A unified diff writes every removal, then every addition.

    So the line facing the second removal is the second *addition*, not the
    neighbouring removal. Pairing by adjacency instead clips four of these six
    lines from the start, where three of them render as the same ellipsis after
    the same run of x's -- a diff claiming that lines it has just called
    different are identical.
    """
    prefix = "x" * 400
    lines = block(
        prefix + "a\n" + prefix + "b\n" + prefix + "e\ntail",
        prefix + "c\n" + prefix + "d\n" + prefix + "f\ntail",
    )
    window = "... (380 earlier characters) " + "x" * 20
    assert lines[2:8] == [
        "    -" + window + "c",
        "    -" + window + "d",
        "    -" + window + "f",
        "    +" + window + "a",
        "    +" + window + "b",
        "    +" + window + "e",
    ]
    assert len(set(lines)) == len(lines)


def test_two_lines_that_part_company_at_the_start_are_clipped_from_the_start() -> None:
    """The window only earns its ellipsis when there is something in front of it.

    A pair that already differs inside the first characters has its difference in
    the part a plain clip keeps, so the window would open at the same place and
    charge the reader a "0 earlier characters" clause for it.
    """
    lines = block("a" + "z" * 300 + "\ntail", "b" + "z" * 300 + "\ntail")

    assert lines[2] == "    -b" + "z" * 118 + "... (182 more characters)"
    assert lines[3] == "    +a" + "z" * 118 + "... (182 more characters)"


def test_the_count_of_elided_diff_lines_has_a_singular() -> None:
    lines = block(
        "\n".join("l" + str(number) + "a" for number in range(10)),
        "\n".join("l" + str(number) + "b" for number in range(10)),
    )
    assert lines[-1] == "    ... (1 more diff line)"


def test_a_change_late_in_a_long_text_keeps_the_line_numbers_it_really_has() -> None:
    """The window drops identical lines; the hunk header must not notice."""
    expected = "\n".join("line " + str(number) for number in range(3000))
    actual = expected.replace("line 2500", "LINE 2500")
    lines = block(actual, expected)
    assert lines[1] == "    @@ -2498,7 +2498,7 @@"
    assert lines[5:7] == ["    -line 2500", "    +LINE 2500"]


def test_a_hunk_header_keeps_its_line_numbers_however_narrow_the_scope() -> None:
    """The character bound applies to values, and a hunk header is not one.

    Cut, a header loses the line numbers it is printed for, and the rewriter that
    puts the windowing back then reads the count in the clip's own "N more
    characters" as the second range -- so the reader is handed a line number the
    text never had. The lines around it are still clipped: this is one exemption,
    not a hole in the bound.
    """
    expected = "\n".join("line " + str(number) for number in range(3000))
    actual = expected.replace("line 2500", "LINE 2500")

    with formatting(max_chars=4):
        lines = block(actual, expected)

    assert lines[1] == "    @@ -2498,7 +2498,7 @@"
    assert lines[2] == "     lin... (6 more characters)"


def test_a_small_change_in_a_huge_text_is_neither_capped_nor_slow() -> None:
    """Thirty thousand lines, one of them changed: the window is nine lines.

    Trimming the identical tail is what keeps this off the cap. Left on, the
    block would end by saying only the first two thousand lines were compared --
    true of the window, false of the finding, and there is nothing more to show.
    """
    expected = "\n".join("line " + str(number) for number in range(30_000))
    actual = expected.replace("line 5\n", "LINE 5\n", 1)
    started = time.perf_counter()
    lines = block(actual, expected)
    assert time.perf_counter() - started < 2.0
    assert lines == [
        "  the strings differ (- expected, + actual):",
        "    @@ -3,7 +3,7 @@",
        "     line 2",
        "     line 3",
        "     line 4",
        "    -line 5",
        "    +LINE 5",
        "     line 6",
        "     line 7",
        "     line 8",
    ]


def test_a_text_too_large_to_diff_is_windowed_rather_than_handed_to_difflib() -> None:
    """``difflib`` costs the square of the number of changed lines.

    Thirty thousand lines differing every seventh is far past the point where
    that cost stops being measured in milliseconds, and a failing assertion that
    takes that long to print is a hung test run as far as the person waiting on
    it can tell. Windowing the input rather than handing all of it to ``difflib``
    is what holds these twenty-two lines inside the budget asserted below.
    """
    expected = "\n".join("line " + str(number) for number in range(30_000))
    actual = "\n".join(
        "line " + str(number) + ("!" if number % 7 == 0 else "") for number in range(30_000)
    )
    started = time.perf_counter()
    lines = block(actual, expected)
    assert time.perf_counter() - started < 2.0
    assert len(lines) == 22
    assert lines[0] == "  the strings differ (- expected, + actual):"
    assert lines[1] == "    @@ -1,1999 +1,1999 @@"
    assert lines[-1] == "    ... (more diff lines; only 2000 lines were compared)"


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------
def test_a_sequence_leads_with_the_position_that_differs() -> None:
    assert block([1, 2, 3], [1, 9, 3]) == ["  first difference at index 1: 2 instead of 9"]


def test_a_sequence_reports_length_and_membership_after_the_position() -> None:
    assert block(["a", "b", "c", "d", "e", "f"], ["a", "c", "b", "d", "e"]) == [
        "  first difference at index 1: 'b' instead of 'c'",
        "  lengths differ: 6 items, expected 5",
        "  extra items: ['f']",
    ]


def test_membership_is_silent_when_it_would_only_echo_the_position() -> None:
    """``missing [9], extra [2]`` after "index 1: 2 instead of 9" says it twice."""
    assert block([1, 2, 3], [1, 9, 3]) == ["  first difference at index 1: 2 instead of 9"]


def test_duplicates_are_counted_rather_than_treated_as_a_set() -> None:
    assert block([1, 1, 2], [1, 2]) == [
        "  first difference at index 1: 1 instead of 2",
        "  lengths differ: 3 items, expected 2",
        "  extra items: [1]",
    ]


def test_the_same_items_in_a_different_order_are_named_as_such() -> None:
    assert block([1, 2, 3, 4], [4, 3, 2, 1]) == [
        "  first difference at index 0: 1 instead of 4",
        "  the same items, in a different order",
    ]


def test_a_list_and_a_tuple_holding_the_same_items() -> None:
    """The reprs differ by two characters, and that is the entire finding."""
    assert block([1, 2], (1, 2)) == [
        "  the same items, but actual is a list and expected is a tuple"
    ]


def test_unhashable_items_are_matched_one_for_one() -> None:
    assert block([{"a": 1}, {"b": 2}], [{"a": 1}, {"b": 2}, {"c": 3}]) == [
        "  lengths differ: 2 items, expected 3",
        "  missing items: [{'c': 3}]",
    ]


def test_ten_thousand_items_do_not_print_ten_thousand_lines() -> None:
    actual = list(range(10_000))
    expected = list(range(10_000, 20_000))
    assert block(actual, expected) == [
        "  first difference at index 0: 0 instead of 10000",
        (
            "  missing items: [10000, 10001, 10002, 10003, 10004, 10005, 10006, 10007,"
            " 10008, 10009, ... (9990 more)]"
        ),
        "  extra items: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (9990 more)]",
    ]


def test_a_length_of_one_is_reported_in_the_singular() -> None:
    assert block([1], []) == ["  lengths differ: 1 item, expected 0", "  extra items: [1]"]


def test_the_same_object_at_the_same_index_is_not_a_difference() -> None:
    """Identity first, which is the rule ``list.__eq__`` applies internally.

    One NaN placed in both sequences is the same item in both, however it
    compares; the difference here is the length, and saying "index 0" as well
    would send the reader looking at the one position that matches.
    """
    shared = float("nan")
    assert block([shared], [shared, 1]) == [
        "  lengths differ: 1 item, expected 2",
        "  missing items: [1]",
    ]


def test_membership_is_computed_up_to_the_unhashable_cap() -> None:
    """A hundred unhashable items a side is still answered in full."""
    actual: list[dict[str, int]] = [{"i": index} for index in range(100)]
    expected: list[dict[str, int]] = [
        *({"i": index} for index in range(98)),
        {"x": 1},
        {"y": 2},
    ]
    assert block(actual, expected) == [
        "  first difference at index 98:",
        "    missing keys: ['x']",
        "    extra keys: ['i']",
        "  missing items: [{'x': 1}, {'y': 2}]",
        "  extra items: [{'i': 98}, {'i': 99}]",
    ]


def test_membership_is_declined_rather_than_computed_quadratically() -> None:
    """Past the cap the position is still reported and membership is dropped.

    The same shape as the test above, fifty items longer: the two membership
    lines are what the cap costs, and their absence is the only thing that
    distinguishes a cap that trips from a cap that does not exist.
    """
    actual: list[dict[str, int]] = [{"i": index} for index in range(150)]
    expected: list[dict[str, int]] = [
        *({"i": index} for index in range(148)),
        {"x": 1},
        {"y": 2},
    ]
    assert block(actual, expected) == [
        "  first difference at index 148:",
        "    missing keys: ['x']",
        "    extra keys: ['i']",
    ]


# ---------------------------------------------------------------------------
# Mappings
# ---------------------------------------------------------------------------
def test_a_mapping_names_the_key_and_both_values() -> None:
    assert block({"a": 1, "b": 2}, {"a": 1, "b": 3}) == [
        "  values differ at key 'b': 2 instead of 3"
    ]


def test_a_mapping_separates_wrong_values_from_missing_and_extra_keys() -> None:
    actual = {"a": 1, "b": 2, "name": "bob"}
    expected = {"a": 1, "b": 3, "nome": "bob"}
    assert block(actual, expected) == [
        "  values differ at key 'b': 2 instead of 3",
        "  missing keys: ['nome']",
        "  extra keys: ['name']",
    ]


def test_a_mapping_truncates_the_keys_whose_values_differ() -> None:
    actual = {str(key): key for key in range(15)}
    expected = {str(key): key + 100 for key in range(15)}
    lines = block(actual, expected)
    assert lines[0] == "  values differ at key '0': 0 instead of 100"
    assert lines[9] == "  values differ at key '9': 9 instead of 109"
    assert lines[10] == "  ... (5 more keys hold a different value)"
    assert len(lines) == 11


def test_the_count_of_elided_keys_has_a_singular() -> None:
    actual = {str(key): key for key in range(11)}
    expected = {str(key): key + 1 for key in range(11)}
    assert block(actual, expected)[-1] == "  ... (1 more key holds a different value)"


def test_a_long_key_is_clipped_in_the_label_like_every_other_value() -> None:
    """A mapping keyed by a request body must not put the body in the label."""
    key = "K" * 5000
    assert block({key: 1}, {key: 2}) == [
        "  values differ at key '" + "K" * 119 + "... (4882 more characters): 1 instead of 2"
    ]


def test_a_nested_mapping_is_descended_into() -> None:
    actual = {"user": {"name": "bob", "roles": ["admin", "dev"]}, "id": 7}
    expected = {"user": {"name": "bob", "roles": ["admin", "ops"]}, "id": 7}
    assert block(actual, expected) == [
        "  values differ at key 'user':",
        "    values differ at key 'roles':",
        "      first difference at index 1: 'dev' instead of 'ops'",
    ]


def test_nesting_stops_at_the_depth_limit() -> None:
    """Past two levels the pair is rendered inline instead of descended into."""
    actual = {"a": {"b": {"c": {"d": 1}}}}
    expected = {"a": {"b": {"c": {"d": 2}}}}
    assert block(actual, expected) == [
        "  values differ at key 'a':",
        "    values differ at key 'b':",
        "      values differ at key 'c': {'d': 1} instead of {'d': 2}",
    ]


def test_a_mapping_of_a_different_type_holding_the_same_entries() -> None:
    class Frozen(dict[str, int]):
        __slots__ = ()

    assert block(Frozen(a=1), {"a": 1}) == [
        "  the same entries, but actual is a Frozen and expected is a dict"
    ]


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------
def test_a_set_reports_what_is_missing_and_what_is_surplus() -> None:
    assert block({1, 2, 3, 8}, {1, 2, 3, 9}) == ["  missing items: [9]", "  extra items: [8]"]


def test_set_items_are_ordered_so_that_two_runs_read_alike() -> None:
    """Iteration order for strings depends on the hash seed; the message must not."""
    assert block({"x", "y", "z", "a"}, {"a", "b", "c", "d"}) == [
        "  missing items: ['b', 'c', 'd']",
        "  extra items: ['x', 'y', 'z']",
    ]


def test_unorderable_set_items_keep_iteration_order_rather_than_raising() -> None:
    lines = block({1, "a"}, {2, "b"})
    assert len(lines) == 2
    assert lines[0].startswith("  missing items: [")
    assert lines[1].startswith("  extra items: [")


def test_a_comparison_that_raises_costs_the_order_and_not_the_items() -> None:
    """``sorted`` runs on somebody else's ``__lt__``, which may raise anything.

    A guard that catches ``TypeError`` alone -- what unorderable mixed types
    raise -- lets a user's ``ValueError`` through to the outer guard, which
    swallows the *whole* difference block: the reader gets two reprs of two
    six-member sets and not one word about which members differed. Ordering the
    two lines is a presentation choice, so failing to order them may cost the
    order and nothing else.

    Six members and not two, because ``sorted`` never calls ``__lt__`` on a
    one-item list, and a guard that is too narrow is invisible below that.
    """

    class Hostile:
        __slots__ = ("n",)

        def __init__(self, n: int) -> None:
            self.n = n

        def __eq__(self, other: object) -> bool:
            return isinstance(other, Hostile) and self.n == other.n

        def __hash__(self) -> int:
            return hash(self.n)

        def __lt__(self, other: object) -> bool:
            message = "no ordering here"
            raise ValueError(message)

        def __repr__(self) -> str:
            return f"H{self.n}"

    lines = block({Hostile(i) for i in range(6)}, {Hostile(i) for i in range(10, 16)})
    assert len(lines) == 2, lines
    assert lines[0].startswith("  missing items: [")
    assert lines[1].startswith("  extra items: [")


def test_a_nan_listed_on_both_set_lines_is_accounted_for() -> None:
    """Set membership hashes first, and two NaNs of separate origin hash apart.

    So each is reported missing *and* extra. Left at that, the block says a value
    is both absent and surplus and stops, which reads as a broken report.
    """
    assert block({float("nan")}, {float("nan")}) == [
        "  missing items: [nan]",
        "  extra items: [nan]",
        "  the nan on both lines is not the same object, and no NaN equals any other",
    ]


def test_the_nan_note_is_silent_when_only_one_side_carries_one() -> None:
    assert block({float("nan"), 1.0}, {2.0, 1.0}) == [
        "  missing items: [2.0]",
        "  extra items: [nan]",
    ]


def test_a_set_and_a_frozenset_holding_the_same_items() -> None:
    assert block({1, 2}, frozenset({1, 2})) == [
        "  the same items, but actual is a set and expected is a frozenset"
    ]


# ---------------------------------------------------------------------------
# Values that render alike
# ---------------------------------------------------------------------------
def test_two_values_that_render_alike_are_told_why_they_are_not_equal() -> None:
    assert block(Point(1), Point(1)) == [
        "  both render as Point(1), but Point does not define __eq__, so they compare by identity"
    ]


def test_a_look_alike_with_an_eq_of_its_own_gets_the_plain_statement() -> None:
    class Odd:
        __slots__ = ()

        def __repr__(self) -> str:
            return "Odd()"

        def __eq__(self, other: object) -> bool:
            return False

        def __hash__(self) -> int:
            return 0

    assert block(Odd(), Odd()) == ["  both render as Odd(), but they are not equal"]


def test_a_nan_is_named_for_what_it_is() -> None:
    assert block(float("nan"), float("nan")) == [
        "  both are nan, and a NaN is equal to nothing, itself included"
    ]


def test_a_nan_inside_a_sequence_is_named_at_its_position() -> None:
    assert block([1.0, float("nan")], [1.0, float("nan")]) == [
        (
            "  first difference at index 1: both are nan,"
            " and a NaN is equal to nothing, itself included"
        )
    ]


def test_a_nested_structure_is_descended_into_even_when_it_renders_alike() -> None:
    """Look-alike is the answer for a value, never for a structure with a key."""
    assert block([{"score": float("nan")}], [{"score": float("nan")}]) == [
        "  first difference at index 0:",
        (
            "    values differ at key 'score': both are nan,"
            " and a NaN is equal to nothing, itself included"
        ),
    ]


def test_a_nested_sequence_is_descended_into() -> None:
    assert block([[1, 2], [3, 4]], [[1, 2], [3, 9]]) == [
        "  first difference at index 1:",
        "    first difference at index 1: 4 instead of 9",
    ]


def test_an_over_long_value_is_clipped_with_a_count() -> None:
    """A pair with no shared structure falls back to two clipped reprs."""
    assert block({"body": "y" * 400}, {"body": b"z" * 300}) == [
        "  values differ at key 'body': '"
        + "y" * 119
        + "... (282 more characters)"
        + " instead of b'"
        + "z" * 118
        + "... (183 more characters)"
    ]


def test_two_long_values_under_a_key_are_diffed_rather_than_clipped() -> None:
    """A nested description beats two reprs cut off before they part company."""
    assert block({"body": "y" * 400 + "a"}, {"body": "y" * 400 + "b"}) == [
        "  values differ at key 'body':",
        "    first difference at index 400: 'a' instead of 'b', after ...'" + "y" * 20 + "'",
    ]


# ---------------------------------------------------------------------------
# It never raises
# ---------------------------------------------------------------------------
def test_a_hostile_repr_costs_detail_rather_than_raising() -> None:
    assert describe_difference([Hostile()], [Hostile()]) == ""
    # Rendering goes through the formatter registry, which answers with a
    # placeholder instead of propagating the exception. That gives the look-alike
    # branch two identical renderings to work with, and what it says about them is
    # the most useful sentence available: the repr is broken *and* the type has no
    # __eq__, which is why two fresh instances compare unequal at all.
    assert describe_difference(Hostile(), Hostile()) == (
        "\n  both render as <Hostile with an unusable __repr__>, but they are not equal"
    )


def test_a_hostile_eq_costs_detail_rather_than_raising() -> None:
    assert describe_difference({"a": Hostile()}, {"a": Hostile()}) == ""


def test_a_self_referential_list_is_described_without_blowing_the_stack() -> None:
    looping: list[Any] = []
    looping.append(looping)
    assert block(looping, [1]) == ["  first difference at index 0: [[...]] instead of 1"]


def test_two_self_referential_lists_degrade_instead_of_recursing_forever() -> None:
    """Their own ``==`` is what recurses; the engine must survive it either way."""
    left: list[Any] = []
    left.append(left)
    right: list[Any] = []
    right.append(right)
    with pytest.raises(RecursionError):
        _ = left == right
    assert describe_difference(left, right) == ""


# ---------------------------------------------------------------------------
# The bounds are a scope, not four constants
# ---------------------------------------------------------------------------
def test_no_module_of_the_package_carries_a_bound_of_its_own() -> None:
    """One source of truth, pinned by its absence -- in every module, not just one.

    A constant here would keep working, keep agreeing with the default, and
    quietly ignore every scope -- which is the failure mode that is hardest to
    notice and easiest to prevent.

    Asked of each module rather than of the package, because ``hasattr`` on a
    package reads only what its ``__init__`` binds: the engine's constants live
    in the modules that spend them, so a bound reintroduced beside them would sit
    exactly where a package-level question cannot see it.
    """
    root = Path(lovely_assertions.__file__).parent
    package = Path(_diff.__file__).parent
    for path in sources(package):
        module = import_module(module_name(path, root))
        for name in ("_MAX_ITEMS", "_MAX_CHARS", "_MAX_DIFF_LINES", "_MAX_DEPTH"):
            assert not hasattr(module, name), (
                f"{name} is back in {module.__name__}; the bounds live on FormattingOptions"
            )


def test_the_defaults_are_the_numbers_the_constants_used_to_be() -> None:
    """What a caller who opens no scope gets: ten items, and two levels of nesting.

    Every other expectation in this module is written against these two, so a
    default that drifted would be read as the engine changing its mind.
    """
    assert block(list(range(400)), [])[-1].endswith(", 8, 9, ... (390 more)]")
    assert block({"a": {"b": {"c": {"d": 1}}}}, {"a": {"b": {"c": {"d": 2}}}}) == [
        "  values differ at key 'a':",
        "    values differ at key 'b':",
        "      values differ at key 'c': {'d': 1} instead of {'d': 2}",
    ]


def test_a_scope_shows_a_hundred_items_of_four_hundred() -> None:
    """The wiring proved from the outside: a real subject, a real assertion.

    Ten items is right for the message a reader skims and wrong for the one they
    are debugging, and a four-hundred-row comparison whose interesting row is the
    hundredth is exactly when they are debugging.
    """
    rows = list(range(400))
    with formatting(max_items=100), pytest.raises(AssertionFailure) as caught:
        expect(rows).is_equal_to([])
    message = str(caught.value)
    assert message.endswith(", 98, 99, ... (300 more)]")
    assert "lengths differ: 400 items, expected 0" in message


def test_the_character_bound_comes_from_the_scope() -> None:
    """The same pair the default-bound test uses, read through a wider window."""
    with formatting(max_chars=200):
        assert block({"body": "y" * 400}, {"body": b"z" * 300}) == [
            "  values differ at key 'body': '"
            + "y" * 199
            + "... (202 more characters)"
            + " instead of b'"
            + "z" * 198
            + "... (103 more characters)"
        ]


def test_the_diff_line_bound_comes_from_the_scope() -> None:
    actual = "\n".join("line " + str(number) for number in range(200))
    expected = "\n".join("line " + str(number) + "!" for number in range(200))
    with formatting(max_diff_lines=5):
        lines = block(actual, expected)
    assert len(lines) == 7  # heading, five diff lines, and the count
    assert lines[0] == "  the strings differ (- expected, + actual):"
    assert lines[-1] == "    ... (396 more diff lines)"


def test_the_depth_bound_comes_from_the_scope() -> None:
    """One level deeper, and then no levels at all."""
    actual = {"a": {"b": {"c": {"d": 1}}}}
    expected = {"a": {"b": {"c": {"d": 2}}}}
    with formatting(max_depth=3):
        assert block(actual, expected) == [
            "  values differ at key 'a':",
            "    values differ at key 'b':",
            "      values differ at key 'c':",
            "        values differ at key 'd': 1 instead of 2",
        ]
    with formatting(max_depth=0):
        assert block(actual, expected) == [
            "  values differ at key 'a': {'b': {'c': {'d': 1}}} instead of {'b': {'c': {'d': 2}}}"
        ]


def test_the_key_bound_comes_from_the_scope() -> None:
    actual = {str(key): key for key in range(15)}
    expected = {str(key): key + 100 for key in range(15)}
    with formatting(max_items=3):
        lines = block(actual, expected)
    assert lines == [
        "  values differ at key '0': 0 instead of 100",
        "  values differ at key '1': 1 instead of 101",
        "  values differ at key '2': 2 instead of 102",
        "  ... (12 more keys hold a different value)",
    ]


def test_the_field_bound_comes_from_the_scope() -> None:
    """The record describer counts with the same bound the mapping one uses."""

    class Record:
        def __init__(self, offset: int) -> None:
            for index in range(15):
                setattr(self, "f" + str(index), index + offset)

        def __eq__(self, other: object) -> bool:
            return isinstance(other, Record) and vars(self) == vars(other)

        def __hash__(self) -> int:
            return 0

    with formatting(max_items=3):
        lines = block(Record(0), Record(100))
    assert lines == [
        "  field f0: 0 instead of 100",
        "  field f1: 1 instead of 101",
        "  field f2: 2 instead of 102",
        "  ... (12 more fields hold a different value)",
    ]


def test_the_cost_ceilings_are_not_offered_as_options() -> None:
    """Legibility is a caller's decision; cost is not.

    ``max_diff_lines`` bounds how much of a diff is *printed* and belongs to
    whoever is reading it. The engine's own two ceilings -- the lines it hands
    ``difflib`` and the unhashable items it will match -- bound how much *work* is
    done while a test is already red, and a caller who could raise them could hang
    the run they were trying to debug. So they stay constants, and the options
    record has no field for either. What they do is pinned by
    ``test_a_text_too_large_to_diff_is_windowed_rather_than_handed_to_difflib``
    and ``test_membership_is_declined_rather_than_computed_quadratically``; what
    is pinned here is that neither one became a knob.
    """
    options = current_formatting()
    assert not hasattr(options, "max_diff_input")
    assert not hasattr(options, "max_unhashable")
    untyped: Any = formatting
    with pytest.raises(TypeError):
        untyped(max_diff_input=10_000)
    with pytest.raises(TypeError):
        untyped(max_unhashable=10_000)


def test_a_scope_changes_what_is_printed_and_never_what_is_decided() -> None:
    """Raising or lowering a bound cannot turn a pass into a failure, or the reverse."""
    rows = list(range(400))
    expect(rows).is_equal_to(list(range(400)))
    with formatting(max_items=1, max_chars=1, max_diff_lines=1, max_depth=0):
        expect(rows).is_equal_to(list(range(400)))
        with pytest.raises(AssertionFailure):
            expect(rows).is_equal_to([])


@pytest.fixture
def no_options_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Booby-trap the options lookup, the way ``tests/test_happy_path.py`` traps ``_fail``."""
    monkeypatch.setattr(_scope, "_ACTIVE", Detonator())


@pytest.mark.usefixtures("no_options_lookup")
def test_a_passing_assertion_never_reaches_the_difference_engine() -> None:
    """A passing assertion reads no ``ContextVar``.

    Every bound in this module is such a read, and the engine is only ever
    entered from the failure branch of ``is_equal_to`` -- so a passing comparison,
    however composite, must not arrive here at all.
    """
    expect(3).is_equal_to(3)
    expect("hello").is_equal_to("hello")
    expect([1, 2, 3]).is_equal_to([1, 2, 3])
    expect({"a": {"b": 1}}).is_equal_to({"a": {"b": 1}})
    expect({1, 2}).is_equal_to({1, 2})


@pytest.mark.usefixtures("no_options_lookup")
def test_the_engine_degrades_rather_than_raising_when_the_lookup_explodes() -> None:
    """The blanket ``except`` covers the options read too, and that is deliberate.

    ``_ACTIVE.get()`` cannot actually raise -- which is why the trap above can only
    be armed by a test. What this pins is the contract underneath it: whatever goes
    wrong while a difference is being described costs the reader detail and never
    replaces their assertion failure with an error from inside the library.

    It is also why this trap proves nothing on its own about the *failure* path,
    and why the scoped tests above exist to prove that half.
    """
    assert describe_difference([1, 2, 3], [1, 9, 3]) == ""
