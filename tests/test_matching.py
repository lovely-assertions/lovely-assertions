"""Typed asymmetric matchers (``lovely_assertions._matching``).

Four things are pinned here, and they fail independently.

*The trick works, at any depth.* Nothing in the library knows matchers exist, so
every claim that ``is_equal_to``, ``is_equivalent_to``, ``contains`` and
``was_called_with`` support them is a claim about Python's reflected-comparison
protocol rather than about code anybody wrote. That makes it exactly the kind of
claim that stops being true without a test failing, so each route is exercised.

*The failure message reads.* A matcher whose mismatch prints
``<lovely_assertions._matching._AnyInstance object at 0x10f3a2d90>`` is worse
than no matcher, because the reader now has an address where the expectation used
to be. Every rendering route is checked -- and one of them,
``is_equivalent_to``, is checked because it is *coupled* to another module's
internals: see :func:`test_an_equivalence_failure_names_the_matcher`.

*``__eq__`` is total.* It is called by anything, from either side, against any
value, including from inside the difference engine while it explains somebody
else's failure. There is no value it may raise on and no value it may hang on.

*A matcher costs nothing to a test that does not use one, and little to one that
does.* The first half is the one that matters and is measured with the
allocation primitives from ``benchmarks``; timings live in the report rather than
in CI, for the reason ``benchmarks/__init__.py`` gives.

The lie the module is built on -- a factory annotated to return ``T`` that
returns a placeholder instead -- is the *static* claim, and a runtime suite
cannot see it at all. ``typing_tests/positive/matching.py`` and
``typing_tests/negative/matching_negative.py`` are the other half of this file.
"""

import copy
import math
from decimal import Decimal
from typing import Any, Final, cast
from unittest.mock import Mock

import pytest
from benchmarks import peak_bytes_allocated

from conftest import measured
from lovely_assertions import (
    AssertionFailure,
    MockExpect,
    ObjectFormatter,
    _matching,
    expect,
    format_value,
    soft_assertions,
)
from lovely_assertions._formatters import _registry
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


def is_truthy(value: object, /) -> bool:
    """A named predicate, so that a message has something to name."""
    return bool(value)


def is_falsey(value: object, /) -> bool:
    """A second named predicate, so two matchers can differ by the one they hold."""
    return not value


MATCHERS: Final[list[object]] = [
    any_instance_of(int),
    anything(),
    string_matching("^a"),
    string_containing("a"),
    close_to(1),
    one_of(1),
    containing({"a": 1}),
    containing([1]),
    matching(is_truthy),
]


def cast_to_pattern(pattern: object, /) -> str:
    """A pattern past its declared type, to reach the runtime check behind it.

    ``string_matching`` is declared ``str | re.Pattern[str]``, so both checkers
    already refuse bytes -- and the runtime guard exists for the caller whose own
    annotations were wrong, which is the caller a typed test cannot spell. Same
    role as :func:`raw`, one argument earlier.
    """
    return cast("str", pattern)


def raw(matcher: object, /) -> object:
    """A matcher as the object it really is, rather than as the type it claims.

    Every factory in this module is annotated to return the type it stands in
    for, which is the whole point and is a lie. A test that compares
    ``any_instance_of(int)`` with a string is then reported by pyright as a
    comparison that can never hold -- correctly, against the declared type, and
    uselessly, because the declared type is the fiction under test. Widening
    through here is where this file stops believing the annotation.
    """
    return matcher


def matcher_base() -> Any:
    """The private base class every matcher shares.

    Read out of the module namespace by name rather than as an attribute, the way
    :func:`_global_registry` reads ``_GLOBAL`` below: a direct access to a
    protected name across a module boundary is what pyright reports.
    """
    return vars(_matching)["_Matcher"]


def message_of(failure: pytest.ExceptionInfo[AssertionFailure], /) -> str:
    return str(failure.value)


def a_dict(**entries: object) -> dict[str, Any]:
    """A mapping whose value type is wide enough to hold a matcher honestly."""
    return dict(entries)


# ---------------------------------------------------------------------------
# The trick: a matcher stands in for a value, at any depth, with no walker
# ---------------------------------------------------------------------------
def test_a_matcher_stands_in_for_a_value_under_is_equal_to() -> None:
    expect({"id": 7, "name": "ada"}).is_equal_to({"id": any_instance_of(int), "name": "ada"})


def test_a_matcher_that_does_not_match_still_fails_the_assertion() -> None:
    """The half that proves the first test is not passing for free."""
    with pytest.raises(AssertionFailure):
        expect({"id": "oops"}).is_equal_to({"id": any_instance_of(int)})


