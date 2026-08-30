"""The documentation is executable, and this is what makes that true.

Every page under ``docs/`` teaches by showing a snippet and the message it
produces. Both halves are claims about this library, and prose is the one part of
a repository nothing checks: a renamed assertion, a reworded message or a changed
default leaves the code green and the documentation quietly wrong. A reader who
follows a page that no longer works loses more than the page was ever worth.

So the pages are run. Each one is concatenated into a single script in document
order, executed, and every quoted result is compared against what actually came
out. The convention the pages follow is small enough to keep in your head:

* a ``python`` block is **executed**, in order, sharing the page's namespace, so
  a page reads top to bottom as one session;
* a ``text`` block immediately after it is that block's **expected output** --
  the failure message if the snippet raised, otherwise whatever it printed;
* ``bash`` and ``console`` blocks are shell transcripts and type-checker
  diagnostics. Neither is something this library produced, so neither is this
  guard's to check -- ``typing_tests/`` is where checker output is pinned.

**Each page runs in its own interpreter.** Registering a formatter mutates a
process-wide registry, and a page that demonstrates one would otherwise change
the messages every page after it quotes -- a failure landing on whichever page
happened to be next rather than on the page with the mistake in it.

**Each page runs from a real file, in an empty directory.** Subject naming reads
the caller's source through ``linecache``, and code handed to ``exec`` has no
source: every message would fall back to ``the value``. The empty directory is
what lets a page assert about a file that is not there.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
DOCS: Final = REPO_ROOT / "docs"

#: The reference is generated, and its generator already runs every example it
#: quotes and pastes back the message verbatim. Checking it here would test the
#: same thing twice and make a regeneration fail in two places at once.
GENERATED: Final = DOCS / "reference" / "assertions.md"

#: Marks a ``python`` block that must not run, and says why. Written as an HTML
#: comment so it is invisible in a rendered page, and read from the line above
#: the fence. A reason is not optional: an unexplained exemption is how a guard
#: stops covering the thing it was written for.
SKIP_DIRECTIVE: Final = re.compile(r"<!--\s*docs-test:\s*skip\s*[-:]\s*(?P<reason>[^>]+?)\s*-->")

#: Marks a block a type checker is *supposed* to reject, and says why. A page
#: that demonstrates a documented limitation -- a runtime-only registration, an
#: enum member that is deliberately not a number -- contains code that must not
#: check, and saying so beside it beats a list of line numbers kept elsewhere.
EXPECT_ERROR_DIRECTIVE: Final = re.compile(
    r"<!--\s*docs-test:\s*expect-error\s*[-:]\s*(?P<reason>[^>]+?)\s*-->"
)

_FENCE: Final = re.compile(r"^```(?P<language>[\w-]*)\n(?P<body>.*?)^```", re.MULTILINE | re.DOTALL)

#: A Markdown link to somewhere in the repository. External links are left to the
#: reader: this checks the ones a rename inside the tree can silently break.
_LINK: Final = re.compile(r"\[[^\]]*\]\((?P<target>[^)\s]+)\)")


class Block:
    """One fenced block, with what precedes it on the page."""

    __slots__ = ("body", "error_reason", "language", "skip_reason")

    def __init__(
        self, language: str, body: str, skip_reason: str | None, error_reason: str | None
    ) -> None:
        self.language = language
        self.body = body
        self.skip_reason = skip_reason
        self.error_reason = error_reason

    @property
    def runnable(self) -> bool:
        return self.language == "python" and self.skip_reason is None


#: Hand-written pages that live outside ``docs/``. The README is the most-read
#: page in the repository and it is also the PyPI landing page, since
#: ``readme = "README.md"`` in ``pyproject.toml`` makes it the wheel's long
#: description. It was the one page nothing executed, and it drifted -- so it
#: runs under the same harness as every guide: its snippets execute, its quoted
#: messages are compared against what the library actually produces, and its
#: relative links are resolved.
ROOT_PAGES: Final = ("README.md",)


def pages() -> list[Path]:
    """Every hand-written page, in a stable order."""
    return sorted(
        [path for path in DOCS.rglob("*.md") if path != GENERATED]
        + [REPO_ROOT / name for name in ROOT_PAGES]
    )


def blocks_of(page: Path) -> list[Block]:
    """The page's fenced blocks in document order, each carrying its directive."""
    text = page.read_text(encoding="utf-8")
    found: list[Block] = []
    for match in _FENCE.finditer(text):
        # The last non-blank line before the fence, and only that one. A wider
        # window would let a directive written for one block silently exempt a
        # later one; a narrower one would break the moment a blank line is added.
        preceding = text[: match.start()].rstrip()
        line = preceding.rsplit("\n", 1)[-1] if preceding else ""
        skip = SKIP_DIRECTIVE.search(line)
        expected = EXPECT_ERROR_DIRECTIVE.search(line)
        found.append(
            Block(
                match.group("language"),
                match.group("body"),
                skip.group("reason") if skip else None,
                expected.group("reason") if expected else None,
            )
        )
    return found


