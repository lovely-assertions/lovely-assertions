"""The equivalence engine under attack: ``compare``.

This file is the flagship assertion's specification written as tests, and it was
written **against what the library promises rather than against the
implementation**. A suite written by reading the engine tests that the code does
what it does; this one tests that it does what it should. Everything here comes
from that promise, from the conventions ``_diff`` already set, and from the
three ordering traps -- each of which silently produces a wrong *pass*, which is
the only kind of bug an assertion library cannot afford.

Four properties get more attention than the rest, because each of them is a wrong
answer rather than a missing one:

*``""`` means equivalent.* The caller branches on emptiness, so a comparison that
cannot decide, cannot render, or cannot reach the difference must never come back
empty. Every "it degrades" test below therefore also asserts the block is *not*
empty: a degraded answer is a less detailed failure, never a pass.

*The three ordering traps.* A NamedTuple is a tuple, a ``str`` is a sequence, and
a dataclass has a ``__dict__``. Each is tested from both directions -- the case
that must fail and the case that must pass -- because getting one wrong turns
``Point(1, 2)`` against ``Point(2, 1)`` into a green test.

*It stays bounded.* A hundred differences must not print a hundred lines, and a
graph that is deep *and* wide must not print the product of the two. The bounds
are asserted in characters and lines, never as "something was returned".

*It never raises.* A property that explodes, a ``__eq__`` that throws, a cycle, a
``__contains__`` that lies: each costs the reader detail, never their test.

**Marking convention.** A docstring or comment opening with ``READING:`` pins
behaviour that is a judgement call rather than a fixed requirement. It is what I
believe is right and why; if the engine disagrees, that is a disagreement to
settle, not necessarily a bug. Every other assertion follows from what the library
promises.

**The one genuinely ambiguous spelling, flagged rather than quietly resolved.** An
identifier-like mapping key reads well printed as ``rows['id']`` and reads well
printed as ``rows.id``. The round-trip property -- a printed path is one
``excluding_path`` accepts -- is tested in a way that holds under either spelling;
the spelling itself is pinned in one separately marked test.

``collections.namedtuple`` is deliberately absent from the two NamedTuple
spellings: pyright strict rejects it outright (``reportUntypedNamedTuple``), so
the two spellings exercised here are ``typing.NamedTuple``'s class syntax and its
functional syntax, which produce the same ``_fields`` the engine reads.
"""

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum, IntEnum, StrEnum
from typing import TYPE_CHECKING, ClassVar, Final, NamedTuple, cast, overload

import pytest

from lovely_assertions import formatting
from lovely_assertions._equivalence import Equivalency, close_within, compare, equivalency
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def rendered(actual: object, expected: object, options: Equivalency | None = None) -> str:
    """``compare`` with the default configuration when none is given."""
    return compare(actual, expected, equivalency() if options is None else options)


def same(actual: object, expected: object, options: Equivalency | None = None) -> None:
    """Assert the two graphs are equivalent -- ``compare`` returned ``""``."""
    found = rendered(actual, expected, options)
    assert found == "", "expected equivalence, got:" + found


def differs(actual: object, expected: object, options: Equivalency | None = None) -> str:
    """Assert the two graphs are *not* equivalent, and hand back the block."""
    found = rendered(actual, expected, options)
    assert found != "", "expected a difference, got equivalence"
    assert found.startswith("\n"), "the block must start with a newline: " + repr(found)
    assert not found.endswith("\n"), "the block must not end with one: " + repr(found)
    return found


def block(actual: object, expected: object, options: Equivalency | None = None) -> list[str]:
    """The block's lines, with the leading newline stripped."""
    return differs(actual, expected, options)[1:].split("\n")


def mentions(lines: list[str], needle: str) -> bool:
    """Whether any line of a block carries ``needle``."""
    return any(needle in line for line in lines)


def spelling(lines: list[str], *candidates: str) -> str:
    """The one candidate spelling of a path the block actually used.

    Lets the round-trip property be tested without the test having to know which
    of the two notations for an identifier-like mapping key the engine chose.
    """
    found = [candidate for candidate in candidates if mentions(lines, candidate)]
    assert len(found) == 1, "expected exactly one of " + repr(candidates) + " in " + repr(lines)
    return found[0]


def nested(depth: int, leaf: object, /) -> object:
    """``{"next": {"next": ... leaf}}``, ``depth`` levels of it."""
    value: object = leaf
    for _ in range(depth):
        value = {"next": value}
    return value


def wide(depth: int, width: int, offset: int, /) -> object:
    """A graph that is deep *and* wide, every leaf shifted by ``offset``."""
    if depth == 0:
        return offset
    return {"k" + str(index): wide(depth - 1, width, offset + index) for index in range(width)}


# ---------------------------------------------------------------------------
# The cast: records of every shape the resolver has to recognise
# ---------------------------------------------------------------------------
@dataclass
class City:
    """The leaf of the headline path, ``address.city.name``."""

    name: str


@dataclass
class Address:
    city: City


@dataclass
class Person:
    address: Address


@dataclass
class UserRecord:
    """A dataclass with the same two members as :class:`PlainUser`."""

    name: str
    age: int


class PlainUser:
    """A hand-written record: two slots, no ``__eq__``, no dataclass machinery."""

    __slots__ = ("age", "name")

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def __repr__(self) -> str:
        return "PlainUser(" + repr(self.name) + ", " + repr(self.age) + ")"


@dataclass
class Measured:
    """Trap 3: the second member is not a member as far as ``==`` is concerned."""

    value: int
    taken_at: str = field(default="", compare=False)


@dataclass
class Computed:
    """A field the constructor does not take, and ``==`` still compares."""

    base: int
    doubled: int = field(init=False)

    def __post_init__(self) -> None:
        self.doubled = self.base * 2


@dataclass
class Animal:
    name: str


@dataclass
class Dog(Animal):
    breed: str


@dataclass(frozen=True, slots=True)
class Frozen:
    """``slots=True`` puts the ignored field in ``__slots__`` as well.

    The whole point of trap 3: a resolver that reached ``__slots__`` before
    ``dataclasses.fields()`` would compare ``label`` and contradict the ``==``
    that produced the failure.
    """

    value: int
    label: str = field(default="", compare=False)


def no_items() -> list[int]:
    """A named factory rather than ``list``, which resolves to ``list[Unknown]``."""
    return []


@dataclass
class Basket:
    """A mutable default, which is the one dataclass shape that needs a factory."""

    items: list[int] = field(default_factory=no_items)


class Point(NamedTuple):
    """Trap 1, class syntax: a record that *is* a tuple."""

    x: int
    y: int


Coord = NamedTuple("Coord", [("x", int), ("y", int)])  # noqa: UP014  (the other spelling)


class Slotted:
    """State in slots, and nowhere else."""

    __slots__ = ("host", "port")

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def __repr__(self) -> str:
        return "Slotted(" + repr(self.host) + ", " + repr(self.port) + ")"


class Tagged(Slotted):
    """Slots from the base, ``__dict__`` from the subclass that forgot to declare."""

    def __init__(self, host: str, port: int, tag: str) -> None:
        super().__init__(host, port)
        self.tag = tag

    def __repr__(self) -> str:
        return "Tagged(" + repr(self.host) + ", " + repr(self.port) + ", " + repr(self.tag) + ")"


class Sparse:
    """Two slots declared, one of them left unassigned."""

    __slots__ = ("a", "b")

    def __init__(self, a: int, b: int | None = None) -> None:
        self.a = a
        if b is not None:
            self.b = b

    def __repr__(self) -> str:
        return "Sparse(" + repr(self.a) + ")"


class Bag:
    """A plain object: state in ``__dict__``, and nothing else."""

    def __init__(self, **members: object) -> None:
        self.__dict__.update(members)

    def __repr__(self) -> str:
        return "Bag(" + ", ".join(sorted(self.__dict__)) + ")"


class AttrsAttribute(str):
    """One entry of a faked ``__attrs_attrs__``.

    Shaped so that *either* way of reading the declaration finds the same name:
    real attrs stores ``Attribute`` objects with a ``.name``, and this is one --
    while also being the string itself, so an engine that reads the entries as
    names is not failed for a choice that is left open.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        return str(self)


class Defined:
    """attrs, duck-typed: two declared fields and one that is not one."""

    __attrs_attrs__: ClassVar[tuple[AttrsAttribute, ...]] = (
        AttrsAttribute("x"),
        AttrsAttribute("y"),
    )

    def __init__(self, x: int, y: int, note: str) -> None:
        self.x = x
        self.y = y
        self.note = note

    def __repr__(self) -> str:
        return "Defined(" + repr(self.x) + ", " + repr(self.y) + ")"


class Model:
    """pydantic v2's shape: dunder slots for storage, field values in ``__dict__``."""

    __slots__ = ("__dict__", "__pydantic_extra__", "__pydantic_fields_set__")

    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)
        self.__pydantic_fields_set__ = set(values)
        self.__pydantic_extra__ = None

    def __repr__(self) -> str:
        return "Model(" + ", ".join(sorted(self.__dict__)) + ")"


# ---------------------------------------------------------------------------
# The cast: values that fight back
# ---------------------------------------------------------------------------
class Hostile:
    """Everything a comparison might touch, wired to explode."""

    __slots__ = ()

    def __repr__(self) -> str:
        raise RuntimeError("repr exploded")

    def __eq__(self, other: object) -> bool:
        raise RuntimeError("eq exploded")

    def __hash__(self) -> int:
        raise RuntimeError("hash exploded")


class Unrenderable:
    """Decidably different, and impossible to print."""

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value

    def __repr__(self) -> str:
        raise RuntimeError("repr exploded")


class Volatile:
    """A member ``vars()`` reports and ``getattr`` refuses to hand over.

    A ``property`` is a data descriptor, so it wins over the instance dictionary
    the value was smuggled into -- which is how a real ``@property`` that raises
    reaches a describer that resolved its name.
    """

    def __init__(self, steady: int) -> None:
        self.__dict__["boom"] = 1
        self.steady = steady

    @property
    def boom(self) -> int:
        raise RuntimeError("property exploded")

    def __repr__(self) -> str:
        return "Volatile(" + repr(self.steady) + ")"


class Truthy:
    """An ``__eq__`` answering with a non-bool that is true.

    No slots content and no ``__dict__``, so no resolver finds a member and the
    engine has nothing to walk: whatever it decides, it decides through ``==``.
    A record here would be compared field by field and would never reach the
    ``__eq__`` this class exists to test.
    """

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        # A deliberate protocol violation -- numpy's `__eq__` answers with an
        # array, and the engine has to survive one. The cast is how the lie is
        # told to both checkers without a suppression comment.
        return cast("bool", [1])

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "Truthy()"


class Falsy:
    """The same, answering with a non-bool that is false."""

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        return cast("bool", [])

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "Falsy()"


class Unbooleanable:
    """The numpy shape: ``__eq__`` answers, and the answer refuses to be a bool."""

    __slots__ = ()

    def __bool__(self) -> bool:
        raise RuntimeError("bool exploded")

    def __repr__(self) -> str:
        return "Unbooleanable()"


class Arrayish:
    """``__eq__`` returns something whose truth value is an error."""

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        # As above: the protocol is broken on purpose, and the cast says so.
        return cast("bool", Unbooleanable())

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "Arrayish()"


