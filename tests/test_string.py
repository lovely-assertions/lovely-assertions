"""The string catalogue: :class:`StringExpect`.

Several things carry more weight here than the pass/fail bookkeeping.

*The messages.* A string assertion that fails has to say what it looked for and
what it found, and it has to stay readable when the haystack is a whole document.

*The ``matches`` collision.* One name serves both the predicate form inherited
from the generic catalogue and the regex form this subject adds. Both have to
work, on the same subject.

*The wildcard translation.* ``*`` and ``?`` are the only metacharacters; anything
that leaks through from ``re`` or ``fnmatch`` is a bug.

*The character classes.* A row of one-line delegations to ``str``, where all of
the risk sits in the message and in two Python subtleties: an empty string
satisfies none of these classes except ``isascii`` and ``isprintable``, and
``isdigit``, ``isdecimal`` and ``isnumeric`` are three different questions.

*``is_uuid``.* ``UUID(text) == text`` is ``False``, silently. The assertion is
the join between the two, so what it hands to ``.which`` has to be the parsed
UUID -- and what it accepts has to be narrower than ``uuid.UUID``, which reads
``"1_23..."`` as a different id rather than refusing it.

*``occurrences=``.* Four assertions can count instead of asking, and counting has
one answer that surprises people: ``"aaa"`` contains ``"aa"`` **once**, because
``str.count`` and ``re`` are both non-overlapping. That answer is pinned from
several directions, along with the lookahead that asks for the other one and the
zero-width pattern that matches everywhere.

*The rendering bounds.* ``max_chars`` and ``max_items`` are not constants in
``_string.py``; they are read from the formatting scope, on the failure path only.
Both halves are tested: a scope really does widen a message, and a *passing*
assertion still never reaches the lookup.
"""

import keyword
import re
import uuid
from collections.abc import Callable
from typing import Any, Final, NoReturn

import pytest
from benchmarks import blocks_allocated

# `formatting` and the occurrence factories are imported from their own private
# modules because the package root does not re-export them.
from conftest import Detonator
from lovely_assertions import (
    AssertionFailure,
    Expect,
    StringExpect,
    _formatting,
    _string,
    _text,
    expect,
    soft_assertions,
)
from lovely_assertions._formatting import formatting
from lovely_assertions._occurrence import (
    Occurrence,
    at_least,
    at_most,
    exactly,
    less_than,
    more_than,
    once,
    twice,
)


@pytest.mark.usefixtures("no_failure_machinery")
def test_a_passing_assertion_never_touches_the_failure_path() -> None:
    """No passing assertion in this catalogue reaches the failure machinery.

    Worth re-arming ``conftest``'s trap here rather than trusting
    ``tests/test_happy_path.py`` alone: this
    is the subject that does real work before it can answer -- casefolding,
    splitting, translating a wildcard, importing and running ``re`` -- and every
    one of those routes has to reach ``return self`` without formatting anything.
    """
    expect("hello").is_not_empty(because="the reason must not be read either")
    expect("").is_empty()
    expect(" ").is_blank()
    expect("hello").is_not_blank()
    expect("hello").has_length(5)
    expect("Hello").is_equal_ignoring_case("hELLO")
    expect(" a b ").is_equal_ignoring_case("AB", ignoring_whitespace=True)
    expect("a\r\nb").is_equal_ignoring_case("a\nb", ignoring_newline_style=True)
    expect("Hello").is_not_equal_ignoring_case("bye")
    expect("hello").contains("ell")
    expect("hello").does_not_contain("bye")
    expect("hello").contains_all("he", "lo")
    expect("hello").does_not_contain_all("he", "bye")
    expect("hello").contains_any("bye", "he")
    expect("hello").does_not_contain_any("bye", "ciao")
    expect("Hello").contains_ignoring_case("ELL")
    expect("Hello").does_not_contain_ignoring_case("BYE")
    expect("hello").starts_with("he").and_.does_not_start_with("bye")
    expect("Hello").starts_with_ignoring_case("HE").and_.does_not_start_with_ignoring_case("BYE")
    expect("hello").ends_with("lo").and_.does_not_end_with("bye")
    expect("Hello").ends_with_ignoring_case("LO").and_.does_not_end_with_ignoring_case("BYE")
    expect("hello").matches("^he").and_.does_not_match("^bye")
    expect("hello").matches(re.compile("^he"))
    expect("hello").matches(lambda text: text.startswith("he"))
    expect("hello").matches_wildcard("he*").and_.does_not_match_wildcard("bye*")
    expect("Hello").matches_wildcard_ignoring_case("HE*")
    expect("Hello").does_not_match_wildcard_ignoring_case("BYE*")
    expect("ABC").is_upper().and_.is_not_lower()
    expect("abc").is_lower().and_.is_not_upper()
    expect("Hello World").is_title().and_.is_not_alpha()
    expect("abc").is_alpha().and_.is_not_digit()
    expect("123").is_digit().and_.is_numeric().and_.is_alnum()
    expect("\u00bd").is_numeric().and_.is_not_digit()
    expect("abc").is_ascii().and_.is_printable()
    expect("caf\u00e9").is_not_ascii()
    expect("a\nb").is_not_printable()
    expect("  ").is_space().and_.is_not_identifier()
    expect("name_1").is_identifier().and_.is_not_space()
    expect("hello").is_not_title()
    expect("b7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c").is_uuid()
    expect("f81d4fae-7dec-11d0-a765-00a0c91e6bf6").is_uuid(version=1)