def _expected(page: Path) -> dict[int, str]:
    """What each runnable block claims to produce, keyed by its index."""
    found = blocks_of(page)
    return {
        index: found[index + 1].body.rstrip("\n")
        for index, block in enumerate(found)
        if block.runnable and index + 1 < len(found) and found[index + 1].language == "text"
    }


def _script(page: Path) -> str:
    """The page as one program: every runnable block, guarded and captured."""
    lines = [
        "import contextlib, io, json, sys",
        "from lovely_assertions import AssertionFailure",
        "CAPTURED = {}",
    ]
    for index, block in enumerate(blocks_of(page)):
        if not block.runnable:
            continue
        # Two levels, because the body is nested inside `try:` and then inside
        # `with`. Blank lines stay blank: an indented blank line is still blank,
        # but leaving the indentation off a *continuation* line would not be.
        indented = "\n".join(
            "        " + line if line.strip() else line for line in block.body.splitlines()
        )
        lines += [
            "_out = io.StringIO()",
            "try:",
            "    with contextlib.redirect_stdout(_out):",
            indented,
            "except AssertionFailure as _failure:",
            f'    CAPTURED[{index}] = ["failure", str(_failure)]',
            "else:",
            f'    CAPTURED[{index}] = ["output", _out.getvalue().strip()]',
        ]
    lines += ["sys.stdout.write(json.dumps(CAPTURED))"]
    return "\n".join(lines) + "\n"


def _run(page: Path) -> dict[int, tuple[str, str]] | str:
    """What each block produced, or the complaint if the page did not run.

    A page that fails to execute is one finding, not one per quoted result in
    it: returning the complaint rather than raising here keeps a single broken
    snippet from burying its own traceback under every other row.
    """
    with tempfile.TemporaryDirectory() as directory:
        # The script lives beside the working directory rather than in it. A page
        # that lists a directory would otherwise find this harness's own file in
        # its output -- documentation quoting an implementation detail of the
        # thing that checks it.
        script = Path(directory) / "page.py"
        workspace = Path(directory) / "workspace"
        workspace.mkdir()
        script.write_text(_script(page), encoding="utf-8")
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            # Run it *in* the empty workspace, so a page that asserts about a
            # missing file is somewhere the file is reliably missing, whatever
            # the repository happens to hold.
            cwd=workspace,
            # The parent environment, with `PYTHONPATH` overridden rather than
            # replaced. A minimal env is tempting for isolation and is wrong on
            # Windows, where the interpreter needs `SYSTEMROOT` to start at all;
            # overriding the one variable that could interfere is the isolation
            # actually needed here.
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
    if result.returncode != 0:
        return (
            f"{page.relative_to(REPO_ROOT)} does not run.\n{result.stderr}"
            f"\nThe pages are executable: fix the snippet, or mark the block "
            f"`<!-- docs-test: skip - why -->`."
        )
    return {int(key): (kind, text) for key, (kind, text) in json.loads(result.stdout).items()}


