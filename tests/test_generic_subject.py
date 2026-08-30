"""The catalogue every subject inherits: ``Expect[T]``.

Equality, identity, ``None`` and the narrowing pair are covered by
``test_failure_messages.py`` and ``test_narrowing.py``. This file covers the rest:
membership, predicates, exact types, and the ``satisfies`` inspection.
"""

from enum import Enum, StrEnum
from typing import TYPE_CHECKING

import pytest

from lovely_assertions import AssertionFailure, Expect, expect, soft_assertions
from lovely_assertions._core import _inspection

if TYPE_CHECKING:
    from collections.abc import Callable


class Animal:
    __slots__ = ()


class Dog(Animal):
    __slots__ = ()


class Colour(Enum):
    RED = 1


class Flavour(StrEnum):
    """A member that is a ``str`` and an ``Enum`` at once -- the awkward case."""

    SWEET = "sweet"


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------
def test_is_one_of_passes_and_chains() -> None:
    subject = expect(2)
    assert subject.is_one_of(1, 2, 3) is subject


def test_is_one_of_reports_the_options() -> None:
    status = "draft"
    with pytest.raises(AssertionFailure) as caught:
        expect(status).is_one_of("published", "archived")
    assert str(caught.value) == (
        "Expected status to be one of ('published', 'archived'), but was 'draft'."
    )


def test_is_in_and_is_not_in() -> None:
    expect(2).is_in([1, 2, 3])
    expect(9).is_not_in([1, 2, 3])
    with pytest.raises(AssertionFailure, match="to be in"):
        expect(9).is_in([1, 2, 3])
    with pytest.raises(AssertionFailure, match="not to be in"):
        expect(2).is_not_in([1, 2, 3])


def test_is_in_works_with_any_container() -> None:
    expect("ell").is_in("hello")
    expect(2).is_in({1, 2})
    expect("a").is_in({"a": 1})


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------
def test_matches_accepts_a_passing_predicate() -> None:
    expect(4).matches(lambda value: value % 2 == 0)


def test_matches_names_a_named_predicate() -> None:
    # `NumericExpect` is an `Expect[int | float]`, so a predicate handed to it
    # has to accept the union rather than just `int`.
    def is_even(value: int | float) -> bool:
        return value % 2 == 0

    count = 3
    with pytest.raises(AssertionFailure) as caught:
        expect(count).matches(is_even)
    assert str(caught.value) == "Expected count to match is_even, but 3 did not."


def test_matches_falls_back_for_a_lambda() -> None:
    """A lambda has no useful name; do not print ``<lambda>``."""
    count = 3
    with pytest.raises(AssertionFailure) as caught:
        expect(count).matches(lambda value: value > 10)
    assert str(caught.value) == "Expected count to match the predicate, but 3 did not."


# ---------------------------------------------------------------------------
# satisfies
# ---------------------------------------------------------------------------
def test_satisfies_passes_when_the_inspection_holds() -> None:
    subject = expect(4)
    assert subject.satisfies(lambda value: expect(value).is_equal_to(4)) is subject


def test_satisfies_reports_every_nested_failure_at_once() -> None:
    total = 7
    with pytest.raises(AssertionFailure) as caught:
        expect(total).satisfies(lambda value: [expect(value).is_equal_to(1)])
    message = str(caught.value)
    assert "to satisfy the inspection." in message
    assert "  - Expected the value to equal 1, but was 7" in message


def test_satisfies_does_not_double_the_final_period() -> None:
    total = 7
    with pytest.raises(AssertionFailure) as caught:
        expect(total).satisfies(lambda value: [expect(value).is_equal_to(1)])
    assert not str(caught.value).endswith("..")


def test_satisfies_lets_a_real_error_through() -> None:
    """A broken inspector is a bug in the test, not a finding about the subject."""
    with pytest.raises(ZeroDivisionError):
        expect(7).satisfies(lambda value: value / 0)


def test_satisfies_restores_the_previous_routing() -> None:
    """The temporary collector must not leak past the call."""
    with pytest.raises(AssertionFailure):
        expect(7).satisfies(lambda value: [expect(value).is_equal_to(1)])
    with pytest.raises(AssertionFailure):
        expect(7).is_equal_to(8)