def test_a_passing_counted_assertion_never_touches_the_failure_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same trap, re-armed for the four assertions that count.

    Kept apart from the sweep above rather than appended to it, because counting
    is real work done *before* the answer is known -- which makes these the four
    most likely places in the module for a message to be built one line too early.
    """
    from lovely_assertions import _core

    def detonate(*_args: object, **_kwargs: object) -> NoReturn:
        pytest.fail("a passing counted assertion reached the failure path")

    monkeypatch.setattr(_core, "resolve_subject_name", detonate)
    monkeypatch.setattr(Expect, "_fail", detonate)

    expect("hello").contains("l", occurrences=twice)
    expect("hello").does_not_contain("l", occurrences=exactly(9))
    expect("Hello").contains_ignoring_case("L", occurrences=twice)
    expect("v2.11.3").matches(r"\d+", occurrences=exactly(3))
    expect("v2.11.3").matches(re.compile(r"\d+"), occurrences=at_least(2))


# ---------------------------------------------------------------------------
# Emptiness and blankness
# ---------------------------------------------------------------------------
def test_is_empty_passes_and_chains() -> None:
    subject = expect("")
    assert subject.is_empty() is subject


def test_is_empty_reports_the_content() -> None:
    greeting = "hello"
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).is_empty()
    assert str(caught.value) == "Expected greeting to be empty, but was 'hello'."


def test_is_not_empty() -> None:
    expect("hello").is_not_empty()
    greeting = ""
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).is_not_empty()
    assert str(caught.value) == "Expected greeting not to be empty, but it was."


@pytest.mark.parametrize("blank", ["", " ", "\t\n", "\u00a0"])
def test_is_blank_accepts_whitespace_and_emptiness(blank: str) -> None:
    expect(blank).is_blank()


def test_is_blank_reports_the_content() -> None:
    label = " x "
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_blank()
    assert str(caught.value) == "Expected label to be blank, but was ' x '."


def test_is_not_blank() -> None:
    expect(" x ").is_not_blank()
    label = "   "
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_not_blank()
    assert str(caught.value) == "Expected label not to be blank, but was '   '."


# ---------------------------------------------------------------------------
# Length
# ---------------------------------------------------------------------------
def test_has_length_reports_both_lengths() -> None:
    code = "abcd"
    expect(code).has_length(4)
    with pytest.raises(AssertionFailure) as caught:
        expect(code).has_length(3)
    assert str(caught.value) == "Expected code to have length 3, but 'abcd' has length 4."


# ---------------------------------------------------------------------------
# Caseless equality and its options
# ---------------------------------------------------------------------------
def test_is_equal_ignoring_case() -> None:
    expect("Hello").is_equal_ignoring_case("hELLO")
    greeting = "Hello"
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).is_equal_ignoring_case("goodbye")
    assert str(caught.value) == (
        "Expected greeting to equal 'goodbye' ignoring case, but was 'Hello'."
    )


def test_is_equal_ignoring_case_uses_casefold_not_lower() -> None:
    """Casefolding is the comparison Unicode defines for caseless matching."""
    expect("STRASSE").is_equal_ignoring_case("straße")


def test_ignoring_whitespace_removes_it_entirely() -> None:
    expect(" a\tb\n").is_equal_ignoring_case("AB", ignoring_whitespace=True)
    with pytest.raises(AssertionFailure):
        expect(" a\tb\n").is_equal_ignoring_case("AB")


def test_ignoring_newline_style_normalises_line_endings() -> None:
    expect("a\r\nb\rc").is_equal_ignoring_case("A\nB\nC", ignoring_newline_style=True)
    with pytest.raises(AssertionFailure):
        expect("a\r\nb").is_equal_ignoring_case("a\nb")


def test_the_options_are_named_in_the_message() -> None:
    greeting = "Hello"
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).is_equal_ignoring_case(
            "bye", ignoring_whitespace=True, ignoring_newline_style=True
        )
    assert str(caught.value) == (
        "Expected greeting to equal 'bye' ignoring case, whitespace and newline style, "
        "but was 'Hello'."
    )


def test_one_option_alone_is_named_too() -> None:
    """The clause is assembled, so the two-part join needs its own witness."""
    greeting = "Hello"
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).is_equal_ignoring_case("bye", ignoring_whitespace=True)
    assert str(caught.value) == (
        "Expected greeting to equal 'bye' ignoring case and whitespace, but was 'Hello'."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).is_equal_ignoring_case("bye", ignoring_newline_style=True)
    assert str(caught.value) == (
        "Expected greeting to equal 'bye' ignoring case and newline style, but was 'Hello'."
    )


def test_is_not_equal_ignoring_case() -> None:
    expect("Hello").is_not_equal_ignoring_case("goodbye")
    greeting = "Hello"
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).is_not_equal_ignoring_case("HELLO")
    assert str(caught.value) == (
        "Expected greeting not to equal 'HELLO' ignoring case, but was 'Hello'."
    )


def test_is_not_equal_ignoring_case_honours_the_options() -> None:
    with pytest.raises(AssertionFailure):
        expect(" a b ").is_not_equal_ignoring_case("AB", ignoring_whitespace=True)
    expect(" a b ").is_not_equal_ignoring_case("AB")


# ---------------------------------------------------------------------------
# Containment
# ---------------------------------------------------------------------------
def test_contains_shows_the_needle_and_the_haystack() -> None:
    greeting = "hello world"
    expect(greeting).contains("lo wo")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).contains("bye")
    assert str(caught.value) == "Expected greeting to contain 'bye', but was 'hello world'."


def test_does_not_contain() -> None:
    greeting = "hello world"
    expect(greeting).does_not_contain("bye")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).does_not_contain("wor")
    assert str(caught.value) == ("Expected greeting not to contain 'wor', but 'hello world' does.")


def test_contains_all_lists_what_is_missing() -> None:
    greeting = "hello world"
    expect(greeting).contains_all("hello", "world")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).contains_all("hello", "bye", "ciao")
    assert str(caught.value) == (
        "Expected greeting to contain all of ['hello', 'bye', 'ciao'], "
        "but 'hello world' is missing ['bye', 'ciao']."
    )


def test_does_not_contain_all_is_satisfied_by_one_absence() -> None:
    greeting = "hello world"
    expect(greeting).does_not_contain_all("hello", "bye")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).does_not_contain_all("hello", "world")
    assert str(caught.value) == (
        "Expected greeting not to contain all of ['hello', 'world'], "
        "but 'hello world' contains every one of them."
    )


def test_contains_any() -> None:
    greeting = "hello world"
    expect(greeting).contains_any("bye", "hello")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).contains_any("bye", "ciao")
    assert str(caught.value) == (
        "Expected greeting to contain at least one of ['bye', 'ciao'], "
        "but 'hello world' contains none of them."
    )


def test_does_not_contain_any_lists_what_slipped_through() -> None:
    greeting = "hello world"
    expect(greeting).does_not_contain_any("bye", "ciao")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).does_not_contain_any("bye", "hello", "world")
    assert str(caught.value) == (
        "Expected greeting not to contain any of ['bye', 'hello', 'world'], "
        "but 'hello world' contains ['hello', 'world']."
    )


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: expect("x").contains_all(), id="contains_all"),
        pytest.param(lambda: expect("x").does_not_contain_all(), id="does_not_contain_all"),
        pytest.param(lambda: expect("x").contains_any(), id="contains_any"),
        pytest.param(lambda: expect("x").does_not_contain_any(), id="does_not_contain_any"),
    ],
)
def test_the_multi_value_assertions_reject_an_empty_call(call: Callable[[], object]) -> None:
    """Vacuous truth is not a test result, so an empty call is a bug, not a finding."""
    with pytest.raises(ValueError, match="at least one value"):
        call()


def test_a_long_value_is_clipped_inside_the_list() -> None:
    """The needles are as likely to be computed as the haystack is to be large."""
    with pytest.raises(AssertionFailure) as caught:
        expect("z").contains_all("q" * 400)
    message = str(caught.value)
    assert "truncated from 400 characters" in message
    assert len(message) < 400


def test_a_long_list_of_values_is_capped() -> None:
    fields = tuple(f"field_{index}" for index in range(25))
    with pytest.raises(AssertionFailure) as caught:
        expect("z").contains_all(*fields)
    message = str(caught.value)
    assert "'field_9', ... 15 more]" in message
    assert "field_10" not in message


def test_contains_ignoring_case() -> None:
    greeting = "Hello World"
    expect(greeting).contains_ignoring_case("LO WO")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).contains_ignoring_case("BYE")
    assert str(caught.value) == (
        "Expected greeting to contain 'BYE' ignoring case, but was 'Hello World'."
    )


def test_does_not_contain_ignoring_case() -> None:
    greeting = "Hello World"
    expect(greeting).does_not_contain_ignoring_case("BYE")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).does_not_contain_ignoring_case("WORLD")
    assert str(caught.value) == (
        "Expected greeting not to contain 'WORLD' ignoring case, but 'Hello World' does."
    )


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------
def test_starts_with() -> None:
    path = "/api/v2/users"
    expect(path).starts_with("/api")
    with pytest.raises(AssertionFailure) as caught:
        expect(path).starts_with("/v2")
    assert str(caught.value) == ("Expected path to start with '/v2', but was '/api/v2/users'.")


def test_does_not_start_with() -> None:
    path = "/api/v2/users"
    expect(path).does_not_start_with("/v2")
    with pytest.raises(AssertionFailure) as caught:
        expect(path).does_not_start_with("/api")
    assert str(caught.value) == ("Expected path not to start with '/api', but was '/api/v2/users'.")


def test_starts_with_ignoring_case() -> None:
    verb = "GET /users"
    expect(verb).starts_with_ignoring_case("get")
    with pytest.raises(AssertionFailure) as caught:
        expect(verb).starts_with_ignoring_case("post")
    assert str(caught.value) == (
        "Expected verb to start with 'post' ignoring case, but was 'GET /users'."
    )


def test_does_not_start_with_ignoring_case() -> None:
    verb = "GET /users"
    expect(verb).does_not_start_with_ignoring_case("post")
    with pytest.raises(AssertionFailure) as caught:
        expect(verb).does_not_start_with_ignoring_case("get")
    assert str(caught.value) == (
        "Expected verb not to start with 'get' ignoring case, but was 'GET /users'."
    )


def test_ends_with() -> None:
    filename = "report.csv"
    expect(filename).ends_with(".csv")
    with pytest.raises(AssertionFailure) as caught:
        expect(filename).ends_with(".json")
    assert str(caught.value) == ("Expected filename to end with '.json', but was 'report.csv'.")


def test_does_not_end_with() -> None:
    filename = "report.csv"
    expect(filename).does_not_end_with(".json")
    with pytest.raises(AssertionFailure) as caught:
        expect(filename).does_not_end_with(".csv")
    assert str(caught.value) == ("Expected filename not to end with '.csv', but was 'report.csv'.")


def test_ends_with_ignoring_case() -> None:
    filename = "REPORT.CSV"
    expect(filename).ends_with_ignoring_case(".csv")
    with pytest.raises(AssertionFailure) as caught:
        expect(filename).ends_with_ignoring_case(".json")
    assert str(caught.value) == (
        "Expected filename to end with '.json' ignoring case, but was 'REPORT.CSV'."
    )


def test_does_not_end_with_ignoring_case() -> None:
    filename = "REPORT.CSV"
    expect(filename).does_not_end_with_ignoring_case(".json")
    with pytest.raises(AssertionFailure) as caught:
        expect(filename).does_not_end_with_ignoring_case(".csv")
    assert str(caught.value) == (
        "Expected filename not to end with '.csv' ignoring case, but was 'REPORT.CSV'."
    )


# ---------------------------------------------------------------------------
# Truncation: a message must survive a large subject
# ---------------------------------------------------------------------------
def test_a_long_subject_is_truncated_with_its_real_length() -> None:
    document = "x" * 500
    with pytest.raises(AssertionFailure) as caught:
        expect(document).is_empty()
    message = str(caught.value)
    assert message.endswith("...' (truncated from 500 characters).")
    assert len(message) < 250


def test_a_short_subject_is_shown_in_full() -> None:
    document = "x" * 120
    with pytest.raises(AssertionFailure) as caught:
        expect(document).is_empty()
    assert "truncated" not in str(caught.value)


def test_one_character_past_the_cap_is_truncated() -> None:
    """The boundary is a `<=`, and a boundary nobody tests is a boundary that moves."""
    document = "x" * 121
    with pytest.raises(AssertionFailure) as caught:
        expect(document).is_empty()
    assert "truncated from 121 characters" in str(caught.value)


def test_ends_with_truncates_from_the_front() -> None:
    """The end of the string is the part an ``ends_with`` failure is about."""
    document = "HEAD" + "y" * 500 + "TAIL"
    with pytest.raises(AssertionFailure) as caught:
        expect(document).ends_with("zzz")
    message = str(caught.value)
    assert "'...y" in message
    assert message.endswith("TAIL' (truncated from 508 characters).")


# ---------------------------------------------------------------------------
# matches: one name, two meanings
# ---------------------------------------------------------------------------
def test_matches_takes_a_regex_string() -> None:
    version = "v2.11.3"
    expect(version).matches(r"^v\d+\.\d+")
    with pytest.raises(AssertionFailure) as caught:
        expect(version).matches(r"^v\d+$")
    assert str(caught.value) == (
        "Expected version to match the regular expression '^v\\\\d+$', but was 'v2.11.3'."
    )


def test_matches_takes_a_compiled_pattern() -> None:
    version = "v2.11.3"
    expect(version).matches(re.compile(r"^v\d+"))
    with pytest.raises(AssertionFailure) as caught:
        expect(version).matches(re.compile("^bye"))
    assert str(caught.value) == (
        "Expected version to match the regular expression '^bye', but was 'v2.11.3'."
    )


def test_a_compiled_pattern_keeps_its_flags() -> None:
    """Passing the pattern *object* through is the point; its text alone loses the flags."""
    expect("ABC").matches(re.compile("abc", re.IGNORECASE))
    with pytest.raises(AssertionFailure):
        expect("ABC").does_not_match(re.compile("abc", re.IGNORECASE))


def test_matches_searches_rather_than_full_matches() -> None:
    """FluentAssertions' ``MatchRegex`` is a search; ``matches_wildcard`` is the anchored one."""
    expect("hello world").matches("wor")


def test_matches_still_takes_the_inherited_predicate() -> None:
    """The inherited ``matches(predicate)`` must survive the regex form taking the name."""

    def is_short(text: str) -> bool:
        return len(text) < 3

    greeting = "hello"
    expect("ab").matches(is_short)
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).matches(is_short)
    assert str(caught.value) == "Expected greeting to match is_short, but 'hello' did not."


def test_matches_accepts_a_lambda_predicate() -> None:
    expect("hello").matches(lambda text: text.startswith("h"))
    with pytest.raises(AssertionFailure, match="to match the predicate"):
        expect("hello").matches(lambda text: text.startswith("z"))


def test_does_not_match_shows_what_did_match() -> None:
    version = "v2.11.3"
    expect(version).does_not_match(r"^\d")
    with pytest.raises(AssertionFailure) as caught:
        expect(version).does_not_match(r"\d+\.\d+")
    assert str(caught.value) == (
        "Expected version not to match the regular expression '\\\\d+\\\\.\\\\d+', "
        "but 'v2.11.3' contains '2.11' at index 1."
    )


def test_does_not_match_says_something_true_about_a_zero_width_match() -> None:
    """``x*`` matches every string, emptily. "contains \'\'" would blame the subject."""
    version = "v2.11.3"
    with pytest.raises(AssertionFailure) as caught:
        expect(version).does_not_match("x*")
    assert str(caught.value) == (
        "Expected version not to match the regular expression 'x*', "
        "but it matches the empty string at index 0 of 'v2.11.3'."
    )


