"""Runtime side of narrowing and the continuations.

The static side lives in ``typing_tests/`` and is checked by pyright and mypy.
Both halves are needed: a runtime pass says nothing about what a checker infers,
and a checker says nothing about what the object actually is.

The claim these tests defend is that the two agree, and specifically that the
static type is never *narrower* than the object. ``is_not_none()`` is declared to
return ``Expect[S]``; at runtime it hands back whatever ``expect()`` already built
from the value, which for a string really is a ``StringExpect``. Declared type
wider than the real one is sound. The other way round would be a lie that only
surfaces as an ``AttributeError`` in a user's test.
"""

from collections import Counter, deque
from collections.abc import Iterator, Mapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum, IntEnum, IntFlag, StrEnum
from fractions import Fraction
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from lovely_assertions import (
    AssertionFailure,
    BoolExpect,
    CollectionExpect,
    DateExpect,
    DateTimeExpect,
    EnumExpect,
    Expect,
    MappingExpect,
    MockExpect,
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
    soft_assertions,
)
from lovely_assertions._subjects import (
    _EXACT_SUBJECTS,  # pyright: ignore[reportPrivateUsage]
)


class Colour(Enum):
    """A plain enumeration: its members are nothing but members."""

    RED = 1


class Level(IntEnum):
    """Its members *are* integers, which is what makes the dispatch order matter."""

    LOW = 1


class Tag(StrEnum):
    """Its members *are* strings, likewise."""

    A = "a"


class Permission(IntFlag):
    """Combinable, and still an enum before it is an integer."""

    READ = 1
    WRITE = 2


@pytest.mark.parametrize(
    ("value", "expected_subject"),
    [
        (True, BoolExpect),
        (False, BoolExpect),
        ("x", StringExpect),
        (3, NumericExpect),
        (3.5, NumericExpect),
        ([1], SequenceExpect),
        ((1,), SequenceExpect),
        ({"a": 1}, MappingExpect),
        # Ordered but not `int | float`, so they get the ordering half of the
        # numeric family and keep their own type.
        (Decimal("1.5"), OrderedExpect),
        (Fraction(1, 3), OrderedExpect),
        # A length, an iterator and a membership test, but no order.
        ({1, 2}, CollectionExpect),
        (frozenset({1}), CollectionExpect),
        ({"a": 1}.keys(), CollectionExpect),
        ({"a": 1}.values(), CollectionExpect),
        ({"a": 1}.items(), CollectionExpect),
        # A sequence is a collection with more to offer, so it keeps the richer
        # subject rather than falling to the new one.
        (b"abc", SequenceExpect),
        (range(3), SequenceExpect),
        (deque([1]), SequenceExpect),
        # A mapping likewise: it is a collection of its keys, and its own subject
        # says more about it.
        (Counter("ab"), MappingExpect),
        # Neither has a length, so neither is a collection -- and nothing here
        # will consume a one-shot iterator behind the caller's back.
        (iter([1]), Expect),
        ((value for value in [1]), Expect),
        # A class is callable and has more to say about itself than that. An
        # `Enum` class is also a `Collection` through `EnumMeta`, which is why the
        # overload sits at the head of the static table and not below `Collection`:
        # below it, `expect(Colour)` infers `CollectionExpect` while the runtime
        # builds a `TypeExpect`.
        (int, TypeExpect),
        (ValueError, TypeExpect),
        (Colour, TypeExpect),
        # Dates are ordered and are not numbers, so they get their own vocabulary
        # rather than `is_greater_than`. `datetime` precedes `date` because it is
        # one.
        (datetime(2020, 1, 1), DateTimeExpect),
        (date(2020, 1, 1), DateExpect),
        (time(9, 30), TimeExpect),
        (timedelta(days=1), TimeDeltaExpect),
        # A path likewise, and `Path` precedes `PurePath` for the same reason.
        (Path("/etc/hosts"), PathExpect),
        (PurePosixPath("/a"), PurePathExpect),
        (PureWindowsPath("C:/a"), PurePathExpect),
        # An enum member is an enum before it is anything else. The last three
        # rows are the whole rule: their members really are an `int`, a `str` and
        # an `int`, and every one of them still gets the enum subject.
        (Colour.RED, EnumExpect),
        (Level.LOW, EnumExpect),
        (Tag.A, EnumExpect),
        (Permission.READ, EnumExpect),
        (None, Expect),
        (object(), Expect),
    ],
)
def test_runtime_dispatch_matches_the_static_overload_order(
    value: object, expected_subject: type[object]
) -> None:
    """Runtime dispatch and the static overloads are one table seen twice."""
    assert type(expect(value)) is expected_subject


