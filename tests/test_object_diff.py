"""Field-level differences between two objects.

``tests/test_diff.py`` covers the engine's four container describers. This file
covers the fifth, which exists because an object is the one composite where
pytest's assert rewriting would otherwise say more than a pair of reprs does:

    ours    Expected user to equal User(name='ann', age=31, admin=False),
            but was User(name='ann', age=30, admin=False).
    pytest  Differing attributes: ['age']

Two properties get more attention than the rest, because each of them is a wrong
answer rather than a missing one.

*The right resolver has to answer.* A dataclass, a NamedTuple, a ``__slots__``
class and a plain object each keep their fields somewhere else, and three of the
four are also something the engine has a container describer for. Picking the
wrong one produces a block that is confidently about the wrong thing -- "index 0"
for a field called ``x``, a difference in a ``field(compare=False)`` that ``==``
never looked at, ``__pydantic_fields_set__`` in place of the fields somebody
wrote.

*It never raises.* A property that explodes, a slot that was never assigned, an
object that contains itself: each costs the reader detail, never an error in
place of their assertion failure.
"""

from dataclasses import InitVar, dataclass, field, make_dataclass
from enum import Enum, IntEnum, StrEnum
from typing import Any, ClassVar, Final, NamedTuple

import pytest

from lovely_assertions import AssertionFailure, expect
from lovely_assertions._diff import describe_difference


def block(actual: object, expected: object, /) -> list[str]:
    """The rendered lines, with the leading newline stripped."""
    rendered = describe_difference(actual, expected)
    assert rendered.startswith("\n")
    return rendered[1:].split("\n")


@dataclass
class User:
    """The headline case: three fields, one of them wrong."""

    name: str
    age: int
    admin: bool = False


@dataclass
class Admin:
    """Same fields, different type -- and so never equal to a ``User``."""

    name: str
    age: int
    admin: bool = False


class Point(NamedTuple):
    """A record that is also a tuple, which is the whole trap."""

    x: int
    y: int


class Slotted:
    """A hand-written value type: ``__slots__``, and an ``__eq__`` to match."""

    __slots__ = ("host", "port")

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Slotted):
            return NotImplemented
        return (self.host, self.port) == (other.host, other.port)

    def __hash__(self) -> int:
        return hash((self.host, self.port))

    def __repr__(self) -> str:
        return "Slotted(" + repr(self.host) + ", " + repr(self.port) + ")"


class Coord(NamedTuple):
    """The same two names as :class:`Point`, under a different class."""

    x: int
    y: int


class Pair(NamedTuple):
    """The same two *slots* as :class:`Point`, under different names."""

    a: int
    b: int


@dataclass
class Node:
    """A record that can hold itself, which its generated ``__eq__`` does not enjoy."""

    name: str
    parent: "Node | None" = None


class Bag:
    """A plain object: state in ``__dict__``, and an ``__eq__`` that reads it."""

    def __init__(self, **members: object) -> None:
        self.__dict__.update(members)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Bag):
            return NotImplemented
        return vars(self) == vars(other)

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "Bag(" + ", ".join(sorted(vars(self))) + ")"


# ---------------------------------------------------------------------------
# The headline: a dataclass says which field
# ---------------------------------------------------------------------------
def test_a_dataclass_names_the_field_that_differs() -> None:
    assert block(User("ann", 30), User("ann", 31)) == ["  field age: 30 instead of 31"]


def test_every_differing_field_is_named_in_declaration_order() -> None:
    assert block(User("ann", 30), User("bob", 31, admin=True)) == [
        "  field name: 'ann' instead of 'bob'",
        "  field age: 30 instead of 31",
        "  field admin: False instead of True",
    ]


def test_the_user_facing_message_carries_the_block() -> None:
    """The wiring, end to end: this is the message that beats pytest's."""
    user = User("ann", 30)
    with pytest.raises(AssertionFailure) as caught:
        expect(user).is_equal_to(User("ann", 31))
    assert str(caught.value) == (
        "Expected user to equal User(name='ann', age=31, admin=False),"
        " but was User(name='ann', age=30, admin=False).\n"
        "  field age: 30 instead of 31"
    )


