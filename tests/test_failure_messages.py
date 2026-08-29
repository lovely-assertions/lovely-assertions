"""What a failure actually says. The message engine is the product.

Format contract::

    Expected {name} {expectation}{because}.

The assertion supplies ``expectation`` without its trailing period; ``_fail``
adds the frame around it.
"""

import pytest

from lovely_assertions import AssertionFailure, expect


def test_failure_is_an_assertion_error() -> None:
    """pytest and unittest must treat a lovely failure as a plain assertion failure."""
    assert issubclass(AssertionFailure, AssertionError)


def test_is_equal_to_reports_both_sides() -> None:
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(3)
    assert str(caught.value) == "Expected balance to equal 3, but was 4."


def test_is_not_equal_to_reports_the_forbidden_value() -> None:
    balance = 3
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_not_equal_to(3)
    assert str(caught.value) == "Expected balance not to equal 3."


def test_is_none_reports_the_actual_value() -> None:
    label = "hello"
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_none()
    assert str(caught.value) == "Expected label to be None, but was 'hello'."


def test_is_not_none_states_that_it_was() -> None:
    label = None
    with pytest.raises(AssertionFailure) as caught:
        expect(label).is_not_none()
    assert str(caught.value) == "Expected label not to be None, but it was."


def test_is_instance_of_names_both_types() -> None:
    payload = "hello"
    with pytest.raises(AssertionFailure) as caught:
        expect(payload).is_instance_of(int)
    assert str(caught.value) == "Expected payload to be an instance of int, but was str."


def test_is_same_as_uses_identity() -> None:
    left = [1]
    with pytest.raises(AssertionFailure) as caught:
        expect(left).is_same_as([1])
    assert str(caught.value).startswith("Expected left to be the same object as [1], but was")


def test_is_not_same_as_uses_identity_too() -> None:
    """The complement, exercised on the only input that can make it fail.

    Two equal lists are *not* the same object, so the only way to fail this is to
    hand it the subject itself. The message says nothing about the value it was
    given a second time, on purpose: both names would print the same repr, and
    repeating it explains nothing that ``not the same object`` has not already
    said.
    """
    rows = [1]
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).is_not_same_as(rows)
    assert str(caught.value) == "Expected rows not to be the same object as [1]."


# ---------------------------------------------------------------------------
# because
# ---------------------------------------------------------------------------
def test_because_is_appended_before_the_period() -> None:
    balance = -4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(0, because="the ledger must balance")
    assert str(caught.value) == (
        "Expected balance to equal 0, but was -4 because the ledger must balance."
    )


def test_because_is_keyword_only() -> None:
    """``because`` is keyword-only, so it can never be mistaken for an operand."""
    with pytest.raises(TypeError):
        expect(1).is_equal_to(1, "a reason")  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]


def test_empty_because_changes_nothing() -> None:
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(3, because="")
    assert str(caught.value) == "Expected balance to equal 3, but was 4."


def test_a_leading_because_in_the_reason_is_not_doubled() -> None:
    """Users write it both ways; neither should produce 'because because'."""
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(3, because="because the ledger must balance")
    assert str(caught.value) == (
        "Expected balance to equal 3, but was 4 because the ledger must balance."
    )