def test_a_matcher_is_reached_at_any_depth() -> None:
    """No walker: ``==`` descends and the reflected call lands on the matcher."""
    actual = {"user": {"id": 7, "tags": ["a", "b"], "score": 0.5000001}}
    expect(actual).is_equal_to(
        {
            "user": {
                "id": any_instance_of(int),
                "tags": ["a", string_matching("^b")],
                "score": close_to(0.5, tol=0.001),
            }
        }
    )


def test_a_matcher_works_through_is_equivalent_to() -> None:
    expect({"id": 7}).is_equivalent_to({"id": any_instance_of(int)})
    with pytest.raises(AssertionFailure):
        expect({"id": "oops"}).is_equivalent_to({"id": any_instance_of(int)})


def test_a_matcher_works_through_contains() -> None:
    """A sequence membership test is a scan, so the matcher is reached.

    The lists are annotated ``list[object]`` because the checkers are doing their
    job: ``expect(["a", "b"]).contains(any_instance_of(int))`` is an ``int``
    matcher offered to a ``list[str]``, and both of them reject it. That rejection
    is the feature -- ``typing_tests/negative/matching_negative.py`` pins it -- so
    the runtime test has to ask its question somewhere the slot is wide enough for
    the answer to be interesting.
    """
    mixed: list[object] = ["a", 7]
    strings: list[object] = ["a", "b"]
    expect(mixed).contains(any_instance_of(int))
    with pytest.raises(AssertionFailure):
        expect(strings).contains(any_instance_of(int))


def test_a_matcher_works_through_a_mock_call_record() -> None:
    """``as_=MockExpect`` because a mock's static type says nothing about what it stands in for."""
    sender = Mock()
    sender("payload", retries=1)
    expect(sender, as_=MockExpect).was_called_with(any_instance_of(str), retries=one_of(0, 1))
    with pytest.raises(AssertionFailure):
        expect(sender, as_=MockExpect).was_called_with(any_instance_of(int), retries=one_of(0, 1))


def test_the_reflected_comparison_is_what_makes_it_work() -> None:
    """The mechanism itself, stated as a test so that it cannot quietly change.

    ``7 == matcher`` never calls the matcher first: ``int.__eq__`` runs, answers
    ``NotImplemented`` because it has never heard of this type, and Python then
    asks the right-hand side. Everything else in this file rests on that.
    """
    assert raw(any_instance_of(int)).__eq__(7) is True
    assert (7).__eq__(raw(any_instance_of(int))) is NotImplemented
    assert raw(any_instance_of(int)) == 7


def test_a_matcher_nests_inside_another_matcher() -> None:
    expect({"user": {"id": 7, "role": "admin"}}).is_equal_to(
        {"user": containing({"id": any_instance_of(int)})}
    )
    expect({"n": 3}).is_equal_to({"n": one_of(1, any_instance_of(int))})


# ---------------------------------------------------------------------------
# The failure message
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("matcher", "expected"),
    [
        (any_instance_of(int), "<any int>"),
        (anything(), "<anything>"),
        (string_matching("^ey"), "<string matching '^ey'>"),
        (string_containing("ab"), "<string containing 'ab'>"),
        (close_to(60), "<close to 60>"),
        (close_to(60, tol=1), "<close to 60 ± 1>"),
        (close_to(60, rel=0.1), "<close to 60 ± 0.1 relative>"),
        (close_to(60, tol=1, rel=0.1), "<close to 60 ± 1 or 0.1 relative>"),
        (one_of(1, 2), "<one of 1, 2>"),
        (containing({"a": 1}), "<containing {'a': 1}>"),
        (containing([1, 2]), "<containing 1, 2>"),
        (matching(is_truthy), "<matching is_truthy>"),
    ],
    ids=lambda value: str(value)[:40],
)
def test_every_matcher_reads_as_the_phrase_it_stands_for(matcher: object, expected: str) -> None:
    assert repr(matcher) == expected
    assert format_value(matcher) == expected


def test_a_lambda_predicate_is_not_named_in_the_message() -> None:
    """``<matching <lambda>>`` tells the reader nothing they could act on."""
    assert repr(raw(matching(lambda value: value is not None))) == "<matching a predicate>"


def test_a_long_one_of_is_truncated_like_every_other_list() -> None:
    assert repr(raw(one_of(*range(15)))) == ("<one of 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (5 more)>")


class _Unnameable(type):
    """A metaclass that makes ``__name__`` raise. They are rare, and they exist.

    ``type.__name__`` is declared ``str`` and reads as the one attribute of a
    class that cannot fail, which is exactly why ``_type_name`` widens past that
    declaration before testing it: the lookup goes through the metaclass, and a
    metaclass may answer however it likes.
    """

    __slots__ = ()

    def __getattribute__(cls, name: str) -> Any:
        if name == "__name__":
            raise RuntimeError("this class refuses to be named")
        return super().__getattribute__(name)


