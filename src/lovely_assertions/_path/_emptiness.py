"""Empty, for a file and for a directory.

A file is empty when it holds no bytes; a directory is empty when it holds no
entries. One assertion, two meanings, and the failure says which one it applied
so a reader who mixed them up can see it.
"""

from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._filesystem import (
    emptiness,
    fullness,
    trouble,
    vacancy,
)
from lovely_assertions._path._purepath import DiskPath, PurePathExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EmptinessAssertions(PurePathExpect[DiskPath]):
    """Nothing in it -- which means two things."""

    __slots__ = ()

    def is_empty(self, *, because: str = "") -> Self:
        """Assert the path holds nothing: zero bytes for a file, no entries for a directory.

        One name and two meanings, decided by what is actually there. A path that
        is neither -- a socket, a device, a dangling link, or nothing at all --
        fails rather than being forced into one of the two, and the message says
        which of those it found. Symbolic links are followed, so a link to an
        empty directory is empty.
        """
        subject = self._subject
        try:
            if emptiness(subject) is True:
                return self
        except OSError as error:
            return self._fail(f"to be empty, but {trouble(subject, error)}", because, cause=error)
        return self._fail(f"to be empty, but {fullness(subject)}", because)

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the path holds something: at least one byte, or at least one entry.

        Not the strict complement of :meth:`is_empty`, and for two reasons rather
        than one: a path with nothing at it fails both (see :meth:`is_not_file`),
        and so does a path that is neither a regular file nor a directory, since
        neither meaning of "empty" applies to a socket.
        """
        subject = self._subject
        try:
            if emptiness(subject) is False:
                return self
        except OSError as error:
            return self._fail(
                f"not to be empty, but {trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be empty, but {vacancy(subject)}", because)
