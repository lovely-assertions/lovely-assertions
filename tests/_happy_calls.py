"""One passing call per public assertion, and the two guards that read it.

The dispatch in ``src/lovely_assertions/_subjects.py`` calls itself "one table
seen twice" -- the runtime chain and the overloads are the same order written
down twice, and the comment is there because the day they drift is the day one of
them is wrong. This module is the same move, one level up: **one table, two
guards.**

``tests/test_happy_path.py`` runs every entry with the failure machinery
booby-trapped, and proves no passing assertion *calls* into it.
``tests/test_performance_invariants.py`` runs every entry under ``tracemalloc``,
and proves no passing assertion *allocates* on its way through. The two see
genuinely different bugs -- a message assembled by a C-level call reaches no
trapped name, and a ``ContextVar`` read allocates nothing -- but they need
exactly the same thing to work: a call that passes, on a subject that exists,
for every assertion the package exports. Written out twice, the second copy
becomes a sample of the first, and a guard over a sample reports coverage it does
not have -- an assertion nobody listed is an assertion both files call covered
and neither one touches.

So the table is written once and imported twice, and the count is the same count
in both files. An assertion added tomorrow with no entry here turns
``test_every_public_assertion_has_a_happy_path_exercise`` red and names itself,
and from that moment both guards cover it.

**What an entry has to be.** A callable that takes the :class:`World` fixture
and performs exactly one assertion, which passes. It may build its own subject --
``lambda _: expect(3).is_equal_to(3)`` -- because a passing call cannot be
generated from a signature and readability is what keeps the table honest. The
allocation guard cancels that construction rather than asking the table to be
written for its convenience; how it does that, and what it costs, is documented
there.

**Why the published names carry no leading underscore.** A name imported across a
module boundary is that module's public surface, and pyright says so with
``reportPrivateUsage``; silencing it with ``# pyright: ignore`` to keep a private
spelling is exactly the kind of thing this repository refuses to write. So
everything the two guards import -- :data:`HAPPY_CALLS`, :class:`World`,
:data:`PUBLIC_ASSERTIONS` and the rest -- is spelled public, and only those.
Everything used solely to build the table below (``_Colour``, ``_caught``,
``_SAME``) stays private, because it is.
"""

import abc
import enum
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from importlib import import_module
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final, Protocol, runtime_checkable
from unittest.mock import Mock

import pytest

import lovely_assertions
from _package import module_name, sources
from lovely_assertions import (
    Expect,
    MockExpect,
    RaisedExpect,
    WarnedExpect,
    exactly,
    expect,
    expect_raises,
    expect_warns,
)
from lovely_assertions._datetime import WithinDelta


def library_modules() -> list[ModuleType]:
    """Every module in the package, the package itself included."""
    package = Path(lovely_assertions.__file__).parent
    return [
        import_module(name)
        for name in sorted({module_name(path, package) for path in sources(package)})
    ]


class _Colour(enum.Enum):
    RED = "red"
    GREEN = "green"


class _Shade(enum.Enum):
    RED = "red"


class _Access(enum.Flag):
    READ = enum.auto()
    WRITE = enum.auto()


class _Abstract(abc.ABC):
    """A class with an unimplemented member, so ``is_abstract`` has a subject."""

    @abc.abstractmethod
    def go(self) -> None: ...


@runtime_checkable
class _Countable(Protocol):
    """Runtime-checkable, which is what ``implements`` requires of a protocol."""

    def __len__(self) -> int: ...


def _raise_plain() -> None:
    raise ValueError("boom")


def _raise_with_note() -> None:
    error = ValueError("boom")
    error.add_note("a note")
    raise error


def _raise_with_cause() -> None:
    raise ValueError("boom") from TypeError("root")


def _caught() -> RaisedExpect[ValueError]:
    """A handle from the context-manager form, which is a ``_CaughtExpect``.

    ``expect_raises`` declares :class:`RaisedExpect`, because that is what the
    ``as`` binding needs; the object is a ``_CaughtExpect``, and three of its
    assertions are its own. This is how the enumeration gets at them.
    """
    with expect_raises(ValueError) as caught:
        _raise_plain()
    return caught


def _issue_warning() -> None:
    """The smallest callable that warns. Used by the warning rows below."""
    import warnings

    warnings.warn("parse() is deprecated since 2.0", UserWarning, stacklevel=2)


def _warned() -> "WarnedExpect[UserWarning]":
    """A subject holding one captured warning, built fresh for each row.

    `expect_warns` is a context manager, so a `WarnedExpect` cannot be built once
    and shared: the capture has to open and close around the call that warns. The
    detonator measures what happens *after* the `with` block, which is where the
    three `WarnedExpect` assertions live.
    """
    with expect_warns(UserWarning) as warned:
        _issue_warning()
    return warned


@dataclass(frozen=True, slots=True)
class World:
    """The fixtures a happy-path call may need: files, links, mocks."""

    file: Path
    empty_file: Path
    directory: Path
    empty_directory: Path
    missing: Path
    link: Path | None
    called: Mock
    uncalled: Mock


def build_world(root: Path, /) -> World:
    """Lay the fixtures out under ``root``.

    Separate from the fixture that calls it so that the table can be measured
    outside pytest: the numbers recorded in the allocation guard are produced by a
    script that imports this module and has no ``TempPathFactory`` to hand.
    """
    directory = root / "holder"
    directory.mkdir()
    file = directory / "note.txt"
    # `newline=""` rather than the default: text mode translates "\n" to the
    # platform's line ending on the way out, and a table below asserts this
    # file's exact size in bytes.
    file.write_text("hello world\n", encoding="utf-8", newline="")
    empty_file = directory / "empty.txt"
    empty_file.touch()
    empty_directory = root / "hollow"
    empty_directory.mkdir()
    made = root / "link.txt"
    link: Path | None = made
    try:
        made.symlink_to(file)
    except (OSError, NotImplementedError):  # pragma: no cover - depends on the platform
        # Windows makes a symbolic link only for a process holding
        # SeCreateSymbolicLinkPrivilege: an elevated one, or an ordinary one with
        # Developer Mode on. Unguarded, that refusal escapes a module-scoped
        # fixture and turns every row of this table into an error, for the sake of
        # the one row that needs a link. The world is built without it instead.
        link = None
    called = Mock()
    called(1, key="v")
    return World(
        file=file,
        empty_file=empty_file,
        directory=directory,
        empty_directory=empty_directory,
        missing=root / "absent.txt",
        link=link,
        called=called,
        uncalled=Mock(),
    )


