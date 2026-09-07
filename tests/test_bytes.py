"""``BytesExpect`` -- the subject a byte string gets (``_bytes``).

Three things are pinned here, in this order of importance.

*The claim-one violation is closed, and nothing is closed with it.*
``expect(b"x").contains(b"x")`` used to be a type error and a runtime pass at the
same time -- the checker refusing the question a reader asks while the runtime
answered it anyway. It now type-checks. What matters as much is that the integer
reading, and every inherited sequence assertion, still mean exactly what they
meant: this subject *extends* ``SequenceExpect[int]`` and takes nothing away.

*The messages read in the reader's own notation.* A byte is written in
hexadecimal in every specification a test is checked against, and a decoding
failure carries an offset that is the useful half of the exception it replaces.

*Nothing else moved.* ``bytearray`` and ``memoryview`` still reach the sequence
subject, because they are not ``bytes`` and the exact table is keyed on identity.
"""

from typing import TYPE_CHECKING

import pytest

from lovely_assertions import (
    AssertionFailure,
    BytesExpect,
    SequenceExpect,
    StringExpect,
    exactly,
    expect,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


# ---------------------------------------------------------------------------
# Which subject, and what it kept
# ---------------------------------------------------------------------------
def test_bytes_gets_its_own_subject() -> None:
    assert type(expect(b"abc")) is BytesExpect


def test_the_neighbours_are_untouched() -> None:
    """The exact table is keyed on identity, so only ``bytes`` itself moved."""
    mutable: Sequence[int] = bytearray(b"abc")
    viewed: Sequence[int] = memoryview(b"abc")
    assert type(expect(mutable)) is SequenceExpect
    assert type(expect(viewed)) is SequenceExpect
    assert type(expect([1, 2])) is SequenceExpect


def test_the_subject_extends_the_sequence_one() -> None:
    assert issubclass(BytesExpect, SequenceExpect)


def test_the_whole_sequence_catalogue_still_applies() -> None:
    """Nothing was withdrawn. This is the half that makes it a non-breaking change."""
    expect(b"abc").has_length(3).and_.starts_with_sequence(b"ab").and_.ends_with_sequence(b"bc")
    expect(b"abc").contains_in_order(97, 99)
    expect(b"abc").is_sorted()
    expect(b"").is_empty()


def test_the_integer_reading_is_unchanged() -> None:
    """``b"abc"[0]`` is 97, and the assertion that follows from it still holds."""
    expect(b"abc").contains(97)
    expect(b"abc").does_not_contain(255)


# ---------------------------------------------------------------------------
# The violation this subject exists to close
# ---------------------------------------------------------------------------
def test_a_run_of_bytes_is_a_membership_question() -> None:
    """What ``in`` means for two byte strings, and what the sequence subject could not ask."""
    payload = b"GET /orders HTTP/1.1"
    expect(payload).contains(b"HTTP/1.1")

    with pytest.raises(AssertionFailure) as caught:
        expect(payload).contains(b"POST")

    assert str(caught.value) == (
        "Expected payload to contain b'POST', but was b'GET /orders HTTP/1.1'."
    )


def test_does_not_contain_names_where_the_run_begins() -> None:
    """ "It is in there somewhere" is the half a reader already knew."""
    payload = b"GET /orders HTTP/1.1"
    expect(payload).does_not_contain(b"DELETE")

    with pytest.raises(AssertionFailure) as caught:
        expect(payload).does_not_contain(b"orders")

    assert str(caught.value) == (
        "Expected payload not to contain b'orders',"
        " but it begins at byte 5 of b'GET /orders HTTP/1.1'."
    )


def test_occurrences_counts_non_overlapping_runs() -> None:
    """``bytes.count``, and the rule the string subject already applies."""
    expect(b"aXbXc").contains(b"X", occurrences=exactly(2))
    expect(b"aaaa").contains(b"aa", occurrences=exactly(2))

    with pytest.raises(AssertionFailure) as caught:
        expect(b"aXbXc").contains(b"X", occurrences=exactly(3))

    assert str(caught.value) == (
        "Expected b\"aXbXc\" to contain b'X' exactly 3 times, but it appears 2 times in b'aXbXc'."
    )


def test_an_integer_with_occurrences_takes_the_inherited_route() -> None:
    expect(b"aXbXc").contains(0x58, occurrences=exactly(2))


# ---------------------------------------------------------------------------
# A byte reads in hexadecimal
# ---------------------------------------------------------------------------
def test_has_byte_at_says_both_values_in_hex() -> None:
    """The whole of what this assertion buys over ``has_element_at``."""
    header = b"\x1f\x8b\x08"
    expect(header).has_byte_at(0, 0x1F).and_.has_byte_at(1, 0x8B)

    with pytest.raises(AssertionFailure) as caught:
        expect(header).has_byte_at(1, 0x1F)

    assert str(caught.value) == (
        "Expected header to have 0x1f at byte 1, but had 0x8b: b'\\x1f\\x8b\\x08'."
    )


def test_has_byte_at_counts_from_the_end_for_a_negative_index() -> None:
    expect(b"\x1f\x8b").has_byte_at(-1, 0x8B)


def test_has_byte_at_says_so_when_the_index_is_past_the_end() -> None:
    header = b"\x1f"
    with pytest.raises(AssertionFailure) as caught:
        expect(header).has_byte_at(5, 0x00)

    assert str(caught.value) == (
        "Expected header to have 0x00 at byte 5, but it holds 1 byte: b'\\x1f'."
    )


def test_a_value_no_byte_could_hold_is_a_misuse() -> None:
    """A mistake in the test, not a finding about the subject."""
    for value in (256, -1, 300):
        with pytest.raises(ValueError, match=r"a byte value is 0\.\.255"):
            expect(b"\x1f").has_byte_at(0, value)


# ---------------------------------------------------------------------------
# Reading it as text
# ---------------------------------------------------------------------------
def test_is_valid_utf8_names_the_offset_that_broke() -> None:
    """The useful half of the ``UnicodeDecodeError`` it replaces."""
    expect("héllo".encode()).is_valid_utf8()

    broken = b"a\xffb"
    with pytest.raises(AssertionFailure) as caught:
        expect(broken).is_valid_utf8()

    assert str(caught.value) == (
        "Expected broken to be valid UTF-8, but byte 1 (0xff) is not: b'a\\xffb'."
    )


def test_decoded_as_hands_back_a_real_string_subject() -> None:
    """A proof rather than a promise: ``bytes.decode`` returned the ``str``."""
    body = b"<!DOCTYPE html>"
    found = expect(body).decoded_as("utf-8")

    assert type(found.which) is StringExpect
    assert found.subject == "<!DOCTYPE html>"
    found.which.starts_with("<!DOCTYPE")


def test_decoded_as_continues_back_to_the_bytes() -> None:
    expect(b"abc").decoded_as("utf-8").and_.has_length(3)


def test_decoded_as_reports_the_offset_too() -> None:
    broken = b"a\xffb"
    with pytest.raises(AssertionFailure) as caught:
        expect(broken).decoded_as("utf-8")

    assert str(caught.value) == (
        "Expected broken to decode as utf-8, but byte 1 (0xff) is not valid there: b'a\\xffb'."
    )


def test_another_encoding_is_accepted() -> None:
    expect("café".encode("latin-1")).decoded_as("latin-1").which.is_equal_to("café")


def test_an_unknown_encoding_is_the_standard_library_s_error() -> None:
    """Nothing this library has anything to add to."""
    with pytest.raises(LookupError):
        expect(b"abc").decoded_as("not-an-encoding")


# ---------------------------------------------------------------------------
# Everything cross-cutting, which the subject gets for free
# ---------------------------------------------------------------------------
def test_because_attaches_to_the_sentence() -> None:
    with pytest.raises(AssertionFailure) as caught:
        expect(b"abc").contains(b"z", because="the header is always present")

    assert str(caught.value).endswith("because the header is always present.")


def test_a_narrowing_failure_absorbs_the_rest_of_the_chain() -> None:
    from lovely_assertions import soft_assertions

    with soft_assertions() as scope:
        expect(b"a\xffb").described_as("payload").decoded_as("utf-8").which.starts_with("x")
        collected = scope.discard()

    assert collected == [
        "Expected payload to decode as utf-8, but byte 1 (0xff) is not valid there: b'a\\xffb'."
    ]
