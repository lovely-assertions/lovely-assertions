"""Whether something is at the path, and what it turned out to be.

The two are one seam because they fail into each other: a path that is not a file
may be a directory, may be a broken link, or may be nothing at all, and an
assertion that says only "is not a file" has told the reader the least useful of
the three.
"""

from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._filesystem import (
    trouble,
    what_is_there,
)
from lovely_assertions._path._purepath import DiskPath, PurePathExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class PresenceAssertions(PurePathExpect[DiskPath]):
    """What is there, and what kind of thing it is."""

    __slots__ = ()

    def exists(self, *, because: str = "") -> Self:
        """Assert something usable exists at the path, following symbolic links.

        A dangling symbolic link fails, because there is nothing at the other end
        of it -- but the message says *that*, rather than claiming the path is
        not there.
        """
        subject = self._subject
        try:
            if subject.exists():
                return self
        except OSError as error:
            return self._fail(f"to exist, but {trouble(subject, error)}", because, cause=error)
        return self._fail(f"to exist, but {what_is_there(subject)}", because)

    def does_not_exist(self, *, because: str = "") -> Self:
        """Assert the path is free -- nothing there, not even a dangling link.

        Asked with ``lstat`` rather than ``stat``, so this is "the name is
        unused" and not "the name resolves to nothing". A broken symbolic link
        fails both this and :meth:`exists`; it is a third state, and each message
        names it.
        """
        subject = self._subject
        try:
            if not subject.exists(follow_symlinks=False):
                return self
        except OSError as error:
            return self._fail(f"not to exist, but {trouble(subject, error)}", because, cause=error)
        return self._fail(f"not to exist, but {what_is_there(subject)}", because)

    # -- what kind of thing is there ---------------------------------------------
    def is_file(self, *, because: str = "") -> Self:
        """Assert a regular file is at the path, following symbolic links."""
        subject = self._subject
        try:
            if subject.is_file():
                return self
        except OSError as error:
            return self._fail(
                f"to be a regular file, but {trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"to be a regular file, but {what_is_there(subject)}", because)

    def is_not_file(self, *, because: str = "") -> Self:
        """Assert something is at the path and it is not a regular file.

        Not the strict complement of :meth:`is_file`: a path with nothing at it
        fails both, because a mistyped path that quietly passed ``is_not_file``
        would be a test asserting nothing. :meth:`does_not_exist` is the
        assertion for an absent path.
        """
        subject = self._subject
        try:
            if subject.exists(follow_symlinks=False) and not subject.is_file():
                return self
        except OSError as error:
            return self._fail(
                f"not to be a regular file, but {trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be a regular file, but {what_is_there(subject)}", because)

    def is_directory(self, *, because: str = "") -> Self:
        """Assert a directory is at the path, following symbolic links."""
        subject = self._subject
        try:
            if subject.is_dir():
                return self
        except OSError as error:
            return self._fail(
                f"to be a directory, but {trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"to be a directory, but {what_is_there(subject)}", because)

    def is_not_directory(self, *, because: str = "") -> Self:
        """Assert something is at the path and it is not a directory.

        Requires the path to exist, for the reason :meth:`is_not_file` does.
        """
        subject = self._subject
        try:
            if subject.exists(follow_symlinks=False) and not subject.is_dir():
                return self
        except OSError as error:
            return self._fail(
                f"not to be a directory, but {trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be a directory, but {what_is_there(subject)}", because)

    def is_symlink(self, *, because: str = "") -> Self:
        """Assert the path itself is a symbolic link, wherever it points.

        Asked with ``lstat``, so a **broken** link passes: the link is a real
        entry in a real directory even when its target is gone. Anything else
        would make this assertion agree with ``exists``, which already has a
        method.
        """
        subject = self._subject
        try:
            if subject.is_symlink():
                return self
        except OSError as error:
            return self._fail(
                f"to be a symbolic link, but {trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"to be a symbolic link, but {what_is_there(subject)}", because)

    def is_not_symlink(self, *, because: str = "") -> Self:
        """Assert something is at the path and it is not a symbolic link.

        Requires the path to exist, for the reason :meth:`is_not_file` does.
        """
        subject = self._subject
        try:
            if subject.exists(follow_symlinks=False) and not subject.is_symlink():
                return self
        except OSError as error:
            return self._fail(
                f"not to be a symbolic link, but {trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be a symbolic link, but {what_is_there(subject)}", because)