class Deceitful(Mapping[str, int]):
    """A mapping whose ``__contains__`` disagrees with its ``__iter__``."""

    __slots__ = ("_data", "_verdict")

    def __init__(self, data: dict[str, int], verdict: bool) -> None:
        self._data = data
        self._verdict = verdict

    def __getitem__(self, key: str) -> int:
        return self._data[key]

    def __iter__(self) -> "Iterator[str]":
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return self._verdict

    def __repr__(self) -> str:
        return "Deceitful(" + repr(self._data) + ")"


class Withholding(Mapping[str, int]):
    """A mapping that yields a key and then refuses to look it up."""

    __slots__ = ()

    def __getitem__(self, key: str) -> int:
        raise RuntimeError("getitem exploded: " + key)

    def __iter__(self) -> "Iterator[str]":
        return iter(("a", "b"))

    def __len__(self) -> int:
        return 2

    def __repr__(self) -> str:
        return "Withholding()"


class Explosive(Sequence[int]):
    """A sequence whose every dunder blows up."""

    __slots__ = ()

    def __len__(self) -> int:
        raise RuntimeError("len exploded")

    @overload
    def __getitem__(self, index: int) -> int: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[int]: ...
    def __getitem__(self, index: int | slice) -> int | Sequence[int]:
        raise RuntimeError("getitem exploded")

    def __iter__(self) -> "Iterator[int]":
        raise RuntimeError("iter exploded")

    def __repr__(self) -> str:
        return "Explosive()"


class BadAttrs:
    """An ``__attrs_attrs__`` that is not a declaration at all."""

    __attrs_attrs__: ClassVar[int] = 3
    __slots__ = ("a",)

    def __init__(self, a: int) -> None:
        self.a = a

    def __repr__(self) -> str:
        return "BadAttrs(" + repr(self.a) + ")"


class Fibbing(tuple[int, ...]):
    """A tuple subclass declaring a ``_fields`` it does not carry."""

    __slots__ = ()
    _fields: ClassVar[tuple[str, ...]] = ("nope",)


class Warm(Enum):
    RED = 1
    AMBER = 2


class Signal(Enum):
    """The same member names as :class:`Warm`, under different values."""

    RED = "stop"
    AMBER = "slow"


class Level(IntEnum):
    LOW = 1
    HIGH = 2


class Rank(IntEnum):
    """``HIGH``'s value, under ``LOW``'s name: equal to Python, differently named."""

    LOW = 2


class Colour(StrEnum):
    RED = "red"


class Planet(Enum):
    """An enum whose ``__init__`` puts state in the member's instance dictionary.

    The shape that turns "an enum member has no fields once ``_value_`` and
    friends are filtered out" from a rule into a coincidence. ``EARTH`` and
    ``MARS`` agree on the one attribute they carry and differ only in the value,
    so a walk that reads the attributes and not the value finds nothing to report.
    """

    EARTH = 1
    MARS = 2

    def __init__(self, _ordinal: int) -> None:
        self.rocky = True


NAN: Final = float("nan")


# ---------------------------------------------------------------------------
# The contract: the shape of the answer
# ---------------------------------------------------------------------------
def test_the_module_exports_exactly_the_names_the_contract_names() -> None:
    """The four public names, plus ``differs`` -- the same verdict without the report.

    Listed rather than folded into ``compare``: the two answer the same question
    and only one of them is allowed on a passing assertion's path, so the split has
    to be visible from outside the module.
    """
    from lovely_assertions import _equivalence

    assert _equivalence.__all__ == [
        "Equivalency",
        "close_within",
        "compare",
        "differs",
        "equivalency",
    ]


def test_the_module_folds_its_frames_out_of_a_failure_traceback() -> None:
    """Every module in the package carries ``__tracebackhide__``; pytest reads it per frame."""
    from lovely_assertions import _equivalence

    assert _equivalence.__tracebackhide__ is hide_internal_frames


def test_equivalency_hands_back_an_equivalency() -> None:
    assert isinstance(equivalency(), Equivalency)
    assert isinstance(equivalency().excluding("x"), Equivalency)


def test_two_equivalent_values_come_back_as_the_empty_string() -> None:
    assert compare(1, 1, equivalency()) == ""
    assert compare({"a": [1, 2]}, {"a": [1, 2]}, equivalency()) == ""


def test_two_unequal_scalars_are_not_equivalent_even_when_their_reprs_say_it_all() -> None:
    """The one place ``compare`` may not copy ``_diff``.

    ``describe_difference(1, 2)`` returns ``""`` because the caller already
    printed both reprs and there is nothing to add. Here ``""`` *means*
    equivalent, so staying silent would report a pass.
    """
    assert compare(1, 2, equivalency()) != ""
    assert compare("a", "b", equivalency()) != ""
    assert compare(None, 0, equivalency()) != ""


def test_the_block_starts_with_a_newline_and_does_not_end_with_one() -> None:
    found = compare({"a": 1}, {"a": 2}, equivalency())
    assert found.startswith("\n")
    assert not found.endswith("\n")


def test_every_line_of_the_block_is_indented_under_the_one_line_message() -> None:
    lines = block({"a": 1, "b": 2}, {"a": 9, "b": 8})
    assert lines
    assert all(line.startswith("  ") for line in lines)


def test_a_root_level_difference_reads_as_the_value_itself() -> None:
    """The root is the empty path, and it reads as ``the value itself`` rather than blank."""
    assert mentions(block(1, 2), "the value itself")


def test_comparing_a_value_with_itself_is_equivalence() -> None:
    shared = {"a": [1, {"b": 2}]}
    assert compare(shared, shared, equivalency()) == ""


# ---------------------------------------------------------------------------
# Ordering trap 1: a NamedTuple is a tuple
# ---------------------------------------------------------------------------
def test_a_named_tuple_is_compared_by_field_and_not_by_index() -> None:
    lines = block(Point(1, 2), Point(2, 1))
    assert not mentions(lines, "[0]"), lines
    assert not mentions(lines, "[1]"), lines


def test_a_named_tuple_names_its_fields_in_a_form_excluding_accepts() -> None:
    same(Point(1, 2), Point(2, 1), equivalency().excluding("x", "y"))


def test_ignoring_order_must_not_make_a_named_tuple_a_bag_of_values() -> None:
    """The trap, from the direction that produces a wrong pass."""
    assert compare(Point(1, 2), Point(2, 1), equivalency().ignoring_order()) != ""


def test_ignoring_order_still_lets_a_named_tuple_match_itself() -> None:
    same(Point(1, 2), Point(1, 2), equivalency().ignoring_order())


def test_the_functional_spelling_of_a_named_tuple_is_read_the_same_way() -> None:
    same(Coord(1, 2), Coord(1, 2))
    assert not mentions(block(Coord(1, 2), Coord(2, 1)), "[0]")
    assert compare(Coord(1, 2), Coord(2, 1), equivalency().ignoring_order()) != ""


def test_two_named_tuple_classes_with_the_same_fields_are_equivalent() -> None:
    """READING: the engine compares members, not declarations.

    ``tuple.__eq__`` already calls these equal, and equivalence is looser than
    ``==``, never stricter -- see the dataclass-against-plain-object test below,
    which is the same decision in its load-bearing form.
    """
    same(Point(1, 2), Coord(1, 2))


def test_a_named_tuple_meets_a_bare_tuple_wherever_equality_left_it() -> None:
    """Equivalence is never stricter than equality, so ``==`` decides here.

    The competing reading -- a record and a sequence are different kinds, and a
    member called ``x`` has no counterpart at index 0 -- loses, because
    ``Point(1, 2) == (1, 2)`` is true and a library that answered *not equivalent*
    would fail the weaker assertion exactly where the stronger one passes. There is
    no reading of two such answers that helps anybody.

    The cost, taken with open eyes: equivalence is not transitive across this
    seam. A tuple is equivalent to a list, and ``Point(1, 2)`` is equivalent to
    ``(1, 2)``, but ``Point(1, 2)`` against ``[1, 2]`` reports the kinds -- because
    nothing settled that pair before the kinds were asked. Non-transitivity is a
    property nobody states about ``==`` either; "never stricter than the assertion
    it loosens" is one this library states and keeps.
    """
    assert Point(1, 2) == (1, 2)
    same(Point(1, 2), (1, 2))
    assert mentions(block(Point(1, 2), [1, 2]), "types differ")


def test_a_named_tuple_and_a_sequence_equality_left_alone_report_their_kinds() -> None:
    """The other half: where ``==`` says nothing, the record and the sequence part."""
    assert Point(1, 2) != (1, 3)
    assert mentions(block(Point(1, 2), (1, 3)), "types differ: Point instead of tuple")


# ---------------------------------------------------------------------------
# Ordering trap 2: str and bytes are sequences
# ---------------------------------------------------------------------------
def test_a_string_is_never_walked_as_a_sequence_of_characters() -> None:
    assert compare("ab", ["a", "b"], equivalency()) != ""
    assert compare("ab", ("a", "b"), equivalency()) != ""


def test_ignoring_order_must_not_make_two_anagrams_equivalent() -> None:
    """The wrong pass this trap produces, in one line."""
    assert compare("ab", "ba", equivalency().ignoring_order()) != ""
    assert compare(b"ab", b"ba", equivalency().ignoring_order()) != ""
    assert compare(bytearray(b"ab"), bytearray(b"ba"), equivalency().ignoring_order()) != ""


def test_a_string_difference_is_not_labelled_with_a_character_index() -> None:
    assert not mentions(block("abc", "abd"), "[2]")


def test_bytes_are_not_walked_as_a_sequence_of_integers() -> None:
    assert not mentions(block(b"abc", b"abd"), "[2]")


def test_equal_strings_stay_equivalent_wherever_they_sit() -> None:
    same({"a": ["xy", b"z"]}, {"a": ["xy", b"z"]})
    same({"a": ["xy"]}, {"a": ["xy"]}, equivalency().ignoring_order())


def test_a_string_inside_a_sequence_is_still_a_leaf() -> None:
    lines = block(["ab"], ["ba"])
    assert mentions(lines, "[0]"), lines


# ---------------------------------------------------------------------------
# Ordering trap 3: a dataclass before vars(), honouring compare=False
# ---------------------------------------------------------------------------
def test_a_field_marked_compare_false_is_not_a_member() -> None:
    same(Measured(1, "monday"), Measured(1, "tuesday"))


def test_a_field_marked_compare_false_does_not_hide_a_real_difference() -> None:
    lines = block(Measured(1, "monday"), Measured(2, "tuesday"))
    assert mentions(lines, "value"), lines
    assert not mentions(lines, "taken_at"), lines


def test_compare_false_is_honoured_even_when_slots_declare_the_field() -> None:
    """``slots=True`` is where a resolver that races ``__slots__`` gets it wrong."""
    same(Frozen(1, "left"), Frozen(1, "right"))
    assert compare(Frozen(1, "left"), Frozen(2, "left"), equivalency()) != ""


def test_a_field_the_constructor_does_not_take_is_still_a_member() -> None:
    """READING: ``init=False`` is still state, and the generated ``__eq__`` reads it."""
    same(Computed(2), Computed(2))
    tampered = Computed(2)
    tampered.doubled = 99
    assert compare(tampered, Computed(2), equivalency()) != ""