# ---------------------------------------------------------------------------
# Which resolver answers
# ---------------------------------------------------------------------------
def test_a_field_the_generated_eq_ignores_is_not_reported() -> None:
    """``field(compare=False)`` is invisible to ``__eq__``, so it is invisible here.

    Reporting it would have this module contradict the very comparison that
    produced the failure, on precisely the type it was written for.
    """

    @dataclass
    class Cached:
        key: str
        hits: int = field(default=0, compare=False)

    assert block(Cached("a", 1), Cached("b", 99)) == ["  field key: 'a' instead of 'b'"]


def test_two_values_differing_only_in_an_ignored_field_are_not_described() -> None:
    """They are *equal*. The block would be describing a difference that is not one."""

    @dataclass
    class Cached:
        key: str
        hits: int = field(default=0, compare=False)

    assert Cached("a", 1) == Cached("a", 2)
    assert describe_difference(Cached("a", 1), Cached("a", 2)) == ""


def test_class_variables_and_init_variables_are_not_fields() -> None:
    """``dataclasses.fields`` drops both; a read of ``__dataclass_fields__`` would not."""

    @dataclass
    class Configured:
        value: int
        kind: ClassVar[str] = "settings"
        seed: InitVar[int] = 0

        def __post_init__(self, seed: int) -> None:
            del seed

    assert block(Configured(1), Configured(2)) == ["  field value: 1 instead of 2"]


def test_a_named_tuple_names_the_field_rather_than_the_index() -> None:
    """The trap this describer exists to avoid.

    A NamedTuple *is* a tuple, so the sequence describer claims it -- and left to
    itself it reports "index 0" for a field the reader calls ``x`` and has never
    indexed by hand. It reads the names from inside that branch for this reason
    alone.
    """
    assert block(Point(1, 2), Point(2, 1)) == [
        "  field x: 1 instead of 2",
        "  field y: 2 instead of 1",
    ]


def test_a_named_tuple_against_a_plain_tuple_stays_on_indices() -> None:
    """One side has no names, so there are none to report."""
    assert block(Point(1, 2), (2, 1)) == [
        "  first difference at index 0: 1 instead of 2",
        "  the same items, in a different order",
    ]


def test_two_named_tuples_of_different_classes_are_still_diffed_by_name() -> None:
    """``tuple.__eq__`` ignores the class, so the class is not why these failed.

    Both sides declare ``x`` and ``y``; the values are what parted company, and
    a note about the two types would be an account of the failure that is not
    true -- as the equality on the first line proves.
    """
    a_coord: object = Coord(1, 2)
    assert Point(1, 2) == a_coord
    assert block(Point(1, 2), Coord(1, 9)) == ["  field y: 2 instead of 9"]


def test_named_tuples_that_do_not_share_their_names_stay_on_indices() -> None:
    """One side's names would be a false label for the other side's values."""
    a_pair: object = Pair(1, 2)
    assert Point(1, 2) == a_pair
    assert block(Point(1, 2), Pair(1, 9)) == ["  first difference at index 1: 2 instead of 9"]


def test_named_tuples_of_different_lengths_are_told_that() -> None:
    """The arity is why ``tuple.__eq__`` refused them, and the names cannot say so.

    ``Triple`` declares ``Point``'s two names and one more, so reading ``Point``'s
    names off it succeeds -- and a resolver that settled for that would report a
    field and never mention the third item, which is the actual finding.
    """

    class Triple(NamedTuple):
        x: int
        y: int
        z: int

    assert block(Point(1, 2), Triple(1, 9, 3)) == [
        "  first difference at index 1: 2 instead of 9",
        "  lengths differ: 2 items, expected 3",
        "  missing items: [9, 3]",
        "  extra items: [2]",
    ]


def test_a_tuple_subclass_that_declares_fields_it_does_not_carry_keeps_its_indices() -> None:
    """``_fields`` is an ordinary class attribute; any tuple subclass may set it.

    Reading it yields nothing here, and an empty block is worse than the index
    diff the sequence describer would have produced.
    """

    class Liar(tuple[int, ...]):
        __slots__ = ()
        _fields: ClassVar[tuple[str, ...]] = ("x", "y")

    assert block(Liar((1, 2)), Liar((1, 9))) == ["  first difference at index 1: 2 instead of 9"]


def test_a_slots_class_is_read_through_its_slots() -> None:
    assert block(Slotted("prod", 8080), Slotted("prod", 443)) == [
        "  field port: 8080 instead of 443"
    ]


