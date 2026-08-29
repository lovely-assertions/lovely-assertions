"""``EnumExpect``: the enumeration catalogue and the one rule behind it.

The rule -- an enum member is an enum before it is anything else -- is what makes
this suite worth reading. ``IntEnum`` members really are integers and ``StrEnum``
members really are strings, so every assertion below has to keep working when the
subject is also something else, and the messages have to name the *member* rather
than the integer or the string it is made of. ``str(Level.LOW)`` is merely
``"1"``, so a message built on it would name neither the enumeration nor the
member.

Two more things are pinned here because Python's own answers are not obvious and
a reader will otherwise assume the opposite:

* an **alias** is a second spelling of one member, not a second member, so
  ``Colour.CRIMSON.name`` is ``"RED"`` and ``has_name("CRIMSON")`` fails;
* the **empty flag** ``Perm(0)`` is a subset of every member and has none of them
  as a subset, so ``has_flag(Perm(0))`` always passes and
  ``expect(Perm(0)).has_flag(anything)`` never does.

``is_defined`` is absent on purpose; the last section says why in the form of a
test, so the reasoning cannot rot silently.
"""

import enum
import subprocess
import sys
import threading
from enum import Enum, EnumType, Flag, IntEnum, IntFlag, StrEnum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest

from lovely_assertions import (
    AssertionFailure,
    EnumExpect,
    NumericExpect,
    StringExpect,
    expect,
    soft_assertions,
)
from lovely_assertions._enum import rendered

if TYPE_CHECKING:
    from collections.abc import Callable


class Colour(Enum):
    """Two names for one value: ``CRIMSON`` is an alias, not a member."""

    RED = 1
    CRIMSON = 1  # noqa: PIE796  (the duplicate value *is* the alias this suite pins)
    GREEN = 2


class Signal(Enum):
    """A different enumeration sharing a name and a value with ``Colour``."""

    GREEN = 1
    AMBER = "amber"


class Counted(Enum):
    """``auto()`` numbers from one, and nothing about that is special here."""

    FIRST = auto()
    SECOND = auto()


class Level(IntEnum):
    """An integer that is an enum first."""

    LOW = 1
    HIGH = 9


class Size(StrEnum):
    """A string that is an enum first."""

    SMALL = "small"
    LARGE = "large"


class Perm(Flag):
    """The flag enumeration every flag test uses."""

    R = auto()
    W = auto()
    X = auto()


class Bits(IntFlag):
    """A second flag enumeration, for the cross-enumeration refusal."""

    A = 1
    B = 2


class Weird(Enum):
    """Values that are not scalars. An enum value may be anything hashable-ish."""

    POINT = (1, 2)
    MAPPING = {"a": 1}  # noqa: RUF012  (an unhashable enum value is the point)
    NOTHING = None


class Inner(Enum):
    X = 1


class Outer(Enum):
    """A member whose value is a member of another enumeration."""

    NESTED = Inner.X


class Mode(Enum):
    """A NaN value, which is not equal to itself and so matches nothing."""

    UNKNOWN = float("nan")


class Holder(Enum):
    """``enum.member`` and ``enum.nonmember`` decide what is a member at all."""

    A = 1
    real = enum.member(3)
    helper = enum.nonmember(4)


class Loud(Enum):
    """A member that lies about itself through ``__str__`` and ``__repr__``."""

    A = 1

    def __str__(self) -> str:
        return "LOUD"

    def __repr__(self) -> str:
        return "!!!"


class Long(Enum):
    """A value too long to print in full, to prove the clipping is inherited."""

    TEXT = "x" * 300


class Huge(IntEnum):
    """A value CPython refuses to convert to text at all."""

    ONE = 10**5000


class Broken(Enum):
    """A member whose ``__repr__`` raises, which the renderer must survive."""

    A = 1

    def __repr__(self) -> str:
        message = "this repr is broken on purpose"
        raise RuntimeError(message)


EMPTY: Final = Perm(0)


def _untyped(member: Enum, /) -> EnumExpect[Any]:
    """The subject an *untyped* caller has -- the only one that reaches the guards.

    ``has_flag`` types its operand ``T``, the subject's own enumeration, so every
    caller-bug test below would otherwise be a line the checkers refuse to let
    the suite contain. ``EnumExpect[Any]`` is what a dynamically typed test has,
    and the guards exist for exactly that reader.
    """
    return expect(member, as_=EnumExpect[Any])


