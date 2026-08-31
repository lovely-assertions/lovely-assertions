"""``is_equivalent_to`` as an assertion, not as an engine.

``tests/test_equivalence.py`` and ``tests/test_equivalence_torture.py`` cover
``compare`` exhaustively. Neither touches the two methods on ``Expect[T]`` that a
user actually calls, so every one of them would pass against an
``is_equivalent_to`` short-circuited to ``return self``. This file is the seam:
that the assertion consults the engine, passes the options through, puts the
difference block in the message, and behaves like every other assertion.
"""

import random
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, cast

import pytest

from conftest import measured
from lovely_assertions import (
    AssertionFailure,
    Equivalency,
    Expect,
    close_within,
    equivalency,
    expect,
    soft_assertions,
)
from lovely_assertions._equivalence import _budget, _leftovers

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class Address:
    city: str
    postcode: str


@dataclass
class User:
    identifier: int
    name: str
    address: Address


def _message(callback: object) -> str:
    with pytest.raises(AssertionFailure) as caught:
        callback()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]
    return str(caught.value)


# ---------------------------------------------------------------------------
# The assertion consults the engine at all
# ---------------------------------------------------------------------------
def test_equivalent_graphs_pass_and_chain() -> None:
    subject = expect(Address("paris", "75001"))
    assert subject.is_equivalent_to(Address("paris", "75001")) is subject


def test_a_difference_fails() -> None:
    """The mutant this file exists for: short-circuiting to ``return self``."""
    address = Address("lyon", "75001")
    with pytest.raises(AssertionFailure):
        expect(address).is_equivalent_to(Address("paris", "75001"))


def test_the_message_carries_the_difference_block() -> None:
    address = Address("lyon", "75001")
    message = _message(lambda: expect(address).is_equivalent_to(Address("paris", "75001")))
    first_line, _, block = message.partition("\n")
    assert first_line.startswith("Expected address to be equivalent to Address(")
    assert "city: 'lyon' instead of 'paris'" in block


def test_every_difference_is_reported_at_once() -> None:
    """Every difference in the graph arrives from one ``_fail`` call, not one per member.

    A per-member failure would make the reader take a wrong graph apart one run
    at a time, which is what makes reporting the whole of it worth having.
    """
    user = User(2, "bob", Address("lyon", "75002"))
    message = _message(
        lambda: expect(user).is_equivalent_to(User(1, "ada", Address("paris", "75001")))
    )
    assert "identifier: 2 instead of 1" in message
    assert "name: 'bob' instead of 'ada'" in message
    assert "address.city: 'lyon' instead of 'paris'" in message
    assert "address.postcode: '75002' instead of '75001'" in message


def test_the_effective_configuration_is_printed() -> None:
    """A reader who excluded the wrong member has to be able to see that."""
    address = Address("lyon", "75001")
    message = _message(lambda: expect(address).is_equivalent_to(Address("paris", "75001")))
    assert "compared with strict ordering" in message


# ---------------------------------------------------------------------------
# Options actually reach the engine
# ---------------------------------------------------------------------------
def test_excluding_reaches_the_engine() -> None:
    user = User(2, "ada", Address("paris", "75001"))
    expect(user).is_equivalent_to(
        User(1, "ada", Address("paris", "75001")), options=equivalency().excluding("identifier")
    )


def test_ignoring_order_reaches_the_engine() -> None:
    items = [2, 1]
    with pytest.raises(AssertionFailure):
        expect(items).is_equivalent_to([1, 2])
    expect(items).is_equivalent_to([1, 2], options=equivalency().ignoring_order())


def test_excluding_path_reaches_the_engine() -> None:
    user = User(1, "ada", Address("lyon", "75001"))
    expect(user).is_equivalent_to(
        User(1, "ada", Address("paris", "75001")),
        options=equivalency().excluding_path("address.city"),
    )