def test_inherited_slots_are_included() -> None:
    """A subclass declares only what it adds; reading one class drops the rest."""

    class Base:
        __slots__ = ("a",)

    class Child(Base):
        __slots__ = ("b",)

        def __init__(self, a: int, b: int) -> None:
            self.a = a
            self.b = b

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Child):
                return NotImplemented
            return (self.a, self.b) == (other.a, other.b)

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Child()"

    assert block(Child(1, 2), Child(9, 2)) == ["  field a: 1 instead of 9"]
    # Base first, the order the fields were declared in -- an MRO walked the
    # other way round reports the same two fields with the subclass's on top.
    assert block(Child(1, 2), Child(9, 8)) == [
        "  field a: 1 instead of 9",
        "  field b: 2 instead of 8",
    ]


def test_a_slots_base_with_a_plain_subclass_reports_both_storages() -> None:
    """The subclass did not repeat ``__slots__``, so it has one of each.

    Racing the two resolvers reports the base's field and stays silent about the
    subclass's -- an incomplete answer that reads exactly like a complete one.
    """

    class Base:
        __slots__ = ("a",)

    class Child(Base):
        def __init__(self, a: int, b: int) -> None:
            self.a = a
            self.b = b

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Child):
                return NotImplemented
            return (self.a, self.b) == (other.a, other.b)

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Child()"

    assert Child.__slots__ == ("a",)
    assert vars(Child(1, 2)) == {"b": 2}
    assert block(Child(1, 2), Child(9, 9)) == [
        "  field a: 1 instead of 9",
        "  field b: 2 instead of 9",
    ]


def test_slots_declared_as_a_bare_string_is_one_field_not_four_letters() -> None:
    class Single:
        __slots__ = "only"  # noqa: PLC0205  (that spelling is what this test is about)

        def __init__(self, only: int) -> None:
            self.only = only

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Single):
                return NotImplemented
            return self.only == other.only

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Single()"

    assert block(Single(1), Single(2)) == ["  field only: 1 instead of 2"]


def test_a_field_called_underscore_is_a_field_and_not_bookkeeping() -> None:
    """The reserved spellings need two characters; ``_`` on its own is a name."""

    class Under:
        __slots__ = ("_",)

        def __init__(self, value: int) -> None:
            self._ = value

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Under):
                return NotImplemented
            return self._ == other._

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Under()"

    assert block(Under(1), Under(2)) == ["  field _: 1 instead of 2"]


def test_a_plain_object_is_read_through_its_instance_dictionary() -> None:
    assert block(Bag(host="prod", port=8080), Bag(host="prod", port=443)) == [
        "  field port: 8080 instead of 443"
    ]


def test_an_attrs_shaped_class_needs_no_attrs() -> None:
    """``@define`` produces slots and an ``__eq__``; both resolvers already exist.

    Shaped by hand rather than imported, because the library has zero runtime
    dependencies and this must keep working without the optional one installed.

    The ``__attrs_attrs__`` here is a tuple of plain strings, which is *not* what
    ``attrs`` builds -- it builds ``Attribute`` objects. So this covers the
    fallback: a declaration the field resolver cannot read leaves it to
    ``__slots__``, and the answer is the same. The real shape is
    :func:`test_an_attrs_field_excluded_from_eq_is_not_reported`.
    """

    class Defined:
        __attrs_attrs__: ClassVar[tuple[str, ...]] = ("x", "y")
        __slots__ = ("x", "y")

        def __init__(self, x: int, y: int) -> None:
            self.x = x
            self.y = y

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Defined):
                return NotImplemented
            return (self.x, self.y) == (other.x, other.y)

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Defined()"


class _AttrsAttribute:
    """The duck ``attrs`` presents: a name and an ``eq`` flag."""

    __slots__ = ("eq", "name")

    def __init__(self, name: str, *, eq: bool = True) -> None:
        self.name = name
        self.eq = eq


