"""Continuations: ``.and_``, ``.which``, ``.subject``.

The property being tested is that chaining never *loses* type information. An
assertion returns ``Self``, so a chain on a ``StringExpect`` is still a
``StringExpect`` ten calls later -- including for a user's own subject class,
which is what makes the extension model worth anything.
"""

from collections.abc import Mapping, Sequence
from enum import Enum, StrEnum
from typing import Self, assert_type

from lovely_assertions import (
    BoolExpect,
    EnumExpect,
    Expect,
    Found,
    MappingExpect,
    NumericExpect,
    SequenceExpect,
    StringExpect,
    custom_assertion,
    expect,
)


class Colour(Enum):
    RED = 1


class Flavour(StrEnum):
    SWEET = "sweet"


# ---------------------------------------------------------------------------
# Self is preserved across chains
# ---------------------------------------------------------------------------
def chaining_keeps_the_subject(text: str, number: int, items: list[int]) -> None:
    assert_type(expect(text).is_equal_to("x"), StringExpect)
    assert_type(expect(text).is_equal_to("x").and_, StringExpect)
    assert_type(expect(text).is_equal_to("x").and_.is_not_equal_to("y"), StringExpect)
    assert_type(expect(number).is_not_equal_to(0).and_.is_same_as(1), NumericExpect)
    assert_type(expect(items).is_not_equal_to([]), SequenceExpect[int])


def subject_returns_the_value(
    text: str,
    flag: bool,
    items: list[int],
    rows: dict[str, int],
) -> None:
    assert_type(expect(text).subject, str)
    assert_type(expect(flag).subject, bool)
    # A sequence subject is an `Expect[Sequence[E]]`, so `.subject` comes back
    # as the ABC rather than the concrete `list`. That is the price of one
    # `SequenceExpect` covering every sequence; the element type is what matters.
    assert_type(expect(items).subject, Sequence[int])
    assert_type(expect(rows).subject, Mapping[str, int])
    assert_type(expect(flag).and_, BoolExpect)
    assert_type(expect(rows).is_not_equal_to({}), MappingExpect[str, int])


# ---------------------------------------------------------------------------
# Found: `.and_` back to the subject, `.which` into the value
# ---------------------------------------------------------------------------
def found_offers_both_directions(payload: object) -> None:
    found = expect(payload).is_instance_of(int)
    assert_type(found, Found[Expect[object], int])
    assert_type(found.and_, Expect[object])
    assert_type(found.which, Expect[int])
    assert_type(found.subject, int)


def found_keeps_the_concrete_subject_on_the_way_back(text: str) -> None:
    """``.and_`` must return the specialised subject, not the base class."""
    assert_type(expect(text).is_instance_of(str).and_, StringExpect)
    assert_type(expect(text).is_instance_of(str).and_.is_equal_to("x"), StringExpect)


def found_chains_onwards(payload: object) -> None:
    assert_type(expect(payload).is_instance_of(int).which.is_equal_to(3), Expect[int])
    assert_type(expect(payload).is_instance_of(int).which.subject, int)


# ---------------------------------------------------------------------------
# Narrowing hands back the subject `expect()` really builds
# ---------------------------------------------------------------------------
# These assert the object, not the declaration. `.as_type(str)` answering
# `Expect[str]` can be true of a signature and false of the value in hand --
# the runtime builds a `StringExpect` -- and a corpus that asserted the weaker
# type would agree with the wrong signature instead of catching it.
def as_type_hands_back_the_specialised_subject(raw: object) -> None:
    assert_type(expect(raw).as_type(str), StringExpect)
    assert_type(expect(raw).as_type(bool), BoolExpect)
    assert_type(expect(raw).as_type(Colour), EnumExpect[Colour])


def the_specialised_subject_offers_its_own_catalogue(raw: object) -> None:
    """The reason the declaration matters: without it, every one of these is an error."""
    assert_type(expect(raw).as_type(str).starts_with("he"), StringExpect)
    assert_type(expect(raw).as_type(bool).is_true(), BoolExpect)
    assert_type(expect(raw).as_type(str).starts_with("he").and_.has_length(5).subject, str)


def is_instance_of_carries_the_same_table(raw: object) -> None:
    assert_type(expect(raw).is_instance_of(str), Found[Expect[object], str, StringExpect])
    assert_type(expect(raw).is_instance_of(str).which, StringExpect)
    assert_type(expect(raw).is_instance_of(str).which.starts_with("he"), StringExpect)
    assert_type(expect(raw).is_instance_of(bool).which, BoolExpect)
    assert_type(expect(raw).is_instance_of(Colour).which, EnumExpect[Colour])
    # `.and_` and `.subject` are untouched by the third parameter.
    assert_type(expect(raw).is_instance_of(str).and_, Expect[object])
    assert_type(expect(raw).is_instance_of(str).subject, str)


