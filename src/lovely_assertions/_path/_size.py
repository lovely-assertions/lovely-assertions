"""A size is a file's size.

A directory has one on most filesystems and it is an implementation detail --
the size of the entry table, not of anything the caller put there. Asking gets a
failure that says what was there instead of a number nobody can act on.
"""

from stat import S_ISREG
from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._filesystem import (
    size_note,
    trouble,
)
from lovely_assertions._path._guards import reject_unusable_size
from lovely_assertions._path._purepath import DiskPath, PurePathExpect
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SizeAssertions(PurePathExpect[DiskPath]):
    """How many bytes, and the refusal to ask it of a directory."""

    __slots__ = ()

    def has_size(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the file holds exactly ``expected`` bytes.

        A size is a *file's* size. A directory's ``st_size`` is bookkeeping the
        filesystem chose -- 64 on one machine and 4096 on another -- so asserting
        on it would be asserting on the host, and a directory fails here with a
        message saying what it is. A negative expectation raises ``ValueError``.
        """
        reject_unusable_size(expected)
        subject = self._subject
        try:
            info = subject.stat()
        except OSError as error:
            return self._fail(
                f"to hold {count_of(expected, 'byte')}, but {trouble(subject, error)}",
                because,
                cause=error,
            )
        if S_ISREG(info.st_mode) and info.st_size == expected:
            return self
        return self._fail(
            f"to hold {count_of(expected, 'byte')}, "
            f"but {size_note(subject, info.st_mode, info.st_size)}",
            because,
        )

    def has_size_greater_than(self, limit: int, /, *, because: str = "") -> Self:
        """Assert the file holds strictly more than ``limit`` bytes."""
        reject_unusable_size(limit)
        subject = self._subject
        try:
            info = subject.stat()
        except OSError as error:
            return self._fail(
                f"to hold more than {count_of(limit, 'byte')}, but {trouble(subject, error)}",
                because,
                cause=error,
            )
        if S_ISREG(info.st_mode) and info.st_size > limit:
            return self
        return self._fail(
            f"to hold more than {count_of(limit, 'byte')}, "
            f"but {size_note(subject, info.st_mode, info.st_size)}",
            because,
        )

    def has_size_less_than(self, limit: int, /, *, because: str = "") -> Self:
        """Assert the file holds strictly fewer than ``limit`` bytes.

        A limit of zero raises ``ValueError``: no file is smaller than nothing,
        so the claim could never hold. :meth:`is_empty` is the zero-byte one.
        """
        reject_unusable_size(limit)
        if limit == 0:
            raise ValueError("no file holds fewer than zero bytes; is_empty is the zero-byte claim")
        subject = self._subject
        try:
            info = subject.stat()
        except OSError as error:
            return self._fail(
                f"to hold fewer than {count_of(limit, 'byte')}, but {trouble(subject, error)}",
                because,
                cause=error,
            )
        if S_ISREG(info.st_mode) and info.st_size < limit:
            return self
        return self._fail(
            f"to hold fewer than {count_of(limit, 'byte')}, "
            f"but {size_note(subject, info.st_mode, info.st_size)}",
            because,
        )
