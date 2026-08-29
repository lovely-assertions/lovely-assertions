"""Every marked line here must be rejected by pyright and mypy.

Two kinds of thing are ruled out. The first is ordinary: an operand of the wrong
shape, a reason passed positionally, an assertion that does not exist.

The second is **the price of the one rule**, and it is the reason this file
matters. An enum member is an enum before it is anything else, so an ``IntEnum``
member does not get ``is_greater_than`` and a ``StrEnum`` member does not get
``starts_with``. That has to be a *checker* error rather than an
``AttributeError`` in somebody's failing test, and this corpus is what says so.
``enum_subject.py`` holds the other half: the same two members reaching
``has_name`` and ``has_value``, which is what the rule buys.
"""

from enum import Enum, Flag, IntEnum, IntFlag, StrEnum, auto
from typing import assert_type

from lovely_assertions import EnumExpect, NumericExpect, StringExpect, expect


class Colour(Enum):
    RED = 1
    GREEN = 2


class Level(IntEnum):
    LOW = 1
    HIGH = 9


class Size(StrEnum):
    SMALL = "small"


class Perm(Flag):
    R = auto()
    W = auto()


class Bits(IntFlag):
    A = 1


def the_int_enum_catalogue_is_the_enum_one(level: Level) -> None:
    """The cost of the rule, and it must be paid at check time, not at run time."""
    expect(level).is_positive()  # expect-error: an enum member, not a number
    expect(level).is_greater_than(Level.LOW)  # expect-error
    expect(level).is_between(Level.LOW, Level.HIGH)  # expect-error
    expect(level).is_zero()  # expect-error


def the_str_enum_catalogue_is_the_enum_one(size: Size) -> None:
    expect(size).starts_with("s")  # expect-error: an enum member, not a string
    expect(size).ends_with("l")  # expect-error
    expect(size).has_length(5)  # expect-error
    expect(size).is_lower()  # expect-error


def the_mixin_subjects_are_not_what_the_dispatch_answers(level: Level, size: Size) -> None:
    assert_type(expect(level), NumericExpect)  # expect-error: it is an `EnumExpect[Level]`
    assert_type(expect(size), StringExpect)  # expect-error: it is an `EnumExpect[Size]`


def the_subject_keeps_its_own_enumeration(colour: Colour, level: Level) -> None:
    """``T`` is the enumeration the caller wrote; ``Enum`` would be a widening."""
    assert_type(expect(colour).subject, Enum)  # expect-error: it is a `Colour`
    assert_type(expect(colour), EnumExpect[Enum])  # expect-error
    assert_type(expect(level).subject, int)  # expect-error: it is a `Level`


def a_name_is_a_string(colour: Colour) -> None:
    expect(colour).has_name(1)  # expect-error: a name is a `str`
    expect(colour).has_name(Colour.RED)  # expect-error: the member is not its own name
    expect(colour).has_name(None)  # expect-error
    expect(colour).does_not_have_name(1)  # expect-error


def a_name_comparison_needs_a_member(colour: Colour) -> None:
    """``has_same_name_as`` is deliberately cross-enumeration, and not cross-*type*."""
    expect(colour).has_same_name_as("RED")  # expect-error: a `str` has no `.name`
    expect(colour).has_same_name_as(1)  # expect-error
    expect(colour).has_same_value_as("red")  # expect-error
    expect(colour).has_same_value_as(None)  # expect-error


def a_flag_belongs_to_its_own_enumeration(perms: Perm, bits: Bits) -> None:
    """``Perm.R`` is not a bit of ``Bits``; the operand is typed ``T`` to say so."""
    expect(perms).has_flag(Bits.A)  # expect-error
    expect(bits).has_flag(Perm.R)  # expect-error
    expect(perms).does_not_have_flag(Bits.A)  # expect-error
    expect(perms).has_flag(1)  # expect-error: an `int` is not a `Perm`
    expect(perms).has_flag("R")  # expect-error


def a_flag_assertion_on_a_plain_enum_is_the_runtime_half(colour: Colour) -> None:
    """Deliberately **not** marked: this line typechecks and raises ``TypeError``.

    ``T`` is fixed to ``Colour`` by ``expect()``, so no signature on this method
    can also demand that ``Colour`` be a ``Flag``. The guard in ``_enum.py``
    catches it instead, and ``tests/test_enum.py`` pins the message.
    """
    expect(colour).has_flag(Colour.GREEN)
    expect(colour).does_not_have_flag(Colour.GREEN)


def because_is_keyword_only(colour: Colour, perms: Perm) -> None:
    expect(colour).has_name("RED", "a reason")  # expect-error: `because` is keyword-only
    expect(colour).has_value(1, "a reason")  # expect-error
    expect(colour).has_same_name_as(Colour.RED, "a reason")  # expect-error
    expect(perms).has_flag(Perm.R, "a reason")  # expect-error


def every_assertion_needs_its_operand(colour: Colour, perms: Perm) -> None:
    expect(colour).has_name()  # expect-error
    expect(colour).has_value()  # expect-error
    expect(colour).does_not_have_value()  # expect-error
    expect(colour).has_same_name_as()  # expect-error
    expect(perms).has_flag()  # expect-error
    expect(colour).has_name("RED", "GREEN")  # expect-error: one name, not two


def is_defined_does_not_exist(colour: Colour) -> None:
    """Python has no undefined member, so the assertion has no subject. See ``_enum.py``."""
    expect(colour).is_defined()  # expect-error
    expect(colour).is_not_defined()  # expect-error


def the_parameter_has_to_be_an_enumeration() -> None:
    EnumExpect(3)  # expect-error: an `int` is not an `Enum`
    EnumExpect("RED")  # expect-error
    EnumExpect(Colour)  # expect-error: the class is not one of its members
