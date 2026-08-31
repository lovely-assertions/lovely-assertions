"""The structural equivalence engine: the walk, the paths, the options.

Four properties get more attention than the rest, because each of them is a
*wrong answer* rather than a missing one.

*The right branch has to claim the pair.* A ``NamedTuple`` is a tuple, a ``str``
is a sequence, a dataclass keeps fields the generated ``__eq__`` was told to skip.
Route any one of those to the wrong describer and the engine reports a difference
that is confidently about the wrong thing -- or, worse, reports none at all and
the test passes.

*"" is a verdict.* ``_diff`` degrades to an empty block because its caller has
already failed; here an empty string means *equivalent*, so every degradation has
to produce a difference instead. A comparison that gives up must fail the test,
not pass it.

*It never raises because of a value.* A property that explodes, a ``__repr__``
that lies, an ``__eq__`` that throws, a graph that contains itself.

*It is bounded.* A hundred differences do not print a hundred lines, and a deep
or cyclic graph does not run until the interpreter stops it.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any, Final, NamedTuple, cast

import pytest

from lovely_assertions import _equivalence, expect, formatting, soft_assertions
from lovely_assertions._equivalence import (
    Equivalency,
    _budget,
    _classification,
    _labels,
    _rendering,
    close_within,
    compare,
    equivalency,
)
from lovely_assertions._equivalence._classification import _fields as _classified_fields
from lovely_assertions._reflection import _cache, _fields

if TYPE_CHECKING:
    from abc import ABCMeta
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# Reading the block
# ---------------------------------------------------------------------------
def block(actual: object, expected: object, options: Equivalency | None = None) -> list[str]:
    """Every line of the rendered block, with the leading newline stripped."""
    rendered = compare(actual, expected, options if options is not None else equivalency())
    assert rendered.startswith("\n"), "the block must start with a newline"
    assert not rendered.endswith("\n"), "the block must not end with a newline"
    return rendered[1:].split("\n")


def findings(actual: object, expected: object, options: Equivalency | None = None) -> list[str]:
    """The difference lines only, without the trailing configuration aside."""
    lines = block(actual, expected, options)
    assert lines[-1].strip().startswith("(compared with "), lines
    return [line.strip() for line in lines[:-1]]


def configuration(actual: object, expected: object, options: Equivalency | None = None) -> str:
    """The trailing configuration aside on its own."""
    return block(actual, expected, options)[-1].strip()


def equivalent(actual: object, expected: object, options: Equivalency | None = None) -> bool:
    """Whether the engine found nothing to report."""
    return compare(actual, expected, options if options is not None else equivalency()) == ""


# ---------------------------------------------------------------------------
# Fixtures of every shape the resolver has to recognise
# ---------------------------------------------------------------------------
@dataclass
class Address:
    city: str
    postcode: str


@dataclass
class User:
    name: str
    address: Address
    tags: list[str]


@dataclass
class Cached:
    """A dataclass with a field its own ``__eq__`` was told to ignore."""

    value: int
    computed: int = field(default=0, compare=False)


class Point(NamedTuple):
    """A record that is also a tuple, which is the whole trap."""

    x: int
    y: int


class Coord(NamedTuple):
    """Same shape, different class -- equivalence does not care."""

    x: int
    y: int


class Slotted:
    """A hand-written value type: fields in ``__slots__``, nothing in a dict."""

    __slots__ = ("host", "port")

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port


class SlottedBase:
    __slots__ = ("a",)

    def __init__(self, a: int) -> None:
        self.a = a


class DictSubclass(SlottedBase):
    """A ``__slots__`` base whose subclass keeps its own fields in a ``__dict__``."""

    def __init__(self, a: int, b: int) -> None:
        super().__init__(a)
        self.b = b


class Plain:
    """The ordinary case: everything in the instance dictionary."""

    def __init__(self, **fields: object) -> None:
        self.__dict__.update(fields)


class FakeModel:
    """The shape pydantic v2 has: slots for bookkeeping, values in ``__dict__``."""

    __slots__ = ("__dict__", "__pydantic_fields_set__")

    def __init__(self, **fields: object) -> None:
        self.__dict__.update(fields)
        self.__pydantic_fields_set__ = set(fields)


class _AttrsAttribute:
    """The duck ``attrs`` presents: a name and an ``eq`` flag."""

    __slots__ = ("eq", "name")

    def __init__(self, name: str, *, eq: bool = True) -> None:
        self.name = name
        self.eq = eq


class AttrsLike:
    """An ``attrs`` class as the engine sees it -- ``__attrs_attrs__``, no import."""

    __attrs_attrs__: Final = (
        _AttrsAttribute("host"),
        _AttrsAttribute("port"),
        _AttrsAttribute("cached", eq=False),
    )

    def __init__(self, host: str, port: int, cached: int) -> None:
        self.host = host
        self.port = port
        self.cached = cached


@dataclass
class Counted(dict[str, int]):
    """A dataclass whose *storage* is a mapping and whose *fields* are not in it.

    Its generated ``__eq__`` reads ``label`` and ignores the entries, so a walk
    that lets the mapping branch claim it compares the wrong thing entirely.
    """

    label: int


class Money:
    """A domain type whose ``repr`` is an address, which is what formatters exist for."""

    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents


class Coins:
    """A formatter for :class:`Money`, scoped rather than registered globally."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, Money)

    def format(self, value: object, /) -> str:
        return "$" + str(value.cents) if isinstance(value, Money) else repr(value)


class Tagged(list[int]):
    """A list subclass that also carries an attribute."""

    def __init__(self, items: list[int], tag: str) -> None:
        super().__init__(items)
        self.tag = tag


class Wire(Enum):
    RED = 1
    BLUE = 2


class Domain(Enum):
    RED = "red"
    BLUE = "blue"


class Level(IntEnum):
    LOW = 1
    HIGH = 2


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------
def test_equivalent_values_produce_an_empty_string() -> None:
    """An empty string is the whole signal: the caller branches on emptiness."""
    assert compare({"id": 1}, {"id": 1}, equivalency()) == ""


def test_a_difference_is_a_block_that_appends_to_a_one_line_message() -> None:
    rendered = compare({"id": 1}, {"id": 2}, equivalency())
    assert rendered.startswith("\n")
    assert not rendered.endswith("\n")


def test_options_that_are_not_options_are_refused_at_the_call() -> None:
    """The one thing that raises: a misconfigured call, not a hostile value."""
    with pytest.raises(TypeError, match="options must be an Equivalency, not str"):
        compare(1, 1, "nope")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def test_options_that_are_the_factory_rather_than_its_result_are_refused() -> None:
    """The mistake this check exists for."""
    with pytest.raises(TypeError, match="not function"):
        compare(1, 1, equivalency)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


# ---------------------------------------------------------------------------
# Equivalence, not equality
# ---------------------------------------------------------------------------
def test_a_list_is_equivalent_to_a_tuple_with_the_same_items() -> None:
    """Where equivalence parts company with ``==``, and the point of the assertion."""
    as_list: object = [1, 2]
    assert as_list != (1, 2)
    assert equivalent(as_list, (1, 2))


def test_equivalence_is_never_stricter_than_equality() -> None:
    """Equality settles equivalence: two equal values hold the same information.

    ``Point(1, 2) == (1, 2)`` is true, so an engine that called them *not*
    equivalent would fail the weaker assertion where the stronger one passes --
    the one pair of answers a reader could never make sense of. It is also why
    the record branch is not consulted when ``==`` has already said yes.
    """
    assert Point(1, 2) == (1, 2)
    assert equivalent(Point(1, 2), (1, 2))


def test_two_records_of_different_classes_are_compared_member_by_member() -> None:
    assert equivalent(Point(1, 2), Coord(1, 2))


def test_a_record_and_a_record_with_a_different_field_report_the_field() -> None:
    assert findings(Point(1, 2), Coord(1, 3)) == ["y: 2 instead of 3"]


def test_int_and_float_that_compare_equal_are_equivalent() -> None:
    assert equivalent(1, 1.0)


def test_values_of_unrelated_kinds_report_their_types() -> None:
    assert findings([1], {"a": 1}) == ["the value itself: types differ: list instead of dict"]


def test_a_leaf_against_a_record_reports_the_types() -> None:
    assert findings(3, Point(1, 2)) == [
        "the value itself: types differ: int instead of Point",
    ]


def test_two_classes_of_the_same_name_are_named_in_full() -> None:
    """The one case where the two reprs are no help whatsoever."""
    leaf = type("Same", (), {"__slots__": ()})
    sequence = type("Same", (list,), {})
    line = findings([leaf()], [sequence()])[0]
    assert "both are called" in line
    assert "they are not the same class object" in line


def test_a_string_and_a_number_are_a_plain_pair_of_values() -> None:
    """Neither has members, so the two reprs are the whole finding."""
    assert findings("1", 1) == ["the value itself: '1' instead of 1"]


def test_nested_structures_are_walked_all_the_way_down() -> None:
    left = {"a": [{"b": {"c": 1}}]}
    right = {"a": [{"b": {"c": 2}}]}
    assert findings(left, right) == ["a[0].b.c: 1 instead of 2"]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def test_the_root_reads_as_the_value_itself() -> None:
    assert findings(1, 2) == ["the value itself: 1 instead of 2"]


def test_fields_and_identifier_keys_use_a_dot() -> None:
    left = User("ann", Address("Paris", "75001"), [])
    right = User("ann", Address("Lyon", "75001"), [])
    assert findings(left, right) == ["address.city: 'Paris' instead of 'Lyon'"]


def test_an_identifier_like_mapping_key_uses_a_dot_too() -> None:
    assert findings({"user": {"city": "a"}}, {"user": {"city": "b"}}) == [
        "user.city: 'a' instead of 'b'"
    ]


def test_an_index_uses_brackets() -> None:
    assert findings([9, 9], [9, 8]) == ["[1]: 9 instead of 8"]


def test_a_key_that_is_not_a_name_uses_brackets_and_its_repr() -> None:
    assert findings({"a b": 1}, {"a b": 2}) == ["['a b']: 1 instead of 2"]


def test_a_numeric_string_key_is_not_an_identifier() -> None:
    """``'0'`` would be indistinguishable from an index in dot notation."""
    assert findings({"0": 1}, {"0": 2}) == ["['0']: 1 instead of 2"]