def test_does_not_match_names_a_whole_subject_match_once() -> None:
    """A greedy pattern matches the lot; printing it as needle *and* haystack is noise."""
    version = "v2.11.3"
    with pytest.raises(AssertionFailure) as caught:
        expect(version).does_not_match(".+")
    assert str(caught.value) == (
        "Expected version not to match the regular expression '.+', "
        "but 'v2.11.3' matches it in full."
    )


def test_does_not_match_does_not_paste_a_large_subject_back() -> None:
    document = "x" * 500
    with pytest.raises(AssertionFailure) as caught:
        expect(document).does_not_match(".+")
    assert len(str(caught.value)) < 250


# ---------------------------------------------------------------------------
# Wildcards: `*` and `?` only, and the whole string
# ---------------------------------------------------------------------------
def test_matches_wildcard_anchors_the_whole_string() -> None:
    greeting = "hello world"
    expect(greeting).matches_wildcard("hello*")
    expect(greeting).matches_wildcard("*world")
    expect(greeting).matches_wildcard("hello?world")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).matches_wildcard("hello")
    assert str(caught.value) == (
        "Expected greeting to match the wildcard pattern 'hello', but was 'hello world'."
    )


def test_the_question_mark_matches_exactly_one_character() -> None:
    expect("cat").matches_wildcard("c?t")
    with pytest.raises(AssertionFailure):
        expect("coat").matches_wildcard("c?t")


def test_regex_metacharacters_are_literal_in_a_wildcard() -> None:
    """The translation escapes everything but ``*`` and ``?``."""
    expect("a.c").matches_wildcard("a.c")
    with pytest.raises(AssertionFailure):
        expect("abc").matches_wildcard("a.c")


def test_bracket_classes_are_literal_too() -> None:
    """``fnmatch`` would read ``[abc]`` as a character class; the contract does not."""
    expect("[abc]").matches_wildcard("[abc]")
    with pytest.raises(AssertionFailure):
        expect("a").matches_wildcard("[abc]")


def test_a_wildcard_star_spans_newlines() -> None:
    """ "Any character" has to mean any character, or multi-line output is unmatchable."""
    expect("first\nsecond").matches_wildcard("first*second")


def test_does_not_match_wildcard() -> None:
    greeting = "hello world"
    expect(greeting).does_not_match_wildcard("bye*")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).does_not_match_wildcard("hello*")
    assert str(caught.value) == (
        "Expected greeting not to match the wildcard pattern 'hello*', but was 'hello world'."
    )


def test_matches_wildcard_ignoring_case() -> None:
    greeting = "Hello World"
    expect(greeting).matches_wildcard_ignoring_case("hello*")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).matches_wildcard_ignoring_case("bye*")
    assert str(caught.value) == (
        "Expected greeting to match the wildcard pattern 'bye*' ignoring case, "
        "but was 'Hello World'."
    )


def test_does_not_match_wildcard_ignoring_case() -> None:
    greeting = "Hello World"
    expect(greeting).does_not_match_wildcard_ignoring_case("bye*")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).does_not_match_wildcard_ignoring_case("hello*")
    assert str(caught.value) == (
        "Expected greeting not to match the wildcard pattern 'hello*' ignoring case, "
        "but was 'Hello World'."
    )


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------
def test_is_upper() -> None:
    code = "ABC"
    expect(code).is_upper()
    label = "Abc"
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_upper()
    assert str(caught.value) == "Expected label to be upper case, but 'Abc' has 'b' at index 1."


def test_is_not_upper() -> None:
    expect("Abc").is_not_upper()
    code = "ABC"
    with pytest.raises(AssertionFailure) as caught:
        expect(code).is_not_upper()
    assert str(caught.value) == "Expected code not to be upper case, but was 'ABC'."


def test_is_lower() -> None:
    code = "abc"
    expect(code).is_lower()
    label = "Abc"
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_lower()
    assert str(caught.value) == "Expected label to be lower case, but 'Abc' has 'A' at index 0."


def test_is_not_lower() -> None:
    expect("Abc").is_not_lower()
    code = "abc"
    with pytest.raises(AssertionFailure) as caught:
        expect(code).is_not_lower()
    assert str(caught.value) == "Expected code not to be lower case, but was 'abc'."


@pytest.mark.parametrize("uncased", ["", "123", "!?"])
def test_a_string_without_cased_characters_is_neither(uncased: str) -> None:
    """``str.isupper`` and ``str.islower`` both say no; the negations both say yes."""
    expect(uncased).is_not_upper()
    expect(uncased).is_not_lower()
    with pytest.raises(AssertionFailure):
        expect(uncased).is_upper()
    with pytest.raises(AssertionFailure):
        expect(uncased).is_lower()


def test_an_uncased_string_is_told_why_it_failed() -> None:
    """``to be upper case, but was '123'`` reads like a bug in the assertion."""
    code = "123"
    with pytest.raises(AssertionFailure) as caught:
        expect(code).is_upper()
    assert str(caught.value) == "Expected code to be upper case, but '123' has no cased characters."
    with pytest.raises(AssertionFailure) as caught:
        expect(code).is_lower()
    assert str(caught.value) == "Expected code to be lower case, but '123' has no cased characters."


def test_a_cased_letter_with_no_case_mapping_is_still_a_cased_letter() -> None:
    """The uncased branch must not claim a string it cannot explain.

    ``"ª"`` -- the ordinal indicator in *1ª* -- is a lower-case letter with no
    upper-case mapping, and Unicode has sixteen hundred like it. Asked as
    ``text.upper() == text.lower()`` the question comes back "uncased", which
    would tell the reader there is nothing cased in a string whose second
    character is exactly the one the message should be naming.
    """
    ordinal = "1ª"
    with pytest.raises(AssertionFailure) as caught:
        expect(ordinal).is_upper()
    assert str(caught.value) == "Expected ordinal to be upper case, but '1ª' has 'ª' at index 1."
    symbol = "ℾ"  # DOUBLE-STRUCK CAPITAL GAMMA: upper case, no lower-case mapping
    with pytest.raises(AssertionFailure) as caught:
        expect(symbol).is_lower()
    assert str(caught.value) == "Expected symbol to be lower case, but 'ℾ' has 'ℾ' at index 0."
    with pytest.raises(AssertionFailure) as caught:
        expect("ℾℾ").is_title()
    assert "continues a word with upper-case 'ℾ' at index 1" in str(caught.value)


def test_a_cased_string_is_told_which_character_broke_it() -> None:
    """The uncased branch must not swallow the ordinary failure, which points.

    ``but was 'Abc'`` would leave the reader to find the offending character
    themselves, and on a long identifier that is the whole question -- so these
    two name a character, exactly as the character-class family does.
    """
    label = "Abc"
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_upper()
    assert str(caught.value) == "Expected label to be upper case, but 'Abc' has 'b' at index 1."
    identifier = "SCREAMING_snake_CASE"
    with pytest.raises(AssertionFailure) as caught:
        expect(identifier).is_upper()
    assert str(caught.value) == (
        "Expected identifier to be upper case, but 'SCREAMING_snake_CASE' has 's' at index 10."
    )


# ---------------------------------------------------------------------------
# Character classes
#
# Each one is a one-line delegation to the ``str`` method of the same name, so
# the pass/fail half is not where the risk is. The risk is in the message, and
# in two Python subtleties a reader should never have to rediscover: the empty
# string satisfies none of these classes except ``isascii`` and ``isprintable``,
# and ``isdigit`` is neither ``isdecimal`` nor ``isnumeric``.
# ---------------------------------------------------------------------------
def test_is_alpha_names_the_character_that_broke_it() -> None:
    """A message that only repeats the assertion has wasted the opportunity."""
    slug = "abc1"
    expect("abc").is_alpha()
    with pytest.raises(AssertionFailure) as caught:
        expect(slug).is_alpha()
    assert str(caught.value) == (
        "Expected slug to contain only alphabetic characters, but 'abc1' has '1' at index 3."
    )


def test_the_first_offender_is_the_one_reported() -> None:
    """Reporting the last, or all of them, would bury the one to go and look at."""
    slug = "a1b2"
    with pytest.raises(AssertionFailure) as caught:
        expect(slug).is_alpha()
    assert "has '1' at index 1" in str(caught.value)
    assert "'2'" not in str(caught.value)


def test_alphabetic_means_unicode_alphabetic() -> None:
    expect("héllo").is_alpha()
    expect("日本語").is_alpha()


@pytest.mark.parametrize(
    ("label", "call"),
    [
        ("is_alpha", lambda: expect("").is_alpha()),
        ("is_digit", lambda: expect("").is_digit()),
        ("is_numeric", lambda: expect("").is_numeric()),
        ("is_alnum", lambda: expect("").is_alnum()),
        ("is_space", lambda: expect("").is_space()),
    ],
    ids=["is_alpha", "is_digit", "is_numeric", "is_alnum", "is_space"],
)
def test_an_empty_string_is_told_why_it_satisfies_no_class(
    label: str, call: Callable[[], object]
) -> None:
    """``"".isalpha()`` is ``False``, and "is not alphabetic" is not an explanation."""
    with pytest.raises(AssertionFailure) as caught:
        call()
    assert "but it was empty (an empty string satisfies no character class)" in str(caught.value), (
        f"{label} left the reader to work out why nothing failed a character class"
    )


def test_is_ascii_and_is_printable_are_the_two_exceptions() -> None:
    """``"".isascii()`` and ``"".isprintable()`` are both ``True``; the library follows."""
    blank = ""
    expect(blank).is_ascii()
    expect(blank).is_printable()
    with pytest.raises(AssertionFailure) as caught:
        expect(blank).is_not_ascii()
    assert str(caught.value) == (
        "Expected blank not to contain only ASCII characters, but '' does."
    )
    with pytest.raises(AssertionFailure):
        expect(blank).is_not_printable()


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: expect("").is_not_alpha(), id="is_not_alpha"),
        pytest.param(lambda: expect("").is_not_digit(), id="is_not_digit"),
        pytest.param(lambda: expect("").is_not_numeric(), id="is_not_numeric"),
        pytest.param(lambda: expect("").is_not_alnum(), id="is_not_alnum"),
        pytest.param(lambda: expect("").is_not_space(), id="is_not_space"),
        pytest.param(lambda: expect("").is_not_identifier(), id="is_not_identifier"),
        pytest.param(lambda: expect("").is_not_title(), id="is_not_title"),
    ],
)
def test_the_negations_accept_the_empty_string(call: Callable[[], object]) -> None:
    """The mirror of the rule above: if nothing is in no class, it is in no class."""
    call()


