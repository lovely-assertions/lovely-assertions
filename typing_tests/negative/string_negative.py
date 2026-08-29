"""Every marked line here must be rejected by pyright and mypy.

Without this half, ``typing_tests/positive/string.py`` proves nothing: a subject
whose assertions all returned ``Any`` would satisfy every ``assert_type`` in it.
These are the mistakes that must not compile -- a subject that quietly widened to
the base class, an argument of the wrong type, and above all a ``matches`` whose
overloads are permissive enough to accept anything at all.

``is_uuid`` gets its own half. It is the only assertion here that finds a value,
so it is the only one that can lie about *what* it found: a ``.which`` typed
``Expect[str]`` would hand the caller back the very string the assertion exists
to convert away from.
"""

import re
from typing import assert_type
from uuid import UUID

from lovely_assertions import Expect, Found, StringExpect, expect


def by_number(value: int) -> bool:
    return value > 0


def by_text(value: str) -> bool:
    return value.startswith("v")


def the_subject_is_not_the_base_class(text: str) -> None:
    assert_type(expect(text).is_empty(), Expect[str])  # expect-error: it is StringExpect
    assert_type(expect(text).matches("x"), Expect[str])  # expect-error


def the_subject_type_is_not_forgotten(text: str) -> None:
    assert_type(expect(text).is_not_empty().subject, int)  # expect-error: `str`
    assert_type(expect(text).is_upper(), StringExpect[str])  # expect-error: not generic


def arguments_are_strings(text: str) -> None:
    expect(text).has_length("3")  # expect-error: a length is an int
    expect(text).contains(3)  # expect-error
    expect(text).contains_all("a", 2)  # expect-error
    expect(text).starts_with(b"a")  # expect-error: bytes are not a prefix of a str


def because_is_keyword_only(text: str) -> None:
    expect(text).is_empty("a reason")  # expect-error: `because` is keyword-only
    expect(text).contains("x", "a reason")  # expect-error


def the_equivalence_options_are_keyword_only(text: str) -> None:
    expect(text).is_equal_ignoring_case("x", True)  # expect-error


def the_equivalence_options_are_booleans(text: str) -> None:
    expect(text).is_equal_ignoring_case("x", ignoring_whitespace="yes")  # expect-error


def the_case_assertions_take_no_operand(text: str) -> None:
    expect(text).is_upper(True)  # expect-error
    expect(text).is_title(True)  # expect-error


def the_character_classes_take_no_operand(text: str) -> None:
    """Nine predicates about the subject alone; an argument means a misremembered API."""
    expect(text).is_alpha(True)  # expect-error
    expect(text).is_digit("0-9")  # expect-error
    expect(text).is_ascii(strict=True)  # expect-error
    expect(text).is_identifier(text)  # expect-error


def the_character_classes_keep_because_keyword_only(text: str) -> None:
    expect(text).is_alnum("a reason")  # expect-error: `because` is keyword-only
    expect(text).is_printable(because=1)  # expect-error: a reason is prose


def matches_accepts_a_pattern_or_a_predicate_and_nothing_else(
    text: str, binary: re.Pattern[bytes]
) -> None:
    expect(text).matches(3)  # expect-error: neither a regex nor a predicate
    expect(text).matches(by_number)  # expect-error: a predicate over the wrong type
    expect(text).matches(binary)  # expect-error: a bytes pattern cannot search a str


def a_predicate_must_answer_with_a_bool(text: str) -> None:
    """``Callable[[str], bool]``, not ``Callable[[str], object]``: a truthy return is not a test."""
    expect(text).matches(lambda value: value.upper())  # expect-error


def a_wildcard_is_not_a_regex_object(text: str, compiled: re.Pattern[str]) -> None:
    """The wildcard family takes its own little syntax, as text."""
    expect(text).matches_wildcard(compiled)  # expect-error
    expect(text).does_not_match_wildcard_ignoring_case(compiled)  # expect-error


def does_not_match_has_no_predicate_form(text: str) -> None:
    """Only ``matches`` carries the inherited predicate overload."""
    expect(text).does_not_match(by_text)  # expect-error


def only_is_uuid_returns_a_found(text: str) -> None:
    """``contains`` returns ``Self`` and must keep doing so: chains depend on it."""
    expect(text).contains("x").which  # expect-error
    expect(text).is_alpha().which  # expect-error


def is_uuid_takes_its_version_by_keyword(text: str) -> None:
    expect(text).is_uuid(4)  # expect-error: `version` is keyword-only
    expect(text).is_uuid(version="4")  # expect-error: a version is an int
    expect(text).is_uuid(version=4.0)  # expect-error: a version is an int, not a float
    expect(text).is_uuid(version=4, because=1)  # expect-error: a reason is prose


def the_found_value_is_a_uuid_and_not_the_string_it_came_from(text: str) -> None:
    """The whole point of the assertion: what it hands back is a ``UUID``, not text."""
    assert_type(expect(text).is_uuid(), Found[StringExpect, str])  # expect-error
    assert_type(expect(text).is_uuid().subject, str)  # expect-error
    assert_type(expect(text).is_uuid().which, Expect[str])  # expect-error


def a_found_is_not_the_subject_it_was_found_on(text: str) -> None:
    """``is_uuid`` breaks the chain on purpose; ``.and_`` is how you resume it."""
    assert_type(expect(text).is_uuid(), StringExpect)  # expect-error
    expect(text).is_uuid().is_not_empty()  # expect-error
    assert_type(expect(text).is_uuid().and_, Expect[UUID])  # expect-error