def _linked(world: World, /) -> Path:
    """The symbolic link, or a skip on a platform that would not make one.

    Only the row asking about a link stands down; every other row keeps working
    on a machine that cannot create one.
    """
    if world.link is None:  # pragma: no cover - depends on the platform
        pytest.skip("symbolic links are unavailable here")
    return world.link


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> World:
    """One set of files, links and mocks per module that reads the table."""
    return build_world(tmp_path_factory.mktemp("happy-path"))


_SAME: Final = object()


@dataclass
class _Shape:
    """A subject with structure, for the two assertions that walk an object graph."""

    name: str
    parts: "list[_Shape]"


def _shape(depth: int, tag: str, /) -> _Shape:
    """A tree. Binary and five deep is sixty-three nodes -- enough to be a walk."""
    if depth == 0:
        return _Shape(tag, [])
    return _Shape("node" + str(depth), [_shape(depth - 1, tag), _shape(depth - 1, tag)])


#: Two graphs that differ, and one pair that does not. The subject has to be
#: something the walk must descend: ``expect(3).is_equivalent_to(3)`` returns at
#: the leaf, so the allocation guard would measure the engine starting up and
#: nothing it does. A passing branch that builds a full difference report and
#: drops it unread would then be recorded at what a pair of integers costs, orders
#: of magnitude below what the same call holds on a graph. Every leaf differs, so
#: the report the **passing** branch must not build is one the engine would have
#: something to say in.
_GRAPH: Final = _shape(5, "leaf")
_SAME_GRAPH: Final = _shape(5, "leaf")
_OTHER_GRAPH: Final = _shape(5, "other")