class Shouty:
    """A scoped formatter, to prove the enum messages reach the registry."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, Colour)

    def format(self, value: object, /) -> str:
        return "<<colour>>"


# ---------------------------------------------------------------------------
# The one rule: an enum member is an enum before it is anything else
# ---------------------------------------------------------------------------
def test_a_plain_member_gets_the_enum_subject() -> None:
    assert isinstance(expect(Colour.RED), EnumExpect)


def test_an_int_enum_member_is_an_enum_and_not_a_number() -> None:
    """``Level.LOW`` is an ``int``; the rule says that does not decide the subject."""
    subject = expect(Level.LOW)
    assert isinstance(subject, EnumExpect)
    assert not isinstance(subject, NumericExpect)


def test_a_str_enum_member_is_an_enum_and_not_a_string() -> None:
    subject = expect(Size.SMALL)
    assert isinstance(subject, EnumExpect)
    assert not isinstance(subject, StringExpect)


def test_the_mixin_catalogue_is_one_move_away() -> None:
    """The rule costs nothing that ``.value`` does not give straight back."""
    assert isinstance(expect(Level.LOW.value), NumericExpect)
    assert isinstance(expect(Size.SMALL.value), StringExpect)


def test_the_generic_catalogue_is_still_there() -> None:
    """``is_equal_to`` and ``is_one_of`` come from the generic subject, unchanged."""
    subject = expect(Colour.RED)
    assert subject.is_equal_to(Colour.RED) is subject
    assert subject.is_one_of(Colour.RED, Colour.GREEN) is subject
    assert subject.is_not_equal_to(Colour.GREEN) is subject
    assert subject.is_in(list(Colour)) is subject


# ---------------------------------------------------------------------------
# `rendered`: a message names the member, never its repr
# ---------------------------------------------------------------------------
def test_a_member_renders_as_the_reader_wrote_it() -> None:
    assert rendered(Colour.RED) == "Colour.RED"


def test_a_mixin_member_renders_as_a_member_too() -> None:
    """``str(Level.LOW)`` is ``'1'`` and ``str(Size.SMALL)`` is ``'small'``."""
    assert rendered(Level.LOW) == "Level.LOW"
    assert rendered(Size.SMALL) == "Size.SMALL"


def test_a_custom_repr_does_not_get_to_speak() -> None:
    """``Loud`` renders as ``Loud.A``, not as ``!!!`` and not as ``LOUD``."""
    assert rendered(Loud.A) == "Loud.A"


def test_a_composite_flag_renders_by_its_compound_name() -> None:
    assert rendered(Perm.R | Perm.W) == "Perm.R|W"


def test_the_empty_flag_renders_as_the_call_that_builds_it() -> None:
    """``repr(Perm(0))`` is ``<Perm: 0>``; that is exactly what must not appear."""
    assert rendered(EMPTY) == "Perm(0)"
    assert rendered(Bits(0)) == "Bits(0)"


def test_a_non_member_falls_through_to_the_ordered_renderer() -> None:
    assert rendered(1) == "1"
    assert rendered("a") == "'a'"
    assert rendered(None) == "None"


def test_a_long_value_is_clipped_by_the_renderer_it_delegates_to() -> None:
    """The 302 is the ``repr``: the two quotes count, as they do everywhere else."""
    text = rendered(Long.TEXT.value)
    assert text.startswith("'xxx")
    assert text.endswith("... (truncated from 302 characters)")


def test_a_long_value_is_clipped_in_the_message_too() -> None:
    long_one = Long.TEXT
    with pytest.raises(AssertionFailure) as caught:
        expect(long_one).has_value("short")
    message = str(caught.value)
    assert message.startswith("Expected long_one to have value 'short', but Long.TEXT has value ")
    assert message.endswith("... (truncated from 302 characters).")


def test_an_object_whose_name_is_none_is_not_mistaken_for_a_flag() -> None:
    """A ``name`` of ``None`` alone does not make a member, nor a ``_value_`` beside it."""

    class Anonymous:
        name = None
        _value_ = 7

        def __repr__(self) -> str:
            return "<anonymous>"

    assert rendered(Anonymous()) == "<anonymous>"


def test_an_object_that_merely_has_a_name_is_not_a_member_either() -> None:
    """A duck test on ``.name`` invents an enumeration that does not exist.

    ``has_value`` types its operand ``object``, so ordinary objects reach the
    renderer -- and plenty of them carry a string ``.name``. A thread rendered
    as a member reads ``_MainThread.MainThread``, which names a class nobody
    wrote and a member nobody defined.
    """
    assert rendered(threading.current_thread()) == repr(threading.current_thread())

    class Named:
        name = "widget"

        def __repr__(self) -> str:
            return "<a widget>"

    assert rendered(Named()) == "<a widget>"
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).has_value(Named())
    assert str(caught.value) == (
        "Expected colour to have value <a widget>, but Colour.RED has value 1."
    )


def test_an_unprintable_operand_still_gets_a_verdict() -> None:
    """The delegation has to happen *before* the member test, not after.

    CPython refuses to convert an integer of more than
    ``sys.get_int_max_str_digits()`` digits to text. Asking such an operand
    whether it looked member-shaped means asking it for a ``repr``, and the
    failing assertion would then raise ``ValueError`` about string conversion
    instead of reporting the verdict it already had.
    """
    enormous = 10**5000
    assert rendered(enormous) == "<integer of about 5001 digits>"
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).has_value(enormous)
    assert str(caught.value) == (
        "Expected colour to have value <integer of about 5001 digits>, but Colour.RED has value 1."
    )


def test_a_member_that_cannot_print_itself_is_still_named() -> None:
    """``repr`` is a method like any other, and the message does not depend on it."""
    assert rendered(Broken.A) == "Broken.A"
    assert rendered(Huge.ONE) == "Huge.ONE"
    broken = Broken.A
    with pytest.raises(AssertionFailure) as caught:
        expect(broken).has_name("B")
    assert str(caught.value) == "Expected broken to be named 'B', but Broken.A is named 'A'."


def test_a_formatted_non_member_is_still_clipped() -> None:
    """Clipping belongs to the renderer a non-member is delegated to, formatter or not.

    A formatter can return anything, length included, and the operand of
    ``has_value`` is whatever the caller had. Asking the registry here and
    returning its answer straight would let an unbounded rendering into the
    message and skip the budget the ordered renderer applies.
    """

    class Wordy:
        __slots__ = ()

        def can_handle(self, value: object, /) -> bool:
            return isinstance(value, Verbose)

        def format(self, value: object, /) -> str:
            return "y" * 300

    class Verbose:
        __slots__ = ()

    with soft_assertions(formatters=(Wordy(),)) as scope:
        text = rendered(Verbose())
        scope.discard()
    assert text == "y" * 120 + "... (truncated from 300 characters)"


def test_a_registered_formatter_keeps_precedence() -> None:
    """The registry decides first; the member's own name is only the fallback."""
    with soft_assertions(formatters=(Shouty(),)) as scope:
        assert rendered(Colour.RED) == "<<colour>>"
        scope.discard()
    assert rendered(Colour.RED) == "Colour.RED"