def test_an_inherited_field_is_a_member_like_any_other() -> None:
    same(Dog("rex", "lab"), Dog("rex", "lab"))
    assert mentions(block(Dog("rex", "lab"), Dog("ace", "lab")), "name")
    assert mentions(block(Dog("rex", "lab"), Dog("rex", "pug")), "breed")


def test_a_mutable_default_is_compared_like_any_other_member() -> None:
    same(Basket(), Basket())
    assert mentions(block(Basket([1]), Basket([2])), "items[0]")


def test_a_nested_dataclass_composes_its_path() -> None:
    lines = block(Person(Address(City("paris"))), Person(Address(City("lyon"))))
    assert mentions(lines, "address.city.name"), lines


def test_an_attribute_that_is_not_a_declared_field_is_not_a_member() -> None:
    """READING: ``dataclasses.fields()`` is terminal, so ``vars()`` never gets a turn."""
    left = UserRecord("ann", 30)
    right = UserRecord("ann", 30)
    object.__setattr__(left, "note", "one")
    object.__setattr__(right, "note", "two")
    same(left, right)


def test_a_dataclass_is_equivalent_to_a_plain_object_with_the_same_members() -> None:
    """READING, and the load-bearing one: equivalence compares members, not types.

    This is the whole reason ``is_equivalent_to`` exists next to ``is_equal_to``:
    a recursive member-by-member comparison, rather than equality by reference or
    by ``__eq__``. Every generated ``__eq__`` in the ecosystem refuses a different
    class outright, so an equivalence that also refused one would be ``==`` with
    extra steps -- and comparing a DTO against an entity, which is what
    FluentAssertions' flagship is *for*, would be impossible.
    """
    same(UserRecord("ann", 30), PlainUser("ann", 30))
    assert compare(UserRecord("ann", 30), PlainUser("ann", 31), equivalency()) != ""


def test_a_record_with_a_member_the_expectation_names_is_not_equivalent() -> None:
    """READING: the expectation drives, so the two directions are not the same question.

    The opposite reading -- a surplus member is a structural difference, not a
    detail -- makes ``expect(row).is_equivalent_to(Expected(id=1, total=5))`` fail
    on every column the test was not about, which is the commonest reason anyone
    reaches for structural equivalence at all, and the asymmetry that gives
    ``BeEquivalentTo`` a reason to exist next to ``Be``. That stricter reading is
    still reachable, and is pinned below under the option that carries it.
    """
    assert compare(Bag(a=1), Bag(a=1, b=2), equivalency()) != ""
    assert compare(Bag(a=1, b=2), Bag(a=1), equivalency()) == ""


def test_the_overturned_reading_is_still_reachable_as_an_option() -> None:
    """``comparing_all_members()`` asks for the stricter reading, in both directions."""
    options = equivalency().comparing_all_members()
    assert compare(Bag(a=1), Bag(a=1, b=2), options) != ""
    assert compare(Bag(a=1, b=2), Bag(a=1), options) != ""


def test_a_mappings_surplus_key_is_a_difference_whatever_the_member_options_say() -> None:
    """READING: a dictionary's keys are its data, not a shape somebody declared.

    The expectation ``{"id": 1}`` is not a partial description of a payload, it is
    a payload, so "the response carried a key I did not expect" stays a difference
    -- and neither member option is about mappings at all. FluentAssertions keeps
    dictionary equivalency apart for the same reason.
    """
    for options in (
        equivalency(),
        equivalency().comparing_all_members(),
        equivalency().excluding_missing(),
    ):
        assert compare({"id": 1, "extra": 2}, {"id": 1}, options) != ""
        assert compare({"id": 1}, {"id": 1, "extra": 2}, options) != ""


def test_a_record_is_not_equivalent_to_a_mapping_of_the_same_names() -> None:
    """READING: a mapping's entries are data, a record's members are structure.

    They are different kinds, and treating them alike would make
    ``{"name": "ann"}`` equivalent to every one-field record ever written.
    """
    assert compare(UserRecord("ann", 30), {"name": "ann", "age": 30}, equivalency()) != ""


# ---------------------------------------------------------------------------
# Records of every other shape
# ---------------------------------------------------------------------------
def test_a_slots_class_is_read_through_its_slots() -> None:
    same(Slotted("prod", 443), Slotted("prod", 443))
    assert mentions(block(Slotted("prod", 8080), Slotted("prod", 443)), "port")


def test_an_object_that_mixes_slots_and_a_dict_is_read_through_both() -> None:
    """Reading only the winner reports two fields and stays silent about two more."""
    same(Tagged("prod", 443, "blue"), Tagged("prod", 443, "blue"))
    assert mentions(block(Tagged("prod", 443, "blue"), Tagged("prod", 443, "green")), "tag")
    assert mentions(block(Tagged("prod", 8080, "blue"), Tagged("prod", 443, "blue")), "port")


def test_an_unset_slot_is_absent_on_both_sides_and_costs_nothing() -> None:
    """READING: a slot that was never assigned is a member the object does not have."""
    same(Sparse(1), Sparse(1))


def test_an_unset_slot_against_an_assigned_one_is_a_difference() -> None:
    """READING, and the direction that matters: absent is not equal to present."""
    assert compare(Sparse(1), Sparse(1, 2), equivalency()) != ""
    assert compare(Sparse(1, 2), Sparse(1), equivalency()) != ""


def test_a_plain_object_is_read_through_its_instance_dictionary() -> None:
    same(Bag(host="prod", port=443), Bag(host="prod", port=443))
    assert mentions(block(Bag(host="prod", port=8080), Bag(host="prod", port=443)), "port")


def test_an_attrs_declaration_wins_over_the_instance_dictionary() -> None:
    """``__attrs_attrs__`` is consulted before ``vars()``.

    ``note`` is in the instance dictionary and is not a declared field, so an
    engine that reached ``vars()`` would report a difference attrs' own ``__eq__``
    never looked at.
    """
    same(Defined(1, 2, "left"), Defined(1, 2, "right"))
    assert mentions(block(Defined(1, 2, "same"), Defined(1, 3, "same")), "y")


def test_a_pydantic_shaped_model_is_read_through_its_dict_not_its_slots() -> None:
    """``__pydantic_fields_set__`` differs on these two, and is not a field."""
    left = Model(name="ann", age=30)
    right = Model(name="ann", age=30)
    right.__pydantic_fields_set__ = {"name"}
    same(left, right)
    lines = block(Model(name="ann", age=30), Model(name="ann", age=31))
    assert mentions(lines, "age"), lines
    assert not mentions(lines, "__pydantic_fields_set__"), lines


# ---------------------------------------------------------------------------
# Mappings
# ---------------------------------------------------------------------------
def test_values_that_differ_are_named_by_their_key() -> None:
    assert mentions(block({"a": 1, "b": 2}, {"a": 1, "b": 3}), "b")


def test_a_missing_key_is_a_difference_even_when_the_value_would_be_none() -> None:
    """A key present with ``None`` is not the same shape as a key absent.

    Neither member option reaches a mapping's keys, so the strict answer is the
    only one on offer here -- and it is the one that cannot silently lose a
    member.
    """
    assert compare({"a": 1, "b": None}, {"a": 1}, equivalency()) != ""
    assert compare({"a": 1}, {"a": 1, "b": None}, equivalency()) != ""


def test_both_directions_of_a_key_mismatch_are_reported() -> None:
    lines = block({"a": 1, "extra": 2}, {"a": 1, "absent": 3})
    assert mentions(lines, "extra"), lines
    assert mentions(lines, "absent"), lines


def test_a_nested_mapping_composes_its_path() -> None:
    lines = block({"outer": {"inner": 1}}, {"outer": {"inner": 2}})
    assert mentions(lines, "outer"), lines
    assert mentions(lines, "inner"), lines


def test_an_integer_key_is_bracketed() -> None:
    assert mentions(block({1: "a"}, {1: "b"}), "[1]")


def test_a_tuple_key_is_bracketed() -> None:
    """READING: the bracket holds the key as it renders, which for a tuple is its repr."""
    assert mentions(block({(1, 2): "a"}, {(1, 2): "b"}), "[(1, 2)]")


def test_a_key_that_is_not_an_identifier_is_bracketed() -> None:
    """READING: brackets, with the key quoted inside them, for a key that is not a name."""
    assert mentions(block({"two words": 1}, {"two words": 2}), "['two words']")


def test_a_mapping_subclass_is_equivalent_to_a_plain_dict_of_the_same_entries() -> None:
    """READING: kinds are compared, declarations are not."""
    same(Deceitful({"a": 1}, verdict=True), {"a": 1})


def test_a_mapping_whose_contains_denies_everything_never_raises() -> None:
    assert isinstance(rendered(Deceitful({"a": 1}, verdict=False), {"a": 1}), str)
    assert isinstance(
        rendered(Deceitful({"a": 1}, verdict=False), Deceitful({"a": 1}, verdict=False)), str
    )


def test_a_mapping_whose_contains_denies_everything_is_still_read_by_iteration() -> None:
    """READING: ``__iter__`` and ``__getitem__`` are the mapping; ``in`` is an opinion.

    An engine that decides membership with ``key in actual`` reports every entry
    of this mapping as missing *and* extra, which is a confident answer about a
    mapping that holds exactly what the other one holds.
    """
    same(Deceitful({"a": 1}, verdict=False), Deceitful({"a": 1}, verdict=False))


def test_a_mapping_whose_contains_accepts_everything_never_raises() -> None:
    """``in`` says yes, ``__getitem__`` then raises ``KeyError`` -- the other lie."""
    assert isinstance(rendered(Deceitful({"a": 1}, verdict=True), {"a": 1, "b": 2}), str)
    assert isinstance(rendered({"a": 1, "b": 2}, Deceitful({"a": 1}, verdict=True)), str)


def test_a_mapping_that_refuses_to_look_up_its_own_keys_never_raises() -> None:
    found = rendered(Withholding(), {"a": 1, "b": 2})
    assert isinstance(found, str)
    assert found != "", "a mapping whose values cannot be read is not proven equivalent"


def test_a_key_whose_value_is_a_record_composes_the_path_through_both() -> None:
    lines = block({"user": UserRecord("ann", 30)}, {"user": UserRecord("ann", 31)})
    assert mentions(lines, "user"), lines
    assert mentions(lines, "age"), lines


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------
def test_order_matters_by_default() -> None:
    """Order is structure in a sequence: ``[1, 2] == [2, 1]`` is false and must stay false."""
    assert compare([1, 2], [2, 1], equivalency()) != ""


def test_ignoring_order_counts_duplicates() -> None:
    """A multiset, not a set: otherwise ``[1, 1, 2]`` passes against ``[1, 2, 2]``."""
    assert compare([1, 1, 2], [1, 2, 2], equivalency().ignoring_order()) != ""
    same([1, 1, 2], [2, 1, 1], equivalency().ignoring_order())


def test_ignoring_order_handles_unhashable_items() -> None:
    left = [{"a": 1}, {"b": 2}]
    right = [{"b": 2}, {"a": 1}]
    same(left, right, equivalency().ignoring_order())
    assert compare(left, [{"b": 2}, {"a": 9}], equivalency().ignoring_order()) != ""


