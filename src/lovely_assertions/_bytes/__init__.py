"""Assertions for a byte string, which is a sequence of integers and also text.

``bytes`` really is a ``Sequence[int]``: ``b"abc"[0]`` is ``97``, and
``expect(payload).contains(97)`` is the assertion that follows from it. That
reading is kept whole here -- :class:`BytesExpect` **extends** the sequence
subject rather than replacing it, so every one of its assertions still applies
and nothing that worked before stops working.

What it adds is the reading the sequence catalogue could not express. ``bytes``
answers ``in`` for a run of bytes as well as for one, so a checker used to refuse
``expect(payload).contains(b"HTTP")`` while the runtime happily answered it --
the one place left in this library where the catalogue on offer was not the
catalogue that applied. Widening the parameter closes that, and widening is
contravariant, so it takes nothing away.

Past that, a payload is usually asked two more things: whether it is valid text,
and what that text says. :meth:`~lovely_assertions._bytes._decoding.DecodingAssertions.decoded_as`
is the seam that makes this subject worth having rather than merely correct -- it
hands back a genuine ``str``, so the whole string catalogue follows it.

**Not here, deliberately.** A byte-offset difference block, which is what would
fix an equality failure on two long payloads clipping both sides at the same
offset with nothing to point at. That belongs in the difference engine rather
than in a subject, and it is a larger change than this one.

Four files: the root the seams share, how a byte and a byte string are written,
what is inside one, and how it reads as text.
"""

from lovely_assertions._bytes._base import BytesBase
from lovely_assertions._bytes._containment import ByteContainmentAssertions
from lovely_assertions._bytes._decoding import DecodingAssertions
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["BytesExpect"]


class BytesExpect(ByteContainmentAssertions, DecodingAssertions, BytesBase):
    """Assertions for a byte string.

    A :class:`~lovely_assertions.SequenceExpect` over integers, with two things
    added: membership widened to a run of bytes, and the seam that reads the
    payload as text.

    The element type stays ``int`` because that is what it is. ``.subject`` is
    the byte string, ``has_length`` counts bytes, and ``contains(97)`` means
    exactly what it always did -- while ``contains(b"a")`` now means what a
    reader expects it to.
    """

    __slots__ = ()
