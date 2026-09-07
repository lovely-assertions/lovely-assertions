"""Rendering a byte string, and a byte, the way their reader writes them.

Two conventions this module keeps that ``repr`` does not. A single byte is read
and written in hexadecimal in every specification a test is checked against, and
``repr`` shows it as a decimal integer. And a long byte string is clipped like
every other value in a message, through the bound in force rather than at a
number written here.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import clipped as clipped_text

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def as_hex(value: int, /) -> str:
    """One byte as ``0x1f``. **Failure path only.**

    Two digits always, so a column of them lines up and ``0x0a`` cannot be
    mistaken for a different width from ``0xa0``.
    """
    return "0x" + format(value, "02x")


def clipped(value: bytes, /) -> str:
    """A byte string rendered and cut to the bound in force. **Failure path only.**

    Through ``format_value`` rather than ``repr``, so a caller who registered a
    formatter for their own byte-string subclass is consulted here as everywhere
    else, and through ``current_formatting`` so that widening a scope widens
    this too.
    """
    return clipped_text(format_value(value), current_formatting().max_chars)