class _Misnamed(type):
    """A metaclass whose ``__name__`` is not a string at all."""

    __slots__ = ()

    def __getattribute__(cls, name: str) -> Any:
        if name == "__name__":
            return 7
        return super().__getattribute__(name)


class _WithoutAName(metaclass=_Unnameable):
    __slots__ = ()


class _WithAnOddName(metaclass=_Misnamed):
    __slots__ = ()


def test_a_class_whose_name_raises_still_leaves_a_readable_message() -> None:
    """A ``repr`` that raised would cost the reader the message it was raised in.

    The matcher stands in for a class it cannot name, so the phrase it renders is
    all it has -- and the assertion around it still explains itself.
    """
    with pytest.raises(AssertionFailure) as failure:
        expect({"x": "oops"}).is_equal_to({"x": any_instance_of(_WithoutAName)})

    assert repr(raw(any_instance_of(_WithoutAName))) == "<any <unnameable type>>"
    assert message_of(failure) == (
        'Expected {"x": "oops"} to equal {\'x\': <any <unnameable type>>}, '
        "but was {'x': 'oops'}.\n"
        "  values differ at key 'x': 'oops' instead of <any <unnameable type>>"
    )


def test_a_class_whose_name_is_not_a_string_reads_as_unnameable_too() -> None:
    """The other half of the same guard: a metaclass may hand back anything."""
    assert repr(raw(any_instance_of(_WithAnOddName))) == "<any <unnameable type>>"


def test_an_equality_failure_names_the_matcher() -> None:
    with pytest.raises(AssertionFailure) as failure:
        expect({"id": "oops", "n": "x"}).is_equal_to({"id": any_instance_of(int), "n": "x"})
    message = message_of(failure)
    assert "to equal {'id': <any int>, 'n': 'x'}" in message
    assert "'oops' instead of <any int>" in message
    assert "_AnyInstance" not in message


def test_an_equivalence_failure_names_the_matcher() -> None:
    """The coupled one, and the reason ``_Matcher``'s slots are spelled oddly.

    ``_equivalence._classify`` decides whether a value is a *leaf* or a *record*
    by reading its ``__slots__``, dropping only the names that both begin and end
    with an underscore. A matcher holding a plainly-named ``_kind`` would be a
    record, and this message would read ``types differ: str instead of
    _AnyInstance`` -- a private class name in place of the expectation. Take the
    trailing underscore off the slots in ``_matching.py`` and this test goes red.
    """
    with pytest.raises(AssertionFailure) as failure:
        expect({"id": "oops"}).is_equivalent_to({"id": any_instance_of(int)})
    message = message_of(failure)
    assert "'oops' instead of <any int>" in message
    assert "_AnyInstance" not in message
    assert "types differ" not in message


def test_a_mock_call_failure_names_the_matcher() -> None:
    sender = Mock()
    sender("a", n=3)
    with pytest.raises(AssertionFailure) as failure:
        expect(sender, as_=MockExpect).was_called_with(any_instance_of(int), n=one_of(1, 2))
    message = message_of(failure)
    assert "to have been called with (<any int>, n=<one of 1, 2>)" in message
    assert "3 instead of <one of 1, 2>" in message


def test_a_nested_failure_names_the_matcher() -> None:
    with pytest.raises(AssertionFailure) as failure:
        expect({"user": {"id": "x"}}).is_equal_to(
            {"user": containing({"id": any_instance_of(int)})}
        )
    message = message_of(failure)
    assert "<containing {'id': <any int>}>" in message
    assert "0x" not in message


@pytest.mark.parametrize("matcher", MATCHERS, ids=lambda value: str(value)[:40])
def test_no_failure_message_ever_shows_an_address(matcher: object) -> None:
    """The failure this module exists to prevent, stated once over the whole surface.

    The expectation is a mapping and the subject is a string, so the comparison
    fails for every matcher there is -- ``anything()`` included, which has no
    value it *would* have refused.
    """
    with pytest.raises(AssertionFailure) as failure:
        expect("nothing like it").is_equal_to(a_dict(unmatched=matcher))
    message = message_of(failure)
    assert " object at 0x" not in message
    assert repr(matcher) in message


class _Ticket:
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code


def test_a_value_inside_a_matcher_goes_through_the_formatter_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A domain type reads as itself inside a matcher exactly as it does outside."""
    registry = [*_global_registry(), ObjectFormatter(_Ticket, "code")]
    monkeypatch.setattr(_registry, "GLOBAL", registry)
    assert format_value(raw(one_of(_Ticket("AB-1")))) == "<one of _Ticket(code='AB-1')>"


class _Greedy:
    """A formatter written more widely than its author meant. They exist."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return True

    def format(self, value: object, /) -> str:
        return "claimed"


