"""Every marked line here must be rejected by pyright and mypy.

Without this half, `typing_tests/positive/exceptions.py` proves nothing: a subject
that had quietly collapsed to `Any` would satisfy every `assert_type` in it. These
are the mistakes the exception surface exists to catch -- asking for something that
is not an exception, losing the type the exception was narrowed to, and reaching
for the caught exception through the context manager instead of through its `as`
binding.
"""

from contextlib import AbstractContextManager
from typing import assert_type

from lovely_assertions._callable import CallableExpect, RaisedExpect, expect_raises


def parse(text: str) -> int:
    return int(text)


def a_pattern() -> object:
    """Stands in for a compiled pattern, which the substring form must refuse."""
    return object()


def the_subject_has_to_be_callable() -> None:
    CallableExpect(3)  # expect-error: a callable is the whole premise
    CallableExpect("parse")  # expect-error


def only_exception_types_can_be_raised() -> None:
    CallableExpect(parse).raises(int)  # expect-error: not a BaseException
    CallableExpect(parse).raises("ValueError")  # expect-error: a type, not its name
    CallableExpect(parse).raises(ValueError())  # expect-error: a type, not an instance
    CallableExpect(parse).raises_exactly(str)  # expect-error
    CallableExpect(parse).raises_exactly(ValueError())  # expect-error
    CallableExpect(parse).does_not_raise(int)  # expect-error
    CallableExpect(parse).does_not_raise(ValueError())  # expect-error


def a_tuple_of_types_is_a_pytest_habit() -> None:
    """``pytest.raises`` takes one; this does not, and the checker has to say so."""
    CallableExpect(parse).raises((ValueError, TypeError))  # expect-error
    expect_raises((ValueError, TypeError))  # expect-error


def the_entry_point_takes_an_exception_type_too() -> None:
    """``expect_raises`` is the primary form, so its own argument is worth pinning."""
    expect_raises(int)  # expect-error: not a BaseException
    expect_raises(ValueError())  # expect-error: a type, not an instance
    expect_raises(ValueError, "a reason")  # expect-error: `because` is keyword-only


def the_narrowed_type_is_the_one_asked_for() -> None:
    caught = CallableExpect(parse).raises(ValueError)
    assert_type(caught, RaisedExpect[TypeError])  # expect-error
    assert_type(caught.subject, TypeError)  # expect-error
    assert_type(caught.which, RaisedExpect[TypeError])  # expect-error
    does_not_raise = CallableExpect(parse).does_not_raise()
    assert_type(does_not_raise, RaisedExpect[ValueError])  # expect-error


def the_exception_keeps_its_own_attributes(failure: RaisedExpect[OSError]) -> None:
    CallableExpect(parse).raises(ValueError).where(lambda e: e.errno == 2)  # expect-error
    failure.where(lambda error: error.errno)  # expect-error: a predicate returns a bool


def arguments_keep_their_own_types(caught: RaisedExpect[ValueError]) -> None:
    caught.with_message(3)  # expect-error
    caught.with_message_containing(a_pattern())  # expect-error: a substring, not a pattern
    caught.with_cause(ValueError())  # expect-error: a type, not an instance
    caught.with_cause(int)  # expect-error: not a BaseException
    caught.does_not_raise()  # expect-error: the subject is the exception, not the call


def because_is_keyword_only() -> None:
    CallableExpect(parse).raises(ValueError, "a reason")  # expect-error: `because` is keyword-only
    CallableExpect(parse).does_not_raise(ValueError, "a reason")  # expect-error


def does_not_raise_takes_at_most_one_type() -> None:
    CallableExpect(parse).does_not_raise(ValueError, TypeError)  # expect-error


def the_context_manager_is_not_the_subject() -> None:
    """The exception exists only through the `as` binding, and only after the block."""
    expect_raises(ValueError).with_message("bad")  # expect-error
    expect_raises(ValueError).subject  # expect-error
    assert_type(expect_raises(ValueError), RaisedExpect[ValueError])  # expect-error


def the_binding_keeps_the_type_that_was_asked_for() -> None:
    with expect_raises(ValueError) as caught:
        parse("x")
    assert_type(caught, RaisedExpect[TypeError])  # expect-error
    manager = expect_raises(ValueError)
    assert_type(manager, AbstractContextManager[RaisedExpect[TypeError]])  # expect-error


def the_binding_carries_the_exception_through_the_block() -> None:
    """Not just its ``assert_type``: the attributes have to be the exception's own."""
    with expect_raises(ValueError) as caught:
        parse("x")
    caught.where(lambda error: error.errno == 2)  # expect-error: ValueError has no errno
    caught.with_cause(KeyError).subject.errno  # expect-error: nor does the cause