@pytest.fixture(scope="module")
def produced() -> dict[Path, dict[int, tuple[str, str]] | str]:
    """Run every page once, and keep what each of their blocks produced."""
    return {page: _run(page) for page in pages()}


@pytest.mark.parametrize(
    ("page", "index"),
    [(page, index) for page in pages() for index in sorted(_expected(page))],
    ids=lambda value: value.stem if isinstance(value, Path) else str(value),
)
def test_every_quoted_result_is_what_the_library_produces(
    page: Path, index: int, produced: dict[Path, dict[int, tuple[str, str]] | str]
) -> None:
    """One test per quoted result, so a failure names the block, not the tree."""
    outcome = produced[page]
    assert not isinstance(outcome, str), outcome
    expected = _expected(page)[index]
    actual = outcome[index][1]
    assert actual == expected, (
        f"{page.relative_to(REPO_ROOT)} quotes a result the library does not produce.\n"
        f"  quoted:   {expected!r}\n"
        f"  produced: {actual!r}\n"
        f"The page is executable; fix whichever of the two is wrong."
    )


def test_every_page_runs(produced: dict[Path, dict[int, tuple[str, str]] | str]) -> None:
    """A page whose snippets all fail to be collected would pass silently above.

    The parametrisation only reaches blocks that have a quoted result, so a page
    of snippets and no quotes contributes no rows at all. Running is the weaker
    claim and it is the one this makes: every page executes to the end.
    """
    assert set(produced) == set(pages())
    broken = [outcome for outcome in produced.values() if isinstance(outcome, str)]
    assert not broken, "\n\n".join(broken)


def test_the_pages_are_actually_being_checked() -> None:
    """A guard over an empty enumeration passes for the wrong reason.

    No exact count, because pages are added and quotes move; a floor catches the
    failure that matters, which is the enumeration silently finding nothing --
    a fence relabelled, a convention changed, a regex that stopped matching.
    """
    quoted = sum(len(_expected(page)) for page in pages())
    assert len(pages()) >= 10, f"only {len(pages())} pages found under docs/"
    assert quoted >= 40, f"only {quoted} quoted results found across the documentation"


def test_no_failure_goes_unquoted(produced: dict[Path, dict[int, tuple[str, str]] | str]) -> None:
    """A block that fails and quotes nothing reads as a block that passes.

    The comparison above only reaches blocks with a quoted result, so a snippet
    that raises an ``AssertionFailure`` nobody quotes is swallowed here and
    presented to the reader as working code. Either show what it produces, or
    mark it ``docs-test: skip`` because it is a fragment rather than an example.
    """
    silent = [
        f"{page.relative_to(REPO_ROOT)} block {index}: {text!r}"
        for page, outcome in produced.items()
        if not isinstance(outcome, str)
        for index, (kind, text) in outcome.items()
        if kind == "failure" and index not in _expected(page)
    ]
    assert not silent, (
        f"snippets that raise an assertion failure the page never quotes: {silent}. "
        f"Quote the message in a `text` block, or mark the block as a skipped fragment."
    )


def test_every_internal_link_resolves() -> None:
    """A documentation tree is mostly links, and a rename breaks them silently.

    Anchors are checked too, against the headings of the page they point into --
    a link to a section that has been retitled lands the reader at the top of a
    long page with no clue what they were meant to read.
    """
    broken: list[str] = []
    for page in [*pages(), GENERATED]:
        text = page.read_text(encoding="utf-8")
        # Fenced blocks and inline code spans come out first: `expect[T](...)`
        # is a type parameter followed by a call, not a link to a file named
        # "...".
        prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        prose = re.sub(r"`[^`\n]*`", "", prose)
        for match in _LINK.finditer(prose):
            target = match.group("target")
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = target.partition("#")
            destination = (page.parent / path).resolve() if path else page
            if not destination.is_file():
                broken.append(f"{page.relative_to(REPO_ROOT)} -> {target} (no such file)")
            elif anchor and anchor not in _anchors(destination):
                broken.append(f"{page.relative_to(REPO_ROOT)} -> {target} (no such heading)")
    assert not broken, "broken links in the documentation:\n  " + "\n  ".join(broken)