def test_a_formatter_reaches_the_failure_message() -> None:
    with soft_assertions(formatters=(Shouty(),)) as scope:
        colour = Colour.RED
        expect(colour).has_name("GREEN")
        collected = scope.discard()
    assert collected == ["Expected colour to be named 'GREEN', but <<colour>> is named 'RED'."]


# ---------------------------------------------------------------------------
# has_name / does_not_have_name
# ---------------------------------------------------------------------------
def test_has_name_passes_and_chains() -> None:
    subject = expect(Colour.RED)
    assert subject.has_name("RED") is subject


def test_has_name_reports_the_name_it_found() -> None:
    colour = Colour.GREEN
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).has_name("RED")
    assert (
        str(caught.value) == "Expected colour to be named 'RED', but Colour.GREEN is named 'GREEN'."
    )


def test_has_name_is_case_sensitive() -> None:
    with pytest.raises(AssertionFailure):
        expect(Colour.RED).has_name("red")


def test_an_alias_answers_with_the_canonical_name() -> None:
    """The trap: ``Colour.CRIMSON`` *is* ``Colour.RED``, so it is named ``'RED'``.

    The annotation is not decoration. Both checkers give a member the literal
    type ``Literal[Colour.CRIMSON]``, and an identity check against
    ``Literal[Colour.RED]`` is one they consider impossible -- pyright narrows
    the expression to ``Never`` and mypy calls it non-overlapping. Widening to
    ``Colour`` says the thing being tested: the alias is a *runtime* fact the
    type system models as two distinct literals.
    """
    crimson: Colour = Colour.CRIMSON
    assert crimson is Colour.RED
    assert expect(crimson).has_name("RED") is not None
    with pytest.raises(AssertionFailure) as caught:
        expect(crimson).has_name("CRIMSON")
    assert str(caught.value) == (
        "Expected crimson to be named 'CRIMSON', but Colour.RED is named 'RED'."
    )


def test_does_not_have_name_passes_and_chains() -> None:
    subject = expect(Colour.RED)
    assert subject.does_not_have_name("GREEN") is subject


def test_does_not_have_name_reports_the_match() -> None:
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).does_not_have_name("RED")
    assert str(caught.value) == "Expected colour not to be named 'RED', but Colour.RED is."


def test_the_two_name_assertions_are_exact_complements() -> None:
    for member in Colour:
        for name in ("RED", "GREEN", "CRIMSON", ""):
            passes = member.name == name
            subject = expect(member)
            if passes:
                assert subject.has_name(name) is subject
                with pytest.raises(AssertionFailure):
                    subject.does_not_have_name(name)
            else:
                assert subject.does_not_have_name(name) is subject
                with pytest.raises(AssertionFailure):
                    subject.has_name(name)


