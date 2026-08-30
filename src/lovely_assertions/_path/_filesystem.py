"""What is actually on the disk, and why a question could not be answered.

Every call here can fail for reasons that have nothing to do with the assertion:
a permission, a broken link, a path that is not there at all. So each returns
what it found *and* what stopped it, and the assertions turn that into a sentence
-- "no such file" and "permission denied" are different bugs and a message that
says only "is not a file" sends the reader to the wrong one.

``pathlib`` is never imported here. The subject arrives already holding a path
object; what this module needs from it is duck-typed, so a program that asserts
on nothing else pays nothing for the module.
"""

from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISLNK, S_ISREG, S_ISSOCK
from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._render import names_preview, rendered
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from pathlib import Path

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: The clause every "there is nothing at all here" message ends with. A constant
#: because a dozen assertions end up reading it, all of them through
#: :func:`what_is_there`, and a reader comparing two failures should not have to
#: wonder whether two spellings mean two different things.
NOTHING_IS_THERE = "nothing is there at "


# ---------------------------------------------------------------------------
# What is actually on the disk -- every clause below is failure path only
# ---------------------------------------------------------------------------
def reason(error: OSError, /) -> str:
    """The operating system's own words for a failure. Failure path only."""
    return error.strerror or type(error).__name__


def kind_of(mode: int, /) -> str:
    """The noun for one ``st_mode`` word. Failure path only."""
    for holds, noun in (
        (S_ISDIR, "a directory"),
        (S_ISREG, "a regular file"),
        (S_ISSOCK, "a socket"),
        (S_ISFIFO, "a named pipe"),
        (S_ISBLK, "a block device"),
        (S_ISCHR, "a character device"),
    ):
        if holds(mode):
            return noun
    return "something the filesystem does not name"


def what_is_there(path: "Path", /) -> str:
    """Say what actually sits at ``path``. Failure path only.

    The whole reason this module has a house style: ``Expected report to be a
    regular file, but it was not`` tells a reader nothing they did not already
    know, and three quite different bugs produce it. This answers the question
    they were about to ask instead.

    Read from ``st_mode`` rather than through ``Path.is_dir`` and its siblings,
    for two reasons. ``lstat`` comes first, so a dangling symbolic link is
    reported as the link it is rather than as an absence -- and the second
    ``stat`` says what the link *points at*, which is what makes ``is_file``'s
    failure on a link to a directory legible. And every one of those convenience
    methods re-raises a permission error rather than answering it, so a helper
    built on them would throw from inside a failure message.
    """
    try:
        link = path.lstat()
    except FileNotFoundError:
        return NOTHING_IS_THERE + rendered(path)
    except OSError as error:
        return trouble(path, error)
    if not S_ISLNK(link.st_mode):
        return rendered(path) + " is " + kind_of(link.st_mode)
    try:
        target = path.stat()
    except FileNotFoundError:
        return rendered(path) + " is a symbolic link to nothing"
    except OSError as error:
        return (
            rendered(path)
            + " is a symbolic link that could not be followed ("
            + reason(error)
            + ")"
        )
    return rendered(path) + " is a symbolic link to " + kind_of(target.st_mode)


def emptiness(path: "Path", /) -> bool | None:
    """Whether ``path`` holds nothing; ``None`` when the question does not apply.

    Not a message builder -- this is the comparison the two emptiness assertions
    make. "Empty" means zero bytes for a regular file and no entries for a
    directory, and means nothing at all for a socket or a device, which is what
    ``None`` says. One ``stat`` decides which, so the answer cannot be about a
    different file from the one whose kind was checked. Raises ``OSError``; the
    caller turns that into a message.
    """
    info = path.stat()
    if S_ISDIR(info.st_mode):
        return not any(path.iterdir())
    if S_ISREG(info.st_mode):
        return info.st_size == 0
    return None


def fullness(path: "Path", /) -> str:
    """Why a path is not empty, as a message clause. Failure path only."""
    try:
        info = path.stat()
        if S_ISDIR(info.st_mode):
            return (
                rendered(path) + " holds " + names_preview(sorted(p.name for p in path.iterdir()))
            )
        if S_ISREG(info.st_mode):
            return rendered(path) + " holds " + count_of(info.st_size, "byte")
    except OSError as error:
        return trouble(path, error)
    return what_is_there(path)