def _global_registry() -> list[object]:
    return list(vars(_registry)["GLOBAL"])


def test_a_later_formatter_cannot_take_a_matcher_over(monkeypatch: pytest.MonkeyPatch) -> None:
    """Why :class:`_matching._MatcherFormatter` is registered at all.

    ``repr`` alone already renders every matcher correctly, because every
    rendering site in this library falls back to it. What the registration buys is
    *priority* over a user formatter registered later -- and the second half of
    this test is what proves that priority is doing something, by showing the same
    greedy formatter taking the matcher over once ours is out of the way.
    """
    greedy = _Greedy()
    monkeypatch.setattr(_registry, "GLOBAL", [*_global_registry(), greedy])
    assert format_value(raw(any_instance_of(int))) == "<any int>"

    monkeypatch.setattr(_registry, "GLOBAL", [greedy])
    assert format_value(raw(any_instance_of(int))) == "claimed"


def test_a_scoped_formatter_still_wins() -> None:
    """Scoping is how a block asks for a different rendering; that stays true.

    The global registration takes priority over anything a ``conftest`` adds
    *later*; it does not take priority over a block that asked for something
    else. ``_formatters`` consults scoped formatters ahead of global ones, and
    this is what says the matcher formatter is not an exception to that.
    """
    with pytest.raises(AssertionFailure) as failure, soft_assertions(formatters=(_Greedy(),)):
        expect("x").is_equal_to(any_instance_of(int))
    assert "claimed" in str(failure.value)


# ---------------------------------------------------------------------------
# ``__eq__`` is total
# ---------------------------------------------------------------------------
class _Hostile:
    """A value that raises rather than answer whether it is equal to anything.

    At module scope because two tests need it: one where it sits in the value a
    matcher is compared against, and one where it sits in the *spec* of two
    matchers being compared with each other.
    """

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        raise RuntimeError("no")

    def __hash__(self) -> int:
        return 0


def test_a_matcher_compares_against_none_without_raising() -> None:
    assert raw(any_instance_of(int)) != None  # noqa: E711  (that is the comparison under test)
    assert raw(anything()) == None  # noqa: E711
    assert raw(one_of(None)) == None  # noqa: E711


def test_a_matcher_compares_against_a_mock_without_raising() -> None:
    """A mock answers every attribute, so anything duck-typed here would be wrong."""
    mock = Mock()
    assert raw(any_instance_of(int)) != mock
    assert raw(anything()) == mock
    assert raw(string_containing("a")) != mock


def test_two_matchers_of_one_kind_compare_by_what_built_them() -> None:
    assert raw(any_instance_of(int)) == any_instance_of(int)
    assert raw(any_instance_of(int)) != any_instance_of(str)
    assert raw(one_of(1, 2)) == one_of(1, 2)
    assert raw(one_of(1, 2)) != one_of(2, 1)
    assert raw(string_matching("^a")) == string_matching("^a")


def test_two_string_containing_matchers_compare_by_their_fragment() -> None:
    assert raw(string_containing("ab")) == string_containing("ab")
    assert raw(string_containing("ab")) != string_containing("ba")


def test_two_close_to_matchers_compare_by_their_value_and_their_tolerance() -> None:
    assert raw(close_to(60, tol=1)) == close_to(60, tol=1)
    assert raw(close_to(60, tol=1)) != close_to(61, tol=1)
    assert raw(close_to(60, tol=1)) != close_to(60, tol=2)


def test_two_close_to_matchers_written_differently_are_not_equal() -> None:
    """Same band, same numbers accepted, two different phrases in a message.

    ``tol=1`` and ``rel=1/60`` around 60 resolve to one absolute band, so they
    accept and reject exactly the same numbers -- and they print as different
    expectations, which is behaviour a reader meets in a failure message. A
    matcher is compared as the expectation somebody wrote, not as the set of
    values it happens to admit; ``at_least(3)`` and ``more_than(2)`` are held
    apart on the same rule, and so are ``one_of(1, 2)`` and ``one_of(2, 1)``.
    """
    absolute = raw(close_to(60, tol=1))
    relative = raw(close_to(60, rel=1 / 60))

    # The premise, without which there would be nothing to decide: no number
    # tells these two apart, at the edge of the band or anywhere else.
    assert absolute == 61.0
    assert relative == 61.0
    assert absolute != 61.0000001
    assert relative != 61.0000001

    assert repr(absolute) == "<close to 60 ± 1>"
    assert repr(relative) == "<close to 60 ± 0.016666666666666666 relative>"
    assert absolute != relative