def test_an_attrs_field_excluded_from_eq_is_not_reported() -> None:
    """``eq=False`` is ``attrs`` spelling ``field(compare=False)``, and it binds here too.

    The describer's whole job is to say what made ``==`` answer no. A field that
    ``__eq__`` never read cannot have, so reporting it points the reader at a
    difference that is real and irrelevant -- under a heading that says the two
    objects are unequal, which is the one place a true fact reads as a cause.

    ``is_equal_to`` and ``is_equivalent_to`` have to answer this identically,
    and they do because ``_diff`` and ``_equivalence`` read fields through one
    shared module -- ``_reflection``. A second copy of the resolvers is how the
    two drift apart: teach one of them ``__attrs_attrs__`` and the same class
    gets the rule from one entry point and not from the other.
    """

    class Connection:
        __slots__ = ("cached", "host")
        __attrs_attrs__: Final = (
            _AttrsAttribute("host"),
            _AttrsAttribute("cached", eq=False),
        )

        def __init__(self, host: str, cached: int) -> None:
            self.host = host
            self.cached = cached

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Connection):
                return NotImplemented
            return self.host == other.host

        def __hash__(self) -> int:
            return hash(self.host)

        def __repr__(self) -> str:
            return "Connection()"

    with pytest.raises(AssertionFailure) as caught:
        expect(Connection("a", 1)).is_equal_to(Connection("b", 2))

    lines = str(caught.value).splitlines()[1:]
    assert lines == ["  field host: 'a' instead of 'b'"], lines


def test_a_pydantic_shaped_model_is_read_through_its_dict_not_its_slots() -> None:
    """pydantic v2's ``BaseModel`` declares ``__slots__``, and none of it is a field.

    ``__slots__ = '__dict__', '__pydantic_fields_set__', '__pydantic_extra__',
    '__pydantic_private__'`` -- storage and bookkeeping, with the field values in
    the instance dictionary the first entry asks for. A slot resolver that kept
    the dunders would answer first and report a difference in
    ``__pydantic_fields_set__`` instead of in the fields somebody wrote.
    """

    class Model:
        __slots__ = ("__dict__", "__pydantic_extra__", "__pydantic_fields_set__")

        def __init__(self, **values: object) -> None:
            self.__dict__.update(values)
            self.__pydantic_fields_set__ = set(values)
            self.__pydantic_extra__ = None

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Model):
                return NotImplemented
            return self.__dict__ == other.__dict__

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Model()"

    assert block(Model(name="ann", age=30), Model(name="ann", age=31)) == [
        "  field age: 30 instead of 31"
    ]


# ---------------------------------------------------------------------------
# The containers keep their own describers
# ---------------------------------------------------------------------------
def test_a_list_subclass_carrying_an_attribute_is_still_diffed_as_a_list() -> None:
    """``list.__eq__`` compares items and nothing else, so the block must too."""

    class Tagged(list[int]):
        def __init__(self, items: list[int], tag: str) -> None:
            super().__init__(items)
            self.tag = tag

    assert block(Tagged([1, 2], "a"), Tagged([1, 9], "b")) == [
        "  first difference at index 1: 2 instead of 9"
    ]


def test_a_dict_subclass_carrying_an_attribute_is_still_diffed_as_a_mapping() -> None:
    class Tagged(dict[str, int]):
        def __init__(self, entries: dict[str, int], tag: str) -> None:
            super().__init__(entries)
            self.tag = tag

    assert block(Tagged({"a": 1}, "x"), Tagged({"a": 2}, "y")) == [
        "  values differ at key 'a': 1 instead of 2"
    ]


# ---------------------------------------------------------------------------
# Two different types
# ---------------------------------------------------------------------------
def test_two_unrelated_types_are_named_and_not_diffed() -> None:
    """Every generated ``__eq__`` refuses a different class outright.

    So no arrangement of the fields would have made these equal, and a
    field-by-field diff would bury the one finding there is.
    """
    # Widened so that the claim survives a checker clever enough to notice that
    # the two can never be equal. That is exactly what is being asserted.
    an_admin: object = Admin("ann", 30)
    assert User("ann", 30) != an_admin
    assert block(User("ann", 30), Admin("ann", 31)) == ["  types differ: User instead of Admin"]


def test_a_named_tuple_against_a_dataclass_is_a_type_difference() -> None:
    assert block(Point(1, 2), User("ann", 30)) == ["  types differ: Point instead of User"]