#: One passing invocation per public assertion, keyed by ``(defining class,
#: method)`` -- the same key the enumeration below produces. Written by hand
#: because a *passing* call cannot be generated from a signature: the arguments
#: are what make it pass.
HAPPY_CALLS: Final[dict[tuple[str, str], Callable[[World], object]]] = {
    # -- Expect ------------------------------------------------------------
    ("Expect", "as_type"): lambda _: expect("x").as_type(str),
    ("Expect", "described_as"): lambda _: expect(3).described_as("the count"),
    ("Expect", "is_equal_to"): lambda _: expect(3).is_equal_to(3),
    ("Expect", "is_equivalent_to"): lambda _: expect(_GRAPH).is_equivalent_to(_SAME_GRAPH),
    ("Expect", "is_exactly_instance_of"): lambda _: expect(3).is_exactly_instance_of(int),
    ("Expect", "is_falsy"): lambda _: expect(0).is_falsy(),
    ("Expect", "is_in"): lambda _: expect(3).is_in([3]),
    ("Expect", "is_instance_of"): lambda _: expect(3).is_instance_of(int),
    ("Expect", "is_none"): lambda _: expect(None).is_none(),
    ("Expect", "is_not_equal_to"): lambda _: expect(3).is_not_equal_to(4),
    ("Expect", "is_not_equivalent_to"): lambda _: expect(_GRAPH).is_not_equivalent_to(_OTHER_GRAPH),
    ("Expect", "is_not_exactly_instance_of"): lambda _: expect(3).is_not_exactly_instance_of(str),
    ("Expect", "is_not_in"): lambda _: expect(3).is_not_in([4]),
    ("Expect", "is_not_instance_of"): lambda _: expect(3).is_not_instance_of(str),
    ("Expect", "is_not_none"): lambda _: expect(3).is_not_none(),
    ("Expect", "is_not_same_as"): lambda _: expect(_SAME).is_not_same_as(object()),
    ("Expect", "is_one_of"): lambda _: expect(3).is_one_of(3, 4),
    ("Expect", "is_same_as"): lambda _: expect(_SAME).is_same_as(_SAME),
    ("Expect", "is_truthy"): lambda _: expect(1).is_truthy(),
    ("Expect", "matches"): lambda _: expect(3).matches(lambda value: value == 3),
    # -- BoolExpect --------------------------------------------------------
    ("BoolExpect", "implies"): lambda _: expect(True).implies(True),
    ("BoolExpect", "is_false"): lambda _: expect(False).is_false(),
    ("BoolExpect", "is_not_false"): lambda _: expect(True).is_not_false(),
    ("BoolExpect", "is_not_true"): lambda _: expect(False).is_not_true(),
    ("BoolExpect", "is_true"): lambda _: expect(True).is_true(),
    # -- NumericExpect -----------------------------------------------------
    ("NumericExpect", "is_close_to"): lambda _: expect(1.0).is_close_to(1.05, tol=0.1),
    ("NumericExpect", "is_infinite"): lambda _: expect(float("inf")).is_infinite(),
    ("NumericExpect", "is_nan"): lambda _: expect(float("nan")).is_nan(),
    ("NumericExpect", "is_not_close_to"): lambda _: expect(1.0).is_not_close_to(5.0, tol=0.1),
    ("NumericExpect", "is_not_infinite"): lambda _: expect(1.0).is_not_infinite(),
    ("NumericExpect", "is_not_nan"): lambda _: expect(1.0).is_not_nan(),
    # -- OrderedExpect -----------------------------------------------------
    ("OrderedExpect", "is_between"): lambda _: expect(2).is_between(1, 3),
    ("OrderedExpect", "is_greater_than"): lambda _: expect(2).is_greater_than(1),
    ("OrderedExpect", "is_greater_than_or_equal_to"): lambda _: expect(
        2
    ).is_greater_than_or_equal_to(2),
    ("OrderedExpect", "is_less_than"): lambda _: expect(1).is_less_than(2),
    ("OrderedExpect", "is_less_than_or_equal_to"): lambda _: expect(2).is_less_than_or_equal_to(2),
    ("OrderedExpect", "is_negative"): lambda _: expect(-1).is_negative(),
    ("OrderedExpect", "is_not_between"): lambda _: expect(9).is_not_between(1, 3),
    ("OrderedExpect", "is_not_zero"): lambda _: expect(1).is_not_zero(),
    ("OrderedExpect", "is_positive"): lambda _: expect(1).is_positive(),
    ("OrderedExpect", "is_strictly_between"): lambda _: expect(2).is_strictly_between(1, 3),
    ("OrderedExpect", "is_zero"): lambda _: expect(Decimal(0)).is_zero(),
    # -- StringExpect ------------------------------------------------------
    ("StringExpect", "contains"): lambda _: expect("abcabc").contains("a", occurrences=exactly(2)),
    ("StringExpect", "contains_all"): lambda _: expect("abc").contains_all("a", "b"),
    ("StringExpect", "contains_any"): lambda _: expect("abc").contains_any("a", "z"),
    ("StringExpect", "contains_ignoring_case"): lambda _: expect("ABC").contains_ignoring_case("a"),
    ("StringExpect", "does_not_contain"): lambda _: expect("abc").does_not_contain("z"),
    ("StringExpect", "does_not_contain_all"): lambda _: expect("abc").does_not_contain_all(
        "a", "z"
    ),
    ("StringExpect", "does_not_contain_any"): lambda _: expect("abc").does_not_contain_any(
        "y", "z"
    ),
    ("StringExpect", "does_not_contain_ignoring_case"): lambda _: expect(
        "abc"
    ).does_not_contain_ignoring_case("z"),
    ("StringExpect", "does_not_end_with"): lambda _: expect("abc").does_not_end_with("z"),
    ("StringExpect", "does_not_end_with_ignoring_case"): lambda _: expect(
        "abc"
    ).does_not_end_with_ignoring_case("z"),
    ("StringExpect", "does_not_match"): lambda _: expect("abc").does_not_match(r"^z"),
    ("StringExpect", "does_not_match_wildcard"): lambda _: expect("abc").does_not_match_wildcard(
        "z*"
    ),
    ("StringExpect", "does_not_match_wildcard_ignoring_case"): lambda _: expect(
        "abc"
    ).does_not_match_wildcard_ignoring_case("z*"),
    ("StringExpect", "does_not_start_with"): lambda _: expect("abc").does_not_start_with("z"),
    ("StringExpect", "does_not_start_with_ignoring_case"): lambda _: expect(
        "abc"
    ).does_not_start_with_ignoring_case("z"),
    ("StringExpect", "ends_with"): lambda _: expect("abc").ends_with("c"),
    ("StringExpect", "ends_with_ignoring_case"): lambda _: expect("abc").ends_with_ignoring_case(
        "C"
    ),
    ("StringExpect", "has_length"): lambda _: expect("abc").has_length(3),
    ("StringExpect", "is_alnum"): lambda _: expect("abc123").is_alnum(),
    ("StringExpect", "is_alpha"): lambda _: expect("abc").is_alpha(),
    ("StringExpect", "is_ascii"): lambda _: expect("abc").is_ascii(),
    ("StringExpect", "is_blank"): lambda _: expect("   ").is_blank(),
    ("StringExpect", "is_digit"): lambda _: expect("123").is_digit(),
    ("StringExpect", "is_empty"): lambda _: expect("").is_empty(),
    ("StringExpect", "is_equal_ignoring_case"): lambda _: expect("abc").is_equal_ignoring_case(
        "ABC"
    ),
    ("StringExpect", "is_identifier"): lambda _: expect("name").is_identifier(),
    ("StringExpect", "is_lower"): lambda _: expect("abc").is_lower(),
    ("StringExpect", "is_not_alnum"): lambda _: expect("a b").is_not_alnum(),
    ("StringExpect", "is_not_alpha"): lambda _: expect("a1").is_not_alpha(),
    ("StringExpect", "is_not_ascii"): lambda _: expect("é").is_not_ascii(),
    ("StringExpect", "is_not_blank"): lambda _: expect("abc").is_not_blank(),
    ("StringExpect", "is_not_digit"): lambda _: expect("abc").is_not_digit(),
    ("StringExpect", "is_not_empty"): lambda _: expect("abc").is_not_empty(),
    ("StringExpect", "is_not_equal_ignoring_case"): lambda _: expect(
        "abc"
    ).is_not_equal_ignoring_case("xyz"),
    ("StringExpect", "is_not_identifier"): lambda _: expect("a b").is_not_identifier(),
    ("StringExpect", "is_not_lower"): lambda _: expect("ABC").is_not_lower(),
    ("StringExpect", "is_not_numeric"): lambda _: expect("abc").is_not_numeric(),
    ("StringExpect", "is_not_printable"): lambda _: expect("a\tb").is_not_printable(),
    ("StringExpect", "is_not_space"): lambda _: expect("abc").is_not_space(),
    ("StringExpect", "is_not_title"): lambda _: expect("abc").is_not_title(),
    ("StringExpect", "is_not_upper"): lambda _: expect("abc").is_not_upper(),
    ("StringExpect", "is_numeric"): lambda _: expect("123").is_numeric(),
    ("StringExpect", "is_printable"): lambda _: expect("abc").is_printable(),
    ("StringExpect", "is_space"): lambda _: expect("   ").is_space(),
    ("StringExpect", "is_title"): lambda _: expect("Abc Def").is_title(),
    ("StringExpect", "is_upper"): lambda _: expect("ABC").is_upper(),
    ("StringExpect", "is_uuid"): lambda _: expect("12345678-1234-5678-1234-567812345678").is_uuid(),
    ("StringExpect", "matches"): lambda _: expect("abc").matches(r"^abc$"),
    ("StringExpect", "matches_wildcard"): lambda _: expect("abc").matches_wildcard("a*"),
    ("StringExpect", "matches_wildcard_ignoring_case"): lambda _: expect(
        "abc"
    ).matches_wildcard_ignoring_case("A*"),
    ("StringExpect", "starts_with"): lambda _: expect("abc").starts_with("a"),
    ("StringExpect", "starts_with_ignoring_case"): lambda _: expect(
        "abc"
    ).starts_with_ignoring_case("A"),
    # -- CollectionExpect --------------------------------------------------
    ("CollectionExpect", "all_are_exactly_type"): lambda _: expect([1, 2]).all_are_exactly_type(
        int
    ),
    ("CollectionExpect", "all_are_instance_of"): lambda _: expect([1, 2]).all_are_instance_of(int),
    ("CollectionExpect", "all_equal_to"): lambda _: expect([1, 1]).all_equal_to(1),
    ("CollectionExpect", "contains"): lambda _: expect([1, 1, 2]).contains(
        1, occurrences=exactly(2)
    ),
    ("CollectionExpect", "contains_all"): lambda _: expect([1, 2]).contains_all(1, 2),
    ("CollectionExpect", "contains_any"): lambda _: expect([1, 2]).contains_any(1, 9),
    ("CollectionExpect", "contains_items_of_type"): lambda _: expect([1, 2]).contains_items_of_type(
        int
    ),
    ("CollectionExpect", "contains_match"): lambda _: expect(["abc"]).contains_match("a*"),
    ("CollectionExpect", "contains_matching"): lambda _: expect([1, 2]).contains_matching(
        lambda item: item == 2
    ),
    ("CollectionExpect", "contains_no_duplicates"): lambda _: expect(
        [1, 2]
    ).contains_no_duplicates(),
    ("CollectionExpect", "contains_none_of"): lambda _: expect([1, 2]).contains_none_of(8, 9),
    ("CollectionExpect", "contains_only"): lambda _: expect([1, 2]).contains_only(1, 2),
    ("CollectionExpect", "contains_single"): lambda _: expect([1]).contains_single(),
    ("CollectionExpect", "contains_single_matching"): lambda _: expect(
        [1, 2]
    ).contains_single_matching(lambda item: item == 2),
    ("CollectionExpect", "does_not_contain"): lambda _: expect({1, 2}).does_not_contain(9),
    ("CollectionExpect", "does_not_contain_all"): lambda _: expect([1, 2]).does_not_contain_all(
        1, 9
    ),
    ("CollectionExpect", "does_not_contain_items_of_type"): lambda _: expect(
        [1, 2]
    ).does_not_contain_items_of_type(str),
    ("CollectionExpect", "does_not_contain_match"): lambda _: expect(
        ["abc"]
    ).does_not_contain_match("z*"),
    ("CollectionExpect", "does_not_contain_matching"): lambda _: expect(
        [1, 2]
    ).does_not_contain_matching(lambda item: item == 9),
    ("CollectionExpect", "does_not_contain_none"): lambda _: expect([1, 2]).does_not_contain_none(),
    ("CollectionExpect", "does_not_have_length"): lambda _: expect([1, 2]).does_not_have_length(9),
    ("CollectionExpect", "does_not_have_same_length_as"): lambda _: expect(
        [1, 2]
    ).does_not_have_same_length_as([1]),
    ("CollectionExpect", "does_not_intersect"): lambda _: expect([1, 2]).does_not_intersect([8, 9]),
    # A `frozenset` rather than a list, and the difference is the entry. A list
    # dispatches to `SequenceExpect`, which overrides `extracting`, so a list here
    # would run that override twice over and leave `CollectionExpect.extracting`
    # uncalled -- a row naming an assertion it does not reach, which both guards
    # then count as covered. `test_every_happy_call_reaches_the_assertion_it_names`
    # is what catches that, and it lives in the allocation guard because that is
    # the guard that has to replace the method in order to measure it: a
    # replacement nobody calls is the signal.
    ("CollectionExpect", "extracting"): lambda _: expect(frozenset({(1, "a")})).extracting(
        lambda row: row[0]
    ),
    ("CollectionExpect", "has_length"): lambda _: expect([1, 2]).has_length(2),
    ("CollectionExpect", "has_length_greater_than"): lambda _: expect(
        [1, 2]
    ).has_length_greater_than(1),
    ("CollectionExpect", "has_length_greater_than_or_equal_to"): lambda _: expect(
        [1, 2]
    ).has_length_greater_than_or_equal_to(2),
    ("CollectionExpect", "has_length_less_than"): lambda _: expect([1, 2]).has_length_less_than(3),
    ("CollectionExpect", "has_length_less_than_or_equal_to"): lambda _: expect(
        [1, 2]
    ).has_length_less_than_or_equal_to(2),
    ("CollectionExpect", "has_length_matching"): lambda _: expect([1, 2]).has_length_matching(
        lambda size: size == 2
    ),
    ("CollectionExpect", "has_same_length_as"): lambda _: expect([1, 2]).has_same_length_as([3, 4]),
    ("CollectionExpect", "has_unique_items"): lambda _: expect([1, 2]).has_unique_items(),
    ("CollectionExpect", "intersects"): lambda _: expect([1, 2]).intersects([2, 9]),
    ("CollectionExpect", "is_disjoint_from"): lambda _: expect([1, 2]).is_disjoint_from([8, 9]),
    ("CollectionExpect", "is_empty"): lambda _: expect(set[int]()).is_empty(),
    ("CollectionExpect", "is_none_or_empty"): lambda _: expect(set[int]()).is_none_or_empty(),
    ("CollectionExpect", "is_not_empty"): lambda _: expect({1}).is_not_empty(),
    ("CollectionExpect", "is_not_none_or_empty"): lambda _: expect({1}).is_not_none_or_empty(),
    ("CollectionExpect", "is_not_subset_of"): lambda _: expect([1, 2]).is_not_subset_of([1]),
    ("CollectionExpect", "is_not_superset_of"): lambda _: expect([1]).is_not_superset_of([1, 2]),
    ("CollectionExpect", "is_proper_subset_of"): lambda _: expect([1]).is_proper_subset_of([1, 2]),
    ("CollectionExpect", "is_proper_superset_of"): lambda _: expect([1, 2]).is_proper_superset_of(
        [1]
    ),
    ("CollectionExpect", "is_subset_of"): lambda _: expect([1]).is_subset_of([1, 2]),
    ("CollectionExpect", "is_superset_of"): lambda _: expect([1, 2]).is_superset_of([1]),
    ("CollectionExpect", "only_contains"): lambda _: expect([2, 4]).only_contains(
        lambda item: item % 2 == 0
    ),
    ("CollectionExpect", "satisfies_in_any_order"): lambda _: expect([1, 2]).satisfies_in_any_order(
        lambda item: item == 2, lambda item: item == 1
    ),
    # -- SequenceExpect ----------------------------------------------------
    ("SequenceExpect", "contains_in_consecutive_order"): lambda _: expect(
        [1, 2, 3]
    ).contains_in_consecutive_order(1, 2),
    ("SequenceExpect", "contains_in_order"): lambda _: expect([1, 2, 3]).contains_in_order(1, 3),
    ("SequenceExpect", "does_not_contain"): lambda _: expect([1, 2]).does_not_contain(9),
    ("SequenceExpect", "does_not_contain_in_consecutive_order"): lambda _: expect(
        [1, 2, 3]
    ).does_not_contain_in_consecutive_order(3, 1),
    ("SequenceExpect", "does_not_contain_in_order"): lambda _: expect(
        [1, 2, 3]
    ).does_not_contain_in_order(3, 1),
    ("SequenceExpect", "does_not_equal_sequence"): lambda _: expect([1, 2]).does_not_equal_sequence(
        [9]
    ),
    ("SequenceExpect", "ends_with_sequence"): lambda _: expect([1, 2]).ends_with_sequence([2]),
    ("SequenceExpect", "equals_approximately"): lambda _: expect([1.0]).equals_approximately(
        [1.01], tol=0.1
    ),
    ("SequenceExpect", "equals_sequence"): lambda _: expect([1, 2]).equals_sequence([1, 2]),
    ("SequenceExpect", "extracting"): lambda _: expect([(1, "a")]).extracting(lambda row: row[0]),
    ("SequenceExpect", "has_element_at"): lambda _: expect([1, 2]).has_element_at(0, 1),
    ("SequenceExpect", "is_not_sorted"): lambda _: expect([2, 1]).is_not_sorted(),
    ("SequenceExpect", "is_not_sorted_descending"): lambda _: expect(
        [1, 2]
    ).is_not_sorted_descending(),
    ("SequenceExpect", "is_sorted"): lambda _: expect([1, 2]).is_sorted(),
    ("SequenceExpect", "is_sorted_descending"): lambda _: expect([2, 1]).is_sorted_descending(),
    ("SequenceExpect", "starts_with_sequence"): lambda _: expect([1, 2]).starts_with_sequence([1]),
    # -- MappingExpect -----------------------------------------------------
    ("MappingExpect", "contains_entries"): lambda _: expect({"a": 1}).contains_entries({"a": 1}),
    ("MappingExpect", "contains_entry"): lambda _: expect({"a": 1}).contains_entry("a", 1),
    ("MappingExpect", "contains_entry_matching"): lambda _: expect(
        {"a": 1}
    ).contains_entry_matching(lambda key, value: key == "a" and value == 1),
    ("MappingExpect", "contains_key"): lambda _: expect({"a": 1}).contains_key("a"),
    ("MappingExpect", "contains_key_matching"): lambda _: expect({"a": 1}).contains_key_matching(
        lambda key: key == "a"
    ),
    ("MappingExpect", "contains_keys"): lambda _: expect({"a": 1, "b": 2}).contains_keys("a", "b"),
    ("MappingExpect", "contains_only_keys"): lambda _: expect({"a": 1}).contains_only_keys("a"),
    ("MappingExpect", "contains_value"): lambda _: expect({"a": 1}).contains_value(1),
    ("MappingExpect", "contains_value_matching"): lambda _: expect(
        {"a": 1}
    ).contains_value_matching(lambda value: value == 1),
    ("MappingExpect", "contains_values"): lambda _: expect({"a": 1}).contains_values(1),
    ("MappingExpect", "does_not_contain_entry"): lambda _: expect({"a": 1}).does_not_contain_entry(
        "a", 9
    ),
    ("MappingExpect", "does_not_contain_key"): lambda _: expect({"a": 1}).does_not_contain_key("z"),
    ("MappingExpect", "does_not_contain_keys"): lambda _: expect({"a": 1}).does_not_contain_keys(
        "y", "z"
    ),
    ("MappingExpect", "does_not_contain_value"): lambda _: expect({"a": 1}).does_not_contain_value(
        9
    ),
    ("MappingExpect", "does_not_contain_values"): lambda _: expect(
        {"a": 1}
    ).does_not_contain_values(8, 9),
    ("MappingExpect", "does_not_have_length"): lambda _: expect({"a": 1}).does_not_have_length(9),
    ("MappingExpect", "does_not_have_same_length_as"): lambda _: expect(
        {"a": 1}
    ).does_not_have_same_length_as([1, 2]),
    ("MappingExpect", "has_length"): lambda _: expect({"a": 1}).has_length(1),
    ("MappingExpect", "has_length_greater_than"): lambda _: expect(
        {"a": 1}
    ).has_length_greater_than(0),
    ("MappingExpect", "has_length_greater_than_or_equal_to"): lambda _: expect(
        {"a": 1}
    ).has_length_greater_than_or_equal_to(1),
    ("MappingExpect", "has_length_less_than"): lambda _: expect({"a": 1}).has_length_less_than(2),
    ("MappingExpect", "has_length_less_than_or_equal_to"): lambda _: expect(
        {"a": 1}
    ).has_length_less_than_or_equal_to(1),
    ("MappingExpect", "has_length_matching"): lambda _: expect({"a": 1}).has_length_matching(
        lambda size: size == 1
    ),
    ("MappingExpect", "has_same_length_as"): lambda _: expect({"a": 1}).has_same_length_as([1]),
    ("MappingExpect", "is_empty"): lambda _: expect(dict[str, int]()).is_empty(),
    ("MappingExpect", "is_none_or_empty"): lambda _: expect(dict[str, int]()).is_none_or_empty(),
    ("MappingExpect", "is_not_empty"): lambda _: expect({"a": 1}).is_not_empty(),
    ("MappingExpect", "is_not_none_or_empty"): lambda _: expect({"a": 1}).is_not_none_or_empty(),
    # -- CallableExpect / RaisedExpect -------------------------------------
    ("CallableExpect", "does_not_raise"): lambda _: expect(lambda: None).does_not_raise(),
    ("CallableExpect", "raises"): lambda _: expect(_raise_plain).raises(ValueError),
    ("CallableExpect", "raises_exactly"): lambda _: expect(_raise_plain).raises_exactly(ValueError),
    # -- warnings ----------------------------------------------------------
    # `warns` and `does_not_warn` capture, so each call needs a warning of its own
    # to find or not find; `_issue_warning` is the smallest callable that issues one.
    ("CallableExpect", "warns"): lambda _: expect(_issue_warning).warns(UserWarning),
    ("CallableExpect", "does_not_warn"): lambda _: expect(lambda: None).does_not_warn(),
    ("WarnedExpect", "with_message"): lambda _: _warned().with_message("deprecated"),
    ("WarnedExpect", "with_message_containing"): lambda _: _warned().with_message_containing(
        "deprecated"
    ),
    ("WarnedExpect", "where"): lambda _: _warned().where(lambda issued: bool(issued.args)),
    ("RaisedExpect", "has_no_notes"): lambda _: (
        expect(_raise_plain).raises(ValueError).has_no_notes()
    ),
    ("RaisedExpect", "where"): lambda _: (
        expect(_raise_plain).raises(ValueError).where(lambda error: str(error) == "boom")
    ),
    ("RaisedExpect", "with_cause"): lambda _: (
        expect(_raise_with_cause).raises(ValueError).with_cause(TypeError)
    ),
    ("RaisedExpect", "with_cause_exactly"): lambda _: (
        expect(_raise_with_cause).raises(ValueError).with_cause_exactly(TypeError)
    ),
    ("RaisedExpect", "with_message"): lambda _: (
        expect(_raise_plain).raises(ValueError).with_message(r"boom")
    ),
    ("RaisedExpect", "with_message_containing"): lambda _: (
        expect(_raise_plain).raises(ValueError).with_message_containing("boo")
    ),
    ("RaisedExpect", "with_note"): lambda _: (
        expect(_raise_with_note).raises(ValueError).with_note("a note")
    ),
    ("RaisedExpect", "with_note_matching"): lambda _: (
        expect(_raise_with_note).raises(ValueError).with_note_matching(r"note")
    ),
    ("_CaughtExpect", "matches"): lambda _: _caught().matches(
        lambda error: error.args == ("boom",)
    ),
    ("_CaughtExpect", "where"): lambda _: _caught().where(lambda error: str(error) == "boom"),
    # -- TypeExpect --------------------------------------------------------
    ("TypeExpect", "does_not_have_attribute"): lambda _: expect(list).does_not_have_attribute(
        "zzz"
    ),
    ("TypeExpect", "does_not_implement"): lambda _: expect(object).does_not_implement(_Countable),
    ("TypeExpect", "has_attribute"): lambda _: expect(list).has_attribute("append"),
    ("TypeExpect", "has_method"): lambda _: expect(list).has_method("append"),
    ("TypeExpect", "implements"): lambda _: expect(list).implements(_Countable),
    ("TypeExpect", "is_abstract"): lambda _: expect(_Abstract).is_abstract(),
    ("TypeExpect", "is_not_abstract"): lambda _: expect(list).is_not_abstract(),
    ("TypeExpect", "is_not_subclass_of"): lambda _: expect(list).is_not_subclass_of(dict),
    ("TypeExpect", "is_subclass_of"): lambda _: expect(bool).is_subclass_of(int),
    # -- EnumExpect --------------------------------------------------------
    ("EnumExpect", "does_not_have_flag"): lambda _: expect(_Access.READ).does_not_have_flag(
        _Access.WRITE
    ),
    ("EnumExpect", "does_not_have_name"): lambda _: expect(_Colour.RED).does_not_have_name("GREEN"),
    ("EnumExpect", "does_not_have_value"): lambda _: expect(_Colour.RED).does_not_have_value(
        "green"
    ),
    ("EnumExpect", "has_flag"): lambda _: expect(_Access.READ | _Access.WRITE).has_flag(
        _Access.READ
    ),
    ("EnumExpect", "has_name"): lambda _: expect(_Colour.RED).has_name("RED"),
    ("EnumExpect", "has_same_name_as"): lambda _: expect(_Colour.RED).has_same_name_as(_Shade.RED),
    ("EnumExpect", "has_same_value_as"): lambda _: expect(_Colour.RED).has_same_value_as(
        _Shade.RED
    ),
    ("EnumExpect", "has_value"): lambda _: expect(_Colour.RED).has_value("red"),
    # -- date and time -----------------------------------------------------
    ("DateExpect", "has_day"): lambda _: expect(date(2020, 1, 2)).has_day(2),
    ("DateExpect", "has_month"): lambda _: expect(date(2020, 1, 2)).has_month(1),
    ("DateExpect", "has_year"): lambda _: expect(date(2020, 1, 2)).has_year(2020),
    ("DateExpect", "is_in_the_future"): lambda _: expect(date(2999, 1, 1)).is_in_the_future(),
    ("DateExpect", "is_in_the_past"): lambda _: expect(date(2000, 1, 1)).is_in_the_past(),
    ("DateExpect", "is_today"): lambda _: expect(date.today()).is_today(),
    ("DateExpect", "is_weekday"): lambda _: expect(date(2020, 1, 2)).is_weekday(),
    ("DateExpect", "is_weekend"): lambda _: expect(date(2020, 1, 4)).is_weekend(),
    ("DateTimeExpect", "has_timezone"): lambda _: expect(
        datetime(2020, 1, 1, tzinfo=UTC)
    ).has_timezone(UTC),
    ("DateTimeExpect", "is_close_to"): lambda _: expect(
        datetime(2020, 1, 1, tzinfo=UTC)
    ).is_close_to(datetime(2020, 1, 1, 0, 0, 30, tzinfo=UTC), within=timedelta(minutes=1)),
    ("DateTimeExpect", "is_not_close_to"): lambda _: expect(
        datetime(2020, 1, 1, tzinfo=UTC)
    ).is_not_close_to(datetime(2020, 1, 2, tzinfo=UTC), within=timedelta(minutes=1)),
    ("DateTimeExpect", "is_same_date_as"): lambda _: expect(
        datetime(2020, 1, 1, 9, tzinfo=UTC)
    ).is_same_date_as(datetime(2020, 1, 1, 18, tzinfo=UTC)),
    ("DateTimeExpect", "is_utc"): lambda _: expect(datetime(2020, 1, 1, tzinfo=UTC)).is_utc(),
    ("DateTimeExpect", "is_within"): lambda _: (
        expect(datetime(2020, 1, 1, tzinfo=UTC))
        .is_within(timedelta(days=1))
        .before(datetime(2020, 1, 1, 12, tzinfo=UTC))
    ),
    ("WithinDelta", "before"): lambda _: (
        expect(datetime(2020, 1, 1, tzinfo=UTC))
        .is_within(timedelta(days=1))
        .before(datetime(2020, 1, 1, 12, tzinfo=UTC))
    ),
    ("WithinDelta", "after"): lambda _: (
        expect(datetime(2020, 1, 1, 12, tzinfo=UTC))
        .is_within(timedelta(days=1))
        .after(datetime(2020, 1, 1, tzinfo=UTC))
    ),
    ("TimeExpect", "is_midnight"): lambda _: expect(time(0, 0)).is_midnight(),
    ("_ClockExpect", "has_hour"): lambda _: expect(time(9, 30, 15, 7)).has_hour(9),
    ("_ClockExpect", "has_microsecond"): lambda _: expect(time(9, 30, 15, 7)).has_microsecond(7),
    ("_ClockExpect", "has_minute"): lambda _: expect(time(9, 30, 15, 7)).has_minute(30),
    ("_ClockExpect", "has_second"): lambda _: expect(time(9, 30, 15, 7)).has_second(15),
    ("_ClockExpect", "is_aware"): lambda _: expect(time(9, 30, tzinfo=UTC)).is_aware(),
    ("_ClockExpect", "is_naive"): lambda _: expect(time(9, 30)).is_naive(),
    ("_TemporalExpect", "is_after"): lambda _: expect(date(2020, 1, 2)).is_after(date(2020, 1, 1)),
    ("_TemporalExpect", "is_before"): lambda _: expect(date(2020, 1, 1)).is_before(
        date(2020, 1, 2)
    ),
    ("_TemporalExpect", "is_between"): lambda _: expect(date(2020, 1, 2)).is_between(
        date(2020, 1, 1), date(2020, 1, 3)
    ),
    ("_TemporalExpect", "is_not_between"): lambda _: expect(date(2020, 6, 1)).is_not_between(
        date(2020, 1, 1), date(2020, 1, 3)
    ),
    ("_TemporalExpect", "is_on_or_after"): lambda _: expect(date(2020, 1, 1)).is_on_or_after(
        date(2020, 1, 1)
    ),
    ("_TemporalExpect", "is_on_or_before"): lambda _: expect(date(2020, 1, 1)).is_on_or_before(
        date(2020, 1, 1)
    ),
    ("_TemporalExpect", "is_strictly_between"): lambda _: expect(
        date(2020, 1, 2)
    ).is_strictly_between(date(2020, 1, 1), date(2020, 1, 3)),
    ("TimeDeltaExpect", "has_total_seconds"): lambda _: expect(
        timedelta(seconds=90)
    ).has_total_seconds(90.0),
    ("TimeDeltaExpect", "is_at_least"): lambda _: expect(timedelta(hours=2)).is_at_least(
        timedelta(hours=1)
    ),
    ("TimeDeltaExpect", "is_at_most"): lambda _: expect(timedelta(hours=1)).is_at_most(
        timedelta(hours=2)
    ),
    ("TimeDeltaExpect", "is_between"): lambda _: expect(timedelta(hours=2)).is_between(
        timedelta(hours=1), timedelta(hours=3)
    ),
    ("TimeDeltaExpect", "is_close_to"): lambda _: expect(timedelta(hours=1)).is_close_to(
        timedelta(hours=1, minutes=1), within=timedelta(minutes=5)
    ),
    ("TimeDeltaExpect", "is_longer_than"): lambda _: expect(timedelta(hours=2)).is_longer_than(
        timedelta(hours=1)
    ),
    ("TimeDeltaExpect", "is_negative"): lambda _: expect(timedelta(hours=-1)).is_negative(),
    ("TimeDeltaExpect", "is_not_between"): lambda _: expect(timedelta(hours=9)).is_not_between(
        timedelta(hours=1), timedelta(hours=3)
    ),
    ("TimeDeltaExpect", "is_not_close_to"): lambda _: expect(timedelta(hours=1)).is_not_close_to(
        timedelta(hours=9), within=timedelta(minutes=5)
    ),
    ("TimeDeltaExpect", "is_not_zero"): lambda _: expect(timedelta(hours=1)).is_not_zero(),
    ("TimeDeltaExpect", "is_positive"): lambda _: expect(timedelta(hours=1)).is_positive(),
    ("TimeDeltaExpect", "is_shorter_than"): lambda _: expect(timedelta(hours=1)).is_shorter_than(
        timedelta(hours=2)
    ),
    ("TimeDeltaExpect", "is_zero"): lambda _: expect(timedelta()).is_zero(),
    # -- paths -------------------------------------------------------------
    ("PurePathExpect", "has_name"): lambda _: expect(PurePosixPath("/a/b.tar.gz")).has_name(
        "b.tar.gz"
    ),
    ("PurePathExpect", "has_no_suffix"): lambda _: expect(PurePosixPath("/a/b")).has_no_suffix(),
    ("PurePathExpect", "has_parent"): lambda _: expect(PurePosixPath("/a/b")).has_parent(
        PurePosixPath("/a")
    ),
    ("PurePathExpect", "has_stem"): lambda _: expect(PurePosixPath("/a/b.tar.gz")).has_stem(
        "b.tar"
    ),
    ("PurePathExpect", "has_suffix"): lambda _: expect(PurePosixPath("/a/b.tar.gz")).has_suffix(
        ".gz"
    ),
    ("PurePathExpect", "has_suffixes"): lambda _: expect(PurePosixPath("/a/b.tar.gz")).has_suffixes(
        [".tar", ".gz"]
    ),
    ("PurePathExpect", "is_absolute"): lambda _: expect(PurePosixPath("/a/b")).is_absolute(),
    ("PurePathExpect", "is_not_relative_to"): lambda _: expect(
        PurePosixPath("/a/b")
    ).is_not_relative_to(PurePosixPath("/z")),
    ("PurePathExpect", "is_relative"): lambda _: expect(PurePosixPath("a/b")).is_relative(),
    ("PurePathExpect", "is_relative_to"): lambda _: expect(PurePosixPath("/a/b")).is_relative_to(
        PurePosixPath("/a")
    ),
    ("PurePathExpect", "matches_pattern"): lambda _: expect(
        PurePosixPath("/a/b.gz")
    ).matches_pattern("*.gz"),
    ("PathExpect", "contains_text"): lambda w: expect(w.file).contains_text("hello"),
    ("PathExpect", "does_not_contain_text"): lambda w: expect(w.file).does_not_contain_text("zzz"),
    ("PathExpect", "does_not_exist"): lambda w: expect(w.missing).does_not_exist(),
    ("PathExpect", "does_not_have_child"): lambda w: expect(w.directory).does_not_have_child("zzz"),
    ("PathExpect", "exists"): lambda w: expect(w.file).exists(),
    ("PathExpect", "has_child"): lambda w: expect(w.directory).has_child("note.txt"),
    ("PathExpect", "has_size"): lambda w: expect(w.file).has_size(12),
    ("PathExpect", "has_size_greater_than"): lambda w: expect(w.file).has_size_greater_than(1),
    ("PathExpect", "has_size_less_than"): lambda w: expect(w.file).has_size_less_than(1000),
    ("PathExpect", "has_text"): lambda w: expect(w.file).has_text("hello world\n"),
    ("PathExpect", "is_directory"): lambda w: expect(w.directory).is_directory(),
    ("PathExpect", "is_empty"): lambda w: expect(w.empty_file).is_empty(),
    ("PathExpect", "is_file"): lambda w: expect(w.file).is_file(),
    ("PathExpect", "is_not_directory"): lambda w: expect(w.file).is_not_directory(),
    ("PathExpect", "is_not_empty"): lambda w: expect(w.file).is_not_empty(),
    ("PathExpect", "is_not_file"): lambda w: expect(w.directory).is_not_file(),
    ("PathExpect", "is_not_symlink"): lambda w: expect(w.file).is_not_symlink(),
    ("PathExpect", "is_same_file_as"): lambda w: expect(w.file).is_same_file_as(w.file),
    ("PathExpect", "is_symlink"): lambda w: expect(_linked(w)).is_symlink(),
    # -- mocks -------------------------------------------------------------
    ("MockExpect", "has_call_count"): lambda w: MockExpect(w.called).has_call_count(1),
    ("MockExpect", "last_call"): lambda w: MockExpect(w.called).last_call(),
    ("MockExpect", "was_called"): lambda w: MockExpect(w.called).was_called(),
    ("MockExpect", "was_called_once"): lambda w: MockExpect(w.called).was_called_once(),
    ("MockExpect", "was_called_once_with"): lambda w: MockExpect(w.called).was_called_once_with(
        1, key="v"
    ),
    ("MockExpect", "was_called_with"): lambda w: MockExpect(w.called).was_called_with(1, key="v"),
    ("MockExpect", "was_ever_called_with"): lambda w: MockExpect(w.called).was_ever_called_with(
        1, key="v"
    ),
    ("MockExpect", "was_never_called_with"): lambda w: MockExpect(w.called).was_never_called_with(
        9
    ),
    ("MockExpect", "was_not_called"): lambda w: MockExpect(w.uncalled).was_not_called(),
}

