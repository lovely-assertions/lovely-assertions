"""``PurePathExpect`` and ``PathExpect``: the path catalogue, and the disk behind half of it.

Two things are being tested here that are not "does the assertion answer
correctly".

**The split is the feature.** A filesystem assertion on a ``PurePath`` subject is
a static error, and that is the whole reason there are two classes;
``typing_tests/negative/path_negative.py`` is where that half is proved, and this
file only pins the runtime shape of the hierarchy.

**A missing path is a different bug from a wrong path.** Most of what follows is
about the failure *text*: ``Expected report to be a regular file, but it was
not`` is produced by a path that is a directory, a path that is not there, and a
path whose parent cannot be searched, and telling those apart is the difference
between a message that finds the bug and one that restates the symptom. So the
messages are pinned character for character.

Every filesystem test uses ``tmp_path``. The symlink tests skip where the
platform will not make one rather than failing, and the permission tests skip
under a user that permissions do not apply to.
"""

import errno
import os
from collections.abc import Callable, Iterator
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from stat import S_IFDOOR
from types import SimpleNamespace
from typing import Final

import pytest

from _package import sources
from lovely_assertions import (
    AssertionFailure,
    Expect,
    _path,
    expect,
    formatting,
    soft_assertions,
)
from lovely_assertions import _path as _path_module
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path import PathExpect, PurePathExpect, _render
from lovely_assertions._path._render import rendered

ARCHIVE: Final = PurePosixPath("/var/backups/archive.tar.gz")


def _message(call: Callable[[], object]) -> str:
    """The rendered failure text of an assertion that is expected to fail."""
    with pytest.raises(AssertionFailure) as caught:
        call()
    return str(caught.value)


@pytest.fixture
def symlinks(tmp_path: Path) -> None:
    """Skip cleanly where the platform will not make a symbolic link."""
    probe = tmp_path / "_symlink_probe"
    try:
        probe.symlink_to(tmp_path / "_symlink_target")
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        pytest.skip("symbolic links are unavailable here")
    probe.unlink()


def _pathlib_reraises_a_refusal() -> bool:
    """Ask this interpreter's ``pathlib`` what it does with a permission denied.

    Asked rather than assumed: the answer changed between two supported versions,
    and a test that hard-codes either one goes red on the interpreter it was not
    written for.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as name:
        vault = Path(name) / "vault"
        vault.mkdir()
        inside = vault / "inside"
        inside.write_text("x", encoding="utf-8")
        vault.chmod(0o000)
        try:
            inside.exists()
        except OSError:
            return True
        else:
            return False
        finally:
            vault.chmod(0o700)


@pytest.fixture
def unprivileged() -> None:
    """Skip where POSIX permission bits do not decide who may read a file.

    Two such places. Under ``root`` the bits are advisory, and on Windows they
    are not the access-control mechanism at all -- ``chmod(0o000)`` leaves the
    owner able to read the file, so the refusal these tests provoke never
    happens and they would assert against a file that opened fine.
    """
    if os.name == "nt":  # pragma: no cover - depends on the platform
        pytest.skip("Windows does not enforce POSIX permission bits")
    if hasattr(os, "geteuid") and os.geteuid() == 0:  # pragma: no cover - depends on the runner
        pytest.skip("running as root; permission bits do not apply")


class Slug:
    """A scoped formatter, to prove the path messages reach the registry."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, PurePath)

    def format(self, value: object, /) -> str:
        return "<" + str(value).rsplit("/", 1)[-1] + ">"


class WalkCounted(list[str]):
    """A run of suffixes that counts how many times something walks it.

    ``list(...)`` over a *subclass* goes through the iterator protocol rather
    than the fast copy an exact list or tuple gets, so a copy taken on the way to
    a comparison shows up here as a walk. Indexing and ``len`` do not.
    """

    __slots__ = ("walks",)

    walks: int

    def __iter__(self) -> "Iterator[str]":
        self.walks += 1
        return super().__iter__()


class Shouted:
    """A scoped formatter for text, claiming the operands a path message quotes.

    ``Slug`` covers the path itself; this covers everything else a path message
    renders -- a name, a stem, a suffix, an entry in a directory listing -- all
    of which are ordinary strings.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, str)

    def format(self, value: object, /) -> str:
        return "<<" + str(value).upper() + ">>"


# ---------------------------------------------------------------------------
# The pieces of a name
# ---------------------------------------------------------------------------
def test_the_name_is_the_last_component() -> None:
    expect(ARCHIVE).has_name("archive.tar.gz")
    expect(PurePosixPath("/a/b/")).has_name("b")
    expect(PurePosixPath("/")).has_name("")
    expect(PurePosixPath("")).has_name("")


def test_a_wrong_name_reports_both() -> None:
    assert _message(lambda: expect(ARCHIVE).has_name("archive")) == (
        "Expected ARCHIVE to have the name 'archive',"
        " but '/var/backups/archive.tar.gz' has the name 'archive.tar.gz'."
    )


def test_the_stem_drops_one_suffix_and_not_all_of_them() -> None:
    """The surprise ``archive.tar.gz`` holds: ``stem`` is not "the name without suffixes"."""
    expect(ARCHIVE).has_stem("archive.tar")
    assert _message(lambda: expect(ARCHIVE).has_stem("archive")) == (
        "Expected ARCHIVE to have the stem 'archive',"
        " but '/var/backups/archive.tar.gz' has the stem 'archive.tar'."
    )


def test_the_suffix_is_the_last_one_and_the_suffixes_are_all_of_them() -> None:
    expect(ARCHIVE).has_suffix(".gz")
    expect(ARCHIVE).has_suffixes([".tar", ".gz"])
    expect(ARCHIVE).has_suffixes((".tar", ".gz"))


def test_a_wrong_suffix_reports_both() -> None:
    assert _message(lambda: expect(ARCHIVE).has_suffix(".tar")) == (
        "Expected ARCHIVE to have the suffix '.tar',"
        " but '/var/backups/archive.tar.gz' has the suffix '.gz'."
    )
    assert _message(lambda: expect(ARCHIVE).has_suffixes([".gz"])) == (
        "Expected ARCHIVE to have the suffixes ['.gz'],"
        " but '/var/backups/archive.tar.gz' has ['.tar', '.gz']."
    )


def test_a_tuple_of_suffixes_reads_exactly_as_the_list_of_the_same_ones() -> None:
    """The two spellings are one claim, so they cannot report it two ways."""
    from_list = _message(lambda: expect(ARCHIVE).has_suffixes([".tar", ".zip"]))
    from_tuple = _message(lambda: expect(ARCHIVE).has_suffixes((".tar", ".zip")))

    assert from_list == from_tuple
    assert from_tuple == (
        "Expected ARCHIVE to have the suffixes ['.tar', '.zip'],"
        " but '/var/backups/archive.tar.gz' has ['.tar', '.gz']."
    )


def test_a_run_of_suffixes_is_matched_in_order_and_to_the_end() -> None:
    """A prefix, a tail and a swap are three different wrong claims, not one."""
    assert _message(lambda: expect(ARCHIVE).has_suffixes([".tar"])) == (
        "Expected ARCHIVE to have the suffixes ['.tar'],"
        " but '/var/backups/archive.tar.gz' has ['.tar', '.gz']."
    )
    assert _message(lambda: expect(ARCHIVE).has_suffixes([".tar", ".gz", ".sig"])) == (
        "Expected ARCHIVE to have the suffixes ['.tar', '.gz', '.sig'],"
        " but '/var/backups/archive.tar.gz' has ['.tar', '.gz']."
    )
    assert _message(lambda: expect(ARCHIVE).has_suffixes([".gz", ".tar"])) == (
        "Expected ARCHIVE to have the suffixes ['.gz', '.tar'],"
        " but '/var/backups/archive.tar.gz' has ['.tar', '.gz']."
    )


def test_a_passing_run_of_suffixes_never_copies_the_sequence_it_was_given() -> None:
    """``==`` cannot match a list against a tuple, and the answer is not to copy one.

    A copy taken so that ``==`` can do the work is built on the *passing* path,
    where the library allocates nothing; the two runs are walked by index
    instead. Counted rather than measured in bytes, because neither measurement
    in ``benchmarks`` can see this particular copy: a two-item list comes off
    CPython's free list, and it is dwarfed anyway by the list ``PurePath.suffixes``
    builds to answer at all.
    """
    suffixes = WalkCounted([".tar", ".gz"])
    suffixes.walks = 0

    expect(ARCHIVE).has_suffixes(suffixes)

    assert suffixes.walks == 1, "the dotless-suffix guard walks it once, and nothing else may"


def test_a_suffix_written_without_its_dot_is_a_caller_bug() -> None:
    """It is not a false claim about this path; no path could ever satisfy it."""
    with pytest.raises(ValueError, match="leading dot") as caught:
        expect(ARCHIVE).has_suffix("gz")
    assert "did you mean '.gz'" in str(caught.value)
    assert not isinstance(caught.value, AssertionFailure)


def test_the_dotless_form_is_refused_inside_a_sequence_too() -> None:
    with pytest.raises(ValueError, match="leading dot"):
        expect(ARCHIVE).has_suffixes([".tar", "gz"])


def test_a_bare_string_of_suffixes_is_refused_rather_than_iterated() -> None:
    """``".tar.gz"`` is a ``Sequence[str]``; iterating it would compare characters."""
    with pytest.raises(TypeError, match="not one string"):
        expect(ARCHIVE).has_suffixes(".tar.gz")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def test_a_path_with_no_suffix_says_so_rather_than_naming_an_empty_one() -> None:
    expect(PurePosixPath("/etc/hosts")).has_no_suffix()
    expect(PurePosixPath(".gitignore")).has_no_suffix()
    expect(PurePosixPath(".gitignore")).has_suffixes([])
    hosts = PurePosixPath("/etc/hosts")
    assert _message(lambda: expect(hosts).has_suffix(".conf")) == (
        "Expected hosts to have the suffix '.conf', but '/etc/hosts' has no suffix."
    )


def test_a_dotfile_has_no_suffix_and_is_all_stem() -> None:
    """The leading dot starts the *name*; ``.gitignore`` is not a ``gitignore``."""
    expect(PurePosixPath(".gitignore")).has_stem(".gitignore").and_.has_no_suffix()


def test_has_no_suffix_names_the_suffix_it_found() -> None:
    assert _message(lambda: expect(ARCHIVE).has_no_suffix()) == (
        "Expected ARCHIVE to have no suffix,"
        " but '/var/backups/archive.tar.gz' has the suffix '.gz'."
    )


def test_an_empty_sequence_of_suffixes_asserts_there_are_none() -> None:
    """Not a vacuous call: it is :meth:`has_no_suffix` said with a list."""
    with pytest.raises(AssertionFailure, match="to have the suffixes \\[\\]"):
        expect(ARCHIVE).has_suffixes([])


# ---------------------------------------------------------------------------
# Absoluteness, relativity, parents
# ---------------------------------------------------------------------------
def test_absolute_and_relative_are_exact_complements() -> None:
    expect(PurePosixPath("/a")).is_absolute()
    expect(PurePosixPath("a")).is_relative()
    expect(PurePosixPath("")).is_relative()
    relative = PurePosixPath("a/b")
    absolute = PurePosixPath("/a/b")
    assert _message(lambda: expect(relative).is_absolute()) == (
        "Expected relative to be an absolute path, but was 'a/b'."
    )
    assert _message(lambda: expect(absolute).is_relative()) == (
        "Expected absolute to be a relative path, but was '/a/b'."
    )


def test_an_empty_path_is_a_dot() -> None:
    """``PurePosixPath("")`` has no parts and renders as ``.``; nothing here crashes on it."""
    empty = PurePosixPath("")
    expect(empty).has_name("").and_.has_no_suffix().and_.is_relative()
    assert _message(lambda: expect(empty).is_absolute()) == (
        "Expected empty to be an absolute path, but was '.'."
    )


def test_is_relative_to_is_prefix_algebra_and_not_a_walk() -> None:
    """No disk is touched, so ``..`` is a component rather than a movement."""
    expect(PurePosixPath("/a/b/c")).is_relative_to(PurePosixPath("/a"))
    expect(PurePosixPath("/a")).is_relative_to(PurePosixPath("/a"))
    expect(PurePosixPath("a/../b")).is_relative_to(PurePosixPath("a"))
    expect(PurePosixPath("/a")).is_not_relative_to(PurePosixPath("/b"))


def test_unrelated_paths_report_which_one_was_asked_about() -> None:
    logs = PurePosixPath("/var/log")
    assert _message(lambda: expect(logs).is_relative_to(PurePosixPath("/etc"))) == (
        "Expected logs to be relative to '/etc', but '/var/log' is not."
    )
    assert _message(lambda: expect(logs).is_not_relative_to(PurePosixPath("/var"))) == (
        "Expected logs not to be relative to '/var', but '/var/log' is."
    )


def test_two_flavours_are_never_relative_to_one_another() -> None:
    """Kept off the host's own rules: both flavours are constructible everywhere."""
    expect(PurePosixPath("/a/b")).is_not_relative_to(PureWindowsPath("/a"))