def test_a_non_string_key_uses_its_repr() -> None:
    assert findings({7: "a"}, {7: "b"}) == ["[7]: 'a' instead of 'b'"]


def test_a_key_with_a_hostile_repr_still_produces_a_path() -> None:
    class BadKey:
        def __repr__(self) -> str:
            raise RuntimeError("no")

        def __hash__(self) -> int:
            return 1

        def __eq__(self, other: object) -> bool:
            return isinstance(other, BadKey)

    key = BadKey()
    assert findings({key: 1}, {key: 2}) == ["[<unreadable key>]: 1 instead of 2"]


def test_an_enormous_key_is_bounded_inside_the_path() -> None:
    """Paths are built during the walk, so this bound is a constant, not a scope."""
    key = "not a name " * 50
    line = findings({key: 1}, {key: 2})[0]
    assert line.startswith("['not a name ")
    assert " more)]: 1 instead of 2" in line
    assert len(line) < 200


def test_an_enormous_identifier_key_is_clipped_when_it_is_printed() -> None:
    """A key that *is* a name grows no brackets, so the render-time clip catches it."""
    line = findings({"x" * 500: 1}, {"x" * 500: 2})[0]
    assert "more characters)" in line
    assert len(line) < 200


def test_a_printed_path_can_be_pasted_into_excluding_path() -> None:
    """The two notations are one notation, or ``excluding_path`` is a guessing game."""
    left = {"user": {"roles": [{"name": "a"}]}}
    right = {"user": {"roles": [{"name": "b"}]}}
    printed = findings(left, right)[0].partition(":")[0]
    assert printed == "user.roles[0].name"
    assert equivalent(left, right, equivalency().excluding_path(printed))


# ---------------------------------------------------------------------------
# The three ordering traps
# ---------------------------------------------------------------------------
def test_a_named_tuple_is_a_record_and_not_a_sequence() -> None:
    """Trap one: routed to the sequence branch this says "index 0" for a field."""
    assert findings(Point(1, 2), Point(2, 1)) == [
        "x: 1 instead of 2",
        "y: 2 instead of 1",
    ]


def test_a_named_tuple_is_still_a_record_when_order_is_ignored() -> None:
    """The silent half of trap one: as a sequence these would compare *equal*."""
    assert not equivalent(Point(1, 2), Point(2, 1), equivalency().ignoring_order())


def test_a_string_is_never_walked_as_a_sequence() -> None:
    """Trap two. As a sequence, ``ignoring_order`` would call these the same bag."""
    assert findings("ab", "ba", equivalency().ignoring_order()) == [
        "the value itself: 'ab' instead of 'ba'"
    ]


def test_bytes_are_never_walked_as_a_sequence() -> None:
    assert findings(b"ab", b"ba", equivalency().ignoring_order()) == [
        "the value itself: b'ab' instead of b'ba'"
    ]


def test_a_dataclass_reports_its_comparable_fields_and_only_those() -> None:
    """Trap three: reporting ``computed`` would disagree with the ``==`` it falls back on.

    Both sides differ in ``computed`` as well, which is what makes the assertion
    mean something: with it equal on both sides, an engine that compared it would
    still find nothing to say and the test would pass either way. The pair that
    is equal on ``value`` is not tested here at all, for the same reason -- the
    generated ``__eq__`` settles it before the fields are ever resolved (the
    torture suite pins that half, where the values differ).
    """
    assert findings(Cached(1, computed=10), Cached(2, computed=20)) == ["value: 1 instead of 2"]


def test_a_declared_record_wins_over_the_storage_it_happens_to_use() -> None:
    """The mapping half of trap three: ``dataclasses.fields()`` before ``dict``.

    A declaration is the author saying what the object *is*; a mapping branch that
    claims it first sees only what it is stored in. Two instances carrying the same
    entries under different fields would come back equivalent while ``==`` -- which
    reads the fields and ignores the entries -- says they are not.
    """
    left = Counted(label=1)
    right = Counted(label=2)
    left["k"] = right["k"] = 7
    equal_by_eq = left == right
    assert equal_by_eq is False
    assert findings(left, right) == ["label: 1 instead of 2"]


def test_a_list_subclass_with_an_attribute_is_still_compared_as_a_list() -> None:
    """The mirror of trap one: a stored field must not steal the sequence branch."""
    assert findings(Tagged([1, 2], "x"), Tagged([1, 3], "y")) == ["[1]: 2 instead of 3"]


# ---------------------------------------------------------------------------
# Field resolution: a declaration first, then whatever storage the object uses
# ---------------------------------------------------------------------------
def test_a_slots_class_resolves_its_slots() -> None:
    assert findings(Slotted("a", 1), Slotted("a", 2)) == ["port: 1 instead of 2"]


def test_a_slots_base_and_a_dict_subclass_resolve_both_storages() -> None:
    """Reading only the winner would compare ``a``, ignore ``b`` and pass."""
    assert findings(DictSubclass(1, 2), DictSubclass(1, 3)) == ["b: 2 instead of 3"]


def test_a_plain_object_resolves_its_instance_dictionary() -> None:
    assert findings(Plain(x=1), Plain(x=2)) == ["x: 1 instead of 2"]


def test_a_pydantic_shaped_model_resolves_its_fields_and_not_its_bookkeeping() -> None:
    left = FakeModel(name="ann", age=30)
    right = FakeModel(name="ann", age=31)
    assert findings(left, right) == ["age: 30 instead of 31"]


def test_attrs_is_duck_typed_through_attrs_attrs() -> None:
    assert findings(AttrsLike("a", 1, 9), AttrsLike("a", 2, 9)) == ["port: 1 instead of 2"]


def test_attrs_honours_a_field_excluded_from_eq() -> None:
    assert equivalent(AttrsLike("a", 1, 9), AttrsLike("a", 1, 99))


def test_a_field_only_the_subject_carries_is_not_a_difference() -> None:
    """The expectation drives: a small literal stands in for the shape under test."""
    assert equivalent(Plain(a=1, b=2), Plain(a=1))


def test_comparing_all_members_puts_the_surplus_field_back() -> None:
    assert findings(Plain(a=1, b=2), Plain(a=1), equivalency().comparing_all_members()) == [
        "the value itself: extra fields: ['b']",
    ]


def test_excluding_missing_drops_the_other_direction() -> None:
    """The mirror image: a field the expectation names and the subject lacks."""
    assert findings(Plain(a=1), Plain(a=1, b=2)) == [
        "the value itself: missing fields: ['b']",
    ]
    assert equivalent(Plain(a=1), Plain(a=1, b=2), equivalency().excluding_missing())


def test_excluding_missing_alone_compares_only_the_fields_both_sides_carry() -> None:
    options = equivalency().excluding_missing()
    assert equivalent(Plain(a=1, b=2), Plain(a=1, c=3), options)
    assert findings(Plain(a=9, b=2), Plain(a=1, c=3), options) == ["a: 9 instead of 1"]


def test_the_two_member_options_together_invert_the_asymmetry() -> None:
    """Subject-driven: the expectation may lack a member, the subject may not."""
    options = equivalency().comparing_all_members().excluding_missing()
    assert equivalent(Plain(a=1), Plain(a=1, b=2), options)
    assert findings(Plain(a=1, b=2), Plain(a=1), options) == [
        "the value itself: extra fields: ['b']",
    ]


def test_a_mapping_still_reports_a_key_only_the_subject_carries() -> None:
    """A mapping's keys are its data, so neither member option reaches them."""
    for options in (
        equivalency(),
        equivalency().excluding_missing(),
        equivalency().comparing_all_members(),
    ):
        assert findings({"a": 1, "b": 2}, {"a": 1}, options) == [
            "the value itself: extra keys: ['b']",
        ]
        assert findings({"a": 1}, {"a": 1, "b": 2}, options) == [
            "the value itself: missing keys: ['b']",
        ]


def test_fields_the_expectation_carries_and_the_subject_does_not_are_reported() -> None:
    assert findings(Plain(a=1), Plain(a=1, b=2)) == [
        "the value itself: missing fields: ['b']",
    ]


def test_a_class_object_is_not_a_record() -> None:
    """A class's dictionary holds its methods, not an instance's state.

    Read as a record, these two would differ in ``encode``.
    """
    assert findings(int, str) == ["the value itself: <class 'int'> instead of <class 'str'>"]


# ---------------------------------------------------------------------------
# Mappings
# ---------------------------------------------------------------------------
def test_a_mapping_reports_values_before_membership() -> None:
    assert findings({"a": 1}, {"a": 2, "b": 3}) == [
        "a: 1 instead of 2",
        "the value itself: missing keys: ['b']",
    ]


def test_a_mapping_reports_surplus_keys() -> None:
    assert findings({"a": 1, "b": 2}, {"a": 1}) == ["the value itself: extra keys: ['b']"]


def test_mapping_keys_are_sorted_so_two_runs_read_the_same() -> None:
    left: dict[str, int] = {}
    right = {"z": 1, "a": 2, "m": 3}
    assert findings(left, right) == ["the value itself: missing keys: ['a', 'm', 'z']"]


def test_unorderable_keys_keep_their_iteration_order() -> None:
    right: dict[object, int] = {"a": 1, 2: 2}
    line = findings({}, right)[0]
    assert line == "the value itself: missing keys: ['a', 2]"


# ---------------------------------------------------------------------------
# Sequences and ordering
# ---------------------------------------------------------------------------
def test_ordering_is_strict_by_default() -> None:
    """Order is structure unless asked otherwise, which inverts FluentAssertions on purpose."""
    assert findings([1, 2], [2, 1]) == ["[0]: 1 instead of 2", "[1]: 2 instead of 1"]


def test_ignoring_order_opts_out() -> None:
    assert equivalent([1, 2], [2, 1], equivalency().ignoring_order())


def test_a_shorter_sequence_reports_its_length_and_what_is_absent() -> None:
    """The tail is reported at the first index with no counterpart, not at the whole."""
    assert findings([1], [1, 2, 3]) == [
        "the value itself: lengths differ: 1 item, expected 3",
        "[1]: missing items: [2, 3]",
    ]