def test_dispatch_handles_subclasses_of_builtins() -> None:
    class Name(str):
        __slots__ = ()

    class Row(dict[str, int]):
        __slots__ = ()

    class Tags(frozenset[str]):
        __slots__ = ()

    class Money(Decimal):
        __slots__ = ()

    assert type(expect(Name("x"))) is StringExpect
    assert type(expect(Row())) is MappingExpect
    assert type(expect(Tags())) is CollectionExpect
    assert type(expect(Money("1.00"))) is OrderedExpect


# ---------------------------------------------------------------------------
# A name must not change which subject a value gets
# ---------------------------------------------------------------------------
# One instance per entry of the exact table, so the sweep below can walk the whole
# of it. Written out rather than derived, because dispatch is asked about a value
# and only a reader of the table knows what each key admits.
_EXACT_SAMPLES: dict[type[object], object] = {
    bool: True,
    str: "x",
    int: 3,
    float: 3.5,
    dict: {"a": 1},
    list: [1],
    tuple: (1,),
    type: int,
    set: {1},
    frozenset: frozenset({1}),
    type({"a": 1}.keys()): {"a": 1}.keys(),
    type({"a": 1}.values()): {"a": 1}.values(),
    type({"a": 1}.items()): {"a": 1}.items(),
}


def test_every_exact_dispatch_entry_has_a_sample_value() -> None:
    """A sweep that skipped a row would report coverage it does not have."""
    assert set(_EXACT_SAMPLES) == set(_EXACT_SUBJECTS)


@pytest.mark.parametrize(("subject_type", "value"), list(_EXACT_SAMPLES.items()))
def test_a_name_does_not_change_which_subject_is_built(
    subject_type: type[object], value: object
) -> None:
    """Every overload declares ``name=``, which is a claim on every row of this table."""
    named = expect(value, name="thing")

    assert type(named) is type(expect(value)), (
        f"expect({subject_type.__name__}, name=...) built {type(named).__name__}, "
        f"but expect({subject_type.__name__}) builds {type(expect(value)).__name__}"
    )


def test_a_named_bool_reaches_the_bool_catalogue() -> None:
    """The exact table is the only place ``bool`` is told apart from ``int``.

    The chain behind that table answers ``NumericExpect``, which has no
    ``is_true``: a green type check and an ``AttributeError`` in the test that
    believed it.
    """
    with pytest.raises(AssertionFailure) as caught:
        expect(False, name="flag").is_true()

    assert str(caught.value) == "Expected flag to be True, but was False."


def test_a_number_that_is_also_a_mapping_follows_the_overloads() -> None:
    """``Mapping`` carries ``ABCMeta``, so a class can inherit it and a built-in both.

    The overloads match ``int | float`` before ``Mapping`` and promise a
    ``NumericExpect``. A shape chain that asked about ``Mapping`` first would
    build a ``MappingExpect`` for the same value, and the catalogue the checker
    offered would not be there.
    """

    class Duration(int, Mapping[str, int]):
        __slots__ = ()

        def __getitem__(self, key: str) -> int:
            return 0

        def __iter__(self) -> Iterator[str]:
            return iter(())

        def __len__(self) -> int:
            return 0

    assert type(expect(Duration(5))) is NumericExpect


def test_the_new_subjects_carry_their_catalogues() -> None:
    """The dispatch table is only worth pinning if it hands over real assertions.

    Every row above can name the right class while every call through it raises
    ``AttributeError``. A set must be assertable empty and comparable as a set,
    and a ``Decimal`` must reach the ordering half of the numeric catalogue it is
    promised.
    """
    expect({1, 2}).is_not_empty().and_.has_length(2).and_.contains(1)
    expect({1, 2}).is_subset_of({1, 2, 3})
    expect({"a": 1}.keys()).contains("a")
    expect(Decimal("1.5")).is_positive().and_.is_greater_than(Decimal(1))
    # The bounds share the subject's type: `OrderedExpect[T]` takes `T`, so a
    # `datetime` cannot be asked whether it lies between two integers.
    expect(Fraction(1, 3)).is_between(Fraction(0), Fraction(1))