def test_an_alias_passes_does_not_have_name_for_its_own_spelling() -> None:
    subject = expect(Colour.CRIMSON)
    assert subject.does_not_have_name("CRIMSON") is subject


def test_the_empty_flag_has_no_name_at_all() -> None:
    """``Perm(0).name`` is ``None``, and the message says so rather than guessing."""
    perms = EMPTY
    with pytest.raises(AssertionFailure) as caught:
        expect(perms).has_name("R")
    assert str(caught.value) == "Expected perms to be named 'R', but Perm(0) is named None."


def test_a_composite_flag_is_named_after_its_parts() -> None:
    subject = expect(Perm.R | Perm.W)
    assert subject.has_name("R|W") is subject


# ---------------------------------------------------------------------------
# has_same_name_as
# ---------------------------------------------------------------------------
def test_has_same_name_as_bridges_two_enumerations() -> None:
    """The reason the operand is any ``Enum`` and not the subject's own class."""
    subject = expect(Colour.GREEN)
    assert subject.has_same_name_as(Signal.GREEN) is subject


def test_has_same_name_as_reports_both_names() -> None:
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).has_same_name_as(Signal.GREEN)
    assert str(caught.value) == (
        "Expected colour to have the same name as Signal.GREEN,"
        " but was named 'RED' rather than 'GREEN'."
    )


def test_a_member_has_the_same_name_as_itself() -> None:
    subject = expect(Colour.RED)
    assert subject.has_same_name_as(Colour.RED) is subject


def test_an_alias_has_the_same_name_as_what_it_aliases() -> None:
    subject = expect(Colour.CRIMSON)
    assert subject.has_same_name_as(Colour.RED) is subject


def test_two_nameless_members_have_the_same_name_as_each_other() -> None:
    """Pinned rather than chosen: the empty flag's ``name`` is ``None`` on both sides.

    ``None == None``, so the assertion passes for a pair of members neither of
    which has a name. It is vacuous in the same way ``has_flag(Perm(0))`` is, and
    it is here so that a reader meeting it knows it was seen.
    """
    subject = expect(EMPTY)
    assert subject.has_same_name_as(Bits(0)) is subject


def test_has_same_name_as_ignores_the_values_entirely() -> None:
    """``Colour.GREEN`` is 2 and ``Signal.GREEN`` is 1; the names are the claim."""
    colour_value: object = Colour.GREEN.value
    signal_value: object = Signal.GREEN.value
    assert colour_value != signal_value
    assert expect(Colour.GREEN).has_same_name_as(Signal.GREEN) is not None


# ---------------------------------------------------------------------------
# has_value / does_not_have_value
# ---------------------------------------------------------------------------
def test_has_value_passes_and_chains() -> None:
    subject = expect(Colour.RED)
    assert subject.has_value(1) is subject


def test_has_value_reports_the_value_it_found() -> None:
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).has_value(2)
    assert str(caught.value) == "Expected colour to have value 2, but Colour.RED has value 1."


def test_has_value_on_the_mixins_names_the_member_and_the_value() -> None:
    level = Level.LOW
    with pytest.raises(AssertionFailure) as caught:
        expect(level).has_value(9)
    assert str(caught.value) == "Expected level to have value 9, but Level.LOW has value 1."

    size = Size.SMALL
    with pytest.raises(AssertionFailure) as caught:
        expect(size).has_value("large")
    assert (
        str(caught.value)
        == "Expected size to have value 'large', but Size.SMALL has value 'small'."
    )


def test_an_auto_value_is_an_ordinary_integer() -> None:
    subject = expect(Counted.SECOND)
    assert subject.has_value(2) is subject


def test_a_tuple_value_is_compared_as_a_tuple() -> None:
    subject = expect(Weird.POINT)
    assert subject.has_value((1, 2)) is subject
    point = Weird.POINT
    with pytest.raises(AssertionFailure) as caught:
        expect(point).has_value((9, 9))
    assert (
        str(caught.value)
        == "Expected point to have value (9, 9), but Weird.POINT has value (1, 2)."
    )


def test_an_unhashable_value_is_compared_all_the_same() -> None:
    """A ``dict`` value cannot go in a set, and ``==`` does not care."""
    subject = expect(Weird.MAPPING)
    assert subject.has_value({"a": 1}) is subject
    with pytest.raises(AssertionFailure):
        subject.has_value({"b": 2})


def test_a_none_value_is_a_value() -> None:
    subject = expect(Weird.NOTHING)
    assert subject.has_value(None) is subject
    assert subject.does_not_have_value(0) is subject