# ---------------------------------------------------------------------------
# Exact types
# ---------------------------------------------------------------------------
def test_is_exactly_instance_of_rejects_a_subclass() -> None:
    pet = Dog()
    with pytest.raises(AssertionFailure) as caught:
        expect(pet).is_exactly_instance_of(Animal)
    assert str(caught.value) == "Expected pet to be exactly Animal, but was Dog."


def test_is_instance_of_accepts_a_subclass() -> None:
    """The difference between the two is the whole point of having both."""
    pet = Dog()
    assert expect(pet).is_instance_of(Animal).subject is pet


def test_is_exactly_instance_of_continues_on_the_value() -> None:
    pet = Dog()
    assert expect(pet).is_exactly_instance_of(Dog).subject is pet
    assert expect(pet).is_exactly_instance_of(Dog).and_.is_instance_of(Animal).subject is pet


def test_is_not_instance_of() -> None:
    expect("x").is_not_instance_of(int)
    label = "x"
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_not_instance_of(str)
    assert str(caught.value) == "Expected label not to be an instance of str, but was str."


def test_is_not_exactly_instance_of_allows_a_subclass() -> None:
    pet = Dog()
    expect(pet).is_not_exactly_instance_of(Animal)
    with pytest.raises(AssertionFailure, match="not to be exactly Dog"):
        expect(pet).is_not_exactly_instance_of(Dog)


def test_as_type_narrows_and_continues() -> None:
    payload: object = 42
    assert expect(payload).as_type(int).subject == 42
    assert isinstance(expect(payload).as_type(int), Expect)


def test_as_type_fails_like_is_instance_of() -> None:
    payload: object = "not a number"
    with pytest.raises(AssertionFailure) as caught:
        expect(payload).as_type(int)
    assert str(caught.value) == "Expected payload to be an instance of int, but was str."


# ---------------------------------------------------------------------------
# What the narrowing overloads claim, asserted against what is really built
# ---------------------------------------------------------------------------
# `as_type`, `is_instance_of` and `is_exactly_instance_of` declare the specialised
# subject for `bool`, `str` and an `Enum` class, so that `as_type(str).starts_with(...)`
# is offered rather than refused. A declaration is only worth as much as the object
# behind it, and the object comes from `expect()` -- so these pin the runtime half of
# the same table. If the dispatch ever stops sending a `str` to `StringExpect`, the
# declaration becomes a lie and these fail first; the static half is held by
# `typing_tests/positive/continuations.py`. One table seen twice.
@pytest.mark.parametrize(
    ("value", "narrowed_to", "subject_name"),
    [
        pytest.param("hello", str, "StringExpect", id="str"),
        pytest.param(True, bool, "BoolExpect", id="bool"),
        pytest.param(Colour.RED, Colour, "EnumExpect", id="enum"),
    ],
)
def test_the_declared_subject_is_the_one_expect_builds(
    value: object, narrowed_to: type[object], subject_name: str
) -> None:
    assert type(expect(value).as_type(narrowed_to)).__name__ == subject_name
    assert type(expect(value).is_instance_of(narrowed_to).which).__name__ == subject_name
    assert type(expect(value).is_exactly_instance_of(narrowed_to).which).__name__ == subject_name


def test_the_narrowed_string_subject_really_carries_the_string_catalogue() -> None:
    """The whole point of the declaration: the method is offered *and* it works."""
    raw: object = "hello"
    assert expect(raw).as_type(str).starts_with("he").subject == "hello"


def test_is_instance_of_int_gives_the_catalogue_of_the_type_that_was_named() -> None:
    """The named type decides, not the value -- which is what the overloads say.

    ``isinstance(True, int)`` holds, and ``expect(True)`` on its own builds a
    ``BoolExpect``. Asked ``is_instance_of(int)``, the caller has said which type
    they mean, so ``.which`` is the ``int`` catalogue and ``is_positive()`` works
    on it.

    The declaration stays ``Expect[int]`` rather than ``NumericExpect``: it
    under-promises rather than lying, and widening it is a separate decision from
    making the runtime honest.
    """
    flag: object = True
    narrowed = expect(flag).is_instance_of(int).which
    assert type(narrowed).__name__ == "NumericExpect"
    # Through the runtime, because the *declaration* is `Expect[int]` and both
    # checkers are right to refuse `is_positive` on it. That is the shape of the
    # under-promise: the object has more than the declaration admits, which is
    # the safe direction.
    assert hasattr(narrowed, "is_positive")


