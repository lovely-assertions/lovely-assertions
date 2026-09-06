"""The root the byte seams share, and the one decision it carries.

There is only one, and it is the whole design of this package:
:class:`BytesBase` extends ``SequenceExpect[int]`` rather than ``Expect[bytes]``.
A byte string *is* a sequence of integers, so every assertion that reads it as
one is true of it, and taking them away to add a few would be a trade nobody
asked for. What the seams above add is the readings that a sequence of integers
cannot express.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._sequence import SequenceExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class BytesBase(SequenceExpect[int]):
    """What every seam of the byte subject inherits: the sequence catalogue, whole."""

    __slots__ = ()

    if TYPE_CHECKING:
        #: The inherited declaration is ``Sequence[int]``, which is true and not
        #: precise enough to call ``decode`` or ``find`` on. Narrowed here rather
        #: than converted at each call site: dispatch builds this subject for a
        #: ``bytes`` and for nothing else, so the conversion would convert a
        #: ``bytes`` into itself -- and it is not free. ``bytes(x)`` on an object
        #: that already is one costs a call and a couple of dozen bytes, on the
        #: path of every *passing* assertion in this package.
        #:
        #: An annotation and not an assignment, under ``TYPE_CHECKING``, so no
        #: slot is added and nothing exists at runtime. pyright reports the
        #: narrowing because an attribute is mutable in general; this one is
        #: written once, in a constructor, by a dispatcher that already knows the
        #: type.
        _subject: bytes  # pyright: ignore[reportIncompatibleVariableOverride]
