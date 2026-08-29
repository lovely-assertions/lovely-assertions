"""The string subject's static surface.

Three claims are pinned here.

*Every assertion returns the subject itself.* ``Self``, not ``Expect[str]`` and
not ``StringExpect`` written out -- so a chain on a user's own subclass is still
that subclass at the end of it, which is what the extension model rests on.

*``matches`` accepts both meanings.* The generic catalogue gives it a predicate
and the string catalogue a regular expression, and the overloads here widen the
inherited parameter to cover both rather than replacing one with the other.

*``is_uuid`` is the one that finds a value.* Everything else in the catalogue
returns ``Self``; this one returns ``Found[Self, UUID]``, so ``.and_`` comes back
to the string and ``.which`` continues on a ``UUID`` -- the point of the
assertion, statically as well as at runtime.
"""

import re
from typing import Self, assert_type
from uuid import UUID

from lovely_assertions import Expect, Found, StringExpect, custom_assertion, expect


# ---------------------------------------------------------------------------
# Every assertion hands the string subject back
# ---------------------------------------------------------------------------
def emptiness_and_length(text: str) -> None:
    assert_type(expect(text).is_empty(), StringExpect)
    assert_type(expect(text).is_not_empty(), StringExpect)
    assert_type(expect(text).is_blank(), StringExpect)
    assert_type(expect(text).is_not_blank(), StringExpect)
    assert_type(expect(text).has_length(3), StringExpect)


def caseless_equality(text: str) -> None:
    assert_type(expect(text).is_equal_ignoring_case("x"), StringExpect)
    assert_type(expect(text).is_not_equal_ignoring_case("x"), StringExpect)
    assert_type(
        expect(text).is_equal_ignoring_case(
            "x", ignoring_whitespace=True, ignoring_newline_style=True
        ),
        StringExpect,
    )


def containment(text: str) -> None:
    assert_type(expect(text).contains("x"), StringExpect)
    assert_type(expect(text).does_not_contain("x"), StringExpect)
    assert_type(expect(text).contains_all("x", "y"), StringExpect)
    assert_type(expect(text).does_not_contain_all("x", "y"), StringExpect)
    assert_type(expect(text).contains_any("x", "y"), StringExpect)
    assert_type(expect(text).does_not_contain_any("x", "y"), StringExpect)
    assert_type(expect(text).contains_ignoring_case("x"), StringExpect)
    assert_type(expect(text).does_not_contain_ignoring_case("x"), StringExpect)


def edges(text: str) -> None:
    assert_type(expect(text).starts_with("x"), StringExpect)
    assert_type(expect(text).does_not_start_with("x"), StringExpect)
    assert_type(expect(text).starts_with_ignoring_case("x"), StringExpect)
    assert_type(expect(text).does_not_start_with_ignoring_case("x"), StringExpect)
    assert_type(expect(text).ends_with("x"), StringExpect)
    assert_type(expect(text).does_not_end_with("x"), StringExpect)
    assert_type(expect(text).ends_with_ignoring_case("x"), StringExpect)
    assert_type(expect(text).does_not_end_with_ignoring_case("x"), StringExpect)


def wildcards(text: str) -> None:
    assert_type(expect(text).matches_wildcard("x*"), StringExpect)
    assert_type(expect(text).does_not_match_wildcard("x*"), StringExpect)
    assert_type(expect(text).matches_wildcard_ignoring_case("x*"), StringExpect)
    assert_type(expect(text).does_not_match_wildcard_ignoring_case("x*"), StringExpect)


def case(text: str) -> None:
    assert_type(expect(text).is_upper(), StringExpect)
    assert_type(expect(text).is_not_upper(), StringExpect)
    assert_type(expect(text).is_lower(), StringExpect)
    assert_type(expect(text).is_not_lower(), StringExpect)
    assert_type(expect(text).is_title(), StringExpect)
    assert_type(expect(text).is_not_title(), StringExpect)


def character_classes(text: str) -> None:
    assert_type(expect(text).is_alpha(), StringExpect)
    assert_type(expect(text).is_not_alpha(), StringExpect)
    assert_type(expect(text).is_digit(), StringExpect)
    assert_type(expect(text).is_not_digit(), StringExpect)
    assert_type(expect(text).is_numeric(), StringExpect)
    assert_type(expect(text).is_not_numeric(), StringExpect)
    assert_type(expect(text).is_alnum(), StringExpect)
    assert_type(expect(text).is_not_alnum(), StringExpect)
    assert_type(expect(text).is_ascii(), StringExpect)
    assert_type(expect(text).is_not_ascii(), StringExpect)
    assert_type(expect(text).is_printable(), StringExpect)
    assert_type(expect(text).is_not_printable(), StringExpect)
    assert_type(expect(text).is_space(), StringExpect)
    assert_type(expect(text).is_not_space(), StringExpect)
    assert_type(expect(text).is_identifier(), StringExpect)
    assert_type(expect(text).is_not_identifier(), StringExpect)


