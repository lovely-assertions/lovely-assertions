"""A child is a name, not a route.

``contains_entry("a/b")`` is refused: a directory holds entries, and a path with
a separator in it is a question about two directories that reads like a question
about one.
"""

from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._filesystem import (
    child_of,
    missing_child,
    trouble,
    what_is_there,
)
from lovely_assertions._path._purepath import DiskPath, PurePathExpect
from lovely_assertions._path._render import (
    clipped,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EntryAssertions(PurePathExpect[DiskPath]):
    """What a directory holds, by name."""

    __slots__ = ()

    def has_child(self, name: str, /, *, because: str = "") -> Self:
        """Assert the directory holds an entry called ``name``.

        One entry, directly inside: ``"logs/app.log"``, ``".."`` and an absolute
        path all raise ``ValueError`` rather than being answered, because a child
        is a name and not a route. A dangling symbolic link counts as a child --
        it is an entry in the directory whatever it points at.
        """
        subject = self._subject
        child = child_of(subject, name)
        try:
            if child.exists(follow_symlinks=False):
                return self
        except OSError as error:
            return self._fail(
                f"to have a child named {clipped(name)}, but {trouble(child, error)}",
                because,
                cause=error,
            )
        return self._fail(
            f"to have a child named {clipped(name)}, but {missing_child(subject)}", because
        )

    def does_not_have_child(self, name: str, /, *, because: str = "") -> Self:
        """Assert the directory holds no entry called ``name``.

        The subject has to be a directory: a file holds no entries, so answering
        "correct, no such child" for one would be a test that passed because the
        question was meaningless.
        """
        subject = self._subject
        child = child_of(subject, name)
        try:
            if not subject.is_dir():
                return self._fail(
                    f"not to have a child named {clipped(name)}, but {what_is_there(subject)}",
                    because,
                )
            if not child.exists(follow_symlinks=False):
                return self
        except OSError as error:
            return self._fail(
                f"not to have a child named {clipped(name)}, but {trouble(subject, error)}",
                because,
                cause=error,
            )
        return self._fail(
            f"not to have a child named {clipped(name)}, but {what_is_there(child)}", because
        )
