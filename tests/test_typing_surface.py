"""The typing surface is a tested surface.

A green runtime suite proves nothing about what pyright and mypy infer, so the
static behaviour gets its own tests. There are two halves:

*Positive* -- ``typing_tests/positive/`` must be **clean** under both checkers.
That half is enforced by the main ``pyright`` and ``mypy`` runs, which include
that directory.

*Negative* -- ``typing_tests/negative/`` must **fail**, exactly where we say it
does. Without this half the positive half is worthless: a harness that cannot
detect a wrong ``assert_type`` is a harness that rubber-stamps. Each line that
must be rejected carries a marker::

    assert_type(expect("x"), int)             # expect-error
    assert_type(expect("x"), int)             # expect-error: and why, in prose
    assert_type(expect("x"), int)             # expect-error(pyright)
    assert_type(expect("x"), int)             # expect-error(mypy): mypy alone rejects it

An unqualified marker means *both* checkers must reject the line; the parenthesised
form names one, for the places where the two are documented to disagree. Anything
after a colon is a note for the reader. The harness is symmetric: a marked line that
is not reported fails the test, and a reported line that is not marked fails it too.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final, NamedTuple, TypedDict, cast

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
NEGATIVE_DIR: Final = REPO_ROOT / "typing_tests" / "negative"
POSITIVE_DIR: Final = REPO_ROOT / "typing_tests" / "positive"

PYRIGHT: Final = "pyright"
MYPY: Final = "mypy"
ALL_CHECKERS: Final = frozenset({PYRIGHT, MYPY})

_MARKER_RE: Final = re.compile(
    r"#\s*expect-error(?:\((?P<checker>pyright|mypy)\))?(?::\s*(?P<reason>.*))?\s*$"
)
_MYPY_ERROR_RE: Final = re.compile(r"^(?P<file>.+?):(?P<line>\d+): error:")

#: Belt as well as braces for the colour above: the flag is the instruction, and
#: this makes the parse correct whatever the invocation. Cheap, and the
#: alternative is a checker that silently verifies nothing.
_ANSI: Final = re.compile(r"\x1b\[[0-9;]*m")


class Expectation(NamedTuple):
    """One line that a checker is required to reject."""

    path: Path
    line: int  # 1-based, as both checkers report them
    checkers: frozenset[str]


#: Errors a checker reported, keyed by :func:`_key` rather than by ``Path``.
type ErrorMap = dict[str, set[int]]


def _key(path: Path | str, /) -> str:
    """One spelling of a file, so both sides of the lookup agree on it.

    A checker echoes whatever path it was handed, and the two ends of this
    comparison arrive from different places -- one from ``rglob``, one out of a
    subprocess's stdout. On a case-insensitive filesystem those can differ in the
    drive letter's case or in the separator while naming the same file, and a
    plain ``Path`` key then silently matches nothing: the map comes back empty,
    which reads as "the checker accepted everything" rather than as "the lookup
    missed". ``normcase`` is a no-op on POSIX and folds exactly those differences
    on Windows.
    """
    return os.path.normcase(str(Path(path).resolve()))


class _Position(TypedDict):
    line: int  # 0-based in pyright's JSON output
    character: int


class _Range(TypedDict):
    start: _Position
    end: _Position


class _Diagnostic(TypedDict):
    file: str
    severity: str
    range: _Range


class _PyrightReport(TypedDict):
    generalDiagnostics: list[_Diagnostic]


def _negative_files() -> list[Path]:
    return sorted(p for p in NEGATIVE_DIR.rglob("*.py") if p.name != "__init__.py")


def _collect_expectations() -> list[Expectation]:
    expectations: list[Expectation] = []
    for path in _negative_files():
        for offset, text in enumerate(path.read_text(encoding="utf-8").splitlines()):
            match = _MARKER_RE.search(text)
            if match is None:
                continue
            checker = match.group("checker")
            checkers = ALL_CHECKERS if checker is None else frozenset({checker})
            expectations.append(Expectation(path, offset + 1, checkers))
    return expectations


def _tool(name: str) -> str:
    """Resolve a checker from the active virtualenv, falling back to PATH."""
    candidate = Path(sys.executable).parent / name
    if candidate.exists():
        return str(candidate)
    found = shutil.which(name)
    if found is None:  # pragma: no cover - environment problem, not a test outcome
        pytest.fail(f"{name} is not installed; the typing surface cannot be verified")
    return found


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    # `encoding` explicitly, rather than letting `text=True` pick the host
    # default: pyright indents the continuation lines of a diagnostic with
    # U+00A0, and its JSON report arrives as UTF-8 on every platform. Decoded
    # with a Windows ANSI code page instead, those bytes come back as mojibake --
    # or, on a multi-byte page, raise and take the whole harness with them.
    return subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture(scope="session")
def pyright_errors() -> ErrorMap:
    """Line numbers pyright reports as errors across the negative corpus."""
    files = [str(p) for p in _negative_files()]
    result = _run([_tool("pyright"), "--outputjson", *files])
    try:
        payload = cast("_PyrightReport", json.loads(result.stdout))
    except json.JSONDecodeError:  # pragma: no cover - pyright crashed
        pytest.fail(
            f"pyright produced no JSON.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    errors: ErrorMap = {}
    for diagnostic in payload["generalDiagnostics"]:
        if diagnostic["severity"] != "error":
            continue
        errors.setdefault(_key(diagnostic["file"]), set()).add(
            diagnostic["range"]["start"]["line"] + 1
        )
    return errors


@pytest.fixture(scope="session")
def mypy_errors() -> ErrorMap:
    """Line numbers mypy reports as errors across the negative corpus."""
    files = [str(p) for p in _negative_files()]
    result = _run(
        [
            _tool("mypy"),
            # Windows is where this matters. mypy disables colour when it sees a
            # pipe on Linux and macOS, and colourises anyway on Windows -- which
            # puts escape codes between the line number and the word `error:`,
            # so a pattern looking for the literal text matched nothing at all.
            # An empty map then read as "mypy accepted everything", and the
            # Windows typing surface went unverified while reporting green.
            "--no-color-output",
            "--no-incremental",
            "--cache-dir",
            str(REPO_ROOT / ".mypy_cache_negative"),
            *files,
        ]
    )
    errors: ErrorMap = {}
    for line in _ANSI.sub("", result.stdout).splitlines():
        match = _MYPY_ERROR_RE.match(line)
        if match is None:
            continue
        errors.setdefault(_key(REPO_ROOT / match.group("file")), set()).add(
            int(match.group("line"))
        )

    # An empty map is indistinguishable from "mypy accepted everything", and the
    # corpus exists to be rejected -- so nothing here can be right. Whatever went
    # wrong (mypy refused to start, aborted on a blocking error, wrote somewhere
    # this does not read, or printed a shape the pattern does not match), the
    # harness has to say what it saw rather than report a silent green.
    #
    # The pyright fixture above already fails loudly for the same reason; this
    # one used to return the empty map, which is how a checker that never ran
    # could look like a checker that agreed.
    if not errors:
        pytest.fail(
            "mypy reported no errors anywhere in the negative corpus, which cannot "
            "be right -- every file in it exists to be rejected.\n"
            f"exit status: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return errors


def _check(checker: str, reported: ErrorMap) -> None:
    expectations = _collect_expectations()
    for path in _negative_files():
        wanted = {e.line for e in expectations if e.path == path and checker in e.checkers}
        marked_for_other = {
            e.line for e in expectations if e.path == path and checker not in e.checkers
        }
        got = reported.get(_key(path), set())

        relative = path.relative_to(REPO_ROOT)
        missing = sorted(wanted - got)
        assert not missing, (
            f"{checker} accepted lines it must reject in {relative}: {missing}. "
            f"The negative corpus is what proves the positive corpus means anything."
        )
        # A line marked for the *other* checker only is allowed to error here too?
        # No: divergences are documented per checker, so an unexpected error is a
        # regression either way.
        unexpected = sorted(got - wanted - marked_for_other)
        assert not unexpected, (
            f"{checker} reported errors on unmarked lines in {relative}: {unexpected}. "
            f"Either the code is wrong or the line needs an `# expect-error` marker."
        )
        overreach = sorted(got & marked_for_other)
        assert not overreach, (
            f"{checker} rejected lines marked as a divergence for the other checker "
            f"in {relative}: {overreach}. The divergence no longer exists; drop the marker."
        )


def test_negative_corpus_is_not_empty() -> None:
    """A harness with nothing to reject would pass vacuously."""
    expectations = _collect_expectations()
    assert expectations, "typing_tests/negative contains no `# expect-error` markers"


def test_positive_corpus_is_not_empty() -> None:
    """Likewise for the half the main checker runs cover."""
    assert list(POSITIVE_DIR.rglob("*.py")), "typing_tests/positive is empty"


@pytest.mark.typing
def test_pyright_rejects_exactly_the_marked_lines(pyright_errors: ErrorMap) -> None:
    _check(PYRIGHT, pyright_errors)


@pytest.mark.typing
def test_mypy_rejects_exactly_the_marked_lines(mypy_errors: ErrorMap) -> None:
    _check(MYPY, mypy_errors)


@pytest.mark.typing
def test_the_published_types_are_complete_and_documented() -> None:
    """``--verifytypes``, which is the check a ``py.typed`` library is *for*.

    The whole premise here is that a user's checker can see everything, and
    pyright answers that precisely: every symbol reachable from ``__all__``, and
    whether its type is known, ambiguous or unknown.

    ``--ignoreexternal`` is required and load-bearing. Without it the score is
    hostage to typeshed -- ``Decimal`` and ``Fraction`` are reported partially
    unknown there, while ``expect(Decimal("1"))`` resolves to
    ``OrderedExpect[Decimal]`` here with no error. Judging this library on
    another distribution's stubs would make the number unreadable.

    The documentation count is asserted too, and it is not decoration. The
    surface an extension author reads first is ``can_handle`` and ``format`` on
    ``IterableFormatter`` and ``ObjectFormatter`` -- the two classes they are
    told to subclass -- so an undocumented method there costs more than an
    undocumented one anywhere else.
    """
    result = _run(
        [
            _tool("pyright"),
            "--verifytypes",
            "lovely_assertions",
            "--ignoreexternal",
            "--outputjson",
        ]
    )
    report = json.loads(result.stdout)["typeCompleteness"]
    assert report["completenessScore"] == 1.0, (
        f"type completeness is {report['completenessScore']:.1%}, not 100%. "
        f"{report['exportedSymbolCounts']} -- a symbol a user's checker cannot see "
        f"is a symbol this library did not really ship."
    )
    assert report["exportedSymbolCounts"]["withUnknownType"] == 0
    assert report["exportedSymbolCounts"]["withAmbiguousType"] == 0
    assert report["missingFunctionDocStringCount"] == 0, (
        f"{report['missingFunctionDocStringCount']} public functions have no docstring. "
        f"Every one of them is reachable from `__all__`, which is the surface an "
        f"extension author reads."
    )
    assert report["missingClassDocStringCount"] == 0