def test_a_str_enum_member_reaches_the_catalogue_the_caller_asked_for() -> None:
    """Where the caller names a type, that type decides which catalogue arrives.

    ``as_type(str)`` is declared ``StringExpect`` because the type *argument* is
    ``str``. A ``StrEnum`` member is an enum before it is a string, so dispatching
    on the value instead would declare one thing and build another:
    ``.starts_with(...)`` type-checks under both checkers and raises
    ``AttributeError``. The one thing this library exists to prevent.

    No *overload* can close that gap, because both answers are correct about the
    value. Only the runtime can, by honouring the type the caller named.

    ``expect(member)`` on its own is unaffected and still an ``EnumExpect``. That
    is the documented rule -- an enum member is an enum before it is anything
    else -- and it is about a value nobody annotated. This is about a type
    somebody wrote down.
    """
    member: object = Flavour.SWEET
    assert type(expect(member)).__name__ == "EnumExpect"
    assert type(expect(member).as_type(str)).__name__ == "StringExpect"
    expect(member).as_type(str).starts_with("sw")
    assert type(expect(member).as_type(Flavour)).__name__ == "EnumExpect"


# ---------------------------------------------------------------------------
# because reaches all of them
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: expect(9).is_one_of(1, because="R"), id="is_one_of"),
        pytest.param(lambda: expect(9).is_in([1], because="R"), id="is_in"),
        pytest.param(lambda: expect(1).is_not_in([1], because="R"), id="is_not_in"),
        pytest.param(lambda: expect(9).matches(lambda _: False, because="R"), id="matches"),
        pytest.param(lambda: expect(9).is_instance_of(str, because="R"), id="is_instance_of"),
        pytest.param(lambda: expect(9).is_not_instance_of(int, because="R"), id="is_not_instance"),
        pytest.param(lambda: expect(9).is_exactly_instance_of(str, because="R"), id="is_exactly"),
        pytest.param(
            lambda: expect(9).is_not_exactly_instance_of(int, because="R"), id="is_not_exactly"
        ),
        pytest.param(lambda: expect(9).as_type(str, because="R"), id="as_type"),
    ],
)
def test_because_reaches_every_assertion(call: object) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]


# ---------------------------------------------------------------------------
# The inspector guard: a callback that returns a verdict has asserted nothing
#
# Every inspector-taking method routes through `_core.collect_failures`, and the
# guard lives there rather than at each call site, where the next one added could
# forget it. `Expect.satisfies_any` and `Expect.satisfies_none` are covered from
# `tests/test_core_additions.py`, where they live; the other three are here,
# because what is under test is the one primitive they share.
# ---------------------------------------------------------------------------
_INSPECTOR_TAKING = [
    pytest.param(
        lambda: expect(5).satisfies(lambda value: value > 100),
        "matches",
        id="Expect.satisfies",
    ),
    pytest.param(
        lambda: expect([1, 2]).all_satisfy(lambda item: item > 100),
        "only_contains",
        id="CollectionExpect.all_satisfy",
    ),
    pytest.param(
        lambda: expect([1, 2]).satisfies_respectively(
            lambda item: item > 0,
            lambda item: item > 0,
        ),
        "satisfies_in_any_order",
        id="SequenceExpect.satisfies_respectively",
    ),
]


@pytest.mark.parametrize(("call", "sibling"), _INSPECTOR_TAKING)
def test_a_callback_that_returns_a_verdict_is_refused(
    call: "Callable[[], object]", sibling: str
) -> None:
    """An inspector that returns a verdict has asserted nothing, so it is refused.

    Nothing else catches ``expect(5).satisfies(lambda v: v > 100)``: both checkers
    are happy with it, because the parameter is ``Callable[[T], object]``, which
    accepts ``bool`` without a murmur, and the call then passes whatever the
    subject is -- the worst thing an assertion can be. The refusal names the
    sibling that takes a predicate, because writing one here is a short step from
    the neighbouring methods that teach exactly that lambda shape.
    """
    with pytest.raises(TypeError) as caught:
        call()
    message = str(caught.value)
    assert "instead of asserting anything" in message
    assert "use `" + sibling + "` to pass a predicate" in message


def test_the_refusal_shows_the_verdict_and_the_way_out() -> None:
    count = 5
    with pytest.raises(TypeError) as caught:
        expect(count).satisfies(lambda value: value > 100)
    assert str(caught.value) == (
        "the callback returned False instead of asserting anything, so this would have"
        " passed whatever the subject was. An inspector asserts; a predicate returns a"
        " verdict. use `matches` to pass a predicate, or assert instead:"
        " `lambda it: expect(it).is_positive()`"
    )