def test_the_parent_is_the_immediate_one() -> None:
    expect(ARCHIVE).has_parent(PurePosixPath("/var/backups"))
    expect(PurePosixPath("/")).has_parent(PurePosixPath("/"))
    expect(PurePosixPath("a")).has_parent(PurePosixPath("."))
    assert _message(lambda: expect(ARCHIVE).has_parent(PurePosixPath("/var"))) == (
        "Expected ARCHIVE to have the parent '/var',"
        " but '/var/backups/archive.tar.gz' has the parent '/var/backups'."
    )


def test_a_trailing_slash_is_not_part_of_the_path() -> None:
    expect(PurePosixPath("/a/b/")).has_name("b").and_.has_parent(PurePosixPath("/a"))


def test_dot_dot_is_a_component() -> None:
    expect(PurePosixPath("..")).has_name("..").and_.has_parent(PurePosixPath("."))


# ---------------------------------------------------------------------------
# `matches_pattern`: the right-anchored surprise
# ---------------------------------------------------------------------------
def test_a_relative_pattern_matches_the_tail_of_the_path() -> None:
    """The surprise: ``PurePath.match`` is anchored at the right, not the left."""
    expect(PurePosixPath("/var/log/app.txt")).matches_pattern("*.txt")
    expect(PurePosixPath("/var/log/app.txt")).matches_pattern("log/*.txt")


def test_a_pattern_anchored_at_the_left_has_to_name_every_component() -> None:
    """The other half of the same surprise, and the reason it is documented."""
    log = PurePosixPath("/var/log/app.txt")
    assert _message(lambda: expect(log).matches_pattern("/*.txt")) == (
        "Expected log to match the pattern '/*.txt', but '/var/log/app.txt' does not."
    )
    expect(log).matches_pattern("/var/*/*.txt")


def test_case_sensitivity_follows_the_flavour_unless_it_is_asked_for() -> None:
    """Both flavours exist on every host, so this says nothing about the machine."""
    expect(PureWindowsPath("C:/Users/X.TXT")).matches_pattern("*.txt")
    expect(PurePosixPath("/a/X.TXT")).matches_pattern("*.txt", case_sensitive=False)
    with pytest.raises(AssertionFailure):
        expect(PurePosixPath("/a/X.TXT")).matches_pattern("*.txt")
    with pytest.raises(AssertionFailure):
        expect(PureWindowsPath("C:/Users/X.TXT")).matches_pattern("*.txt", case_sensitive=True)


def test_an_empty_pattern_is_a_caller_bug() -> None:
    with pytest.raises(ValueError, match="must not be empty") as caught:
        expect(ARCHIVE).matches_pattern("")
    assert not isinstance(caught.value, AssertionFailure)


# ---------------------------------------------------------------------------
# Presence: nothing there, something there, and the third state
# ---------------------------------------------------------------------------
def test_exists_and_does_not_exist_answer_for_an_ordinary_path(tmp_path: Path) -> None:
    present = tmp_path / "present.txt"
    present.write_text("x", encoding="utf-8")
    expect(present).exists()
    expect(tmp_path / "absent.txt").does_not_exist()


def test_a_missing_path_is_named_rather_than_described(tmp_path: Path) -> None:
    absent = tmp_path / "absent.txt"
    assert _message(lambda: expect(absent).exists()) == (
        f"Expected absent to exist, but nothing is there at '{absent}'."
    )


def test_does_not_exist_says_what_is_in_the_way(tmp_path: Path) -> None:
    assert _message(lambda: expect(tmp_path).does_not_exist()) == (
        f"Expected tmp_path not to exist, but '{tmp_path}' is a directory."
    )


@pytest.mark.usefixtures("symlinks")
def test_a_dangling_link_is_a_third_state_and_both_presence_assertions_say_so(
    tmp_path: Path,
) -> None:
    """The classic bug. ``exists()`` follows the link and ``lstat`` does not."""
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "gone")
    assert _message(lambda: expect(dangling).exists()) == (
        f"Expected dangling to exist, but '{dangling}' is a symbolic link to nothing."
    )
    assert _message(lambda: expect(dangling).does_not_exist()) == (
        f"Expected dangling not to exist, but '{dangling}' is a symbolic link to nothing."
    )


