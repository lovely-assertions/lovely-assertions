"""Where a path sits, and how two of them relate.

Still no disk: whether a path is absolute is a fact about its text, and whether
one is under another is a question about their parts. Both are answered without
asking the filesystem anything, which is what makes them safe on a path that was
never created.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._render import clipped, rendered

if TYPE_CHECKING:
    from pathlib import PurePath

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class PlacementAssertions[T: PurePath](Expect[T]):
    """Absolute or relative, and one path against another."""

    __slots__ = ()

    def is_absolute(self, *, because: str = "") -> Self:
        """Assert the path is absolute."""
        if self._subject.is_absolute():
            return self
        return self._fail(f"to be an absolute path, but was {rendered(self._subject)}", because)

    def is_relative(self, *, because: str = "") -> Self:
        """Assert the path is relative -- the exact complement of :meth:`is_absolute`."""
        if not self._subject.is_absolute():
            return self
        return self._fail(f"to be a relative path, but was {rendered(self._subject)}", because)

    # -- one path against another ------------------------------------------------
    def is_relative_to(self, other: "PurePath", /, *, because: str = "") -> Self:
        """Assert the path sits under ``other``, or is ``other``.

        This is ``PurePath.is_relative_to``: pure prefix algebra on the parts,
        with nothing resolved against a disk. So ``a/../b`` **is** relative to
        ``a`` -- the ``..`` is a component here and not a movement -- and a path
        is relative to itself. Two different flavours never match, and case
        sensitivity belongs to the flavour, so a claim that has to mean the same
        on every machine is written with two paths of one named flavour rather
        than with whatever the host happens to produce.
        """
        subject = self._subject
        if subject.is_relative_to(other):
            return self
        return self._fail(
            f"to be relative to {rendered(other)}, but {rendered(subject)} is not", because
        )

    def is_not_relative_to(self, other: "PurePath", /, *, because: str = "") -> Self:
        """Assert the path does not sit under ``other``.

        The exact complement of :meth:`is_relative_to`.
        """
        subject = self._subject
        if not subject.is_relative_to(other):
            return self
        return self._fail(
            f"not to be relative to {rendered(other)}, but {rendered(subject)} is", because
        )

    def has_parent(self, other: "PurePath", /, *, because: str = "") -> Self:
        """Assert the path's immediate parent is ``other``.

        Immediate, and by equality: a grandparent does not count, and
        :meth:`is_relative_to` is the assertion for "somewhere underneath". The
        parent of a root is itself, and the parent of a one-component relative
        path is ``.``.
        """
        subject = self._subject
        if subject.parent == other:
            return self
        return self._fail(
            f"to have the parent {rendered(other)}, "
            f"but {rendered(subject)} has the parent {rendered(subject.parent)}",
            because,
        )

    def matches_pattern(
        self, pattern: str, /, *, case_sensitive: bool | None = None, because: str = ""
    ) -> Self:
        """Assert the path matches a glob ``pattern`` -- ``PurePath.match``.

        **The pattern is anchored at the right, not the left**, and that surprises
        everyone once. A relative pattern is matched against the *tail* of the
        path, so ``"*.txt"`` matches ``/var/log/app.txt`` -- it is asking about
        the last component only. Anchor it by starting the pattern with a
        separator: ``"/*.txt"`` does not match that path, because there are three
        components and the pattern names one. ``PurePath.full_match`` is the
        whole-path form if that is what you meant.

        Case sensitivity follows the path's flavour unless ``case_sensitive``
        says otherwise -- so a ``PureWindowsPath`` matches case-insensitively and
        a ``PurePosixPath`` does not. Pass the keyword when the answer must be
        the same on every machine.

        An empty pattern raises ``ValueError``: it matches nothing at all, so it
        is a bug in the test rather than a finding about the path.
        """
        if not pattern:
            raise ValueError("a match pattern must not be empty")
        subject = self._subject
        if subject.match(pattern, case_sensitive=case_sensitive):
            return self
        return self._fail(
            f"to match the pattern {clipped(pattern)}, but {rendered(subject)} does not", because
        )
