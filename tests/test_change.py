"""``expect_change`` and ``expect_no_change`` -- assertions about what an action did.

Three things are pinned here, in this order of importance.

*The two failures the hand-written form cannot separate stay separated.* An
action that did nothing and an action that did the wrong amount both come back
from ``expect(count() - before).is_equal_to(1)`` as one sentence about a number.
Here each has its own, and each is pinned byte for byte -- including the *before*
value, which is the thing the subtraction throws away before the assertion ever
sees it.

*Neither trap this family has is left for the reader.* A probe that hands back the
same mutable object twice can observe nothing at all, and used to be reported as
"it stayed at ['widget']" -- naming the changed value while denying it changed. A
scope built and never entered asserts nothing while reading as a finished
sentence. Both are refused, and both refusals are exercised.

*The block is the assertion, so the block is what is measured.* Sampling happens
in ``__enter__`` and ``__exit__`` and nowhere else; an exception on its way out of
the block is the finding and is never buried under a second one.
"""

import warnings
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, cast

import pytest

from lovely_assertions import (
    AssertionFailure,
    expect,
    expect_change,
    expect_no_change,
    soft_assertions,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class Counter:
    """A value the blocks below can watch move."""

    __slots__ = ("total",)

    def __init__(self, total: int = 0) -> None:
        self.total = total

    def read(self) -> int:
        return self.total


def _message(callback: "Callable[[], object]") -> str:
    """The text of the failure ``callback`` produces."""
    with pytest.raises(AssertionFailure) as caught:
        callback()
    return str(caught.value)


# ---------------------------------------------------------------------------
# Why this module exists
# ---------------------------------------------------------------------------
def test_the_two_failures_the_hand_written_form_cannot_tell_apart() -> None:
    """The claim in the module docstring, checked rather than asserted in prose.

    Subtracting first throws the *before* value away, and gives an action that did
    nothing and an action that did too much the same sentence about one number.
    """
    counter = Counter(3)
    before = counter.read()
    by_hand = _message(lambda: expect(counter.read() - before).is_equal_to(1))
    assert by_hand == "Expected counter.read() - before to equal 1, but was 0."

    did_nothing = _message(_a_block_that_does_nothing)
    did_too_much = _message(_a_block_that_moves_two)

    assert did_nothing == ("Expected counter.read to increase by 1, but it did not move from 3.")
    assert did_too_much == (
        "Expected counter.read to increase by 1, but it went from 3 to 5 (a change of 2)."
    )
    assert did_nothing != did_too_much


def _a_block_that_does_nothing() -> None:
    counter = Counter(3)
    with expect_change(counter.read).by(1):
        pass


def _a_block_that_moves_two() -> None:
    counter = Counter(3)
    with expect_change(counter.read).by(1):
        counter.total += 2


# ---------------------------------------------------------------------------
# The plain claim: it moved
# ---------------------------------------------------------------------------
def test_a_value_that_moves_passes() -> None:
    counter = Counter(3)
    with expect_change(counter.read):
        counter.total += 1


def test_a_value_that_does_not_move_is_reported() -> None:
    counter = Counter(3)

    def run() -> None:
        with expect_change(counter.read):
            pass

    assert _message(run) == "Expected counter.read to change, but it did not move from 3."


def test_the_direction_does_not_matter_to_the_plain_claim() -> None:
    counter = Counter(3)
    with expect_change(counter.read):
        counter.total -= 1


# ---------------------------------------------------------------------------
# expect_no_change
# ---------------------------------------------------------------------------
def test_a_value_that_holds_still_passes() -> None:
    counter = Counter(3)
    with expect_no_change(counter.read):
        pass


def test_a_value_that_moves_is_reported_with_both_ends() -> None:
    counter = Counter(3)

    def run() -> None:
        with expect_no_change(counter.read):
            counter.total += 1

    assert _message(run) == "Expected counter.read not to change, but it went from 3 to 4."


def test_because_attaches_to_the_sentence() -> None:
    counter = Counter(3)

    def run() -> None:
        with expect_no_change(counter.read, because="a retry must not double-count"):
            counter.total += 1

    assert _message(run) == (
        "Expected counter.read not to change, but it went from 3 to 4"
        " because a retry must not double-count."
    )


# ---------------------------------------------------------------------------
# .to(...) -- where it landed
# ---------------------------------------------------------------------------
def test_a_value_that_lands_where_it_was_asked_to_passes() -> None:
    order = {"state": "pending"}
    with expect_change(lambda: order["state"]).to("shipped"):
        order["state"] = "shipped"


def test_a_value_that_never_moved_fails_its_destination() -> None:
    """The case a destination alone would miss: it already looked right."""
    order = {"state": "pending"}

    def run() -> None:
        with expect_change(lambda: order["state"]).to("shipped"):
            pass

    assert _message(run) == (
        "Expected lambda: order[\"state\"] to change to 'shipped',"
        " but it did not move from 'pending'."
    )


def test_a_value_that_lands_somewhere_else_says_where() -> None:
    order = {"state": "pending"}

    def run() -> None:
        with expect_change(lambda: order["state"]).to("shipped"):
            order["state"] = "cancelled"

    assert _message(run) == (
        "Expected lambda: order[\"state\"] to change to 'shipped',"
        " but it went from 'pending' to 'cancelled'."
    )


def test_a_destination_of_none_is_a_destination() -> None:
    """``None`` is a value a probe can return, so it cannot double as "no claim"."""
    holder: dict[str, object] = {"token": "abc"}
    with expect_change(lambda: holder["token"]).to(None):
        holder["token"] = None


# ---------------------------------------------------------------------------
# .by(...) -- how far
# ---------------------------------------------------------------------------
def test_an_exact_amount_passes() -> None:
    counter = Counter(3)
    with expect_change(counter.read).by(1):
        counter.total += 1


def test_a_negative_amount_reads_as_a_decrease() -> None:
    counter = Counter(3)
    with expect_change(counter.read).by(-1):
        counter.total -= 1

    def run() -> None:
        moved = Counter(3)
        with expect_change(moved.read).by(-1):
            moved.total += 1

    assert _message(run) == (
        "Expected moved.read to decrease by 1, but it went from 3 to 4 (a change of 1)."
    )


def test_an_amount_of_zero_reads_neutrally() -> None:
    """Not refused -- ``expect_no_change`` says it better, but it is a true claim."""
    counter = Counter(3)

    def run() -> None:
        with expect_change(counter.read).by(0):
            counter.total += 1

    assert _message(run) == (
        "Expected counter.read to change by 0, but it went from 3 to 4 (a change of 1)."
    )


def test_a_decimal_probe_gets_an_amount() -> None:
    """The case the money example needs, and the reason the overloads are not int-only."""
    balance = [Decimal("10.00")]
    with expect_change(lambda: balance[0]).by(Decimal("5.00")):
        balance[0] += Decimal("5.00")


def test_two_instants_differ_by_a_duration() -> None:
    """The row whose delta type is not its value type."""
    clock = [datetime(2024, 1, 1, tzinfo=UTC)]
    with expect_change(lambda: clock[0]).by(timedelta(hours=1)):
        clock[0] += timedelta(hours=1)


def test_by_over_values_that_do_not_subtract_is_a_misuse_not_a_failure() -> None:
    """A caller who went around the overloads gets a ``TypeError``, not a verdict.

    Reporting it as a failed assertion would be a lie about the subject: the value
    may have changed exactly as the test intended, and nothing about it is wrong.
    """
    words = ["a"]
    # The shape a caller reaches this with: a probe whose annotation says `int`,
    # so the overloads offer `.by`, and which returns a `str`. The cast is the
    # lie, written out rather than hidden behind `Any` so the test says which
    # mistake it is reproducing.
    probe = cast("Callable[[], int]", lambda: words[0])

    with (
        pytest.raises(TypeError, match="needs two samples that subtract"),
        expect_change(probe).by(1),
    ):
        words[0] = "b"


# ---------------------------------------------------------------------------
# The probe that can observe nothing
# ---------------------------------------------------------------------------
def test_a_probe_returning_one_mutable_object_is_refused() -> None:
    """The defect that used to read as a bug in this library rather than in the test."""
    items: list[str] = []

    def run() -> None:
        with expect_change(lambda: items):
            items.append("widget")

    assert _message(run) == (
        "Expected lambda: items to change, but the probe returned the same list both times,"
        " so nothing could be observed -- sample a value instead,"
        " as in lambda: list(...) or lambda: len(...)."
    )


def test_the_same_refusal_reaches_expect_no_change() -> None:
    """Refused there too, and that is the sharper half.

    ``expect_no_change`` over one mutable object is not passing because nothing
    happened; it is passing because it looked at one object twice. An assertion
    that cannot fail is the thing this library exists to refuse.
    """
    rows: dict[str, int] = {}

    def run() -> None:
        with expect_no_change(lambda: rows):
            rows["a"] = 1

    assert "the probe returned the same dict both times" in _message(run)


def test_sampling_a_copy_is_what_the_message_asks_for() -> None:
    """The fix the message names, exercised so it cannot stop working."""
    items: list[str] = []
    with expect_change(lambda: list(items)):
        items.append("widget")

    lengths: list[str] = []
    with expect_change(lambda: len(lengths)).by(1):
        lengths.append("widget")


def test_an_immutable_value_read_twice_is_not_mistaken_for_it() -> None:
    """Identity alone would refuse these: a small int and an interned string.

    Hashability is what separates "one object because it cannot be copied" from
    "one object because it was mutated in place".
    """
    counter = Counter(3)
    with expect_no_change(counter.read):
        pass

    word = ["hello"]
    with expect_no_change(lambda: word[0]):
        pass

    frozen = [frozenset({1})]
    with expect_no_change(lambda: frozen[0]):
        pass


# ---------------------------------------------------------------------------
# The scope nobody entered
# ---------------------------------------------------------------------------
def test_a_scope_built_and_never_entered_warns() -> None:
    """It asserts nothing, and unlike the other half-chain it reads as finished."""
    counter = Counter(3)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        expect_change(counter.read).by(1)
        import gc

        gc.collect()

    assert any(
        issubclass(one.category, RuntimeWarning) and "asserted nothing" in str(one.message)
        for one in caught
    ), [str(one.message) for one in caught]


def test_a_scope_that_was_entered_does_not_warn() -> None:
    counter = Counter(3)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with expect_change(counter.read):
            counter.total += 1
        import gc

        gc.collect()

    assert not [one for one in caught if "asserted nothing" in str(one.message)]


# ---------------------------------------------------------------------------
# Everything cross-cutting, which the family gets for free
# ---------------------------------------------------------------------------
def test_an_exception_out_of_the_block_is_the_finding() -> None:
    """Reporting a second failure on top would bury the first, and be about nothing."""
    counter = Counter(3)

    with pytest.raises(ZeroDivisionError), expect_change(counter.read).by(1):
        _ = 1 // 0


def test_a_soft_scope_collects_these_like_any_other() -> None:
    first = Counter(3)
    second = Counter(7)

    with soft_assertions() as scope:
        with expect_change(first.read).by(1):
            pass
        with expect_no_change(second.read):
            second.total += 1
        collected = scope.discard()

    assert collected == [
        "Expected first.read to increase by 1, but it did not move from 3.",
        "Expected second.read not to change, but it went from 7 to 8.",
    ]


def test_the_name_is_recovered_from_the_with_header() -> None:
    """The header is a different statement from the body for naming purposes.

    Every assertion in the body would otherwise be a candidate subject, the
    answer would be ambiguous, and the sentence would fall back to "the value".
    """
    counter = Counter(3)

    def run() -> None:
        with expect_change(counter.read):
            expect(1).is_equal_to(1)
            expect("a").is_equal_to("a")

    assert _message(run).startswith("Expected counter.read to change")


def test_an_explicit_probe_expression_is_named_as_written() -> None:
    balances = {"eur": 10}

    def run() -> None:
        with expect_change(lambda: balances["eur"]).by(5):
            pass

    assert _message(run).startswith('Expected lambda: balances["eur"] to increase by 5')