# ---------------------------------------------------------------------------
# What kind of thing is there
# ---------------------------------------------------------------------------
def test_the_kind_assertions_pass_for_the_kind_they_name(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_text("x", encoding="utf-8")
    expect(document).is_file().and_.is_not_directory().and_.is_not_symlink()
    expect(tmp_path).is_directory().and_.is_not_file().and_.is_not_symlink()


def test_a_directory_where_a_file_was_wanted_says_which(tmp_path: Path) -> None:
    assert _message(lambda: expect(tmp_path).is_file()) == (
        f"Expected tmp_path to be a regular file, but '{tmp_path}' is a directory."
    )


def test_a_missing_path_never_says_the_kind_was_wrong(tmp_path: Path) -> None:
    """The headline behaviour: three different bugs must not share one message."""
    absent = tmp_path / "absent"
    subject = expect(absent, name="absent")
    for call, claim in (
        (subject.is_file, "to be a regular file"),
        (subject.is_directory, "to be a directory"),
        (subject.is_symlink, "to be a symbolic link"),
        (subject.is_not_file, "not to be a regular file"),
        (subject.is_not_directory, "not to be a directory"),
        (subject.is_not_symlink, "not to be a symbolic link"),
    ):
        assert _message(call) == (f"Expected absent {claim}, but nothing is there at '{absent}'.")


def test_a_negation_is_not_the_complement_of_its_assertion(tmp_path: Path) -> None:
    """A negation still needs something there: a mistyped path passes neither form."""
    absent = tmp_path / "absent"
    with pytest.raises(AssertionFailure):
        expect(absent).is_file()
    with pytest.raises(AssertionFailure):
        expect(absent).is_not_file()


def test_a_negation_names_what_it_found(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_text("x", encoding="utf-8")
    assert _message(lambda: expect(document).is_not_file()) == (
        f"Expected document not to be a regular file, but '{document}' is a regular file."
    )
    assert _message(lambda: expect(tmp_path).is_not_directory()) == (
        f"Expected tmp_path not to be a directory, but '{tmp_path}' is a directory."
    )


@pytest.mark.usefixtures("symlinks")
def test_a_broken_symlink_is_still_a_symlink(tmp_path: Path) -> None:
    """The classic bug this catalogue is most likely to get wrong."""
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "gone")
    expect(dangling).is_symlink()
    assert _message(lambda: expect(dangling).is_not_symlink()) == (
        f"Expected dangling not to be a symbolic link,"
        f" but '{dangling}' is a symbolic link to nothing."
    )


@pytest.mark.usefixtures("symlinks")
def test_a_link_to_a_directory_is_reported_as_one(tmp_path: Path) -> None:
    """``is_file`` follows the link, so the message has to say what it followed."""
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    expect(link).is_directory().and_.is_symlink()
    assert _message(lambda: expect(link).is_file()) == (
        f"Expected link to be a regular file, but '{link}' is a symbolic link to a directory."
    )


@pytest.mark.usefixtures("symlinks")
def test_a_link_to_a_file_is_a_file(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    expect(link).is_file().and_.is_symlink().and_.exists()


# ---------------------------------------------------------------------------
# Emptiness: one name, two meanings, and a third case that is neither
# ---------------------------------------------------------------------------
def test_an_empty_file_is_zero_bytes_and_an_empty_directory_has_no_entries(
    tmp_path: Path,
) -> None:
    blank = tmp_path / "blank.txt"
    blank.write_bytes(b"")
    hollow = tmp_path / "hollow"
    hollow.mkdir()
    expect(blank).is_empty()
    expect(hollow).is_empty()
    expect(tmp_path).is_not_empty()
    blank.write_text("x", encoding="utf-8")
    expect(blank).is_not_empty()


def test_a_full_file_reports_its_size_and_a_full_directory_its_entries(
    tmp_path: Path,
) -> None:
    document = tmp_path / "document.txt"
    document.write_text("hello", encoding="utf-8")
    assert _message(lambda: expect(document).is_empty()) == (
        f"Expected document to be empty, but '{document}' holds 5 bytes."
    )
    assert _message(lambda: expect(tmp_path).is_empty()) == (
        f"Expected tmp_path to be empty, but '{tmp_path}' holds ['document.txt']."
    )


def test_one_byte_is_reported_in_the_singular(tmp_path: Path) -> None:
    """A message that says "1 bytes" is a message nobody read."""
    document = tmp_path / "document.txt"
    document.write_bytes(b"x")
    assert "holds 1 byte." in _message(lambda: expect(document).is_empty())


def test_an_empty_thing_says_which_kind_of_empty_it_is(tmp_path: Path) -> None:
    blank = tmp_path / "blank.txt"
    blank.write_bytes(b"")
    hollow = tmp_path / "hollow"
    hollow.mkdir()
    assert _message(lambda: expect(blank).is_not_empty()) == (
        f"Expected blank not to be empty, but '{blank}' is an empty file."
    )
    assert _message(lambda: expect(hollow).is_not_empty()) == (
        f"Expected hollow not to be empty, but '{hollow}' is an empty directory."
    )


def test_a_directory_listing_is_capped_like_every_other_rendered_collection(
    tmp_path: Path,
) -> None:
    for index in range(12):
        (tmp_path / f"file{index:02d}").write_bytes(b"")
    message = _message(lambda: expect(tmp_path).is_empty())
    assert "'file00', 'file01'" in message
    assert "... 2 more]" in message
    with formatting(max_items=3):
        assert "... 9 more]" in _message(lambda: expect(tmp_path).is_empty())


def test_emptiness_has_no_answer_for_a_missing_path(tmp_path: Path) -> None:
    absent = tmp_path / "absent"
    assert _message(lambda: expect(absent).is_empty()) == (
        f"Expected absent to be empty, but nothing is there at '{absent}'."
    )
    assert _message(lambda: expect(absent).is_not_empty()) == (
        f"Expected absent not to be empty, but nothing is there at '{absent}'."
    )


@pytest.mark.usefixtures("symlinks")
def test_emptiness_has_no_answer_for_a_dangling_link_either(tmp_path: Path) -> None:
    """And it says *link*, not *absence*: the two are different bugs."""
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "gone")
    assert _message(lambda: expect(dangling).is_empty()) == (
        f"Expected dangling to be empty, but '{dangling}' is a symbolic link to nothing."
    )
    assert _message(lambda: expect(dangling).is_not_empty()) == (
        f"Expected dangling not to be empty, but '{dangling}' is a symbolic link to nothing."
    )


# ---------------------------------------------------------------------------
# Size
# ---------------------------------------------------------------------------
def test_the_size_assertions_answer_for_a_regular_file(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_bytes(b"hello")
    expect(document).has_size(5)
    expect(document).has_size_greater_than(4)
    expect(document).has_size_less_than(6)


def test_a_wrong_size_reports_the_real_one(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_bytes(b"hello")
    assert _message(lambda: expect(document).has_size(3)) == (
        f"Expected document to hold 3 bytes, but '{document}' holds 5 bytes."
    )
    assert _message(lambda: expect(document).has_size_greater_than(9)) == (
        f"Expected document to hold more than 9 bytes, but '{document}' holds 5 bytes."
    )
    assert _message(lambda: expect(document).has_size_less_than(2)) == (
        f"Expected document to hold fewer than 2 bytes, but '{document}' holds 5 bytes."
    )


def test_the_size_bounds_are_strict_at_the_boundary(tmp_path: Path) -> None:
    """ "More than 5" excludes 5, and "fewer than 5" excludes it too.

    Without this the two bounds could quietly become ``>=`` and ``<=`` -- the one
    mutation the rest of the size tests cannot see, because every other case sits
    a comfortable distance from the number it names.
    """
    document = tmp_path / "document.txt"
    document.write_bytes(b"hello")
    assert _message(lambda: expect(document).has_size_greater_than(5)) == (
        f"Expected document to hold more than 5 bytes, but '{document}' holds 5 bytes."
    )
    assert _message(lambda: expect(document).has_size_less_than(5)) == (
        f"Expected document to hold fewer than 5 bytes, but '{document}' holds 5 bytes."
    )
    expect(document).has_size_greater_than(4).and_.has_size_less_than(6)


def test_a_directory_has_no_meaningful_size(tmp_path: Path) -> None:
    """``st_size`` for a directory is the host's bookkeeping, not a fact about the tree."""
    assert _message(lambda: expect(tmp_path).has_size(0)) == (
        f"Expected tmp_path to hold 0 bytes, but '{tmp_path}' is a directory."
    )


def test_a_missing_file_has_no_size_either(tmp_path: Path) -> None:
    absent = tmp_path / "absent"
    assert _message(lambda: expect(absent).has_size(0)) == (
        f"Expected absent to hold 0 bytes, but nothing is there at '{absent}'."
    )


def test_a_negative_size_is_a_caller_bug(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_bytes(b"hello")
    calls: tuple[Callable[[], object], ...] = (
        lambda: expect(document).has_size(-1),
        lambda: expect(document).has_size_greater_than(-1),
        lambda: expect(document).has_size_less_than(-1),
    )
    for call in calls:
        with pytest.raises(ValueError, match="never negative") as caught:
            call()
        assert not isinstance(caught.value, AssertionFailure)


def test_a_file_smaller_than_nothing_is_a_caller_bug(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_bytes(b"hello")
    with pytest.raises(ValueError, match="fewer than zero bytes"):
        expect(document).has_size_less_than(0)


# ---------------------------------------------------------------------------
# Text: exactly what is in the file, and the differences nobody can see
# ---------------------------------------------------------------------------
def test_has_text_compares_the_whole_of_the_file(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("hello", encoding="utf-8")
    expect(notes).has_text("hello")
    expect(notes).contains_text("ell")
    expect(notes).does_not_contain_text("goodbye")


def test_a_difference_in_line_endings_is_said_out_loud(tmp_path: Path) -> None:
    """Read in binary on purpose: text mode would translate CRLF and hide this."""
    notes = tmp_path / "notes.txt"
    notes.write_bytes(b"first\r\nsecond")
    assert _message(lambda: expect(notes).has_text("first\nsecond")) == (
        f"Expected notes to have the text 'first\\nsecond',"
        f" but '{notes}' holds 'first\\r\\nsecond'"
        f" (the two differ only in their line endings)."
    )


def test_a_substring_missed_because_of_line_endings_says_so(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_bytes(b"first\r\nsecond")
    assert "(the file uses CRLF line endings; the text is there with those)" in _message(
        lambda: expect(notes).contains_text("first\nsecond")
    )
    expect(notes).contains_text("first\r\nsecond")


def test_a_substring_missed_only_by_case_says_so(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("Hello", encoding="utf-8")
    assert "(it is there in a different case)" in _message(
        lambda: expect(notes).contains_text("hello")
    )


def test_a_byte_order_mark_is_content_and_the_message_names_the_fix(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_bytes(b"\xef\xbb\xbfhello")
    assert _message(lambda: expect(notes).has_text("hello")) == (
        f"Expected notes to have the text 'hello', but '{notes}' holds '\\ufeffhello'"
        f" (it starts with a byte-order mark; read it with encoding='utf-8-sig')."
    )
    expect(notes).has_text("hello", encoding="utf-8-sig")


def test_surrounding_whitespace_is_named_too(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("hello\n", encoding="utf-8")
    assert "(the two differ only in surrounding whitespace)" in _message(
        lambda: expect(notes).has_text("hello")
    )


def test_a_real_difference_gets_the_librarys_own_diff(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("first\nsecond\nthird", encoding="utf-8")
    message = _message(lambda: expect(notes).has_text("first\nSECOND\nthird"))
    assert "the strings differ (- expected, + actual):" in message
    assert "-SECOND" in message
    assert "+second" in message


def test_bytes_that_are_not_text_do_not_escape_as_a_decode_error(tmp_path: Path) -> None:
    """A ``UnicodeDecodeError`` out of an assertion is a bad failure; this is the good one."""
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff\xfe\x00")
    assert _message(lambda: expect(blob).has_text("x")) == (
        f"Expected blob to have the text 'x',"
        f" but '{blob}' is not utf-8 text (invalid start byte at byte 0)."
    )
    expect(blob).has_text("ÿþ\x00", encoding="latin-1")


def test_the_decode_error_is_chained_rather_than_thrown_away(tmp_path: Path) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff")
    with pytest.raises(AssertionFailure) as caught:
        expect(blob).has_text("x")
    assert isinstance(caught.value.__cause__, UnicodeDecodeError)


def test_an_unknown_encoding_is_a_caller_bug(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("hello", encoding="utf-8")
    with pytest.raises(LookupError):
        expect(notes).has_text("hello", encoding="not-a-codec")


def test_reading_a_directory_as_text_reports_the_error_rather_than_raising(
    tmp_path: Path,
) -> None:
    """The reason in the message is the operating system's own, quoted verbatim.

    Which reason that is depends on the platform -- POSIX refuses a directory
    with "Is a directory", Windows with "Permission denied" -- so the expectation
    asks for it rather than naming one. Hard-coding either would pin the library
    to a sentence it did not write and does not control.
    """
    try:
        tmp_path.read_text(encoding="utf-8")
    except OSError as error:
        reason = error.strerror
    else:  # pragma: no cover - no platform the tests run on allows this
        pytest.skip("this platform reads a directory as text without complaining")
    assert _message(lambda: expect(tmp_path).has_text("x")) == (
        f"Expected tmp_path to have the text 'x', but '{tmp_path}' could not be read ({reason})."
    )


def test_a_missing_file_has_no_text(tmp_path: Path) -> None:
    absent = tmp_path / "absent.txt"
    subject = expect(absent, name="absent")
    for call, claim in (
        (lambda: subject.has_text("x"), "to have the text 'x'"),
        (lambda: subject.contains_text("x"), "to contain 'x'"),
        (lambda: subject.does_not_contain_text("x"), "not to contain 'x'"),
    ):
        assert _message(call) == (f"Expected absent {claim}, but nothing is there at '{absent}'.")


def test_a_large_file_is_clipped_rather_than_dumped_into_the_message(tmp_path: Path) -> None:
    """The message budget, applied to a file: a failure is a line, not the file.

    The budget is on what the library *chose* to put in the message, so the path
    is measured out of it. A path is quoted whole and deliberately never clipped
    -- a reader who cannot copy it cannot go and look -- and its length belongs
    to the host: a deeper temporary directory or a longer account name would
    otherwise fail this on a machine where nothing had changed but the username.
    """
    fat = tmp_path / "fat.txt"
    fat.write_text("a" * 5000, encoding="utf-8")
    message = _message(lambda: expect(fat).has_text("b"))
    assert len(message) - len(str(fat)) < 400
    assert "(truncated from 5000 characters)" in message


def test_a_large_file_gets_no_line_by_line_diff(tmp_path: Path) -> None:
    """``difflib`` over a multi-megabyte fixture would cost more than the test did."""
    fat = tmp_path / "fat.txt"
    fat.write_text("line\n" * 40_000, encoding="utf-8")
    assert len("line\n" * 40_000) > _render._MAX_DIFFED  # pyright: ignore[reportPrivateUsage]
    message = _message(lambda: expect(fat).has_text("nope"))
    assert "the strings differ" not in message


def test_does_not_contain_text_reports_the_haystack(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("hello", encoding="utf-8")
    assert _message(lambda: expect(notes).does_not_contain_text("ell")) == (
        f"Expected notes not to contain 'ell', but '{notes}' holds 'hello'."
    )


# ---------------------------------------------------------------------------
# Directory entries
# ---------------------------------------------------------------------------
def test_has_child_looks_one_level_down(tmp_path: Path) -> None:
    (tmp_path / "app.log").write_text("x", encoding="utf-8")
    (tmp_path / "logs").mkdir()
    expect(tmp_path).has_child("app.log").and_.has_child("logs")
    expect(tmp_path).does_not_have_child("absent.log")


def test_a_missing_child_reports_what_is_there_instead(tmp_path: Path) -> None:
    (tmp_path / "app.log").write_text("x", encoding="utf-8")
    assert _message(lambda: expect(tmp_path).has_child("other.log")) == (
        f"Expected tmp_path to have a child named 'other.log', but '{tmp_path}' holds ['app.log']."
    )


def test_an_empty_directory_says_it_is_empty_rather_than_listing_nothing(
    tmp_path: Path,
) -> None:
    assert _message(lambda: expect(tmp_path).has_child("app.log")) == (
        f"Expected tmp_path to have a child named 'app.log',"
        f" but '{tmp_path}' is an empty directory."
    )


def test_a_file_has_no_children_and_the_message_says_why(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_text("x", encoding="utf-8")
    assert _message(lambda: expect(document).has_child("anything")) == (
        f"Expected document to have a child named 'anything', but '{document}' is a regular file."
    )


def test_does_not_have_child_refuses_to_pass_on_something_that_is_not_a_directory(
    tmp_path: Path,
) -> None:
    """Otherwise it passes for a file, a socket and a typo alike, asserting nothing."""
    document = tmp_path / "document.txt"
    document.write_text("x", encoding="utf-8")
    assert _message(lambda: expect(document).does_not_have_child("anything")) == (
        f"Expected document not to have a child named 'anything',"
        f" but '{document}' is a regular file."
    )
    absent = tmp_path / "absent"
    assert _message(lambda: expect(absent).does_not_have_child("anything")) == (
        f"Expected absent not to have a child named 'anything', but nothing is there at '{absent}'."
    )


def test_an_unwanted_child_is_named_with_its_kind(tmp_path: Path) -> None:
    (tmp_path / "app.log").write_text("x", encoding="utf-8")
    assert _message(lambda: expect(tmp_path).does_not_have_child("app.log")) == (
        f"Expected tmp_path not to have a child named 'app.log',"
        f" but '{tmp_path / 'app.log'}' is a regular file."
    )


@pytest.mark.usefixtures("symlinks")
def test_a_dangling_link_is_still_a_child(tmp_path: Path) -> None:
    """It is an entry in the directory whatever it points at."""
    (tmp_path / "dangling").symlink_to(tmp_path / "gone")
    expect(tmp_path).has_child("dangling")


def test_a_child_is_a_name_and_not_a_route(tmp_path: Path) -> None:
    """Including the forms that *normalise* to a child rather than looking like one.

    ``"./app.log"`` and ``"app.log/"`` both join to the right entry, so a guard
    that only compared the joined parent would wave them through. A child is a
    name; anything that had to be normalised into one was a route.
    """
    for name in ("logs/app.log", "..", ".", "", "/etc", "./app.log", "app.log/"):
        with pytest.raises(ValueError, match="a child is the name of one") as caught:
            expect(tmp_path).has_child(name)
        assert not isinstance(caught.value, AssertionFailure)
    with pytest.raises(ValueError, match="a child is the name of one"):
        expect(tmp_path).does_not_have_child("logs/app.log")


# ---------------------------------------------------------------------------
# Identity on disk
# ---------------------------------------------------------------------------
def test_two_names_for_one_file_are_the_same_file(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_text("x", encoding="utf-8")
    expect(document).is_same_file_as(tmp_path / "." / "document.txt")


@pytest.mark.usefixtures("symlinks")
def test_a_link_is_the_same_file_as_its_target(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    expect(link).is_same_file_as(target)


def test_two_different_files_are_not(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("x", encoding="utf-8")
    right.write_text("x", encoding="utf-8")
    assert _message(lambda: expect(left).is_same_file_as(right)) == (
        f"Expected left to be the same file as '{right}', but was '{left}'."
    )


def test_a_missing_side_is_named_rather_than_raising(tmp_path: Path) -> None:
    """``Path.samefile`` raises ``FileNotFoundError``; an assertion must not."""
    present = tmp_path / "present.txt"
    present.write_text("x", encoding="utf-8")
    absent = tmp_path / "absent.txt"
    assert _message(lambda: expect(present).is_same_file_as(absent)) == (
        f"Expected present to be the same file as '{absent}', but nothing is there at '{absent}'."
    )
    assert _message(lambda: expect(absent).is_same_file_as(present)) == (
        f"Expected absent to be the same file as '{present}', but nothing is there at '{absent}'."
    )


# ---------------------------------------------------------------------------
# Permission problems are reported, not swallowed and not raw
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("unprivileged")
@pytest.mark.usefixtures("unprivileged")
def test_an_unreadable_file_reports_the_operating_systems_own_reason(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("x", encoding="utf-8")
    secret.chmod(0o000)
    try:
        message = _message(lambda: expect(secret).has_text("x"))
    finally:
        secret.chmod(0o600)
    assert message == (
        f"Expected secret to have the text 'x',"
        f" but '{secret}' could not be read (Permission denied)."
    )


@pytest.mark.usefixtures("unprivileged")
def test_the_operating_system_error_is_chained_onto_the_failure(tmp_path: Path) -> None:
    """Not swallowed: the traceback a permissions problem needs is still underneath."""
    secret = tmp_path / "secret.txt"
    secret.write_text("x", encoding="utf-8")
    secret.chmod(0o000)
    try:
        with pytest.raises(AssertionFailure) as caught:
            expect(secret).has_text("x")
    finally:
        secret.chmod(0o600)
    assert isinstance(caught.value.__cause__, PermissionError)


@pytest.mark.usefixtures("unprivileged")
def test_an_unsearchable_directory_does_not_claim_the_path_is_missing(tmp_path: Path) -> None:
    """``is_file`` answers ``False`` here too, and "it is not a file" would be a lie."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "inside.txt").write_text("x", encoding="utf-8")
    vault.chmod(0o000)
    try:
        message = _message(lambda: expect(vault / "inside.txt").is_file())
    finally:
        vault.chmod(0o700)
    assert "could not be read (Permission denied)" in message
    assert "nothing is there" not in message


@pytest.mark.usefixtures("unprivileged")
def test_an_unlistable_directory_reports_the_reason_when_asked_for_a_child(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    vault.chmod(0o000)
    try:
        message = _message(lambda: expect(vault).is_empty())
    finally:
        vault.chmod(0o700)
    assert "could not be read (Permission denied)" in message


# ---------------------------------------------------------------------------
# Things that are neither a file nor a directory
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("symlinks")
def test_a_symbolic_link_loop_is_reported_as_a_loop(tmp_path: Path) -> None:
    """``lstat`` succeeds, ``stat`` cannot: the message has to say which."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.symlink_to(right)
    right.symlink_to(left)
    message = _message(lambda: expect(left).is_file())
    assert message.startswith(
        f"Expected left to be a regular file, but '{left}' is a symbolic link"
    )
    assert "could not be followed (" in message
    expect(left).is_symlink()


def test_a_named_pipe_is_neither_empty_nor_full(tmp_path: Path) -> None:
    """ "Empty" has two meanings and a FIFO has neither; both assertions say so."""
    if not hasattr(os, "mkfifo"):  # pragma: no cover - platform dependent
        pytest.skip("named pipes are unavailable here")
    pipe = tmp_path / "pipe"
    os.mkfifo(pipe)
    assert _message(lambda: expect(pipe).is_empty()) == (
        f"Expected pipe to be empty, but '{pipe}' is a named pipe."
    )
    assert _message(lambda: expect(pipe).is_not_empty()) == (
        f"Expected pipe not to be empty, but '{pipe}' is a named pipe."
    )
    assert _message(lambda: expect(pipe).has_size(0)) == (
        f"Expected pipe to hold 0 bytes, but '{pipe}' is a named pipe."
    )
    expect(pipe).exists().and_.is_not_file().and_.is_not_directory()


def test_an_empty_needle_is_in_every_file(tmp_path: Path) -> None:
    """``StringExpect.contains("")`` says the same; two subjects must not disagree."""
    notes = tmp_path / "notes.txt"
    notes.write_text("hello", encoding="utf-8")
    expect(notes).contains_text("")
    expect("hello").contains("")
    with pytest.raises(AssertionFailure):
        expect(notes).does_not_contain_text("")


# ---------------------------------------------------------------------------
# Across the whole catalogue: a broken link is not an absence
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("symlinks")
def test_no_assertion_reports_a_dangling_link_as_a_missing_path(tmp_path: Path) -> None:
    """A dangling link is a third state, on every assertion and not just the obvious two.

    Every assertion that reaches the disk through ``stat`` gets a
    ``FileNotFoundError`` for a broken symbolic link -- the same exception a name
    with nothing at it produces -- and the two are different bugs. One that
    answered "nothing is there" would send the reader hunting for a file that was
    never the problem.
    """
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "gone")
    calls: list[tuple[str, Callable[[], object]]] = [
        ("exists", lambda: expect(dangling).exists()),
        ("does_not_exist", lambda: expect(dangling).does_not_exist()),
        ("is_file", lambda: expect(dangling).is_file()),
        ("is_directory", lambda: expect(dangling).is_directory()),
        ("is_empty", lambda: expect(dangling).is_empty()),
        ("is_not_empty", lambda: expect(dangling).is_not_empty()),
        ("has_size", lambda: expect(dangling).has_size(0)),
        ("has_size_greater_than", lambda: expect(dangling).has_size_greater_than(0)),
        ("has_size_less_than", lambda: expect(dangling).has_size_less_than(1)),
        ("has_text", lambda: expect(dangling).has_text("x")),
        ("contains_text", lambda: expect(dangling).contains_text("x")),
        ("does_not_contain_text", lambda: expect(dangling).does_not_contain_text("x")),
        ("has_child", lambda: expect(dangling).has_child("x")),
        ("does_not_have_child", lambda: expect(dangling).does_not_have_child("x")),
    ]
    for label, call in calls:
        message = _message(call)
        assert "is a symbolic link to nothing" in message, label
        assert "nothing is there" not in message, label


@pytest.mark.usefixtures("symlinks")
def test_a_broken_side_of_a_comparison_is_the_one_that_gets_named(tmp_path: Path) -> None:
    """``samefile`` says only that it failed, and blaming the wrong path is worse than silence.

    A dangling link is a directory entry that ``stat`` refuses, so an existence
    test walks straight past the guilty side -- and the message then reports the
    *other*, perfectly healthy, file as missing.
    """
    present = tmp_path / "present.txt"
    present.write_text("x", encoding="utf-8")
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "gone")
    assert _message(lambda: expect(present).is_same_file_as(dangling)) == (
        f"Expected present to be the same file as '{dangling}',"
        f" but '{dangling}' is a symbolic link to nothing."
    )
    assert _message(lambda: expect(dangling).is_same_file_as(present)) == (
        f"Expected dangling to be the same file as '{present}',"
        f" but '{dangling}' is a symbolic link to nothing."
    )


# ---------------------------------------------------------------------------
# Soft scopes
# ---------------------------------------------------------------------------
def test_a_soft_scope_collects_path_failures_and_keeps_chaining(tmp_path: Path) -> None:
    """Including the ones that report an operating system error, which raise nothing."""
    absent = tmp_path / "absent.txt"
    with soft_assertions() as scope:
        subject = expect(absent, name="absent")
        assert subject.is_file().and_.has_text("hello") is subject
        collected = scope.discard()
    assert collected == [
        f"Expected absent to be a regular file, but nothing is there at '{absent}'.",
        f"Expected absent to have the text 'hello', but nothing is there at '{absent}'.",
    ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def test_a_path_is_rendered_as_itself_and_not_as_its_repr() -> None:
    """``PosixPath('/etc/hosts')`` is not what a reader is looking for."""
    assert rendered(PurePosixPath("/etc/hosts")) == "'/etc/hosts'"
    hosts = PurePosixPath("/etc/hosts")
    assert "PosixPath" not in _message(lambda: expect(hosts).is_relative())


def test_a_registered_formatter_still_wins() -> None:
    with soft_assertions(formatters=(Slug(),)) as scope:
        log = PurePosixPath("/var/log/app.txt")
        expect(log).is_relative()
        collected = scope.discard()
    assert collected == ["Expected log to be a relative path, but was <app.txt>."]


def test_a_formatter_for_text_reaches_the_operands_a_path_message_quotes() -> None:
    """A name, a stem and a suffix are strings, and a project may spell them its own way.

    Rendering them with a bare ``repr`` would skip the registry for exactly the
    half of a path message that is not the path.
    """
    with soft_assertions(formatters=(Shouted(),)) as scope:
        expect(ARCHIVE, name="archive").has_name("report.txt")
        expect(ARCHIVE, name="archive").has_stem("report")
        expect(ARCHIVE, name="archive").has_suffix(".zip")
        collected = scope.discard()

    assert collected == [
        (
            "Expected archive to have the name <<REPORT.TXT>>,"
            " but '/var/backups/archive.tar.gz' has the name <<ARCHIVE.TAR.GZ>>."
        ),
        (
            "Expected archive to have the stem <<REPORT>>,"
            " but '/var/backups/archive.tar.gz' has the stem <<ARCHIVE.TAR>>."
        ),
        (
            "Expected archive to have the suffix <<.ZIP>>,"
            " but '/var/backups/archive.tar.gz' has the suffix <<.GZ>>."
        ),
    ]


def test_a_formatter_for_text_reaches_every_entry_of_a_rendered_list() -> None:
    """Both sides of a suffix run, and neither half of one list left in ``repr``."""
    with soft_assertions(formatters=(Shouted(),)) as scope:
        expect(ARCHIVE, name="archive").has_suffixes([".zip"])
        collected = scope.discard()

    assert collected == [
        (
            "Expected archive to have the suffixes [<<.ZIP>>],"
            " but '/var/backups/archive.tar.gz' has [<<.TAR>>, <<.GZ>>]."
        )
    ]


def test_a_formatter_for_text_reaches_a_directory_listing(tmp_path: Path) -> None:
    """The entries a filesystem message shows are strings too."""
    (tmp_path / "app.log").write_bytes(b"")
    with soft_assertions(formatters=(Shouted(),)) as scope:
        expect(tmp_path, name="workspace").has_child("missing.txt")
        collected = scope.discard()

    assert collected == [
        (
            "Expected workspace to have a child named <<MISSING.TXT>>,"
            f" but '{tmp_path}' holds [<<APP.LOG>>]."
        )
    ]


def test_a_clipped_operand_is_rendered_after_it_is_cut_not_before() -> None:
    """The budget bounds the value, so the elision is inside what the formatter is given.

    Rendering first and cutting the rendering would spend the budget on the
    quoting, and would let a formatter that lengthens a value shorten how much
    of it the reader gets to see.
    """
    long_name = "a" * 40
    with formatting(max_chars=8), soft_assertions(formatters=(Shouted(),)) as scope:
        expect(PurePosixPath("/var/spool/" + long_name), name="report").has_name("b" * 40)
        collected = scope.discard()

    assert collected == [
        (
            "Expected report to have the name <<BBBBBBBB...>> (truncated from 40 characters),"
            " but '/var/spool/" + long_name + "' has the name"
            " <<AAAAAAAA...>> (truncated from 40 characters)."
        )
    ]


# ---------------------------------------------------------------------------
# The subject hierarchy, chaining, and the shape every subject has
# ---------------------------------------------------------------------------
def test_the_filesystem_subject_is_a_pure_one() -> None:
    """``Path`` is a ``PurePath``, and the subjects mirror that exactly."""
    assert issubclass(PathExpect, PurePathExpect)
    assert issubclass(PurePathExpect, Expect)
    assert isinstance(expect(Path("/a")), PathExpect)
    assert isinstance(expect(PurePosixPath("/a")), PurePathExpect)
    assert not isinstance(expect(PurePosixPath("/a")), PathExpect)


def test_the_pure_subject_has_no_filesystem_assertions() -> None:
    """The runtime half of what ``typing_tests/negative/path_negative.py`` proves."""
    for name in ("exists", "is_file", "is_directory", "has_text", "has_size", "has_child"):
        assert hasattr(PathExpect, name)
        assert not hasattr(PurePathExpect, name), f"{name} must not reach a PurePath subject"


def test_neither_subject_carries_an_instance_dictionary() -> None:
    """Every subject in the library is ``__slots__``-ed, both of these included."""
    assert PurePathExpect.__slots__ == ()
    assert PathExpect.__slots__ == ()
    assert not hasattr(expect(PurePosixPath("/a")), "__dict__")
    assert not hasattr(expect(Path("/a")), "__dict__")


def test_every_assertion_hands_back_the_same_subject(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_text("hello", encoding="utf-8")
    subject = expect(document)
    chained = (
        subject.is_absolute()
        .and_.has_suffix(".txt")
        .and_.has_stem("document")
        .and_.exists()
        .and_.is_file()
        .and_.is_not_empty()
        .and_.has_size(5)
        .and_.contains_text("ell")
    )
    assert chained is subject
    assert subject.subject is document


def test_a_pure_subject_chains_too() -> None:
    subject = expect(ARCHIVE)
    chained = (
        subject.is_absolute()
        .and_.has_name("archive.tar.gz")
        .and_.has_suffixes([".tar", ".gz"])
        .and_.has_parent(PurePosixPath("/var/backups"))
        .and_.matches_pattern("*.gz")
    )
    assert chained is subject


def test_this_modules_frames_fold_out_of_an_assertion_traceback() -> None:
    """A failing assertion shows the reader's own line, not this module's frames.

    pytest reads ``__tracebackhide__`` from a frame's globals, so one
    module-level assignment folds every frame of ``_path.py`` out of the
    traceback. It has to be the callable rather than ``True``: a ``ValueError``
    raised in here -- a dotless suffix, an empty pattern -- wants those frames
    kept, and only a callable can answer the two cases differently.
    """
    assert _path.__tracebackhide__ is hide_internal_frames
    assert hide_internal_frames(SimpleNamespace(value=AssertionFailure("x"))) is True
    assert hide_internal_frames(SimpleNamespace(value=ValueError("x"))) is False


# ---------------------------------------------------------------------------
# The happy path and `because`
# ---------------------------------------------------------------------------
def test_passing_path_assertions_never_touch_the_failure_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A passing assertion never reaches the failure path, argument checks and all.

    ``tests/test_happy_path.py`` owns the general form. The ones here do work
    *before* the comparison -- a suffix guard, a size guard, a child name -- which
    is the obvious place to start building a message by accident.
    """

    def detonate(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a passing assertion reached the failure path")

    monkeypatch.setattr(Expect, "_fail", detonate)
    document = tmp_path / "document.txt"
    document.write_text("hello", encoding="utf-8")
    expect(document).has_suffix(".txt").and_.has_suffixes([".txt"])
    expect(tmp_path).has_no_suffix()
    expect(document).has_size(5).and_.has_size_greater_than(1).and_.has_size_less_than(9)
    expect(tmp_path).has_child("document.txt").and_.does_not_have_child("absent")
    expect(document).matches_pattern("*.txt").and_.is_relative_to(tmp_path)
    expect(document).has_text("hello").and_.contains_text("ell")
    expect(document).is_file().and_.is_not_directory().and_.is_not_empty()


_FAILING: Final[list[tuple[str, Callable[[Path], object]]]] = [
    ("has_name", lambda p: expect(p).has_name("nope", because="R")),
    ("has_stem", lambda p: expect(p).has_stem("nope", because="R")),
    ("has_suffix", lambda p: expect(p).has_suffix(".nope", because="R")),
    ("has_suffixes", lambda p: expect(p).has_suffixes([".nope"], because="R")),
    ("has_no_suffix", lambda p: expect(p / "x.txt").has_no_suffix(because="R")),
    ("is_absolute", lambda p: expect(PurePosixPath(p.name)).is_absolute(because="R")),
    ("is_relative", lambda p: expect(p).is_relative(because="R")),
    ("is_relative_to", lambda p: expect(p).is_relative_to(p / "deeper", because="R")),
    ("is_not_relative_to", lambda p: expect(p).is_not_relative_to(p.parent, because="R")),
    ("has_parent", lambda p: expect(p).has_parent(p, because="R")),
    ("matches_pattern", lambda p: expect(p).matches_pattern("*.nope", because="R")),
    ("exists", lambda p: expect(p / "absent").exists(because="R")),
    ("does_not_exist", lambda p: expect(p).does_not_exist(because="R")),
    ("is_file", lambda p: expect(p).is_file(because="R")),
    ("is_not_file", lambda p: expect(p / "absent").is_not_file(because="R")),
    ("is_directory", lambda p: expect(p / "absent").is_directory(because="R")),
    ("is_not_directory", lambda p: expect(p).is_not_directory(because="R")),
    ("is_symlink", lambda p: expect(p).is_symlink(because="R")),
    ("is_not_symlink", lambda p: expect(p / "absent").is_not_symlink(because="R")),
    ("is_empty", lambda p: expect(p).is_empty(because="R")),
    ("is_not_empty", lambda p: expect(p / "empty").is_not_empty(because="R")),
    ("has_size", lambda p: expect(p / "notes.txt").has_size(99, because="R")),
    (
        "has_size_greater_than",
        lambda p: expect(p / "notes.txt").has_size_greater_than(99, because="R"),
    ),
    ("has_size_less_than", lambda p: expect(p / "notes.txt").has_size_less_than(1, because="R")),
    ("has_text", lambda p: expect(p / "notes.txt").has_text("nope", because="R")),
    ("contains_text", lambda p: expect(p / "notes.txt").contains_text("nope", because="R")),
    (
        "does_not_contain_text",
        lambda p: expect(p / "notes.txt").does_not_contain_text("hello", because="R"),
    ),
    ("has_child", lambda p: expect(p).has_child("absent", because="R")),
    ("does_not_have_child", lambda p: expect(p).does_not_have_child("notes.txt", because="R")),
    (
        "is_same_file_as",
        lambda p: expect(p / "notes.txt").is_same_file_as(p / "other.txt", because="R"),
    ),
]


@pytest.mark.parametrize(
    "call", [call for _, call in _FAILING], ids=[label for label, _ in _FAILING]
)
def test_because_reaches_every_path_assertion(
    call: Callable[[Path], object], tmp_path: Path
) -> None:
    """Every assertion in the catalogue carries its ``because`` into the message."""
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "other.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "empty").mkdir()
    with pytest.raises(AssertionFailure, match="because R"):
        call(tmp_path)


def test_the_failing_table_covers_the_whole_catalogue() -> None:
    """A table that drifts behind the catalogue is a guard that stopped guarding."""
    catalogue = {
        name
        for owner in (PurePathExpect, PathExpect)
        for name in vars(owner)
        if not name.startswith("_")
    }
    assert catalogue - {label for label, _ in _FAILING} == set()


# ---------------------------------------------------------------------------
# When the filesystem will not answer
# ---------------------------------------------------------------------------
#: Every ``PathExpect`` assertion that has an ``except OSError`` branch, and the
#: call that reaches it. A branch missing from here builds a message no test ever
#: renders, so it could be neutered and the suite would stay green.
UNREADABLE_CALLS: Final[dict[str, Callable[[PathExpect], object]]] = {
    "exists": lambda subject: subject.exists(),
    "does_not_exist": lambda subject: subject.does_not_exist(),
    "is_file": lambda subject: subject.is_file(),
    "is_not_file": lambda subject: subject.is_not_file(),
    "is_directory": lambda subject: subject.is_directory(),
    "is_not_directory": lambda subject: subject.is_not_directory(),
    "is_symlink": lambda subject: subject.is_symlink(),
    "is_not_symlink": lambda subject: subject.is_not_symlink(),
    "is_empty": lambda subject: subject.is_empty(),
    "is_not_empty": lambda subject: subject.is_not_empty(),
    "has_size": lambda subject: subject.has_size(1),
    "has_size_greater_than": lambda subject: subject.has_size_greater_than(0),
    "has_size_less_than": lambda subject: subject.has_size_less_than(9),
    "has_text": lambda subject: subject.has_text("x"),
    "contains_text": lambda subject: subject.contains_text("x"),
    "does_not_contain_text": lambda subject: subject.does_not_contain_text("x"),
    "has_child": lambda subject: subject.has_child("c"),
    "does_not_have_child": lambda subject: subject.does_not_have_child("c"),
    "is_same_file_as": lambda subject: subject.is_same_file_as(Path(__file__)),
}

#: The one that passes rather than reporting, and it is not an oversight: a name
#: that cannot be resolved is not a name anything is at.
PASSES_WHEN_UNREADABLE: Final = frozenset({"does_not_exist"})


def _through_a_file(tmp_path: Path) -> Path:
    """A path whose parent is a regular file.

    On POSIX, ``stat`` on it raises ``NotADirectoryError`` -- an ``OSError`` that
    is *not* ``FileNotFoundError``, which is the branch under test. The obvious
    alternative is ``chmod 000``, which does nothing when the suite runs as root.

    Windows resolves the same path to a plain "not found" instead, so the branch
    is out of reach there and the test that uses this skips; the caller checks.
    """
    note = tmp_path / "note.txt"
    note.write_text("hi", encoding="utf-8")
    return note / "child"


@pytest.mark.parametrize("name", sorted(UNREADABLE_CALLS))
def test_a_filesystem_that_will_not_answer_says_so(name: str, tmp_path: Path) -> None:
    """The error's own words are the finding, and they are kept.

    "Not a directory" is what the reader needs; a message that said only "the
    assertion failed" would send them looking for a missing file.
    """
    target = _through_a_file(tmp_path)
    try:
        target.stat()
    except FileNotFoundError:  # pragma: no cover - depends on the platform
        pytest.skip("this platform reports a path through a file as merely missing")
    except OSError:
        pass
    else:  # pragma: no cover - no platform the tests run on answers this
        pytest.skip("this platform answers about a path whose parent is a file")
    subject = PathExpect(target)
    if name in PASSES_WHEN_UNREADABLE:
        assert UNREADABLE_CALLS[name](subject) is subject
        return
    with pytest.raises(AssertionFailure) as caught:
        UNREADABLE_CALLS[name](subject)
    assert "could not be read (Not a directory)" in str(caught.value), str(caught.value)
    # The exception rides along wherever the library is the one that provoked it.
    # Where `pathlib` swallowed it first -- `Path.exists()` answers False for a
    # `NotADirectoryError` rather than raising -- the reason is re-derived for the
    # message and there is no live exception at the raise site to attach.
    assert caught.value.__cause__ is None or isinstance(caught.value.__cause__, OSError)


def test_every_assertion_with_an_oserror_branch_is_in_the_table() -> None:
    """Read off the module, so a new one cannot be added without an exercise."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(_path_module))
    guarded = {
        node.name
        for klass in ast.walk(tree)
        if isinstance(klass, ast.ClassDef) and klass.name == "PathExpect"
        for node in klass.body
        if isinstance(node, ast.FunctionDef)
        and not node.name.startswith("_")
        and any(
            isinstance(handler, ast.ExceptHandler)
            and handler.type is not None
            and "OSError" in ast.unparse(handler.type)
            for handler in ast.walk(node)
        )
    }
    missing = sorted(guarded - set(UNREADABLE_CALLS))
    assert not missing, (
        f"these PathExpect assertions guard an OSError and have no unreadable-path "
        f"exercise: {missing}. Their failure message has never been rendered."
    )


# ---------------------------------------------------------------------------
# When the filesystem refuses rather than answering
# ---------------------------------------------------------------------------
#: Every ``PathExpect`` assertion that reaches the disk through one of
#: ``pathlib``'s convenience methods, and the expectation clause its message opens
#: with.
#:
#: ``Path.exists``, ``is_file``, ``is_dir`` and ``is_symlink`` answer ``False``
#: for exactly four errno values -- the ones that mean "there is nothing usable
#: at this name" -- and **re-raise** everything else. So each of these assertions
#: has two failure routes and they produce different sentences: the table above
#: reaches the one where ``pathlib`` swallowed the error and the reason had to be
#: worked out a second time, and this one reaches the ``except OSError`` branch,
#: where the live exception is still there to be attached with ``cause=``.
#:
#: A permission-denied parent directory is what separates them, which is why
#: every test here needs :func:`unprivileged`.
#: Whether ``pathlib`` still hands a refusal to its caller.
#:
#: Up to 3.13, ``Path.exists``, ``is_file``, ``is_dir`` and ``is_symlink`` answer
#: ``False`` for the four errnos that mean "there is nothing usable at this name"
#: and **re-raise** everything else -- so a permission-denied parent reaches the
#: assertion's own ``except OSError`` and the live exception is attached with
#: ``cause=``. 3.14 rewrote pathlib and those methods now swallow ``EACCES`` too,
#: answering ``False``. The assertion still fails and still names the reason,
#: because the message builder asks the filesystem a second time -- but it fails
#: through the other route, with no exception to chain.
#:
#: Gated explicitly rather than left to fail on the next release, and gated on
#: the behaviour rather than on the version, so it is the property that is being
#: named and not a number to be revisited.
_REFUSALS_REACH_THE_CALLER: Final = _pathlib_reraises_a_refusal()

refusal_is_visible = pytest.mark.skipif(
    not _REFUSALS_REACH_THE_CALLER,
    reason="this pathlib answers False for a permission denied instead of raising",
)


REFUSED_CALLS: Final[list[tuple[str, Callable[[PathExpect], object], str]]] = [
    ("exists", lambda subject: subject.exists(), "to exist"),
    ("does_not_exist", lambda subject: subject.does_not_exist(), "not to exist"),
    ("is_file", lambda subject: subject.is_file(), "to be a regular file"),
    ("is_not_file", lambda subject: subject.is_not_file(), "not to be a regular file"),
    ("is_directory", lambda subject: subject.is_directory(), "to be a directory"),
    ("is_not_directory", lambda subject: subject.is_not_directory(), "not to be a directory"),
    ("is_symlink", lambda subject: subject.is_symlink(), "to be a symbolic link"),
    ("is_not_symlink", lambda subject: subject.is_not_symlink(), "not to be a symbolic link"),
]


@refusal_is_visible
@pytest.mark.usefixtures("unprivileged")
@pytest.mark.parametrize(
    ("call", "clause"),
    [(call, clause) for _, call, clause in REFUSED_CALLS],
    ids=[name for name, _, _ in REFUSED_CALLS],
)
def test_a_refusal_reports_the_reason_and_keeps_the_exception(
    call: Callable[[PathExpect], object], clause: str, tmp_path: Path
) -> None:
    """A refusal is a problem with the machine, and neither answer that hides it is right.

    Letting it escape turns a failing assertion into a traceback about ``stat``,
    and folding it into "but it was not" reports a bug in the code under test
    that is not there. The reason goes in the sentence and the exception rides
    along underneath it.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    inside = vault / "inside.txt"
    inside.write_text("x", encoding="utf-8")
    vault.chmod(0o000)

    try:
        with pytest.raises(AssertionFailure) as caught:
            call(expect(inside, name="inside"))
    finally:
        vault.chmod(0o700)

    assert str(caught.value) == (
        f"Expected inside {clause}, but '{inside}' could not be read (Permission denied)."
    )
    assert isinstance(caught.value.__cause__, PermissionError)


def test_every_assertion_pathlib_can_refuse_has_a_refusal_exercise() -> None:
    """Read off the module, so a new one cannot be added without an exercise.

    ``UNREADABLE_CALLS`` cannot stand in for this. The path it uses trips
    ``ENOTDIR``, which is one of the four values these methods answer ``False``
    for, so the ``except OSError`` branch is never entered there and could be
    deleted with that table still green.

    Read off every module of the package rather than the one the subject is
    assembled in. ``inspect.getsource`` on a package hands back its ``__init__``,
    which declares no assertion at all -- the set below would have come out empty
    and the comparison would have been against nothing.
    """
    import ast

    answering_false = {"exists", "is_file", "is_dir", "is_symlink"}
    package = Path(_path_module.__file__).parent
    trees = [ast.parse(source.read_text(encoding="utf-8")) for source in sources(package)]
    reachable = {
        node.name
        for tree in trees
        for klass in ast.walk(tree)
        if isinstance(klass, ast.ClassDef)
        for node in klass.body
        if isinstance(node, ast.FunctionDef)
        and not node.name.startswith("_")
        and any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in answering_false
            for call in ast.walk(node)
        )
    }

    # The two child assertions are exercised on their own rather than through the
    # table, because a refusal there is about a path that is not the subject and
    # the two of them disagree about which one to name.
    assert reachable - {name for name, _, _ in REFUSED_CALLS} == {
        "has_child",
        "does_not_have_child",
    }
    assert {name for name, _, _ in REFUSED_CALLS} <= set(UNREADABLE_CALLS)


@refusal_is_visible
@pytest.mark.usefixtures("unprivileged")
def test_a_child_that_cannot_be_looked_at_is_the_path_that_gets_named(tmp_path: Path) -> None:
    """``has_child`` asked about the child, so the child is what the reader has to go and see."""
    vault = tmp_path / "vault"
    vault.mkdir()
    inside = vault / "inside.txt"
    inside.write_text("x", encoding="utf-8")
    vault.chmod(0o000)

    try:
        with pytest.raises(AssertionFailure) as caught:
            expect(vault).has_child("inside.txt")
    finally:
        vault.chmod(0o700)

    assert str(caught.value) == (
        f"Expected vault to have a child named 'inside.txt',"
        f" but '{inside}' could not be read (Permission denied)."
    )
    assert isinstance(caught.value.__cause__, PermissionError)


@refusal_is_visible
@pytest.mark.usefixtures("unprivileged")
def test_a_denied_child_lookup_names_the_directory_that_was_asked(tmp_path: Path) -> None:
    """``does_not_have_child`` asks the directory two questions, and either can be refused.

    So the directory is what the message names -- the one path that is certainly
    involved whichever of the two calls tripped. The mirror assertion blames the
    child instead, and the difference is deliberate rather than an oversight.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "inside.txt").write_text("x", encoding="utf-8")
    vault.chmod(0o000)

    try:
        with pytest.raises(AssertionFailure) as caught:
            expect(vault).does_not_have_child("inside.txt")
    finally:
        vault.chmod(0o700)

    assert str(caught.value) == (
        f"Expected vault not to have a child named 'inside.txt',"
        f" but '{vault}' could not be read (Permission denied)."
    )
    assert isinstance(caught.value.__cause__, PermissionError)


# ---------------------------------------------------------------------------
# When the disk says something the message builder did not plan for
# ---------------------------------------------------------------------------
def _lstat_saying_a_door(_self: Path, /) -> os.stat_result:
    """A ``Path.lstat`` reporting a Solaris door: a real file type with no noun here.

    Only ``st_mode`` carries meaning; the rest is the padding the structure wants.
    """
    return os.stat_result((S_IFDOOR, 0, 0, 1, 0, 0, 0, 0, 0, 0))


def _stat_that_answers_once(
    original: Callable[..., os.stat_result], /
) -> Callable[..., os.stat_result]:
    """A ``Path.stat`` that answers truthfully once and then refuses.

    Two of the message builders stat a **second** time, after the comparison has
    already been made, to say why the assertion failed. On a live filesystem that
    second call can fail where the first one did not -- another process removes
    the file, or takes the permission away -- and no arrangement of real files
    reaches it, because the first call would fail too and be reported by the
    assertion's own handler instead. So the race is arranged here.
    """
    answered = False

    def stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        nonlocal answered
        if answered:
            raise PermissionError(errno.EACCES, "Permission denied")
        answered = True
        return original(path, follow_symlinks=follow_symlinks)

    return stat


def _samefile_that_refuses(_self: Path, _other: object, /) -> bool:
    """A ``Path.samefile`` that fails without either side being at fault."""
    raise PermissionError(errno.EACCES, "Permission denied")


def test_a_file_type_with_no_noun_is_still_described(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``st_mode`` carries kinds this catalogue has no word for, and one must not go silent.

    A Solaris door and a BSD whiteout are both real values with no ``S_IS*``
    predicate here to claim them, and the honest answer to "what is at this path"
    is then that the filesystem is reporting something unnamed -- not an empty
    clause, and not a guess at the nearest noun.
    """
    strange = tmp_path / "strange"
    strange.touch()
    monkeypatch.setattr(Path, "lstat", _lstat_saying_a_door)

    message = _message(lambda: expect(strange).is_directory())
    monkeypatch.undo()

    assert message == (
        f"Expected strange to be a directory,"
        f" but '{strange}' is something the filesystem does not name."
    )


def test_a_file_that_stops_answering_after_the_comparison_reports_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``is_empty`` stats twice -- once to compare, once to say why -- and the second can fail."""
    notes = tmp_path / "notes.txt"
    notes.write_text("hello", encoding="utf-8")
    monkeypatch.setattr(Path, "stat", _stat_that_answers_once(Path.stat))

    message = _message(lambda: expect(notes).is_empty())
    monkeypatch.undo()

    assert message == (
        f"Expected notes to be empty, but '{notes}' could not be read (Permission denied)."
    )


def test_an_empty_file_that_stops_answering_after_the_comparison_reports_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same second stat, on ``is_not_empty``, whose message builder is the other one."""
    notes = tmp_path / "notes.txt"
    notes.touch()
    monkeypatch.setattr(Path, "stat", _stat_that_answers_once(Path.stat))

    message = _message(lambda: expect(notes).is_not_empty())
    monkeypatch.undo()

    assert message == (
        f"Expected notes not to be empty, but '{notes}' could not be read (Permission denied)."
    )


def test_a_comparison_that_fails_with_both_sides_readable_still_names_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``samefile`` does not say which side it tripped over, and the re-ask can clear both.

    A file that came back between the two calls leaves the library holding an
    error it cannot attribute. The message then falls back to the subject and the
    operating system's own words, rather than reporting a healthy path as broken
    or dropping the reason entirely.
    """
    left = tmp_path / "left.txt"
    left.write_text("a", encoding="utf-8")
    right = tmp_path / "right.txt"
    right.write_text("b", encoding="utf-8")
    monkeypatch.setattr(Path, "samefile", _samefile_that_refuses)

    with pytest.raises(AssertionFailure) as caught:
        expect(left).is_same_file_as(right)
    monkeypatch.undo()

    assert str(caught.value) == (
        f"Expected left to be the same file as '{right}',"
        f" but '{left}' could not be read (Permission denied)."
    )
    assert isinstance(caught.value.__cause__, PermissionError)