def test_a_path_from_a_message_is_one_excluding_path_accepts() -> None:
    """The round trip is a contract: what is printed can be pasted back."""
    user = User(1, "ada", Address("lyon", "75001"))
    expected = User(1, "ada", Address("paris", "75001"))
    message = _message(lambda: expect(user).is_equivalent_to(expected))
    path = next(line.split(":")[0].strip() for line in message.splitlines() if "instead of" in line)
    expect(user).is_equivalent_to(expected, options=equivalency().excluding_path(path))


def test_a_comparator_reaches_the_engine() -> None:
    readings = [1.0000001]
    with pytest.raises(AssertionFailure):
        expect(readings).is_equivalent_to([1.0])
    expect(readings).is_equivalent_to(
        [1.0], options=equivalency().using(float, close_within(0.001))
    )


def test_the_configuration_reported_is_the_one_that_was_used() -> None:
    items = [2, 1, 9]
    message = _message(
        lambda: expect(items).is_equivalent_to([1, 2], options=equivalency().ignoring_order())
    )
    assert "order ignored" in message


# ---------------------------------------------------------------------------
# is_not_equivalent_to
# ---------------------------------------------------------------------------
def test_is_not_equivalent_to_passes_on_a_difference() -> None:
    subject = expect(Address("lyon", "75001"))
    assert subject.is_not_equivalent_to(Address("paris", "75001")) is subject


def test_is_not_equivalent_to_fails_when_they_match() -> None:
    address = Address("paris", "75001")
    message = _message(lambda: expect(address).is_not_equivalent_to(Address("paris", "75001")))
    assert message.startswith("Expected address not to be equivalent to Address(")


def test_is_not_equivalent_to_takes_the_same_options() -> None:
    """Asserting two payloads differ *once the volatile fields are out* needs them."""
    user = User(2, "ada", Address("paris", "75001"))
    only_the_id = equivalency().excluding("identifier")
    expect(user).is_not_equivalent_to(
        User(1, "bob", Address("paris", "75001")), options=only_the_id
    )
    with pytest.raises(AssertionFailure):
        expect(user).is_not_equivalent_to(
            User(1, "ada", Address("paris", "75001")), options=only_the_id
        )


# ---------------------------------------------------------------------------
# It behaves like every other assertion
# ---------------------------------------------------------------------------
def test_it_takes_a_reason() -> None:
    address = Address("lyon", "75001")
    message = _message(
        lambda: expect(address).is_equivalent_to(Address("paris", "75001"), because="the sync ran")
    )
    assert message.partition("\n")[0].endswith("because the sync ran.")


def test_it_reports_into_a_soft_scope() -> None:
    with soft_assertions("payload") as scope:
        address = Address("lyon", "75001")
        expect(address).is_equivalent_to(Address("paris", "75001"))
        collected = scope.discard()
    assert len(collected) == 1
    assert collected[0].startswith("Expected payload/address to be equivalent to")


def test_it_is_available_on_every_subject() -> None:
    """It lives on ``Expect[T]``, so a list and a mapping get it too."""
    expect([1, 2]).is_equivalent_to([1, 2])
    expect({"a": 1}).is_equivalent_to({"a": 1})
    expect("abc").is_equivalent_to("abc")
    assert hasattr(Expect(1), "is_equivalent_to")


def test_a_passing_equivalence_still_returns_the_concrete_subject() -> None:
    assert expect([1, 2]).is_equivalent_to([1, 2]).and_.has_length(2).subject == [1, 2]


