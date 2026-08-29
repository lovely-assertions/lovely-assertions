"""Occurrence constraints -- ``_occurrence.py``.

The truth table is the specification. Every shipped factory is enumerated across
counts 0, 1, 2 and 3 in :data:`_TRUTH_TABLE`, and every one of its rows is a
claim about what the constraint *means* rather than about how it is implemented.
Three things hang off it:

*The boundaries.* ``at_most(0)``, ``exactly(0)`` and ``less_than(1)`` are three
spellings of "it never appears" and all three are kept; ``at_least(0)`` and
``less_than(0)`` are refused, one for holding always and the other for holding
never. Both refusals are ``ValueError`` -- a bug in the test, not a finding about
a subject, exactly as ``tests/test_empty_arguments.py`` argues for the variadic
assertions.

*The singular.* ``describe()`` lands in the middle of a sentence a human reads,
so it has to say "once" where the phrase takes it and "1 time" where it does
not -- never "1 times". That is the case every library ships broken, so it is
checked at the boundary *and* swept generically across every factory, in case a
sixth one arrives without one.

*The value semantics.* A user builds ``exactly(3)`` at module scope and reuses
it. That only works if it is immutable, hashable and equal to its twin -- and if
nothing quietly rewrites the phrase the caller chose, which is why
``at_least(3) != more_than(2)`` despite the two accepting identical counts.
"""

from typing import TYPE_CHECKING, Final

import pytest
from benchmarks import blocks_allocated

from lovely_assertions import _occurrence
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._occurrence import (
    Occurrence,
    at_least,
    at_most,
    exactly,
    less_than,
    more_than,
    once,
    twice,
)

if TYPE_CHECKING:
    from collections.abc import Callable

#: Every factory, for the sweeps that must not miss one. Keyed by name because a
#: ``Callable`` has no ``__name__`` as far as a type checker is concerned, and a
#: sweep that cannot say *which* factory failed is half a test.
_FACTORIES: Final[dict[str, "Callable[[int], Occurrence]"]] = {
    "at_least": at_least,
    "at_most": at_most,
    "exactly": exactly,
    "less_than": less_than,
    "more_than": more_than,
}


# ---------------------------------------------------------------------------
# The truth table. This is the specification.
# ---------------------------------------------------------------------------
#: ``(spelling, constraint, accepted at counts 0, 1, 2, 3)``.
_TRUTH_TABLE: Final[tuple[tuple[str, Occurrence, tuple[bool, bool, bool, bool]], ...]] = (
    ("exactly(0)", exactly(0), (True, False, False, False)),
    ("exactly(1)", exactly(1), (False, True, False, False)),
    ("exactly(2)", exactly(2), (False, False, True, False)),
    ("exactly(3)", exactly(3), (False, False, False, True)),
    ("exactly(4)", exactly(4), (False, False, False, False)),
    ("at_least(1)", at_least(1), (False, True, True, True)),
    ("at_least(2)", at_least(2), (False, False, True, True)),
    ("at_least(3)", at_least(3), (False, False, False, True)),
    ("at_least(4)", at_least(4), (False, False, False, False)),
    ("at_most(0)", at_most(0), (True, False, False, False)),
    ("at_most(1)", at_most(1), (True, True, False, False)),
    ("at_most(2)", at_most(2), (True, True, True, False)),
    ("at_most(3)", at_most(3), (True, True, True, True)),
    ("more_than(0)", more_than(0), (False, True, True, True)),
    ("more_than(1)", more_than(1), (False, False, True, True)),
    ("more_than(2)", more_than(2), (False, False, False, True)),
    ("more_than(3)", more_than(3), (False, False, False, False)),
    ("less_than(1)", less_than(1), (True, False, False, False)),
    ("less_than(2)", less_than(2), (True, True, False, False)),
    ("less_than(3)", less_than(3), (True, True, True, False)),
    ("less_than(4)", less_than(4), (True, True, True, True)),
    ("once", once, (False, True, False, False)),
    ("twice", twice, (False, False, True, False)),
)