def test_subject_returns_the_wrapped_value() -> None:
    values = [1, 2]
    assert expect(values).subject is values


def test_and_returns_the_same_object() -> None:
    subject = expect(3)
    assert subject.and_ is subject


# ---------------------------------------------------------------------------
# is_not_none: the declared type must be the runtime type
# ---------------------------------------------------------------------------
def test_is_not_none_hands_back_the_typed_subject() -> None:
    maybe_text: str | None = "hello"
    assert type(expect(maybe_text).is_not_none()) is StringExpect

    maybe_items: list[int] | None = [1]
    assert type(expect(maybe_items).is_not_none()) is SequenceExpect

    maybe_rows: dict[str, int] | None = {"a": 1}
    assert type(expect(maybe_rows).is_not_none()) is MappingExpect


def test_is_not_none_returns_the_very_same_wrapper() -> None:
    """No re-dispatch is needed: ``expect()`` already typed it by its value."""
    subject = expect("hello")
    assert subject.is_not_none() is subject


def test_is_not_none_raises_on_none() -> None:
    maybe_text: str | None = None
    with pytest.raises(AssertionFailure):
        expect(maybe_text).is_not_none()


def test_is_none_passes_on_none() -> None:
    assert expect(None).is_none().subject is None


# ---------------------------------------------------------------------------
# is_instance_of and the `.which` continuation
# ---------------------------------------------------------------------------
def test_is_instance_of_offers_and_which_and_subject() -> None:
    payload: object = "hello"
    found = expect(payload).is_instance_of(str)
    assert found.subject == "hello"
    assert found.which.subject == "hello"


def test_and_returns_the_originating_subject() -> None:
    payload: object = "hello"
    subject = expect(payload)
    assert subject.is_instance_of(str).and_ is subject


def test_which_is_a_typed_subject() -> None:
    payload: object = "hello"
    assert type(expect(payload).is_instance_of(str).which) is StringExpect


def test_is_instance_of_accepts_subclasses() -> None:
    assert expect(True).is_instance_of(int).subject is True


def test_is_instance_of_rejects_the_wrong_type() -> None:
    payload: object = "hello"
    with pytest.raises(AssertionFailure):
        expect(payload).is_instance_of(int)


# ---------------------------------------------------------------------------
# Soft mode: a failed narrowing has no narrowed subject to offer
# ---------------------------------------------------------------------------
def test_a_failed_narrowing_in_a_soft_scope_absorbs_further_assertions() -> None:
    """One root cause, one message. A missing subject must not cascade."""
    with soft_assertions() as scope:
        maybe_text: str | None = None
        expect(maybe_text).is_not_none().is_equal_to("hello").is_equal_to("world")
        collected = scope.discard()
    assert collected == ["Expected maybe_text not to be None, but it was."]


def test_a_failed_is_instance_of_in_a_soft_scope_absorbs_further_assertions() -> None:
    with soft_assertions() as scope:
        payload: object = "hello"
        expect(payload).is_instance_of(int).which.is_equal_to(3)
        collected = scope.discard()
    assert len(collected) == 1
    assert "to be an instance of int" in collected[0]


def _missing_text() -> str | None:
    """Keeps the declared type optional; assigning ``None`` would narrow it away."""
    return None


def test_the_absorbing_subject_is_recognisable_if_it_ever_leaks() -> None:
    with soft_assertions() as scope:
        dead = expect(_missing_text()).is_not_none()
        scope.discard()
    assert "narrowing failed" in repr(dead)


# ---------------------------------------------------------------------------
# Mocks: the one place the two orders genuinely cannot be one table
# ---------------------------------------------------------------------------
def test_a_mock_dispatches_to_the_mock_subject_at_runtime() -> None:
    """And only at runtime — the static side is beyond reach, on purpose.

    typeshed gives ``NonCallableMock`` an ``Any`` in its MRO, so a mock is
    statically assignable to everything: ``b: bool = Mock()`` type-checks. No
    position in the overload list can reach it, because the first concrete
    overload always wins. The static answer for a mock is therefore meaningless
    whatever is written, so the runtime is left to be right on its own and
    ``expect(mock, as_=MockExpect)`` is the typed route.
    """
    from unittest.mock import AsyncMock, MagicMock, Mock, NonCallableMock, create_autospec

    for label, value in [
        ("Mock", Mock()),
        ("MagicMock", MagicMock()),
        ("AsyncMock", AsyncMock()),
        ("NonCallableMock", NonCallableMock()),
        ("create_autospec(fn)", create_autospec(len)),
    ]:
        assert type(expect(value)) is MockExpect, f"{label} did not reach MockExpect"