def test_the_refusal_is_a_caller_bug_and_not_an_assertion_failure() -> None:
    """An assertion failure is a statement about the value under test.

    "You handed me the wrong kind of callback" is not one, so it is raised rather
    than reported -- including inside a soft scope, which collects findings about
    values and must not collect this.
    """
    with pytest.raises(TypeError), soft_assertions() as scope:
        expect(5).satisfies(lambda value: value > 100)
    assert scope.discard() == []


def test_a_real_inspector_still_inspects() -> None:
    """The guard must not cost the inspector-taking methods the thing they are for."""
    subject = expect(5)
    assert subject.satisfies(lambda value: expect(value).is_positive()) is subject
    items = expect([1, 2])
    assert items.all_satisfy(lambda item: expect(item).is_positive()) is items
    assert (
        items.satisfies_respectively(
            lambda item: expect(item).is_equal_to(1),
            lambda item: expect(item).is_equal_to(2),
        )
        is items
    )
    total = 7
    with pytest.raises(AssertionFailure, match="to satisfy the inspection"):
        expect(total).satisfies(lambda value: expect(value).is_equal_to(1))


#: Everything a legitimate inspector hands back, which is to say: anything at
#: all. The value is ignored by design.
_NOT_A_VERDICT: list[object] = [None, 0, 1, "", "yes", [], object()]


@pytest.mark.parametrize(
    "returned",
    _NOT_A_VERDICT,
    ids=["none", "zero", "one", "empty-str", "str", "empty-list", "object"],
)
def test_only_the_two_bool_singletons_are_refused(returned: object) -> None:
    """``is True`` / ``is False``, never truthiness.

    An inspector's return value is ignored, so it may be anything, and the
    ordinary ones cover both halves of truthiness already: an assertion chain
    hands back a truthy wrapper, a statement lambda hands back ``None``, a
    comprehension hands back a list that is empty exactly when nothing was
    inspected. Refusing on truthiness would refuse all three. Only ``True`` and
    ``False`` are evidence that the callback computed a verdict instead of
    asserting -- and ``1`` is not ``True``, which is why the test says so.
    """
    subject = expect(5)
    assert subject.satisfies(lambda _value: returned) is subject


def test_the_predicate_taking_siblings_are_untouched() -> None:
    """A whole family of methods takes a predicate *by design*; the guard spares them.

    Their whole contract is the verdict, and a failing one is an assertion
    failure about the subject -- not a ``TypeError`` about the callback.
    """
    expect(5).matches(lambda value: value > 1)
    expect([1, 2]).only_contains(lambda item: item > 0)
    expect([1, 2]).satisfies_in_any_order(lambda item: item == 2, lambda item: item == 1)
    assert expect([1, 2]).contains_matching(lambda item: item > 1).subject == 2
    with pytest.raises(AssertionFailure, match="to match the predicate"):
        expect(5).matches(lambda value: value > 100)
    with pytest.raises(AssertionFailure):
        expect([1, 2]).only_contains(lambda item: item > 1)
    with pytest.raises(AssertionFailure):
        expect([1, 2]).satisfies_in_any_order(lambda item: item == 1, lambda item: item == 1)
    with pytest.raises(AssertionFailure):
        expect([1, 2]).contains_matching(lambda item: item > 9)


def test_the_guard_costs_nothing_on_the_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two identity comparisons, and nothing built unless one of them fires.

    Booby-trapped the way ``tests/test_happy_path.py`` traps the failure path: the
    message builder is replaced with something that detonates if it is so much as
    reached, so a guard that formatted first and decided afterwards would be
    caught here rather than in a benchmark.
    """

    def detonate(_outcome: bool, _predicate_form: str, /) -> str:
        message = "the guard built its message for a callback that asserted properly"
        raise AssertionError(message)

    monkeypatch.setattr(_inspection, "_predicate_not_inspector", detonate)
    expect(5).satisfies(lambda value: expect(value).is_positive())
    expect([1, 2]).all_satisfy(lambda item: expect(item).is_positive())
    expect([1]).satisfies_respectively(lambda item: expect(item).is_positive())
    expect(5).satisfies_any(lambda it: it.is_positive())
    expect(5).satisfies_none(lambda it: it.is_negative())
