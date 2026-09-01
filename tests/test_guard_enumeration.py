"""The guards over ``src/`` see every file in it, including files not there yet.

Several tests in this suite state a rule about *every module in the package* and
then go and find those modules themselves. That second half is the fragile one,
and it fails in a way the first half cannot survive: a walk that misses a file
does not report a smaller claim, it reports the same claim over fewer files. The
build stays green and now means less than it says.

While the package is one flat directory that mistake is invisible, because
``glob`` and ``rglob`` return the same list. It becomes visible only once a
module moves into a subpackage -- which is to say, only after the damage.

So this file guards the guards three ways, because no one way covers both now and
then. :func:`sources` and :func:`module_name` are exercised against a tree built
for the purpose, which is the only way to test subpackage handling while the real
package has no subpackages. The lists the guards actually build are compared
against the package as it is, which is what will catch the mistake once
subpackages exist. And the suite's own source is scanned for the shape of the
bug, which is what catches it before then.

What the scan does *not* recognise is worth stating, since a guard trusted past
its reach is the failure it exists to prevent: it matches a ``glob`` or ``rglob``
call whose pattern is written out at the call site. A walk built from a pattern
held in a variable, or spelled ``os.walk``, ``Path.iterdir`` or
``pkgutil.walk_packages``, goes through it untouched. The comparison against the
real package is what covers those, once there is a subpackage for it to bite on.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

import lovely_assertions
import test_docstring_examples
import test_source_conventions
from _happy_calls import library_modules
from _package import module_name, sources

TESTS: Final = Path(__file__).resolve().parent
SRC: Final = Path(lovely_assertions.__file__).parent

#: Walks in this suite that are over something other than the package, keyed by
#: the file they appear in as well as the name they are called on -- a bare name
#: would exempt any variable that happened to be spelled the same, in any file.
#: ``typing_tests`` and ``fuzz`` are separate trees with their own layouts, and
#: nothing about walking them says whether the package's guards are complete.
#: :func:`test_every_exemption_is_still_load_bearing` is what keeps this honest.
NOT_THE_PACKAGE: Final = frozenset(
    {
        ("test_typing_surface.py", "NEGATIVE_DIR"),
        ("test_typing_surface.py", "POSITIVE_DIR"),
        ("test_fuzzing.py", "drivers"),
    }
)

#: The lists the guards build, by the expression a reader would go and look at.
#: Parametrised rather than asserted together, so a failure names the guard that
#: lost a file instead of the fact that one of them did.
#:
#: Each list is turned into module *names* before it is compared, and each is
#: relativised against the root it was walked from rather than against :data:`SRC`.
#: Those roots are not always the same directory: this file and
#: ``test_docstring_examples`` reach the package through
#: ``lovely_assertions.__file__``, while ``test_source_conventions`` reads the
#: shipped text out of ``src/`` on purpose. In a checkout the two resolve to one
#: directory and the difference is invisible; installed from a wheel they do not,
#: and relativising one against the other raises rather than comparing.
GUARD_LISTS: Final = {
    "test_docstring_examples.MODULES": lambda: set(test_docstring_examples.MODULES),
    "test_source_conventions.MODULES": (
        lambda: {
            module_name(path, test_source_conventions.SRC)
            for path in test_source_conventions.MODULES
        }
    ),
    "_happy_calls.library_modules()": lambda: {module.__name__ for module in library_modules()},
}


def _package_tree(root: Path) -> Path:
    """A package with a module, a subpackage, and a module inside the subpackage."""
    package = root / "fake_package"
    (package / "_inner").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "_flat.py").write_text("", encoding="utf-8")
    (package / "_inner" / "__init__.py").write_text("", encoding="utf-8")
    (package / "_inner" / "_deep.py").write_text("", encoding="utf-8")
    return package


def _walks_of(source: str) -> list[tuple[int, str, str]]:
    """Every ``glob``/``rglob`` call over Python files, and the name it is called on.

    The pattern is read from positional *and* keyword arguments, and any pattern
    ending in ``.py`` counts: the rule is that the package is walked in one
    place, so a recursive walk written somewhere else is as much an offence as a
    non-recursive one.
    """
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"glob", "rglob"}:
            continue
        patterns = [*node.args, *(keyword.value for keyword in node.keywords)]
        if not any(
            isinstance(pattern, ast.Constant)
            and isinstance(pattern.value, str)
            and pattern.value.endswith(".py")
            for pattern in patterns
        ):
            continue
        receiver = node.func.value
        name = receiver.id if isinstance(receiver, ast.Name) else ast.unparse(receiver)
        found.append((node.lineno, node.func.attr, name))
    return found


def test_the_walk_reaches_a_module_inside_a_subpackage(tmp_path: Path) -> None:
    """The failure a non-recursive walk produces, reproduced against a real tree."""
    package = _package_tree(tmp_path)

    found = sources(package)

    assert [path.relative_to(package).as_posix() for path in found] == [
        "__init__.py",
        "_flat.py",
        "_inner/__init__.py",
        "_inner/_deep.py",
    ]


def test_the_walk_names_a_package_by_its_directory(tmp_path: Path) -> None:
    """``__init__.py`` is the package it sits in, not a module called ``__init__``.

    Both halves matter. Naming the root ``fake_package.__init__`` would import
    something real but spell it as nobody writes it; naming the subpackage's
    ``__init__`` after the file rather than the directory would leave the
    subpackage itself absent from every guard's list.
    """
    package = _package_tree(tmp_path)

    names = [module_name(path, package) for path in sources(package)]

    assert names == [
        "fake_package",
        "fake_package._flat",
        "fake_package._inner",
        "fake_package._inner._deep",
    ]


@pytest.mark.parametrize("guard", sorted(GUARD_LISTS), ids=lambda name: name)
def test_the_list_a_guard_builds_is_the_whole_package(guard: str) -> None:
    """A guard's own list of modules is the package, not a subset of it.

    This is the check that bites once the package has subpackages, and the reason
    it is worth writing before then: at that point the walks disagree, and
    whichever guard lost a file loses it without complaining.
    """
    expected = {module_name(path, SRC) for path in sources(SRC)}

    assert GUARD_LISTS[guard]() == expected


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ('SRC.glob("*.py")', [(1, "glob", "SRC")]),
        ('SRC.rglob("*.py")', [(1, "rglob", "SRC")]),
        ('SRC.glob("**/*.py")', [(1, "glob", "SRC")]),
        ('SRC.glob(pattern="*.py")', [(1, "glob", "SRC")]),
        ('SRC.glob("fuzz_*.py")', [(1, "glob", "SRC")]),
        ('SRC.glob("*.md")', []),
        ("SRC.iterdir()", []),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_the_scan_recognises_a_walk_over_python_files(
    pattern: str, expected: list[tuple[int, str, str]]
) -> None:
    """The scanner is tried against violations, not only against a clean tree.

    Every file in the suite passes the scan, so without this a scanner that
    returned nothing at all would look exactly like a working one.
    """
    assert _walks_of(pattern) == expected


def test_every_exemption_is_still_load_bearing() -> None:
    """An exemption whose walk is gone is a free pass waiting for the next walk.

    Pinning the count alone would not catch that: a name left behind after its
    call site went away leaves a slot that a walk over the package itself can be
    dropped into without the total ever changing.
    """
    stale = [
        f"  {module}: {receiver}"
        for module, receiver in sorted(NOT_THE_PACKAGE)
        if receiver not in {name for _, _, name in _walks_of((TESTS / module).read_text("utf-8"))}
    ]
    assert not stale, (
        "these exemptions no longer name a walk that exists:\n"
        + "\n".join(stale)
        + "\nDrop the entry rather than leaving a name nothing checks."
    )


def test_no_exemption_covers_the_package_itself() -> None:
    """The one substitution the exemption table must never accept.

    The walks this file exists to prevent bound the package to ``SRC``, so an
    entry naming it would re-blind the scan to precisely the bug it is here for
    -- and while the package is one flat directory, nothing else would notice.
    """
    package_roots = {"SRC", "SRC_DIR", "package", "package_dir"}

    assert not {receiver for _, receiver in NOT_THE_PACKAGE} & package_roots


@pytest.mark.parametrize(
    "module",
    [path for path in sources(TESTS) if path.name != "_package.py"],
    ids=lambda path: path.relative_to(TESTS).as_posix(),
)
def test_no_guard_walks_the_package_outside_the_shared_enumeration(module: Path) -> None:
    """One walk, in one place, so a subpackage has one thing left to get wrong.

    Scanned rather than trusted, because the defect this replaces was not a walk
    somebody wrote badly -- it was several walks written separately, of which two
    drifted. Sharing them only helps for as long as they stay shared.
    """
    where = module.relative_to(TESTS).as_posix()
    offences = [
        f"  {where}:{lineno}: {name}.{call}(...)"
        for lineno, call, name in _walks_of(module.read_text(encoding="utf-8"))
        if (module.name, name) not in NOT_THE_PACKAGE
    ]
    assert not offences, (
        f"{where} walks the package itself instead of using the shared enumeration:\n"
        + "\n".join(offences)
        + "\nCall `sources()` from `tests/_package.py`, which recurses into subpackages."
    )