def test_ignoring_order_matches_items_equivalently_and_not_merely_by_equality() -> None:
    """READING, and the reason unordered matching is quadratic *in deep comparisons*.

    Under ``ignoring_order`` the engine has to decide which item faces which, and
    ``excluding`` has to still apply while it does -- otherwise the two options
    cannot be used together on a list of records, which is the commonest place
    anyone would want them.
    """
    left = [{"id": 1, "noise": "a"}, {"id": 2, "noise": "b"}]
    right = [{"id": 2, "noise": "z"}, {"id": 1, "noise": "y"}]
    same(left, right, equivalency().ignoring_order().excluding("noise"))


def test_ignoring_order_reaches_a_nested_collection() -> None:
    same({"xs": [1, 2]}, {"xs": [2, 1]}, equivalency().ignoring_order())
    assert compare({"xs": [1, 2]}, {"xs": [2, 1]}, equivalency()) != ""


def test_a_set_is_unordered_without_asking() -> None:
    same({1, 2, 3}, {3, 2, 1})
    same(frozenset({1, 2}), frozenset({2, 1}))


def test_a_frozenset_is_equivalent_to_a_set_of_the_same_items() -> None:
    """READING: both are sets, and a set is the kind whose order is not structure."""
    same(frozenset({1, 2}), {1, 2})


def test_a_set_is_not_equivalent_to_a_list() -> None:
    """READING: the argument for strict ordering, applied to the other side.

    A ``list`` is ordered by definition and a ``set`` exists for the other case;
    calling them the same thing would make the distinction the language draws
    invisible to the assertion.
    """
    assert compare({1, 2}, [1, 2], equivalency()) != ""
    assert compare({1, 2}, [1, 2], equivalency().ignoring_order()) != ""


def test_a_range_is_a_sequence_like_any_other() -> None:
    same(range(3), range(3))
    assert compare(range(3), range(4), equivalency()) != ""


def test_a_range_is_equivalent_to_the_list_of_what_it_yields() -> None:
    """READING: ``range(3) == [0, 1, 2]`` is false, and structurally they are one thing."""
    same(range(3), [0, 1, 2])


def test_lengths_that_differ_are_reported_with_the_index_that_has_no_counterpart() -> None:
    """READING: a surplus item has a *where*, and every difference names one.

    "extra items: [3]" is ``_diff``'s vocabulary and reads well, but it is the one
    finding in a sequence comparison the reader cannot paste into
    ``excluding_path``.
    """
    lines = block([1, 2, 3], [1, 2])
    assert mentions(lines, "[2]"), lines


def test_a_one_shot_iterable_is_not_consumed() -> None:
    """READING: an assertion that drains the subject changes the test it is in.

    A generator is not a ``Sequence`` and has no length; this library's own
    dispatch already treats it as a plain value (``CollectionExpect`` wants a
    ``Collection``). Comparing two of them therefore compares two objects, and --
    whatever answer the engine gives -- the caller's generator must still hold
    everything it held before.
    """
    left = (index for index in range(3))
    right = (index for index in range(3))
    assert isinstance(rendered(left, right), str)
    assert list(left) == [0, 1, 2]
    assert list(right) == [0, 1, 2]


def test_a_generator_is_equivalent_to_itself() -> None:
    generator = (index for index in range(3))
    same(generator, generator)
    assert list(generator) == [0, 1, 2]


def test_a_sequence_of_records_names_the_index_and_then_the_member() -> None:
    lines = block([UserRecord("ann", 30)], [UserRecord("ann", 31)])
    assert mentions(lines, "[0]"), lines
    assert mentions(lines, "age"), lines


# ---------------------------------------------------------------------------
# Values that fight back
# ---------------------------------------------------------------------------
def test_an_eq_that_raises_never_reaches_the_caller() -> None:
    assert isinstance(rendered(Hostile(), Hostile()), str)


def test_an_eq_that_raises_is_never_reported_as_equivalence() -> None:
    """A comparison that could not be made has not been made."""
    assert rendered(Hostile(), Hostile()) != ""


def test_an_interrupt_is_not_a_value_and_goes_through() -> None:
    """Where the guarantee stops, and it stops in the right place.

    Every guard here catches ``Exception``, the line ``_diff`` and the formatter
    registry already draw. A ``BaseException`` is not a value misbehaving -- it is
    ``Ctrl-C``, or an interpreter on its way out -- and swallowing one would make
    a comparison of two large graphs the one thing a reader could not interrupt.
    """

    class Interrupting:
        __slots__ = ()

        def __eq__(self, _other: object) -> bool:
            raise KeyboardInterrupt

        def __hash__(self) -> int:
            return 0

    with pytest.raises(KeyboardInterrupt):
        compare(Interrupting(), Interrupting(), equivalency())


def test_an_eq_that_raises_still_yields_to_identity() -> None:
    """READING: identity first, the rule ``_diff._equal`` and ``list.__eq__`` share."""
    hostile = Hostile()
    same(hostile, hostile)


def test_a_repr_that_raises_costs_detail_and_not_the_answer() -> None:
    found = rendered(Unrenderable(1), Unrenderable(2))
    assert found != "", "two different values must not come back equivalent"


def test_a_property_that_raises_costs_that_member_only() -> None:
    """One hostile member of a record must not cost the reader the others."""
    found = rendered(Volatile(1), Volatile(2))
    assert found != ""
    assert "steady" in found, found


def test_an_eq_that_answers_with_a_non_bool_is_taken_at_its_truth_value() -> None:
    """READING: ``bool(actual == expected)``, which is what ``_diff._equal`` does."""
    same(Truthy(), Truthy())
    assert compare(Falsy(), Falsy(), equivalency()) != ""


def test_an_eq_whose_answer_refuses_to_be_a_bool_never_raises() -> None:
    found = rendered(Arrayish(), Arrayish())
    assert isinstance(found, str)
    assert found != ""


def test_a_registered_sequence_whose_dunders_explode_never_raises() -> None:
    assert isinstance(rendered(Explosive(), Explosive()), str)
    assert isinstance(rendered(Explosive(), [1, 2]), str)
    assert isinstance(rendered([1, 2], Explosive()), str)


def test_a_garbage_attrs_declaration_never_raises() -> None:
    assert isinstance(rendered(BadAttrs(1), BadAttrs(2)), str)
    assert rendered(BadAttrs(1), BadAttrs(2)) != ""


def test_a_tuple_that_declares_fields_it_does_not_carry_is_not_a_free_pass() -> None:
    """READING: a resolver that finds no readable member has resolved nothing.

    ``Fibbing((1, 2))`` and ``Fibbing((1, 3))`` are two different tuples. An engine
    that trusts ``_fields``, fails to read ``nope`` on both sides, and calls that
    "no differences" turns a hostile declaration into a green test.
    """
    assert compare(Fibbing((1, 2)), Fibbing((1, 3)), equivalency()) != ""


def test_a_nan_is_equal_to_nothing_itself_included() -> None:
    """READING: identity first, then equality -- Python's own containment rule."""
    assert compare(NAN, float("nan"), equivalency()) != ""
    assert compare([NAN], [float("nan")], equivalency()) != ""
    assert compare({"a": NAN}, {"a": float("nan")}, equivalency()) != ""


def test_the_same_nan_object_matches_itself_wherever_it_sits() -> None:
    same(NAN, NAN)
    same([NAN], [NAN])
    same({"a": NAN}, {"a": NAN})
    same({NAN: 1}, {NAN: 1})
    same(Bag(items=[NAN]), Bag(items=[NAN]))


def test_a_nan_inside_a_record_never_raises() -> None:
    assert isinstance(rendered(Bag(items=[NAN]), Bag(items=[float("nan")])), str)
    assert isinstance(rendered({"a": [NAN]}, {"a": [float("nan")]}), str)


def test_zero_false_and_zero_point_zero_are_one_value() -> None:
    """READING, and the one I would most expect the engine to disagree with.

    Equality is the leaf rule, and ``0 == False == 0.0`` in Python. Making
    equivalence stricter than ``==`` at the leaves would mean ``is_equivalent_to``
    could fail where ``is_equal_to`` passes on the very same pair, which is not a
    relation anyone can reason about.
    """
    same(0, False)
    same({"a": 0}, {"a": 0.0})
    same([0, 1], [False, True])


def test_a_decimal_and_an_int_that_compare_equal_are_equivalent() -> None:
    """READING: the same leaf rule as above."""
    same(Decimal("1.0"), 1)
    same({"total": Decimal("1.0")}, {"total": 1})


def test_a_decimal_that_does_not_compare_equal_is_a_difference() -> None:
    assert compare(Decimal("1.5"), 1, equivalency()) != ""


# ---------------------------------------------------------------------------
# Cycles, and the diamond that is not one
# ---------------------------------------------------------------------------
def test_two_structurally_identical_cycles_are_equivalent() -> None:
    """READING: a pair already on the path is assumed to hold -- the co-inductive rule.

    Anything else reports a difference in two structures that hold exactly the
    same thing, which is a false failure on the commonest cyclic shape there is:
    a parent pointer.
    """
    left: list[object] = [1]
    left.append(left)
    right: list[object] = [1]
    right.append(right)
    same(left, right)


def test_a_cycle_does_not_swallow_a_real_difference() -> None:
    """The direction that matters: co-induction must not become a free pass."""
    left: list[object] = [1]
    left.append(left)
    right: list[object] = [2]
    right.append(right)
    assert compare(left, right, equivalency()) != ""


def test_two_mutually_referential_objects_terminate() -> None:
    """Two graphs that hold the same thing must not differ because they refer back.

    READING for the verdict; that the comparison terminates at all is required
    whichever way the verdict goes.
    """
    left_a = Bag(name="a")
    left_b = Bag(name="b", peer=left_a)
    left_a.__dict__["peer"] = left_b
    right_a = Bag(name="a")
    right_b = Bag(name="b", peer=right_a)
    right_a.__dict__["peer"] = right_b
    started = time.perf_counter()
    found = rendered(left_a, right_a)
    assert time.perf_counter() - started < 2.0
    assert found == "", found


def test_a_self_referential_mapping_terminates() -> None:
    left: dict[str, object] = {"n": 1}
    left["self"] = left
    right: dict[str, object] = {"n": 1}
    right["self"] = right
    started = time.perf_counter()
    assert isinstance(rendered(left, right), str)
    assert time.perf_counter() - started < 2.0


def test_a_diamond_is_not_a_cycle_and_is_reported_at_both_paths() -> None:
    """The bug this catches: one global "already visited" set instead of a path.

    ``shared`` is reachable twice and refers to nothing above it. Marking it seen
    at ``left`` and skipping it at ``right`` reports one of the two differences and
    silently drops the other.

    The node is shared on **both** sides, and that is the whole test. The memo is
    keyed on the *pair* of identities, so a diamond in the subject alone produces
    two different keys and a memo that never forgets would go unnoticed. Only when
    the same pair is reached twice does the difference between "on the path above
    me" and "seen at some point" show up.
    """
    shared = {"v": 1}
    counterpart = {"v": 2}
    lines = block({"left": shared, "right": shared}, {"left": counterpart, "right": counterpart})
    assert mentions(lines, "left"), lines
    assert mentions(lines, "right"), lines