@pytest.mark.parametrize(
    ("spelling", "constraint", "accepted"),
    _TRUTH_TABLE,
    ids=[row[0] for row in _TRUTH_TABLE],
)
def test_the_truth_table(
    spelling: str, constraint: Occurrence, accepted: tuple[bool, bool, bool, bool]
) -> None:
    """What each constraint accepts, count by count."""
    actual = tuple(constraint.allows(count) for count in (0, 1, 2, 3))
    assert actual == accepted, f"{spelling}.allows over counts 0..3 gave {actual}, not {accepted}"


def test_the_truth_table_covers_every_factory() -> None:
    """A table that quietly stopped enumerating a factory would still pass."""
    covered = {spelling.partition("(")[0] for spelling, _, _ in _TRUTH_TABLE}
    assert set(_FACTORIES) <= covered


def test_allows_answers_with_a_real_bool() -> None:
    """A calling assertion branches on this; a truthy stand-in would be a trap."""
    assert exactly(3).allows(3) is True
    assert exactly(3).allows(2) is False


# ---------------------------------------------------------------------------
# describe(): the fragment that lands in a failure message
# ---------------------------------------------------------------------------
_DESCRIPTIONS: Final[tuple[tuple[Occurrence, str], ...]] = (
    (exactly(0), "exactly 0 times"),
    (exactly(1), "exactly once"),
    (exactly(2), "exactly twice"),
    (exactly(3), "exactly 3 times"),
    (at_least(1), "at least once"),
    (at_least(2), "at least twice"),
    (at_most(0), "at most 0 times"),
    (at_most(1), "at most once"),
    (at_most(2), "at most twice"),
    (more_than(0), "more than 0 times"),
    (more_than(1), "more than once"),
    (more_than(2), "more than twice"),
    (less_than(1), "less than 1 time"),
    (less_than(2), "less than 2 times"),
    (less_than(3), "less than 3 times"),
    (once, "exactly once"),
    (twice, "exactly twice"),
)


@pytest.mark.parametrize(
    ("constraint", "expected"), _DESCRIPTIONS, ids=[text for _, text in _DESCRIPTIONS]
)
def test_describe_counts_in_english(constraint: Occurrence, expected: str) -> None:
    """Singular at one, plural everywhere else -- including at zero."""
    assert constraint.describe() == expected


def test_no_constraint_anywhere_says_one_times() -> None:
    """The bug this file exists to prevent, swept rather than spot-checked.

    The parametrised table above pins the boundary for the factories that ship
    today. This one would still catch a sixth factory that arrived with its own
    pluralisation, which is the way the mistake actually gets back in.
    """
    offenders = [
        constraint.describe()
        for name in _FACTORIES
        for count in range(6)
        for constraint in [_build(name, count)]
        if constraint is not None and " 1 times" in constraint.describe()
    ]
    assert not offenders, f"a description used a plural for a count of one: {offenders}"


def test_describe_reads_inside_the_sentence_it_was_written_for() -> None:
    """The whole point of the module, spelled out once.

    ``describe()`` is not a label; it is the middle of a sentence somebody reads
    at 2am. If this assertion ever needs rewording, the wording is wrong.
    """
    message = "Expected log to contain 'retrying' " + exactly(3).describe() + ", but found 2."
    assert message == "Expected log to contain 'retrying' exactly 3 times, but found 2."

    singular = "Expected log to contain 'retrying' " + at_most(1).describe() + ", but found 4."
    assert singular == "Expected log to contain 'retrying' at most once, but found 4."


# ---------------------------------------------------------------------------
# The boundary cases: which zero-ish constraints mean something
# ---------------------------------------------------------------------------
_NEVER_APPEARS: Final[tuple[tuple[str, Occurrence], ...]] = (
    ("exactly(0)", exactly(0)),
    ("at_most(0)", at_most(0)),
    ("less_than(1)", less_than(1)),
)


@pytest.mark.parametrize(
    ("spelling", "constraint"), _NEVER_APPEARS, ids=[name for name, _ in _NEVER_APPEARS]
)
def test_three_spellings_of_never_appears_are_all_kept(
    spelling: str, constraint: Occurrence
) -> None:
    """Zero is a real number of occurrences, so a constraint naming it is real."""
    assert constraint.allows(0) is True, spelling
    assert not any(constraint.allows(count) for count in (1, 2, 3)), spelling


