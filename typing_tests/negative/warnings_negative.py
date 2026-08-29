"""Every marked line here must be rejected by pyright and mypy.

Without this half, `typing_tests/positive/warning_subject.py` proves nothing: a subject
that had quietly collapsed to `Any` would satisfy every `assert_type` in it. These
are the mistakes the warning surface exists to catch -- asking for something that
is not a warning, forgetting that the subject is a *tuple* of them, reaching for
the capture through the context manager instead of through its `as` binding, and
the two habits carried over from `pytest.warns`: a tuple of categories, and a
positional argument where this library takes a keyword.

This one keeps its name: `warnings_negative` shadows nothing. Its positive
counterpart cannot, and says why at the top of
`typing_tests/positive/warning_subject.py`.
"""

from contextlib import AbstractContextManager
from typing import assert_type

from lovely_assertions import exactly
from lovely_assertions._callable import CallableExpect
from lovely_assertions._warnings import WarnedExpect, expect_warns


class Removed(DeprecationWarning):
    version: str


def legacy() -> None: ...


def a_pattern() -> object:
    """Stands in for a compiled pattern, which the substring form must refuse."""
    return object()


def only_warning_types_can_be_expected() -> None:
    CallableExpect(legacy).warns(int)  # expect-error: not a Warning
    CallableExpect(legacy).warns("UserWarning")  # expect-error: a type, not its name
    CallableExpect(legacy).warns(UserWarning())  # expect-error: a type, not an instance
    CallableExpect(legacy).warns(ValueError)  # expect-error: an exception is not a warning
    CallableExpect(legacy).does_not_warn(int)  # expect-error
    CallableExpect(legacy).does_not_warn(UserWarning())  # expect-error


def a_tuple_of_categories_is_a_pytest_habit() -> None:
    """``pytest.warns`` takes one; this does not, and the checker has to say so."""
    CallableExpect(legacy).warns((UserWarning, DeprecationWarning))  # expect-error
    expect_warns((UserWarning, DeprecationWarning))  # expect-error


def the_entry_point_takes_a_warning_type_too() -> None:
    expect_warns(int)  # expect-error: not a Warning
    expect_warns(UserWarning())  # expect-error: a type, not an instance
    expect_warns(UserWarning, "a reason")  # expect-error: `because` is keyword-only
    expect_warns(UserWarning, exactly(2))  # expect-error: `occurrences` is keyword-only


def because_and_occurrences_are_keyword_only() -> None:
    CallableExpect(legacy).warns(UserWarning, exactly(2))  # expect-error
    CallableExpect(legacy).warns(UserWarning, "a reason")  # expect-error
    CallableExpect(legacy).does_not_warn(UserWarning, "a reason")  # expect-error


def does_not_warn_takes_at_most_one_category() -> None:
    CallableExpect(legacy).does_not_warn(UserWarning, DeprecationWarning)  # expect-error


def the_narrowed_type_is_the_one_asked_for() -> None:
    warned = CallableExpect(legacy).warns(Removed)
    assert_type(warned, WarnedExpect[UserWarning])  # expect-error
    assert_type(warned.subject, tuple[UserWarning, ...])  # expect-error
    assert_type(warned.which, WarnedExpect[UserWarning])  # expect-error


def the_subject_is_a_tuple_and_not_one_warning() -> None:
    """The one shape difference from the exception family, so it gets its own probe."""
    warned = CallableExpect(legacy).warns(Removed)
    assert_type(warned.subject, Removed)  # expect-error
    warned.subject.version  # expect-error: a tuple has no `version`


def the_warning_keeps_its_own_attributes(warned: WarnedExpect[UserWarning]) -> None:
    CallableExpect(legacy).warns(UserWarning).where(lambda w: w.version == "3")  # expect-error
    warned.where(lambda warning: warning.args)  # expect-error: a predicate returns a bool


def arguments_keep_their_own_types(warned: WarnedExpect[Removed]) -> None:
    warned.with_message(3)  # expect-error
    warned.with_message_containing(a_pattern())  # expect-error: a substring, not a pattern
    warned.with_message_containing(3)  # expect-error
    warned.does_not_warn()  # expect-error: the subject is the capture, not the call


def the_context_manager_is_not_the_subject() -> None:
    """The capture exists only through the `as` binding, and only after the block."""
    expect_warns(UserWarning).with_message("gone")  # expect-error
    expect_warns(UserWarning).subject  # expect-error
    assert_type(expect_warns(UserWarning), WarnedExpect[UserWarning])  # expect-error


def the_binding_keeps_the_category_that_was_asked_for() -> None:
    with expect_warns(Removed) as warned:
        legacy()
    assert_type(warned, WarnedExpect[UserWarning])  # expect-error
    manager = expect_warns(Removed)
    assert_type(manager, AbstractContextManager[WarnedExpect[UserWarning]])  # expect-error


def the_binding_carries_the_warnings_through_the_block() -> None:
    """Not just its ``assert_type``: the attributes have to be the warnings' own."""
    with expect_warns(UserWarning) as warned:
        legacy()
    warned.where(lambda warning: warning.version == "3")  # expect-error: no `version`
    warned.subject[0].version  # expect-error: nor on the captured warning
