"""Every marked line here must be rejected by pyright and mypy.

Without this half, `typing_tests/positive/mock.py` proves nothing: a subject that
had quietly collapsed to `Any` would satisfy every `assert_type` in it. And this
subject is the one most at risk of exactly that, because its *value* is `Any` by
design -- so the tests below are mostly about the boundary between the parts that
are deliberately untyped (what a mock was called with) and the parts that are
not (which assertion, which subject comes back, what a call count is).

Two mistakes the mock surface exists to catch have their own sections: reaching
for `unittest.mock`'s own vocabulary on the subject, and giving `has_call_count`
something that is neither a count nor an occurrence constraint.

A third has a section of its own and is the load-bearing one for the async split:
`MockExpect` must **refuse** every await assertion. That refusal is the whole
argument for `AsyncMockExpect` being a separate subject rather than nine guarded
methods on this one -- a runtime guard cannot be pinned by a checker, and a
catalogue that advertises what it cannot answer is the thing this library exists
not to do. It is enforceable only through `as_=`: `expect(m)` hands back
something a checker cannot reason about at all.
"""

from typing import Any, assert_type
from unittest.mock import AsyncMock, Mock

from lovely_assertions import Expect, Found, SequenceExpect, expect
from lovely_assertions._mock import AsyncMockExpect, MockExpect, is_async_mock, is_mock


def a_mock() -> Mock:
    return Mock()


def an_async_mock() -> AsyncMock:
    return AsyncMock()


def the_subject_is_the_one_that_comes_back(subject: MockExpect) -> None:
    """The whole point of the typed surface: a chain that widened would be a lie."""
    assert_type(subject.was_called(), Expect[Any])  # expect-error
    assert_type(subject.was_called_once(), Expect[Any])  # expect-error
    assert_type(subject.was_called_with("/a"), Expect[Any])  # expect-error
    assert_type(subject.has_call_count(1), Expect[Any])  # expect-error


def the_continuations_have_the_shapes_they_have(subject: MockExpect) -> None:
    assert_type(subject.calls, MockExpect)  # expect-error
    assert_type(subject.calls, SequenceExpect[str])  # expect-error: the elements are calls
    assert_type(subject.last_call(), MockExpect)  # expect-error
    assert_type(subject.last_call(), Found[MockExpect, str])  # expect-error


def calls_makes_no_claim_and_is_not_called(subject: MockExpect) -> None:
    """A property, because an empty recording is an answer rather than a failure."""
    subject.calls()  # expect-error: `calls` is a property, not an assertion
    subject.calls(because="R")  # expect-error


def last_call_asserts_and_so_is_not_a_property(subject: MockExpect) -> None:
    """The other half of that asymmetry: it can fail, so it has to be called."""
    subject.last_call.which  # expect-error: `last_call()` -- it takes a `because`


def because_is_keyword_only(subject: MockExpect) -> None:
    """`because` is keyword-only, and it holds on the signatures carrying `**kwargs` too."""
    subject.was_called("R")  # expect-error: no positional parameters at all
    subject.was_not_called("R")  # expect-error
    subject.was_called_once("R")  # expect-error
    subject.has_call_count(1, "R")  # expect-error
    subject.last_call("R")  # expect-error


def a_call_count_is_a_count_or_a_constraint(subject: MockExpect) -> None:
    subject.has_call_count("3")  # expect-error: not a count
    subject.has_call_count(1.5)  # expect-error: a call count is a whole number
    subject.has_call_count(None)  # expect-error
    subject.has_call_count([1])  # expect-error
    subject.has_call_count()  # expect-error: it is required
    subject.has_call_count(exactly=3)  # expect-error: positional-only


def an_occurrence_constraint_needs_both_of_its_methods(subject: MockExpect) -> None:
    """`Occurrence` is structural, so an object with half of it must be refused."""

    class HalfAConstraint:
        def allows(self, count: int, /) -> bool:
            return count > 0

    subject.has_call_count(HalfAConstraint())  # expect-error: no `describe`

    class WrongShape:
        def allows(self, count: int, /) -> str:
            return str(count)

        def describe(self) -> str:
            return "sometimes"

    subject.has_call_count(WrongShape())  # expect-error: `allows` returns a bool


def the_predicate_answers_a_bool_and_nothing_else() -> None:
    assert_type(is_mock(a_mock()), Any)  # expect-error
    is_mock()  # expect-error: it takes a value
    is_mock(a_mock(), a_mock())  # expect-error: one value


def unittest_mocks_own_vocabulary_is_not_on_the_subject(subject: MockExpect) -> None:
    """The mistake the module exists to make impossible, checked statically too.

    On a bare mock every one of these returns a child mock and passes. On the
    subject they are not merely wrong at runtime -- they do not type-check.
    """
    subject.assert_called_with("/a")  # expect-error
    subject.assert_called_once_with("/a")  # expect-error
    subject.assert_not_called()  # expect-error
    subject.was_called_once_wth("/a")  # expect-error: the textbook typo
    subject.was_ever_called("/a")  # expect-error: not a name this subject has
    subject.call_count  # expect-error: read it through `.subject`