def is_exactly_instance_of_carries_it_too(raw: object) -> None:
    assert_type(expect(raw).is_exactly_instance_of(str).which, StringExpect)
    assert_type(expect(raw).is_exactly_instance_of(bool).which, BoolExpect)
    assert_type(expect(raw).is_exactly_instance_of(Colour).which, EnumExpect[Colour])


def an_enum_class_beats_the_str_entry_that_would_also_match_it(raw: object) -> None:
    """A ``StrEnum`` subclass is a ``str`` subclass, so the order is load-bearing.

    If ``type[str]`` came first it would claim ``type[Flavour]`` and promise the
    string catalogue for an object the dispatch builds as an ``EnumExpect``. The
    ``Enum`` overload leads for the reason it leads in ``expect()``.
    """
    assert_type(expect(raw).as_type(Flavour), EnumExpect[Flavour])
    assert_type(expect(raw).is_instance_of(Flavour).which, EnumExpect[Flavour])


def there_is_no_int_entry_because_a_bool_is_an_int(raw: object, flag: bool) -> None:
    """``int`` stays unspecialised, deliberately -- see ``Expect.is_instance_of``.

    ``expect(True)`` builds a ``BoolExpect``, which is not a ``NumericExpect``, so
    a ``type[int]`` entry would be a declaration the object cannot honour. The
    widening to ``Expect[int]`` is sound whatever the value turns out to be.
    """
    assert_type(expect(raw).as_type(int), Expect[int])
    assert_type(expect(raw).is_instance_of(int).which, Expect[int])
    assert_type(expect(flag).is_instance_of(int).which, Expect[int])


def a_type_with_no_entry_falls_through_unchanged(raw: object) -> None:
    """The bare overload still answers for everything the table does not name."""
    assert_type(expect(raw).as_type(Exception), Expect[Exception])
    assert_type(expect(raw).is_instance_of(Exception).which, Expect[Exception])


def found_keeps_its_two_parameter_spelling(found: Found[StringExpect, int]) -> None:
    """``A`` has a default, so a two-parameter ``Found[P, V]`` still names the plain form."""
    assert_type(found.which, Expect[int])
    assert_type(found.whose_value, Expect[int])
    assert_type(found.subject, int)
    assert_type(found.and_, StringExpect)


def found_can_be_spelled_with_all_three(found: Found[StringExpect, str, StringExpect]) -> None:
    """And a producer that knows the subject says so in the third parameter."""
    assert_type(found.which, StringExpect)
    assert_type(found.whose_value, StringExpect)
    assert_type(found.whose_value.starts_with("a"), StringExpect)


# ---------------------------------------------------------------------------
# Extension subjects get the same treatment
# ---------------------------------------------------------------------------
class AccountExpect(Expect[int]):
    __slots__ = ()

    @custom_assertion
    def is_solvent(self, *, because: str = "") -> Self:
        if self._subject >= 0:
            return self
        return self._fail(f"to be solvent, but was {self._subject}", because)


def custom_assertion_is_signature_transparent(balance: int) -> None:
    """The decorator must not erase the signature or the ``Self`` return."""
    subject = AccountExpect(balance)
    assert_type(subject.is_solvent(), AccountExpect)
    assert_type(subject.is_solvent(because="regulatory"), AccountExpect)
    assert_type(subject.is_solvent().and_.is_solvent(), AccountExpect)
    assert_type(subject.is_solvent().subject, int)


def inherited_assertions_return_the_subclass(balance: int) -> None:
    assert_type(AccountExpect(balance).is_equal_to(1), AccountExpect)
    assert_type(AccountExpect(balance).is_equal_to(1).and_.is_solvent(), AccountExpect)


def is_not_none_widens_rather_than_relabels(balance: int) -> None:
    """A narrowing assertion returns ``Expect[S]``, never a guess at the subject.

    Re-specialising this to ``NumericExpect`` would be a lie: the object really is
    an ``AccountExpect``, and ``AccountExpect`` is not a ``NumericExpect``.
    ``Expect[int]`` is its supertype, so the widening is sound. Narrow first,
    then assert -- do not narrow *in order to* assert.
    """
    assert_type(AccountExpect(balance).is_not_none(), Expect[int])
    assert_type(AccountExpect(balance).is_not_none().subject, int)
