"""The change surface: ``expect_change``, ``expect_no_change`` and their scopes.

Four claims are pinned here.

*The probe's return type decides which scope comes back.* A probe returning
something a difference can be taken of gets a ``NumericChange`` and is offered
``.by(...)``; everything else gets a plain ``Change``. That is the whole of what
the overload chain does, and it is the only place claim one is enforced for this
family -- the runtime builds one class either way, because the type of the value
is not knowable until the probe has been called.

*The delta type is not the value type.* Two instants differ by a duration, so a
``datetime`` probe takes a ``timedelta`` amount. Its own type would not compile.

*``bool`` is not offered an amount*, because a ``bool`` is an ``int`` and a flag
that went from ``False`` to ``True`` did not increase by one.

*``expect_no_change`` has neither continuation*, and that is a separate type
rather than a runtime refusal: a destination and an amount both narrow a claim
that something moved, and this one claims the opposite.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import TYPE_CHECKING, assert_type

from lovely_assertions import Change, NoChange, NumericChange, expect_change, expect_no_change

if TYPE_CHECKING:
    from collections.abc import Callable


def a_count() -> int:
    return 0


def a_ratio() -> float:
    return 0.0


def a_balance() -> Decimal:
    return Decimal(0)


def a_share() -> Fraction:
    return Fraction(0)


def an_instant() -> datetime:
    return datetime.now(tz=None)


def a_span() -> timedelta:
    return timedelta()


def a_state() -> str:
    return ""


def a_flag() -> bool:
    return False


def some_rows() -> list[int]:
    return []


# ---------------------------------------------------------------------------
# Which scope a probe gets
# ---------------------------------------------------------------------------
def a_subtractable_probe_gets_an_amount() -> None:
    assert_type(expect_change(a_count), NumericChange[int, int])
    assert_type(expect_change(a_ratio), NumericChange[float, float])
    assert_type(expect_change(a_balance), NumericChange[Decimal, Decimal])
    assert_type(expect_change(a_share), NumericChange[Fraction, Fraction])
    assert_type(expect_change(a_span), NumericChange[timedelta, timedelta])


def two_instants_differ_by_a_duration() -> None:
    """The one row whose delta type is not its value type."""
    assert_type(expect_change(an_instant), NumericChange[datetime, timedelta])
    assert_type(
        expect_change(an_instant).by(timedelta(hours=1)), NumericChange[datetime, timedelta]
    )


def everything_else_gets_the_plain_scope() -> None:
    assert_type(expect_change(a_state), Change[str])
    assert_type(expect_change(some_rows), Change[list[int]])


def a_flag_is_not_offered_an_amount() -> None:
    """``bool`` leads the chain, exactly as it leads the dispatch table."""
    assert_type(expect_change(a_flag), Change[bool])


def expect_no_change_has_its_own_scope() -> None:
    assert_type(expect_no_change(a_count), NoChange[int])
    assert_type(expect_no_change(a_state), NoChange[str])
    assert_type(expect_no_change(an_instant), NoChange[datetime])


# ---------------------------------------------------------------------------
# The continuations return the scope, so the chain does not widen
# ---------------------------------------------------------------------------
def the_continuations_hand_the_scope_back() -> None:
    assert_type(expect_change(a_count).by(1), NumericChange[int, int])
    assert_type(expect_change(a_count).to(4), NumericChange[int, int])
    assert_type(expect_change(a_state).to("shipped"), Change[str])
    assert_type(expect_change(a_count).by(1).to(4), NumericChange[int, int])


def because_is_keyword_only_and_accepted_on_both() -> None:
    assert_type(expect_change(a_count, because="R"), NumericChange[int, int])
    assert_type(expect_no_change(a_count, because="R"), NoChange[int])


# ---------------------------------------------------------------------------
# The scopes are context managers, and the block binds the scope
# ---------------------------------------------------------------------------
def the_block_binds_the_scope() -> None:
    with expect_change(a_count) as scope:
        assert_type(scope, NumericChange[int, int])
    with expect_no_change(a_state) as held:
        assert_type(held, NoChange[str])


def a_destination_takes_the_probe_s_own_type() -> None:
    """``.to`` is typed by what the probe returns, not by ``object``."""
    assert_type(expect_change(a_state).to("shipped"), Change[str])
    assert_type(expect_change(some_rows).to([1, 2]), Change[list[int]])


# ---------------------------------------------------------------------------
# A bound method and a lambda are both probes
# ---------------------------------------------------------------------------
def any_zero_argument_callable_is_a_probe() -> None:
    class Ledger:
        def size(self) -> int:
            return 0

    ledger = Ledger()
    assert_type(expect_change(ledger.size), NumericChange[int, int])

    rows = [1]
    lengths: Callable[[], int] = lambda: len(rows)  # noqa: E731  (a probe is a callable)
    assert_type(expect_change(lengths), NumericChange[int, int])