def test_two_containing_matchers_compare_by_the_items_they_look_for() -> None:
    assert raw(containing([1, 2])) == containing([1, 2])
    assert raw(containing([1, 2])) != containing([1, 3])


def test_two_matching_matchers_compare_by_their_predicate() -> None:
    assert raw(matching(is_truthy)) == matching(is_truthy)
    assert raw(matching(is_truthy)) != matching(is_falsey)


def test_a_copied_matcher_built_from_nothing_still_equals_the_original() -> None:
    """Two matchers with no spec are equal by having none -- the base ``_spec_key``.

    ``anything()`` hands back one shared object, so a copy is the only way to
    hold two of them, and a deep copy of a payload carrying an expectation is how
    that happens outside a test.
    """
    original = raw(anything())

    copied = copy.deepcopy(original)

    assert copied is not original
    assert original == copied


def test_two_matchers_whose_specs_cannot_be_compared_are_not_equal() -> None:
    """``__eq__`` is total against another matcher too, not only against a value.

    The two specs hold different objects, so the tuple comparison cannot take its
    identity shortcut and asks the hostile value itself.
    """
    assert raw(one_of(_Hostile())).__eq__(one_of(_Hostile())) is False


def test_two_matchers_of_different_kinds_are_never_equal() -> None:
    """Symmetry, and the reason ``__eq__`` answers ``NotImplemented`` here.

    ``anything()`` matches every value there is. If it matched another matcher on
    the same rule, ``anything() == any_int`` would be ``True`` while
    ``any_int == anything()`` was ``False``, and ``==`` would depend on which side
    each was written -- for two objects that both define it.
    """
    any_value, any_int = raw(anything()), raw(any_instance_of(int))
    assert any_value.__eq__(any_int) is NotImplemented
    assert any_int.__eq__(any_value) is NotImplemented
    assert any_value != any_int
    assert any_int != any_value


def test_a_matcher_compares_equal_to_itself() -> None:
    matcher = raw(containing({"a": 1}))
    assert matcher == matcher  # noqa: PLR0124  (identity through `==` is the claim)


def test_a_matcher_survives_being_a_set_member_and_a_dict_key() -> None:
    matchers = {raw(any_instance_of(int)), raw(any_instance_of(str)), raw(anything())}
    assert len(matchers) == 3
    assert len({raw(one_of(1, 2)), raw(one_of(1, 2))}) == 1
    index = {raw(anything()): "any"}
    assert index[raw(anything())] == "any"


def test_a_matcher_with_an_unhashable_spec_is_still_hashable() -> None:
    """The reason ``__hash__`` answers from the class rather than from the spec."""
    assert isinstance(hash(raw(containing({"a": [1, 2]}))), int)
    assert isinstance(hash(raw(one_of([1], [2]))), int)


def test_a_hash_is_stable_across_calls() -> None:
    matcher = raw(one_of(1, 2))
    assert hash(matcher) == hash(matcher)


def test_hash_based_containment_does_not_match_and_is_documented() -> None:
    """The one place a matcher cannot reach, pinned so the docstring cannot drift.

    ``in`` against a set is a hash lookup, and no object can be hashed into
    agreement with everything it is equal to. The module docstring says so; this
    is what keeps that sentence true.
    """
    assert raw(any_instance_of(int)) not in {1, 2, 3}
    assert raw(any_instance_of(int)) in [1, 2, 3]


def test_a_value_whose_equality_raises_costs_a_match_rather_than_the_run() -> None:
    assert raw(one_of(_Hostile())) != 3
    assert raw(containing({"a": _Hostile()})) != {"a": 3}


def test_a_predicate_that_raises_is_read_as_no_match() -> None:
    def explodes(value: object) -> bool:
        raise RuntimeError(repr(value))

    assert raw(matching(explodes)) != 3
    with pytest.raises(AssertionFailure) as failure:
        expect({"n": 3}).is_equal_to({"n": matching(explodes)})
    assert "<matching explodes>" in message_of(failure)


def test_the_base_matcher_refuses_to_say_whether_it_matches() -> None:
    """``matches`` *is* the subclass, so the base has nothing it could answer.

    Built with ``type()`` rather than a ``class`` statement because the base is
    private: mypy refuses to inherit from a name it only knows as ``Any``.
    """
    forgetful: Any = type("Forgetful", (matcher_base(),), {"__slots__": ()})

    with pytest.raises(NotImplementedError):
        forgetful().matches("anything at all")


