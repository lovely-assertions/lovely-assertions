"""``PurePathExpect[T]`` and ``PathExpect``: two subjects, one inheritance.

``pathlib`` has two kinds of path and only one of them can touch a disk, so the
library has two subjects and ``PathExpect`` inherits from ``PurePathExpect``
exactly as ``Path`` inherits from ``PurePath``. Three properties are pinned here:

* ``T`` survives every pure assertion, so ``.subject`` comes back as the flavour
  that went in -- a ``PurePosixPath`` stays a ``PurePosixPath`` and does not
  widen to ``PurePath``;
* a ``Path`` subject reaches **both** catalogues in one expression, because the
  string algebra is still true of a path that also exists;
* the operands are paths, not strings, which is what keeps ``"/tmp"`` out of an
  assertion whose whole subject is that paths are not strings.

``path_negative.py`` holds the half that matters most: every filesystem
assertion is a static error on a ``PurePath`` subject. That file is the entire
justification for there being two classes here rather than one.
"""

from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import assert_type

from lovely_assertions import expect
from lovely_assertions._path import PathExpect, PurePathExpect


def a_pure_path_gets_the_pure_subject(pure: PurePosixPath) -> None:
    assert_type(expect(pure), PurePathExpect[PurePosixPath])
    assert_type(expect(pure).is_absolute(), PurePathExpect[PurePosixPath])
    assert_type(expect(pure).is_absolute().subject, PurePosixPath)


def the_flavour_is_kept_rather_than_widened(
    posix: PurePosixPath, windows: PureWindowsPath, either: PurePath
) -> None:
    """The point of the parameter: a flavour does not flatten into ``PurePath``."""
    assert_type(expect(posix).is_relative().subject, PurePosixPath)
    assert_type(expect(windows).is_relative().subject, PureWindowsPath)
    assert_type(expect(either).is_relative().subject, PurePath)


def the_whole_pure_catalogue_chains(pure: PurePosixPath, other: PurePosixPath) -> None:
    subject = expect(pure)
    assert_type(subject.has_name("app.txt"), PurePathExpect[PurePosixPath])
    assert_type(subject.has_stem("app"), PurePathExpect[PurePosixPath])
    assert_type(subject.has_suffix(".txt"), PurePathExpect[PurePosixPath])
    assert_type(subject.has_suffixes([".tar", ".gz"]), PurePathExpect[PurePosixPath])
    assert_type(subject.has_suffixes((".tar", ".gz")), PurePathExpect[PurePosixPath])
    assert_type(subject.has_no_suffix(), PurePathExpect[PurePosixPath])
    assert_type(subject.is_absolute().and_.is_relative(), PurePathExpect[PurePosixPath])
    assert_type(subject.is_relative_to(other), PurePathExpect[PurePosixPath])
    assert_type(subject.is_not_relative_to(other), PurePathExpect[PurePosixPath])
    assert_type(subject.has_parent(other), PurePathExpect[PurePosixPath])
    assert_type(subject.matches_pattern("*.txt"), PurePathExpect[PurePosixPath])
    assert_type(
        subject.matches_pattern("*.txt", case_sensitive=True), PurePathExpect[PurePosixPath]
    )


def a_real_path_gets_the_filesystem_subject(path: Path) -> None:
    assert_type(expect(path), PathExpect)
    assert_type(expect(path).exists(), PathExpect)
    assert_type(expect(path).exists().subject, Path)


def one_expression_reaches_both_catalogues(path: Path, other: Path) -> None:
    """The reason the split is inheritance rather than two unrelated classes."""
    assert_type(
        expect(path)
        .is_absolute()
        .and_.has_suffix(".log")
        .and_.has_parent(other)
        .and_.exists()
        .and_.is_file()
        .and_.is_not_empty()
        .and_.has_size_greater_than(0)
        .and_.contains_text("started")
        .and_.is_same_file_as(other),
        PathExpect,
    )


def the_whole_filesystem_catalogue_chains(path: Path, other: Path) -> None:
    subject = expect(path)
    assert_type(subject.exists().and_.does_not_exist(), PathExpect)
    assert_type(subject.is_file().and_.is_not_file(), PathExpect)
    assert_type(subject.is_directory().and_.is_not_directory(), PathExpect)
    assert_type(subject.is_symlink().and_.is_not_symlink(), PathExpect)
    assert_type(subject.is_empty().and_.is_not_empty(), PathExpect)
    assert_type(subject.has_size(0), PathExpect)
    assert_type(subject.has_size_greater_than(0).and_.has_size_less_than(9), PathExpect)
    assert_type(subject.has_text("hello"), PathExpect)
    assert_type(subject.has_text("hello", encoding="utf-8-sig"), PathExpect)
    assert_type(subject.contains_text("ell").and_.does_not_contain_text("nope"), PathExpect)
    assert_type(subject.has_child("app.log").and_.does_not_have_child("other"), PathExpect)
    assert_type(subject.is_same_file_as(other), PathExpect)


def a_path_subject_is_a_pure_one(path: Path) -> None:
    """``PathExpect`` is a ``PurePathExpect[Path]``, so a helper can take either."""

    def inspect(subject: PurePathExpect[Path]) -> Path:
        return subject.is_absolute().subject

    assert_type(inspect(expect(path)), Path)


def because_reaches_every_path_assertion(path: Path, pure: PurePosixPath) -> None:
    assert_type(expect(pure).has_suffix(".txt", because="R"), PurePathExpect[PurePosixPath])
    assert_type(expect(pure).matches_pattern("*.txt", because="R"), PurePathExpect[PurePosixPath])
    assert_type(expect(path).exists(because="R"), PathExpect)
    assert_type(expect(path).has_text("hello", encoding="latin-1", because="R"), PathExpect)
    assert_type(expect(path).has_child("app.log", because="R"), PathExpect)


def the_inherited_catalogue_still_sees_the_parameter(pure: PurePosixPath, path: Path) -> None:
    """``PurePathExpect[T]`` is an ``Expect[T]``, so ``matches`` gets the real flavour."""

    def is_hidden(value: PurePosixPath) -> bool:
        return value.name.startswith(".")

    assert_type(expect(pure).matches(is_hidden), PurePathExpect[PurePosixPath])
    assert_type(expect(pure).is_equal_to(PurePosixPath("/a")), PurePathExpect[PurePosixPath])
    assert_type(expect(path).is_truthy(), PathExpect)
    assert_type(expect(path).is_one_of(Path("/a"), Path("/b")), PathExpect)


def the_subject_can_be_asked_for_by_name(pure: PurePosixPath, path: Path) -> None:
    """``as_=`` is the fully typed way to name a subject."""
    assert_type(expect(pure, as_=PurePathExpect[PurePosixPath]), PurePathExpect[PurePosixPath])
    assert_type(expect(path, as_=PathExpect).is_file(), PathExpect)