#: Assertions with no happy-path exercise, each with the reason. **Shrink only**:
#: :func:`test_the_uncovered_list_cannot_grow` fails if anything is added, and
#: :func:`test_the_uncovered_list_has_no_stale_entries` fails if an entry names
#: something that no longer exists. Nothing may be put here to make a red build
#: green.
#: The reason most of them share: they run *nested* assertions and report them
#: together, which means opening a soft-assertion scope whether or not anything
#: fails. Recorded rather than papered over -- whether "a passing assertion reads
#: no ``ContextVar``" was ever meant to reach the aggregating family is the
#: library's call to make, not this table's.
_NESTED: Final = (
    "runs nested assertions through `collect_failures`, which sets the collector "
    "ContextVar whether or not anything fails"
)

NO_HAPPY_PATH: Final[dict[tuple[str, str], str]] = {
    ("Expect", "satisfies_any"): (
        "runs each branch inside a soft-assertion collector, so the collector "
        "ContextVar is on its happy path by construction"
    ),
    ("Expect", "satisfies_none"): (
        "passes only when every branch *fails*, so the failure machinery is what it asserts with"
    ),
    ("Expect", "satisfies"): _NESTED,
    ("_CaughtExpect", "satisfies"): (
        "delegates to `Expect.satisfies` once it has checked that the failure "
        "was not already absorbed, so it inherits that exemption whole"
    ),
    ("CollectionExpect", "all_satisfy"): _NESTED,
    ("SequenceExpect", "satisfies_respectively"): _NESTED,
}


