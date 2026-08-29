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
negations in ``_ordered.py``: a missing path fails ``is_file`` *and*
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
"""

from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISLNK, S_ISREG, S_ISSOCK
from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._diff import describe_difference
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import count_of, length_note

if TYPE_CHECKING:
    from pathlib import Path, PurePath

#: The value type again, this time as a PEP 695 alias, for the one class
#: statement below whose *base* names it.
#:
#: A base is evaluated when the class is created, so it cannot be a name only
#: the checkers can see. A string is the obvious escape and it is not free: on
#: CPython 3.14, subscripting a generic with a string builds a ``ForwardRef``,
#: and building one imports ``annotationlib``, which pulls in ``ast`` and
#: ``enum`` -- three modules that would then load for every program that merely
#: says ``import lovely_assertions``, and invisible on 3.13 where a
#: ``ForwardRef`` costs nothing.
#:
#: A PEP 695 alias is lazily evaluated in the one way that matters here: the
#: object exists without its right-hand side being resolved, so the alias can
#: name a type from a module this library refuses to import, and a checker still
#: reads through it to ``PurePathExpect[Path]``. A bound -- ``[T: "PurePath"]``
#: -- is lazy already and stays a string; only a base needs this.
type _Path = Path

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["PathExpect", "PurePathExpect", "rendered"]

#: Longest file content this module will hand to ``_diff`` for a line-by-line
#: difference. The clipped rendering and the invisible-difference note are cheap
#: whatever the size; a unified diff is ``difflib`` over the whole of both sides,
#: and running that across a multi-megabyte fixture would turn one failing
#: assertion into a hang. Past this the message still names the file, shows the
#: first :data:`~lovely_assertions.FormattingOptions.max_chars` of it and says
#: how long it really is.
_MAX_DIFFED = 100_000

#: The clause every "there is nothing at all here" message ends with. A constant
#: because a dozen assertions end up reading it, all of them through
#: :func:`_what_is_there`, and a reader comparing two failures should not have to
#: wonder whether two spellings mean two different things.
_NOTHING_IS_THERE = "nothing is there at "


def rendered(value: object, /) -> str:
    """Render a path for a failure message. Failure path only.

    A path's ``repr`` is ``PosixPath('/etc/hosts')``; what a reader wants to see
    is ``/etc/hosts``. The formatter registry keeps precedence, so a project that
    has registered its own spelling still gets it.
    """
    text = format_value(value)
    if text != repr(value):
        return text
    return "'" + str(value) + "'"


def _clipped(text: str, /) -> str:
    """Render a string operand or a file's contents, eliding an over-long one.

    Failure path only, which is what makes the ``ContextVar`` read affordable.
    The same budget and the same tail as ``_string._clipped``: a file's text and
    a string subject are the same kind of thing to a reader, and two subjects
    that elide the same value at different lengths would only raise the question
    of which one was lying.

    Rendered through the formatter registry rather than with a bare ``repr``, so
    a project that has registered a spelling of its own for text gets it here.
    The budget bounds the *value*, not the rendering of it, so the cut is made
    before the rendering: what the reader sees elided is the text that was too
    long, not the quoting around it.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    return format_value(text[:limit] + "...") + length_note(len(text))


def _names_preview(names: "list[str] | tuple[str, ...]", /) -> str:
    """Render a directory listing, or a run of suffixes. Failure path only.

    Capped at ``max_items`` for the reason ``_string._preview`` is: a directory
    with four hundred entries in it answers no question by having all four
    hundred printed at the reader.

    A tuple renders exactly as the list of the same names does. The parameter
    admits one so that :meth:`PurePathExpect.has_suffixes` can show the sequence
    it was handed without copying it into a list first.

    Each name goes through the formatter registry, so one list in one message
    does not render half its entries the library's way and half a project's.
    """
    limit = current_formatting().max_items
    shown = [format_value(name) for name in names[:limit]]
    if len(names) <= limit:
        return "[" + ", ".join(shown) + "]"
    return "[" + ", ".join(shown) + ", ... " + str(len(names) - limit) + " more]"