def test_a_longer_sequence_reports_what_is_surplus() -> None:
    assert findings([1, 2], [1]) == [
        "the value itself: lengths differ: 2 items, expected 1",
        "[1]: extra items: [2]",
    ]


def test_a_surplus_tail_is_named_where_it_starts() -> None:
    """Every other finding names a *where*; a surplus item has one too."""
    left = {"rows": [1, 2, 3]}
    right = {"rows": [1, 2]}
    assert findings(left, right)[1].startswith("rows[2]: ")


def test_ignoring_order_matches_unhashable_items_structurally() -> None:
    left = [{"id": 1}, {"id": 2}]
    right = [{"id": 2}, {"id": 1}]
    assert equivalent(left, right, equivalency().ignoring_order())


def test_ignoring_order_honours_the_options_while_matching() -> None:
    """The structural half is a full comparison, so exclusions apply inside it."""
    left = [{"id": 1, "seen": "monday"}, {"id": 2, "seen": "tuesday"}]
    right = [{"id": 2, "seen": "friday"}, {"id": 1, "seen": "sunday"}]
    options = equivalency().ignoring_order().excluding("seen")
    assert equivalent(left, right, options)


def test_ignoring_order_reports_what_it_could_not_pair() -> None:
    left = [{"id": 1}]
    right = [{"id": 2}]
    assert findings(left, right, equivalency().ignoring_order()) == [
        "the value itself: missing items: [{'id': 2}]",
        "the value itself: extra items: [{'id': 1}]",
    ]


def test_ignoring_order_pairs_up_more_unmatched_items_than_the_old_per_level_cap() -> None:
    """A hundred and fifty unpaired items on each side is an answer, not a shrug.

    A per-level cap of a hundred would stop here and report "too many unpaired
    items to match them up" -- a *difference* standing in for a comparison that
    never happened. Twenty-two thousand probes is well inside the matching
    allowance, so the pairing runs to the end and reports what genuinely had no
    counterpart.
    """
    left = [{"i": index} for index in range(150)]
    right = [{"i": index + 1000} for index in range(150)]
    lines = findings(left, right, equivalency().ignoring_order())
    assert not any("too many unpaired items" in line for line in lines), lines
    assert lines[0].startswith("the value itself: missing items: [{'i': 1000}")
    assert lines[1].startswith("the value itself: extra items: [{'i': 0}")


def test_a_range_is_a_sequence() -> None:
    assert equivalent(range(3), [0, 1, 2])


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------
def test_a_set_reports_membership_and_no_position() -> None:
    assert findings({"a"}, {"a", "b"}) == ["the value itself: missing items: ['b']"]


def test_a_set_reports_surplus_members() -> None:
    assert findings({"a", "b"}, {"a"}) == ["the value itself: extra items: ['b']"]


def test_equal_sets_are_equivalent() -> None:
    assert equivalent({1, 2, 3}, {3, 2, 1})


def test_a_set_whose_items_cannot_be_read_is_a_finding() -> None:
    """The set branch's degradation, and it has to produce a difference rather than silence.

    A ``Set`` is claimed by declaration -- the ABC, not the built-in -- so a class
    that registers as one and then refuses to be iterated reaches the item walk
    with nothing to walk. Reporting nothing there is a **passing** test on two
    values the engine never looked at.
    """
    from collections.abc import Set as AbstractSet

    class Unreadable(AbstractSet[int]):
        """A set by declaration that will not give its items up."""

        def __iter__(self) -> "Iterator[int]":
            raise RuntimeError("no")

        def __len__(self) -> int:
            return 1

        def __contains__(self, item: object, /) -> bool:
            return True

    assert findings(Unreadable(), Unreadable()) == [
        "the value itself: the items of this set could not be read"
    ]


# ---------------------------------------------------------------------------
# excluding / excluding_path / including
# ---------------------------------------------------------------------------
def test_excluding_skips_a_record_field() -> None:
    left = User("ann", Address("Paris", "75001"), [])
    right = User("anne", Address("Paris", "75001"), [])
    assert equivalent(left, right, equivalency().excluding("name"))


def test_excluding_skips_a_mapping_key_of_the_same_name() -> None:
    """To the reader ``{"password": ...}`` and ``User(password=...)`` are one member."""
    assert equivalent({"password": "a"}, {"password": "b"}, equivalency().excluding("password"))


def test_excluding_applies_at_every_depth() -> None:
    left = {"a": {"id": 1, "v": 1}, "b": {"id": 2, "v": 2}}
    right = {"a": {"id": 9, "v": 1}, "b": {"id": 8, "v": 2}}
    assert equivalent(left, right, equivalency().excluding("id"))


def test_an_excluded_member_cannot_be_missing_or_surplus() -> None:
    """A member nobody is comparing has nowhere to be absent from."""
    assert equivalent({"a": 1}, {"a": 1, "trace": 2}, equivalency().excluding("trace"))
    assert equivalent({"a": 1, "trace": 2}, {"a": 1}, equivalency().excluding("trace"))


def test_excluding_a_path_skips_that_member_only() -> None:
    left = {"a": {"v": 1}, "b": {"v": 1}}
    right = {"a": {"v": 2}, "b": {"v": 2}}
    assert findings(left, right, equivalency().excluding_path("a.v")) == ["b.v: 1 instead of 2"]


def test_excluding_a_path_excludes_the_subtree_beneath_it() -> None:
    left = {"a": {"deep": {"v": 1}}}
    right = {"a": {"deep": {"v": 2}}}
    assert equivalent(left, right, equivalency().excluding_path("a.deep"))


def test_excluding_a_path_does_not_catch_a_longer_sibling() -> None:
    """``user`` must not swallow ``username``, which is the whole prefix rule.

    A name, not an index: ``items[1]`` cannot be a prefix of ``items[10]`` in the
    first place, because the closing bracket lands where the ``0`` would be. Only
    names run together, so only names need the separator -- and an exclusion that
    quietly takes a member the caller never wrote is the one way this option turns
    into a wrong pass.
    """
    left = {"user": 1, "username": "ann"}
    right = {"user": 2, "username": "bob"}
    assert findings(left, right, equivalency().excluding_path("user")) == [
        "username: 'ann' instead of 'bob'",
    ]


def test_excluding_an_index_path_works() -> None:
    assert equivalent([1, 2], [1, 3], equivalency().excluding_path("[1]"))


def test_an_excluded_path_takes_a_member_whose_path_only_extends_it() -> None:
    """The prefix rule asked directly, rather than through the subtree it usually prunes.

    ``excluding_path("a.b")`` normally never gets this far: the member *at* ``a.b``
    is refused by the equality arm and its subtree is never descended, so nothing
    below it is asked about. The prefix arm answers only where the excluded path
    is not itself a member -- here because the member's own name carries the
    separator, so the only path it can produce is ``a.b.c``.
    """

    class Dotted:
        """One member, named so that its path extends ``a.b`` without ever being it."""

        def __init__(self, value: int, /) -> None:
            setattr(self, "b.c", value)

    class Holder:
        __slots__ = ("a", "tag")

        def __init__(self, inner: Dotted, tag: str, /) -> None:
            self.a = inner
            self.tag = tag

    left = Holder(Dotted(1), "x")
    right = Holder(Dotted(2), "y")

    assert findings(left, right) == ["a.b.c: 1 instead of 2", "tag: 'x' instead of 'y'"]
    assert findings(left, right, equivalency().excluding_path("a.b")) == ["tag: 'x' instead of 'y'"]


def test_including_restricts_the_named_members_compared() -> None:
    left = {"id": 1, "noise": "a"}
    right = {"id": 1, "noise": "b"}
    assert equivalent(left, right, equivalency().including("id"))


def test_including_reports_a_difference_in_a_selected_member() -> None:
    left = {"id": 1, "noise": "a"}
    right = {"id": 2, "noise": "b"}
    assert findings(left, right, equivalency().including("id")) == ["id: 1 instead of 2"]


def test_including_leaves_members_that_have_no_name_alone() -> None:
    """Otherwise one ``including`` call empties every list in the graph."""
    assert findings([1, 2], [1, 3], equivalency().including("id")) == ["[1]: 2 instead of 3"]


def test_including_leaves_keys_that_are_not_names_alone() -> None:
    assert findings({7: "a"}, {7: "b"}, equivalency().including("id")) == [
        "[7]: 'a' instead of 'b'"
    ]


def test_excluding_wins_where_it_disagrees_with_including() -> None:
    left = {"id": 1}
    right = {"id": 2}
    assert equivalent(left, right, equivalency().including("id").excluding("id"))


# ---------------------------------------------------------------------------
# using / close_within
# ---------------------------------------------------------------------------
def test_close_within_gives_floats_a_tolerance() -> None:
    options = equivalency().using(float, close_within(0.01))
    assert equivalent({"total": 1.0}, {"total": 1.005}, options)
    assert not equivalent({"total": 1.0}, {"total": 1.5}, options)


def test_close_within_gives_datetimes_a_tolerance() -> None:
    moment = datetime(2020, 1, 1, 12, 0, 0)  # a fixed instant, not a clock reading
    options = equivalency().using(datetime, close_within(timedelta(minutes=1)))
    assert equivalent(moment, moment + timedelta(seconds=30), options)
    assert not equivalent(moment, moment + timedelta(hours=1), options)


def test_a_comparator_applies_at_every_depth() -> None:
    options = equivalency().using(float, close_within(0.5))
    assert equivalent({"a": [{"b": 1.0}]}, {"a": [{"b": 1.2}]}, options)


def test_a_comparator_needs_both_sides_to_be_instances() -> None:
    """A comparator for ``float`` has no business deciding a ``float`` against a ``str``."""
    options = equivalency().using(float, close_within(100.0))
    # Consulted, the comparator would have raised on `1.0 - "1.0"` and said so.
    assert findings(1.0, "1.0", options) == ["the value itself: 1.0 instead of '1.0'"]


def test_the_last_registered_comparator_wins() -> None:
    """A later call narrows an earlier one rather than being shadowed by it."""
    options = equivalency().using(object, lambda _a, _b: True).using(int, lambda _a, _b: False)
    assert not equivalent(1, 1000, options)
    assert equivalent("a", "b", options)