def test_a_nested_enum_value_renders_as_a_member() -> None:
    nested = Outer.NESTED
    assert expect(nested).has_value(Inner.X) is not None
    with pytest.raises(AssertionFailure) as caught:
        expect(nested).has_value(2)
    assert str(caught.value) == (
        "Expected nested to have value 2, but Outer.NESTED has value Inner.X."
    )


def test_a_nan_value_matches_nothing_and_the_message_says_why() -> None:
    """Not a misfire: ``nan != nan``, so no value assertion can ever match one."""
    mode = Mode.UNKNOWN
    with pytest.raises(AssertionFailure) as caught:
        expect(mode).has_value(float("nan"))
    assert str(caught.value) == (
        "Expected mode to have value nan, but Mode.UNKNOWN has value nan"
        " (a NaN is not equal to itself, so no value can match one)."
    )


def test_a_nan_value_passes_the_negation_for_the_same_reason() -> None:
    subject = expect(Mode.UNKNOWN)
    assert subject.does_not_have_value(float("nan")) is subject
    assert subject.does_not_have_value(Mode.UNKNOWN.value) is subject


def test_does_not_have_value_passes_and_chains() -> None:
    subject = expect(Colour.RED)
    assert subject.does_not_have_value(2) is subject


def test_does_not_have_value_reports_the_match() -> None:
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).does_not_have_value(1)
    assert str(caught.value) == "Expected colour not to have value 1, but Colour.RED has it."


def test_the_two_value_assertions_are_exact_complements() -> None:
    for member in (Colour.RED, Colour.GREEN, Level.LOW, Size.SMALL, Weird.NOTHING):
        for candidate in (1, 2, "small", None, object()):
            subject = expect(member)
            if member.value == candidate:
                assert subject.has_value(candidate) is subject
                with pytest.raises(AssertionFailure):
                    subject.does_not_have_value(candidate)
            else:
                assert subject.does_not_have_value(candidate) is subject
                with pytest.raises(AssertionFailure):
                    subject.has_value(candidate)


def test_an_int_enum_value_equals_a_bare_integer() -> None:
    """``Level.LOW.value`` is ``1``; nothing about the enum changes that."""
    assert expect(Level.LOW).has_value(1) is not None
    assert (
        expect(Level.LOW).has_value(True) is not None
    )  # `True == 1`, and an enum value is compared with `==`


def test_enum_member_and_nonmember_decide_what_has_a_value() -> None:
    """``enum.member`` makes a member of a value the class would have skipped."""
    assert list(Holder) == [Holder.A, Holder.real]
    subject = expect(Holder.real)
    assert subject.has_name("real") is subject
    assert subject.has_value(3) is subject
    assert Holder.helper == 4  # a plain attribute, and so not a subject at all


# ---------------------------------------------------------------------------
# has_same_value_as
# ---------------------------------------------------------------------------
def test_has_same_value_as_passes_within_one_enumeration() -> None:
    subject = expect(Colour.RED)
    assert subject.has_same_value_as(Colour.CRIMSON) is subject


def test_two_unrelated_enumerations_sharing_a_value_do_have_the_same_value() -> None:
    """The decision: the assertion is named after the values, so values decide it."""
    subject = expect(Colour.RED)
    assert subject.has_same_value_as(Signal.GREEN) is subject


def test_and_they_are_still_not_equal() -> None:
    """The other half of the decision, so the pair cannot be mistaken for a bug."""
    red: Enum = Colour.RED
    green: Enum = Signal.GREEN
    assert red != green
    with pytest.raises(AssertionFailure):
        expect(Colour.RED).is_equal_to(Signal.GREEN)


def test_has_same_value_as_reports_both_values() -> None:
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).has_same_value_as(Signal.AMBER)
    assert str(caught.value) == (
        "Expected colour to have the same value as Signal.AMBER,"
        " but had value 1 rather than 'amber'."
    )


def test_has_same_value_as_reaches_across_the_mixins() -> None:
    """An ``IntEnum`` member and a plain member both holding 1 hold the same value."""
    subject = expect(Level.LOW)
    assert subject.has_same_value_as(Colour.RED) is subject


def test_a_member_has_the_same_value_as_itself_unless_it_is_a_nan() -> None:
    assert expect(Colour.RED).has_same_value_as(Colour.RED) is not None
    mode = Mode.UNKNOWN
    with pytest.raises(AssertionFailure) as caught:
        expect(mode).has_same_value_as(Mode.UNKNOWN)
    assert str(caught.value) == (
        "Expected mode to have the same value as Mode.UNKNOWN,"
        " but had value nan rather than nan"
        " (a NaN is not equal to itself, so no value can match one)."
    )