def test_a_subclass_whose_eq_compares_across_the_two_types_still_gets_its_fields() -> None:
    """ "Types differ" is true here, and on its own it would be a false explanation.

    A hand-written ``isinstance``-based ``__eq__`` compares a ``Cash`` to a
    ``Money`` happily -- the equality on the first line proves it -- so the
    reader sent hunting for a construction bug would be hunting for nothing. The
    amount is what is wrong, and the block has to say so.
    """

    class Money:
        __slots__ = ("amount", "currency")

        def __init__(self, amount: int, currency: str) -> None:
            self.amount = amount
            self.currency = currency

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Money):
                return NotImplemented
            return (self.amount, self.currency) == (other.amount, other.currency)

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return type(self).__name__ + "()"

    class Cash(Money):
        __slots__ = ()

    same_amount: object = Cash(1, "EUR")
    assert Money(1, "EUR") == same_amount
    assert block(Money(1, "EUR"), Cash(2, "EUR")) == [
        "  types differ: Money instead of Cash",
        "  field amount: 1 instead of 2",
    ]


def test_a_subclass_that_adds_a_field_is_not_told_it_is_missing_one() -> None:
    """Declaring a field the base does not is what subclassing *is*, not a finding."""

    @dataclass
    class Base:
        name: str

    @dataclass
    class Extended(Base):
        extra: int = 0

    assert block(Base("ann"), Extended("bob", 1)) == [
        "  types differ: Base instead of Extended",
        "  field name: 'ann' instead of 'bob'",
    ]


def test_a_metaclass_that_refuses_a_subclass_check_costs_only_the_field_half() -> None:
    """``issubclass`` runs somebody else's code, and it is not the whole block."""

    class Rude(type):
        def __subclasscheck__(cls, subclass: type) -> bool:
            raise RuntimeError("subclass check exploded")

    class Left(metaclass=Rude):
        def __init__(self) -> None:
            self.x = 1

        def __eq__(self, other: object) -> bool:
            return False

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Left()"

    class Right(metaclass=Rude):
        def __init__(self) -> None:
            self.x = 2

        def __eq__(self, other: object) -> bool:
            return False

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Right()"

    with pytest.raises(RuntimeError):
        _ = issubclass(Left, Right)
    assert block(Left(), Right()) == ["  types differ: Left instead of Right"]


def test_two_classes_of_the_same_name_are_told_apart_by_their_module() -> None:
    """The bare name is no help here, and neither are the two reprs above it."""

    def define() -> type[Any]:
        @dataclass
        class Thing:
            x: int

        return Thing

    first = define()
    second = define()
    assert first.__name__ == second.__name__ == "Thing"
    assert block(first(1), second(1)) == [
        "  types differ: both are called "
        + first.__module__
        + "."
        + first.__qualname__
        + ", but they are not the same class object"
    ]


def test_a_type_difference_is_silent_when_only_one_side_is_an_object() -> None:
    """``3`` resolves no fields, so there is no field-level claim to make at all."""
    assert describe_difference(User("ann", 30), 3) == ""
    assert describe_difference(3, User("ann", 30)) == ""


# ---------------------------------------------------------------------------
# Fields only one side carries
# ---------------------------------------------------------------------------
def test_attributes_only_one_side_carries_are_named_as_missing_and_extra() -> None:
    """Only reachable through ``vars``: elsewhere the field set belongs to the class."""
    assert block(Bag(a=1, b=2), Bag(a=1, c=2)) == [
        "  missing fields: ['c']",
        "  extra fields: ['b']",
    ]


def test_a_wrong_value_is_reported_before_a_missing_field() -> None:
    assert block(Bag(a=1, b=2), Bag(a=9, c=2)) == [
        "  field a: 1 instead of 9",
        "  missing fields: ['c']",
        "  extra fields: ['b']",
    ]


# ---------------------------------------------------------------------------
# Nesting, inside the depth budget
# ---------------------------------------------------------------------------
def test_an_object_under_a_key_is_descended_into() -> None:
    assert block({"p": Point(1, 2)}, {"p": Point(1, 9)}) == [
        "  values differ at key 'p':",
        "    field y: 2 instead of 9",
    ]


def test_an_object_in_a_sequence_is_descended_into() -> None:
    assert block([Point(1, 2)], [Point(1, 9)]) == [
        "  first difference at index 0:",
        "    field y: 2 instead of 9",
    ]