def test_a_comparator_that_raises_is_a_finding_not_a_crash() -> None:
    def explode(_actual: object, _expected: object) -> bool:
        raise RuntimeError("boom")

    options = equivalency().using(int, explode)
    assert findings(1, 2, options) == [
        "the value itself: the comparator for int raised RuntimeError"
    ]


def test_a_comparator_whose_type_will_not_answer_isinstance_claims_nothing() -> None:
    """Deciding whether a comparator claims a pair runs user code before the comparator does.

    ``isinstance`` reaches a metaclass's ``__instancecheck__``, and one that raises
    must leave the pair to the structural walk. Read as a claim, the comparator
    would settle two values it was never registered for -- and one that agrees
    turns that into a green test.
    """

    class Unaskable(type):
        def __instancecheck__(cls, instance: object) -> bool:
            raise RuntimeError("no")

    class Kind(metaclass=Unaskable):
        pass

    def always_agrees(_actual: object, _expected: object) -> bool:
        return True

    options = equivalency().using(Kind, always_agrees)

    assert findings({"total": 1}, {"total": 2}, options) == ["total: 1 instead of 2"]


def test_close_within_reports_a_pair_it_cannot_subtract() -> None:
    """A comparator for the wrong type is a configuration mistake, and reads as one."""
    options = equivalency().using(object, close_within(1.0))
    assert findings("a", "b", options) == [
        "the value itself: the comparator for str raised TypeError"
    ]


def test_close_within_refuses_a_negative_tolerance() -> None:
    with pytest.raises(ValueError, match="tolerance must be zero or more"):
        close_within(-1.0)


def test_close_within_refuses_a_nan_tolerance() -> None:
    """A NaN tolerance makes everything a difference, a long way from the mistake."""
    with pytest.raises(ValueError, match="tolerance must be zero or more"):
        close_within(float("nan"))


def test_close_within_accepts_a_zero_tolerance() -> None:
    assert equivalent(1.0, 1.0, equivalency().using(float, close_within(0.0)))


def test_close_within_refuses_a_negative_timedelta() -> None:
    with pytest.raises(ValueError, match="tolerance must be zero or more"):
        close_within(timedelta(seconds=-1))


# ---------------------------------------------------------------------------
# with_max_depth
# ---------------------------------------------------------------------------
def test_the_walk_stops_at_the_maximum_depth_and_says_so() -> None:
    left = {"a": {"b": {"c": 1}}}
    right = {"a": {"b": {"c": 2}}}
    line = findings(left, right, equivalency().with_max_depth(2))[0]
    assert line.startswith("a.b: ")
    assert "the maximum depth of 2 stops here" in line


def test_a_depth_of_zero_compares_without_taking_anything_apart() -> None:
    assert equivalent({"a": 1}, {"a": 1}, equivalency().with_max_depth(0))
    line = findings({"a": 1}, {"a": 2}, equivalency().with_max_depth(0))[0]
    assert line.startswith("the value itself: ")


def test_a_deeper_bound_reaches_further() -> None:
    left = {"a": {"b": {"c": 1}}}
    right = {"a": {"b": {"c": 2}}}
    assert findings(left, right, equivalency().with_max_depth(5)) == ["a.b.c: 1 instead of 2"]


def test_the_default_depth_is_ten() -> None:
    assert equivalency().max_depth == 10


# ---------------------------------------------------------------------------
# comparing_enums_by_name
# ---------------------------------------------------------------------------
def test_enums_compare_by_value_by_default() -> None:
    assert not equivalent(Wire.RED, Domain.RED)


def test_comparing_enums_by_name_bridges_two_enum_classes() -> None:
    options = equivalency().comparing_enums_by_name()
    assert equivalent(Wire.RED, Domain.RED, options)
    assert not equivalent(Wire.RED, Domain.BLUE, options)


def test_comparing_enums_by_name_reaches_inside_a_graph() -> None:
    options = equivalency().comparing_enums_by_name()
    assert equivalent({"state": Wire.BLUE}, {"state": Domain.BLUE}, options)


def test_a_mixed_in_enum_member_is_not_taken_apart() -> None:
    """An ``IntEnum`` carries ``_name_`` and friends; none of them is a field."""
    assert equivalent(Level.LOW, Level.LOW)
    assert findings(Level.LOW, Level.HIGH) == [
        "the value itself: <Level.LOW: 1> instead of <Level.HIGH: 2>"
    ]


# ---------------------------------------------------------------------------
# The options record
# ---------------------------------------------------------------------------
def test_equivalency_returns_the_documented_defaults() -> None:
    options = equivalency()
    assert options.excluded_names == frozenset()
    assert options.excluded_paths == frozenset()
    assert options.included_names == frozenset()
    assert options.ignore_order is False
    assert options.comparators == ()
    assert options.max_depth == 10
    assert options.enums_by_name is False


def test_every_method_returns_a_new_configuration() -> None:
    base = equivalency()
    assert base.excluding("a") is not base
    assert base.excluded_names == frozenset()


def test_options_are_immutable() -> None:
    options = equivalency()
    with pytest.raises(AttributeError, match="cannot set max_depth"):
        options.max_depth = 3
    with pytest.raises(AttributeError, match="cannot delete max_depth"):
        del options.max_depth


def test_options_compare_and_hash_by_value() -> None:
    assert equivalency().excluding("a") == equivalency().excluding("a")
    assert hash(equivalency().excluding("a")) == hash(equivalency().excluding("a"))
    assert equivalency().excluding("a") != equivalency().excluding("b")
    assert equivalency() != "not an equivalency"


def test_options_repr_is_the_chain_that_built_them() -> None:
    options = (
        equivalency()
        .excluding("b", "a")
        .excluding_path("x.y")
        .including("c")
        .ignoring_order()
        .with_max_depth(3)
        .comparing_enums_by_name()
    )
    assert repr(options) == (
        "equivalency().excluding('a', 'b').excluding_path('x.y').including('c')"
        ".ignoring_order().with_max_depth(3).comparing_enums_by_name()"
    )


def test_options_repr_names_a_comparator() -> None:
    assert repr(equivalency().using(float, close_within(1.0))) == (
        "equivalency().using(float, close_within)"
    )


def test_options_repr_falls_back_for_an_anonymous_comparator() -> None:
    assert repr(equivalency().using(int, lambda _a, _b: True)) == (
        "equivalency().using(int, <comparator>)"
    )


def test_options_repr_never_elides() -> None:
    """A repr is a faithful account, and Python's own reprs do not truncate."""
    options = equivalency().excluding(*(str(index) for index in range(30)))
    with formatting(max_items=2):
        assert "more)" not in repr(options)


def test_a_selection_call_with_no_names_changes_nothing() -> None:
    """``formatting()`` sets the precedent: an override-less builder call is honest.

    It is what ``excluding(*configured)`` comes to when nothing was configured,
    and unlike a variadic *assertion* an empty selection decides nothing. A name
    that went missing shows up in the configuration printed on every failure.
    """
    assert equivalency().excluding() == equivalency()
    assert equivalency().excluding_path() == equivalency()
    assert equivalency().including() == equivalency()
    assert equivalent({"a": 1}, {"a": 1}, equivalency().excluding())
    assert not equivalent({"a": 1}, {"a": 2}, equivalency().excluding())


def test_selection_calls_refuse_a_name_that_is_not_a_name() -> None:
    with pytest.raises(TypeError, match="excluding needs names, not int"):
        equivalency().excluding(7)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def test_excluding_path_refuses_the_empty_path() -> None:
    """Excluding the root would report two values equivalent having compared none."""
    with pytest.raises(ValueError, match="the empty path is the whole value"):
        equivalency().excluding_path("")


def test_using_refuses_something_that_is_not_a_class() -> None:
    with pytest.raises(TypeError, match="using needs a class to claim, not str"):
        bad_kind = "float"
        equivalency().using(bad_kind, close_within(1.0))  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def test_using_refuses_a_comparator_that_is_not_callable() -> None:
    """Left alone it would turn every value of its type into a silent difference."""
    with pytest.raises(TypeError, match="using needs a callable comparator, not int"):
        equivalency().using(float, 7)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def test_with_max_depth_refuses_a_non_integer() -> None:
    with pytest.raises(TypeError, match="with_max_depth needs an integer, not str"):
        equivalency().with_max_depth("3")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def test_with_max_depth_refuses_a_negative_depth() -> None:
    with pytest.raises(ValueError, match="with_max_depth needs zero or more, not -1"):
        equivalency().with_max_depth(-1)


def test_options_accumulate_rather_than_replace() -> None:
    options = equivalency().excluding("a").excluding("b")
    assert options.excluded_names == frozenset({"a", "b"})


# ---------------------------------------------------------------------------
# The configuration aside: every failure prints what it was compared with
# ---------------------------------------------------------------------------
def test_every_failure_prints_the_effective_configuration() -> None:
    assert configuration(1, 2) == "(compared with strict ordering, maximum depth 10)"


def test_the_configuration_names_the_ordering_rule() -> None:
    line = configuration([1, 2], [2, 3], equivalency().ignoring_order())
    assert "order ignored" in line


def test_the_configuration_names_what_was_excluded() -> None:
    line = configuration({"a": 1}, {"a": 2}, equivalency().excluding("b"))
    assert "excluding members 'b'" in line


def test_the_configuration_names_excluded_paths_and_included_members() -> None:
    options = equivalency().excluding_path("x.y").including("a")
    line = configuration({"a": 1}, {"a": 2}, options)
    assert "excluding paths 'x.y'" in line
    assert "comparing only members 'a'" in line


def test_the_configuration_names_comparators_and_enum_handling() -> None:
    options = equivalency().using(float, close_within(1.0)).comparing_enums_by_name()
    line = configuration(1, 2, options)
    assert "a custom comparator for float" in line
    assert "comparing enums by name" in line


def test_the_configuration_is_bounded_like_everything_else() -> None:
    options = equivalency().excluding(*(str(index) for index in range(30)))
    with formatting(max_items=3):
        assert "... (27 more)" in configuration(1, 2, options)


