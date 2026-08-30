"""Name, stem and suffixes -- the parts of a path that need no disk.

Pure in the ``pathlib`` sense: these read the text of the path and nothing else,
so they answer for a path that does not exist and for one on a filesystem this
process cannot see.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._guards import reject_bare_string, reject_bare_suffix
from lovely_assertions._path._render import clipped, names_preview, rendered, suffix_note

if TYPE_CHECKING:
    from pathlib import PurePath

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NameAssertions[T: PurePath](Expect[T]):
    """The pieces a path name is made of."""

    __slots__ = ()

    def has_name(self, expected: str, /, *, because: str = "") -> Self:
        """Assert the last component of the path is ``expected``.

        The name is what ``PurePath.name`` reports, so a trailing slash is not
        part of it -- ``PurePosixPath("/a/b/")`` is named ``"b"`` -- and a root
        or a bare ``"."`` is named ``""``.
        """
        subject = self._subject
        if subject.name == expected:
            return self
        return self._fail(
            f"to have the name {clipped(expected)}, "
            f"but {rendered(subject)} has the name {clipped(subject.name)}",
            because,
        )

    def has_stem(self, expected: str, /, *, because: str = "") -> Self:
        """Assert the name without its final suffix is ``expected``.

        One suffix comes off, not all of them: the stem of ``archive.tar.gz`` is
        ``archive.tar``. :meth:`has_suffixes` is how the whole tail is asserted.
        """
        subject = self._subject
        if subject.stem == expected:
            return self
        return self._fail(
            f"to have the stem {clipped(expected)}, "
            f"but {rendered(subject)} has the stem {clipped(subject.stem)}",
            because,
        )

    def has_suffix(self, expected: str, /, *, because: str = "") -> Self:
        """Assert the final suffix is ``expected``, leading dot included.

        ``.txt``, not ``txt``: that is how ``PurePath.suffix`` reports it, and a
        suffix without its dot is a claim no path could satisfy, so it raises
        ``ValueError`` rather than failing. Only the *final* suffix is compared,
        so ``archive.tar.gz`` has suffix ``.gz``.
        """
        reject_bare_suffix(expected)
        subject = self._subject
        if subject.suffix == expected:
            return self
        return self._fail(
            f"to have the suffix {clipped(expected)}, "
            f"but {rendered(subject)} has {suffix_note(subject.suffix)}",
            because,
        )

    def has_suffixes(
        self, expected: "list[str] | tuple[str, ...]", /, *, because: str = ""
    ) -> Self:
        """Assert the full run of suffixes is ``expected``, in order.

        ``archive.tar.gz`` has suffixes ``[".tar", ".gz"]``. Each one carries its
        leading dot, on the same terms as :meth:`has_suffix`. An empty sequence
        asserts the path has no suffixes at all, which is a real claim rather
        than a vacuous one -- :meth:`has_no_suffix` is the same assertion in
        words.

        The parameter is a list or a tuple rather than a ``Sequence[str]``
        deliberately. A ``str`` *is* a ``Sequence[str]``, so the pleasant-looking
        signature would let ``has_suffixes(".tar.gz")`` type-check and then
        compare the path's suffixes against ``['.', 't', 'a', 'r', ...]``. The
        checker refuses it instead, and the runtime guard catches the same
        mistake from an untyped caller.
        """
        reject_bare_string(expected)
        for suffix in expected:
            reject_bare_suffix(suffix)
        subject = self._subject
        found = subject.suffixes
        # `==` answers False for a list against a tuple however the two line up,
        # so the runs are compared position by position instead. Copying one side
        # to let `==` do the work would allocate on the passing path, and so
        # would iterating either of them; an index walk allocates nothing.
        count = len(expected)
        if len(found) == count:
            index = 0
            while index < count and found[index] == expected[index]:
                index += 1
            if index == count:
                return self
        return self._fail(
            f"to have the suffixes {names_preview(expected)}, "
            f"but {rendered(subject)} has {names_preview(found)}",
            because,
        )

    def has_no_suffix(self, *, because: str = "") -> Self:
        """Assert the path's name carries no suffix at all.

        A dotfile has none: ``PurePosixPath(".gitignore").suffix`` is ``""``,
        because the leading dot starts the name rather than a suffix.
        """
        subject = self._subject
        if not subject.suffix:
            return self
        return self._fail(
            f"to have no suffix, but {rendered(subject)} has {suffix_note(subject.suffix)}",
            because,
        )
