"""Packaging invariants, cheap to keep and ruinous to retrofit.

A dependency that creeps in, a ``py.typed`` that stops shipping, an eager
``import re`` on the hot path: each one breaks a promise the library makes on its
front page -- no runtime dependencies, a distribution a checker can read, and an
import that costs nothing a passing assertion does not need.

The last three are about ``docs/reference/assertions.md``, and they are here for the same
reason. It is generated, so nothing fails when it stops being regenerated: the
document simply describes a smaller library than the one that ships, quietly,
for as long as nobody reads it against the code.
"""

import ast
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Final, Generic

import lovely_assertions
from _happy_calls import library_modules
from lovely_assertions import AssertionFailure

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

#: The generated reference, its generator, and the one command that rebuilds it.
#: Named once because three tests below have to say it, and a failure message
#: that names the wrong command is worse than one that names none.
REFERENCE: Final = REPO_ROOT / "docs" / "reference" / "assertions.md"
GENERATOR: Final = REPO_ROOT / "scripts" / "generate_reference.py"
REGENERATE: Final = "uv run python scripts/generate_reference.py"

#: Imported lazily, inside the function that needs them, because every one of
#: them is only ever reached on the failure path. Importing the package must not
#: pay for machinery that a suite of passing assertions never touches.
FAILURE_PATH_MODULES: Final = ("ast", "dataclasses", "difflib", "linecache", "re")

#: Not a failure-path module -- never wanted at all, and listed separately because
#: it is the only entry here that no line of this library mentions.
#:
#: ``annotationlib`` is CPython 3.14's deferred-annotation machinery, and it
#: arrives by a route that is invisible on 3.13: subscripting a generic with a
#: *string* builds a ``ForwardRef``, and building one imports it -- along with
#: ``ast`` and ``enum``. A class statement cannot dodge this by naming its base
#: as a string, because a base is evaluated when the class is created and so
#: cannot be a name only the checkers can see; the package uses PEP 695 aliases,
#: which are lazy, wherever such a base is wanted.
#:
#: ``ast`` in the tuple above already catches the same breakage. The name is here
#: so the next reader learns what to look for from the failure rather than from
#: the traceback.
ANNOTATION_MACHINERY: Final = ("annotationlib",)

#: Never imported at all, which is a stronger rule than the one above. These hold
#: the *value types* of the date, path and enum subjects -- types the library needs
#: for typing and never at runtime, because every assertion in those catalogues
#: works through a method on the subject it was handed. They arrive under
#: ``if TYPE_CHECKING:`` (PEP 695 bounds are lazily evaluated, so a class can be
#: parameterised on one of them without it being present), and ``_subjects.py``
#: finds the real classes through ``sys.modules`` when it has a value to dispatch.
#:
#: ``pathlib`` is what makes this load-bearing rather than tidy: it pulls
#: ``fnmatch`` and therefore ``re``, so importing the path subject eagerly would
#: quietly break the rule above on everyone's behalf.
SUBJECT_VALUE_MODULES: Final = ("datetime", "enum", "pathlib")

DEFERRED_MODULES: Final = FAILURE_PATH_MODULES + SUBJECT_VALUE_MODULES + ANNOTATION_MACHINERY