def test_is_digit_is_not_is_decimal() -> None:
    """``"²".isdigit()`` is ``True`` and ``"²".isdecimal()`` is ``False``.

    The distinction the docstring warns about, pinned: this assertion accepts a
    superscript that ``int()`` will not read. Anyone who meant "parses as an
    integer" wanted a different test, and this is the case that proves it.
    """
    expect("²").is_digit()
    with pytest.raises(ValueError, match="invalid literal"):
        int("²")


def test_is_numeric_is_wider_than_is_digit() -> None:
    """Fractions and Roman numerals are numeric without being digits."""
    expect("½").is_numeric()
    expect("Ⅷ").is_numeric()
    for wider in ("½", "Ⅷ"):
        expect(wider).is_not_digit()


def test_arabic_indic_digits_pass_every_one_of_the_three() -> None:
    """``"١٢٣"`` is decimal, so it is a digit and numeric too. Not a Unicode-hostile test."""
    expect("١٢٣").is_digit().and_.is_numeric().and_.is_alnum()


def test_is_digit_reports_the_letter_that_broke_it() -> None:
    code = "12a3"
    expect("1234").is_digit()
    with pytest.raises(AssertionFailure) as caught:
        expect(code).is_digit()
    assert str(caught.value) == (
        "Expected code to contain only digits, but '12a3' has 'a' at index 2."
    )


def test_is_numeric_reports_the_character_that_broke_it() -> None:
    quantity = "1a"
    with pytest.raises(AssertionFailure) as caught:
        expect(quantity).is_numeric()
    assert str(caught.value) == (
        "Expected quantity to contain only numeric characters, but '1a' has 'a' at index 1."
    )


def test_is_alnum_covers_letters_and_numbers_and_not_the_underscore() -> None:
    """``str.isalnum`` is the union of the three; a Python name is not alphanumeric."""
    expect("a1").is_alnum()
    expect("½").is_alnum()
    name = "user_id"
    with pytest.raises(AssertionFailure) as caught:
        expect(name).is_alnum()
    assert str(caught.value) == (
        "Expected name to contain only letters and numbers, but 'user_id' has '_' at index 4."
    )


def test_is_ascii_finds_the_character_that_came_back_from_the_editor() -> None:
    header = "café"
    expect("cafe").is_ascii()
    with pytest.raises(AssertionFailure) as caught:
        expect(header).is_ascii()
    assert str(caught.value) == (
        "Expected header to contain only ASCII characters, but 'café' has 'é' at index 3."
    )


def test_is_printable_shows_the_offender_escaped() -> None:
    """``repr`` escapes exactly what ``isprintable`` rejects, so the message shows it."""
    line = "a\x07b"
    expect("a b").is_printable()
    with pytest.raises(AssertionFailure) as caught:
        expect(line).is_printable()
    assert str(caught.value) == (
        "Expected line to contain only printable characters, but 'a\\x07b' has '\\x07' at index 1."
    )


def test_a_newline_is_not_printable_but_a_space_is() -> None:
    expect(" ").is_printable()
    expect("a\nb").is_not_printable()


def test_is_space_is_the_strict_sibling_of_is_blank() -> None:
    """``is_blank`` takes the empty string, ``str.isspace`` does not."""
    expect("").is_blank()
    expect(" \t\n").is_space()
    with pytest.raises(AssertionFailure) as caught:
        expect("").is_space()
    assert "but it was empty" in str(caught.value)


def test_is_space_reports_the_first_non_space() -> None:
    padding = "  x  "
    with pytest.raises(AssertionFailure) as caught:
        expect(padding).is_space()
    assert str(caught.value) == (
        "Expected padding to contain only whitespace, but '  x  ' has 'x' at index 2."
    )


@pytest.mark.parametrize(
    ("label", "call", "shown"),
    [
        ("is_not_alpha", lambda: expect("abc").is_not_alpha(), "alphabetic characters"),
        ("is_not_digit", lambda: expect("123").is_not_digit(), "digits"),
        ("is_not_numeric", lambda: expect("½").is_not_numeric(), "numeric characters"),
        ("is_not_alnum", lambda: expect("a1").is_not_alnum(), "letters and numbers"),
        ("is_not_ascii", lambda: expect("abc").is_not_ascii(), "ASCII characters"),
        ("is_not_printable", lambda: expect("abc").is_not_printable(), "printable characters"),
        ("is_not_space", lambda: expect("  ").is_not_space(), "whitespace"),
    ],
    ids=[
        "is_not_alpha",
        "is_not_digit",
        "is_not_numeric",
        "is_not_alnum",
        "is_not_ascii",
        "is_not_printable",
        "is_not_space",
    ],
)
def test_every_negation_says_what_the_subject_does(
    label: str, call: Callable[[], object], shown: str
) -> None:
    with pytest.raises(AssertionFailure) as caught:
        call()
    message = str(caught.value)
    assert "not to contain only " + shown in message, f"{label} named the wrong class"
    assert message.endswith(" does."), f"{label} did not say what the subject does"


def test_the_offending_character_is_shown_in_its_own_window() -> None:
    """Naming a character the elision had already cut out would answer nothing."""
    document = "a" * 300 + "\t" + "b" * 300
    with pytest.raises(AssertionFailure) as caught:
        expect(document).is_alpha()
    message = str(caught.value)
    assert "has '\\t' at index 300" in message
    assert "a\\tb" in message, "the window has to carry the character it names"
    assert "truncated from 601 characters" in message
    assert len(message) < 300
    assert "'..." in message, "an elided head has to say it was elided"
    assert "...'" in message, "an elided tail has to say it was elided"


def test_the_window_cuts_where_the_plain_rendering_cuts() -> None:
    """The same boundary ``test_one_character_past_the_cap_is_truncated`` pins.

    A subject of exactly the cap is shown whole, so a ``truncated from`` note
    beside it would send the reader looking for the rest of a string they are
    already being shown all of. One character more and the note is the truth.
    """
    line = "x" * 119 + "\t"
    with pytest.raises(AssertionFailure) as caught:
        expect(line).is_alpha()
    message = str(caught.value)
    assert "truncated" not in message
    assert "..." not in message
    assert repr(line) in message
    line = "x" * 120 + "\t"
    with pytest.raises(AssertionFailure) as caught:
        expect(line).is_alpha()
    assert "truncated from 121 characters" in str(caught.value)


def test_an_offender_in_the_opening_window_gets_no_leading_ellipsis() -> None:
    """The window is clamped to the front of the document rather than sliding off it.

    ``_clipped_around`` centres the window on the offender, and for a character
    in the first half-window there is nothing before it to elide. A leading
    ``'...'`` there would claim text was cut that never existed, and would move
    the reported index away from where the reader can count to it. The trailing
    one is still owed, because the rest of the document really was cut.
    """
    document = "a" * 40 + "\t" + "a" * 400

    with pytest.raises(AssertionFailure) as caught:
        expect(document).is_alpha()

    assert str(caught.value) == (
        "Expected document to contain only alphabetic characters, but "
        + repr("a" * 40 + "\t" + "a" * 79 + "...")
        + " (truncated from 441 characters) has '\\t' at index 40."
    )


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------
def test_is_identifier_tells_an_opening_character_from_a_later_one() -> None:
    """The two halves are told apart, because they send the reader to different fixes."""
    expect("user_id").is_identifier()
    expect("_private").is_identifier()
    field = "1st"
    with pytest.raises(AssertionFailure) as caught:
        expect(field).is_identifier()
    assert str(caught.value) == (
        "Expected field to be a valid Python identifier, but '1st' cannot start with '1'."
    )
    field = "my-var"
    with pytest.raises(AssertionFailure) as caught:
        expect(field).is_identifier()
    assert str(caught.value) == (
        "Expected field to be a valid Python identifier, but 'my-var' has '-' at index 2."
    )


def test_an_empty_string_is_not_an_identifier() -> None:
    field = ""
    with pytest.raises(AssertionFailure) as caught:
        expect(field).is_identifier()
    assert str(caught.value) == (
        "Expected field to be a valid Python identifier, but it was empty."
    )


def test_a_digit_inside_an_identifier_is_not_the_offender() -> None:
    """The opening rule and the continuation rule are different sets.

    A digit cannot *start* an identifier and is perfectly legal after one, so
    testing each character with the opening rule would stop at the ``"1"`` and
    send the reader to fix a character that is not the problem.
    """
    field = "a1-b"
    with pytest.raises(AssertionFailure) as caught:
        expect(field).is_identifier()
    assert str(caught.value) == (
        "Expected field to be a valid Python identifier, but 'a1-b' has '-' at index 2."
    )


def test_a_keyword_is_a_valid_identifier() -> None:
    """``str.isidentifier`` answers the lexical question only, and so does this."""
    expect("class").is_identifier()
    expect("class").is_identifier().and_.is_in(keyword.kwlist)


def test_is_not_identifier() -> None:
    expect("my-var").is_not_identifier()
    field = "user_id"
    with pytest.raises(AssertionFailure) as caught:
        expect(field).is_not_identifier()
    assert str(caught.value) == (
        "Expected field not to be a valid Python identifier, but 'user_id' is one."
    )


# ---------------------------------------------------------------------------
# Title case
# ---------------------------------------------------------------------------
def test_is_title_names_which_half_of_the_rule_broke() -> None:
    heading = "hello World"
    expect("Hello World").is_title()
    with pytest.raises(AssertionFailure) as caught:
        expect(heading).is_title()
    assert str(caught.value) == (
        "Expected heading to be title case, "
        "but 'hello World' starts a word with lower-case 'h' at index 0."
    )
    heading = "HELLO"
    with pytest.raises(AssertionFailure) as caught:
        expect(heading).is_title()
    assert str(caught.value) == (
        "Expected heading to be title case, "
        "but 'HELLO' continues a word with upper-case 'E' at index 1."
    )


def test_the_word_boundary_resets_the_title_case_walk() -> None:
    """An uncased character ends a word; the next lower-case one starts a new one.

    Without the reset the walk reads ``"Hello world"`` as one long word, finds
    nothing wrong with it, and falls through to a message that names no
    character at all -- on the single most likely way to get title case wrong.
    """
    heading = "Hello world"
    with pytest.raises(AssertionFailure) as caught:
        expect(heading).is_title()
    assert str(caught.value) == (
        "Expected heading to be title case, "
        "but 'Hello world' starts a word with lower-case 'w' at index 6."
    )


def test_an_uncased_string_is_not_title_case_and_is_told_why() -> None:
    """The same trap ``is_upper`` documents, and the same message."""
    code = "123"
    with pytest.raises(AssertionFailure) as caught:
        expect(code).is_title()
    assert str(caught.value) == "Expected code to be title case, but '123' has no cased characters."


