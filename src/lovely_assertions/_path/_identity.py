"""Same file on disk, whatever the two paths say.

Two paths that differ in every character can name one file -- a link, a mount, a
relative path resolved from elsewhere. The comparison asks the filesystem rather
than the strings, and says which of the two it could not resolve when it fails.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._filesystem import pair_trouble
from lovely_assertions._path._purepath import DiskPath, PurePathExpect
from lovely_assertions._path._render import (
    rendered,
)

if TYPE_CHECKING:
    from pathlib import Path

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class IdentityAssertions(PurePathExpect[DiskPath]):
    """The same file, which is not the same path."""

    __slots__ = ()

    def is_same_file_as(self, other: "Path", /, *, because: str = "") -> Self:
        """Assert the subject and ``other`` are the same file on disk.

        Same *file*, not same path: two names for one inode -- a hard link, a
        symbolic link, ``./x`` against ``x`` -- are the same file. Both sides have
        to exist for the question to have an answer, so a missing one is reported
        by name rather than escaping as a ``FileNotFoundError``.
        """
        subject = self._subject
        try:
            same = subject.samefile(other)
        except OSError as error:
            return self._fail(
                f"to be the same file as {rendered(other)}, "
                f"but {pair_trouble(subject, other, error)}",
                because,
                cause=error,
            )
        if same:
            return self
        return self._fail(
            f"to be the same file as {rendered(other)}, but was {rendered(subject)}", because
        )
