"""Every marked line here must be rejected. It is the half that makes the other half mean something.

``typing_tests/positive/matching.py`` proves a matcher is accepted wherever the
type it stands in for is accepted. On its own that proves nothing: a matcher
annotated ``Any`` would pass every line of it. What is ruled out here is exactly
that -- **the wrong matcher, in a slot whose type was fixed without matchers in
mind, is still refused**. If any of these lines ever stops being an error, the
trick has quietly turned into ``expect.any(Number)``: a matcher that fits
anywhere, which is the spelling this library does not offer.

The tolerances, the pattern and the predicate are checked too, because a factory
that took ``Any`` would swallow those mistakes on the way in and produce a
matcher that could never match anything -- a green test that asserts nothing.
"""

from lovely_assertions import expect
from lovely_assertions._matching import (
    any_instance_of,
    close_to,
    containing,
    matching,
    one_of,
    string_containing,
    string_matching,
)


def a_matcher_for_the_wrong_type_is_refused_by_an_invariant_slot() -> None:
    """The claim, in the one place it has to hold."""
    items: list[int] = [any_instance_of(str)]  # expect-error
    rows: dict[str, int] = {"a": any_instance_of(str)}  # expect-error
    pair: tuple[int, str] = (any_instance_of(str), "a")  # expect-error
    members: set[str] = {any_instance_of(int)}  # expect-error
    del items, rows, pair, members


def a_matcher_for_the_wrong_type_is_refused_by_an_assertion() -> None:
    """Wherever the assertion's parameter carries the element type."""
    expect(["a", "b"]).contains(any_instance_of(int))  # expect-error
    expect([1, 2]).contains(string_matching("^a"))  # expect-error


def a_nested_matcher_for_the_wrong_type_is_refused_too() -> None:
    ids: dict[str, dict[str, int]] = {"u": containing({"id": any_instance_of(str)})}  # expect-error
    del ids


def a_container_matcher_keeps_the_shape_it_was_built_from() -> None:
    names: dict[str, str] = containing({"a": 1})  # expect-error
    counts: list[int] = containing(["a"])  # expect-error
    del names, counts


def a_choice_keeps_the_type_of_what_was_chosen_between() -> None:
    name: str = one_of(1, 2)  # expect-error
    del name


def a_closeness_matcher_is_a_float_and_not_an_int() -> None:
    """``float`` covers an ``int`` slot nowhere: the numeric tower runs one way."""
    counts: dict[str, int] = {"n": close_to(1.0)}  # expect-error
    del counts


def the_factories_refuse_arguments_they_could_not_use() -> None:
    """A factory taking ``Any`` would build a matcher that never matches anything."""
    any_instance_of("int")  # expect-error: a class, not the name of one
    string_matching(3)  # expect-error
    string_containing(3)  # expect-error
    close_to("x")  # expect-error
    matching(3)  # expect-error: a predicate has to be callable


def a_tolerance_is_keyword_only_and_numeric() -> None:
    """The tolerances are keyword-only, so ``close_to(x, 0.5)`` never has to be guessed at."""
    close_to(1.0, 0.5)  # expect-error
    close_to(1.0, tol="0.5")  # expect-error
    close_to(1.0, rel="0.01")  # expect-error


def identity(value: int) -> int:
    return value


def a_predicate_has_to_return_a_verdict() -> None:
    """The inspector/predicate mix-up (``_core.collect_failures``), one module over."""
    counts: dict[str, int] = {"n": matching(identity)}  # expect-error
    del counts


def an_unannotated_lambda_predicate_is_only_caught_by_one_of_them() -> None:
    """An unannotated lambda predicate that returns its argument is caught by pyright only.

    ``matching(lambda value: value)`` in a ``dict[str, int]`` slot is a predicate
    that returns its argument rather than a verdict -- the mistake the line above
    catches when the predicate has a name. Given a *lambda*, mypy solves ``T``
    from the body instead of from the slot, lands on ``bool``, and accepts it
    because a ``bool`` fits an ``int`` slot; pyright solves ``T`` from the slot
    and reports it. Nothing in the signature can close that: it is where the two
    checkers disagree about which end of a generic call drives inference. What it
    costs is one shape of always-true matcher going unreported under mypy alone,
    and it is written down here rather than left to be discovered.
    """
    counts: dict[str, int] = {"n": matching(lambda value: value)}  # expect-error(pyright)
    del counts


def a_mixed_choice_needs_its_union_spelled(count: int, name: str) -> None:
    """pyright unions a variadic ``T``; mypy joins it, and lands on ``object``.

    ``one_of(1, "a")`` is ``int | str`` to pyright, which is what the caller
    meant, and ``object`` to mypy, which then refuses the assignment. Neither is
    wrong about its own inference rules and neither can be worked around without
    shaving the API -- an overload per arity would give mypy the union and would
    cap the number of choices. Spelling the union on the operands
    (``count: int | str``) is the workaround that costs nothing, and the positive
    corpus pins it.
    """
    either: int | str = one_of(count, name)  # expect-error(mypy)
    del either