def test_an_empty_string_is_not_title_case() -> None:
    heading = ""
    with pytest.raises(AssertionFailure) as caught:
        expect(heading).is_title()
    assert str(caught.value) == "Expected heading to be title case, but it was empty."


def test_is_not_title() -> None:
    expect("hello world").is_not_title()
    heading = "Hello World"
    with pytest.raises(AssertionFailure) as caught:
        expect(heading).is_not_title()
    assert str(caught.value) == "Expected heading not to be title case, but 'Hello World' is."


def test_a_title_case_character_is_neither_upper_nor_lower() -> None:
    """``"ǅ"`` is Unicode category ``Lt``: ``istitle`` is true, ``isupper`` is false.

    The three assertions that walk a string character by character have to agree
    with ``str``'s own answer on it, or the message would name an innocent
    character.
    """
    expect("ǅ").is_title()
    expect("ǅ").is_not_upper().and_.is_not_lower()
    for failing in (StringExpect.is_upper, StringExpect.is_lower):
        with pytest.raises(AssertionFailure) as caught:
            failing(expect("ǅ"))
        assert "has 'ǅ' at index 0" in str(caught.value), (
            "a title-case character is cased, so the uncased branch must not claim it"
        )
    with pytest.raises(AssertionFailure) as caught:
        expect("Aǅ").is_upper()
    assert "has 'ǅ' at index 1" in str(caught.value)
    with pytest.raises(AssertionFailure) as caught:
        expect("aǅ").is_lower()
    assert "has 'ǅ' at index 1" in str(caught.value)


# ---------------------------------------------------------------------------
# UUIDs
# ---------------------------------------------------------------------------
_UUID4 = "b7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c"
_UUID1 = "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"


def test_is_uuid_hands_back_a_uuid_that_compares_the_way_the_reader_expects() -> None:
    """The whole reason this assertion exists.

    ``UUID(text) == text`` is ``False``, silently and in both directions, so an
    id that crossed a JSON boundary never equals the same id that did not.
    """
    assert uuid.UUID(_UUID4) != _UUID4
    found = expect(_UUID4).is_uuid()
    assert found.subject == uuid.UUID(_UUID4)
    found.which.is_equal_to(uuid.UUID(_UUID4))


def test_which_dispatches_onward_for_free() -> None:
    """``.which`` is an ordinary subject; the generic catalogue comes with it."""
    expect(_UUID4).is_uuid().which.is_not_none().and_.is_instance_of(uuid.UUID)


def test_and_returns_to_the_string() -> None:
    expect(_UUID4).is_uuid().and_.has_length(36).and_.is_not_upper()


@pytest.mark.parametrize(
    "spelling",
    [
        _UUID4,
        _UUID4.upper(),
        _UUID4.replace("-", ""),
        "{" + _UUID4 + "}",
        "urn:uuid:" + _UUID4,
    ],
    ids=["dashed", "upper-case", "dashless", "braced", "urn"],
)
def test_every_spelling_uuid_accepts_is_accepted(spelling: str) -> None:
    assert expect(spelling).is_uuid().subject == uuid.UUID(_UUID4)


@pytest.mark.parametrize(
    "sloppy",
    ["1_234567890123456789012345678901", " 0123456789abcdef0123456789abcde"],
    ids=["underscore", "leading-space"],
)
def test_the_spellings_uuid_accepts_by_accident_are_refused(sloppy: str) -> None:
    """``uuid.UUID`` finishes with ``int(body, 16)``, which is far too forgiving.

    Both of these parse, and both come back as a *different* id from the one
    that was written -- which is the exact bug this assertion exists to catch.
    """
    assert str(uuid.UUID(sloppy)).replace("-", "") != sloppy.replace("-", "")
    with pytest.raises(AssertionFailure, match="hexadecimal digit was expected"):
        expect(sloppy).is_uuid()


def test_is_uuid_reports_a_body_of_the_wrong_length() -> None:
    identifier = "not-a-uuid"
    with pytest.raises(AssertionFailure) as caught:
        expect(identifier).is_uuid()
    assert str(caught.value) == (
        "Expected identifier to be a UUID, "
        "but 'not-a-uuid' has a body of 8 characters, not 32 hexadecimal digits."
    )


def test_the_length_is_counted_after_the_punctuation_comes_off() -> None:
    """Dashes and braces are punctuation; counting them would report a number nobody meant."""
    identifier = ""
    with pytest.raises(AssertionFailure) as caught:
        expect(identifier).is_uuid()
    assert "a body of 0 characters" in str(caught.value)


def test_is_uuid_points_at_the_character_that_is_not_hexadecimal() -> None:
    identifier = "z7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c"
    with pytest.raises(AssertionFailure) as caught:
        expect(identifier).is_uuid()
    assert str(caught.value) == (
        "Expected identifier to be a UUID, but 'z7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c' has 'z' "
        "where a hexadecimal digit was expected, at digit 1 of 32."
    )


def test_is_uuid_checks_the_version_when_it_is_asked_to() -> None:
    expect(_UUID4).is_uuid(version=4)
    expect(_UUID1).is_uuid(version=1)
    identifier = _UUID4
    with pytest.raises(AssertionFailure) as caught:
        expect(identifier).is_uuid(version=1)
    assert str(caught.value) == (
        f"Expected identifier to be a version 1 UUID, but '{_UUID4}' is version 4."
    )


def test_a_well_formed_uuid_can_carry_no_version_at_all() -> None:
    """``UUID.version`` reads bits only an RFC 4122 variant has, so it can be ``None``.

    Reporting "is version None" would send the reader looking for a version 4
    that is not there, when the actual finding is about the variant.
    """
    identifier = "12345678-1234-5678-1234-567812345678"
    expect(identifier).is_uuid()
    assert uuid.UUID(identifier).version is None
    with pytest.raises(AssertionFailure) as caught:
        expect(identifier).is_uuid(version=4)
    assert str(caught.value) == (
        f"Expected identifier to be a version 4 UUID, but '{identifier}' carries no version, "
        "its variant not being RFC 4122."
    )


@pytest.mark.parametrize("version", [0, 6, 7, -1, 42])
def test_a_version_outside_the_supported_range_is_a_caller_bug(version: int) -> None:
    """``ValueError``, not ``AssertionFailure``: the test is wrong, not the subject.

    The message is a fact about the assertion rather than about UUIDs, because
    versions 6, 7 and 8 are perfectly real -- RFC 9562 defines them and v7 is
    now a common database id. Telling their holder that "a UUID version must be
    1, 2, 3, 4 or 5" would send them to debug an id that is not broken.
    """
    with pytest.raises(ValueError, match="checks UUID versions 1 to 5") as caught:
        expect(_UUID4).is_uuid(version=version)
    assert not isinstance(caught.value, AssertionFailure)
    assert "6, 7 and 8" in str(caught.value), "the reader has to be told what is missing"


def test_the_rejected_uuid_version_is_named_in_the_message() -> None:
    """A rejection that lists what is valid and not what arrived is half a message.

    Pinned as the whole sentence rather than through ``match=``: the clause that
    carries the number is the last one, and a pattern aimed at the range would go
    on passing with it gone.
    """
    with pytest.raises(ValueError, match="version asked for") as caught:
        expect(_UUID4).is_uuid(version=9)

    assert str(caught.value) == (
        "this assertion checks UUID versions 1 to 5; RFC 9562 also defines 6, 7 and 8,"
        " and the version asked for was 9"
    )


def test_two_rejected_uuid_versions_do_not_read_alike() -> None:
    """The defect this guards is a constant: one sentence for every wrong number."""
    with pytest.raises(ValueError, match="version asked for") as nine:
        expect(_UUID4).is_uuid(version=9)
    with pytest.raises(ValueError, match="version asked for") as zero:
        expect(_UUID4).is_uuid(version=0)

    assert str(nine.value) != str(zero.value)


def test_a_version_7_uuid_still_parses() -> None:
    """Only the ``version=`` filter stops at five; the format check does not."""
    identifier = "0192f0e1-2c3d-7abc-8def-0123456789ab"
    assert expect(identifier).is_uuid().subject.version == 7


def test_the_version_guard_is_not_swallowed_by_a_soft_scope() -> None:
    with pytest.raises(ValueError, match="checks UUID versions"), soft_assertions():
        expect(_UUID4).is_uuid(version=9)


def test_a_failed_is_uuid_absorbs_the_rest_of_its_chain() -> None:
    """One root cause, one message: the UUID that was never parsed cannot be wrong too."""
    identifier = "nope"
    with soft_assertions() as scope:
        expect(identifier).is_uuid().which.is_equal_to(uuid.UUID(_UUID4))
        messages = scope.discard()
    assert len(messages) == 1
    assert "to be a UUID" in messages[0]


# ---------------------------------------------------------------------------
# The subject itself
# ---------------------------------------------------------------------------
def test_expect_hands_back_a_string_subject() -> None:
    assert isinstance(expect("x"), StringExpect)


def test_chaining_keeps_the_same_wrapper() -> None:
    subject = expect("hello world")
    assert subject.is_not_empty().and_.contains("wor").and_.has_length(11) is subject


def test_inherited_assertions_are_still_there() -> None:
    """A string subject keeps every assertion the generic catalogue gives it."""
    expect("draft").is_equal_to("draft").and_.is_one_of("draft", "final")


def test_every_broken_clause_is_reported_in_a_soft_scope() -> None:
    """``_fail`` hands the subject back, so a soft block reports the whole chain."""
    slug = "Hello World"
    with pytest.raises(AssertionFailure) as caught, soft_assertions("payload"):
        expect(slug).is_lower().and_.does_not_contain(" ").and_.matches_wildcard("hello*")
    message = str(caught.value)
    assert "3 assertions failed:" in message
    assert "Expected payload/slug to be lower case, but 'Hello World' has 'H' at index 0" in message
    assert "Expected payload/slug not to contain ' ', but 'Hello World' does" in message
    assert (
        "Expected payload/slug to match the wildcard pattern 'hello*', but was 'Hello World'"
        in message
    )


def test_an_empty_multi_value_call_is_not_swallowed_by_a_soft_scope() -> None:
    """A caller bug is not an assertion failure, so a soft scope must not collect it."""
    with pytest.raises(ValueError, match="at least one value"), soft_assertions():
        expect("x").contains_all()