def test_a_diamond_that_holds_matches_on_both_sides() -> None:
    shared = {"v": 1}
    counterpart = {"v": 1}
    same({"left": shared, "right": shared}, {"left": counterpart, "right": counterpart})


def test_a_shared_leaf_on_one_side_only_changes_nothing() -> None:
    shared = [1, 2]
    same({"a": shared, "b": shared}, {"a": [1, 2], "b": [1, 2]})


# ---------------------------------------------------------------------------
# Depth and size: the output stays bounded
# ---------------------------------------------------------------------------
def test_a_hundred_differences_stay_inside_a_bounded_message() -> None:
    """Characters, not lines: ``tests/test_equivalence.py`` counts the lines, this the bulk.

    A block can hold its line count and still be unreadable, because one line of
    it may carry a rendered value of any size at all.
    """
    actual = {"k" + str(index): index for index in range(100)}
    expected = {"k" + str(index): index + 1 for index in range(100)}
    found = differs(actual, expected)
    assert len(found) <= 2000, len(found)


def test_a_ten_thousand_element_sequence_stays_bounded_and_quick() -> None:
    actual = list(range(10_000))
    expected = [value + 1 for value in actual]
    started = time.perf_counter()
    found = differs(actual, expected)
    assert time.perf_counter() - started < 2.0
    assert len(found[1:].split("\n")) <= 15
    assert len(found) <= 2000, len(found)


def test_a_graph_that_is_deep_and_wide_does_not_print_their_product() -> None:
    """Per-level bounds are not bounds: ten items at each of five levels is ten thousand lines.

    Whatever is elided must be counted rather than printed.
    """
    found = differs(wide(4, 6, 0), wide(4, 6, 1))
    lines = found[1:].split("\n")
    assert len(lines) <= 80, len(lines)
    assert len(found) <= 10_000, len(found)


def test_unordered_matching_of_a_nested_graph_stops_without_pretending_to_an_answer() -> None:
    """A per-level cap on pairing is not a cap: it multiplies with every level.

    ``ignoring_order()`` pairs whatever equality could not by *comparing* each
    remaining candidate against each remaining item, and a hundred against a
    hundred is ten thousand comparisons at one level. When the items are
    themselves lists of unhashables, each of those ten thousand is another ten
    thousand, and two levels is a hundred million: no exception, no output, just a
    test run that never comes back. The bound has to be on the total.

    These two *are* equivalent, and the engine cannot afford to find that out. So
    the one thing it must not do is answer. Reporting the unpaired items as a
    difference with a "stopped pairing" aside would be a wrong failure for
    ``is_equivalent_to`` and, worse, a silent wrong pass for
    ``is_not_equivalent_to`` -- the aside is not something a boolean can read. It
    raises instead, which both directions see identically.
    """
    rows = [[[row, cell] for cell in range(100)] for row in range(100)]
    shuffled = [list(reversed(row)) for row in reversed(rows)]
    started = time.perf_counter()
    with pytest.raises(ValueError, match="stopped rather than answered") as caught:
        rendered(rows, shuffled, equivalency().ignoring_order())
    assert time.perf_counter() - started < 10.0
    assert "Compare fewer items in one call" in str(caught.value)


def test_a_graph_deeper_than_any_sane_limit_never_raises() -> None:
    started = time.perf_counter()
    assert isinstance(rendered(nested(2000, 1), nested(2000, 1)), str)
    assert isinstance(rendered(nested(2000, 1), nested(2000, 2)), str)
    assert time.perf_counter() - started < 2.0


def test_a_long_value_is_clipped_rather_than_printed_whole() -> None:
    long = "x" * 5000
    lines = block({"a": long}, {"a": long + "y"})
    assert all(len(line) <= 400 for line in lines), max(len(line) for line in lines)


def test_how_many_differences_are_shown_follows_the_formatting_scope() -> None:
    """The caps are ``current_formatting()``'s, so a reader can raise them for a scope."""
    actual = {"k" + str(index): index for index in range(100)}
    expected = {"k" + str(index): index + 1 for index in range(100)}
    default_lines = block(actual, expected)
    with formatting(max_items=2):
        narrow_lines = block(actual, expected)
    assert len(narrow_lines) < len(default_lines), (narrow_lines, default_lines)


def test_the_formatting_scope_never_changes_the_verdict() -> None:
    """Bounds change what a failure *says*, never what a comparison *decides*."""
    with formatting(max_items=1, max_chars=1):
        assert compare({"a": 1}, {"a": 1}, equivalency()) == ""
        assert compare({"a": 1}, {"a": 2}, equivalency()) != ""


# ---------------------------------------------------------------------------
# The options, one at a time
# ---------------------------------------------------------------------------
def test_excluding_removes_a_member_at_every_depth() -> None:
    actual = {"secret": 1, "a": {"secret": 2, "keep": 3}}
    expected = {"secret": 9, "a": {"secret": 8, "keep": 3}}
    same(actual, expected, equivalency().excluding("secret"))


def test_excluding_does_not_remove_anything_else() -> None:
    actual = {"secret": 1, "keep": 3}
    expected = {"secret": 9, "keep": 4}
    lines = block(actual, expected, equivalency().excluding("secret"))
    assert mentions(lines, "keep"), lines


def test_excluding_takes_several_names_and_composes() -> None:
    actual = {"a": 1, "b": 2, "c": 3}
    expected = {"a": 9, "b": 8, "c": 3}
    same(actual, expected, equivalency().excluding("a", "b"))
    same(actual, expected, equivalency().excluding("a").excluding("b"))


def test_excluding_a_member_of_a_record_works_the_same_way() -> None:
    same(UserRecord("ann", 30), UserRecord("ann", 31), equivalency().excluding("age"))


def test_excluding_nothing_is_a_configuration_that_changes_nothing() -> None:
    """READING: the precedent is ``formatting()`` with no overrides.

    ``formatting(max_items=configured)`` with nothing configured is an honest
    no-op, and so is this. A builder call is not a variadic *assertion*, so the
    rule behind ``_NEEDS_VALUES`` -- an assertion given nothing must not quietly
    pass -- does not reach it: ``excluding()`` excludes nothing and decides
    nothing.
    """
    same({"a": 1}, {"a": 1}, equivalency().excluding())
    assert compare({"a": 1}, {"a": 2}, equivalency().excluding()) != ""


def test_excluding_path_matches_one_place_and_not_the_name_everywhere() -> None:
    """Asserted positively on purpose.

    "``a.n`` is absent from the block" would be a claim about the *whole* string,
    and the block ends with the effective configuration -- which names the
    excluded path. The two halves below say the same thing without tripping over
    it: excluded on its own it is silent, and it silences nothing else.
    """
    options = equivalency().excluding_path("a.n")
    same({"a": {"n": 1}}, {"a": {"n": 2}}, options)
    lines = block({"a": {"n": 1}, "b": {"n": 1}}, {"a": {"n": 2}, "b": {"n": 2}}, options)
    assert mentions(lines, "b.n"), lines


def test_excluding_a_path_that_matches_nothing_is_silent() -> None:
    """Silent rather than loud, on two legs.

    Printing the effective configuration on every failure exists *because* a
    mis-typed exclusion is invisible otherwise: a reader who excluded the wrong
    field can see that they did. That mechanism is pointless if the wrong field
    raised instead. And a raise would also fire on a comparison that was going to
    *pass*, turning a rendering preference into a test failure.
    """
    same({"a": 1}, {"a": 1}, equivalency().excluding_path("nope.nope"))
    assert compare({"a": 1}, {"a": 2}, equivalency().excluding_path("nope.nope")) != ""


def test_excluding_a_path_takes_the_whole_subtree_under_it() -> None:
    """READING: a path names a node, and a node's members are part of it."""
    actual = {"a": {"n": 1, "m": 2}, "keep": 3}
    expected = {"a": {"n": 9, "m": 8}, "keep": 3}
    same(actual, expected, equivalency().excluding_path("a"))


def test_including_restricts_what_is_compared() -> None:
    same({"id": 1, "noise": "a"}, {"id": 1, "noise": "b"}, equivalency().including("id"))


def test_including_does_not_hide_a_difference_in_an_included_member() -> None:
    assert (
        compare({"id": 1, "noise": "a"}, {"id": 2, "noise": "a"}, equivalency().including("id"))
        != ""
    )


def test_including_takes_several_names() -> None:
    actual = {"id": 1, "name": "ann", "noise": "a"}
    expected = {"id": 1, "name": "ann", "noise": "b"}
    same(actual, expected, equivalency().including("id", "name"))
    assert (
        compare(
            actual, {"id": 1, "name": "bob", "noise": "a"}, equivalency().including("id", "name")
        )
        != ""
    )


def test_including_a_name_nothing_carries_compares_nothing_and_passes() -> None:
    """READING, and the sharp edge of ``including``: a typo is a silently green test.

    Nothing named is selected, so nothing is compared, so the two are equivalent --
    the same answer excluding every member gives, and consistent with it. The one
    vacuity that *can* be caught at the call, ``excluding_path("")``, is caught
    there. FluentAssertions instead reports "no members were found for
    comparison"; saying that here needs a channel this option set does not have,
    and the engine prints its configuration only on a failure, which this is not.
    Pinned so that it is a decision rather than an accident.
    """
    same(PlainUser("ann", 30), PlainUser("bob", 99), equivalency().including("naem"))
    same({"a": 1}, {"a": 2}, equivalency().including("naem"))
    same(UserRecord("ann", 30), UserRecord("bob", 99), equivalency().excluding("name", "age"))


def test_an_index_path_does_not_reach_a_sequence_whose_order_is_ignored() -> None:
    """READING: once order stops being structure, an index stops naming anything.

    ``excluding_path("[0]")`` excludes the first item of an ordered sequence. Under
    ``ignoring_order()`` there is no first item to exclude -- the items are a bag --
    so the exclusion reaches nothing and the difference is still reported. That is
    the safe direction (a reader gets a failure they did not expect rather than a
    pass they did not earn) but it is silent, so it is pinned here.
    """
    same([1, 2], [9, 2], equivalency().excluding_path("[0]"))
    assert compare([1, 2], [9, 2], equivalency().ignoring_order().excluding_path("[0]")) != ""


def test_ignoring_order_alone_changes_nothing_else() -> None:
    assert compare({"a": 1}, {"a": 2}, equivalency().ignoring_order()) != ""


def test_using_applies_at_every_depth_a_value_of_that_type_appears() -> None:
    options = equivalency().using(float, close_within(0.01))
    actual = {"a": 1.0, "b": [2.0, {"c": 3.0}]}
    expected = {"a": 1.005, "b": [2.005, {"c": 3.005}]}
    same(actual, expected, options)


def test_using_does_not_widen_past_its_own_tolerance() -> None:
    options = equivalency().using(float, close_within(0.01))
    assert compare({"a": 1.0}, {"a": 1.5}, options) != ""


def test_using_leaves_every_other_type_alone() -> None:
    def always(_left: float, _right: float) -> bool:
        return True

    options = equivalency().using(float, always)
    assert compare({"a": 1, "b": 2.0}, {"a": 9, "b": 99.0}, options) != ""