def test_package_ships_py_typed() -> None:
    """Without PEP 561's marker, users get none of the typing this library is for."""
    package_dir = Path(lovely_assertions.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_every_module_folds_its_frames_out_of_a_traceback() -> None:
    """The reader's traceback is theirs, not ours: every module folds its frames.

    pytest reads ``__tracebackhide__`` from a *frame's globals*, so one assignment
    per module folds every frame of that module out of an assertion failure --
    and a module that forgets it puts its own internals back in front of the line
    the reader wrote. Other tests check that the mechanism works where it is set;
    this one checks that the next module to be written remembers to set it.

    Two do not, and both are right. ``__init__`` re-exports and has no function
    to appear in a traceback, and ``_exceptions`` is where the hook itself lives:
    the failure is raised from ``_core``, so no frame of it is ever on the stack.
    """
    exempt = {"lovely_assertions", "lovely_assertions._exceptions"}
    missing = sorted(
        module.__name__
        for module in library_modules()
        if module.__name__ not in exempt and not hasattr(module, "__tracebackhide__")
    )
    assert not missing, (
        f"these modules do not set `__tracebackhide__ = hide_internal_frames`: {missing}. "
        f"Every frame of them will appear in the reader's traceback above their own "
        f"failing line."
    )


def test_public_api_is_exported_under_all() -> None:
    """``__all__`` is the public API; everything in it must actually resolve."""
    for name in lovely_assertions.__all__:
        assert hasattr(lovely_assertions, name), f"__all__ advertises missing name {name!r}"


def test_all_is_sorted() -> None:
    """Keeps diffs on the public API reviewable."""
    assert list(lovely_assertions.__all__) == sorted(lovely_assertions.__all__)


def test_the_failure_reads_as_the_package_it_comes_from() -> None:
    """The short-summary line is the one most people read; it must carry the message.

    pytest prints ``module.Class: message`` there, truncated to the terminal
    width. A rewritten bare ``assert`` gets its prefix stripped and reads
    ``assert 4 == 3``; a custom ``AssertionError`` subclass does not, so a long
    module path eats the line: at a narrow width ``lovely_assertions._excepti...``
    is not one character of the message, on a library whose whole claim is the
    message. Every character the prefix gives back is a character of the message.

    The short name is no fiction: it is what the class is exported as, and the
    path ``pickle`` resolves it by, which this checks because a wrong
    ``__module__`` breaks unpickling silently.
    """
    import pickle

    assert lovely_assertions.AssertionFailure.__module__ == "lovely_assertions"
    qualified = "lovely_assertions.AssertionFailure"
    assert f"{AssertionFailure.__module__}.{AssertionFailure.__qualname__}" == qualified
    restored = pickle.loads(pickle.dumps(AssertionFailure("boom")))  # noqa: S301
    assert type(restored) is AssertionFailure


def test_the_version_has_one_source() -> None:
    """``__version__`` is the version, and the wheel is built from that line.

    ``[project]`` declares ``dynamic = ["version"]`` and ``[tool.hatch.version]``
    points at the module, so there is nothing here to drift *from* -- which is
    exactly why this test reads the configuration rather than trusting it. A
    ``version = "..."`` put back into ``[project]`` would silently become the
    second source, and the module's line would go stale with nothing to say so.

    A literal rather than ``importlib.metadata.version()``: that reads the
    installed distribution's metadata off disk on first access, which is more
    than this whole package costs to import.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert "version" not in pyproject["project"], (
        "pyproject.toml declares a literal version again; it is `dynamic` and read "
        "from `lovely_assertions.__version__`, which is the one place it is written."
    )
    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/lovely_assertions/__init__.py"
    assert isinstance(lovely_assertions.__version__, str)
    assert lovely_assertions.__version__.count(".") >= 2, lovely_assertions.__version__


def test_zero_runtime_dependencies() -> None:
    """Zero runtime dependencies is a promise, not a preference, so it is pinned."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert pyproject["project"]["dependencies"] == []


def _module_level_imports(source: str) -> set[str]:
    """Top-level import targets only.

    Imports nested in a function, or guarded by ``if TYPE_CHECKING:``, do not run
    at import time, so they are exactly what this invariant permits.
    """
    imported: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            imported.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            imported.add(node.module.partition(".")[0])
    return imported


def test_no_module_level_import_of_failure_path_modules() -> None:
    """Importing the package must not import a failure-path module, checked statically.

    A runtime check cannot cover this on its own: CPython already has ``re`` and
    ``linecache`` in ``sys.modules`` before user code runs, so an eager import of
    either would be invisible to a delta measurement.
    """
    package_dir = Path(lovely_assertions.__file__).parent
    offenders: dict[str, list[str]] = {}
    for module_path in sorted(package_dir.rglob("*.py")):
        eager = _module_level_imports(module_path.read_text(encoding="utf-8"))
        found = sorted(eager.intersection(DEFERRED_MODULES))
        if found:
            offenders[module_path.name] = found
    assert not offenders, (
        f"module-level imports of failure-path modules: {offenders}. "
        f"Move them inside the function that uses them."
    )


def test_import_does_not_transitively_pull_in_failure_path_modules() -> None:
    """Complements the static check by catching imports pulled in indirectly.

    Runs under ``-S`` so that site initialisation does not preload ``re`` and
    mask a regression.
    """
    probe = (
        "import sys;"
        "sys.path.insert(0, 'src');"
        "before = frozenset(sys.modules);"
        "import lovely_assertions;"
        "print(repr(sorted(frozenset(sys.modules) - before)))"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-S", "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    newly_imported: set[str] = set(ast.literal_eval(result.stdout.strip()))
    offenders = sorted(newly_imported.intersection(DEFERRED_MODULES))
    assert not offenders, (
        f"importing lovely_assertions pulled in {offenders}; these belong on the failure path only"
    )


def _documented_names() -> set[str]:
    """Every identifier ``docs/reference/assertions.md`` spells inside a code span.

    The fenced examples come out first: a name that appears only as a local
    variable in one of them is not documented by it. What is left is the prose,
    the catalogue bullets and the tables -- the places where the document is
    actually making a claim about a name.
    """
    prose = re.sub(r"```.*?```", "", REFERENCE.read_text(encoding="utf-8"), flags=re.DOTALL)
    return {
        identifier
        for span in re.findall(r"`([^`\n]+)`", prose)
        for identifier in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", span)
    }


def _subject_classes() -> dict[str, type]:
    """The exported subjects: every public name that is an ``Expect``."""
    classes: dict[str, type] = {}
    for name in lovely_assertions.__all__:
        exported = getattr(lovely_assertions, name)
        if isinstance(exported, type) and issubclass(exported, lovely_assertions.Expect):
            classes[name] = exported
    return classes


def test_every_public_name_appears_in_the_reference() -> None:
    """``__all__`` is the public API, and the reference is where it is written up.

    A name that resolves but appears nowhere in the document is half-shipped.
    """
    documented = _documented_names()
    missing = [name for name in lovely_assertions.__all__ if name not in documented]
    assert not missing, (
        f"public names documented nowhere in docs/reference/assertions.md: {missing}. "
        f"Add them to TARGETS or EXTRAS in scripts/generate_reference.py, "
        f"then run `{REGENERATE}`."
    )


def test_every_assertion_on_every_subject_appears_in_the_reference() -> None:
    """Every assertion reachable on an exported subject must be written up.

    A new assertion on an already-documented subject moves nothing a class-level
    check can see, so the reference can fall arbitrarily far behind the library
    while still listing a subject for every section it has. Private base classes
    count: ``DateExpect`` really does offer ``is_before``, whichever class it
    happens to be written on.
    """
    documented = _documented_names()
    missing: dict[str, list[str]] = {}
    for name, subject in _subject_classes().items():
        undocumented = sorted(
            member
            for ancestor in subject.__mro__
            if ancestor not in (object, Generic)
            for member in vars(ancestor)
            if not member.startswith("_") and member not in documented
        )
        if undocumented:
            missing[name] = undocumented
    assert not missing, (
        f"assertions reachable on an exported subject and documented nowhere in "
        f"docs/reference/assertions.md: {missing}. Run `{REGENERATE}`."
    )


def test_reference_is_up_to_date_with_its_generator() -> None:
    """A reference that has drifted from the code is worse than no reference.

    Regenerated into a temporary file rather than over the committed one: a check
    that rewrites what it is checking passes by construction. The whole cost is
    one interpreter start and one document, so it runs in the default suite like
    everything else here.
    """
    with tempfile.TemporaryDirectory() as directory:
        regenerated = Path(directory) / "assertions.md"
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(GENERATOR), str(regenerated)],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"`{REGENERATE}` failed:\n{result.stderr}"
        fresh = regenerated.read_text(encoding="utf-8")
    assert fresh == REFERENCE.read_text(encoding="utf-8"), (
        f"docs/reference/assertions.md is out of date with scripts/generate_reference.py. "
        f"It is generated and never hand-edited: run `{REGENERATE}` and commit the result."
    )
