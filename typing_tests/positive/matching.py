"""Typed asymmetric matchers: the half a runtime suite cannot see.

A matcher's entire reason to exist is static. At runtime it is an object with a
loose ``__eq__``, which ``dirty-equals`` has had for years; what is new is that
the *slot it goes into stays checked*. ``any_instance_of(int)`` is declared to
return ``int``, so it drops into a ``dict[str, int]`` -- an invariant container,
where no honestly-typed placeholder could ever go -- and a checker that has been
told the value is an ``int`` goes on refusing everything that is not one.

That claim is only worth something if both halves are pinned. This file proves a
matcher is **accepted** wherever the type it stands in for is accepted;
``typing_tests/negative/matching_negative.py`` proves the wrong matcher is
**rejected** in the same places. Either half alone is worthless: a matcher typed
``Any`` would pass everything here and nothing there.
"""

from typing import Any, assert_type
from unittest.mock import Mock

from lovely_assertions import MockExpect, expect
from lovely_assertions._matching import (
    any_instance_of,
    anything,
    close_to,
    containing,
    is_matcher,
    matching,
    one_of,
    string_containing,
    string_matching,
)


def a_matcher_is_the_type_it_stands_in_for() -> None:
    """The lie, stated as the checkers see it."""
    assert_type(any_instance_of(int), int)
    assert_type(any_instance_of(str), str)
    assert_type(any_instance_of(Mock), Mock)
    assert_type(anything(), Any)
    assert_type(string_matching("^a"), str)
    assert_type(string_containing("a"), str)
    assert_type(close_to(1.0), float)
    assert_type(one_of(1, 2), int)
    assert_type(containing({"a": 1}), dict[str, int])
    assert_type(containing([1, 2]), list[int])


def a_matcher_of_several_types_is_their_union() -> None:
    """With one documented exception, which lives in the negative corpus.

    ``one_of(1, None)`` is ``int | None`` to both checkers. ``one_of(1, "a")`` is
    ``int | str`` to pyright and **object** to mypy, which solves a variadic
    ``T`` by joining rather than by unioning -- so the value no longer fits an
    ``int | str`` slot there. It is pinned as a per-checker expectation in
    ``typing_tests/negative/matching_negative.py`` rather than papered over.
    Given operands that already carry the union, both agree.
    """
    assert_type(one_of(1, None), int | None)
    count: int | str = 1
    name: int | str = "a"
    either: int | str = one_of(count, name)
    del either


def a_matcher_fits_an_invariant_container_slot() -> None:
    """The whole point, and the thing ``dirty-equals`` cannot do.

    ``list[int | IsInt]`` is what a matcher with an honest type forces on the
    caller, and it stops the element type from meaning anything. These slots keep
    meaning what they said.
    """
    rows: dict[str, int] = {"a": any_instance_of(int)}
    items: list[int] = [any_instance_of(int), 7]
    pair: tuple[int, str] = (any_instance_of(int), string_matching("^a"))
    members: set[str] = {string_containing("a")}
    ratios: list[float] = [close_to(1.0, tol=0.5)]
    del rows, items, pair, members, ratios


def a_matcher_nests_to_any_depth() -> None:
    payload: dict[str, dict[str, int]] = {"user": containing({"id": any_instance_of(int)})}
    nested: dict[str, list[str]] = {"tags": [string_matching("^a"), "b"]}
    del payload, nested


def a_matcher_goes_into_an_expectation() -> None:
    """Where matchers are actually written, on the assertions that take one."""
    expect({"id": 7, "name": "ada"}).is_equal_to({"id": any_instance_of(int), "name": "ada"})
    expect({"id": 7}).is_equivalent_to({"id": any_instance_of(int)})
    expect(["a", "b"]).contains(string_matching("^a"))
    expect({"n": 1}).is_equal_to({"n": one_of(0, 1)})


def a_matcher_goes_into_a_recorded_call() -> None:
    sender = Mock()
    expect(sender, as_=MockExpect).was_called_with(any_instance_of(str), retries=one_of(0, 1))


def a_predicate_matcher_takes_its_parameter_type() -> None:
    def is_even(value: int) -> bool:
        return value % 2 == 0

    assert_type(matching(is_even), int)
    counts: dict[str, int] = {"n": matching(is_even)}
    del counts


def a_lambda_predicate_takes_its_type_from_the_slot() -> None:
    """Which is where a matcher is written, so the common spelling is the safe one.

    Both checkers solve ``T`` from the target and hand the lambda its parameter
    type. A ``matching(lambda ...)`` written with no target at all has nothing to
    solve from and neither checker can type it -- the same limitation any generic
    callback has, and the reason the examples all sit in an expectation.
    """
    counts: dict[str, int] = {"n": matching(lambda value: value > 3)}
    scores: list[float] = [matching(lambda value: value > 0.5)]
    del counts, scores


def a_tolerance_is_keyword_only_and_optional() -> None:
    assert_type(close_to(1.0), float)
    assert_type(close_to(1.0, tol=0.5), float)
    assert_type(close_to(1.0, rel=0.01), float)
    assert_type(close_to(1, tol=1, rel=0.01), float)


def anything_really_does_go_anywhere() -> None:
    """``Any`` is the honest annotation for the one matcher that refuses nothing."""
    count: int = anything()
    name: str = anything()
    rows: dict[str, list[int]] = {"a": anything()}
    del count, name, rows


def the_predicate_is_a_bool() -> None:
    assert_type(is_matcher(any_instance_of(int)), bool)