def test_using_takes_a_comparator_for_more_than_one_type() -> None:
    def folded(left: str, right: str) -> bool:
        return left.casefold() == right.casefold()

    options = equivalency().using(float, close_within(0.5)).using(str, folded)
    same({"a": 1.0, "b": "ANN"}, {"a": 1.2, "b": "ann"}, options)


def test_a_later_comparator_for_a_type_replaces_the_earlier_one() -> None:
    """READING: a builder refines, so the last word on a type is the one in force."""
    options = equivalency().using(float, close_within(10.0)).using(float, close_within(0.1))
    assert compare({"a": 1.0}, {"a": 5.0}, options) != ""


def test_a_comparator_that_raises_never_reaches_the_caller() -> None:
    def explodes(_left: int, _right: int) -> bool:
        raise RuntimeError("comparator exploded")

    options = equivalency().using(int, explodes)
    # Two values that are not the same object, so no identity short-circuit can
    # settle the pair before the comparator is asked.
    found = rendered({"a": 1}, {"a": 1000}, options)
    assert isinstance(found, str)
    assert found != "", "a comparison that could not be made is not equivalence"
    assert isinstance(rendered({"a": 1000}, {"a": 1000}, options), str)


def test_a_comparator_applies_to_subclasses_of_the_type_it_names() -> None:
    """READING: ``isinstance``, which is what ``type[C]`` reads as everywhere else."""

    def always(_left: int, _right: int) -> bool:
        return True

    same({"a": True}, {"a": False}, equivalency().using(int, always))


def test_max_depth_zero_still_decides_the_root_pair() -> None:
    same({"a": 1}, {"a": 1}, equivalency().with_max_depth(0))
    assert compare({"a": 1}, {"a": 2}, equivalency().with_max_depth(0)) != ""


def test_a_difference_past_the_depth_limit_is_not_silently_a_pass() -> None:
    """The limit bounds the *walk*, never the verdict.

    A limit that turned an unexamined subtree into a pass would be exactly the
    failure mode every default here refuses: a configuration that produces tests
    which pass when they should not.
    """
    for depth in (0, 1, 2, 3):
        options = equivalency().with_max_depth(depth)
        assert compare(nested(6, 1), nested(6, 2), options) != "", depth


def test_equal_graphs_stay_equivalent_at_every_depth_limit() -> None:
    for depth in (0, 1, 2, 3, 20):
        assert compare(nested(6, 1), nested(6, 1), equivalency().with_max_depth(depth)) == "", depth


def test_a_negative_depth_is_refused_at_the_call_that_makes_the_mistake() -> None:
    """READING, following ``_formatting._checked``: a bad limit is reported where
    it is written, not later, in the middle of reporting somebody's failure."""
    with pytest.raises(ValueError, match="depth"):
        equivalency().with_max_depth(-1)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
def test_an_enum_member_matches_itself_without_any_option() -> None:
    same(Warm.RED, Warm.RED)
    same({"state": Warm.RED}, {"state": Warm.RED})


def test_two_members_of_one_enum_are_not_equivalent() -> None:
    assert compare(Warm.RED, Warm.AMBER, equivalency()) != ""


def test_an_enum_member_is_not_walked_as_a_record() -> None:
    """``_name_``, ``_value_`` and ``_sort_order_`` are the runtime's, not the reader's."""
    lines = block(Warm.RED, Warm.AMBER)
    assert not mentions(lines, "_value_"), lines
    assert not mentions(lines, "_sort_order_"), lines


def test_an_enum_member_that_carries_attributes_is_still_not_a_record() -> None:
    """The wrong pass hiding behind the test above, which a plain enum cannot show.

    Filtering ``_name_`` and ``_value_`` out of the instance dictionary leaves a
    *plain* member with nothing to compare, so it lands on the leaf branch by
    accident rather than by rule. Give the enum an ``__init__`` and the accident
    stops: the member becomes a record whose fields are the attributes, its value
    stops being compared at all, and two members that agree on those attributes
    come back **equivalent**. An enum member is its value; there is nothing
    underneath it to walk.
    """
    assert Planet.EARTH.rocky == Planet.MARS.rocky
    lines = block(Planet.EARTH, Planet.MARS)
    assert not mentions(lines, "rocky"), lines


def test_two_enum_classes_are_not_equivalent_by_default() -> None:
    assert compare(Warm.RED, Signal.RED, equivalency()) != ""


def test_comparing_enums_by_name_matches_across_classes() -> None:
    same(Warm.RED, Signal.RED, equivalency().comparing_enums_by_name())


def test_comparing_enums_by_name_still_separates_different_names() -> None:
    assert compare(Warm.RED, Signal.AMBER, equivalency().comparing_enums_by_name()) != ""


def test_comparing_enums_by_name_reaches_every_depth() -> None:
    options = equivalency().comparing_enums_by_name()
    same({"a": [Warm.RED]}, {"a": [Signal.RED]}, options)
    assert compare({"a": [Warm.RED]}, {"a": [Signal.AMBER]}, options) != ""


def test_comparing_enums_by_name_does_not_match_a_bare_string() -> None:
    """READING: the option compares two enums by name, not an enum to a name."""
    assert compare(Warm.RED, "RED", equivalency().comparing_enums_by_name()) != ""


def test_comparing_enums_by_name_is_the_one_option_that_narrows() -> None:
    """READING: asking for name semantics is asking for the value to stop deciding.

    Every other option in the set only widens what counts as equivalent, which is
    what lets ``==`` settle a pair before the options are consulted at all. This
    one replaces the rule instead: two ``IntEnum`` members that Python calls equal,
    under different names, are not equivalent once names are what is compared.
    Surprising enough to be worth a test rather than a discovery.
    """
    # Held as ``object`` so the comparison survives the checkers: mypy reads two
    # differently-typed enum literals as non-overlapping, which is exactly the
    # assumption this test exists to contradict at runtime.
    equal_to_python: object = Level.HIGH
    assert equal_to_python == Rank.LOW
    same(Level.HIGH, Rank.LOW)
    assert compare(Level.HIGH, Rank.LOW, equivalency().comparing_enums_by_name()) != ""


def test_an_int_enum_keeps_the_equality_it_already_had() -> None:
    """READING: the leaf rule is ``==``, and ``Level.LOW == 1``."""
    same(Level.LOW, 1)


def test_a_str_enum_is_a_string_and_is_not_walked_as_a_sequence() -> None:
    same(Colour.RED, "red")
    assert not mentions(block(Colour.RED, "rex"), "[2]")


# ---------------------------------------------------------------------------
# close_within
# ---------------------------------------------------------------------------
def test_close_within_accepts_a_float_tolerance() -> None:
    near = close_within(0.5)
    assert near(1.0, 1.4)
    assert not near(1.0, 1.6)


def test_close_within_is_inclusive_at_its_bound() -> None:
    """READING: "within" reads as inclusive, and a strict bound would make
    ``close_within(0)`` mean "never equal", which is not a tolerance."""
    assert close_within(0.5)(1.0, 1.5)


def test_close_within_is_symmetric() -> None:
    near = close_within(0.5)
    assert near(1.0, 1.4) == near(1.4, 1.0)
    assert near(1.0, 2.0) == near(2.0, 1.0)


def test_close_within_never_makes_a_nan_close_to_anything() -> None:
    near = close_within(1.0)
    assert not near(NAN, NAN)
    assert not near(NAN, 1.0)


def test_close_within_accepts_a_timedelta_tolerance() -> None:
    near = close_within(timedelta(seconds=1))
    base = datetime(2024, 1, 1, 12, 0, 0)
    assert near(base, base + timedelta(milliseconds=500))
    assert not near(base, base + timedelta(seconds=2))


def test_close_within_is_the_vehicle_for_date_tolerance_inside_a_graph() -> None:
    base = datetime(2024, 1, 1, 12, 0, 0)
    options = equivalency().using(datetime, close_within(timedelta(seconds=1)))
    same({"at": base}, {"at": base + timedelta(milliseconds=200)}, options)
    assert compare({"at": base}, {"at": base + timedelta(minutes=1)}, options) != ""


def test_close_within_works_for_any_type_that_subtracts() -> None:
    near = close_within(0.5)
    assert near(Decimal("1.0"), Decimal("1.2"))
    assert not near(Decimal("1.0"), Decimal("2.0"))


def test_close_within_never_raises_on_types_that_cannot_be_subtracted() -> None:
    """It is handed to ``using``, and ``compare`` promises never to raise."""
    options = equivalency().using(str, close_within(0.5))
    assert isinstance(rendered({"a": "x"}, {"a": "y"}, options), str)
    assert isinstance(rendered({"a": "x"}, {"a": "x"}, options), str)


# ---------------------------------------------------------------------------
# The options: immutability and combination
# ---------------------------------------------------------------------------
def test_a_builder_is_never_mutated_by_deriving_from_it() -> None:
    base = equivalency()
    lenient = base.excluding("noise")
    assert lenient is not base
    assert compare({"noise": 1}, {"noise": 2}, base) != ""
    assert compare({"noise": 1}, {"noise": 2}, lenient) == ""


def test_a_builder_reused_twice_gives_the_same_answer_twice() -> None:
    base = equivalency().excluding("noise")
    first = compare({"noise": 1, "id": 1}, {"noise": 2, "id": 1}, base)
    _ = base.ignoring_order()
    _ = base.with_max_depth(0)
    _ = base.including("id")
    second = compare({"noise": 1, "id": 1}, {"noise": 2, "id": 1}, base)
    assert first == second == ""


def test_comparing_twice_with_one_configuration_gives_one_answer() -> None:
    options = equivalency().ignoring_order().excluding("noise")
    actual = [{"id": 1, "noise": "a"}, {"id": 2, "noise": "b"}]
    expected = [{"id": 2, "noise": "z"}, {"id": 1, "noise": "y"}]
    first = compare(actual, expected, options)
    second = compare(actual, expected, options)
    assert first == second


def test_comparing_does_not_disturb_the_values_it_was_given() -> None:
    actual = [{"a": 1}, {"b": 2}]
    expected = [{"b": 2}, {"a": 1}]
    _ = compare(actual, expected, equivalency().ignoring_order())
    assert actual == [{"a": 1}, {"b": 2}]
    assert expected == [{"b": 2}, {"a": 1}]


def test_excluding_wins_over_including() -> None:
    """READING: a member has to clear both gates, and the narrower one decides.

    The other order would let ``including`` resurrect a member somebody had
    explicitly excluded, which is the reading no one would predict from the call.
    """
    options = equivalency().including("id", "name").excluding("name")
    same({"id": 1, "name": "a"}, {"id": 1, "name": "b"}, options)


def test_excluding_and_including_written_the_other_way_round_agree() -> None:
    """READING: a builder is a configuration, not a pipeline; call order is not
    part of the meaning."""
    left = equivalency().including("id", "name").excluding("name")
    right = equivalency().excluding("name").including("id", "name")
    pair = ({"id": 1, "name": "a"}, {"id": 1, "name": "b"})
    assert compare(pair[0], pair[1], left) == compare(pair[0], pair[1], right) == ""


def test_ignoring_order_and_excluding_reach_a_nested_list_of_records() -> None:
    options = equivalency().ignoring_order().excluding("noise")
    actual = {"users": [{"id": 1, "noise": "a"}, {"id": 2, "noise": "b"}]}
    expected = {"users": [{"id": 2, "noise": "z"}, {"id": 1, "noise": "y"}]}
    same(actual, expected, options)