# ---------------------------------------------------------------------------
# It never raises because of a value
# ---------------------------------------------------------------------------
def test_a_hostile_repr_costs_detail_and_not_the_test() -> None:
    class NoRepr:
        def __init__(self, value: int) -> None:
            self.value = value

        def __repr__(self) -> str:
            raise RuntimeError("no repr for you")

    assert findings(NoRepr(1), NoRepr(2)) == ["value: 1 instead of 2"]


def test_an_eq_that_raises_is_reported_as_a_difference() -> None:
    class NoEq:
        __slots__ = ()

        def __eq__(self, other: object) -> bool:
            raise ValueError("no")

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "NoEq()"

    line = findings(NoEq(), NoEq())[0]
    assert "comparing them raised ValueError" in line


class Sparse:
    """A declared member that is only sometimes assigned."""

    __slots__ = ("always", "sometimes")

    def __init__(self, always: int, sometimes: int | None = None) -> None:
        self.always = always
        if sometimes is not None:
            self.sometimes = sometimes


def test_a_member_neither_side_has_is_not_a_difference() -> None:
    """A slot nobody assigned is a member the object does not have.

    Reported, it would fail an object against an identical one -- the loudest
    possible wrong answer on an entirely ordinary class.
    """
    assert equivalent(Sparse(1), Sparse(1))


def test_a_member_only_one_side_has_says_which_side() -> None:
    assert findings(Sparse(1), Sparse(1, 2)) == [
        "sometimes: this field could not be read on the actual value"
    ]
    assert findings(Sparse(1, 2), Sparse(1)) == [
        "sometimes: this field could not be read on the expected value"
    ]


def test_an_unreadable_member_costs_only_that_member() -> None:
    """One hostile field of a record must cost that field, not the other ones."""
    assert findings(Sparse(1), Sparse(2)) == ["always: 1 instead of 2"]


def test_a_declaration_nothing_backs_is_not_a_free_pass() -> None:
    """A tuple subclass may declare ``_fields`` it does not carry.

    Trusting the declaration, reading nothing, and calling that "no differences"
    turns a hostile class into a green test.
    """

    class Fibbing(tuple[int, ...]):
        __slots__ = ()
        _fields = ("nope",)

    line = findings(Fibbing((1, 2)), Fibbing((1, 3)))[0]
    assert "(1, 2) instead of (1, 3)" in line
    assert "none of the fields it declares could be read" in line


def test_a_mapping_that_will_not_iterate_is_a_finding() -> None:
    from collections.abc import Mapping

    class Broken(Mapping[str, int]):
        def __iter__(self) -> "Iterator[str]":
            raise RuntimeError("no")

        def __len__(self) -> int:
            return 1

        def __getitem__(self, key: str) -> int:
            return 1

    assert findings(Broken(), Broken()) == [
        "the value itself: the keys of this mapping could not be read"
    ]


def test_an_entry_that_will_not_be_read_costs_only_that_entry() -> None:
    class Trap(dict[str, int]):
        def __getitem__(self, key: str) -> int:
            if key == "bad":
                raise RuntimeError("no")
            return super().__getitem__(key)

    left = Trap({"good": 1, "bad": 2})
    right = Trap({"good": 9, "bad": 2})
    assert findings(left, right) == [
        "good: 1 instead of 9",
        "bad: this entry could not be read",
    ]


def test_a_self_referential_list_terminates() -> None:
    left: list[object] = []
    left.append(left)
    right: list[object] = []
    right.append(right)
    assert equivalent(left, right)


def test_two_objects_that_reference_each_other_terminate() -> None:
    class Node:
        def __init__(self, name: str) -> None:
            self.name = name
            self.peer: Node | None = None

    left, left_peer = Node("a"), Node("b")
    left.peer, left_peer.peer = left_peer, left
    right, right_peer = Node("a"), Node("b")
    right.peer, right_peer.peer = right_peer, right
    assert equivalent(left, right)


def test_a_cycle_does_not_hide_a_real_difference() -> None:
    """The memo answers "already being compared", never "equivalent, stop looking"."""

    class Node:
        def __init__(self, name: str) -> None:
            self.name = name
            self.peer: Node | None = None

    left, left_peer = Node("a"), Node("b")
    left.peer, left_peer.peer = left_peer, left
    right, right_peer = Node("a"), Node("z")
    right.peer, right_peer.peer = right_peer, right
    assert findings(left, right) == ["peer.name: 'b' instead of 'z'"]


def test_a_deep_cycle_under_a_raised_depth_still_terminates() -> None:
    left: list[object] = []
    left.append(left)
    right: list[object] = []
    right.append(right)
    assert equivalent(left, right, equivalency().with_max_depth(1000))


def test_an_unhashable_item_does_not_break_unordered_matching() -> None:
    left = [{"a": 1}, 2]
    right = [2, {"a": 1}]
    assert equivalent(left, right, equivalency().ignoring_order())


def test_a_hostile_hash_does_not_break_unordered_matching() -> None:
    class BadHash:
        def __hash__(self) -> int:
            raise RuntimeError("no")

        def __eq__(self, other: object) -> bool:
            return isinstance(other, BadHash)

        def __repr__(self) -> str:
            return "BadHash()"

    assert equivalent([BadHash()], [BadHash()], equivalency().ignoring_order())