# ---------------------------------------------------------------------------
# Caller-bug guards -- a claim no subject could satisfy is a bug in the test
# ---------------------------------------------------------------------------
def _reject_bare_suffix(suffix: str, /) -> None:
    """Raise ``ValueError`` for a suffix written without its leading dot.

    ``PurePath.suffix`` is either ``""`` or a string beginning with ``.``, so
    ``has_suffix("txt")`` is not a claim that happens to be false about this
    path: it is a claim no path could ever satisfy, which makes it a bug in the
    test rather than a finding about the subject. The library's rule for those
    is ``ValueError``, and the message names the spelling that was meant.

    ``""`` is left alone -- it is what a path with no suffix genuinely reports,
    so the claim is satisfiable. :meth:`PurePathExpect.has_no_suffix` says the
    same thing in words.
    """
    if suffix and not suffix.startswith("."):
        raise ValueError(
            "a suffix carries its leading dot, the way PurePath.suffix reports it:"
            " got " + repr(suffix) + ", did you mean " + repr("." + suffix) + "?"
        )


def _reject_bare_string(expected: object, /) -> None:
    """Raise ``TypeError`` for a bare string where a list of suffixes was wanted.

    The checkers already refuse it -- :meth:`PurePathExpect.has_suffixes` is typed
    to make that possible -- so this is the untyped caller's copy of the same
    answer. Without it ``has_suffixes(".tar.gz")`` iterates the string one
    character at a time and reports something about ``'t'``.

    The parameter is ``object`` rather than the operand's own type on purpose:
    mypy knows a ``list`` is never a ``str`` and calls the check unreachable, and
    widening here is the honest way to say "this is for values the annotation
    could not stop".
    """
    if isinstance(expected, str):
        raise TypeError(
            "has_suffixes takes a list of suffixes, not one string: a str would be"
            " read one character at a time; got " + repr(expected)
        )


def _reject_unusable_size(size: int, /) -> None:
    """Raise ``ValueError`` for a byte count no file could have."""
    if size < 0:
        raise ValueError("a size in bytes is never negative, got " + str(size))


def _child_of(parent: "Path", name: str, /) -> "Path":
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


# ---------------------------------------------------------------------------
# What is actually on the disk -- every clause below is failure path only
# ---------------------------------------------------------------------------
def _reason(error: OSError, /) -> str:
    """The operating system's own words for a failure. Failure path only."""
    return error.strerror or type(error).__name__


def _trouble(path: "Path", error: OSError, /) -> str:
    """Why a filesystem call did not answer, as a message clause. Failure path only.

    An error's own text is kept, because "Permission denied" is the finding and
    paraphrasing it would lose it. The caller attaches the exception itself with
    ``cause=``, so the traceback survives alongside the sentence.

    ``FileNotFoundError`` is the one that must not be taken at face value, and it
    is handed to :func:`_what_is_there` rather than answered here. ``stat`` on a
    **dangling symbolic link** raises it, and so does ``stat`` on a name with
    nothing at it at all; this module's third rule is that those are two
    different findings. Saying "nothing is there" for a link that is plainly
    sitting in its directory would send the reader looking for a missing file
    instead of a broken link -- and it would make these assertions contradict
    :meth:`PathExpect.exists`, which names it correctly.

    :func:`_what_is_there` calls back here only for errors that are *not*
    ``FileNotFoundError``, so the two cannot loop.
    """
    if isinstance(error, FileNotFoundError):
        return _what_is_there(path)
    return rendered(path) + " could not be read (" + _reason(error) + ")"


def _kind_of(mode: int, /) -> str:
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