def test_a_matcher_that_forgot_matches_refuses_inside_a_comparison_too() -> None:
    """The refusal above is worth nothing if ``==`` swallows it, so it does not.

    ``__eq__`` is total about the *values* it is handed, which is a promise made
    to somebody else's code. A subclass that never implemented its own method is
    this library's contract broken instead, and reading it as "no match" would
    buy a matcher that stands for nothing wherever it is placed: in
    ``is_not_equal_to`` or ``does_not_contain`` it never matches, so the assertion
    passes every time and that test can no longer fail.
    """
    forgetful: Any = type("Forgetful", (matcher_base(),), {"__slots__": ()})

    with pytest.raises(NotImplementedError):
        forgetful().__eq__("x")


def test_a_predicate_that_raises_not_implemented_is_still_read_as_no_match() -> None:
    """The same exception class out of a caller's code, and the opposite answer.

    Which is the distinction being drawn: an unfinished predicate is exactly the
    code ``__eq__``'s totality was promised to, and it is met from inside a
    ``dict`` comparison the difference engine is making, where an error costs the
    reader the failure message they were owed.
    """

    def unfinished(value: object) -> bool:
        raise NotImplementedError(repr(value))

    assert raw(matching(unfinished)) != 3


def test_a_matcher_is_immutable() -> None:
    matcher = raw(any_instance_of(int))
    with pytest.raises(AttributeError, match="immutable"):
        matcher._kind_ = str  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(AttributeError, match="immutable"):
        del matcher._kind_  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]


def test_anything_hands_back_one_shared_object() -> None:
    """Which is only safe because a matcher cannot be changed."""
    assert raw(anything()) is raw(anything())


# ---------------------------------------------------------------------------
# What each matcher means
# ---------------------------------------------------------------------------
def test_any_instance_of_follows_isinstance() -> None:
    class Base:
        __slots__ = ()

    class Derived(Base):
        __slots__ = ()

    assert raw(any_instance_of(Base)) == Derived()
    assert raw(any_instance_of(int)) == True  # noqa: E712  (a bool *is* an int)
    assert raw(any_instance_of(str)) != 7
    assert raw(any_instance_of(object)) == 7


def test_anything_matches_anything() -> None:
    values: tuple[object, ...] = (None, 0, "", [], object(), float("nan"))
    for value in values:
        assert raw(anything()) == value


def test_string_matching_is_a_search_not_a_full_match() -> None:
    """The same reading ``StringExpect.matches`` documents."""
    assert raw(string_matching("wor")) == "hello world"
    assert raw(string_matching("^hello")) == "hello world"
    assert raw(string_matching("^world")) != "hello world"
    assert raw(string_matching("a")) != 7


def test_string_matching_keeps_the_flags_of_a_compiled_pattern() -> None:
    import re

    assert raw(string_matching(re.compile("HELLO", re.IGNORECASE))) == "hello"
    assert raw(string_matching("HELLO")) != "hello"


def test_string_matching_refuses_a_bytes_pattern() -> None:
    """A matcher that can never match is a bug at the call, not a finding later.

    ``re`` compiles a bytes pattern happily, and the matcher it would build asks
    every candidate for ``isinstance(value, str)`` first -- so it matches nothing,
    for ever. The damage is not a wrong failure message: in a negative assertion
    it is a test that passes every time and can no longer fail, which is exactly
    what ``one_of()`` and ``containing({})`` are refused for.
    """
    import re

    with pytest.raises(TypeError, match="bytes pattern matches no string"):
        string_matching(cast_to_pattern(b"^ey"))
    with pytest.raises(TypeError, match="bytes pattern matches no string"):
        string_matching(cast_to_pattern(re.compile(b"^ey")))


def test_a_bytes_pattern_would_otherwise_have_made_a_negative_assertion_vacuous() -> None:
    """What the refusal above is actually protecting, spelled as the damage.

    With the pattern accepted, this assertion passes -- and would pass for every
    payload anybody ever wrote, because the matcher inside it never matches.
    """
    with pytest.raises(TypeError):
        expect(a_dict(t="eyJ")).is_not_equal_to({"t": string_matching(cast_to_pattern(b"^ey"))})


def test_string_containing_is_a_plain_substring() -> None:
    assert raw(string_containing("b.c")) == "a b.c d"
    assert raw(string_containing("b.c")) != "abXc"
    assert raw(string_containing("a")) != 7


@pytest.mark.parametrize(
    ("value", "tol", "rel", "candidate"),
    [
        (1.0, None, None, 1.0),
        (1.0, None, None, 1.0 + 1e-9),
        (60, 1, None, 59.5),
        (60, None, 0.1, 55.0),
        (0.0, None, None, 0.0),
        (float("inf"), None, None, float("inf")),
        (10**400, 1, None, 10**400),
    ],
)
def test_close_to_agrees_with_the_numeric_assertion(
    value: float, tol: float | None, rel: float | None, candidate: float
) -> None:
    """One question, one answer: the matcher and ``is_close_to`` share the helpers.

    Both directions are asserted, so a matcher that accepted *more* than the
    assertion would be caught as readily as one that accepted less.
    """
    matched = raw(close_to(value, tol=tol, rel=rel)) == candidate
    try:
        expect(candidate).is_close_to(value, tol=tol, rel=rel)
        asserted = True
    except AssertionFailure:
        asserted = False
    assert matched is asserted is True


