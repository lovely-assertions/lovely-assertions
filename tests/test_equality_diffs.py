"""``is_equal_to`` on a composite value.

The difference engine itself is covered by ``tests/test_diff.py``. This file
covers the *wiring*: that equality failures actually carry a difference block,
that the two operands printed around it stay bounded, and that the sentence still
reads as a sentence once a block hangs off it.

The size half is the part that rots quietly. A message is not wrong for being
enormous — no assertion fails because of it — so nothing catches it except a
test that says so out loud.
"""

import pytest

from lovely_assertions import AssertionFailure, expect, soft_assertions

#: Comfortably past any per-operand clip, so a regression shows up as orders of
#: magnitude rather than a few characters.
_BIG = 5000


def _message(callback: object) -> str:
    with pytest.raises(AssertionFailure) as caught:
        callback()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]
    return str(caught.value)


# ---------------------------------------------------------------------------
# The block is present, and it is the useful part
# ---------------------------------------------------------------------------
def test_a_mapping_failure_names_the_keys_that_moved() -> None:
    actual = {"host": "prod", "port": 8080, "timeout": 30}
    expected = {"host": "prod", "port": 443, "retries": 3}
    message = _message(lambda: expect(actual).is_equal_to(expected))
    assert "values differ at key 'port': 8080 instead of 443" in message
    assert "missing keys: ['retries']" in message
    assert "extra keys: ['timeout']" in message


def test_a_sequence_failure_names_the_first_offending_index() -> None:
    message = _message(lambda: expect([1, 2, 3, 4]).is_equal_to([1, 9, 3]))
    assert "first difference at index 1: 2 instead of 9" in message


def test_multi_line_text_gets_a_unified_diff() -> None:
    before = "alpha\nbeta\ngamma\n"
    after = "alpha\nBETA\ngamma\n"
    message = _message(lambda: expect(after).is_equal_to(before))
    assert "the strings differ (- expected, + actual)" in message
    assert "-beta" in message
    assert "+BETA" in message


def test_a_short_value_gets_no_block_at_all() -> None:
    """The block earns its place; two small reprs already say everything."""
    count = 3
    message = _message(lambda: expect(count).is_equal_to(4))
    assert message == "Expected count to equal 4, but was 3."


# ---------------------------------------------------------------------------
# Bounded output — the operands as well as the block
# ---------------------------------------------------------------------------
def test_comparing_two_large_sequences_stays_readable() -> None:
    """The operands are clipped, not just the block.

    The difference engine bounds its own output; the two reprs printed around it
    have to be bounded as well, or comparing two 5,000-element lists prints both
    lists in full and buries the one line that says where they parted company.
    """
    actual = list(range(_BIG))
    expected = list(range(_BIG))
    expected[4000] = -1
    message = _message(lambda: expect(actual).is_equal_to(expected))
    assert "first difference at index 4000" in message
    assert len(message) < 1000, f"message ran to {len(message)} characters"


def test_comparing_two_large_strings_stays_readable() -> None:
    actual = "\n".join(f"line {index}" for index in range(_BIG))
    expected = actual.replace("line 2500", "LINE 2500")
    message = _message(lambda: expect(actual).is_equal_to(expected))
    assert "line 2500" in message
    assert len(message) < 2000, f"message ran to {len(message)} characters"


def test_a_clipped_operand_says_how_much_it_cut() -> None:
    message = _message(lambda: expect("a" * _BIG).is_equal_to("b" * _BIG))
    assert "more characters)" in message


# ---------------------------------------------------------------------------
# The sentence survives having a block attached
# ---------------------------------------------------------------------------
def test_the_reason_attaches_to_the_sentence_not_to_the_block() -> None:
    """``because`` belongs to the claim, not to the last line of a diff."""
    actual = {"a": 1}
    expected = {"b": 2}
    message = _message(lambda: expect(actual).is_equal_to(expected, because="the sync ran twice"))
    first_line, _, block = message.partition("\n")
    assert first_line.endswith("because the sync ran twice.")
    assert block, "the difference block should follow the sentence"
    assert "because" not in block


def test_only_the_first_line_carries_the_full_stop() -> None:
    actual = {"a": 1}
    expected = {"b": 2}
    message = _message(lambda: expect(actual).is_equal_to(expected))
    assert not message.endswith(".")
    assert message.partition("\n")[0].endswith(".")


def test_a_block_stays_aligned_under_its_numbered_item_in_a_soft_scope() -> None:
    """Otherwise a diff in an aggregate reads as if it belonged to the list."""
    # Nested rather than combined: the soft scope must be the inner one, so that
    # its aggregate is what `pytest.raises` catches.
    with pytest.raises(AssertionFailure) as caught:  # noqa: SIM117
        with soft_assertions():
            actual = {"a": 1}
            expected = {"b": 2}
            expect(actual).is_equal_to(expected)
            count = 5
            expect(count).is_equal_to(9)
    lines = str(caught.value).splitlines()
    assert lines[0] == "2 assertions failed:"
    assert lines[1].startswith("  (1) ")
    continuation = [line for line in lines[2:] if not line.startswith("  (")]
    assert continuation, "the difference block should still be there"
    assert all(line.startswith("      ") for line in continuation), (
        f"continuation lines must sit under the item, not under the list: {continuation}"
    )
