"""Every marked line here must be rejected by pyright and mypy.

Without this half, `typing_tests/positive/bytes_subject.py` proves nothing —
and for this subject the negative half carries the *second* claim as well as the
first. Widening a parameter is easy to overdo: a `contains` that quietly took
`object` would satisfy every `assert_type` next door while offering a catalogue
that no longer applies. The refusals below are what says it did not.
"""

from typing import assert_type

from lovely_assertions import BytesExpect, Found, SequenceExpect, StringExpect, expect


def a_payload() -> bytes:
    return b""


# ---------------------------------------------------------------------------
# The widening stopped where it was meant to
# ---------------------------------------------------------------------------
def membership_takes_a_byte_or_a_run_and_nothing_else(payload: BytesExpect) -> None:
    payload.contains("ab")  # expect-error: a `str` is not a run of bytes
    payload.contains(1.5)  # expect-error
    payload.contains(None)  # expect-error
    payload.contains([97])  # expect-error
    payload.does_not_contain("ab")  # expect-error


def a_byte_string_subject_is_not_a_string_subject(payload: BytesExpect) -> None:
    """The catalogue is not the string one, however much the two look alike."""
    payload.starts_with(b"ab")  # expect-error
    payload.is_valid_uuid()  # expect-error
    payload.matches(b"a.")  # expect-error: `matches` is the string subject's


def has_byte_at_takes_two_integers(payload: BytesExpect) -> None:
    payload.has_byte_at(0, b"\x1f")  # expect-error: a byte value, not a byte string
    payload.has_byte_at("0", 1)  # expect-error
    payload.has_byte_at(0)  # expect-error: both are required
    payload.has_byte_at(index=0, value=1)  # expect-error: positional-only


# ---------------------------------------------------------------------------
# Reading it as text
# ---------------------------------------------------------------------------
def decoded_as_takes_an_encoding_name(payload: BytesExpect) -> None:
    payload.decoded_as(b"utf-8")  # expect-error: the name of an encoding, not bytes
    payload.decoded_as()  # expect-error: it is required
    payload.decoded_as("utf-8", "R")  # expect-error: `because` is keyword-only


def the_found_text_is_a_string_subject(payload: BytesExpect) -> None:
    found = payload.decoded_as("utf-8")
    assert_type(found.which, BytesExpect)  # expect-error
    assert_type(found.subject, bytes)  # expect-error
    assert_type(found, Found[BytesExpect, bytes, StringExpect])  # expect-error
    found.which.has_byte_at(0, 1)  # expect-error: it is text now


def is_valid_utf8_takes_nothing_positional(payload: BytesExpect) -> None:
    payload.is_valid_utf8("R")  # expect-error


# ---------------------------------------------------------------------------
# The subject that comes back is the one that comes back
# ---------------------------------------------------------------------------
def the_chain_does_not_widen(payload: BytesExpect) -> None:
    assert_type(payload.contains(b"a"), SequenceExpect[int])  # expect-error
    assert_type(payload.has_length(3), SequenceExpect[int])  # expect-error
    assert_type(expect(b"abc"), SequenceExpect[int])  # expect-error
    assert_type(expect(a_payload()), StringExpect)  # expect-error


def a_sequence_subject_has_none_of_this(rows: SequenceExpect[int]) -> None:
    """Extending means the byte assertions are on the byte subject, and only there."""
    rows.is_valid_utf8()  # expect-error
    rows.decoded_as("utf-8")  # expect-error
    rows.has_byte_at(0, 1)  # expect-error
    rows.contains(b"ab")  # expect-error: its elements are ints, and it is not bytes