@pytest.mark.parametrize(
    ("value", "tol", "rel", "candidate"),
    [(1.0, None, None, 1.1), (60, 1, None, 50), (60, None, 0.01, 40), (1.0, None, None, math.nan)],
)
def test_close_to_refuses_what_the_numeric_assertion_refuses(
    value: float, tol: float | None, rel: float | None, candidate: float
) -> None:
    assert raw(close_to(value, tol=tol, rel=rel)) != candidate
    with pytest.raises(AssertionFailure):
        expect(candidate).is_close_to(value, tol=tol, rel=rel)


def test_close_to_does_not_match_a_decimal() -> None:
    """The boundary ``NumericExpect.is_close_to`` draws, drawn the same way here."""
    assert raw(close_to(1.0, tol=0.5)) != Decimal("1.0")


def test_close_to_matches_a_bool_the_way_equality_does() -> None:
    assert raw(close_to(1.0, tol=0.001)) == True  # noqa: E712


def test_one_of_finds_a_nan_where_it_sits() -> None:
    """Identity before equality, which is the rule ``in`` already follows."""
    nan = float("nan")
    assert raw(one_of(nan)) == nan
    assert raw(one_of(float("nan"))) != nan


def test_containing_is_a_subset_of_a_mapping() -> None:
    assert raw(containing({"a": 1})) == {"a": 1, "b": 2}
    assert raw(containing({"a": 1})) != {"a": 2, "b": 2}
    assert raw(containing({"a": 1})) != {"b": 2}
    assert raw(containing({"a": 1})) != ["a"]


def test_containing_is_a_subset_of_a_sequence_in_any_order() -> None:
    assert raw(containing([1, 2])) == [3, 2, 1]
    assert raw(containing([1, 2])) == (1, 2)
    assert raw(containing({1, 2})) == [1, 2, 3]
    assert raw(containing([1, 4])) != [1, 2, 3]


def test_containing_scans_rather_than_hashes() -> None:
    """Which is what lets a nested matcher work inside a set."""
    assert raw(containing([any_instance_of(int)])) == {1, 2}
    assert raw(containing([any_instance_of(str)])) != {1, 2}


def test_containing_never_reads_a_mapping_as_a_sequence_of_its_keys() -> None:
    """The wrong pass this would otherwise be, since iterating a dict yields keys."""
    assert raw(containing(["a"])) != {"a": 1}


def test_containing_never_reads_text_as_a_sequence_of_characters() -> None:
    assert raw(containing(["a", "b"])) != "ab"


def test_matching_takes_any_predicate() -> None:
    assert raw(matching(lambda value: value == 4)) == 4
    assert raw(matching(lambda value: value == 4)) != 5


def test_is_matcher_tells_a_matcher_from_a_value() -> None:
    assert is_matcher(raw(any_instance_of(int)))
    assert is_matcher(raw(anything()))
    assert not is_matcher(7)
    assert not is_matcher(Mock())


# ---------------------------------------------------------------------------
# Caller bugs raise where they were written
# ---------------------------------------------------------------------------
def test_a_choice_between_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        one_of()


def test_an_empty_container_spec_is_refused() -> None:
    """It matches every container there is, so the assertion asserts nothing."""
    no_entries: dict[str, int] = {}
    no_items: list[int] = []
    with pytest.raises(ValueError, match="at least one entry"):
        containing(no_entries)
    with pytest.raises(ValueError, match="at least one entry"):
        containing(no_items)


@pytest.mark.parametrize("spec", [3, "ab", b"ab", None])
def test_containing_refuses_something_it_cannot_look_inside(spec: object) -> None:
    with pytest.raises(TypeError, match="mapping, a sequence or a set"):
        containing(spec)


def test_any_instance_of_refuses_something_that_is_not_a_class() -> None:
    """Reported here rather than from inside a comparison that may never raise."""
    with pytest.raises(TypeError, match="takes a class"):
        any_instance_of(cast_to_type("int"))


def test_matching_refuses_something_that_is_not_callable() -> None:
    with pytest.raises(TypeError, match="callable"):
        matching(cast_to_predicate(3))