# ---------------------------------------------------------------------------
# has_flag / does_not_have_flag
# ---------------------------------------------------------------------------
def test_has_flag_passes_and_chains() -> None:
    subject = expect(Perm.R | Perm.W)
    assert subject.has_flag(Perm.R) is subject
    assert subject.has_flag(Perm.W) is subject


def test_has_flag_reports_the_member_it_was_given() -> None:
    perms = Perm.R | Perm.W
    with pytest.raises(AssertionFailure) as caught:
        expect(perms).has_flag(Perm.X)
    assert str(caught.value) == "Expected perms to have flag Perm.X, but was Perm.R|W."


def test_has_flag_is_subset_containment_not_equality() -> None:
    subject = expect(Perm.R | Perm.W)
    assert subject.has_flag(Perm.R | Perm.W) is subject


def test_a_composite_operand_is_all_or_nothing() -> None:
    perms = Perm.R
    with pytest.raises(AssertionFailure) as caught:
        expect(perms).has_flag(Perm.R | Perm.W)
    assert str(caught.value) == "Expected perms to have flag Perm.R|W, but was Perm.R."


def test_does_not_have_flag_passes_and_chains() -> None:
    subject = expect(Perm.R)
    assert subject.does_not_have_flag(Perm.W) is subject


def test_does_not_have_flag_reports_the_match() -> None:
    perms = Perm.R | Perm.W
    with pytest.raises(AssertionFailure) as caught:
        expect(perms).does_not_have_flag(Perm.R)
    assert str(caught.value) == "Expected perms not to have flag Perm.R, but Perm.R|W has it."


def test_does_not_have_flag_passes_on_a_partially_present_composite() -> None:
    """One missing bit is enough, which is what "not a subset" means."""
    subject = expect(Perm.R)
    assert subject.does_not_have_flag(Perm.R | Perm.W) is subject


def test_the_two_flag_assertions_are_exact_complements() -> None:
    members = (EMPTY, Perm.R, Perm.W, Perm.R | Perm.W, Perm.R | Perm.W | Perm.X)
    for subject_member in members:
        for operand in members:
            subject = expect(subject_member)
            if operand in subject_member:
                assert subject.has_flag(operand) is subject
                with pytest.raises(AssertionFailure):
                    subject.does_not_have_flag(operand)
            else:
                assert subject.does_not_have_flag(operand) is subject
                with pytest.raises(AssertionFailure):
                    subject.has_flag(operand)


def test_an_int_flag_works_the_same_way() -> None:
    subject = expect(Bits.A | Bits.B)
    assert subject.has_flag(Bits.A) is subject
    assert subject.has_flag(Bits.A | Bits.B) is subject
    bits = Bits.A
    with pytest.raises(AssertionFailure) as caught:
        expect(bits).has_flag(Bits.B)
    assert str(caught.value) == "Expected bits to have flag Bits.B, but was Bits.A."


# ---------------------------------------------------------------------------
# The empty flag, which behaves the opposite way round from most guesses
# ---------------------------------------------------------------------------
def test_every_member_has_the_empty_flag() -> None:
    """``Perm(0) in anything`` is true: the empty set is a subset of every set."""
    for member in (EMPTY, Perm.R, Perm.R | Perm.W):
        assert expect(member).has_flag(EMPTY) is not None


def test_the_empty_flag_has_nothing_but_itself() -> None:
    perms = EMPTY
    assert expect(perms).has_flag(EMPTY) is not None
    with pytest.raises(AssertionFailure) as caught:
        expect(perms).has_flag(Perm.R)
    assert str(caught.value) == "Expected perms to have flag Perm.R, but was Perm(0)."


def test_does_not_have_the_empty_flag_can_never_pass() -> None:
    perms = EMPTY
    with pytest.raises(AssertionFailure) as caught:
        expect(perms).does_not_have_flag(EMPTY)
    assert str(caught.value) == "Expected perms not to have flag Perm(0), but Perm(0) has it."


# ---------------------------------------------------------------------------
# Caller bugs: a `TypeError` rather than an assertion failure
# ---------------------------------------------------------------------------
def test_a_flag_assertion_on_a_plain_enum_says_so() -> None:
    """A plain member supports neither ``in`` nor ``&``; a silent ``False`` would lie."""
    with pytest.raises(TypeError) as caught:
        expect(Colour.RED).has_flag(Colour.GREEN)
    assert str(caught.value) == (
        "the flag assertions need enum.Flag members: Colour.RED is a Colour, which is not a Flag"
    )


def test_the_negation_refuses_a_plain_enum_too() -> None:
    """The dangerous half: a silent ``False`` here would make it pass."""
    with pytest.raises(TypeError):
        expect(Colour.RED).does_not_have_flag(Colour.GREEN)