def vacancy(path: "Path", /) -> str:
    """Why a path is not *non*-empty, as a message clause. Failure path only."""
    try:
        info = path.stat()
        if S_ISDIR(info.st_mode):
            return rendered(path) + " is an empty directory"
        if S_ISREG(info.st_mode):
            return rendered(path) + " is an empty file"
    except OSError as error:
        return trouble(path, error)
    return what_is_there(path)


def missing_child(parent: "Path", /) -> str:
    """Why a directory does not hold the child that was asked for. Failure path only.

    A subject that is not a directory at all falls through to
    :func:`what_is_there`, because "it holds no such entry" is a true statement
    about a regular file and a useless one.
    """
    try:
        names = sorted(entry.name for entry in parent.iterdir())
    except NotADirectoryError:
        return what_is_there(parent)
    except OSError as error:
        return trouble(parent, error)
    if not names:
        return rendered(parent) + " is an empty directory"
    return rendered(parent) + " holds " + names_preview(names)


def child_of(parent: "Path", name: str, /) -> "Path":
    """The direct child of ``parent`` called ``name``, or ``ValueError``.

    A child is one entry in one directory. ``has_child("logs/app.log")`` asks
    about a grandchild and ``has_child("..")`` asks about the parent, so both
    are refused rather than quietly answered -- and the check is done by joining
    and looking at the result, which keeps it in the subject's own path flavour
    instead of hard-coding a separator this module cannot even import.
    """
    if name in {"", ".", ".."}:
        raise ValueError("a child is the name of one directory entry, got " + repr(name))
    child = parent / name
    if child.name != name or child.parent != parent:
        raise ValueError(
            "a child is the name of one entry directly inside the subject, got " + repr(name)
        )
    return child


def size_note(path: "Path", mode: int, size: int, /) -> str:
    """Why a file's size is not the one that was claimed. Failure path only."""
    if S_ISREG(mode):
        return rendered(path) + " holds " + count_of(size, "byte")
    return what_is_there(path)


def trouble(path: "Path", error: OSError, /) -> str:
    """Why a filesystem call did not answer, as a message clause. Failure path only.

    An error's own text is kept, because "Permission denied" is the finding and
    paraphrasing it would lose it. The caller attaches the exception itself with
    ``cause=``, so the traceback survives alongside the sentence.

    ``FileNotFoundError`` is the one that must not be taken at face value, and it
    is handed to :func:`what_is_there` rather than answered here. ``stat`` on a
    **dangling symbolic link** raises it, and so does ``stat`` on a name with
    nothing at it at all; this module's third rule is that those are two
    different findings. Saying "nothing is there" for a link that is plainly
    sitting in its directory would send the reader looking for a missing file
    instead of a broken link -- and it would make these assertions contradict
    :meth:`PathExpect.exists`, which names it correctly.

    :func:`what_is_there` calls back here only for errors that are *not*
    ``FileNotFoundError``, so the two cannot loop.
    """
    if isinstance(error, FileNotFoundError):
        return what_is_there(path)
    return rendered(path) + " could not be read (" + reason(error) + ")"


def pair_trouble(subject: "Path", other: "Path", error: OSError, /) -> str:
    """Which of two paths a comparison tripped over. Failure path only.

    ``Path.samefile`` stats both sides and the exception does not say, in any way
    this module is willing to depend on, which one it was. Asking again costs a
    syscall on a path that has already failed, and buys a message that names the
    file the reader has to go and look at.

    The re-ask is ``stat``, the same call ``samefile`` made, and not ``exists``:
    a dangling symbolic link *exists* as a directory entry while being exactly
    the thing ``samefile`` could not stat, so an existence test walks past the
    guilty side and leaves the message blaming the innocent one. Whichever side
    ``stat`` refuses is described by :func:`what_is_there`, so a broken link, an
    absent name and a permissions problem each get their own words.
    """
    for candidate in (subject, other):
        try:
            candidate.stat()
        except OSError:
            return what_is_there(candidate)
    return trouble(subject, error)