def _what_is_there(path: "Path", /) -> str:
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
        return _NOTHING_IS_THERE + rendered(path)
    except OSError as error:
        return _trouble(path, error)
    if not S_ISLNK(link.st_mode):
        return rendered(path) + " is " + _kind_of(link.st_mode)
    try:
        target = path.stat()
    except FileNotFoundError:
        return rendered(path) + " is a symbolic link to nothing"
    except OSError as error:
        return (
            rendered(path)
            + " is a symbolic link that could not be followed ("
            + _reason(error)
            + ")"
        )
    return rendered(path) + " is a symbolic link to " + _kind_of(target.st_mode)


def _emptiness(path: "Path", /) -> bool | None:
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


def _fullness(path: "Path", /) -> str:
    """Why a path is not empty, as a message clause. Failure path only."""
    try:
        info = path.stat()
        if S_ISDIR(info.st_mode):
            return (
                rendered(path) + " holds " + _names_preview(sorted(p.name for p in path.iterdir()))
            )
        if S_ISREG(info.st_mode):
            return rendered(path) + " holds " + count_of(info.st_size, "byte")
    except OSError as error:
        return _trouble(path, error)
    return _what_is_there(path)


def _vacancy(path: "Path", /) -> str:
    """Why a path is not *non*-empty, as a message clause. Failure path only."""
    try:
        info = path.stat()
        if S_ISDIR(info.st_mode):
            return rendered(path) + " is an empty directory"
        if S_ISREG(info.st_mode):
            return rendered(path) + " is an empty file"
    except OSError as error:
        return _trouble(path, error)
    return _what_is_there(path)


def _missing_child(parent: "Path", /) -> str:
    """Why a directory does not hold the child that was asked for. Failure path only.

    A subject that is not a directory at all falls through to
    :func:`_what_is_there`, because "it holds no such entry" is a true statement
    about a regular file and a useless one.
    """
    try:
        names = sorted(entry.name for entry in parent.iterdir())
    except NotADirectoryError:
        return _what_is_there(parent)
    except OSError as error:
        return _trouble(parent, error)
    if not names:
        return rendered(parent) + " is an empty directory"
    return rendered(parent) + " holds " + _names_preview(names)


def _pair_trouble(subject: "Path", other: "Path", error: OSError, /) -> str:
    """Which of two paths a comparison tripped over. Failure path only.

    ``Path.samefile`` stats both sides and the exception does not say, in any way
    this module is willing to depend on, which one it was. Asking again costs a
    syscall on a path that has already failed, and buys a message that names the
    file the reader has to go and look at.

    The re-ask is ``stat``, the same call ``samefile`` made, and not ``exists``:
    a dangling symbolic link *exists* as a directory entry while being exactly
    the thing ``samefile`` could not stat, so an existence test walks past the
    guilty side and leaves the message blaming the innocent one. Whichever side
    ``stat`` refuses is described by :func:`_what_is_there`, so a broken link, an
    absent name and a permissions problem each get their own words.
    """
    for candidate in (subject, other):
        try:
            candidate.stat()
        except OSError:
            return _what_is_there(candidate)
    return _trouble(subject, error)


# ---------------------------------------------------------------------------
# Reading text -- shared by `has_text`, `contains_text`, `does_not_contain_text`
# ---------------------------------------------------------------------------
def _read_text(path: "Path", encoding: str, /) -> str:
    """The exact contents of ``path``, decoded and otherwise untouched.

    Bytes are read and decoded here rather than through ``Path.read_text``
    because ``read_text`` opens in text mode, and text mode translates ``\\r\\n``
    to ``\\n``. An assertion whose whole promise is "this is exactly what is in
    the file" cannot be built on a reader that silently edits two of its
    characters -- ``has_text`` would pass on a CRLF file given LF text, which is
    the difference a Windows checkout introduces and the one a reader most needs
    to be told about.

    Raises ``OSError`` if the file cannot be read and ``UnicodeDecodeError`` if
    it is not text in ``encoding``; both are turned into messages by the caller.
    An unknown ``encoding`` raises ``LookupError``, which is left to propagate --
    a misspelled codec is a bug in the test and not a finding about the file.
    """
    return path.read_bytes().decode(encoding)