def test_a_walk_that_blows_up_reports_a_difference_rather_than_equivalence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rule the whole module is arranged around: failing is the safe direction."""
    from lovely_assertions import _equivalence

    def explode(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("engine bug")

    monkeypatch.setattr(_equivalence, "Walk", explode)
    rendered = compare(1, 1, equivalency())
    assert rendered != ""
    assert "the comparison could not be completed" in rendered


def test_a_rendering_that_blows_up_still_reports_a_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lovely_assertions import _equivalence

    def explode(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("rendering bug")

    monkeypatch.setattr(_equivalence, "render", explode)
    rendered = compare(1, 2, equivalency())
    assert "could not be rendered" in rendered


def test_a_rendering_that_blows_up_does_not_invent_a_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard runs after the verdict, so equivalent values stay equivalent."""
    from lovely_assertions import _equivalence

    def explode(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("rendering bug")

    monkeypatch.setattr(_equivalence, "render", explode)
    assert compare(1, 1, equivalency()) == ""


# ---------------------------------------------------------------------------
# Values that render alike
# ---------------------------------------------------------------------------
def test_two_nans_are_named_rather_than_printed_twice() -> None:
    line = findings(float("nan"), float("nan"))[0]
    assert "a NaN is equal to nothing, itself included" in line


def test_the_same_nan_object_is_equivalent_to_itself() -> None:
    """Identity first, the rule ``list.__eq__`` applies internally."""
    value = float("nan")
    assert equivalent([value], [value])


def test_a_type_with_neither_eq_nor_members_says_so() -> None:
    class Opaque:
        __slots__ = ()

        def __repr__(self) -> str:
            return "Opaque()"

    line = findings(Opaque(), Opaque())[0]
    assert "has no __eq__ and no members to compare" in line


def test_two_values_that_render_alike_and_are_not_equal_say_so() -> None:
    class Weird:
        __slots__ = ()

        def __eq__(self, other: object) -> bool:
            return False

        def __hash__(self) -> int:
            return 0

        def __repr__(self) -> str:
            return "Weird()"

    line = findings(Weird(), Weird())[0]
    assert "both render as Weird(), but they are not equivalent" in line


# ---------------------------------------------------------------------------
# Bounded output
# ---------------------------------------------------------------------------
def test_a_hundred_differences_do_not_print_a_hundred_lines() -> None:
    left = list(range(100))
    right = list(range(100, 200))
    lines = findings(left, right)
    assert len(lines) == 11
    assert lines[-1] == "... (90 more differences)"


def test_the_walk_stops_collecting_and_says_that_it_did() -> None:
    """The cap is a stopping rule, and the count of what is held back reflects it.

    The surplus key matters: it is the one finding this mapping produces *after*
    the loop that watches the cap, so it is where a collector that merely filtered
    at render time rather than refusing at collection time would show up -- as
    "191 more" for a walk that stopped at 200.
    """
    left: dict[str, object] = {str(index): index for index in range(1000)}
    left["surplus"] = 1
    right = {str(index): index + 1 for index in range(1000)}
    lines = findings(left, right)
    assert lines[-2] == "... (190 more differences)"
    assert lines[-1] == "... (the comparison stopped at 200 differences)"


def test_the_rendering_bounds_are_the_formatting_scope() -> None:
    left = list(range(20))
    right = list(range(20, 40))
    with formatting(max_items=3):
        lines = findings(left, right)
    assert len(lines) == 4
    assert lines[-1] == "... (17 more differences)"


def test_an_enormous_value_is_clipped() -> None:
    line = findings("x" * 500, "y" * 500)[0]
    assert "more characters)" in line
    assert len(line) < 400


def test_a_long_list_of_missing_members_is_bounded() -> None:
    right = {str(index): index for index in range(50)}
    line = findings({}, right)[0]
    assert "... (40 more)]" in line


def test_unordered_matching_stops_and_names_the_bound_it_stopped_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The matching budget caps the *product* of the levels, which is where the cost is.

    Ten thousand structural matches at one level, each of which is another ten
    thousand at the next, is the one shape in this engine whose cost is not
    proportional to the graph it was handed. The bound is lowered here rather than
    reached, because reaching it honestly costs the second of nested pairing that
    the torture suite spends on the real shape once.

    The items are pairs that are *reordered* rather than merely shuffled, because
    the cheap equality pass settles a shuffle outright and never reaches the
    structural pairing this bound is on.
    """
    monkeypatch.setattr(_budget, "_MAX_MATCHING", 3)
    rows = [[1, 2], [3, 4], [5, 6], [7, 8]]
    reordered = [list(reversed(row)) for row in rows]
    with pytest.raises(ValueError, match="needed more than 3 comparisons") as caught:
        compare(rows, reordered, equivalency().ignoring_order())
    remedy = str(caught.value)
    assert "ignoring_order()" in remedy, remedy
    assert "matched by position instead" in remedy, remedy


def test_a_pairing_cut_short_is_neither_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrong *pass* a pairing cut short would introduce, from both directions.

    The two graphs below are equivalent with order ignored. Cut the
    allowance and the engine cannot establish that, so what it must not do is
    report a *difference*: a difference is a failure for ``is_equivalent_to`` and a
    **pass** for ``is_not_equivalent_to``, which means the same truncation would be
    a wrong answer in one of the two directions whichever way it fell. Neither is
    offered; the call raises.
    """
    items = [[1, 2], [3, 4], [5, 6], [7, 8]]
    other = [list(reversed(row)) for row in items]
    options = equivalency().ignoring_order()
    assert compare(items, other, options) == "", "with a whole allowance they are equivalent"
    monkeypatch.setattr(_budget, "_MAX_MATCHING", 3)
    with pytest.raises(ValueError, match="not a verdict, in either direction"):
        expect(items).is_equivalent_to(other, options=options)
    with pytest.raises(ValueError, match="not a verdict, in either direction"):
        expect(items).is_not_equivalent_to(other, options=options)


def test_walking_the_graph_it_was_handed_is_never_cut_short() -> None:
    """The other side of that bound: linear work on honest data is not clipped.

    Sixty thousand pairs of a graph nothing settles by ``==`` -- ten thousand
    identity-only records of six fields -- is well past the matching budget, and
    must still come back *equivalent* rather than "stopped".
    """
    left = [Slotted("h" + str(index), index) for index in range(10_000)]
    right = [Slotted("h" + str(index), index) for index in range(10_000)]
    assert left[0] != right[0]
    assert equivalent(left, right)


def test_a_wide_graph_does_not_recurse_forever() -> None:
    """A chain deeper than the bound stops at it rather than at the interpreter."""
    left: dict[str, object] = {}
    right: dict[str, object] = {}
    cursor, other = left, right
    for _ in range(500):
        cursor["n"] = {}
        other["n"] = {}
        cursor = cursor["n"]  # type: ignore[assignment]
        other = other["n"]  # type: ignore[assignment]
    cursor["end"] = 1
    other["end"] = 2
    lines = findings(left, right)
    assert len(lines) == 1
    assert "the maximum depth of 10 stops here" in lines[0]


# ---------------------------------------------------------------------------
# The formatter registry
# ---------------------------------------------------------------------------
def test_every_value_in_the_block_goes_through_the_formatter_registry() -> None:
    """A registry the flagship's own messages ignore is decoration.

    Every shape that renders a value is checked, because each reaches the registry
    by a different route: the pair of operands, the computed list of members, and
    the note that explains two values which render alike.

    Two shapes deliberately do *not* consult it, and both are pinned below rather
    than left to be discovered -- a kind mismatch, which names types rather than
    values, and a path, which has to be pasteable.
    """
    with soft_assertions(formatters=(Coins(),)) as scope:
        shallow = equivalency().with_max_depth(0)
        pair = findings(Money(1), Money(2), shallow)
        surplus = findings([Money(1)], [])
        alike = findings(Money(1), Money(1), shallow)
        kinds = findings(Money(1), [1])
        scope.discard()
    assert pair[0].startswith("the value itself: $1 instead of $2 (not taken apart")
    assert surplus[-1] == "[0]: extra items: [$1]"
    assert alike[0].startswith("the value itself: both render as $1")
    assert kinds == ["the value itself: types differ: Money instead of list"]


def test_a_path_is_spelled_with_repr_and_not_with_a_formatter() -> None:
    """The one deliberate exception, and the reason for it.

    A path is text the reader has to be able to paste into ``excluding_path``.
    A formatter renders a key *for a reader*; the two must not diverge in the one
    string the API matches against, so a key inside a path keeps its ``repr``.
    """
    key = Money(1)
    with soft_assertions(formatters=(Coins(),)) as scope:
        line = findings({key: 1}, {key: 2})[0]
        scope.discard()
    assert line.startswith("[<"), line
    assert "$1" not in line, line


# ---------------------------------------------------------------------------
# Module conventions
# ---------------------------------------------------------------------------
def test_the_module_hides_its_frames_from_an_assertion_traceback() -> None:
    """pytest reads ``__tracebackhide__`` from a frame's globals, so every module sets it."""
    from lovely_assertions import _equivalence, _exceptions

    assert _equivalence.__tracebackhide__ is _exceptions.hide_internal_frames


def test_the_public_names_are_sorted_and_resolve() -> None:
    from lovely_assertions import _equivalence

    assert list(_equivalence.__all__) == sorted(_equivalence.__all__)
    for name in _equivalence.__all__:
        assert hasattr(_equivalence, name)


def test_the_examples_in_the_docstrings_hold() -> None:
    """The docstrings promise specific output; a promise nobody checks is a comment."""
    import doctest

    from lovely_assertions import _equivalence

    results = doctest.testmod(
        _equivalence,
        extraglobs={"equivalency": equivalency, "close_within": close_within, "compare": compare},
    )
    assert results.failed == 0
    assert results.attempted > 0


def test_the_engine_holds_no_state_between_comparisons() -> None:
    """Two runs of one comparison read the same, whatever ran in between."""
    left = {"a": [1, 2]}
    right = {"a": [1, 3]}
    first = compare(left, right, equivalency())
    _ = compare({"z": 1}, {"z": 2}, equivalency().ignoring_order())
    assert compare(left, right, equivalency()) == first


def test_an_equivalency_can_be_shared_between_comparisons() -> None:
    options = equivalency().excluding("noise")
    assert equivalent({"noise": 1}, {"noise": 2}, options)
    assert equivalent({"noise": 3}, {"noise": 4}, options)
    assert options.excluded_names == frozenset({"noise"})


def test_a_comparator_may_call_back_into_the_engine() -> None:
    """The cycle memo travels with the walk, so a nested comparison gets a fresh one."""
    seen: list[Any] = []

    def by_id(actual: Plain, expected: Plain) -> bool:
        seen.append(actual)
        return compare(actual.__dict__, expected.__dict__, equivalency().excluding("noise")) == ""

    options = equivalency().using(Plain, by_id)
    assert equivalent(Plain(id=1, noise="a"), Plain(id=1, noise="b"), options)
    assert len(seen) == 1


# ---------------------------------------------------------------------------
# The cheap half of unordered pairing, and its bound
#
# `_equality_leftovers` pairs by equality before anything is compared
# structurally. Doing that through a hash alone pairs nothing at all in a list of
# `dict` records -- the ordinary shape of a JSON payload -- and hands every item
# to the structural pass, where a cap on the total then declines to look. The
# tests below are about the second pool: what it pairs, what it charges, and that
# a bound it hits is not an answer.
# ---------------------------------------------------------------------------
class NoHash:
    """Equal by value, and refusing to be hashed -- like every list and dict.

    Written as a ``__hash__`` that raises rather than as ``__hash__ = None``: the
    two are the same thing to every caller (``hash()`` raises ``TypeError``
    either way), and only the first one is a shape both type checkers accept.
    """

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        message = "unhashable type: 'NoHash'"
        raise TypeError(message)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NoHash) and other.value == self.value

    def __repr__(self) -> str:
        return "NoHash(" + str(self.value) + ")"


class HostileEq:
    """Unhashable, and it explodes when the scan asks whether it matches."""

    __slots__ = ()

    def __hash__(self) -> int:
        message = "unhashable type: 'HostileEq'"
        raise TypeError(message)

    def __eq__(self, other: object) -> bool:
        message = "no"
        raise RuntimeError(message)


def test_unhashable_items_pair_off_before_anything_is_compared_structurally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No structural allowance at all, and a shuffled list of records still pairs up.

    The sharpest form the claim can take: with ``_MAX_MATCHING`` at zero the engine
    may not run a single structural probe, so anything that comes back equivalent
    here was settled by equality -- which is what the second pool is for.
    """
    monkeypatch.setattr(_budget, "_MAX_MATCHING", 0)
    rows = [{"id": index} for index in range(120)]
    assert equivalent(rows, list(reversed(rows)), equivalency().ignoring_order())


def test_a_type_that_refuses_to_be_hashed_is_paired_by_the_scan() -> None:
    items = [NoHash(1), NoHash(2), NoHash(3)]
    other = [NoHash(3), NoHash(1), NoHash(2)]
    assert equivalent(items, other, equivalency().ignoring_order())


def test_the_scan_consumes_the_position_it_matched_and_not_another() -> None:
    """Interleaved pools: what is left over has to be the item nothing paired with."""
    options = equivalency().ignoring_order()
    left: list[object] = [1, {"a": 1}, 2, {"b": 2}]
    assert equivalent(left, [{"b": 2}, 2, {"a": 1}, 1], options)
    assert findings(left, [{"b": 2}, 2, {"a": 1}, 9], options) == [
        "the value itself: missing items: [9]",
        "the value itself: extra items: [1]",
    ]


def test_unhashable_duplicates_are_consumed_one_for_one() -> None:
    options = equivalency().ignoring_order()
    assert equivalent([[1], [1], [2]], [[2], [1], [1]], options)
    assert findings([[1], [1], [2]], [[1], [2]], options) == [
        "the value itself: extra items: [[1]]"
    ]


def test_an_item_whose_eq_explodes_during_the_scan_costs_that_item_only() -> None:
    """A value never turns into an error here, the scan included."""
    options = equivalency().ignoring_order()
    lines = findings([HostileEq(), [1]], [[1], HostileEq()], options)
    assert lines, "two objects that cannot answer == are not equivalent"
    assert all("missing items" in line or "extra items" in line for line in lines), lines


class _Unpoolable:  # noqa: PLW1641  (unhashable is the entire point)
    """A record nothing hashable can stand for.

    ``dict`` and ``list`` are canonicalised into the equality pool, so a list of
    either pairs in linear time and never reaches the scanning meter. The bound
    still exists and still has to be pinned, so these two tests use the one shape
    that cannot be pooled: ``__eq__`` defined and ``__hash__`` set to ``None``,
    which is what Python does to any class that defines equality without hashing.
    """

    __slots__ = ("identifier",)

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier

    # No `__hash__`: Python sets it to `None` for any class that defines `__eq__`
    # without one, which is exactly what makes this shape reach the scan.
    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Unpoolable) and self.identifier == other.identifier

    def __repr__(self) -> str:
        return "_Unpoolable(" + str(self.identifier) + ")"


def test_the_scanning_bound_stops_the_comparison_rather_than_answering_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 2)
    left = [_Unpoolable(1), _Unpoolable(2), _Unpoolable(3)]
    right = [_Unpoolable(3), _Unpoolable(2), _Unpoolable(1)]
    with pytest.raises(ValueError, match="needed more than 2 equality checks") as caught:
        compare(left, right, equivalency().ignoring_order())
    assert "cannot be hashed" in str(caught.value)


def test_a_scan_that_finds_nothing_is_charged_for_what_it_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The charge that makes the pathological case terminate at all.

    ``test_the_scanning_bound_stops_the_comparison_rather_than_answering_it`` pins
    the charge on a scan that *matches*; this pins the one on a scan that does not,
    and that is the load-bearing half. Items nothing pairs are exactly the shape
    that costs the most -- every one of them walks the whole pool -- so a scan that
    finds nothing and is charged nothing is not bounded by anything. Deleting the
    charge leaves the suite green and turns a list of unpaired records into a
    quadratic crawl with nothing to stop it.

    The right-hand records share no identifier with the left, so the first
    expected item alone walks all three positions and returns empty-handed.
    """
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 2)
    left = [_Unpoolable(1), _Unpoolable(2), _Unpoolable(3)]
    with pytest.raises(ValueError, match="needed more than 2 equality checks"):
        compare(
            left,
            [_Unpoolable(9), _Unpoolable(8), _Unpoolable(7)],
            equivalency().ignoring_order(),
        )


