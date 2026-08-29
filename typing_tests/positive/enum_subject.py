"""``EnumExpect[T]``: the enumeration subject, and the one rule made static.

An enum member is an enum before it is anything else, and that sentence is a
*typing* claim before it is a runtime one. Three properties carry it:

* ``T`` is the enumeration the caller wrote, not ``Enum``, so ``.subject`` comes
  back as a ``Colour`` and the chain never widens;
* an ``IntEnum`` member is an ``EnumExpect[Level]`` and **not** a
  ``NumericExpect``, and a ``StrEnum`` member is an ``EnumExpect[Size]`` and not
  a ``StringExpect``. Those two ``assert_type`` calls *are* the rule; the
  overload order in ``_subjects.py`` exists to make them hold, and
  ``enum_negative.py`` pins what they cost;
* the generic catalogue is inherited intact, so ``is_equal_to``, ``is_one_of``
  and ``matches`` still see the enumeration.

The flag operand is typed ``T`` rather than ``Flag``, which is what keeps
``Bits.A`` out of a ``Perm`` subject at check time. Being a ``Flag`` at all is
the half no signature can state -- ``T`` is fixed by whatever ``expect()`` was
handed -- and it is checked at runtime instead.
"""

from enum import Enum, Flag, IntEnum, IntFlag, StrEnum, auto
from typing import assert_type

from lovely_assertions import EnumExpect, expect


class Colour(Enum):
    RED = 1
    GREEN = 2


class Signal(Enum):
    GREEN = "go"


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


def the_dispatch_answers_the_enum_subject(colour: Colour) -> None:
    assert_type(expect(colour), EnumExpect[Colour])


def an_int_enum_member_is_an_enum_and_not_a_number(level: Level) -> None:
    """The one rule. ``Level.LOW`` is an ``int``, and this is the subject it gets."""
    assert_type(expect(level), EnumExpect[Level])
    assert_type(expect(level).has_name("LOW"), EnumExpect[Level])
    assert_type(expect(level).subject, Level)


def a_str_enum_member_is_an_enum_and_not_a_string(size: Size) -> None:
    assert_type(expect(size), EnumExpect[Size])
    assert_type(expect(size).has_value("small"), EnumExpect[Size])
    assert_type(expect(size).subject, Size)


def the_mixin_catalogue_is_one_move_away(level: Level, size: Size) -> None:
    """What the rule costs, and how it is paid: ask for the value by name."""
    assert_type(expect(level.value).is_positive().subject, int | float)
    assert_type(expect(size.value).starts_with("s").subject, str)


def chaining_keeps_the_parameterised_subject(colour: Colour) -> None:
    subject = expect(colour)
    assert_type(subject.has_name("RED"), EnumExpect[Colour])
    assert_type(subject.does_not_have_name("GREEN"), EnumExpect[Colour])
    assert_type(subject.has_same_name_as(Signal.GREEN), EnumExpect[Colour])
    assert_type(subject.has_value(1), EnumExpect[Colour])
    assert_type(subject.does_not_have_value(2), EnumExpect[Colour])
    assert_type(subject.has_same_value_as(Signal.GREEN), EnumExpect[Colour])
    assert_type(subject.has_name("RED").and_.has_value(1), EnumExpect[Colour])


def the_subject_keeps_its_own_enumeration(colour: Colour) -> None:
    """The point of the parameter: a ``Colour`` does not widen to ``Enum``."""
    assert_type(expect(colour).has_name("RED").subject, Colour)
    assert_type(expect(Colour.RED).subject, Colour)


def the_name_operand_bridges_two_enumerations(colour: Colour, signal: Signal) -> None:
    """``has_same_name_as`` and ``has_same_value_as`` take any member, on purpose."""
    assert_type(expect(colour).has_same_name_as(signal), EnumExpect[Colour])
    assert_type(expect(signal).has_same_value_as(colour), EnumExpect[Signal])


def the_value_operand_is_deliberately_untyped(colour: Colour) -> None:
    """``has_value`` takes ``object``: an enum value may be anything at all."""
    assert_type(expect(colour).has_value(1), EnumExpect[Colour])
    assert_type(expect(colour).has_value("red"), EnumExpect[Colour])
    assert_type(expect(colour).has_value(None), EnumExpect[Colour])
    assert_type(expect(colour).has_value((1, 2)), EnumExpect[Colour])
    assert_type(expect(colour).does_not_have_value(object()), EnumExpect[Colour])


def the_flag_assertions_take_the_subjects_own_enumeration(perms: Perm, bits: Bits) -> None:
    assert_type(expect(perms).has_flag(Perm.R), EnumExpect[Perm])
    assert_type(expect(perms).does_not_have_flag(Perm.W), EnumExpect[Perm])
    assert_type(expect(perms).has_flag(Perm.R | Perm.W), EnumExpect[Perm])
    assert_type(expect(bits).has_flag(Bits.A), EnumExpect[Bits])


def because_reaches_every_assertion(colour: Colour, perms: Perm) -> None:
    assert_type(expect(colour).has_name("RED", because="R"), EnumExpect[Colour])
    assert_type(expect(colour).does_not_have_name("GREEN", because="R"), EnumExpect[Colour])
    assert_type(expect(colour).has_same_name_as(Signal.GREEN, because="R"), EnumExpect[Colour])
    assert_type(expect(colour).has_value(1, because="R"), EnumExpect[Colour])
    assert_type(expect(colour).does_not_have_value(2, because="R"), EnumExpect[Colour])
    assert_type(expect(colour).has_same_value_as(Signal.GREEN, because="R"), EnumExpect[Colour])
    assert_type(expect(perms).has_flag(Perm.R, because="R"), EnumExpect[Perm])
    assert_type(expect(perms).does_not_have_flag(Perm.W, because="R"), EnumExpect[Perm])


def the_inherited_catalogue_still_sees_the_enumeration(colour: Colour, level: Level) -> None:
    """``EnumExpect[T]`` is an ``Expect[T]``, so ``matches`` gets a ``Colour``."""

    def is_warm(value: Colour) -> bool:
        return value is Colour.RED

    assert_type(expect(colour).matches(is_warm), EnumExpect[Colour])
    assert_type(expect(colour).is_equal_to(Colour.RED), EnumExpect[Colour])
    assert_type(expect(colour).is_one_of(Colour.RED, Colour.GREEN), EnumExpect[Colour])
    assert_type(expect(colour).is_in(list(Colour)), EnumExpect[Colour])
    assert_type(expect(level).is_one_of(Level.LOW, Level.HIGH), EnumExpect[Level])
    assert_type(expect(colour).described_as("the colour").has_name("RED"), EnumExpect[Colour])


def the_explicit_subject_form_is_typed(colour: Colour) -> None:
    """``as_=`` is the fully typed way to ask for a subject by name."""
    assert_type(expect(colour, as_=EnumExpect[Colour]), EnumExpect[Colour])
    assert_type(expect(colour, as_=EnumExpect[Colour]).has_name("RED"), EnumExpect[Colour])


def the_subject_is_constructible_directly(colour: Colour) -> None:
    assert_type(EnumExpect(colour), EnumExpect[Colour])
    assert_type(EnumExpect(colour).has_name("RED").subject, Colour)