def subject_classes() -> tuple[type, ...]:
    """Every subject class in the package, exported or not, plus ``WithinDelta``.

    Read off the package rather than listed, because a tuple of the exported
    classes leaves out the ones that are public in use and private in name.
    ``_CaughtExpect`` -- the handle ``with expect_raises(...) as caught`` binds,
    which is the primary form of that API -- overrides ``where``, ``matches`` and
    ``satisfies``, and an enumeration derived from ``__all__`` sees none of the
    three: three public assertions with a happy path and no exercise, which is
    exactly the gap the two guards reading this table exist to close.

    So a subject class added tomorrow is walked whether or not it is exported and
    whether or not anyone remembers this file. ``WithinDelta`` is the one thing
    the derivation cannot reach: it is not an :class:`Expect` at all, but
    ``is_within(...).before(...)`` is a public assertion, so it is named.

    A *seam* is left out. Every subject is assembled from one mixin per seam, and
    a mixin is an :class:`Expect` subclass like any other -- but it is never what
    ``expect()`` hands back, so counting it as a subject would report every
    assertion twice and attribute each to a class no reader has heard of. Seams
    are named ``<Something>Assertions``, and
    :func:`test_no_seam_is_ever_handed_back_by_expect` is what holds them to it.
    """
    classes: dict[type, None] = {}
    for module in library_modules():
        for member in vars(module).values():
            if (
                isinstance(member, type)
                and issubclass(member, Expect)
                and member.__module__.startswith("lovely_assertions")
                and not member.__name__.endswith("Assertions")
            ):
                classes[member] = None
    return (*sorted(classes, key=lambda cls: cls.__qualname__), WithinDelta)


