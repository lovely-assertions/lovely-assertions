"""Defects that sit below the catalogue.

They are grouped here rather than scattered among the catalogues because they
share a property: none is a missing assertion, and every one of them costs more
than a missing assertion would. Two would make a reader's tests lie, one would
bury the message the library exists to produce, and one would crash on a type the
reference documents.
"""

import asyncio
import warnings

import pytest

from lovely_assertions import AssertionFailure, expect


# ---------------------------------------------------------------------------
# An async callable handed to a sync assertion
# ---------------------------------------------------------------------------
async def _raises_value_error() -> None:
    raise ValueError("this must actually run")


async def _returns_quietly() -> int:
    return 1


def test_does_not_raise_refuses_an_async_callable() -> None:
    """A coroutine nobody awaits asserts nothing, so handing one over is refused.

    Calling an async function returns a coroutine without running its body, so
    ``does_not_raise()`` sees no exception and passes — green, and testing
    nothing. A suite migrating onto asyncio would stop asserting without a single
    test turning red.
    """
    with pytest.raises(TypeError, match="coroutine"):
        expect(_raises_value_error).does_not_raise()


def test_raises_refuses_an_async_callable() -> None:
    with pytest.raises(TypeError, match="coroutine"):
        expect(_raises_value_error).raises(ValueError)


def test_raises_exactly_refuses_an_async_callable() -> None:
    with pytest.raises(TypeError, match="coroutine"):
        expect(_raises_value_error).raises_exactly(ValueError)


def test_the_refusal_names_the_remedy() -> None:
    with pytest.raises(TypeError) as caught:
        expect(_returns_quietly).does_not_raise()
    message = str(caught.value)
    assert "coroutine" in message
    assert "await" in message.casefold(), "the message should say what to do instead"


def test_the_coroutine_is_closed_rather_than_leaked() -> None:
    """An un-awaited coroutine warns at collection time and confuses the reader."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(TypeError):
            expect(_raises_value_error).does_not_raise()


def test_a_sync_callable_returning_a_value_is_still_fine() -> None:
    """The guard must not narrow what a callable subject may return."""
    expect(lambda: 42).does_not_raise()


def test_an_awaited_result_is_an_ordinary_subject() -> None:
    """Nothing here blocks asserting on what a coroutine produced."""
    assert expect(asyncio.run(_returns_quietly())).is_equal_to(1).subject == 1


# ---------------------------------------------------------------------------
# Subject naming must never be confidently wrong
# ---------------------------------------------------------------------------
def test_two_statements_on_one_line_fall_back_rather_than_guess() -> None:
    """A wrong name is worse than no name.

    Both statements share a line, so both ``ast.Expr`` nodes span zero lines and
    there is nothing to prefer one of them by. The failure below is about
    ``second``; taking the first candidate would report it as ``first``, a
    sentence about the reader's code that is simply false. An ambiguous answer
    falls back to ``the value`` instead.
    """
    first = 2
    second = 3
    # fmt: off
    with pytest.raises(AssertionFailure) as caught:
        expect(first).is_equal_to(2); expect(second).is_equal_to(1)  # noqa: E702
    # fmt: on
    message = str(caught.value)
    assert "Expected first " not in message, "named the wrong variable"
    assert message == "Expected the value to equal 1, but was 3."


def test_a_single_statement_on_its_own_line_is_still_named() -> None:
    """The fallback must not become the common case."""
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(3)
    assert str(caught.value) == "Expected balance to equal 3, but was 4."


def test_a_one_line_body_is_still_named() -> None:
    balance = 4
    # fmt: off
    with pytest.raises(AssertionFailure) as caught:
        if balance: expect(balance).is_equal_to(3)  # noqa: E701
    # fmt: on
    assert str(caught.value) == "Expected balance to equal 3, but was 4."


def test_a_comprehension_is_still_named() -> None:
    values = [2]
    with pytest.raises(AssertionFailure) as caught:
        [expect(value).is_equal_to(1) for value in values]
    assert str(caught.value) == "Expected value to equal 1, but was 2."


def test_a_statement_spanning_several_lines_is_still_named() -> None:
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(
            balance,
        ).is_equal_to(3)
    assert str(caught.value) == "Expected balance to equal 3, but was 4."


# ---------------------------------------------------------------------------
# bytes is a Sequence, and the sequence catalogue must not assume otherwise
# ---------------------------------------------------------------------------
def test_does_not_contain_none_works_on_bytes() -> None:
    """``None in b"abc"`` raises ``TypeError``; iterating does not.

    ``expect()`` routes ``bytes`` to the sequence subject and the reference
    documents it, so an assertion that crashes there is the library's bug, not
    the caller's.
    """
    expect(b"abc").does_not_contain_none()
    expect(bytearray(b"abc")).does_not_contain_none()
    view: memoryview[int] = memoryview(b"abc")
    expect(view).does_not_contain_none()


def test_does_not_contain_none_still_finds_a_none() -> None:
    items = [1, None, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_contain_none()
    assert "index 1" in str(caught.value)


def test_the_rest_of_the_sequence_catalogue_survives_bytes() -> None:
    expect(b"abc").has_length(3)
    expect(b"abc").is_not_empty()
    expect(b"abc").contains(ord("a"))
    expect(b"abc").is_sorted()


# ---------------------------------------------------------------------------
# A vacuous call that arrives as an empty mapping rather than as no arguments
# ---------------------------------------------------------------------------
def test_contains_entries_with_an_empty_mapping_is_a_caller_bug() -> None:
    """An empty mapping asserts nothing, exactly as a variadic call with no values."""
    with pytest.raises(ValueError, match="at least one"):
        expect({"a": 1}).contains_entries({})


def test_contains_entries_with_entries_is_unaffected() -> None:
    expect({"a": 1, "b": 2}).contains_entries({"a": 1})