def test_the_three_spellings_describe_themselves_differently() -> None:
    """Which is exactly why all three are kept rather than normalised to one."""
    assert {constraint.describe() for _, constraint in _NEVER_APPEARS} == {
        "exactly 0 times",
        "at most 0 times",
        "less than 1 time",
    }


def test_two_spellings_of_it_appears_are_both_kept() -> None:
    """``more_than(0)`` and ``at_least(1)`` accept the same counts, and read apart."""
    assert [more_than(0).allows(count) for count in (0, 1, 2, 3)] == [False, True, True, True]
    assert [at_least(1).allows(count) for count in (0, 1, 2, 3)] == [False, True, True, True]
    assert more_than(0).describe() == "more than 0 times"
    assert at_least(1).describe() == "at least once"


# ---------------------------------------------------------------------------
# The refusals: a caller bug is raised, never reported
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(_FACTORIES))
@pytest.mark.parametrize("count", [-1, -2, -100])
def test_a_negative_count_is_a_caller_bug(name: str, count: int) -> None:
    """Nothing counts to -1, so a constraint written against it is a typo.

    Every factory refuses, not just the two with a further rule of their own:
    a negative count is wrong before the relation is even considered.
    """
    with pytest.raises(ValueError, match="cannot be negative") as caught:
        _FACTORIES[name](count)
    assert str(count) in str(caught.value), "the refusal must name the offending count"


def test_at_least_zero_asserts_nothing_and_is_refused() -> None:
    """Every count is zero or more, so the assertion carrying it could never fail.

    Same reasoning as ``_core._NEEDS_VALUES``: a test that cannot fail is a bug
    in the test, so it is raised where it is written.
    """
    with pytest.raises(ValueError, match="asserts nothing") as caught:
        at_least(0)
    assert "more_than(0)" in str(caught.value), "a refusal should name the thing that was meant"


def test_less_than_zero_can_never_pass_and_is_refused() -> None:
    """The mirror image: no count is below zero, so no subject could satisfy it."""
    with pytest.raises(ValueError, match="never pass") as caught:
        less_than(0)
    assert "at_most(0)" in str(caught.value)


#: ``(spelling, the call, the words its refusal must contain)``.
_REFUSALS: Final[tuple[tuple[str, "Callable[[], Occurrence]", str], ...]] = (
    ("at_least(0)", lambda: at_least(0), "asserts nothing"),
    ("less_than(0)", lambda: less_than(0), "never pass"),
    ("exactly(-1)", lambda: exactly(-1), "cannot be negative"),
)


@pytest.mark.parametrize(
    ("spelling", "call", "expected"), _REFUSALS, ids=[row[0] for row in _REFUSALS]
)
def test_a_refusal_is_never_an_assertion_failure(
    spelling: str, call: "Callable[[], Occurrence]", expected: str
) -> None:
    """A runner must not present a broken test as a finding about the subject."""
    from lovely_assertions import AssertionFailure

    with pytest.raises(ValueError, match=expected) as caught:
        call()
    assert not isinstance(caught.value, AssertionFailure), (
        f"{spelling} reported a caller bug as an assertion failure"
    )


def test_zero_is_accepted_where_it_means_something() -> None:
    """The refusals must not have taken the meaningful boundary cases with them."""
    assert exactly(0).describe() == "exactly 0 times"
    assert at_most(0).describe() == "at most 0 times"
    assert more_than(0).describe() == "more than 0 times"
    assert less_than(1).describe() == "less than 1 time"


# ---------------------------------------------------------------------------
# Value semantics
# ---------------------------------------------------------------------------
def test_two_constraints_built_the_same_way_are_equal() -> None:
    """The point of the exercise: a user reuses one, or rebuilds it, indifferently."""
    assert exactly(3) == exactly(3)
    assert at_least(2) == at_least(2)
    assert less_than(5) == less_than(5)


def test_a_different_count_is_a_different_value() -> None:
    assert exactly(3) != exactly(4)
    assert at_most(1) != at_most(2)