# ---------------------------------------------------------------------------
# The unordered-comparison cliff
#
# Pairing items through a hash and nothing else leaves every unhashable item --
# every `dict` in a list of JSON records -- to reach the structural pass unpaired,
# where a cap on the *total* number of items declines to look at a list that would
# have paired off perfectly. Reporting "a difference" for a comparison the engine
# declined to make fails `is_equivalent_to` on graphs that are equivalent, and
# worse, makes `is_not_equivalent_to` **pass** on them: a degraded comparison read
# as a confident answer, in the direction where a wrong answer is silent.
#
# These go through the two methods a user calls rather than through `compare`,
# because that is the seam the danger sits in: the engine's own suites read the
# block, and a block that says "too many unpaired items" looks like a difference
# to a reader and *is* one to `is_not_equivalent_to`.
# ---------------------------------------------------------------------------
def _rows(count: int, first: int = 0) -> list[dict[str, object]]:
    """``count`` JSON-shaped records -- unhashable, which is the whole point."""
    return [{"id": index, "name": "n" + str(index)} for index in range(first, first + count)]


class Unpoolable:  # noqa: PLW1641  (unhashable is the entire point)
    """A record nothing hashable can stand for, which is what the scan is for.

    ``dict`` and ``list`` are canonicalised into the pool
    (``_leftovers._stand_in``), so a list of JSON records pairs in linear time
    and never reaches the scanning meter at all. The bound still exists and still
    has to be pinned, so the tests that pin it use a shape that genuinely cannot
    be pooled: ``__eq__`` defined and ``__hash__`` set to ``None``, which is what
    Python does to any class that defines equality without hashing.
    """

    __slots__ = ("identifier",)

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier

    # No `__hash__`: Python sets it to `None` for any class that defines `__eq__`
    # without one, which is exactly what makes this shape reach the scan.
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Unpoolable) and self.identifier == other.identifier

    def __repr__(self) -> str:
        return "Unpoolable(" + str(self.identifier) + ")"


def _unpoolable(count: int) -> list[Any]:
    """``count`` records that must be paired by scan."""
    return [Unpoolable(index) for index in range(count)]


def _shuffled(items: list[Any], seed: int = 0) -> list[Any]:
    return random.Random(seed).sample(items, len(items))  # noqa: S311 (a fixture, not a key)


def _one_changed(rows: list[dict[str, object]], identifier: int) -> list[dict[str, object]]:
    """The same records, shuffled, with the one under ``identifier`` rewritten."""
    changed = [row for row in rows if row["id"] != identifier]
    changed.append({"id": identifier, "name": "somebody else"})
    return _shuffled(changed)


def _both_ways(
    actual: object, expected: object, *, equivalent: bool, options: Equivalency | None = None
) -> None:
    """Assert both methods, because they have to stay exact complements.

    Every case below goes through this. A defect that makes one of the two decline
    to look shows up as *agreement* -- both passing, or both failing -- which is
    the one thing two complements can never do.
    """
    subject = expect(actual)
    if equivalent:
        assert subject.is_equivalent_to(expected, options=options) is subject
        with pytest.raises(AssertionFailure):
            subject.is_not_equivalent_to(expected, options=options)
        return
    assert subject.is_not_equivalent_to(expected, options=options) is subject
    with pytest.raises(AssertionFailure):
        subject.is_equivalent_to(expected, options=options)


IGNORING_ORDER: Final = equivalency().ignoring_order()


def test_a_shuffled_list_of_records_is_equivalent_however_long_it_is() -> None:
    """A shuffled list of JSON records is equivalent to itself at every size.

    A hundred and twenty of them is not an exotic input; it is Tuesday. An engine
    that pairs by hash alone reports them as wholly unpaired -- so
    ``is_not_equivalent_to`` passes on a list against its own shuffle, with no
    diagnostic at all, which is a green test asserting the opposite of the truth.
    """
    for count in (0, 1, 50, 99, 100, 101, 120, 500):
        rows = _rows(count)
        _both_ways(rows, _shuffled(rows), equivalent=True, options=IGNORING_ORDER)


def test_one_record_out_of_a_hundred_and_twenty_is_still_found() -> None:
    """The other half: pairing the rest must not pair the one that has no counterpart."""
    _both_ways(_rows(120), _one_changed(_rows(120), 7), equivalent=False, options=IGNORING_ORDER)