@pytest.mark.parametrize(
    ("tol", "rel"), [(-1.0, None), (None, -1.0), (math.nan, None), (None, math.nan)]
)
def test_close_to_refuses_a_tolerance_no_value_could_satisfy(
    tol: float | None, rel: float | None
) -> None:
    with pytest.raises(ValueError, match="tolerance"):
        close_to(1.0, tol=tol, rel=rel)


def test_close_to_refuses_a_nan_target() -> None:
    """A NaN is close to nothing, itself included, so the matcher could never match."""
    with pytest.raises(ValueError, match="matches nothing"):
        close_to(math.nan)


def cast_to_type(value: object) -> type[Any]:
    """A wrong argument, declared right, so the runtime check is the one under test."""
    return value  # type: ignore[return-value]  # pyright: ignore[reportReturnType]


def cast_to_predicate(value: object) -> "Any":
    """As above, for :func:`matching`."""
    return value


# ---------------------------------------------------------------------------
# A matcher is an expectation and never a subject
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("matcher", MATCHERS, ids=lambda value: str(value)[:40])
def test_expect_refuses_a_matcher(matcher: object) -> None:
    with pytest.raises(TypeError, match="belongs in an expectation"):
        expect(matcher)


def test_the_refusal_names_the_matcher_and_the_remedy() -> None:
    with pytest.raises(TypeError) as failure:
        expect(raw(any_instance_of(int)))
    message = str(failure.value)
    assert "<any int>" in message
    assert "is_equal_to" in message


def test_the_refusal_is_a_type_error_and_not_an_assertion_failure() -> None:
    """A caller bug is not a statement about a value under test."""
    with pytest.raises(TypeError) as failure:
        expect(raw(anything()))
    assert not isinstance(failure.value, AssertionError)


def test_every_matcher_type_is_refused() -> None:
    """The registration is a list; a matcher added without one would slip through."""
    registered = vars(_matching)["_MATCHER_TYPES"]
    assert len(registered) == len({type(matcher) for matcher in MATCHERS})


def test_ordinary_values_still_reach_their_subjects() -> None:
    """The refusal must not have cost anything else its dispatch."""
    assert expect(3).is_positive().subject == 3
    assert expect("x").starts_with("x").subject == "x"
    assert expect([1]).has_length(1).subject == [1]


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------
def _nothing() -> None:
    """The reference for work that is genuinely free."""


@measured
def test_comparing_against_a_matcher_allocates_nothing() -> None:
    """Comparing against a matcher happens on the passing path, which allocates nothing.

    A matcher is evaluated by ``==`` inside an assertion that is about to pass, so
    a generator expression or a formatted string in ``matches`` would be paid for
    on every green test. The matchers that scan allocate their loop's iterator and
    nothing else, which is the allowance the rest of the library takes -- and only
    they get it, because an allowance that everything shares stops being evidence.
    """
    baseline = peak_bytes_allocated(_nothing)
    one_iterator = 128
    rows = {"id": 7, "name": "ada"}
    expected = {"id": raw(any_instance_of(int)), "name": "ada"}
    any_value = raw(anything())
    holds_a = raw(string_containing("a"))
    either = raw(one_of(1, 2))
    near = raw(close_to(1.0))
    assert peak_bytes_allocated(lambda: rows == expected) <= baseline
    assert peak_bytes_allocated(lambda: any_value == rows) <= baseline
    assert peak_bytes_allocated(lambda: holds_a == "ada") <= baseline
    assert peak_bytes_allocated(lambda: either == 2) <= baseline + one_iterator
    # `close_to` does not scan, so it gets no share of that allowance. Spelling
    # its type test as `isinstance(value, int | float)` would build the union on
    # every comparison -- tens of bytes on most interpreters, small enough to
    # hide under a budget meant for something else, and an order of magnitude
    # more on CPython 3.14.
    assert peak_bytes_allocated(lambda: near == 1.0) <= baseline


@measured
def test_an_assertion_with_no_matcher_in_it_pays_for_none_of_this() -> None:
    """The claim that matters most, and the one the dispatch design is for.

    The refusal of ``expect(<matcher>)`` is registered rather than branched on, so
    a value that is not a matcher meets no extra test anywhere -- and a passing
    assertion still peaks at exactly the no-op's bytes with this module imported.
    """
    baseline = peak_bytes_allocated(_nothing)
    subject = expect(3)
    assert peak_bytes_allocated(lambda: subject.is_equal_to(3)) <= baseline


# ---------------------------------------------------------------------------
# The docstrings
# ---------------------------------------------------------------------------
def test_the_examples_in_the_docstrings_hold() -> None:
    """The docstrings promise specific output; a promise nobody checks is a comment."""
    import doctest

    results = doctest.testmod(_matching, extraglobs={"expect": expect})
    assert results.failed == 0
    assert results.attempted > 0
