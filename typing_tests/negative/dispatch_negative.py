"""Every marked line here must be rejected by pyright and mypy.

If ``expect()`` ever stopped discriminating, `typing_tests/positive/dispatch.py`
would still be green -- because everything would collapse to a permissive type
that satisfies any `assert_type`. This file is what rules that out.
"""

from typing import assert_type

from lovely_assertions import (
    BoolExpect,
    CallableExpect,
    Expect,
    MappingExpect,
    NumericExpect,
    SequenceExpect,
    StringExpect,
    expect,
)


def order_of_the_overloads(text: str, flag: bool, number: int) -> None:
    assert_type(expect(text), SequenceExpect[str])  # expect-error: str beats Sequence
    assert_type(expect(flag), NumericExpect)  # expect-error: bool beats int
    assert_type(expect(number), BoolExpect)  # expect-error
    assert_type(expect(text), Expect[str])  # expect-error: must be the specialised subject


def element_types_are_not_forgotten(items: list[int], rows: dict[str, int]) -> None:
    assert_type(expect(items), SequenceExpect[str])  # expect-error
    assert_type(expect(rows), MappingExpect[int, str])  # expect-error
    assert_type(expect(rows), SequenceExpect[str])  # expect-error


def subjects_only_carry_their_own_assertions(number: int, text: str) -> None:
    expect(number).has_length(1)  # expect-error: not a string subject
    expect(text).is_positive()  # expect-error: not a numeric subject


def optional_is_not_silently_specialised(maybe_text: str | None) -> None:
    assert_type(expect(maybe_text), StringExpect)  # expect-error


def callables_are_not_the_generic_subject() -> None:
    def parse(text: str, /) -> int:
        return int(text)

    assert_type(expect(parse), Expect[object])  # expect-error: callables get CallableExpect


def non_callables_do_not_get_the_exception_catalogue(number: int) -> None:
    expect(number).raises(ValueError)  # expect-error: raises is not on a numeric subject
    assert_type(expect(number), CallableExpect)  # expect-error


def a_name_is_keyword_only_and_a_string(text: str) -> None:
    expect(text, "text")  # expect-error: `name=` cannot be passed positionally
    expect(text, name=3)  # expect-error: a subject's name is a string


def a_name_does_not_change_the_subject(flag: bool, rows: dict[str, int]) -> None:
    """Every overload declares ``name=``, so passing one cannot re-dispatch."""
    assert_type(expect(flag, name="flag"), NumericExpect)  # expect-error: still a bool
    assert_type(expect(rows, name="rows"), Expect[dict[str, int]])  # expect-error