def test_the_one_record_that_differs_is_named_rather_than_the_whole_list() -> None:
    rows = _rows(120)
    changed = _one_changed(rows, 7)
    message = _message(lambda: expect(rows).is_equivalent_to(changed, options=IGNORING_ORDER))
    assert "missing items: [{'id': 7, 'name': 'somebody else'}]" in message
    assert "extra items: [{'id': 7, 'name': 'n7'}]" in message
    assert "too many unpaired items" not in message


def test_every_kind_of_unhashable_item_pairs_up() -> None:
    """``dict``, ``list`` and ``set`` all fail ``hash``, and all three are ordinary."""
    for items in (
        [{"a": 1}, {"b": 2}, {"c": 3}],
        [[1, 2], [3, 4], [5, 6]],
        [{1, 2}, {3, 4}, {5, 6}],
        [bytearray(b"ab"), bytearray(b"cd")],
    ):
        _both_ways(items, _shuffled(items), equivalent=True, options=IGNORING_ORDER)


def test_hashable_items_still_pair_up_through_the_hash() -> None:
    for items in ([1, 2, 3], ["a", "b", "c"], [(1, 2), (3, 4)], [None, True, 0.5]):
        _both_ways(items, _shuffled(items), equivalent=True, options=IGNORING_ORDER)


def test_a_mix_of_hashable_and_unhashable_items_pairs_up() -> None:
    """The two pools have to be consulted together, or the mixed case is the cliff again."""
    items: list[object] = [1, {"a": 1}, "x", [2], (3,), {4}, None, {"a": 1}]
    _both_ways(items, _shuffled(items), equivalent=True, options=IGNORING_ORDER)


def test_a_mix_with_one_unhashable_item_missing_is_not_equivalent() -> None:
    items: list[object] = [1, {"a": 1}, "x", [2]]
    _both_ways(items, [1, {"a": 1}, "x", [99]], equivalent=False, options=IGNORING_ORDER)


def test_unhashable_duplicates_are_counted_rather_than_deduplicated() -> None:
    """Three copies on one side match three on the other and no more."""
    three = [{"a": 1}, {"a": 1}, {"a": 1}]
    _both_ways(three, [{"a": 1}, {"a": 1}, {"a": 1}], equivalent=True, options=IGNORING_ORDER)
    _both_ways(three, [{"a": 1}, {"a": 1}], equivalent=False, options=IGNORING_ORDER)
    _both_ways([{"a": 1}, {"a": 1}], three, equivalent=False, options=IGNORING_ORDER)


def test_items_equal_but_not_identical_pair_up() -> None:
    """Nothing here may pair by ``is``: every record is built twice, separately."""
    left = [{"id": index, "tags": [index]} for index in range(120)]
    right = _shuffled([{"id": index, "tags": [index]} for index in range(120)])
    assert all(left[0] is not item for item in right)
    _both_ways(left, right, equivalent=True, options=IGNORING_ORDER)


def test_a_nan_item_is_equivalent_to_itself_and_to_no_other_nan() -> None:
    """A NaN is equal to nothing, itself included -- so identity is all there is.

    Pinned in both directions because it is the one item whose answer differs
    between "the same object" and "an equal object", and an engine that quietly
    paired two distinct NaNs would be claiming something Python does not.
    """
    one = float("nan")
    _both_ways([1.0, one, 3.0], [3.0, one, 1.0], equivalent=True, options=IGNORING_ORDER)
    _both_ways([1.0, float("nan")], [float("nan"), 1.0], equivalent=False, options=IGNORING_ORDER)


def test_a_nan_inside_an_unhashable_item_does_not_pair() -> None:
    """``[nan] == [nan]`` is true by identity, and false for two different NaNs."""
    one = float("nan")
    _both_ways([[1.0, one]], [[1.0, one]], equivalent=True, options=IGNORING_ORDER)
    _both_ways(
        [[1.0, float("nan")]], [[1.0, float("nan")]], equivalent=False, options=IGNORING_ORDER
    )


