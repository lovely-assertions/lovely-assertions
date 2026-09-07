"""Every marked line here must be rejected by pyright and mypy.

Without this half, `typing_tests/positive/change.py` proves nothing. And for this
family it carries more weight than usual: the runtime builds one scope class
whatever the probe returns, because the type of the value is not knowable until
the probe has been called. So the refusals below are the *only* place the
distinction between a scope that has `.by(...)` and one that does not is
enforced at all.

Three sections, one per way this surface can be got wrong: handing it a value
instead of a probe, asking a non-subtractable probe how far it moved, and asking
`expect_no_change` a question that contradicts what it asserts.
"""

from datetime import datetime, timedelta
from typing import assert_type

from lovely_assertions import Change, NoChange, NumericChange, expect_change, expect_no_change


def a_count() -> int:
    return 0


def a_state() -> str:
    return ""


def a_flag() -> bool:
    return False


def an_instant() -> datetime:
    return datetime.now(tz=None)


# ---------------------------------------------------------------------------
# The probe is a callable, not a value
# ---------------------------------------------------------------------------
def a_value_is_not_a_probe() -> None:
    """Sampled once, a value could never move. The whole family depends on this."""
    total = 3
    expect_change(total)  # expect-error
    expect_no_change(total)  # expect-error
    expect_change("pending")  # expect-error
    expect_change(a_count())  # expect-error: called, so this is an int


def a_probe_takes_no_arguments() -> None:
    """It is called twice, by this library, with nothing to pass it."""

    def needs_one(key: str) -> int:
        return len(key)

    expect_change(needs_one)  # expect-error


# ---------------------------------------------------------------------------
# `.by(...)` is offered only where a difference can be taken
# ---------------------------------------------------------------------------
def a_string_probe_has_no_amount(scope: Change[str]) -> None:
    """Claim one for this family: the catalogue offered is the one that applies."""
    scope.by(1)  # expect-error
    expect_change(a_state).by(1)  # expect-error


def a_flag_has_no_amount() -> None:
    """`bool` leads the overload chain precisely so this is refused."""
    expect_change(a_flag).by(1)  # expect-error


def an_amount_is_the_delta_type_not_the_value_type() -> None:
    """Two instants differ by a duration, so a `datetime` amount is wrong."""
    expect_change(an_instant).by(datetime(2024, 1, 1))  # expect-error
    expect_change(an_instant).by(1)  # expect-error


def an_amount_is_not_any_number(scope: NumericChange[int, int]) -> None:
    scope.by("1")  # expect-error
    scope.by(None)  # expect-error
    scope.by()  # expect-error: it is required
    scope.by(amount=1)  # expect-error: positional-only


# ---------------------------------------------------------------------------
# A destination is the probe's own type
# ---------------------------------------------------------------------------
def a_destination_is_checked_against_the_probe(scope: Change[str]) -> None:
    scope.to(3)  # expect-error
    expect_change(a_count).to("four")  # expect-error


# ---------------------------------------------------------------------------
# `expect_no_change` narrows nothing
# ---------------------------------------------------------------------------
def the_held_scope_has_neither_continuation(scope: NoChange[int]) -> None:
    """A destination and an amount both narrow "it moved"; this claims it did not."""
    scope.to(4)  # expect-error
    scope.by(1)  # expect-error
    expect_no_change(a_count).by(1)  # expect-error
    expect_no_change(a_count).to(4)  # expect-error


# ---------------------------------------------------------------------------
# The scopes that come back are the ones that come back
# ---------------------------------------------------------------------------
def the_scope_is_not_widened(scope: NumericChange[int, int]) -> None:
    assert_type(scope.by(1), Change[int])  # expect-error
    assert_type(expect_change(a_count), Change[int])  # expect-error
    assert_type(expect_no_change(a_count), Change[int])  # expect-error
    assert_type(expect_change(an_instant), NumericChange[datetime, datetime])  # expect-error


def because_is_keyword_only() -> None:
    expect_change(a_count, "R")  # expect-error
    expect_no_change(a_count, "R")  # expect-error


def a_scope_is_not_a_subject(scope: NumericChange[int, int]) -> None:
    """It has no assertions of its own: the block is the assertion."""
    scope.is_equal_to(3)  # expect-error
    scope.subject  # expect-error
    scope.described_as("the count")  # expect-error


def the_amount_type_is_not_free(scope: NumericChange[timedelta, timedelta]) -> None:
    scope.by(3)  # expect-error: a duration, not a number