def a_character_class_chains_like_everything_else(text: str) -> None:
    assert_type(expect(text).is_alpha().and_.is_not_digit().is_ascii(), StringExpect)


# ---------------------------------------------------------------------------
# is_uuid: the one assertion here that finds a value
# ---------------------------------------------------------------------------
def is_uuid_hands_back_a_found(text: str) -> None:
    assert_type(expect(text).is_uuid(), Found[StringExpect, UUID])
    assert_type(expect(text).is_uuid(version=4), Found[StringExpect, UUID])
    assert_type(expect(text).is_uuid(because="R"), Found[StringExpect, UUID])


def the_continuations_go_both_ways(text: str) -> None:
    assert_type(expect(text).is_uuid().subject, UUID)
    assert_type(expect(text).is_uuid().which, Expect[UUID])
    assert_type(expect(text).is_uuid().and_, StringExpect)
    assert_type(expect(text).is_uuid().and_.is_not_empty(), StringExpect)


def the_parsed_uuid_is_what_a_test_compares_against(text: str, known: UUID) -> None:
    """The point of the assertion: ``UUID(text) == text`` is ``False``."""
    identifier: UUID = expect(text).is_uuid(version=4).subject
    expect(text).is_uuid().which.is_equal_to(known)
    assert_type(identifier, UUID)


# ---------------------------------------------------------------------------
# matches: one name, both meanings
# ---------------------------------------------------------------------------
def is_short(value: str) -> bool:
    return len(value) < 3


def matches_resolves_all_three_argument_forms(text: str, compiled: re.Pattern[str]) -> None:
    assert_type(expect(text).matches("^v"), StringExpect)
    assert_type(expect(text).matches(compiled), StringExpect)
    assert_type(expect(text).matches(is_short), StringExpect)
    assert_type(expect(text).matches(lambda value: value.startswith("v")), StringExpect)


def a_lambda_parameter_is_inferred_as_str(text: str) -> None:
    """The predicate overload has to supply the parameter type, or the form is useless."""
    expect(text).matches(lambda value: value.casefold() == "x")


def does_not_match_is_regex_only(text: str, compiled: re.Pattern[str]) -> None:
    assert_type(expect(text).does_not_match("^v"), StringExpect)
    assert_type(expect(text).does_not_match(compiled), StringExpect)


# ---------------------------------------------------------------------------
# Chaining and continuations
# ---------------------------------------------------------------------------
def chaining_never_degrades_the_subject(text: str) -> None:
    assert_type(expect(text).is_not_empty().and_.contains("x"), StringExpect)
    assert_type(expect(text).starts_with("a").ends_with("z").matches("m"), StringExpect)
    assert_type(expect(text).is_not_empty().subject, str)
    assert_type(expect(text).is_equal_to("x").and_.is_upper(), StringExpect)


def the_generic_catalogue_is_still_available(text: str) -> None:
    """A string subject keeps everything the generic catalogue gave it."""
    assert_type(expect(text).is_one_of("a", "b"), StringExpect)
    assert_type(expect(text).satisfies(lambda value: expect(value).is_upper()), StringExpect)


def because_is_accepted_everywhere(text: str) -> None:
    assert_type(expect(text).is_empty(because="R"), StringExpect)
    assert_type(expect(text).contains("x", because="R"), StringExpect)
    assert_type(expect(text).contains_all("x", because="R"), StringExpect)
    assert_type(expect(text).matches("x", because="R"), StringExpect)
    assert_type(expect(text).matches(is_short, because="R"), StringExpect)


# ---------------------------------------------------------------------------
# Extension subjects inherit the whole surface
# ---------------------------------------------------------------------------
class SlugExpect(StringExpect):
    __slots__ = ()

    @custom_assertion
    def is_kebab_case(self, *, because: str = "") -> Self:
        if self._subject.islower() and " " not in self._subject:
            return self
        return self._fail(f"to be kebab-case, but was {self._subject!r}", because)


def a_subclass_stays_itself_across_the_inherited_catalogue(slug: str) -> None:
    subject = SlugExpect(slug)
    assert_type(subject.is_not_empty(), SlugExpect)
    assert_type(subject.contains("-").and_.is_kebab_case(), SlugExpect)
    assert_type(subject.matches("^[a-z-]+$").and_.is_kebab_case(), SlugExpect)
    assert_type(subject.matches(is_short).and_.is_kebab_case(), SlugExpect)
    assert_type(subject.is_kebab_case().subject, str)
    assert_type(subject.is_alpha().and_.is_kebab_case(), SlugExpect)
    assert_type(subject.is_uuid(), Found[SlugExpect, UUID])
    assert_type(subject.is_uuid().and_.is_kebab_case(), SlugExpect)