def test_a_mapping_under_a_field_is_descended_into() -> None:
    assert block(Bag(config={"a": 1}), Bag(config={"a": 2})) == [
        "  field config:",
        "    values differ at key 'a': 1 instead of 2",
    ]


def test_nesting_stops_at_the_depth_limit() -> None:
    """Past two levels the pair is rendered inline, exactly as a mapping is."""

    @dataclass
    class Leaf:
        v: int

        def __repr__(self) -> str:
            return "Leaf(" + str(self.v) + ")"

    @dataclass
    class Inner:
        leaf: Leaf

    @dataclass
    class Middle:
        inner: Inner

    @dataclass
    class Outer:
        middle: Middle

    assert block(Outer(Middle(Inner(Leaf(1)))), Outer(Middle(Inner(Leaf(2))))) == [
        "  field middle:",
        "    field inner:",
        "      field leaf: Leaf(1) instead of Leaf(2)",
    ]


# ---------------------------------------------------------------------------
# Bounded output
# ---------------------------------------------------------------------------
#: One more than the ten items every other describer in the module shows.
_WIDE: Final = 11


def test_two_hundred_fields_do_not_print_two_hundred_lines() -> None:
    wide = make_dataclass("Wide", [("f" + str(index), int) for index in range(200)])
    lines = block(wide(*range(200)), wide(*range(1000, 1200)))
    assert len(lines) == 11
    assert lines[0] == "  field f0: 0 instead of 1000"
    assert lines[9] == "  field f9: 9 instead of 1009"
    assert lines[10] == "  ... (190 more fields hold a different value)"


def test_the_count_of_elided_fields_has_a_singular() -> None:
    wide = make_dataclass("Wide", [("f" + str(index), int) for index in range(_WIDE)])
    lines = block(wide(*range(_WIDE)), wide(*range(100, 100 + _WIDE)))
    assert lines[-1] == "  ... (1 more field holds a different value)"


def test_an_over_long_field_value_is_clipped_with_a_count() -> None:
    assert block(Bag(body=b"y" * 400), Bag(body=b"z" * 300)) == [
        "  field body: b'"
        + "y" * 118
        + "... (283 more characters)"
        + " instead of b'"
        + "z" * 118
        + "... (183 more characters)"
    ]


# ---------------------------------------------------------------------------
# A type that compares by identity
# ---------------------------------------------------------------------------
def test_a_type_without_an_eq_gets_no_field_diff() -> None:
    """The fields are not why it failed and never could be.

    Two instances of a type that compares by identity are unequal however their
    fields read, so a list of differing fields would read as the explanation for
    a failure it has nothing to do with. The look-alike clause says the thing
    that is actually wrong, when the two reprs let it.
    """

    class Bare:
        __slots__ = ("x",)

        def __init__(self, x: int) -> None:
            self.x = x

        def __repr__(self) -> str:
            return "Bare(" + str(self.x) + ")"

    assert describe_difference(Bare(1), Bare(2)) == ""
    assert block(Bare(1), Bare(1)) == [
        "  both render as Bare(1), but Bare does not define __eq__, so they compare by identity"
    ]


# ---------------------------------------------------------------------------
# Nothing to say
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (3, 4),
        (None, 4),
        (len, print),
        (object(), object()),
        (ValueError("a"), ValueError("b")),
    ],
)
def test_values_that_resolve_no_fields_are_left_to_their_reprs(
    actual: object, expected: object
) -> None:
    assert describe_difference(actual, expected) == ""


def test_an_enum_member_never_reports_the_names_the_enum_module_reserves() -> None:
    """``_name_``, ``_value_`` and ``_sort_order_`` are bookkeeping, not fields.

    Only a mixin enum reaches the object describer at all -- a plain ``Enum``
    compares by identity and a ``StrEnum`` is routed to the text describer -- so
    without the rule two members would differ in an ordinal nobody wrote, and
    would do so only for one of the three flavours.
    """

    class Plain(Enum):
        RED = 1
        BLUE = 2

    class Numeric(IntEnum):
        RED = 1
        BLUE = 2

    class Textual(StrEnum):
        RED = "red"
        BLUE = "blue"

    assert vars(Numeric.RED).keys() >= {"_name_", "_value_", "_sort_order_"}
    assert describe_difference(Numeric.RED, Numeric.BLUE) == ""
    assert describe_difference(Plain.RED, Plain.BLUE) == ""
    # A `StrEnum` member *is* a string and so is routed to the text describer
    # instead; what it must never do is name the bookkeeping either.
    assert "_sort_order_" not in describe_difference(Textual.RED, Textual.BLUE)