def test_constraints_that_accept_the_same_counts_are_still_not_equal() -> None:
    """A deliberate judgement, and the one most worth arguing with.

    ``at_least(3)`` and ``more_than(2)`` are extensionally identical: no count
    tells them apart. They are unequal anyway, because ``describe()`` tells them
    apart, and normalising the pair would print a phrase the caller did not
    write. The message is the product.
    """
    assert at_least(3).describe() != more_than(2).describe()
    assert at_least(3) != more_than(2)
    assert at_most(0) != exactly(0)
    assert less_than(1) != at_most(0)


def test_equality_declines_a_foreign_object_rather_than_exploding() -> None:
    """``NotImplemented``, so Python falls back rather than raising."""
    constraint = exactly(3)
    for foreign in ("exactly(3)", 3, None, object(), _Between(3, 3)):
        assert constraint != foreign, foreign
    assert hash(constraint) == hash(exactly(3))


def test_constraints_are_hashable_and_deduplicate() -> None:
    """A user putting them in a set or a dict key must get value semantics."""
    assert hash(exactly(3)) == hash(exactly(3))
    assert len({exactly(1), exactly(1), once}) == 1
    assert len({exactly(1), exactly(2), at_least(1)}) == 3


def test_repr_is_the_call_that_built_it() -> None:
    """What a debugger and a pytest parametrisation id both want to show."""
    assert repr(exactly(3)) == "exactly(3)"
    assert repr(at_least(2)) == "at_least(2)"
    assert repr(at_most(0)) == "at_most(0)"
    assert repr(more_than(1)) == "more_than(1)"
    assert repr(less_than(4)) == "less_than(4)"
    assert repr(once) == "exactly(1)"


def test_a_constraint_carries_no_instance_dictionary() -> None:
    """Every factory returns a value with ``__slots__`` and nothing else on it.

    These are built once and shared across a whole suite, so an instance
    dictionary would be both an allocation per constraint and somewhere for one
    test to leave state behind for the next.
    """
    for name in _FACTORIES:
        constraint = _build(name, 2)
        assert constraint is not None, name
        assert not hasattr(constraint, "__dict__"), name


@pytest.mark.parametrize("attribute", ["_count", "_phrase", "brand_new"])
def test_a_constraint_refuses_to_be_mutated(attribute: str) -> None:
    """``once`` is shared by a whole suite; one test must not be able to move it.

    ``__slots__`` alone would only stop ``brand_new`` -- the existing attribute
    would still be writable, and rewriting ``once`` would corrupt every test that
    runs after the one that did it.
    """
    constraint = exactly(3)
    with pytest.raises(AttributeError, match="immutable"):
        setattr(constraint, attribute, 99)
    assert constraint.describe() == "exactly 3 times"


def test_a_constraint_refuses_to_have_an_attribute_deleted() -> None:
    constraint = exactly(3)
    with pytest.raises(AttributeError, match="immutable"):
        delattr(constraint, "_count")
    assert constraint.allows(3)


# ---------------------------------------------------------------------------
# once / twice
# ---------------------------------------------------------------------------
def test_once_and_twice_are_exactly_one_and_exactly_two() -> None:
    """Sugar, not a separate concept -- so they compare equal to what they are."""
    assert once == exactly(1)
    assert twice == exactly(2)
    assert once != twice


def test_once_and_twice_describe_as_what_they_are() -> None:
    """No second phrasing for the same value: ``once`` *is* ``exactly(1)``."""
    assert once.describe() == exactly(1).describe()
    assert twice.describe() == exactly(2).describe()


def test_once_and_twice_are_shared_objects() -> None:
    """Built at import, so reusing them across a suite costs nothing."""
    assert _occurrence.once is once
    assert _occurrence.twice is twice


# ---------------------------------------------------------------------------
# The protocol: a user can write their own
# ---------------------------------------------------------------------------
class _Between:
    """A user's own constraint, written against the protocol and nothing else."""

    __slots__ = ("_high", "_low")

    def __init__(self, low: int, high: int) -> None:
        self._low = low
        self._high = high

    def allows(self, count: int, /) -> bool:
        return self._low <= count <= self._high

    def describe(self) -> str:
        return "between " + str(self._low) + " and " + str(self._high) + " times"


def _consume(constraint: Occurrence, count: int) -> str:
    """Everything an assertion will ever do with one of these.

    Annotated ``Occurrence``, so pyright and mypy check the structural match at
    every call site below -- the runtime assertions alone would not.
    """
    if constraint.allows(count):
        return "ok"
    return constraint.describe()