# ---------------------------------------------------------------------------
# `because` reaches all of them, and is keyword-only on every one
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: expect("x").is_empty(because="R"), id="is_empty"),
        pytest.param(lambda: expect("").is_not_empty(because="R"), id="is_not_empty"),
        pytest.param(lambda: expect("x").is_blank(because="R"), id="is_blank"),
        pytest.param(lambda: expect(" ").is_not_blank(because="R"), id="is_not_blank"),
        pytest.param(lambda: expect("x").has_length(9, because="R"), id="has_length"),
        pytest.param(
            lambda: expect("x").is_equal_ignoring_case("y", because="R"), id="is_equal_ic"
        ),
        pytest.param(
            lambda: expect("x").is_not_equal_ignoring_case("X", because="R"), id="is_not_equal_ic"
        ),
        pytest.param(lambda: expect("x").contains("y", because="R"), id="contains"),
        pytest.param(
            lambda: expect("x").contains("y", occurrences=once, because="R"),
            id="contains_occurrences",
        ),
        pytest.param(
            lambda: expect("x").does_not_contain("x", occurrences=once, because="R"),
            id="does_not_contain_occurrences",
        ),
        pytest.param(
            lambda: expect("x").contains_ignoring_case("X", occurrences=twice, because="R"),
            id="contains_ignoring_case_occurrences",
        ),
        pytest.param(
            lambda: expect("x").matches("x", occurrences=twice, because="R"),
            id="matches_occurrences",
        ),
        pytest.param(lambda: expect("x").does_not_contain("x", because="R"), id="does_not_contain"),
        pytest.param(lambda: expect("x").contains_all("y", because="R"), id="contains_all"),
        pytest.param(
            lambda: expect("x").does_not_contain_all("x", because="R"), id="does_not_contain_all"
        ),
        pytest.param(lambda: expect("x").contains_any("y", because="R"), id="contains_any"),
        pytest.param(
            lambda: expect("x").does_not_contain_any("x", because="R"), id="does_not_contain_any"
        ),
        pytest.param(
            lambda: expect("x").contains_ignoring_case("y", because="R"), id="contains_ic"
        ),
        pytest.param(
            lambda: expect("x").does_not_contain_ignoring_case("X", because="R"),
            id="does_not_contain_ic",
        ),
        pytest.param(lambda: expect("x").starts_with("y", because="R"), id="starts_with"),
        pytest.param(
            lambda: expect("x").does_not_start_with("x", because="R"), id="does_not_start_with"
        ),
        pytest.param(
            lambda: expect("x").starts_with_ignoring_case("y", because="R"), id="starts_with_ic"
        ),
        pytest.param(
            lambda: expect("x").does_not_start_with_ignoring_case("X", because="R"),
            id="does_not_start_with_ic",
        ),
        pytest.param(lambda: expect("x").ends_with("y", because="R"), id="ends_with"),
        pytest.param(
            lambda: expect("x").does_not_end_with("x", because="R"), id="does_not_end_with"
        ),
        pytest.param(
            lambda: expect("x").ends_with_ignoring_case("y", because="R"), id="ends_with_ic"
        ),
        pytest.param(
            lambda: expect("x").does_not_end_with_ignoring_case("X", because="R"),
            id="does_not_end_with_ic",
        ),
        pytest.param(lambda: expect("x").matches("y", because="R"), id="matches_regex"),
        pytest.param(
            lambda: expect("x").matches(lambda _: False, because="R"), id="matches_predicate"
        ),
        pytest.param(lambda: expect("x").does_not_match("x", because="R"), id="does_not_match"),
        pytest.param(lambda: expect("x").matches_wildcard("y", because="R"), id="matches_wildcard"),
        pytest.param(
            lambda: expect("x").does_not_match_wildcard("x", because="R"),
            id="does_not_match_wildcard",
        ),
        pytest.param(
            lambda: expect("x").matches_wildcard_ignoring_case("y", because="R"),
            id="matches_wildcard_ic",
        ),
        pytest.param(
            lambda: expect("x").does_not_match_wildcard_ignoring_case("X", because="R"),
            id="does_not_match_wildcard_ic",
        ),
        pytest.param(lambda: expect("x").is_upper(because="R"), id="is_upper"),
        pytest.param(lambda: expect("X").is_not_upper(because="R"), id="is_not_upper"),
        pytest.param(lambda: expect("X").is_lower(because="R"), id="is_lower"),
        pytest.param(lambda: expect("x").is_not_lower(because="R"), id="is_not_lower"),
        pytest.param(lambda: expect("x").is_title(because="R"), id="is_title"),
        pytest.param(lambda: expect("X").is_not_title(because="R"), id="is_not_title"),
        pytest.param(lambda: expect("1").is_alpha(because="R"), id="is_alpha"),
        pytest.param(lambda: expect("a").is_not_alpha(because="R"), id="is_not_alpha"),
        pytest.param(lambda: expect("a").is_digit(because="R"), id="is_digit"),
        pytest.param(lambda: expect("1").is_not_digit(because="R"), id="is_not_digit"),
        pytest.param(lambda: expect("a").is_numeric(because="R"), id="is_numeric"),
        pytest.param(lambda: expect("1").is_not_numeric(because="R"), id="is_not_numeric"),
        pytest.param(lambda: expect("!").is_alnum(because="R"), id="is_alnum"),
        pytest.param(lambda: expect("a").is_not_alnum(because="R"), id="is_not_alnum"),
        pytest.param(lambda: expect("\u00e9").is_ascii(because="R"), id="is_ascii"),
        pytest.param(lambda: expect("a").is_not_ascii(because="R"), id="is_not_ascii"),
        pytest.param(lambda: expect("\n").is_printable(because="R"), id="is_printable"),
        pytest.param(lambda: expect("a").is_not_printable(because="R"), id="is_not_printable"),
        pytest.param(lambda: expect("a").is_space(because="R"), id="is_space"),
        pytest.param(lambda: expect(" ").is_not_space(because="R"), id="is_not_space"),
        pytest.param(lambda: expect("1a").is_identifier(because="R"), id="is_identifier"),
        pytest.param(lambda: expect("a").is_not_identifier(because="R"), id="is_not_identifier"),
        pytest.param(lambda: expect("nope").is_uuid(because="R"), id="is_uuid"),
        pytest.param(lambda: expect(_UUID4).is_uuid(version=1, because="R"), id="is_uuid_version"),
    ],
)
def test_because_reaches_every_assertion(call: Callable[[], object]) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()


# ---------------------------------------------------------------------------
# occurrences: counting instead of asking
# ---------------------------------------------------------------------------
def test_contains_counts_when_it_is_given_a_constraint() -> None:
    """The sentence the whole feature exists to produce."""
    log = "retrying\nretrying\n"
    expect(log).contains("retrying", occurrences=twice)
    with pytest.raises(AssertionFailure) as caught:
        expect(log).contains("retrying", occurrences=exactly(3))
    assert str(caught.value) == "Expected log to contain 'retrying' exactly 3 times, but found 2."


def test_no_constraint_leaves_the_assertion_exactly_as_it_was() -> None:
    """The ``occurrences`` keyword must not move a byte of a message it did not touch.

    Both spellings of "no constraint" are checked -- the default, and ``None``
    passed outright, which is what a caller forwarding an optional gets.
    """
    greeting = "hello world"
    expect(greeting).contains("lo wo")
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).contains("bye")
    assert str(caught.value) == "Expected greeting to contain 'bye', but was 'hello world'."
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).contains("bye", occurrences=None)
    assert str(caught.value) == "Expected greeting to contain 'bye', but was 'hello world'."


def test_counting_is_non_overlapping_because_str_count_is() -> None:
    r"""The one answer that surprises people, pinned against ``str.count`` itself.

    The scan resumes *past* the match it just made rather than one character into
    it, so the two ``"aa"``\ s a reader can see in ``"aaa"`` are one match.
    """
    stutter = "aaa"
    assert stutter.count("aa") == 1
    expect(stutter).contains("aa", occurrences=once)
    with pytest.raises(AssertionFailure) as caught:
        expect(stutter).contains("aa", occurrences=twice)
    assert str(caught.value) == "Expected stutter to contain 'aa' exactly twice, but found 1."


def test_a_lookahead_is_how_the_overlapping_count_is_asked_for() -> None:
    """The escape hatch :meth:`contains` promises. If it stops working, so does the promise."""
    expect("aaa").matches(r"(?=aa)", occurrences=twice)


def test_the_empty_needle_follows_str_count_too() -> None:
    """One position before each character and one after the last -- Python's rule, kept."""
    assert "abc".count("") == 4
    expect("abc").contains("", occurrences=exactly(4))


def test_does_not_contain_negates_the_count_and_not_the_presence() -> None:
    """Worth reading twice: with a constraint this is no longer "it is not there"."""
    log = "retrying\nretrying\n"
    # It *is* there, twice. The constraint asked about three, and three is not what
    # happened, so the assertion holds.
    expect(log).does_not_contain("retrying", occurrences=exactly(3))
    with pytest.raises(AssertionFailure) as caught:
        expect(log).does_not_contain("retrying", occurrences=twice)
    assert str(caught.value) == (
        "Expected log not to contain 'retrying' exactly twice, but found 2."
    )


def test_never_appearing_can_be_said_three_ways_and_all_three_work() -> None:
    """``_occurrence`` keeps three spellings of "it never appears"; they arrive here."""
    quiet = "all good"
    expect(quiet).does_not_contain("ERROR")
    expect(quiet).contains("ERROR", occurrences=exactly(0))
    expect(quiet).contains("ERROR", occurrences=at_most(0))
    expect(quiet).contains("ERROR", occurrences=less_than(1))
    with pytest.raises(AssertionFailure) as caught:
        expect(quiet).contains("good", occurrences=exactly(0))
    assert str(caught.value) == "Expected quiet to contain 'good' exactly 0 times, but found 1."


def test_contains_ignoring_case_counts_the_folded_text() -> None:
    greeting = "Hello HELLO hello"
    expect(greeting).contains_ignoring_case("hello", occurrences=exactly(3))
    with pytest.raises(AssertionFailure) as caught:
        expect(greeting).contains_ignoring_case("HELLO", occurrences=twice)
    assert str(caught.value) == (
        "Expected greeting to contain 'HELLO' ignoring case exactly twice, but found 3."
    )


def test_folding_can_change_the_length_and_the_count_follows_it() -> None:
    """``"\u00df"`` folds to ``"ss"``, so the folded text is what gets counted."""
    sharp = "\u00df\u00df"
    assert sharp.casefold() == "ssss"
    expect(sharp).contains_ignoring_case("ss", occurrences=twice)


def test_matches_counts_non_overlapping_matches() -> None:
    version = "v2.11.3"
    expect(version).matches(r"\d+", occurrences=exactly(3))
    expect(version).matches(r"\d+", occurrences=at_least(3))
    expect(version).matches(r"\d+", occurrences=more_than(2))
    with pytest.raises(AssertionFailure) as caught:
        expect(version).matches(r"\d+", occurrences=twice)
    assert str(caught.value) == (
        "Expected version to match the regular expression '\\\\d+' exactly twice, but found 3."
    )