def test_a_set_can_reach_the_bound_without_anyone_asking_for_ignoring_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The remedy the message names has to be one this caller can actually take.

    ``ignoring_order()`` is opt-in for a sequence, so it is tempting to write the
    truncation message as advice to a caller who asked for it. A ``set`` has no
    positions, so ``_set`` matches its items the unordered way whatever the options
    say -- which puts an ordinary ``expect(left).is_equivalent_to(right)`` over two
    sets on the same path, under the default configuration. Telling that caller to
    "drop ignoring_order()" names an option they never wrote and cannot remove.
    """
    monkeypatch.setattr(_budget, "_MAX_MATCHING", 1)
    left = {frozenset({("k", index)}) for index in range(3)}
    right = {frozenset({("k", index + 100)}) for index in range(3)}
    with pytest.raises(ValueError, match="needed more than 1 comparisons") as caught:
        compare(left, right, equivalency())
    remedy = str(caught.value)
    assert "Compare fewer items in one call" in remedy
    assert "A set is matched this way whatever the options say" in remedy, remedy


def test_the_scanning_bound_is_not_spent_by_hashable_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second pool costs nothing at all to a comparison that does not need it."""
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 0)
    items = list(range(200))
    assert equivalent(items, list(reversed(items)), equivalency().ignoring_order())


def test_a_strictly_ordered_comparison_never_reaches_the_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Order is the default, and the default pays nothing for the option it did not take."""
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 0)
    monkeypatch.setattr(_budget, "_MAX_MATCHING", 0)
    rows = [{"id": index} for index in range(500)]
    assert equivalent(rows, [dict(row) for row in rows])


# ---------------------------------------------------------------------------
# `differs`: the same verdict, with no message built to reach it
# ---------------------------------------------------------------------------
_VERDICT_CASES: Final[list[tuple[object, object, Equivalency]]] = [
    (1, 1, equivalency()),
    (1, 2, equivalency()),
    ({"id": 1, "at": "x"}, {"id": 1, "at": "y"}, equivalency()),
    (
        User("ann", Address("Lyon", "69"), ["a"]),
        User("ann", Address("Lyon", "69"), ["a"]),
        equivalency(),
    ),
    (
        User("ann", Address("Lyon", "69"), ["a"]),
        User("ann", Address("Nice", "06"), ["a"]),
        equivalency(),
    ),
    ([1, 2, 3], [3, 2, 1], equivalency()),
    ([1, 2, 3], [3, 2, 1], equivalency().ignoring_order()),
    (Plain(a=1, b=2), Plain(a=1), equivalency()),
    (Plain(a=1, b=2), Plain(a=1), equivalency().comparing_all_members()),
    (float("nan"), float("nan"), equivalency()),
]


@pytest.mark.parametrize(("actual", "expected", "options"), _VERDICT_CASES)
def test_differs_answers_exactly_what_compare_answers(
    actual: object, expected: object, options: Equivalency
) -> None:
    """One walk, two callers: the boolean must not be a second opinion."""
    assert _equivalence.differs(actual, expected, options) == (
        compare(actual, expected, options) != ""
    )


def test_differs_builds_no_report_even_when_there_is_one_to_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The point of it: the passing branch of ``is_not_equivalent_to`` renders nothing.

    Counted rather than forbidden, because ``compare`` survives a ``_render`` that
    raises -- that is its contract -- and a test that only planted an explosion
    would pass with ``differs`` defined as ``compare(...) != ""``. What is asserted
    is the number: nought for the boolean, one for the block.
    """
    rendered_reports = 0
    render = getattr(_equivalence, "render")  # noqa: B009  (a private name, read as data)

    def counted(*arguments: object) -> str:
        nonlocal rendered_reports
        rendered_reports += 1
        return cast("str", render(*arguments))

    monkeypatch.setattr(_equivalence, "render", counted)
    assert _equivalence.differs({"a": 1}, {"a": 2}, equivalency()) is True
    assert rendered_reports == 0, "differs built a report nobody asked for"
    assert compare({"a": 1}, {"a": 2}, equivalency()) != ""
    assert rendered_reports == 1, "compare must still build the report"


def test_differs_never_reads_the_formatting_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """``current_formatting()`` is a ``ContextVar`` lookup, and it is off this path.

    Building a block reads it once for the block, once per rendered value and once
    per clipped string. On the branch where ``is_not_equivalent_to`` *passes*
    nothing is ever looked at, so none of those reads may happen at all.
    """
    reads = 0
    # Read from its own home rather than through a module that merely imports it:
    # the two are the same function, and only one of them is an export.
    from lovely_assertions._formatting import current_formatting as formatting_now

    def counted() -> object:
        nonlocal reads
        reads += 1
        return formatting_now()

    # Two readers, so two patches: the engine is a package now, and each module
    # that reads the context holds its own binding for it.
    monkeypatch.setattr(_labels, "current_formatting", counted)
    monkeypatch.setattr(_rendering, "current_formatting", counted)
    assert _equivalence.differs(User("ann", Address("Lyon", "69"), ["a", "b"]), 3, equivalency())
    assert reads == 0, f"differs read the formatting context {reads} times"


def test_differs_refuses_a_misconfigured_call_the_way_compare_does() -> None:
    with pytest.raises(TypeError, match="options must be an Equivalency"):
        _ = _equivalence.differs(1, 1, cast("Equivalency", "not options"))


def test_differs_reports_a_pairing_it_could_not_finish_as_neither_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A boolean has no room for a third answer, so it raises rather than guessing."""
    monkeypatch.setattr(_budget, "_MAX_MATCHING", 1)
    left = [{"id": index} for index in range(6)]
    right = [{"id": index + 100} for index in range(6)]
    with pytest.raises(ValueError, match="needed more than 1 comparisons"):
        _ = _equivalence.differs(left, right, equivalency().ignoring_order())


def test_differs_says_they_differ_when_the_walk_itself_broke() -> None:
    """The same safe direction ``compare`` takes: a comparison that broke is not silence."""

    def explode(*_: object, **__: object) -> object:
        message = "the walk broke"
        raise RuntimeError(message)

    assert _equivalence.differs(1, 1, equivalency()) is False
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_equivalence, "Walk", explode)
        assert _equivalence.differs(1, 2, equivalency()) is True


def test_differs_discards_a_remembered_route_when_an_abc_takes_a_new_member() -> None:
    """``differs`` checks the ABC token itself rather than riding on ``compare``'s.

    The two entry points share :data:`_ROUTE_BY_TYPE`, and ``is_equivalent_to``
    reaches the boolean one *first* -- on the passing branch it is the only one
    reached at all. A stale route read there is a verdict taken from the wrong
    describer, which is the same wrong answer
    ``test_a_remembered_route_is_discarded_when_an_abc_takes_a_new_member``
    rules out for the reporting path.
    """

    class Rowish:
        __slots__ = ("items", "label")

        def __init__(self, label: str, items: list[int], /) -> None:
            self.label = label
            self.items = items

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, index: int) -> int:
            return self.items[index]

    left = Rowish("x", [1, 2])
    right = Rowish("y", [1, 2])

    # A record while nothing claims it: `label` is a field, and the two disagree.
    assert _equivalence.differs(left, right, equivalency()) is True

    cast("ABCMeta", Sequence).register(Rowish)

    # A sequence now: `label` is not an item, and the items agree.
    assert _equivalence.differs(left, right, equivalency()) is False


def test_differs_refuses_a_walk_that_ran_out_of_stack() -> None:
    """The other way a walk stops without finishing, and a boolean has no third answer.

    ``compare`` is shown doing this in ``tests/test_equivalence_torture.py``. Here
    it matters more: a ``RecursionError`` read as *they differ* is the branch on
    which ``is_not_equivalent_to`` **passes**, so two identical graphs and a depth
    bound long enough to exhaust the stack would be a silent green.
    """

    class Link:
        __slots__ = ("child",)

        def __init__(self, child: "Link | None", /) -> None:
            self.child = child

    def chain(length: int, /) -> Link:
        node = Link(None)
        for _ in range(length - 1):
            node = Link(node)
        return node

    with pytest.raises(ValueError, match="used up the interpreter's stack") as failure:
        _ = _equivalence.differs(chain(400), chain(400), equivalency().with_max_depth(500))

    assert "allowed to descend 500 levels" in str(failure.value)


# ---------------------------------------------------------------------------
# What a type declares is worked out once
# ---------------------------------------------------------------------------
def _user(name: str, /) -> User:
    return User(name, Address("Lyon", "69"), ["a"])


def test_a_type_resolved_once_still_resolves_the_same_way() -> None:
    """The caches answer for the class, so the second instance must read the same."""
    first = findings(_user("ann"), _user("bob"))
    second = findings(_user("ann"), _user("bob"))
    assert first == second == ["name: 'ann' instead of 'bob'"]


def test_what_a_type_declares_is_worked_out_once_and_then_remembered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not an optimisation to take on trust; the second comparison must not re-derive it.

    Resolving what a type declares runs ``dataclasses.fields()``, an MRO lookup
    for ``_fields`` and another for ``__attrs_attrs__``, and for a value that
    declares nothing most of the cost is an exception raised and caught -- all of
    it on a function the walk calls twice for every pair it takes apart.
    """
    resolutions = 0
    resolve = getattr(_classified_fields, "_resolve_declared_field_names")  # noqa: B009

    def counted(value: object, /) -> object:
        nonlocal resolutions
        resolutions += 1
        return resolve(value)

    getattr(_classified_fields, "_DECLARED_BY_TYPE").clear()  # noqa: B009
    # `_ROUTE_BY_TYPE` sits in front of it and would answer for the whole
    # classification before `_declared_field_names` was ever reached.
    getattr(_equivalence, "ROUTE_BY_TYPE").clear()  # noqa: B009
    monkeypatch.setattr(_classified_fields, "_resolve_declared_field_names", counted)
    assert findings(_user("ann"), _user("bob")) == ["name: 'ann' instead of 'bob'"]
    first_pass = resolutions
    assert first_pass > 0, "nothing was resolved at all"
    assert findings(_user("ann"), _user("bob")) == ["name: 'ann' instead of 'bob'"]
    assert resolutions == first_pass, "a type resolved once was resolved again"