def _anchors(page: Path) -> set[str]:
    """The GitHub-style anchor of every heading on a page."""
    found: set[str] = set()
    for line in page.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            continue
        # GitHub lowercases, drops punctuation but keeps hyphens and
        # underscores, then turns spaces into hyphens. Backticks around a
        # method name disappear; the underscore inside it does not.
        heading = line.lstrip("#").strip().lower()
        found.add(re.sub(r"[^a-z0-9\s_-]", "", heading).replace(" ", "-"))
    return found


def test_no_fence_hides_inside_a_blockquote() -> None:
    """A quoted fence is invisible to the enumeration, and so is never checked.

    ``^```` anchors at the start of a line, so ``> ```python`` matches nothing and
    the block is neither run nor compared -- silently, which is the part that
    makes it worth a test. Un-quote the block, or the page grows an example that
    nothing verifies.
    """
    quoted = [
        f"{page.relative_to(REPO_ROOT)}:{number}"
        for page in pages()
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1)
        if line.lstrip().startswith(">") and "```" in line
    ]
    assert not quoted, (
        f"fenced blocks inside a blockquote, which nothing executes: {quoted}. "
        f"Take the block out of the quote."
    )


def test_no_exemption_has_gone_stale() -> None:
    """An exemption that stopped covering anything is an exemption to delete."""
    reasons = [
        (page.relative_to(REPO_ROOT), block.skip_reason)
        for page in pages()
        for block in blocks_of(page)
        if block.skip_reason is not None and block.language != "python"
    ]
    assert not reasons, (
        f"`docs-test: skip` on a block that was never going to run anyway: {reasons}. "
        f"Only a `python` block is executed."
    )


# ---------------------------------------------------------------------------
# The examples are type-checked, because typed discoverability is the product.
# ---------------------------------------------------------------------------

#: Suppressions for the artefacts of stitching a page's blocks into one module.
#: Each block is written to be self-contained, so a page that defines ``Order``
#: twice is two complete examples rather than a mistake -- and the imports repeat
#: for the same reason. Nothing here relaxes a rule about the *library's* types.
_STITCHING_ARTEFACTS: Final = {
    "reportRedeclaration": "none",
    "reportDuplicateImport": "none",
    "reportUnusedImport": "none",
    "reportUnusedExpression": "none",
    "reportMissingParameterType": "none",
    "reportUnknownParameterType": "none",
    "reportUnknownMemberType": "none",
    "reportUnknownVariableType": "none",
    "reportUnknownArgumentType": "none",
    "reportUnknownLambdaType": "none",
    "reportMissingTypeStubs": "none",
}


def _tool(name: str) -> str:
    """Resolve a checker from the active virtualenv, falling back to PATH."""
    candidate = Path(sys.executable).parent / name
    if candidate.exists():
        return str(candidate)
    found = shutil.which(name)
    if found is None:  # pragma: no cover - environment problem, not a test outcome
        pytest.fail(f"{name} is not installed; the documentation cannot be type-checked")
    return found


def _as_module(page: Path) -> tuple[str, set[int]]:
    """A page's runnable blocks as one module, and the lines allowed to error."""
    lines: list[str] = []
    permitted: set[int] = set()
    for block in blocks_of(page):
        if not block.runnable:
            continue
        body = block.body.rstrip("\n").splitlines()
        if block.error_reason is not None:
            permitted.update(range(len(lines) + 1, len(lines) + len(body) + 1))
        lines += body
    return "\n".join(lines) + "\n", permitted