def test_a_class_object_is_not_a_record() -> None:
    """``vars`` of a class is the methods it defines, not the state of an instance.

    The metaclass is what makes this reachable: without one, two classes compare
    by identity and the describer declines earlier for that reason instead.
    """

    class Meta(type):
        def __eq__(cls, other: object) -> bool:
            return False

        def __hash__(cls) -> int:
            return 0

    class Left(metaclass=Meta):
        shared = 1
        only_left = 2

    class Right(metaclass=Meta):
        shared = 9
        only_right = 3

    assert describe_difference(Left, Right) == ""
    assert describe_difference(User, User("ann", 30)) == ""


def test_a_dataclass_whose_fields_all_match_falls_through_to_the_look_alike_clause() -> None:
    """Not reachable through ``is_equal_to`` -- but the engine must not invent a field."""

    @dataclass(eq=False)
    class Frozen:
        x: int

        def __repr__(self) -> str:
            return "Frozen()"

    assert block(Frozen(1), Frozen(1)) == [
        "  both render as Frozen(), but Frozen does not define __eq__, so they compare by identity"
    ]


# ---------------------------------------------------------------------------
# It never raises
# ---------------------------------------------------------------------------
def test_a_property_that_raises_costs_that_field_and_no_other() -> None:
    """One hostile member of a record must not delete the block for the rest of it."""

    class Guarded:
        def __init__(self, label: str) -> None:
            self.label = label

        @property
        def boom(self) -> int:
            raise RuntimeError("property exploded")

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Guarded):
                return NotImplemented
            return self.label == other.label

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Guarded(" + repr(self.label) + ")"

    subject = Guarded("a")
    subject.__dict__["boom"] = None  # the name resolves; reading it does not
    other = Guarded("b")
    other.__dict__["boom"] = None
    assert block(subject, other) == ["  field label: 'a' instead of 'b'"]


def test_a_slot_that_was_never_assigned_costs_detail_rather_than_raising() -> None:
    class Partial:
        __slots__ = ("a", "b")

        def __init__(self, **members: int) -> None:
            for name, value in members.items():
                setattr(self, name, value)

        def __eq__(self, other: object) -> bool:
            return False

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Partial()"

    assert block(Partial(a=1), Partial(a=1, b=2)) == [
        "  both render as Partial(), but they are not equal"
    ]


def test_a_hostile_field_costs_that_field_and_no_other() -> None:
    class Hostile:
        __slots__ = ()

        def __repr__(self) -> str:
            raise RuntimeError("repr exploded")

        def __eq__(self, other: object) -> bool:
            raise RuntimeError("eq exploded")

        def __hash__(self) -> int:
            raise RuntimeError("hash exploded")

    @dataclass
    class Holder:
        count: int
        payload: object

    assert block(Holder(1, Hostile()), Holder(2, Hostile())) == ["  field count: 1 instead of 2"]


def test_a_self_referential_object_degrades_instead_of_recursing_forever() -> None:
    """Its own ``==`` is what recurses; the describer must survive it either way."""
    left = Node("a")
    left.parent = left
    right = Node("a")
    right.parent = right
    with pytest.raises(RecursionError):
        _ = left == right
    assert block(left, right) == [
        "  both render as Node(name='a', parent=...), but they are not equal"
    ]


def test_slots_declared_as_a_dict_of_docstrings_still_names_the_fields() -> None:
    """A documented, and easily missed, spelling of ``__slots__``.

    Iterating a ``dict`` yields its keys, which is why this works at all; a
    resolver that assumed a sequence of strings would work here by accident and
    break on the day the values stopped being strings.
    """

    class Documented:
        __slots__ = {"host": "where it lives", "port": "how to reach it"}

        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Documented):
                return NotImplemented
            return (self.host, self.port) == (other.host, other.port)

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Documented()"

    assert block(Documented("prod", 80), Documented("prod", 443)) == [
        "  field port: 80 instead of 443"
    ]
