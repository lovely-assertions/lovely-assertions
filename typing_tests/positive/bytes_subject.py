"""The byte surface: ``BytesExpect``.

Three claims are pinned here.

*The violation is closed.* ``expect(b"x").contains(b"x")`` type-checks. That one
line is the whole reason this subject exists: it used to be a checker error and a
runtime pass at the same time, which is claim one inverted.

*Nothing was withdrawn to close it.* ``BytesExpect`` extends
``SequenceExpect[int]``, so the integer reading and every inherited assertion are
still there and still typed. The negative corpus is where "still there" is
proved to mean something.

*``decoded_as`` is a proof and not a promise.* It hands back a ``Found`` whose
``.which`` is a ``StringExpect``, and the value really is a ``str`` -- it came out
of ``bytes.decode`` -- so the declaration is one the runtime keeps.
"""

from collections.abc import Sequence
from typing import assert_type

from lovely_assertions import (
    BytesExpect,
    Found,
    SequenceExpect,
    StringExpect,
    exactly,
    expect,
)


def a_payload() -> bytes:
    return b""


# ---------------------------------------------------------------------------
# Which subject a byte string gets
# ---------------------------------------------------------------------------
def bytes_gets_its_own_subject() -> None:
    assert_type(expect(b"abc"), BytesExpect)
    assert_type(expect(a_payload()), BytesExpect)


def the_neighbours_are_untouched() -> None:
    """Only ``bytes`` moved; the other buffers stay on the sequence subject."""
    assert_type(expect(bytearray(b"abc")), SequenceExpect[int])
    assert_type(expect([1, 2]), SequenceExpect[int])


# ---------------------------------------------------------------------------
# The widened membership, which is why the subject exists
# ---------------------------------------------------------------------------
def membership_takes_a_byte_or_a_run_of_them(payload: BytesExpect) -> None:
    assert_type(payload.contains(97), BytesExpect)
    assert_type(payload.contains(b"ab"), BytesExpect)
    assert_type(payload.does_not_contain(97), BytesExpect)
    assert_type(payload.does_not_contain(b"ab"), BytesExpect)


def occurrences_is_accepted_either_way(payload: BytesExpect) -> None:
    assert_type(payload.contains(97, occurrences=exactly(2)), BytesExpect)
    assert_type(payload.contains(b"ab", occurrences=exactly(2)), BytesExpect)


def has_byte_at_takes_two_integers(payload: BytesExpect) -> None:
    assert_type(payload.has_byte_at(0, 0x1F), BytesExpect)
    assert_type(payload.has_byte_at(-1, 0x1F, because="R"), BytesExpect)


# ---------------------------------------------------------------------------
# Nothing was withdrawn
# ---------------------------------------------------------------------------
def the_inherited_catalogue_is_still_typed(payload: BytesExpect) -> None:
    assert_type(payload.has_length(3), BytesExpect)
    assert_type(payload.starts_with_sequence(b"ab"), BytesExpect)
    assert_type(payload.is_sorted(), BytesExpect)
    assert_type(payload.contains_in_order(97, 98), BytesExpect)
    assert_type(payload.subject, Sequence[int])


def it_substitutes_for_the_sequence_subject(payload: BytesExpect) -> None:
    """Extending rather than replacing means exactly this."""
    accepts: SequenceExpect[int] = payload
    _ = accepts


# ---------------------------------------------------------------------------
# Reading it as text
# ---------------------------------------------------------------------------
def decoded_as_narrows_to_a_string_subject(payload: BytesExpect) -> None:
    assert_type(payload.decoded_as("utf-8"), Found[BytesExpect, str, StringExpect])
    assert_type(payload.decoded_as("utf-8").which, StringExpect)
    assert_type(payload.decoded_as("utf-8").subject, str)
    assert_type(payload.decoded_as("utf-8").and_, BytesExpect)
    assert_type(payload.decoded_as("utf-8").which.starts_with("<"), StringExpect)


def is_valid_utf8_returns_the_subject(payload: BytesExpect) -> None:
    assert_type(payload.is_valid_utf8(), BytesExpect)
    assert_type(payload.is_valid_utf8(because="R"), BytesExpect)


# ---------------------------------------------------------------------------
# A user's own subclass keeps its own type
# ---------------------------------------------------------------------------
def a_subclass_gets_itself_back() -> None:
    class FrameExpect(BytesExpect):
        __slots__ = ()

        def has_magic(self, *, because: str = "") -> "FrameExpect":
            return self.has_byte_at(0, 0x1F, because=because)

    frame = FrameExpect(b"\x1f\x8b")
    assert_type(frame.contains(b"\x8b"), FrameExpect)
    assert_type(frame.has_magic(), FrameExpect)
    assert_type(frame.decoded_as("latin-1").and_, FrameExpect)
