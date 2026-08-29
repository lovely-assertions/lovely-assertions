"""``expect()`` must hand back the right subject, statically.

The overload order is contractual and the reason is subtyping: ``bool`` is an
``int``, and ``str`` is a ``Sequence[str]``. First match wins, so the narrow cases
come first. The runtime dispatch in ``_subjects.py`` mirrors this table exactly;
``tests/test_narrowing.py`` checks the runtime half against the same expectations.
"""

from collections.abc import Collection, Iterator, Mapping, Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum, IntEnum, IntFlag, StrEnum
from fractions import Fraction
from pathlib import Path, PurePath, PurePosixPath
from typing import assert_type

from lovely_assertions import (
    BoolExpect,
    CallableExpect,
    CollectionExpect,
    DateExpect,
    DateTimeExpect,
    EnumExpect,
    Expect,
    MappingExpect,
    NumericExpect,
    OrderedExpect,
    PathExpect,
    PurePathExpect,
    SequenceExpect,
    StringExpect,
    TimeDeltaExpect,
    TimeExpect,
    TypeExpect,
    expect,
)


class Colour(Enum):
    RED = 1


class Level(IntEnum):
    LOW = 1


class Tag(StrEnum):
    A = "a"


class Permission(IntFlag):
    READ = 1


def literals() -> None:
    assert_type(expect("x"), StringExpect)
    assert_type(expect([1]), SequenceExpect[int])
    assert_type(expect({"a": 1}), MappingExpect[str, int])
    assert_type(expect(3), NumericExpect)
    assert_type(expect(3.5), NumericExpect)
    assert_type(expect(True), BoolExpect)
    assert_type(expect(object()), Expect[object])
    assert_type(expect(None), Expect[None])


def declared(
    text: str,
    number: int,
    real: float,
    flag: bool,
    items: list[int],
    pairs: tuple[str, ...],
    rows: dict[str, int],
) -> None:
    """Declared types, not just literals: inference must not depend on the syntax."""
    assert_type(expect(text), StringExpect)
    assert_type(expect(number), NumericExpect)
    assert_type(expect(real), NumericExpect)
    assert_type(expect(flag), BoolExpect)
    assert_type(expect(items), SequenceExpect[int])
    assert_type(expect(pairs), SequenceExpect[str])
    assert_type(expect(rows), MappingExpect[str, int])


def abstract(
    sequence: Sequence[bytes],
    mapping: Mapping[int, str],
    collection: Collection[bytes],
) -> None:
    """The ABCs, not only the concrete built-ins."""
    assert_type(expect(sequence), SequenceExpect[bytes])
    assert_type(expect(mapping), MappingExpect[int, str])
    assert_type(expect(collection), CollectionExpect[bytes])


def collections(tags: set[str], frozen: frozenset[int], rows: dict[str, int]) -> None:
    """The unordered half of the table, seen statically as well as at runtime.

    Sets, frozensets and the three dict views all land on ``CollectionExpect``,
    and every one of them has to be asserted here: ``tests/test_narrowing.py``
    covers the runtime half, and a row checked on only one side is exactly where
    the two halves drift apart.

    The views are the interesting rows. They have no name in ``builtins`` and the
    runtime reaches them through :data:`~lovely_assertions._subjects._VIEW_SOURCE`
    rather than through the ``issubclass`` chain, so a checker that disagreed here
    would disagree about the three fastest paths in the dispatch.
    """
    assert_type(expect(tags), CollectionExpect[str])
    assert_type(expect(frozen), CollectionExpect[int])
    assert_type(expect(rows.keys()), CollectionExpect[str])
    assert_type(expect(rows.values()), CollectionExpect[int])
    assert_type(expect(rows.items()), CollectionExpect[tuple[str, int]])


def nested() -> None:
    assert_type(expect([[1], [2]]), SequenceExpect[list[int]])
    assert_type(expect({"a": [1]}), MappingExpect[str, list[int]])
    assert_type(expect([{"a": 1}]), SequenceExpect[dict[str, int]])


def falls_back_rather_than_guessing(anything: object) -> None:
    """Anything without a dedicated subject still gets the generic one."""

    class Opaque:
        __slots__ = ()

    assert_type(expect(Opaque()), Expect[Opaque])
    assert_type(expect(anything), Expect[object])


def the_other_ordered_numbers(price: Decimal, ratio: Fraction) -> None:
    """``Decimal`` and ``Fraction`` keep their own type on ``.subject``.

    They are ordered but are not ``int | float``, so they reach the ordering half
    of the numeric family rather than the whole of it -- NaN and infinity belong
    to the built-in numbers, comparisons and ranges to anything comparable.
    """
    assert_type(expect(price), OrderedExpect[Decimal])
    assert_type(expect(ratio), OrderedExpect[Fraction])
    assert_type(expect(price).subject, Decimal)
    assert_type(expect(price).is_greater_than(Decimal(1)), OrderedExpect[Decimal])


def optional_does_not_get_expanded(maybe_text: str | None) -> None:
    """A union argument must resolve to the fallback, not split across overloads.

    If pyright expanded the union it would return ``StringExpect | Expect[None]``,
    and every narrowing chain built on ``expect(optional)`` would collapse.
    """
    assert_type(expect(maybe_text), Expect[str | None])


def custom_subclasses_dispatch_to_their_base(text: str) -> None:
    class Slug(str):
        __slots__ = ()

    assert_type(expect(Slug(text)), StringExpect)


# ---------------------------------------------------------------------------
# Callables are subjects too
# ---------------------------------------------------------------------------
def parse(text: str, /) -> int:
    return int(text)


