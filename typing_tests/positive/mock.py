"""The mock surface: ``MockExpect``.

Four claims are pinned here.

*Every assertion hands back the subject it was called on.* ``MockExpect`` is an
``Expect[Any]``, so nothing about the generic catalogue is lost, and a chain
never widens to ``Expect[Any]`` half-way through -- including for a user's own
subclass, which gets its own type back rather than the base one.

*The subject is ``Any``, deliberately.* A mock stands in for something, and
typing it as that something would be a claim about the stand-in's stand-in.
``.subject`` is ``Any``, and so is everything read off it.

*The two continuations have different shapes because they answer different
questions.* ``calls`` is a ``SequenceExpect[Any]`` over the recorded calls;
``last_call()`` is a ``Found``, so ``.and_`` returns to the mock and ``.which``
descends into the call.

*``has_call_count`` takes a count or an occurrence constraint* -- one signature,
both spellings, and ``int`` is not silently widened to something a constraint
would satisfy.
"""

from collections.abc import Sequence
from typing import Any, assert_type
from unittest.mock import Mock

from lovely_assertions import EnumExpect, Expect, Found, SequenceExpect
from lovely_assertions._mock import MockExpect, is_mock
from lovely_assertions._occurrence import Occurrence, at_least, exactly, once


def a_mock() -> Mock:
    return Mock()


# ---------------------------------------------------------------------------
# Every assertion returns the subject
# ---------------------------------------------------------------------------
def the_counting_assertions_return_the_subject(subject: MockExpect) -> None:
    assert_type(subject.was_called(), MockExpect)
    assert_type(subject.was_not_called(), MockExpect)
    assert_type(subject.was_called_once(), MockExpect)
    assert_type(subject.has_call_count(3), MockExpect)


def the_argument_assertions_return_the_subject(subject: MockExpect) -> None:
    assert_type(subject.was_called_with("/a", timeout=3), MockExpect)
    assert_type(subject.was_called_once_with("/a"), MockExpect)
    assert_type(subject.was_ever_called_with("/a"), MockExpect)
    assert_type(subject.was_never_called_with("/a"), MockExpect)


def a_chain_never_widens(subject: MockExpect) -> None:
    assert_type(subject.was_called().and_.was_called_once(), MockExpect)


def because_is_accepted_everywhere(subject: MockExpect) -> None:
    """``because`` is keyword-only, which is how it sits between ``*args`` and ``**kwargs``."""
    assert_type(subject.was_called(because="R"), MockExpect)
    assert_type(subject.was_called_with("/a", because="R"), MockExpect)
    assert_type(subject.was_called_once_with("/a", because="R"), MockExpect)
    assert_type(subject.was_ever_called_with("/a", because="R"), MockExpect)
    assert_type(subject.was_never_called_with("/a", because="R"), MockExpect)
    assert_type(subject.has_call_count(1, because="R"), MockExpect)
    assert_type(subject.last_call(because="R"), Found[MockExpect, Any])


# ---------------------------------------------------------------------------
# The subject
# ---------------------------------------------------------------------------
def the_subject_is_any(subject: MockExpect) -> None:
    assert_type(subject.subject, Any)
    assert_type(subject.subject.call_args_list, Any)


def the_generic_catalogue_still_applies(subject: MockExpect) -> None:
    """``MockExpect`` is an ``Expect``; nothing about the base subject is lost.

    ``.which`` says ``EnumExpect[Mock]``, which is nonsense, and it is the same
    nonsense ``expect(mock)`` produces: typeshed gives ``NonCallableMock`` an
    ``Any`` in its MRO, so a mock is assignable to everything and whichever
    concrete overload comes first claims it. No overload can be written that
    reaches a mock honestly, so the answer is pinned here rather than hidden and
    a change to it has to be a decision. The runtime builds a ``MockExpect``.
    """
    assert_type(subject.is_not_none(), Expect[Any])
    assert_type(subject.is_instance_of(Mock), Found[MockExpect, Mock, EnumExpect[Mock]])
    assert_type(subject.is_instance_of(Mock).which, EnumExpect[Mock])
    assert_type(subject.satisfies(lambda value: value), MockExpect)
    assert_type(subject.described_as("the client"), MockExpect)


def the_constructor_takes_anything(subject: MockExpect) -> None:
    """A mock is not a type the checker can name, so the subject is unconstrained."""
    assert_type(MockExpect(a_mock()), MockExpect)
    assert_type(MockExpect(object()), MockExpect)
    _ = subject


# ---------------------------------------------------------------------------
# Continuations
# ---------------------------------------------------------------------------
def calls_is_a_sequence_subject(subject: MockExpect) -> None:
    assert_type(subject.calls, SequenceExpect[Any])
    assert_type(subject.calls.has_length(2), SequenceExpect[Any])
    assert_type(subject.calls.subject, Sequence[Any])


def last_call_is_a_finder(subject: MockExpect) -> None:
    assert_type(subject.last_call(), Found[MockExpect, Any])
    assert_type(subject.last_call().and_, MockExpect)
    assert_type(subject.last_call().which, Expect[Any])
    assert_type(subject.last_call().subject, Any)


# ---------------------------------------------------------------------------
# has_call_count takes either spelling
# ---------------------------------------------------------------------------
def a_count_or_a_constraint(subject: MockExpect) -> None:
    assert_type(subject.has_call_count(3), MockExpect)
    assert_type(subject.has_call_count(exactly(3)), MockExpect)
    assert_type(subject.has_call_count(at_least(2)), MockExpect)
    assert_type(subject.has_call_count(once), MockExpect)


def a_user_written_constraint_is_accepted(subject: MockExpect) -> None:
    """``Occurrence`` is structural, so a caller's own constraint fits with nothing registered."""

    class Between:
        __slots__ = ("_high", "_low")

        def __init__(self, low: int, high: int) -> None:
            self._low, self._high = low, high

        def allows(self, count: int, /) -> bool:
            return self._low <= count <= self._high

        def describe(self) -> str:
            return "between " + str(self._low) + " and " + str(self._high) + " times"

    constraint: Occurrence = Between(1, 3)
    assert_type(subject.has_call_count(constraint), MockExpect)
    assert_type(subject.has_call_count(Between(1, 3)), MockExpect)


# ---------------------------------------------------------------------------
# The dispatch predicate
# ---------------------------------------------------------------------------
def the_predicate_takes_anything_and_answers_a_bool() -> None:
    assert_type(is_mock(a_mock()), bool)
    assert_type(is_mock(3), bool)
    assert_type(is_mock(None), bool)


# ---------------------------------------------------------------------------
# A user's own subject keeps its own type
# ---------------------------------------------------------------------------
class RepositoryExpect(MockExpect):
    """A domain subject built on the mock one: the ordinary shape of an extension."""

    __slots__ = ()

    def saved_once(self, *, because: str = "") -> "RepositoryExpect":
        return self.was_called_once(because=because)


def a_subclass_gets_itself_back(repository: RepositoryExpect) -> None:
    assert_type(repository.was_called(), RepositoryExpect)
    assert_type(repository.saved_once(), RepositoryExpect)
    assert_type(repository.was_called().and_.saved_once(), RepositoryExpect)
    assert_type(repository.last_call(), Found[RepositoryExpect, Any])
    assert_type(repository.last_call().and_, RepositoryExpect)