def test_an_int_enum_is_not_a_flag_either() -> None:
    """``Level.LOW & Level.HIGH`` is a legal ``int``, and means nothing about flags."""
    with pytest.raises(TypeError) as caught:
        expect(Level.LOW).has_flag(Level.HIGH)
    assert str(caught.value) == (
        "the flag assertions need enum.Flag members: Level.LOW is a Level, which is not a Flag"
    )


def test_a_non_flag_operand_is_named_as_the_problem() -> None:
    """What an *untyped* caller gets when the operand is not a flag member.

    The operand is typed ``T``, so a typed caller cannot write this line at all;
    ``typing_tests/negative/enum_negative.py`` holds that half.
    """
    with pytest.raises(TypeError) as caught:
        _untyped(Perm.R).has_flag(Colour.RED)
    assert str(caught.value) == (
        "the flag assertions need enum.Flag members: Colour.RED is a Colour, which is not a Flag"
    )


def test_two_different_flag_enumerations_do_not_mix() -> None:
    """``Perm.R in Bits.A`` raises in Python too; this names both sides instead."""
    with pytest.raises(TypeError) as caught:
        _untyped(Perm.R).has_flag(Bits.A)
    assert str(caught.value) == (
        "a flag can only be looked for in its own enumeration:"
        " Bits.A is a Bits and Perm.R is a Perm"
    )


def test_the_subject_is_checked_before_the_operand() -> None:
    """Two wrong sides, one message, and it names the subject -- the reader's value."""
    with pytest.raises(TypeError) as caught:
        _untyped(Colour.RED).has_flag(Bits.A)
    assert str(caught.value) == (
        "the flag assertions need enum.Flag members: Colour.RED is a Colour, which is not a Flag"
    )


def test_a_caller_bug_is_not_collected_by_a_soft_scope() -> None:
    """A ``TypeError`` is a bug in the test, so it stops the test rather than piling up."""
    with pytest.raises(TypeError), soft_assertions():
        expect(Colour.RED).has_flag(Colour.GREEN)


# ---------------------------------------------------------------------------
# `because`, naming, chaining and soft scopes
# ---------------------------------------------------------------------------
def test_because_reaches_every_assertion() -> None:
    colour = Colour.RED
    with pytest.raises(AssertionFailure) as caught:
        expect(colour).has_name("GREEN", because="the traffic light is green")
    assert str(caught.value) == (
        "Expected colour to be named 'GREEN', but Colour.RED is named 'RED'"
        " because the traffic light is green."
    )


def test_because_is_keyword_only_everywhere() -> None:
    import inspect

    for name in (
        "has_name",
        "does_not_have_name",
        "has_same_name_as",
        "has_value",
        "does_not_have_value",
        "has_same_value_as",
        "has_flag",
        "does_not_have_flag",
    ):
        parameters = inspect.signature(getattr(EnumExpect, name)).parameters
        assert parameters["because"].kind is inspect.Parameter.KEYWORD_ONLY, name
        operands = [p for p in parameters.values() if p.name not in {"self", "because"}]
        assert all(p.kind is inspect.Parameter.POSITIONAL_ONLY for p in operands), name


def test_described_as_names_the_subject() -> None:
    with pytest.raises(AssertionFailure) as caught:
        expect(Colour.RED).described_as("the primary colour").has_name("GREEN")
    assert str(caught.value) == (
        "Expected the primary colour to be named 'GREEN', but Colour.RED is named 'RED'."
    )


def test_a_long_chain_stays_on_one_subject() -> None:
    subject = expect(Perm.R | Perm.W)
    assert (
        subject.has_flag(Perm.R)
        .and_.does_not_have_flag(Perm.X)
        .and_.has_name("R|W")
        .and_.has_value(3)
        .and_.does_not_have_value(0)
    ) is subject


def test_a_soft_scope_collects_every_enum_failure() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        colour = Colour.RED
        expect(colour).has_name("GREEN").and_.has_value(2).and_.does_not_have_name("RED")
    message = str(caught.value)
    assert "to be named 'GREEN'" in message
    assert "to have value 2" in message
    assert "not to be named 'RED'" in message


def test_the_subject_survives_the_chain() -> None:
    assert expect(Colour.RED).has_name("RED").subject is Colour.RED


def test_every_assertion_returns_the_same_subject() -> None:
    """Chaining is the API; one assertion returning something else would break it."""
    subject = expect(Perm.R)
    calls: tuple[Callable[[], object], ...] = (
        lambda: subject.has_name("R"),
        lambda: subject.does_not_have_name("W"),
        lambda: subject.has_same_name_as(Perm.R),
        lambda: subject.has_value(1),
        lambda: subject.does_not_have_value(2),
        lambda: subject.has_same_value_as(Perm.R),
        lambda: subject.has_flag(Perm.R),
        lambda: subject.does_not_have_flag(Perm.W),
    )
    for call in calls:
        assert call() is subject


