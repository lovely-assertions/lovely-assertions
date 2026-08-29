"""The exception surface: ``CallableExpect``, ``RaisedExpect`` and ``expect_raises``.

Four claims are pinned here.

*The exception type asked for is the exception type handed back.* ``raises``
narrows through what it returns: the subject after it is the exception, typed as
the argument, so ``.subject.errno`` is checked rather than guessed.

*The continuations keep it.* ``.and_`` and ``.which`` are both ``Self`` here --
the subject already *is* what was found -- and every assertion returns the
subject it was called on, a user's own subclass included.

*``with_cause`` re-specialises.* Descending into the cause hands back a subject
typed as the cause, which is what makes ``with_cause(OSError).where(...)`` worth
writing.

*The context-manager form types its ``as`` binding.* ``expect_raises`` is declared
as a context manager over ``RaisedExpect[E]``; the handle's own class is an
implementation detail and never appears in a user's inferred types.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import assert_type

from lovely_assertions import Expect, Found
from lovely_assertions._callable import CallableExpect, RaisedExpect, expect_raises


def parse(text: str) -> int:
    return int(text)


# ---------------------------------------------------------------------------
# raises: the requested type is the new subject
# ---------------------------------------------------------------------------
def raises_narrows_to_the_requested_type() -> None:
    caught = CallableExpect(lambda: parse("x")).raises(ValueError)
    assert_type(caught, RaisedExpect[ValueError])
    assert_type(caught.subject, ValueError)


def raises_exactly_narrows_the_same_way() -> None:
    assert_type(CallableExpect(parse).raises_exactly(OSError), RaisedExpect[OSError])
    assert_type(CallableExpect(parse).raises_exactly(OSError).subject.errno, int | None)


def a_base_exception_is_a_valid_request() -> None:
    """The bound is ``BaseException``: ``SystemExit`` is a legitimate thing to expect."""
    assert_type(CallableExpect(parse).raises(SystemExit), RaisedExpect[SystemExit])
    assert_type(CallableExpect(parse).raises(SystemExit).subject.code, int | str | None)


def does_not_raise_returns_the_callable_subject() -> None:
    assert_type(CallableExpect(parse).does_not_raise(), CallableExpect)
    assert_type(CallableExpect(parse).does_not_raise(ValueError), CallableExpect)
    assert_type(CallableExpect(parse).subject, Callable[..., object])


# ---------------------------------------------------------------------------
# Continuations
# ---------------------------------------------------------------------------
def the_continuations_keep_the_exception(caught: RaisedExpect[ValueError]) -> None:
    assert_type(caught.and_, RaisedExpect[ValueError])
    assert_type(caught.which, RaisedExpect[ValueError])
    assert_type(caught.with_message("bad"), RaisedExpect[ValueError])
    assert_type(caught.with_message_containing("bad"), RaisedExpect[ValueError])
    assert_type(caught.where(lambda error: bool(error.args)), RaisedExpect[ValueError])


def the_generic_catalogue_still_applies(caught: RaisedExpect[ValueError]) -> None:
    """``RaisedExpect`` is an ``Expect``; nothing about the base subject is lost."""
    assert_type(caught.is_not_none(), Expect[ValueError])
    assert_type(caught.is_instance_of(OSError), Found[RaisedExpect[ValueError], OSError])
    assert_type(caught.is_instance_of(OSError).which, Expect[OSError])


def the_inspection_assertions_keep_the_exception(caught: RaisedExpect[ValueError]) -> None:
    """``matches`` and ``satisfies`` hand the subject to a callable of the user's.

    The handle ``expect_raises`` yields overrides both, so what they take and what
    they give back has to stay exactly what the base subject promised.
    """
    assert_type(caught.matches(lambda error: bool(error.args)), RaisedExpect[ValueError])
    assert_type(caught.satisfies(lambda error: error.args), RaisedExpect[ValueError])


def the_predicate_receives_the_narrowed_exception() -> None:
    CallableExpect(parse).raises(OSError).where(lambda error: error.errno == 2)


# ---------------------------------------------------------------------------
# with_cause re-specialises onto the cause
# ---------------------------------------------------------------------------
def with_cause_descends_into_the_cause(caught: RaisedExpect[ValueError]) -> None:
    assert_type(caught.with_cause(KeyError), RaisedExpect[KeyError])
    assert_type(caught.with_cause_exactly(OSError), RaisedExpect[OSError])
    assert_type(caught.with_cause(OSError).subject.errno, int | None)
    assert_type(caught.with_cause(OSError).with_message("denied"), RaisedExpect[OSError])


# ---------------------------------------------------------------------------
# The context-manager form
# ---------------------------------------------------------------------------
def expect_raises_types_its_binding() -> None:
    with expect_raises(ValueError) as caught:
        parse("x")
    assert_type(caught, RaisedExpect[ValueError])
    assert_type(caught.subject, ValueError)
    assert_type(caught.with_message_containing("invalid"), RaisedExpect[ValueError])


def expect_raises_is_a_context_manager_over_the_exception() -> None:
    assert_type(expect_raises(OSError), AbstractContextManager[RaisedExpect[OSError]])


# ---------------------------------------------------------------------------
# Extension: a subclass gets its own type back
# ---------------------------------------------------------------------------
class HttpError(RaisedExpect[OSError]):
    """A user's own exception subject, to pin what ``Self`` promises."""

    __slots__ = ()

    def with_errno(self, expected: int, /, *, because: str = "") -> "HttpError":
        if self.subject.errno == expected:
            return self
        return self._fail(f"to have errno {expected}", because)


def a_subclass_keeps_its_own_type(error: OSError) -> None:
    assert_type(HttpError(error).with_message("denied"), HttpError)
    assert_type(HttpError(error).which.with_errno(2), HttpError)
    assert_type(HttpError(error).where(lambda failure: failure.errno == 2), HttpError)