def the_recorded_calls_are_not_the_mock(subject: MockExpect) -> None:
    """`calls` descends; the sequence subject has no mock assertions on it."""
    subject.calls.was_called()  # expect-error
    subject.calls.has_call_count(1)  # expect-error


def a_finder_is_not_a_subject(subject: MockExpect) -> None:
    subject.last_call().was_called()  # expect-error: `.and_` first
    subject.last_call().calls  # expect-error


def the_constructor_takes_one_subject() -> None:
    MockExpect()  # expect-error: there is nothing to assert on
    MockExpect(a_mock(), a_mock())  # expect-error
    MockExpect(a_mock(), name="fetch")  # expect-error: `expect(..., name=...)` does that


# ---------------------------------------------------------------------------
# A synchronous mock has no await catalogue
# ---------------------------------------------------------------------------
def the_await_assertions_are_not_on_the_plain_subject(subject: MockExpect) -> None:
    """Claim one, made enforceable: a `Mock` subject has no `was_awaited`.

    A plain `Mock` keeps no `await_args_list`, and -- because a mock answers every
    attribute with a child mock -- an await assertion pointed at one would compare
    against that child and pass. Splitting the subject is what turns that from a
    runtime hazard into a line a checker refuses.
    """
    subject.was_awaited()  # expect-error
    subject.was_not_awaited()  # expect-error
    subject.was_awaited_once()  # expect-error
    subject.was_awaited_with("/a")  # expect-error
    subject.was_awaited_once_with("/a")  # expect-error
    subject.was_ever_awaited_with("/a")  # expect-error
    subject.was_never_awaited_with("/a")  # expect-error
    subject.has_await_count(1)  # expect-error
    subject.awaits  # expect-error
    subject.last_await()  # expect-error


def the_typed_route_refuses_it_too() -> None:
    """`as_=` is where the split is enforced, so it is where it is pinned."""
    expect(a_mock(), as_=MockExpect).was_awaited()  # expect-error
    expect(an_async_mock(), as_=MockExpect).was_awaited()  # expect-error: the subject was named


def the_async_subject_is_the_one_that_comes_back(subject: AsyncMockExpect) -> None:
    """A chain that widened to the base subject would lose the await catalogue."""
    assert_type(subject.was_awaited(), MockExpect)  # expect-error
    assert_type(subject.was_called(), MockExpect)  # expect-error: inherited, still `Self`
    assert_type(subject.has_await_count(1), Expect[Any])  # expect-error
    assert_type(subject.last_await(), Found[MockExpect, Any])  # expect-error
    assert_type(subject.awaits, SequenceExpect[str])  # expect-error: the elements are calls


def awaits_makes_no_claim_and_is_not_called(subject: AsyncMockExpect) -> None:
    """The same asymmetry as `calls`, for the same reason."""
    subject.awaits()  # expect-error: `awaits` is a property, not an assertion
    subject.last_await.which  # expect-error: `last_await()` -- it takes a `because`


def because_is_keyword_only_on_the_await_catalogue(subject: AsyncMockExpect) -> None:
    subject.was_awaited("R")  # expect-error: no positional parameters at all
    subject.was_not_awaited("R")  # expect-error
    subject.was_awaited_once("R")  # expect-error
    subject.has_await_count(1, "R")  # expect-error
    subject.last_await("R")  # expect-error


def an_await_count_is_a_count_or_a_constraint(subject: AsyncMockExpect) -> None:
    subject.has_await_count("3")  # expect-error: not a count
    subject.has_await_count(1.5)  # expect-error: an await count is a whole number
    subject.has_await_count(None)  # expect-error
    subject.has_await_count()  # expect-error: it is required
    subject.has_await_count(exactly=3)  # expect-error: positional-only


def unittest_mocks_own_await_vocabulary_is_not_on_the_subject(subject: AsyncMockExpect) -> None:
    """The same trap as the call side, and the same refusal."""
    subject.assert_awaited()  # expect-error
    subject.assert_awaited_once_with("/a")  # expect-error
    subject.assert_not_awaited()  # expect-error
    subject.was_awaited_once_wth("/a")  # expect-error: the textbook typo
    subject.was_ever_awaited("/a")  # expect-error: not a name this subject has
    subject.await_count  # expect-error: read it through `.subject`


def the_recorded_awaits_are_not_the_mock(subject: AsyncMockExpect) -> None:
    subject.awaits.was_awaited()  # expect-error
    subject.awaits.has_await_count(1)  # expect-error


def the_async_predicate_answers_a_bool_and_nothing_else() -> None:
    assert_type(is_async_mock(an_async_mock()), Any)  # expect-error
    is_async_mock()  # expect-error: it takes a value
    is_async_mock(a_mock(), a_mock())  # expect-error: one value