def test_a_set_of_records_is_an_unordered_comparison_without_asking_for_one() -> None:
    """A set has no order to ignore, so it takes the same path with the default options."""
    left = [frozenset({("id", index)}) for index in range(120)]
    _both_ways({*left}, {*_shuffled(left)}, equivalent=True)


def test_a_shuffled_list_of_records_nested_two_levels_deep_pairs_up() -> None:
    """The shape a per-level pairing cap multiplies on, at a size the budget affords."""
    pages: list[dict[str, object]] = [
        {"page": number, "rows": _rows(20, number * 20)} for number in range(20)
    ]
    shuffled = [
        {"page": page["page"], "rows": _shuffled(cast("list[Any]", page["rows"]))}
        for page in _shuffled(pages)
    ]
    _both_ways(pages, shuffled, equivalent=True, options=IGNORING_ORDER)


# ---------------------------------------------------------------------------
# A comparison the engine declines to make is neither verdict
# ---------------------------------------------------------------------------
def test_a_comparison_too_big_to_pair_raises_rather_than_answering() -> None:
    """The floor: a degraded comparison must never be reported as a confident one.

    A difference is a failure for one method and a **pass** for the other, so a
    truncation reported as a difference is a wrong answer in whichever direction
    happens to read it. Both directions raise instead, with a message naming the
    bound that stopped it and what to do about it.
    """
    rows = _unpoolable(5000)
    shuffled = _shuffled(rows)
    with pytest.raises(ValueError, match="stopped rather than answered") as asked:
        expect(rows).is_equivalent_to(shuffled, options=IGNORING_ORDER)
    with pytest.raises(ValueError, match="stopped rather than answered") as denied:
        expect(rows).is_not_equivalent_to(shuffled, options=IGNORING_ORDER)
    assert str(asked.value) == str(denied.value), "the same non-answer, whichever way it was asked"
    assert "equality checks between items that cannot be hashed" in str(asked.value)
    assert "Compare fewer items in one call" in str(asked.value)


@measured
def test_ten_thousand_unhashable_items_stop_rather_than_hang() -> None:
    """Quadratic on ten thousand items would be a hang, which is its own defect.

    The five-second bound is what makes this a test of the *budget* rather than
    of the raise: a budget a hundred times too large still raises, just not
    soon. That reading cannot be taken while the interpreter is being traced --
    under coverage the same work takes longer than the bound on a shared runner
    -- so the claim is made in the untraced run, which CI always does as well.
    """
    rows = _unpoolable(10_000)
    shuffled = _shuffled(rows)
    started = time.perf_counter()
    with pytest.raises(ValueError, match="stopped rather than answered"):
        expect(rows).is_equivalent_to(shuffled, options=IGNORING_ORDER)
    assert time.perf_counter() - started < 5.0


def test_the_bound_is_on_the_unpaired_remainder_and_not_on_the_total() -> None:
    """Records that *do* pair up cost nothing structural at all.

    The bound is on the unpaired remainder rather than on the total: a cap on the
    total number of items fires on a list that paired off perfectly. The
    structural allowance is spent only on what equality could not settle -- here,
    one record out of four thousand.
    """
    rows = _rows(4000)
    _both_ways(rows, _one_changed(rows, 11), equivalent=False, options=IGNORING_ORDER)