def test_a_compiled_pattern_is_counted_too() -> None:
    version = "v2.11.3"
    expect(version).matches(re.compile(r"\d+"), occurrences=exactly(3))
    with pytest.raises(AssertionFailure, match="exactly twice, but found 3"):
        expect(version).matches(re.compile(r"\d+"), occurrences=twice)


def test_a_pattern_with_groups_is_counted_once_per_match() -> None:
    """``re.findall`` answers with the *groups*; what is counted here is matches.

    The count is taken with ``finditer`` for that reason -- and because a pattern
    with groups would otherwise have ``findall`` build a tuple per match to answer
    a question about how many there were.
    """
    pairs = "a=1 b=2 c=3"
    assert re.findall(r"(\w)=(\d)", pairs) == [("a", "1"), ("b", "2"), ("c", "3")]
    expect(pairs).matches(r"(\w)=(\d)", occurrences=exactly(3))
    expect(pairs).matches(r"(\w)=\d", occurrences=exactly(3))


def test_a_zero_width_pattern_matches_everywhere() -> None:
    """The trap the docstring names: ``x*`` matches at every position, and at the end."""
    subject = "abc"
    with pytest.raises(AssertionFailure) as caught:
        expect(subject).matches("x*", occurrences=once)
    assert str(caught.value) == (
        "Expected subject to match the regular expression 'x*' exactly once, but found 4."
    )


def test_occurrences_with_a_predicate_is_a_caller_bug() -> None:
    """A predicate answers yes or no and has nothing to count.

    The overloads refuse the pair statically; this is what an untyped caller gets,
    and it must not be an ``AssertionFailure`` -- a runner would present a bug in
    the test as a finding about the subject.
    """

    def starts_with_h(text: str) -> bool:
        return text.startswith("h")

    untyped: Any = expect("hello")
    with pytest.raises(TypeError, match="pass a pattern, or drop occurrences") as caught:
        untyped.matches(starts_with_h, occurrences=once)
    assert not isinstance(caught.value, AssertionFailure)


def test_the_predicate_form_is_untouched_when_no_count_is_asked_for() -> None:
    """The inherited ``matches(predicate)`` still works, keyword or no keyword."""
    expect("ab").matches(lambda text: len(text) < 3)
    with pytest.raises(AssertionFailure, match="to match the predicate"):
        expect("hello").matches(lambda text: len(text) < 3)


#: One row per constraint the occurrence module ships, each with a subject that
#: makes it fail, so that the phrase can be read where it actually lands. The
#: singular is in the table on purpose: "at most onces" is the tell that nobody
#: read the output of the thing whose whole job is to be read.
_COUNTED: Final[list[tuple[str, Occurrence, str, str, int]]] = [
    ("exactly", exactly(3), "xx", "exactly 3 times", 2),
    ("at_least", at_least(3), "xx", "at least 3 times", 2),
    ("at_most", at_most(1), "xx", "at most once", 2),
    ("more_than", more_than(2), "xx", "more than twice", 2),
    ("less_than", less_than(2), "xx", "less than 2 times", 2),
    ("once", once, "xx", "exactly once", 2),
    ("twice", twice, "xxx", "exactly twice", 3),
]


@pytest.mark.parametrize(
    ("constraint", "subject", "phrase", "found"),
    [(row[1], row[2], row[3], row[4]) for row in _COUNTED],
    ids=[row[0] for row in _COUNTED],
)
def test_every_constraint_reads_inside_the_message(
    constraint: Occurrence, subject: str, phrase: str, found: int
) -> None:
    with pytest.raises(AssertionFailure) as caught:
        expect(subject).contains("x", occurrences=constraint)
    assert str(caught.value) == (
        "Expected subject to contain 'x' " + phrase + ", but found " + str(found) + "."
    )


def test_a_counted_assertion_reports_into_a_soft_scope() -> None:
    """Counting happens before ``_fail``, so the soft route has to survive it."""
    log = "retrying\n"
    with soft_assertions() as scope:
        expect(log).contains("retrying", occurrences=exactly(3))
        expect(log).matches("retry", occurrences=at_least(2))
        collected = scope.discard()
    assert collected == [
        "Expected log to contain 'retrying' exactly 3 times, but found 1.",
        "Expected log to match the regular expression 'retry' at least twice, but found 1.",
    ]


def test_counting_holds_nothing_after_the_call() -> None:
    """A passing counted assertion holds nothing once it has answered.

    ``tests/test_performance_invariants.py`` does not reach these calls.
    ``blocks_allocated`` counts blocks the interpreter still *holds*, so the
    ``occurrences=None`` rows say the keyword puts nothing on a path that is
    already free, and the counted rows say the counting keeps nothing either.
    """
    baseline = blocks_allocated(lambda: None)
    text = expect("hello world")
    cases: list[tuple[str, Callable[[], object]]] = [
        ("contains", lambda: text.contains("wor")),
        ("contains + occurrences", lambda: text.contains("o", occurrences=twice)),
        ("does_not_contain", lambda: text.does_not_contain("bye")),
        ("does_not_contain + occurrences", lambda: text.does_not_contain("o", occurrences=once)),
        ("contains_ignoring_case", lambda: text.contains_ignoring_case("WOR")),
        (
            "contains_ignoring_case + occurrences",
            lambda: text.contains_ignoring_case("O", occurrences=twice),
        ),
    ]
    for label, call in cases:
        allocated = blocks_allocated(call)
        assert allocated <= baseline, (
            f"{label} held {allocated - baseline} blocks after 20000 passing calls; "
            f"a passing assertion is a comparison and a `return self`."
        )


# ---------------------------------------------------------------------------
# Values go out through the formatter registry
# ---------------------------------------------------------------------------
class Braced:
    """A ``str`` formatter, told apart from ``repr`` at a glance.

    Scoped rather than registered globally: global registration is write-once and
    would rewrite every other test's strings for the rest of the session.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return type(value) is str

    def format(self, value: object, /) -> str:
        return "<<" + str(value) + ">>"


def test_a_registered_formatter_reaches_this_catalogue_too() -> None:
    """One value must not read two ways in one report.

    ``is_equal_to`` is inherited and has always rendered through the registry, so
    a formatter looks like it works. The assertions written here interpolate the
    string themselves, and rendering those with ``repr`` at the call site is the
    quiet half of the failure: the same subject then appears formatted on one line
    of a soft report and raw on the next.
    """
    with soft_assertions(formatters=(Braced(),)) as scope:
        label = "hello"
        expect(label).is_equal_to("bye")
        expect(label).starts_with("bye")
        expect(label).ends_with("bye")
        expect(label).contains("bye")
        expect(label).contains_all("bye", "he")
        collected = scope.discard()

    assert collected == [
        "Expected label to equal <<bye>>, but was <<hello>>.",
        "Expected label to start with <<bye>>, but was <<hello>>.",
        "Expected label to end with <<bye>>, but was <<hello>>.",
        "Expected label to contain <<bye>>, but was <<hello>>.",
        "Expected label to contain all of [<<bye>>, <<he>>], but <<hello>> is missing [<<bye>>].",
    ]


def test_a_formatter_reaches_the_character_that_broke_a_class_assertion() -> None:
    """The offending character is a value the message renders, so it goes out too."""
    with soft_assertions(formatters=(Braced(),)) as scope:
        label = "a b"
        expect(label).is_alpha()
        collected = scope.discard()

    assert collected == [
        "Expected label to contain only alphabetic characters, but <<a b>> has << >> at index 1."
    ]


def test_a_formatter_is_handed_the_elided_text_and_not_the_whole_document() -> None:
    """The clip runs first, so the ``...`` lands inside the rendering.

    Rendering the whole document and clipping the *result* instead would cut a
    formatter's own output in half, and would spend ``max_chars`` on the quotes
    and escapes a rendering adds rather than on the subject's characters. The
    length note still reports the document, not the window.
    """
    document = "z" * 300
    windowed = "z" * 20 + "1" + "z" * 20
    with formatting(max_chars=8), soft_assertions(formatters=(Braced(),)) as scope:
        expect(document).is_empty()
        expect(document).ends_with("q")
        expect(windowed).is_alpha()
        collected = scope.discard()

    tail = " (truncated from 300 characters)."
    assert collected == [
        "Expected document to be empty, but was <<zzzzzzzz...>>" + tail,
        "Expected document to end with <<q>>, but was <<...zzzzzzzz>>" + tail,
        (
            "Expected windowed to contain only alphabetic characters, but"
            " <<...zzzz1zzz...>> (truncated from 41 characters) has <<1>> at index 20."
        ),
    ]


@pytest.fixture
def no_value_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """Booby-trap the registry lookup, which no passing assertion may reach."""
    monkeypatch.setattr(_string, "format_value", Detonator())


@pytest.mark.usefixtures("no_value_rendering")
def test_a_passing_string_assertion_never_renders_a_value() -> None:
    """Rendering is a failure-path cost, and the registry walk is the expensive half.

    Every string in every message here goes through the registry, which reads a
    ``ContextVar`` and then asks each registered formatter about the value. A
    passing assertion pays a comparison and a ``return self``, so the render has
    to sit past it.
    """
    expect("hello world").contains("wor")
    expect("hello world").starts_with("hello").and_.ends_with("world")
    expect("hello world").contains_all("hello", "world")
    expect("hello").is_lower().and_.is_alpha()
    expect("b7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c").is_uuid()


@pytest.mark.usefixtures("no_value_rendering")
def test_the_rendering_trap_actually_detonates() -> None:
    """A rule nobody can fail is not a rule: a *failing* assertion does render."""
    with pytest.raises(AssertionError, match="called into the failure path"):
        expect("hello").is_empty()


# ---------------------------------------------------------------------------
# The rendering bounds come from the formatting scope, not from a constant here
# ---------------------------------------------------------------------------
def test_the_default_bounds_are_the_numbers_that_used_to_be_constants() -> None:
    """With no scope open, a subject still clips at 120 characters and a listing at ten.

    ``_string.py`` holds neither number; the defaults on ``FormattingOptions``
    are the only place either one lives, which is the whole risk of keeping a
    bound in one place -- what it *says* has to go on holding.
    """
    document = "z" * 400
    with pytest.raises(AssertionFailure) as caught:
        expect(document).is_empty()
    message = str(caught.value)
    assert "'" + "z" * 120 + "...'" in message
    assert "(truncated from 400 characters)" in message

    fields = tuple("field_" + str(index) for index in range(400))
    with pytest.raises(AssertionFailure) as caught:
        expect("z").contains_all(*fields)
    assert "'field_9', ... 390 more]" in str(caught.value)


def test_a_scope_shows_a_hundred_of_four_hundred_values() -> None:
    """The wiring, proved from the outside rather than by reading the source.

    Ten values is the right number for the message a reader *skims*. It is the
    wrong number for the one they are debugging, and this is the block that lets
    them say so.
    """
    fields = tuple("field_" + str(index) for index in range(400))
    with formatting(max_items=100), pytest.raises(AssertionFailure) as caught:
        expect("z").contains_all(*fields)
    message = str(caught.value)
    assert "'field_99', ... 300 more]" in message
    assert "'field_100'" not in message


def test_a_scope_widens_the_clipped_subject() -> None:
    document = "z" * 400
    with formatting(max_chars=300), pytest.raises(AssertionFailure) as caught:
        expect(document).is_empty()
    message = str(caught.value)
    assert "'" + "z" * 300 + "...'" in message
    assert "(truncated from 400 characters)" in message


def test_a_scope_widens_the_tail_the_ends_with_family_shows() -> None:
    """``_clipped_end`` keeps the end of a long document; the bound is the same one."""
    document = "z" * 400 + "TAIL"
    with formatting(max_chars=300), pytest.raises(AssertionFailure) as caught:
        expect(document).ends_with("nope")
    assert "'..." + "z" * 296 + "TAIL'" in str(caught.value)


def test_a_scope_widens_the_window_around_an_offending_character() -> None:
    """``_clipped_around`` keeps the offender in view, inside a window of the same bound."""
    document = "a" * 400 + "1" + "a" * 400
    with formatting(max_chars=40), pytest.raises(AssertionFailure) as caught:
        expect(document).is_alpha()
    message = str(caught.value)
    assert "'..." + "a" * 20 + "1" + "a" * 19 + "...'" in message
    assert "has '1' at index 400" in message
    assert "(truncated from 801 characters)" in message


def test_a_scope_changes_what_is_said_and_never_what_is_decided() -> None:
    """The narrowest legal bounds cannot turn a pass into a failure, or the reverse."""
    with formatting(max_chars=1, max_items=1):
        expect("hello").contains("ell")
        expect("hello").contains_all("he", "lo")
        expect("hello").matches("^he", occurrences=once)
        with pytest.raises(AssertionFailure):
            expect("hello").contains("bye")


@pytest.fixture
def no_options_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Booby-trap the options lookup, the way this file already traps ``_fail``."""
    monkeypatch.setattr(_formatting, "_ACTIVE", Detonator())


