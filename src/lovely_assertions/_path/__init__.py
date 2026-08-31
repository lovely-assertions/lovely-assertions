"""Filesystem paths.

Two subjects, because ``pathlib`` has two kinds of path and only one of them can
touch a disk. ``PurePath`` is string algebra -- suffixes, parents, absoluteness
-- and answers without a filesystem; ``Path`` adds the questions that require
one. Folding them together would let ``expect(PurePosixPath("/a")).exists()``
type-check and then fail with ``AttributeError``, which is exactly the class of
bug this library exists to make impossible. The split makes the checker say no.

**Nothing here imports ``pathlib``**, and that is not a micro-optimisation:
``pathlib`` pulls in ``fnmatch`` and therefore ``re``, and ``re`` is a cost only
the assertions that genuinely need it should pay. The path types are used for
typing and never at runtime -- every assertion below goes through a method on
the subject it was handed -- so they arrive under ``TYPE_CHECKING``.
``_subjects.py`` finds the real types through ``sys.modules``: a program holding
a ``Path`` has already imported ``pathlib``.

Four rules govern the half of the catalogue that touches a disk. They exist
because the obvious implementation of every one of these assertions --
``if path.is_file(): return self`` and a message that says "but it was not" --
reports the wrong bug more often than the right one.

**A missing path is its own answer.** ``Path.is_file`` answers ``False`` for a
regular file that is not there, for a directory, and for a path whose parent
directory cannot be searched. Those are three different bugs in the reader's
code and only one of them is "that is not a file", so every failure here goes
through :func:`_what_is_there`, which says *what is actually at the path*:
nothing, a directory, a socket, a symbolic link to nothing, or an error that
stopped the question being answered at all.

**A negation still requires something to be there.** ``is_not_file`` on a
mistyped path would otherwise pass -- the classic green test that asserts
nothing, which is the failure mode this whole library is pointed at. So
``is_not_file``, ``is_not_directory``, ``is_not_symlink``, ``is_not_empty`` and
``does_not_have_child`` all fail when nothing is there, and say so. **They are
therefore not the strict complements of their positive forms**, unlike the
negations in ``_ordered``: a missing path fails ``is_file`` *and*
``is_not_file``. That is stated on every one of them rather than left for a
reader to discover, and :meth:`PathExpect.does_not_exist` is the assertion that
means "nothing is there".

**A dangling symbolic link is a third state, not a missing path.**
``Path.exists`` follows links, so it says ``False`` for one; ``lstat`` says the
link is right there. Both facts are true and the messages carry both:
``is_symlink`` passes for a broken link (that is the classic bug this catches),
``exists`` fails with "is a symbolic link to nothing" rather than "nothing is
there", and ``does_not_exist`` -- which asks whether the *name* is free -- fails
too. So ``exists`` and ``does_not_exist`` are not complements either, for the
one state where neither answer is the whole truth.

**An ``OSError`` is reported, never swallowed and never raw.** A permission
denied on the parent directory is a real problem with the machine the tests are
running on, and the two easy answers are both wrong: letting it escape turns a
failing assertion into a traceback about ``stat``, and folding it into "but it
was not a file" hides it completely. Instead the error's own words go into the
message -- ``'/root/x' could not be read (Permission denied)`` -- and the
original exception is attached through ``_fail(..., cause=error)``, so the
traceback the reader needs is still underneath the sentence that explains it.
The same goes for text that will not decode: :meth:`PathExpect.has_text` names
the encoding and the byte that stopped it rather than letting a
``UnicodeDecodeError`` escape from inside an assertion.

Each subject is assembled from one mixin per seam. The pure one asks the
filesystem nothing and is assembled first; the disk one inherits the whole of it
and adds the seams that need a filesystem to answer.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._contents import ContentAssertions
from lovely_assertions._path._emptiness import EmptinessAssertions
from lovely_assertions._path._entries import EntryAssertions
from lovely_assertions._path._identity import IdentityAssertions
from lovely_assertions._path._presence import PresenceAssertions
from lovely_assertions._path._purepath import DiskPath, PurePathExpect
from lovely_assertions._path._size import SizeAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["PathExpect", "PurePathExpect"]


class PathExpect(
    PresenceAssertions,
    EmptinessAssertions,
    SizeAssertions,
    ContentAssertions,
    EntryAssertions,
    IdentityAssertions,
    PurePathExpect[DiskPath],
):
    """Assertions for a path that can be resolved against a filesystem.

    Everything in :class:`PurePathExpect` is here too, so one chain can go from
    the shape of a name to the bytes behind it. Read this module's docstring
    before adding to this class: a missing path, a dangling symbolic link and an
    ``OSError`` each have a settled answer, and they are the difference between
    a message that finds the bug and one that describes the symptom.
    """

    __slots__ = ()