@pytest.fixture(scope="module")
def checked() -> dict[str, list[tuple[int, str]]]:
    """Every pyright error over the documentation, keyed by module name."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "pyrightconfig.json").write_text(
            json.dumps(
                {
                    "typeCheckingMode": "strict",
                    "pythonVersion": "3.13",
                    # Explicit, because pyright does not read `PYTHONPATH`: without
                    # this it resolves the package from whatever interpreter it
                    # happens to find, and a miss would report an import error on
                    # every page rather than a missing path once.
                    "extraPaths": [str(REPO_ROOT / "src")],
                    **_STITCHING_ARTEFACTS,
                }
            ),
            encoding="utf-8",
        )
        for page in pages():
            source, _ = _as_module(page)
            if source.strip():
                (root / _module_name(page)).write_text(source, encoding="utf-8")
        result = subprocess.run(  # noqa: S603
            [_tool("pyright"), "--outputjson", "--project", str(root), str(root)],
            capture_output=True,
            # `encoding` explicitly rather than the host default: pyright indents
            # its continuation lines with U+00A0 and reports UTF-8 on every
            # platform, which a Windows ANSI code page turns into mojibake.
            text=True,
            encoding="utf-8",
            check=False,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:  # pragma: no cover - pyright crashed
            pytest.fail(f"pyright produced no JSON.\nstdout:\n{result.stdout}\n{result.stderr}")
        found: dict[str, list[tuple[int, str]]] = {}
        for diagnostic in payload["generalDiagnostics"]:
            if diagnostic["severity"] != "error":
                continue
            name = Path(diagnostic["file"]).name
            line = diagnostic["range"]["start"]["line"] + 1
            found.setdefault(name, []).append((line, diagnostic["message"].splitlines()[0]))
        return found


def _module_name(page: Path) -> str:
    """A filename for the page, unique across the tree and legal as a module.

    Built from ``.parts`` rather than from the rendered path: ``str(Path)`` uses a
    backslash on Windows, so replacing ``"/"`` there changes nothing and the
    separator survives into a filename -- which then names a subdirectory that was
    never created.
    """
    relative = page.relative_to(REPO_ROOT)
    return "__".join(relative.with_suffix("").parts).replace("-", "_") + ".py"


@pytest.mark.parametrize("page", pages(), ids=lambda page: page.stem)
def test_every_example_type_checks(page: Path, checked: dict[str, list[tuple[int, str]]]) -> None:
    """A page of examples a checker rejects would refute the library's own claim.

    Typed discoverability is the first thing this package sells, so an example
    that does not check is not a cosmetic problem -- it is the documentation
    demonstrating the opposite of the pitch. A block that is *supposed* to be
    rejected says so with ``docs-test: expect-error``.
    """
    _, permitted = _as_module(page)
    unexpected = [
        f"line {line}: {message}"
        for line, message in checked.get(_module_name(page), [])
        if line not in permitted
    ]
    assert not unexpected, (
        f"pyright rejects examples in {page.relative_to(REPO_ROOT)}:\n  "
        + "\n  ".join(unexpected)
        + "\nFix the example, or mark its block `<!-- docs-test: expect-error - why -->`."
    )


def test_no_expect_error_block_has_started_checking(
    checked: dict[str, list[tuple[int, str]]],
) -> None:
    """An exemption that stopped covering an error is an exemption to delete.

    Without this, a block marked as deliberately unsound keeps its licence long
    after the unsoundness is gone -- and the next real error inside it is waved
    through.
    """
    stale: list[str] = []
    for page in pages():
        _, permitted = _as_module(page)
        if not permitted:
            continue
        erroring = {line for line, _ in checked.get(_module_name(page), [])}
        if not permitted & erroring:
            stale.append(str(page.relative_to(REPO_ROOT)))
    assert not stale, (
        f"`docs-test: expect-error` on a block pyright now accepts: {stale}. Remove the directive."
    )