def _read_trouble(path: "Path", error: "OSError | UnicodeDecodeError", /) -> str:
    """Why a file's text could not be had, as a message clause. Failure path only."""
    if isinstance(error, UnicodeDecodeError):
        return (
            rendered(path)
            + " is not "
            + error.encoding
            + " text ("
            + error.reason
            + " at byte "
            + str(error.start)
            + ")"
        )
    return _trouble(path, error)


def _invisible_note(actual: str, expected: str, /) -> str:
    """Name a difference the two renderings do not show. Failure path only.

    ``Expected notes to have the text 'hello', but 'hello'`` is the worst message
    this module could produce, and three ordinary situations produce it: a
    byte-order mark, CRLF line endings, and trailing whitespace. Each gets said
    out loud, with the fix where there is one.
    """
    if actual.startswith("﻿") and actual[1:] == expected:
        return " (it starts with a byte-order mark; read it with encoding='utf-8-sig')"
    if actual.replace("\r\n", "\n").replace("\r", "\n") == expected.replace("\r\n", "\n").replace(
        "\r", "\n"
    ):
        return " (the two differ only in their line endings)"
    if actual.strip() == expected.strip():
        return " (the two differ only in surrounding whitespace)"
    return ""


def _text_difference(actual: str, expected: str, /) -> str:
    """The line-by-line difference between two file contents. Failure path only.

    Bounded by :data:`_MAX_DIFFED`, because ``difflib`` over a large fixture is
    the one way a failure message here could cost more than the test did.
    """
    if len(actual) > _MAX_DIFFED or len(expected) > _MAX_DIFFED:
        return ""
    return describe_difference(actual, expected)


class PurePathExpect[T: "PurePath"](Expect[T]):
    """Assertions answerable without a filesystem (``PurePath``).

    :class:`PathExpect` extends this with the ones that need a disk, mirroring
    ``Path``'s own inheritance from ``PurePath``.
    """

    __slots__ = ()

    # -- the pieces of a name ----------------------------------------------
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
            f"to have the name {_clipped(expected)}, "
            f"but {rendered(subject)} has the name {_clipped(subject.name)}",
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
            f"to have the stem {_clipped(expected)}, "
            f"but {rendered(subject)} has the stem {_clipped(subject.stem)}",
            because,
        )

    def has_suffix(self, expected: str, /, *, because: str = "") -> Self:
        """Assert the final suffix is ``expected``, leading dot included.

        ``.txt``, not ``txt``: that is how ``PurePath.suffix`` reports it, and a
        suffix without its dot is a claim no path could satisfy, so it raises
        ``ValueError`` rather than failing. Only the *final* suffix is compared,
        so ``archive.tar.gz`` has suffix ``.gz``.
        """
        _reject_bare_suffix(expected)
        subject = self._subject
        if subject.suffix == expected:
            return self
        return self._fail(
            f"to have the suffix {_clipped(expected)}, "
            f"but {rendered(subject)} has {_suffix_note(subject.suffix)}",
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
        _reject_bare_string(expected)
        for suffix in expected:
            _reject_bare_suffix(suffix)
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
            f"to have the suffixes {_names_preview(expected)}, "
            f"but {rendered(subject)} has {_names_preview(found)}",
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
            f"to have no suffix, but {rendered(subject)} has {_suffix_note(subject.suffix)}",
            because,
        )

    # -- absoluteness -------------------------------------------------------
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

    # -- one path against another ------------------------------------------
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
            f"to match the pattern {_clipped(pattern)}, but {rendered(subject)} does not", because
        )