def test_not_implemented_is_the_other_value_assignable_to_everything() -> None:
    """A mock is not the only value a checker will accept anywhere.

    ``types.NotImplementedType`` is assignable to everything the way a mock is:
    ``b: bool = NotImplemented`` type-checks under pyright strict and mypy strict.
    So both checkers match the first concrete overload of ``expect()`` and answer
    ``TypeExpect``, while the runtime answers ``Expect`` -- which is the correct
    answer, because ``NotImplemented`` is not a class.

    Nothing is done about it. Nobody asserts on ``NotImplemented``; what would be
    wrong is to go on claiming a mock is the only such value, when a sweep of the
    exotic subjects through both checkers turns up a second one.
    """
    assert isinstance(NotImplemented, type) is False
    assert type(expect(NotImplemented)) is Expect


def test_things_that_only_look_like_mocks_are_not_claimed() -> None:
    """One familiar method is not a mock; the assertions would then fail obscurely."""
    from unittest.mock import call, sentinel

    class Spy:
        def assert_called_with(self, *args: object) -> None:
            """A hand-written double with one familiar name."""

    assert not isinstance(expect(Spy()), MockExpect)
    assert not isinstance(expect(call), MockExpect)
    assert not isinstance(expect(sentinel.thing), MockExpect)


def test_a_class_with_a_metaclass_still_reaches_the_type_subject() -> None:
    """The O(1) table is keyed on ``type(value)``, which is the *metaclass*.

    A plain class has ``type`` for its metaclass and hits the fast path. An ABC
    has ``ABCMeta``, an enum has ``EnumMeta``, and a Django model or a pydantic
    model has its own — every one of those misses the table and depends on the
    ``isinstance(value, type)` branch that follows it. Without this the branch is
    dead code as far as the suite can tell.
    """
    from abc import ABC, abstractmethod
    from enum import Enum

    class Shape(ABC):
        @abstractmethod
        def area(self) -> float: ...

    class Colour(Enum):
        RED = 1

    class Meta(type):
        pass

    class Custom(metaclass=Meta):
        pass

    assert type(Shape) is not type, "the fixture must not hit the exact-type table"
    for candidate in (Shape, Colour, Custom):
        assert type(expect(candidate)) is TypeExpect, f"{candidate} missed the type subject"


def test_a_class_keeps_the_callable_catalogue_it_had() -> None:
    """``TypeExpect`` extends ``CallableExpect``, so a class keeps both catalogues.

    A constructor that must reject bad arguments is a real assertion, and giving
    classes a subject of their own must not cost them the one they share with
    every other callable.
    """

    class Strict:
        def __init__(self) -> None:
            message = "always"
            raise ValueError(message)

    expect(Strict).raises(ValueError)
    expect(Strict).is_subclass_of(object)


def test_a_count_constraint_on_a_sequence_uses_the_collection_rule() -> None:
    """One counting rule, in one place: the sequence subject defers to the base.

    ``SequenceExpect`` overrides ``does_not_contain`` so it can report the index
    it found at; a count has nothing to do with position, so that case is handed
    back to the base rather than reimplemented. Two implementations of one rule
    is how they come to disagree.
    """
    from lovely_assertions import exactly

    votes = ["ada", "ada", "bob"]
    as_sequence = _message(lambda: expect(votes).does_not_contain("ada", occurrences=exactly(2)))
    unique: set[str] = set(votes)
    as_collection = _message(lambda: expect(unique).does_not_contain("ada", occurrences=exactly(1)))
    assert "exactly twice" in as_sequence
    assert "exactly once" in as_collection


def _message(callback: object) -> str:
    with pytest.raises(AssertionFailure) as caught:
        callback()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]
    return str(caught.value)