def test_what_a_types_slots_hold_is_worked_out_once_too() -> None:
    """The other half: an MRO walk per pair, for an answer that belongs to the class."""
    slots: dict[type, object] = getattr(_fields, "_SLOTS_BY_TYPE")  # noqa: B009
    slots.clear()
    assert findings(Slotted("a", 1), Slotted("a", 2)) == ["port: 1 instead of 2"]
    assert Slotted in slots, "the type's slots were resolved and thrown away"


def test_the_type_caches_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cache keyed on class objects keeps every class it has seen alive.

    A suite that builds a class per test would grow it without bound, so the miss
    path empties it rather than letting it become a leak with a lookup on top.
    """
    monkeypatch.setattr(_cache, "_MAX_CACHED_TYPES", 2)
    declared: dict[type, object] = getattr(_classified_fields, "_DECLARED_BY_TYPE")  # noqa: B009
    slots: dict[type, object] = getattr(_fields, "_SLOTS_BY_TYPE")  # noqa: B009
    routes: dict[type, object] = getattr(_equivalence, "ROUTE_BY_TYPE")  # noqa: B009
    declared.clear()
    slots.clear()
    routes.clear()
    for index in range(20):
        made = type(f"Built{index}", (), {"__slots__": ("value",)})
        instance = made()
        instance.value = index  # pyright: ignore[reportAttributeAccessIssue]
        twin = made()
        twin.value = index  # pyright: ignore[reportAttributeAccessIssue]
        assert equivalent(instance, twin)
        assert len(declared) <= 2
        assert len(slots) <= 2
        assert len(routes) <= 2


def test_a_remembered_route_is_discarded_when_an_abc_takes_a_new_member() -> None:
    """The soundness argument for :data:`_ROUTE_BY_TYPE`, checked rather than asserted.

    Classification is remembered per type because every question but one is asked
    of the type. Three of those questions -- ``Mapping``, ``Set``, ``Sequence`` --
    are ABCs, and an ABC takes virtual subclasses *after* the type exists, so
    ``Sequence.register(X)`` really does change the right answer for an ``X``
    already in the table.

    ``abc.get_cache_token()`` moves when that happens, which is what the token is
    for and what ``functools.singledispatch`` guards on. The same argument, the
    same mechanism and the same test as ``tests/test_dispatch_memo.py`` makes for
    the dispatch table.
    """

    class Rowish:
        __slots__ = ("items",)

        def __init__(self) -> None:
            self.items = [1, 2]

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, index: int) -> int:
            return self.items[index]

    classify: Callable[[object], tuple[str, tuple[str, ...]]] = _classification.classify

    # A record while nothing claims it: its one stored field is compared by name.
    assert compare(Rowish(), Rowish(), equivalency()) == ""
    assert classify(Rowish())[0] == "record"

    # Cast to the metaclass: typeshed declares `register` on `ABCMeta` and not on
    # the ABCs themselves, so `Sequence.register(...)` is a pyright error even
    # though it is the spelling every project uses.
    cast("ABCMeta", Sequence).register(Rowish)
    _ = compare(Rowish(), Rowish(), equivalency())  # a comparison checks the token

    after = classify(Rowish())[0]
    assert after == "sequence", f"the token did not discard the stale route: still {after!r}"


class Proxying:
    """A stand-in that answers ``isinstance`` from the instance, not from its class.

    ``wrapt``'s object proxies and Django's lazy objects are this shape: one
    ``type()`` at runtime, and a ``__class__`` read off the instance. So two values
    the route cache cannot tell apart can be a mapping and not a mapping.

    Not a ``dict`` subclass, deliberately: ``isinstance`` answers from the real
    type as well as from ``__class__``, so inheriting the shape would hide the very
    disagreement this double exists to create. It reads like a mapping through the
    entries it holds instead.
    """

    __slots__ = ("_claimed", "entries")

    def __init__(self, claimed: type, entries: dict[str, int], /) -> None:
        self._claimed = claimed
        self.entries = entries

    @property
    def __class__(self) -> type:
        return self._claimed

    @__class__.setter
    def __class__(self, claimed: type, /) -> None:
        self._claimed = claimed

    def __repr__(self) -> str:
        return "Proxying(" + self._claimed.__name__ + ", " + repr(self.entries) + ")"

    def __iter__(self) -> "Iterator[str]":
        return iter(self.entries)

    def __getitem__(self, key: str, /) -> int:
        return self.entries[key]


def test_a_route_that_does_not_fit_the_subject_is_a_difference_and_not_a_pass() -> None:
    """The other hazard of :data:`_ROUTE_BY_TYPE`: a class the instance decides.

    The route is worked out once per ``type()``, but ``Mapping`` membership is an
    ``isinstance`` question and ``isinstance`` reads ``__class__``. Prime the cache
    with an instance that really is a mapping and the next one of the same
    ``type()`` is walked as one, whatever it turns out to be. The branch that
    notices has to record a difference: :func:`compare` reads silence as
    *equivalent*, so the failure to catch here is a passing test.
    """
    assert equivalent(Proxying(dict, {"id": 1}), {"id": 1}), "the route was not primed"

    reported = findings(Proxying(list, {"id": 1}), {"id": 2})

    assert reported == ["the value itself: Proxying(list, {'id': 1}) instead of {'id': 2}"]


def test_a_route_that_does_not_fit_the_expectation_is_a_difference_too() -> None:
    """The guard reads both sides, so the expectation reaches it the other way."""
    assert equivalent({"id": 1}, Proxying(dict, {"id": 1})), "the route was not primed"

    reported = findings({"id": 2}, Proxying(list, {"id": 1}))

    assert reported == ["the value itself: {'id': 2} instead of Proxying(list, {'id': 1})"]


# ---------------------------------------------------------------------------
# The internals' reprs
#
# Debugging surface, and the only thing a reader of a paused walk has to go on.
# A repr that names the wrong field, or drops one, is worse than no repr at all:
# it is read as a fact about the object. So each is pinned as an exact string,
# built from an instance whose every number is chosen here rather than inherited
# from a module constant.
# ---------------------------------------------------------------------------
def internal(name: str, /) -> Any:
    """One of the engine's names, read out of the package as data.

    A direct attribute access to a protected name across a module boundary is what
    pyright reports, which is why the rest of this file reaches for them the same
    way -- and these are wanted for what their ``repr`` says rather than for their
    types.

    The package is searched rather than its front door, because most of these are
    not on it: the engine is a package of one concern per module, and a class the
    front door has no use for is not re-exported there just so a test can find it.
    Searching keeps this working the next time a module is split.
    """
    for candidate in (name, name.lstrip("_"), "_" + name.lstrip("_")):
        if hasattr(_equivalence, candidate):
            return getattr(_equivalence, candidate)
    for module in vars(_equivalence).values():
        if getattr(module, "__name__", "").startswith("lovely_assertions._equivalence."):
            for candidate in (name, name.lstrip("_"), "_" + name.lstrip("_")):
                if hasattr(module, candidate):
                    return getattr(module, candidate)
    message = f"no {name!r} anywhere in lovely_assertions._equivalence"
    raise AttributeError(message)


def test_a_difference_reprs_as_its_path_and_the_shape_it_shows() -> None:
    pair = internal("pair_difference")("user.name", "ann", "bob")
    items = internal("items_difference")("rows", "missing items:", [1, 2])

    assert repr(pair) == "Difference('user.name', 'pair')"
    assert repr(items) == "Difference('rows', 'items')"


def test_findings_reprs_as_what_it_holds_against_what_it_will_take() -> None:
    collector = internal("Findings")(3)
    collector.add(internal("_note_difference")("a", "this entry could not be read"))

    assert repr(collector) == "Findings(1 of 3)"


def test_a_budget_reprs_as_what_is_left_of_each_of_its_two_meters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both allowances are set here, so the string cannot quietly track a constant."""
    monkeypatch.setattr(_budget, "_MAX_MATCHING", 7)
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 9)
    budget = internal("Budget")()

    budget.spend_comparison()
    budget.spend_scans(2)

    assert repr(budget) == "Budget(6 comparisons, 7 scans left)"


def test_a_memo_reprs_as_what_is_open_and_what_it_has_settled() -> None:
    """One open and two settled, so a repr that read the wrong field would say so."""
    memo = internal("Memo")()

    memo.open[(1, 2)] = 0
    memo.settled[(1, 2, 0)] = ("a", "b")
    memo.settled[(3, 4, 1)] = ("c", "d")

    assert repr(memo) == "Memo(1 open, 2 settled)"


def test_a_walk_reprs_as_the_configuration_it_is_carrying() -> None:
    """The one of the five fields that says which comparison this walk is."""
    walk = internal("Walk")(
        equivalency().ignoring_order(),
        internal("Memo")(),
        internal("Findings")(1),
        internal("Budget")(),
        False,
    )

    assert repr(walk) == "Walk(equivalency().ignoring_order())"