def test_neither_method_is_reached_by_a_truncation_dressed_as_a_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutant: turn the raise into a returned block and both directions rot.

    Lowering the scanning allowance to nothing makes the cheap pass give up on the
    first unhashable item. If that came back as a difference, this list would be
    reported as *not* equivalent to its own shuffle -- and the second assertion
    below, ``is_not_equivalent_to``, would go green.
    """
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 0)
    rows = _unpoolable(4)
    shuffled = _shuffled(rows)
    with pytest.raises(ValueError, match="needed more than 0 "):
        expect(rows).is_equivalent_to(shuffled, options=IGNORING_ORDER)
    with pytest.raises(ValueError, match="needed more than 0 "):
        expect(rows).is_not_equivalent_to(shuffled, options=IGNORING_ORDER)


def test_json_shaped_records_pair_without_touching_the_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shape this engine is used on, and the one a scan would be quadratic on.

    A shuffled list of records has no hash of its own to pair through, so matching
    it by linear scan costs a probe per candidate and refuses outright once the
    allowance runs out before an answer does. ``_stand_in`` gives a ``dict`` and a
    ``list`` a hashable surrogate, so they pool like anything else.

    The allowance is set to nothing here, which is the sharpest way to say "the
    scan is not reached": a single charge against it would raise.
    """
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 0)
    rows = _rows(2000)
    _both_ways(rows, _shuffled(rows), equivalent=True, options=IGNORING_ORDER)
    _both_ways(rows, _one_changed(rows, 7), equivalent=False, options=IGNORING_ORDER)

    nested = [{"id": index, "tags": [index, "x"], "at": {"n": index}} for index in range(500)]
    _both_ways(nested, _shuffled(nested), equivalent=True, options=IGNORING_ORDER)


def test_a_surrogate_pairs_exactly_what_equality_pairs() -> None:
    """The soundness condition, case by case.

    A surrogate is only sound if two values share one *exactly* when they are
    equal. Each pair below is one way that could fail: a tag keeps a list from
    pairing with the tuple holding its items, a subclass free to narrow ``__eq__``
    is refused a surrogate altogether, and a value the engine cannot canonicalise
    falls back to the scan rather than to a wrong answer.
    """
    stand_in: Callable[[object], object] = getattr(_leftovers, "_stand_in")  # noqa: B009
    absent: object = getattr(_leftovers, "_NO_STAND_IN")  # noqa: B009

    assert stand_in({"a": 1}) == stand_in({"a": 1})
    assert stand_in({"a": 1}) != stand_in({"a": 2})
    assert stand_in({"a": 1, "b": 2}) == stand_in({"b": 2, "a": 1}), "a mapping has no order"
    assert stand_in([1, 2]) != stand_in((1, 2)), "a list is not the tuple of its items"
    assert stand_in([1, 2]) != stand_in([2, 1]), "a list has order"

    assert stand_in(OrderedDict[str, int](a=1)) is absent, "a subclass may narrow __eq__"
    assert stand_in(Unpoolable(1)) is absent, "no hash and nothing to stand for it"
    assert stand_in({"a": Unpoolable(1)}) is absent, "a record is only as poolable as it holds"

    deep: object = 1
    for _ in range(8):
        deep = [deep]
    assert stand_in(deep) is absent, "past the depth limit it gives up rather than guesses"


def test_what_cannot_be_pooled_is_still_paired_correctly() -> None:
    """Falling back to the scan must not change a single verdict."""

    def ordered(value: int) -> "OrderedDict[str, int]":
        return OrderedDict(a=value)

    left = [ordered(1), ordered(2)]
    _both_ways(left, [ordered(2), ordered(1)], equivalent=True, options=IGNORING_ORDER)
    _both_ways(left, [ordered(2), ordered(3)], equivalent=False, options=IGNORING_ORDER)

    unpoolable = _unpoolable(3)
    _both_ways(unpoolable, _shuffled(unpoolable), equivalent=True, options=IGNORING_ORDER)

    # A plain dict and an OrderedDict that are `==`: one pools and the other does
    # not, so equality never pairs them -- and the structural pass, which is wider
    # than `==`, finds them equivalent anyway.
    _both_ways([{"a": 1}], [ordered(1)], equivalent=True, options=IGNORING_ORDER)


def test_a_hashable_comparison_never_spends_the_scanning_allowance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scan is reached only by items that have no hash, which is what keeps it cheap."""
    monkeypatch.setattr(_budget, "_MAX_SCANNING", 0)
    items = list(range(500))
    _both_ways(items, _shuffled(items), equivalent=True, options=IGNORING_ORDER)