def test_a_user_defined_constraint_satisfies_the_protocol() -> None:
    """Structural: nothing has to subclass anything."""
    assert _consume(_Between(2, 4), 3) == "ok"
    assert _consume(_Between(2, 4), 5) == "between 2 and 4 times"


def test_the_shipped_constraints_satisfy_it_too() -> None:
    assert _consume(exactly(3), 3) == "ok"
    assert _consume(exactly(3), 2) == "exactly 3 times"


def test_the_protocol_is_not_runtime_checkable_on_purpose() -> None:
    """A deliberate omission, pinned so it is not "fixed" by accident.

    ``isinstance`` against a protocol only asks whether the two *names* exist, so
    it would accept an object whose ``allows`` is a ``bool`` and hand back a
    guarantee it cannot keep. A constraint is used the instant it is passed, so a
    wrong object raises ``TypeError`` at the call site instead, which says more.
    ``ValueFormatter`` is checked at runtime because registration and use are far
    apart there; here they are the same moment.
    """
    # Routed through an `object`-typed name because both checkers reject the
    # call outright -- which is the static half of the same finding.
    check: object = isinstance
    assert callable(check)
    with pytest.raises(TypeError, match="runtime_checkable"):
        check(exactly(3), Occurrence)


# ---------------------------------------------------------------------------
# Module hygiene
# ---------------------------------------------------------------------------
def test_the_public_surface_is_exported_and_sorted() -> None:
    """``__all__`` is what the package root re-exports, so every name in it must exist.

    Kept sorted: the list is read by hand far more often than it is edited, and
    a fixed order keeps two additions from landing on the same line.
    """
    assert _occurrence.__all__ == [
        "Occurrence",
        "at_least",
        "at_most",
        "exactly",
        "less_than",
        "more_than",
        "once",
        "twice",
    ]
    assert list(_occurrence.__all__) == sorted(_occurrence.__all__)
    for name in _occurrence.__all__:
        assert hasattr(_occurrence, name), f"__all__ advertises missing name {name!r}"


def test_this_modules_frames_fold_out_of_an_assertion_traceback() -> None:
    """This module's frames fold out of an assertion traceback, and stay in any other.

    Nothing in this module raises ``AssertionFailure``; it raises ``ValueError``
    for a caller bug. ``hide_internal_frames`` is a callable precisely so those
    two get opposite answers -- the frames stay for the ``ValueError``, which is
    the case a reader needs to see.
    """
    assert _occurrence.__tracebackhide__ is hide_internal_frames
    assert hide_internal_frames(_Excinfo(ValueError("x"))) is False


class _Excinfo:
    """The shape pytest hands ``__tracebackhide__``: something with ``.value``."""

    __slots__ = ("value",)

    def __init__(self, value: BaseException) -> None:
        self.value = value


# ---------------------------------------------------------------------------
# Cost: the hot path
# ---------------------------------------------------------------------------
def test_checking_a_count_allocates_nothing() -> None:
    """``allows`` sits on the hot path of every assertion that takes one.

    A passing ``expect(log).contains("x", occurrences=exactly(3))`` must cost the
    count plus a comparison. ``describe`` is the failure path and is free to
    allocate; this is the other half.
    """
    baseline = blocks_allocated(lambda: None)
    for name in _FACTORIES:
        constraint = _build(name, 2)
        assert constraint is not None, name
        for count in (1, 2, 3):
            allocated = _blocks_for(constraint, count)
            assert allocated <= baseline, (
                f"{name}(2).allows({count}) allocated {allocated - baseline} blocks; "
                f"a passing assertion is a comparison and a `return self`."
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build(name: str, count: int) -> Occurrence | None:
    """Build by factory name, or ``None`` where that factory refuses that count."""
    try:
        return _FACTORIES[name](count)
    except ValueError:
        return None


def _blocks_for(constraint: Occurrence, count: int) -> int:
    """Blocks the interpreter keeps after many ``allows`` calls.

    A function rather than an inline lambda with default arguments: the
    defaults are what it takes to close over a loop variable safely, and they
    are also what stops mypy inferring the lambda at all.
    """
    return blocks_allocated(lambda: constraint.allows(count))
