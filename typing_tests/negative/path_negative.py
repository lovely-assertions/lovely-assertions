"""Every marked line here must be rejected by pyright and mypy.

**This file is why there are two path subjects.** ``PurePath`` is string algebra
and ``Path`` is string algebra plus a disk, so ``expect(PurePosixPath("/a")).exists()``
would type-check under a single folded subject and then fail at runtime with an
``AttributeError`` -- the exact class of bug the library exists to make
impossible. Every filesystem assertion is therefore listed below on a pure
subject, one per line, and the checkers have to refuse all of them.

The rest rules out the operand mistakes: a string where a path belongs (the
whole point of a path type is that it is not a string), a size that is not a
number, and a bare string of suffixes -- which is a ``Sequence[str]`` and would
otherwise be compared one character at a time.
"""

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import assert_type

from lovely_assertions import expect
from lovely_assertions._path import PathExpect, PurePathExpect


def the_filesystem_catalogue_is_out_of_reach_of_a_pure_path(pure: PurePosixPath) -> None:
    """The headline: a pure path cannot be asked anything that needs a disk."""
    expect(pure).exists()  # expect-error: `PurePath` has no filesystem
    expect(pure).does_not_exist()  # expect-error
    expect(pure).is_file()  # expect-error
    expect(pure).is_not_file()  # expect-error
    expect(pure).is_directory()  # expect-error
    expect(pure).is_not_directory()  # expect-error
    expect(pure).is_symlink()  # expect-error
    expect(pure).is_not_symlink()  # expect-error
    expect(pure).is_empty()  # expect-error
    expect(pure).is_not_empty()  # expect-error
    expect(pure).has_size(0)  # expect-error
    expect(pure).has_size_greater_than(0)  # expect-error
    expect(pure).has_size_less_than(1)  # expect-error
    expect(pure).has_text("hello")  # expect-error
    expect(pure).contains_text("hello")  # expect-error
    expect(pure).does_not_contain_text("hello")  # expect-error
    expect(pure).has_child("app.log")  # expect-error
    expect(pure).does_not_have_child("app.log")  # expect-error
    expect(pure).is_same_file_as(Path("/a"))  # expect-error


def a_windows_flavour_is_no_more_a_filesystem_than_a_posix_one(pure: PureWindowsPath) -> None:
    expect(pure).exists()  # expect-error
    expect(pure).has_text("hello")  # expect-error


def the_pure_catalogue_stays_reachable_from_a_pure_path(pure: PurePosixPath) -> None:
    """A sanity line, unmarked: the split must not have cost the pure assertions."""
    expect(pure).is_absolute().and_.has_suffix(".txt").and_.matches_pattern("*.txt")


def a_path_is_not_a_string(path: Path, pure: PurePosixPath) -> None:
    """The whole point of a path type is that it is not a string."""
    expect(pure).is_relative_to("/var")  # expect-error: a string is not a path
    expect(pure).is_not_relative_to("/var")  # expect-error
    expect(pure).has_parent("/var")  # expect-error
    expect(path).is_same_file_as("/var/log/app.log")  # expect-error


def a_size_is_a_number_of_bytes(path: Path) -> None:
    expect(path).has_size("3")  # expect-error: a size is an `int`
    expect(path).has_size_greater_than("3")  # expect-error
    expect(path).has_size_less_than(1.5)  # expect-error: bytes do not come in halves
    expect(path).has_size(None)  # expect-error


def a_run_of_suffixes_is_not_one_string(pure: PurePosixPath) -> None:
    """``".tar.gz"`` is a ``Sequence[str]``; the signature refuses it anyway."""
    expect(pure).has_suffixes(".tar.gz")  # expect-error: a bare string, read as characters
    expect(pure).has_suffixes(".gz")  # expect-error
    expect(pure).has_suffixes([1, 2])  # expect-error: suffixes are strings


def the_name_pieces_are_strings(pure: PurePosixPath) -> None:
    expect(pure).has_name(PurePosixPath("app.txt"))  # expect-error: a name is a `str`
    expect(pure).has_stem(None)  # expect-error
    expect(pure).has_suffix(3)  # expect-error


def because_is_keyword_only(path: Path, pure: PurePosixPath) -> None:
    expect(pure).is_absolute("a reason")  # expect-error: `because` is keyword-only
    expect(pure).has_suffix(".txt", "a reason")  # expect-error
    expect(path).exists("a reason")  # expect-error
    expect(path).has_text("hello", "utf-8")  # expect-error: the encoding is keyword-only
    expect(pure).matches_pattern("*.txt", True)  # expect-error: so is case sensitivity


def the_operand_kinds_are_not_interchangeable(path: Path) -> None:
    """The remaining ways to hand an assertion the wrong sort of thing."""
    expect(path).has_child(Path("app.log"))  # expect-error: a child is a name, not a path
    expect(path).has_text("hello", encoding=None)  # expect-error: an encoding is named by a `str`
    expect(path).contains_text(b"hello")  # expect-error: bytes are not text


def the_no_operand_assertions_take_no_operand(path: Path, pure: PurePosixPath) -> None:
    expect(pure).has_no_suffix(".txt")  # expect-error
    expect(pure).is_relative(True)  # expect-error
    expect(path).is_empty(0)  # expect-error
    expect(path).does_not_exist(path)  # expect-error


def the_two_subjects_are_not_interchangeable(path: Path, pure: PurePosixPath) -> None:
    assert_type(expect(path), PurePathExpect[Path])  # expect-error: it is the richer subject
    assert_type(expect(pure), PathExpect)  # expect-error: no disk behind a `PurePath`
    assert_type(expect(pure).subject, Path)  # expect-error: the flavour is kept


def a_pure_subject_is_not_a_filesystem_one(pure: PurePosixPath) -> None:
    """A helper that needs a disk must not accept a subject that has none."""

    def inspect(subject: PathExpect) -> None:
        subject.exists()

    inspect(expect(pure))  # expect-error