def callables_reach_the_exception_subject() -> None:
    assert_type(expect(parse), CallableExpect)
    assert_type(expect(lambda: parse("1")), CallableExpect)
    # A class is callable, so it reaches this family too -- but as a `TypeExpect`,
    # which says it is a class rather than only that it can be called. Nothing is
    # given up for that: `TypeExpect` extends `CallableExpect`, so
    # `expect(SomeClass).raises(...)` stays available, and a constructor that must
    # reject bad arguments is a real assertion.
    assert_type(expect(ValueError), TypeExpect)
    assert_type(expect(int), TypeExpect)


def a_non_callable_object_does_not() -> None:
    assert_type(expect(object()), Expect[object])


# ---------------------------------------------------------------------------
# Types from modules the library refuses to import
#
# `_subjects._LAZY_SUBJECTS` is the runtime half of this block, and the two are
# checked against the same expectations. Subclass before superclass throughout:
# `datetime` is a `date` and `Path` is a `PurePath`, so each pair only resolves
# correctly in one order.
# ---------------------------------------------------------------------------
def dates_get_their_own_vocabulary() -> None:
    assert_type(expect(datetime(2020, 1, 1)), DateTimeExpect)
    assert_type(expect(date(2020, 1, 1)), DateExpect[date])
    assert_type(expect(time(9, 30)), TimeExpect)
    assert_type(expect(timedelta(days=1)), TimeDeltaExpect)


def a_date_subclass_keeps_its_own_type() -> None:
    """The reason `DateExpect` is generic: `.subject` must not widen to `date`."""

    class BillingDate(date):
        __slots__ = ()

    assert_type(expect(BillingDate(2020, 1, 1)), DateExpect[BillingDate])
    assert_type(expect(BillingDate(2020, 1, 1)).subject, BillingDate)


def paths_split_by_whether_they_can_touch_a_disk() -> None:
    assert_type(expect(Path("/etc/hosts")), PathExpect)
    assert_type(expect(PurePosixPath("/a")), PurePathExpect[PurePosixPath])


def a_declared_pure_path_stays_pure(pure: PurePath) -> None:
    assert_type(expect(pure), PurePathExpect[PurePath])


def an_enum_member_is_an_enum_before_it_is_anything_else() -> None:
    """The one rule, pinned. The last three really are an `int` and a `str`."""
    assert_type(expect(Colour.RED), EnumExpect[Colour])
    assert_type(expect(Level.LOW), EnumExpect[Level])
    assert_type(expect(Tag.A), EnumExpect[Tag])
    assert_type(expect(Permission.READ), EnumExpect[Permission])


def an_enum_class_is_a_class(colour_type: type[Colour]) -> None:
    """An enum class is a class, not the collection its metaclass makes of it.

    An `Enum` class is a `Collection` through `EnumMeta`, so the `type[Any]`
    overload has to lead the `Collection` one. Below it, this infers
    `CollectionExpect` while the runtime builds a `TypeExpect`.
    """
    assert_type(expect(Colour), TypeExpect)
    assert_type(expect(colour_type), TypeExpect)


# ---------------------------------------------------------------------------
# `name=` is on every overload, so it cannot change which subject is built
#
# The runtime half is in `tests/test_narrowing.py`, which walks the exact-type
# table and compares the two calls entry by entry. A checker that promised
# `BoolExpect` here while `expect(flag, name=...)` built a `NumericExpect` would
# hand a user a green type check and an `AttributeError`.
# ---------------------------------------------------------------------------
def a_name_leaves_the_subject_alone(
    flag: bool,
    text: str,
    number: int,
    real: float,
    rows: dict[str, int],
    items: list[int],
    tags: set[str],
    price: Decimal,
    when: datetime,
    where: Path,
    colour: Colour,
    anything: object,
) -> None:
    assert_type(expect(flag, name="flag"), BoolExpect)
    assert_type(expect(text, name="text"), StringExpect)
    assert_type(expect(number, name="number"), NumericExpect)
    assert_type(expect(real, name="real"), NumericExpect)
    assert_type(expect(rows, name="rows"), MappingExpect[str, int])
    assert_type(expect(items, name="items"), SequenceExpect[int])
    assert_type(expect(tags, name="tags"), CollectionExpect[str])
    assert_type(expect(price, name="price"), OrderedExpect[Decimal])
    assert_type(expect(when, name="when"), DateTimeExpect)
    assert_type(expect(where, name="where"), PathExpect)
    assert_type(expect(colour, name="colour"), EnumExpect[Colour])
    assert_type(expect(parse, name="parse"), CallableExpect)
    assert_type(expect(int, name="int"), TypeExpect)
    assert_type(expect(anything, name="anything"), Expect[object])


def a_name_composes_with_an_explicit_subject(colour: Colour) -> None:
    """``name=`` is applied after the subject is built, so ``as_=`` still decides."""
    assert_type(expect(colour, as_=EnumExpect[Colour], name="colour"), EnumExpect[Colour])


# ---------------------------------------------------------------------------
# The one shape the overload order and the runtime chain could differ on
# ---------------------------------------------------------------------------
class Duration(int, Mapping[str, int]):
    """An integer that is also a mapping, which `ABCMeta` allows.

    Every overload above `Mapping` claims such a class, so the runtime chain has
    to ask about `str` and `int | float` before `Mapping` or the two halves part
    company on it.
    """

    __slots__ = ()

    def __getitem__(self, key: str) -> int:
        return 0

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0


def a_number_that_is_also_a_mapping_stays_a_number(span: Duration) -> None:
    assert_type(expect(span), NumericExpect)