def _suffix_note(suffix: str, /) -> str:
    """``the suffix '.gz'``, or ``no suffix`` for a path that has none. Failure path only.

    Rendered through the formatter registry, as the claimed suffix on the other
    side of the same sentence is: one message must not render the suffix that
    was wanted and the suffix that was found two different ways.
    """
    if not suffix:
        return "no suffix"
    return "the suffix " + format_value(suffix)


class PathExpect(PurePathExpect[_Path]):
    """Assertions for a path that can be resolved against a filesystem.

    Everything in :class:`PurePathExpect` is here too, so one chain can go from
    the shape of a name to the bytes behind it. Read this module's docstring
    before adding to this class: a missing path, a dangling symbolic link and an
    ``OSError`` each have a settled answer, and they are the difference between
    a message that finds the bug and one that describes the symptom.
    """

    __slots__ = ()

    # -- presence -----------------------------------------------------------
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
            return self._fail(f"to exist, but {_trouble(subject, error)}", because, cause=error)
        return self._fail(f"to exist, but {_what_is_there(subject)}", because)

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
            return self._fail(f"not to exist, but {_trouble(subject, error)}", because, cause=error)
        return self._fail(f"not to exist, but {_what_is_there(subject)}", because)

    # -- what kind of thing is there ----------------------------------------
    def is_file(self, *, because: str = "") -> Self:
        """Assert a regular file is at the path, following symbolic links."""
        subject = self._subject
        try:
            if subject.is_file():
                return self
        except OSError as error:
            return self._fail(
                f"to be a regular file, but {_trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"to be a regular file, but {_what_is_there(subject)}", because)

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
                f"not to be a regular file, but {_trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be a regular file, but {_what_is_there(subject)}", because)

    def is_directory(self, *, because: str = "") -> Self:
        """Assert a directory is at the path, following symbolic links."""
        subject = self._subject
        try:
            if subject.is_dir():
                return self
        except OSError as error:
            return self._fail(
                f"to be a directory, but {_trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"to be a directory, but {_what_is_there(subject)}", because)

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
                f"not to be a directory, but {_trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be a directory, but {_what_is_there(subject)}", because)

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
                f"to be a symbolic link, but {_trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"to be a symbolic link, but {_what_is_there(subject)}", because)

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
                f"not to be a symbolic link, but {_trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be a symbolic link, but {_what_is_there(subject)}", because)

    # -- emptiness ----------------------------------------------------------
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
            if _emptiness(subject) is True:
                return self
        except OSError as error:
            return self._fail(f"to be empty, but {_trouble(subject, error)}", because, cause=error)
        return self._fail(f"to be empty, but {_fullness(subject)}", because)

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the path holds something: at least one byte, or at least one entry.

        Not the strict complement of :meth:`is_empty`, and for two reasons rather
        than one: a path with nothing at it fails both (see :meth:`is_not_file`),
        and so does a path that is neither a regular file nor a directory, since
        neither meaning of "empty" applies to a socket.
        """
        subject = self._subject
        try:
            if _emptiness(subject) is False:
                return self
        except OSError as error:
            return self._fail(
                f"not to be empty, but {_trouble(subject, error)}", because, cause=error
            )
        return self._fail(f"not to be empty, but {_vacancy(subject)}", because)

    # -- size ---------------------------------------------------------------
    def has_size(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the file holds exactly ``expected`` bytes.

        A size is a *file's* size. A directory's ``st_size`` is bookkeeping the
        filesystem chose -- 64 on one machine and 4096 on another -- so asserting
        on it would be asserting on the host, and a directory fails here with a
        message saying what it is. A negative expectation raises ``ValueError``.
        """
        _reject_unusable_size(expected)
        subject = self._subject
        try:
            info = subject.stat()
        except OSError as error:
            return self._fail(
                f"to hold {count_of(expected, 'byte')}, but {_trouble(subject, error)}",
                because,
                cause=error,
            )
        if S_ISREG(info.st_mode) and info.st_size == expected:
            return self
        return self._fail(
            f"to hold {count_of(expected, 'byte')}, "
            f"but {_size_note(subject, info.st_mode, info.st_size)}",
            because,
        )

    def has_size_greater_than(self, limit: int, /, *, because: str = "") -> Self:
        """Assert the file holds strictly more than ``limit`` bytes."""
        _reject_unusable_size(limit)
        subject = self._subject
        try:
            info = subject.stat()
        except OSError as error:
            return self._fail(
                f"to hold more than {count_of(limit, 'byte')}, but {_trouble(subject, error)}",
                because,
                cause=error,
            )
        if S_ISREG(info.st_mode) and info.st_size > limit:
            return self
        return self._fail(
            f"to hold more than {count_of(limit, 'byte')}, "
            f"but {_size_note(subject, info.st_mode, info.st_size)}",
            because,
        )

    def has_size_less_than(self, limit: int, /, *, because: str = "") -> Self:
        """Assert the file holds strictly fewer than ``limit`` bytes.

        A limit of zero raises ``ValueError``: no file is smaller than nothing,
        so the claim could never hold. :meth:`is_empty` is the zero-byte one.
        """
        _reject_unusable_size(limit)
        if limit == 0:
            raise ValueError("no file holds fewer than zero bytes; is_empty is the zero-byte claim")
        subject = self._subject
        try:
            info = subject.stat()
        except OSError as error:
            return self._fail(
                f"to hold fewer than {count_of(limit, 'byte')}, but {_trouble(subject, error)}",
                because,
                cause=error,
            )
        if S_ISREG(info.st_mode) and info.st_size < limit:
            return self
        return self._fail(
            f"to hold fewer than {count_of(limit, 'byte')}, "
            f"but {_size_note(subject, info.st_mode, info.st_size)}",
            because,
        )

    # -- contents -----------------------------------------------------------
    def has_text(self, expected: str, /, *, encoding: str = "utf-8", because: str = "") -> Self:
        """Assert the file's contents are exactly ``expected``.

        **Exactly** means the bytes are decoded and compared with nothing
        touched: no newline translation, no byte-order mark stripped, no
        trailing whitespace forgiven. So a CRLF file does not match LF text --
        which is the difference a Windows checkout introduces, and the one worth
        being told about. Because those differences are invisible in a rendered
        message, the failure names them: a byte-order mark, line endings, or
        surrounding whitespace each get said out loud, and anything else gets the
        library's ordinary line-by-line difference.

        The file is read as UTF-8. That is the encoding a test fixture is written
        in unless somebody decided otherwise, and ``encoding=`` is how they say
        so -- ``encoding="utf-8-sig"`` to drop a byte-order mark, ``"latin-1"``
        for bytes that must not be interpreted at all. Contents that are not text
        in that encoding fail with the codec's own reason and the offending byte
        rather than letting a ``UnicodeDecodeError`` out of an assertion; an
        encoding name that does not exist raises ``LookupError``, because that is
        a bug in the test.
        """
        subject = self._subject
        try:
            actual = _read_text(subject, encoding)
        except (OSError, UnicodeDecodeError) as error:
            return self._fail(
                f"to have the text {_clipped(expected)}, but {_read_trouble(subject, error)}",
                because,
                cause=error,
            )
        if actual == expected:
            return self
        return self._fail(
            f"to have the text {_clipped(expected)}, but {rendered(subject)} holds "
            f"{_clipped(actual)}{_invisible_note(actual, expected)}"
            f"{_text_difference(actual, expected)}",
            because,
        )

    def contains_text(
        self, expected: str, /, *, encoding: str = "utf-8", because: str = ""
    ) -> Self:
        """Assert ``expected`` appears somewhere in the file's contents.

        A plain substring test on the decoded text, read on the same terms as
        :meth:`has_text` -- exact line endings included, so a needle spelled with
        ``\\n`` will not be found in a CRLF file, and the failure says so.
        """
        subject = self._subject
        try:
            actual = _read_text(subject, encoding)
        except (OSError, UnicodeDecodeError) as error:
            return self._fail(
                f"to contain {_clipped(expected)}, but {_read_trouble(subject, error)}",
                because,
                cause=error,
            )
        if expected in actual:
            return self
        return self._fail(
            f"to contain {_clipped(expected)}, but {rendered(subject)} holds "
            f"{_clipped(actual)}{_missing_note(actual, expected)}",
            because,
        )

    def does_not_contain_text(
        self, unexpected: str, /, *, encoding: str = "utf-8", because: str = ""
    ) -> Self:
        """Assert ``unexpected`` appears nowhere in the file's contents."""
        subject = self._subject
        try:
            actual = _read_text(subject, encoding)
        except (OSError, UnicodeDecodeError) as error:
            return self._fail(
                f"not to contain {_clipped(unexpected)}, but {_read_trouble(subject, error)}",
                because,
                cause=error,
            )
        if unexpected not in actual:
            return self
        return self._fail(
            f"not to contain {_clipped(unexpected)}, but {rendered(subject)} holds "
            f"{_clipped(actual)}",
            because,
        )

    # -- directory entries --------------------------------------------------
    def has_child(self, name: str, /, *, because: str = "") -> Self:
        """Assert the directory holds an entry called ``name``.

        One entry, directly inside: ``"logs/app.log"``, ``".."`` and an absolute
        path all raise ``ValueError`` rather than being answered, because a child
        is a name and not a route. A dangling symbolic link counts as a child --
        it is an entry in the directory whatever it points at.
        """
        subject = self._subject
        child = _child_of(subject, name)
        try:
            if child.exists(follow_symlinks=False):
                return self
        except OSError as error:
            return self._fail(
                f"to have a child named {_clipped(name)}, but {_trouble(child, error)}",
                because,
                cause=error,
            )
        return self._fail(
            f"to have a child named {_clipped(name)}, but {_missing_child(subject)}", because
        )

    def does_not_have_child(self, name: str, /, *, because: str = "") -> Self:
        """Assert the directory holds no entry called ``name``.

        The subject has to be a directory: a file holds no entries, so answering
        "correct, no such child" for one would be a test that passed because the
        question was meaningless.
        """
        subject = self._subject
        child = _child_of(subject, name)
        try:
            if not subject.is_dir():
                return self._fail(
                    f"not to have a child named {_clipped(name)}, but {_what_is_there(subject)}",
                    because,
                )
            if not child.exists(follow_symlinks=False):
                return self
        except OSError as error:
            return self._fail(
                f"not to have a child named {_clipped(name)}, but {_trouble(subject, error)}",
                because,
                cause=error,
            )
        return self._fail(
            f"not to have a child named {_clipped(name)}, but {_what_is_there(child)}", because
        )

    # -- identity on disk ---------------------------------------------------
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
                f"but {_pair_trouble(subject, other, error)}",
                because,
                cause=error,
            )
        if same:
            return self
        return self._fail(
            f"to be the same file as {rendered(other)}, but was {rendered(subject)}", because
        )


def _size_note(path: "Path", mode: int, size: int, /) -> str:
    """Why a file's size is not the one that was claimed. Failure path only."""
    if S_ISREG(mode):
        return rendered(path) + " holds " + count_of(size, "byte")
    return _what_is_there(path)


def _missing_note(actual: str, expected: str, /) -> str:
    """Name a near-miss a substring search would otherwise leave unexplained.

    Failure path only. Text read from a file carries its real line endings, so a
    needle spelled with ``\\n`` misses a CRLF file entirely -- and the two
    renderings look identical unless somebody says why.
    """
    normalised = actual.replace("\r\n", "\n").replace("\r", "\n")
    if expected in normalised:
        return " (the file uses CRLF line endings; the text is there with those)"
    if expected.casefold() in actual.casefold():
        return " (it is there in a different case)"
    return ""