@pytest.mark.usefixtures("no_options_lookup")
def test_a_passing_string_assertion_never_reads_the_formatting_options() -> None:
    """A passing assertion reads no ``ContextVar``.

    Every rendering helper in ``_string.py`` performs one, so each of them has to
    sit past a ``return self``. This is the half of the invariant that the
    allocation count cannot see -- a lookup that allocates nothing is still a
    lookup.
    """
    expect("hello world").contains("wor")
    expect("hello world").contains("wor", occurrences=once)
    expect("hello world").does_not_contain("bye")
    expect("hello world").does_not_contain("wor", occurrences=twice)
    expect("Hello World").contains_ignoring_case("WOR")
    expect("Hello World").contains_ignoring_case("O", occurrences=twice)
    expect("hello world").contains_all("hello", "world")
    expect("hello world").contains_any("bye", "hello")
    expect("hello world").starts_with("hello").and_.ends_with("world")
    expect("hello world").matches(r"\w+")
    expect("hello world").matches(r"o", occurrences=twice)
    expect("hello").is_lower().and_.is_not_empty()
    expect("name_1").is_identifier()
    expect("b7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c").is_uuid()


@pytest.mark.usefixtures("no_options_lookup")
def test_the_options_trap_actually_detonates() -> None:
    """A rule nobody can fail is not a rule: a *failing* assertion does read them."""
    with pytest.raises(AssertionError, match="belongs to the failure path"):
        expect("hello").is_empty()


# ---------------------------------------------------------------------------
# The regex assertions compile once per pattern
# ---------------------------------------------------------------------------
def test_a_pattern_is_compiled_once_and_then_looked_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``re.search(pattern, subject)`` compiles through ``re``'s cache every call.

    That is a lookup, a lock and a function call before the match begins, and it
    is paid on the branch where the assertion *passes* -- roughly twice the cost
    of a lookup in this module's own table followed by ``matcher.search``.

    Counted on the compile step, so removing the table turns this red rather than
    leaving it green and slower.
    """
    regexes: dict[object, object] = getattr(_text, "_REGEXES")  # noqa: B009
    regexes.clear()
    compilations = [0]
    original = getattr(_text, "_compile_regex")  # noqa: B009

    def counted(pattern: object, /) -> object:
        compilations[0] += 1
        return original(pattern)

    monkeypatch.setattr(_text, "_compile_regex", counted)
    subject = expect("hello world")
    for _ in range(50):
        subject.matches("wor")
    assert compilations[0] == 1, f"compiled {compilations[0]} times for one pattern"
    regexes.clear()


def test_a_compiled_pattern_is_accepted_and_pooled() -> None:
    """``re.compile`` hands a compiled pattern straight back, so both spellings pool."""
    regexes: dict[object, object] = getattr(_text, "_REGEXES")  # noqa: B009
    regexes.clear()
    pattern = re.compile("wor")
    expect("hello world").matches(pattern)
    expect("hello world").does_not_match(re.compile("zzz"))
    assert pattern in regexes
    regexes.clear()


def test_the_pattern_table_is_bounded() -> None:
    """A suite that builds a pattern per case must not pin one compiled regex each."""
    regexes: dict[object, object] = getattr(_text, "_REGEXES")  # noqa: B009
    bound: int = getattr(_text, "_MAX_MATCHERS")  # noqa: B009
    regexes.clear()
    for index in range(bound + 10):
        expect("hello world").matches("hello" + "|zz" + str(index))
        assert len(regexes) <= bound
    regexes.clear()


# ---------------------------------------------------------------------------
# The explainers are total: each ends in a clause, never in `None`
# ---------------------------------------------------------------------------
#: Strings that put the character-class explainers as close to their fallback as
#: the public API can get them: the title-case digraph that is neither upper nor
#: lower, cased letters with no case mapping, a cased combining mark, numerics
#: that are not digits, and the empty string every class but two rejects.
_AWKWARD: Final = (
    "",
    "ǅ",
    "Ǆ",
    "ǆ",
    "aǅ",
    "ǅa",
    "Aǅ",
    "ǅǅ",
    "ª",
    "1ª",
    "ℾ",
    "ℾ1",
    "ß",
    "ẞ",
    "µ",
    "ͅ",
    "Ⅷ",
    "½",
    "٣",
    "_1",
    "1st",
    "my-var",
    "123",
    "  ",
)


def test_no_character_class_failure_falls_through_to_the_totality_clause() -> None:
    """The comment on ``_class_fault``'s last line, turned into something checkable.

    ``str.isalpha`` and its siblings decide per character, and ``_stays_upper``
    and ``_stays_lower`` mirror the per-character half of ``str.isupper`` and
    ``str.islower`` -- so a non-empty string that failed one of them has a
    character that failed it, and the explainer always finds that character. The
    day one of those mirrors drifts, the message stops naming a character and
    starts saying ``but was '...'``, which is the assertion repeated back at the
    reader. This is the tripwire for exactly that.
    """
    checks: Final[tuple[tuple[str, Callable[[str], object]], ...]] = (
        ("is_upper", lambda text: expect(text).is_upper()),
        ("is_lower", lambda text: expect(text).is_lower()),
        ("is_title", lambda text: expect(text).is_title()),
        ("is_alpha", lambda text: expect(text).is_alpha()),
        ("is_digit", lambda text: expect(text).is_digit()),
        ("is_numeric", lambda text: expect(text).is_numeric()),
        ("is_alnum", lambda text: expect(text).is_alnum()),
        ("is_ascii", lambda text: expect(text).is_ascii()),
        ("is_printable", lambda text: expect(text).is_printable()),
        ("is_space", lambda text: expect(text).is_space()),
        ("is_identifier", lambda text: expect(text).is_identifier()),
    )

    fell_through: list[str] = []
    failures = 0
    for text in _AWKWARD:
        for name, check in checks:
            try:
                check(text)
            except AssertionFailure as failure:
                failures += 1
                if ", but was " in str(failure):
                    fell_through.append(f"{name}({text!r}): {failure}")

    assert failures > len(_AWKWARD), "the corpus has to actually fail these assertions"
    assert not fell_through, (
        f"these failures named no offending character and fell through to the "
        f"totality clause instead: {fell_through}"
    )


def test_class_fault_still_answers_when_no_character_is_at_fault() -> None:
    """``_class_fault`` ends in a clause even for a predicate that accuses nobody.

    Unreachable for a genuine character class, which is why the branch is there:
    a caller that passes some other predicate gets a sentence rather than
    ``None`` spliced into the middle of a failure message.
    """
    class_fault: Callable[[str, Callable[[str], bool]], str] = getattr(  # noqa: B009
        _string, "_class_fault"
    )

    clause = class_fault("abc", lambda _char: True)

    assert clause == "was 'abc'"


def test_title_fault_still_answers_when_the_walk_finds_no_fault() -> None:
    """``_title_fault`` ends in a clause when handed a string that *is* title case."""
    title_fault: Callable[[str], str] = getattr(_string, "_title_fault")  # noqa: B009

    clause = title_fault("Hello World")

    assert clause == "was 'Hello World'"


def test_identifier_fault_still_answers_when_every_character_is_valid() -> None:
    """``_identifier_fault`` ends in a clause when handed a valid identifier.

    ``str.isidentifier`` decomposes exactly the way this explainer takes it
    apart -- the first character against ``XID_Start``, every character against
    ``XID_Continue`` -- so ``is_identifier`` never asks about a string that
    passes both halves. The clause is the guard against a future caller that
    does.
    """
    identifier_fault: Callable[[str], str] = getattr(_string, "_identifier_fault")  # noqa: B009

    clause = identifier_fault("name_1")

    assert clause == "was 'name_1'"


def test_uuid_fault_still_answers_when_the_body_is_thirty_two_hexadecimal_digits() -> None:
    """``_uuid_fault`` ends in a clause when neither of its two checks has anything to say.

    ``is_uuid`` asks only when the body is the wrong length or holds a
    non-hexadecimal character, so this pair never reaches it. Asked anyway, the
    answer is a sentence about the subject rather than ``None``.
    """
    uuid_fault: Callable[[str, str], str] = getattr(_string, "_uuid_fault")  # noqa: B009

    clause = uuid_fault("b7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c", "b7f8b4d03a1e4f2b9c6a1d2e3f4a5b6c")

    assert clause == "'b7f8b4d0-3a1e-4f2b-9c6a-1d2e3f4a5b6c' could not be read as one"