def test_using_and_ignoring_order_hold_together() -> None:
    options = equivalency().ignoring_order().using(float, close_within(0.01))
    same([1.0, 2.0], [2.005, 1.005], options)


def test_every_option_at_once_still_decides_correctly() -> None:
    options = (
        equivalency()
        .excluding("noise")
        .including("id", "at", "noise")
        .ignoring_order()
        .using(datetime, close_within(timedelta(seconds=1)))
        .comparing_enums_by_name()
        .with_max_depth(6)
    )
    base = datetime(2024, 1, 1, 12, 0, 0)
    actual = [{"id": Warm.RED, "at": base, "noise": "a"}]
    expected = [{"id": Signal.RED, "at": base + timedelta(milliseconds=100), "noise": "z"}]
    same(actual, expected, options)
    louder = [{"id": Signal.AMBER, "at": base, "noise": "z"}]
    assert compare(actual, louder, options) != ""


def test_a_non_default_configuration_is_visible_in_the_failure_block() -> None:
    """READING, and the one most likely to be a disagreement.

    The failure message prints the effective configuration, so that a reader who
    excluded the wrong field can see that they did. ``compare``'s block is the
    engine's only output, so that is where it has to be -- unless the orchestrator
    renders it in ``_core`` from the options object instead, which
    ``is_not_equivalent_to`` (where ``compare`` returns ``""``) is an argument for.
    If the engine puts it there, this test is the disagreement, not a bug.
    """
    found = differs(
        {"a": 1, "dropped": 2}, {"a": 9, "dropped": 3}, equivalency().excluding("dropped")
    )
    assert "dropped" in found, found


# ---------------------------------------------------------------------------
# Paths: what is printed is what excluding_path accepts
# ---------------------------------------------------------------------------
def test_an_attribute_path_reads_with_dots_and_round_trips() -> None:
    actual = Person(Address(City("paris")))
    expected = Person(Address(City("lyon")))
    assert mentions(block(actual, expected), "address.city.name")
    same(actual, expected, equivalency().excluding_path("address.city.name"))


def test_an_index_path_reads_with_brackets_and_round_trips() -> None:
    actual = {"items": [0, 1, 2, 3]}
    expected = {"items": [0, 1, 2, 9]}
    assert mentions(block(actual, expected), "items[3]")
    same(actual, expected, equivalency().excluding_path("items[3]"))


def test_a_root_level_index_path_carries_no_leading_name() -> None:
    assert mentions(block([1, 2], [1, 9]), "[1]")
    same([1, 2], [1, 9], equivalency().excluding_path("[1]"))


def test_a_mapping_key_path_round_trips_whichever_spelling_is_chosen() -> None:
    """The round trip is the property; the spelling is the ambiguous part.

    An identifier-like mapping key could be printed as ``rows['id']`` or as
    ``rows.id``. The dot wins, because a reader holding ``{"user": {"city": ...}}``
    writes ``user.city`` and a notation is worth nothing if it is not the one they
    would reach for. This test holds either way, and is the property that actually
    matters: a path a reader can see is a path a reader can paste. The spelling
    itself is pinned in ``tests/test_equivalence.py``, which asserts the whole
    rendered line.
    """
    actual = {"rows": {"id": 1}}
    expected = {"rows": {"id": 2}}
    shown = spelling(block(actual, expected), "rows.id", "rows['id']")
    same(actual, expected, equivalency().excluding_path(shown))


def test_a_non_identifier_key_path_round_trips() -> None:
    actual = {"rows": {"two words": 1}}
    expected = {"rows": {"two words": 2}}
    shown = spelling(block(actual, expected), "rows['two words']", 'rows["two words"]')
    same(actual, expected, equivalency().excluding_path(shown))


def test_a_path_through_a_record_a_mapping_and_a_sequence_round_trips() -> None:
    actual = {"users": [UserRecord("ann", 30)]}
    expected = {"users": [UserRecord("ann", 31)]}
    lines = block(actual, expected)
    assert mentions(lines, "users[0].age"), lines
    same(actual, expected, equivalency().excluding_path("users[0].age"))


def test_a_named_tuple_field_path_round_trips() -> None:
    actual = {"at": Point(1, 2)}
    expected = {"at": Point(1, 9)}
    assert mentions(block(actual, expected), "at.y")
    same(actual, expected, equivalency().excluding_path("at.y"))


# ---------------------------------------------------------------------------
# The never-raises guarantee, swept across every configuration
# ---------------------------------------------------------------------------
HOSTILE_PAIRS: Final[list[tuple[object, object]]] = [
    (Hostile(), Hostile()),
    (Hostile(), 1),
    ([Hostile()], [Hostile()]),
    ({"a": Hostile()}, {"a": Hostile()}),
    ({Hostile: 1}, {Hostile: 2}),
    (Unrenderable(1), Unrenderable(2)),
    (Volatile(1), Volatile(2)),
    (Truthy(), Falsy()),
    (Falsy(), Falsy()),
    (Arrayish(), Arrayish()),
    (Explosive(), Explosive()),
    (Explosive(), [1, 2]),
    (Withholding(), {"a": 1, "b": 2}),
    (Deceitful({"a": 1}, verdict=False), Deceitful({"a": 2}, verdict=True)),
    (BadAttrs(1), BadAttrs(2)),
    (Fibbing((1, 2)), Fibbing((1, 3))),
    (Sparse(1), Sparse(1, 2)),
    (NAN, float("nan")),
    ({NAN: [NAN]}, {NAN: [NAN]}),
    (Point(1, 2), (1, 2)),
    ("ab", ["a", "b"]),
    (object(), object()),
    (type, type),
    (int, str),
    (len, print),
    (nested(2000, 1), nested(2000, 2)),
    (range(10_000), list(range(10_000))),
]

CONFIGURATIONS: Final[list[Equivalency]] = [
    equivalency(),
    equivalency().ignoring_order(),
    equivalency().with_max_depth(0),
    equivalency().with_max_depth(50),
    equivalency().excluding("a", "value", "x"),
    equivalency().excluding_path("a.b[0]"),
    equivalency().including("a"),
    equivalency().comparing_enums_by_name(),
    equivalency().using(int, close_within(1)),
    equivalency().using(object, close_within(1)),
]


@pytest.mark.parametrize("options", CONFIGURATIONS)
@pytest.mark.parametrize(("actual", "expected"), HOSTILE_PAIRS)
def test_compare_never_raises(actual: object, expected: object, options: Equivalency) -> None:
    """Every attempt to make ``compare`` raise is a test, under every configuration."""
    assert isinstance(compare(actual, expected, options), str)


@pytest.mark.parametrize(("actual", "expected"), HOSTILE_PAIRS)
def test_a_hostile_pair_never_costs_more_than_a_moment(actual: object, expected: object) -> None:
    started = time.perf_counter()
    _ = compare(actual, expected, equivalency())
    assert time.perf_counter() - started < 2.0


def test_a_block_produced_from_a_hostile_pair_still_obeys_its_shape() -> None:
    """A degraded answer is still an answer, and still renders like one."""
    for actual, expected in HOSTILE_PAIRS:
        found = compare(actual, expected, equivalency())
        if found:
            assert found.startswith("\n"), (actual, found)
            assert not found.endswith("\n"), (actual, found)
            assert all(line.startswith("  ") for line in found[1:].split("\n")), found


# ---------------------------------------------------------------------------
# The cost of the walk itself: nodes, not paths
# ---------------------------------------------------------------------------
class Shared:
    """A node whose fields are handed in, so a graph can be wired by hand.

    An ordinary object with an instance dictionary and nothing declared, which is
    what makes it a *stored* record to the resolver -- and what stops a type
    checker from knowing any of its members, hence the two accessors.
    """

    def __init__(self, **members: object) -> None:
        self.__dict__.update(members)

    def link(self, name: str, value: object, /) -> None:
        """Add a member after the fact, which is how a backref has to be wired."""
        self.__dict__[name] = value

    def member(self, name: str, /) -> object:
        """One member by name."""
        return self.__dict__[name]


def fan_in(width: int, depth: int, *, backref: bool = False) -> Shared:
    """``depth`` levels, each holding *one* shared child under ``width`` names.

    Nine objects at width four and depth eight -- and 4**8 paths through them,
    which is what an engine with a cycle memo and no visited memo pays. Only the
    number of paths is exponential; nothing here is deep, wide or unusual. A
    parent backref, which ``backref`` adds, is the same shape with a cycle in it.
    """
    node = Shared(leaf=1)
    for _ in range(depth):
        shared = node
        node = Shared(**{f"f{index}": shared for index in range(width)})
        if backref:
            shared.link("parent", node)
    return node


def classify_calls(
    actual: object, expected: object, options: Equivalency, monkeypatch: pytest.MonkeyPatch, /
) -> tuple[int, str]:
    """How many nodes the walk resolved, and what it decided.

    ``_classify`` runs exactly twice for every pair the walk takes apart and not
    at all for one ``==`` settles, so counting it counts the walk in a unit that
    is the same on every machine. A wall-clock assertion here would be a flaky
    test wearing a useful disguise -- see ``tests/test_performance_invariants.py``.
    """
    from lovely_assertions import _equivalence

    resolve = getattr(_equivalence, "_classify")  # noqa: B009  (a private name, read as data)
    calls = 0

    def counted(value: object, /) -> tuple[str, tuple[str, ...]]:
        nonlocal calls
        calls += 1
        return cast("tuple[str, tuple[str, ...]]", resolve(value))

    monkeypatch.setattr(_equivalence, "_classify", counted)
    # Two statements rather than one tuple: the elements of a tuple are evaluated
    # left to right, so `return calls, compare(...)` reads the counter before the
    # comparison runs and reports zero however slow the walk was.
    verdict = compare(actual, expected, options)
    return calls, verdict


#: Comfortably above the few dozen a settled-pair memo needs for the graphs
#: below, and four orders of magnitude below what walking every path costs.
_NODE_BUDGET: Final = 500


def test_a_graph_of_shared_children_costs_its_nodes_and_not_its_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hang: ordinary objects, default options, and the comparison *passes*.

    Nine objects, tens of thousands of paths through them. The cycle memo discards
    a pair the moment its frame returns -- which is right for a cycle and useless
    as a visited memo -- so with nothing else remembering anything the cost follows
    the paths rather than the nodes, and a graph this small takes minutes to say
    "equivalent", with no message and nothing to read, on a test about to go green.
    """
    left, right = fan_in(4, 8), fan_in(4, 8)
    calls, verdict = classify_calls(left, right, equivalency().with_max_depth(60), monkeypatch)
    assert verdict == "", verdict
    assert calls < _NODE_BUDGET, f"took {calls} resolutions for a graph of nine objects"


def test_a_parent_backref_does_not_bring_the_cost_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same shape with a cycle in it, which is the ordinary way to write it.

    Every field of a node whose child points back at it reaches a verdict that
    leans on the node's own still-open assumption. A memo that refused to record
    those would be correct and would leave this graph as costly as no memo at all.
    """
    left, right = fan_in(4, 8, backref=True), fan_in(4, 8, backref=True)
    calls, verdict = classify_calls(left, right, equivalency().with_max_depth(60), monkeypatch)
    assert verdict == "", verdict
    assert calls < _NODE_BUDGET, f"took {calls} resolutions for a graph of nine objects"