# ---------------------------------------------------------------------------
# `is_defined` is absent, and the reason is a test rather than a comment
# ---------------------------------------------------------------------------
def test_an_enum_member_is_defined_by_construction() -> None:
    """The premise: Python has no undefined member for the assertion to be false about."""
    with pytest.raises(ValueError, match="99 is not a valid Colour"):
        Colour(99)


def test_the_catalogue_does_not_pretend_otherwise() -> None:
    assert not hasattr(EnumExpect, "is_defined")
    assert not hasattr(EnumExpect, "is_not_defined")


def test_the_question_is_asked_of_the_value_instead() -> None:
    """What a reader wanting ``is_defined`` actually has: a claim about the integer."""
    assert expect([member.value for member in Colour]).contains(1) is not None


# ---------------------------------------------------------------------------
# The two questions asked through `sys.modules` rather than through an import
# ---------------------------------------------------------------------------
#: The tree the subprocess probe below runs from, so it can put `src` on the path.
REPO_ROOT: Final = Path(__file__).resolve().parent.parent


def test_a_member_renders_by_repr_while_the_enum_module_is_unloaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no ``enum`` in ``sys.modules``, nothing can be shown to be a member.

    The probe is a ``sys.modules`` miss rather than an import, and the miss *is*
    the answer: the renderer falls through to the ordered one and prints the
    stdlib ``repr`` instead of the ``Colour.RED`` it would otherwise build.
    Deleting the entry is the only way to reach that inside a process that has
    already imported ``enum`` -- a suite about enumerations cannot help it -- and
    the condition a real program meets is pinned in the subprocess below.
    """
    monkeypatch.delitem(sys.modules, "enum")

    rendering = rendered(Colour.RED)

    assert rendering == "<Colour.RED: 1>"


def test_a_program_that_never_imported_enum_dispatches_without_importing_it() -> None:
    """The condition the ``sys.modules`` probe exists for, in a process that really has it.

    A program with no enumeration in it must not pay for ``enum``, the value it
    does hold must still reach the generic subject, and asking this module to
    render that value must not drag the import in through the back door.
    """
    probe = (
        "import sys;"
        "sys.path.insert(0, 'src');"
        "from lovely_assertions import expect;"
        "from lovely_assertions._enum import rendered;"
        "assert 'enum' not in sys.modules, 'the probe needs enum unloaded';"
        "Reading = type('Reading', (), {'__repr__': lambda self: 'Reading()'});"
        "print(type(expect(Reading())).__name__, rendered(Reading()), 'enum' in sys.modules)"
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-S", "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )

    assert result.stdout.split() == ["Expect", "Reading()", "False"]


# ---------------------------------------------------------------------------
# The flag guard's last line: identity is stricter than the `isinstance` below it
# ---------------------------------------------------------------------------
class LenientEnumType(EnumType):
    """A metaclass that counts any ``Flag`` member as one of its own.

    Python refuses to extend an enumeration that has members, so the subclass
    the guard allows for -- a member of a *subclass* of the subject's
    enumeration -- cannot be written down directly. Widening ``isinstance`` is
    how a metaclass reaches the same situation: the fast path's identity test
    says no and the guard's ``isinstance`` says yes, which is the only shape in
    which the last line of the guard is the one that answers.
    """

    def __instancecheck__(cls, instance: object) -> bool:
        return isinstance(instance, Flag)


class Wide(Flag, metaclass=LenientEnumType):
    """A flag enumeration that accepts any flag member as one of its own."""

    ALPHA = 1
    BETA = 2


def test_a_flag_the_subject_widened_to_is_answered_rather_than_refused() -> None:
    """Past the fast path and past all three refusals, the question still gets an answer."""
    granted = Wide.ALPHA | Wide.BETA

    with pytest.raises(AssertionFailure) as caught:
        _untyped(granted).does_not_have_flag(Perm.R)

    assert str(caught.value) == (
        "Expected the value not to have flag Perm.R, but Wide.ALPHA|BETA has it."
    )


def test_a_widened_flag_that_is_absent_fails_instead_of_raising() -> None:
    """The other verdict from the same line: answered ``False``, not refused."""
    granted = Wide.ALPHA

    with pytest.raises(AssertionFailure) as caught:
        _untyped(granted).has_flag(Perm.W)

    assert str(caught.value) == "Expected the value to have flag Perm.W, but was Wide.ALPHA."
