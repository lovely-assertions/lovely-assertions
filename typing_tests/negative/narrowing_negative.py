"""Every marked line here must be rejected by pyright and mypy.

These are the failures that would mean the narrowing claim is hollow: a subject
that was never re-typed, or one that was re-typed to the wrong thing.
"""

from enum import Enum
from typing import assert_type

from lovely_assertions import BoolExpect, Expect, StringExpect, expect


class Colour(Enum):
    RED = 1


def not_narrowed_at_all(raw: str | None) -> str:
    return expect(raw).subject  # expect-error: still `str | None`


def narrowed_to_the_wrong_type(raw: str | None) -> int:
    return expect(raw).is_not_none().subject  # expect-error: `str` is not `int`


def none_is_not_stripped(raw: str | None) -> None:
    assert_type(expect(raw).is_not_none(), Expect[str | None])  # expect-error


def instance_of_narrows_to_its_argument(payload: object) -> str:
    return expect(payload).is_instance_of(int).subject  # expect-error: `int` is not `str`


def which_is_not_the_original_subject(payload: object) -> None:
    assert_type(expect(payload).is_instance_of(int).which, Expect[object])  # expect-error


def found_is_not_an_expect(payload: object) -> None:
    """`.which` or `.and_` is required; `Found` is not itself a subject."""
    expect(payload).is_instance_of(int).is_equal_to(3)  # expect-error


def because_is_keyword_only(number: int) -> None:
    expect(number).is_equal_to(1, "a reason")  # expect-error: `because` is keyword-only


def the_original_variable_stays_optional(raw: str | None) -> None:
    expect(raw).is_not_none()
    assert_type(raw, str)  # expect-error: a chain cannot re-type the caller's own variable


# ---------------------------------------------------------------------------
# The narrowing overloads specialise; they must not over-specialise
# ---------------------------------------------------------------------------
# A positive `assert_type` only ever checks the declaration, so it agrees with an
# overload table that promises too little and never notices the richer subject
# underneath. Each line here names a specialisation the table must NOT make, so
# that an entry cannot be added to it by accident.
def as_type_str_is_no_longer_the_generic_subject(raw: object) -> None:
    assert_type(expect(raw).as_type(str), Expect[str])  # expect-error: it is a StringExpect


def as_type_does_not_specialise_int(raw: object) -> None:
    """``bool`` is an ``int`` and gets a ``BoolExpect``; ``int`` must stay generic."""
    assert_type(expect(raw).as_type(int), Expect[int])
    expect(raw).as_type(int).is_positive()  # expect-error: NumericExpect is not promised


def as_type_does_not_specialise_an_arbitrary_class(raw: object) -> None:
    expect(raw).as_type(Exception).with_message("x")  # expect-error: no entry for Exception


def the_specialised_subject_is_not_interchangeable(raw: object) -> None:
    """``as_type(bool)`` is a ``BoolExpect``, and a ``BoolExpect`` is not a string."""
    subject: StringExpect = expect(raw).as_type(bool)  # expect-error
    _ = subject


def the_enum_entry_is_parameterised_by_the_class_it_was_given(raw: object) -> None:
    expect(raw).as_type(Colour).starts_with("R")  # expect-error: EnumExpect, not a string


def which_still_refuses_the_wrong_catalogue(raw: object) -> None:
    expect(raw).is_instance_of(str).which.is_true()  # expect-error: StringExpect, not bool


def found_is_still_not_a_subject(raw: object) -> None:
    """The third parameter does not make ``Found`` chainable in its own right."""
    expect(raw).is_instance_of(str).starts_with("a")  # expect-error: `.which` is required


def a_bool_subject_is_not_relabelled_by_narrowing_to_int(flag: bool) -> None:
    """The lie the missing ``int`` entry exists to refuse.

    At runtime ``.which`` here is a ``BoolExpect``. If ``type[int]`` ever gains a
    ``NumericExpect`` entry, this line starts type-checking and then raising, and
    the harness says so.
    """
    expect(flag).is_instance_of(int).which.is_positive()  # expect-error: AttributeError below


def the_third_parameter_is_not_free(raw: object) -> None:
    subject: BoolExpect = expect(raw).is_instance_of(str).which  # expect-error
    _ = subject