def test_excluding_a_path_costs_the_memo_only_on_the_branch_it_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A path-sensitive option must not put the hang back everywhere.

    A verdict remembered under a key that says nothing about where the pair was
    reached is only sound when where it was reached cannot change it, and
    ``excluding_path`` is the one option that can. Switching the memo off for the
    whole comparison would be the easy answer and would put the cost of every path
    back; switching it off for the named branch is the true one.
    """
    left, right = fan_in(4, 8), fan_in(4, 8)
    options = equivalency().with_max_depth(60).excluding_path("f0.f1.f2")
    calls, verdict = classify_calls(left, right, options, monkeypatch)
    assert verdict == "", verdict
    assert calls < _NODE_BUDGET, f"took {calls} resolutions with one path excluded"


def test_a_pair_settled_shallow_does_not_answer_for_the_same_pair_deep() -> None:
    """The depth belongs in the key, because it belongs in the answer.

    ``near`` and ``far`` end at the same pair, one level down and four. At four the
    depth bound stops the walk, and "I stopped here" is a finding; at one it is
    taken apart and found equivalent. A key naming only the pair would hand the
    shallow verdict to the deep reach and the bound would go unreported -- which is
    ``is_equivalent_to`` passing on a comparison that never happened.
    """

    def graph() -> Shared:
        deepest = Shared(leaf=1)
        chain = Shared(x=Shared(x=Shared(x=deepest)))
        root = Shared()
        root.link("near", deepest)
        root.link("far", chain)
        return root

    lines = block(graph(), graph(), equivalency().with_max_depth(4))

    assert mentions(lines, "far.x.x.x"), lines
    assert mentions(lines, "maximum depth of 4"), lines


def test_the_memo_is_not_consulted_across_two_comparisons() -> None:
    """It belongs to one comparison, so nothing it learned can outlive one."""
    left, right = fan_in(3, 4), fan_in(3, 4)
    assert compare(left, right, equivalency()) == ""
    deepest = right
    for _ in range(3):
        deepest = cast("Shared", deepest.member("f0"))
    deepest.link("leaf", 99)
    assert compare(left, right, equivalency()) != ""


def test_a_settled_entry_holds_the_pair_whose_identities_name_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one defence against ``id`` reuse, asserted rather than reasoned about.

    A settled verdict is keyed on two ``id``s and outlives the frames that held
    the objects, which the cycle memo never does. A value built on the way past --
    a property returning a fresh object, a field read nothing else keeps -- could
    therefore be collected and have its identity handed to an unrelated object,
    and the next pair to land on those two numbers would be called equivalent
    without being looked at. That is a wrong *pass*.

    What stops it is that each entry's value is the pair itself, so both objects
    stay alive, and their ``id``s stay unusable by anything else, for as long as
    the entry does. Nothing else in the file can see that, because the failure it
    prevents needs a collection at exactly the wrong moment.
    """
    from lovely_assertions import _equivalence

    build = getattr(_equivalence, "_Memo")  # noqa: B009  (a private name, read as data)
    made: list[object] = []

    def capture() -> object:
        memo = build()
        made.append(memo)
        return memo

    monkeypatch.setattr(_equivalence, "_Memo", capture)
    left, right = fan_in(3, 4, backref=True), fan_in(3, 4, backref=True)
    assert compare(left, right, equivalency().with_max_depth(60)) == ""

    settled = cast("dict[tuple[int, int, int], object]", getattr(made[0], "settled"))  # noqa: B009
    assert settled, "nothing was settled, so this asserts nothing about the entries"
    for (left_id, right_id, _depth), held in settled.items():
        pair = cast("tuple[object, object]", held)
        assert (id(pair[0]), id(pair[1])) == (left_id, right_id), (
            "an entry that does not hold its own pair leaves both ids free to be reused"
        )


# ---------------------------------------------------------------------------
# The memo must never turn a difference into an equivalence
# ---------------------------------------------------------------------------
class Cell:
    """Two members, so that one can cycle and the other can disagree."""

    __slots__ = ("into", "tag")

    into: "Ring"
    tag: int

    def __init__(self, tag: int, /) -> None:
        self.tag = tag


class Ring:
    """The other half of the cycle: it points straight back at its ``Cell``."""

    __slots__ = ("back",)

    back: Cell


class Holder:
    """A third route to the same ``Ring``, reached without the ``Cell`` above it."""

    __slots__ = ("inner",)

    inner: Ring


def ring(tag: int, /) -> tuple[Cell, Ring]:
    cell, loop = Cell(tag), Ring()
    cell.into, loop.back = loop, cell
    return cell, loop


def test_a_verdict_reached_under_a_cycle_assumption_is_not_kept_when_it_fails() -> None:
    """The wrong pass a settled-pair memo makes available, and the guard against it.

    Taking the cycle branch answers "equivalent" by *assuming* the pair further up
    the stack is equivalent, and an assumption is not a result. Here a pairing
    probe compares two ``Cell``s, settles their two ``Ring``s along the way while
    leaning on that assumption, and only then finds that the ``Cell``s' tags
    disagree. A memo that had kept the ``Ring`` verdict would hand it to the next
    probe, the two ``Holder``s would pair off, every item would find a partner and
    the comparison would come back **equivalent** -- which it is not.

    Remove the promote-or-drop bookkeeping in ``_by_structure`` and this comes back
    ``""``; it is the only test here that does.
    """
    left_cell, left_ring = ring(0)
    right_cell, right_ring = ring(1)
    twin_of_right, _ = ring(1)
    twin_of_left, _ = ring(0)
    left_holder, right_holder = Holder(), Holder()
    left_holder.inner, right_holder.inner = left_ring, right_ring

    _ = differs(
        [left_cell, left_holder, twin_of_right],
        [right_cell, right_holder, twin_of_left],
        equivalency().ignoring_order(),
    )


def excluded_branch_graph(tag: str, /, *, leans_on: str) -> Shared:
    """A graph where one exclusion decides a verdict that is then reused elsewhere.

    ``root.a`` is the node whose ``tag`` the caller excludes. Its child ``b``
    points back at it, and ``root.d`` reaches that same ``b`` by a second route
    that no exclusion touches. So the pair under ``b`` is settled once inside the
    excluded branch and asked for again outside it, at the same depth, which is
    the whole of the trap.

    ``leans_on`` names which still-open assumptions ``b``'s verdict rests on, by
    adding backrefs. It changes nothing about what the graph *means* and everything
    about which line of the bookkeeping is doing the work:

    ``"the excluded frame"`` -- ``b`` leans on ``a`` alone, so the frame at ``a``
    is the one that discharges the assumption and the drop happens on its promoting
    exit. ``"the root as well"`` -- the shallowest assumption is the root's, so
    ``a`` merely passes the verdict up and the drop has to happen on that exit too;
    bookkeeping that covers only the first exit leaves this shape passing.
    ``"itself as well"`` -- ``b``'s own subtree reaches back to ``b``, so the
    shallowest assumption and the deepest one differ, and only because
    ``_Memo.lean_on`` keeps the shallowest does ``a`` ever see that the root was
    involved.
    """
    root, marked, shared, second = Shared(), Shared(tag=tag), Shared(), Shared()
    root.link("a", marked)
    root.link("d", second)
    marked.link("b", shared)
    shared.link("a", marked)
    if leans_on != "the excluded frame":
        shared.link("d", root)
    if leans_on == "itself as well":
        loop = Shared()
        shared.link("c", loop)
        loop.link("a", shared)
    second.link("a", shared)
    return root


@pytest.mark.parametrize("leans_on", ["the excluded frame", "the root as well", "itself as well"])
def test_an_exclusion_does_not_settle_a_pair_for_the_branches_it_does_not_name(
    leans_on: str,
) -> None:
    """The other wrong pass a settled-pair memo makes available, through an option.

    ``excluding_path("a.tag")`` says nothing about ``d``, so the disagreement at
    ``d.a.a.tag`` has to be reported. What loses it: the frame at ``a`` finishes
    clean *because* its ``tag`` was excluded, the child that points back at it
    takes the cycle branch on the strength of that, and a verdict reached that way
    goes into the memo under a key naming only the pair and its depth -- then
    answers for the same pair at ``d.a``, where nothing is excluded.

    Withholding a key from the frame the exclusion names is not enough, which is
    what makes this worth three cases rather than one: what a frame settles
    *beneath* it has to go too, on both of the exits it can take, and the
    bookkeeping only reaches that frame at all because the assumption it records is
    the shallowest one leaned on rather than the latest.
    """
    left = excluded_branch_graph("LEFT", leans_on=leans_on)
    right = excluded_branch_graph("RIGHT", leans_on=leans_on)
    lines = block(left, right, equivalency().excluding_path("a.tag"))

    assert mentions(lines, "d.a.a.tag"), lines
    assert mentions(lines, "'LEFT' instead of 'RIGHT'"), lines


def test_the_excluded_path_itself_is_still_excluded() -> None:
    """The control: the option still does what it says on the branch it names.

    Without this, a fix that simply stopped honouring ``excluding_path`` would pass
    the test above.
    """
    left = excluded_branch_graph("LEFT", leans_on="the excluded frame")
    right = excluded_branch_graph("RIGHT", leans_on="the excluded frame")
    lines = block(left, right, equivalency().excluding_path("a.tag"))

    # Startswith rather than `mentions`, because `d.a.a.tag:` carries `a.tag:`.
    assert not any(line.strip().startswith("a.tag:") for line in lines), lines
    same(left, right, equivalency().excluding_path("a.tag", "d"))


# ---------------------------------------------------------------------------
# Running out of stack is not a verdict either
# ---------------------------------------------------------------------------
class Link:
    """One link of a chain as long as the caller likes."""

    __slots__ = ("child", "tag")

    def __init__(self, child: "Link | None", /) -> None:
        self.child = child
        self.tag = "t"


def chain(length: int, /) -> Link:
    node = Link(None)
    for _ in range(length - 1):
        node = Link(node)
    return node


def test_a_walk_that_runs_out_of_stack_raises_instead_of_reporting_a_difference() -> None:
    """A ``RecursionError`` is not a statement about the values.

    Caught by ``compare``'s blanket handler, it comes back as "the comparison could
    not be completed, so the two are not equivalent" -- which
    ``is_not_equivalent_to`` reads as *they differ* and **passes**. Two identical
    chains and a ``with_max_depth`` long enough to exhaust the stack are then a
    silent green.

    The rule is ``_TruncatedError``'s, applied to the other way a walk can stop
    without finishing: an unfinished comparison is not a verdict, in either
    direction, so it leaves as a ``ValueError`` that both assertions see alike.
    """
    left, right = chain(400), chain(400)
    options = equivalency().with_max_depth(500)
    with pytest.raises(ValueError, match="used up the interpreter's stack"):
        _ = compare(left, right, options)


def test_the_same_chain_inside_the_stack_is_answered_rather_than_refused() -> None:
    """The control: it is the stack that ran out, not the graphs that differ."""
    same(chain(60), chain(60), equivalency().with_max_depth(500))