SUBJECT_CLASSES: Final = subject_classes()


def declared_by_the_subject(subject_class: type, /) -> dict[str, object]:
    """Everything the subject's own seams declare, and nothing a parent's do.

    A subject is built from one mixin per seam, so ``vars(subject_class)`` holds
    none of its assertions. Its own bases are walked instead, stopping at the
    first one a *different* exported subject also has -- which is where this
    subject stops being the thing under measurement.
    """
    others = [cls for cls in SUBJECT_CLASSES if cls is not subject_class]
    shared = {base for cls in others for base in cls.__mro__ if base not in subject_class.__mro__}
    del shared
    inherited = {base for cls in others if issubclass(subject_class, cls) for base in cls.__mro__}
    declared: dict[str, object] = {}
    for base in reversed(subject_class.__mro__):
        if base in inherited or base is object:
            continue
        declared.update(vars(base))
    return declared


def owning_subject(declared_in: type, /) -> str:
    """The subject a seam belongs to, given the class that declares the method.

    Takes the class object rather than its name. Two packages both name a seam
    ``WildcardAssertions`` -- strings match a pattern and so do collections of
    them -- and resolving by name attributed one package's assertions to the
    other's subject, which is a guard measuring the wrong thing while staying
    green.

    The most basic carrier wins: a seam of ``CollectionExpect`` is reached from
    ``SequenceExpect`` too, and the assertion belongs to the class that declares
    the catalogue rather than to every class that inherits it.
    """
    if declared_in in SUBJECT_CLASSES:
        return declared_in.__name__
    carriers = [cls for cls in SUBJECT_CLASSES if declared_in in cls.__mro__]
    return min(carriers, key=lambda cls: len(cls.__mro__)).__name__


def declaring_class(cls: type, name: str, /) -> type:
    """The class in ``cls``'s MRO that actually declares ``name``."""
    return next(base for base in cls.__mro__ if name in vars(base))


def public_assertions() -> list[tuple[str, str]]:
    """Every public method of every subject class, keyed by where it is defined.

    Introspection rather than a list, for the reason ``test_empty_arguments.py``
    gives: a hand-written list drifts and nothing notices. Keying on the defining
    class rather than on each class that inherits the method keeps one entry per
    implementation instead of one per place it shows up.

    A subject is assembled from one mixin per seam, so the class that *defines*
    an assertion is usually not a subject at all. The owner is resolved back to
    the most basic subject that carries the seam, which is the name a reader
    knows the assertion by and the one they would look for in this table.
    """
    found: dict[tuple[str, str], None] = {}
    for cls in SUBJECT_CLASSES:
        for name, _ in inspect.getmembers(cls, inspect.isfunction):
            if name.startswith("_"):
                continue
            found[(owning_subject(declaring_class(cls, name)), name)] = None
    return sorted(found)


PUBLIC_ASSERTIONS: Final = public_assertions()
